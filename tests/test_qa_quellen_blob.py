"""Die Blocknamen der KI-Antwort ziehen auch IM gespeicherten Blob um.

Die Quellen einer Antwort stehen nicht nur auf der Leitung, sondern als JSON
in `qa_gespraech_turns.sources`, `qa_shares.extras` und
`deep_research_jobs.sources`. Wer nur die Leitung umbenennt, lässt jedes
gespeicherte Gespräch mit leeren Presse-, Debatten- und Anlagen-Blöcken
zurück — sichtbar erst, wenn jemand ein altes Gespräch öffnet, und von keinem
Test zu sehen, weil Tests frische Datenbanken bauen.

Der erste Blob-Umzug (Feld-Namen wie `sprecher`/`partei`) ließ die
Blocknamen bewusst stehen. Dieser Schnitt holt sie nach — unter EIGENER
Marke, denn die Marke des ersten Laufs hätte den zweiten verschluckt.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kern.store import Store  # noqa: E402

#: Nachgebaut aus den 113 echten Blobs auf Prod (01.09.2026) — dieselben
#: Pfade, erfundene Inhalte.
#: ACHTUNG: Diese Schlüssel sind der ALTE Stand. Ein Suchen-und-Ersetzen darf
#: sie NIE mitübersetzen — sonst prüft der Test einen Umzug, den es im Fixture
#: schon gar nicht mehr zu machen gibt, und bleibt grün, ohne etwas zu zeigen.
BLOB = {
    "sources": [{"id": 1, "title": "Stadionneubau", "ort_name": "Marschweg",
                 "location_matches": [{"name": "Marschwegstadion", "stadtteil": "Innenstadt"}]}],
    "cited": [1],
    "presse": [{"titel": "Rat beschließt", "datum": "2026-08-01", "url": "https://example.org/a"}],
    "debatten": [{"sprecher": "A. Beispiel", "partei": "SPD", "top": "Ö 5",
                  "auszug": "…", "art": "wortbeitrag",
                  "protokoll_url": "https://example.org/p.pdf", "protokoll_seite": 7}],
    "anlagen": [{"nr": 1, "label": "Anlage 1", "vorlage_nr": "25/0001", "auszug": "…"}],
    "planungen": [{"vorlage_titel": "B-Plan 851", "gremium": "Rat"}],
    "sitzungen": [{"committee": "Rat", "n_beschluesse": 3}],
    "parteien": [{"partei": "SPD", "haltung": "dafuer", "einig": True}],
    "grafik": {"art": "schulden", "series": []},
    "geld": {"facetten": ["plan"]},
    "gelesen": 14, "zeitraum": "2024–2026", "kontext": "Wie teuer ist das Stadion?",
    "recherche": True, "beleglage": "solide",
}


def _mit_blob(pfad: Path) -> None:
    """Eine GEWACHSENE Konten-Datenbank im Stand vor beiden Blob-Umzügen.

    Nicht von Hand gebaut: Erst das echte Schema anlegen lassen, dann die
    alte Zeile hineinschreiben und beide Marken löschen. Eine handgebaute
    Tabelle hätte ein anderes Schema als das echte — und der Test hätte
    dann etwas anderes geprüft als das, was auf dem Server passiert.
    """
    Store(str(pfad))._conn.close()
    conn = sqlite3.connect(pfad)
    conn.execute(
        "INSERT INTO qa_gespraech_turns (conversation_id, user_id, question, answer, "
        "sources, created) VALUES (1, 1, 'Frage', 'Antwort', ?, datetime('now'))",
        (json.dumps(BLOB, ensure_ascii=False),))
    conn.execute("DELETE FROM migrationsmarken WHERE marke LIKE 'json_%qa_gespraech_turns%'")
    conn.commit()
    conn.close()


def _gelesen(pfad: Path) -> dict:
    with sqlite3.connect(pfad) as c:
        return json.loads(c.execute("SELECT sources FROM qa_gespraech_turns").fetchone()[0])


def test_die_blocknamen_ziehen_um(tmp_path):
    pfad = tmp_path / "ratslotse.sqlite"
    _mit_blob(pfad)
    Store(str(pfad))._conn.close()
    d = _gelesen(pfad)
    for alt, neu in (("presse", "press_releases"), ("debatten", "debates"),
                     ("anlagen", "attachments"), ("planungen", "planning_procedures"),
                     ("sitzungen", "sessions"), ("parteien", "parties"),
                     ("grafik", "chart"), ("gelesen", "documents_read"),
                     ("zeitraum", "period"), ("kontext", "context"),
                     ("recherche", "research"), ("beleglage", "evidence_level"),
                     ("geld", "money")):
        assert alt not in d, f"{alt} steht noch da"
        assert neu in d, f"{neu} fehlt"


def test_der_inhalt_bleibt_unangetastet(tmp_path):
    """Umbenannt werden SCHLÜSSEL, nicht Werte. Ein verlorener Beschluss wäre
    schlimmer als ein deutscher Schlüssel."""
    pfad = tmp_path / "ratslotse.sqlite"
    _mit_blob(pfad)
    Store(str(pfad))._conn.close()
    d = _gelesen(pfad)
    assert d["sources"][0]["title"] == "Stadionneubau"
    assert d["press_releases"][0]["url"] == "https://example.org/a"
    assert d["documents_read"] == 14
    assert d["context"] == "Wie teuer ist das Stadion?"
    assert d["cited"] == [1]


def test_der_erste_umzug_laeuft_weiter_mit(tmp_path):
    """Beide Läufe müssen greifen — der zweite darf den ersten nicht ersetzen."""
    pfad = tmp_path / "ratslotse.sqlite"
    _mit_blob(pfad)
    Store(str(pfad))._conn.close()
    d = _gelesen(pfad)
    assert d["debates"][0]["speaker"] == "A. Beispiel", "Feld-Umzug (erster Lauf)"
    assert d["debates"][0]["party"] == "SPD"
    assert d["press_releases"][0]["title"] == "Rat beschließt"


def test_zweimal_oeffnen_aendert_nichts(tmp_path):
    """Die Marke muss den zweiten Start abfangen — sonst liefe der Umzug über
    frisch geschriebene Zeilen und benannte deren neue Schlüssel wieder um."""
    pfad = tmp_path / "ratslotse.sqlite"
    _mit_blob(pfad)
    Store(str(pfad))._conn.close()
    erst = _gelesen(pfad)
    Store(str(pfad))._conn.close()
    assert _gelesen(pfad) == erst


def test_auch_die_felder_der_zeilen_ziehen_um(tmp_path):
    """Zweiter Lauf, eine Ebene tiefer.

    In #913 blieben `art`, `top` und `auszug` stehen — zu allgemein, hieß es,
    für einen Lauf über den ganzen Baum. Sie standen damit aber als letzte
    deutsche FELDER in der OpenAPI-Doku. Die Auszählung aller Schlüsselpfade
    der 113 echten Prod-Blöcke zeigt, dass jeder dieser Namen dort genau eine
    Bedeutung hat; deshalb zieht jetzt auch diese Ebene um — unter EIGENER
    Marke, denn die des Block-Laufs ist auf dev längst gesetzt und hätte
    diesen Lauf verschluckt."""
    pfad = tmp_path / "ratslotse.sqlite"
    _mit_blob(pfad)
    Store(str(pfad))._conn.close()
    d = _gelesen(pfad)
    z = d["debates"][0]
    assert z["agenda_item"] == "Ö 5" and "top" not in z
    assert z["excerpt"] == "…" and "auszug" not in z
    assert z["kind"] == "wortbeitrag" and "art" not in z
    assert d["attachments"][0]["excerpt"] == "…"
    assert d["parties"][0]["stance"] == "dafuer"
    assert d["parties"][0]["unanimous"] is True
    assert z["minutes_page"] == 7 and z["minutes_url"].endswith("p.pdf")
    assert d["attachments"][0]["number"] == 1
