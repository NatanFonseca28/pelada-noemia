from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.security_log import security_event
from app.core.security import hash_password
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.repositories.player_repo import PlayerRepository
from app.repositories.user_repo import RefreshTokenRepository, UserRepository
from app.schemas.user import UserApprove, UserCreate, UserUpdate
from app.services import audit_service


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.players = PlayerRepository(session)

    async def list(self, status: UserStatus | None = None) -> list[User]:
        return await self.users.list(status)

    async def get(self, user_id: int) -> User:
        user = await self.users.get(user_id)
        if user is None:
            raise NotFoundError("Usuário não encontrado")
        return user

    async def create(self, data: UserCreate, actor: User) -> User:
        """Cadastro feito pelo ADMIN já nasce ATIVO."""
        if await self.users.get_by_email(data.email):
            raise ConflictError("E-mail já cadastrado")
        if data.player_id is not None:
            await self._ensure_player_linkable(data.player_id)
        user = self.users.add(
            User(
                email=data.email.lower(),
                name=data.name,
                password_hash=hash_password(data.password),
                role=data.role,
                status=UserStatus.ATIVO,
                player_id=data.player_id,
                must_change_password=True,  # senha definida pelo admin: troca obrigatória no 1º acesso
                approved_by=actor.id,
                approved_at=datetime.now(UTC),
            )
        )
        await self.session.flush()
        await audit_service.record(
            self.session, user_id=actor.id, action="CREATE", entity="user", entity_id=user.id,
            after=audit_service.snapshot(user),
        )
        await self.session.commit()
        return user

    async def update(self, user_id: int, data: UserUpdate, actor: User) -> User:
        user = await self.get(user_id)
        before = audit_service.snapshot(user)
        if user.is_superadmin and not actor.is_superadmin:
            raise ForbiddenError("Só o superadmin pode alterar a conta do superadmin")
        if user.id == actor.id and (
            (data.role and data.role != UserRole.ADMIN) or (data.status and data.status != UserStatus.ATIVO)
        ):
            raise ValidationError("Você não pode remover o próprio acesso de administrador")
        if data.name is not None:
            user.name = data.name
        if data.role is not None and data.role != user.role:
            security_event("role_changed", user_id=user.id, by=actor.id, old=user.role.value, new=data.role.value)
            user.role = data.role
        if data.status is not None:
            user.status = data.status
            if data.status != UserStatus.ATIVO:
                await RefreshTokenRepository(self.session).revoke_all_for_user(user.id, datetime.now(UTC))
        if data.unlink_player:
            user.player_id = None
        elif data.player_id is not None and data.player_id != user.player_id:
            await self._ensure_player_linkable(data.player_id)
            user.player_id = data.player_id
        if data.password:
            user.password_hash = hash_password(data.password)
            user.must_change_password = True  # senha redefinida pelo admin: o usuário troca no próximo acesso
            await RefreshTokenRepository(self.session).revoke_all_for_user(user.id, datetime.now(UTC))
        await audit_service.record(
            self.session, user_id=actor.id, action="UPDATE", entity="user", entity_id=user.id,
            before=before, after=audit_service.snapshot(user),
        )
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def approve(self, user_id: int, data: UserApprove, actor: User) -> User:
        user = await self.get(user_id)
        if user.status != UserStatus.PENDENTE:
            raise ValidationError("Usuário não está pendente de aprovação")
        before = audit_service.snapshot(user)
        if data.player_id is not None:
            await self._ensure_player_linkable(data.player_id)
            user.player_id = data.player_id
        user.role = data.role
        user.status = UserStatus.ATIVO
        user.approved_by = actor.id
        user.approved_at = datetime.now(UTC)
        await audit_service.record(
            self.session, user_id=actor.id, action="APPROVE", entity="user", entity_id=user.id,
            before=before, after=audit_service.snapshot(user),
        )
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def reject(self, user_id: int, actor: User) -> None:
        """Recusa um autocadastro pendente (remove o registro)."""
        user = await self.get(user_id)
        if user.status != UserStatus.PENDENTE:
            raise ValidationError("Só é possível recusar cadastros pendentes")
        await audit_service.record(
            self.session, user_id=actor.id, action="REJECT", entity="user", entity_id=user.id,
            before=audit_service.snapshot(user),
        )
        await self.users.delete(user)
        await self.session.commit()

    async def _ensure_player_linkable(self, player_id: int) -> None:
        if await self.players.get(player_id) is None:
            raise NotFoundError("Jogador não encontrado")
        if await self.users.get_by_player(player_id):
            raise ConflictError("Jogador já vinculado a outro usuário")
