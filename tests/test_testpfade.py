"""Wächter: Kein Test hängt an einem Pfad, den es nur auf EINEM Rechner gibt.

Der gemessene Fall: Fünf Messungen der Haushalts-Facetten (`business_plans`,
`bylaw`, `donations`, `execution`, `companies`) trugen den Scratchpad-Pfad
einer Agenten-Sitzung fest im Code::

    /private/tmp/claude-501/…-worktrees-haushaltsseite-review-763d8c/…/council.sqlite

Abgesichert mit ``if not ECHTE_DB.exists(): pytest.skip(...)`` — und genau das
macht den Fehler unsichtbar: Das Verzeichnis war mit der Sitzung weg, die
Messungen wurden ÜBERALL übersprungen, lokal wie in der CI, und nichts wurde
je rot. Was sie prüfen sollten, prüfte monatelang niemand.

Ein toter Pfad hinter einem `skip` meldet sich nie von selbst. Deshalb ein
Wächter und keine Konvention — die Bauform steht in ``CLAUDE.md`` nebenan.
"""
import re
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent

#: Pfad-Anfänge, die es nur auf einem Rechner oder in einer Sitzung gibt.
#: ``/tmp/claude-…`` und ``/private/tmp/claude-…`` sind die Scratchpads der
#: Coding-Agents (mit der Sitzung weg), ``/var/folders/`` das macOS-Pendant,
#: ``/Users/`` und ``/home/`` fremde Home-Verzeichnisse.
MASCHINENPFADE = re.compile(
    r"""["']/(?:private/)?tmp/claude-"""      # Agenten-Scratchpad
    r"""|["']/var/folders/"""                 # macOS-Temp
    r"""|["']/Users/"""                       # Home (macOS)
    r"""|["']/home/[a-z]"""                   # Home (Linux)
)

#: Ausdrücklich erlaubte Stellen: ``datei -> begründung``. Hier stehen NUR
#: erfundene Pfade, die als Eingabe dienen und nie geöffnet werden.
AUSNAHMEN = {
    "test_hooks_einrichten.py":
        "'/Users/wer/repo/.githooks' ist ein erfundener core.hooksPath — "
        "der Fall, den soll_setzen() erkennen muss, nicht eine Datei, die "
        "jemand aufmacht.",
}

#: Testmodule setzen ``COUNCIL_DB`` beim Import auf eine leere Wegwerf-
#: Datenbank. Wer eine ECHTE Datenbank sucht, darf deshalb nicht daran
#: hängen — sonst ist ``exists()`` wahr, der Bestand leer und der Test je nach
#: Modul-Reihenfolge mal grün, mal rot (06.09.2026 an #1142 gemessen).
MESS_VARIABLE = "RATSLOTSE_MESS_DB"
COUNCIL_DB_GELESEN = re.compile(r"""environ\.get\(\s*["']COUNCIL_DB["']""")

#: Erlaubte COUNCIL_DB-Leser: ``datei -> begründung``. Hier wird die Variable
#: NICHT benutzt, um eine echte Datenbank zu finden.
COUNCIL_DB_AUSNAHMEN = {
    "test_finanzquellen.py":
        "liest COUNCIL_DB im Quelltext eines erzeugten Prüf-Skripts — der Test "
        "belegt, dass der Cron die Variable an das Ingest-Skript durchreicht, "
        "und öffnet selbst keine Datenbank.",
}


def _testdateien():
    return sorted(p for p in TESTS.glob("test_*.py") if p.name != Path(__file__).name)


def test_kein_test_haengt_an_einem_maschinenpfad():
    """Ein Pfad in ein fremdes Scratchpad ist tot, und ein `skip` verschweigt es."""
    treffer = []
    for pfad in _testdateien():
        if pfad.name in AUSNAHMEN:
            continue
        for nr, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), 1):
            if MASCHINENPFADE.search(zeile):
                treffer.append(f"{pfad.name}:{nr}: {zeile.strip()[:90]}")

    assert not treffer, (
        "Diese Tests tragen einen Pfad, den es nur auf einem Rechner bzw. in\n"
        "einer Agenten-Sitzung gibt. Hinter einem `if not …exists(): skip` wird\n"
        "daraus eine Messung, die überall stillschweigend entfällt.\n\n"
        + "\n".join(treffer)
        + "\n\nSo geht es richtig (s. test_geld_measures.py):\n"
        f'    ECHTE_DB = Path(os.environ.get("{MESS_VARIABLE}")\n'
        '                    or Path(__file__).resolve().parents[1] / "data" / "council.sqlite")\n'
        "Den Abzug holt `python scripts/lokale_daten.py hol` + `setz`.\n"
        "Ist der Pfad erfunden und wird nie geöffnet, gehört er mit Begründung\n"
        "in AUSNAHMEN in dieser Datei."
    )


@pytest.mark.parametrize("liste,muster,was", [
    (AUSNAHMEN, MASCHINENPFADE, "trägt keinen Maschinenpfad mehr"),
    (COUNCIL_DB_AUSNAHMEN, COUNCIL_DB_GELESEN, "liest COUNCIL_DB nicht mehr"),
])
def test_ausnahmelisten_sind_nicht_veraltet(liste, muster, was):
    """Eine Ausnahmeliste, die nur wächst, ist kaputt — also die Gegenrichtung."""
    veraltet = []
    for name in sorted(liste):
        pfad = TESTS / name
        if not pfad.exists():
            veraltet.append(f"{name}: Datei gibt es nicht mehr")
        elif not muster.search(pfad.read_text(encoding="utf-8")):
            veraltet.append(f"{name}: {was}")

    assert not veraltet, (
        "Diese Einträge in AUSNAHMEN braucht niemand mehr — bitte streichen:\n  "
        + "\n  ".join(veraltet)
    )


@pytest.mark.parametrize("pfad", _testdateien(), ids=lambda p: p.name)
def test_messtests_haengen_nicht_an_council_db(pfad):
    """Die echte Datenbank kommt aus der EIGENEN Variable, nicht aus COUNCIL_DB.

    ``COUNCIL_DB`` setzen über ein Dutzend Backend-Testmodule beim Import auf
    eine leere Wegwerf-Datei. Ein Messtest, der sie liest, misst dann je nach
    Modul-Reihenfolge gegen einen leeren Bestand."""
    if pfad.name in COUNCIL_DB_AUSNAHMEN:
        pytest.skip(COUNCIL_DB_AUSNAHMEN[pfad.name])
    zeilen = [
        f"{pfad.name}:{nr}: {z.strip()[:90]}"
        for nr, z in enumerate(pfad.read_text(encoding="utf-8").splitlines(), 1)
        if COUNCIL_DB_GELESEN.search(z)
    ]
    assert not zeilen, (
        "Hier wird COUNCIL_DB gelesen, um eine echte Datenbank zu finden:\n"
        + "\n".join(zeilen)
        + f"\n\nBackend-Testmodule setzen COUNCIL_DB beim Import auf eine LEERE\n"
        f"Wegwerf-Datenbank — `exists()` ist dann wahr und der Bestand leer.\n"
        f'Stattdessen os.environ.get("{MESS_VARIABLE}") benutzen.'
    )
