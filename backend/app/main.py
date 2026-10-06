import mimetypes
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ratelimit import limiter, rate_limit_handler
from app.core.security_log import configure_logging
from app.routers import audit, auth, dashboard, export, finance, players, rounds, settings, stats, tournaments, users

app_settings = get_settings()  # em produção, falha aqui se a configuração for insegura
configure_logging(json_logs=app_settings.is_production)

app = FastAPI(
    title="Pelada Manager API",
    version="0.1.0",
    description="API para gestão da pelada semanal: jogadores, sorteio, campeonato e súmulas.",
    # Documentação interativa só fora de produção
    docs_url="/api/docs" if app_settings.docs_enabled else None,
    redoc_url="/api/redoc" if app_settings.docs_enabled else None,
    openapi_url="/api/openapi.json" if app_settings.docs_enabled else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=app_settings.allowed_host_list)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    path = request.url.path
    if app_settings.is_production and not path.startswith("/api/media"):
        # Respostas da API são JSON: nada pode ser executado nem embutido
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    if path.startswith("/api/auth") or path.startswith("/api/export"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code, **({"details": exc.details} if exc.details else {})},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {
            "field": ".".join(str(p) for p in err["loc"] if p != "body"),
            "message": str(err["msg"]).removeprefix("Value error, "),
        }
        for err in exc.errors()
    ]
    first = errors[0]["message"] if errors else "Dados inválidos"
    return JSONResponse(status_code=422, content={"detail": first, "code": "VALIDATION", "errors": errors})


api = APIRouter(prefix="/api")
for module in (auth, users, players, rounds, tournaments, stats, settings, finance, dashboard, export, audit):
    api.include_router(module.router)


@api.get("/health", tags=["Infra"])
async def health() -> dict:
    return {"status": "ok"}


app.include_router(api)

# Imagens slim do Python não têm /etc/mime.types: registra o WEBP (fotos são regravadas nesse formato)
mimetypes.add_type("image/webp", ".webp")

media_dir = Path(app_settings.media_dir)
media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/media", StaticFiles(directory=media_dir), name="media")
