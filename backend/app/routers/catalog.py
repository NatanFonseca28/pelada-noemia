from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.deps import AdminUser, SessionDep, SuperAdminUser
from app.core.errors import ValidationError
from app.db.session import SessionLocal
from app.services import audit_service
from app.services.team_catalog_service import TeamCatalogService

router = APIRouter(prefix="/catalog", tags=["Campeonatos do sorteio"])


class CompetitionOut(BaseModel):
    code: str
    name: str
    season: int | None
    clubs: int
    updated_at: datetime | None


class SyncStarted(BaseModel):
    message: str


@router.get("/competitions", response_model=list[CompetitionOut])
async def competitions(admin: AdminUser, session: SessionDep):
    """Campeonatos disponíveis para dar nomes de clubes aos times do sorteio."""
    return await TeamCatalogService(session).competitions()


async def _sync() -> None:
    async with SessionLocal() as session:
        await TeamCatalogService(session).sync()


@router.post("/sync", response_model=SyncStarted, status_code=status.HTTP_202_ACCEPTED)
async def sync(admin: SuperAdminUser, session: SessionDep, background: BackgroundTasks):
    """Atualiza clubes e escudos do football-data.org (cerca de 1,5 min, em segundo plano)."""
    if not get_settings().football_data_token:
        raise ValidationError("Configure FOOTBALL_DATA_TOKEN no servidor para atualizar os campeonatos.")
    await audit_service.record(session, user_id=admin.id, action="SYNC", entity="catalog", entity_id=0)
    await session.commit()
    background.add_task(_sync)
    return SyncStarted(message="Atualização iniciada. Leva cerca de 1 minuto e meio.")
