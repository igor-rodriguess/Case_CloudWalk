"""Simulador dos canais de saída (chat, WhatsApp, e-mail): recebe o que a plataforma envia
ao cliente e guarda cada entrega, inclusive repetidas. É a ponta onde o juiz do experimento
conta o que o cliente de fato recebeu. `POST /modo` com `fora` simula o canal indisponível.
"""

import os
from contextlib import asynccontextmanager
from typing import Literal

import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

BANCO = os.getenv("CANAIS_DATABASE_URL", "postgresql://helpdesk:helpdesk@localhost:5433/canais")
estado = {"modo": "normal"}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS entregas (
    id bigserial PRIMARY KEY, id_evento uuid NOT NULL, id_conversa uuid NOT NULL, canal text NOT NULL,
    autor text NOT NULL, conteudo text NOT NULL, causado_por uuid, sequencia int,
    recebida_em timestamptz NOT NULL DEFAULT clock_timestamp());
CREATE INDEX IF NOT EXISTS ix_entregas_conversa ON entregas (id_conversa, id);
-- Inbox do adaptador de canal: o relay entrega pelo menos uma vez (reserva vencida sob pausa
-- reenvia o item); o adaptador deduplica pelo id do evento. Reenvio absorvido fica registrado.
CREATE UNIQUE INDEX IF NOT EXISTS uq_entregas_evento ON entregas (id_evento);
CREATE TABLE IF NOT EXISTS duplicatas_absorvidas (
    id_evento uuid NOT NULL, id_conversa uuid NOT NULL,
    recebida_em timestamptz NOT NULL DEFAULT clock_timestamp());
"""


class Entrega(BaseModel):
    id_evento: str
    id_conversa: str
    canal: str
    marca: str | None = None
    autor: str
    conteudo: str
    causado_por: str | None = None
    sequencia: int = 0
    timestamp: str | None = None


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    async with await psycopg.AsyncConnection.connect(BANCO, autocommit=True) as conn:
        await conn.execute(ESQUEMA)
    yield


app = FastAPI(title="Simulador de canais", lifespan=ciclo_de_vida)


@app.post("/entregas")
async def entregar(e: Entrega):
    if estado["modo"] == "fora":
        return JSONResponse(status_code=503, content={"erro": "canal indisponível"})
    async with await psycopg.AsyncConnection.connect(BANCO, autocommit=True) as conn:
        cur = await conn.execute(
            "INSERT INTO entregas (id_evento, id_conversa, canal, autor, conteudo, causado_por, sequencia) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id_evento) DO NOTHING RETURNING id",
            (e.id_evento, e.id_conversa, e.canal, e.autor, e.conteudo, e.causado_por, e.sequencia),
        )
        if await cur.fetchone() is None:
            await conn.execute("INSERT INTO duplicatas_absorvidas (id_evento, id_conversa) VALUES (%s, %s)",
                               (e.id_evento, e.id_conversa))
            return {"ok": True, "duplicada": True}
    return {"ok": True, "duplicada": False}


@app.get("/entregas")
async def listar(id_conversa: str):
    async with await psycopg.AsyncConnection.connect(BANCO, autocommit=True) as conn:
        cur = await conn.execute(
            "SELECT id_evento, autor, conteudo, recebida_em, causado_por FROM entregas "
            "WHERE id_conversa = %s ORDER BY id",
            (id_conversa,),
        )
        return [
            {"id_evento": str(a), "autor": b, "conteudo": c, "recebida_em": d.isoformat(),
             "causado_por": str(e) if e else None}
            for a, b, c, d, e in await cur.fetchall()
        ]


@app.get("/duplicatas")
async def duplicatas():
    """Reenvios do relay absorvidos pela deduplicação do adaptador (pelo menos uma vez)."""
    async with await psycopg.AsyncConnection.connect(BANCO, autocommit=True) as conn:
        cur = await conn.execute("SELECT count(*) FROM duplicatas_absorvidas")
        return {"absorvidas": (await cur.fetchone())[0]}


class Modo(BaseModel):
    modo: Literal["normal", "fora"]


@app.post("/modo")
async def mudar_modo(m: Modo):
    estado["modo"] = m.modo
    return estado


@app.get("/saude")
async def saude():
    return {"ok": True, **estado}
