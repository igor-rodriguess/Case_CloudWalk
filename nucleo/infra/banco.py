"""Sessão do banco e unidade de trabalho.

Com OUTBOX_ATIVA, toda saída vai para a tabela outbox na mesma transação (o relay envia).
Com a outbox desligada (ablação), as saídas ficam em `sessao.info["diretos"]` e são
enviadas uma vez, sem retentativa, só depois do commit.
"""

from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nucleo import config

engine = create_async_engine(config.DATABASE_URL, pool_size=20, max_overflow=20, pool_pre_ping=True)
Sessao = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def unidade():
    s: AsyncSession = Sessao()
    s.info["diretos"] = []
    try:
        async with s.begin():
            yield s
        diretos = s.info["diretos"]
    finally:
        await s.close()
    if diretos:
        from nucleo.infra.relay import enviar_direto

        for saida in diretos:
            await enviar_direto(saida)


async def executar(s: AsyncSession, sql: str, **params):
    return await s.execute(text(sql), params)
