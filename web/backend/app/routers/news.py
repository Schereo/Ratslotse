"""„Neu bei Ratslotse": die Highlights eines Releases lesen und ankündigen.

Der Inhalt steht in ``kern/releases.py``, der Versandweg in ``kern/news.py``.
Hier ist nur die Schnittstelle — und die eine Entscheidung, die **serverseitig**
fallen muss: wer welche Karte noch sehen soll. Web und native App bekommen
dieselbe Antwort, statt die Regel je Client nachzubauen (dieselbe Begründung
wie beim Einrichtungs-Assistenten, ``Store.get_setup``).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from kern import news, releases
from kern.store import Store

from ..antworten import (AdminNewsList, AdminNewsRelease, AdminNewsSent,
                         NewsSeen, NewsState, TestDelivery)
from ..config import get_settings
from ..deps import get_store, require_active, require_admin
from ..schemas import NewsSeenIn

logger = logging.getLogger("ratslotse.web.news")

router = APIRouter(prefix="/api/news", tags=["news"])
admin_router = APIRouter(prefix="/api/admin/news", tags=["admin"])


@router.get("")
def get_news(
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> NewsState:
    """Die offenen Release-Karten dieses Kontos, neueste zuerst."""
    offen, weitere = releases.pending_for(
        user.get("news_seen_version"), user.get("created_at"))
    return {
        "releases": [releases.as_dict(r) for r in offen],  # pyright: ignore[reportReturnType]
        "older_count": weitere,
        "seen_version": user.get("news_seen_version"),
    }


@router.post("/seen")
def mark_seen(
    payload: NewsSeenIn,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> NewsSeen:
    """Die Karte ist weggeklickt — die Hochwassermarke nachziehen.

    Der Client meldet die Version, die er GEZEIGT hat. Käme zwischen Laden und
    Wegklicken ein Deploy, würde „die neueste laut Server" ein Release
    miterledigen, das nie jemand gesehen hat.
    """
    return {"seen_version": store.set_news_seen(user["id"], payload.version)}


# --------------------------------------------------------------------------
# Admin: ankündigen
# --------------------------------------------------------------------------


@admin_router.get("")
def admin_news(
    admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> AdminNewsList:
    """Alle Einträge der Registry samt Stand ihres Versands.

    Die beiden Zahlen je Eintrag beantworten die Frage vor dem Drücken: Wie
    viele bekämen die Ankündigung jetzt, und wie viele haben sie schon. Sie
    entstehen aus **einer** Abfrage über alle Konten, nicht aus einer je
    Release — die Registry wächst mit jedem Release, die Kontenzahl auch.
    """
    konten = store.news_candidates()
    zeilen: list[AdminNewsRelease] = []
    for release in releases.RELEASES:
        ziel = releases.version_key(release.version)

        def erledigt(marke: str | None, _ziel=ziel) -> bool:
            if not marke:
                return False
            try:
                return releases.version_key(marke) >= _ziel
            except ValueError:
                return False

        infrage = [k for k in konten
                   if (k.get("created_at") or "")[:10] <= release.date]
        offen = [k for k in infrage
                 if not erledigt(k.get("news_sent_version"))
                 and not erledigt(k.get("news_seen_version"))]
        zeilen.append({
            **releases.as_dict(release),  # pyright: ignore[reportGeneralTypeIssues]
            "open_recipients": len(offen),
            "sent_recipients": sum(
                1 for k in infrage if erledigt(k.get("news_sent_version"))),
        })
    return {"releases": zeilen}


def _release_oder_404(version: str):
    release = releases.get(version)
    if release is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"Kein Release-Eintrag für {version}.")
    return release


@admin_router.post("/{version}/test")
def admin_news_test(
    version: str,
    admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> TestDelivery:
    """Die Ankündigung einmal an das eigene Konto — vor dem echten Versand.

    Bewusst **nicht** über die Warteschlange: Eine Probe soll sofort ankommen
    und darf nicht an der eigenen Nachtruhe oder Tagesgrenze hängen bleiben.
    Sie ändert deshalb auch keine Marke — sie zählt nicht als Versand.
    """
    from kern.delivery import deliver_message

    release = _release_oder_404(version)
    owner = {
        "email": admin["email"],
        "display_name": admin.get("display_name"),
        "delivery_channel": admin.get("delivery_channel") or "email",
        "push_tokens": store.get_push_tokens_for_owner(admin["id"]),
    }
    sent = deliver_message(
        owner, news.body_html(release),
        email_subject=f"[Probe] {news.title_for(release)}",
        push_url=news.TAP_ZIEL, push_text=news.push_text_for(release),
    )
    return {"sent": sent}


@admin_router.post("/{version}/send")
def admin_news_send(
    version: str,
    background: BackgroundTasks,
    admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> AdminNewsSent:
    """Die Ankündigung an alle offenen Empfänger einreihen.

    Eingereiht wird sofort (nur Datenbank), **zugestellt im Hintergrund**:
    Zweihundert Mails über die Resend-API dauern länger, als eine HTTP-Anfrage
    warten darf. Der Hintergrund-Lauf öffnet einen eigenen Store — die
    Abhängigkeit aus dem Request ist zu diesem Zeitpunkt längst geschlossen.
    """
    release = _release_oder_404(version)
    bilanz = news.announce(store, release)
    if bilanz["queued"]:
        background.add_task(_zustellen)
    return {"version": release.version, **bilanz}  # pyright: ignore[reportReturnType]


def _zustellen() -> None:
    """Die Warteschlange leeren — nach der Antwort, mit eigenem Store."""
    from kern import notify

    settings = get_settings()
    store = Store(settings.ratslotse_db)
    try:
        anzahl = notify.zustellen(store)
        logger.info("Release-Ankündigung: %s Zustellung(en) raus", anzahl)
    except Exception:
        logger.exception("Zustellung der Release-Ankündigung fehlgeschlagen")
    finally:
        store.close()
