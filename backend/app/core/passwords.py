"""Política de senha para senhas NOVAS (cadastro, criação por admin, troca). Senhas antigas seguem válidas até a troca."""
from typing import Annotated

from pydantic import AfterValidator, Field

MIN_LENGTH = 10

# Senhas mais comuns em vazamentos (amostra) + variações óbvias do contexto do sistema
COMMON = {
    "1234567890", "12345678910", "123456789a", "0123456789", "1111111111", "0000000000", "qwertyuiop",
    "password123", "password1234", "senha12345", "senha123456", "senhasenha", "mudar12345", "trocar1234",
    "iloveyou12", "abcdefghij", "abc1234567", "a1b2c3d4e5", "qwerty1234", "asdfghjkl1", "zaq12wsxcde",
    "futebol123", "futebol1234", "pelada1234", "pelada12345", "peladadequarta", "quarta1234", "society123",
    "flamengo123", "corinthians", "palmeiras123", "saopaulo123", "vasco12345", "gremio12345", "brasil1234",
    "admin12345", "administrador", "mesario123", "jogador123", "jogador1234", "bemvindo123", "welcome123",
}


def check_password(password: str) -> str:
    low = password.lower()
    if len(password) < MIN_LENGTH:
        raise ValueError(f"A senha precisa ter pelo menos {MIN_LENGTH} caracteres")
    if low in COMMON or low.rstrip("!@#$%.") in COMMON:
        raise ValueError("Essa senha é muito comum. Escolha outra")
    if len(set(password)) < 4:
        raise ValueError("Use uma senha com mais variedade de caracteres")
    if low.isdigit() and (low in "01234567890123456789" or low in "98765432109876543210"):
        raise ValueError("Evite sequências como 1234567890")
    return password


StrongPassword = Annotated[str, Field(min_length=1, max_length=128), AfterValidator(check_password)]
