"""financeiro: mensalidades, caixa e cobranças avulsas

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

CASH_KIND = ("ENTRADA", "SAIDA")
CASH_CATEGORY = ("DIARISTAS_COLETE", "CAMPO", "DIVERSOS", "OUTROS")


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(*CASH_KIND, name="cash_kind").create(bind, checkfirst=True)
    postgresql.ENUM(*CASH_CATEGORY, name="cash_category").create(bind, checkfirst=True)

    # Jogadores importados podem ficar com posição "a definir"
    op.alter_column("players", "primary_position", nullable=True)

    op.add_column("settings", sa.Column("monthly_fee", sa.Numeric(10, 2), nullable=False, server_default="50.00"))
    op.add_column(
        "settings", sa.Column("finance_opening_balance", sa.Numeric(10, 2), nullable=False, server_default="0.00")
    )
    op.add_column("settings", sa.Column("finance_opening_month", sa.Date()))

    op.create_table(
        "monthly_fees",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("player_id", sa.BigInteger(), sa.ForeignKey("players.id", ondelete="RESTRICT",
                  name="fk_monthly_fees_player_id_players"), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2)),
        sa.Column("marker", sa.String(20)),
        *timestamps(),
        sa.UniqueConstraint("player_id", "month", name="uq_monthly_fees_player_month"),
    )
    op.create_index("ix_monthly_fees_player_id", "monthly_fees", ["player_id"])
    op.create_index("ix_monthly_fees_month", "monthly_fees", ["month"])

    op.create_table(
        "cash_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("kind", postgresql.ENUM(*CASH_KIND, name="cash_kind", create_type=False), nullable=False),
        sa.Column("category", postgresql.ENUM(*CASH_CATEGORY, name="cash_category", create_type=False),
                  nullable=False),
        sa.Column("description", sa.String(200)),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_cash_entries_month", "cash_entries", ["month"])

    op.create_table(
        "finance_collections",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("amount_per_person", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "collection_items",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("collection_id", sa.BigInteger(), sa.ForeignKey("finance_collections.id", ondelete="CASCADE",
                  name="fk_collection_items_collection_id_finance_collections"), nullable=False),
        sa.Column("player_id", sa.BigInteger(), sa.ForeignKey("players.id", ondelete="SET NULL",
                  name="fk_collection_items_player_id_players")),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("paid", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_collection_items_collection_id", "collection_items", ["collection_id"])


def downgrade() -> None:
    op.drop_table("collection_items")
    op.drop_table("finance_collections")
    op.drop_table("cash_entries")
    op.drop_table("monthly_fees")
    op.drop_column("settings", "finance_opening_month")
    op.drop_column("settings", "finance_opening_balance")
    op.drop_column("settings", "monthly_fee")
    op.execute("UPDATE players SET primary_position = 'ALA' WHERE primary_position IS NULL")
    op.alter_column("players", "primary_position", nullable=False)
    bind = op.get_bind()
    postgresql.ENUM(name="cash_category").drop(bind, checkfirst=True)
    postgresql.ENUM(name="cash_kind").drop(bind, checkfirst=True)
