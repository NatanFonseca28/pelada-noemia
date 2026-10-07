"""celular do usuário (informado no cadastro)

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-06
"""
import sqlalchemy as sa

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(20)))
    # quem já está vinculado a um jogador herda o WhatsApp dele
    op.execute("UPDATE users u SET phone = p.phone FROM players p WHERE u.player_id = p.id AND p.phone IS NOT NULL")


def downgrade() -> None:
    op.drop_column("users", "phone")
