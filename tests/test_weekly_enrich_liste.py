"""Wächter: Der Schritt-Katalog im Docstring von ``weekly_enrich`` ist echt.

Über ``STEPS`` steht seit jeher „Diese Liste MUSS zu STEPS unten passen." Ein
Satz hält nichts: Die Liste ist dreimal weggelaufen, zuletzt um drei Schritte
(``backfill_anlagen_texte``, ``embed_anlagen``, ``build_district_projects``,
gemessen am 08.09.2026). Das fällt niemandem auf, weil der Lauf davon nicht
kaputtgeht — nur die Kostenschätzung und die Frage „was macht der Sonntagslauf
eigentlich?" werden falsch beantwortet.

Deshalb misst dieser Wächter beide Richtungen und die Zahl dazu.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from scripts import weekly_enrich as we  # noqa: E402

#: Eine Katalogzeile: „   11b. Mein Viertel   build_district_projects.py  — …"
#: Der Abstand vor dem Gedankenstrich schrumpft auf eins, wenn der Skriptname
#: über die Spalte hinausragt (``generate_simple_summaries.py``).
ZEILE = re.compile(r"^\s*(\d+[a-z]?)\.\s+(.+?)\s\s+([a-z_]+\.py)\s+—", re.M)

#: Der Docstring endet mit der Cron-Zeile, und die nennt das Skript selbst.
#: Ein zulässiger Fund, kein Katalogeintrag.
SELBST = "weekly_enrich.py"


def _katalog() -> list[tuple[str, str]]:
    """Die nummerierten Zeilen des Docstrings als (Nummer, Skript)."""
    assert we.__doc__, "weekly_enrich hat seinen Modul-Docstring verloren"
    return [(m.group(1), m.group(3)) for m in ZEILE.finditer(we.__doc__)]


def _steps() -> list[str]:
    """Die Skriptnamen aus STEPS, ohne Argumente („rate_impact.py --limit 500")."""
    return [skript.split()[0] for _, skript in we.STEPS]


def test_jeder_schritt_steht_im_docstring():
    """Die Messung, an der die Drift aufgefallen ist — als Test."""
    gelistet = {skript for _, skript in _katalog()}
    fehlt = [s for s in _steps() if s not in gelistet]
    assert not fehlt, (
        f"{fehlt} laufen in STEPS, stehen aber nicht im Modul-Docstring von "
        f"scripts/weekly_enrich.py. Zeile im Katalog nachtragen — Unternummer "
        f"(2b, 4c) an der passenden Stelle, damit die übrigen Nummern gültig "
        f"bleiben.")


def test_kein_docstring_eintrag_ohne_schritt():
    """Die Gegenrichtung: ein Eintrag, den STEPS gar nicht mehr fährt, ist eine
    Zusage über Arbeit, die niemand tut."""
    schritte = set(_steps())
    tot = [s for _, s in _katalog() if s not in schritte]
    assert not tot, (
        f"{tot} stehen im Docstring-Katalog, aber nicht in STEPS — Zeile "
        f"entfernen oder den Schritt wieder einhängen.")
    # Das Skript nennt sich am Ende selbst (Cron-Zeile); das ist kein Eintrag.
    assert SELBST in (we.__doc__ or ""), "die Cron-Zeile ist verschwunden"
    assert SELBST not in {s for _, s in _katalog()}


def test_katalog_und_steps_stehen_in_derselben_reihenfolge():
    """Gleiche Menge reicht nicht: Die Reihenfolge ist die Aussage des Katalogs
    („Schritt 10 muss vor 11 laufen"), und sie ist die einzige Stelle, an der
    die Abhängigkeiten zwischen den Schritten überhaupt notiert sind."""
    assert [s for _, s in _katalog()] == _steps(), (
        "Katalog und STEPS führen dieselben Skripte in verschiedener "
        "Reihenfolge — der Katalog ist die Doku der Reihenfolge, nicht eine "
        "zweite Liste daneben.")


#: Dateien, die eine abgeleitete Zahl über die Schritte in Prosa behaupten.
#: Solche Sätze veralten still — sie zeigen auf nichts, was der Lauf prüft.
ZAHLENQUELLEN = ("scripts/weekly_enrich.py", "tests/test_jobs.py")

#: „18 der 20 Schritte rufen kein run_guarded"
BEHAUPTUNG = re.compile(r"(\d+) der (\d+)\s*\n?\s*Schritte")


def test_satz_ueber_die_schrittzahl_stimmt_noch():
    """Die Schrittzahl steht auch als Fließtext da — und muss mitwachsen.

    ``main()`` begründet die Schritt-Bilanz mit „18 der 20 Schritte rufen kein
    ``run_guarded``". Beide Zahlen sind aus STEPS und den Skripten ableitbar,
    also darf keine von Hand danebenliegen.
    """
    gesamt = len(we.STEPS)
    ohne_wache = sum(
        1 for skript in _steps()
        if "run_guarded(" not in (WURZEL / "scripts" / skript).read_text(encoding="utf-8"))

    gefunden = 0
    for datei in ZAHLENQUELLEN:
        text = (WURZEL / datei).read_text(encoding="utf-8")
        for treffer in BEHAUPTUNG.finditer(text):
            gefunden += 1
            satz = " ".join(treffer.group(0).split())  # der Satz darf umbrechen
            assert (int(treffer.group(1)), int(treffer.group(2))) == (ohne_wache, gesamt), (
                f"{datei}: ‚{satz} …‘ stimmt nicht mehr — heute rufen "
                f"{ohne_wache} der {gesamt} Schritte kein run_guarded.")
    assert gefunden, (
        "Kein Satz der Form ‚X der Y Schritte‘ mehr in "
        f"{list(ZAHLENQUELLEN)} — entweder ist er weg (dann diesen Test samt "
        "ZAHLENQUELLEN streichen) oder er wurde umformuliert (dann hier "
        "nachziehen, sonst bewacht der Test nichts mehr).")
