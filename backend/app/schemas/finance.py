from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.finance import CashCategory, CashKind
from app.schemas.common import ORMModel


def _first_day(v: date) -> date:
    return v.replace(day=1)


class FinanceConfig(ORMModel):
    monthly_fee: Decimal = Field(ge=0, le=10000)
    finance_opening_balance: Decimal = Field(ge=-1_000_000, le=1_000_000)
    finance_opening_month: date | None

    @field_validator("finance_opening_month")
    @classmethod
    def first_day(cls, v: date | None) -> date | None:
        return _first_day(v) if v else v


class FeeCellIn(BaseModel):
    player_id: int
    month: date
    amount: Decimal | None = Field(default=None, ge=0, le=10000)
    marker: str | None = Field(default=None, max_length=20)

    @field_validator("amount")
    @classmethod
    def cents(cls, v: Decimal | None) -> Decimal | None:
        return v.quantize(Decimal("0.01")) if v is not None else v

    @field_validator("month")
    @classmethod
    def first_day(cls, v: date) -> date:
        return _first_day(v)


class FeeCellOut(BaseModel):
    amount: Decimal | None
    marker: str | None


class FeeRow(BaseModel):
    player_id: int
    name: str
    type: str
    active: bool
    cells: dict[str, FeeCellOut]  # chave: "YYYY-MM"
    total: Decimal
    # Inadimplência: mensalista ativo sem pagar o mês atual nem o anterior (relativo a hoje)
    delinquent: bool = False
    months_due: list[date] = []


class MonthSummary(BaseModel):
    month: date
    fees: Decimal
    income: Decimal
    expenses: Decimal
    net: Decimal
    paid_count: int


class FinanceOverview(BaseModel):
    year: int
    months: list[date]
    rows: list[FeeRow]
    summary: list[MonthSummary]
    config: FinanceConfig
    balance: Decimal
    year_total: Decimal
    reference_months: list[date]  # (anterior, atual) usados na regra de inadimplência
    delinquent_count: int


class DelinquentOut(BaseModel):
    """Base da futura cobrança por WhatsApp: quem cobrar, para onde e quanto."""

    player_id: int
    name: str
    phone: str | None
    whatsapp_opt_in: bool
    months_due: list[date]
    amount_due: Decimal


class CashEntryIn(BaseModel):
    month: date
    kind: CashKind
    category: CashCategory
    description: str | None = Field(default=None, max_length=200)
    amount: Decimal = Field(gt=0, le=1_000_000)

    @field_validator("month")
    @classmethod
    def first_day(cls, v: date) -> date:
        return _first_day(v)


class CashEntryOut(ORMModel, CashEntryIn):
    id: int


class CollectionItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    player_id: int | None = None
    amount: Decimal | None = Field(default=None, ge=0, le=100_000)
    paid: bool = False


class CollectionItemUpdate(BaseModel):
    paid: bool | None = None
    amount: Decimal | None = Field(default=None, ge=0, le=100_000)
    player_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)


class CollectionItemOut(ORMModel):
    id: int
    name: str
    player_id: int | None
    amount: Decimal
    paid: bool


class CollectionIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    amount_per_person: Decimal = Field(ge=0, le=100_000)


class CollectionOut(ORMModel):
    id: int
    title: str
    amount_per_person: Decimal
    items: list[CollectionItemOut]


class ImportResult(BaseModel):
    players_created: list[str]
    players_matched: list[str]
    fee_cells: int
    cash_entries: int
    collections: int
    opening_balance: Decimal | None
    opening_month: date | None
