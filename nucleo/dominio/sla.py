"""SLA da conversa: relógio que corre enquanto a operação deve uma resposta ao cliente e pausa
enquanto o cliente deve uma. Função pura (o relógio entra como argumento).

Estado: `acumulado_ms` (trechos já fechados) e `desde` (início do trecho aberto, ou None se
pausado). Pausar fecha o trecho aberto e soma; retomar abre um trecho novo. Pausar o que já está
pausado e retomar o que já corre não mudam nada, então o acumulado nunca anda para trás nem conta
duas vezes o mesmo intervalo.
"""

from datetime import datetime


def decorrido_ms(acumulado_ms: int, desde: datetime | None, agora: datetime) -> int:
    if desde is None:
        return acumulado_ms
    return acumulado_ms + max(0, int((agora - desde).total_seconds() * 1000))


def pausar(acumulado_ms: int, desde: datetime | None, agora: datetime) -> tuple[int, None]:
    return decorrido_ms(acumulado_ms, desde, agora), None


def retomar(acumulado_ms: int, desde: datetime | None, agora: datetime) -> tuple[int, datetime]:
    if desde is not None:
        return acumulado_ms, desde
    return acumulado_ms, agora


def limite_da_fila(fila: dict | None, prioridade: int | None) -> int | None:
    """Limite em segundos pela lista `slas` da fila: a entrada da prioridade, senão a geral."""
    for s in (fila or {}).get("slas") or []:
        if s.get("prioridade") == (prioridade or 1):
            return s["limite_s"]
    for s in (fila or {}).get("slas") or []:
        if s.get("prioridade") is None:
            return s["limite_s"]
    return None
