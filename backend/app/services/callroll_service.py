"""Chamada no local e empréstimo de jogadores para completar times desfalcados.

A escala das partidas ainda não encerradas é sempre recalculada a partir da chamada (um atrasado que chega
cancela os empréstimos seguintes). Ao encerrar uma partida, os empréstimos dela são gravados em
`match_loans`, para o histórico, a súmula e o rodízio das próximas.
"""
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.domain.draw import DEFAULT_LEVEL, DEFAULT_SPEED
from app.domain.loans import Loan, LoanMatch, LoanPlan, LoanPlayer, plan_loans
from app.models.player import Player
from app.models.round import Attendance, AttendanceStatus, Round, RoundStatus, Team, TeamPlayer
from app.models.tournament import Match, MatchLoan, MatchStatus, Tournament
from app.models.user import User
from app.repositories.settings_repo import SettingsRepository
from app.services import audit_service

CHECKIN_VALUES = ("PRESENTE", "FALTOU")


@dataclass
class RoundLoans:
    plan: LoanPlan
    matches: dict[int, Match]
    teams: dict[int, Team]
    names: dict[int, str]


class CallRollService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------------------------------------------------------- chamada
    async def set_checkin(self, round_id: int, player_id: int, status: str | None, actor: User) -> None:
        rnd = await self._round(round_id)
        att = await self.session.scalar(
            select(Attendance).where(Attendance.round_id == rnd.id, Attendance.player_id == player_id,
                                     Attendance.status == AttendanceStatus.CONFIRMADO)
        )
        if att is None:
            raise ValidationError("Só quem confirmou presença entra na chamada")
        before = att.checkin
        att.checkin = status
        att.checkin_at = datetime.now(UTC) if status else None
        await audit_service.record(self.session, user_id=actor.id, action="CHECKIN", entity="round",
                                   entity_id=rnd.id, before={"player_id": player_id, "checkin": before},
                                   after={"player_id": player_id, "checkin": status})
        await self.session.commit()

    async def all_present(self, round_id: int, actor: User) -> None:
        """Marca como presente todo confirmado ainda não chamado (não mexe em quem já foi marcado)."""
        rnd = await self._round(round_id)
        rows = list(await self.session.scalars(
            select(Attendance).where(Attendance.round_id == rnd.id, Attendance.status == AttendanceStatus.CONFIRMADO,
                                     Attendance.checkin.is_(None))
        ))
        now = datetime.now(UTC)
        for att in rows:
            att.checkin, att.checkin_at = "PRESENTE", now
        await audit_service.record(self.session, user_id=actor.id, action="CHECKIN_ALL", entity="round",
                                   entity_id=rnd.id, after={"players": [a.player_id for a in rows]})
        await self.session.commit()

    # ---------------------------------------------------------- empréstimos
    async def plan(self, round_id: int) -> RoundLoans | None:
        """Escala de empréstimos da rodada (None sem campeonato ou sem times)."""
        tournament = await self.session.scalar(select(Tournament).where(Tournament.round_id == round_id))
        if tournament is None:
            return None
        teams = {t.id: t for t in await self.session.scalars(select(Team).where(Team.round_id == round_id))}
        if not teams:
            return None
        rows = (await self.session.execute(
            select(TeamPlayer, Player).join(Player, Player.id == TeamPlayer.player_id)
            .where(TeamPlayer.round_id == round_id)
        )).all()
        players = [
            LoanPlayer(
                id=p.id, name=p.display_name, team_id=tp.team_id, role=tp.role.value, position=tp.assigned_position,
                primary=p.primary_position.value if p.primary_position else None,
                secondary=p.secondary_position.value if p.secondary_position else None,
                strength=(p.skill_level or DEFAULT_LEVEL) + (p.speed or DEFAULT_SPEED),
            )
            for tp, p in rows
        ]
        # Falta = marcado "faltou" na chamada ou cancelou a presença depois do sorteio
        absent = set(await self.session.scalars(
            select(Attendance.player_id).where(
                Attendance.round_id == round_id,
                (Attendance.checkin == "FALTOU") | (Attendance.status == AttendanceStatus.CANCELADO),
            )
        ))
        matches = {m.id: m for m in await self.session.scalars(
            select(Match).where(Match.tournament_id == tournament.id).order_by(Match.seq))}
        fixed = [
            Loan(x.match_id, x.team_id, x.player_id, x.from_team_id, x.replaces_id, float(x.strength_delta))
            for x in await self.session.scalars(select(MatchLoan).where(MatchLoan.match_id.in_(matches)))
        ] if matches else []
        settings = await SettingsRepository(self.session).get_current()
        result = plan_loans(
            players, absent,
            [LoanMatch(m.id, m.seq, m.home_team_id, m.away_team_id, m.status == MatchStatus.ENCERRADA)
             for m in matches.values()],
            per_team=settings.line_players_per_team, fixed=fixed,
        )
        names = {p.id: p.name for p in players}
        missing_ids = {pid for ids in result.unfilled.values() for pid in ids} | {x.replaces_id for x in result.loans}
        for pid in missing_ids - names.keys():  # quem faltou e já não está no time
            player = await self.session.get(Player, pid)
            names[pid] = player.display_name if player else "?"
        return RoundLoans(result, matches, teams, names)

    async def match_loans(self, match: Match) -> list[Loan]:
        """Empréstimos de uma partida: gravados se encerrada; senão, os da escala atual."""
        if match.status == MatchStatus.ENCERRADA:
            return [Loan(x.match_id, x.team_id, x.player_id, x.from_team_id, x.replaces_id, float(x.strength_delta))
                    for x in await self.session.scalars(select(MatchLoan).where(MatchLoan.match_id == match.id))]
        round_id = await self.session.scalar(select(Tournament.round_id).where(Tournament.id == match.tournament_id))
        data = await self.plan(round_id)
        return [x for x in data.plan.loans if x.match_id == match.id] if data else []

    async def absent_ids(self, round_id: int) -> set[int]:
        return set(await self.session.scalars(
            select(Attendance.player_id).where(Attendance.round_id == round_id, Attendance.checkin == "FALTOU")))

    async def freeze(self, match: Match) -> None:
        """Grava os empréstimos da partida que está sendo encerrada (chamar antes de mudar o status)."""
        if match.status == MatchStatus.ENCERRADA:
            return  # correção de placar: mantém o que foi gravado
        loans = await self.match_loans(match)
        await self.session.execute(delete(MatchLoan).where(MatchLoan.match_id == match.id))
        for x in loans:
            self.session.add(MatchLoan(match_id=match.id, team_id=x.team_id, player_id=x.player_id,
                                       from_team_id=x.from_team_id, replaces_id=x.replaces_id,
                                       strength_delta=x.strength_delta))

    async def unfreeze(self, match: Match) -> None:
        await self.session.execute(delete(MatchLoan).where(MatchLoan.match_id == match.id))

    async def _round(self, round_id: int) -> Round:
        rnd = await self.session.get(Round, round_id)
        if rnd is None:
            raise NotFoundError("Rodada não encontrada")
        if rnd.status == RoundStatus.ENCERRADA:
            raise ValidationError("Rodada encerrada")
        return rnd
