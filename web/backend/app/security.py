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


# Throwaway hash for the "email has no account" login path: verifying a password
# against it costs exactly the same scrypt work as checking a real account, so a
# missing account can't be told apart from a wrong password by response time
# (CWE-208 user enumeration). Built with hash_password() — never a hardcoded
# digest — so it automatically tracks the real parameters above, and computed
# once at import so no single request ever pays for deriving it. The password is
# random and the result is always discarded; it can never authenticate anyone.
DUMMY_PASSWORD_HASH = hash_password(os.urandom(32).hex())


# --- JWT (HS256) -------------------------------------------------------------
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(message: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(sig)


def _signiert(nutzlast: dict) -> str:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url_encode(json.dumps(nutzlast).encode())
    signing_input = f"{header}.{payload}".encode()
    return f"{header}.{payload}.{_sign(signing_input, get_settings().web_jwt_secret)}"


#: Woher eine Sitzung stammt, wenn nicht aus Passwort, Apple oder Bestätigung:
#: aus einem Anmeldelink in einer Mail (``create_magic_token``). Eine solche
#: Sitzung darf lesen und einstellen, aber nichts, was das Konto übernimmt
#: (``deps.require_volle_anmeldung``).
VIA_LINK = "magic"


def create_access_token(
    subject: str | int, token_version: int = 0, expires_minutes: int | None = None,
    via: str | None = None,
) -> str:
    settings = get_settings()
    minutes = settings.access_token_expire_minutes if expires_minutes is None else expires_minutes
    nutzlast: dict = {"sub": str(subject), "exp": int(time.time()) + minutes * 60,
                      "ver": token_version}
    if via:
        nutzlast["via"] = via
    return _signiert(nutzlast)


#: So lange gilt ein Anmeldelink aus einer Mail (Tims Vorgabe 08.11.2026).
MAGIC_TAGE = 10


def create_magic_token(subject: str | int, token_version: int = 0, tage: int = MAGIC_TAGE) -> str:
    """Ein Anmeldelink-Token für eine Mail — **kein** Sitzungs-Token.

    Es trägt ``zweck: magic``, und ``decode_access_token`` weist jedes Token
    mit Zweck ab: Ein zehn Tage gültiger Schlüssel, der zugleich als Sitzung
    gälte, wäre ein Generalschlüssel im Postfach. Eingelöst wird es nur über
    ``POST /api/auth/magic`` — per Klick, damit Mail-Scanner, die Links vorab
    öffnen, nichts auslösen. ``ver`` bindet es an ``token_version``: Abmelden
    überall, Passwortwechsel oder Sperre machen alle offenen Links wertlos.
    """
    return _signiert({"sub": str(subject), "exp": int(time.time()) + tage * 86400,
                      "ver": token_version, "zweck": VIA_LINK})


def magic_grund(token: str) -> str:
    """Warum ein Anmeldelink nicht gilt: ``abgelaufen`` (echt, aber zu alt)
    oder ``ungueltig`` (falsche Signatur, kein Anmeldelink, Unsinn)."""
    payload = _verified_payload(token)
    if payload and payload.get("zweck") == VIA_LINK and payload.get("exp", 0) < int(time.time()):
        return "abgelaufen"
    return "ungueltig"


def decode_magic_token(token: str) -> tuple[str, int] | None:
    """``(Konto, token_version)`` eines gültigen Anmeldelinks — sonst ``None``."""
    payload = _verified_payload(token)
    if not payload or payload.get("zweck") != VIA_LINK:
        return None
    if payload.get("exp", 0) < int(time.time()) or payload.get("sub") is None:
        return None
    return str(payload["sub"]), int(payload.get("ver", 0))


def token_via(token: str) -> str | None:
    """Woher die Sitzung stammt (``VIA_LINK``) — ``None`` für eine gewöhnliche."""
    payload = _verified_payload(token)
    return (payload or {}).get("via") or None


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
    except (ValueError, json.JSONDecodeError, RecursionError):
        # RecursionError: ein Kopf aus tausenden `[` sprengt json.loads.
        return None
    # Ein Kopf wie `[]` ist gültiges JSON, aber kein Objekt — `header.get`
    # warf dann einen AttributeError, und aus einer fremden Eingabe ohne
    # Konto wurde ein 500er samt Admin-Mail (zweite Prüfung 10/2026, F6).
    if not isinstance(header, dict) or not isinstance(payload, dict):
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


def _verified_payload(token: str) -> dict | None:
    """Signatur prüfen und die Nutzlast liefern — ohne Ablauf-Prüfung.

    Getrennt von ``decode_access_token``, weil die stille Verlängerung
    (``app/session.py``) nicht nur wissen muss, *ob* ein Token gilt, sondern
    auch *wie lange noch*.
    """
    try:
        header_b64, payload_b64, signature = token.split(".")
    except ValueError:
        return None
    expected = _sign(f"{header_b64}.{payload_b64}".encode(), get_settings().web_jwt_secret)
    # Bytes vergleichen, nicht Zeichenketten: `compare_digest` wirft auf einen
    # str mit Nicht-ASCII-Zeichen einen TypeError, statt False zu sagen — und
    # ein Cookie wie `"a.b.\351"` liefert genau so ein Zeichen. Der Fehler fiel
    # in der Sitzungsverlängerung, VOR jedem Router, und landete als 500er samt
    # Admin-Mail im Fehlersammler (Sicherheitsprüfung 10/2026, F2).
    if not hmac.compare_digest(expected.encode(),
                               signature.encode("utf-8", "surrogatepass")):
        return None
    try:
        return json.loads(_b64url_decode(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None


def decode_access_token(token: str) -> tuple[str, int] | None:
    """Return (subject, token_version) or None if the token is invalid/expired."""
    payload = _verified_payload(token)
    if payload is None:
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    # Ein Token mit Zweck (der Anmeldelink) ist nie eine Sitzung.
    if payload.get("zweck"):
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    return sub, int(payload.get("ver", 0))


def token_lifetime_left(token: str) -> int | None:
    """Restlaufzeit in Sekunden — ``None``, wenn das Token ungültig oder schon
    abgelaufen ist. Der billige Vorab-Test der Sitzungsverlängerung: In aller
    Regel steht hier eine große Zahl und der Request ist damit durch."""
    payload = _verified_payload(token)
    if payload is None:
        return None
    left = int(payload.get("exp", 0)) - int(time.time())
    return left if left > 0 else None
