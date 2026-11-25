"""Tráfego de demonstração (DEMO, dado sintético): manda mensagens de lojistas fictícios pelo
mesmo `POST /mensagens` dos canais, para o painel ao vivo mostrar o sistema trabalhando.

Uma rodada por vez em todo o núcleo: a trava consultiva do Postgres fica com a conexão da rodada
enquanto ela dura (a API roda em vários processos).
"""

import asyncio
import random
import time
import uuid

import httpx
import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from nucleo import config

router = APIRouter(prefix="/demo", tags=["demonstração"])

TRAVA = 4242
TEXTOS = {
    "infinitepay": ["meu repasse não caiu", "quero saber meu saldo", "a maquininha não liga",
                    "como antecipo minhas vendas?", "o pix não chegou", "quero um empréstimo", "obrigado!"],
    "jim": ["my payout did not arrive", "how do I check my balance?", "the card reader is off", "thanks!"],
}
PEDE_HUMANO = {"infinitepay": "quero falar com um atendente", "jim": "I want to talk to a human"}
estado: dict = {}


class Rodada(BaseModel):
    msg_s: float = Field(10, gt=0, le=40, description="mensagens do cliente por segundo")
    segundos: int = Field(60, gt=0, le=600)
    clientes: int = Field(300, gt=0, le=5000)
    frac_humano: float = Field(0.03, ge=0, le=0.5, description="fração que pede atendente humano")


def _url_banco() -> str:
    return config.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")


async def _rodar(r: Rodada, conn) -> None:
    rnd = random.Random()
    prefixo = f"demo-{uuid.uuid4().hex[:6]}"
    inicio, enviadas, falhas = time.time(), 0, 0
    sem = asyncio.Semaphore(32)
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=15) as h:

            async def uma(i: int):
                nonlocal enviadas, falhas
                c = rnd.randrange(r.clientes)
                marca = "jim" if c % 5 == 0 else "infinitepay"
                texto = PEDE_HUMANO[marca] if rnd.random() < r.frac_humano else rnd.choice(TEXTOS[marca])
                corpo = {"canal": rnd.choice(["chat", "whatsapp", "email"]), "marca": marca,
                         "identificador": f"{prefixo}-c{c}", "nome": f"Loja demo {c}", "conteudo": texto,
                         "id_externo": f"{prefixo}-m{i}"}
                async with sem:
                    try:
                        resp = await h.post("/mensagens", json=corpo)
                        if resp.status_code < 300:
                            enviadas += 1
                        else:
                            falhas += 1
                    except httpx.HTTPError:
                        falhas += 1

            tarefas, i = [], 0
            while time.time() - inicio < r.segundos:
                alvo = int((time.time() - inicio) * r.msg_s)
                while i < alvo:
                    tarefas.append(asyncio.create_task(uma(i)))
                    i += 1
                estado.update(enviadas=enviadas, falhas=falhas, programadas=i)
                await asyncio.sleep(0.05)
            await asyncio.gather(*tarefas)
    finally:
        estado.update(ativa=False, enviadas=enviadas, falhas=falhas, fim=time.time())
        await conn.execute("SELECT pg_advisory_unlock(%s)", (TRAVA,))
        await conn.close()


@router.post("/trafego", summary="DEMO: dispara tráfego sintético de lojistas")
async def iniciar(r: Rodada):
    conn = await psycopg.AsyncConnection.connect(_url_banco(), autocommit=True)
    pegou = (await (await conn.execute("SELECT pg_try_advisory_lock(%s)", (TRAVA,))).fetchone())[0]
    if not pegou:
        await conn.close()
        raise HTTPException(409, "já existe uma rodada de demonstração em andamento")
    estado.clear()
    estado.update(ativa=True, inicio=time.time(), msg_s=r.msg_s, segundos=r.segundos, enviadas=0, falhas=0)
    asyncio.create_task(_rodar(r, conn))
    return {"iniciada": True, "msg_s": r.msg_s, "segundos": r.segundos, "rotulo": "DEMO: dado sintético"}


@router.get("/trafego", summary="DEMO: rodada em andamento neste processo da API")
async def situacao():
    conn = await psycopg.AsyncConnection.connect(_url_banco(), autocommit=True)
    try:
        ocupada = (await (await conn.execute(
            "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND objid = %s AND granted",
            (TRAVA,))).fetchone())[0] > 0
    finally:
        await conn.close()
    return {"em_andamento": ocupada, **{k: v for k, v in estado.items() if k != "ativa"}}
