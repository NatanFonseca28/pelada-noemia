"""Chatbot de cobrança pelo WhatsApp de um admin (via Evolution API).

Fluxo: o admin dispara ("Cobrar todos" ou "Cobrar") → mensagens entram na fila → a tarefa de envio manda uma por
vez, com intervalo aleatório entre cobranças (anti-bloqueio) → o jogador responde pelo menu → o bot responde na
hora (Pix) ou cria um pedido para o admin (pagamento a conferir, "F", falar com o gestor).
"""
import asyncio
import base64
import binascii
import logging
import random
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.domain import chatbot as bot
from app.domain.charge_message import DEFAULT_CHARGE_MESSAGE
from app.domain.delinquency import OUT_MARKER, reference_months
from app.domain.pix import pix_copy_paste
from app.models.chatbot import ChargeConversation, ChargeReply, WhatsAppOutbox
from app.models.finance import MonthlyFee
from app.models.player import Player
from app.models.user import User
from app.repositories.settings_repo import SettingsRepository
from app.schemas.finance import FeeCellIn
from app.services import audit_service
from app.services.finance_service import FinanceService, today_local
from app.services.storage import save_photo
from app.services.whatsapp_gateway import GatewayError, WhatsAppGateway, get_gateway

log = logging.getLogger(__name__)

PIX_CITY = "RIO DE JANEIRO"
WORKER_LOCK = 734_221  # pg_advisory_lock: só um processo envia a fila
_next_charge_at: datetime | None = None  # próxima cobrança só depois do intervalo aleatório


def _now() -> datetime:
    return datetime.now(UTC)


