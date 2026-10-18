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

import html
import logging
import threading
import time
from collections.abc import Callable

from .config import get_settings

logger = logging.getLogger("ratslotse.web.fehler")

#: Platzhalter-Route für Fehler, die vor jedem Router fielen.
OHNE_ROUTE = "(vor dem Routing)"

#: Höchstens so viele Fehler-Mails je Stunde und Prozess. Neue Fehlerarten
#: sind begrenzt (die Routen stehen im Code), aber eine Kaskade nach einem
#: Deploy soll das Postfach und das gemeinsame Resend-Kontingent — an dem auch
#: Bestätigungs- und Passwort-Mails hängen — nicht leerräumen. Gezählt wird
#: trotzdem alles; das Panel zeigt jede Gruppe. (Sicherheitsprüfung 10/2026;
#: lebte bis zum Rückmerge im 500er-Handler von ``main.py`` — hier gilt sie
#: auch für Fehler aus Strömen.)
MAILS_JE_STUNDE = 10
_mail_zeiten: list[float] = []
_mail_sperre = threading.Lock()


def _meldung_erlaubt() -> bool:
    # Mit Sperre: `sammeln` läuft seit 10/2026 im Threadpool, mehrere 500er
    # können also gleichzeitig hier ankommen.
    with _mail_sperre:
        jetzt = time.monotonic()
        while _mail_zeiten and jetzt - _mail_zeiten[0] > 3600:
            _mail_zeiten.pop(0)
        if len(_mail_zeiten) >= MAILS_JE_STUNDE:
            return False
        _mail_zeiten.append(jetzt)
        return True


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

        # Ohne getroffene Route ist der Pfad das, was der Aufrufer geschickt
        # hat — fremde Eingabe. Er gehört weder in die Mail noch in den
        # Fingerabdruck: Sonst ergäbe jeder neue Pfad eine neue Gruppe und
        # damit eine neue Mail, und ein Fehler VOR dem Routing (die
        # Sitzungsverlängerung läuft vor jedem Router) ließe sich beliebig oft
        # auslösen (Sicherheitsprüfung 10/2026, F2).
        if not route:
            route, pfad = OHNE_ROUTE, OHNE_ROUTE
        daten = fehlerhilfe.aufbereiten(exc, methode, route, pfad)
        store = Store(get_settings().ratslotse_db)
        try:
            neu = store.merke_request_fehler(daten)
        finally:
            store.close()
        if not neu or not _meldung_erlaubt():
            return None

        from kern import alerts

        # Alles maskieren, was aus der Ausnahme kommt: Die Meldung einer
        # Ausnahme trägt oft Eingabe weiter (ein Wert, der nicht passte), und
        # `notify_admin` setzt den Text als HTML in die Mail.
        esc = html.escape
        text = (f"<b>{esc(daten['exc_type'])}</b> bei "
                f"<code>{esc(daten['method'])} {esc(daten['route'])}</code>\n\n"
                f"{esc(daten['message'])}\n\n<code>{esc(daten['trace'])}</code>")

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
