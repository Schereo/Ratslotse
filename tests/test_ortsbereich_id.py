"""`ortsbereich_id` → `local_area_id`: die letzte deutsche Spalte, ein Blob-Schlüssel, ein Feld.

Drei Orte, die zusammen umziehen müssen — und die drei Fallen, die heute je
einmal zugeschnappt sind: eine Spalte nur im Code umbenannt (#917), ein
Blob-Lauf unter einer schon gesetzten Marke (#915), ein ADD-COLUMN-Guard, der
den falschen Namen prüft (#917).
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council.store import CouncilStore  # noqa: E402
from kern.store import Store  # noqa: E402


def test_die_spalte_zieht_um_und_behaelt_ihre_werte(tmp_path):
    pfad = tmp_path / "council.sqlite"
    CouncilStore(str(pfad))._conn.close()
    conn = sqlite3.connect(pfad)
    conn.execute("ALTER TABLE council_locations RENAME COLUMN local_area_id TO ortsbereich_id")
    conn.execute("INSERT INTO council_locations (slug, name, kind, ortsbereich_id, updated_at) "
                 "VALUES ('marschweg', 'Marschweg', 'street', '07', datetime('now'))")
    conn.commit(); conn.close()
    CouncilStore(str(pfad))._conn.close()
    with sqlite3.connect(pfad) as c:
        sp = {r[1] for r in c.execute("PRAGMA table_info(council_locations)")}
        assert "ortsbereich_id" not in sp and "local_area_id" in sp
        assert c.execute("SELECT local_area_id FROM council_locations WHERE slug = 'marschweg'").fetchone()[0] == "07"


def test_der_add_column_guard_prueft_den_neuen_namen():
    """Sonst legte der Start die alte Spalte leer daneben — genau #917."""
    q = (WURZEL / "council" / "store.py").read_text()
    m = re.search(r'if "(\w+)" not in \w+:\s*\n\s*self\._conn\.execute\("ALTER TABLE council_locations ADD COLUMN local_area_id TEXT"\)', q)
    assert m, "ADD COLUMN local_area_id nicht gefunden"
    assert m.group(1) == "local_area_id", f"der Guard prüft {m.group(1)!r}, nicht die Spalte selbst"


def test_der_blob_schluessel_zieht_unter_eigener_marke_um(tmp_path):
    pfad = tmp_path / "ratslotse.sqlite"
    Store(str(pfad))._conn.close()
    blob = {"sources": [{"id": 1, "title": "x", "location_matches": [{"name": "Marschwegstadion", "ortsbereich_id": "07"}]}], "cited": [1]}
    conn = sqlite3.connect(pfad)
    conn.execute("INSERT INTO qa_conversation_turns (conversation_id, user_id, question, answer, sources, created) "
                 "VALUES (1, 1, 'F', 'A', ?, datetime('now'))", (json.dumps(blob),))
    # Nur die NEUE Marke löschen — die drei älteren Läufe sind auf dev längst durch.
    conn.execute("DELETE FROM migration_marks WHERE marke LIKE 'json_ortsbereich_%'")
    conn.commit(); conn.close()
    Store(str(pfad))._conn.close()
    with sqlite3.connect(pfad) as c:
        d = json.loads(c.execute("SELECT sources FROM qa_conversation_turns").fetchone()[0])
        lm = d["sources"][0]["location_matches"][0]
        assert "ortsbereich_id" not in lm and lm["local_area_id"] == "07"
        assert c.execute("SELECT COUNT(*) FROM migration_marks WHERE marke LIKE 'json_ortsbereich_%'").fetchone()[0] == 3
