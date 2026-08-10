"""Channel-aware notification delivery: email and/or push.

Centralises the per-owner delivery decision so the cron jobs don't each
re-implement it. An owner is a dict with at least ``delivery_channel``,
``email`` and ``push_tokens`` (as returned by the store's owner queries).

Channels: ``email``, ``push``, ``both`` (= email + push) — oder ``off``: gar
nicht. A former Telegram channel was removed; push notifications replace it.

``off`` fällt hier durch beide Prüfungen, weil es in keiner der beiden Listen
steht. Das ist die letzte Bastion, nicht die erste: Wer abgeschaltet hat, kommt
über ``nwz.notify.gewuenscht()`` gar nicht erst bis in die Warteschlange. Diese
Schicht greift für die wenigen Wege, die direkt zustellen — der Test-Knopf in
den Einstellungen etwa.
"""
from __future__ import annotations

import logging
import re

from .email import email_ready, send_email
from .push import push_ready, send_push
from .digest_email import render_html_email

logger = logging.getLogger("nwz.delivery")


def is_synthetic_email(email: str | None) -> bool:
    """True for the sentinel address of a legacy account without a real email."""
    return bool(email) and email.startswith("tg-") and email.endswith("@local")


def _plain(text_html: str, limit: int = 180) -> str:
    """Collapse HTML to a short plain-text push body."""
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


def wants_email(owner: dict) -> bool:
    return (
        owner.get("delivery_channel", "email") in ("email", "both")
        and not is_synthetic_email(owner.get("email"))
        and bool(owner.get("email"))
        and email_ready()
    )


def wants_push(owner: dict) -> bool:
    """Push notifications on the user's registered app devices. Requires ≥1 device
    token and configured APNs/FCM credentials."""
    return (
        owner.get("delivery_channel", "email") in ("push", "both")
        and bool(owner.get("push_tokens"))
        and push_ready()
    )


def push_quittung(owner: dict, titel: str, text: str, url: str) -> bool:
    """Push OHNE Warteschlange — für die **Quittung einer Handlung** des Nutzers
    („deine Recherche ist fertig"), nicht für einen Ratsvorgang.

    Die Grenzen aus 30a gelten hier bewusst nicht, und zwar aus demselben Grund,
    aus dem es sie gibt: Sie zähmen Meldungen, die *wir* anfangen. Diese hier hat
    der Nutzer selbst vor ein paar Minuten ausgelöst. Bis 7 Uhr früh liegen zu
    bleiben wäre sinnlos, und von zwei Sitzungsmeldungen verdrängt zu werden erst
    recht. Auch der Zustellweg entscheidet nicht mit: Wer „nur E-Mail" gewählt
    hat, meinte Neuigkeiten aus dem Rat — nicht die Antwort auf seinen eigenen
    Auftrag. Eine E-Mail gibt es dafür nicht; ein Zwei-Minuten-Job ist kein
    Briefanlass.

    Einzige Ausnahme ist das ausdrückliche ``off``: Wer alles abgeschaltet hat,
    hört auch hier nichts. Rückgabe: wurde ein Push abgeschickt?
    """
    if owner.get("delivery_channel") == "off":
        return False
    devices = owner.get("push_tokens") or []
    if not devices or not push_ready():
        return False
    _send_push_and_prune(devices, titel, text, {"url": url})
    return True


def deliver_message(owner: dict, message_html: str, email_subject: str,
                    push_url: str = "/dashboard") -> list[str]:
    """Deliver a single formatted message (HTML) to the owner's channel(s).
    Used for the weekly digest and council notifications. The same text is
    wrapped in the email shell for email delivery and stripped to plain text for
    the push body."""
    sent: list[str] = []
    if wants_email(owner):
        try:
            send_email(
                owner["email"], email_subject,
                render_html_email(email_subject, message_html, greeting_name=owner.get("display_name")),
                text=None,
            )
            sent.append("email")
        except Exception:
            logger.exception("email message send failed for %s", owner.get("email"))
    if wants_push(owner):
        _send_push_and_prune(owner["push_tokens"], email_subject, _plain(message_html), {"url": push_url})
        sent.append("push")
    return sent
