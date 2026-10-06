"""segurança da conta: troca de senha obrigatória e bloqueio por tentativas

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-06
"""
import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("failed_logins", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_logins")
    op.drop_column("users", "must_change_password")
