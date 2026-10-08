from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.domain.delinquency import FeeMark
from app.models.enums import pg_enum


class CashKind(StrEnum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"


class CashCategory(StrEnum):
    DIARISTAS_COLETE = "DIARISTAS_COLETE"
    CAMPO = "CAMPO"
    DIVERSOS = "DIVERSOS"
    OUTROS = "OUTROS"


class MonthlyFee(TimestampMixin, Base):
    """Uma célula da grade de mensalidades: jogador × mês.

    `amount` é o valor pago (pode ser parcial); `settled` marca um valor diferente da mensalidade
    como quitado (conta como pago); `marker` guarda anotações textuais, como "F" (fora: não é dívida).
    """

    __tablename__ = "monthly_fees"
    __table_args__ = (UniqueConstraint("player_id", "month", name="uq_monthly_fees_player_month"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"), index=True)
    month: Mapped[date] = mapped_column(Date, index=True)  # sempre dia 1
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    marker: Mapped[str | None] = mapped_column(String(20), nullable=True)
    settled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    @property
    def mark(self) -> FeeMark:
        return FeeMark(self.amount, self.settled, self.marker)


class CashEntry(TimestampMixin, Base):
    """Lançamento de caixa que não é mensalidade (diaristas, colete, campo, churrasco...)."""

    __tablename__ = "cash_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    month: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[CashKind] = mapped_column(pg_enum(CashKind, "cash_kind"))
    category: Mapped[CashCategory] = mapped_column(pg_enum(CashCategory, "cash_category"))
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # sempre positivo; o sinal vem de `kind`


class FinanceCollection(Base):
    """Cobrança avulsa (vaquinha), ex.: "Coletes novos" a R$ 20 por pessoa."""

    __tablename__ = "finance_collections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    amount_per_person: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["CollectionItem"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan", order_by="CollectionItem.id", lazy="selectin"
    )


class CollectionItem(Base):
    __tablename__ = "collection_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("finance_collections.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(120))  # nome como escrito (quando não há jogador vinculado)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    paid: Mapped[bool] = mapped_column(Boolean, default=False)

    collection: Mapped[FinanceCollection] = relationship(back_populates="items")
