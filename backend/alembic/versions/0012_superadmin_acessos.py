"""superadmin, páginas ocultas por categoria e log de acessos

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

SUPERADMIN_EMAIL = "natanfs28@gmail.com"


def upgrade() -> None:
    op.add_column("users", sa.Column("is_superadmin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute(sa.text("UPDATE users SET is_superadmin = true, role = 'ADMIN' WHERE lower(email) = :e")
               .bindparams(e=SUPERADMIN_EMAIL))
    op.add_column("settings", sa.Column("hidden_pages", JSONB(), nullable=False, server_default="{}"))
    op.create_table(
        "access_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("event", sa.String(20), nullable=False),
        sa.Column("ip", sa.String(64)),
        sa.Column("user_agent", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_access_logs_user_id", "access_logs", ["user_id"])
    op.create_index("ix_access_logs_created_at", "access_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("access_logs")
    op.drop_column("settings", "hidden_pages")
    op.drop_column("users", "is_superadmin")
