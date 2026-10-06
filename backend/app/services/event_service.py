"""Súmula: eventos de partida (gols, gols contra, cartões) e placar derivado deles."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.domain.formats import Stage
from app.domain.standings import KnockoutResult, TieRuleError, campaign_ranking, knockout_winner
from app.models.match_event import EventType, MatchEvent
from app.models.player import Player
from app.models.round import TeamPlayer
from app.models.tournament import Match, MatchStatus, Tournament
from app.models.user import User
from app.schemas.event import EventIn, EventOut, MatchSheet, RosterPlayer
from app.services import audit_service


def score_from_events(match: Match, events: list[MatchEvent]) -> tuple[int, int]:
    home = away = 0
    for e in events:
        if e.deleted_at is not None:
            continue
        if e.type == EventType.GOL:
            home += e.team_id == match.home_team_id
            away += e.team_id == match.away_team_id
        elif e.type == EventType.GOL_CONTRA:
            home += e.team_id == match.away_team_id
            away += e.team_id == match.home_team_id
    return home, away


class EventService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------------------------------------------------------- leitura
    async def sheet(self, match_id: int) -> MatchSheet:
        m = await self._match(match_id)
        events = await self._events(m.id)
        names = await self._names({x for e in events for x in (e.player_id, e.assist_player_id) if x})
        rosters: dict[int, list[RosterPlayer]] = {}
        for team_id in filter(None, (m.home_team_id, m.away_team_id)):
            rows = (await self.session.execute(
                select(TeamPlayer, Player).join(Player, Player.id == TeamPlayer.player_id)
                .where(TeamPlayer.team_id == team_id)
            )).all()
            rosters[team_id] = sorted(
                (RosterPlayer(player_id=p.id, name=p.display_name, role=tp.role.value) for tp, p in rows),
                key=lambda r: r.name.casefold(),
            )
        return MatchSheet(
            match_id=m.id, status=m.status.value, home_team_id=m.home_team_id, away_team_id=m.away_team_id,
            home_score=m.home_score, away_score=m.away_score,
            events=[self._out(e, names) for e in events if e.deleted_at is None],
            rosters=rosters,
        )

    # ---------------------------------------------------------- escrita
    async def add(self, match_id: int, data: EventIn, actor: User) -> MatchSheet:
        m = await self._match(match_id)
        # Idempotência: reenvio do mesmo client_event_id devolve o estado atual sem duplicar
        existing = await self.session.scalar(select(MatchEvent).where(
            MatchEvent.match_id == m.id, MatchEvent.client_event_id == data.client_event_id))
        if existing is not None:
            return await self.sheet(m.id)
        if m.home_team_id is None or m.away_team_id is None:
            raise ValidationError("Os times desta partida ainda não estão definidos")
        if data.team_id not in (m.home_team_id, m.away_team_id):
            raise ValidationError("Time não participa desta partida")
        for pid in filter(None, (data.player_id, data.assist_player_id)):
            in_team = await self.session.scalar(select(TeamPlayer.id).where(
                TeamPlayer.team_id == data.team_id, TeamPlayer.player_id == pid))
            if not in_team:
                raise ValidationError("Jogador não pertence a este time")

        event = MatchEvent(match_id=m.id, created_by=actor.id, auto_generated=False, **data.model_dump())
        self.session.add(event)
        try:
            await self.session.flush()
        except IntegrityError:  # corrida com o mesmo client_event_id
            await self.session.rollback()
            return await self.sheet(m.id)
        await audit_service.record(self.session, user_id=actor.id, action="CREATE", entity="match_event",
                                   entity_id=event.id, after=audit_service.snapshot(event))
        await self._apply_score(m)
        await self.session.commit()
        return await self.sheet(m.id)

    async def delete(self, event_id: int, actor: User) -> MatchSheet:
        event = await self.session.get(MatchEvent, event_id)
        if event is None:
            raise NotFoundError("Evento não encontrado")
        if event.deleted_at is None:
            event.deleted_at = datetime.now(UTC)
            await audit_service.record(self.session, user_id=actor.id, action="DELETE", entity="match_event",
                                       entity_id=event.id, before=audit_service.snapshot(event))
            m = await self._match(event.match_id)
            await self._apply_score(m)
            await self.session.commit()
        return await self.sheet(event.match_id)

    async def reconcile_anonymous_goals(self, m: Match, home: int, away: int, actor: User) -> None:
        """Placar rápido: ajusta gols sem autor para bater com o placar informado."""
        events = await self._events(m.id)
        live = [e for e in events if e.deleted_at is None]
        for team_id, wanted, label in ((m.home_team_id, home, "mandante"), (m.away_team_id, away, "visitante")):
            identified = sum(
                1 for e in live
                if (e.type == EventType.GOL and e.team_id == team_id and e.player_id is not None)
                or (e.type == EventType.GOL_CONTRA and e.team_id != team_id)
            )
            anonymous = [e for e in live if e.type == EventType.GOL and e.team_id == team_id and e.player_id is None]
            if wanted < identified:
                raise ValidationError(
                    f"O time {label} já tem {identified} gol(s) com autor na súmula; remova-os antes de baixar o placar"
                )
            missing = wanted - identified - len(anonymous)
            for _ in range(missing):
                self.session.add(MatchEvent(match_id=m.id, client_event_id=uuid.uuid4(), type=EventType.GOL,
                                            team_id=team_id, created_by=actor.id, auto_generated=False))
            for e in anonymous[: max(-missing, 0)]:
                e.deleted_at = datetime.now(UTC)
        await self.session.flush()
        m.home_score, m.away_score = score_from_events(m, await self._events(m.id))

    async def _apply_score(self, m: Match) -> None:
        """Recalcula o placar; se a partida já terminou, refaz vencedor, classificação e chaveamento."""
        from app.services.tournament_service import TournamentService

        await self.session.flush()
        m.home_score, m.away_score = score_from_events(m, await self._events(m.id))
        m.version += 1
        if m.status != MatchStatus.ENCERRADA:
            return
        t = await self.session.get(Tournament, m.tournament_id)
        service = TournamentService(self.session)
        await service.ensure_no_finished_dependents(t, m)
        if m.stage in (Stage.SEMIFINAL, Stage.FINAL):
            tables, _ = await service.group_tables(t)
            try:
                m.winner_team_id = knockout_winner(
                    KnockoutResult(m.home_team_id, m.away_team_id, m.home_score, m.away_score,
                                   m.home_penalties, m.away_penalties),
                    t.config["knockout_tie_rule"], campaign_ranking(tables))
            except TieRuleError as exc:
                raise ValidationError(f"{exc} (a partida já estava encerrada)") from exc
        else:
            m.winner_team_id = (m.home_team_id if m.home_score > m.away_score
                                else m.away_team_id if m.away_score > m.home_score else None)
        await service.recalc(t)

    # ---------------------------------------------------------- helpers
    async def _events(self, match_id: int) -> list[MatchEvent]:
        return list(await self.session.scalars(
            select(MatchEvent).where(MatchEvent.match_id == match_id)
            .order_by(MatchEvent.minute.asc().nulls_last(), MatchEvent.second.asc().nulls_last(), MatchEvent.id)
        ))

    async def _names(self, ids: set[int]) -> dict[int, str]:
        if not ids:
            return {}
        return {p.id: p.display_name for p in await self.session.scalars(select(Player).where(Player.id.in_(ids)))}

    @staticmethod
    def _out(e: MatchEvent, names: dict[int, str]) -> EventOut:
        return EventOut(
            id=e.id, client_event_id=e.client_event_id, type=e.type, team_id=e.team_id,
            player_id=e.player_id, player_name=names.get(e.player_id) if e.player_id else None,
            assist_player_id=e.assist_player_id,
            assist_name=names.get(e.assist_player_id) if e.assist_player_id else None,
            minute=e.minute, second=e.second, created_at=e.created_at,
        )

    async def _match(self, match_id: int) -> Match:
        m = await self.session.get(Match, match_id)
        if m is None:
            raise NotFoundError("Partida não encontrada")
        return m
