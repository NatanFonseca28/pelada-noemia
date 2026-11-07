from fastapi import APIRouter, Query

from app.core.deps import AdminUser, SessionDep
from app.core.year_lock import FIRST_YEAR
from app.schemas.dashboard import DashboardOut, YearSummaryOut
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard (ADMIN)"])


@router.get("", response_model=DashboardOut)
async def dashboard(admin: AdminUser, session: SessionDep):
    """Números da gestão: elenco, financeiro, rodada atual, temporada e pendências."""
    return await DashboardService(session).build()


@router.get("/year-summary", response_model=YearSummaryOut)
async def year_summary(admin: AdminUser, session: SessionDep, year: int = Query(ge=FIRST_YEAR, le=2100)):
    """Fechamento do ano: jogos, campeão, arrecadação, despesas e o saldo que segue para o ano seguinte."""
    return await DashboardService(session).year_summary(year)
