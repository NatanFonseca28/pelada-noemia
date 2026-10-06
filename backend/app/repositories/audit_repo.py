from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.user import User
from app.repositories.base import Repository


class AuditRepository(Repository[AuditLog]):
    model = AuditLog

    async def list(
        self, *, entity: str | None = None, entity_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[tuple[AuditLog, str | None]]:
        stmt = (
            select(AuditLog, User.name)
            .outerjoin(User, User.id == AuditLog.user_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
        if entity:
            stmt = stmt.where(AuditLog.entity == entity)
        if entity_id:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
        return [(row[0], row[1]) for row in await self.session.execute(stmt)]
