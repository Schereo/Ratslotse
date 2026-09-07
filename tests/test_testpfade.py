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

#: ``conftest.py`` setzt ``COUNCIL_DB`` je Prozess auf eine leere Wegwerf-
#: Datenbank. Wer eine ECHTE Datenbank sucht, darf deshalb nicht daran
#: hängen — sonst ist ``exists()`` wahr und der Bestand leer
#: (06.09.2026 an #1142 gemessen).
MESS_VARIABLE = "RATSLOTSE_MESS_DB"
COUNCIL_DB_GELESEN = re.compile(r"""environ\.get\(\s*["']COUNCIL_DB["']""")

#: Umgebungsvariablen, die ausschließlich ``conftest.py`` setzen darf.
#: Ein Testmodul, das sie beim Import zuweist, verabredet sich über den
#: Prozess mit allen anderen — und wer am Ende gewinnt, hängt an der
#: Import-Reihenfolge (s. u.).
NUR_IM_CONFTEST = ("RATSLOTSE_DB", "COUNCIL_DB", "WAHLABEND_HISTORY_FILE",
                   "WEB_JWT_SECRET", "WEB_ADMIN_EMAIL", "COOKIE_SECURE",
                   "DISABLE_RATE_LIMIT")
#: Nur das SETZEN ist gemeint — ``COUNCIL_DB = os.environ["COUNCIL_DB"]``
#: liest den Wert der conftest und ist genau richtig so.
GESETZT = re.compile(
    r"""os\.environ\.setdefault\(\s*["'](?:{namen})["']"""
    r"""|os\.environ\[\s*["'](?:{namen})["']\s*\]\s*=[^=]""".format(
        namen="|".join(NUR_IM_CONFTEST)))

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


@pytest.mark.parametrize("pfad", _testdateien(), ids=lambda p: p.name)
def test_kein_testmodul_setzt_die_gemeinsamen_variablen(pfad):
    """Die Wegwerf-Datenbanken gehören der ``conftest.py``, nicht den Modulen.

    Bis 09/2026 verabredete jedes Backend-Testmodul seine eigene::

        _TMP = tempfile.mkdtemp()
        os.environ.setdefault("COUNCIL_DB", str(Path(_TMP) / "council.sqlite"))

    ``setdefault`` heißt „nimm, was schon da ist" — welche Datei galt, hing
    also an der Import-Reihenfolge. Seriell trug das; unter ``pytest -n auto``
    importiert jeder Worker eine andere Teilmenge, und ein Modul schrieb seine
    Zeilen in eine andere Datei, als die App las
    (``test_stadtquellen.py::test_tafel_traegt_sperrungen_und_presse``,
    reproduzierbar am 07.09.2026). Der Lauf in der CI fährt seitdem ``-n auto``
    — eine neue Zuweisung hier macht ihn sporadisch rot, in einem PR, der
    nichts damit zu tun hat.
    """
    zeilen = [
        f"{pfad.name}:{nr}: {z.strip()[:90]}"
        for nr, z in enumerate(pfad.read_text(encoding="utf-8").splitlines(), 1)
        if GESETZT.search(z)
    ]
    assert not zeilen, (
        "Diese Zeilen setzen eine Variable, die der ganze Prozess teilt:\n"
        + "\n".join(zeilen)
        + "\n\nGesetzt werden sie EINMAL je Prozess in tests/conftest.py.\n"
        "Braucht der Test einen anderen Wert, gehört er per\n"
        "`monkeypatch.setenv(...)` gesetzt (wird nach dem Test zurückgenommen);\n"
        "braucht er eine eigene Datenbank, legt er sie unter `tmp_path` an und\n"
        "hängt sie über `app.dependency_overrides` ein."
    )
