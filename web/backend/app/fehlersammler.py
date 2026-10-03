"""Eine Ausnahme festhalten — für den 500er-Handler UND für Ströme.

**Warum eine eigene Datei.** Der Sammler lebte bis 03.10.2026 nur im
Ausnahme-Handler von ``main.py``. Ein Fehler MITTEN in einem SSE-Strom
erreicht den nie: Der Strom hat schon mit 200 geantwortet, der Generator
fängt die Ausnahme selbst und schickt einen ``error``-Rahmen. Lottis Fenster
schrieb so jeden Absturz nur ins ``journalctl`` — genau die Lücke, die
``kern/fehler.py`` schließen sollte. Die Router können ``main`` nicht
importieren (Ring), also steht der Weg hier.

**Was gespeichert wird, entscheidet weiter** ``kern.fehler.aufbereiten`` —
Fingerabdruck, Typ, gesäuberter Text, Routen-VORLAGE, kurze Spur. Kein
Anfragekörper, keine Frage, kein Seiteninhalt.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from .config import get_settings

logger = logging.getLogger("ratslotse.web.fehler")


def sammeln(exc: BaseException, methode: str, route: str | None,
            pfad: str) -> Callable[[], None] | None:
    """Ablegen; bei der ERSTEN Begegnung die Meldung zurückgeben.

    Die Meldung geht übers Netz und läuft deshalb NICHT hier, sondern dort,
    wo der Aufrufer sie nach der Antwort einplant (``BackgroundTask``). Wirft
    nie — im schlimmsten Fall gibt es keinen Eintrag, wie vorher.
    """
    try:
        from kern import fehler as fehlerhilfe
        from kern.store import Store

        daten = fehlerhilfe.aufbereiten(exc, methode, route, pfad)
        store = Store(get_settings().ratslotse_db)
        try:
            neu = store.merke_request_fehler(daten)
        finally:
            store.close()
        if not neu:
            return None

        from kern import alerts

        text = (f"<b>{daten['exc_type']}</b> bei "
                f"<code>{daten['method']} {daten['route']}</code>\n\n"
                f"{daten['message']}\n\n<code>{daten['trace']}</code>")

        def melden() -> None:
            alerts.notify_admin(
                text, betreff="Ratslotse – neuer Fehler im Web",
                fusszeile="Erste Begegnung mit dieser Fehlerart. "
                          "Weitere Vorkommen zählt das Admin-Panel mit, ohne "
                          "erneut zu melden.")
        return melden
    except Exception:  # noqa: BLE001 — der Sammler bleibt folgenlos
        logger.exception("Fehler ließ sich nicht sammeln")
        return None
