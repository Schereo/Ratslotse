"""Channel-aware digest delivery: Telegram, email, or both.

Centralises the per-owner delivery decision so the daily and weekly cron jobs
don't each re-implement it. An owner is a dict with at least
``delivery_channel``, ``telegram_chat_id`` and ``email`` (as returned by
``Store.get_all_owner_digests``).
"""
from __future__ import annotations

import logging
import re

from .telegram_bot import reply, reply_with_buttons, telegram_ready
from .email import email_ready, send_email
from .push import push_ready, send_push
from .digest_email import render_digest_email, render_html_email

logger = logging.getLogger("nwz.delivery")


def is_synthetic_email(email: str | None) -> bool:
    """True for the sentinel address of a Telegram-only synthetic account."""
    return bool(email) and email.startswith("tg-") and email.endswith("@local")


def _plain(text_html: str, limit: int = 180) -> str:
    """Collapse Telegram-style HTML to a short plain-text push body."""
    t = re.sub(r"<[^>]+>", "", text_html or "")
    t = re.sub(r"\s+", " ", t).strip()
    return (t[: limit - 1] + "…") if len(t) > limit else t


def _send_push_and_prune(devices: list[dict], title: str, body: str, data: dict[str, str]) -> None:
    """Send a push and drop the device tokens APNs/FCM reported as gone (app
    deleted, token rotated), so future sends stop retrying them. Opens its own
    Store handle — same NWZ_DB-env/repo default as the cron scripts — because
    callers only pass owner dicts, not their DB connection. Best-effort."""
    stale = send_push(devices, title, body, data)
    if not stale:
        return
    try:
        import os
        from pathlib import Path

        from .store import Store

        db = os.environ.get("NWZ_DB") or str(
            Path(__file__).resolve().parent.parent / "data" / "nwz.sqlite"
        )
        store = Store(db)
        try:
            for token in stale:
                store.remove_push_token(token)
        finally:
            store.close()
        logger.info("pruned %d stale push token(s)", len(stale))
    except Exception:
        logger.exception("pruning stale push tokens failed")


def _build_read_buttons(matches: list[dict], refid_to_id: dict[str, int]) -> list[list[dict]]:
    buttons: list[list[dict]] = []
    row: list[dict] = []
    for i, m in enumerate(matches, 1):
        mid = refid_to_id.get(m["refid"])
        if mid:
            row.append({"text": f"📖 {i}", "callback_data": f"art:{mid}"})
            if len(row) == 4:
                buttons.append(row)
                row = []
    if row:
        buttons.append(row)
    return buttons


def wants_telegram(owner: dict) -> bool:
    return (
        owner.get("delivery_channel", "telegram") in ("telegram", "both")
        and bool(owner.get("telegram_chat_id"))
        and telegram_ready()
    )


def wants_email(owner: dict) -> bool:
    return (
        owner.get("delivery_channel", "telegram") in ("email", "both")
        and not is_synthetic_email(owner.get("email"))
        and bool(owner.get("email"))
        and email_ready()
    )


def wants_push(owner: dict) -> bool:
    """Push is a first-class digest channel (delivery_channel == 'push'): the user
    gets notifications on their registered app devices instead of Telegram/email.
    Requires ≥1 device token and configured APNs/FCM credentials."""
    return (
        owner.get("delivery_channel", "telegram") == "push"
        and bool(owner.get("push_tokens"))
        and push_ready()
    )


def deliver_digest(
    owner: dict,
    topics: list,
    digest_text: str,
    matches: list[dict],
    refid_to_id: dict[str, int],
    pub_date: str,
    empty_text: str | None = None,
) -> list[str]:
    """Deliver one owner's digest to their chosen channel(s).

    Telegram mirrors the old behaviour (matches → digest with read buttons,
    otherwise the ``empty_text`` notice). Email is only sent when there are
    matches — no daily "nothing found" spam. Returns the channels delivered to.
    """
    sent: list[str] = []

    if wants_telegram(owner):
        chat_id = owner["telegram_chat_id"]
        if digest_text:
            buttons = _build_read_buttons(matches, refid_to_id)
            if not buttons or reply_with_buttons(chat_id, digest_text, buttons) is None:
                reply(chat_id, digest_text)
            sent.append("telegram")
        elif empty_text:
            reply(chat_id, empty_text)
            sent.append("telegram")

    if wants_email(owner) and matches:
        subject, html_body, text_body = render_digest_email(topics, matches, pub_date)
        try:
            send_email(owner["email"], subject, html_body, text=text_body)
            sent.append("email")
        except Exception:
            logger.exception("email digest send failed for %s", owner.get("email"))

    # Push mirrors email: only when there are matches (no daily "nothing found").
    if wants_push(owner) and matches:
        first = (matches[0].get("title") or "").strip()
        body = f"{len(matches)} neue Artikel zu deinen Themen" + (f": {first}" if first else "")
        _send_push_and_prune(owner["push_tokens"], "Ratslotse – neue Treffer", body, {"url": "/topics"})
        sent.append("push")

    return sent


def deliver_message(owner: dict, message_html: str, email_subject: str) -> list[str]:
    """Deliver a single formatted message (Telegram-style HTML) to the owner's
    channel(s). Used for the weekly digest and council notifications. The same
    text is wrapped in the email shell for email delivery."""
    sent: list[str] = []
    if wants_telegram(owner):
        reply(owner["telegram_chat_id"], message_html)
        sent.append("telegram")
    if wants_email(owner):
        try:
            send_email(
                owner["email"], email_subject,
                render_html_email(email_subject, message_html),
                text=None,
            )
            sent.append("email")
        except Exception:
            logger.exception("email message send failed for %s", owner.get("email"))
    if wants_push(owner):
        _send_push_and_prune(owner["push_tokens"], email_subject, _plain(message_html), {"url": "/dashboard"})
        sent.append("push")
    return sent
