"""„Neu bei Ratslotse" verschicken — die Highlights eines Releases als Mail/Push.

Der Text kommt aus ``kern/releases.py``, der Weg aus ``kern/notify.py``. Dass
er über die **Warteschlange** geht und nicht direkt an ``send_email``, ist der
Punkt: Nur so greifen der Aus-Schalter des Kontos, der eigene Anlass-Schalter
(``N7_NEWS``), die Nachtruhe, die Tagesgrenze und die Wiederholung bei einem
Zustell-Ausfall. Eine Ankündigung, die diese vier Grenzen umgeht, wäre genau
der Newsletter, der Ratslotse nicht sein soll.

**Von Hand, nicht aus einem Cron.** Alle anderen Anlässe reagieren auf den Rat;
dieser hier auf uns. Er wird im Admin-Panel ausgelöst, wenn der Deploy ein paar
Tage stabil ist — Ausliefern und Ankündigen sind zwei Entscheidungen.

**Zweimal drücken schadet nicht.** ``news_sent_version`` am Konto vermerkt, wer
diese Version schon bekommen hat; der zweite Lauf findet null Empfänger. Auch
Konten, für die nichts eingereiht wurde (Anlass aus, Zustellung aus), werden
vermerkt — sonst fragte sie jeder weitere Lauf erneut.
"""
from __future__ import annotations

import html
import logging

from kern import digest_email, notify, releases
from kern.releases import Release

logger = logging.getLogger("kern.news")

#: Wohin der Tipp auf die Push-Mitteilung führt: die Übersicht, auf der die
#: Karte steht. Ein einzelnes Highlight wäre das falsche Ziel — die Meldung
#: kündigt mehrere an.
TAP_ZIEL = "/dashboard"


def title_for(release: Release) -> str:
    """Die Betreffzeile: Was es gibt, nicht welche Zahl es trägt.

    Die Version steht in der Karte und im Changelog. Im Postfach konkurriert
    „Ratslotse 2.3.0" mit allem anderen — der Halbsatz aus dem Eintrag sagt
    wenigstens, worum es geht.
    """
    return f"Neu bei Ratslotse: {release.title}"


def push_text_for(release: Release) -> str:
    """Die Vorschau auf dem Sperrbildschirm — die Sachen, nicht die Einleitung.

    Dieselbe Regel wie bei den Ratsmeldungen (``kern.notify._buendel``): Dort
    sind es die Titel der Posten, hier die der Highlights.
    """
    text = " · ".join(h.title for h in release.highlights)
    return text[:179] + "…" if len(text) > 180 else text


def body_html(release: Release) -> str:
    """Der Meldungskörper für Mail und Warteschlange.

    Ohne Hülle und ohne Anrede — beides setzt ``kern.delivery.deliver_message``
    beim Zustellen. Je Highlight ein Block mit Titel, Satz und leisem Weg
    dorthin; darunter der eine Knopf zurück in die App und der Verweis auf den
    vollständigen Changelog.
    """
    teile = [
        "<p style='margin:0'>Ratslotse hat ein Update bekommen. "
        "Das Wichtigste in Kürze:</p>"
    ]
    for h in release.highlights:
        # Dasselbe Bild wie auf der Karte, nur eben still: Ein Clip liefe in
        # keinem Postfach, sein Standbild schon.
        bild = ""
        if h.media:
            quelle = h.media.poster if h.media.kind == "video" else h.media.src
            if quelle:
                bild = (
                    f"<div style='margin-top:10px'><img src='{digest_email.absolut(quelle)}' "
                    f"alt='{html.escape(h.media.alt, quote=True)}' width='552' "
                    "style='display:block;width:100%;max-width:552px;height:auto;"
                    "border-radius:12px;border:1px solid #e2e8f0'></div>"
                )
        teile.append(
            "<div style='margin-top:18px'>"
            f"<div style='font-size:15px;font-weight:700;line-height:1.35'>"
            f"{html.escape(h.title)}</div>"
            f"<div style='margin-top:4px;font-size:15px;line-height:1.55'>"
            f"{html.escape(h.text)}</div>"
            f"{bild}"
            f"{digest_email.nebenlink(digest_email.absolut(h.url), 'Ansehen')}"
            "</div>"
        )
    teile.append(digest_email.knopf(TAP_ZIEL, "In Ratslotse ansehen"))
    teile.append(
        digest_email.nebenlink(
            digest_email.absolut("/changelog"), "Alle Änderungen dieser Version"))
    # Ohne Zeilenumbrüche zusammensetzen: Die Hülle rendert mit
    # ``white-space:pre-wrap``, jedes ``\n`` zwischen den Blöcken wäre eine
    # sichtbare Leerzeile (dieselbe Falle wie in ``digest_email.buendel``).
    return "".join(teile)


