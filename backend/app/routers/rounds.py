from fastapi import APIRouter, status

from app.core.deps import AdminUser, CurrentUser, SessionDep
from app.core.errors import NotFoundError
from app.schemas.round import AttendanceSet, DrawRequest, MoveRequest, RoundCreate, RoundDetail, RoundSummary
from app.services.round_service import RoundService

router = APIRouter(prefix="/rounds", tags=["Rodadas e sorteio"])


@router.get("", response_model=list[RoundSummary])
async def list_rounds(user: CurrentUser, session: SessionDep):
    return await RoundService(session).list()


@router.get("/current", response_model=RoundDetail)
async def current_round(user: CurrentUser, session: SessionDep):
    """Rodada mais recente não encerrada (para confirmar presença e ver os times)."""
    service = RoundService(session)
    rnd = await service.current()
    if rnd is None:
        raise NotFoundError("Nenhuma rodada aberta")
    return await service.detail(rnd.id, user)


@router.get("/{round_id}", response_model=RoundDetail)
async def get_round(round_id: int, user: CurrentUser, session: SessionDep):
    return await RoundService(session).detail(round_id, user)


@router.post("", response_model=RoundDetail, status_code=status.HTTP_201_CREATED)
async def create_round(data: RoundCreate, admin: AdminUser, session: SessionDep):
    service = RoundService(session)
    rnd = await service.create(data.date, data.notes, admin)
    return await service.detail(rnd.id, admin)


@router.delete("/{round_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_round(round_id: int, admin: AdminUser, session: SessionDep, force: bool = False):
    """Exclui a rodada. Rodada já realizada (travada/encerrada) exige `force=true`: apaga também presenças,
    sorteios, times, campeonato, partidas e súmula. Mensalidades e caixa não são afetados."""
    await RoundService(session).delete(round_id, admin, force)


@router.put("/{round_id}/attendance/me", response_model=RoundDetail)
async def set_my_attendance(round_id: int, data: AttendanceSet, user: CurrentUser, session: SessionDep):
    """O próprio jogador confirma ou cancela presença (lista precisa estar aberta)."""
    service = RoundService(session)
    await service.set_my_attendance(round_id, data.confirmed, user)
    return await service.detail(round_id, user)


@router.put("/{round_id}/attendances/{player_id}", response_model=RoundDetail)
async def set_attendance(round_id: int, player_id: int, data: AttendanceSet, admin: AdminUser, session: SessionDep):
    """ADMIN adiciona/remove confirmados (ex.: diarista que avisou pelo WhatsApp)."""
    service = RoundService(session)
    await service.set_attendance(round_id, player_id, data.confirmed, admin, as_admin=True)
    return await service.detail(round_id, admin)


@router.delete("/{round_id}/attendances/{player_id}", response_model=RoundDetail)
async def clear_attendance(round_id: int, player_id: int, admin: AdminUser, session: SessionDep):
    """ADMIN volta o jogador para "sem resposta"."""
    service = RoundService(session)
    await service.clear_attendance(round_id, player_id, admin)
    return await service.detail(round_id, admin)


@router.post("/{round_id}/draw", response_model=RoundDetail)
async def draw(round_id: int, data: DrawRequest, admin: AdminUser, session: SessionDep):
    """Sorteia (ou refaz) os times. `num_teams` escolhe uma formação alternativa; `seed` reproduz um sorteio."""
    service = RoundService(session)
    await service.draw(round_id, data.num_teams, data.seed, admin, data.allow_short_team)
    return await service.detail(round_id, admin)


@router.post("/{round_id}/move", response_model=RoundDetail)
async def move_player(round_id: int, data: MoveRequest, admin: AdminUser, session: SessionDep):
    """Ajuste manual: mover jogador de time, trocar papel (revezamento/goleiro) ou tirar do time."""
    service = RoundService(session)
    await service.move(round_id, data.player_id, data.team_id, data.role, admin)
    return await service.detail(round_id, admin)


def _status_route(action: str, summary: str):
    async def handler(round_id: int, admin: AdminUser, session: SessionDep):
        service = RoundService(session)
        await service.set_status(round_id, action, admin)
        return await service.detail(round_id, admin)

    router.add_api_route(f"/{{round_id}}/{action}", handler, methods=["POST"], response_model=RoundDetail,
                         summary=summary, name=f"round_{action}")


_status_route("open", "Abrir a lista de presença")
_status_route("close", "Fechar a lista de presença")
_status_route("lock", "Travar os times")
_status_route("unlock", "Destravar os times")
