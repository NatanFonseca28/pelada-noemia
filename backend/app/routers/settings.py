from fastapi import APIRouter

from app.core.deps import AdminUser, CurrentUser, SessionDep
from app.schemas.settings import SettingsOut, SettingsUpdate
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["Configurações"])


@router.get("", response_model=SettingsOut)
async def get_settings(user: CurrentUser, session: SessionDep):
    return await SettingsService(session).get()


@router.put("", response_model=SettingsOut)
async def update_settings(data: SettingsUpdate, admin: AdminUser, session: SessionDep):
    return await SettingsService(session).update(data, admin)
