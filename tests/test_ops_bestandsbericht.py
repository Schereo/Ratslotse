"""Der Bestandsbericht des Ops-Laufs muss Tabellen zählen, die es gibt.

``.github/workflows/ops-finanzdaten-ingest.yml`` endet mit einem Python-
Block, der für jede Finanztabelle Zeilenzahl und Jahresspanne meldet. Die
Tabellennamen stehen dort als Literal — und Literale wandern bei einer
Umbenennung nicht mit: Nach dem Umzug der 66 deutschen Tabellennamen (#918)
zählte der Bericht wochenlang Tabellen, die nicht mehr existierten, und
meldete für jede Zeile nur noch „no such table". Genau den stillen Ausfall,
vor dem der Bericht schützen soll, hatte er damit selbst.

Gelesen wird deshalb der Workflow-Quelltext, nicht eine Kopie der Liste:
Wer dort einen Namen einträgt, den das Schema nicht kennt, sieht es hier.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from council.store import CouncilStore

WORKFLOW = (Path(__file__).resolve().parents[1]
            / ".github" / "workflows" / "ops-finanzdaten-ingest.yml")


def _block() -> str:
    """Der Heredoc-Block des Bestandsberichts, ohne den YAML-Einzug."""
    text = WORKFLOW.read_text(encoding="utf-8")
    anfang = text.index(".venv/bin/python - <<'PY'\n") + len(".venv/bin/python - <<'PY'\n")
    ende = text.index("\n            PY\n", anfang)
    return "\n".join(zeile[12:] for zeile in text[anfang:ende].splitlines())


def _tabellen() -> list[str]:
    treffer = re.search(r"^tabellen = (\[.*?^\])", _block(), re.S | re.M)
    assert treffer, "Liste `tabellen = [...]` nicht im Workflow gefunden"
    return ast.literal_eval(treffer.group(1))


def _jahreskandidaten() -> tuple[str, ...]:
    treffer = re.search(r"for kandidat in (\(.*?\)):", _block())
    assert treffer, "Kandidatenliste der Jahresspalte nicht gefunden"
    return ast.literal_eval(treffer.group(1))


@pytest.fixture(scope="module")
def schema() -> dict[str, list[str]]:
    """Tabelle → Spalten einer frisch angelegten DB — der Stand nach Migration."""
    store = CouncilStore(":memory:")
    namen = [r[0] for r in store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")]
    return {n: [r[1] for r in store._conn.execute(f"PRAGMA table_info({n})")]
            for n in namen}


def test_jede_gezaehlte_tabelle_existiert(schema):
    tabellen = _tabellen()
    assert len(tabellen) > 30, "die Liste ist verdächtig kurz — falsch gelesen?"
    fehlend = [t for t in tabellen if t not in schema]
    assert not fehlend, (
        "Der Bestandsbericht zählt Tabellen, die das Schema nicht kennt — "
        "nach einer Umbenennung die Namen in council/store.py "
        f"(TABELLEN_UMBENANNT) nachziehen: {fehlend}")


def test_keine_tabelle_doppelt():
    tabellen = _tabellen()
    doppelt = sorted({t for t in tabellen if tabellen.count(t) > 1})
    assert not doppelt, doppelt


def test_jahresspalte_wird_fuer_jede_tabelle_gefunden(schema):
    """Eine Tabelle mit Jahresspalte, die der Bericht nicht erkennt, zeigt
    „—" statt einer Spanne — und damit genau die Lücke, die der Stellenplan
    nach dem Umzug von `jahrgang` auf `budget_year` hatte."""
    kandidaten = _jahreskandidaten()
    for kandidat in kandidaten:
        assert any(kandidat in spalten for spalten in schema.values()), (
            f"Kandidat {kandidat!r} kommt in keiner Tabelle mehr vor — "
            "Rest einer Umbenennung, bitte entfernen")
    ohne_spanne = []
    for t in _tabellen():
        spalten = schema.get(t, [])
        jahresartig = [s for s in spalten if s.endswith("year")]
        if jahresartig and not any(k in spalten for k in kandidaten):
            ohne_spanne.append((t, jahresartig))
    assert not ohne_spanne, (
        "Tabellen mit Jahresspalte, die `jahresspalte()` nicht erkennt: "
        f"{ohne_spanne}")


def test_der_ganze_bericht_laeuft_gegen_ein_frisches_schema(capsys):
    """Der Block hat mehr Literale als die Liste: die OCR-Zählung, die
    Urheber-Abfrage, die Schlüssel der Rücklagen-Reihe. Jede steht in einem
    ``try/except`` und würde bei einem falschen Namen nur eine Zeile
    „nicht lesbar" drucken — der Lauf bliebe grün. Deshalb läuft hier der
    ganze Block gegen eine leere DB, und keine Zeile darf einen Fehler
    tragen."""
    quelle = _block().replace(
        'CouncilStore("data/council.sqlite")', 'CouncilStore(":memory:")')
    assert 'CouncilStore(":memory:")' in quelle
    exec(compile(quelle, str(WORKFLOW), "exec"), {})  # noqa: S102
    ausgabe = capsys.readouterr().out
    assert "Bestand nach dem Lauf:" in ausgabe
    fehler = [z for z in ausgabe.splitlines()
              if "no such" in z or "nicht lesbar" in z or "Error" in z]
    assert not fehler, "\n".join(fehler)
