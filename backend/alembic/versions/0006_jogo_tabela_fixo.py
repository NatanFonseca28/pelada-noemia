"""jogo de tabela com duração fixa (8 min)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-06
"""
import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("settings", "min_match_minutes", new_column_name="group_match_minutes")
    op.execute("UPDATE settings SET group_match_minutes = 8")
    op.drop_column("settings", "max_match_minutes")


def downgrade() -> None:
    op.add_column("settings", sa.Column("max_match_minutes", sa.SmallInteger(), nullable=False, server_default="10"))
    op.alter_column("settings", "group_match_minutes", new_column_name="min_match_minutes")
