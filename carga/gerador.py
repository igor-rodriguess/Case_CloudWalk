"""Reproduz a agenda contra POST /mensagens e grava cada envio (lado do cliente do juiz).

Faz o papel do k6 com `constant-arrival-rate`: cada envio sai no seu instante, sem esperar
os anteriores. Em erro ou timeout da requisição, reenvia uma vez com o mesmo id_externo;
sem 2xx depois disso, o envio é "recusado".
"""

import asyncio
import time
from dataclasses import dataclass

import httpx

from carga.agenda import Envio


@dataclass
class Registro:
    envio: Envio
    enviado_em: float = 0.0
    status: int = 0
    id_conversa: str | None = None
    duplicada: bool = False
    latencia_req_s: float = 0.0


import os

# Abaixo do pool (200): a fila fica no semáforo, não dentro do httpcore. Dentro do Docker, 50 é
# o ponto de maior vazão medido pela bancada (carga/bancada.py).
EM_VOO = int(os.getenv("CARGA_EM_VOO", "150"))


async def _enviar(cliente: httpx.AsyncClient, url: str, envio: Envio, reg: Registro,
                  limite: asyncio.Semaphore) -> None:
    async with limite:
        await _enviar_uma(cliente, url, envio, reg)


async def _enviar_uma(cliente: httpx.AsyncClient, url: str, envio: Envio, reg: Registro) -> None:
    corpo = {"canal": envio.canal, "marca": envio.marca, "identificador": envio.conversa,
             "conteudo": envio.texto, "id_externo": envio.id_externo}
    for tentativa in range(2):
        reg.enviado_em = time.time()
        try:
            r = await cliente.post(url, json=corpo)
            reg.status = r.status_code
            reg.latencia_req_s = time.time() - reg.enviado_em
            if r.status_code < 300:
                dados = r.json()
                reg.id_conversa = dados.get("id_conversa")
                reg.duplicada = bool(dados.get("duplicada"))
                return
        except httpx.HTTPError:
            reg.status = 0
        await asyncio.sleep(0.5)


async def reproduzir(agenda: list[Envio], nucleo: str, inicio: float | None = None) -> list[Registro]:
    url = f"{nucleo}/mensagens"
    limites = httpx.Limits(max_connections=200, max_keepalive_connections=100)
    registros = [Registro(e) for e in agenda]
    inicio = inicio or time.time()
    limite = asyncio.Semaphore(EM_VOO)
    async with httpx.AsyncClient(timeout=10, limits=limites) as cliente:
        tarefas = []
        for reg in registros:
            espera = inicio + reg.envio.t - time.time()
            if espera > 0:
                await asyncio.sleep(espera)
            # Sem wait_for: cancelar requisições no meio corrompia o estado do pool do httpcore.
            # O prazo de cada requisição já é o timeout do cliente (10 s, duas tentativas).
            tarefas.append(asyncio.create_task(_enviar(cliente, url, reg.envio, reg, limite)))
        await asyncio.gather(*tarefas, return_exceptions=True)
    return registros
