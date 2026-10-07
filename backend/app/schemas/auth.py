from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.passwords import StrongPassword
from app.domain.phone import normalize_mobile
from app.schemas.user import MeOut


class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    password: StrongPassword
    phone: Annotated[str, Field(max_length=30), AfterValidator(normalize_mobile)]


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: MeOut


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: StrongPassword


class ForgotIn(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)  # e-mail ou celular


class ResetIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: StrongPassword


class PasswordRequestOut(BaseModel):
    id: int
    user_id: int
    name: str
    email: str
    phone: str | None
    requested_at: datetime
    link_sent_at: datetime | None


class ResetLinkOut(BaseModel):
    url: str
    expires_at: datetime
    name: str
    phone: str | None
