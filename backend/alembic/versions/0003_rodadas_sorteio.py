"""rodadas, presença, sorteios e times

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

ENUMS = {
    "round_status": ("ABERTA", "FECHADA", "TIMES_TRAVADOS", "ENCERRADA"),
    "attendance_status": ("CONFIRMADO", "CANCELADO"),
    "attendance_source": ("APP", "ADMIN"),
    "team_role": ("LINHA", "GOLEIRO_FIXO", "REVEZAMENTO"),
}


def enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def fk(col: str, target: str, table: str, ondelete: str) -> sa.ForeignKey:
    return sa.ForeignKey(f"{target}.id", ondelete=ondelete, name=f"fk_{table}_{col}_{target}")


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    op.create_table(
        "rounds",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", enum("round_status"), nullable=False),
        sa.Column("notes", sa.String(500)),
        sa.Column("settings_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("date", name="uq_rounds_date"),
    )

    op.create_table(
        "attendances",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("round_id", sa.BigInteger(), fk("round_id", "rounds", "attendances", "CASCADE"), nullable=False),
        sa.Column("player_id", sa.BigInteger(), fk("player_id", "players", "attendances", "RESTRICT"),
                  nullable=False),
        sa.Column("status", enum("attendance_status"), nullable=False),
        sa.Column("source", enum("attendance_source"), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), fk("updated_by", "users", "attendances", "SET NULL")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("round_id", "player_id", name="uq_attendances_round_player"),
    )
    op.create_index("ix_attendances_round_id", "attendances", ["round_id"])
    op.create_index("ix_attendances_player_id", "attendances", ["player_id"])

    op.create_table(
        "draws",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("round_id", sa.BigInteger(), fk("round_id", "rounds", "draws", "CASCADE"), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("algorithm_version", sa.String(10), nullable=False),
        sa.Column("num_teams", sa.SmallInteger(), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), fk("created_by", "users", "draws", "SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_draws_round_id", "draws", ["round_id"])

    op.create_table(
        "teams",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("round_id", sa.BigInteger(), fk("round_id", "rounds", "teams", "CASCADE"), nullable=False),
        sa.Column("draw_id", sa.BigInteger(), fk("draw_id", "draws", "teams", "CASCADE"), nullable=False),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("color", sa.String(9), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
    )
    op.create_index("ix_teams_round_id", "teams", ["round_id"])
    op.create_index("ix_teams_draw_id", "teams", ["draw_id"])

    op.create_table(
        "team_players",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("team_id", sa.BigInteger(), fk("team_id", "teams", "team_players", "CASCADE"), nullable=False),
        sa.Column("round_id", sa.BigInteger(), fk("round_id", "rounds", "team_players", "CASCADE"), nullable=False),
        sa.Column("player_id", sa.BigInteger(), fk("player_id", "players", "team_players", "RESTRICT"),
                  nullable=False),
        sa.Column("assigned_position", sa.String(20), nullable=False),
        sa.Column("role", enum("team_role"), nullable=False),
        sa.Column("filled_by", sa.String(20), nullable=False),
        sa.Column("moved_manually", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("round_id", "player_id", name="uq_team_players_round_player"),
    )
    for col in ("team_id", "round_id", "player_id"):
        op.create_index(f"ix_team_players_{col}", "team_players", [col])


def downgrade() -> None:
    for table in ("team_players", "teams", "draws", "attendances", "rounds"):
        op.drop_table(table)
    bind = op.get_bind()
    for name in ENUMS:
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
