from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MediaFile(Base):
    """Arquivo enviado (hoje só fotos de jogador, já sanitizadas em WEBP). Fica no banco para sobreviver a
    deploys em plataformas com disco efêmero (Render) e entrar nos backups junto com os dados."""

    __tablename__ = "media_files"

    path: Mapped[str] = mapped_column(String(200), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(50))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
