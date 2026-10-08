from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, field_validator

from app.domain.charge_message import validate_charge_message
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
    # Valor diferente da mensalidade que conta como pago (ex.: desconto combinado)
    settled: bool = False

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
    settled: bool = False


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
    # devem pelo menos 1 dos 2 meses de referência (lista "Para cobrar")
    to_charge_count: int = 0


class DelinquentOut(BaseModel):
    """Quem cobrar, para onde, quanto e quando foi cobrado pela última vez (por qual administrador)."""

    player_id: int
    name: str
    phone: str | None
    whatsapp_opt_in: bool
    months_due: list[date]  # só os meses em aberto
    amount_due: Decimal
    delinquent: bool = True  # deve os 2 meses (inadimplente) ou só 1
    last_charged_at: datetime | None = None
    last_charged_by: str | None = None


class ChargeVariable(BaseModel):
    name: str
    description: str


class ChargeMessageOut(BaseModel):
    message: str
    pix_key: str | None
    is_default: bool
    default_message: str
    variables: list[ChargeVariable]


class ChargeMessageIn(BaseModel):
    message: Annotated[str, AfterValidator(validate_charge_message)]
    pix_key: str | None = Field(default=None, max_length=140)


class ChargeIn(BaseModel):
    player_id: int


class ChargeOut(BaseModel):
    player_id: int
    charged_at: datetime
    charged_by: str


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


class MyMonth(BaseModel):
    month: date
    amount: Decimal | None
    marker: str | None
    settled: bool = False
    # paid | partial | out (F: fora, não é dívida) | open (mês atual em aberto) | late (atrasado)
    # | future | none (não se aplica)
    status: str


class MyFinanceOut(BaseModel):
    """Mensalidades do próprio jogador (área do jogador)."""

    has_player: bool
    player_name: str | None = None
    type: str | None = None
    year: int
    monthly_fee: Decimal
    months: list[MyMonth] = []
    total_paid: Decimal = Decimal("0.00")
    months_due: list[date] = []
    amount_due: Decimal = Decimal("0.00")
    pix_key: str | None = None


class TransparencyExpense(BaseModel):
    month: date
    category: CashCategory
    description: str | None
    amount: Decimal


class TransparencyPlayer(BaseModel):
    """Situação do mensalista mês a mês, sem valores: paid | out | partial | open | late | future | none."""

    name: str
    months: dict[str, str]  # chave: "YYYY-MM"


class TransparencyOut(BaseModel):
    """Portal da transparência: visível a qualquer usuário logado (sem telefones nem valores por jogador)."""

    year: int
    months: list[date]
    balance: Decimal
    year_income: Decimal
    year_expenses: Decimal
    summary: list[MonthSummary]
    expenses: list[TransparencyExpense]
    players: list[TransparencyPlayer]
