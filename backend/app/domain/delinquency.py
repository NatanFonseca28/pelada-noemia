"""Inadimplência de mensalidade (regra pura).

Inadimplente = mensalista ativo que NÃO pagou nem o mês atual nem o anterior.
Um mês conta como pago quando o valor pago é >= mensalidade ou quando o admin marcou o valor como
quitado (ex.: desconto combinado). "F" (fora) não é dívida: o jogador não jogou naquele mês.
Parcial não quitado, outra anotação ou vazio = não pago.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

OUT_MARKER = "F"


@dataclass(frozen=True)
class FeeMark:
    """O que está numa célula da grade (jogador × mês)."""

    amount: Decimal | None = None
    settled: bool = False
    marker: str | None = None

    @property
    def is_out(self) -> bool:
        return (self.marker or "").strip().upper() == OUT_MARKER


def reference_months(today: date) -> tuple[date, date]:
    """(mês anterior, mês atual), sempre no dia 1. Em janeiro, o anterior é dezembro do ano passado."""
    current = today.replace(day=1)
    previous = date(current.year - 1, 12, 1) if current.month == 1 else current.replace(month=current.month - 1)
    return previous, current


def is_paid(mark: FeeMark | None, fee: Decimal) -> bool:
    if mark is None or mark.amount is None:
        return False
    return mark.settled or mark.amount >= fee


def is_owed(mark: FeeMark | None, fee: Decimal) -> bool:
    """Mês em aberto: nem pago nem fora."""
    return not is_paid(mark, fee) and not (mark is not None and mark.is_out)


def month_state(mark: FeeMark | None, fee: Decimal) -> str:
    """paid | out | partial | empty (empty inclui outras anotações sem valor)."""
    if is_paid(mark, fee):
        return "paid"
    if mark is not None and mark.is_out:
        return "out"
    if mark is not None and mark.amount:
        return "partial"
    return "empty"


def is_delinquent(marks: list[FeeMark | None], fee: Decimal) -> bool:
    """`marks`: células dos meses de referência (None = vazio). Pago ou F em algum deles afasta a inadimplência."""
    return bool(marks) and all(is_owed(m, fee) for m in marks)


def months_owed(months: list[date], marks: list[FeeMark | None], fee: Decimal) -> list[date]:
    """Meses de referência ainda não quitados (parcial conta como em aberto; F não conta)."""
    return [m for m, mark in zip(months, marks, strict=True) if is_owed(mark, fee)]


def amount_due(marks: list[FeeMark | None], fee: Decimal) -> Decimal:
    """Quanto falta nos meses de referência (desconta pagamentos parciais; ignora pagos e F)."""
    return sum(
        (max(fee - ((m.amount if m else None) or Decimal(0)), Decimal(0)) for m in marks if is_owed(m, fee)),
        Decimal(0),
    )
