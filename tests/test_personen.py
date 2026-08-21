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


def test_person_slug_und_anzeige_normalisieren_anreden():
    """Tims Befund 10.08.: „Herr Jens Freymuth" und „Jens Freymuth" erschienen
    als zwei Personen im Verzeichnis — Anreden gehören weder in den Slug noch
    in den Anzeige-Namen; Titel (Dr.) bleiben Teil des Namens."""
    slug = CouncilStore._person_slug
    assert slug("Herr Jens Freymuth") == slug("Jens Freymuth") == "jens-freymuth"
    assert slug("Frau Dr. Niewerth-Baumann") == slug("Dr. Niewerth-Baumann")
    assert slug("Ratsfrau Finke") == slug("Finke")
    # Adelspartikel bleiben — „zu Jeddeloh" ist der Nachname.
    assert slug("Herr zu Jeddeloh") == "zu-jeddeloh"

    anzeige = CouncilStore._person_anzeige
    assert anzeige("Herr Jens Freymuth") == "Jens Freymuth"
    assert anzeige("Frau Dr. Niewerth-Baumann") == "Dr. Niewerth-Baumann"
    assert anzeige("Jens Lükermann") == "Jens Lükermann"
    assert anzeige("Frau Blohm") == "Blohm"


def _wb_store(tmp_path):
    """Zwei Sitzungen in zwei Gremien, zwei Namensvettern („Harms")."""
    store = CouncilStore(tmp_path / "wb.sqlite")
    with store._conn:
        store._conn.executemany(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
            "location, fetched_at) VALUES (?, ?, ?, '', '', datetime('now'))",
            [(1, "Rat", "2026-06-01"), (2, "Verkehrsausschuss", "2026-05-01")])
        store._conn.executemany(
            "INSERT INTO council_attendance (ksinr, name, party, role) VALUES (?, ?, ?, ?)",
            [(1, "Tim Harms", "SPD", "mitglied"), (1, "Dr. Ingo Harms", "CDU", "mitglied"),
             (2, "Tim Harms", "SPD", "mitglied")])
        store._conn.executemany(
            "INSERT INTO council_wortbeitraege (ksinr, position, sprecher, partei, art, top, "
            "text, extracted_at) VALUES (?, ?, ?, 'SPD', 'rede', 'Ö 1', ?, datetime('now'))",
            [(1, 1, "Tim Harms", "Voller Name im Rat"),
             (1, 2, "Harms", "Nur Nachname"),
             (1, 3, "Ratsherr Harms", "Mit Anrede"),
             (1, 4, "Dr. Ingo Harms", "Der Namensvetter"),
             (2, 5, "Tim Harms", "Im Verkehrsausschuss"),
             (2, 6, "Pfeiffer", "Ganz andere Person")])
    return store


def test_wortbeitraege_person_trennt_namensvettern(tmp_path):
    """Der Nachname reicht — solange der Eintrag keinen FREMDEN Vornamen trägt.
    Sonst erbte „Tim Harms" die Beiträge von „Dr. Ingo Harms" (auf Prod real:
    8 von 279 Treffern)."""
    store = _wb_store(tmp_path)
    try:
        d = store.wortbeitraege_person("Tim Harms", limit=20)
        texte = {w["text"] for w in d["items"]}
        assert texte == {"Voller Name im Rat", "Nur Nachname", "Mit Anrede",
                         "Im Verkehrsausschuss"}
        assert "Der Namensvetter" not in texte
        assert d["gesamt"] == 4
        # Der Namensvetter behält seine eigenen Beiträge …
        ingo = store.wortbeitraege_person("Dr. Ingo Harms", limit=20)
        assert "Der Namensvetter" in {w["text"] for w in ingo["items"]}
        # … und erbt die mehrdeutigen (reiner Nachname) ebenfalls — mehr gibt
        # das Protokoll dort nicht her.
        assert "Nur Nachname" in {w["text"] for w in ingo["items"]}
    finally:
        store.close()


