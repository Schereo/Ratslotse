"""Die Hebesatz-Probe der Haushaltssatzung prüft wirklich.

**Warum es diesen Test gibt.** ``hebesatz_probe`` hält den Hebesatz einer
Haushaltssatzung gegen Tabelle 1105 des Statistischen Jahrbuchs — zwei
unabhängige Häuser, die dieselbe Zahl nennen müssen. Sie tat das seit ihrer
Einführung (#674) **nie**: Die Schlüssel hießen ``grundsteuer_a``, in der
Spalte steht ``Grundsteuer A``. ``felder.get()`` traf also nie, die Schleife
sammelte nichts, und der Rückgabewert war jedes Mal ``None`` — von außen
nicht von „für diesen Jahrgang gibt es noch keine Jahrbuchzahl" zu
unterscheiden, dem echten Normalfall.

Der Umbau auf englische Spaltennamen legte später einen zweiten Bruch
darauf (``art`` heißt ``kind``), den das umschließende ``except`` verschluckte.

Zwei Fehler, die sich gegenseitig verdeckten, und beide unsichtbar, weil das
Ergebnis in beiden Fällen gleich aussah wie der Normalfall. Deshalb prüft
dieser Test jetzt beide Richtungen: Sie muss anschlagen, wenn die Zahlen
auseinandergehen, **und** bestätigen, wenn sie zusammenpassen.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council.budget_bylaw import SatzungFehler  # noqa: E402
from council.steuertabellen import HEBESATZ_ARTEN  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from scripts.ingest_haushaltssatzung import hebesatz_probe  # noqa: E402


@dataclass
class Satzung:
    year: int
    property_tax_a_rate: int
    property_tax_b_rate: int
    trade_tax_rate: int


def _store(tmp_path, jahr: int, saetze: tuple[int, int, int] | None):
    store = CouncilStore(tmp_path / "council.sqlite")
    if saetze is not None:
        with store._conn:                                    # noqa: SLF001
            for art, wert in zip(HEBESATZ_ARTEN, saetze):
                store._conn.execute(                         # noqa: SLF001
                    "INSERT INTO council_tax_rates "
                    "(year, kind, rate, fetched_at) VALUES (?, ?, ?, ?)",
                    (jahr, art, wert, "2026-09-02T00:00:00"))
    return store


def test_gleiche_zahlen_werden_bestaetigt(tmp_path):
    store = _store(tmp_path, 2025, (500, 539, 439))
    text = hebesatz_probe(store, Satzung(2025, 500, 539, 439))
    assert text is not None, (
        "Die Probe meldet nichts, obwohl beide Quellen dieselben Zahlen "
        "nennen — genau so sah der Ausfall aus."
    )
    for art in HEBESATZ_ARTEN:
        assert art in text
    assert "1105" in text


def test_widersprechende_zahlen_lassen_den_jahrgang_durchfallen(tmp_path):
    store = _store(tmp_path, 2025, (500, 539, 439))
    with pytest.raises(SatzungFehler, match="Grundsteuer B"):
        hebesatz_probe(store, Satzung(2025, 500, 500, 439))


def test_ohne_jahrbuchzahl_ist_das_kein_fehler(tmp_path):
    """Der Normalfall für den kommenden Haushalt: Das Jahrbuch kommt später."""
    store = _store(tmp_path, 2025, None)
    assert hebesatz_probe(store, Satzung(2026, 500, 539, 439)) is None
