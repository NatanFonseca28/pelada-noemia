"""Views de estatísticas (criadas na migration 0007; mudanças exigem nova migration).

Ficam num MetaData separado: não entram no create_all/alembic check, só servem para consultas.
"""
from sqlalchemy import BigInteger, Column, Date, Integer, MetaData, String, Table

views_metadata = MetaData()

# Uma linha por jogador × partida encerrada que ele disputou (pelo time em que estava na rodada)
vw_player_matches = Table(
    "vw_player_matches",
    views_metadata,
    Column("player_id", BigInteger),
    Column("match_id", BigInteger),
    Column("tournament_id", BigInteger),
    Column("round_id", BigInteger),
    Column("round_date", Date),
    Column("team_id", BigInteger),
    Column("stage", String),
    Column("goals_for", Integer),
    Column("goals_against", Integer),
)

# Uma linha por jogador × partida com seus números (gols, contra, assistências, cartões)
vw_player_events = Table(
    "vw_player_events",
    views_metadata,
    Column("player_id", BigInteger),
    Column("match_id", BigInteger),
    Column("tournament_id", BigInteger),
    Column("round_id", BigInteger),
    Column("round_date", Date),
    Column("goals", Integer),
    Column("own_goals", Integer),
    Column("assists", Integer),
    Column("yellows", Integer),
    Column("reds", Integer),
)

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
