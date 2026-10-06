from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def snapshot(obj: Any, exclude: set[str] | None = None) -> dict:
    """Foto das colunas de um model para before/after da auditoria."""
    exclude = (exclude or set()) | {"password_hash", "created_at", "updated_at"}
    return {
        attr.key: _jsonable(getattr(obj, attr.key))
        for attr in inspect(obj).mapper.column_attrs
        if attr.key not in exclude
    }


async def record(
    session: AsyncSession,
    *,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: Any = None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """Adiciona o log na mesma transação da alteração (commit fica com o chamador)."""
    session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            before=before,
            after=after,
        )
    )
