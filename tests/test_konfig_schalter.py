"""Kein Schalter, den niemand liest.

**Der Fehler, gegen den das steht.** Eine Umgebungsvariable, die woanders
hinzeigt als gedacht, meldet sich nicht. Sie wird gesetzt, ignoriert, und die
Vorgabe greift — alles läuft, nur eben gegen das falsche Ziel.

Am 02.09.2026 lag genau das im Browsertest-Aufbau: ``start-backend.sh`` setzte
``NWZ_DB`` auf eine Wegwerf-Datenbank. Diesen Namen liest seit der Umbenennung
der Konten-Datenbank (08/2026) niemand mehr; er heißt ``RATSLOTSE_DB``. Die
Vorgabe zeigt auf ``data/ratslotse.sqlite`` — die Browsertests legten ihre
Konten also in der **echten lokalen Datenbank** an, und der Aufräum-Trap
löschte den leeren Wegwerf-Ordner.

Der Test hält deshalb jeden ``*_DB``-Schalter, den das Repo setzt, gegen die
Felder, die die Anwendung wirklich kennt.
"""
from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))
os.environ.setdefault("WEB_JWT_SECRET", "test-secret")


def _bekannte_schalter() -> set[str]:
    """Die Namen, auf die die Konfiguration wirklich hört."""
    from app.config import Settings

    return {name.upper() for name in Settings.model_fields}


def _gesetzte_db_schalter() -> list[tuple[str, int, str]]:
    """``(datei, zeile, name)`` für jedes gesetzte ``*_DB``."""
    gefunden: list[tuple[str, int, str]] = []

    for pfad in WURZEL.rglob("*.sh"):
        if any(t in pfad.parts for t in ("node_modules", ".git", ".venv")):
            continue
        for nr, zeile in enumerate(pfad.read_text().splitlines(), 1):
            if zeile.lstrip().startswith("#"):
                continue
            m = re.match(r"\s*export\s+([A-Z_][A-Z_0-9]*_DB)=", zeile)
            if m:
                gefunden.append((pfad.relative_to(WURZEL).as_posix(), nr, m.group(1)))

    for pfad in list((WURZEL / "tests").rglob("*.py")) + list((WURZEL / "scripts").rglob("*.py")):
        try:
            baum = ast.parse(pfad.read_text())
        except SyntaxError:
            continue
        for k in ast.walk(baum):
            # os.environ["X_DB"] = …
            if (isinstance(k, ast.Assign) and len(k.targets) == 1
                    and isinstance(k.targets[0], ast.Subscript)
                    and isinstance(k.targets[0].slice, ast.Constant)
                    and isinstance(k.targets[0].slice.value, str)
                    and k.targets[0].slice.value.endswith("_DB")):
                gefunden.append((pfad.relative_to(WURZEL).as_posix(), k.lineno,
                                 k.targets[0].slice.value))
    return gefunden


def test_jeder_gesetzte_db_schalter_wird_auch_gelesen():
    bekannt = _bekannte_schalter()
    assert "RATSLOTSE_DB" in bekannt and "COUNCIL_DB" in bekannt, (
        "Die Konfiguration kennt RATSLOTSE_DB/COUNCIL_DB nicht mehr — dann "
        "prüft dieser Test das Falsche und muss nachgezogen werden."
    )

    tot = [f"{datei}:{zeile}  {name}"
           for datei, zeile, name in _gesetzte_db_schalter()
           if name not in bekannt]
    assert not tot, (
        "Diese Stellen setzen einen Datenbank-Schalter, den die Anwendung "
        "nicht liest:\n  " + "\n  ".join(tot)
        + "\n\nDie Vorgabe greift dann still weiter — im schlimmsten Fall "
          "arbeitet ein Test gegen die echte Datenbank. Bekannte Namen: "
        + ", ".join(sorted(n for n in bekannt if n.endswith("_DB")))
    )


def _gesetzte_umgebungsvariablen() -> dict[str, str]:
    """``{NAME: datei}`` für alles, was ein Testmodul beim Import setzt."""
    gesetzt: dict[str, str] = {}
    for pfad in sorted((WURZEL / "tests").rglob("*.py")):
        try:
            baum = ast.parse(pfad.read_text())
        except SyntaxError:
            continue
        for k in ast.walk(baum):
            if (isinstance(k, ast.Assign) and len(k.targets) == 1
                    and isinstance(k.targets[0], ast.Subscript)
                    and isinstance(k.targets[0].value, ast.Attribute)
                    and k.targets[0].value.attr == "environ"
                    and isinstance(k.targets[0].slice, ast.Constant)
                    and isinstance(k.targets[0].slice.value, str)):
                gesetzt.setdefault(k.targets[0].slice.value,
                                   pfad.relative_to(WURZEL).as_posix())
    return gesetzt


def test_kein_ueberspringen_haengt_an_einer_variable_die_die_suite_selbst_setzt():
    """Eine Bedingung, die immer wahr ist, überspringt nichts.

    ``test_geld_amendments.py`` wollte nur laufen, wenn jemand mit
    ``COUNCIL_DB`` auf eine echte Datenbank zeigt. Genau diese Variable setzen
    aber drei Testmodule beim Import auf eine Wegwerf-Datei — in einem
    vollständigen Lauf ist sie also immer gesetzt. Der Test lief damit gegen
    eine leere oder längst weggeräumte Datenbank und riss den Lauf mit
    „unable to open database file" um (dev, 02.09.2026).

    Ein Merkmal, das die Suite sich selbst setzt, taugt nicht als Ja.
    """
    gesetzt = _gesetzte_umgebungsvariablen()
    assert gesetzt, "Kein Testmodul setzt mehr eine Umgebungsvariable — Leser kaputt?"

    treffer: list[str] = []
    muster = re.compile(r"""skipif\(\s*not\s+os\.environ(?:\.get\(|\[)["']([A-Z_0-9]+)["']""")
    for pfad in sorted((WURZEL / "tests").rglob("*.py")):
        for nr, zeile in enumerate(pfad.read_text().splitlines(), 1):
            for name in muster.findall(zeile):
                if name in gesetzt:
                    treffer.append(
                        f"{pfad.relative_to(WURZEL).as_posix()}:{nr}  {name} "
                        f"(gesetzt in {gesetzt[name]})")
    assert not treffer, (
        "Diese Bedingungen überspringen nie, weil die Suite die Variable "
        "selbst setzt:\n  " + "\n  ".join(treffer)
        + "\n\nNimm einen eigenen Namen, den nur ein Mensch von außen setzt."
    )
