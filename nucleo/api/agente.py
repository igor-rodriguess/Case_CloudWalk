"""API do agente: recebe os eventos que o broker consome de `agente.para-helpdesk`.

Responde 200 para duplicata, descarte por fencing, transição inválida e tipo desconhecido
(tudo auditado), para o broker não reenviar para sempre. 422 para esquema inválido.
503 quando o banco está fora (tratado no main). Nunca 500 por regra de negócio.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from contrato import Envelope
from nucleo import config
from nucleo.dominio.acoes import escalar
from nucleo.dominio.transicionar import Ator, Resultado, auditar, para_canal, transicionar
from nucleo.infra.banco import unidade

router = APIRouter(tags=["agente"])
log = logging.getLogger("api.agente")


async def _cancelar_prazos(s, env: Envelope) -> None:
    """A resposta a uma mensagem cobre as anteriores da mesma atribuição."""
    await s.execute(
        text(
            """
            UPDATE agendamentos SET status = 'cancelado', motivo_fim = 'resposta', finalizado_em = now()
            WHERE tipo = 'timeout_agente' AND status = 'pendente' AND id_atribuicao = :a
              AND criado_em <= coalesce(
                  (SELECT criado_em FROM agendamentos WHERE referencia = :ref AND tipo = 'timeout_agente'
                   ORDER BY criado_em DESC LIMIT 1), now())
            """
        ),
        {"a": env.id_atribuicao, "ref": env.causado_por},
    )


async def _aplicar(s, env: Envelope) -> str:
    ator = Ator("ia")
    if env.tipo == "mensagem.enviada":
        conteudo = str(env.dados.get("conteudo", ""))
        sequencia = int(env.dados.get("sequencia", 0))

        async def saidas(s2, c):
            return [para_canal(c, "ia", conteudo, causado_por=env.causado_por, sequencia=sequencia)]

        resultado, _ = await transicionar(
            s, env.id_conversa, None, ator, id_atribuicao=env.id_atribuicao, saidas=saidas,
            mensagem={"autor_tipo": "ia", "conteudo": conteudo, "id_evento": env.id_evento,
                      "causado_por": env.causado_por, "sequencia": sequencia},
        )
        if resultado == Resultado.APLICADO:
            await _cancelar_prazos(s, env)
        return resultado.value

    if env.tipo == "conversa.escalada":
        await _cancelar_prazos(s, env)
        resultado = await escalar(
            s, env.id_conversa, ator, str(env.dados.get("motivo", "agente")),
            id_atribuicao=env.id_atribuicao, resumo=env.dados.get("resumo"),
            fontes=env.dados.get("fontes"), prioridade_sugerida=env.dados.get("prioridade_sugerida"),
            causado_por=env.id_evento,
        )
        return resultado.value

    if env.tipo == "conversa.resolvida":
        await _cancelar_prazos(s, env)
        resultado, _ = await transicionar(
            s, env.id_conversa, "resolvida", ator, id_atribuicao=env.id_atribuicao, motivo="resolvida"
        )
        return resultado.value

    # acao.executada e agente.processando (heartbeat fica como evolução): só auditoria
    r = await s.execute(text("SELECT id_atribuicao_atual FROM conversas WHERE id = :c"), {"c": env.id_conversa})
    vigente = r.scalar()
    fora = config.FENCING_ATIVO and vigente != env.id_atribuicao
    await auditar(s, env.tipo, ator, env.id_conversa, env.id_atribuicao, id_evento=env.id_evento,
                  dados=env.dados, fora_da_atribuicao=fora)
    return "auditado"


@router.post("/agente/eventos", summary="Evento do agente (chamado pelo broker)")
async def receber(request: Request):
    corpo = await request.json()
    try:
        env = Envelope.model_validate(corpo)
    except ValidationError as e:
        so_tipo = all(err["loc"] and err["loc"][0] == "tipo" for err in e.errors())
        if so_tipo:  # tipo de uma versão 1.x mais nova: audita e confirma
            async with unidade() as s:
                await auditar(s, "evento_desconhecido", Ator("ia"), corpo.get("id_conversa"),
                              tipo_recebido=corpo.get("tipo"), versao=corpo.get("versao"))
            return {"resultado": "tipo_desconhecido"}
        return JSONResponse(status_code=422, content={"erro": "esquema", "detalhes": e.errors(include_url=False)})

    try:
        async with unidade() as s:
            if config.INBOX_ATIVA:
                r = await s.execute(
                    text(
                        "INSERT INTO eventos_processados (consumidor, id_evento) VALUES ('nucleo', :e) "
                        "ON CONFLICT DO NOTHING RETURNING 1"
                    ),
                    {"e": env.id_evento},
                )
                if r.first() is None:
                    return {"resultado": "duplicado"}
            resultado = await _aplicar(s, env)
    except IntegrityError:
        # Só acontece com a inbox desligada: id_evento repetido em mensagens. Log e segue.
        log.warning("evento %s repetido (inbox desligada)", env.id_evento)
        return {"resultado": "repetido_sem_inbox"}
    return {"resultado": resultado}
