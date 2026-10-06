from datetime import date, datetime
from decimal import Decimal

import pytest

from app.domain.finance_sheet import SheetFormatError, clean_player_name, normalize, parse_rows


def row(*cells, n=19):
    cells = list(cells) + [None] * (n - len(cells))
    return tuple(cells)


def at(**cols):
    """Cria uma linha preenchendo colunas por letra: at(A='X', N='Y')."""
    cells = [None] * 19
    for letter, value in cols.items():
        cells[ord(letter) - ord("A")] = value
    return tuple(cells)


JAN, FEV, MAR = datetime(2026, 1, 1), datetime(2026, 2, 1), datetime(2026, 3, 1)
# Obs.: a linha do MICHEL deixa a coluna N vazia no meio da cobrança (como na planilha real)

ROWS = [
    at(A="x"),
    row(),
    at(A="NOME", B=JAN, C=FEV, D=MAR, N="RESUMO"),
    at(A="DANIEL", B=50.0, C=50.0, D=50.0, N="SALDO MÊS ANTERIOR", Q=2266.0),
    at(A="DG", C=50.0),
    at(A="WAGNER", B=50.0, C="F", N="SALDO MÊS ATUAL", Q=120),
    at(A="DG", B=50.0, N="VALOR CAMPO", Q=-800),
    at(A="RODRIGO GOMES ZAG", B=20.0, N="DIVERSOS, CHURRASCO, BOLA, COLETE"),
    at(A="LEONARDO", B=50.0, N="COLETES NOVOS", P="PG"),
    at(A="GUMA", D=35.0, N="PETER", O=20.0),
    at(A="GUMA", D=15.0, N="DANIEL", O=20.0, P="OK"),
    at(A="MICHEL", B=50.0),
    at(A="DIARISTA, COLETE", B=60.0, D=300.0, N="PENETRA"),
    at(A="TOTAL", B=330, C=150, D=400),
]


def test_parse_planilha_completa():
    sheet = parse_rows(ROWS)
    assert sheet.months == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]
    assert list(sheet.fees) == ["DANIEL", "DG", "WAGNER", "RODRIGO GOMES ZAG", "LEONARDO", "GUMA", "MICHEL"]
    # Linhas repetidas do mesmo nome são mescladas
    assert sheet.fees["DG"][date(2026, 1, 1)].amount == Decimal("50.00")
    assert sheet.fees["DG"][date(2026, 2, 1)].amount == Decimal("50.00")
    assert sheet.fees["GUMA"][date(2026, 3, 1)].amount == Decimal("50.00")
    # Texto vira marcador
    assert sheet.fees["WAGNER"][date(2026, 2, 1)].marker == "F"
    assert sheet.fees["WAGNER"][date(2026, 2, 1)].amount is None
    assert sheet.extra_income == {date(2026, 1, 1): Decimal("60.00"), date(2026, 3, 1): Decimal("300.00")}
    assert sheet.current_month == date(2026, 3, 1)
    assert sheet.opening_balance == Decimal("2266.00")
    assert sheet.field_cost == Decimal("800.00")
    assert sheet.misc_cost is None


def test_parse_cobranca_avulsa():
    (coletes,) = parse_rows(ROWS).collections
    assert coletes.title == "Coletes novos"
    assert [(i.name, i.amount, i.paid) for i in coletes.items] == [
        ("PETER", Decimal("20.00"), False),
        ("DANIEL", Decimal("20.00"), True),
        ("PENETRA", None, False),
    ]
    assert coletes.amount_per_person == Decimal("20.00")


def test_sem_cabecalho():
    with pytest.raises(SheetFormatError):
        parse_rows([at(A="qualquer coisa")])


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("DANIEL", ("Daniel", None)),
        ("DG", ("DG", None)),
        ("FELIPE NOGUEIRA", ("Felipe Nogueira", None)),
        ("RODRIGO GOMES ZAG", ("Rodrigo Gomes", "ZAGUEIRO")),
        ("PATRICK AMIGO WAGNER", ("Patrick (amigo do Wagner)", None)),
        ("IGOR CUNHADO LEANDRO", ("Igor (cunhado do Leandro)", None)),
    ],
)
def test_clean_player_name(label, expected):
    assert clean_player_name(label) == expected


def test_normalize():
    assert normalize("  Moisés  ") == normalize("MOISES")
