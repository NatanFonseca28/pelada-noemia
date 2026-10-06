"""fotos no banco (media_files) — importa as que estavam em MEDIA_DIR

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-06
"""
from pathlib import Path

import sqlalchemy as sa

from alembic import op
from app.core.config import get_settings

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    media = op.create_table(
        "media_files",
        sa.Column("path", sa.String(200), primary_key=True),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Fotos que já existiam no disco passam para o banco; as que faltarem viram "sem foto"
    conn = op.get_bind()
    media_dir = Path(get_settings().media_dir)
    rows = []
    for (path,) in conn.execute(sa.text("SELECT photo_path FROM players WHERE photo_path IS NOT NULL")):
        file = media_dir / path
        if file.is_file():
            rows.append({"path": path, "content_type": "image/webp", "content": file.read_bytes()})
        else:
            conn.execute(sa.text("UPDATE players SET photo_path = NULL WHERE photo_path = :p"), {"p": path})
    if rows:
        op.bulk_insert(media, rows)


def downgrade() -> None:
    op.drop_table("media_files")
