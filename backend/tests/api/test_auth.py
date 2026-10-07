import pytest

from app.core.config import get_settings

COOKIE = get_settings().refresh_cookie_name

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_register_fica_pendente_e_nao_loga(client):
    r = await client.post("/api/auth/register", json={"email": "Novo@Test.com", "name": "Novo", "password": "Gol-de-placa-2026", "phone": "21987654321"})
    assert r.status_code == 201
    assert r.json()["status"] == "PENDENTE"
    assert r.json()["email"] == "novo@test.com"

    r = await client.post("/api/auth/login", json={"email": "novo@test.com", "password": "Gol-de-placa-2026", "phone": "21987654321"})
    assert r.status_code == 403
    assert r.json()["code"] == "USER_PENDING"


async def test_register_email_duplicado(client):
    body = {"email": "dup@test.com", "name": "Dup", "password": "Gol-de-placa-2026", "phone": "21987654321"}
    assert (await client.post("/api/auth/register", json=body)).status_code == 201
    assert (await client.post("/api/auth/register", json=body)).status_code == 409


async def test_aprovacao_libera_login(client, admin_headers):
    r = await client.post("/api/auth/register", json={"email": "p@test.com", "name": "Pedro", "password": "Gol-de-placa-2026", "phone": "21987654321"})
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    pend = await client.get("/api/users", params={"status": "PENDENTE"}, headers=admin_headers)
    assert [u["id"] for u in pend.json()] == [uid]

    r = await client.post(f"/api/users/{uid}/approve", json={"role": "MESARIO"}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "ATIVO" and r.json()["role"] == "MESARIO"

    r = await client.post("/api/auth/login", json={"email": "p@test.com", "password": "Gol-de-placa-2026", "phone": "21987654321"})
    assert r.status_code == 200


async def test_login_senha_errada(client, admin_headers):
    r = await client.post("/api/auth/login", json={"email": "admin@test.com", "password": "errada"})
    assert r.status_code == 401


async def test_me_exige_token(client):
    assert (await client.get("/api/auth/me")).status_code == 401
    r = await client.get("/api/auth/me", headers={"Authorization": "Bearer lixo"})
    assert r.status_code == 401


async def test_refresh_rotaciona_e_detecta_reuso(client, admin_headers):
    first = client.cookies.get(COOKIE)
    assert first

    r = await client.post("/api/auth/refresh")
    assert r.status_code == 200
    second = client.cookies.get(COOKIE)
    assert second and second != first

    # Reutilizar o token antigo (revogado) derruba todas as sessões
    client.cookies.set(COOKIE, first, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401
    client.cookies.set(COOKIE, second, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_logout_revoga_refresh(client, admin_headers):
    token = client.cookies.get(COOKIE)
    assert (await client.post("/api/auth/logout")).status_code == 204
    client.cookies.set(COOKIE, token, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_troca_de_senha(client, jogador_headers):
    r = await client.post(
        "/api/auth/change-password",
        json={"current_password": "senha123", "new_password": "Chapeu-no-goleiro-7"},
        headers=jogador_headers,
    )
    assert r.status_code == 204
    r = await client.post("/api/auth/login", json={"email": "jogador@test.com", "password": "Chapeu-no-goleiro-7"})
    assert r.status_code == 200


async def test_cadastro_exige_celular_e_leva_para_o_jogador(client, admin_headers):
    base = {"email": "cel@test.com", "name": "Celso", "password": "Gol-de-placa-2026"}
    for phone, msg in ((None, "obrigatório"), ("(21) 3456-7890", "celular"), ("", "celular")):
        body = base if phone is None else {**base, "phone": phone}
        r = await client.post("/api/auth/register", json=body)
        assert r.status_code == 422, phone
        assert msg.lower() in r.json()["detail"].lower()
    r = await client.post("/api/auth/register", json={**base, "phone": "(21) 98765-4321"})
    assert r.status_code == 201 and r.json()["phone"] == "+5521987654321"
    uid = r.json()["id"]

    pending = (await client.get("/api/users", params={"status": "PENDENTE"}, headers=admin_headers)).json()
    assert next(u for u in pending if u["id"] == uid)["phone"] == "+5521987654321"

    # ao aprovar vinculando a um jogador sem WhatsApp, o celular vai para o cadastro do jogador
    pid = (await client.post("/api/players", json={"name": "Celso", "type": "DIARISTA", "primary_position": "ALA"},
                             headers=admin_headers)).json()["id"]
    r = await client.post(f"/api/users/{uid}/approve", json={"role": "JOGADOR", "player_id": pid}, headers=admin_headers)
    assert r.status_code == 200
    assert (await client.get(f"/api/players/{pid}", headers=admin_headers)).json()["phone"] == "+5521987654321"
