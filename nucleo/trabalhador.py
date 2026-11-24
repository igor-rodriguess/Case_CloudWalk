"""Laços de fundo do núcleo num processo próprio: relay da outbox, agendador e distribuidor.

A API roda com vários processos (uvicorn --workers) e sem laços; este serviço roda os laços.
Mais de uma instância é segura: todos reservam trabalho com FOR UPDATE SKIP LOCKED.
"""

import asyncio
import logging

from nucleo import config
from nucleo.infra import agendador, distribuidor, relay
from nucleo.infra.seed import semear

logging.basicConfig(level=logging.INFO, format='{"servico":"trabalhador","nivel":"%(levelname)s","origem":"%(name)s","msg":"%(message)s"}')
logging.getLogger("httpx").setLevel(logging.WARNING)  # uma linha por requisição custava CPU sob carga


async def main() -> None:
    await semear()
    await agendador.reagendar_na_subida()
    tarefas = [asyncio.create_task(relay.trabalhador(i)) for i in range(config.RELAY_WORKERS)]
    tarefas.append(asyncio.create_task(agendador.laco()))
    tarefas.append(asyncio.create_task(distribuidor.laco()))
    await asyncio.gather(*tarefas)


if __name__ == "__main__":
    asyncio.run(main())
