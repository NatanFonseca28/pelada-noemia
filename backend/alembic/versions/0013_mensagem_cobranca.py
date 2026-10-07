"""mensagem de cobrança por WhatsApp e chave Pix

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-06
"""
import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("charge_message", sa.Text()))
    op.add_column("settings", sa.Column("pix_key", sa.String(140)))


def downgrade() -> None:
    op.drop_column("settings", "pix_key")
    op.drop_column("settings", "charge_message")
