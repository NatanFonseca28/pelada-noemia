"""catálogo de clubes por campeonato (football-data.org) e sigla/escudo nos times do sorteio

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_competitions",
        sa.Column("code", sa.String(10), primary_key=True),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("season", sa.SmallInteger(), nullable=True),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "catalog_clubs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("competition_code", sa.String(10),
                  sa.ForeignKey("catalog_competitions.code", ondelete="CASCADE"), nullable=False),
        sa.Column("api_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("tla", sa.String(5), nullable=False),
        sa.Column("color", sa.String(9), nullable=False),
        sa.Column("crest_url", sa.String(255), nullable=True),
        sa.Column("crest_path", sa.String(200), nullable=True),
        sa.UniqueConstraint("competition_code", "api_id", name=op.f("uq_catalog_clubs_competition_code_api")),
    )
    op.create_index(op.f("ix_catalog_clubs_competition_code"), "catalog_clubs", ["competition_code"])
    op.add_column("teams", sa.Column("abbr", sa.String(5), nullable=True))
    op.add_column("teams", sa.Column("crest_path", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("teams", "crest_path")
    op.drop_column("teams", "abbr")
    op.drop_index(op.f("ix_catalog_clubs_competition_code"), table_name="catalog_clubs")
    op.drop_table("catalog_clubs")
    op.drop_table("catalog_competitions")
