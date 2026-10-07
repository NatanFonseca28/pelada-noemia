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
