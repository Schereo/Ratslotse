"""Channel-aware digest delivery: Telegram, email, or both.

Centralises the per-owner delivery decision so the daily and weekly cron jobs
don't each re-implement it. An owner is a dict with at least
``delivery_channel``, ``telegram_chat_id`` and ``email`` (as returned by
``Store.get_all_owner_digests``).
"""
from __future__ import annotations

import logging

from .telegram_bot import reply, reply_with_buttons, telegram_ready
from .email import email_ready, send_email
from .digest_email import render_digest_email

logger = logging.getLogger("nwz.delivery")


def is_synthetic_email(email: str | None) -> bool:
    """True for the sentinel address of a Telegram-only synthetic account."""
    return bool(email) and email.startswith("tg-") and email.endswith("@local")


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

    return sent
