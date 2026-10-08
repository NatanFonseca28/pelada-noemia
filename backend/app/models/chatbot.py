from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WhatsAppOutbox(Base):
    """Fila de mensagens do chatbot. O envio respeita intervalos para não parecer robô (anti-bloqueio)."""

    __tablename__ = "whatsapp_outbox"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True,
                                                  index=True)
    phone: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(12))  # COBRANCA | MENU | RESPOSTA
    status: Mapped[str] = mapped_column(String(10), default="PENDENTE", index=True)  # PENDENTE | ENVIADA | ERRO
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChargeConversation(Base):
    """Estado da conversa de cobrança de um jogador (o que foi cobrado e em que passo está)."""

    __tablename__ = "charge_conversations"

    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    months: Mapped[list[str]] = mapped_column(JSONB, default=list)  # ISO "2026-09-01"
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    last_charge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_menu_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    awaiting_proof: Mapped[bool] = mapped_column(Boolean, default=False)
    last_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class ChargeReply(Base):
    """Resposta de jogador que precisa do admin: pagamento a confirmar, pedido de "F" ou falar com o gestor."""

    __tablename__ = "charge_replies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # PAGO | FORA | FALAR
    months: Mapped[list[str]] = mapped_column(JSONB, default=list)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    media_path: Mapped[str | None] = mapped_column(String(200), nullable=True)  # comprovante (imagem)
    has_document: Mapped[bool] = mapped_column(Boolean, default=False)  # mandou PDF (não guardado)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="ABERTO", index=True)  # ABERTO | CONFIRMADO | RECUSADO
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def media_url(self) -> str | None:
        return f"/api/media/{self.media_path}" if self.media_path else None
