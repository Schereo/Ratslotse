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
    assert not qa.recency_intent("Warum wurde die Brücke confidential?")


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

def _decision(id_, kvonr, template_number, date, committee="Rat", title="Stadionneubau"):
    return {"id": id_, "kvonr": kvonr, "template_number": template_number,
            "session_date": date, "committee": committee, "title": title,
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
                "INSERT INTO council_decisions (id, ksinr, position, kind, title, kvonr, template_number) "
                "VALUES (?, ?, 1, 'official_text', ?, ?, ?)",
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
        assert marker and marker["date"] == "2026-06-01" and marker["committee"] == "Rat"
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
    c["neuere_station"] = {"id": 102, "date": "2026-06-01", "committee": "Rat"}
    ctx = qa._build_context([c])
    assert "NEUERE Station" in ctx or "neuere Station" in ctx.lower()
    assert "01.06.2026" in ctx and "[102]" in ctx


# ---- Paket 1 (11.08.26): Ausblick, Steckbrief, Beleglage, „Kurz gesagt" ----

def test_beleglage_trennt_duenn_von_solide():
    """Schwellen gemessen am Prod-Bestand (10.08.): tragfähige Themen kommen
    auf mehrere Treffer ≥0,5 und einen Bestwert ≥0,6; die nachweislich dünnen
    (Küstenautobahn A20: 2 Treffer, Ärztemangel: 1) liegen darunter."""
    solide = [{"score": 0.85}, {"score": 0.7}, {"score": 0.55}, {"score": 0.3}]
    assert qa.beleglage(solide) == "solide"
    # Zu wenige starke Treffer (A20-Signatur: 2 Treffer, bester 0,54).
    assert qa.beleglage([{"score": 0.54}, {"score": 0.51}, {"score": 0.2}]) == "duenn"
    # Genug Treffer, aber KEIN Volltreffer — die Straßenbahn-Signatur (sechs
    # mittelmäßige, bester 0,61). Am echten Bestand nachjustiert: Die erste
    # Fassung ging über den Bestwert und stufte genau die als solide ein.
    assert qa.beleglage([{"score": 0.61}, {"score": 0.58}, {"score": 0.55},
                         {"score": 0.53}, {"score": 0.52}, {"score": 0.5}]) == "duenn"
    # Ein einzelner Volltreffer trägt, wenn genug Brauchbares daneben steht.
    assert qa.beleglage([{"score": 0.72}, {"score": 0.55}, {"score": 0.51}]) == "solide"
    # Kein Volltreffer, aber einer klar nah dran → trägt ebenfalls.
    assert qa.beleglage([{"score": 0.78}, {"score": 0.55}, {"score": 0.51}]) == "solide"
    # Gar nichts gefunden ist der dünnste Fall.
    assert qa.beleglage([]) == "duenn"
    # Fehlende Scores (Keyword-Fallback) zählen als 0 — nie als stark.
    assert qa.beleglage([{"title": "ohne score"}] * 5) == "duenn"


def test_latest_intent_ist_enger_als_allgemeine_aktualitaet():
    """Nur eine ausdrückliche Neueste-Frage darf den semantischen Reranker
    umgehen. Ein aktueller Sachstand braucht weiterhin die fachlich wichtigen
    Stationen; ein genanntes historisches Jahr erst recht."""
    assert qa.latest_intent("Was wurde in Kreyenbrück zuletzt beschlossen?")
    assert qa.latest_intent("Welche neuesten Beschlüsse gibt es in Nadorst?")
    assert qa.latest_intent("Was sind die jüngsten Beschlüsse für Eversten?")
    assert not qa.latest_intent("Wie ist der aktuelle Stand in Kreyenbrück?")
    assert not qa.latest_intent("Was wurde 2019 zuletzt in Kreyenbrück beschlossen?")
    messages, _ = qa._answer_messages(
        "Was wurde in Kreyenbrück zuletzt beschlossen?",
        [{"id": 1, "title": "Sachstandsbericht", "outcome": "zur_kenntnis",
          "session_date": "2026-04-28"},
         {"id": 2, "title": "Jüngster echter Beschluss", "outcome": "angenommen",
          "session_date": "2026-04-21"}],
        typ="ort",
    )
    assert "CHRONOLOGIE" in messages[0]["content"]
    assert "echte Entscheidung" in messages[0]["content"]
    assert "[2] vom 2026-04-21" in messages[0]["content"]
    assert qa.latest_real_decision([
        {"id": 1, "outcome": "zur_kenntnis"},
        {"id": 2, "outcome": "vertagt"},
        {"id": 3, "outcome": "abgelehnt"},
        {"id": 4, "outcome": "angenommen"},
    ])["id"] == 3


def test_latest_place_answer_ist_deterministisch_und_unterscheidet_berichte():
    answer = qa.latest_place_answer([
        {"id": 1, "title": "Neuer Sachstandsbericht", "outcome": "zur_kenntnis",
         "session_date": "2026-04-28", "committee": "Rat"},
        {"id": 2, "title": "Jüngster echter Beschluss", "outcome": "angenommen",
         "session_date": "2026-04-21", "committee": "Rat"},
        {"id": 3, "title": "Alter Beschluss", "outcome": "angenommen",
         "session_date": "2025-12-11", "committee": "Rat"},
    ])
    assert answer.startswith("Am 21.04.2026")
    assert "Jüngster echter Beschluss" in answer and "[2]" in answer
    assert "28.04.2026" in answer and "kein neuer Beschluss" in answer and "[1]" in answer
    assert "Alter Beschluss" not in answer

    rejected = qa.latest_place_answer([
        {"id": 4, "title": "Antrag auf Umbau", "outcome": "abgelehnt",
         "session_date": "2026-05-02", "committee": "Bauausschuss"},
    ])
    assert "jüngste Abstimmungsentscheidung" in rejected
    assert "abgelehnt" in rejected and "nicht beschlossen [4]" in rejected

    report_only = qa.latest_place_answer([
        {"id": 5, "title": "Bericht", "outcome": "zur_kenntnis",
         "session_date": "2026-05-03"},
    ])
    assert report_only.startswith("Einen angenommenen oder abgelehnten Beschluss")
    assert "[5]" in report_only


def test_duenn_regel_nur_bei_duenner_lage():
    messages, _ = qa._answer_messages("Frage?", [{"id": 1, "title": "T"}], duenn=True)
    assert "DÜNNE BELEGLAGE" in messages[0]["content"]
    messages, _ = qa._answer_messages("Frage?", [{"id": 1, "title": "T"}])
    assert "DÜNNE BELEGLAGE" not in messages[0]["content"]


def test_gross_regel_verlangt_kurz_gesagt():
    """Der Blind-Judge kritisierte am neuen Stand die KLARHEIT („mischt
    Informationen") — die Langfassung führt jetzt mit einem Fazit-Satz."""
    messages, _ = qa._answer_messages("Wie läuft es mit dem Stadion?",
                                      [{"id": 1, "title": "T"}], gross=True)
    assert "**Kurz gesagt:**" in messages[0]["content"]


def test_steckbrief_block_ist_kein_zitierbarer_beschluss():
    block = qa._steckbrief_block([
        {"name": "GSG", "slug": "gsg", "description": "Die GSG ist eine kommunale " * 40},
        {"name": "Stadion", "slug": "stadion", "description": "Neubau an der Maastrichter Straße."},
        {"name": "Drittes", "slug": "x", "description": "wird gekappt"},
    ])
    assert "HINTERGRUND" in block and "NIE mit [id]" in block
    assert "GSG" in block and "Stadion" in block
    assert "Drittes" not in block          # höchstens zwei
    assert len(block) < 1200               # Beschreibungen gekappt
    assert qa._steckbrief_block([]) == ""
    assert qa._steckbrief_block(None) == ""


def test_steckbriefe_fuer_findet_ueber_den_entitaets_anker(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_entities (id, slug, name, kind, n) "
                "VALUES (1, 'gsg', 'GSG', 'organisation', 12)")
            store._conn.execute(
                "INSERT INTO council_entity_meta (slug, description) "
                "VALUES ('gsg', 'Die GSG ist die kommunale Wohnungsgesellschaft.')")
        treffer = qa.steckbriefe_fuer(store, "Was ist die GSG und was macht sie?")
        assert [t["name"] for t in treffer] == ["GSG"]
        assert "Wohnungsgesellschaft" in treffer[0]["description"]
        # Ohne genannte Entität bleibt es leer — kein Rauschen im Prompt.
        assert qa.steckbriefe_fuer(store, "Was kostet der Radweg?") == []
        # Entität ohne Beschreibung liefert keinen leeren Steckbrief.
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_entities (id, slug, name, kind, n) "
                "VALUES (2, 'hafen', 'Hafen', 'ort', 5)")
        assert qa.steckbriefe_fuer(store, "Was ist mit dem Hafen?") == []
    finally:
        store.close()


