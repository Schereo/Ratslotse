"""Keine Jahreszahl im Feldnamen, keine Jahreszahl neben einem Wahlwert.

Bis 09/2026 hieß das Vergleichsfeld ``seats_2021`` und das Wort „2021" stand
an rund dreißig Stellen im Frontend und in den Teilen-Bildern. Beides ist
dieselbe Schuld: Bei der nächsten Kommunalwahl wäre der Feldname eine Lüge,
die kein Client umbenennen kann, und die dreißig Texte wären dreißig stille
Fehler — nichts bricht, es steht nur Falsches da.

Dieser Wächter prüft beides und in beide Richtungen: dass die alten Namen
nirgends mehr auftauchen UND dass die Ausnahmen, die stehen bleiben dürfen,
noch gebraucht werden.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import elections  # noqa: E402

#: Die Felder, die es nicht mehr geben darf — samt dem, was stattdessen gilt.
ALTE_FELDER = {
    "seats_2021": "seats_previous",
    "share_2021_pct": "share_previous_pct",
}

#: Wo gesucht wird: **nur** die Wahl-Fläche. Der Haushalt ist voller richtiger
#: Jahreszahlen („seit 2018", „Plan von 2020") — dort wäre dieselbe Suche
#: sinnlos. Die Referenzordner sind ebenfalls nicht dabei: Dort GEHÖRT die
#: Jahreszahl in den Dateinamen, sie benennt den Bestand.
ORDNER = (
    WURZEL / "web" / "backend" / "app" / "election",
    WURZEL / "web" / "backend" / "app" / "prediction",
    WURZEL / "web" / "frontend" / "components" / "wahlabend",
    WURZEL / "web" / "frontend" / "components" / "tipp",
    WURZEL / "web" / "frontend" / "app" / "wahlabend",
    WURZEL / "web" / "frontend" / "app" / "tipp",
)
EINZELN = (
    WURZEL / "web" / "backend" / "app" / "routers" / "wahlabend.py",
    WURZEL / "web" / "backend" / "app" / "routers" / "tippspiel.py",
    WURZEL / "web" / "frontend" / "lib" / "wahlabend.ts",
    WURZEL / "web" / "frontend" / "lib" / "tipp.ts",
    WURZEL / "web" / "frontend" / "lib" / "stichwahl.ts",
    WURZEL / "web" / "frontend" / "lib" / "wahl-flaechen.ts",
)
ENDUNGEN = (".py", ".ts", ".tsx")


def _dateien():
    for ordner in ORDNER:
        for pfad in sorted(ordner.rglob("*")):
            if pfad.suffix in ENDUNGEN and pfad.is_file():
                yield pfad
    for pfad in EINZELN:
        if pfad.is_file():
            yield pfad


#: Stellen, an denen eine Jahreszahl bleiben DARF, mit Grund. Jede wird
#: geprüft: Verschwindet die Zeile, meldet sich der zweite Test.
ERLAUBT = {
    # Die Verifikation der Sitzzuteilung IST an 2021 gebunden — sie wurde
    # gegen dieses amtliche Ergebnis gerechnet und bleibt es auch 2031.
    ("web/backend/app/election/seats.py", "Ratswahl Oldenburg 2021"),
    ("web/frontend/components/wahlabend/view.tsx", "Gegen das amtliche Ergebnis von 2021 geprüft"),
    # Eine Erfahrung aus jener Nacht, kein Vergleichswert.
    ("web/frontend/components/wahlabend/view.tsx", "2021 lag das vorläufige Ergebnis"),
}

#: „2021" NEBEN einem Wahlwert — das Muster, das dieser Wächter jagt.
VERDAECHTIG = re.compile(r"(?:zu|von|gegenüber|seit|Vergleich (?:zu|mit))\s+20\d\d\b")


def _sichtbare_zeilen(pfad: Path) -> list[tuple[int, str]]:
    """Nur Text, der Leser*innen erreichen kann — Kommentare zählen nicht.

    Das ist der Unterschied, an dem eine erste Fassung dieses Wächters
    gescheitert ist: In den Modulen steht die Jahreszahl zu Recht überall
    („die Zahlen von 2021 im Register von 2026", „altes Schema von 2021") —
    das ist Herkunft, kein Anzeigetext. Gejagt wird nur, was in einer
    Zeichenkette steht, die jemand liest.
    """
    text = pfad.read_text(encoding="utf-8")
    if pfad.suffix == ".py":
        import ast

        try:
            baum = ast.parse(text)
        except SyntaxError:  # pragma: no cover — dann meldet sich ruff
            return []
        docstrings = {
            id(k.body[0].value) for k in ast.walk(baum)
            if isinstance(k, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and k.body and isinstance(k.body[0], ast.Expr) and isinstance(k.body[0].value, ast.Constant)
            and isinstance(k.body[0].value.value, str)
        }
        return [(n.lineno, n.value) for n in ast.walk(baum)
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]

    # TypeScript: Zeilen- und Blockkommentare raus, der Rest zählt (JSX-Text
    # steht nackt im Code, nicht in Anführungszeichen — er muss mitgeprüft
    # werden).
    ohne_block = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    zeilen = []
    for nr, zeile in enumerate(ohne_block.splitlines(), start=1):
        blank = re.sub(r"//.*$", "", zeile)
        if blank.strip():
            zeilen.append((nr, blank))
    return zeilen


@pytest.mark.parametrize("alt,neu", sorted(ALTE_FELDER.items()))
def test_die_alten_feldnamen_sind_weg(alt: str, neu: str):
    """Der Feldname selbst darf keine Jahreszahl tragen.

    Ein Client kann ihn nicht umbenennen: Was der Vertrag sagt, liest er.
    Die eine Stelle, an der der alte Name stehen bleiben darf, ist der
    Erklärtext in ``antworten.py`` — dort steht, warum umbenannt wurde.
    """
    treffer = []
    for pfad in _dateien():
        for nr, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), start=1):
            if alt in zeile and not zeile.lstrip().startswith(("#", "//", "*")):
                treffer.append(f"{pfad.relative_to(WURZEL)}:{nr}")
    assert not treffer, (
        f"\u201e{alt}\u201c heißt jetzt \u201e{neu}\u201c — hier steht noch der alte Name:\n  "
        + "\n  ".join(treffer))


def test_keine_jahreszahl_neben_einem_wahlwert():
    """„zu 2021", „gegenüber 2021", „Vergleich zu 2021" — alles Texte, die
    aus ``election.previous_label`` kommen müssen."""
    treffer = []
    for pfad in _dateien():
        rel = str(pfad.relative_to(WURZEL))
        for nr, zeile in _sichtbare_zeilen(pfad):
            if not VERDAECHTIG.search(zeile):
                continue
            if any(rel == datei and stueck in zeile for datei, stueck in ERLAUBT):
                continue
            treffer.append(f"{rel}:{nr}: {zeile.strip()[:100]}")
    assert not treffer, (
        "Diese Stellen schreiben eine Jahreszahl, die aus der Antwort kommen sollte "
        "(`election.previous_label`):\n  " + "\n  ".join(treffer))


def test_die_ausnahmen_werden_noch_gebraucht():
    """Eine Ausnahmeliste, die nur wächst, ist kaputt (tests/CLAUDE.md)."""
    verwaist = []
    for datei, stueck in sorted(ERLAUBT):
        pfad = WURZEL / datei
        if not pfad.is_file() or stueck not in pfad.read_text(encoding="utf-8"):
            verwaist.append(f"{datei}: „{stueck}“")
    assert not verwaist, "Diese Ausnahmen gibt es nicht mehr — raus damit:\n  " + "\n  ".join(verwaist)


def test_jede_ratswahl_sagt_wie_ihre_vorwahl_heisst():
    """Ohne Etikett zeigte die Seite „Punkte gegenüber " und sonst nichts."""
    for wahl in elections.all().values():
        if wahl.kind != "council":
            continue
        assert wahl.previous_label, f"{wahl.slug}: „previous_label“ fehlt"
        assert wahl.reference_folder is not None
        jahr = wahl.reference_folder.name.rsplit("-", 1)[-1]
        assert wahl.previous_label == jahr, (
            f"{wahl.slug}: Etikett „{wahl.previous_label}“ passt nicht zum Referenzordner "
            f"„{wahl.reference_folder.name}“ — eine der beiden Angaben ist falsch.")
