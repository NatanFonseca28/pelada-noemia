from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, ForbiddenError, UnauthorizedError, ValidationError
from app.core.security_log import security_event
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.enums import UserRole, UserStatus
from app.models.user import RefreshToken, User
from app.repositories.user_repo import RefreshTokenRepository, UserRepository
from app.services import audit_service

# Hash fictício (de uma senha aleatória descartada) para manter o tempo do login constante
DUMMY_HASH = hash_password(generate_refresh_token())


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.tokens = RefreshTokenRepository(session)

    async def register(self, *, email: str, name: str, password: str) -> User:
        """Autocadastro: fica PENDENTE até aprovação do ADMIN."""
        if await self.users.get_by_email(email):
            raise ConflictError("E-mail já cadastrado")
        user = self.users.add(
            User(
                email=email.lower(),
                name=name,
                password_hash=hash_password(password),
                role=UserRole.JOGADOR,
                status=UserStatus.PENDENTE,
            )
        )
        await self.session.flush()
        await audit_service.record(
            self.session, user_id=None, action="REGISTER", entity="user", entity_id=user.id,
            after=audit_service.snapshot(user),
        )
        await self.session.commit()
        return user

    async def login(self, email: str, password: str, ip: str | None = None) -> tuple[User, str, str]:
        settings = get_settings()
        now = datetime.now(UTC)
        user = await self.users.get_by_email(email)
        if user is None:
            # Tempo constante: verifica contra um hash fictício para não revelar se o e-mail existe
            verify_password(password, DUMMY_HASH)
            security_event("login_failed", reason="unknown_email", ip=ip)
            raise UnauthorizedError("E-mail ou senha inválidos")
        if user.locked_until and user.locked_until > now:
            minutes = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
            security_event("login_blocked", user_id=user.id, ip=ip)
            raise ForbiddenError(
                f"Conta bloqueada temporariamente por excesso de tentativas. Tente de novo em {minutes} min.",
                code="ACCOUNT_LOCKED",
            )
        if not verify_password(password, user.password_hash):
            user.failed_logins += 1
            if user.failed_logins >= settings.login_max_failures:
                user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
                user.failed_logins = 0
                await audit_service.record(self.session, user_id=None, action="LOCKED", entity="user", entity_id=user.id,
                                           after={"locked_until": user.locked_until.isoformat()})
                security_event("account_locked", user_id=user.id, ip=ip)
            else:
                security_event("login_failed", reason="wrong_password", user_id=user.id, ip=ip)
            await self.session.commit()
            raise UnauthorizedError("E-mail ou senha inválidos")
        self._ensure_active(user)
        user.failed_logins = 0
        user.locked_until = None
        refresh = await self._issue_refresh(user)
        await self.session.commit()
        return user, create_access_token(user.id, user.role.value), refresh

    async def refresh(self, raw_token: str | None) -> tuple[User, str, str]:
        """Rotação: o refresh usado é revogado e substituído. Reuso de token revogado
        indica vazamento e revoga todas as sessões do usuário."""
        if not raw_token:
            raise UnauthorizedError("Sessão expirada")
        now = datetime.now(UTC)
        stored = await self.tokens.get_by_hash(hash_refresh_token(raw_token))
        if stored is None:
            raise UnauthorizedError("Sessão inválida")
        if stored.revoked_at is not None:
            await self.tokens.revoke_all_for_user(stored.user_id, now)
            await self.session.commit()
            raise UnauthorizedError("Sessão inválida")
        if stored.expires_at <= now:
            raise UnauthorizedError("Sessão expirada")
        user = await self.users.get(stored.user_id)
        if user is None:
            raise UnauthorizedError("Sessão inválida")
        self._ensure_active(user)
        new_raw = await self._issue_refresh(user)
        new_stored = await self.tokens.get_by_hash(hash_refresh_token(new_raw))
        stored.revoked_at = now
        stored.replaced_by_id = new_stored.id if new_stored else None
        await self.session.commit()
        return user, create_access_token(user.id, user.role.value), new_raw

    async def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        stored = await self.tokens.get_by_hash(hash_refresh_token(raw_token))
        if stored and stored.revoked_at is None:
            stored.revoked_at = datetime.now(UTC)
            await self.session.commit()

    async def change_password(self, user: User, current: str, new: str) -> None:
        if not verify_password(current, user.password_hash):
            raise ValidationError("Senha atual incorreta")
        if verify_password(new, user.password_hash):
            raise ValidationError("A nova senha precisa ser diferente da atual")
        user.password_hash = hash_password(new)
        user.must_change_password = False
        await self.tokens.revoke_all_for_user(user.id, datetime.now(UTC))
        await audit_service.record(
            self.session, user_id=user.id, action="CHANGE_PASSWORD", entity="user", entity_id=user.id
        )
        await self.session.commit()

    async def _issue_refresh(self, user: User) -> str:
        raw = generate_refresh_token()
        now = datetime.now(UTC)
        # Limpeza: tokens vencidos ou revogados há mais de 30 dias deixam de ser guardados
        await self.session.execute(
            delete(RefreshToken).where(
                RefreshToken.user_id == user.id,
                (RefreshToken.expires_at < now) | (RefreshToken.revoked_at < now - timedelta(days=30)),
            )
        )
        self.tokens.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_refresh_token(raw),
                created_at=now,
                expires_at=now + timedelta(days=get_settings().refresh_token_days),
            )
        )
        await self.session.flush()
        return raw

    @staticmethod
    def _ensure_active(user: User) -> None:
        if user.status == UserStatus.PENDENTE:
            raise ForbiddenError("Cadastro aguardando aprovação do administrador", code="USER_PENDING")
        if user.status == UserStatus.BLOQUEADO:
            raise ForbiddenError("Usuário bloqueado", code="USER_BLOCKED")
