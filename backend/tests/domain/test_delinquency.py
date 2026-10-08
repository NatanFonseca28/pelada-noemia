from datetime import date
from decimal import Decimal

from app.domain.delinquency import FeeMark, amount_due, is_delinquent, month_state, months_owed, reference_months

FEE = Decimal("50")
PAID = FeeMark(FEE)
OUT = FeeMark(marker="F")


def test_meses_de_referencia():
    assert reference_months(date(2026, 10, 6)) == (date(2026, 9, 1), date(2026, 10, 1))
    # virada de ano: em janeiro, o anterior é dezembro do ano passado
    assert reference_months(date(2027, 1, 15)) == (date(2026, 12, 1), date(2027, 1, 1))


def test_inadimplente_so_quando_os_dois_meses_estao_em_aberto():
    assert is_delinquent([None, None], FEE)
    assert not is_delinquent([PAID, None], FEE)  # pagou o anterior
    assert not is_delinquent([None, PAID], FEE)  # pagou o atual
    assert is_delinquent([FeeMark(Decimal("20")), FeeMark(Decimal("35"))], FEE)  # parcial nos dois = não pago
    assert not is_delinquent([FeeMark(Decimal("100")), None], FEE)  # pagou a mais num deles
    assert is_delinquent([FeeMark(marker="obs"), None], FEE)  # outra anotação não conta


def test_valor_devido_desconta_parciais():
    assert amount_due([None, None], FEE) == Decimal("100")
    assert amount_due([FeeMark(Decimal("20")), None], FEE) == Decimal("80")


def test_valor_diferente_quitado_conta_como_pago():
    quitado = FeeMark(Decimal("30"), settled=True)
    assert month_state(quitado, FEE) == "paid"
    assert not is_delinquent([quitado, None], FEE)
    assert amount_due([quitado, None], FEE) == Decimal("50")
    assert month_state(FeeMark(Decimal("30")), FEE) == "partial"  # sem quitar continua parcial


def test_fora_nao_e_divida():
    prev, cur = date(2026, 9, 1), date(2026, 10, 1)
    assert month_state(OUT, FEE) == "out" and month_state(FeeMark(marker=" f "), FEE) == "out"
    assert not is_delinquent([OUT, OUT], FEE)
    # F + vazio: não é inadimplente, mas deve o mês vazio ("para cobrar")
    assert not is_delinquent([OUT, None], FEE)
    assert months_owed([prev, cur], [OUT, None], FEE) == [cur]
    assert amount_due([OUT, None], FEE) == Decimal("50")
    assert months_owed([prev, cur], [OUT, PAID], FEE) == []


def test_vazio_continua_inadimplencia():
    assert month_state(None, FEE) == "empty"
    assert months_owed([date(2026, 9, 1), date(2026, 10, 1)], [None, None], FEE) == [date(2026, 9, 1), date(2026, 10, 1)]
