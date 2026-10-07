from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import CurrentUser, SessionDep
from app.core.ratelimit import LOGIN_LIMIT, PASSWORD_LIMIT, REFRESH_LIMIT, REGISTER_LIMIT, limiter
from app.models.user import User
from app.schemas.auth import ChangePasswordIn, ForgotIn, LoginIn, RegisterIn, ResetIn, TokenOut
from app.schemas.user import MeOut, UserOut
from app.services.access_service import hidden_pages_for
from app.services.auth_service import AuthService
from app.services.password_reset_service import PasswordResetService

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
    return await AuthService(session).register(email=data.email, name=data.name, password=data.password,
                                               phone=data.phone)


@router.post("/login", response_model=TokenOut)
@limiter.limit(LOGIN_LIMIT)
async def login(request: Request, data: LoginIn, response: Response, session: SessionDep):
    user, access, refresh = await AuthService(session).login(data.email, data.password, ip=_ip(request),
                                                             user_agent=request.headers.get("user-agent"))
    _set_refresh_cookie(response, refresh)
    return TokenOut(access_token=access, user=await _me(session, user))


@router.post("/refresh", response_model=TokenOut)
@limiter.limit(REFRESH_LIMIT)
async def refresh(request: Request, response: Response, session: SessionDep, refresh_token: RefreshCookie = None):
    user, access, new_refresh = await AuthService(session).refresh(refresh_token)
    _set_refresh_cookie(response, new_refresh)
    return TokenOut(access_token=access, user=await _me(session, user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, session: SessionDep, refresh_token: RefreshCookie = None):
    await AuthService(session).logout(refresh_token, ip=_ip(request), user_agent=request.headers.get("user-agent"))
    response.delete_cookie(settings.refresh_cookie_name, path="/api/auth")


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser, session: SessionDep):
    return await _me(session, user)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _me(session: AsyncSession, user: User) -> MeOut:
    return MeOut.model_validate(user).model_copy(update={"hidden_pages": await hidden_pages_for(session, user)})


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(PASSWORD_LIMIT)
async def change_password(request: Request, data: ChangePasswordIn, user: CurrentUser, session: SessionDep):
    await AuthService(session).change_password(user, data.current_password, data.new_password)


FORGOT_MESSAGE = "Pedido enviado. Um administrador vai te mandar o link para criar uma senha nova pelo WhatsApp."


@router.post("/forgot", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(REGISTER_LIMIT)
async def forgot(request: Request, data: ForgotIn, session: SessionDep) -> dict:
    """Esqueci minha senha (e-mail ou celular). Resposta sempre igual: não revela se a conta existe."""
    await PasswordResetService(session).request(data.identifier, _ip(request), request.headers.get("user-agent"))
    return {"detail": FORGOT_MESSAGE}


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(PASSWORD_LIMIT)
async def reset_password(request: Request, data: ResetIn, session: SessionDep):
    """Cria a senha nova a partir do link enviado pelo administrador (1 h, uso único). Derruba todas as sessões."""
    await PasswordResetService(session).reset(data.token, data.new_password, _ip(request))
