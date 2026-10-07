from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select

from app.core.ratelimit import limiter
from app.models.password_reset import PasswordReset
from tests.api.conftest import _login, _make_user

pytestmark = pytest.mark.asyncio(loop_scope="session")
NEW = "Bola-no-angulo-99"


def token_of(url: str) -> str:
    return parse_qs(urlsplit(url).query)["token"][0]


async def test_fluxo_completo_esqueci_senha(client, admin_headers, jogador_headers, session_factory):
    user = await _make_user(session_factory, "esqueci@test.com", "JOGADOR")
    async with session_factory() as s:
        u = await s.get(type(user), user.id)
        u.phone = "+5521987654321"
        await s.commit()
    old_session = await _login(client, "esqueci@test.com")

    # mesma resposta para conta existente, inexistente, por e-mail ou celular
    a = await client.post("/api/auth/forgot", json={"identifier": "esqueci@test.com"})
    b = await client.post("/api/auth/forgot", json={"identifier": "ninguem@test.com"})
    c = await client.post("/api/auth/forgot", json={"identifier": "(21) 98765-4321"})
    assert a.status_code == b.status_code == c.status_code == 202 and a.json() == b.json()

    # só admin vê e gera o link; pedido repetido não duplica
    assert (await client.get("/api/users/password-requests", headers=jogador_headers)).status_code == 403
    reqs = (await client.get("/api/users/password-requests", headers=admin_headers)).json()
    assert [r["email"] for r in reqs] == ["esqueci@test.com"] and reqs[0]["phone"] == "+5521987654321"
    assert (await client.post(f"/api/users/password-requests/{reqs[0]['id']}/link", headers=jogador_headers)).status_code == 403
    link = (await client.post(f"/api/users/password-requests/{reqs[0]['id']}/link", headers=admin_headers)).json()
    assert "/redefinir-senha?token=" in link["url"] and link["phone"] == "+5521987654321"
    token = token_of(link["url"])

    # senha fraca é recusada; senha boa troca, derruba sessões e o link não serve de novo
    weak = await client.post("/api/auth/reset", json={"token": token, "new_password": "1234567890"})
    assert weak.status_code == 422
    assert (await client.post("/api/auth/reset", json={"token": token, "new_password": NEW})).status_code == 204
    assert (await client.post("/api/auth/reset", json={"token": token, "new_password": NEW})).status_code == 422
    assert (await client.post("/api/auth/refresh")).status_code == 401  # sessão antiga caiu
    assert (await client.get("/api/auth/me", headers=old_session)).status_code == 200  # access token curto ainda vale
    await _login(client, "esqueci@test.com", NEW)
    assert (await client.get("/api/users/password-requests", headers=admin_headers)).json() == []


async def test_link_expira_em_uma_hora(client, admin_headers, session_factory):
    await _make_user(session_factory, "expira@test.com", "JOGADOR")
    await client.post("/api/auth/forgot", json={"identifier": "expira@test.com"})
    req = (await client.get("/api/users/password-requests", headers=admin_headers)).json()[0]
    token = token_of((await client.post(f"/api/users/password-requests/{req['id']}/link", headers=admin_headers)).json()["url"])
    async with session_factory() as s:
        r = await s.scalar(select(PasswordReset).where(PasswordReset.id == req["id"]))
        r.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await s.commit()
    r = await client.post("/api/auth/reset", json={"token": token, "new_password": NEW})
    assert r.status_code == 422 and "expirado" in r.json()["detail"]
    bad = await client.post("/api/auth/reset", json={"token": "x" * 43, "new_password": NEW})
    assert bad.status_code == 422


async def test_limite_de_pedidos(client):
    limiter.enabled = True
    codes = [(await client.post("/api/auth/forgot", json={"identifier": f"a{i}@test.com"})).status_code for i in range(4)]
    assert codes[:3] == [202] * 3 and codes[3] == 429
