from datetime import datetime

from app.schemas.common import ORMModel


class AuditLogOut(ORMModel):
    id: int
    user_id: int | None
    user_name: str | None = None
    action: str
    entity: str
    entity_id: str | None
    before: dict | None
    after: dict | None
    created_at: datetime
