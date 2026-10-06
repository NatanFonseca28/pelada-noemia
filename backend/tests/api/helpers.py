from io import BytesIO

from PIL import Image


def image_bytes(fmt: str = "PNG", size=(64, 48), exif: bytes | None = None) -> bytes:
    """Imagem real em memória (para testar upload)."""
    buf = BytesIO()
    img = Image.new("RGB", size, (31, 122, 61))
    kwargs = {"exif": exif} if exif else {}
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()
