"""Normalização de telefone para E.164 (formato exigido por APIs de WhatsApp). Puro e testável."""
import re

# DDDs válidos no Brasil
BR_DDD = {
    11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28, 31, 32, 33, 34, 35, 37, 38, 41, 42, 43, 44, 45, 46, 47, 48,
    49, 51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68, 69, 71, 73, 74, 75, 77, 79, 81, 82, 83, 84, 85, 86, 87, 88, 89,
    91, 92, 93, 94, 95, 96, 97, 98, 99,
}


class PhoneError(ValueError):
    pass


def _br(national: str) -> str:
    """national = DDD + número (10 ou 11 dígitos)."""
    ddd, number = int(national[:2]), national[2:]
    if ddd not in BR_DDD:
        raise PhoneError(f"DDD {national[:2]} não existe")
    if len(number) == 9 and number[0] != "9":
        raise PhoneError("Celular com 9 dígitos deve começar com 9")
    if len(number) == 8 and number[0] not in "2345":
        raise PhoneError("Número fixo inválido (ou falta o 9 do celular)")
    return f"+55{national}"


def normalize_phone(raw: str | None) -> str | None:
    """Aceita "(21) 98765-4321", "21987654321", "+55 21 98765-4321" ou E.164 estrangeiro. Vazio → None."""
    if raw is None or not raw.strip():
        return None
    text = raw.strip()
    digits = re.sub(r"\D", "", text)
    if text.startswith("+"):
        if digits.startswith("55"):
            if len(digits) not in (12, 13):
                raise PhoneError("Número brasileiro deve ter DDD + 8 ou 9 dígitos")
            return _br(digits[2:])
        if not 8 <= len(digits) <= 15:
            raise PhoneError("Número internacional deve ter de 8 a 15 dígitos")
        return f"+{digits}"
    if digits.startswith("55") and len(digits) in (12, 13):
        return _br(digits[2:])
    if len(digits) in (10, 11):
        return _br(digits)
    raise PhoneError("Informe DDD + número, ex.: (21) 98765-4321")


def normalize_mobile(raw: str | None) -> str:
    """Celular obrigatório (cadastro): no Brasil, DDD + 9 dígitos começando com 9."""
    phone = normalize_phone(raw)
    if phone is None:
        raise PhoneError("Informe seu celular com DDD")
    if phone.startswith("+55") and len(phone) != 14:
        raise PhoneError("Informe um celular (9 dígitos depois do DDD), não um telefone fixo")
    return phone