def _ausblick_store(tmp_path):
    """Zwei kommende Termine (mit geplanter Behandlung im ergebnis-Feld) und
    einer in der Vergangenheit."""
    store = CouncilStore(tmp_path / "a.sqlite")
    with store._conn:
        store._conn.executemany(
            "INSERT INTO council_vorlagen (kvonr, template_number, title, fetched_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            [(1, "26/1", "Kompensation bei städtischen Baumfällungen"),
             (2, "26/2", "Bürgerbeteiligung an einem Windkraftwerk"),
             (3, "26/3", "Sachstandsbericht EU-Wiederherstellungsverordnung")])
        store._conn.executemany(
            "INSERT INTO council_beratungen (kvonr, date, committee, result, fetched_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            [(1, "2099-01-05", "Umweltausschuss", "Vorberatung"),
             (2, "2099-02-01", "Umweltausschuss", "Kenntnisnahme"),
             (3, "2099-01-20", "Rat", "Kenntnisnahme"),
             (1, "2000-01-01", "Rat", "beschlossen")])
    return store


def test_geplante_beratungen_ignoriert_das_ergebnis_feld(tmp_path):
    """Bei KÜNFTIGEN Stationen trägt ``result`` die geplante Behandlung
    („Vorberatung"), kein Resultat. Die erste Fassung verlangte ein leeres
    Feld — und lieferte damit auf Prod dauerhaft nichts (0 von 22 Terminen)."""
    store = _ausblick_store(tmp_path)
    try:
        plan = store.geplante_beratungen_fuer([1, 2])
        assert [p["date"] for p in plan] == ["2099-01-05", "2099-02-01"]  # nach Datum
        assert plan[0]["art"] == "Vorberatung"        # Behandlungsart kommt mit
        assert all(p["date"] >= "2099" for p in plan)  # Vergangenes bleibt draußen
        assert store.geplante_beratungen_fuer([]) == []
    finally:
        store.close()


