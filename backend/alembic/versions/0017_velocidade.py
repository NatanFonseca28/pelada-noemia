"""velocidade do jogador (1 a 5), usada com o nível técnico no equilíbrio do sorteio

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("speed", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(op.f("ck_players_speed_range"), "players", "speed BETWEEN 1 AND 5")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_players_speed_range"), "players", type_="check")
    op.drop_column("players", "speed")
