"""Único caminho que escreve na conversa (docs/arquitetura.md 11.2, docs/implementacao.md 7.1).

Numa transação aberta por quem chama:
1. trava a conversa (FOR UPDATE);
2. fencing: evento de atribuição vencida é descartado e auditado;
3. confere a transição em transicoes_permitidas;
4. confere a capacidade do novo dono ANTES de encerrar a atribuição atual;
5. grava estado, mensagem, auditoria e saídas (outbox) juntos.
Nunca levanta exceção por regra de negócio: devolve um Resultado. Nenhuma chamada HTTP aqui.
Ordem de travas: conversa -> atendente novo -> agendamentos e atendente antigo (ao encerrar).
A trava da conversa serializa tudo o que mexe nela, então não há ciclo entre duas transações.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nucleo import config


class Resultado(str, Enum):
    APLICADO = "aplicado"
    DESCARTADO = "descartado"
    REJEITADO = "rejeitado"
    SEM_CAPACIDADE = "sem_capacidade"
    INEXISTENTE = "inexistente"


@dataclass(frozen=True)
class Ator:
    tipo: str  # cliente, ia, humano, sistema
    id: uuid.UUID | None = None


SISTEMA = Ator("sistema")


@dataclass
class Saida:
    destino: str  # broker ou canal
    payload: dict
    id_evento: uuid.UUID = field(default_factory=uuid.uuid4)
    tipo: str = ""
    id_atribuicao: uuid.UUID | None = None
    id_conversa: uuid.UUID | None = None


ESTADOS_COM_DONO = ("com_ia", "com_humano")


def agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def novo_evento(tipo: str, conversa: dict, dados: dict, causado_por=None) -> Saida:
    """Evento para o agente; id_atribuicao é preenchido pelo transicionar sob a trava."""
    id_evento = uuid.uuid4()
    payload = {
        "versao": "1.0",
        "id_evento": str(id_evento),
        "tipo": tipo,
        "id_conversa": str(conversa["id"]),
        "id_atribuicao": None,
        "causado_por": str(causado_por) if causado_por else None,
        "marca": conversa["marca"],
        "timestamp": agora_iso(),
        "dados": dados,
    }
    return Saida(destino="broker", payload=payload, id_evento=id_evento, tipo=tipo)


def para_canal(conversa: dict, autor: str, conteudo: str, causado_por=None, sequencia=0) -> Saida:
    id_evento = uuid.uuid4()
    payload = {
        "id_evento": str(id_evento),
        "id_conversa": str(conversa["id"]),
        "canal": conversa["canal"],
        "marca": conversa["marca"],
        "autor": autor,
        "conteudo": conteudo,
        "causado_por": str(causado_por) if causado_por else None,
        "sequencia": sequencia,
        "timestamp": agora_iso(),
    }
    return Saida(destino="canal", payload=payload, id_evento=id_evento, tipo="entrega")


async def auditar(s: AsyncSession, tipo: str, ator: Ator, id_conversa=None, id_atribuicao=None,
                  id_evento=None, **payload: Any) -> None:
    await s.execute(
        text(
            "INSERT INTO eventos (id_evento, tipo, ator_tipo, id_ator, id_conversa, id_atribuicao, payload) "
            "VALUES (:e, :t, :at, :ai, :c, :a, CAST(:p AS jsonb))"
        ),
        {
            "e": id_evento, "t": tipo, "at": ator.tipo, "ai": ator.id, "c": id_conversa,
            "a": id_atribuicao, "p": json.dumps(payload, default=str),
        },
    )


async def _permitida(s, de: str, para: str, ator_tipo: str) -> bool:
    r = await s.execute(
        text("SELECT 1 FROM transicoes_permitidas WHERE de = :d AND para = :p AND ator_tipo = :a"),
        {"d": de, "p": para, "a": ator_tipo},
    )
    return r.first() is not None


async def _atendente_com_capacidade(s, id_atendente) -> dict | None:
    """Trava a linha do atendente e confere a capacidade. A IA conta só como limite de custo."""
    r = await s.execute(
        text("SELECT * FROM atendentes WHERE id = :id FOR UPDATE"), {"id": id_atendente}
    )
    a = r.mappings().first()
    if a is None or a["status"] != "disponivel" or a["ativas"] >= a["capacidade"]:
        return None
    return dict(a)


async def encerrar_atribuicao(s, c: dict, motivo: str | None) -> None:
    r = await s.execute(
        text(
            "UPDATE atribuicoes SET fim = now(), motivo_fim = :m WHERE id = :id AND fim IS NULL "
            "RETURNING id_atendente"
        ),
        {"id": c["id_atribuicao_atual"], "m": motivo or "transicao"},
    )
    linha = r.first()
    await s.execute(
        text(
            "UPDATE agendamentos SET status = 'cancelado', motivo_fim = 'atribuicao_encerrada', "
            "finalizado_em = now() WHERE id_atribuicao = :a AND status = 'pendente'"
        ),
        {"a": c["id_atribuicao_atual"]},
    )
    if linha:
        await s.execute(
            text("UPDATE atendentes SET ativas = greatest(ativas - 1, 0) WHERE id = :id"),
            {"id": linha[0]},
        )


async def transicionar(
    s: AsyncSession,
    id_conversa,
    para: str | None,
    ator: Ator,
    *,
    id_atribuicao=None,
    id_atendente=None,
    id_fila: str | None = None,
    mensagem: dict | None = None,
    saidas: Callable[[AsyncSession, dict], Awaitable[list[Saida]]] | None = None,
    motivo: str | None = None,
    campos: dict | None = None,
) -> tuple[Resultado, dict | None]:
    r = await s.execute(text("SELECT * FROM conversas WHERE id = :id FOR UPDATE"), {"id": id_conversa})
    linha = r.mappings().first()
    if linha is None:
        return Resultado.INEXISTENTE, None
    c = dict(linha)

    if config.FENCING_ATIVO and id_atribuicao is not None and id_atribuicao != c["id_atribuicao_atual"]:
        await auditar(s, "evento_descartado", ator, c["id"], id_atribuicao,
                      motivo="atribuicao_vencida", atual=c["id_atribuicao_atual"])
        return Resultado.DESCARTADO, c

    mudancas: dict[str, Any] = dict(campos or {})
    if para is not None:
        if not await _permitida(s, c["estado"], para, ator.tipo):
            await auditar(s, "transicao_invalida", ator, c["id"], id_atribuicao, de=c["estado"], para=para)
            return Resultado.REJEITADO, c
        atende = para in ESTADOS_COM_DONO
        novo_dono = None
        if atende:
            novo_dono = await _atendente_com_capacidade(s, id_atendente)
            if novo_dono is None:
                await auditar(s, "sem_capacidade", ator, c["id"], id_atribuicao, atendente=id_atendente)
                return Resultado.SEM_CAPACIDADE, c
        if c["id_atribuicao_atual"] is not None:
            await encerrar_atribuicao(s, c, motivo)
            mudancas.update(id_atribuicao_atual=None, id_atendente=None)
        if atende:
            nova = uuid.uuid4()
            await s.execute(
                text(
                    "INSERT INTO atribuicoes (id, id_conversa, id_fila, id_atendente) "
                    "VALUES (:id, :c, :f, :a)"
                ),
                {"id": nova, "c": c["id"], "f": id_fila or c["id_fila"], "a": novo_dono["id"]},
            )
            await s.execute(
                text("UPDATE atendentes SET ativas = ativas + 1 WHERE id = :id"), {"id": novo_dono["id"]}
            )
            mudancas.update(id_atribuicao_atual=nova, id_atendente=novo_dono["id"])
        if para == "escalada":
            mudancas["origem"] = "escalado"
        if para in ("na_fila", "escalada"):
            mudancas["na_fila_desde"] = datetime.now(timezone.utc)
        if para == "resolvida":
            mudancas["motivo_encerramento"] = "inatividade" if motivo == "inatividade" else "resolvida"
            mudancas["resolvida_em"] = datetime.now(timezone.utc)
        mudancas["estado"] = para
        mudancas["versao"] = c["versao"] + 1

    c.update(mudancas)

    if mensagem is not None:
        c["seq_mensagem"] = c["seq_mensagem"] + 1
        mudancas["seq_mensagem"] = c["seq_mensagem"]
        m = dict(mensagem)
        m.setdefault("id", uuid.uuid4())
        m.setdefault("canal", c["canal"])
        await s.execute(
            text(
                "INSERT INTO mensagens (id, id_conversa, autor_tipo, id_autor, conteudo, canal, id_externo, "
                "id_evento, causado_por, sequencia, id_atribuicao_declarada, id_atribuicao, seq) VALUES "
                "(:id, :c, :autor, :id_autor, :conteudo, :canal, :id_externo, :id_evento, :causado_por, "
                ":sequencia, :declarada, :vigente, :seq)"
            ),
            {
                "id": m["id"], "c": c["id"], "autor": m["autor_tipo"], "id_autor": m.get("id_autor"),
                "conteudo": m["conteudo"], "canal": m["canal"], "id_externo": m.get("id_externo"),
                "id_evento": m.get("id_evento"), "causado_por": m.get("causado_por"),
                "sequencia": m.get("sequencia", 0), "declarada": id_atribuicao,
                "vigente": c["id_atribuicao_atual"], "seq": c["seq_mensagem"],
            },
        )
        c["_id_mensagem"] = m["id"]

    lista = await saidas(s, c) if saidas else []
    for saida in lista:
        if saida.destino == "broker":
            saida.payload["id_atribuicao"] = (
                str(c["id_atribuicao_atual"]) if c["id_atribuicao_atual"] else None
            )
        saida.id_atribuicao = c["id_atribuicao_atual"]
        saida.id_conversa = c["id"]
        c["seq_outbox"] = c["seq_outbox"] + 1
        mudancas["seq_outbox"] = c["seq_outbox"]
        if config.OUTBOX_ATIVA:
            await s.execute(
                text(
                    "INSERT INTO outbox (id_evento, id_conversa, id_atribuicao, sequencia, destino, payload) "
                    "VALUES (:e, :c, :a, :seq, :d, CAST(:p AS jsonb))"
                ),
                {
                    "e": saida.id_evento, "c": c["id"], "a": c["id_atribuicao_atual"],
                    "seq": c["seq_outbox"], "d": saida.destino, "p": json.dumps(saida.payload, default=str),
                },
            )
        else:
            s.info.setdefault("diretos", []).append(saida)

    mudancas["atualizada_em"] = datetime.now(timezone.utc)
    sets = ", ".join(f"{k} = :{k}" for k in mudancas)
    await s.execute(text(f"UPDATE conversas SET {sets} WHERE id = :id_conversa"),
                    {**mudancas, "id_conversa": c["id"]})

    await auditar(
        s, "transicao" if para else "mensagem", ator, c["id"], c["id_atribuicao_atual"],
        para=para, motivo=motivo, saidas=[x.tipo for x in lista],
    )
    return Resultado.APLICADO, c
