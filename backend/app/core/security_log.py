"""Eventos de segurança em JSON (stdout) para monitoramento. Nunca registra senhas, tokens ou hashes."""
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("pelada.security")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": datetime.now(UTC).isoformat(), "level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        payload.update(getattr(record, "fields", {}))
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(json_logs: bool) -> None:
    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(_JsonFormatter())
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False


def security_event(event: str, **fields: Any) -> None:
    """Ex.: security_event("login_failed", email=..., ip=...)."""
    logger.info(event, extra={"fields": {"event": event, **fields}})
