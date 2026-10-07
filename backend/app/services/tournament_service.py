import random
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.domain.formats import FORMAT_INFO, FormatCode, Stage, TimeConfig, build_matches, suggest_formats
from app.domain.kickoff import KickoffMatch, assign_kickoffs
from app.domain.standings import (
    KnockoutResult,
    PointsConfig,
    Result,
    Row,
    TieRuleError,
    campaign_ranking,
    compute_standings,
    knockout_winner,
    resolve_source,
)
from app.models.round import Round, RoundStatus, Team
from app.models.tournament import Match, MatchStatus, Tournament, TournamentGroup, TournamentGroupTeam, TournamentStatus
from app.models.user import User
from app.repositories.settings_repo import SettingsRepository
from app.schemas.tournament import (
    FormatOptionOut,
    FormatsOut,
    GroupOut,
    MatchOut,
    MatchResultIn,
    StandingRow,
    TeamRef,
    TournamentOut,
)
from app.services import audit_service

STAGE_LABEL = {"SF1": "Semifinal 1", "SF2": "Semifinal 2", "R": "2º × 3º", "F": "Final"}


def source_label(source: str | None) -> str:
    if not source:
        return "A definir"
    kind, ref = source.split(":", 1)
    if kind == "V":
        return f"Vencedor {STAGE_LABEL.get(ref, ref)}"
    if kind == "P":
        return f"Perdedor {STAGE_LABEL.get(ref, ref)}"
    return f"{ref}º do grupo {kind}"


class TournamentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------------------------------------------------------- formatos
    async def _teams(self, round_id: int) -> list[Team]:
        return list(await self.session.scalars(
            select(Team).where(Team.round_id == round_id).order_by(Team.display_order)
        ))

    async def _time_config(self, final_weight: Decimal | None = None) -> TimeConfig:
        s = await SettingsRepository(self.session).get_current()
        return TimeConfig(
            total_minutes=s.total_minutes,
            changeover_minutes=s.changeover_minutes,
            final_weight=final_weight if final_weight is not None else s.final_weight,
            group_match_minutes=s.group_match_minutes,
            casual_match_minutes=s.casual_match_minutes,
        )

    async def formats(self, round_id: int, final_weight: Decimal | None) -> FormatsOut:
        await self._round(round_id)
        teams = await self._teams(round_id)
        if len(teams) < 2:
            raise ValidationError("Faça o sorteio dos times antes de escolher o formato")
        cfg = await self._time_config(final_weight)
        options = suggest_formats(len(teams), cfg)
        return FormatsOut(
            num_teams=len(teams),
            total_minutes=cfg.total_minutes,
            changeover_minutes=cfg.changeover_minutes,
            group_match_minutes=cfg.group_match_minutes,
            final_weight=Decimal(cfg.final_weight),
            options=[FormatOptionOut(code=o.code.value, legs=o.legs, name=o.name, description=o.description,
                                     total_matches=o.total_matches, match_seconds=o.match_seconds,
                                     final_seconds=o.final_seconds, feasible=o.feasible, note=o.note,
                                     knockout_seconds=o.knockout_seconds, recommended=o.recommended,
                                     groups=o.groups) for o in options],
        )

    # ---------------------------------------------------------- criação
    async def create(self, round_id: int, format_code: str, final_weight: Decimal | None, actor: User,
                     legs: int = 1) -> Tournament:
        rnd = await self._round(round_id)
        if rnd.status != RoundStatus.TIMES_TRAVADOS:
            raise ValidationError("Trave os times antes de criar o campeonato")
        if await self.session.scalar(select(Tournament.id).where(Tournament.round_id == rnd.id)):
            raise ConflictError("Esta rodada já tem um campeonato")
        teams = await self._teams(rnd.id)
        cfg = await self._time_config(final_weight)
        option = next((o for o in suggest_formats(len(teams), cfg)
                       if o.code.value == format_code and (o.legs == legs or o.code == FormatCode.PELADA_NORMAL)), None)
        if option is None:
            raise ValidationError(f"Formato inválido para {len(teams)} times")
        if not option.feasible:
            raise ValidationError(f"Formato inviável: {option.note}")

        settings = await SettingsRepository(self.session).get_current()
        seed = random.SystemRandom().randrange(1, 2**31)
        # Ordem dos times sorteada: define grupos e confrontos da 1ª fase
        order = [t.id for t in teams]
        random.Random(seed).shuffle(order)

        t = Tournament(
            round_id=rnd.id,
            format_code=option.code.value,
            status=TournamentStatus.EM_ANDAMENTO,
            match_seconds=option.match_seconds,
            final_seconds=option.final_seconds,
            config={
                "seed": seed,
                "legs": option.legs,
                "knockout_seconds": option.knockout_seconds,
                "team_order": order,
                "points": {"win": settings.points_win, "draw": settings.points_draw, "loss": settings.points_loss},
                "tiebreakers": list(settings.tiebreakers),
                "knockout_tie_rule": settings.knockout_tie_rule.value,
                "final_weight": str(cfg.final_weight),
                "total_minutes": cfg.total_minutes,
                "changeover_minutes": cfg.changeover_minutes,
                "casual_goal_limit": settings.casual_goal_limit,
            },
            created_by=actor.id,
        )
        self.session.add(t)
        await self.session.flush()

        groups_db: dict[str, TournamentGroup] = {}
        for name, idxs in option.groups.items():
            g = TournamentGroup(tournament_id=t.id, name=name)
            self.session.add(g)
            await self.session.flush()
            groups_db[name] = g
            for i in idxs:
                self.session.add(TournamentGroupTeam(group_id=g.id, team_id=order[i]))

        _, plans = build_matches(option.code, len(teams), option.legs)
        for p in plans:
            match = self._new_match(t, p.seq, p.stage, p.code,
                                    groups_db[p.group].id if p.group else None,
                                    order[p.home] if p.home is not None else None,
                                    order[p.away] if p.away is not None else None,
                                    p.home_source, p.away_source)
            match.leg = p.leg
            self.session.add(match)
        await audit_service.record(self.session, user_id=actor.id, action="CREATE", entity="tournament",
                                   entity_id=t.id, after={"round_id": rnd.id, "format": option.code.value,
                                                          "legs": option.legs,
                "knockout_seconds": option.knockout_seconds,
                                                          "match_seconds": option.match_seconds,
                                                          "knockout_seconds": option.knockout_seconds,
                                                          "final_seconds": option.final_seconds})
        await self.session.commit()
        return t

    def _new_match(self, t: Tournament, seq: int, stage: Stage, code: str, group_id, home, away,
                   home_source=None, away_source=None) -> Match:
        casual = t.format_code == FormatCode.PELADA_NORMAL
        return Match(
            tournament_id=t.id, group_id=group_id, stage=stage.value, code=code, seq=seq,
            home_team_id=home, away_team_id=away, home_source=home_source, away_source=away_source,
            planned_seconds=(t.final_seconds if stage == Stage.FINAL and t.final_seconds
                             else t.config.get("knockout_seconds") or t.match_seconds if stage == Stage.SEMIFINAL
                             else t.match_seconds),
            goal_limit=t.config.get("casual_goal_limit") if casual else None,
            leg=1, status=MatchStatus.AGENDADA, elapsed_before_pause=0, home_score=0, away_score=0, version=1,
        )

    async def add_casual_match(self, tournament_id: int, actor: User) -> None:
        t = await self._tournament(tournament_id)
        if t.format_code != FormatCode.PELADA_NORMAL:
            raise ValidationError("Só a pelada normal permite adicionar partidas")
        if t.status == TournamentStatus.ENCERRADO:
            raise ValidationError("Pelada encerrada")
        matches = await self._matches(t.id)
        if any(m.status != MatchStatus.ENCERRADA for m in matches):
            raise ValidationError("Encerre a partida atual antes de criar a próxima")
        order = t.config["team_order"]
        seq = len(matches) + 1
        self.session.add(self._new_match(t, seq, Stage.AMISTOSO, f"J{seq}", None, order[0], order[1]))
        await self.session.commit()

    async def finish_casual(self, tournament_id: int, actor: User) -> None:
        t = await self._tournament(tournament_id)
        if t.format_code != FormatCode.PELADA_NORMAL:
            raise ValidationError("Use os resultados para encerrar o campeonato")
        for m in await self._matches(t.id):
            if m.status != MatchStatus.ENCERRADA:
                await self.session.delete(m)  # partidas não jogadas são descartadas
        t.status = TournamentStatus.ENCERRADO
        t.finished_at = datetime.now(UTC)
        (await self._round(t.round_id)).status = RoundStatus.ENCERRADA
        await audit_service.record(self.session, user_id=actor.id, action="FINISH", entity="tournament",
                                   entity_id=t.id)
        await self.session.commit()

    async def delete(self, tournament_id: int, actor: User) -> None:
        t = await self._tournament(tournament_id)
        rnd = await self._round(t.round_id)
        await audit_service.record(self.session, user_id=actor.id, action="DELETE", entity="tournament",
                                   entity_id=t.id, before={"format": t.format_code, "round_id": t.round_id})
        await self.session.delete(t)
        rnd.status = RoundStatus.TIMES_TRAVADOS
        await self.session.commit()

    # ---------------------------------------------------------- resultados
    async def set_result(self, match_id: int, data: MatchResultIn, actor: User) -> Tournament:
        m = await self._match(match_id)
        t = await self._tournament(m.tournament_id)
        if m.home_team_id is None or m.away_team_id is None:
            raise ValidationError("Os times desta partida ainda não estão definidos")
        await self.ensure_no_finished_dependents(t, m)
        is_ko = m.stage in (Stage.SEMIFINAL, Stage.FINAL)
        before = self._score_snapshot(m)

        from app.services.event_service import EventService

        await EventService(self.session).reconcile_anonymous_goals(m, data.home_score, data.away_score, actor)
        m.home_penalties, m.away_penalties = (data.home_penalties, data.away_penalties) if is_ko else (None, None)
        if is_ko:
            tables, _ = await self.group_tables(t)
            try:
                m.winner_team_id = knockout_winner(
                    KnockoutResult(m.home_team_id, m.away_team_id, m.home_score, m.away_score,
                                   m.home_penalties, m.away_penalties),
                    t.config["knockout_tie_rule"], campaign_ranking(tables),
                )
            except TieRuleError as exc:
                raise ValidationError(str(exc)) from exc
            if m.home_score != m.away_score:
                m.home_penalties = m.away_penalties = None
        else:
            m.winner_team_id = (m.home_team_id if m.home_score > m.away_score
                                else m.away_team_id if m.away_score > m.home_score else None)
        m.status = MatchStatus.ENCERRADA
        if data.started_at is not None:
            m.started_at = data.started_at
        if data.played_seconds is not None:
            m.elapsed_before_pause = data.played_seconds  # tempo jogado, sem pausas
        m.ended_at = data.ended_at or m.ended_at or datetime.now(UTC)
        m.version += 1
        await audit_service.record(self.session, user_id=actor.id, action="RESULT", entity="match", entity_id=m.id,
                                   before=before, after=self._score_snapshot(m))
        await self.recalc(t)
        await self.session.commit()
        return t

    async def reopen(self, match_id: int, actor: User) -> Tournament:
        m = await self._match(match_id)
        t = await self._tournament(m.tournament_id)
        await self.ensure_no_finished_dependents(t, m)
        before = self._score_snapshot(m)
        m.status = MatchStatus.AGENDADA  # a súmula (e o placar que vem dela) é preservada
        m.home_penalties = m.away_penalties = None
        m.winner_team_id = None
        m.started_at = m.ended_at = None
        m.elapsed_before_pause = 0
        m.version += 1
        await audit_service.record(self.session, user_id=actor.id, action="REOPEN", entity="match", entity_id=m.id,
                                   before=before)
        await self.recalc(t)
        await self.session.commit()
        return t

    @staticmethod
    def _score_snapshot(m: Match) -> dict:
        return {"status": m.status.value, "home_score": m.home_score, "away_score": m.away_score,
                "home_penalties": m.home_penalties, "away_penalties": m.away_penalties}

    async def ensure_no_finished_dependents(self, t: Tournament, m: Match) -> None:
        """Não deixa alterar um jogo se um jogo seguinte que depende dele já terminou."""
        if m.status != MatchStatus.ENCERRADA:
            return
        group_name = None
        if m.group_id:
            group_name = await self.session.scalar(select(TournamentGroup.name).where(TournamentGroup.id == m.group_id))
        for other in await self._matches(t.id):
            if other.status != MatchStatus.ENCERRADA or other.id == m.id:
                continue
            for src in (other.home_source, other.away_source):
                if not src:
                    continue
                kind, ref = src.split(":", 1)
                if (kind in ("V", "P") and ref == m.code) or (group_name and kind == group_name):
                    raise ValidationError(
                        f"Reabra antes a partida {other.code} ({source_label(src)}), que depende deste resultado"
                    )

    # ---------------------------------------------------------- recálculo
    async def group_tables(self, t: Tournament) -> tuple[dict[str, list[Row]], dict[str, bool]]:
        groups = list(await self.session.scalars(select(TournamentGroup).where(TournamentGroup.tournament_id == t.id)))
        matches = await self._matches(t.id)
        points = PointsConfig(**t.config["points"])
        tables, complete = {}, {}
        for g in groups:
            team_ids = list(await self.session.scalars(
                select(TournamentGroupTeam.team_id).where(TournamentGroupTeam.group_id == g.id)
            ))
            gm = [x for x in matches if x.group_id == g.id]
            results = [Result(x.home_team_id, x.away_team_id, x.home_score, x.away_score)
                       for x in gm if x.status == MatchStatus.ENCERRADA]
            tables[g.name] = compute_standings(team_ids, results, points, t.config["tiebreakers"], t.config["seed"])
            complete[g.name] = bool(gm) and all(x.status == MatchStatus.ENCERRADA for x in gm)
        return tables, complete

    async def recalc(self, t: Tournament) -> None:
        """Atualiza chaveamento (preenche próximos confrontos) e define campeão/vice."""
        await self.session.flush()
        tables, complete = await self.group_tables(t)
        matches = await self._matches(t.id)
        winners = {m.code: m.winner_team_id for m in matches
                   if m.status == MatchStatus.ENCERRADA and m.winner_team_id and m.stage != Stage.GRUPO}
        losers = {m.code: (m.away_team_id if m.winner_team_id == m.home_team_id else m.home_team_id)
                  for m in matches if m.code in winners}
        for m in matches:
            if m.status == MatchStatus.ENCERRADA or m.stage == Stage.GRUPO:
                continue
            if m.home_source:
                m.home_team_id = resolve_source(m.home_source, tables, complete, winners, losers)
            if m.away_source:
                m.away_team_id = resolve_source(m.away_source, tables, complete, winners, losers)

        champion = runner_up = None
        final = next((m for m in matches if m.stage == Stage.FINAL), None)
        if final and final.status == MatchStatus.ENCERRADA:
            champion = final.winner_team_id
            runner_up = final.away_team_id if champion == final.home_team_id else final.home_team_id
        elif t.format_code == FormatCode.PONTOS_CORRIDOS and all(complete.values()):
            table = tables["A"]
            champion, runner_up = table[0].team, table[1].team

        rnd = await self._round(t.round_id)
        if t.format_code != FormatCode.PELADA_NORMAL:
            t.champion_team_id, t.runner_up_team_id = champion, runner_up
            if champion:
                t.status = TournamentStatus.ENCERRADO
                t.finished_at = t.finished_at or datetime.now(UTC)
                rnd.status = RoundStatus.ENCERRADA
            else:
                t.status = TournamentStatus.EM_ANDAMENTO
                t.finished_at = None
                rnd.status = RoundStatus.TIMES_TRAVADOS

    # ---------------------------------------------------------- leitura
    async def detail(self, tournament_id: int) -> TournamentOut:
        t = await self._tournament(tournament_id)
        rnd = await self._round(t.round_id)
        teams = {tm.id: TeamRef(id=tm.id, name=tm.name, color=tm.color) for tm in await self._teams(t.round_id)}
        matches = await self._matches(t.id)
        groups = list(await self.session.scalars(
            select(TournamentGroup).where(TournamentGroup.tournament_id == t.id).order_by(TournamentGroup.name)
        ))
        group_name = {g.id: g.name for g in groups}
        tables, complete = await self.group_tables(t)

        if t.format_code == FormatCode.PELADA_NORMAL:
            # Placar geral da pelada normal
            results = [Result(m.home_team_id, m.away_team_id, m.home_score, m.away_score)
                       for m in matches if m.status == MatchStatus.ENCERRADA]
            tables = {"Geral": compute_standings(t.config["team_order"], results, PointsConfig(**t.config["points"]),
                                                 ["PONTOS", "SALDO_GOLS", "GOLS_PRO"], t.config["seed"])}
            complete = {"Geral": t.status == TournamentStatus.ENCERRADO}

        group_out = [
            GroupOut(name=name, complete=complete[name], standings=[
                StandingRow(position=r.position, team=teams[r.team], played=r.played, wins=r.wins, draws=r.draws,
                            losses=r.losses, goals_for=r.goals_for, goals_against=r.goals_against,
                            goal_diff=r.goal_diff, points=r.points, tiebreak_note=r.tiebreak_note)
                for r in rows
            ])
            for name, rows in tables.items()
        ]

        def label(team_id, source):
            return teams[team_id].name if team_id in teams else source_label(source)

        kickoffs = assign_kickoffs(
            [KickoffMatch(id=m.id, seq=m.seq, stage=str(m.stage), home=m.home_team_id, away=m.away_team_id)
             for m in matches],
            campaign_ranking(tables) if t.format_code != FormatCode.PELADA_NORMAL else {},
        )
        match_out = [
            MatchOut(
                id=m.id, seq=m.seq, code=m.code, stage=m.stage, leg=m.leg, group=group_name.get(m.group_id),
                home=teams.get(m.home_team_id), away=teams.get(m.away_team_id),
                home_source=m.home_source, away_source=m.away_source,
                home_label=label(m.home_team_id, m.home_source), away_label=label(m.away_team_id, m.away_source),
                planned_seconds=m.planned_seconds, goal_limit=m.goal_limit, status=m.status,
                home_score=m.home_score, away_score=m.away_score,
                home_penalties=m.home_penalties, away_penalties=m.away_penalties,
                winner_team_id=m.winner_team_id, kickoff_team_id=kickoffs.get(m.id), started_at=m.started_at,
                elapsed_before_pause=m.elapsed_before_pause, ended_at=m.ended_at, version=m.version,
            )
            for m in matches
        ]
        next_match = next((m for m in matches if m.status != MatchStatus.ENCERRADA), None)
        return TournamentOut(
            id=t.id, round_id=t.round_id, round_date=rnd.date.isoformat(), format_code=t.format_code,
            format_name=FORMAT_INFO[FormatCode(t.format_code)][0]
            + (" — ida e volta" if t.config.get("legs") == 2 else ""),
            legs=t.config.get("legs", 1), status=t.status,
            match_seconds=t.match_seconds, knockout_seconds=t.config.get("knockout_seconds"),
            final_seconds=t.final_seconds,
            config={k: v for k, v in t.config.items() if k != "team_order"},
            teams=[teams[i] for i in t.config["team_order"] if i in teams],
            groups=group_out, matches=match_out, next_match_id=next_match.id if next_match else None,
            champion=teams.get(t.champion_team_id), runner_up=teams.get(t.runner_up_team_id),
            finished_at=t.finished_at,
        )

    async def by_round(self, round_id: int) -> Tournament | None:
        return await self.session.scalar(select(Tournament).where(Tournament.round_id == round_id))

    # ---------------------------------------------------------- helpers
    async def _matches(self, tournament_id: int) -> list[Match]:
        return list(await self.session.scalars(
            select(Match).where(Match.tournament_id == tournament_id).order_by(Match.seq)
        ))

    async def _round(self, round_id: int) -> Round:
        rnd = await self.session.get(Round, round_id)
        if rnd is None:
            raise NotFoundError("Rodada não encontrada")
        return rnd

    async def _tournament(self, tournament_id: int) -> Tournament:
        t = await self.session.get(Tournament, tournament_id)
        if t is None:
            raise NotFoundError("Campeonato não encontrado")
        return t

    async def _match(self, match_id: int) -> Match:
        m = await self.session.get(Match, match_id)
        if m is None:
            raise NotFoundError("Partida não encontrada")
        return m
