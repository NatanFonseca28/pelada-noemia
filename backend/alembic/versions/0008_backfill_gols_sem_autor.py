"""placares lançados antes da súmula viram gols sem autor

Partidas com placar e sem eventos (criadas antes da 0007) recebem eventos GOL sem jogador,
para que o placar continue igual quando a súmula passar a ser a fonte do placar.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-06
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for side in ("home", "away"):
        op.execute(f"""
            INSERT INTO match_events (match_id, client_event_id, type, team_id, auto_generated, created_at)
            SELECT m.id, gen_random_uuid(), 'GOL', m.{side}_team_id, true, COALESCE(m.ended_at, now())
            FROM matches m
            CROSS JOIN LATERAL generate_series(1, m.{side}_score) AS g
            WHERE m.{side}_score > 0
              AND m.{side}_team_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM match_events e WHERE e.match_id = m.id AND NOT e.auto_generated)
        """)


def downgrade() -> None:
    op.execute("DELETE FROM match_events WHERE auto_generated AND player_id IS NULL")