class ChatbotService:
    def __init__(self, session: AsyncSession, gateway: WhatsAppGateway | None = None,
                 clock: Callable[[], datetime] = _now):
        self.session = session
        self.gateway = gateway if gateway is not None else get_gateway()
        self.clock = clock

    # ---------------------------------------------------------- configuração e status
    async def _settings(self):
        return await SettingsRepository(self.session).get_current()

    async def owner(self) -> User | None:
        s = await self._settings()
        return await self.session.get(User, s.chatbot_owner_user_id) if s.chatbot_owner_user_id else None

    async def gestor(self) -> str:
        owner = await self.owner()
        return owner.name.split()[0] if owner else "gestor"

    async def status(self) -> dict:
        s = await self._settings()
        state = "unconfigured"
        if self.gateway is not None:
            try:
                state = await self.gateway.state()
            except GatewayError:
                state = "offline"
        start = datetime.combine(today_local(), datetime.min.time(), tzinfo=UTC) - timedelta(hours=3)
        sent_today = await self.session.scalar(select(func.count()).select_from(WhatsAppOutbox).where(
            WhatsAppOutbox.kind == "COBRANCA", WhatsAppOutbox.created_at >= start)) or 0
        pending = await self.session.scalar(select(func.count()).select_from(WhatsAppOutbox).where(
            WhatsAppOutbox.status == "PENDENTE")) or 0
        owner = await self.owner()
        return {"enabled": s.chatbot_enabled, "state": state, "daily_limit": s.chatbot_daily_limit,
                "charges_today": sent_today, "pending": pending,
                "owner_user_id": owner.id if owner else None, "owner_name": owner.name if owner else None}

    async def update_settings(self, enabled: bool, daily_limit: int, owner_user_id: int | None, actor: User) -> None:
        s = await self._settings()
        if owner_user_id is not None and await self.session.get(User, owner_user_id) is None:
            raise NotFoundError("Administrador não encontrado")
        before = {"enabled": s.chatbot_enabled, "daily_limit": s.chatbot_daily_limit,
                  "owner": s.chatbot_owner_user_id}
        s.chatbot_enabled, s.chatbot_daily_limit, s.chatbot_owner_user_id = enabled, daily_limit, owner_user_id
        await audit_service.record(self.session, user_id=actor.id, action="UPDATE", entity="chatbot", entity_id=1,
                                   before=before, after={"enabled": enabled, "daily_limit": daily_limit,
                                                         "owner": owner_user_id})
        await self.session.commit()

    async def connect(self, actor: User) -> dict:
        cfg = get_settings()
        if self.gateway is None or not cfg.whatsapp_webhook_secret or not cfg.chatbot_webhook_base:
            raise ValidationError("Chatbot não configurado no servidor (Evolution API e webhook).")
        url = f"{cfg.chatbot_webhook_base.rstrip('/')}/chatbot/webhook/{cfg.whatsapp_webhook_secret}"
        try:
            qr = await self.gateway.connect(url)
        except GatewayError as exc:
            raise ValidationError(f"Não foi possível falar com a Evolution API: {exc}") from exc
        s = await self._settings()
        if s.chatbot_owner_user_id is None:
            s.chatbot_owner_user_id = actor.id  # quem escaneia o QR é o dono do número
        await audit_service.record(self.session, user_id=actor.id, action="CONNECT", entity="chatbot", entity_id=1)
        await self.session.commit()
        return {"qr": qr, **(await self.status())}

    async def disconnect(self, actor: User) -> None:
        if self.gateway is not None:
            try:
                await self.gateway.logout()
            except GatewayError as exc:
                raise ValidationError(str(exc)) from exc
        await audit_service.record(self.session, user_id=actor.id, action="DISCONNECT", entity="chatbot",
                                   entity_id=1)
        await self.session.commit()

    # ---------------------------------------------------------- disparo
    async def charge(self, actor: User, player_ids: list[int] | None = None, force: bool = False) -> dict:
        """Enfileira cobranças. Sem `player_ids`: todos de "Para cobrar" que aceitaram WhatsApp."""
        s = await self._settings()
        if not s.chatbot_enabled:
            raise ValidationError("O chatbot está desligado. O superadmin liga em Configurações.")
        if self.gateway is None:
            raise ValidationError("Chatbot não configurado no servidor.")
        finance = FinanceService(self.session)
        config = await finance.get_config()
        owing = {d.player_id: d for d in await finance.delinquents(include_partial=True)}
        targets = player_ids if player_ids is not None else list(owing)
        now = self.clock()
        start_of_day = now - timedelta(hours=24)
        used = await self.session.scalar(select(func.count()).select_from(WhatsAppOutbox).where(
            WhatsAppOutbox.kind == "COBRANCA", WhatsAppOutbox.created_at >= start_of_day)) or 0
        template = s.charge_message or DEFAULT_CHARGE_MESSAGE
        gestor = await self.gestor()
        queued: list[str] = []
        skipped: list[dict] = []
        for pid in targets:
            d = owing.get(pid)
            if d is None:
                if player_ids is not None:
                    raise ValidationError("Este jogador está com as mensalidades em dia")
                continue
            reason = None
            conv = await self.session.get(ChargeConversation, pid)
            if not d.phone:
                reason = "sem telefone"
            elif not d.whatsapp_opt_in:
                reason = "não aceitou WhatsApp"
            elif not force and conv and conv.last_charge_at and \
                    now - conv.last_charge_at < timedelta(days=bot.CHARGE_COOLDOWN_DAYS):
                reason = "cobrado há menos de 3 dias"
            elif used + len(queued) >= s.chatbot_daily_limit:
                reason = "limite diário atingido"
            if reason:
                if player_ids is not None and len(player_ids) == 1:
                    raise ConflictError(f"{d.name}: {reason}.")
                skipped.append({"name": d.name, "reason": reason})
                continue
            values = bot.charge_values(d.name, d.months_due, d.amount_due, config.monthly_fee, s.pix_key, gestor)
            self._enqueue(pid, d.phone, bot.render(template, values), "COBRANCA", actor.id)
            self._enqueue(pid, d.phone, bot.menu_text(gestor), "MENU", actor.id)
            if conv is None:
                conv = ChargeConversation(player_id=pid)
                self.session.add(conv)
            conv.months = [m.isoformat() for m in d.months_due]
            conv.amount = d.amount_due
            conv.last_charge_at = now
            conv.last_menu_at = now
            conv.awaiting_proof = False
            await audit_service.record(self.session, user_id=actor.id, action="CHARGE", entity="charge",
                                       entity_id=pid, after={"months": conv.months, "amount": str(d.amount_due),
                                                             "via": "chatbot"})
            queued.append(d.name)
        await self.session.commit()
        return {"queued": queued, "skipped": skipped}

    def _enqueue(self, player_id: int | None, phone: str, text_: str, kind: str, actor_id: int | None = None) -> None:
        self.session.add(WhatsAppOutbox(player_id=player_id, phone=phone, text=text_, kind=kind,
                                        created_by=actor_id))

    async def queue(self) -> list[dict]:
        rows = (await self.session.execute(
            select(WhatsAppOutbox, Player.nickname, Player.name)
            .outerjoin(Player, Player.id == WhatsAppOutbox.player_id)
            .where(WhatsAppOutbox.kind == "COBRANCA")
            .order_by(WhatsAppOutbox.id.desc()).limit(60)
        )).all()
        return [{"id": o.id, "player_id": o.player_id, "name": nick or name or o.phone, "status": o.status,
                 "error": o.error, "created_at": o.created_at, "sent_at": o.sent_at} for o, nick, name in rows]

    # ---------------------------------------------------------- envio (tarefa de fundo)
    async def process_outbox(self, max_items: int = 1) -> int:
        """Envia até `max_items` mensagens elegíveis. Cobranças respeitam o intervalo aleatório entre si."""
        global _next_charge_at
        if self.gateway is None or not (await self._settings()).chatbot_enabled:
            return 0
        sent = 0
        for _ in range(max_items):
            item = await self.session.scalar(
                select(WhatsAppOutbox).where(WhatsAppOutbox.status == "PENDENTE").order_by(WhatsAppOutbox.id).limit(1)
            )
            if item is None:
                break
            now = self.clock()
            if item.kind == "COBRANCA" and _next_charge_at and now < _next_charge_at:
                break
            try:
                await self.gateway.send_text(_digits(item.phone), item.text,
                                             typing_ms=random.randint(1200, 3500))
                item.status, item.sent_at, item.error = "ENVIADA", now, None
                if item.kind == "COBRANCA":
                    _next_charge_at = now + timedelta(seconds=random.randint(bot.MIN_GAP_SECONDS,
                                                                             bot.MAX_GAP_SECONDS))
                sent += 1
            except GatewayError as exc:
                item.attempts += 1
                item.error = str(exc)[:300]
                if item.attempts >= 6:  # ~2 min tentando: cobre o serviço acordando no plano grátis
                    item.status = "ERRO"
                await self.session.commit()
                break  # provavelmente desconectado: tenta de novo no próximo ciclo
            await self.session.commit()
        return sent

    # ---------------------------------------------------------- respostas (webhook)
    async def handle_webhook(self, payload: dict) -> str:
        if payload.get("event") not in ("messages.upsert", "MESSAGES_UPSERT"):
            return "ignorado"
        data = payload.get("data") or {}
        if isinstance(data, list):
            data = data[0] if data else {}
        key = data.get("key") or {}
        if key.get("fromMe"):
            return "ignorado"  # mensagens do próprio admin
        digits = bot.jid_digits(key.get("remoteJid")) or bot.jid_digits(key.get("remoteJidAlt")) \
            or bot.jid_digits(key.get("senderPn"))
        if not digits:
            return "ignorado"
        player = await self._player_by_digits(digits)
        if player is None:
            return "ignorado"
        conv = await self.session.get(ChargeConversation, player.id)
        if conv is None or not conv.last_charge_at or self.clock() - conv.last_charge_at > timedelta(days=30):
            return "ignorado"  # não está numa cobrança: é conversa normal do admin
        message_id = key.get("id")
        if message_id and conv.last_message_id == message_id:
            return "repetido"
        # ao acordar (plano grátis), o WhatsApp reentrega mensagens antigas: só processa as mais novas
        ts = _timestamp(data.get("messageTimestamp"))
        if ts is not None:
            if conv.last_inbound_ts and ts < conv.last_inbound_ts:
                return "repetido"
            if conv.last_charge_at and ts < int(conv.last_charge_at.timestamp()) - 60:
                return "ignorado"  # anterior à cobrança atual
            conv.last_inbound_ts = ts
        conv.last_message_id = message_id

        msg = data.get("message") or {}
        text_ = (msg.get("conversation") or (msg.get("extendedTextMessage") or {}).get("text")
                 or (msg.get("imageMessage") or {}).get("caption") or (msg.get("documentMessage") or {}).get("caption"))
        image_b64 = msg.get("base64") if "imageMessage" in msg else None
        is_document = "documentMessage" in msg or "documentWithCaptionMessage" in msg
        intent = bot.parse_reply(text_, has_media=bool(image_b64) or is_document)
        gestor = await self.gestor()
        phone = player.phone

        if intent == bot.Intent.PIX:
            await self._send_pix(player, conv, gestor)
        elif intent in (bot.Intent.PAID, bot.Intent.PROOF):
            reply = await self._open_reply(player.id, "PAGO", conv, note=text_)
            if intent == bot.Intent.PROOF:
                if image_b64:
                    reply.media_path = self._store_proof(image_b64) or reply.media_path
                reply.has_document = reply.has_document or is_document
                conv.awaiting_proof = False
                self._enqueue(player.id, phone, f"Valeu! O {gestor} vai conferir e dar baixa. ✅", "RESPOSTA")
            else:
                conv.awaiting_proof = True
                self._enqueue(player.id, phone, f"Beleza! Manda o comprovante aqui (foto ou PDF) que eu passo "
                                                f"pro {gestor} conferir.", "RESPOSTA")
        elif intent == bot.Intent.OUT:
            month = today_local().replace(day=1)
            await self._open_reply(player.id, "FORA", conv, note=text_, months=[month.isoformat()])
            self._enqueue(player.id, phone, f"Anotado! O {gestor} vai confirmar que você fica fora em "
                                            f"{bot.months_text([month])}.", "RESPOSTA")
        elif intent == bot.Intent.TALK:
            await self._open_reply(player.id, "FALAR", conv, note=text_)
            self._enqueue(player.id, phone, f"Beleza, avisei o {gestor}. Ele te chama por aqui.", "RESPOSTA")
        else:
            now = self.clock()
            if not conv.last_menu_at or now - conv.last_menu_at > timedelta(hours=bot.MENU_RESEND_HOURS):
                conv.last_menu_at = now
                self._enqueue(player.id, phone, bot.menu_text(gestor), "MENU")
        await self.session.commit()
        return intent.value

    async def _send_pix(self, player: Player, conv: ChargeConversation, gestor: str) -> None:
        s = await self._settings()
        if not s.pix_key:
            self._enqueue(player.id, player.phone, f"O {gestor} ainda não cadastrou a chave Pix. Ele vai te passar.",
                          "RESPOSTA")
            return
        months = [date.fromisoformat(m) for m in conv.months]
        owner = await self.owner()
        code = pix_copy_paste(s.pix_key, conv.amount or None, owner.name if owner else "PELADA", PIX_CITY,
                              message=f"Mensalidade {bot.months_text(months)}" if months else None)
        self._enqueue(player.id, player.phone,
                      f"Segue o Pix de {bot.money(conv.amount)} ({bot.months_text(months)}). "
                      f"É só copiar a próxima mensagem 👇\nChave: {s.pix_key}", "RESPOSTA")
        self._enqueue(player.id, player.phone, code, "RESPOSTA")

    async def _open_reply(self, player_id: int, kind: str, conv: ChargeConversation, note: str | None,
                          months: list[str] | None = None) -> ChargeReply:
        reply = await self.session.scalar(select(ChargeReply).where(
            ChargeReply.player_id == player_id, ChargeReply.kind == kind, ChargeReply.status == "ABERTO"))
        if reply is None:
            reply = ChargeReply(player_id=player_id, kind=kind, months=months or list(conv.months),
                                amount=conv.amount if kind == "PAGO" else Decimal("0"))
            self.session.add(reply)
            await self.session.flush()
        if note:
            reply.note = note[:500]
        return reply

    def _store_proof(self, image_b64: str) -> str | None:
        try:
            content = base64.b64decode(image_b64.split(",", 1)[-1], validate=False)
            return save_photo(self.session, content, folder="comprovantes")
        except (binascii.Error, ValidationError):
            log.warning("Comprovante inválido recebido pelo chatbot")
            return None

    async def _player_by_digits(self, digits: str) -> Player | None:
        players = list(await self.session.scalars(select(Player).where(Player.phone.is_not(None))))
        return next((p for p in players if digits in bot.phone_variants(p.phone)), None)

    # ---------------------------------------------------------- pedidos para o admin
    async def replies(self, status: str = "ABERTO") -> list[dict]:
        rows = (await self.session.execute(
            select(ChargeReply, Player).join(Player, Player.id == ChargeReply.player_id)
            .where(ChargeReply.status == status).order_by(ChargeReply.created_at.desc()).limit(100)
        )).all()
        return [{"id": r.id, "player_id": p.id, "name": p.display_name, "phone": p.phone, "kind": r.kind,
                 "months": r.months, "amount": r.amount, "media_url": r.media_url, "has_document": r.has_document,
                 "note": r.note, "status": r.status, "created_at": r.created_at} for r, p in rows]

    async def resolve(self, reply_id: int, approve: bool, actor: User) -> None:
        reply = await self.session.get(ChargeReply, reply_id)
        if reply is None:
            raise NotFoundError("Pedido não encontrado")
        if reply.status != "ABERTO":
            raise ConflictError("Este pedido já foi resolvido")
        player = await self.session.get(Player, reply.player_id)
        finance = FinanceService(self.session)
        months = [date.fromisoformat(m) for m in reply.months]
        if approve and reply.kind == "PAGO":
            fee = (await finance.get_config()).monthly_fee
            for m in months:
                await finance.set_fee(FeeCellIn(player_id=reply.player_id, month=m, amount=fee), actor)
            if player and player.phone and player.whatsapp_opt_in:
                self._enqueue(player.id, player.phone,
                              f"Pagamento confirmado ✅ ({bot.months_text(months)}). Valeu!", "RESPOSTA", actor.id)
        elif approve and reply.kind == "FORA":
            for m in months:
                cell = await self.session.scalar(select(MonthlyFee).where(
                    MonthlyFee.player_id == reply.player_id, MonthlyFee.month == m))
                if cell is None or cell.amount is None:  # não apaga pagamento já lançado
                    await finance.set_fee(FeeCellIn(player_id=reply.player_id, month=m, marker=OUT_MARKER), actor)
            if player and player.phone and player.whatsapp_opt_in:
                self._enqueue(player.id, player.phone,
                              f"Confirmado: você fica fora em {bot.months_text(months)}. 👍", "RESPOSTA", actor.id)
        reply.status = "CONFIRMADO" if approve else "RECUSADO"
        reply.resolved_by, reply.resolved_at = actor.id, self.clock()
        await audit_service.record(self.session, user_id=actor.id, action="RESOLVE", entity="charge_reply",
                                   entity_id=reply.id, after={"kind": reply.kind, "status": reply.status})
        await self.session.commit()


