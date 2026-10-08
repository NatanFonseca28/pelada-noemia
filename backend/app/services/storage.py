"""Armazenamento de fotos. A imagem é validada pelo CONTEÚDO (Pillow), não pelo Content-Type enviado pelo cliente,
e é regravada como WEBP: isso descarta metadados (EXIF/GPS) e qualquer conteúdo embutido no arquivo original."""
import uuid
from io import BytesIO

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.models.media import MediaFile

ACCEPTED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_SIDE = 1024  # px: fotos de perfil não precisam de mais
Image.MAX_IMAGE_PIXELS = 40_000_000  # recusa "bombas de descompressão"


async def read_limited(file: UploadFile, max_bytes: int, label: str) -> bytes:
    """Lê o upload em blocos e aborta assim que passar do limite (não carrega arquivos gigantes na memória)."""
    chunks, total = [], 0
    while chunk := await file.read(64 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise ValidationError(f"{label} maior que {max_bytes // (1024 * 1024)} MB")
        chunks.append(chunk)
    return b"".join(chunks)


def sanitize_image(content: bytes, max_side: int = MAX_SIDE) -> bytes:
    """Valida e regrava a imagem como WEBP sem metadados, com no máximo `max_side` px de lado."""
    try:
        with Image.open(BytesIO(content)) as probe:
            fmt = probe.format
            probe.verify()  # estrutura do arquivo
        if fmt not in ACCEPTED_FORMATS:
            raise ValidationError("Formato de imagem não suportado (use JPG, PNG ou WEBP)")
        with Image.open(BytesIO(content)) as img:  # verify() invalida o objeto: reabre para decodificar
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
            img.thumbnail((max_side, max_side))
            out = BytesIO()
            img.save(out, format="WEBP", quality=85, method=4)  # sem exif= → metadados descartados
            return out.getvalue()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise ValidationError("Arquivo não é uma imagem válida (use JPG, PNG ou WEBP)") from exc


def save_photo(session: AsyncSession, content: bytes, folder: str = "players") -> str:
    """Sanitiza e guarda a imagem no banco (vai junto no commit de quem chamou); retorna o caminho relativo."""
    relative = f"{folder}/{uuid.uuid4().hex}.webp"
    session.add(MediaFile(path=relative, content_type="image/webp", content=sanitize_image(content)))
    return relative


async def delete_file(session: AsyncSession, relative: str | None) -> None:
    """Remove o arquivo (vai junto no commit de quem chamou)."""
    if relative:
        await session.execute(delete(MediaFile).where(MediaFile.path == relative))
