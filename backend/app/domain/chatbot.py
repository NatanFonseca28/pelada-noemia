"""Chatbot de cobrança pelo WhatsApp: texto da cobrança, menu, interpretação das respostas (regras puras).

A conversa é por menu numerado para ser previsível; algumas palavras óbvias também valem ("paguei", "pix").
"""
import re
import unicodedata
from datetime import date
from decimal import Decimal
from enum import StrEnum

MONTH_ABBR = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

CHARGE_COOLDOWN_DAYS = 3  # no máximo 1 cobrança a cada 3 dias por jogador
MENU_RESEND_HOURS = 24
SESSION_WINDOW_HOURS = 24  # Meta: texto livre só até 24 h depois da última mensagem do jogador

# Botões de resposta rápida do modelo de cobrança (payload → intenção), na ordem do modelo
BUTTONS = ["PIX", "PAGO", "FORA", "FALAR"]


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


def payload_intent(payload: str | None) -> "Intent | None":
    """Botão do modelo (payload) ou botão interativo (id)."""
    return {"PIX": Intent.PIX, "PAGO": Intent.PAID, "FORA": Intent.OUT, "FALAR": Intent.TALK}.get(
        (payload or "").strip().upper())


def template_params(values: dict[str, str]) -> list[str]:
    """Parâmetros do modelo de cobrança, na ordem {{1}}..{{5}}: nome, gestor, meses, valor, pix."""
    return [values["nome"], values["gestor"], values["meses"], values["valor"], values["pix"]]


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


# Modelos enviados à Meta para aprovação (categoria utilidade). O texto da cobrança é o mesmo da mensagem manual.
TEMPLATES = [
    {
        "name": "cobranca_mensalidade",
        "category": "UTILITY",
        "body": ("Fala, {{1}}! Aqui é o {{2}}, da pelada de quarta. Passando pra lembrar da mensalidade: "
                 "{{3}} em aberto, total de {{4}}. Pix: {{5}}. Valeu! ⚽"),
        "example": ["Daniel", "Natan", "set e out", "R$ 100,00", "pix@pelada.com"],
        "buttons": ["Pix copia e cola", "Já paguei", "Não vou jogar", "Falar com o gestor"],
    },
    {
        "name": "pagamento_confirmado",
        "category": "UTILITY",
        "body": "Pagamento da mensalidade confirmado ✅ ({{1}}). Valeu!",
        "example": ["set e out"],
        "buttons": [],
    },
]


def template_definition(t: dict, language: str = "pt_BR") -> dict:
    """Corpo da criação do modelo na API da Meta (POST /{waba_id}/message_templates)."""
    components: list[dict] = [{"type": "BODY", "text": t["body"], "example": {"body_text": [t["example"]]}}]
    if t["buttons"]:
        components.append({"type": "BUTTONS",
                           "buttons": [{"type": "QUICK_REPLY", "text": b} for b in t["buttons"]]})
    return {"name": t["name"], "language": language, "category": t["category"], "components": components}
