import pytest

from app.domain.phone import PhoneError, normalize_phone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("(21) 98765-4321", "+5521987654321"),
        ("21987654321", "+5521987654321"),
        ("+55 21 98765-4321", "+5521987654321"),
        ("5521987654321", "+5521987654321"),
        ("(11) 3456-7890", "+551134567890"),  # fixo
        ("+351 912 345 678", "+351912345678"),  # exterior
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_normaliza_para_e164(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize(
    ("raw", "msg"),
    [
        ("(20) 98765-4321", "DDD 20"),  # DDD inexistente
        ("(21) 88765-4321", "começar com 9"),  # celular sem o 9 na frente
        ("(21) 8765-432", r"DDD \+ número"),  # curto
        ("2198765432199", r"DDD \+ número"),  # longo
        ("+1 23", "8 a 15"),
    ],
)
def test_recusa_numeros_invalidos(raw, msg):
    with pytest.raises(PhoneError, match=msg):
        normalize_phone(raw)
