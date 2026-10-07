"""Mensagem de cobrança por WhatsApp: variáveis permitidas e validação (sem banco, testável)."""
import re

DEFAULT_CHARGE_MESSAGE = (
    "Fala, {nome}! Aqui é o {gestor}, da pelada de quarta. Passando pra lembrar da mensalidade: "
    "{meses} em aberto, total de {valor}. Pix: {pix}. Valeu! ⚽"
)

# variável → o que ela vira (mostrado como instrução na tela do superadmin)
CHARGE_VARIABLES: dict[str, str] = {
    "nome": "Apelido (ou nome) do jogador",
    "meses": "Meses em aberto, ex.: set e out",
    "valor": "Total devido, ex.: R$ 100,00",
    "mensalidade": "Valor da mensalidade, ex.: R$ 50,00",
    "pix": "A chave Pix configurada",
    "gestor": "Primeiro nome de quem está cobrando",
}

MAX_LENGTH = 1000
_VAR = re.compile(r"\{([^{}]*)\}")


def validate_charge_message(text: str) -> str:
    text = text.strip()
    if not text:
        raise ValueError("Escreva a mensagem de cobrança")
    if len(text) > MAX_LENGTH:
        raise ValueError(f"A mensagem pode ter no máximo {MAX_LENGTH} caracteres")
    unknown = sorted({v for v in _VAR.findall(text) if v not in CHARGE_VARIABLES})
    if unknown:
        listed = ", ".join("{" + v + "}" for v in unknown)
        raise ValueError(f"Variável desconhecida: {listed}. Use só as da tabela, entre chaves.")
    if text.count("{") != text.count("}"):
        raise ValueError("Há uma chave { ou } sem par. As variáveis vão entre chaves, ex.: {nome}")
    return text
