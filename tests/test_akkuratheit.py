"""Akkuratheits-Paket (10.08.26): Entitäts-Anker, „ältere Station"-Marker,
Recency-Bonus — drei deterministische Signale neben der Semantik."""
from __future__ import annotations

from datetime import date

from council import embeddings as emb
from council import qa
from council.store import CouncilStore


# ---- Entitäts-Anker ---------------------------------------------------------

class _AnkerStore:
    """Nur entity_suchindex/decision_ids_for_entities — mehr braucht der Anker nicht."""

    def __init__(self):
        self.index = [
            (1, "Cäcilienbrücke", 6),
            (1, "caeci", 6),                # Glossar-Alias (source='glossar')
            (2, "Fliegerhorst", 158),
            (3, "IGS Flötenteich", 12),
            (4, "Flötenteich", 18),
            (5, "Rat", 999),                # kurz — darf NIE matchen (Mindestlänge)
        ]
        self.links = {1: [101, 102], 2: [201], 3: [301], 4: [401, 402]}

    def entity_suchindex(self):
        return self.index

    def decision_ids_for_entities(self, entity_ids, je=12):
        out = []
        for e in entity_ids:
            out += [d for d in self.links.get(e, []) if d not in out]
        return out


def test_finde_entitaeten_matcht_namen_umlaute_und_glossar():
    store = _AnkerStore()
    # Offizieller Name, mit Umlaut und Beugung drumherum.
    assert [e["id"] for e in qa.finde_entitaeten(store, "Was passiert mit der Cäcilienbrücke?")] == [1]
    # Glossar-Alias aus council_entity_aliases („Cäci" → caecilienbruecke).
    assert [e["id"] for e in qa.finde_entitaeten(store, "Was ist eigentlich mit der Cäci los?")] == [1]
    # ASCII-Schreibweise der Frage trifft den Umlaut-Namen.
    assert [e["id"] for e in qa.finde_entitaeten(store, "Neues zur Caecilienbruecke bitte")] == [1]


def test_finde_entitaeten_laengster_match_und_deckel():
    store = _AnkerStore()
    # „IGS Flötenteich" enthält „Flötenteich" — der längere, spezifischere
    # Match steht vorn; beide zusammen bleiben unter dem Deckel (max 2).
    ids = [e["id"] for e in qa.finde_entitaeten(store, "Was wurde zur IGS Flötenteich beschlossen?")]
    assert ids[0] == 3 and set(ids) <= {3, 4} and len(ids) <= 2


def test_finde_entitaeten_keine_kurz_und_fehlmatches():
    store = _AnkerStore()
    # „Rat" (3 Zeichen) steckt in „Ratsherren", „beraten" … — Mindestlänge
    # und Wortgrenzen verhindern den Anker-Beifang.
    assert qa.finde_entitaeten(store, "Was hat der Rat zuletzt beraten?") == []
    assert qa.finde_entitaeten(store, "Wie hoch ist der Haushalt 2026?") == []


# ---- Recency-Bonus ----------------------------------------------------------

def test_recency_intent_wortliste():
    assert qa.recency_intent("Wie ist der Stand beim Stadionneubau?")
    assert qa.recency_intent("Was wurde zuletzt zum Radverkehr beschlossen?")
    assert qa.recency_intent("Was gilt aktuell beim Bebauungsplan 831?")
    assert not qa.recency_intent("Was wurde 2019 zum Stadion beschlossen?")
    assert not qa.recency_intent("Warum wurde die Brücke gesperrt?")


def test_recency_boost_kippt_nur_nahe_scores():
    heute = date(2026, 8, 10)
    hits = [(1, 0.20), (2, 0.10), (3, -2.5)]
    dates = {1: "2019-05-01", 2: "2026-06-01", 3: "2026-07-01"}
    geboostet = emb.recency_boost(hits, dates, heute=heute)
    # Der frische, fast gleich gute Treffer 2 überholt den alten Spitzenreiter …
    assert [i for i, _ in geboostet][:2] == [2, 1]
    # … aber ein klar schlechterer (−2.5) klettert NICHT nach oben.
    assert geboostet[-1][0] == 3
    # Ohne Datum: kein Bonus, Reihenfolge stabil.
    assert [i for i, _ in emb.recency_boost(hits, {}, heute=heute)] == [1, 2, 3]


# ---- „Ältere Station"-Marker ------------------------------------------------

def _decision(id_, kvonr, vorlage_nr, datum, committee="Rat", titel="Stadionneubau"):
    return {"id": id_, "kvonr": kvonr, "vorlage_nr": vorlage_nr,
            "session_date": datum, "committee": committee, "title": titel,
            "summary": "", "outcome": "angenommen"}


def test_markiere_veraltete_ueber_kvonr_und_revisionen(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        with store._conn:
            store._conn.executemany(
                "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
                "location, fetched_at) VALUES (?, ?, ?, '', '', datetime('now'))",
                [(10, "Bauausschuss", "2024-03-01"), (11, "Rat", "2026-06-01"),
                 (12, "Finanzausschuss", "2025-01-15")])
            store._conn.executemany(
                "INSERT INTO council_decisions (id, ksinr, position, kind, title, kvonr, vorlage_nr) "
                "VALUES (?, ?, 1, 'beschluss', ?, ?, ?)",
                [(101, 10, "Stadion (Ausschuss)", 500, "24/0100"),
                 (102, 11, "Stadion (Rat)", 500, "24/0100"),      # gleiche Vorlage, jünger
                 (103, 12, "Stadion Revision", 501, "24/0100-1"),  # Revisions-Familie
                 (104, 10, "Radweg", 600, "24/0200")])             # unbeteiligt
        kandidaten = [
            _decision(101, 500, "24/0100", "2024-03-01", "Bauausschuss"),
            _decision(104, 600, "24/0200", "2024-03-01"),
        ]
        qa.markiere_veraltete(store, kandidaten, kandidaten_ids={101, 104})
        # 101 hat zwei jüngere Stationen (102 via kvonr, 103 via Revisions-Nr.) —
        # markiert wird die JÜNGSTE (102, Rat, 01.06.2026), ohne [id]-Verweis,
        # weil 102 nicht im Kandidatenset liegt.
        marker = kandidaten[0].get("neuere_station")
        assert marker and marker["datum"] == "2026-06-01" and marker["committee"] == "Rat"
        assert marker.get("id") is None
        # Der unbeteiligte Kandidat bleibt sauber.
        assert "neuere_station" not in kandidaten[1]

        # Liegt die jüngste Station SELBST im Kandidatenset, trägt der Marker
        # ihre id — die Antwort darf dann direkt auf [id] verweisen.
        kandidaten2 = [
            _decision(101, 500, "24/0100", "2024-03-01", "Bauausschuss"),
            _decision(102, 500, "24/0100", "2026-06-01"),
        ]
        qa.markiere_veraltete(store, kandidaten2, kandidaten_ids={101, 102})
        assert kandidaten2[0]["neuere_station"]["id"] == 102
        assert "neuere_station" not in kandidaten2[1]  # die jüngste selbst nie markieren
    finally:
        store.close()


def test_build_context_rendert_stations_hinweis():
    c = _decision(101, 500, "24/0100", "2024-03-01", "Bauausschuss")
    c["neuere_station"] = {"id": 102, "datum": "2026-06-01", "committee": "Rat"}
    ctx = qa._build_context([c])
    assert "NEUERE Station" in ctx or "neuere Station" in ctx.lower()
    assert "01.06.2026" in ctx and "[102]" in ctx
