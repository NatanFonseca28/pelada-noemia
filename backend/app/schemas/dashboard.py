from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class SquadNumbers(BaseModel):
    monthly_active: int
    daily_active: int
    inactive: int


class FinanceNumbers(BaseModel):
    balance: Decimal
    month: date
    month_income: Decimal  # mensalidades + entradas do mês
    month_expenses: Decimal
    monthly_paid: int  # mensalistas ativos que quitaram o mês
    monthly_total: int
    delinquent_count: int
    delinquent_amount: Decimal
    reference_months: list[date]
    collections_open: Decimal  # cobranças avulsas ainda não pagas


class RoundNumbers(BaseModel):
    id: int
    date: date
    status: str
    confirmed: int
    goalkeepers: int
    teams: int
    tournament_id: int | None


class Highlight(BaseModel):
    player_id: int
    name: str
    value: str


class SeasonNumbers(BaseModel):
    year: int
    rounds_played: int
    avg_players: float
    goals: int
    last_champion: str | None
    last_champion_date: date | None
    last_tournament_id: int | None
    top_scorer: Highlight | None
    most_present: Highlight | None
    best_win_rate: Highlight | None


class YearSummaryOut(BaseModel):
    """Fechamento do ano: jogos, campeão, dinheiro e o saldo que vira o saldo inicial do ano seguinte."""

    year: int
    closed: bool  # ano já terminou (só leitura para admin)
    partial: bool  # ano em andamento: números parciais
    season: SeasonNumbers
    fees_total: Decimal  # mensalidades recebidas
    daily_total: Decimal  # diárias antecipadas pagas
    other_income: Decimal  # outras entradas do caixa
    expenses: Decimal
    net: Decimal  # entradas - saídas do ano
    opening_balance: Decimal  # saldo no início do ano
    closing_balance: Decimal  # saldo no fim do ano = saldo inicial do ano seguinte


class Pending(BaseModel):
    pending_users: int
    players_without_position: int
    monthly_without_whatsapp: int
    monthly_without_consent: int
    locked_accounts: int


class DashboardOut(BaseModel):
    squad: SquadNumbers
    finance: FinanceNumbers
    current_round: RoundNumbers | None
    season: SeasonNumbers
    pending: Pending
