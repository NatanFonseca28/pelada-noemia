from datetime import datetime

from fastapi import APIRouter, Query, Response

from app.core.deps import AdminUser, SessionDep
from app.services.export_service import TABLE_LABELS, ExportService, exportable_tables

router = APIRouter(prefix="/export", tags=["Exportação (ADMIN)"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/tables")
async def list_tables(admin: AdminUser) -> list[dict]:
    """Tabelas disponíveis para exportação (segredos como senhas e tokens ficam de fora)."""
    return [{"name": t.name, "label": TABLE_LABELS.get(t.name, t.name)} for t in exportable_tables()]


@router.get("/xlsx", response_class=Response, responses={200: {"content": {XLSX: {}}}})
async def export_xlsx(admin: AdminUser, session: SessionDep, tables: list[str] | None = Query(None)):
    """Baixa um .xlsx com uma aba por tabela. Sem `tables`, exporta todas."""
    content = await ExportService(session).export_xlsx(tables, admin)
    filename = f"pelada-export-{datetime.now():%Y-%m-%d-%H%M}.xlsx"
    return Response(content, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
