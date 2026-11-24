"""Núcleo do help desk: API (OpenAPI em /docs) e laços de fundo (relay, agendador, distribuidor)."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from nucleo import config
from nucleo.api import agente, conversas, filas, mensagens, painel, supervisor
from nucleo.infra import agendador, distribuidor, relay
from nucleo.infra.seed import semear

logging.basicConfig(level=logging.INFO, format='{"servico":"nucleo","nivel":"%(levelname)s","origem":"%(name)s","msg":"%(message)s"}')
logging.getLogger("httpx").setLevel(logging.WARNING)  # uma linha por requisição custava CPU sob carga


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    await semear()
    tarefas = []
    if config.WORKERS_ATIVOS:
        await agendador.reagendar_na_subida()
        tarefas += [asyncio.create_task(relay.trabalhador(i)) for i in range(config.RELAY_WORKERS)]
        tarefas.append(asyncio.create_task(agendador.laco()))
        tarefas.append(asyncio.create_task(distribuidor.laco()))
    yield
    for t in tarefas:
        t.cancel()


app = FastAPI(
    title="Help Desk AI First",
    description="Núcleo: canais, agente, painel do analista, filas e supervisor. Contrato e decisões em docs/.",
    version="1.0",
    lifespan=ciclo_de_vida,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(OperationalError)
async def banco_fora(request: Request, exc: Exception):
    # Dependência fora vira 503: o broker trata como contrapressão e não descarta.
    return JSONResponse(status_code=503, content={"erro": "banco indisponível"})


@app.exception_handler(OSError)
async def rede_fora(request: Request, exc: Exception):
    return JSONResponse(status_code=503, content={"erro": "dependência indisponível"})


@app.get("/saude", tags=["supervisor"])
async def saude():
    return {"ok": True}


for modulo in (mensagens, agente, painel, conversas, filas, supervisor):
    app.include_router(modulo.router)
