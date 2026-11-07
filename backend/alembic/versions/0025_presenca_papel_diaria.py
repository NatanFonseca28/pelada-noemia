"""papel por presença (linha | goleiro) e diária antecipada por presença

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attendances", sa.Column("role", sa.String(10), nullable=False, server_default="LINHA"))
    op.add_column("attendances", sa.Column("fee_amount", sa.Numeric(10, 2), nullable=True))
    op.add_column("attendances", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(op.f("ck_attendances_role_values"), "attendances", "role IN ('LINHA', 'GOLEIRO')")
    op.add_column("settings", sa.Column("daily_fee", sa.Numeric(10, 2), nullable=False, server_default="20.00"))


def downgrade() -> None:
    op.drop_column("settings", "daily_fee")
    op.drop_constraint(op.f("ck_attendances_role_values"), "attendances", type_="check")
    op.drop_column("attendances", "paid_at")
    op.drop_column("attendances", "fee_amount")
    op.drop_column("attendances", "role")
