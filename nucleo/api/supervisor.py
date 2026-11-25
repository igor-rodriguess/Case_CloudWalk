"""Supervisor: saúde da operação, fila de erros da outbox e reconciliação de invariantes."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from nucleo import config
from nucleo.infra.banco import Sessao, unidade
from nucleo.infra.relay import reprocessar
from nucleo.reconciliacao import reconciliar

router = APIRouter(tags=["supervisor"])


@router.get("/supervisor/metricas", summary="Indicadores da operação")
async def metricas():
    async with Sessao() as s:
        estados = await s.execute(text("SELECT estado, count(*) FROM conversas GROUP BY estado"))
        filas = await s.execute(
            text(
                "SELECT id_fila, count(*) AS tamanho, "
                "max(extract(epoch FROM now() - coalesce(na_fila_desde, criada_em)))::int AS espera_max_s "
                "FROM conversas WHERE estado IN ('na_fila', 'escalada') GROUP BY id_fila"
            )
        )
        escalas = await s.execute(
            text("SELECT motivo, count(*) FROM escalas WHERE criada_em > now() - interval '1 hour' GROUP BY motivo")
        )
        outbox = await s.execute(text("SELECT status, count(*) FROM outbox GROUP BY status"))
        atendentes = await s.execute(
            text("SELECT a.id, a.nome, a.tipo, a.marca, a.id_equipe, CASE WHEN a.tipo = 'ia' THEN (SELECT count(*) FROM conversas c WHERE c.id_atendente = a.id AND c.estado = 'com_ia') ELSE a.ativas END AS ativas, a.capacidade, a.status "
            "FROM atendentes a ORDER BY a.tipo, a.nome")
        )
        fencing = await s.execute(
            text("SELECT count(*) FROM eventos WHERE tipo = 'evento_descartado' AND criado_em > now() - interval '1 hour'")
        )
        resolvidas = await s.execute(
            text(
                "SELECT count(*) FILTER (WHERE origem = 'cliente') AS pela_ia, count(*) AS total "
                "FROM conversas WHERE estado = 'resolvida' AND resolvida_em > now() - interval '1 hour'"
            )
        )
        sla = await s.execute(
            text(
                "SELECT count(*) FILTER (WHERE sla_desde IS NOT NULL) AS correndo, "
                "count(*) FILTER (WHERE sla_limite_s IS NOT NULL AND sla_acumulado_ms "
                "+ coalesce(extract(epoch FROM now() - sla_desde) * 1000, 0) > sla_limite_s * 1000) AS estourados "
                "FROM conversas WHERE estado <> 'resolvida'"
            )
        )
        res = resolvidas.mappings().first()
        return {
            "conversas_por_estado": dict(estados.all()),
            "filas": [dict(x) for x in filas.mappings().all()],
            "escalas_ultima_hora": dict(escalas.all()),
            "outbox": dict(outbox.all()),
            "atendentes": [dict(x) for x in atendentes.mappings().all()],
            "descartes_fencing_ultima_hora": fencing.scalar(),
            "resolvidas_ultima_hora": dict(res),
            "sla": dict(sla.mappings().first()),
            "chaves": config.chaves(),
        }


@router.get("/outbox/erros", summary="Fila de erros da outbox")
async def erros():
    async with Sessao() as s:
        r = await s.execute(
            text("SELECT id, id_conversa, destino, tentativas, ultimo_erro, criado_em FROM outbox "
                 "WHERE status = 'erro' ORDER BY id DESC LIMIT 200")
        )
        return [dict(x) for x in r.mappings().all()]


@router.post("/outbox/{id_outbox}/reprocessar", summary="Devolve um item da fila de erros para envio")
async def reprocessar_item(id_outbox: int):
    if not await reprocessar(id_outbox):
        raise HTTPException(404, "item não está em erro")
    return {"reprocessado": id_outbox}


@router.get("/supervisor/reconciliacao", summary="Confere as invariantes I1 a I6 agora")
async def reconciliacao():
    return await reconciliar()


@router.get("/config", summary="Chaves de ablação e prazos em uso")
async def configuracao():
    return config.chaves()


EXPURGO = """
WITH alvo AS (
    SELECT id FROM conversas
    WHERE estado = 'resolvida' AND NOT ouvidoria
      AND resolvida_em < now() - make_interval(days => :dias)
), msgs AS (
    UPDATE mensagens SET conteudo = '[expurgado]', expurgada_em = now()
    WHERE id_conversa IN (SELECT id FROM alvo) AND expurgada_em IS NULL
    RETURNING id
), saidas AS (
    UPDATE outbox SET payload = jsonb_build_object('expurgado', true)
    WHERE id_conversa IN (SELECT id FROM alvo) AND status = 'enviado' AND NOT payload ? 'expurgado'
    RETURNING id
), notas AS (
    UPDATE escalas SET resumo = '[expurgado]', fontes = '[]'
    WHERE id_conversa IN (SELECT id FROM alvo) AND resumo <> '[expurgado]'
    RETURNING id
)
SELECT (SELECT count(*) FROM alvo), (SELECT count(*) FROM msgs), (SELECT count(*) FROM saidas),
       (SELECT count(*) FROM notas)
