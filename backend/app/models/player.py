from sqlalchemy import BigInteger, Boolean, CheckConstraint, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import PlayerType, Position, pg_enum


class Player(TimestampMixin, Base):
    __tablename__ = "players"
    __table_args__ = (
        CheckConstraint("skill_level BETWEEN 1 AND 5", name="skill_level_range"),
        CheckConstraint("speed BETWEEN 1 AND 5", name="speed_range"),
        CheckConstraint(
            "secondary_position IS NULL OR secondary_position <> primary_position",
            name="secondary_differs",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    nickname: Mapped[str | None] = mapped_column(String(60), nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[PlayerType] = mapped_column(pg_enum(PlayerType, "player_type"))
    # Nulo = "a definir" (ex.: jogadores importados da planilha financeira)
    primary_position: Mapped[Position | None] = mapped_column(pg_enum(Position, "player_position"), nullable=True)
    secondary_position: Mapped[Position | None] = mapped_column(
        pg_enum(Position, "player_position"), nullable=True
    )
    skill_level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    speed: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Contato (visível só para ADMIN). E.164, ex.: +5521987654321
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    @property
    def display_name(self) -> str:
        return self.nickname or self.name

    @property
    def photo_url(self) -> str | None:
        return f"/api/media/{self.photo_path}" if self.photo_path else None
