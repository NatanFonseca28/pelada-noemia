from datetime import datetime

from pydantic import BaseModel

from app.models.enums import UserRole


class PageInfo(BaseModel):
    path: str
    label: str


class PageVisibilityOut(BaseModel):
    pages: list[PageInfo]
    # categoria → páginas ocultas
    hidden: dict[UserRole, list[str]]


class PageVisibilityIn(BaseModel):
    hidden: dict[UserRole, list[str]]


class AccessLogOut(BaseModel):
    id: int
    user_id: int | None
    user_name: str | None = None
    email: str
    event: str
    ip: str | None
    user_agent: str | None
    created_at: datetime
