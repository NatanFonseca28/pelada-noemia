from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.enums import UserRole, UserStatus
from app.models.user import User

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False)


# Rotas liberadas enquanto o usuário precisa trocar a senha (1º acesso / senha redefinida pelo admin)
PASSWORD_CHANGE_ALLOWED = {"/api/auth/me", "/api/auth/change-password", "/api/auth/logout"}


async def get_current_user(
    request: Request,
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise UnauthorizedError("Autenticação necessária")
    user = await user_from_token(session, credentials.credentials)
    if user.must_change_password and request.url.path not in PASSWORD_CHANGE_ALLOWED:
        raise ForbiddenError("Troque sua senha para continuar", code="PASSWORD_CHANGE_REQUIRED")
    return user


async def user_from_token(session: AsyncSession, token: str) -> User:
    """Também usado pelo WebSocket (token na query string)."""
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Token inválido ou expirado", code="TOKEN_INVALID") from exc
    user = await session.get(User, int(payload["sub"]))
    if user is None or user.status != UserStatus.ATIVO:
        raise UnauthorizedError("Usuário inativo")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable:
    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError("Permissão insuficiente")
        return user

    return checker


AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]


async def require_superadmin(user: CurrentUser) -> User:
    if not (user.is_superadmin and user.role == UserRole.ADMIN):
        raise ForbiddenError("Restrito ao superadmin")
    return user


SuperAdminUser = Annotated[User, Depends(require_superadmin)]
StaffUser = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.MESARIO))]
