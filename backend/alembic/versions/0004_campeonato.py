"""campeonato: torneios, grupos e partidas

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

ENUMS = {
    "tournament_status": ("EM_ANDAMENTO", "ENCERRADO"),
    "match_status": ("AGENDADA", "EM_ANDAMENTO", "PAUSADA", "ENCERRADA"),
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
        "tournaments",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("round_id", sa.BigInteger(), fk("round_id", "rounds", "tournaments", "CASCADE"), nullable=False),
        sa.Column("format_code", sa.String(40), nullable=False),
        sa.Column("status", enum("tournament_status"), nullable=False),
        sa.Column("match_seconds", sa.Integer(), nullable=False),
        sa.Column("final_seconds", sa.Integer()),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("champion_team_id", sa.BigInteger(), fk("champion_team_id", "teams", "tournaments", "SET NULL")),
        sa.Column("runner_up_team_id", sa.BigInteger(), fk("runner_up_team_id", "teams", "tournaments", "SET NULL")),
        sa.Column("created_by", sa.BigInteger(), fk("created_by", "users", "tournaments", "SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("round_id", name="uq_tournaments_round_id"),
    )
    op.create_table(
        "tournament_groups",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("tournament_id", sa.BigInteger(), fk("tournament_id", "tournaments", "tournament_groups", "CASCADE"),
                  nullable=False),
        sa.Column("name", sa.String(10), nullable=False),
        sa.UniqueConstraint("tournament_id", "name", name="uq_tournament_groups_tournament_name"),
    )
    op.create_index("ix_tournament_groups_tournament_id", "tournament_groups", ["tournament_id"])
    op.create_table(
        "tournament_group_teams",
        sa.Column("group_id", sa.BigInteger(), fk("group_id", "tournament_groups", "tournament_group_teams", "CASCADE"),
                  primary_key=True),
        sa.Column("team_id", sa.BigInteger(), fk("team_id", "teams", "tournament_group_teams", "CASCADE"),
                  primary_key=True),
    )
    op.create_table(
        "matches",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("tournament_id", sa.BigInteger(), fk("tournament_id", "tournaments", "matches", "CASCADE"),
                  nullable=False),
        sa.Column("group_id", sa.BigInteger(), fk("group_id", "tournament_groups", "matches", "SET NULL")),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("seq", sa.SmallInteger(), nullable=False),
        sa.Column("home_team_id", sa.BigInteger(), fk("home_team_id", "teams", "matches", "SET NULL")),
        sa.Column("away_team_id", sa.BigInteger(), fk("away_team_id", "teams", "matches", "SET NULL")),
        sa.Column("home_source", sa.String(20)),
        sa.Column("away_source", sa.String(20)),
        sa.Column("planned_seconds", sa.Integer(), nullable=False),
        sa.Column("goal_limit", sa.SmallInteger()),
        sa.Column("status", enum("match_status"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("elapsed_before_pause", sa.Integer(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("home_score", sa.SmallInteger(), nullable=False),
        sa.Column("away_score", sa.SmallInteger(), nullable=False),
        sa.Column("home_penalties", sa.SmallInteger()),
        sa.Column("away_penalties", sa.SmallInteger()),
        sa.Column("winner_team_id", sa.BigInteger(), fk("winner_team_id", "teams", "matches", "SET NULL")),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tournament_id", "seq", name="uq_matches_tournament_seq"),
    )
    op.create_index("ix_matches_tournament_id", "matches", ["tournament_id"])


def downgrade() -> None:
    for table in ("matches", "tournament_group_teams", "tournament_groups", "tournaments"):
        op.drop_table(table)
    bind = op.get_bind()
    for name in ENUMS:
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
