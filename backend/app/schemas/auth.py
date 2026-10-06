from pydantic import BaseModel, EmailStr, Field

from app.core.passwords import StrongPassword

from app.schemas.user import UserOut


class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    password: StrongPassword


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: StrongPassword
