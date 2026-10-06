from fastapi import APIRouter, Query

from app.core.deps import SessionDep, SuperAdminUser
from app.schemas.access import AccessLogOut, PageVisibilityIn, PageVisibilityOut
from app.services.access_service import AccessService

router = APIRouter(prefix="/access", tags=["Superadmin"])


@router.get("/pages", response_model=PageVisibilityOut)
async def get_pages(admin: SuperAdminUser, session: SessionDep):
    """Páginas que podem ser ocultadas e quais estão ocultas para cada categoria."""
    return await AccessService(session).visibility()


@router.put("/pages", response_model=PageVisibilityOut)
async def set_pages(data: PageVisibilityIn, admin: SuperAdminUser, session: SessionDep):
    return await AccessService(session).set_visibility(data, admin)


@router.get("/log", response_model=list[AccessLogOut])
async def access_log(
    admin: SuperAdminUser,
    session: SessionDep,
    email: str | None = None,
    event: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Entradas, tentativas com senha errada, bloqueios e saídas."""
    return await AccessService(session).log(email=email, event=event, limit=limit, offset=offset)
