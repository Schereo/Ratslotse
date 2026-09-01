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
        {"speaker": "Jens Lükermann", "party": "FDP/Volt", "text": "…"},
        {"speaker": "Pfeiffer", "party": "Fraktion FDP/Volt", "text": "…"},
        {"speaker": "Ratsherr Unbekannt", "party": "FDP/Volt", "text": "…"},
        {"speaker": "Finke", "party": "Für Oldenburg", "text": "…"},
        {"speaker": "Oeljeschläger", "party": "SPD", "text": "…"},
    ]
    qa.parteien_aufloesen(_PersonenStore(), rows)
    assert rows[0]["party"] == "Volt"
    assert rows[1]["party"] == "FDP"
    # Ohne Stammdaten-Treffer bleibt das quellentreue Gruppen-Label stehen.
    assert rows[2]["party"] == "FDP/Volt"
    # „Für Oldenburg" ist NICHT auflösbar (das RIS führt selbst nur die Gruppe).
    assert rows[3]["party"] == "Für Oldenburg"
    assert rows[4]["party"] == "SPD"


def test_finde_person_namen_titel_und_faltung():
    store = _PersonenStore()
    assert qa.finde_person(store, "Was sagt Lükermann zum Stadion?")["party"] == "Volt"
    assert qa.finde_person(store, "Wie steht Jens Lükermann zur Brücke?")["name"] == "Jens Lükermann"
    # ASCII-Schreibweise trifft den Umlaut-Namen; Doppelname als Ganzes.
    assert qa.finde_person(store, "Was meint Luekermann dazu?")["party"] == "Volt"
    assert qa.finde_person(store, "Position von Niewerth-Baumann zum Haushalt?")["party"] == "CDU"
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
                "INSERT INTO council_wortbeitraege (ksinr, position, speaker, party, kind, "
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
            return [{"id": i, "speaker": "Lükermann", "party": "FDP/Volt",
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
            [(1, "Tim Harms", "SPD", "member"), (1, "Dr. Ingo Harms", "CDU", "member"),
             (2, "Tim Harms", "SPD", "member")])
        store._conn.executemany(
            "INSERT INTO council_wortbeitraege (ksinr, position, speaker, party, kind, top, "
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
        assert d["overall"] == 4
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
        assert {g["committee"]: g["n"] for g in d["committees"]} == {"Rat": 3, "Verkehrsausschuss": 1}

        nur_verkehr = store.wortbeitraege_person("Tim Harms", committee="Verkehrsausschuss")
        assert nur_verkehr["total"] == 1 and nur_verkehr["overall"] == 4
        assert nur_verkehr["items"][0]["text"] == "Im Verkehrsausschuss"

        # Seiten überlappen nicht und decken zusammen alles ab.
        s1 = store.wortbeitraege_person("Tim Harms", limit=2, offset=0)
        s2 = store.wortbeitraege_person("Tim Harms", limit=2, offset=2)
        assert len(s1["items"]) == 2 and len(s2["items"]) == 2
        assert {w["text"] for w in s1["items"]}.isdisjoint({w["text"] for w in s2["items"]})
        assert s1["total"] == 4

        # Unbekanntes Gremium → leere Seite, aber ehrliche Gesamtzahl.
        leer = store.wortbeitraege_person("Tim Harms", committee="Sportausschuss")
        assert leer["items"] == [] and leer["total"] == 0 and leer["overall"] == 4
    finally:
        store.close()


def test_member_name_und_erste_seite(tmp_path):
    store = _wb_store(tmp_path)
    try:
        assert store.member_name("tim-harms") == "Tim Harms"
        assert store.member_name("gibt-es-nicht") is None
        d = store.member_detail("tim-harms")
        assert d["speeches_total"] == 4
        assert len(d["speeches"]) == 4          # weniger als eine volle Seite
        assert {g["committee"] for g in d["speeches_committees"]} == {"Rat", "Verkehrsausschuss"}
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
                [(2, "Jens Lükermann", "FDP/Volt", "member", None),
                 (1, "Hans-Henning Adler", "DIE LINKE.", "member", None),
                 (2, "Jürgen Krogmann", "Verwaltung", "administration", "Oberbürgermeister"),
                 (2, "Jürgen Krogmann", "Verwaltung", "administration", "Oberbürgermeister, bis TOP 8.2"),
                 (1, "Gabriele Nießen", "Verwaltung", "administration", "Stadtbaurätin"),
                 (2, "Dagmar Sachse", "Verwaltung", "administration", "Für Oberbürgermeister Krogmann")])
        lex = {p["slug"]: p for p in store.personen_lexikon()}

        lk = lex["jens-luekermann"]
        assert lk["art"] == "council" and lk["aktiv"] is True
        assert lk["nachname"] == "luekermann" and lk["vorname"] == "jens"

        adler = lex["hans-henning-adler"]
        assert adler["aktiv"] is False  # zuletzt vor ~2,5 Jahren gesehen

        kro = lex["juergen-krogmann"]
        assert kro["art"] == "city" and kro["role"] == "Oberbürgermeister"

        # Zeit-Zusätze („bis TOP 8.2") und Vertretungs-Notizen sind kein Amt.
        assert lex["dagmar-sachse"]["role"] is None
        # Amt bleibt erhalten, aktiv aber nicht mehr (Nießen lange raus).
        niessen = lex["gabriele-niessen"]
        assert niessen["role"] == "Stadtbaurätin" and niessen["aktiv"] is False
    finally:
        store.close()


def _bericht_personen(store, zeilen):
    """Aufsichtsorgan-Zeilen einsetzen: (bericht_jahr, name, funktion)."""
    with store._conn:
        store._conn.executemany(
            "INSERT INTO council_gesellschaft_personen (report_year, company, "
            "sort_order, committee, name, position, chair_role, note, "
            "roles_assignable, fetched_at) "
            "VALUES (?, 'gsg', ?, 'Aufsichtsrat', ?, ?, NULL, NULL, 1, datetime('now'))",
            [(j, i, n, f) for i, (j, n, f) in enumerate(zeilen)])


def test_personen_lexikon_beteiligung_mit_funktion(tmp_path):
    """Tims Auftrag 17.08.: Wer in einem Aufsichtsorgan einer städtischen
    Gesellschaft sitzt, steht mit **seiner Funktion** im Verzeichnis — auch
    ohne Ratsmandat.

    Die GOL ist eine Gemeinschaftsgesellschaft mit dem Landkreis; Landrätin
    und Kreistagsmitglieder sind gewählte Mandatsträger*innen, nur eben nicht
    des Stadtrats. Daneben stehen Beschäftigtenvertretungen. Beide kamen in
    keiner Anwesenheitsliste vor und standen deshalb namenlos da.

    Belegt ist genau dreierlei: Name, Funktion und die Berichtsjahrgänge, in
    denen die Person vorkommt — keine Partei, keine Amtszeit."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        _bericht_personen(store, [
            (2022, "Karin Harms", "Landrätin"),
            (2023, "Karin Harms", "Landrätin"),
            (2024, "Karin Harms", "Landrätin"),
            (2022, "Inga Bartels", "Beschäftigtenvertreterin"),
        ])
        lex = {p["slug"]: p for p in store.personen_lexikon()}

        harms = lex["karin-harms"]
        assert harms["art"] == "participation"
        assert harms["role"] == "Landrätin"      # die Funktion aus dem Bericht
        assert harms["party"] is None            # der Bericht nennt keine
        # Zeitraum = Berichtsjahrgänge, nicht Amtszeit.
        assert (harms["von"], harms["bis"]) == ("2022", "2024")
        assert harms["aktiv"] is True             # steht im jüngsten Bericht

        # Wer nur in einem alten Bericht steht, gilt nicht mehr als aktuell.
        bartels = lex["inga-bartels"]
        assert bartels["role"] == "Beschäftigtenvertreterin"
        assert (bartels["von"], bartels["bis"], bartels["aktiv"]) == ("2022", "2022", False)
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
            zeilen.append((ks, "Thomas Klein", "SPD", "member"))
        zeilen.append((2, "Klein", "SPD", "member"))
        # Britta Klein sitzt in der Verwaltung — anderer Namensraum, bleibt.
        zeilen.append((3, "Britta Klein", "Verwaltung", "administration"))
        # Namensänderung: „Tim Harms" heißt zuletzt „Tim Ebbeke Harms".
        zeilen += [(1, "Tim Harms", "Bündnis 90/Die Grünen", "member"),
                   (2, "Tim Harms", "Bündnis 90/Die Grünen", "member"),
                   (3, "Tim Ebbeke Harms", "Bündnis 90/Die Grünen", "member")]
        # Zwei echte Namensvetterinnen derselben Fraktion: NICHT zusammenlegen.
        zeilen += [(3, "Meike Bruns", "CDU", "member"), (3, "Sarah Bruns", "CDU", "member")]
        # Gleicher Nachname, verschiedene Fraktion: erst recht nicht.
        zeilen += [(3, "Meyer", "SPD", "member"), (3, "Jan-Martin Meyer", "DIE LINKE.", "member")]
        store._conn.executemany(
            "INSERT INTO council_attendance (ksinr, name, party, role, note) "
            "VALUES (?, ?, ?, ?, NULL)", zeilen)
    return store



def test_person_seite_bleibt_unter_alter_schreibweise_erreichbar(tmp_path):
    """Die weichende Namensform ist ein Link, der irgendwo stehen kann — er
    muss weiter auf dieselbe Person führen, nicht ins Leere. Geführt werden die
    Formen in ``council.namensformen.GRUPPEN``."""
    store = _varianten_store(tmp_path)
    try:
        # Beide Slugs führen zu EINER Person — angezeigt wird die Form der
        # jüngsten Fundstelle (die Regel in council/namensformen.py).
        assert store.member_name("klein") == store.member_name("thomas-klein") == "Thomas Klein"
        alt_form = store.member_detail("tim-ebbeke-harms")
        neue_form = store.member_detail("tim-harms")
        assert alt_form and neue_form
        assert alt_form["name"] == neue_form["name"] == "Tim Ebbeke Harms"
        assert alt_form["n_sessions"] == neue_form["n_sessions"] == 3
        assert store.member_detail("gibt-es-nicht") is None
    finally:
        store.close()


def test_personen_lexikon_beteiligung_ueberschreibt_kein_ratsmandat(tmp_path):
    """Rangfolge: Wer schon als Ratsmitglied oder Verwaltungsperson im Lexikon
    steht, behält diesen Eintrag — der Bericht ergänzt nur, was fehlt.

    Sonst würde aus einem Ratsmandat ein „Ratsmitglied" ohne Partei und ohne
    Personen-Seite, und aus der Oberbürgermeisterei „Vertreter
    Mitgesellschafter". Verglichen wird über das **Namenspaar**, nicht über
    den Slug: Das Verzeichnis führt „Ruth Regina Drügemöller", der Bericht
    „Ruth Drügemöller" — verschiedene Slugs, derselbe Mensch."""
    from datetime import date, timedelta
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        frisch = (date.today() - timedelta(days=30)).isoformat()
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_sessions (ksinr, committee, session_date, "
                "session_time, location, fetched_at) "
                "VALUES (1, 'Rat', ?, '', '', datetime('now'))", (frisch,))
            store._conn.executemany(
                "INSERT INTO council_attendance (ksinr, name, party, role, note) "
                "VALUES (1, ?, ?, ?, ?)",
                [("Dr. Ruth Regina Drügemöller", "SPD", "member", None),
                 ("Jürgen Krogmann", "Verwaltung", "administration", "Oberbürgermeister")])
        _bericht_personen(store, [
            (2024, "Ruth Drügemöller", "Ratsmitglied"),
            (2024, "Jürgen Krogmann", "Oberbürgermeister"),
        ])
        lex = store.personen_lexikon()
        arten = {p["slug"]: p["art"] for p in lex}

        # Das Ratsmandat bleibt — und es entsteht KEIN zweiter Eintrag unter
        # der Schreibweise des Berichts.
        assert arten["ruth-regina-druegemoeller"] == "council"
        assert "ruth-druegemoeller" not in arten
        # Dasselbe für die Verwaltung: Amt aus den Protokollen, nicht aus dem
        # Beteiligungsbericht.
        assert arten["juergen-krogmann"] == "city"
        krogmann = next(p for p in lex if p["slug"] == "juergen-krogmann")
        assert krogmann["role"] == "Oberbürgermeister"
    finally:
        store.close()


def _mandats_store(tmp_path):
    """Plenum + Ausschuss, Ratsleute und beratende Mitglieder nebeneinander."""
    from datetime import date, timedelta
    store = CouncilStore(tmp_path / "c.sqlite")
    frisch = (date.today() - timedelta(days=20)).isoformat()
    with store._conn:
        store._conn.executemany(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
            "location, fetched_at) VALUES (?, ?, ?, '', '', datetime('now'))",
            [(1, "Rat", frisch),
             (2, "Ausschuss für Stadtgrün, Umwelt und Klima", frisch),
             (3, "Ausschuss für Stadtgrün, Umwelt und Klima", frisch)])
        store._conn.executemany(
            "INSERT INTO council_attendance (ksinr, name, party, role, note) VALUES (?, ?, ?, ?, ?)",
            [(1, "Paul Behrens", "SPD", "member", None),          # Plenum → Mandat
             (2, "Paul Behrens", "SPD", "member", None),
             (2, "Ben Carlsson Skiba", "Fridays for Future Oldenburg", "member",
              "Beratendes Mitglied"),                               # nur Ausschuss
             (3, "Ben Carlsson Skiba", None, "member", "beratend"),
             (2, "Sabine Görg", "Behindertenbeirat", "member", None),
             (2, "Jörg Kowollik", "beratend", "member", None),     # nur ein Rollenwort
             (1, "Franz Norrenbrock", "WFO-LKR", "member", None)])  # Gruppe im Plenum
    return store


def test_list_members_trennt_mandat_von_beratung(tmp_path):
    """Tims Skiba-Befund 21.08.2026: Wer nur in Ausschüssen sitzt, ist kein
    Ratsmitglied — und trägt statt einer Fraktion seine Organisation."""
    store = _mandats_store(tmp_path)
    try:
        m = {x["slug"]: x for x in store.list_members()}
        assert m["paul-behrens"]["art"] == "council" and m["paul-behrens"]["party"] == "SPD"
        assert m["paul-behrens"]["organisation"] is None
        skiba = m["ben-carlsson-skiba"]
        assert skiba["art"] == "advisory" and skiba["party"] is None
        assert skiba["organisation"] == "Fridays for Future Oldenburg"
        assert m["sabine-goerg"]["organisation"] == "Behindertenbeirat"
        # Reine Rollenwörter sind keine Organisation.
        assert m["joerg-kowollik"]["art"] == "advisory"
        assert m["joerg-kowollik"]["organisation"] is None
        # Ratsgruppe im Plenum: Mandat mit Gruppen-Label statt „parteilos".
        assert m["franz-norrenbrock"]["art"] == "council"
        assert m["franz-norrenbrock"]["party"] == "WFO-LKR"
    finally:
        store.close()


def test_personen_lexikon_beteiligung_nur_echte_personennamen(tmp_path):
    """Nicht jede Zeile des Berichts ist ein Mensch.

    Die TGO Besitz benennt statt Personen ihre Entsendungsrechte
    („Vertreter/in der Landessparkasse zu Oldenburg"), der Bericht führt
    denselben Menschen mal mit, mal ohne Vornamen („Prof. Dr. Bruder" neben
    „Prof. Dr. Ralph Bruder"), und der zweispaltige Extrakt bricht
    gelegentlich mitten im Namen um („Jens Lükerm an"). Keine dieser drei
    Zeilen darf zu einem Verzeichniseintrag werden."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        _bericht_personen(store, [
            (2024, "Vertreter/in der Landessparkasse zu Oldenburg", None),
            (2024, "Prof. Dr. Bruder", "Vertreter Universität"),
            (2024, "Prof. Dr. Ralph Bruder", "Vertreter Universität"),
            (2024, "Jens Lükerm an", "Ratsmitglied"),
            (2024, "Prof. Dr.-Ing. Weisensee", "Vertreter Hochschule"),
            (2024, "Prof. Dr.-Ing. Manfred Weisensee", "Vertreter Hochschule"),
        ])
        lex = {p["slug"]: p for p in store.personen_lexikon()}

        # Der Mensch mit vollem Namen steht drin …
        assert lex["ralph-bruder"]["art"] == "participation"
        assert lex["manfred-weisensee"]["role"] == "Vertreter Hochschule"
        # … die kahlen Nachnamen nicht (von einem Namensvetter nicht zu
        # unterscheiden) …
        assert "bruder" not in lex and "weisensee" not in lex
        # … das Entsendungsrecht nicht …
        assert not any(s.startswith("vertreter-in-") for s in lex)
        # … und der abgebrochene Name auch nicht.
        assert not any("luekerm" in s for s in lex)
    finally:
        store.close()


def test_beratendes_mitglied_ohne_fraktions_zeitreihe(tmp_path):
    """Auf der Personen-Seite stand „Ratsmitglied · parteilos" — beides falsch.
    Ohne Fraktion gibt es auch keine Fraktions-Zeitreihe."""
    store = _mandats_store(tmp_path)
    try:
        skiba = store.member_detail("ben-carlsson-skiba")
        assert skiba["kind"] == "advisory"
        assert skiba["party"] is None and skiba["faction_timeline"] == []
        assert skiba["organisation"] == "Fridays for Future Oldenburg"
        behrens = store.member_detail("paul-behrens")
        assert behrens["kind"] == "council" and behrens["party"] == "SPD"
        assert behrens["faction_timeline"]
        lex = {p["slug"]: p for p in store.personen_lexikon()}
        assert lex["ben-carlsson-skiba"]["art"] == "advisory"
        assert lex["ben-carlsson-skiba"]["role"] == "Beratendes Mitglied · Fridays for Future Oldenburg"
        assert lex["paul-behrens"]["art"] == "council"
    finally:
        store.close()


def test_personen_lexikon_beteiligung_heilt_druckfehler_nicht_zu_neuer_person(tmp_path):
    """„Claudia Oeljeschleger" im Bericht ist kein zweiter Mensch neben
    „Claudia Oeljeschläger" im Verzeichnis — sie darf deshalb auch keinen
    eigenen Eintrag bekommen. Sonst stünden zwei Personen im Verzeichnis, von
    denen es nur eine gibt, und die Bericht-Schreibweise nähme dem
    Ratsmitglied beim Abgleich der Beteiligungsseite die Personen-Seite weg."""
    from datetime import date, timedelta
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        frisch = (date.today() - timedelta(days=30)).isoformat()
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_sessions (ksinr, committee, session_date, "
                "session_time, location, fetched_at) "
                "VALUES (1, 'Rat', ?, '', '', datetime('now'))", (frisch,))
            store._conn.execute(
                "INSERT INTO council_attendance (ksinr, name, party, role, note) "
                "VALUES (1, 'Claudia Oeljeschläger', 'SPD', 'member', NULL)")
        _bericht_personen(store, [(2024, "Claudia Oeljeschleger", "Ratsmitglied")])

        slugs = {p["slug"] for p in store.personen_lexikon()}
        assert "claudia-oeljeschlaeger" in slugs
        assert "claudia-oeljeschleger" not in slugs
    finally:
        store.close()


def test_ris_stammdaten_zaehlen_als_mandat(tmp_path):
    """Nachrücker:innen stehen im RIS als Ratsmitglied, bevor sie im ersten
    Ratsprotokoll auftauchen — das zählt als zweite Quelle."""
    store = _mandats_store(tmp_path)
    try:
        assert store.list_members()  # Cache der Varianten füllen
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_persons (kpenr, name, current_faction, fetched_at) "
                "VALUES (99, 'Sabine Görg', 'SPD', datetime('now'))")
            store._conn.execute(
                "INSERT INTO council_memberships (kpenr, kgrnr, committee, role, valid_from, valid_until, fetched_at) "
                "VALUES (99, 1, 'Rat', 'Ratsmitglied', '2026-01-01', NULL, datetime('now'))")
        m = {x["slug"]: x for x in store.list_members()}
        assert m["sabine-goerg"]["art"] == "council"
    finally:
        store.close()


def test_tippfehler_heilung_regeln():
    """Die drei Bedingungen der Druckfehler-Heilung, jede einzeln geprüft.

    Sie greift, wo der Bericht „Ratsmitglied" behauptet, der Vorname exakt
    stimmt und der Nachname um höchstens einen Buchstaben abweicht — und
    sonst nirgends."""
    lex = {
        ("claudia", "oeljeschlaeger"): [
            {"slug": "claudia-oeljeschlaeger", "name": "Claudia Oeljeschläger",
             "art": "council", "party": "SPD"}],
        ("jens", "luekermann"): [
            {"slug": "jens-luekermann", "name": "Jens Lükermann",
             "art": "council", "party": "Volt"}],
        ("petra", "schmidt"): [
            {"slug": "petra-schmidt", "name": "Petra Schmidt",
             "art": "council", "party": "CDU"}],
        ("petra", "schmitz"): [
            {"slug": "petra-schmitz", "name": "Petra Schmitz",
             "art": "council", "party": "SPD"}],
        ("heiko", "meier"): [
            {"slug": "heiko-meier", "name": "Heiko Meier",
             "art": "city", "party": None}],
    }
    heilung = CouncilStore.tippfehler_ratsmitglied

    # Beide echten Druckfehler des Berichts finden ihre Person.
    assert heilung("claudia", "oeljeschleger", "Ratsmitglied", lex)["slug"] \
        == "claudia-oeljeschlaeger"
    assert heilung("jens", "luekerman", "Ratsmitglied", lex)["slug"] == "jens-luekermann"

    # (a) Ohne die Funktion „Ratsmitglied" greift sie nie — eine
    # Beschäftigtenvertreterin ist keine verschriebene Ratsfrau.
    assert heilung("claudia", "oeljeschleger", "Beschäftigtenvertreterin", lex) is None
    assert heilung("claudia", "oeljeschleger", None, lex) is None

    # (b) Der Vorname muss exakt stimmen.
    assert heilung("claudius", "oeljeschlaeger", "Ratsmitglied", lex) is None

    # (c) Zwei Buchstaben Abstand sind kein Druckfehler mehr (Dreher „ue"→„eu").
    assert heilung("jens", "leukermann", "Ratsmitglied", lex) is None

    # Zwei verschiedene Menschen mit ähnlichem Namen: „Petra Schmitt" liegt
    # je einen Buchstaben neben Petra Schmidt UND Petra Schmitz — dann lieber
    # niemand. Ein fehlender Link ist ein fehlender Link; ein falscher ist
    # eine Falschaussage über einen namentlich genannten Menschen.
    assert heilung("petra", "schmitt", "Ratsmitglied", lex) is None

    # Und geheilt wird nur auf ein Ratsmandat: Verwaltungsleute haben gar
    # keine Personen-Seite, auf die man verlinken könnte.
    assert heilung("heiko", "meiers", "Ratsmitglied", lex) is None


def test_verwaltung_detail_nur_mit_erkanntem_amt(tmp_path):
    """Tims Wunsch 19.08.: Verwaltungsleute mit erkanntem Amt bekommen einen
    Steckbrief — ohne (nur Vertretungs-/Zeit-Notiz) gibt es keinen toten
    Link (s. #588). Kein Nachbau von member_detail(): keine Fraktion, kein
    Vorsitz-Zähler, keine Gremien-Präsenz — nur Amt, Zeitraum, Beiträge."""
    from datetime import date, timedelta
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        frisch = (date.today() - timedelta(days=30)).isoformat()
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
                "location, fetched_at) VALUES (1, 'Rat', ?, '', '', datetime('now'))", (frisch,))
            store._conn.executemany(
                "INSERT INTO council_attendance (ksinr, name, party, role, note) VALUES (1, ?, ?, ?, ?)",
                [("Jürgen Krogmann", "Verwaltung", "administration", "Oberbürgermeister"),
                 ("Dagmar Sachse", "Verwaltung", "administration", "Für Oberbürgermeister Krogmann")])
            store._conn.executemany(
                "INSERT INTO council_wortbeitraege (ksinr, position, speaker, party, kind, top, "
                "text, extracted_at) VALUES (1, ?, ?, NULL, 'zusage', 'Ö 1', ?, datetime('now'))",
                [(1, "Krogmann", "Wird geprüft.")])

        kro = store.verwaltung_detail("juergen-krogmann")
        assert kro["type"] == "administration" and kro["role"] == "Oberbürgermeister"
        assert kro["aktiv"] is True
        assert kro["speeches_total"] == 1

        # Nur eine Vertretungs-Notiz, kein erkanntes Amt → kein Steckbrief.
        assert store.verwaltung_detail("dagmar-sachse") is None
        assert store.verwaltung_detail("gibt-es-nicht") is None

        assert store.verwaltung_name("juergen-krogmann") == "Jürgen Krogmann"
        assert store.verwaltung_name("gibt-es-nicht") is None
    finally:
        store.close()


def test_lexikon_fuehrt_fraktions_phasen_nur_bei_wechslern(tmp_path):
    """Für die Zeile „Finke (SPD)" von 2022 muss das Lexikon wissen, dass Vally
    Finke damals SPD war — heute sitzt sie für „Für Oldenburg" (Tims Befund
    21.08.2026). Wer nie gewechselt hat, braucht die Liste nicht."""
    from datetime import date, timedelta
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        frisch = (date.today() - timedelta(days=20)).isoformat()
        frueher = f"{int(frisch[:4]) - 3}{frisch[4:]}"
        with store._conn:
            store._conn.executemany(
                "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
                "location, fetched_at) VALUES (?, 'Rat', ?, '', '', datetime('now'))",
                [(1, frueher), (2, frisch)])
            store._conn.executemany(
                "INSERT INTO council_attendance (ksinr, name, party, role, note) "
                "VALUES (?, ?, ?, 'member', NULL)",
                [(1, "Vally Finke", "SPD"), (2, "Vally Finke", "Für Oldenburg"),
                 (1, "Paul Behrens", "SPD"), (2, "Paul Behrens", "SPD")])
        lex = {p["slug"]: p for p in store.personen_lexikon()}
        finke = lex["vally-finke"]
        assert finke["party"] == "Für Oldenburg"      # heute
        assert [ph["party"] for ph in finke["phasen"]] == ["SPD", "Für Oldenburg"]
        assert finke["phasen"][0]["von"] == frueher[:4] and finke["phasen"][0]["bis"] == frueher[:4]
        # Ohne Wechsel keine Phasen-Liste — das Lexikon lädt jede Seite mit.
        assert lex["paul-behrens"]["phasen"] is None
        assert lex["paul-behrens"]["party"] == "SPD"
    finally:
        store.close()


def test_gruppen_label_wird_zur_partei_aufgeloest(tmp_path):
    """Tims Filter-Befund 21.08.2026: „Mitglied der Gruppe FDP/Volt" ist
    niemand. Wo die Zugehörigkeit belegt ist, zeigt das Verzeichnis die
    Partei — eigenständige Gruppen bleiben, Unbelegtes bleibt auch."""
    from datetime import date, timedelta
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        frisch = (date.today() - timedelta(days=20)).isoformat()
        frueher = f"{int(frisch[:4]) - 2}{frisch[4:]}"
        with store._conn:
            store._conn.executemany(
                "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
                "location, fetched_at) VALUES (?, 'Rat', ?, '', '', datetime('now'))",
                [(1, frueher), (2, frisch)])
            store._conn.executemany(
                "INSERT INTO council_attendance (ksinr, name, party, role, note) "
                "VALUES (?, ?, ?, 'member', NULL)",
                [(1, "Benno Schulz", "FDP"), (2, "Benno Schulz", "FDP/Volt"),
                 (2, "Dr. Gunnar Meister", "FDP/Volt"),         # nie einzeln geführt
                 (2, "Jens Lükermann", "FDP/Volt"),             # löst über die Stammdaten auf
                 (2, "Vally Finke", "Für Oldenburg"),           # eigenständige Gruppe
                 (2, "Manfred Klöpper", "Gruppe DIE LINKE./Piratenpartei")])
            store._conn.execute(
                "INSERT INTO council_persons (kpenr, name, current_faction, fetched_at) "
                "VALUES (7, 'Jens Lükermann', 'Volt', datetime('now'))")
        m = {x["slug"]: x for x in store.list_members()}
        assert m["benno-schulz"]["party"] == "FDP"          # aus der eigenen Historie
        assert m["jens-luekermann"]["party"] == "Volt"      # aus den Stammdaten
        assert m["vally-finke"]["party"] == "Für Oldenburg"  # eigenständig, bleibt
        # Ohne Beleg wird nicht geraten — das Label bleibt ehrlich stehen …
        assert m["gunnar-meister"]["party"] == "FDP/Volt"
        assert m["manfred-kloepper"]["party"] == "Die Linke/Piraten"
        # … die Person fällt aber nicht aus dem Filter.
        assert m["gunnar-meister"]["filter_parteien"] == ["FDP", "Volt"]
        assert m["manfred-kloepper"]["filter_parteien"] == ["Die Linke", "Piraten"]
        assert m["benno-schulz"]["filter_parteien"] == ["FDP"]
        assert m["vally-finke"]["filter_parteien"] == ["Für Oldenburg"]
        # Kein Zusammenschluss-Label mehr im Dropdown.
        werte = {w for x in m.values() for w in x["filter_parteien"]}
        assert "FDP/Volt" not in werte and "Die Linke/Piraten" not in werte
    finally:
        store.close()


def test_personen_seite_kopf_loest_gruppe_auf_zeitreihe_bleibt(tmp_path):
    """Tims Wunsch 21.08.2026: Der Kopf der Personen-Seite sagt dasselbe wie
    das Verzeichnis — „FDP/Volt" aufgelöst, wo es belegt ist. Die Zeitreihe
    darunter bleibt quellentreu: Sie erzählt, was die Protokolle DAMALS
    schrieben."""
    from datetime import date, timedelta
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        frisch = (date.today() - timedelta(days=20)).isoformat()
        frueher = f"{int(frisch[:4]) - 2}{frisch[4:]}"
        with store._conn:
            store._conn.executemany(
                "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
                "location, fetched_at) VALUES (?, 'Rat', ?, '', '', datetime('now'))",
                [(1, frueher), (2, frisch)])
            store._conn.executemany(
                "INSERT INTO council_attendance (ksinr, name, party, role, note) "
                "VALUES (?, ?, ?, 'member', NULL)",
                [(1, "Benno Schulz", "FDP"), (2, "Benno Schulz", "FDP/Volt"),
                 (1, "Paul Behrens", "SPD"), (2, "Paul Behrens", "SPD")])
        d = store.member_detail("benno-schulz")
        assert d["current_affiliation"]["label"] == "FDP"      # Kopf: aufgelöst
        assert d["party"] == "FDP"
        assert [t["label"] for t in d["faction_timeline"]] == ["FDP", "FDP/Volt"]  # roh
        # Ohne Zusammenschluss bleibt alles, wie es war.
        b = store.member_detail("paul-behrens")
        assert b["current_affiliation"] == {"label": "SPD", "kind": "party", "parties": ["SPD"]}
    finally:
        store.close()


def test_verein_ist_keine_ratsgruppe(tmp_path):
    """„Gemeinsam für Oldenburg e.V." las als Ratsgruppe „Für Oldenburg" —
    ein Verbandsvertreter wurde so zum Gruppenmitglied (21.08.2026)."""
    from council.parties import classify_faction
    assert classify_faction("Gemeinsam für Oldenburg e.V.")["kind"] == "unknown"
    assert classify_faction("City-Management Oldenburg GmbH")["kind"] == "unknown"
    assert classify_faction("Für Oldenburg")["kind"] == "group"


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
                [("Mara-Marciel Oltmanns", "NABU", "member"),
                 ("Rüdiger Oltmanns", "Wasserstraßen- und Schifffahrtsamt", "guest"),
                 ("Herr Oltmanns", None, "guest")])
        lex = store.personen_lexikon()
        oltmanns = [p for p in lex if p["nachname"] == "oltmanns"]
        arten = sorted(p["art"] for p in oltmanns)
        # Rats-Eintrag + mindestens ein Blocker → kahler Nachname ist mehrdeutig.
        assert "council" in arten and "blocker" in arten and len(oltmanns) >= 2
        blocker = [p for p in oltmanns if p["art"] == "blocker"]
        assert all(p["name"] is None for p in blocker)
    finally:
        store.close()
