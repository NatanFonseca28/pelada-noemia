"""Limite de tentativas por IP (slowapi, memória do processo).

Com proxy reverso, o IP real chega via --proxy-headers do uvicorn (X-Forwarded-For confiável só da rede interna).
Com N workers, cada processo tem seu contador: o limite efetivo é até N× o configurado.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.security_log import security_event

limiter = Limiter(key_func=get_remote_address, enabled=get_settings().rate_limit_enabled, headers_enabled=False)

# Limites por rota de autenticação
LOGIN_LIMIT = "5/minute;30/hour"
REGISTER_LIMIT = "3/hour"
REFRESH_LIMIT = "30/minute"
PASSWORD_LIMIT = "5/minute;20/hour"


async def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    detail = exc.detail if isinstance(exc, RateLimitExceeded) else ""
    security_event("rate_limited", path=request.url.path, ip=get_remote_address(request), limit=str(detail))
    return JSONResponse(
        status_code=429,
        content={"detail": "Muitas tentativas em pouco tempo. Aguarde alguns minutos e tente de novo.", "code": "RATE_LIMITED"},
        headers={"Retry-After": "60"},
    )
