"""Esqueci minha senha: o jogador pede, um administrador gera o link (1 h, uso único) e envia pelo WhatsApp."""
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import NotFoundError, ValidationError
from app.core.security import hash_password, hash_refresh_token
from app.core.security_log import security_event
from app.domain.phone import PhoneError, normalize_phone
from app.models.enums import UserStatus
from app.models.password_reset import PasswordReset
from app.models.player import Player
from app.models.user import User
from app.repositories.user_repo import RefreshTokenRepository
from app.schemas.auth import PasswordRequestOut, ResetLinkOut
from app.services import audit_service
from app.services.access_service import record_access

LINK_TTL = timedelta(hours=1)
INVALID_LINK = "Link inválido ou expirado. Peça um novo a um administrador."


class PasswordResetService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _find_user(self, identifier: str) -> User | None:
        identifier = identifier.strip()
        if "@" in identifier:
            return await self.session.scalar(select(User).where(User.email == identifier.lower()))
        try:
            phone = normalize_phone(identifier)
        except PhoneError:
            return None
        if not phone:
            return None
        return await self.session.scalar(
            select(User).outerjoin(Player, Player.id == User.player_id)
            .where(or_(User.phone == phone, Player.phone == phone)).limit(1)
        )

    async def request(self, identifier: str, ip: str | None, user_agent: str | None) -> None:
        """Registra o pedido. Não revela se o e-mail/celular existe (a resposta é sempre a mesma)."""
        user = await self._find_user(identifier)
        if user is None or user.status != UserStatus.ATIVO:
            security_event("password_reset_unknown", ip=ip)
            return
        now = datetime.now(UTC)
        open_request = await self.session.scalar(
            select(PasswordReset).where(
                PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None),
                or_(PasswordReset.expires_at.is_(None), PasswordReset.expires_at > now),
            )
        )
        if open_request is None:
            self.session.add(PasswordReset(user_id=user.id, requested_ip=(ip or None) and ip[:64]))
        await record_access(self.session, event="SENHA_PEDIDA", email=user.email, user_id=user.id, ip=ip,
                            user_agent=user_agent)
        await self.session.commit()

    async def pending(self) -> list[PasswordRequestOut]:
        now = datetime.now(UTC)
        rows = (await self.session.execute(
            select(PasswordReset, User, Player.phone)
            .join(User, User.id == PasswordReset.user_id)
            .outerjoin(Player, Player.id == User.player_id)
            .where(PasswordReset.used_at.is_(None),
                   or_(PasswordReset.expires_at.is_(None), PasswordReset.expires_at > now))
            .order_by(PasswordReset.created_at)
        )).all()
        return [
            PasswordRequestOut(id=r.id, user_id=u.id, name=u.name, email=u.email, phone=u.phone or player_phone,
                               requested_at=r.created_at, link_sent_at=r.handled_at)
            for r, u, player_phone in rows
        ]

    async def create_link(self, request_id: int, actor: User) -> ResetLinkOut:
        """Gera um link novo (o anterior, se houver, deixa de valer) válido por 1 hora."""
        reset = await self.session.get(PasswordReset, request_id)
        if reset is None or reset.used_at is not None:
            raise NotFoundError("Pedido não encontrado ou já resolvido")
        user = await self.session.get(User, reset.user_id)
        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        reset.token_hash = hash_refresh_token(token)
        reset.expires_at = now + LINK_TTL
        reset.handled_by = actor.id
        reset.handled_at = now
        await audit_service.record(self.session, user_id=actor.id, action="RESET_LINK", entity="user",
                                   entity_id=user.id, after={"request_id": reset.id, "expires_at": reset.expires_at.isoformat()})
        await self.session.commit()
        player_phone = await self.session.scalar(select(Player.phone).where(Player.id == user.player_id)) \
            if user.player_id else None
        origin = (get_settings().cors_origin_list or ["http://localhost:5173"])[0].rstrip("/")
        return ResetLinkOut(url=f"{origin}/redefinir-senha?token={token}", expires_at=reset.expires_at,
                            name=user.name, phone=user.phone or player_phone)

    async def reset(self, token: str, new_password: str, ip: str | None) -> None:
        now = datetime.now(UTC)
        reset = await self.session.scalar(select(PasswordReset).where(PasswordReset.token_hash == hash_refresh_token(token)))
        if reset is None or reset.used_at is not None or reset.expires_at is None or reset.expires_at <= now:
            security_event("password_reset_invalid", ip=ip)
            raise ValidationError(INVALID_LINK)
        user = await self.session.get(User, reset.user_id)
        if user is None or user.status != UserStatus.ATIVO:
            raise ValidationError(INVALID_LINK)
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        user.failed_logins = 0
        user.locked_until = None
        # este e qualquer outro pedido aberto do usuário ficam resolvidos; todas as sessões caem
        await self.session.execute(
            update(PasswordReset).where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None)).values(used_at=now)
        )
        await RefreshTokenRepository(self.session).revoke_all_for_user(user.id, now)
        await audit_service.record(self.session, user_id=user.id, action="PASSWORD_RESET", entity="user", entity_id=user.id)
        security_event("password_reset_done", user_id=user.id, ip=ip)
        await self.session.commit()
