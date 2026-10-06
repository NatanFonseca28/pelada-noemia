"""Visibilidade de páginas por categoria e log de acessos (login/logout)."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.domain.pages import HIDEABLE_PAGES
from app.models.access_log import AccessLog
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.settings_repo import SettingsRepository
from app.schemas.access import AccessLogOut, PageInfo, PageVisibilityIn, PageVisibilityOut
from app.services import audit_service

ACCESS_LOG_RETENTION_DAYS = 365


async def hidden_pages_for(session: AsyncSession, user: User) -> list[str]:
    if user.is_superadmin:
        return []
    current = await SettingsRepository(session).get_current()
    return list((current.hidden_pages or {}).get(user.role.value, []))


async def record_access(session: AsyncSession, *, event: str, email: str, user_id: int | None,
                        ip: str | None, user_agent: str | None) -> None:
    """Grava no log de acessos (vai junto no commit de quem chamou)."""
    session.add(AccessLog(user_id=user_id, email=email[:255], event=event, ip=(ip or None) and ip[:64],
                          user_agent=(user_agent or None) and user_agent[:300]))


class AccessService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def visibility(self) -> PageVisibilityOut:
        current = await SettingsRepository(self.session).get_current()
        stored = current.hidden_pages or {}
        return PageVisibilityOut(
            pages=[PageInfo(path=p, label=label) for p, label in HIDEABLE_PAGES.items()],
            hidden={role: stored.get(role.value, []) for role in UserRole},
        )

    async def set_visibility(self, data: PageVisibilityIn, actor: User) -> PageVisibilityOut:
        unknown = {p for pages in data.hidden.values() for p in pages} - HIDEABLE_PAGES.keys()
        if unknown:
            raise ValidationError(f"Página não pode ser ocultada: {', '.join(sorted(unknown))}")
        current = await SettingsRepository(self.session).get_current()
        before = current.hidden_pages or {}
        after = {role.value: sorted(set(pages)) for role, pages in data.hidden.items() if pages}
        current.hidden_pages = after
        await audit_service.record(self.session, user_id=actor.id, action="UPDATE", entity="page_visibility",
                                   entity_id="1", before=before, after=after)
        await self.session.commit()
        return await self.visibility()

    async def log(self, *, email: str | None, event: str | None, limit: int, offset: int) -> list[AccessLogOut]:
        # limpeza simples: o log guarda um ano
        await self.session.execute(delete(AccessLog).where(
            AccessLog.created_at < datetime.now(UTC) - timedelta(days=ACCESS_LOG_RETENTION_DAYS)))
        await self.session.commit()
        q = (select(AccessLog, User.name).outerjoin(User, User.id == AccessLog.user_id)
             .order_by(AccessLog.created_at.desc(), AccessLog.id.desc()).limit(limit).offset(offset))
        if email:
            q = q.where(AccessLog.email.ilike(f"%{email.strip()}%"))
        if event:
            q = q.where(AccessLog.event == event)
        rows = (await self.session.execute(q)).all()
        return [AccessLogOut(id=a.id, user_id=a.user_id, user_name=name, email=a.email, event=a.event, ip=a.ip,
                             user_agent=a.user_agent, created_at=a.created_at) for a, name in rows]
