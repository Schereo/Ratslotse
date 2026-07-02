"""User feedback → email to the operator."""
from __future__ import annotations

import html as _html
import logging

from fastapi import APIRouter, Depends

from nwz.email import send_email

from ..config import get_settings
from ..deps import require_active
from ..schemas import FeedbackIn

logger = logging.getLogger("nwz.web.feedback")

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

_KIND_LABELS = {"feature": "Feature-Vorschlag", "bug": "Fehler", "other": "Sonstiges"}


@router.post("")
def submit_feedback(body: FeedbackIn, user: dict = Depends(require_active)) -> dict:
    """Email the operator a piece of user feedback. Reply-to is the user's address so
    the operator can answer directly. Best-effort: never surfaces email config to the user."""
    settings = get_settings()
    recipient = settings.feedback_email or settings.web_admin_email
    kind_label = _KIND_LABELS.get(body.kind, body.kind)
    user_email = (user.get("email") or "").strip()

    if not settings.resend_api_key or not recipient:
        logger.warning("feedback received but email not configured (kind=%s, from=%s)", body.kind, user_email)
        return {"ok": True}

    msg_html = _html.escape(body.message).replace("\n", "<br>")
    subject = f"Ratslotse-Feedback: {kind_label}"
    html_body = (
        "<div style='max-width:560px;margin:0 auto;padding:24px 16px;"
        "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a'>"
        "<div style='font-size:18px;font-weight:700;color:#2563eb'>Neues Feedback</div>"
        f"<p style='margin:16px 0 4px'><b>Art:</b> {_html.escape(kind_label)}</p>"
        f"<p style='margin:0 0 12px'><b>Von:</b> {_html.escape(user_email or 'unbekannt')}</p>"
        "<div style='white-space:pre-wrap;border-left:3px solid #e2e8f0;padding-left:12px;"
        f"color:#334155;line-height:1.6'>{msg_html}</div></div>"
    )
    text_body = f"Feedback ({kind_label}) von {user_email or 'unbekannt'}:\n\n{body.message}\n"
    try:
        send_email(
            recipient, subject, html_body, text=text_body,
            reply_to=user_email if "@" in user_email else None,
            api_key=settings.resend_api_key, sender=settings.email_from,
        )
    except Exception:  # noqa: BLE001 — a failed feedback mail must not error the user
        logger.exception("feedback email failed (from=%s)", user_email)
    return {"ok": True}
