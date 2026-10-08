from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.domain.draw import DEFAULT_LEVEL, DEFAULT_SPEED, DrawConfig, DrawError, DrawPlayer, new_seed, run_draw
from app.models.enums import Position, UserRole
from app.models.match_event import MatchEvent
from app.models.player import Player
from app.models.round import (
    Attendance,
    AttendanceSource,
    AttendanceStatus,
    Draw,
    Round,
    RoundStatus,
    Team,
    TeamPlayer,
    TeamRole,
)
from app.models.tournament import Match, MatchStatus, Tournament
from app.models.user import User
from app.repositories.settings_repo import SettingsRepository
from app.schemas.round import (
    AttendanceOut,
    DrawInfo,
    LoanOut,
    RoundDetail,
    RoundSummary,
    SimplePlayer,
    TeamOut,
    TeamPlayerOut,
    UnfilledOut,
)
from app.services import audit_service
from app.services.callroll_service import CallRollService

EDITABLE = {RoundStatus.ABERTA, RoundStatus.FECHADA}


class RoundService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------------------------------------------------------- consultas
    async def list(self) -> list[RoundSummary]:
        confirmed = (
            select(Attendance.round_id, func.count().label("n"))
            .where(Attendance.status == AttendanceStatus.CONFIRMADO)
            .group_by(Attendance.round_id)
            .subquery()
        )
        teams = select(Team.round_id).distinct().subquery()
        rows = await self.session.execute(
            select(Round, func.coalesce(confirmed.c.n, 0), teams.c.round_id.is_not(None), Tournament.id)
            .outerjoin(confirmed, confirmed.c.round_id == Round.id)
            .outerjoin(teams, teams.c.round_id == Round.id)
            .outerjoin(Tournament, Tournament.round_id == Round.id)
            .order_by(Round.date.desc())
        )
        return [
            RoundSummary(id=r.id, date=r.date, status=r.status, notes=r.notes, confirmed_count=n, has_teams=has,
                         tournament_id=tid)
            for r, n, has, tid in rows
        ]

    async def current(self) -> Round | None:
        """Rodada em andamento mais próxima (a mais recente não encerrada)."""
        return await self.session.scalar(
            select(Round).where(Round.status != RoundStatus.ENCERRADA).order_by(Round.date.desc()).limit(1)
        )

    async def detail(self, round_id: int, viewer: User) -> RoundDetail:
        rnd = await self._round(round_id)
        att_rows = (
            await self.session.execute(
                select(Attendance, Player)
                .join(Player, Player.id == Attendance.player_id)
                .where(Attendance.round_id == rnd.id)
                .order_by(Attendance.updated_at)
            )
        ).all()
        confirmed = [(a, p) for a, p in att_rows if a.status == AttendanceStatus.CONFIRMADO]
        absent = [(a, p) for a, p in att_rows if a.status == AttendanceStatus.CANCELADO]
        my_status = next((a.status.value for a, p in att_rows if p.id == viewer.player_id), None)

        draw = await self.session.scalar(select(Draw).where(Draw.round_id == rnd.id, Draw.is_current.is_(True)))
        teams = list(
            await self.session.scalars(select(Team).where(Team.round_id == rnd.id).order_by(Team.display_order))
        )
        player_ids = {tp.player_id for t in teams for tp in t.players}
        players = {
            p.id: p for p in await self.session.scalars(select(Player).where(Player.id.in_(player_ids)))
        } if player_ids else {}

        mode = draw.result.get("mode") if draw else None
        # Goleiro fixo confirmado e fora dos times = goleiro da pelada (agarra para todos)
        shared_gks = [SimplePlayer(player_id=p.id, name=p.display_name) for _, p in confirmed
                      if teams and p.id not in player_ids and p.primary_position == Position.GOLEIRO_FIXO]
        team_out = []
        for t in teams:
            slots = sorted(
                t.players,
                key=lambda tp: (tp.role == TeamRole.REVEZAMENTO, tp.role != TeamRole.GOLEIRO_FIXO,
                                ["GOLEIRO_FIXO", "ZAGUEIRO", "ALA", "ATACANTE"].index(tp.assigned_position)
                                if tp.assigned_position in ("GOLEIRO_FIXO", "ZAGUEIRO", "ALA", "ATACANTE") else 9),
            )
            has_gk = any(tp.role == TeamRole.GOLEIRO_FIXO for tp in t.players)
            line = [players[tp.player_id] for tp in t.players if tp.role != TeamRole.GOLEIRO_FIXO]
            # Equilíbrio (nível/velocidade são internos: só ADMIN vê). Goleiro fixo não conta.
            balance = {}
            if viewer.role == UserRole.ADMIN and line:
                levels = [p.skill_level or DEFAULT_LEVEL for p in line]
                speeds = [p.speed or DEFAULT_SPEED for p in line]
                balance = dict(level_avg=round(sum(levels) / len(line), 2),
                               speed_avg=round(sum(speeds) / len(line), 2),
                               strength_avg=round((sum(levels) + sum(speeds)) / len(line), 2))
            has_rot = any(tp.role == TeamRole.REVEZAMENTO for tp in t.players)
            team_out.append(
                TeamOut(
                    id=t.id,
                    name=t.name,
                    color=t.color,
                    players=[
                        TeamPlayerOut(
                            player_id=tp.player_id,
                            name=players[tp.player_id].display_name,
                            photo_url=players[tp.player_id].photo_url,
                            position=tp.assigned_position,
                            role=tp.role,
                            filled_by=tp.filled_by,
                            moved_manually=tp.moved_manually,
                        )
                        for tp in slots
                    ],
                    line_count=sum(1 for tp in t.players if tp.role != TeamRole.GOLEIRO_FIXO),
                    has_fixed_gk=has_gk,
                    has_rotation_gk=has_rot,
                    uses_volunteer_gk=mode == "CAMPEONATO" and not has_gk and not has_rot and not shared_gks,
                    uses_shared_gk=not has_gk and not has_rot and bool(shared_gks),
                    **balance,
                )
            )

        confirmed_ids = {p.id for _, p in confirmed}
        not_in_teams = [SimplePlayer(player_id=p.id, name=p.display_name)
                        for _, p in confirmed if teams and p.id not in player_ids
                        and p.primary_position != Position.GOLEIRO_FIXO]
        no_longer = [SimplePlayer(player_id=pid, name=players[pid].display_name)
                     for pid in player_ids if pid not in confirmed_ids]

        tournament_id = await self.session.scalar(select(Tournament.id).where(Tournament.round_id == rnd.id))
        loans, unfilled = await self._loans(rnd.id, viewer.role == UserRole.ADMIN)
        return RoundDetail(
            id=rnd.id,
            tournament_id=tournament_id,
            date=rnd.date,
            status=rnd.status,
            notes=rnd.notes,
            confirmed_count=len(confirmed),
            has_teams=bool(teams),
            attendances=[self._attendance_out(a, p) for a, p in confirmed],
            absences=[self._attendance_out(a, p) for a, p in absent],
            my_player_id=viewer.player_id,
            my_status=my_status,
            draw=DrawInfo(
                id=draw.id,
                seed=draw.seed,
                mode=draw.result["mode"],
                num_teams=draw.num_teams,
                warnings=draw.result["warnings"],
                infos=draw.result["infos"],
                substitutions=draw.result["substitutions"],
                alternatives=draw.result["alternatives"],
                allow_short_team=draw.input_snapshot["config"].get("allow_short_team", False),
                created_at=draw.created_at,
            ) if draw else None,
            teams=team_out,
            not_in_teams=not_in_teams,
            shared_goalkeepers=shared_gks,
            loans=loans,
            unfilled=unfilled,
            no_longer_confirmed=no_longer,
        )

    # ---------------------------------------------------------- rodada
    async def create(self, round_date, notes: str | None, actor: User) -> Round:
        if await self.session.scalar(select(Round).where(Round.date == round_date)):
            raise ConflictError("Já existe uma rodada nessa data")
        settings = await SettingsRepository(self.session).get_current()
        rnd = Round(date=round_date, notes=notes, status=RoundStatus.ABERTA,
                    settings_snapshot=audit_service.snapshot(settings))
        self.session.add(rnd)
        await self.session.flush()
        await audit_service.record(self.session, user_id=actor.id, action="CREATE", entity="round",
                                   entity_id=rnd.id, after={"date": round_date.isoformat()})
        await self.session.commit()
        return rnd

    async def set_status(self, round_id: int, action: str, actor: User) -> None:
        rnd = await self._round(round_id)
        transitions = {
            "open": ({RoundStatus.FECHADA}, RoundStatus.ABERTA),
            "close": ({RoundStatus.ABERTA}, RoundStatus.FECHADA),
            "lock": (EDITABLE, RoundStatus.TIMES_TRAVADOS),
            "unlock": ({RoundStatus.TIMES_TRAVADOS}, RoundStatus.FECHADA),
        }
        allowed, target = transitions[action]
        if rnd.status not in allowed:
            raise ValidationError(f"Não é possível essa ação com a rodada no status {rnd.status.value}")
        if action == "unlock":
            if await self.session.scalar(select(Tournament.id).where(Tournament.round_id == rnd.id)):
                raise ValidationError("Exclua o campeonato antes de destravar os times")
        if action == "lock":
            if not await self.session.scalar(select(Team.id).where(Team.round_id == rnd.id).limit(1)):
                raise ValidationError("Faça o sorteio antes de travar os times")
        before = rnd.status.value
        rnd.status = target
        await audit_service.record(self.session, user_id=actor.id, action=action.upper(), entity="round",
                                   entity_id=rnd.id, before={"status": before}, after={"status": target.value})
        await self.session.commit()

    async def delete(self, round_id: int, actor: User, force: bool = False) -> None:
        """Exclui a rodada. Rodada travada/encerrada só com `force`: apaga junto presenças, sorteios, times,
        campeonato, partidas e súmula (cascata do banco). Mensalidades e caixa não têm vínculo e ficam intactos."""
        rnd = await self._round(round_id)
        played = rnd.status in (RoundStatus.TIMES_TRAVADOS, RoundStatus.ENCERRADA)
        if played and not force:
            raise ValidationError("Rodada já realizada: confirme a exclusão definitiva (apaga campeonato e súmulas)")
        summary = await self._delete_summary(rnd)
        await audit_service.record(self.session, user_id=actor.id, action="DELETE", entity="round",
                                   entity_id=rnd.id, before=summary)
        await self.session.delete(rnd)
        await self.session.commit()

    async def _delete_summary(self, rnd: Round) -> dict:
        t = await self.session.scalar(select(Tournament).where(Tournament.round_id == rnd.id))
        matches = events = 0
        champion = None
        if t:
            matches = await self.session.scalar(select(func.count()).select_from(Match).where(Match.tournament_id == t.id))
            events = await self.session.scalar(
                select(func.count()).select_from(MatchEvent).join(Match, Match.id == MatchEvent.match_id)
                .where(Match.tournament_id == t.id, MatchEvent.deleted_at.is_(None))
            )
            if t.champion_team_id:
                champion = await self.session.scalar(select(Team.name).where(Team.id == t.champion_team_id))
        confirmed = await self.session.scalar(
            select(func.count()).select_from(Attendance)
            .where(Attendance.round_id == rnd.id, Attendance.status == AttendanceStatus.CONFIRMADO)
        )
        return {"date": rnd.date.isoformat(), "status": rnd.status.value, "confirmed": confirmed,
                "tournament": t.format_code if t else None, "matches": matches, "events": events, "champion": champion}

    # ---------------------------------------------------------- presença
    async def set_attendance(self, round_id: int, player_id: int, confirmed: bool, actor: User,
                             as_admin: bool) -> None:
        rnd = await self._round(round_id)
        player = await self.session.get(Player, player_id)
        if player is None:
            raise NotFoundError("Jogador não encontrado")
        if as_admin:
            if rnd.status not in EDITABLE:
                raise ValidationError("Times travados: destrave para alterar a lista")
        else:
            if rnd.status != RoundStatus.ABERTA:
                raise ValidationError("A lista de presença desta rodada está fechada")
            if not player.active:
                raise ForbiddenError("Jogador inativo")
        att = await self.session.scalar(
            select(Attendance).where(Attendance.round_id == rnd.id, Attendance.player_id == player_id)
        )
        status = AttendanceStatus.CONFIRMADO if confirmed else AttendanceStatus.CANCELADO
        before = att.status.value if att else None
        if att is None:
            att = Attendance(round_id=rnd.id, player_id=player_id)
            self.session.add(att)
        att.status = status
        att.source = AttendanceSource.ADMIN if as_admin else AttendanceSource.APP
        att.updated_by = actor.id
        att.updated_at = datetime.now(UTC)
        await audit_service.record(self.session, user_id=actor.id, action="ATTENDANCE", entity="round",
                                   entity_id=rnd.id, before={"player_id": player_id, "status": before},
                                   after={"player_id": player_id, "status": status.value})
        await self.session.commit()

    async def clear_attendance(self, round_id: int, player_id: int, actor: User) -> None:
        """ADMIN volta o jogador para "sem resposta" (apaga o registro de presença)."""
        rnd = await self._round(round_id)
        if rnd.status not in EDITABLE:
            raise ValidationError("Times travados: destrave para alterar a lista")
        att = await self.session.scalar(
            select(Attendance).where(Attendance.round_id == rnd.id, Attendance.player_id == player_id)
        )
        if att is None:
            return
        before = att.status.value
        await self.session.delete(att)
        await audit_service.record(self.session, user_id=actor.id, action="ATTENDANCE", entity="round",
                                   entity_id=rnd.id, before={"player_id": player_id, "status": before},
                                   after={"player_id": player_id, "status": None})
        await self.session.commit()

    async def set_my_attendance(self, round_id: int, confirmed: bool, user: User) -> None:
        if user.player_id is None:
            raise ValidationError("Seu usuário não está vinculado a um jogador. Fale com o administrador.")
        await self.set_attendance(round_id, user.player_id, confirmed, user, as_admin=False)

    # ---------------------------------------------------------- sorteio
    async def draw(self, round_id: int, num_teams: int | None, seed: int | None, actor: User,
                   allow_short_team: bool = False) -> None:
        rnd = await self._round(round_id)
        if rnd.status not in EDITABLE:
            raise ValidationError("Times travados: destrave para sortear novamente")
        settings = await SettingsRepository(self.session).get_current()
        rows = (
            await self.session.execute(
                select(Player)
                .join(Attendance, Attendance.player_id == Player.id)
                .where(Attendance.round_id == rnd.id, Attendance.status == AttendanceStatus.CONFIRMADO)
            )
        ).scalars().all()
        players = [
            DrawPlayer(
                id=p.id,
                name=p.display_name,
                primary=p.primary_position.value if p.primary_position else None,
                secondary=p.secondary_position.value if p.secondary_position else None,
                level=p.skill_level,
                speed=p.speed,
            )
            for p in rows
        ]
        config = DrawConfig(
            line_per_team=settings.line_players_per_team,
            balance_by_skill=settings.balance_by_skill,
            extra_team_threshold=settings.extra_team_threshold,
            allow_short_team=allow_short_team,
        )
        seed = seed or new_seed()
        try:
            result = run_draw(players, config, seed, num_teams)
        except DrawError as exc:
            raise ValidationError(str(exc)) from exc

        await self.session.execute(update(Draw).where(Draw.round_id == rnd.id).values(is_current=False))
        await self.session.execute(delete(Team).where(Team.round_id == rnd.id))
        data = result.to_dict()
        draw = Draw(
            round_id=rnd.id,
            seed=seed,
            algorithm_version=result.algorithm_version,
            num_teams=result.num_teams,
            input_snapshot={
                "players": [vars(p) for p in sorted(players, key=lambda p: p.id)],
                "config": vars(config),
                "num_teams": num_teams,
            },
            result=data,
            is_current=True,
            created_by=actor.id,
        )
        self.session.add(draw)
        await self.session.flush()
        for team in result.teams:
            row = Team(round_id=rnd.id, draw_id=draw.id, name=team.name, color=team.color, display_order=team.index)
            row.players = [
                TeamPlayer(round_id=rnd.id, player_id=s.player_id, assigned_position=s.position,
                           role=TeamRole(s.role.value), filled_by=s.filled_by.value, moved_manually=False)
                for s in team.players
            ]
            self.session.add(row)
        if rnd.status == RoundStatus.ABERTA:
            rnd.status = RoundStatus.FECHADA  # sortear fecha a lista
        await audit_service.record(self.session, user_id=actor.id, action="DRAW", entity="round", entity_id=rnd.id,
                                   after={"draw_id": draw.id, "seed": seed, "num_teams": result.num_teams})
        await self.session.commit()

    async def move(self, round_id: int, player_id: int, team_id: int | None, role: TeamRole | None,
                   actor: User) -> None:
        rnd = await self._round(round_id)
        if rnd.status not in EDITABLE:
            raise ValidationError("Times travados: destrave para ajustar")
        player = await self.session.get(Player, player_id)
        if player is None:
            raise NotFoundError("Jogador não encontrado")
        tp = await self.session.scalar(
            select(TeamPlayer).where(TeamPlayer.round_id == rnd.id, TeamPlayer.player_id == player_id)
        )
        before = {"team_id": tp.team_id, "role": tp.role.value} if tp else None

        if team_id is None:
            if tp is None:
                raise ValidationError("Jogador não está em nenhum time")
            await self.session.delete(tp)
            after = None
        else:
            team = await self.session.get(Team, team_id)
            if team is None or team.round_id != rnd.id:
                raise NotFoundError("Time não encontrado nesta rodada")
            if tp is None:
                is_gk = player.primary_position == Position.GOLEIRO_FIXO
                tp = TeamPlayer(
                    round_id=rnd.id, player_id=player_id,
                    assigned_position=player.primary_position.value if player.primary_position else "ALA",
                    role=TeamRole.GOLEIRO_FIXO if is_gk else TeamRole.LINHA,
                    filled_by="PRIMARIA" if player.primary_position else "SEM_POSICAO",
                )
                self.session.add(tp)
            tp.team_id = team.id
            if role is not None:
                tp.role = role
                if role == TeamRole.GOLEIRO_FIXO:
                    tp.assigned_position = "GOLEIRO_FIXO"
                elif tp.assigned_position == "GOLEIRO_FIXO":
                    tp.assigned_position = "ALA"
            if tp.role == TeamRole.GOLEIRO_FIXO:
                other_gk = await self.session.scalar(
                    select(TeamPlayer).where(TeamPlayer.team_id == team.id, TeamPlayer.role == TeamRole.GOLEIRO_FIXO,
                                             TeamPlayer.player_id != player_id)
                )
                if other_gk:
                    raise ValidationError(f"O Time {team.name} já tem goleiro fixo")
            tp.moved_manually = True
            after = {"team_id": team.id, "role": tp.role.value}
        await audit_service.record(self.session, user_id=actor.id, action="MOVE", entity="round", entity_id=rnd.id,
                                   before={"player_id": player_id, **(before or {})},
                                   after={"player_id": player_id, **(after or {})})
        await self.session.commit()

    @staticmethod
    def _attendance_out(a: Attendance, p: Player) -> AttendanceOut:
        return AttendanceOut(player_id=p.id, name=p.display_name, type=p.type,
                             primary_position=p.primary_position, source=a.source, updated_at=a.updated_at,
                             checkin=a.checkin)

    async def _loans(self, round_id: int, show_strength: bool) -> "tuple[list[LoanOut], list[UnfilledOut]]":
        data = await CallRollService(self.session).plan(round_id)
        if data is None:
            return [], []
        team_name = {t.id: t.name for t in data.teams.values()}

        def label(match_id: int) -> str:
            m = data.matches[match_id]
            return f"{team_name.get(m.home_team_id, '?')} × {team_name.get(m.away_team_id, '?')}"

        loans = [
            LoanOut(match_id=x.match_id, match_seq=data.matches[x.match_id].seq, match_label=label(x.match_id),
                    finished=data.matches[x.match_id].status == MatchStatus.ENCERRADA,
                    team_id=x.team_id, team_name=team_name[x.team_id], player_id=x.player_id,
                    player_name=data.names.get(x.player_id, "?"), from_team_name=team_name[x.from_team_id],
                    replaces_name=data.names.get(x.replaces_id, "?"),
                    strength_delta=x.strength_delta if show_strength else None)
            for x in data.plan.loans
        ]
        unfilled = [
            UnfilledOut(match_id=mid, match_seq=data.matches[mid].seq, match_label=label(mid),
                        missing_names=[data.names.get(pid, "?") for pid in ids])
            for mid, ids in data.plan.unfilled.items()
        ]
        return sorted(loans, key=lambda x: (x.match_seq, x.team_name)), sorted(unfilled, key=lambda x: x.match_seq)

    async def _round(self, round_id: int) -> Round:
        rnd = await self.session.get(Round, round_id)
        if rnd is None:
            raise NotFoundError("Rodada não encontrada")
        return rnd
