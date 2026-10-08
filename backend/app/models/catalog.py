from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CatalogCompetition(Base):
    """Campeonato do football-data.org usado para dar nomes de clubes aos times do sorteio."""

    __tablename__ = "catalog_competitions"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    season: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CatalogClub(Base):
    __tablename__ = "catalog_clubs"
    __table_args__ = (UniqueConstraint("competition_code", "api_id", name="uq_catalog_clubs_competition_code_api"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    competition_code: Mapped[str] = mapped_column(
        ForeignKey("catalog_competitions.code", ondelete="CASCADE"), index=True
    )
    api_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(40))
    tla: Mapped[str] = mapped_column(String(5))
    color: Mapped[str] = mapped_column(String(9))
    crest_url: Mapped[str | None] = mapped_column(String(255), nullable=True)  # origem (para não baixar de novo)
    crest_path: Mapped[str | None] = mapped_column(String(200), nullable=True)  # em media_files

    @property
    def crest(self) -> str | None:
        return f"/api/media/{self.crest_path}" if self.crest_path else None
