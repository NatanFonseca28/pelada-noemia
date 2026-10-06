from datetime import datetime

from fastapi import APIRouter, Query, Response

from app.core.deps import AdminUser, SessionDep
from app.services.export_service import TABLE_LABELS, ExportService, exportable_tables

router = APIRouter(prefix="/export", tags=["Exportação (ADMIN)"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ZIP = "application/zip"


def _download(content: bytes, media_type: str, ext: str) -> Response:
    filename = f"pelada-export-{datetime.now():%Y-%m-%d-%H%M}.{ext}"
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/tables")
async def list_tables(admin: AdminUser) -> list[dict]:
    """Tabelas que este usuário pode exportar (segredos nunca; auditoria e acessos só o superadmin)."""
    return [{"name": t.name, "label": TABLE_LABELS.get(t.name, t.name)} for t in exportable_tables(admin)]


@router.get("/xlsx", response_class=Response, responses={200: {"content": {XLSX: {}}}})
async def export_xlsx(admin: AdminUser, session: SessionDep, tables: list[str] | None = Query(None)):
    """Planilha com uma aba por tabela (nome e colunas reais) e a aba `_sobre` com contagens e SHA-256."""
    return _download(await ExportService(session).export_xlsx(tables, admin), XLSX, "xlsx")


@router.get("/csv", response_class=Response, responses={200: {"content": {ZIP: {}}}})
async def export_csv(admin: AdminUser, session: SessionDep, tables: list[str] | None = Query(None)):
    """ZIP com um CSV por tabela (valores exatos, sem conversões), manifest.json e SHA256SUMS."""
    return _download(await ExportService(session).export_csv_zip(tables, admin), ZIP, "zip")
