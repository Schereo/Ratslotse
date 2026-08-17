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


def _bericht_personen(store, zeilen):
    """Aufsichtsorgan-Zeilen einsetzen: (bericht_jahr, name, funktion)."""
    with store._conn:
        store._conn.executemany(
            "INSERT INTO council_gesellschaft_personen (bericht_jahr, gesellschaft, "
            "reihenfolge, gremium, name, funktion, vorsitz, hinweis, "
            "funktionen_zuordenbar, fetched_at) "
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
        assert harms["art"] == "beteiligung"
        assert harms["rolle"] == "Landrätin"      # die Funktion aus dem Bericht
        assert harms["partei"] is None            # der Bericht nennt keine
        # Zeitraum = Berichtsjahrgänge, nicht Amtszeit.
        assert (harms["von"], harms["bis"]) == ("2022", "2024")
        assert harms["aktiv"] is True             # steht im jüngsten Bericht

        # Wer nur in einem alten Bericht steht, gilt nicht mehr als aktuell.
        bartels = lex["inga-bartels"]
        assert bartels["rolle"] == "Beschäftigtenvertreterin"
        assert (bartels["von"], bartels["bis"], bartels["aktiv"]) == ("2022", "2022", False)
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
                [("Dr. Ruth Regina Drügemöller", "SPD", "mitglied", None),
                 ("Jürgen Krogmann", "Verwaltung", "verwaltung", "Oberbürgermeister")])
        _bericht_personen(store, [
            (2024, "Ruth Drügemöller", "Ratsmitglied"),
            (2024, "Jürgen Krogmann", "Oberbürgermeister"),
        ])
        lex = store.personen_lexikon()
        arten = {p["slug"]: p["art"] for p in lex}

        # Das Ratsmandat bleibt — und es entsteht KEIN zweiter Eintrag unter
        # der Schreibweise des Berichts.
        assert arten["ruth-regina-druegemoeller"] == "rat"
        assert "ruth-druegemoeller" not in arten
        # Dasselbe für die Verwaltung: Amt aus den Protokollen, nicht aus dem
        # Beteiligungsbericht.
        assert arten["juergen-krogmann"] == "stadt"
        krogmann = next(p for p in lex if p["slug"] == "juergen-krogmann")
        assert krogmann["rolle"] == "Oberbürgermeister"
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
        assert lex["ralph-bruder"]["art"] == "beteiligung"
        assert lex["manfred-weisensee"]["rolle"] == "Vertreter Hochschule"
        # … die kahlen Nachnamen nicht (von einem Namensvetter nicht zu
        # unterscheiden) …
        assert "bruder" not in lex and "weisensee" not in lex
        # … das Entsendungsrecht nicht …
        assert not any(s.startswith("vertreter-in-") for s in lex)
        # … und der abgebrochene Name auch nicht.
        assert not any("luekerm" in s for s in lex)
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
                "VALUES (1, 'Claudia Oeljeschläger', 'SPD', 'mitglied', NULL)")
        _bericht_personen(store, [(2024, "Claudia Oeljeschleger", "Ratsmitglied")])

        slugs = {p["slug"] for p in store.personen_lexikon()}
        assert "claudia-oeljeschlaeger" in slugs
        assert "claudia-oeljeschleger" not in slugs
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
             "art": "rat", "partei": "SPD"}],
        ("jens", "luekermann"): [
            {"slug": "jens-luekermann", "name": "Jens Lükermann",
             "art": "rat", "partei": "Volt"}],
        ("petra", "schmidt"): [
            {"slug": "petra-schmidt", "name": "Petra Schmidt",
             "art": "rat", "partei": "CDU"}],
        ("petra", "schmitz"): [
            {"slug": "petra-schmitz", "name": "Petra Schmitz",
             "art": "rat", "partei": "SPD"}],
        ("heiko", "meier"): [
            {"slug": "heiko-meier", "name": "Heiko Meier",
             "art": "stadt", "partei": None}],
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
