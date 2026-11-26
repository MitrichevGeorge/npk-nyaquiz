import json

from shared.errors import build_error_response
from shared.security import (
    decrypt_secret,
    encrypt_secret,
    generate_totp_secret,
    hash_password,
    verify_password,
    verify_totp,
)


def test_argon2id_password_roundtrip():
    hashed = hash_password("VeryStrongPassphrase123!")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "VeryStrongPassphrase123!") is True
    assert verify_password(hashed, "wrong") is False


def test_secret_encryption_roundtrip():
    secret = generate_totp_secret()
    enc = encrypt_secret(secret)
    assert enc != secret
    assert decrypt_secret(enc) == secret


def test_totp_rejects_invalid_format():
    secret = generate_totp_secret()
    assert verify_totp(secret, "abcdef") is False
    assert verify_totp(secret, "123") is False


def test_error_response_has_no_internal_leaks():
    response = build_error_response("INTERNAL_ERROR", 500, "ru", "req-123")
    body = json.loads(response.body.decode("utf-8"))
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"code", "message", "request_id"}
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["error"]["request_id"] == "req-123"
    serialized = json.dumps(body).lower()
    for forbidden in ("traceback", "select ", "sqlalchemy", "/app/"):
        assert forbidden not in serialized
