"""Exportação fiel do banco para auditoria: .xlsx (uma aba por tabela) ou .zip com um CSV por tabela.

Regras de fidelidade:
- Uma aba/arquivo por tabela, com o NOME REAL da tabela, as colunas reais na ordem do banco e nada inventado.
- Valores exatos: decimais sem arredondamento, datas/horas em UTC (como estão gravadas), JSON completo, códigos dos enums.
- Todas as tabelas são lidas no MESMO instante (transação REPEATABLE READ): os totais batem entre si.
- Cada tabela vai com contagem de registros e SHA-256 do CSV, para conferência posterior.
- Segredos nunca saem (hashes de senha e tokens de sessão). Auditoria e log de acessos: só para o superadmin.
"""
import base64
import csv
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any

from openpyxl import Workbook
from openpyxl.cell.cell import TYPE_STRING
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import LargeBinary, Table, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.models  # noqa: F401  (registra todas as tabelas no metadata)
from app.core.errors import ForbiddenError, ValidationError
from app.db.base import Base
from app.models.user import User
from app.services import audit_service

# Nunca exportar segredos
EXCLUDED_TABLES = {"refresh_tokens"}
EXCLUDED_COLUMNS = {"password_hash", "token_hash"}
# Registros de controle: só o superadmin exporta
SUPERADMIN_TABLES = {"audit_logs", "access_logs"}

EXCEL_CELL_LIMIT = 32_767

TABLE_LABELS = {
    "users": "Usuários",
    "players": "Jogadores",
    "settings": "Configurações",
    "audit_logs": "Auditoria",
    "access_logs": "Log de acessos",
    "media_files": "Fotos",
    "monthly_fees": "Mensalidades",
    "cash_entries": "Caixa",
    "finance_collections": "Cobranças avulsas",
    "collection_items": "Itens de cobrança",
    "rounds": "Rodadas",
    "attendances": "Presenças",
    "draws": "Sorteios",
    "teams": "Times",
    "team_players": "Jogadores nos times",
    "tournaments": "Campeonatos",
    "tournament_groups": "Grupos",
    "tournament_group_teams": "Times nos grupos",
    "matches": "Partidas",
    "match_events": "Súmula (eventos)",
}

HEADER_FILL = PatternFill("solid", fgColor="027A48")
HEADER_FONT = Font(bold=True, color="FFFFFF")


@dataclass
class TableDump:
    table: Table
    columns: list[str]
    rows: list[tuple]
    csv_bytes: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.csv_bytes).hexdigest()


def exportable_tables(user: User | None = None) -> list[Table]:
    tables = [t for t in Base.metadata.sorted_tables if t.name not in EXCLUDED_TABLES]
    if user is not None and not user.is_superadmin:
        tables = [t for t in tables if t.name not in SUPERADMIN_TABLES]
    return sorted(tables, key=lambda t: t.name)


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value


def csv_value(value: Any) -> str | None:
    """Texto exato do valor (None = NULL, que no CSV fica sem aspas; textos sempre entre aspas)."""
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (bytes, memoryview)):
        return base64.b64encode(bytes(value)).decode()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _xlsx_value(value: Any) -> Any:
    """Valor nativo para o Excel. Datas/horas em UTC sem fuso (o Excel não guarda fuso)."""
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return _utc(value).replace(tzinfo=None)
    if isinstance(value, (bytes, memoryview)):
        raw = bytes(value)
        return f"sha256:{hashlib.sha256(raw).hexdigest()} ({len(raw)} bytes)"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _number_format(column) -> str | None:
    kind = type(column.type).__name__
    if kind == "DateTime":
        return "yyyy-mm-dd hh:mm:ss"
    if kind == "Date":
        return "yyyy-mm-dd"
    if kind == "Time":
        return "hh:mm:ss"
    if kind == "Numeric":
        scale = getattr(column.type, "scale", None) or 2
        return "0." + "0" * scale
    return None


class ExportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _select_tables(self, table_names: list[str] | None, actor: User) -> list[Table]:
        tables = exportable_tables()
        known = {t.name for t in tables}
        if table_names:
            unknown = set(table_names) - known
            if unknown:
                raise ValidationError(f"Tabelas desconhecidas: {', '.join(sorted(unknown))}")
            tables = [t for t in tables if t.name in table_names]
        else:
            tables = exportable_tables(actor)
        if not actor.is_superadmin and any(t.name in SUPERADMIN_TABLES for t in tables):
            raise ForbiddenError("Auditoria e log de acessos só podem ser exportados pelo superadmin")
        return tables

    async def _dump(self, tables: list[Table]) -> tuple[list[TableDump], datetime]:
        """Lê todas as tabelas numa única transação REPEATABLE READ (fotografia consistente do banco)."""
        dumps: list[TableDump] = []
        async with self.session.bind.connect() as conn:
            await conn.execution_options(isolation_level="REPEATABLE READ")
            async with conn.begin():
                snapshot_at = (await conn.execute(select(func.now()))).scalar_one()
                for table in tables:
                    cols = [c for c in table.columns if c.name not in EXCLUDED_COLUMNS]
                    order = list(table.primary_key.columns) or cols
                    rows = [tuple(r) for r in (await conn.execute(select(*cols).order_by(*order))).all()]
                    buf = io.StringIO(newline="")
                    writer = csv.writer(buf, quoting=csv.QUOTE_NOTNULL, lineterminator="\r\n")
                    writer.writerow([c.name for c in cols])
                    for row in rows:
                        writer.writerow([csv_value(v) for v in row])
                    dumps.append(TableDump(table, [c.name for c in cols], rows, buf.getvalue().encode("utf-8")))
        return dumps, snapshot_at

    async def _record(self, actor: User, fmt: str, dumps: list[TableDump], snapshot_at: datetime) -> None:
        await audit_service.record(
            self.session, user_id=actor.id, action="EXPORT", entity="export",
            after={"format": fmt, "snapshot_at": _utc(snapshot_at).isoformat(),
                   "tables": {d.table.name: {"rows": len(d.rows), "sha256": d.sha256} for d in dumps}},
        )
        await self.session.commit()

    async def export_xlsx(self, table_names: list[str] | None, actor: User) -> bytes:
        dumps, snapshot_at = await self._dump(self._select_tables(table_names, actor))
        wb = Workbook()
        about = wb.active
        about.title = "_sobre"
        truncated: dict[str, int] = {}

        for d in dumps:
            ws = wb.create_sheet(d.table.name)
            ws.append(d.columns)
            for c in ws[1]:
                c.font, c.fill = HEADER_FONT, HEADER_FILL
            columns = [d.table.c[name] for name in d.columns]
            for r, row in enumerate(d.rows, start=2):
                for i, value in enumerate(row, start=1):
                    v = _xlsx_value(value)
                    if isinstance(v, str) and len(v) > EXCEL_CELL_LIMIT:
                        v = v[:EXCEL_CELL_LIMIT]
                        truncated[d.table.name] = truncated.get(d.table.name, 0) + 1
                    cell = ws.cell(r, i, v)
                    if isinstance(v, str):
                        cell.data_type = TYPE_STRING  # texto que começa com "=" não vira fórmula
            for i, col in enumerate(columns, start=1):
                letter = get_column_letter(i)
                sample = [len(str(ws.cell(r, i).value or "")) for r in range(1, min(ws.max_row, 200) + 1)]
                ws.column_dimensions[letter].width = min(max(sample) + 2, 50)
                fmt = _number_format(col)
                if fmt and not isinstance(col.type, LargeBinary):
                    for (cell,) in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                        cell.number_format = fmt
            ws.freeze_panes = "A2"
            if d.rows:
                ws.auto_filter.ref = ws.dimensions

        _write_about(about, dumps, snapshot_at, actor, truncated)
        await self._record(actor, "xlsx", dumps, snapshot_at)
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    async def export_csv_zip(self, table_names: list[str] | None, actor: User) -> bytes:
        dumps, snapshot_at = await self._dump(self._select_tables(table_names, actor))
        manifest = {
            "sistema": "Pelada de Quarta",
            "fotografia_do_banco_em": _utc(snapshot_at).isoformat(),
            "exportado_por": {"id": actor.id, "nome": actor.name, "email": actor.email},
            "formato": "CSV UTF-8, separador vírgula, textos entre aspas, NULL = campo vazio sem aspas, "
                       "datas/horas ISO 8601 em UTC, binários em base64",
            "omitido": {"tabelas": sorted(EXCLUDED_TABLES), "colunas": sorted(EXCLUDED_COLUMNS)},
            "tabelas": [
                {"tabela": d.table.name, "descricao": TABLE_LABELS.get(d.table.name, d.table.name),
                 "arquivo": f"{d.table.name}.csv", "registros": len(d.rows), "colunas": d.columns,
                 "sha256": d.sha256}
                for d in dumps
            ],
        }
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for d in dumps:
                zf.writestr(f"{d.table.name}.csv", d.csv_bytes)
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            zf.writestr("SHA256SUMS", "".join(f"{d.sha256}  {d.table.name}.csv\n" for d in dumps))
        await self._record(actor, "csv", dumps, snapshot_at)
        return buf.getvalue()


def _write_about(ws, dumps: list[TableDump], snapshot_at: datetime, actor: User, truncated: dict[str, int]) -> None:
    ws.append(["Pelada de Quarta — exportação fiel do banco de dados"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append(["Fotografia do banco em (UTC)", _utc(snapshot_at).replace(tzinfo=None)])
    ws["B2"].number_format = "yyyy-mm-dd hh:mm:ss"
    ws.append(["Exportado por", f"{actor.name} <{actor.email}>"])
    ws.append(["Datas e horas", "Em UTC, como gravadas no banco (horário de Brasília = UTC − 3)"])
    ws.append(["Fotos (media_files.content)", "Representadas por SHA-256 e tamanho; o conteúdo vai no export CSV"])
    ws.append(["Omitido por segurança", "tabela refresh_tokens; colunas password_hash e token_hash"])
    ws.append(["SHA-256", "Hash do CSV da tabela (igual ao do export CSV da mesma fotografia)"])
    ws.append([])
    header_row = ws.max_row + 1
    ws.append(["Aba / tabela", "Descrição", "Registros", "Colunas", "SHA-256 do CSV", "Células truncadas (>32.767)"])
    for c in ws[header_row]:
        c.font, c.fill = HEADER_FONT, HEADER_FILL
    for d in dumps:
        ws.append([d.table.name, TABLE_LABELS.get(d.table.name, d.table.name), len(d.rows), len(d.columns),
                   d.sha256, truncated.get(d.table.name, 0)])
    for letter, width in zip("ABCDEF", (30, 60, 10, 9, 66, 24), strict=True):
        ws.column_dimensions[letter].width = width