def test_kommende_beratungen_matcht_auf_wortgrenzen(tmp_path):
    """Themen-Ausblick: Der Titel-Abgleich muss an Wortanfängen greifen —
    als Teilwort-Suche traf „stand" das „Sach*stand*sbericht" und hängte einer
    Brücken-Frage einen EU-Verordnungs-Termin an (gemessen 11.08.)."""
    store = _ausblick_store(tmp_path)
    try:
        # Kompositum: „Baumfällungen" trifft, Wortanfang genügt.
        treffer = store.kommende_beratungen(["baumfällungen"])
        assert [t["template_number"] for t in treffer] == ["26/1"]
        assert store.kommende_beratungen(["windkraft"])[0]["template_number"] == "26/2"
        # Generisches „Stand" trifft NICHTS mehr (weder Stoppliste noch Wortmitte).
        assert store.kommende_beratungen(["stand"]) == []
        assert store.kommende_beratungen(["sachstand", "beschluss"]) == []
        # Kurze Wörter zählen nicht, leere Eingabe liefert leer.
        assert store.kommende_beratungen(["rat"]) == []
        assert store.kommende_beratungen([]) == []
        # Je Vorlage nur die NÄCHSTE Station, nicht jede.
        assert len(store.kommende_beratungen(["kompensation"])) == 1
    finally:
        store.close()


def test_kommende_beratungen_ignoriert_strasse(tmp_path):
    """Tims Screenshot-Befund 19.08.: Bei „Stadionneubau Maastrichter Straße"
    hängte „Wie es weitergeht" drei fremde Verkehrsausschuss-Termine an —
    zwei Straßenwidmungen und einen B-Plan-Sachstand, die nur das Wort
    „Straße" mit der Frage teilten. Derselbe Fehlerklasse wie „stand"."""
    store = CouncilStore(tmp_path / "a.sqlite")
    try:
        with store._conn:
            store._conn.executemany(
                "INSERT INTO council_vorlagen (kvonr, template_number, title, fetched_at) "
                "VALUES (?, ?, ?, datetime('now'))",
                [(1, "26/1", "Widmung der Straße \"Sylter Ring\" - Beschluss"),
                 (2, "26/2", "Sachstand Hannah-Arendt-Straße (B-Plan S-745 A)")])
            store._conn.executemany(
                "INSERT INTO council_beratungen (kvonr, date, committee, result, fetched_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                [(1, "2099-01-05", "Verkehrsausschuss", "Vorberatung"),
                 (2, "2099-01-05", "Verkehrsausschuss", "Kenntnisnahme")])
        # Nur "straße" (gefaltet: "strasse") wäre der einzige Treffer — und
        # steht jetzt in der Stoppliste. "maastrichter" träfe nichts hier,
        # weil kein Stadion-Termin in dieser Fixture liegt.
        assert store.kommende_beratungen(["stadionneubau", "maastrichter", "straße"]) == []
    finally:
        store.close()


