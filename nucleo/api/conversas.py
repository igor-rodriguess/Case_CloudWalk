"""Leitura de conversas: lista, detalhe com histórico, auditoria, escalas e perfil."""

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from nucleo.dominio.acoes import perfil_operacional
from nucleo.infra.banco import Sessao, escopo_marca

router = APIRouter(prefix="/conversas", tags=["conversas"])


@router.get("", summary="Lista de conversas")
async def listar(estado: str | None = None, marca: str | None = None, limite: int = 100):
    async with Sessao() as s:
        await escopo_marca(s, marca)
        r = await s.execute(
            text(
                """
                SELECT c.id, c.marca, c.canal, c.estado, c.categoria, c.prioridade, c.sentimento, c.origem,
                       c.id_fila, c.id_atendente, a.nome AS atendente, cl.nome AS cliente,
                       c.criada_em, c.atualizada_em
                FROM conversas c JOIN clientes cl ON cl.id = c.id_cliente
                LEFT JOIN atendentes a ON a.id = c.id_atendente
                WHERE (CAST(:estado AS text) IS NULL OR c.estado = :estado)
                  AND (CAST(:marca AS text) IS NULL OR c.marca = :marca)
                ORDER BY c.atualizada_em DESC LIMIT :limite
                """
            ),
            {"estado": estado, "marca": marca, "limite": min(limite, 500)},
        )
        return [dict(x) for x in r.mappings().all()]


@router.get("/{id_conversa}", summary="Conversa com mensagens, auditoria, escalas e perfil")
async def detalhe(id_conversa: uuid.UUID, marca: str | None = None):
    """Com `marca`, a leitura roda isolada pela marca: conversa de outra marca dá 404."""
    async with Sessao() as s:
        await escopo_marca(s, marca)
        r = await s.execute(
            text(
                "SELECT c.*, cl.nome AS cliente, a.nome AS atendente FROM conversas c "
                "JOIN clientes cl ON cl.id = c.id_cliente LEFT JOIN atendentes a ON a.id = c.id_atendente "
                "WHERE c.id = :id"
            ),
            {"id": id_conversa},
        )
        c = r.mappings().first()
        if c is None:
            raise HTTPException(404, "conversa não existe")
        conversa = dict(c)
        mensagens = await s.execute(
            text(
                "SELECT id, autor_tipo, id_autor, conteudo, canal, id_externo, seq, criada_em "
                "FROM mensagens WHERE id_conversa = :id ORDER BY seq NULLS FIRST, criada_em"
            ),
            {"id": id_conversa},
        )
        eventos = await s.execute(
            text(
                "SELECT tipo, ator_tipo, id_ator, id_atribuicao, payload, criado_em FROM eventos "
                "WHERE id_conversa = :id ORDER BY id"
            ),
            {"id": id_conversa},
        )
        escalas = await s.execute(
            text("SELECT motivo, resumo, fontes, reserva, prioridade, criada_em FROM escalas "
                 "WHERE id_conversa = :id ORDER BY criada_em"),
            {"id": id_conversa},
        )
        return {
            "conversa": conversa,
            "mensagens": [dict(x) for x in mensagens.mappings().all()],
            "auditoria": [dict(x) for x in eventos.mappings().all()],
            "escalas": [dict(x) for x in escalas.mappings().all()],
            "perfil": await perfil_operacional(s, conversa),
        }


