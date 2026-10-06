"""Painel da gestão: junta números do elenco, financeiro, rodada atual, temporada e pendências.
Reaproveita os cálculos existentes (financeiro, estatísticas, rodadas) para os números baterem com as outras telas."""
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.views import vw_player_events as ev
from app.domain.delinquency import amount_due, reference_months
from app.models.enums import PlayerType, Position, UserStatus
from app.models.finance import CollectionItem
from app.models.finance import MonthlyFee as fin_fee
from app.models.player import Player
from app.models.round import Attendance, AttendanceStatus, Round, RoundStatus, Team, TeamPlayer
from app.models.tournament import Tournament, TournamentStatus
from app.models.user import User
from app.schemas.dashboard import (
    DashboardOut,
    FinanceNumbers,
    Highlight,
    Pending,
    RoundNumbers,
    SeasonNumbers,
    SquadNumbers,
)
from app.services.finance_service import FinanceService, today_local
from app.services.round_service import RoundService
from app.services.stats_service import StatsService

ZERO = Decimal("0.00")


def _win_rate(s) -> str:
    return f"{s.win_rate:g}".replace(".", ",") + f"% em {s.matches} jogos"
PLAYED = (RoundStatus.TIMES_TRAVADOS, RoundStatus.ENCERRADA)


class DashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def build(self) -> DashboardOut:
        today = today_local()
        return DashboardOut(
            squad=await self._squad(),
            finance=await self._finance(today),
            current_round=await self._current_round(),
            season=await self._season(today.year),
            pending=await self._pending(),
        )

    async def _count(self, *where) -> int:
        return await self.session.scalar(select(func.count()).select_from(Player).where(*where)) or 0

    async def _squad(self) -> SquadNumbers:
        return SquadNumbers(
            monthly_active=await self._count(Player.type == PlayerType.MENSALISTA, Player.active.is_(True)),
            daily_active=await self._count(Player.type == PlayerType.DIARISTA, Player.active.is_(True)),
            inactive=await self._count(Player.active.is_(False)),
        )

    async def _finance(self, today: date) -> FinanceNumbers:
        fin = FinanceService(self.session)
        overview = await fin.overview(today.year)
        month = today.replace(day=1)
        summary = next(s for s in overview.summary if s.month == month)
        fee = overview.config.monthly_fee
        overdue = await fin.delinquency()
        paid_month = await self.session.scalar(
            select(func.count()).select_from(Player)
            .where(Player.type == PlayerType.MENSALISTA, Player.active.is_(True),
                   Player.id.in_(select(fin_fee.player_id).where(fin_fee.month == month, fin_fee.amount >= fee)))
        ) or 0
        collections_open = await self.session.scalar(
            select(func.coalesce(func.sum(CollectionItem.amount), 0)).where(CollectionItem.paid.is_(False))
        )
        return FinanceNumbers(
            balance=overview.balance,
            month=month,
            month_income=summary.fees + summary.income,
            month_expenses=summary.expenses,
            monthly_paid=paid_month,
            monthly_total=await self._count(Player.type == PlayerType.MENSALISTA, Player.active.is_(True)),
            delinquent_count=len(overdue),
            delinquent_amount=sum((amount_due(a, fee) for a in overdue.values()), ZERO),
            reference_months=list(reference_months(today)),
            collections_open=Decimal(collections_open).quantize(Decimal("0.01")),
        )

    async def _current_round(self) -> RoundNumbers | None:
        rnd = await RoundService(self.session).current()
        if rnd is None:
            return None
        confirmed = (await self.session.execute(
            select(Player.primary_position)
            .join(Attendance, Attendance.player_id == Player.id)
            .where(Attendance.round_id == rnd.id, Attendance.status == AttendanceStatus.CONFIRMADO)
        )).scalars().all()
        teams = await self.session.scalar(select(func.count()).select_from(Team).where(Team.round_id == rnd.id)) or 0
        tournament_id = await self.session.scalar(select(Tournament.id).where(Tournament.round_id == rnd.id))
        return RoundNumbers(
            id=rnd.id, date=rnd.date, status=rnd.status.value, confirmed=len(confirmed),
            goalkeepers=sum(1 for p in confirmed if p == Position.GOLEIRO_FIXO), teams=teams, tournament_id=tournament_id,
        )

    async def _season(self, year: int) -> SeasonNumbers:
        start, end = date(year, 1, 1), date(year, 12, 31)
        rounds = list(await self.session.scalars(
            select(Round.id).where(Round.status.in_(PLAYED), Round.date >= start, Round.date <= end)
        ))
        players_per_round = []
        for rid in rounds:
            players_per_round.append(await self.session.scalar(
                select(func.count()).select_from(TeamPlayer).where(TeamPlayer.round_id == rid)) or 0)
        goals = await self.session.scalar(
            select(func.coalesce(func.sum(ev.c.goals), 0)).where(ev.c.round_date >= start, ev.c.round_date <= end)
        ) or 0
        last = (await self.session.execute(
            select(Tournament, Round.date, Team.name)
            .join(Round, Round.id == Tournament.round_id)
            .join(Team, Team.id == Tournament.champion_team_id)
            .where(Tournament.status == TournamentStatus.ENCERRADO)
            .order_by(Round.date.desc()).limit(1)
        )).first()

        stats = await StatsService(self.session).players(year)

        def best(key, fmt, cond=lambda s: True) -> Highlight | None:
            pool = [s for s in stats if cond(s) and key(s) > 0]
            if not pool:
                return None
            top = max(pool, key=lambda s: (key(s), -len(s.name)))
            return Highlight(player_id=top.player_id, name=top.name, value=fmt(top))

        return SeasonNumbers(
            year=year,
            rounds_played=len(rounds),
            avg_players=round(sum(players_per_round) / len(players_per_round), 1) if players_per_round else 0.0,
            goals=int(goals),
            last_champion=f"Time {last[2]}" if last else None,
            last_champion_date=last[1] if last else None,
            last_tournament_id=last[0].id if last else None,
            top_scorer=best(lambda s: s.goals, lambda s: f"{s.goals} gols"),
            most_present=best(lambda s: s.presences, lambda s: f"{s.presences} rodadas"),
            best_win_rate=best(lambda s: s.win_rate, _win_rate, lambda s: s.matches >= 3),
        )

    async def _pending(self) -> Pending:
        monthly = (Player.type == PlayerType.MENSALISTA, Player.active.is_(True))
        return Pending(
            pending_users=await self.session.scalar(
                select(func.count()).select_from(User).where(User.status == UserStatus.PENDENTE)) or 0,
            players_without_position=await self._count(Player.active.is_(True), Player.primary_position.is_(None)),
            monthly_without_whatsapp=await self._count(*monthly, Player.phone.is_(None)),
            monthly_without_consent=await self._count(*monthly, Player.phone.is_not(None), Player.whatsapp_opt_in.is_(False)),
            locked_accounts=await self.session.scalar(
                select(func.count()).select_from(User).where(User.locked_until > datetime.now(UTC))) or 0,
        )
