"""User feedback → email to the operator."""
from __future__ import annotations

import html as _html
import logging

from fastapi import APIRouter, Depends, Request, status

from kern.email import send_email
from kern.store import Store

from ..config import get_settings
from ..deps import get_store, require_active
from ..ratelimit import support_limiter
from ..schemas import FeedbackIn, SupportIn

logger = logging.getLogger("nwz.web.feedback")

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

_KIND_LABELS = {
    "feature": "Feature-Vorschlag",
    "bug": "Fehler",
    "other": "Sonstiges",
    "konto": "Konto & Anmeldung",
}

# Anonyme Kontaktanfragen haben kein Konto, `feedback.owner_id` ist aber
# NOT NULL. 0 ist im Schema schon die etablierte „gehört niemandem"-Kennung
# (siehe `topics.owner_id DEFAULT 0`) — und weil `delete_web_user` über echte
# owner_ids löscht, bleibt eine Support-Anfrage erhalten, wenn ihr Absender
# später doch ein Konto anlegt und wieder löscht.
_KEIN_KONTO = 0


def _mail_bauen(titel: str, kind_label: str, absender: str, message: str) -> tuple[str, str]:
    """Baut (html, text) für eine Benachrichtigungs-Mail an den Betreiber."""
    msg_html = _html.escape(message).replace("\n", "<br>")
    html_body = (
        "<div style='max-width:560px;margin:0 auto;padding:24px 16px;"
        "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a'>"
        f"<div style='font-size:18px;font-weight:700;color:#2563eb'>{_html.escape(titel)}</div>"
        f"<p style='margin:16px 0 4px'><b>Art:</b> {_html.escape(kind_label)}</p>"
        f"<p style='margin:0 0 12px'><b>Von:</b> {_html.escape(absender)}</p>"
        "<div style='white-space:pre-wrap;border-left:3px solid #e2e8f0;padding-left:12px;"
        f"color:#334155;line-height:1.6'>{msg_html}</div></div>"
    )
    text_body = f"{titel} ({kind_label}) von {absender}:\n\n{message}\n"
    return html_body, text_body


@router.post("")
def submit_feedback(
    body: FeedbackIn,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> dict:
    """Email the operator a piece of user feedback. Reply-to is the user's address so
    the operator can answer directly. Best-effort: never surfaces email config to the user."""
    settings = get_settings()
    recipient = settings.feedback_email or settings.web_admin_email
    kind_label = _KIND_LABELS.get(body.kind, body.kind)
    user_email = (user.get("email") or "").strip()

    # Zuerst ablegen, dann mailen: Der Mailversand ist der unzuverlässige Teil
    # (fremder Dienst, fehlender Key). Andersherum ginge Feedback verloren,
    # sobald Resend zickt — und genau dagegen ist die Kopie im Admin-Panel da.
    try:
        store.add_feedback(user["id"], user_email or None, body.kind, body.message)
    except Exception:  # noqa: BLE001 — Speichern darf den Absender nie scheitern lassen
        logger.exception("feedback konnte nicht gespeichert werden (from=%s)", user_email)

    if not settings.resend_api_key or not recipient:
        logger.warning("feedback received but email not configured (kind=%s, from=%s)", body.kind, user_email)
        return {"ok": True}

    html_body, text_body = _mail_bauen("Neues Feedback", kind_label, user_email or "unbekannt", body.message)
    try:
        send_email(
            recipient, f"Ratslotse-Feedback: {kind_label}", html_body, text=text_body,
            reply_to=user_email if "@" in user_email else None,
            api_key=settings.resend_api_key, sender=settings.email_from,
        )
    except Exception:  # noqa: BLE001 — a failed feedback mail must not error the user
        logger.exception("feedback email failed (from=%s)", user_email)
    return {"ok": True}


@router.post("/kontakt", status_code=status.HTTP_202_ACCEPTED)
def submit_support(
    request: Request,
    body: SupportIn,
    store: Store = Depends(get_store),
) -> dict:
    """Kontaktformular der Hilfe-Seite — **ohne Anmeldung**.

    Bewusst öffentlich: Der Feedback-Dialog oben hängt am eingeloggten Konto und
    hilft damit ausgerechnet dem nicht, der sich nicht anmelden kann. Genau
    diesen Weg verlangt Apples Richtlinie 1.5 für die Support-URL.

    Der Preis der Öffentlichkeit sind Bots, dagegen stehen drei Dinge:
    IP-Limit, Honigtopf und die 4000-Zeichen-Grenze aus dem Schema.
    """
    support_limiter.check(request)

    # Honigtopf gefüllt ⇒ Bot. Wir antworten wie im Erfolgsfall, damit das
    # Skript keinen Unterschied misst und nichts zu optimieren hat.
    if body.website.strip():
        logger.info("support-kontakt: honigtopf ausgelöst, verworfen")
        return {"ok": True}

    settings = get_settings()
    recipient = settings.feedback_email or settings.web_admin_email
    kind_label = _KIND_LABELS.get(body.kind, body.kind)
    absender = body.email.strip()

    # Gleiche Reihenfolge wie beim Feedback — und hier wiegt sie schwerer: Eine
    # Support-Anfrage kommt oft von jemandem, der gerade nicht reinkommt. Ginge
    # sie mit einem Resend-Aussetzer verloren, wäre die Person still ausgesperrt.
    try:
        store.add_feedback(_KEIN_KONTO, absender, body.kind, body.message)
    except Exception:  # noqa: BLE001 — Speichern darf den Absender nie scheitern lassen
        logger.exception("support-kontakt konnte nicht gespeichert werden (from=%s)", absender)

    if not settings.resend_api_key or not recipient:
        logger.warning("support-kontakt received but email not configured (kind=%s, from=%s)",
                       body.kind, absender)
        return {"ok": True}

    html_body, text_body = _mail_bauen("Anfrage über die Hilfe-Seite", kind_label, absender, body.message)
    try:
        send_email(
            recipient, f"Ratslotse-Hilfe: {kind_label}", html_body, text=text_body,
            reply_to=absender,
            api_key=settings.resend_api_key, sender=settings.email_from,
        )
    except Exception:  # noqa: BLE001 — ein gescheiterter Mailversand darf den Absender nicht treffen
        logger.exception("support-kontakt email failed (from=%s)", absender)
    return {"ok": True}
