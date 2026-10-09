"""chatbot: horário da última resposta processada (evita reprocessar mensagens reentregues)

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("charge_conversations", sa.Column("last_inbound_ts", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("charge_conversations", "last_inbound_ts")
