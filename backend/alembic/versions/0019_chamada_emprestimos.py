"""chamada no local (presença confirmada x presente) e empréstimos gravados das partidas encerradas

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attendances", sa.Column("checkin", sa.String(10), nullable=True))
    op.add_column("attendances", sa.Column("checkin_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(op.f("ck_attendances_checkin_values"), "attendances",
                               "checkin IN ('PRESENTE', 'FALTOU')")
    op.create_table(
        "match_loans",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("match_id", sa.BigInteger(), sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.BigInteger(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.BigInteger(), sa.ForeignKey("players.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("from_team_id", sa.BigInteger(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("replaces_id", sa.BigInteger(), sa.ForeignKey("players.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("strength_delta", sa.Numeric(4, 2), nullable=False, server_default="0"),
        sa.UniqueConstraint("match_id", "player_id", name=op.f("uq_match_loans_match_player")),
    )
    op.create_index(op.f("ix_match_loans_match_id"), "match_loans", ["match_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_match_loans_match_id"), table_name="match_loans")
    op.drop_table("match_loans")
    op.drop_constraint(op.f("ck_attendances_checkin_values"), "attendances", type_="check")
    op.drop_column("attendances", "checkin_at")
    op.drop_column("attendances", "checkin")
