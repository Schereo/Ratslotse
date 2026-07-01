"""Native-app push delivery: APNs (iOS) direct + FCM v1 (Android).

Mirrors ``nwz.email``: entirely optional and env-driven. If the platform
credentials aren't configured — or the optional deps aren't installed —
``push_ready()`` is ``False`` and sends are graceful no-ops, so the digest cron
keeps working without push. Heavy deps (httpx, cryptography, google-auth) are
imported lazily inside the send paths, so importing this module never fails.

iOS goes straight to Apple (no Firebase), keeping Apple push out of Google for
DSGVO reasons; Android uses FCM because Play requires it.

Environment (.env, shared with the bot/cron via load_dotenv):

  APNs (iOS):
    APNS_KEY_P8      path to the AuthKey_XXXX.p8 file (or the PEM contents inline)
    APNS_KEY_ID      the 10-char key id of that .p8
    APNS_TEAM_ID     your Apple Developer team id
    APNS_TOPIC       the iOS bundle id, e.g. de.ratslotse.app
    APNS_USE_SANDBOX 1 to target the sandbox gateway (dev/TestFlight debug builds)

  FCM (Android):
    FCM_PROJECT_ID   Firebase project id
    FCM_CREDENTIALS  path to the service-account JSON with the messaging role
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time

logger = logging.getLogger("nwz.push")

APNS_PROD_HOST = "https://api.push.apple.com"
APNS_SANDBOX_HOST = "https://api.sandbox.push.apple.com"
FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


# --- readiness guards --------------------------------------------------------
def apns_ready() -> bool:
    return all(
        os.environ.get(k)
        for k in ("APNS_KEY_P8", "APNS_KEY_ID", "APNS_TEAM_ID", "APNS_TOPIC")
    )


def fcm_ready() -> bool:
    return bool(os.environ.get("FCM_PROJECT_ID") and os.environ.get("FCM_CREDENTIALS"))


def push_ready() -> bool:
    """True if at least one platform is configured, i.e. push can be sent."""
    return apns_ready() or fcm_ready()


# --- APNs (iOS) --------------------------------------------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


_apns_jwt_cache: tuple[str, float] | None = None  # (jwt, issued_at)


def _load_apns_key_pem() -> bytes:
    raw = os.environ["APNS_KEY_P8"]
    # Accept either a path to the .p8 or the PEM contents pasted inline.
    if "BEGIN PRIVATE KEY" in raw:
        return raw.encode("utf-8")
    with open(raw, "rb") as fh:
        return fh.read()


def _apns_jwt() -> str:
    """Build (and cache for ~45 min) the ES256 provider JWT APNs wants. Apple
    accepts a token up to 60 min old and rejects refreshing more than once every
    20 min, so caching is required, not just an optimisation."""
    global _apns_jwt_cache
    now = time.time()
    if _apns_jwt_cache and now - _apns_jwt_cache[1] < 45 * 60:
        return _apns_jwt_cache[0]

    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    from cryptography.hazmat.primitives.hashes import SHA256
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    header = _b64url(json.dumps({"alg": "ES256", "kid": os.environ["APNS_KEY_ID"]}).encode())
    payload = _b64url(json.dumps({"iss": os.environ["APNS_TEAM_ID"], "iat": int(now)}).encode())
    signing_input = f"{header}.{payload}".encode()

    key = load_pem_private_key(_load_apns_key_pem(), password=None)
    der = key.sign(signing_input, ec.ECDSA(SHA256()))
    r, s = decode_dss_signature(der)  # DER → JOSE raw r||s (32 bytes each)
    jose_sig = _b64url(r.to_bytes(32, "big") + s.to_bytes(32, "big"))

    jwt = f"{header}.{payload}.{jose_sig}"
    _apns_jwt_cache = (jwt, now)
    return jwt


def _send_apns(client, tokens: list[str], title: str, body: str, data: dict[str, str]) -> list[str]:
    """POST one alert per device over the shared HTTP/2 client. Returns tokens
    Apple reports as gone (410) or invalid, so the caller can prune them."""
    host = APNS_SANDBOX_HOST if os.environ.get("APNS_USE_SANDBOX") == "1" else APNS_PROD_HOST
    topic = os.environ["APNS_TOPIC"]
    jwt = _apns_jwt()
    payload = {"aps": {"alert": {"title": title, "body": body}, "sound": "default"}, **data}
    stale: list[str] = []
    for tok in tokens:
        try:
            resp = client.post(
                f"{host}/3/device/{tok}",
                headers={
                    "authorization": f"bearer {jwt}",
                    "apns-topic": topic,
                    "apns-push-type": "alert",
                },
                json=payload,
            )
        except Exception:  # noqa: BLE001 — one bad device must not sink the batch
            logger.exception("APNs send failed for a device")
            continue
        if resp.status_code == 200:
            continue
        reason = ""
        try:
            reason = resp.json().get("reason", "")
        except Exception:  # noqa: BLE001
            pass
        if resp.status_code == 410 or reason in ("BadDeviceToken", "Unregistered"):
            stale.append(tok)
        else:
            logger.warning("APNs rejected a device (%s %s)", resp.status_code, reason)
    return stale


# --- FCM (Android) -----------------------------------------------------------
_fcm_creds = None  # cached google.oauth2.service_account.Credentials


def _fcm_access_token() -> str:
    global _fcm_creds
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import service_account

    if _fcm_creds is None:
        _fcm_creds = service_account.Credentials.from_service_account_file(
            os.environ["FCM_CREDENTIALS"], scopes=[FCM_SCOPE]
        )
    if not _fcm_creds.valid:
        _fcm_creds.refresh(GoogleRequest())
    return _fcm_creds.token


def _send_fcm(client, tokens: list[str], title: str, body: str, data: dict[str, str]) -> list[str]:
    """POST one message per device to FCM HTTP v1. Returns tokens FCM reports as
    unregistered (404 / UNREGISTERED) so the caller can prune them."""
    project = os.environ["FCM_PROJECT_ID"]
    url = f"https://fcm.googleapis.com/v1/projects/{project}/messages:send"
    access = _fcm_access_token()
    stale: list[str] = []
    for tok in tokens:
        message = {
            "message": {
                "token": tok,
                "notification": {"title": title, "body": body},
                **({"data": data} if data else {}),
            }
        }
        try:
            resp = client.post(
                url, headers={"Authorization": f"Bearer {access}"}, json=message
            )
        except Exception:  # noqa: BLE001
            logger.exception("FCM send failed for a device")
            continue
        if resp.status_code == 200:
            continue
        status_str = ""
        try:
            status_str = resp.json().get("error", {}).get("status", "")
        except Exception:  # noqa: BLE001
            pass
        if resp.status_code == 404 or status_str in ("NOT_FOUND", "UNREGISTERED"):
            stale.append(tok)
        else:
            logger.warning("FCM rejected a device (%s %s)", resp.status_code, status_str)
    return stale


# --- public API --------------------------------------------------------------
def send_push(
    devices: list[dict],
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> list[str]:
    """Send one notification to every device in ``devices`` ([{token, platform}]).

    Routes iOS tokens to APNs and Android tokens to FCM (skipping a platform that
    isn't configured). Returns the tokens the gateways reported as stale/invalid,
    so the caller can drop them from the store. Never raises.
    """
    if not devices or not push_ready():
        return []
    # FCM data values must be strings; APNs custom keys ride alongside `aps`.
    data = {str(k): str(v) for k, v in (data or {}).items()}
    ios = [d["token"] for d in devices if d.get("platform") == "ios"]
    android = [d["token"] for d in devices if d.get("platform") == "android"]
    stale: list[str] = []

    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed — cannot send push")
        return []

    if ios and apns_ready():
        try:
            with httpx.Client(http2=True, timeout=10) as client:
                stale += _send_apns(client, ios, title, body, data)
        except Exception:  # noqa: BLE001 — e.g. h2 missing, or key load error
            logger.exception("APNs batch failed (missing http2 support or bad key?)")

    if android and fcm_ready():
        try:
            with httpx.Client(timeout=10) as client:
                stale += _send_fcm(client, android, title, body, data)
        except Exception:  # noqa: BLE001
            logger.exception("FCM batch failed")

    return stale
