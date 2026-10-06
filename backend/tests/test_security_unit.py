"""Testes unitários de segurança (sem banco): configuração de produção e importação de planilha."""
import io
import zipfile

import pytest

from app.core.config import DEV_JWT_SECRET, InsecureConfigError, Settings
from app.core.errors import ValidationError
from app.services.finance_import_service import read_workbook


def test_producao_recusa_configuracao_insegura():
    with pytest.raises(InsecureConfigError) as exc:
        Settings(environment="production", jwt_secret=DEV_JWT_SECRET, cookie_secure=False,
                 database_url="postgresql+asyncpg://pelada:pelada@db/pelada")
    msg = str(exc.value)
    assert "JWT_SECRET" in msg and "COOKIE_SECURE" in msg and "CORS_ORIGINS" in msg and "senha de banco" in msg


def test_producao_aceita_configuracao_segura():
    s = Settings(
        environment="production",
        jwt_secret="x" * 48,
        cookie_secure=True,
        cors_origins="https://pelada.exemplo.com.br",
        allowed_hosts="pelada.exemplo.com.br,api",
        database_url="postgresql+asyncpg://app:S3nh4-Forte-Do-Banco@db/pelada",
    )
    assert s.is_production and not s.docs_enabled


def test_planilha_zip_bomb_recusada():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/worksheets/sheet1.xml", b"\x00" * (60 * 1024 * 1024))  # comprime para poucos KB
    with pytest.raises(ValidationError, match="grande demais"):
        read_workbook(buf.getvalue())


def test_arquivo_que_nao_e_planilha_recusado():
    with pytest.raises(ValidationError, match="xlsx"):
        read_workbook(b"isto nao e um zip")
