from app.models.settings import PeladaSettings
from app.repositories.base import Repository


class SettingsRepository(Repository[PeladaSettings]):
    model = PeladaSettings

    async def get_current(self) -> PeladaSettings:
        current = await self.get(1)
        if current is None:
            current = self.add(PeladaSettings(id=1))
            await self.session.flush()
        return current
