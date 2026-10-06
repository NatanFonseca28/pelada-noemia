from fastapi import APIRouter

from app.core.deps import AdminUser, SessionDep
from app.schemas.dashboard import DashboardOut
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard (ADMIN)"])


@router.get("", response_model=DashboardOut)
async def dashboard(admin: AdminUser, session: SessionDep):
    """Números da gestão: elenco, financeiro, rodada atual, temporada e pendências."""
    return await DashboardService(session).build()
