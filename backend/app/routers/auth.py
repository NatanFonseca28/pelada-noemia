from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response, status

from app.core.config import get_settings
from app.core.deps import CurrentUser, SessionDep
from app.core.ratelimit import LOGIN_LIMIT, PASSWORD_LIMIT, REFRESH_LIMIT, REGISTER_LIMIT, limiter
from app.schemas.auth import ChangePasswordIn, LoginIn, RegisterIn, TokenOut
from app.schemas.user import UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Autenticação"])

settings = get_settings()
RefreshCookie = Annotated[str | None, Cookie(alias=settings.refresh_cookie_name)]


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.refresh_cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/auth",
        max_age=settings.refresh_token_days * 24 * 3600,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(REGISTER_LIMIT)
async def register(request: Request, data: RegisterIn, session: SessionDep):
    """Autocadastro público: o usuário fica PENDENTE até aprovação do ADMIN."""
    return await AuthService(session).register(email=data.email, name=data.name, password=data.password)


@router.post("/login", response_model=TokenOut)
@limiter.limit(LOGIN_LIMIT)
async def login(request: Request, data: LoginIn, response: Response, session: SessionDep):
    ip = request.client.host if request.client else None
    user, access, refresh = await AuthService(session).login(data.email, data.password, ip=ip)
    _set_refresh_cookie(response, refresh)
    return TokenOut(access_token=access, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=TokenOut)
@limiter.limit(REFRESH_LIMIT)
async def refresh(request: Request, response: Response, session: SessionDep, refresh_token: RefreshCookie = None):
    user, access, new_refresh = await AuthService(session).refresh(refresh_token)
    _set_refresh_cookie(response, new_refresh)
    return TokenOut(access_token=access, user=UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, session: SessionDep, refresh_token: RefreshCookie = None):
    await AuthService(session).logout(refresh_token)
    response.delete_cookie(settings.refresh_cookie_name, path="/api/auth")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(PASSWORD_LIMIT)
async def change_password(request: Request, data: ChangePasswordIn, user: CurrentUser, session: SessionDep):
    await AuthService(session).change_password(user, data.current_password, data.new_password)
