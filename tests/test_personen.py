"""Personen-Paket (10.08.26): FDP/Volt-Auflösung über die Stammdaten und der
Personen-Fragetyp („Was sagt Ratsfrau X dazu?")."""
from __future__ import annotations

from council import embeddings as emb
from council import qa
from council.store import CouncilStore


class _PersonenStore:
    def personen_suchindex(self):
        return [
            ("Jens Lükermann", "Volt"),
            ("Daniela Pfeiffer", "FDP"),
            ("Jonas Christopher Höpken", "BSW"),
            ("Vally Finke", "Für Oldenburg"),
            ("Dr. Christiane Niewerth-Baumann", "CDU"),
        ]


def test_parteien_aufloesen_trennt_fdp_volt():
    rows = [
        {"sprecher": "Jens Lükermann", "partei": "FDP/Volt", "text": "…"},
        {"sprecher": "Pfeiffer", "partei": "Fraktion FDP/Volt", "text": "…"},
        {"sprecher": "Ratsherr Unbekannt", "partei": "FDP/Volt", "text": "…"},
        {"sprecher": "Finke", "partei": "Für Oldenburg", "text": "…"},
        {"sprecher": "Oeljeschläger", "partei": "SPD", "text": "…"},
    ]
    qa.parteien_aufloesen(_PersonenStore(), rows)
    assert rows[0]["partei"] == "Volt"
    assert rows[1]["partei"] == "FDP"
    # Ohne Stammdaten-Treffer bleibt das quellentreue Gruppen-Label stehen.
    assert rows[2]["partei"] == "FDP/Volt"
    # „Für Oldenburg" ist NICHT auflösbar (das RIS führt selbst nur die Gruppe).
    assert rows[3]["partei"] == "Für Oldenburg"
    assert rows[4]["partei"] == "SPD"


def test_finde_person_namen_titel_und_faltung():
    store = _PersonenStore()
    assert qa.finde_person(store, "Was sagt Lükermann zum Stadion?")["partei"] == "Volt"
    assert qa.finde_person(store, "Wie steht Jens Lükermann zur Brücke?")["name"] == "Jens Lükermann"
    # ASCII-Schreibweise trifft den Umlaut-Namen; Doppelname als Ganzes.
    assert qa.finde_person(store, "Was meint Luekermann dazu?")["partei"] == "Volt"
    assert qa.finde_person(store, "Position von Niewerth-Baumann zum Haushalt?")["partei"] == "CDU"
    # Keine Person genannt → None (kein Fehlmatch über kurze Wortteile).
    assert qa.finde_person(store, "Was kostet das neue Stadion?") is None


def test_wortbeitraege_von_sprecher_umlaut_varianten(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
                "location, fetched_at) VALUES (1, 'Rat', '2026-06-01', '', '', datetime('now'))")
            store._conn.executemany(
                "INSERT INTO council_wortbeitraege (ksinr, position, sprecher, partei, art, "
                "top, text, extracted_at) VALUES (1, ?, ?, 'FDP/Volt', 'rede', 'Ö 1', ?, "
                "datetime('now'))",
                [(1, "Jens Lükermann", "Beitrag mit Umlaut"),
                 (2, "Luekermann", "Beitrag in ASCII-Schreibweise"),
                 (3, "Pfeiffer", "Anderer Sprecher")])
        rows = store.wortbeitraege_von_sprecher("Lükermann")
        assert {r["text"] for r in rows} == {"Beitrag mit Umlaut", "Beitrag in ASCII-Schreibweise"}
    finally:
        store.close()


def test_search_wortbeitraege_von_person_fallback(monkeypatch):
    """Schafft bei einer ganz allgemeinen Frage nichts den Rerank-Cutoff,
    kommen die neuesten Beiträge — die Person wurde ausdrücklich gefragt."""
    class _S:
        def wortbeitraege_von_sprecher(self, nachname, limit=120):
            return [{"id": i, "sprecher": "Lükermann", "partei": "FDP/Volt",
                     "art": "rede", "top": None, "text": f"Beitrag {i}",
                     "committee": "Rat", "session_date": f"2026-0{7 - i}-01"}
                    for i in (1, 2, 3)]

    monkeypatch.setattr(emb, "_rerank_kontext", lambda q, k, top_k: [])
    rows = emb.search_wortbeitraege_von_person(_S(), "Was sagt Lükermann?", "luekermann")
    assert [r["id"] for r in rows] == [1, 2, 3]  # Store-Reihenfolge (neueste zuerst)

    monkeypatch.setattr(emb, "_rerank_kontext",
                        lambda q, k, top_k: [(2, 0.5)])
    rows = emb.search_wortbeitraege_von_person(_S(), "Was sagt Lükermann zum Stadion?", "luekermann")
    assert [r["id"] for r in rows] == [2]
