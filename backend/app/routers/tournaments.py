from decimal import Decimal

from fastapi import APIRouter, Query, status

from app.core.deps import AdminUser, CurrentUser, SessionDep, StaffUser
from app.core.errors import NotFoundError
from app.schemas.tournament import FormatsOut, MatchResultIn, TournamentCreate, TournamentOut
from app.services.tournament_service import TournamentService

router = APIRouter(tags=["Campeonato"])


@router.get("/rounds/{round_id}/tournament/formats", response_model=FormatsOut)
async def formats(round_id: int, admin: AdminUser, session: SessionDep,
                  final_weight: Decimal | None = Query(None, ge=1, le=3)):
    """Formatos possíveis para o nº de times da rodada, com total de jogos e minutos por partida."""
    return await TournamentService(session).formats(round_id, final_weight)


@router.post("/rounds/{round_id}/tournament", response_model=TournamentOut, status_code=status.HTTP_201_CREATED)
async def create(round_id: int, data: TournamentCreate, admin: AdminUser, session: SessionDep):
    service = TournamentService(session)
    t = await service.create(round_id, data.format_code, data.final_weight, admin, data.legs)
    return await service.detail(t.id)


@router.get("/rounds/{round_id}/tournament", response_model=TournamentOut)
async def by_round(round_id: int, user: CurrentUser, session: SessionDep):
    service = TournamentService(session)
    t = await service.by_round(round_id)
    if t is None:
        raise NotFoundError("Esta rodada ainda não tem campeonato")
    return await service.detail(t.id)


@router.get("/tournaments/{tournament_id}", response_model=TournamentOut)
async def detail(tournament_id: int, user: CurrentUser, session: SessionDep):
    return await TournamentService(session).detail(tournament_id)


@router.delete("/tournaments/{tournament_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(tournament_id: int, admin: AdminUser, session: SessionDep):
    await TournamentService(session).delete(tournament_id, admin)


@router.post("/tournaments/{tournament_id}/matches", response_model=TournamentOut)
async def add_casual_match(tournament_id: int, staff: StaffUser, session: SessionDep):
    """Pelada normal: cria a próxima partida."""
    service = TournamentService(session)
    await service.add_casual_match(tournament_id, staff)
    return await service.detail(tournament_id)


@router.post("/tournaments/{tournament_id}/finish", response_model=TournamentOut)
async def finish_casual(tournament_id: int, admin: AdminUser, session: SessionDep):
    """Pelada normal: encerra a noite."""
    service = TournamentService(session)
    await service.finish_casual(tournament_id, admin)
    return await service.detail(tournament_id)


@router.post("/matches/{match_id}/result", response_model=TournamentOut)
async def set_result(match_id: int, data: MatchResultIn, staff: StaffUser, session: SessionDep):
    """Lança/corrige o resultado final. Atualiza classificação e chaveamento automaticamente."""
    service = TournamentService(session)
    t = await service.set_result(match_id, data, staff)
    return await service.detail(t.id)


@router.post("/matches/{match_id}/reopen", response_model=TournamentOut)
async def reopen(match_id: int, staff: StaffUser, session: SessionDep):
    """Desfaz o resultado (escape para encerramento acidental). Mesário ou admin; bloqueado se um jogo
    seguinte que depende dele já terminou. Fica na auditoria."""
    service = TournamentService(session)
    t = await service.reopen(match_id, staff)
    return await service.detail(t.id)
