"""Relay da outbox (docs/implementacao.md 7.3).

Reserva um item por transação (SKIP LOCKED, respeitando a ordem por conversa e destino),
envia FORA da transação e grava o resultado em outra. Item em `erro` (esgotou as tentativas, a
mensagem envenenada) estaciona os seguintes da mesma conversa e destino; as outras conversas
seguem. O reprocessamento (`/outbox/{id}/reprocessar`) devolve o item à fila e os estacionados
saem depois dele, na ordem. O prazo do agente (timeout_agente)
só nasce aqui, no ack do broker: atraso da própria plataforma não vira falha do agente.
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import text

from nucleo import config
from nucleo.infra.banco import Sessao

log = logging.getLogger("relay")

COBRAM_AGENTE = {"mensagem.recebida", "conversa.atribuida", "conversa.devolvida"}

RESERVAR = """
UPDATE outbox SET status = 'enviando', reservado_ate = now() + make_interval(secs => :reserva)
WHERE id = (
    SELECT o.id FROM outbox o
    WHERE o.status IN ('pendente', 'enviando')          -- casa o índice parcial ix_outbox_pendentes
      AND (o.status = 'pendente' AND o.proxima_tentativa <= now()
           OR o.status = 'enviando' AND o.reservado_ate < now())
      AND NOT EXISTS (
          SELECT 1 FROM outbox p
          WHERE p.id_conversa = o.id_conversa AND p.destino = o.destino
            AND p.sequencia < o.sequencia AND p.status IN ('pendente', 'enviando', 'erro'))
    ORDER BY o.criado_em
    LIMIT 1
    FOR UPDATE SKIP LOCKED)
RETURNING id, id_evento, id_conversa, id_atribuicao, destino, payload, tentativas
"""

_cliente: httpx.AsyncClient | None = None


def cliente_http() -> httpx.AsyncClient:
    global _cliente
    if _cliente is None:
        _cliente = httpx.AsyncClient(timeout=config.REQUISICAO_TIMEOUT_S)
    return _cliente


def atraso(tentativas: int) -> float:
    teto = min(config.BACKOFF_TETO_S, config.BACKOFF_BASE_S * 2**tentativas)
    return random.uniform(teto / 2, teto)


async def _post(destino: str, payload: dict) -> None:
    url = f"{config.BROKER_URL}/webhook" if destino == "broker" else f"{config.CANAIS_URL}/entregas"
    r = await cliente_http().post(url, json=payload)
    if r.status_code >= 300:
        raise RuntimeError(f"{destino} respondeu {r.status_code}")


async def criar_timeout(s, id_conversa, id_atribuicao, id_evento, tipo: str) -> None:
    """Cria o prazo do agente se a atribuição ainda é a vigente e nada o cobriu."""
    if not config.TIMEOUT_ATIVO or tipo not in COBRAM_AGENTE or id_atribuicao is None:
        return
    r = await s.execute(
        text("SELECT id_atribuicao_atual FROM conversas WHERE id = :c FOR UPDATE"), {"c": id_conversa}
    )
    vigente = r.scalar()
    if vigente != id_atribuicao:
        return
    coberto = await s.execute(
        text("SELECT 1 FROM mensagens WHERE causado_por = :e AND autor_tipo = 'ia' LIMIT 1"), {"e": id_evento}
    )
    if coberto.first():
        return
    await s.execute(
        text(
            "INSERT INTO agendamentos (tipo, id_conversa, id_atribuicao, referencia, executar_em) "
            "VALUES ('timeout_agente', :c, :a, :e, now() + make_interval(secs => :t))"
        ),
        {"c": id_conversa, "a": id_atribuicao, "e": id_evento, "t": config.TIMEOUT_AGENTE_S},
    )


async def _processar_um() -> bool:
    async with Sessao() as s:
        async with s.begin():
            r = await s.execute(text(RESERVAR), {"reserva": config.RELAY_RESERVA_S})
            item = r.mappings().first()
    if item is None:
        return False
    payload = item["payload"] if isinstance(item["payload"], dict) else json.loads(item["payload"])
    try:
        await _post(item["destino"], payload)
        ok, erro = True, None
    except Exception as e:  # rede, timeout, 5xx
        ok, erro = False, str(e)[:500]

    async with Sessao() as s:
        async with s.begin():
            if ok:
                await s.execute(
                    text("UPDATE outbox SET status = 'enviado', enviado_em = now() WHERE id = :id"),
                    {"id": item["id"]},
                )
                if item["destino"] == "broker":
                    await criar_timeout(s, item["id_conversa"], item["id_atribuicao"], item["id_evento"],
                                        payload.get("tipo", ""))
                return True
            tentativas = item["tentativas"] + 1
            if tentativas < config.RETENTATIVAS_MAX:
                await s.execute(
                    text(
                        "UPDATE outbox SET status = 'pendente', tentativas = :t, ultimo_erro = :e, "
                        "proxima_tentativa = :p WHERE id = :id"
                    ),
                    {"t": tentativas, "e": erro, "id": item["id"],
                     "p": datetime.now(timezone.utc) + timedelta(seconds=atraso(tentativas))},
                )
                return True
            await s.execute(
                text("UPDATE outbox SET status = 'erro', tentativas = :t, ultimo_erro = :e WHERE id = :id"),
                {"t": tentativas, "e": erro, "id": item["id"]},
            )
            # A escala vai na mesma transação do 'erro': se o processo cair aqui, nenhum dos dois fica.
            if item["destino"] == "broker" and item["id_atribuicao"]:
                from nucleo.dominio.acoes import escalar
                from nucleo.dominio.transicionar import SISTEMA

                s.info.setdefault("diretos", [])
                await escalar(s, item["id_conversa"], SISTEMA, "falha_integracao",
                              id_atribuicao=item["id_atribuicao"], causado_por=item["id_evento"])
    log.warning("outbox %s esgotou as tentativas: %s", item["id"], erro)
    return True


async def trabalhador(n: int) -> None:
    while True:
        try:
            trabalhou = await _processar_um()
        except Exception:
            log.exception("relay %s", n)
            trabalhou = False
        if not trabalhou:
            await asyncio.sleep(config.RELAY_INTERVALO_MS / 1000)


async def enviar_direto(saida) -> None:
    """Ablação OUTBOX_ATIVA = false: um envio depois do commit, sem retentativa."""
    try:
        await _post(saida.destino, saida.payload)
    except Exception as e:
        log.warning("envio direto perdido %s: %s", saida.id_evento, e)
        return
    if saida.destino == "broker":
        async with Sessao() as s:
            async with s.begin():
                await criar_timeout(s, saida.id_conversa, saida.id_atribuicao, saida.id_evento, saida.tipo)


async def reprocessar(id_outbox: int) -> bool:
    async with Sessao() as s:
        async with s.begin():
            r = await s.execute(
                text(
                    "UPDATE outbox SET status = 'pendente', tentativas = 0, proxima_tentativa = now() "
                    "WHERE id = :id AND status = 'erro' RETURNING id"
                ),
                {"id": id_outbox},
            )
            return r.first() is not None
