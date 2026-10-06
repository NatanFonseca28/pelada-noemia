from sqlalchemy import or_, select

from app.models.enums import Position
from app.models.player import Player
from app.repositories.base import Repository


class PlayerRepository(Repository[Player]):
    model = Player

    async def list(
        self,
        *,
        active: bool | None = None,
        position: Position | None = None,
        search: str | None = None,
    ) -> list[Player]:
        stmt = select(Player).order_by(Player.name)
        if active is not None:
            stmt = stmt.where(Player.active == active)
        if position:
            stmt = stmt.where(Player.primary_position == position)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(Player.name.ilike(like), Player.nickname.ilike(like)))
        return list(await self.session.scalars(stmt))
