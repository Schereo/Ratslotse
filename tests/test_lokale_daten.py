"""Der Abzug für die lokale Arbeit darf keine Personendaten mitnehmen.

``scripts/lokale_daten.py`` holt die Ratsdaten von dev, damit Agenten und
Menschen gegen echte Mengen bauen statt gegen eine leere Datenbank. Zwei
Dinge müssen dabei stimmen, und beide sind still, wenn sie es nicht tun:

1. **Die nutzerbezogenen Tabellen bleiben draußen.** Das Skript liest die
   Liste aus ``council.store``, statt sie abzuschreiben — dieselbe, die das
   Konto-Löschen benutzt. Ein Abschreiben veraltete beim nächsten neuen
   Feature, und niemand würde es merken: Der Abzug sähe genauso aus.
2. **Die Konten werden gebaut, nicht geholt.** ``scripts/saat_konten.py`` legt
   erfundene Konten an; einen Abzug der echten Konten-Datenbank gibt es
   bewusst nicht, und dieser Test hält fest, dass keiner dazukommt.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SKRIPT = WURZEL / "scripts" / "lokale_daten.py"
SAAT = WURZEL / "scripts" / "saat_konten.py"


def test_die_nutzertabellen_kommen_aus_dem_code():
    """Nicht abgeschrieben — sonst veraltet die Liste lautlos."""
    sys.path.insert(0, str(WURZEL))
    from council.store import COUNCIL_USER_OWNED_TABLES

    quelle = SKRIPT.read_text()
    assert "COUNCIL_USER_OWNED_TABLES" in quelle, (
        "scripts/lokale_daten.py liest die nutzerbezogenen Tabellen nicht mehr "
        "aus council.store. Eine abgeschriebene Liste veraltet, und der Abzug "
        "trüge dann Personendaten, ohne dass es jemandem auffällt."
    )
    namen = {t for t, _ in COUNCIL_USER_OWNED_TABLES}
    fest = {n for n in namen if f'"{n}"' in quelle}
    assert not fest, (
        "Diese Tabellennamen stehen im Skript fest verdrahtet, obwohl sie aus "
        "der Liste kommen sollen: " + ", ".join(sorted(fest))
    )


def test_die_konten_datenbank_wird_nirgends_geholt():
    """Sie trägt Adressen, Tokens und Gespräche — sie bleibt auf dem Server."""
    quelle = SKRIPT.read_text()
    baum = ast.parse(quelle)
    pfade: list[str] = []
    for k in ast.walk(baum):
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            if k.value.endswith(".sqlite") and "/" in k.value:
                pfade.append(k.value)
    verboten = [p for p in pfade
                if any(n in p for n in ("ratslotse.sqlite", "nwz.sqlite"))]
    assert not verboten, (
        "Das Hol-Skript nennt eine Konten-Datenbank:\n  " + "\n  ".join(verboten)
        + "\n\nDie wird gebaut (scripts/saat_konten.py), nicht geholt."
    )


def test_die_saat_benutzt_nur_erfundene_adressen():
    """Beispieladressen, keine echten — dieselbe Regel wie im ganzen Repo."""
    quelle = SAAT.read_text()
    import re

    adressen = set(re.findall(r"[\w.+-]+@[\w.-]+\.\w+", quelle))
    erlaubt = {"admin@test.de"}
    fremd = sorted(a for a in adressen - erlaubt
                   if not a.endswith(("@example.org", "@example.com", "@test.de")))
    assert not fremd, (
        "Die Saat nennt Adressen, die jemandem gehören könnten: "
        + ", ".join(fremd)
    )
    assert adressen, "Die Saat legt gar keine Konten mehr an?"


def test_nur_lesen_kommt_an_eine_wal_datenbank(tmp_path):
    """``kern.dbfehler.nur_lesen`` liest, wo ``mode=ro`` aufgeben kann.

    Der Rückfall steht dort NICHT auf Verdacht: ``file:…?mode=ro`` ist am
    02.09.2026 zweimal an einer laufenden WAL-Datenbank gescheitert (in der
    Rauchprobe an der Konten-Datei, hier am frisch geklonten Abzug), jedes Mal
    mit „unable to open database file" — einer Meldung, die nach fehlender
    Datei klingt und keine ist.

    Nachstellen lässt sich das hier nur halb: Der Fehler braucht eine WAL, die
    ein anderer Prozess offen hält. Was der Test hält, ist die Zusage, die
    zählt — dass diese Verbindung eine WAL-Datenbank liest.
    """
    import sqlite3

    from kern.dbfehler import nur_lesen

    pfad = tmp_path / "wal.sqlite"
    auf = sqlite3.connect(pfad)
    auf.execute("PRAGMA journal_mode=WAL")
    auf.execute("CREATE TABLE t (a INTEGER)")
    auf.execute("INSERT INTO t VALUES (1)")
    auf.commit()
    try:
        # Verbindung bleibt offen: So liegen `-wal` und `-shm` daneben, und
        # die Datei ist der Fall, um den es geht.
        verbindung = nur_lesen(pfad)
        try:
            assert verbindung.execute("SELECT a FROM t").fetchone()[0] == 1
        finally:
            verbindung.close()
    finally:
        auf.close()
