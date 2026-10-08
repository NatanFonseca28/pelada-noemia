"""mensalidade quitada com valor diferente (conta como pago)

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("monthly_fees", sa.Column("settled", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("monthly_fees", "settled")
