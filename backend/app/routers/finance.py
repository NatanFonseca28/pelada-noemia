from datetime import date

from fastapi import APIRouter, File, Query, UploadFile, status

from app.core.deps import AdminUser, SessionDep
from app.core.errors import ValidationError
from app.schemas.finance import (
    CashEntryIn,
    CashEntryOut,
    CollectionIn,
    CollectionItemIn,
    CollectionItemUpdate,
    CollectionOut,
    DelinquentOut,
    FeeCellIn,
    FeeCellOut,
    FinanceConfig,
    FinanceOverview,
    ImportResult,
)
from app.services.finance_import_service import FinanceImportService, read_workbook
from app.services.finance_service import FinanceService

router = APIRouter(prefix="/finance", tags=["Financeiro (ADMIN)"])

MAX_SHEET_BYTES = 5 * 1024 * 1024


def _year(year: int | None) -> int:
    return year or date.today().year


@router.get("/overview", response_model=FinanceOverview)
async def overview(admin: AdminUser, session: SessionDep, year: int | None = Query(None, ge=2000, le=2100)):
    """Grade de mensalidades do ano, resumo mensal e saldo do caixa."""
    return await FinanceService(session).overview(_year(year))


@router.get("/delinquents", response_model=list[DelinquentOut])
async def delinquents(admin: AdminUser, session: SessionDep):
    """Inadimplentes (sem pagar o mês atual nem o anterior), com contato e valor devido.
    Ponto de encaixe da futura cobrança por WhatsApp — hoje só lista, nada é enviado."""
    return await FinanceService(session).delinquents()


@router.get("/config", response_model=FinanceConfig)
async def get_config(admin: AdminUser, session: SessionDep):
    return await FinanceService(session).get_config()


@router.put("/config", response_model=FinanceConfig)
async def update_config(data: FinanceConfig, admin: AdminUser, session: SessionDep):
    return await FinanceService(session).update_config(data, admin)


@router.put("/fees", response_model=FeeCellOut | None)
async def set_fee(data: FeeCellIn, admin: AdminUser, session: SessionDep):
    """Edita uma célula da grade. Valor e anotação vazios apagam a célula."""
    return await FinanceService(session).set_fee(data, admin)


@router.get("/entries", response_model=list[CashEntryOut])
async def list_entries(admin: AdminUser, session: SessionDep, year: int | None = Query(None, ge=2000, le=2100)):
    return await FinanceService(session).list_entries(_year(year))


@router.post("/entries", response_model=CashEntryOut, status_code=status.HTTP_201_CREATED)
async def create_entry(data: CashEntryIn, admin: AdminUser, session: SessionDep):
    return await FinanceService(session).create_entry(data, admin)


@router.put("/entries/{entry_id}", response_model=CashEntryOut)
async def update_entry(entry_id: int, data: CashEntryIn, admin: AdminUser, session: SessionDep):
    return await FinanceService(session).update_entry(entry_id, data, admin)


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(entry_id: int, admin: AdminUser, session: SessionDep):
    await FinanceService(session).delete_entry(entry_id, admin)


@router.get("/collections", response_model=list[CollectionOut])
async def list_collections(admin: AdminUser, session: SessionDep):
    return await FinanceService(session).list_collections()


@router.post("/collections", response_model=CollectionOut, status_code=status.HTTP_201_CREATED)
async def create_collection(data: CollectionIn, admin: AdminUser, session: SessionDep):
    return await FinanceService(session).create_collection(data, admin)


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(collection_id: int, admin: AdminUser, session: SessionDep):
    await FinanceService(session).delete_collection(collection_id, admin)


@router.post("/collections/{collection_id}/items", response_model=CollectionOut)
async def add_item(collection_id: int, data: CollectionItemIn, admin: AdminUser, session: SessionDep):
    return await FinanceService(session).add_item(collection_id, data, admin)


@router.patch("/collection-items/{item_id}", response_model=CollectionOut)
async def update_item(item_id: int, data: CollectionItemUpdate, admin: AdminUser, session: SessionDep):
    return await FinanceService(session).update_item(item_id, data, admin)


@router.delete("/collection-items/{item_id}", response_model=CollectionOut)
async def delete_item(item_id: int, admin: AdminUser, session: SessionDep):
    return await FinanceService(session).delete_item(item_id, admin)


@router.post("/import", response_model=ImportResult)
async def import_sheet(admin: AdminUser, session: SessionDep, file: UploadFile = File(...)):
    """Importa a planilha "PELADA DE QUARTA CONTROLE" (.xlsx). Pode ser repetido sem duplicar."""
    content = await file.read(MAX_SHEET_BYTES + 1)
    if len(content) > MAX_SHEET_BYTES:
        raise ValidationError("Planilha maior que 5 MB")
    return await FinanceImportService(session).import_sheet(read_workbook(content), admin)
