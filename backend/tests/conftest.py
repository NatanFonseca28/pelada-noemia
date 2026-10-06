"""Fixtures de teste.

- tests/domain: unitários puros, sem banco.
- tests/api: integração com Postgres real (TEST_DATABASE_URL). O schema é criado
  rodando as migrations do Alembic, o que também valida as migrations.
"""
import os
from collections.abc import AsyncIterator

import pytest

from app.core.config import get_settings


@pytest.fixture(scope="session")
def test_db_url() -> str:
    return os.environ.get("TEST_DATABASE_URL") or get_settings().test_database_url


@pytest.fixture(scope="session")
async def engine(test_db_url: str, tmp_path_factory) -> AsyncIterator:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    os.environ["MEDIA_DIR"] = str(tmp_path_factory.mktemp("media"))
    get_settings.cache_clear()

    eng = create_async_engine(test_db_url)
    async with eng.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))

    def _upgrade(sync_conn):
        cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
        cfg.attributes["connection"] = sync_conn
        command.upgrade(cfg, "head")

    async with eng.begin() as conn:
        await conn.run_sync(_upgrade)
    yield eng
    await eng.dispose()
