import jwt
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_hash_e_verificacao_de_senha():
    h = hash_password("segredo")
    assert h.startswith("$argon2")
    assert verify_password("segredo", h)
    assert not verify_password("outra", h)
    assert not verify_password("segredo", "hash-invalido")


def test_access_token_roundtrip():
    payload = decode_access_token(create_access_token(7, "ADMIN"))
    assert payload["sub"] == "7" and payload["role"] == "ADMIN"


def test_access_token_adulterado():
    token = create_access_token(1, "JOGADOR")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token[:-2] + "xx")


def test_refresh_hash_deterministico():
    assert hash_refresh_token("abc") == hash_refresh_token("abc") != hash_refresh_token("abd")
