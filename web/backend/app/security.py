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


# --- RS256-Verifikation (Sign in with Apple, RL-1002) ------------------------
# Nur VERIFIKATION eines fremden RSA-Signums (öffentlicher Schlüssel aus dem
# Apple-JWKS) — dafür reicht die Schulbuch-Formel sig^e mod n plus der
# deterministische EMSA-PKCS1-v1_5-Vergleich. Bewusst stdlib-pur, wie der
# Rest dieses Moduls; es gibt hier keine Geheimnis-Operationen.

# DigestInfo-Präfix für SHA-256 (RFC 8017, EMSA-PKCS1-v1_5).
_SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


def _rsa_verify_pkcs1_sha256(message: bytes, signature: bytes, n: int, e: int) -> bool:
    k = (n.bit_length() + 7) // 8
    if len(signature) != k:
        return False
    em = pow(int.from_bytes(signature, "big"), e, n).to_bytes(k, "big")
    expected = (
        b"\x00\x01"
        + b"\xff" * (k - 3 - len(_SHA256_DIGEST_INFO) - 32)
        + b"\x00"
        + _SHA256_DIGEST_INFO
        + hashlib.sha256(message).digest()
    )
    return hmac.compare_digest(em, expected)


def decode_rs256_token(token: str, jwks_keys: list[dict]) -> dict | None:
    """Verify an RS256 JWT against a JWKS key list and return its payload.

    Checks signature (kid-matched key), and ``exp``. Issuer/audience checks are
    the caller's job — they're deployment-specific. Returns None on any failure.
    """
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
        signature = _b64url_decode(signature_b64)
    except (ValueError, json.JSONDecodeError):
        return None
    if header.get("alg") != "RS256":
        return None
    key = next((k for k in jwks_keys if k.get("kid") == header.get("kid")), None)
    if not key or key.get("kty") != "RSA":
        return None
    try:
        n = int.from_bytes(_b64url_decode(key["n"]), "big")
        e = int.from_bytes(_b64url_decode(key["e"]), "big")
    except (KeyError, ValueError):
        return None
    if not _rsa_verify_pkcs1_sha256(f"{header_b64}.{payload_b64}".encode(), signature, n, e):
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    return payload


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
