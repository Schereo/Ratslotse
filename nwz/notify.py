"""Warteschlange und harte Grenzen für Benachrichtigungen (Design 30a).

Bis hierher schickte jeder Anlass direkt los, sobald er etwas fand. Bei mehreren
Gremien-Abos konnten daraus an einem Sitzungstag beliebig viele Meldungen
werden, und ein Beschluss um 22:40 Uhr klingelte um 22:40 Uhr.

30a stellt vier Grenzen über *alle* Anlässe. Zwei davon sind hier zu Hause:

* **Höchstens zwei am Tag.** Pro Person, nicht pro Anlass. Fällt mehr an, wird
  gebündelt statt gestapelt — die letzte freie Zustellung des Tages nimmt alles
  Übrige als eine Nachricht mit. Nichts geht verloren, nichts wird zur Flut.
* **Nachtruhe 21–7 Uhr.** Ratssitzungen enden regelmäßig nach 22 Uhr. Was danach
  entschieden wird, wartet bis zum Morgen — nichts im Rat ist so dringend, dass
  es jemanden weckt.

Die beiden anderen Grenzen stehen nicht hier, sondern in der Bauweise:
*nie ohne Ereignis* (es gibt schlicht keine Funktion, die ohne Ratsvorgang
einreiht) und *jede Mitteilung landet auf einer echten Seite* — ``url`` ist ein
Pflichtfeld, kein Vorgabewert auf die Startseite.

Ablauf: Die Cron-Jobs **reihen ein** (``einreihen``) und stoßen am Ende ihres
Laufs die **Zustellung** an (``zustellen``). Damit braucht es keinen eigenen
Cron-Eintrag: ``check_committees`` läuft um 7 Uhr und leert damit genau dann,
was die Nacht über liegen geblieben ist.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger("nwz.notify")

# Ortszeit ist maßgeblich: „nichts zwischen 21 und 7 Uhr" meint 21 Uhr in
# Oldenburg, nicht in UTC. Gespeichert wird trotzdem UTC (wie überall sonst).
ZONE = ZoneInfo("Europe/Berlin")

NACHTRUHE_AB = 21   # ab 21:00 Ortszeit geht nichts mehr raus
NACHTRUHE_BIS = 7   # … bis 7:00 Ortszeit
TAGESGRENZE = 2     # höchstens zwei Zustellungen pro Person und Tag

#: Anlässe aus 30a/B. Der Schlüssel steht so in der Warteschlange und später in
#: den Schaltern der Einstellungs-Seite.
N1_TAGESORDNUNG = "n1_tagesordnung"
N2_THEMA = "n2_thema"
N3_ERGEBNIS = "n3_ergebnis"
N4_VORGANG = "n4_vorgang"
N5_VORABEND = "n5_vorabend"
N6_WOCHE = "n6_woche"


def _jetzt(jetzt: datetime | None = None) -> datetime:
    return (jetzt or datetime.now(timezone.utc)).astimezone(timezone.utc)


def naechstes_fenster(jetzt: datetime | None = None) -> datetime:
    """Frühester Zeitpunkt, zu dem zugestellt werden darf (UTC).

    Innerhalb der Nachtruhe ist das der kommende 7-Uhr-Morgen in Ortszeit,
    sonst der Moment selbst.
    """
    n = _jetzt(jetzt)
    lokal = n.astimezone(ZONE)
    if lokal.hour >= NACHTRUHE_AB:
        ziel = (lokal + timedelta(days=1)).replace(hour=NACHTRUHE_BIS, minute=0, second=0, microsecond=0)
    elif lokal.hour < NACHTRUHE_BIS:
        ziel = lokal.replace(hour=NACHTRUHE_BIS, minute=0, second=0, microsecond=0)
    else:
        return n
    return ziel.astimezone(timezone.utc)


def ist_nachtruhe(jetzt: datetime | None = None) -> bool:
    lokal = _jetzt(jetzt).astimezone(ZONE)
    return lokal.hour >= NACHTRUHE_AB or lokal.hour < NACHTRUHE_BIS


def _tag(zeitpunkt: datetime) -> str:
    """Kalendertag in Ortszeit — die Bezugsgröße der Tagesgrenze."""
    return zeitpunkt.astimezone(ZONE).date().isoformat()


def einreihen(store, owner_id: int, kind: str, titel: str, html: str, url: str,
              jetzt: datetime | None = None) -> int:
    """Eine Benachrichtigung in die Warteschlange legen. Gibt ihre id zurück.

    ``url`` ist Pflicht (Grenze 4): Antippen muss den Beschluss oder die
    Tagesordnung öffnen, nie nur die Startseite.
    """
    if not url:
        raise ValueError("Jede Benachrichtigung braucht ein Ziel (30a, Grenze 4).")
    n = _jetzt(jetzt)
    return store.enqueue_notification(
        owner_id=owner_id, kind=kind, title=titel, body_html=html, url=url,
        created_at=n.isoformat(timespec="seconds"),
        deliver_after=naechstes_fenster(n).isoformat(timespec="seconds"),
    )


def _buendel(posten: list[dict]) -> tuple[str, str, str]:
    """Aus mehreren Fälligen eine Nachricht machen (titel, html, url).

    Das Ziel ist bewusst die Übersicht: Ein Bündel hat mehrere Ereignisse, also
    kann es nicht auf eine einzelne Seite zeigen — „Heute" listet sie alle.
    """
    titel = f"{len(posten)} Neuigkeiten aus dem Rat"
    zeilen = ["<ul style='margin:0;padding-left:18px'>"]
    for p in posten:
        zeilen.append(
            f"<li style='margin-bottom:6px'><a href=\"{p['url']}\">{p['title']}</a></li>"
        )
    zeilen.append("</ul>")
    return titel, "\n".join(zeilen), "/dashboard"


def zustellen(store, jetzt: datetime | None = None, stats: dict | None = None) -> int:
    """Fällige Benachrichtigungen ausliefern — unter den Grenzen aus 30a/C.

    Gibt die Zahl der tatsächlich verschickten Nachrichten zurück (ein Bündel
    zählt als eine). Alles, was heute nicht mehr durchpasst, bleibt in der
    Warteschlange und kommt morgen im Bündel mit.
    """
    from nwz.delivery import deliver_message

    n = _jetzt(jetzt)
    if ist_nachtruhe(n):
        return 0

    heute = _tag(n)
    verschickt = 0
    for owner_id in store.owners_with_due_notifications(n.isoformat(timespec="seconds")):
        owner = store.get_owner_delivery(owner_id)
        if not owner:
            continue
        offen = store.due_notifications(owner_id, n.isoformat(timespec="seconds"))
        if not offen:
            continue

        frei = TAGESGRENZE - store.notifications_sent_on(owner_id, heute)
        if frei <= 0:
            logger.info("owner %s: Tagesgrenze erreicht, %d warten auf morgen",
                        owner_id, len(offen))
            continue

        # Passt alles einzeln? Sonst nimmt die letzte freie Zustellung den Rest
        # als ein Bündel mit — „ab der dritten wird gebündelt statt gestapelt".
        einzeln = offen if len(offen) <= frei else offen[: frei - 1]
        rest = offen[len(einzeln):]

        for p in einzeln:
            deliver_message(owner, p["body_html"], email_subject=p["title"], push_url=p["url"])
            store.mark_notification_sent([p["id"]], n.isoformat(timespec="seconds"))
            verschickt += 1

        if rest:
            titel, html, url = _buendel(rest)
            deliver_message(owner, html, email_subject=titel, push_url=url)
            store.mark_notification_sent([p["id"] for p in rest], n.isoformat(timespec="seconds"),
                                         bundled=True)
            verschickt += 1

    if stats is not None:
        stats["Zugestellte Benachrichtigungen"] = verschickt
    return verschickt
