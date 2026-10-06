"""súmula (eventos de partida) e views de estatísticas

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

EVENT_TYPES = ("GOL", "GOL_CONTRA", "AMARELO", "VERMELHO")

# Cópia congelada de app/db/views.py no momento desta migration
VIEWS_SQL = {
    "vw_player_matches": """
        CREATE VIEW vw_player_matches AS
        SELECT tp.player_id,
               m.id AS match_id,
               m.tournament_id,
               t.round_id,
               r.date AS round_date,
               tp.team_id,
               m.stage,
               CASE WHEN tp.team_id = m.home_team_id THEN m.home_score ELSE m.away_score END AS goals_for,
               CASE WHEN tp.team_id = m.home_team_id THEN m.away_score ELSE m.home_score END AS goals_against
        FROM team_players tp
        JOIN matches m ON m.status = 'ENCERRADA' AND tp.team_id IN (m.home_team_id, m.away_team_id)
        JOIN tournaments t ON t.id = m.tournament_id
        JOIN rounds r ON r.id = t.round_id
    """,
    "vw_player_events": """
        CREATE VIEW vw_player_events AS
        SELECT x.player_id,
               x.match_id,
               m.tournament_id,
               t.round_id,
               r.date AS round_date,
               SUM(x.goals)::int AS goals,
               SUM(x.own_goals)::int AS own_goals,
               SUM(x.assists)::int AS assists,
               SUM(x.yellows)::int AS yellows,
               SUM(x.reds)::int AS reds
        FROM (
            SELECT player_id, match_id,
                   (type = 'GOL')::int AS goals,
                   (type = 'GOL_CONTRA')::int AS own_goals,
                   0 AS assists,
                   (type = 'AMARELO')::int AS yellows,
                   (type = 'VERMELHO')::int AS reds
            FROM match_events
            WHERE deleted_at IS NULL AND player_id IS NOT NULL
            UNION ALL
            SELECT assist_player_id, match_id, 0, 0, 1, 0, 0
            FROM match_events
            WHERE deleted_at IS NULL AND assist_player_id IS NOT NULL AND type = 'GOL'
        ) x
        JOIN matches m ON m.id = x.match_id
        JOIN tournaments t ON t.id = m.tournament_id
        JOIN rounds r ON r.id = t.round_id
        GROUP BY x.player_id, x.match_id, m.tournament_id, t.round_id, r.date
    """,
}


def fk(col: str, target: str, ondelete: str) -> sa.ForeignKey:
    return sa.ForeignKey(f"{target}.id", ondelete=ondelete, name=f"fk_match_events_{col}_{target}")


def upgrade() -> None:
    postgresql.ENUM(*EVENT_TYPES, name="match_event_type").create(op.get_bind(), checkfirst=True)
    op.create_table(
        "match_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("match_id", sa.BigInteger(), fk("match_id", "matches", "CASCADE"), nullable=False),
        sa.Column("client_event_id", sa.Uuid(), nullable=False),
        sa.Column("type", postgresql.ENUM(*EVENT_TYPES, name="match_event_type", create_type=False), nullable=False),
        sa.Column("team_id", sa.BigInteger(), fk("team_id", "teams", "CASCADE"), nullable=False),
        sa.Column("player_id", sa.BigInteger(), fk("player_id", "players", "RESTRICT")),
        sa.Column("assist_player_id", sa.BigInteger(), fk("assist_player_id", "players", "RESTRICT")),
        sa.Column("minute", sa.SmallInteger()),
        sa.Column("second", sa.SmallInteger()),
        sa.Column("auto_generated", sa.Boolean(), nullable=False),
        sa.Column("parent_event_id", sa.BigInteger(), fk("parent_event_id", "match_events", "CASCADE")),
        sa.Column("created_by", sa.BigInteger(), fk("created_by", "users", "SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("match_id", "client_event_id", name="uq_match_events_match_client"),
    )
    op.create_index("ix_match_events_match_id", "match_events", ["match_id"])
    op.create_index("ix_match_events_player_id", "match_events", ["player_id"])
    for sql in VIEWS_SQL.values():
        op.execute(sql)


def downgrade() -> None:
    for name in VIEWS_SQL:
        op.execute(f"DROP VIEW IF EXISTS {name}")
    op.drop_table("match_events")
    postgresql.ENUM(name="match_event_type").drop(op.get_bind(), checkfirst=True)
