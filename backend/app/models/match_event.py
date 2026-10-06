import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, SmallInteger, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import pg_enum


class EventType(StrEnum):
    GOL = "GOL"
    GOL_CONTRA = "GOL_CONTRA"
    AMARELO = "AMARELO"
    VERMELHO = "VERMELHO"


class MatchEvent(Base):
    """Evento de partida. É a fonte do placar e das estatísticas.

    - GOL: `team_id` é o time que marcou; `player_id` pode ser nulo (gol sem autor identificado).
    - GOL_CONTRA: `team_id` é o time do jogador que fez contra; o gol conta para o adversário.
    - Cartões: `team_id` é o time do jogador.
    Exclusão é lógica (`deleted_at`) para que desfazer/reenviar seja idempotente.
    """

    __tablename__ = "match_events"
    __table_args__ = (UniqueConstraint("match_id", "client_event_id", name="uq_match_events_match_client"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    client_event_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    type: Mapped[EventType] = mapped_column(pg_enum(EventType, "match_event_type"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"), nullable=True,
                                                  index=True)
    assist_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"),
                                                         nullable=True)
    minute: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    second: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_event_id: Mapped[int | None] = mapped_column(ForeignKey("match_events.id", ondelete="CASCADE"),
                                                        nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
