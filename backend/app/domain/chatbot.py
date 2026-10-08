"""Chatbot de cobrança pelo WhatsApp: texto da cobrança, menu, interpretação das respostas (regras puras).

A conversa é por menu numerado para ser previsível; algumas palavras óbvias também valem ("paguei", "pix").
"""
import re
import unicodedata
from datetime import date
from decimal import Decimal
from enum import StrEnum

MONTH_ABBR = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# Envio: intervalo aleatório entre mensagens e limites anti-bloqueio
MIN_GAP_SECONDS = 25
MAX_GAP_SECONDS = 60
CHARGE_COOLDOWN_DAYS = 3
MENU_RESEND_HOURS = 24


class Intent(StrEnum):
    PIX = "PIX"
    PAID = "PAID"
    OUT = "OUT"
    TALK = "TALK"
    PROOF = "PROOF"  # mandou imagem/documento (comprovante)
    OTHER = "OTHER"


def money(value: Decimal | float | int) -> str:
    s = f"{Decimal(value):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def months_text(months: list[date]) -> str:
    names = [MONTH_ABBR[m.month - 1] for m in months]
    return f"{', '.join(names[:-1])} e {names[-1]}" if len(names) > 1 else "".join(names)


def charge_values(name: str, months: list[date], amount: Decimal, monthly_fee: Decimal, pix: str | None,
                  gestor: str) -> dict[str, str]:
    """Mesmas variáveis da tela de configuração (frontend/src/lib/charge.ts)."""
    return {
        "nome": name,
        "meses": months_text(months),
        "valor": money(amount),
        "mensalidade": money(monthly_fee),
        "pix": pix or "(peça a chave Pix)",
        "gestor": gestor,
    }


def render(template: str, values: dict[str, str]) -> str:
    return re.sub(r"\{([^{}]+)\}", lambda m: values.get(m.group(1), m.group(0)), template)


def menu_text(gestor: str) -> str:
    return (
        "Responda com o número:\n"
        "1 – Pix copia e cola\n"
        "2 – Já paguei (mande o comprovante)\n"
        "3 – Não vou jogar este mês\n"
        f"4 – Falar com o {gestor}"
    )


def _plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower().strip()


def parse_reply(text: str | None, has_media: bool = False) -> Intent:
    if has_media:
        return Intent.PROOF
    t = _plain(text or "")
    if not t:
        return Intent.OTHER
    first = re.match(r"^\s*([1-4])\b", t)
    if first:
        return {"1": Intent.PIX, "2": Intent.PAID, "3": Intent.OUT, "4": Intent.TALK}[first.group(1)]
    if re.search(r"\b(ja )?pag(uei|o|ei)\b|\bcomprovante\b|\bfiz o pix\b|\btransferi\b", t):
        return Intent.PAID
    if re.search(r"\bpix\b|\bchave\b|copia e cola", t):
        return Intent.PIX
    if re.search(r"nao vou|\bfora\b|nao jogo|nao vou jogar", t):
        return Intent.OUT
    if re.search(r"\bfalar\b|\bligar\b|\bgestor\b|\badmin\b", t):
        return Intent.TALK
    return Intent.OTHER


def phone_variants(e164: str) -> set[str]:
    """Só dígitos, com e sem o 9 do celular brasileiro: contas antigas do WhatsApp usam o número sem o 9."""
    digits = re.sub(r"\D", "", e164)
    out = {digits}
    if digits.startswith("55") and len(digits) == 13 and digits[4] == "9":
        out.add(digits[:4] + digits[5:])
    elif digits.startswith("55") and len(digits) == 12 and digits[4] in "6789":
        out.add(digits[:4] + "9" + digits[4:])
    return out


def jid_digits(jid: str | None) -> str | None:
    """'5521987654321@s.whatsapp.net' → '5521987654321'. Grupos e listas de transmissão → None."""
    if not jid or not jid.endswith("@s.whatsapp.net"):
        return None
    return jid.split("@", 1)[0].split(":", 1)[0]