def _timestamp(value) -> int | None:
    """messageTimestamp da Evolution: número, texto ou {"low": n} (Long do protobuf)."""
    if isinstance(value, dict):
        value = value.get("low")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _digits(phone: str) -> str:
    return "".join(c for c in phone if c.isdigit())


_drain_task: asyncio.Task | None = None


def kick(session_factory) -> None:
    """Começa a esvaziar a fila neste processo (se já não estiver). Chamado após disparos e respostas.

    Não há varredura periódica: assim o banco (Neon) pode "dormir" quando o chatbot não está em uso.
    """
    global _drain_task
    if not get_settings().chatbot_worker:
        return
    if _drain_task is not None and not _drain_task.done():
        return
    _drain_task = asyncio.get_running_loop().create_task(_drain(session_factory))


async def _drain(session_factory) -> None:
    try:
        async with session_factory() as lock_session:
            # um único remetente entre os workers do uvicorn (o outro desiste; quem tem o lock envia tudo)
            if not await lock_session.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": WORKER_LOCK}):
                return
            try:
                idle = 0
                while idle < 3:
                    async with session_factory() as session:
                        service = ChatbotService(session)
                        sent = await service.process_outbox(max_items=1)
                        pending = await session.scalar(select(func.count()).select_from(WhatsAppOutbox)
                                                       .where(WhatsAppOutbox.status == "PENDENTE")) or 0
                    if not pending:
                        break
                    # esperar o intervalo entre cobranças não conta como "parado"; falhas seguidas, sim
                    waiting_gap = _next_charge_at is not None and _now() < _next_charge_at
                    idle = 0 if sent or waiting_gap else idle + 1
                    # sem envio e sem intervalo a respeitar: provavelmente o WhatsApp está acordando
                    await asyncio.sleep(1 if sent else 5 if waiting_gap else 20)
            finally:
                await lock_session.scalar(text("SELECT pg_advisory_unlock(:k)"), {"k": WORKER_LOCK})
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Falha ao enviar a fila do chatbot")
