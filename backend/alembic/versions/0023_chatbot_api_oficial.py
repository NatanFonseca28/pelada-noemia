"""chatbot na API oficial da Meta: conteúdo de modelo na fila e janela de 24 h

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # modelo aprovado pela Meta: {"template": nome, "params": [...], "buttons": [...]}; None = texto livre
    op.add_column("whatsapp_outbox", sa.Column("payload", JSONB(), nullable=True))
    op.add_column("whatsapp_outbox", sa.Column("message_id", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("whatsapp_outbox", "message_id")
    op.drop_column("whatsapp_outbox", "payload")
