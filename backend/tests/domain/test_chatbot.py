from datetime import date
from decimal import Decimal

import pytest

from app.domain.chatbot import Intent, charge_values, jid_digits, months_text, parse_reply, phone_variants, render
from app.domain.charge_message import DEFAULT_CHARGE_MESSAGE
from app.domain.pix import crc16, pix_copy_paste


def test_crc16_ccitt_vetor_padrao():
    assert crc16("123456789") == "29B1"


def test_pix_copia_e_cola_bem_formado():
    code = pix_copy_paste("pelada@exemplo.com", Decimal("100"), "Natan Fonsêca", "Rio de Janeiro")
    assert code.startswith("000201") and "br.gov.bcb.pix" in code
    assert "5406100.00" in code and "5303986" in code and "5802BR" in code
    assert "5913NATAN FONSECA" in code and "6014RIO DE JANEIRO" in code
    assert code[-8:-4] == "6304" and code[-4:] == crc16(code[:-4])


def test_texto_da_cobranca_igual_ao_do_front():
    values = charge_values("Daniel", [date(2026, 9, 1), date(2026, 10, 1)], Decimal("100"), Decimal("50"),
                           "pix@pelada", "Natan")
    text = render(DEFAULT_CHARGE_MESSAGE, values)
    assert text == ("Fala, Daniel! Aqui é o Natan, da pelada de quarta. Passando pra lembrar da mensalidade: "
                    "set e out em aberto, total de R$ 100,00. Pix: pix@pelada. Valeu! ⚽")
    assert months_text([date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]) == "jan, fev e mar"


@pytest.mark.parametrize(("text", "media", "intent"), [
    ("1", False, Intent.PIX), (" 2 ", False, Intent.PAID), ("3", False, Intent.OUT), ("4 por favor", False, Intent.TALK),
    ("Já paguei!", False, Intent.PAID), ("fiz o pix ontem", False, Intent.PAID), ("manda a chave pix", False, Intent.PIX),
    ("Não vou jogar esse mês", False, Intent.OUT), ("quero falar com o gestor", False, Intent.TALK),
    ("blz", False, Intent.OTHER), ("", True, Intent.PROOF), (None, False, Intent.OTHER), ("12345", False, Intent.OTHER),
])
def test_interpreta_respostas(text, media, intent):
    assert parse_reply(text, media) == intent


def test_telefone_com_e_sem_o_nove():
    assert phone_variants("+5521987654321") == {"5521987654321", "552187654321"}
    assert phone_variants("+552187654321") == {"552187654321", "5521987654321"}
    assert phone_variants("+552133334444") == {"552133334444"}  # fixo: sem variação
    assert jid_digits("5521987654321@s.whatsapp.net") == "5521987654321"
    assert jid_digits("120363000000@g.us") is None and jid_digits(None) is None
