from fastapi import APIRouter, Query

from app.core.deps import AdminUser, SessionDep
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogOut

router = APIRouter(prefix="/audit", tags=["Auditoria"])


@router.get("", response_model=list[AuditLogOut])
async def list_audit(
    admin: AdminUser,
    session: SessionDep,
    entity: str | None = None,
    entity_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    rows = await AuditRepository(session).list(entity=entity, entity_id=entity_id, limit=limit, offset=offset)
    return [
        AuditLogOut.model_validate(log).model_copy(update={"user_name": user_name})
        for log, user_name in rows
    ]