def test_wortbeitraege_person_seiten_und_gremienfilter(tmp_path):
    store = _wb_store(tmp_path)
    try:
        d = store.wortbeitraege_person("Tim Harms", limit=20)
        assert {g["committee"]: g["n"] for g in d["gremien"]} == {"Rat": 3, "Verkehrsausschuss": 1}

        nur_verkehr = store.wortbeitraege_person("Tim Harms", gremium="Verkehrsausschuss")
        assert nur_verkehr["total"] == 1 and nur_verkehr["gesamt"] == 4
        assert nur_verkehr["items"][0]["text"] == "Im Verkehrsausschuss"

        # Seiten überlappen nicht und decken zusammen alles ab.
        s1 = store.wortbeitraege_person("Tim Harms", limit=2, offset=0)
        s2 = store.wortbeitraege_person("Tim Harms", limit=2, offset=2)
        assert len(s1["items"]) == 2 and len(s2["items"]) == 2
        assert {w["text"] for w in s1["items"]}.isdisjoint({w["text"] for w in s2["items"]})
        assert s1["total"] == 4

        # Unbekanntes Gremium → leere Seite, aber ehrliche Gesamtzahl.
        leer = store.wortbeitraege_person("Tim Harms", gremium="Sportausschuss")
        assert leer["items"] == [] and leer["total"] == 0 and leer["gesamt"] == 4
    finally:
        store.close()


def test_member_name_und_erste_seite(tmp_path):
    store = _wb_store(tmp_path)
    try:
        assert store.member_name("tim-harms") == "Tim Harms"
        assert store.member_name("gibt-es-nicht") is None
        d = store.member_detail("tim-harms")
        assert d["wortbeitraege_gesamt"] == 4
        assert len(d["wortbeitraege"]) == 4          # weniger als eine volle Seite
        assert {g["committee"] for g in d["wortbeitraege_gremien"]} == {"Rat", "Verkehrsausschuss"}
    finally:
        store.close()


def test_ratspartei_label_filtert_verbaende_und_rollen():
    """Tims TestFlight-Befund 11.08.: Die „Keine passenden Wortbeiträge von:"-
    Zeile nannte ALLE Anwesenheits-Labels — Verbände, Rollen, kaputte
    Einzel-Label. In die Ehrlichkeits-Zeile gehören nur Ratsparteien."""
    echt = {
        "SPD": "SPD", "CDU": "CDU", "CDU-Fraktion": "CDU",
        "BSW-Fraktion": "BSW", "Fraktion DIE LINKE.": "DIE LINKE",
        "Die Grünen": "Bündnis 90/Die Grünen",
        "Bündnis 90/ Die Grünen": "Bündnis 90/Die Grünen",
        "Für Oldenburg": "Für Oldenburg", "FDP/Volt": "FDP/Volt",
        "Volt": "Volt", "AfD": "AfD",
    }
    for roh, kanon in echt.items():
        assert qa.ratspartei_label(roh) == kanon, roh
    for kein_treffer in (
        "ADFC", "VCD Regionalverband Oldenburg e.V", "Fridays for Future Oldenburg",
        "VWG", "Elternvertreter", "Fahrgastverband Pro Bahn",
        "Bund für Umwelt und Naturschutz", "Beschäftigtenvertreterin",
        "BSW Für RH Dr. Onken", "Gemeinsam für Oldenburg e.V. (GfO)",
        "Diakonisches Werk Oldenburg-Stadt", "Beratendes Mitglied",
        "Behindertenbeirat", "", None,
    ):
        assert qa.ratspartei_label(kein_treffer) is None, kein_treffer


