from fastapi import APIRouter, Response

from app.core.deps import SessionDep
from app.core.errors import NotFoundError
from app.models.media import MediaFile

router = APIRouter(prefix="/media", tags=["Mídia"])


@router.get("/{path:path}", include_in_schema=False)
async def media(path: str, session: SessionDep) -> Response:
    """Fotos públicas (usadas em <img>, sem token). O nome é um UUID: o conteúdo nunca muda, então o cache é longo."""
    file = await session.get(MediaFile, path)
    if file is None:
        raise NotFoundError("Arquivo não encontrado")
    headers = {"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"}
    if file.content_type == "image/svg+xml":
        # escudo SVG de terceiros: aberto direto no navegador, não executa nada
        headers["Content-Security-Policy"] = "sandbox; default-src 'none'; style-src 'unsafe-inline'"
    return Response(file.content, media_type=file.content_type, headers=headers)
