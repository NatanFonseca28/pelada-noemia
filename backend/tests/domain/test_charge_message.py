import pytest

from app.domain.charge_message import DEFAULT_CHARGE_MESSAGE, validate_charge_message


def test_padrao_e_valido_e_mantem_quebras_e_emoji():
    assert validate_charge_message(DEFAULT_CHARGE_MESSAGE) == DEFAULT_CHARGE_MESSAGE
    text = "Oi {nome}!\nDeve {valor} ⚽"
    assert validate_charge_message(f"  {text}  ") == text


@pytest.mark.parametrize(
    ("text", "msg"),
    [
        ("Oi {nome}, pague {valr}", r"\{valr\}"),
        ("Oi {Nome}", r"\{Nome\}"),
        ("Oi {nome", "sem par"),
        ("   ", "Escreva"),
        ("x" * 1001, "1000"),
    ],
)
def test_recusa_mensagens_invalidas(text, msg):
    with pytest.raises(ValueError, match=msg):
        validate_charge_message(text)
