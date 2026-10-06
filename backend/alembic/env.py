import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.core.config import get_settings
from app.db.base import Base
import app.models  # noqa: F401  (registra os models no metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    settings = get_settings()
    return config.attributes.get("database_url") or settings.migrations_database_url or settings.database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _do_run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_url())
    async with engine.connect() as connection:
        await connection.run_sync(_do_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
elif (connection := config.attributes.get("connection")) is not None:
    # Conexão fornecida pelo chamador (ex.: fixtures de teste).
    _do_run(connection)
else:
    asyncio.run(run_migrations_online())
