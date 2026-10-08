from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import pg_enum


class RoundStatus(StrEnum):
    ABERTA = "ABERTA"  # confirmações abertas
    FECHADA = "FECHADA"  # lista fechada (sorteio permitido)
    TIMES_TRAVADOS = "TIMES_TRAVADOS"
    ENCERRADA = "ENCERRADA"


class AttendanceStatus(StrEnum):
    CONFIRMADO = "CONFIRMADO"
    CANCELADO = "CANCELADO"


class AttendanceSource(StrEnum):
    APP = "APP"
    ADMIN = "ADMIN"


class TeamRole(StrEnum):
    LINHA = "LINHA"
    GOLEIRO_FIXO = "GOLEIRO_FIXO"
    REVEZAMENTO = "REVEZAMENTO"


class Round(TimestampMixin, Base):
    """Uma quarta-feira de pelada."""

    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True)
    status: Mapped[RoundStatus] = mapped_column(pg_enum(RoundStatus, "round_status"), default=RoundStatus.ABERTA)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    settings_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)


class Attendance(Base):
    __tablename__ = "attendances"
    __table_args__ = (
        UniqueConstraint("round_id", "player_id", name="uq_attendances_round_player"),
        CheckConstraint("checkin IN ('PRESENTE', 'FALTOU')", name="checkin_values"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"), index=True)
    status: Mapped[AttendanceStatus] = mapped_column(pg_enum(AttendanceStatus, "attendance_status"))
    source: Mapped[AttendanceSource] = mapped_column(pg_enum(AttendanceSource, "attendance_source"))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Chamada no local: PRESENTE | FALTOU (None = ainda não chamado)
    checkin: Mapped[str | None] = mapped_column(String(10), nullable=True)
    checkin_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Draw(Base):
    """Sorteio imutável: seed + entrada + resultado, para auditoria e reprodução."""

    __tablename__ = "draws"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), index=True)
    seed: Mapped[int] = mapped_column(BigInteger)
    algorithm_version: Mapped[str] = mapped_column(String(10))
    num_teams: Mapped[int] = mapped_column(SmallInteger)
    input_snapshot: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict] = mapped_column(JSONB)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), index=True)
    draw_id: Mapped[int] = mapped_column(ForeignKey("draws.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(40))
    color: Mapped[str] = mapped_column(String(9))
    display_order: Mapped[int] = mapped_column(Integer)

    players: Mapped[list["TeamPlayer"]] = relationship(
        back_populates="team", cascade="all, delete-orphan", lazy="selectin", order_by="TeamPlayer.id"
    )


class TeamPlayer(Base):
    __tablename__ = "team_players"
    __table_args__ = (UniqueConstraint("round_id", "player_id", name="uq_team_players_round_player"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"), index=True)
    assigned_position: Mapped[str] = mapped_column(String(20))
    role: Mapped[TeamRole] = mapped_column(pg_enum(TeamRole, "team_role"))
    filled_by: Mapped[str] = mapped_column(String(20))
    moved_manually: Mapped[bool] = mapped_column(Boolean, default=False)

    team: Mapped[Team] = relationship(back_populates="players")
