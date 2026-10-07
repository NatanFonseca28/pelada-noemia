from fastapi import APIRouter, File, UploadFile, status

from app.core.config import get_settings
from app.core.deps import AdminUser, CurrentUser, SessionDep
from app.models.enums import Position, UserRole
from app.models.player import Player
from app.models.user import User
from app.schemas.player import PlayerCreate, PlayerOut, PlayerUpdate
from app.services.player_service import PlayerService
from app.services.storage import read_limited

router = APIRouter(prefix="/players", tags=["Jogadores"])


# Campos internos da gestão: nível técnico e velocidade (sorteio equilibrado) e contato (cobrança por WhatsApp)
ADMIN_ONLY_FIELDS = {"skill_level": None, "speed": None, "phone": None, "whatsapp_opt_in": False}


def _visible(player: Player, user: User) -> PlayerOut:
    out = PlayerOut.model_validate(player)
    return out if user.role == UserRole.ADMIN else out.model_copy(update=ADMIN_ONLY_FIELDS)


@router.get("", response_model=list[PlayerOut])
async def list_players(
    user: CurrentUser,
    session: SessionDep,
    active: bool | None = None,
    position: Position | None = None,
    q: str | None = None,
):
    players = await PlayerService(session).list(active=active, position=position, search=q)
    return [_visible(p, user) for p in players]


@router.get("/{player_id}", response_model=PlayerOut)
async def get_player(player_id: int, user: CurrentUser, session: SessionDep):
    return _visible(await PlayerService(session).get(player_id), user)


@router.post("", response_model=PlayerOut, status_code=status.HTTP_201_CREATED)
async def create_player(data: PlayerCreate, admin: AdminUser, session: SessionDep):
    return await PlayerService(session).create(data, admin)


@router.patch("/{player_id}", response_model=PlayerOut)
async def update_player(player_id: int, data: PlayerUpdate, admin: AdminUser, session: SessionDep):
    return await PlayerService(session).update(player_id, data, admin)


@router.delete("/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_player(player_id: int, admin: AdminUser, session: SessionDep):
    await PlayerService(session).delete(player_id, admin)


@router.put("/{player_id}/photo", response_model=PlayerOut)
async def upload_photo(player_id: int, admin: AdminUser, session: SessionDep, file: UploadFile = File(...)):
    content = await read_limited(file, get_settings().max_photo_mb * 1024 * 1024, "Imagem")
    return await PlayerService(session).set_photo(player_id, content, admin)


@router.delete("/{player_id}/photo", response_model=PlayerOut)
async def delete_photo(player_id: int, admin: AdminUser, session: SessionDep):
    return await PlayerService(session).remove_photo(player_id, admin)
