from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-secret-change-me-dev-secret-change-me"
DEFAULT_DB_PASSWORDS = {"pelada", "postgres", "password", "admin", ""}


def asyncpg_url(url: str | None) -> str | None:
    """Aceita a URL como os provedores entregam (ex.: Neon: postgresql://…?sslmode=require&channel_binding=require)
    e converte para o driver asyncpg: esquema postgresql+asyncpg e `ssl=` no lugar de `sslmode` (que o asyncpg
    não entende); `channel_binding` é descartado."""
    if not url:
        return url
    parts = urlsplit(url)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    query = []
    for key, value in parse_qsl(parts.query):
        if key == "sslmode":
            query.append(("ssl", value))
        elif key != "channel_binding":
            query.append((key, value))
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class InsecureConfigError(RuntimeError):
    """Configuração insegura em produção: a API se recusa a subir."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["dev", "production"] = "dev"

    database_url: str = "postgresql+asyncpg://pelada:pelada@localhost:5432/pelada"
    # Migrations rodam com o dono do schema; a app usa um usuário de privilégio mínimo (produção)
    migrations_database_url: str | None = None
    test_database_url: str = "postgresql+asyncpg://pelada:pelada@localhost:5432/pelada_test"

    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    refresh_cookie_name: str = "pelada_refresh"
    cookie_secure: bool = False

    cors_origins: str = "http://localhost:5173"
    # Hosts aceitos no header Host (TrustedHostMiddleware)
    allowed_hosts: str = "localhost,127.0.0.1,api,test,testserver"

    # Proteções de autenticação
    rate_limit_enabled: bool = True
    login_max_failures: int = 10  # bloqueio temporário da conta após N senhas erradas seguidas
    login_lock_minutes: int = 15

    media_dir: Path = Path("media")
    max_photo_mb: int = 3

    # Sentry (avisos de erro). Vazio = desligado.
    sentry_dsn: str | None = None
    # football-data.org: catálogo de clubes para os nomes dos times do sorteio (nunca vai ao front)
    football_data_token: str | None = None

    admin_email: str = "admin@pelada.app"
    admin_password: str = "admin123-dev-only"

    @field_validator("database_url", "migrations_database_url", "test_database_url")
    @classmethod
    def _asyncpg(cls, value: str | None) -> str | None:
        return asyncpg_url(value)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def docs_enabled(self) -> bool:
        return not self.is_production

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @model_validator(mode="after")
    def refuse_insecure_production(self) -> "Settings":
        """Em produção, não sobe com segredo padrão, cookie inseguro, origem/host local ou senha de banco padrão."""
        if not self.is_production:
            return self
        problems: list[str] = []
        if self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET padrão ou com menos de 32 caracteres (gere com: openssl rand -base64 48)")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE precisa ser true (cookie de sessão só por HTTPS)")
        local = ("localhost", "127.0.0.1")
        if not self.cors_origin_list or any(any(h in o for h in local) or o.startswith("http://") for o in self.cors_origin_list):
            problems.append("CORS_ORIGINS precisa listar só o domínio público em https://")
        if not self.allowed_host_list or any(h in local or h in ("test", "testserver") for h in self.allowed_host_list):
            problems.append("ALLOWED_HOSTS precisa listar só o domínio público (e o nome interno 'api')")
        for name, url in (("DATABASE_URL", self.database_url), ("MIGRATIONS_DATABASE_URL", self.migrations_database_url)):
            if url and (urlsplit(url.replace("+asyncpg", "")).password or "") in DEFAULT_DB_PASSWORDS:
                problems.append(f"{name} usa senha de banco padrão/fraca")
            if url and "-pooler." in (urlsplit(url).hostname or ""):
                # PgBouncer em modo transação quebra os prepared statements do asyncpg
                problems.append(f"{name} aponta para o endpoint com pooling do Neon (-pooler): use a conexão direta")
        if problems:
            raise InsecureConfigError("Configuração insegura para produção:\n- " + "\n- ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
