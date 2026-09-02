"""Das Merge-Tor — die Entscheidungen, die ohne GitHub prüfbar sind.

Der Netzteil gehört nicht in die Suite. Prüfbar ist die Logik, an der es
tatsächlich gescheitert ist: Was zählt als „fertig und grün", und was sieht
nur so aus.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from scripts import merge_wenn_gruen as tor  # noqa: E402


urteil = tor.urteil


def test_alles_gruen_ist_gruen():
    assert urteil([("test", "completed", "success"),
                   ("docs", "completed", "success")]) == "gruen"


def test_eine_laufende_pruefung_ist_kein_gruen():
    """Genau der Fehler vom 02.09.2026: gemergt, während `test` noch lief."""
    assert urteil([("test", "in_progress", "—"),
                   ("docs", "completed", "success")]) == "wartet"


def test_gar_keine_pruefung_ist_kein_gruen():
    """Der gefährlichste Zustand: Ein Pull Request mit Konflikt bekommt keine
    Läufe — null Prüfungen sähen sonst aus wie „alles grün"."""
    assert urteil([]) == "wartet"


def test_eine_einzige_pruefung_reicht_nicht():
    assert urteil([("docs", "completed", "success")]) == "zu wenige"


def test_ein_fehlschlag_ist_rot():
    assert urteil([("test", "completed", "failure"),
                   ("docs", "completed", "success")]) == "rot"


def test_uebersprungen_und_neutral_gelten_als_bestanden():
    """`skipped` entsteht durch Pfad-Filter — der iOS-Auftrag läuft nur, wenn
    jemand `ios/` anfasst. Das ist kein Fehlschlag."""
    assert urteil([("build", "completed", "skipped"),
                   ("test", "completed", "success"),
                   ("docs", "completed", "neutral")]) == "gruen"


def test_hilfe_laeuft():
    ergebnis = subprocess.run([sys.executable, "scripts/merge_wenn_gruen.py", "--help"],
                              cwd=WURZEL, capture_output=True, text=True)
    assert ergebnis.returncode == 0, ergebnis.stderr
    assert "--trocken" in ergebnis.stdout


def test_gh_versucht_es_erneut(monkeypatch):
    """Ein Netzaussetzer beim Warten darf das Tor nicht abbrechen lassen.

    Am 02.09.2026 mitten in einem Lauf: „error connecting to api.github.com".
    Der Pull Request blieb ungemergt, obwohl alles grün war, und der nächste
    Anlauf musste von vorn warten.
    """
    import subprocess as sp

    versuche = {"n": 0}

    class Ergebnis:
        def __init__(self, kode, aus="", fehler=""):
            self.returncode, self.stdout, self.stderr = kode, aus, fehler

    def unzuverlaessig(*_a, **_k):
        versuche["n"] += 1
        if versuche["n"] < 3:
            return Ergebnis(1, fehler="error connecting to api.github.com")
        return Ergebnis(0, aus="endlich\n")

    monkeypatch.setattr(sp, "run", unzuverlaessig)
    monkeypatch.setattr(tor, "subprocess", sp)
    monkeypatch.setattr(tor.time, "sleep", lambda _s: None)
    assert tor.gh("api", "x", versuche=3) == "endlich"
    assert versuche["n"] == 3


def test_gh_gibt_irgendwann_auf(monkeypatch):
    import subprocess as sp

    class Ergebnis:
        returncode, stdout, stderr = 1, "", "dauerhaft kaputt"

    monkeypatch.setattr(sp, "run", lambda *_a, **_k: Ergebnis())
    monkeypatch.setattr(tor, "subprocess", sp)
    monkeypatch.setattr(tor.time, "sleep", lambda _s: None)
    import pytest
    with pytest.raises(SystemExit) as fehler:
        tor.gh("api", "x", versuche=2)
    assert "dauerhaft kaputt" in str(fehler.value)
