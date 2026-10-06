"""Estatísticas derivadas da súmula e dos times (views vw_player_matches / vw_player_events)."""
import random
from collections import defaultdict
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.views import vw_player_events as ev
from app.db.views import vw_player_matches as pm
from app.models.player import Player
from app.models.round import Round, RoundStatus, Team, TeamPlayer
from app.models.tournament import Tournament
from app.repositories.settings_repo import SettingsRepository
from app.schemas.stats import (
    CardOut,
    PlayerProfile,
    PlayerStats,
    RoundHistory,
    ScorerOut,
    TournamentSummary,
)

PLAYED_STATUSES = (RoundStatus.TIMES_TRAVADOS, RoundStatus.ENCERRADA)


def _win_rate(w: int, d: int, played: int) -> float:
    return round((3 * w + d) / (3 * played) * 100, 1) if played else 0.0


class StatsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------------------------------------------------------- rankings
    async def players(self, year: int | None = None, player_id: int | None = None) -> list[PlayerStats]:
        def period(col):
            conds = []
            if year:
                conds += [col >= date(year, 1, 1), col <= date(year, 12, 31)]
            return conds

        win = case((pm.c.goals_for > pm.c.goals_against, 1), else_=0)
        draw = case((pm.c.goals_for == pm.c.goals_against, 1), else_=0)
        loss = case((pm.c.goals_for < pm.c.goals_against, 1), else_=0)
        q = select(pm.c.player_id, func.count(), func.sum(win), func.sum(draw), func.sum(loss)) \
            .where(*period(pm.c.round_date)).group_by(pm.c.player_id)
        if player_id:
            q = q.where(pm.c.player_id == player_id)
        matches = {r[0]: r[1:] for r in await self.session.execute(q)}

        q = select(ev.c.player_id, func.sum(ev.c.goals), func.sum(ev.c.own_goals), func.sum(ev.c.assists),
                   func.sum(ev.c.yellows), func.sum(ev.c.reds)).where(*period(ev.c.round_date)) \
            .group_by(ev.c.player_id)
        if player_id:
            q = q.where(ev.c.player_id == player_id)
        events = {r[0]: r[1:] for r in await self.session.execute(q)}

        # Presença = estar escalado num time de rodada com times travados (ou encerrada)
        q = select(TeamPlayer.player_id, func.count(func.distinct(TeamPlayer.round_id))) \
            .join(Round, Round.id == TeamPlayer.round_id) \
            .where(Round.status.in_(PLAYED_STATUSES), *period(Round.date)).group_by(TeamPlayer.player_id)
        if player_id:
            q = q.where(TeamPlayer.player_id == player_id)
        presences = dict((await self.session.execute(q)).all())

        titles = await self._titles(period, player_id)

        ids = set(matches) | set(events) | set(presences) | set(titles)
        if player_id:
            ids.add(player_id)
        players = {p.id: p for p in await self.session.scalars(select(Player).where(Player.id.in_(ids)))} if ids else {}
        out = []
        for pid in ids:
            p = players.get(pid)
            if p is None:
                continue
            j, w, d, lo = (int(x or 0) for x in matches.get(pid, (0, 0, 0, 0)))
            g, og, a, y, r = (int(x or 0) for x in events.get(pid, (0, 0, 0, 0, 0)))
            champ, vice = titles.get(pid, (0, 0))
            out.append(PlayerStats(
                player_id=pid, name=p.display_name, photo_url=p.photo_url, type=p.type,
                primary_position=p.primary_position, presences=presences.get(pid, 0), matches=j, wins=w,
                draws=d, losses=lo, win_rate=_win_rate(w, d, j), goals=g, own_goals=og, assists=a,
                yellows=y, reds=r, titles=champ, runner_ups=vice,
            ))
        out.sort(key=lambda s: (-s.goals, -s.assists, s.name.casefold()))
        return out

    async def _titles(self, period, player_id: int | None) -> dict[int, tuple[int, int]]:
        result: dict[int, list[int]] = defaultdict(lambda: [0, 0])
        for col, idx in ((Tournament.champion_team_id, 0), (Tournament.runner_up_team_id, 1)):
            q = select(TeamPlayer.player_id, func.count()).join(Tournament, col == TeamPlayer.team_id) \
                .join(Round, Round.id == Tournament.round_id).where(*period(Round.date)) \
                .group_by(TeamPlayer.player_id)
            if player_id:
                q = q.where(TeamPlayer.player_id == player_id)
            for pid, n in await self.session.execute(q):
                result[pid][idx] = n
        return {k: (v[0], v[1]) for k, v in result.items()}

    # ---------------------------------------------------------- perfil
    async def profile(self, player_id: int) -> PlayerProfile:
        if await self.session.get(Player, player_id) is None:
            raise NotFoundError("Jogador não encontrado")
        (stats,) = await self.players(player_id=player_id)

        rows = (await self.session.execute(
            select(Round, Team, Tournament)
            .join(TeamPlayer, TeamPlayer.round_id == Round.id)
            .join(Team, Team.id == TeamPlayer.team_id)
            .outerjoin(Tournament, Tournament.round_id == Round.id)
            .where(TeamPlayer.player_id == player_id, Round.status.in_(PLAYED_STATUSES))
            .order_by(Round.date.desc())
        )).all()

        win = case((pm.c.goals_for > pm.c.goals_against, 1), else_=0)
        draw = case((pm.c.goals_for == pm.c.goals_against, 1), else_=0)
        loss = case((pm.c.goals_for < pm.c.goals_against, 1), else_=0)
        per_round = {r[0]: r[1:] for r in await self.session.execute(
            select(pm.c.round_id, func.count(), func.sum(win), func.sum(draw), func.sum(loss))
            .where(pm.c.player_id == player_id).group_by(pm.c.round_id))}
        ev_round = {r[0]: r[1:] for r in await self.session.execute(
            select(ev.c.round_id, func.sum(ev.c.goals), func.sum(ev.c.assists), func.sum(ev.c.yellows),
                   func.sum(ev.c.reds)).where(ev.c.player_id == player_id).group_by(ev.c.round_id))}

        history = []
        for rnd, team, t in rows:
            j, w, d, lo = (int(x or 0) for x in per_round.get(rnd.id, (0, 0, 0, 0)))
            g, a, y, r = (int(x or 0) for x in ev_round.get(rnd.id, (0, 0, 0, 0)))
            history.append(RoundHistory(
                round_id=rnd.id, date=rnd.date, tournament_id=t.id if t else None, team_name=team.name,
                team_color=team.color, matches=j, wins=w, draws=d, losses=lo, goals=g, assists=a, yellows=y,
                reds=r, champion=bool(t and t.champion_team_id == team.id),
                runner_up=bool(t and t.runner_up_team_id == team.id),
            ))
        return PlayerProfile(stats=stats, history=history)

    # ---------------------------------------------------------- resumo do campeonato
    async def tournament_summary(self, tournament_id: int) -> TournamentSummary:
        t = await self.session.get(Tournament, tournament_id)
        if t is None:
            raise NotFoundError("Campeonato não encontrado")
        tiebreak = (await SettingsRepository(self.session).get_current()).top_scorer_tiebreak.value

        rows = (await self.session.execute(
            select(ev.c.player_id, func.sum(ev.c.goals), func.sum(ev.c.assists), func.sum(ev.c.yellows),
                   func.sum(ev.c.reds)).where(ev.c.tournament_id == t.id).group_by(ev.c.player_id))).all()
        played = dict((await self.session.execute(
            select(pm.c.player_id, func.count()).where(pm.c.tournament_id == t.id).group_by(pm.c.player_id))).all())
        ids = {r[0] for r in rows}
        players = {p.id: p for p in await self.session.scalars(select(Player).where(Player.id.in_(ids)))} if ids else {}
        team_of = {pid: (team.name, team.color) for pid, team in (await self.session.execute(
            select(TeamPlayer.player_id, Team).join(Team, Team.id == TeamPlayer.team_id)
            .where(TeamPlayer.round_id == t.round_id))).all()}

        scorers, cards = [], []
        total_goals = total_y = total_r = 0
        for pid, g, a, y, r in rows:
            g, a, y, r = int(g or 0), int(a or 0), int(y or 0), int(r or 0)
            name = players[pid].display_name if pid in players else "?"
            team = team_of.get(pid, (None, None))
            total_goals, total_y, total_r = total_goals + g, total_y + y, total_r + r
            if g:
                scorers.append(ScorerOut(player_id=pid, name=name, team_name=team[0], team_color=team[1],
                                         goals=g, assists=a, matches=played.get(pid, 0)))
            if y or r:
                cards.append(CardOut(player_id=pid, name=name, yellows=y, reds=r))
        scorers.sort(key=lambda s: (-s.goals, -s.assists, s.name.casefold()))
        cards.sort(key=lambda c: (-c.reds, -c.yellows, c.name.casefold()))

        top: list[ScorerOut] = []
        if scorers:
            best = [s for s in scorers if s.goals == scorers[0].goals]
            if len(best) > 1 and tiebreak == "MAIS_ASSISTENCIAS":
                most = max(s.assists for s in best)
                best = [s for s in best if s.assists == most]
            elif len(best) > 1 and tiebreak == "MENOS_JOGOS":
                fewest = min(s.matches for s in best)
                best = [s for s in best if s.matches == fewest]
            elif len(best) > 1 and tiebreak == "SORTEIO":
                best = [random.Random(t.config["seed"]).choice(sorted(best, key=lambda s: s.player_id))]
            top = best
        return TournamentSummary(tournament_id=t.id, top_scorers=top, tiebreak=tiebreak, scorers=scorers,
                                 cards=cards, total_goals=total_goals, total_yellows=total_y, total_reds=total_r)