def test_steckbrief_karte_nur_wenn_die_antwort_sie_nicht_wiederholt():
    """Tims Befund 12.08.: Bei „Was ist die GSG?" las sich Steckbrief und
    Antwort doppelt. Zwei Wege halfen gemessen NICHT — das Modell bitten
    umzulenken (Überlappung 45 % → 44 %) und das „Kurz gesagt" streichen (die
    Definition rutschte in den ersten Satz, 79 % Überlappung). Also die KARTE
    weglassen; der Hintergrund bleibt im Prompt.

    Nur bei echten Definitionsfragen: Bei der Cäcilienbrücke ergänzen sich
    beide Blöcke — das war Tims ausdrückliches Lob."""
    assert qa.steckbrief_karte_zeigen("Was ist die GSG und was macht sie?") is False
    assert qa.steckbrief_karte_zeigen("Wer ist der Oberbürgermeister?") is False
    assert qa.steckbrief_karte_zeigen("Was macht die GSG?") is False
    # Sachstand und eigene Prädikate: Karte bleibt.
    assert qa.steckbrief_karte_zeigen("Wie ist der Stand bei der Cäcilienbrücke?") is True
    assert qa.steckbrief_karte_zeigen("Was ist beim Fliegerhorst geplant?") is True
    assert qa.steckbrief_karte_zeigen("Was ist zum Stadion beschlossen worden?") is True
    assert qa.steckbrief_karte_zeigen("Was kostet der Neubau?") is True

    # Der Hintergrund bleibt in JEDEM Fall im Prompt — er macht die Antwort besser.
    sb = [{"name": "GSG", "slug": "gsg", "description": "Kommunale Wohnungsgesellschaft."}]
    messages, _ = qa._answer_messages("Was ist die GSG?", [{"id": 1, "title": "T"}],
                                      gross=True, steckbriefe=sb)
    assert "HINTERGRUND" in messages[0]["content"]
    assert "**Kurz gesagt:**" in messages[0]["content"]   # Fazit bleibt unberührt


def test_rerank_cache_spart_den_teuren_schritt(monkeypatch):
    """Der Cross-Encoder ist mit ~3,5 s für 119 Paare der teuerste Schritt der
    Suche (86 % der Retrieval-Zeit, auf Prod gemessen). Wortgleiche Fragen —
    Beispielfragen, Folgefragen-Chips, „nochmal versuchen" — dürfen ihn nicht
    zweimal zahlen. Gemessen: 3,6 s → 0,07 s bei identischer Reihenfolge."""
    aufrufe = {"n": 0}

    class _Fake:
        def rerank(self, query, texte):
            aufrufe["n"] += 1
            # Später gelistete Dokumente sollen schlechter ranken.
            return [1.0 - i for i, _ in enumerate(texte)]

    emb._RERANK_CACHE.clear()
    monkeypatch.setattr(emb, "_get_reranker", lambda: _Fake())
    docs = [(1, "Stadion Maastrichter Straße"), (2, "Radweg"), (3, "Hafen")]

    erst = emb.rerank("Wie ist der Stand?", docs)
    assert [i for i, _ in erst] == [1, 2, 3]
    assert aufrufe["n"] == 1

    # Zweiter Lauf: identisches Ergebnis, KEIN Modell-Aufruf.
    nochmal = emb.rerank("Wie ist der Stand?", docs)
    assert nochmal == erst
    assert aufrufe["n"] == 1

    # Andere Frage → der Cache darf nicht antworten.
    emb.rerank("Was kostet das?", docs)
    assert aufrufe["n"] == 2

    # Geänderter Paartext (neuer Vorlagen-Auszug) → neu bewerten, nichts Altes.
    emb.rerank("Wie ist der Stand?", [(1, "Stadion — jetzt mit Auszug"), (2, "Radweg")])
    assert aufrufe["n"] == 3

    # Doppelte ids fallen weg, statt das Ergebnis zu verdoppeln.
    assert len(emb.rerank("Doppelt?", [(7, "a"), (7, "a"), (8, "b")])) == 2
    emb._RERANK_CACHE.clear()
