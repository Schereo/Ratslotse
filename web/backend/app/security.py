"""Password hashing and JWT helpers, implemented with the standard library only.

Avoiding bcrypt/passlib/cryptography keeps the backend dependency-light and
portable. Passwords use scrypt (memory-hard, stdlib via hashlib); session
tokens are HS256 JWTs signed with hmac.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from .config import get_settings

# --- password hashing (scrypt) ----------------------------------------------
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 32


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_DKLEN
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, hash_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(hash_hex) // 2,
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


# --- JWT (HS256) -------------------------------------------------------------
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(message: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(sig)


def create_access_token(
    subject: str | int, token_version: int = 0, expires_minutes: int | None = None
) -> str:
    settings = get_settings()
    minutes = settings.access_token_expire_minutes if expires_minutes is None else expires_minutes
    exp = int(time.time()) + minutes * 60
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url_encode(
        json.dumps({"sub": str(subject), "exp": exp, "ver": token_version}).encode()
    )
    signing_input = f"{header}.{payload}".encode()
    signature = _sign(signing_input, settings.web_jwt_secret)
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str) -> tuple[str, int] | None:
    """Return (subject, token_version) or None if the token is invalid/expired."""
    settings = get_settings()
    try:
        header_b64, payload_b64, signature = token.split(".")
    except ValueError:
        return None
    expected = _sign(f"{header_b64}.{payload_b64}".encode(), settings.web_jwt_secret)
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    return sub, int(payload.get("ver", 0))
