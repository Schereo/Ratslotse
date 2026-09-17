"""Eine verschickte Mail festhalten — aus einem Router oder aus einer Hintergrundaufgabe.

Die Ratsmeldungen protokolliert ``kern/delivery.py`` selbst, weil sie ohnehin
alle durch ``deliver_message`` laufen. Die Dienst-Mails tun das nicht:
Bestätigungslink, Passwort-Reset, Adresswechsel und Feedback-Antwort gehen
direkt über ``kern.email.send_email``, jede aus einer anderen Ecke des
Backends. Diese Datei ist die eine Zeile, die sie alle danach aufrufen.

**Warum ein eigener Store, wenn keiner mitkommt.** Ein Teil dieser Mails geht
aus einer ``BackgroundTask`` raus, also nachdem die Antwort samt ihrer
Store-Abhängigkeit längst weg ist. Die Aufgabe öffnet dafür ohnehin schon
ihre eigene Verbindung (so macht es die Admin-FYI seit jeher); hier ist
dasselbe noch einmal, aber an einer Stelle statt in fünf.

**Nie load-bearing.** Die Mail ist raus, wenn diese Funktion gerufen wird. Ein
Fehler beim Protokollieren darf daran nichts mehr ändern — er wird geloggt
und geschluckt, wie in ``Store.protokolliere_mail`` selbst.
"""
from __future__ import annotations

import logging

from kern.store import Store

from .config import get_settings

logger = logging.getLogger("app.mailprotokoll")


def protokolliere(owner_id: int | None, anlass: str, subject: str, *,
                  ok: bool = True, message_id: str | None = None,
                  store: Store | None = None) -> None:
    """Eine Mail ins Protokoll schreiben. Wirft nie.

    ``owner_id=None`` ist zulässig (Mails an Adressen ohne Konto), erzeugt
    aber keine Zeile in der Personen-Ansicht — sie taucht nur in der
    Gesamtstatistik auf.
    """
    try:
        if store is not None:
            store.protokolliere_mail(owner_id, anlass, subject, ok=ok, message_id=message_id)
            return
        eigener = Store(get_settings().ratslotse_db)
        try:
            eigener.protokolliere_mail(owner_id, anlass, subject, ok=ok, message_id=message_id)
        finally:
            eigener.close()
    except Exception:  # noqa: BLE001 — s. Modul-Docstring
        logger.exception("Mail-Protokoll fehlgeschlagen (anlass=%s)", anlass)
