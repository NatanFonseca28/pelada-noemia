from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.enums import Position
from app.models.player import Player
from app.models.user import User
from app.repositories.player_repo import PlayerRepository
from app.schemas.player import PlayerCreate, PlayerUpdate, _validate_positions
from app.services import audit_service, storage


class PlayerService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.players = PlayerRepository(session)

    async def list(
        self, *, active: bool | None = None, position: Position | None = None, search: str | None = None
    ) -> list[Player]:
        return await self.players.list(active=active, position=position, search=search)

    async def get(self, player_id: int) -> Player:
        player = await self.players.get(player_id)
        if player is None:
            raise NotFoundError("Jogador não encontrado")
        return player

    async def create(self, data: PlayerCreate, actor: User) -> Player:
        player = self.players.add(Player(**data.model_dump()))
        await self.session.flush()
        await audit_service.record(
            self.session, user_id=actor.id, action="CREATE", entity="player", entity_id=player.id,
            after=audit_service.snapshot(player),
        )
        await self.session.commit()
        return player

    async def update(self, player_id: int, data: PlayerUpdate, actor: User) -> Player:
        player = await self.get(player_id)
        before = audit_service.snapshot(player)
        changes = data.model_dump(exclude_unset=True)
        for field in ("name", "type", "primary_position", "active", "whatsapp_opt_in"):
            if field in changes and changes[field] is None:
                raise ValidationError(f"Campo '{field}' não pode ser nulo")
        for key, value in changes.items():
            setattr(player, key, value)
        if player.primary_position == Position.GOLEIRO_FIXO:
            player.secondary_position = None
        try:
            _validate_positions(player.primary_position, player.secondary_position)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        await audit_service.record(
            self.session, user_id=actor.id, action="UPDATE", entity="player", entity_id=player.id,
            before=before, after=audit_service.snapshot(player),
        )
        await self.session.commit()
        await self.session.refresh(player)
        return player

    async def delete(self, player_id: int, actor: User) -> None:
        """Exclusão definitiva só sem histórico; com histórico, use 'ativo = false'."""
        player = await self.get(player_id)
        before = audit_service.snapshot(player)
        photo = player.photo_path
        await self.players.delete(player)
        await audit_service.record(
            self.session, user_id=actor.id, action="DELETE", entity="player", entity_id=player_id,
            before=before,
        )
        await storage.delete_file(self.session, photo)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(
                "Jogador possui histórico e não pode ser excluído; marque-o como inativo"
            ) from exc

    async def set_photo(self, player_id: int, content: bytes, actor: User) -> Player:
        player = await self.get(player_id)
        old = player.photo_path
        player.photo_path = storage.save_photo(self.session, content)
        await storage.delete_file(self.session, old)
        await audit_service.record(
            self.session, user_id=actor.id, action="UPDATE_PHOTO", entity="player", entity_id=player.id,
            before={"photo_path": old}, after={"photo_path": player.photo_path},
        )
        await self.session.commit()
        await self.session.refresh(player)
        return player

    async def remove_photo(self, player_id: int, actor: User) -> Player:
        player = await self.get(player_id)
        old = player.photo_path
        player.photo_path = None
        await audit_service.record(
            self.session, user_id=actor.id, action="REMOVE_PHOTO", entity="player", entity_id=player.id,
            before={"photo_path": old},
        )
        await storage.delete_file(self.session, old)
        await self.session.commit()
        await self.session.refresh(player)
        return player
