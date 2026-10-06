import pytest

from tests.api.conftest import _login, _make_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_auditoria_e_log_de_acesso_so_superadmin(client, admin_headers, mesario_headers, superadmin_headers):
    for h in (admin_headers, mesario_headers):
        assert (await client.get("/api/audit", headers=h)).status_code == 403
        assert (await client.get("/api/access/log", headers=h)).status_code == 403
        assert (await client.get("/api/access/pages", headers=h)).status_code == 403
    assert (await client.get("/api/audit", headers=superadmin_headers)).status_code == 200

    # login certo, senha errada e e-mail inexistente ficam no log de acessos, com IP e navegador
    await client.post("/api/auth/login", json={"email": "admin@test.com", "password": "errada-123"})
    await client.post("/api/auth/login", json={"email": "ninguem@test.com", "password": "x"})
    log = (await client.get("/api/access/log", headers=superadmin_headers)).json()
    events = [(e["email"], e["event"]) for e in log]
    assert ("admin@test.com", "LOGIN") in events and ("admin@test.com", "LOGIN_FALHOU") in events
    assert ("ninguem@test.com", "LOGIN_FALHOU") in events
    assert all(e["user_agent"] for e in log)
    assert next(e for e in log if e["email"] == "admin@test.com")["user_name"] == "Admin"
    only = (await client.get("/api/access/log", params={"event": "LOGIN_FALHOU"}, headers=superadmin_headers)).json()
    assert {e["event"] for e in only} == {"LOGIN_FALHOU"}


async def test_logout_entra_no_log(client, superadmin_headers):
    client.cookies.clear()
    await client.post("/api/auth/logout")  # sem cookie: nada a registrar
    await client.post("/api/auth/login", json={"email": "super@test.com", "password": "senha123"})
    await client.post("/api/auth/logout")  # usa o cookie de sessão guardado pelo cliente
    log = (await client.get("/api/access/log", params={"event": "LOGOUT"}, headers=superadmin_headers)).json()
    assert [e["email"] for e in log] == ["super@test.com"]


async def test_ocultar_paginas_por_categoria(client, admin_headers, jogador_headers, superadmin_headers):
    cfg = (await client.get("/api/access/pages", headers=superadmin_headers)).json()
    assert {"path": "/gestao/financeiro", "label": "Financeiro"} in cfg["pages"]
    assert cfg["hidden"] == {"ADMIN": [], "MESARIO": [], "JOGADOR": []}

    body = {"hidden": {"JOGADOR": ["/estatisticas", "/campeonato"], "ADMIN": ["/gestao/financeiro"]}}
    r = await client.put("/api/access/pages", json=body, headers=superadmin_headers)
    assert r.status_code == 200 and r.json()["hidden"]["JOGADOR"] == ["/campeonato", "/estatisticas"]

    me = lambda h: client.get("/api/auth/me", headers=h)  # noqa: E731
    assert (await me(jogador_headers)).json()["hidden_pages"] == ["/campeonato", "/estatisticas"]
    assert (await me(admin_headers)).json()["hidden_pages"] == ["/gestao/financeiro"]
    sup = (await me(superadmin_headers)).json()
    assert sup["hidden_pages"] == [] and sup["is_superadmin"] is True  # superadmin vê tudo
    # o login já devolve as páginas ocultas
    login = await client.post("/api/auth/login", json={"email": "jogador@test.com", "password": "senha123"})
    assert login.json()["user"]["hidden_pages"] == ["/campeonato", "/estatisticas"]

    # páginas fixas (Início, Conta, Auditoria...) não podem ser ocultadas; admin comum não altera
    bad = {"hidden": {"JOGADOR": ["/conta"]}}
    assert (await client.put("/api/access/pages", json=bad, headers=superadmin_headers)).status_code == 422
    assert (await client.put("/api/access/pages", json=body, headers=admin_headers)).status_code == 403


async def test_admin_comum_nao_altera_superadmin(client, admin_headers, superadmin_headers, session_factory):
    users = (await client.get("/api/users", headers=admin_headers)).json()
    sup = next(u for u in users if u["email"] == "super@test.com")
    assert sup["is_superadmin"] is True
    for change in ({"role": "JOGADOR"}, {"status": "BLOQUEADO"}, {"password": "Bola-no-angulo-99"}):
        r = await client.patch(f"/api/users/{sup['id']}", json=change, headers=admin_headers)
        assert r.status_code == 403, change
    # nenhum campo da API concede superadmin
    await _make_user(session_factory, "outro@test.com", "ADMIN")
    outro = next(u for u in (await client.get("/api/users", headers=admin_headers)).json() if u["email"] == "outro@test.com")
    await client.patch(f"/api/users/{outro['id']}", json={"is_superadmin": True}, headers=superadmin_headers)
    h = await _login(client, "outro@test.com")
    assert (await client.get("/api/auth/me", headers=h)).json()["is_superadmin"] is False
