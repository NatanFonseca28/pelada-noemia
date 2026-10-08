"""chatbot de cobrança pelo WhatsApp: fila de envio, conversas, pedidos e configuração

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_outbox",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("player_id", sa.BigInteger(), sa.ForeignKey("players.id", ondelete="SET NULL"), nullable=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="PENDENTE"),
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("error", sa.String(300), nullable=True),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_whatsapp_outbox_player_id"), "whatsapp_outbox", ["player_id"])
    op.create_index(op.f("ix_whatsapp_outbox_status"), "whatsapp_outbox", ["status"])
    op.create_table(
        "charge_conversations",
        sa.Column("player_id", sa.BigInteger(), sa.ForeignKey("players.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("months", JSONB(), nullable=False, server_default="[]"),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("last_charge_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_menu_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("awaiting_proof", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_message_id", sa.String(100), nullable=True),
    )
    op.create_table(
        "charge_replies",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("player_id", sa.BigInteger(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("months", JSONB(), nullable=False, server_default="[]"),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("media_path", sa.String(200), nullable=True),
        sa.Column("has_document", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="ABERTO"),
        sa.Column("resolved_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_charge_replies_player_id"), "charge_replies", ["player_id"])
    op.create_index(op.f("ix_charge_replies_status"), "charge_replies", ["status"])
    op.add_column("settings", sa.Column("chatbot_enabled", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("settings", sa.Column("chatbot_daily_limit", sa.SmallInteger(), nullable=False,
                                        server_default="40"))
    op.add_column("settings", sa.Column("chatbot_owner_user_id", sa.BigInteger(),
                                        sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))


def downgrade() -> None:
    op.drop_column("settings", "chatbot_owner_user_id")
    op.drop_column("settings", "chatbot_daily_limit")
    op.drop_column("settings", "chatbot_enabled")
    op.drop_table("charge_replies")
    op.drop_table("charge_conversations")
    op.drop_index(op.f("ix_whatsapp_outbox_status"), table_name="whatsapp_outbox")
    op.drop_index(op.f("ix_whatsapp_outbox_player_id"), table_name="whatsapp_outbox")
    op.drop_table("whatsapp_outbox")