"""


@router.post("/supervisor/expurgo", summary="Apaga os corpos vencidos pela retenção, menos ouvidoria")
async def expurgo(dias: int = config.RETENCAO_DIAS):
    """Apaga o texto de mensagens, payloads enviados da outbox e notas de escala de conversas
    resolvidas há mais de `dias`. As linhas ficam (contagem, ordem e auditoria continuam); só o
    corpo sai. Conversa marcada como ouvidoria é preservada. A trilha de eventos não guarda corpo
    de mensagem e é só de inserção."""
    if dias < 0:
        raise HTTPException(422, "dias deve ser >= 0")
    async with unidade() as s:
        conversas, mensagens, saidas, notas = (await s.execute(text(EXPURGO), {"dias": dias})).one()
    return {"conversas": conversas, "mensagens": mensagens, "outbox": saidas, "notas_de_escala": notas,
            "retencao_dias": dias}


SERIE = """
WITH baldes AS (
    SELECT generate_series(date_bin(make_interval(secs => :passo), now() - make_interval(mins => :minutos),
                                    timestamptz '2000-01-01'),
                           now(), make_interval(secs => :passo)) AS t
), msgs AS (
    SELECT date_bin(make_interval(secs => :passo), m.criada_em, timestamptz '2000-01-01') AS t,
           count(*) FILTER (WHERE m.autor_tipo = 'cliente') AS cliente,
           count(*) FILTER (WHERE m.autor_tipo = 'ia') AS ia,
           count(*) FILTER (WHERE m.autor_tipo = 'humano') AS humano,
           percentile_cont(0.95) WITHIN GROUP (ORDER BY extract(epoch FROM m.criada_em - o.criado_em))
               FILTER (WHERE m.autor_tipo = 'ia') AS resposta_ia_p95_s
    FROM mensagens m LEFT JOIN outbox o ON o.id_evento = m.causado_por AND m.autor_tipo = 'ia'
    WHERE m.criada_em > now() - make_interval(mins => :minutos)
    GROUP BY 1
), esc AS (
    SELECT date_bin(make_interval(secs => :passo), criada_em, timestamptz '2000-01-01') AS t, count(*) AS escalas
    FROM escalas WHERE criada_em > now() - make_interval(mins => :minutos) GROUP BY 1
)
SELECT b.t, coalesce(m.cliente, 0) AS cliente, coalesce(m.ia, 0) AS ia, coalesce(m.humano, 0) AS humano,
       coalesce(e.escalas, 0) AS escalas, m.resposta_ia_p95_s
FROM baldes b LEFT JOIN msgs m USING (t) LEFT JOIN esc e USING (t)
ORDER BY b.t
"""


@router.get("/supervisor/serie", summary="Série das chamadas por intervalo, para o painel ao vivo")
async def serie(minutos: int = 10, passo: int = 5):
    """Mensagens do cliente, respostas da IA e de humanos e escalas por balde de `passo` segundos
    nos últimos `minutos`, mais a p95 do tempo de resposta da IA (do evento gravado na outbox até
    a resposta gravada). Contagens por balde; a tela divide pelo passo para mostrar por segundo."""
    minutos, passo = max(1, min(minutos, 120)), max(1, min(passo, 300))
    async with Sessao() as s:
        r = await s.execute(text(SERIE), {"minutos": minutos, "passo": passo})
        pontos = [
            {"t": x["t"].isoformat(), "cliente": x["cliente"], "ia": x["ia"], "humano": x["humano"],
             "escalas": x["escalas"],
             "resposta_ia_p95_s": round(float(x["resposta_ia_p95_s"]), 3) if x["resposta_ia_p95_s"] is not None else None}
            for x in r.mappings().all()
        ]
        abertas = (await s.execute(text(
            "SELECT count(*) FROM conversas WHERE estado <> 'resolvida'"))).scalar()
        na_fila = (await s.execute(text(
            "SELECT count(*) FROM conversas WHERE estado IN ('na_fila', 'escalada')"))).scalar()
        pendentes = (await s.execute(text(
            "SELECT count(*) FROM outbox WHERE status IN ('pendente', 'enviando')"))).scalar()
        total = (await s.execute(text("SELECT count(*) FROM mensagens WHERE autor_tipo = 'cliente'"))).scalar()
    return {"passo_s": passo, "pontos": pontos, "conversas_abertas": abertas, "aguardando_atendente": na_fila,
            "outbox_pendente": pendentes, "mensagens_do_cliente_total": total}
