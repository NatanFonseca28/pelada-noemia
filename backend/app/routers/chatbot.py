import hmac
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.deps import AdminUser, SessionDep, SuperAdminUser
from app.core.errors import NotFoundError
from app.db.session import SessionLocal
from app.services.chatbot_service import ChatbotService, kick

router = APIRouter(prefix="/chatbot", tags=["Chatbot de cobrança"])


class ChatbotStatus(BaseModel):
    enabled: bool
    state: str  # open | connecting | close | missing | offline | unconfigured
    daily_limit: int
    charges_today: int
    pending: int
    owner_user_id: int | None
    owner_name: str | None


class ConnectOut(ChatbotStatus):
    qr: str | None  # QR Code (data URI) para escanear no WhatsApp do admin; None = já conectado


class ChatbotSettingsIn(BaseModel):
    enabled: bool
    daily_limit: int = Field(ge=1, le=200)
    owner_user_id: int | None = None


class ChargeIn(BaseModel):
    force: bool = False  # cobrar mesmo se foi cobrado há menos de 3 dias


class Skipped(BaseModel):
    name: str
    reason: str


class ChargeResult(BaseModel):
    queued: list[str]
    skipped: list[Skipped]


class QueueItem(BaseModel):
    id: int
    player_id: int | None
    name: str
    status: str
    error: str | None
    created_at: datetime
    sent_at: datetime | None


class ReplyOut(BaseModel):
    id: int
    player_id: int
    name: str
    phone: str | None
    kind: str  # PAGO | FORA | FALAR
    months: list[str]
    amount: Decimal
    media_url: str | None
    has_document: bool
    note: str | None
    status: str
    created_at: datetime


@router.get("/status", response_model=ChatbotStatus)
async def status_(admin: AdminUser, session: SessionDep):
    return await ChatbotService(session).status()


@router.put("/settings", response_model=ChatbotStatus)
async def update_settings(data: ChatbotSettingsIn, admin: SuperAdminUser, session: SessionDep):
    service = ChatbotService(session)
    await service.update_settings(data.enabled, data.daily_limit, data.owner_user_id, admin)
    kick(SessionLocal)  # ao religar, envia o que ficou na fila
    return await service.status()


@router.post("/connect", response_model=ConnectOut)
async def connect(admin: SuperAdminUser, session: SessionDep):
    """Prepara a conexão e devolve o QR Code para o admin escanear em WhatsApp → Aparelhos conectados."""
    return await ChatbotService(session).connect(admin)


@router.post("/disconnect", response_model=ChatbotStatus)
async def disconnect(admin: SuperAdminUser, session: SessionDep):
    service = ChatbotService(session)
    await service.disconnect(admin)
    return await service.status()


@router.post("/charge-all", response_model=ChargeResult)
async def charge_all(admin: AdminUser, session: SessionDep):
    """Cobra todos de "Para cobrar" que aceitaram WhatsApp (respeita limite diário e intervalo de 3 dias)."""
    result = await ChatbotService(session).charge(admin)
    kick(SessionLocal)
    return result


@router.post("/charge/{player_id}", response_model=ChargeResult)
async def charge_one(player_id: int, data: ChargeIn, admin: AdminUser, session: SessionDep):
    result = await ChatbotService(session).charge(admin, [player_id], force=data.force)
    kick(SessionLocal)
    return result


@router.get("/queue", response_model=list[QueueItem])
async def queue(admin: AdminUser, session: SessionDep):
    return await ChatbotService(session).queue()


@router.get("/replies", response_model=list[ReplyOut])
async def replies(admin: AdminUser, session: SessionDep, status: str = "ABERTO"):
    return await ChatbotService(session).replies(status)


@router.post("/replies/{reply_id}/confirm", status_code=204)
async def confirm(reply_id: int, admin: AdminUser, session: SessionDep):
    await ChatbotService(session).resolve(reply_id, True, admin)
    kick(SessionLocal)


@router.post("/replies/{reply_id}/reject", status_code=204)
async def reject(reply_id: int, admin: AdminUser, session: SessionDep):
    await ChatbotService(session).resolve(reply_id, False, admin)


@router.post("/webhook/{secret}", include_in_schema=False)
async def webhook(secret: str, request: Request, session: SessionDep):
    """Eventos da Evolution API (mensagens recebidas). O segredo na URL autentica a chamada."""
    expected = get_settings().whatsapp_webhook_secret
    if not expected or not hmac.compare_digest(secret, expected):
        raise NotFoundError("Não encontrado")  # não revela que a rota existe
    payload = await request.json()
    result = await ChatbotService(session).handle_webhook(payload if isinstance(payload, dict) else {})
    kick(SessionLocal)
    return {"result": result}
