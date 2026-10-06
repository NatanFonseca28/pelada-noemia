"""Leitura da planilha "PELADA DE QUARTA CONTROLE" (sem banco, testável).

Layout esperado (o mesmo da planilha atual):
- Uma linha de cabeçalho com "NOME" na coluna A e os meses (datas) nas colunas seguintes.
- Abaixo dela, uma linha por jogador com o valor pago em cada mês (número) ou uma
  anotação de texto (ex.: "F"). O mesmo nome pode aparecer em mais de uma linha.
- Uma linha "DIARISTA, COLETE" com a arrecadação avulsa do mês e uma linha "TOTAL".
- Um bloco de resumo na coluna N com o valor na coluna Q: "SALDO MÊS ANTERIOR",
  "VALOR CAMPO", "DIVERSOS, CHURRASCO, BOLA, COLETE".
- Uma cobrança avulsa (ex.: "COLETES NOVOS") na coluna N, com "PG" na coluna P;
  abaixo dela, nome (N), valor (O) e "OK" (P) para quem já pagou.
"""
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

COL_NAME, COL_SUMMARY_LABEL, COL_COLLECTION_AMOUNT, COL_COLLECTION_STATUS, COL_SUMMARY_VALUE = 0, 13, 14, 15, 16


class SheetFormatError(ValueError):
    pass


@dataclass
class FeeCell:
    amount: Decimal | None = None
    marker: str | None = None


@dataclass
class CollectionRow:
    name: str
    amount: Decimal | None
    paid: bool


@dataclass
class ParsedCollection:
    title: str
    items: list[CollectionRow] = field(default_factory=list)

    @property
    def amount_per_person(self) -> Decimal:
        amounts = [i.amount for i in self.items if i.amount is not None]
        return Counter(amounts).most_common(1)[0][0] if amounts else Decimal("0")


@dataclass
class ParsedSheet:
    months: list[date]
    # rótulo original → mês → célula (linhas repetidas do mesmo nome são somadas)
    fees: dict[str, dict[date, FeeCell]]
    extra_income: dict[date, Decimal]
    current_month: date | None
    opening_balance: Decimal | None
    field_cost: Decimal | None
    misc_cost: Decimal | None
    collections: list[ParsedCollection]


def normalize(text: str) -> str:
    """Comparação de nomes sem acento, caixa e espaços extras."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip().casefold()


def clean_player_name(label: str) -> tuple[str, str | None]:
    """'RODRIGO GOMES ZAG' → ('Rodrigo Gomes', 'ZAGUEIRO');
    'PATRICK AMIGO WAGNER' → ('Patrick (amigo do Wagner)', None)."""
    words = label.split()
    position = None
    if words and words[-1].upper() in {"ZAG", "ZAGUEIRO"}:
        position, words = "ZAGUEIRO", words[:-1]
    elif words and words[-1].upper() in {"GOL", "GOLEIRO"}:
        position, words = "GOLEIRO_FIXO", words[:-1]

    def title(ws: list[str]) -> str:
        return " ".join(w.upper() if len(w) <= 2 else w.capitalize() for w in ws)

    upper = [w.upper() for w in words]
    for relation in ("AMIGO", "CUNHADO", "IRMAO", "IRMÃO", "PRIMO", "FILHO", "PAI", "TIO"):
        if relation in upper[1:]:
            i = upper.index(relation, 1)
            rel = relation.lower().replace("irmao", "irmão")
            return f"{title(words[:i])} ({rel} do {title(words[i + 1:])})".replace(" do )", ")"), position
    return title(words), position


def _to_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    return None


def _month(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date().replace(day=1)
    if isinstance(value, date):
        return value.replace(day=1)
    return None


def _cell(row: tuple, idx: int) -> Any:
    return row[idx] if idx < len(row) else None


def _label(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def parse_rows(rows: list[tuple]) -> ParsedSheet:
    header_idx = next((i for i, r in enumerate(rows) if normalize(_label(_cell(r, COL_NAME))) == "nome"), None)
    if header_idx is None:
        raise SheetFormatError('Cabeçalho com "NOME" na coluna A não encontrado')

    header = rows[header_idx]
    month_cols = {c: m for c in range(1, len(header)) if (m := _month(header[c])) is not None}
    if not month_cols:
        raise SheetFormatError("Nenhum mês encontrado no cabeçalho")

    fees: dict[str, dict[date, FeeCell]] = {}
    extra_income: dict[date, Decimal] = {}
    totals: dict[date, Decimal] = {}
    by_norm: dict[str, str] = {}

    for row in rows[header_idx + 1:]:
        label = _label(_cell(row, COL_NAME))
        if not label:
            continue
        norm = normalize(label)
        if norm == "total":
            for c, m in month_cols.items():
                if (v := _to_decimal(_cell(row, c))) is not None:
                    totals[m] = v
            break
        if "diarista" in norm:
            for c, m in month_cols.items():
                if (v := _to_decimal(_cell(row, c))) is not None and v != 0:
                    extra_income[m] = extra_income.get(m, Decimal("0")) + v
            continue

        key = by_norm.setdefault(norm, label)
        cells = fees.setdefault(key, {})
        for c, m in month_cols.items():
            raw = _cell(row, c)
            amount = _to_decimal(raw)
            marker = _label(raw) if amount is None and raw is not None and _label(raw) else None
            if amount is None and marker is None:
                continue
            cell = cells.setdefault(m, FeeCell())
            if amount is not None:
                cell.amount = (cell.amount or Decimal("0")) + amount
            if marker is not None:
                cell.marker = marker if not cell.marker else f"{cell.marker}/{marker}"

    # Mês corrente = último mês com arrecadação
    computed = dict(totals)
    if not computed:
        for cells in fees.values():
            for m, cell in cells.items():
                computed[m] = computed.get(m, Decimal("0")) + (cell.amount or 0)
        for m, v in extra_income.items():
            computed[m] = computed.get(m, Decimal("0")) + v
    current_month = max((m for m, v in computed.items() if v), default=None)

    opening_balance = field_cost = misc_cost = None
    collections: list[ParsedCollection] = []
    current: ParsedCollection | None = None
    blank_streak = 0
    for row in rows:
        label = _label(_cell(row, COL_SUMMARY_LABEL))
        norm = normalize(label)
        value = _to_decimal(_cell(row, COL_SUMMARY_VALUE))
        status = normalize(_label(_cell(row, COL_COLLECTION_STATUS)))

        if current is not None:
            if not label:
                # Tolera uma linha em branco no meio da lista; duas encerram a cobrança
                blank_streak += 1
                if blank_streak >= 2:
                    current = None
                continue
            blank_streak = 0
            current.items.append(
                CollectionRow(
                    name=label,
                    amount=_to_decimal(_cell(row, COL_COLLECTION_AMOUNT)),
                    paid=status in {"ok", "pg", "pago", "sim", "x"},
                )
            )
            continue
        if not label:
            continue
        if status == "pg":
            current, blank_streak = ParsedCollection(title=label.capitalize()), 0
            collections.append(current)
        elif norm.startswith("saldo mes anterior"):
            opening_balance = value
        elif norm.startswith("valor campo"):
            field_cost = abs(value) if value else None
        elif norm.startswith("diversos"):
            misc_cost = abs(value) if value else None

    return ParsedSheet(
        months=sorted(month_cols.values()),
        fees=fees,
        extra_income=extra_income,
        current_month=current_month,
        opening_balance=opening_balance,
        field_cost=field_cost,
        misc_cost=misc_cost,
        collections=collections,
    )
