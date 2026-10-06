from datetime import datetime

from sqlalchemy import func, select, update

from app.models.enums import UserStatus
from app.models.user import RefreshToken, User
from app.repositories.base import Repository


class UserRepository(Repository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email.lower()))

    async def get_by_player(self, player_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.player_id == player_id))

    async def list(self, status: UserStatus | None = None) -> list[User]:
        stmt = select(User).order_by(User.name)
        if status:
            stmt = stmt.where(User.status == status)
        return list(await self.session.scalars(stmt))

    async def count(self) -> int:
        return await self.session.scalar(select(func.count(User.id))) or 0


class RefreshTokenRepository(Repository[RefreshToken]):
    model = RefreshToken

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return await self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )

    async def revoke_all_for_user(self, user_id: int, now: datetime) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
