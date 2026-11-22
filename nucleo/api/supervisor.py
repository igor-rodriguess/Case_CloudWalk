"""Supervisor: saúde da operação, fila de erros da outbox e reconciliação de invariantes."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from nucleo import config
from nucleo.infra.banco import Sessao
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
            text("SELECT nome, tipo, marca, id_equipe, ativas, capacidade, status FROM atendentes ORDER BY tipo, nome")
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
        res = resolvidas.mappings().first()
        return {
            "conversas_por_estado": dict(estados.all()),
            "filas": [dict(x) for x in filas.mappings().all()],
            "escalas_ultima_hora": dict(escalas.all()),
            "outbox": dict(outbox.all()),
            "atendentes": [dict(x) for x in atendentes.mappings().all()],
            "descartes_fencing_ultima_hora": fencing.scalar(),
            "resolvidas_ultima_hora": dict(res),
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
