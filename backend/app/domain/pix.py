"""Pix copia-e-cola (BR Code estático), conforme o Manual de Padrões para Iniciação do Pix (Banco Central).

Formato EMV: campos ID(2) + tamanho(2) + valor, terminado pelo CRC16-CCITT (0x1021, inicial 0xFFFF).
"""
import unicodedata
from decimal import Decimal


def _field(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"


def _ascii(text: str, limit: int) -> str:
    """Nome/cidade do recebedor: sem acentos, maiúsculas, no tamanho máximo do padrão."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "".join(c for c in plain.upper() if c.isalnum() or c == " ").strip()[:limit] or "PELADA"


def crc16(payload: str) -> str:
    crc = 0xFFFF
    for byte in payload.encode():
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def pix_copy_paste(key: str, amount: Decimal | None, name: str, city: str, txid: str = "***",
                   message: str | None = None) -> str:
    account = _field("00", "br.gov.bcb.pix") + _field("01", key.strip())
    if message:
        account += _field("02", message[:40])
    payload = (
        _field("00", "01")
        + _field("26", account)
        + _field("52", "0000")
        + _field("53", "986")  # real
        + (_field("54", f"{amount:.2f}") if amount else "")
        + _field("58", "BR")
        + _field("59", _ascii(name, 25))
        + _field("60", _ascii(city, 15))
        + _field("62", _field("05", txid[:25]))
        + "6304"
    )
    return payload + crc16(payload)
