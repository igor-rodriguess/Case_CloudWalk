"""Agendador único para prazos (docs/implementacao.md 7.4).

Lê os vencidos sem travar e age um por transação: trava a conversa com SKIP LOCKED
(ocupada = próximo ciclo) e só depois o agendamento, na mesma ordem do transicionar.
"""

import asyncio
import logging

from sqlalchemy import text

from nucleo import config
from nucleo.dominio.acoes import escalar
from nucleo.dominio.transicionar import SISTEMA, Resultado
from nucleo.infra.banco import Sessao, unidade

log = logging.getLogger("agendador")


async def _agir(id_agendamento: int, id_conversa) -> None:
    async with unidade() as s:
        r = await s.execute(
            text("SELECT id FROM conversas WHERE id = :c FOR UPDATE SKIP LOCKED"), {"c": id_conversa}
        )
        if r.first() is None:
            return  # ocupada; tenta no próximo ciclo
        r = await s.execute(
            text("SELECT * FROM agendamentos WHERE id = :a AND status = 'pendente' FOR UPDATE"),
            {"a": id_agendamento},
        )
        ag = r.mappings().first()
        if ag is None:
            return
        motivo = "executado"
        if ag["tipo"] == "timeout_agente":
            resultado = await escalar(s, id_conversa, SISTEMA, "timeout_agente",
                                      id_atribuicao=ag["id_atribuicao"], causado_por=ag["referencia"])
            motivo = "timeout" if resultado == Resultado.APLICADO else "descartado"
        await s.execute(
            text(
                "UPDATE agendamentos SET status = 'executado', motivo_fim = :m, finalizado_em = now() "
                "WHERE id = :a"
            ),
            {"m": motivo, "a": id_agendamento},
        )


async def laco() -> None:
    while True:
        try:
            async with Sessao() as s:
                r = await s.execute(
                    text(
                        "SELECT id, id_conversa FROM agendamentos WHERE status = 'pendente' "
                        "AND executar_em <= now() ORDER BY executar_em LIMIT 50"
                    )
                )
                vencidos = r.all()
            for id_ag, id_conversa in vencidos:
                try:
                    await _agir(id_ag, id_conversa)
                except Exception:
                    log.exception("agendamento %s", id_ag)
        except Exception:
            log.exception("agendador")
        await asyncio.sleep(config.AGENDADOR_INTERVALO_MS / 1000)


async def reagendar_na_subida() -> None:
    """Prazos vencidos enquanto o núcleo estava fora não são culpa do agente."""
    async with unidade() as s:
        await s.execute(
            text(
                "UPDATE agendamentos SET executar_em = now() + make_interval(secs => :t) "
                "WHERE tipo = 'timeout_agente' AND status = 'pendente' AND executar_em <= now()"
            ),
            {"t": config.TIMEOUT_AGENTE_S},
        )
