from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, SessionDep, StaffUser
from app.schemas.event import EventIn, MatchSheet
from app.schemas.stats import PlayerProfile, PlayerStats, TournamentSummary
from app.services.event_service import EventService
from app.services.stats_service import StatsService

router = APIRouter(tags=["Súmula e estatísticas"])


@router.get("/matches/{match_id}/events", response_model=MatchSheet)
async def match_sheet(match_id: int, user: CurrentUser, session: SessionDep):
    """Súmula da partida: eventos e elencos."""
    return await EventService(session).sheet(match_id)


@router.post("/matches/{match_id}/events", response_model=MatchSheet)
async def add_event(match_id: int, data: EventIn, staff: StaffUser, session: SessionDep):
    """Registra gol/gol contra/cartão. Idempotente por `client_event_id` (reenvio não duplica)."""
    return await EventService(session).add(match_id, data, staff)


@router.delete("/events/{event_id}", response_model=MatchSheet)
async def delete_event(event_id: int, staff: StaffUser, session: SessionDep):
    """Exclui (logicamente) um evento; o placar e a classificação são recalculados."""
    return await EventService(session).delete(event_id, staff)


@router.get("/stats/players", response_model=list[PlayerStats])
async def players_stats(user: CurrentUser, session: SessionDep, year: int | None = Query(None, ge=2000, le=2100)):
    """Rankings históricos (ou de um ano): artilharia, assistências, cartões, presenças, aproveitamento, títulos."""
    return await StatsService(session).players(year)


@router.get("/stats/players/{player_id}", response_model=PlayerProfile)
async def player_profile(player_id: int, user: CurrentUser, session: SessionDep):
    return await StatsService(session).profile(player_id)


@router.get("/tournaments/{tournament_id}/summary", response_model=TournamentSummary)
async def tournament_summary(tournament_id: int, user: CurrentUser, session: SessionDep):
    """Resumo: artilheiro (com o critério de desempate configurado) e cartões."""
    return await StatsService(session).tournament_summary(tournament_id)
