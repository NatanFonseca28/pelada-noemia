"""Monitoramento de erros (Sentry). Só liga com SENTRY_DSN definido; nunca envia dados pessoais."""
import re

import sentry_sdk

from app.core.config import get_settings

SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-forwarded-for"}
PHONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")


def _scrub(event: dict, _hint: dict) -> dict:
    request = event.get("request") or {}
    headers = request.get("headers") or {}
    for name in list(headers):
        if name.lower() in SENSITIVE_HEADERS:
            headers[name] = "[removido]"
    request.pop("cookies", None)
    if str(request.get("url", "")).find("/api/auth/") >= 0:
        request.pop("data", None)  # senhas, tokens
    elif "data" in request:
        request["data"] = "[removido]"
    request.pop("query_string", None)  # pode conter token de redefinição de senha
    event.pop("user", None)
    for exc in (event.get("exception") or {}).get("values", []):
        if exc.get("value"):
            exc["value"] = PHONE.sub("[telefone]", exc["value"])
    return event


def init_monitoring() -> bool:
    settings = get_settings()
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        send_default_pii=False,
        traces_sample_rate=0,
        max_request_body_size="never",
        before_send=_scrub,
    )
    return True