def test_personen_lexikon_rat_verwaltung_und_zeitlichkeit(tmp_path):
    """Tims Badge-Wunsch 12.08.: Ratsmitglieder mit Partei und Zeitraum,
    Verwaltung mit geerntetem Amt aus den Protokoll-Notizen — und wer seit
    über einem Jahr in keiner Anwesenheitsliste steht, gilt nicht mehr als
    aktiv (nie „falsch als aktuell anzeigen")."""
    from datetime import date, timedelta
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        frisch = (date.today() - timedelta(days=30)).isoformat()
        alt = (date.today() - timedelta(days=900)).isoformat()
        with store._conn:
            store._conn.executemany(
                "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
                "location, fetched_at) VALUES (?, 'Rat', ?, '', '', datetime('now'))",
                [(1, alt), (2, frisch)])
            store._conn.executemany(
                "INSERT INTO council_attendance (ksinr, name, party, role, note) "
                "VALUES (?, ?, ?, ?, ?)",
                [(2, "Jens Lükermann", "FDP/Volt", "mitglied", None),
                 (1, "Hans-Henning Adler", "DIE LINKE.", "mitglied", None),
                 (2, "Jürgen Krogmann", "Verwaltung", "verwaltung", "Oberbürgermeister"),
                 (2, "Jürgen Krogmann", "Verwaltung", "verwaltung", "Oberbürgermeister, bis TOP 8.2"),
                 (1, "Gabriele Nießen", "Verwaltung", "verwaltung", "Stadtbaurätin"),
                 (2, "Dagmar Sachse", "Verwaltung", "verwaltung", "Für Oberbürgermeister Krogmann")])
        lex = {p["slug"]: p for p in store.personen_lexikon()}

        lk = lex["jens-luekermann"]
        assert lk["art"] == "rat" and lk["aktiv"] is True
        assert lk["nachname"] == "luekermann" and lk["vorname"] == "jens"

        adler = lex["hans-henning-adler"]
        assert adler["aktiv"] is False  # zuletzt vor ~2,5 Jahren gesehen

        kro = lex["juergen-krogmann"]
        assert kro["art"] == "stadt" and kro["rolle"] == "Oberbürgermeister"

        # Zeit-Zusätze („bis TOP 8.2") und Vertretungs-Notizen sind kein Amt.
        assert lex["dagmar-sachse"]["rolle"] is None
        # Amt bleibt erhalten, aktiv aber nicht mehr (Nießen lange raus).
        niessen = lex["gabriele-niessen"]
        assert niessen["rolle"] == "Stadtbaurätin" and niessen["aktiv"] is False
    finally:
        store.close()


def _varianten_store(tmp_path):
    """Ein Bestand mit genau den Schreibweisen, die im Prod-Bestand stehen."""
    from datetime import date, timedelta
    store = CouncilStore(tmp_path / "c.sqlite")
    frisch = (date.today() - timedelta(days=30)).isoformat()
    mittel = (date.today() - timedelta(days=200)).isoformat()
    alt = (date.today() - timedelta(days=1200)).isoformat()
    with store._conn:
        store._conn.executemany(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
            "location, fetched_at) VALUES (?, 'Rat', ?, '', '', datetime('now'))",
            [(1, alt), (2, mittel), (3, frisch)])
        zeilen = []
        # Thomas Klein: dreimal voll, einmal nur als „Klein" — eine Person.
        for ks in (1, 2, 3):
            zeilen.append((ks, "Thomas Klein", "SPD", "mitglied"))
        zeilen.append((2, "Klein", "SPD", "mitglied"))
        # Britta Klein sitzt in der Verwaltung — anderer Namensraum, bleibt.
        zeilen.append((3, "Britta Klein", "Verwaltung", "verwaltung"))
        # Namensänderung: „Tim Harms" heißt zuletzt „Tim Ebbeke Harms".
        zeilen += [(1, "Tim Harms", "Bündnis 90/Die Grünen", "mitglied"),
                   (2, "Tim Harms", "Bündnis 90/Die Grünen", "mitglied"),
                   (3, "Tim Ebbeke Harms", "Bündnis 90/Die Grünen", "mitglied")]
        # Zwei echte Namensvetterinnen derselben Fraktion: NICHT zusammenlegen.
        zeilen += [(3, "Meike Bruns", "CDU", "mitglied"), (3, "Sarah Bruns", "CDU", "mitglied")]
        # Gleicher Nachname, verschiedene Fraktion: erst recht nicht.
        zeilen += [(3, "Meyer", "SPD", "mitglied"), (3, "Jan-Martin Meyer", "DIE LINKE.", "mitglied")]
        store._conn.executemany(
            "INSERT INTO council_attendance (ksinr, name, party, role, note) "
            "VALUES (?, ?, ?, ?, NULL)", zeilen)
    return store


