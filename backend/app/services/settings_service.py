from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import PeladaSettings
from app.models.user import User
from app.repositories.settings_repo import SettingsRepository
from app.schemas.settings import SettingsUpdate
from app.services import audit_service


class SettingsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SettingsRepository(session)

    async def get(self) -> PeladaSettings:
        current = await self.repo.get_current()
        await self.session.commit()
        return current

    async def update(self, data: SettingsUpdate, actor: User) -> PeladaSettings:
        current = await self.repo.get_current()
        before = audit_service.snapshot(current)
        for key, value in data.model_dump(mode="python").items():
            if key == "tiebreakers":
                value = [str(v) for v in value]
            setattr(current, key, value)
        await audit_service.record(
            self.session, user_id=actor.id, action="UPDATE", entity="settings", entity_id=1,
            before=before, after=audit_service.snapshot(current),
        )
        await self.session.commit()
        await self.session.refresh(current)
        return current