@router.get("/{id_conversa}/traco/{id_mensagem}", summary="Trace de uma mensagem do cliente, ponta a ponta")
async def traco(id_conversa: uuid.UUID, id_mensagem: uuid.UUID):
    """Um trace por mensagem do cliente, ligado pelos ids que já viajam no contrato:
    canal (id_externo) -> núcleo (mensagem) -> outbox -> broker/Kafka (ack = enviado_em) ->
    agente (resposta com causado_por = evento) -> núcleo -> outbox -> canal (entrega).
    Cada salto traz o horário; `ms` é o tempo desde a chegada da mensagem."""
    import httpx

    from nucleo import config

    async with Sessao() as s:
        m = (await s.execute(text(
            "SELECT id, id_externo, canal, conteudo, criada_em FROM mensagens "
            "WHERE id = :m AND id_conversa = :c AND autor_tipo = 'cliente'"), {"m": id_mensagem, "c": id_conversa})
        ).mappings().first()
        if m is None:
            raise HTTPException(404, "mensagem do cliente não existe nesta conversa")
        ida = (await s.execute(text(
            """
            SELECT id_evento::text, payload->>'tipo' AS tipo, criado_em, enviado_em, status, tentativas
            FROM outbox WHERE id_conversa = :c AND destino = 'broker'
              AND (payload->'dados'->>'id_mensagem' = :m
                   OR payload->'dados'->'historico' @> jsonb_build_array(jsonb_build_object('id', CAST(:m AS text))))
            ORDER BY criado_em
            """), {"c": id_conversa, "m": str(id_mensagem)})).mappings().all()
        eventos = [x["id_evento"] for x in ida]
        respostas = (await s.execute(text(
            "SELECT id, autor_tipo, id_evento::text, causado_por::text, sequencia, criada_em FROM mensagens "
            "WHERE id_conversa = :c AND causado_por::text = ANY(:e) ORDER BY seq"),
            {"c": id_conversa, "e": eventos})).mappings().all()
        volta = (await s.execute(text(
            "SELECT id_evento::text, payload->>'causado_por' AS causado_por, criado_em, enviado_em, status "
            "FROM outbox WHERE id_conversa = :c AND destino = 'canal' AND payload->>'causado_por' = ANY(:e) "
            "ORDER BY criado_em"), {"c": id_conversa, "e": eventos})).mappings().all()
    entregas = []
    try:
        async with httpx.AsyncClient(timeout=3) as h:
            r = await h.get(f"{config.CANAIS_URL}/entregas", params={"id_conversa": str(id_conversa)})
            entregas = [e for e in r.json() if e.get("causado_por") in eventos]
    except (httpx.HTTPError, ValueError):
        pass  # o canal fora não impede o resto do trace

    t0 = m["criada_em"]

    def salto(onde, o_que, quando, **extra):
        if quando is None:
            return None
        if isinstance(quando, str):
            from datetime import datetime

            quando = datetime.fromisoformat(quando)
        return {"onde": onde, "o_que": o_que, "quando": quando.isoformat(),
                "ms": round((quando - t0).total_seconds() * 1000), **extra}

    saltos = [salto("canal -> núcleo", "mensagem recebida e gravada", t0, id_externo=m["id_externo"])]
    for e in ida:
        saltos.append(salto("núcleo", f"{e['tipo']} gravado na outbox", e["criado_em"], id_evento=e["id_evento"]))
        saltos.append(salto("broker -> Kafka", "webhook aceito (ack do Kafka)", e["enviado_em"],
                            id_evento=e["id_evento"], tentativas=e["tentativas"]))
    for r in respostas:
        saltos.append(salto("agente -> broker -> núcleo", f"resposta da {r['autor_tipo']} gravada", r["criada_em"],
                            id_evento=r["id_evento"], causado_por=r["causado_por"], sequencia=r["sequencia"]))
    for v in volta:
        saltos.append(salto("núcleo -> canal", "saída enviada ao canal", v["enviado_em"], id_evento=v["id_evento"]))
    for e in entregas:
        saltos.append(salto("canal", "entregue ao cliente", e["recebida_em"], id_evento=e["id_evento"]))
    saltos = sorted((x for x in saltos if x), key=lambda x: x["ms"])
    return {"id_mensagem": str(id_mensagem), "id_externo": m["id_externo"], "conteudo": m["conteudo"],
            "eventos_ao_agente": eventos, "saltos": saltos,
            "ponta_a_ponta_ms": saltos[-1]["ms"] if entregas else None}
