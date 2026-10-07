"""Testes das proteções de segurança para produção."""
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.ratelimit import limiter
from app.core.security import hash_refresh_token
from app.models.audit import AuditLog
from app.models.user import RefreshToken, User
from tests.api.conftest import _make_user
from tests.api.helpers import image_bytes

pytestmark = pytest.mark.asyncio(loop_scope="session")

STRONG = "Gol-de-placa-2026"


# ---------------------------------------------------------------- headers e host

async def test_headers_de_seguranca(client, admin_headers):
    r = await client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "strict-origin" in r.headers["referrer-policy"]
    r = await client.get("/api/auth/me", headers=admin_headers)
    assert r.headers["cache-control"] == "no-store"


async def test_host_desconhecido_e_recusado(client):
    r = await client.get("/api/health", headers={"host": "site-malicioso.com"})
    assert r.status_code == 400


# ---------------------------------------------------------------- força bruta

async def test_limite_de_tentativas_no_login(client, session_factory):
    await _make_user(session_factory, "alvo@test.com", "JOGADOR")
    limiter.enabled = True
    codes = [
        (await client.post("/api/auth/login", json={"email": "alvo@test.com", "password": f"errada-{i}"})).status_code
        for i in range(6)
    ]
    assert codes[:5] == [401] * 5 and codes[5] == 429
    r = await client.post("/api/auth/login", json={"email": "alvo@test.com", "password": "senha123"})
    assert r.status_code == 429 and r.json()["code"] == "RATE_LIMITED"


async def test_bloqueio_da_conta_apos_falhas(client, session_factory):
    await _make_user(session_factory, "vitima@test.com", "JOGADOR")
    for i in range(get_settings().login_max_failures):
        await client.post("/api/auth/login", json={"email": "vitima@test.com", "password": f"chute-{i}"})
    # Mesmo com a senha certa, fica bloqueada por um tempo
    r = await client.post("/api/auth/login", json={"email": "vitima@test.com", "password": "senha123"})
    assert r.status_code == 403 and r.json()["code"] == "ACCOUNT_LOCKED"
    async with session_factory() as s:
        user = await s.scalar(select(User).where(User.email == "vitima@test.com"))
        assert user.locked_until is not None
        assert await s.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "LOCKED")) == 1
        # Passado o bloqueio, a senha certa volta a funcionar e zera o contador
        user.locked_until = datetime.now(UTC) - timedelta(minutes=1)
        await s.commit()
    r = await client.post("/api/auth/login", json={"email": "vitima@test.com", "password": "senha123"})
    assert r.status_code == 200


async def test_email_inexistente_tem_mesma_resposta(client, admin_headers):
    a = await client.post("/api/auth/login", json={"email": "nao-existe@test.com", "password": "qualquer"})
    b = await client.post("/api/auth/login", json={"email": "admin@test.com", "password": "errada"})
    assert a.status_code == b.status_code == 401 and a.json()["detail"] == b.json()["detail"]


# ---------------------------------------------------------------- política de senha

@pytest.mark.parametrize("pwd", ["curta1", "1234567890", "pelada1234", "aaaaaaaaaaaa", "Futebol123"])
async def test_senhas_fracas_recusadas(client, pwd):
    r = await client.post("/api/auth/register", json={"email": "x@test.com", "name": "Xis", "password": pwd, "phone": "21987654321"})
    assert r.status_code == 422, pwd


async def test_nova_senha_igual_a_atual_recusada(client, session_factory):
    await _make_user(session_factory, "troca@test.com", "JOGADOR", password=STRONG)
    login = await client.post("/api/auth/login", json={"email": "troca@test.com", "password": STRONG})
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}
    r = await client.post("/api/auth/change-password", json={"current_password": STRONG, "new_password": STRONG}, headers=h)
    assert r.status_code == 422


async def test_troca_de_senha_obrigatoria_para_usuario_criado_pelo_admin(client, admin_headers):
    r = await client.post("/api/users", json={"email": "novo@test.com", "name": "Novo", "password": STRONG}, headers=admin_headers)
    assert r.status_code == 201 and r.json()["must_change_password"] is True
    login = (await client.post("/api/auth/login", json={"email": "novo@test.com", "password": STRONG})).json()
    assert login["user"]["must_change_password"] is True
    h = {"Authorization": f"Bearer {login['access_token']}"}
    r = await client.get("/api/players", headers=h)
    assert r.status_code == 403 and r.json()["code"] == "PASSWORD_CHANGE_REQUIRED"
    assert (await client.get("/api/auth/me", headers=h)).status_code == 200
    r = await client.post("/api/auth/change-password", json={"current_password": STRONG, "new_password": "Bola-no-angulo-99"}, headers=h)
    assert r.status_code == 204
    login = (await client.post("/api/auth/login", json={"email": "novo@test.com", "password": "Bola-no-angulo-99"})).json()
    h = {"Authorization": f"Bearer {login['access_token']}"}
    assert (await client.get("/api/players", headers=h)).status_code == 200


# ---------------------------------------------------------------- upload

async def _player(client, admin_headers) -> int:
    body = {"name": "Foto Teste", "type": "MENSALISTA", "primary_position": "ALA"}
    return (await client.post("/api/players", json=body, headers=admin_headers)).json()["id"]


async def test_html_disfarcado_de_png_recusado(client, admin_headers):
    pid = await _player(client, admin_headers)
    evil = b"<html><script>alert(document.cookie)</script></html>"
    r = await client.put(f"/api/players/{pid}/photo", files={"file": ("x.png", evil, "image/png")}, headers=admin_headers)
    assert r.status_code == 422


async def test_foto_regravada_sem_metadados(client, admin_headers):
    pid = await _player(client, admin_headers)
    exif = Image.Exif()
    exif[0x010F] = "Camera Fabricante"  # Make
    exif[0x010E] = "Casa do jogador, lat -22.90 lon -43.17"  # ImageDescription (dado pessoal)
    jpg = image_bytes("JPEG", size=(3000, 2000), exif=exif.tobytes())
    r = await client.put(f"/api/players/{pid}/photo", files={"file": ("x.jpg", jpg, "image/jpeg")}, headers=admin_headers)
    assert r.status_code == 200
    saved = (await client.get(r.json()["photo_url"])).content
    with Image.open(BytesIO(saved)) as img:
        assert img.format == "WEBP" and max(img.size) <= 1024
        assert not img.getexif()  # sem EXIF/GPS


async def test_upload_grande_demais_recusado(client, admin_headers):
    pid = await _player(client, admin_headers)
    big = b"\x00" * (get_settings().max_photo_mb * 1024 * 1024 + 1)
    r = await client.put(f"/api/players/{pid}/photo", files={"file": ("x.png", big, "image/png")}, headers=admin_headers)
    assert r.status_code == 422 and "MB" in r.json()["detail"]


# ---------------------------------------------------------------- tokens

async def test_tokens_antigos_sao_limpos_no_login(client, session_factory):
    user = await _make_user(session_factory, "limpeza@test.com", "JOGADOR")
    async with session_factory() as s:
        old = datetime.now(UTC) - timedelta(days=60)
        s.add(RefreshToken(user_id=user.id, token_hash=hash_refresh_token("velho"), created_at=old, expires_at=old))
        await s.commit()
    await client.post("/api/auth/login", json={"email": "limpeza@test.com", "password": "senha123"})
    async with session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(RefreshToken).where(RefreshToken.user_id == user.id)) == 1
