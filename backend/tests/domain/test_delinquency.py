from datetime import date
from decimal import Decimal

from app.domain.delinquency import amount_due, is_delinquent, reference_months

FEE = Decimal("50")


def test_meses_de_referencia():
    assert reference_months(date(2026, 10, 6)) == (date(2026, 9, 1), date(2026, 10, 1))
    # virada de ano: em janeiro, o anterior é dezembro do ano passado
    assert reference_months(date(2027, 1, 15)) == (date(2026, 12, 1), date(2027, 1, 1))


def test_inadimplente_so_quando_os_dois_meses_estao_em_aberto():
    assert is_delinquent([None, None], FEE)
    assert not is_delinquent([FEE, None], FEE)  # pagou o anterior
    assert not is_delinquent([None, FEE], FEE)  # pagou o atual
    assert is_delinquent([Decimal("20"), Decimal("35")], FEE)  # parcial nos dois conta como não pago
    assert not is_delinquent([Decimal("100"), None], FEE)  # pagou a mais num deles


def test_valor_devido_desconta_parciais():
    assert amount_due([None, None], FEE) == Decimal("100")
    assert amount_due([Decimal("20"), None], FEE) == Decimal("80")
