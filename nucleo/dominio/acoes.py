"""Ações compostas sobre a conversa: rotear, escalar e montar o contexto da IA."""

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nucleo import config
from nucleo.dominio.roteador import rotear
from nucleo.dominio.sla import limite_da_fila
from nucleo.dominio.transicionar import (
    SISTEMA,
    Ator,
    Resultado,
    auditar,
    para_canal,
    transicionar,
)

MSG_TRANSFERENCIA = {
    "pt": "Vou te transferir para um especialista. Ele já recebe todo o histórico da conversa.",
    "en": "I'm transferring you to a specialist, who will see the full conversation history.",
}
MSG_ESPERA = {
    "pt": {0: "Um especialista já vai te atender.", 1: "Tempo estimado de espera: cerca de {m} min."},
    "en": {0: "A specialist will be with you shortly.", 1: "Estimated wait: about {m} min."},
}


async def estimar_espera(s: AsyncSession, marca: str) -> int:
    """Segundos até um analista da marca pegar uma nova escala.

    Vagas livres agora (capacidade menos conversas) atendem na hora. Sem vaga, a escala espera a
    vez: (escalas na frente - vagas + 1) / capacidade total, em rodadas do tempo médio de
    atendimento humano das últimas 24 h da marca; sem histórico, `ATENDIMENTO_HUMANO_S`
    (hipótese). É uma estimativa, não uma promessa: o texto ao cliente diz "cerca de".
    """
    r = await s.execute(text(
        "SELECT coalesce(sum(capacidade), 0), coalesce(sum(greatest(capacidade - ativas, 0)), 0) "
        "FROM atendentes WHERE tipo = 'humano' AND marca = :m AND status = 'disponivel'"), {"m": marca})
    capacidade, livres = r.one()
    frente = (await s.execute(text(
        "SELECT count(*) FROM conversas WHERE marca = :m AND estado = 'escalada'"), {"m": marca})).scalar()
    if livres > frente:
        return 0
    media = (await s.execute(text(
        "SELECT avg(extract(epoch FROM t.fim - t.inicio)) FROM atribuicoes t "
        "JOIN atendentes a ON a.id = t.id_atendente JOIN conversas c ON c.id = t.id_conversa "
        "WHERE a.tipo = 'humano' AND c.marca = :m AND t.fim > now() - interval '24 hours'"), {"m": marca})).scalar()
    media = float(media) if media else config.ATENDIMENTO_HUMANO_S
    rodadas = -(-(frente - livres + 1) // max(int(capacidade), 1))
    return int(rodadas * media)


def texto_espera(idioma: str, segundos: int) -> str:
    textos = MSG_ESPERA.get(idioma or "pt", MSG_ESPERA["pt"])
    if segundos <= 0:
        return textos[0]
    return textos[1].format(m=max(1, round(segundos / 60)))


async def regras_ativas(s: AsyncSession) -> tuple[dict, int]:
    r = await s.execute(text("SELECT numero, filas FROM versoes_regras WHERE ativa"))
    linha = r.first()
    if linha is None:
        raise RuntimeError("nenhuma versão de regras ativa")
    return linha[1], linha[0]


async def atendimento_de(s: AsyncSession, c: dict) -> dict:
    r = await s.execute(text("SELECT segmento FROM clientes WHERE id = :id"), {"id": c["id_cliente"]})
    segmento = r.scalar()
    return {
        "marca": c["marca"], "canal": c["canal"], "categoria": c["categoria"],
        "prioridade": c["prioridade"], "idioma": c["idioma"], "sentimento": c["sentimento"],
        "origem": c["origem"], "segmento_cliente": segmento,
    }


async def rotear_conversa(s: AsyncSession, c: dict, ator: Ator = SISTEMA) -> str:
    """Roteia e grava a fila e o registro de decisão. Chamado com a conversa já travada."""
    regras, versao = await regras_ativas(s)
    atendimento = await atendimento_de(s, c)
    decisao = rotear(atendimento, regras, versao)
    fila = next((f for f in regras["filas"] if f["id"] == decisao.fila), None)
    limite = limite_da_fila(fila, c.get("prioridade"))
    await s.execute(
        text("UPDATE conversas SET id_fila = :f, versao_regras = :v, sla_limite_s = :l WHERE id = :id"),
        {"f": decisao.fila, "v": versao, "l": limite, "id": c["id"]},
    )
    c["id_fila"], c["versao_regras"], c["sla_limite_s"] = decisao.fila, versao, limite
    await auditar(s, "decisao_roteamento", ator, c["id"], atendimento=atendimento,
                  versao=versao, fila=decisao.fila, regra=decisao.regra)
    return decisao.fila


async def ultimas_mensagens(s: AsyncSession, id_conversa, n: int) -> list[dict]:
    r = await s.execute(
        text(
            "SELECT id, autor_tipo, conteudo, canal, seq, criada_em FROM mensagens "
            "WHERE id_conversa = :c ORDER BY seq DESC NULLS LAST LIMIT :n"
        ),
        {"c": id_conversa, "n": n},
    )
    return [
        {"id": str(m["id"]), "autor": m["autor_tipo"], "conteudo": m["conteudo"],
         "canal": m["canal"], "seq": m["seq"], "criada_em": m["criada_em"].isoformat()}
        for m in reversed(r.mappings().all())
    ]


async def perfil_operacional(s: AsyncSession, c: dict) -> dict:
    """Só fatos sobre o cliente na marca; nenhum texto inferido."""
    r = await s.execute(
        text(
            """
            SELECT
              count(*) FILTER (WHERE criada_em > now() - make_interval(days => :j)) AS contatos,
              count(*) FILTER (WHERE origem = 'escalado' AND criada_em > now() - make_interval(days => :j)) AS escalas,
              mode() WITHIN GROUP (ORDER BY canal) AS canal_preferido
            FROM conversas WHERE id_cliente = :cli AND marca = :m AND id <> :id
            """
        ),
        {"j": config.PERFIL_JANELA_DIAS, "cli": c["id_cliente"], "m": c["marca"], "id": c["id"]},
    )
    agg = r.mappings().first()
    r2 = await s.execute(
        text(
            "SELECT categoria, resolvida_em FROM conversas WHERE id_cliente = :cli AND marca = :m "
            "AND estado = 'resolvida' ORDER BY resolvida_em DESC LIMIT 1"
        ),
        {"cli": c["id_cliente"], "m": c["marca"]},
    )
    ultimo = r2.mappings().first()
    r3 = await s.execute(text("SELECT produtos, segmento FROM clientes WHERE id = :id"), {"id": c["id_cliente"]})
    cli = r3.mappings().first()
    return {
        "produtos": list(cli["produtos"] or []),
        "segmento": cli["segmento"],
        "contatos_30d": agg["contatos"],
        "escalas_30d": agg["escalas"],
        "canal_preferido": agg["canal_preferido"],
        "ultimo_assunto": (
            {"categoria": ultimo["categoria"], "data": ultimo["resolvida_em"].date().isoformat()}
            if ultimo and ultimo["resolvida_em"] else None
        ),
    }


async def contexto_para_ia(s: AsyncSession, c: dict) -> dict:
    r = await s.execute(
        text("SELECT id, nome, segmento FROM clientes WHERE id = :id"), {"id": c["id_cliente"]}
    )
    cli = r.mappings().first()
    return {
        "cliente": {"id": str(cli["id"]), "nome": cli["nome"], "segmento": cli["segmento"]},
        "fila": c["id_fila"],
        "triagem": {"categoria": c["categoria"], "prioridade": c["prioridade"],
                    "sentimento": c["sentimento"], "idioma": c["idioma"]},
        "historico": await ultimas_mensagens(s, c["id"], config.HISTORICO_N),
        "perfil": await perfil_operacional(s, c),
    }


async def resumo_de_reserva(s: AsyncSession, c: dict) -> tuple[str, list[str]]:
    """Extrativo: triagem + últimas mensagens do cliente. Não inventa texto."""
    msgs = await ultimas_mensagens(s, c["id"], 6)
    do_cliente = [m for m in msgs if m["autor"] == "cliente"][-3:]
    linhas = [f"Categoria: {c['categoria']}; prioridade: {c['prioridade']}; sentimento: {c['sentimento']}."]
    linhas += [f"Cliente: {m['conteudo']}" for m in do_cliente]
    return " ".join(linhas), [m["id"] for m in do_cliente]


async def escalar(
    s: AsyncSession,
    id_conversa,
    ator: Ator,
    motivo: str,
    *,
    id_atribuicao=None,
    resumo: str | None = None,
    fontes: list | None = None,
    prioridade_sugerida: int | None = None,
    causado_por=None,
) -> Resultado:
    """com_ia ou na_fila -> escalada, volta ao roteador com origem = escalado e avisa o cliente,
    com o tempo estimado de espera (`estimar_espera`), gravado também na escala.

    A mensagem de transferência leva `causado_por` = evento que escalou, para o juiz do
    experimento contar a escala na ponta (o cliente vê "vou te transferir").
    """

    espera: dict = {}

    async def aviso(s2, c):
        espera["s"] = await estimar_espera(s2, c["marca"])
        idioma = c["idioma"] or "pt"
        texto = f"{MSG_TRANSFERENCIA.get(idioma)} {texto_espera(idioma, espera['s'])}"
        return [para_canal(c, "sistema", texto, causado_por=causado_por)]

    resultado, c = await transicionar(
        s, id_conversa, "escalada", ator, id_atribuicao=id_atribuicao, motivo=motivo, saidas=aviso,
        mensagem=None,
    )
    if resultado != Resultado.APLICADO:
        return resultado
    reserva = resumo is None
    if reserva:
        resumo, fontes = await resumo_de_reserva(s, c)
    if prioridade_sugerida in (1, 2, 3) and (c["prioridade"] or 1) < prioridade_sugerida:
        await s.execute(text("UPDATE conversas SET prioridade = :p WHERE id = :id"),
                        {"p": prioridade_sugerida, "id": c["id"]})
        c["prioridade"] = prioridade_sugerida
    await s.execute(
        text(
            "INSERT INTO escalas (id_conversa, motivo, resumo, fontes, reserva, prioridade, tempo_estimado_s) "
            "VALUES (:c, :m, :r, CAST(:f AS jsonb), :res, :p, :eta)"
        ),
        {"c": c["id"], "m": motivo, "r": resumo, "f": json.dumps(fontes or []), "res": reserva,
         "p": c["prioridade"], "eta": espera.get("s")},
    )
    await rotear_conversa(s, c, ator)
    return resultado
