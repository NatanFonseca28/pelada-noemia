"""Chatbot de cobrança pelo WhatsApp oficial (WhatsApp Business Platform da Meta).

Fluxo: o admin dispara ("Cobrar todos" ou "Cobrar") → a cobrança (modelo aprovado, com botões) entra na fila →
a tarefa de envio manda → o jogador toca num botão ou escreve → o bot responde na hora (Pix) ou cria um pedido para
o admin (pagamento a conferir, "F", falar com o gestor). Nenhuma cobrança sai sem o admin disparar.
"""
import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.domain import chatbot as bot
from app.domain.charge_message import DEFAULT_CHARGE_MESSAGE
from app.domain.delinquency import OUT_MARKER
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

    async def status(self, with_info: bool = False) -> dict:
        s = await self._settings()
        state, info = "unconfigured", None
        if self.gateway is not None:
            state = await self.gateway.state()
            if with_info and state == "open":
                try:
                    info = await self.gateway.info()
                except GatewayError as exc:
                    info = {"error": str(exc)}
        since = self.clock() - timedelta(hours=24)
        charges = await self.session.scalar(select(func.count()).select_from(WhatsAppOutbox).where(
            WhatsAppOutbox.kind == "COBRANCA", WhatsAppOutbox.created_at >= since)) or 0
        pending = await self.session.scalar(select(func.count()).select_from(WhatsAppOutbox).where(
            WhatsAppOutbox.status == "PENDENTE")) or 0
        owner = await self.owner()
        return {"enabled": s.chatbot_enabled, "state": state, "daily_limit": s.chatbot_daily_limit,
                "charges_today": charges, "pending": pending,
                "owner_user_id": owner.id if owner else None, "owner_name": owner.name if owner else None,
                "info": info}

    async def update_settings(self, enabled: bool, daily_limit: int, owner_user_id: int | None, actor: User) -> None:
        s = await self._settings()
        owner_user_id = owner_user_id or s.chatbot_owner_user_id or actor.id  # {gestor} da mensagem
        if await self.session.get(User, owner_user_id) is None:
            raise NotFoundError("Administrador não encontrado")
        before = {"enabled": s.chatbot_enabled, "daily_limit": s.chatbot_daily_limit,
                  "owner": s.chatbot_owner_user_id}
        s.chatbot_enabled, s.chatbot_daily_limit, s.chatbot_owner_user_id = enabled, daily_limit, owner_user_id
        await audit_service.record(self.session, user_id=actor.id, action="UPDATE", entity="chatbot", entity_id=1,
                                   before=before, after={"enabled": enabled, "daily_limit": daily_limit,
                                                         "owner": owner_user_id})
        await self.session.commit()

    # ---------------------------------------------------------- disparo
    async def charge(self, actor: User, player_ids: list[int] | None = None, force: bool = False) -> dict:
        """Enfileira cobranças. Sem `player_ids`: todos de "Para cobrar" que aceitaram WhatsApp."""
        s = await self._settings()
        if not s.chatbot_enabled:
            raise ValidationError("O chatbot está desligado. O superadmin liga em Configurações.")
        if self.gateway is None:
            raise ValidationError("Chatbot não configurado no servidor (API oficial do WhatsApp).")
        cfg = get_settings()
        finance = FinanceService(self.session)
        config = await finance.get_config()
        owing = {d.player_id: d for d in await finance.delinquents(include_partial=True)}
        targets = player_ids if player_ids is not None else list(owing)
        now = self.clock()
        used = await self.session.scalar(select(func.count()).select_from(WhatsAppOutbox).where(
            WhatsAppOutbox.kind == "COBRANCA", WhatsAppOutbox.created_at >= now - timedelta(hours=24))) or 0
        gestor = await self.gestor()
        own = await self._own_numbers()
        single = player_ids is not None and len(player_ids) == 1
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
            elif own & bot.phone_variants(d.phone):
                if single:
                    raise ValidationError(f"{d.name} usa o mesmo número do WhatsApp da pelada. "
                                          "Para testar, use um jogador com outro número.")
                reason = "é o número do WhatsApp da pelada"
            elif not d.whatsapp_opt_in:
                reason = "não aceitou WhatsApp"
            elif not force and conv and conv.last_charge_at and \
                    now - conv.last_charge_at < timedelta(days=bot.CHARGE_COOLDOWN_DAYS):
                reason = "cobrado há menos de 3 dias"
            elif used + len(queued) >= s.chatbot_daily_limit:
                reason = "limite diário atingido"
            if reason:
                if single:
                    raise ConflictError(f"{d.name}: {reason}.")
                skipped.append({"name": d.name, "reason": reason})
                continue
            values = bot.charge_values(d.name, d.months_due, d.amount_due, config.monthly_fee, s.pix_key, gestor)
            # o texto do modelo aprovado é o padrão; o painel mostra a mensagem como ela chega
            self._enqueue(pid, d.phone, bot.render(DEFAULT_CHARGE_MESSAGE, values), "COBRANCA", actor.id,
                          payload={"template": cfg.meta_template_charge, "params": bot.template_params(values),
                                   "buttons": bot.BUTTONS})
            if conv is None:
                conv = ChargeConversation(player_id=pid)
                self.session.add(conv)
            conv.months = [m.isoformat() for m in d.months_due]
            conv.amount = d.amount_due
            conv.last_charge_at = now
            conv.awaiting_proof = False
            await audit_service.record(self.session, user_id=actor.id, action="CHARGE", entity="charge",
                                       entity_id=pid, after={"months": conv.months, "amount": str(d.amount_due),
                                                             "via": "chatbot"})
            queued.append(d.name)
        await self.session.commit()
        return {"queued": queued, "skipped": skipped}

    def _enqueue(self, player_id: int | None, phone: str, text_: str, kind: str, actor_id: int | None = None,
                 payload: dict | None = None) -> None:
        self.session.add(WhatsAppOutbox(player_id=player_id, phone=phone, text=text_, kind=kind,
                                        created_by=actor_id, payload=payload))

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
    async def process_outbox(self, max_items: int = 10) -> int:
        if self.gateway is None or not (await self._settings()).chatbot_enabled:
            return 0
        sent = 0
        for _ in range(max_items):
            item = await self.session.scalar(
                select(WhatsAppOutbox).where(WhatsAppOutbox.status == "PENDENTE").order_by(WhatsAppOutbox.id).limit(1)
            )
            if item is None:
                break
            try:
                number = _digits(item.phone)
                if item.payload:
                    message_id = await self.gateway.send_template(
                        number, item.payload["template"], item.payload.get("params") or [],
                        item.payload.get("buttons"))
                else:
                    message_id = await self.gateway.send_text(number, item.text)
                item.status, item.sent_at, item.error, item.message_id = "ENVIADA", self.clock(), None, message_id
                sent += 1
            except GatewayError as exc:
                item.attempts += 1
                item.error = str(exc)[:300]
                if item.attempts >= 3:
                    item.status = "ERRO"
                await self.session.commit()
                break
            await self.session.commit()
        return sent

    # ---------------------------------------------------------- respostas (webhook da Meta)
    async def handle_webhook(self, payload: dict) -> list[str]:
        results: list[str] = []
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                for st in value.get("statuses") or []:
                    await self._status_update(st)
                for msg in value.get("messages") or []:
                    results.append(await self._handle_message(msg))
        await self.session.commit()
        return results

    async def _status_update(self, st: dict) -> None:
        """Entrega falhou (ex.: número sem WhatsApp, fora da janela de 24 h): mostra o motivo no painel."""
        if st.get("status") != "failed" or not st.get("id"):
            return
        item = await self.session.scalar(select(WhatsAppOutbox).where(WhatsAppOutbox.message_id == st["id"]))
        if item is not None:
            err = (st.get("errors") or [{}])[0]
            item.status = "ERRO"
            item.error = f"{err.get('code', '')} {err.get('title') or err.get('message') or 'falhou'}"[:300]

    async def _handle_message(self, msg: dict) -> str:
        digits = "".join(c for c in str(msg.get("from") or "") if c.isdigit())
        player = await self._player_by_digits(digits) if digits else None
        if player is None:
            return "ignorado"
        conv = await self.session.get(ChargeConversation, player.id)
        if conv is None or not conv.last_charge_at or self.clock() - conv.last_charge_at > timedelta(days=30):
            return "ignorado"  # não está numa cobrança
        message_id = msg.get("id")
        if message_id and conv.last_message_id == message_id:
            return "repetido"
        ts = _timestamp(msg.get("timestamp"))
        if ts is not None and conv.last_inbound_ts and ts < conv.last_inbound_ts:
            return "repetido"
        conv.last_message_id = message_id
        conv.last_inbound_ts = ts or int(self.clock().timestamp())  # abre a janela de 24 h

        kind = msg.get("type")
        text_ = None
        intent = None
        media_id = None
        is_document = False
        if kind == "text":
            text_ = (msg.get("text") or {}).get("body")
        elif kind == "button":
            button = msg.get("button") or {}
            intent = bot.payload_intent(button.get("payload"))
            text_ = button.get("text")
        elif kind == "interactive":
            inter = msg.get("interactive") or {}
            reply = inter.get("button_reply") or inter.get("list_reply") or {}
            intent = bot.payload_intent(reply.get("id"))
            text_ = reply.get("title")
        elif kind == "image":
            media_id = (msg.get("image") or {}).get("id")
            text_ = (msg.get("image") or {}).get("caption")
        elif kind == "document":
            is_document = True
            text_ = (msg.get("document") or {}).get("caption")
        if intent is None:
            intent = bot.parse_reply(text_, has_media=bool(media_id) or is_document)

        gestor = await self.gestor()
        phone = player.phone
        note = text_ if kind == "text" else None
        if intent == bot.Intent.STOP:
            # LGPD/Meta: o jogador pode sair a qualquer momento; o admin passa a cobrar pelo próprio WhatsApp
            player.whatsapp_opt_in = False
            self._enqueue(player.id, phone, "Pronto, você não vai mais receber cobranças por aqui. "
                                            f"Se mudar de ideia, fale com o {gestor}.", "RESPOSTA")
        elif intent == bot.Intent.PIX:
            await self._send_pix(player, conv, gestor)
        elif intent in (bot.Intent.PAID, bot.Intent.PROOF):
            reply = await self._open_reply(player.id, "PAGO", conv, note=note)
            if intent == bot.Intent.PROOF:
                if media_id:
                    reply.media_path = await self._store_proof(media_id) or reply.media_path
                reply.has_document = reply.has_document or is_document
                conv.awaiting_proof = False
                self._enqueue(player.id, phone, f"Valeu! O {gestor} vai conferir e dar baixa. ✅", "RESPOSTA")
            else:
                conv.awaiting_proof = True
                self._enqueue(player.id, phone, f"Beleza! Manda o comprovante aqui (foto ou PDF) que eu passo "
                                                f"pro {gestor} conferir.", "RESPOSTA")
        elif intent == bot.Intent.OUT:
            month = today_local().replace(day=1)
            await self._open_reply(player.id, "FORA", conv, note=note, months=[month.isoformat()])
            self._enqueue(player.id, phone, f"Anotado! O {gestor} vai confirmar que você fica fora em "
                                            f"{bot.months_text([month])}.", "RESPOSTA")
        elif intent == bot.Intent.TALK:
            await self._open_reply(player.id, "FALAR", conv, note=note)
            self._enqueue(player.id, phone, f"Beleza, avisei o {gestor}. Ele te chama por aqui.", "RESPOSTA")
        else:
            now = self.clock()
            if not conv.last_menu_at or now - conv.last_menu_at > timedelta(hours=bot.MENU_RESEND_HOURS):
                conv.last_menu_at = now
                self._enqueue(player.id, phone, bot.menu_text(gestor), "MENU")
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

    async def _store_proof(self, media_id: str) -> str | None:
        try:
            content, _ = await self.gateway.download_media(media_id)
            return save_photo(self.session, content, folder="comprovantes")
        except (GatewayError, ValidationError):
            log.warning("Comprovante do chatbot não pôde ser baixado ou não é imagem válida")
            return None

    async def _own_numbers(self) -> set[str]:
        """Variações do número da pelada (e do celular do dono), para nunca cobrar a si mesmo."""
        out: set[str] = set()
        try:
            number = await self.gateway.owner_number() if self.gateway else None
        except GatewayError:
            number = None
        if number:
            out |= bot.phone_variants("+" + number)
        owner = await self.owner()
        if owner and owner.phone:
            out |= bot.phone_variants(owner.phone)
        return out

    async def _player_by_digits(self, digits: str) -> Player | None:
        players = list(await self.session.scalars(select(Player).where(Player.phone.is_not(None))))
        return next((p for p in players if digits in bot.phone_variants(p.phone)), None)

    def _window_open(self, conv: ChargeConversation | None) -> bool:
        return bool(conv and conv.last_inbound_ts) and \
            self.clock().timestamp() - conv.last_inbound_ts < bot.SESSION_WINDOW_HOURS * 3600

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
        conv = await self.session.get(ChargeConversation, reply.player_id)
        finance = FinanceService(self.session)
        months = [date.fromisoformat(m) for m in reply.months]
        can_message = bool(player and player.phone and player.whatsapp_opt_in and self.gateway is not None)
        if approve and reply.kind == "PAGO":
            fee = (await finance.get_config()).monthly_fee
            for m in months:
                await finance.set_fee(FeeCellIn(player_id=reply.player_id, month=m, amount=fee), actor)
            if can_message:
                label = bot.months_text(months)
                text_ = f"Pagamento confirmado ✅ ({label}). Valeu!"
                # fora das 24 h desde a última mensagem do jogador, só com modelo aprovado
                payload = None if self._window_open(conv) else \
                    {"template": get_settings().meta_template_paid, "params": [label]}
                self._enqueue(player.id, player.phone, text_, "RESPOSTA", actor.id, payload=payload)
        elif approve and reply.kind == "FORA":
            for m in months:
                cell = await self.session.scalar(select(MonthlyFee).where(
                    MonthlyFee.player_id == reply.player_id, MonthlyFee.month == m))
                if cell is None or cell.amount is None:  # não apaga pagamento já lançado
                    await finance.set_fee(FeeCellIn(player_id=reply.player_id, month=m, marker=OUT_MARKER), actor)
            if can_message and self._window_open(conv):
                self._enqueue(player.id, player.phone,
                              f"Confirmado: você fica fora em {bot.months_text(months)}. 👍", "RESPOSTA", actor.id)
        reply.status = "CONFIRMADO" if approve else "RECUSADO"
        reply.resolved_by, reply.resolved_at = actor.id, self.clock()
        await audit_service.record(self.session, user_id=actor.id, action="RESOLVE", entity="charge_reply",
                                   entity_id=reply.id, after={"kind": reply.kind, "status": reply.status})
        await self.session.commit()


def _timestamp(value) -> int | None:
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
    """Esvazia a fila neste processo (se já não estiver). Chamado após disparos, respostas e na subida da API.

    Não há varredura periódica: o banco (Neon) pode "dormir" quando o chatbot não está em uso.
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
            # um único remetente entre os workers do uvicorn
            if not await lock_session.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": WORKER_LOCK}):
                return
            try:
                failures = 0
                while failures < 3:
                    async with session_factory() as session:
                        sent = await ChatbotService(session).process_outbox(max_items=10)
                        pending = await session.scalar(select(func.count()).select_from(WhatsAppOutbox)
                                                       .where(WhatsAppOutbox.status == "PENDENTE")) or 0
                    if not pending:
                        break
                    failures = 0 if sent else failures + 1
                    await asyncio.sleep(1 if sent else 10)
            finally:
                await lock_session.scalar(text("SELECT pg_advisory_unlock(:k)"), {"k": WORKER_LOCK})
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Falha ao enviar a fila do chatbot")
