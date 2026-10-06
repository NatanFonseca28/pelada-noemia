from fastapi import APIRouter, status

from app.core.deps import AdminUser, SessionDep
from app.models.enums import UserStatus
from app.schemas.user import UserApprove, UserCreate, UserOut, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Usuários"])


@router.get("", response_model=list[UserOut])
async def list_users(admin: AdminUser, session: SessionDep, status: UserStatus | None = None):
    return await UserService(session).list(status)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, admin: AdminUser, session: SessionDep):
    return await UserService(session).create(data, admin)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, admin: AdminUser, session: SessionDep):
    return await UserService(session).get(user_id)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: int, data: UserUpdate, admin: AdminUser, session: SessionDep):
    return await UserService(session).update(user_id, data, admin)


@router.post("/{user_id}/approve", response_model=UserOut)
async def approve_user(user_id: int, data: UserApprove, admin: AdminUser, session: SessionDep):
    return await UserService(session).approve(user_id, data, admin)


@router.post("/{user_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_user(user_id: int, admin: AdminUser, session: SessionDep):
    await UserService(session).reject(user_id, admin)
