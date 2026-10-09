import hmac
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.deps import AdminUser, SessionDep, SuperAdminUser
from app.core.errors import ForbiddenError
from app.db.session import SessionLocal
from app.services.chatbot_service import ChatbotService, kick
from app.services.whatsapp_gateway import valid_signature

router = APIRouter(prefix="/chatbot", tags=["Chatbot de cobrança"])


class ChatbotStatus(BaseModel):
    enabled: bool
    state: str  # open (API oficial respondendo) | offline | unconfigured
    daily_limit: int
    charges_today: int
    pending: int
    owner_user_id: int | None
    owner_name: str | None
    # número da pelada, nome verificado, qualidade e status dos modelos na Meta (só com ?details=true)
    info: dict | None = None


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
async def status_(admin: AdminUser, session: SessionDep, details: bool = False):
    return await ChatbotService(session).status(with_info=details)


@router.put("/settings", response_model=ChatbotStatus)
async def update_settings(data: ChatbotSettingsIn, admin: SuperAdminUser, session: SessionDep):
    service = ChatbotService(session)
    await service.update_settings(data.enabled, data.daily_limit, data.owner_user_id, admin)
    kick(SessionLocal)  # ao religar, envia o que ficou na fila
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


@router.get("/webhook", include_in_schema=False)
async def webhook_verify(mode: str = Query(alias="hub.mode", default=""),
                         token: str = Query(alias="hub.verify_token", default=""),
                         challenge: str = Query(alias="hub.challenge", default="")):
    """Verificação do webhook no painel da Meta: devolve o desafio se o token conferir."""
    expected = get_settings().meta_verify_token
    if mode == "subscribe" and expected and hmac.compare_digest(token, expected):
        return PlainTextResponse(challenge)
    raise ForbiddenError("Token de verificação inválido")


@router.post("/webhook", include_in_schema=False)
async def webhook(request: Request, session: SessionDep):
    """Mensagens e status de entrega da Meta. A assinatura (App Secret) autentica a chamada."""
    secret = get_settings().meta_app_secret
    body = await request.body()
    if not secret or not valid_signature(body, request.headers.get("X-Hub-Signature-256"), secret):
        raise ForbiddenError("Assinatura inválida")
    payload = await request.json()
    results = await ChatbotService(session).handle_webhook(payload if isinstance(payload, dict) else {})
    kick(SessionLocal)
    return {"results": results}
