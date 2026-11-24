"""Sessão do banco e unidade de trabalho.

Com OUTBOX_ATIVA, toda saída vai para a tabela outbox na mesma transação (o relay envia).
Com a outbox desligada (ablação), as saídas ficam em `sessao.info["diretos"]` e são
enviadas uma vez, sem retentativa, só depois do commit.
"""

from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nucleo import config

engine = create_async_engine(config.DATABASE_URL, pool_size=config.DB_POOL, max_overflow=config.DB_POOL // 2,
                             pool_pre_ping=True)
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


async def escopo_marca(s, marca: str | None) -> None:
    """Leitura em nome de uma marca: troca para o papel `leitura_marca` e fixa `app.marca` só nesta
    transação (migration 0006). A partir daqui o Postgres esconde as linhas da outra marca."""
    if marca is None:
        return
    from sqlalchemy import text

    await s.execute(text("SET LOCAL ROLE leitura_marca"))
    await s.execute(text("SELECT set_config('app.marca', :m, true)"), {"m": marca})