def recipients(store, release: Release) -> list[int]:
    """Wer diese Ankündigung noch bekommen soll.

    Drei Bedingungen, jede mit einem Grund:

    * **noch nicht angeschrieben** — ``news_sent_version`` liegt unter dieser
      Version (Hochwassermarke, verglichen über ``releases.version_key``).
    * **die Karte noch nicht weggeklickt** — wer die Neuigkeiten schon gesehen
      hat, braucht keine Mail darüber. Die Mail ist für die, die nicht von
      selbst vorbeikommen.
    * **das Konto ist älter als das Release** — wer danach dazugekommen ist,
      hat das Feature von der ersten Minute an gehabt.

    Ob jemand Mail, Push oder nichts will, steht hier bewusst **nicht**: Das
    entscheidet ``notify.einreihen`` für alle Anlässe an einer Stelle.
    """
    ziel = releases.version_key(release.version)

    def erledigt(marke: str | None) -> bool:
        """Deckt diese Marke die Zielversion schon ab? Eine unlesbare Marke
        gilt als „nichts gemerkt" — lieber eine Ankündigung zu viel als eine
        Person, die wegen eines kaputten Werts nie wieder etwas hört."""
        if not marke:
            return False
        try:
            return releases.version_key(marke) >= ziel
        except ValueError:
            return False

    return [
        konto["id"] for konto in store.news_candidates()
        if not erledigt(konto.get("news_sent_version"))
        and not erledigt(konto.get("news_seen_version"))
        and (konto.get("created_at") or "")[:10] <= release.date
    ]


def announce(store, release: Release, *, dry_run: bool = False) -> dict:
    """Die Ankündigung einreihen. Gibt Kennzahlen zurück.

    ``queued`` zählt die tatsächlich eingereihten Meldungen, ``skipped`` die
    Konten, die den Anlass abgeschaltet haben (``einreihen`` gibt dort 0
    zurück). Beide gelten danach als angeschrieben: Ein Nein ist eine Antwort,
    keine offene Aufgabe.

    ``dry_run`` zählt nur — der Weg, mit dem das Admin-Panel die Empfängerzahl
    zeigt, bevor jemand drückt.
    """
    empfaenger = recipients(store, release)
    if dry_run:
        return {"recipients": len(empfaenger), "queued": 0, "skipped": 0}

    titel = title_for(release)
    text = body_html(release)
    push = push_text_for(release)
    erledigt: list[int] = []
    queued = 0
    for owner_id in empfaenger:
        try:
            if notify.einreihen(store, owner_id, notify.N7_NEWS, titel, text,
                                TAP_ZIEL, push_text=push):
                queued += 1
        except Exception:
            # Ein einzelnes Konto darf den Lauf nicht beenden. Es bleibt
            # unmarkiert und kommt beim nächsten Drücken wieder dran — deshalb
            # steht es NICHT in `erledigt`.
            logger.exception("Release-Ankündigung für Konto %s fehlgeschlagen", owner_id)
            continue
        erledigt.append(owner_id)
    store.mark_news_sent(erledigt, release.version)
    return {"recipients": len(erledigt), "queued": queued,
            "skipped": len(erledigt) - queued}
