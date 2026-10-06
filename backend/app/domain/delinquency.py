"""Inadimplência de mensalidade (regra pura).

Inadimplente = mensalista ativo que NÃO pagou nem o mês atual nem o anterior.
Um mês conta como pago quando o valor pago é >= mensalidade; parcial, anotação ou vazio = não pago.
"""
from datetime import date
from decimal import Decimal


def reference_months(today: date) -> tuple[date, date]:
    """(mês anterior, mês atual), sempre no dia 1. Em janeiro, o anterior é dezembro do ano passado."""
    current = today.replace(day=1)
    previous = date(current.year - 1, 12, 1) if current.month == 1 else current.replace(month=current.month - 1)
    return previous, current


def is_paid(amount: Decimal | None, fee: Decimal) -> bool:
    return amount is not None and amount >= fee


def is_delinquent(amounts: list[Decimal | None], fee: Decimal) -> bool:
    """`amounts`: valores pagos nos meses de referência (None = nada pago)."""
    return bool(amounts) and not any(is_paid(a, fee) for a in amounts)


def amount_due(amounts: list[Decimal | None], fee: Decimal) -> Decimal:
    """Quanto falta nos meses de referência (desconta pagamentos parciais)."""
    return sum((max(fee - (a or Decimal(0)), Decimal(0)) for a in amounts), Decimal(0))
