from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.ratelimit import limiter
from app.core.security import hash_password
from app.db.session import get_session
from app.main import app
from app.models.enums import UserRole, UserStatus
from app.models.user import User

TABLES = "audit_logs, refresh_tokens, match_events, matches, tournament_group_teams, tournament_groups, tournaments, team_players, teams, draws, attendances, rounds, collection_items, finance_collections, cash_entries, monthly_fees, users, players, settings"


@pytest.fixture(autouse=True)
def no_rate_limit():
    """Limite de tentativas desligado por padrão (os testes fazem muitos logins); test_security liga quando precisa."""
    limiter.enabled = False
    limiter.reset()
    yield
    limiter.enabled = False


@pytest.fixture
async def session_factory(engine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    yield factory
    app.dependency_overrides.clear()


@pytest.fixture
async def client(session_factory) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _make_user(factory, email: str, role: UserRole, status=UserStatus.ATIVO, password="senha123") -> User:
    async with factory() as s:
        user = User(email=email, name=email.split("@")[0].title(), password_hash=hash_password(password),
                    role=role, status=status)
        s.add(user)
        await s.commit()
        return user


async def _login(client: AsyncClient, email: str, password="senha123") -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def admin_headers(client, session_factory) -> dict:
    await _make_user(session_factory, "admin@test.com", UserRole.ADMIN)
    return await _login(client, "admin@test.com")


@pytest.fixture
async def mesario_headers(client, session_factory) -> dict:
    await _make_user(session_factory, "mesa@test.com", UserRole.MESARIO)
    return await _login(client, "mesa@test.com")


@pytest.fixture
async def jogador_headers(client, session_factory) -> dict:
    await _make_user(session_factory, "jogador@test.com", UserRole.JOGADOR)
    return await _login(client, "jogador@test.com")
