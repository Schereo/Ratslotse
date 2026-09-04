"""Wächter für den Geltungsbereich der Typprüfung (`pyrightconfig.json`).

**Wogegen.** Ein Typprüfer stirbt nicht daran, dass jemand ihn abschaltet —
er stirbt daran, dass ein roter Lauf mit einem Eintrag in ``exclude``
beruhigt wird. Nach dem dritten Mal prüft er nichts mehr, meldet aber weiter
„grün". Deshalb steht hier, was Stufe 1 abdeckt, und zwar so, dass ein
Herausnehmen den Test rot macht statt die CI grün.

**Beide Richtungen**, wie jeder Wächter hier: Fehlt etwas im Geltungsbereich?
Und ist eine Ausnahme überflüssig geworden — also inzwischen von selbst
sauber und damit reif für die nächste Stufe?
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
KONFIG = WURZEL / "pyrightconfig.json"

#: Was Stufe 1 abdeckt. Wer hier etwas herausnimmt, nimmt es aus der CI —
#: das soll eine bewusste Änderung an dieser Liste sein, kein Nebeneffekt.
STUFE_1 = ("kern", "web/backend/app")

#: Verzeichnisse mit Projekt-Code, die (noch) nicht geprüft werden, mit dem
#: Grund. Jeder Eintrag ist eine Schuld, kein Zustand.
NOCH_NICHT = {
    "web/backend/app/routers":
        "Die Router bauen ihre Antwort-Dicts aus Store-Methoden, die "
        "`dict[str, Any]` liefern. Sinnvoll wird die Prüfung mit einem "
        "typisierten Store — dann fängt sie die Fehlerklasse aus "
        "`antworten.py`: fehlender Pflichtschlüssel (500) und stumm "
        "abgeschnittenes Feld.",
}


def _konfig() -> dict:
    """`pyrightconfig.json` mit ``//``-Kommentaren lesen.

    pyright erlaubt sie, ``json.load`` nicht. Die Zeilen fliegen raus; in
    keiner davon steht ein ``//`` innerhalb einer Zeichenkette (und stünde es
    dort, meldete der Test es als Syntaxfehler statt still das Falsche zu
    prüfen).
    """
    roh = KONFIG.read_text(encoding="utf-8")
    ohne = re.sub(r"^\s*//.*$", "", roh, flags=re.MULTILINE)
    return json.loads(ohne)


def test_stufe_1_steht_vollstaendig_im_geltungsbereich():
    include = _konfig()["include"]
    fehlt = [p for p in STUFE_1 if p not in include]
    assert not fehlt, (
        f"{fehlt} steht nicht mehr in `include` von pyrightconfig.json. "
        "Diese Pfade sind die geteilte Infrastruktur — sie ungeprüft zu "
        "lassen, ist die teuerste der möglichen Abkürzungen. Wenn das "
        "Absicht ist, gehört STUFE_1 in dieser Datei mit geändert.")


def test_keine_stillen_zusatz_ausnahmen():
    """`exclude` darf Werkzeug-Verzeichnisse nennen — und sonst nur das,
    was oben mit Grund steht."""
    werkzeug = {"**/__pycache__", "**/node_modules", "**/.venv"}
    exclude = set(_konfig()["exclude"])
    unerklaert = exclude - werkzeug - set(NOCH_NICHT)
    assert not unerklaert, (
        f"Neue Ausnahme(n) in pyrightconfig.json: {sorted(unerklaert)}. "
        "Eine Ausnahme ist eine Schuld und braucht einen Grund: Trag sie in "
        "NOCH_NICHT in tests/test_typpruefung.py ein — mit dem, was passieren "
        "muss, damit sie wieder verschwindet.")


def test_jede_ausnahme_zeigt_auf_vorhandenen_code():
    for pfad in NOCH_NICHT:
        assert (WURZEL / pfad).is_dir(), (
            f"NOCH_NICHT nennt {pfad!r}, das Verzeichnis gibt es nicht mehr. "
            "Eintrag in tests/test_typpruefung.py und in pyrightconfig.json "
            "löschen.")


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="pyright braucht eine Node-Laufzeit")
def test_ausnahmen_sind_noch_noetig():
    """Die zweite Richtung: Ist eine Ausnahme sauber geworden?

    Dann ist sie überflüssig, und der Geltungsbereich soll wachsen. Ohne
    diesen Test bliebe ein Verzeichnis für immer draußen, nur weil es einmal
    rot war.
    """
    for pfad, grund in NOCH_NICHT.items():
        r = subprocess.run(
            [sys.executable, "-m", "pyright", "--pythonpath", sys.executable,
             "--outputjson", "--project", "/dev/null", pfad],
            cwd=WURZEL, capture_output=True, text=True)
        if not r.stdout.strip():
            pytest.skip(f"pyright nicht lauffähig: {r.stderr[:200]}")
        fehler = json.loads(r.stdout)["summary"]["errorCount"]
        assert fehler > 0, (
            f"{pfad} meldet keine Typfehler mehr — die Ausnahme ist "
            f"überflüssig. Aus `exclude` in pyrightconfig.json und aus "
            f"NOCH_NICHT hier entfernen, dann hält die CI es fest.\n"
            f"Grund, aus dem es draußen stand: {grund}")
