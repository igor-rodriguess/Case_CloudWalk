"""Injeção de falhas por docker compose, com horário registrado para o juiz."""

import asyncio
import subprocess
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], cwd=RAIZ, check=True, capture_output=True)


async def parar_por(servico: str, aos_s: float, por_s: float, inicio: float) -> dict:
    """Para o serviço no instante `aos_s` da execução e religa `por_s` depois."""
    await asyncio.sleep(max(0.0, inicio + aos_s - time.time()))
    parou = time.time()
    await asyncio.to_thread(compose, "stop", servico)
    await asyncio.sleep(max(0.0, parou + por_s - time.time()))
    await asyncio.to_thread(compose, "start", servico)
    return {"servico": servico, "parou_em": parou, "voltou_em": time.time()}
