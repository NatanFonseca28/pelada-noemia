"""contato do jogador (WhatsApp) e consentimento

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-06
"""
import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("phone", sa.String(20)))
    op.add_column("players", sa.Column("whatsapp_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("players", "whatsapp_opt_in")
    op.drop_column("players", "phone")
