"""Der Bestandsvergleich dev ↔ Prod (scripts/council_inventory.py).

Er soll eine Lücke beim Namen nennen: Am 23.11.2026 hatte dev im Ausschuss
für Allgemeine Angelegenheiten 2025 null Beschlüsse, Prod 44 — und
vergangene Sitzungen ohne einen einzigen Beschluss.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from council.scraper import CouncilSession
from council.store import CouncilStore

WURZEL = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("council_inventory", WURZEL / "scripts" / "council_inventory.py")
assert _spec and _spec.loader
inventory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(inventory)


def _db(tmp_path, name: str, mit_beschluessen: bool) -> str:
    pfad = str(tmp_path / name)
    cs = CouncilStore(pfad)
    cs.save_session(CouncilSession(1, "Ausschuss für Allgemeine Angelegenheiten", "2025-03-17", "17:00", "Rathaus"))
    if mit_beschluessen:
        with cs._conn:
            for i in range(6):
                cs._conn.execute("INSERT INTO council_decisions (id, ksinr, position, item_number, title, kind)"
                                 " VALUES (?, 1, ?, ?, 'Punkt', 'decision')", (i + 1, i, str(i)))
    cs.close()
    return pfad


def test_kennzahlen_zaehlen_beschluesse_und_leere_sitzungen(tmp_path):
    voll = inventory.collect(_db(tmp_path, "voll.sqlite", True), today="2026-11-23")
    leer = inventory.collect(_db(tmp_path, "leer.sqlite", False), today="2026-11-23")
    assert voll["decisions_by_year"] == {"2025": 6}
    assert leer["decisions_by_year"] == {}
    assert leer["empty_past_sessions_by_year"] == {"2025": 1}
    assert voll["totals"]["decisions"] == 6


def test_bericht_nennt_das_gremium_mit_luecke(tmp_path):
    dev = inventory.collect(_db(tmp_path, "dev.sqlite", False), today="2026-11-23")
    prod = inventory.collect(_db(tmp_path, "prod.sqlite", True), today="2026-11-23")
    bericht = inventory.compare(dev, prod)
    assert "| 2025 | Ausschuss für Allgemeine Angelegenheiten | 0 | 6 | -6 |" in bericht


def test_fehlende_tabelle_ist_kein_absturz(tmp_path):
    """Eine Umgebung ohne Presse-Embeddings (Tabelle fehlt) liefert None."""
    pfad = _db(tmp_path, "c.sqlite", True)
    import sqlite3
    con = sqlite3.connect(pfad)
    con.execute("DROP TABLE IF EXISTS council_press_embeddings")
    con.commit()
    con.close()
    werte = inventory.collect(pfad, today="2026-11-23")
    assert werte["embeddings"]["press"]["covered"] is None
