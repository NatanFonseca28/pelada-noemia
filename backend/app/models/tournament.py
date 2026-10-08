from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import pg_enum


class TournamentStatus(StrEnum):
    EM_ANDAMENTO = "EM_ANDAMENTO"
    ENCERRADO = "ENCERRADO"


class MatchStatus(StrEnum):
    AGENDADA = "AGENDADA"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    PAUSADA = "PAUSADA"
    ENCERRADA = "ENCERRADA"


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), unique=True)
    format_code: Mapped[str] = mapped_column(String(40))
    status: Mapped[TournamentStatus] = mapped_column(
        pg_enum(TournamentStatus, "tournament_status"), default=TournamentStatus.EM_ANDAMENTO
    )
    match_seconds: Mapped[int] = mapped_column(Integer)
    final_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Regras congeladas na criação: pontos, desempates, empate no mata-mata, seed do sorteio, etc.
    config: Mapped[dict] = mapped_column(JSONB)
    champion_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    runner_up_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TournamentGroup(Base):
    __tablename__ = "tournament_groups"
    __table_args__ = (UniqueConstraint("tournament_id", "name", name="uq_tournament_groups_tournament_name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(10))


class TournamentGroupTeam(Base):
    __tablename__ = "tournament_group_teams"

    group_id: Mapped[int] = mapped_column(ForeignKey("tournament_groups.id", ondelete="CASCADE"), primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("tournament_id", "seq", name="uq_matches_tournament_seq"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("tournament_groups.id", ondelete="SET NULL"),
                                                 nullable=True)
    stage: Mapped[str] = mapped_column(String(20))
    code: Mapped[str] = mapped_column(String(10))
    seq: Mapped[int] = mapped_column(SmallInteger)
    leg: Mapped[int] = mapped_column(SmallInteger, default=1)  # 1 = ida, 2 = volta
    home_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    away_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    home_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    away_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    planned_seconds: Mapped[int] = mapped_column(Integer)
    goal_limit: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    status: Mapped[MatchStatus] = mapped_column(pg_enum(MatchStatus, "match_status"), default=MatchStatus.AGENDADA)
    # Cronômetro (usado na etapa 5)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    elapsed_before_pause: Mapped[int] = mapped_column(Integer, default=0)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    home_score: Mapped[int] = mapped_column(SmallInteger, default=0)
    away_score: Mapped[int] = mapped_column(SmallInteger, default=0)
    home_penalties: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    away_penalties: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    winner_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class MatchLoan(Base):
    """Empréstimo usado numa partida ENCERRADA (as demais são calculadas na hora a partir da chamada)."""

    __tablename__ = "match_loans"
    __table_args__ = (UniqueConstraint("match_id", "player_id", name="uq_match_loans_match_player"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"))
    from_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    replaces_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"))
    strength_delta: Mapped[float] = mapped_column(Numeric(4, 2), default=0)
