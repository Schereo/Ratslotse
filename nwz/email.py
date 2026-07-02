"""Transactional email via Resend.

Env-driven and requests-based. The Resend API key is a *sending-only* key and
lives only in ``.env`` / 1Password — never in the repo.

Set ``RESEND_API_KEY`` to enable sending. ``EMAIL_FROM`` overrides the
default sender (must be on a domain verified in the Resend dashboard).
"""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger("nwz.email")

RESEND_API = "https://api.resend.com/emails"

# Default sender. Override via EMAIL_FROM once ratslotse.de is verified in
# Resend. Until then, Resend's shared sandbox sender only delivers to your own
# Resend account address.
DEFAULT_FROM = "Ratslotse <noreply@ratslotse.de>"


def email_ready() -> bool:
    """True if an API key is configured, i.e. sending is possible."""
    return bool(os.environ.get("RESEND_API_KEY"))


def _sender() -> str:
    return os.environ.get("EMAIL_FROM", DEFAULT_FROM)


def send_email(
    to: str | list[str],
    subject: str,
    html: str,
    *,
    text: str | None = None,
    reply_to: str | None = None,
    api_key: str | None = None,
    sender: str | None = None,
) -> str | None:
    """Send a single transactional email. Returns the Resend message id, or
    ``None`` if email is not configured.

    ``api_key`` / ``sender`` override the ``RESEND_API_KEY`` / ``EMAIL_FROM``
    env vars — the cron jobs rely on the env (via ``load_dotenv``) and omit
    them; the web backend passes them explicitly from its pydantic settings so
    it doesn't depend on the process environment.

    Raises ``requests.HTTPError`` on a non-2xx response so callers can decide
    whether a failed digest send is fatal (cron) or should surface to the user
    (verification flow).
    """
    api_key = api_key or os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.warning("RESEND_API_KEY not set — skipping email to %s", to)
        return None

    payload: dict = {
        "from": sender or _sender(),
        "to": [to] if isinstance(to, str) else to,
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text
    if reply_to:
        payload["reply_to"] = reply_to

    resp = requests.post(
        RESEND_API,
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    message_id = resp.json().get("id")
    logger.info("Sent email to %s (id=%s)", payload["to"], message_id)
    return message_id
