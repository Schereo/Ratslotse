"""Warum ein langer Lauf freiwillig aufhört — und woran er das merkt.

**Der Anlass.** ``check_cities.py`` läuft sonntags ab 5 Uhr. Am 20.09.2026
lief er vierzehn Stunden (ein Versionssprung des ``fit``-Annotators hatte
9.560 Urteile entwertet, s. ``scripts/check_cities.py``), und solange er lief,
brach **jeder** Prod-Deploy in der Vorflug-Prüfung ab: sechs an einem Tag. Der
Abbruch war folgenlos, aber endlos — ein abgebrochener Deploy startet sich
nicht von selbst neu, und Prod stand 33 Stunden auf dem Vortagsstand.

Die Wartungsbarriere (``kern/maintenance.py``) hilft hier nicht: Sie sperrt
**neue** Datenbank-Zugriffe, einen bereits laufenden Prozess erreicht sie
nicht. Und ein ``kill`` wäre die Holzhammer-Fassung — er träfe den Lauf
mitten in einem Stapel.

**Die Lösung ist kooperativ.** Der Deploy legt ``data/.deploy-wartet``, bevor
er irgendetwas anfasst. Lange Läufe sehen an ihrer nächsten Stapelgrenze nach,
behalten das bereits Geschriebene und hören auf. Nächster Lauf macht weiter,
wo dieser aufgehört hat — die Arbeitslisten der Pipeline fragen ohnehin „was
fehlt noch?", nicht „wo war ich?".

**Genau deshalb wird inkrementell geschrieben und nicht am Ende.** Ein
14-Stunden-Lauf, der erst zum Schluss schreibt, ist alles-oder-nichts: Ein
Abbruch bei Stunde dreizehn wirft einen ganzen Tag Modellkosten weg. Das
stapelweise Schreiben ist das, was das Zur-Seite-Treten kostenlos macht.

**Die Frist ist die zweite Hälfte.** Ein Lauf, der in den Abend hineinläuft,
ist auch ohne Deploy ein Problem: Er hält eine VM mit zwei Kernen besetzt, und
niemand hat entschieden, dass er so lange dauern darf. ``frist_sekunden``
macht daraus eine Zahl, die in der ``.env`` steht.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

#: Der Marker, mit dem der Deploy um Platz bittet. Liegt neben der
#: Wartungsbarriere in ``data/`` und wird vom Deploy wieder entfernt.
WARTET_NAME = ".deploy-wartet"

#: Ab wann ein liegengebliebener Marker nicht mehr zählt. Ein Deploy dauert
#: rund zehn Minuten; was älter ist, hat ein abgebrochener Lauf vergessen
#: wegzuräumen. Ohne diese Kappe wäre aus der Bitte ein Knebel geworden: Jeder
#: Wochenlauf träte danach sofort zur Seite und täte nie wieder etwas — und
#: zwar still, weil „ich mache gleich wieder weiter" genau so aussieht wie
#: „alles erledigt". Dieselbe Überlegung wie ``LIMIT_SECONDS`` in
#: ``scripts/ops_deploy_window.py``.
WARTET_MAX_ALTER = 30 * 60


@dataclass(frozen=True)
class Grund:
    """Warum aufgehört wurde — als Kennzahl-Schlüssel und als Klartext."""
    schluessel: str
    text: str


class Stopp:
    """Fragt an einer Stapelgrenze: weitermachen oder aufhören?

    Ohne Argumente sagt sie immer „weitermachen" — Tests und Läufe von Hand
    brauchen dann nichts zu wissen.
    """

    def __init__(self, daten_dir: Path | None = None,
                 frist_sekunden: float | None = None,
                 jetzt=time.monotonic,
                 marker_max_alter: float = WARTET_MAX_ALTER) -> None:
        self._marker = Path(daten_dir) / WARTET_NAME if daten_dir else None
        self._jetzt = jetzt
        self._max_alter = marker_max_alter
        self._frist = (self._jetzt() + frist_sekunden
                       if frist_sekunden and frist_sekunden > 0 else None)

    def _deploy_wartet(self) -> bool:
        """Liegt der Marker — und ist er frisch genug, um ernst zu sein?"""
        if self._marker is None:
            return False
        try:
            alter = time.time() - self._marker.stat().st_mtime
        except OSError:
            return False
        return alter <= self._max_alter

    def grund(self) -> Grund | None:
        """``None`` heißt weitermachen.

        Der Deploy zuerst: Er wartet auf eine Antwort, die Frist nicht.
        """
        if self._deploy_wartet():
            return Grund("deploy", "Ein Deploy wartet — der Lauf tritt zur Seite "
                                   "und macht beim nächsten Mal weiter.")
        if self._frist is not None and self._jetzt() >= self._frist:
            return Grund("frist", "Die Frist für diesen Lauf ist um — der Rest "
                                  "kommt beim nächsten Mal.")
        return None


def aus_umgebung(daten_dir: Path, variable: str,
                 vorgabe_sekunden: float | None = None,
                 jetzt=time.monotonic) -> Stopp:
    """Ein ``Stopp`` mit der Frist aus der ``.env``.

    Ein unlesbarer oder negativer Wert heißt „keine Frist" und nicht „sofort
    aufhören": Ein Tippfehler in der ``.env`` darf einen Wochenlauf nicht
    stillschweigend auf null Sekunden setzen.
    """
    roh = (os.environ.get(variable) or "").strip()
    frist = vorgabe_sekunden
    if roh:
        try:
            gelesen = float(roh)
        except ValueError:
            gelesen = -1.0
        frist = gelesen if gelesen > 0 else None
    return Stopp(daten_dir, frist, jetzt)
