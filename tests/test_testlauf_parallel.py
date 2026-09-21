"""Jeder Ort, der die ganze Suite fährt, fährt sie parallel.

Der Fehler, gegen den das hier steht, kostet nichts außer Zeit — und meldet
sich deshalb nie. PR #1162 (07.09.2026) hat die Suite auf ``pytest -n auto``
umgestellt und dabei ``.github/workflows/test.yml`` und ``scripts/pruefe.py``
angefasst, aber nicht ``deploy.yml``. Zwei Wochen lang lief die Suite vor
**jedem** Prod-Deploy seriell weiter: gemessen am Release 2.7.0 (21.09.2026)
7 min 25 s, während derselbe Lauf auf dem Pull Request gut zwei Minuten
brauchte. Nichts wurde rot, niemand bekam eine Mail, im Changelog stand nichts
— der Deploy war einfach fünf Minuten länger unterwegs, und das sah nach
„der Deploy dauert halt" aus.

Der Test hält die Aufrufe deshalb **beieinander** statt sie einzeln zu prüfen:
Wer einen vierten Ort baut, der die ganze Suite fährt, wird hier genannt.
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]

#: Ein Lauf über das ganze Verzeichnis ``tests/`` — genau die sind gemeint.
#: Ein gezielter Aufruf einer einzelnen Datei (der Vertrags-Wächter etwa)
#: braucht keine vier Prozesse und taucht hier nicht auf.
GANZE_SUITE = re.compile(r"pytest[\"',\s].{0,40}?tests/[\"',\s]")


def _zeilen_mit_ganzer_suite() -> list[tuple[str, str]]:
    """(Datei, Zeile) für jeden Aufruf, der die ganze Suite fährt."""
    orte = [WURZEL / "scripts" / "pruefe.py"]
    orte += sorted((WURZEL / ".github" / "workflows").glob("*.yml"))
    gefunden = []
    for pfad in orte:
        for zeile in pfad.read_text().splitlines():
            nackt = zeile.strip()
            # Kommentare zählen nicht: In `pruefe.py` und `test.yml` steht die
            # Begründung für `-n auto` als Fließtext daneben, samt der Wörter,
            # die das Muster sonst greifen ließe.
            if nackt.startswith(("#", "//")):
                continue
            if GANZE_SUITE.search(nackt):
                gefunden.append((pfad.relative_to(WURZEL).as_posix(), nackt))
    return gefunden


def _parallel(zeile: str) -> bool:
    """Steht in dieser Zeile ``-n auto``?

    Die drei Orte schreiben denselben Aufruf verschieden: In den Workflows
    steht er als Kommandozeile (``pytest tests/ -q -n auto``), in
    ``pruefe.py`` als Python-Liste (``[PY, "-m", "pytest", …, "-n", "auto"]``).
    Ein Vergleich auf den nackten Text hätte den zweiten Fall für seriell
    gehalten — und damit ausgerechnet die Stelle rot gemeldet, die von Anfang
    an in Ordnung war.
    """
    flach = zeile.replace('"', " ").replace("'", " ").replace(",", " ")
    return "-n auto" in " ".join(flach.split())


def test_wer_die_ganze_suite_faehrt_faehrt_sie_parallel():
    orte = _zeilen_mit_ganzer_suite()
    assert orte, (
        "Kein einziger Aufruf der ganzen Suite gefunden — das Muster oben "
        "passt nicht mehr. Ein Wächter, der nichts sieht, ist schlimmer als "
        "keiner: Bitte das Muster nachziehen, nicht den Test löschen.")
    seriell = [f"{datei}: {zeile}" for datei, zeile in orte if not _parallel(zeile)]
    assert not seriell, (
        "Diese Stelle(n) fahren die Testsuite seriell:\n  "
        + "\n  ".join(seriell)
        + "\n\nMit `-n auto` (pytest-xdist, steht in requirements-dev.txt) "
          "dauert der Lauf auf dem Vierkern-Runner der CI gut zwei statt "
          "siebeneinhalb Minuten. Das fällt sonst nirgends auf — es wird "
          "einfach alles langsamer.")


def test_die_drei_bekannten_orte_sind_noch_da():
    """Gegen den stillen Gegenfall: Der Test oben wäre auch dann grün, wenn
    ein Aufruf schlicht verschwindet (etwa weil jemand das Test-Gate vor dem
    Deploy herausnimmt). Das mag eine bewusste Entscheidung sein — aber eine
    bewusste, und dann gehört diese Liste angefasst."""
    dateien = {datei for datei, _ in _zeilen_mit_ganzer_suite()}
    assert dateien == {
        "scripts/pruefe.py",
        ".github/workflows/deploy.yml",
        ".github/workflows/test.yml",
    }, (f"Die Orte, die die ganze Suite fahren, haben sich geändert: {sorted(dateien)}. "
        "Wenn das so gewollt ist, diese Liste nachziehen.")
