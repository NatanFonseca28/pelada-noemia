import pytest

from tests.api.helpers import image_bytes

PLAYER = {
    "name": "Fulano de Tal",
    "nickname": "Fulaninho",
    "type": "MENSALISTA",
    "primary_position": "ZAGUEIRO",
    "secondary_position": "ALA",
    "skill_level": 3,
}

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_rbac_rotas_de_gestao(client, jogador_headers, mesario_headers):
    for headers in (jogador_headers, mesario_headers):
        assert (await client.get("/api/users", headers=headers)).status_code == 403
        assert (await client.post("/api/players", json=PLAYER, headers=headers)).status_code == 403
        assert (await client.get("/api/audit", headers=headers)).status_code == 403
    # Leitura de jogadores é liberada para qualquer usuário logado
    assert (await client.get("/api/players", headers=jogador_headers)).status_code == 200
    assert (await client.get("/api/players")).status_code == 401


async def test_crud_jogador_com_auditoria(client, admin_headers, superadmin_headers):
    r = await client.post("/api/players", json=PLAYER, headers=admin_headers)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["display_name"] == "Fulaninho"

    r = await client.patch(f"/api/players/{pid}", json={"skill_level": 5, "active": False}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["skill_level"] == 5 and r.json()["active"] is False

    r = await client.get("/api/players", params={"active": True}, headers=admin_headers)
    assert r.json() == []

    logs = (await client.get("/api/audit", params={"entity": "player"}, headers=superadmin_headers)).json()
    update = next(log for log in logs if log["action"] == "UPDATE")
    assert update["before"]["skill_level"] == 3
    assert update["after"]["skill_level"] == 5
    assert update["user_name"] == "Admin"

    assert (await client.delete(f"/api/players/{pid}", headers=admin_headers)).status_code == 204
    assert (await client.get(f"/api/players/{pid}", headers=admin_headers)).status_code == 404


async def test_validacoes_de_posicao(client, admin_headers):
    bad = {**PLAYER, "secondary_position": "ZAGUEIRO"}
    assert (await client.post("/api/players", json=bad, headers=admin_headers)).status_code == 422
    gk = {**PLAYER, "primary_position": "GOLEIRO_FIXO", "secondary_position": "ALA"}
    assert (await client.post("/api/players", json=gk, headers=admin_headers)).status_code == 422
    lvl = {**PLAYER, "skill_level": 6}
    assert (await client.post("/api/players", json=lvl, headers=admin_headers)).status_code == 422

    pid = (await client.post("/api/players", json=PLAYER, headers=admin_headers)).json()["id"]
    r = await client.patch(f"/api/players/{pid}", json={"primary_position": "ALA"}, headers=admin_headers)
    assert r.status_code == 422  # secundária (ALA) ficaria igual à principal
    r = await client.patch(f"/api/players/{pid}", json={"primary_position": "GOLEIRO_FIXO"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["secondary_position"] is None


async def test_upload_foto(client, admin_headers):
    pid = (await client.post("/api/players", json=PLAYER, headers=admin_headers)).json()["id"]
    r = await client.put(
        f"/api/players/{pid}/photo", files={"file": ("f.png", image_bytes("PNG"), "image/png")}, headers=admin_headers
    )
    assert r.status_code == 200
    url = r.json()["photo_url"]
    assert url.startswith("/api/media/players/") and url.endswith(".webp")  # regravada como WEBP
    img = await client.get(url)  # pública (usada em <img>) e servida do banco
    assert img.status_code == 200 and img.headers["content-type"] == "image/webp" and "immutable" in img.headers["cache-control"]
    r = await client.put(
        f"/api/players/{pid}/photo", files={"file": ("f.gif", b"GIF89a", "image/gif")}, headers=admin_headers
    )
    assert r.status_code == 422
    # trocar e remover a foto apaga o arquivo antigo
    new = (await client.put(f"/api/players/{pid}/photo", files={"file": ("g.png", image_bytes("PNG"), "image/png")},
                            headers=admin_headers)).json()["photo_url"]
    assert (await client.get(url)).status_code == 404
    await client.delete(f"/api/players/{pid}/photo", headers=admin_headers)
    assert (await client.get(new)).status_code == 404


async def test_admin_cria_usuario_vinculado_a_jogador(client, admin_headers):
    pid = (await client.post("/api/players", json=PLAYER, headers=admin_headers)).json()["id"]
    body = {"email": "f@test.com", "name": "Fulano", "password": "Gol-de-placa-2026", "player_id": pid}
    r = await client.post("/api/users", json=body, headers=admin_headers)
    assert r.status_code == 201
    assert r.json()["status"] == "ATIVO" and r.json()["player_id"] == pid

    body2 = {**body, "email": "g@test.com"}
    assert (await client.post("/api/users", json=body2, headers=admin_headers)).status_code == 409


async def test_admin_nao_remove_proprio_acesso(client, admin_headers):
    me = (await client.get("/api/auth/me", headers=admin_headers)).json()
    r = await client.patch(f"/api/users/{me['id']}", json={"role": "JOGADOR"}, headers=admin_headers)
    assert r.status_code == 422


async def test_bloquear_usuario_revoga_acesso(client, admin_headers, jogador_headers):
    users = (await client.get("/api/users", headers=admin_headers)).json()
    jid = next(u["id"] for u in users if u["email"] == "jogador@test.com")
    r = await client.patch(f"/api/users/{jid}", json={"status": "BLOQUEADO"}, headers=admin_headers)
    assert r.status_code == 200
    assert (await client.get("/api/auth/me", headers=jogador_headers)).status_code == 401


async def test_settings(client, admin_headers, jogador_headers):
    r = await client.get("/api/settings", headers=jogador_headers)
    assert r.status_code == 200
    cfg = r.json()
    assert cfg["total_minutes"] == 90 and cfg["tiebreakers"][0] == "PONTOS"
    assert cfg["balance_by_skill"] is False

    cfg["final_weight"] = "1.5"
    cfg["changeover_minutes"] = 3
    assert (await client.put("/api/settings", json=cfg, headers=jogador_headers)).status_code == 403
    r = await client.put("/api/settings", json=cfg, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["changeover_minutes"] == 3

    cfg["tiebreakers"] = ["PONTOS", "PONTOS"]
    assert (await client.put("/api/settings", json=cfg, headers=admin_headers)).status_code == 422


async def test_nivel_tecnico_visivel_so_para_admin(client, admin_headers, jogador_headers):
    pid = (await client.post("/api/players", json=PLAYER, headers=admin_headers)).json()["id"]
    assert (await client.get(f"/api/players/{pid}", headers=admin_headers)).json()["skill_level"] == 3
    assert (await client.get(f"/api/players/{pid}", headers=jogador_headers)).json()["skill_level"] is None
    assert (await client.get("/api/players", headers=jogador_headers)).json()[0]["skill_level"] is None


async def test_excluir_usuario(client, admin_headers, superadmin_headers, jogador_headers, session_factory):
    from sqlalchemy import select

    from app.models.player import Player
    from app.models.user import User

    pid = (await client.post("/api/players", json=PLAYER, headers=admin_headers)).json()["id"]
    body = {"email": "sai@test.com", "name": "Vai Sair", "password": "Bola-no-angulo-99", "player_id": pid}
    uid = (await client.post("/api/users", json=body, headers=admin_headers)).json()["id"]

    assert (await client.delete(f"/api/users/{uid}", headers=jogador_headers)).status_code == 403
    assert (await client.delete(f"/api/users/{uid}", headers=admin_headers)).status_code == 204
    assert (await client.get(f"/api/users/{uid}", headers=admin_headers)).status_code == 404
    async with session_factory() as s:
        assert await s.get(Player, pid) is not None  # o jogador continua no elenco
    logs = (await client.get("/api/audit", params={"entity": "user"}, headers=superadmin_headers)).json()
    assert any(log["action"] == "DELETE" and log["before"]["email"] == "sai@test.com" for log in logs)

    # não exclui a própria conta nem a do superadmin
    async with session_factory() as s:
        me = await s.scalar(select(User).where(User.email == "admin@test.com"))
        sup = await s.scalar(select(User).where(User.email == "super@test.com"))
    assert (await client.delete(f"/api/users/{me.id}", headers=admin_headers)).status_code == 422
    assert (await client.delete(f"/api/users/{sup.id}", headers=admin_headers)).status_code == 403
