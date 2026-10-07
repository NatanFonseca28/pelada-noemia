"""tipo de jogador ISENTO: goleiro fixo não é mensalista nem diarista

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-07
"""
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Recria o enum (em vez de ADD VALUE) para poder usar o valor novo na mesma transação
    op.execute("ALTER TYPE player_type RENAME TO player_type_old")
    op.execute("CREATE TYPE player_type AS ENUM ('MENSALISTA', 'DIARISTA', 'ISENTO')")
    op.execute(
        "ALTER TABLE players ALTER COLUMN type TYPE player_type USING ("
        "CASE WHEN primary_position = 'GOLEIRO_FIXO' THEN 'ISENTO' ELSE type::text END)::player_type"
    )
    op.execute("DROP TYPE player_type_old")


def downgrade() -> None:
    op.execute("ALTER TYPE player_type RENAME TO player_type_old")
    op.execute("CREATE TYPE player_type AS ENUM ('MENSALISTA', 'DIARISTA')")
    op.execute(
        "ALTER TABLE players ALTER COLUMN type TYPE player_type USING ("
        "CASE WHEN type::text = 'ISENTO' THEN 'DIARISTA' ELSE type::text END)::player_type"
    )
    op.execute("DROP TYPE player_type_old")
