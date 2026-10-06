"""Importa a planilha financeira pela linha de comando.

Uso: python -m scripts.import_planilha "PELADA DE QUARTA CONTROLE.xlsx"
"""
import asyncio
import sys
from pathlib import Path

from app.db.session import SessionLocal
from app.services.finance_import_service import FinanceImportService, read_workbook


async def main(path: str) -> None:
    sheet = read_workbook(Path(path).read_bytes())
    async with SessionLocal() as session:
        result = await FinanceImportService(session).import_sheet(sheet, actor=None)
    print(f"Jogadores criados ({len(result.players_created)}): {', '.join(result.players_created) or '-'}")
    print(f"Jogadores já existentes ({len(result.players_matched)}): {', '.join(result.players_matched) or '-'}")
    print(f"Mensalidades: {result.fee_cells} · Lançamentos de caixa: {result.cash_entries} · "
          f"Cobranças: {result.collections}")
    print(f"Saldo de abertura: R$ {result.opening_balance} em {result.opening_month}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1]))
