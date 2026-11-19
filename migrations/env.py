import os

from alembic import context
from sqlalchemy import create_engine

from nucleo.infra.modelos import Base

target_metadata = Base.metadata


def url() -> str:
    try:
        return os.environ["DATABASE_URL"]
    except KeyError:
        raise SystemExit("Defina DATABASE_URL (ver .env.example).")


def rodar_offline() -> None:
    context.configure(url=url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def rodar_online() -> None:
    engine = create_engine(url())
    with engine.connect() as conexao:
        context.configure(connection=conexao, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    rodar_offline()
else:
    rodar_online()
