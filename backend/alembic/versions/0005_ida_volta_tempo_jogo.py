"""jogos de 8 a 10 minutos e ida e volta

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-06
"""
import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("max_match_minutes", sa.SmallInteger(), nullable=False, server_default="10"))
    # Regra da pelada: jogos de tabela entre 8 e 10 minutos (o padrão antigo era 5)
    op.execute("UPDATE settings SET min_match_minutes = 8 WHERE min_match_minutes = 5")
    op.add_column("matches", sa.Column("leg", sa.SmallInteger(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("matches", "leg")
    op.drop_column("settings", "max_match_minutes")
