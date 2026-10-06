from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.core.passwords import StrongPassword
from app.models.enums import UserRole, UserStatus
from app.schemas.common import ORMModel


class UserOut(ORMModel):
    id: int
    email: str
    name: str
    role: UserRole
    status: UserStatus
    player_id: int | None
    approved_at: datetime | None
    created_at: datetime
    must_change_password: bool = False
    is_superadmin: bool = False


class MeOut(UserOut):
    """Usuário logado + páginas ocultas para a categoria dele (vazio para o superadmin)."""

    hidden_pages: list[str] = []


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    password: StrongPassword
    role: UserRole = UserRole.JOGADOR
    player_id: int | None = None


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    role: UserRole | None = None
    status: UserStatus | None = None
    player_id: int | None = None
    unlink_player: bool = False
    password: StrongPassword | None = None


class UserApprove(BaseModel):
    role: UserRole = UserRole.JOGADOR
    player_id: int | None = None
