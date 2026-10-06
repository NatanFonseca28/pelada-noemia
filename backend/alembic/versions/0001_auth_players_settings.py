"""auth, jogadores, configurações e auditoria

Revision ID: 0001
Revises:
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

ENUMS = {
    "user_role": ("ADMIN", "MESARIO", "JOGADOR"),
    "user_status": ("PENDENTE", "ATIVO", "BLOQUEADO"),
    "player_type": ("MENSALISTA", "DIARISTA"),
    "player_position": ("ZAGUEIRO", "ALA", "ATACANTE", "GOLEIRO_FIXO"),
    "knockout_tie_rule": ("PENALTIS", "MELHOR_CAMPANHA", "GOL_DE_OURO"),
    "top_scorer_tiebreak": ("DIVIDIDA", "MAIS_ASSISTENCIAS", "MENOS_JOGOS", "SORTEIO"),
    "red_card_rule": ("NENHUMA", "PROXIMA_PARTIDA", "RESTO_CAMPEONATO"),
}


def enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    op.create_table(
        "players",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("nickname", sa.String(60)),
        sa.Column("photo_path", sa.String(255)),
        sa.Column("type", enum("player_type"), nullable=False),
        sa.Column("primary_position", enum("player_position"), nullable=False),
        sa.Column("secondary_position", enum("player_position")),
        sa.Column("skill_level", sa.SmallInteger()),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        *timestamps(),
        sa.CheckConstraint("skill_level BETWEEN 1 AND 5", name="ck_players_skill_level_range"),
        sa.CheckConstraint(
            "secondary_position IS NULL OR secondary_position <> primary_position",
            name="ck_players_secondary_differs",
        ),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("role", enum("user_role"), nullable=False),
        sa.Column("status", enum("user_status"), nullable=False),
        sa.Column("player_id", sa.BigInteger(), sa.ForeignKey("players.id", ondelete="SET NULL",
                  name="fk_users_player_id_players")),
        sa.Column("approved_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL",
                  name="fk_users_approved_by_users")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.UniqueConstraint("player_id", name="uq_users_player_id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE",
                  name="fk_refresh_tokens_user_id_users"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("replaced_by_id", sa.BigInteger(), sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL",
                  name="fk_refresh_tokens_replaced_by_id_refresh_tokens")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("total_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("line_players_per_team", sa.SmallInteger(), nullable=False),
        sa.Column("balance_by_skill", sa.Boolean(), nullable=False),
        sa.Column("extra_team_threshold", sa.SmallInteger(), nullable=False),
        sa.Column("changeover_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("min_match_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("final_weight", sa.Numeric(3, 2), nullable=False),
        sa.Column("points_win", sa.SmallInteger(), nullable=False),
        sa.Column("points_draw", sa.SmallInteger(), nullable=False),
        sa.Column("points_loss", sa.SmallInteger(), nullable=False),
        sa.Column("tiebreakers", postgresql.JSONB(), nullable=False),
        sa.Column("knockout_tie_rule", enum("knockout_tie_rule"), nullable=False),
        sa.Column("top_scorer_tiebreak", enum("top_scorer_tiebreak"), nullable=False),
        sa.Column("casual_goal_limit", sa.SmallInteger(), nullable=False),
        sa.Column("casual_match_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("red_card_rule", enum("red_card_rule"), nullable=False),
        sa.Column("two_yellows_red", sa.Boolean(), nullable=False),
        *timestamps(),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL",
                  name="fk_audit_logs_user_id_users")),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(40)),
        sa.Column("before", postgresql.JSONB()),
        sa.Column("after", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    for table in ("audit_logs", "settings", "refresh_tokens", "users", "players"):
        op.drop_table(table)
    bind = op.get_bind()
    for name in ENUMS:
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