def test_personen_varianten_legt_schreibweisen_zusammen(tmp_path):
    """Ein Mensch, zwei Einträge (Tims Befund 21.08.2026): „Klein" neben
    „Thomas Klein", „Tim Ebbeke Harms" neben „Tim Harms". Das Verzeichnis
    führt sie einmal — echte Namensvettern bleiben getrennt."""
    store = _varianten_store(tmp_path)
    try:
        var = store._personen_varianten()
        assert var == {("rat", "klein"): "thomas-klein",
                       ("rat", "tim-ebbeke-harms"): "tim-harms"}
        namen = {m["slug"]: m for m in store.list_members()}
        assert namen["thomas-klein"]["n"] == 3      # alle Sitzungen, einmal gezählt
        assert namen["tim-harms"]["n"] == 3
        assert "klein" not in namen and "tim-ebbeke-harms" not in namen
        # Zwei Bruns, zwei Meyer: bleiben zwei Personen.
        assert {"meike-bruns", "sarah-bruns", "meyer", "jan-martin-meyer"} <= set(namen)
        # Die Verwaltungs-Klein ist ein anderer Mensch (anderer Namensraum).
        lex = {(p["art"], p["slug"]) for p in store.personen_lexikon()}
        assert ("stadt", "britta-klein") in lex and ("rat", "thomas-klein") in lex
        assert not any(slug == "klein" for _art, slug in lex)
    finally:
        store.close()


def test_person_seite_bleibt_unter_alter_schreibweise_erreichbar(tmp_path):
    """Die weichende Variante ist ein Link, der irgendwo stehen kann — er muss
    weiter auf dieselbe Person führen, nicht ins Leere."""
    store = _varianten_store(tmp_path)
    try:
        assert store.member_name("klein") == "Thomas Klein"
        assert store.member_name("thomas-klein") == "Thomas Klein"
        detail = store.member_detail("tim-ebbeke-harms")
        assert detail and detail["name"] == "Tim Harms"
        assert detail["n_sessions"] == store.member_detail("tim-harms")["n_sessions"] == 3
        assert store.member_detail("gibt-es-nicht") is None
    finally:
        store.close()


def test_haeufigster_name_entscheidet_bei_gleichstand_ausfuehrlich(tmp_path):
    """Bei Gleichstand gewinnt der vollständigere Name — sonst hieß eine Person
    „Dr. Götte", während ihr Slug walter-goette lautete."""
    from collections import Counter
    assert CouncilStore._haeufigster_name(Counter({"Dr. Götte": 2, "Walter Götte": 2})) == "Walter Götte"
    assert CouncilStore._haeufigster_name(Counter({"Streit": 3, "Tim Streit": 1})) == "Streit"


def test_personen_lexikon_blocker_fuer_gaeste(tmp_path):
    """Tims Oltmanns-Befund 12.08.: Ein Gast-Namensvetter (Wasserstraßen-Amt)
    muss den kahlen Nachnamen mehrdeutig machen — als blocker-Eintrag ohne
    Badge-Daten, damit das Frontend lieber gar kein Badge zeigt."""
    from datetime import date, timedelta
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        frisch = (date.today() - timedelta(days=30)).isoformat()
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
                "location, fetched_at) VALUES (1, 'Rat', ?, '', '', datetime('now'))", (frisch,))
            store._conn.executemany(
                "INSERT INTO council_attendance (ksinr, name, party, role, note) "
                "VALUES (1, ?, ?, ?, NULL)",
                [("Mara-Marciel Oltmanns", "NABU", "mitglied"),
                 ("Rüdiger Oltmanns", "Wasserstraßen- und Schifffahrtsamt", "gast"),
                 ("Herr Oltmanns", None, "gast")])
        lex = store.personen_lexikon()
        oltmanns = [p for p in lex if p["nachname"] == "oltmanns"]
        arten = sorted(p["art"] for p in oltmanns)
        # Rats-Eintrag + mindestens ein Blocker → kahler Nachname ist mehrdeutig.
        assert "rat" in arten and "blocker" in arten and len(oltmanns) >= 2
        blocker = [p for p in oltmanns if p["art"] == "blocker"]
        assert all(p["name"] is None for p in blocker)
    finally:
        store.close()
