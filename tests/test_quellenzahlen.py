"""Woher die Zahlen kommen (council/quellenzahlen.py)."""
import sys
from pathlib import Path

from council import herkunft, quellenzahlen
from council.store import CouncilStore


def _store(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    h = herkunft.Herkunft(kind="ris", probe=["budget_preface_figures"], document_id=4711, label="Vorbericht")
    store.save_vorbericht_zahlen(2026, [
        {"series": "tax_trade", "year": 2026, "variant": "budget", "amount": 218e6, "page": 16},
        {"series": "tax_trade", "year": 2025, "variant": "forecast", "amount": 210e6, "page": 16},
    ], h)
    return store


def test_zaehlt_werte_ohne_schluessel(tmp_path):
    store = _store(tmp_path)
    try:
        d = quellenzahlen.zaehle(store)
    finally:
        store.close()
    # Zwei Zeilen, je EINE Zahl (amount) — Jahr, Seite, Planjahr sind Schlüssel.
    assert d["rows"] == 2 and d["numbers"] == 2
    assert d["documents"] == 1 and d["sources"] == [
        {"kind": "ris", "label": "Ratsinformationssystem", "documents": 1}]
    assert d["probe_kinds"] == 1 and d["probe_runs"] == 1
    vorbericht = next(s for s in d["layers"] if "budget_notes" in s["keys"])
    assert vorbericht["numbers"] == 2 and vorbericht["documents"] == 1


def test_geteilte_tabellen_sind_eine_zeile(tmp_path):
    store = _store(tmp_path)
    try:
        d = quellenzahlen.zaehle(store)
    finally:
        store.close()
    tabellen = [tuple(s["keys"]) for s in d["layers"]]
    assert len(tabellen) == len(set(tabellen))
    vergleich = [s for s in d["layers"] if len(s["keys"]) > 1]
    assert vergleich, "die Vergleiche teilen sich council_city_comparison"


def test_schluesselspalten():
    for c in ("year", "budget_year", "plan_budget_year", "page", "herkunft_id", "seq", "document_id"):
        assert quellenzahlen._SCHLUESSEL.search(c), c
    for c in ("amount", "planned", "forecast", "value", "rate"):
        assert not quellenzahlen._SCHLUESSEL.search(c), c


def test_endpunkt(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))
    from app.routers.council import haushalt_quellenzahlen
    store = _store(tmp_path)
    try:
        a = haushalt_quellenzahlen(_user={}, store=store)
    finally:
        store.close()
    assert a["documents"] == 1 and a["other"]["rows"] == 0
