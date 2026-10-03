"""Suche über Akten (council/akte_suche.py, Plan „Akte“ Phase 3).

Hier steht die Auswahlregel; ob sie die Antworten besser macht, misst der
Gold-Lauf (scripts/eval_ask_gold.py) mit Schalter an und aus.
"""
import pytest

from council import akte_suche
from tests.akten_testdaten import store_bauen, themen_bauen


@pytest.fixture
def themen(tmp_path):
    return themen_bauen(store_bauen(tmp_path))


def test_leer_ohne_treffer(themen, monkeypatch):
    assert akte_suche.material(themen, "Frage?", [])["decisions"] == []


def test_beschluesse_neueste_zuerst_ohne_teilabstimmung(themen, monkeypatch):
    m = akte_suche.material(themen, "Spielleitplanung?", [{"id": 10}])
    ids = [d["id"] for d in m["decisions"]]
    assert ids[0] == 11 and 10 in ids          # Rat (Mai) vor Ausschuss (April)
    assert 12 not in ids                        # Teilabstimmung


def test_verwaltung_kommt_auch_ohne_naehe(themen, monkeypatch):
    # Nach Vektor-Nähe wird nichts gewählt — die Verwaltung kommt trotzdem.
    monkeypatch.setattr(akte_suche, "_naechste", lambda store, frage, beitraege: [])
    m = akte_suche.material(themen, "Trinkwasserspender?", [{"id": 13}])
    assert [w["id"] for w in m["speeches"]] == [801]   # Protokollnotiz (pledge)


def test_presse_der_akte_neueste_zuerst(themen, monkeypatch):
    m = akte_suche.material(themen, "Spielplatz Schlossplatz?", [{"id": 20}])
    assert [p["id"] for p in m["press"]] == [30]


def test_ohne_grundakten_bleibt_alles_beim_alten(themen, monkeypatch):
    themen._conn.execute("DROP TABLE council_matter_items")
    assert akte_suche.material(themen, "Frage?", [{"id": 10}]) == {
        "decisions": [], "speeches": [], "press": [], "announced": [], "akte": {}}


# --------------------------------------------------------------------------- #
# Phase 4: Zeitleiste, letzte Station, „Zuletzt“
# --------------------------------------------------------------------------- #

BESCHLUSS_ALT = {"id": 1, "title": "Spielleitplanung", "committee": "Ausschuss",
                 "session_date": "2026-04-16", "outcome": "accepted"}
BESCHLUSS_NEU = {"id": 2, "title": "Spielleitplanung", "committee": "Rat",
                 "session_date": "2026-06-01", "outcome": "accepted"}
BEITRAG = {"id": 9, "session_date": "2026-04-16", "committee": "Ausschuss",
           "speaker": "Verwaltung (Protokollnotiz)", "kind": "pledge",
           "text": "Auf dem Schlossplatz ist kein Platz für einen Spielplatz."}
PM = {"id": 5, "date": "2026-08-12", "title": "EU gibt grünes Licht", "auszug": "…"}
TERMIN = {"id": 7, "date": "2026-09-28", "committee": "Rat", "result": "Entscheidung",
          "title": "Ausfallbürgschaft Klinikum"}


def test_zeitleiste_aelteste_zuerst_und_markiert():
    text = akte_suche.zeitleiste([BESCHLUSS_NEU, BESCHLUSS_ALT], [BEITRAG], [PM], [TERMIN])
    text = text[text.index("\n- "):]            # ohne die Kopfzeile des Blocks
    reihe = [text.index(s) for s in ("[1]", "Protokollnotiz der Verwaltung", "[2]",
                                     "Pressemitteilung", "ANGEKÜNDIGT (Entscheidung)")]
    assert reihe == sorted(reihe)
    assert "noch nicht protokolliert" in text


def test_letzte_station_ist_der_juengste_termin():
    st = akte_suche.letzte_station([BESCHLUSS_ALT, BESCHLUSS_NEU], [PM], [TERMIN])
    assert st["art"] == "angekuendigt"
    assert akte_suche.letzte_station([BESCHLUSS_ALT], [], [])["c"]["id"] == 1


def test_nennt_erkennt_id_monat_und_ziffern():
    beschluss = {"art": "beschluss", "datum": "2026-06-01", "c": BESCHLUSS_NEU}
    termin = {"art": "angekuendigt", "datum": "2026-09-28", "c": TERMIN}
    assert akte_suche.nennt("Der Rat stimmte zu [2].", beschluss)
    assert akte_suche.nennt("Im September 2026 berät der Rat.", termin)
    assert akte_suche.nennt("Termin: 28.09.2026.", termin)
    assert not akte_suche.nennt("Der Ausschuss empfahl es im April.", termin)


def test_zuletzt_satz_fuer_termin():
    satz = akte_suche.zuletzt_satz({"art": "angekuendigt", "datum": "2026-09-28", "c": TERMIN})
    assert "Ausfallbürgschaft Klinikum" in satz and "noch nicht" in satz


def test_akte_steht_einmal_im_prompt():
    """Was zum Vorgang gehört, steht nur in der AKTE, nicht doppelt."""
    from council import qa
    andere = {"id": 3, "title": "Etwas anderes", "committee": "Rat",
              "session_date": "2025-01-01", "outcome": "accepted"}
    messages, _ = qa._answer_messages(
        "Wie ist der Stand?", [BESCHLUSS_ALT, BESCHLUSS_NEU, andere], debatten=[BEITRAG],
        presse=[PM], akte={"decision_ids": {1, 2}, "speech_ids": {9}, "press_ids": {5},
                           "announced": [TERMIN]})
    prompt = messages[0]["content"]
    akte_teil = prompt[prompt.index("AKTE DES VORGANGS"):]
    assert prompt.count("[1]") == 1 and "[1]" in akte_teil
    assert "[3]" in prompt[:prompt.index("AKTE DES VORGANGS")]   # Rest bleibt bei den Beschlüssen
    assert prompt.count("kein Platz für einen Spielplatz") == 1
    assert "ZUM VORGANG IN DER AKTE" in prompt


def test_ohne_akte_bleibt_der_prompt_wie_er_war():
    from council import qa
    mit, _ = qa._answer_messages("Frage?", [BESCHLUSS_ALT], akte=None)
    assert "AKTE DES VORGANGS" not in mit[0]["content"]


# --------------------------------------------------------------------------- #
# Die Zeitleiste im Chat
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("tage, text", [
    (0, "am selben Tag"), (1, "1 Tag"), (6, "6 Tage"), (13, "13 Tage"),
    (14, "2 Wochen"), (56, "8 Wochen"), (63, "2 Monate"), (154, "5 Monate"),
    (365, "1 Jahr"), (396, "1 Jahr, 1 Monat"), (761, "2 Jahre, 1 Monat"),
])
def test_abstand_wie_man_ihn_sagt(tage, text):
    assert akte_suche.abstand_text(tage) == text


def _b(i, tag, outcome="accepted", gremium="Rat", **rest):
    return {"id": i, "session_date": tag, "outcome": outcome, "committee": gremium,
            "title": f"Mobilitätsplan {i}", **rest}


def test_zeitleiste_gruppiert_beratungen_ohne_abstimmung():
    """Vier Fachausschüsse binnen fünf Wochen ohne Abstimmung sind EINE Zeile."""
    z = akte_suche.zeitleiste_anzeige([
        _b(1, "2023-03-13", "postponed", "Verkehrsausschuss", vote="unanimous"),
        _b(2, "2023-05-08", "settled", "Wirtschaft"),
        _b(3, "2023-05-11", "settled", "Stadtgrün"),
        _b(4, "2023-06-13", "no_decision", "Soziales"),
        _b(5, "2023-06-26", no_votes=17, vote="majority"),
    ], [], [])
    st = z["stations"]
    assert [s["kind"] for s in st] == ["decision", "group", "decision"]
    gruppe = st[1]
    assert gruppe["title"] == "3 Beratungen ohne Abstimmung"
    assert gruppe["date"] == "2023-05-08" and gruppe["date_end"] == "2023-06-13"
    assert [m["decision_id"] for m in gruppe["members"]] == [2, 3, 4]
    assert st[2]["gap_label"] == "13 Tage"          # ab dem ENDE der Gruppe
    assert st[2]["detail"] == "mehrheitlich, 17 Gegenstimmen"
    assert z["count"] == 5 and z["span"] == "3 Monate"


def test_lange_pause_und_reihenfolge_am_selben_tag():
    z = akte_suche.zeitleiste_anzeige(
        [_b(1, "2024-05-27"), _b(2, "2026-04-20", "noted", "Verkehrsausschuss")],
        [{"id": 9, "date": "2026-04-20", "title": "Viel erreicht", "url": "https://example.org/pm"}],
        [{"date": "2026-09-28", "committee": "Rat", "title": "SUMP 2040"}])
    st = z["stations"]
    assert [s["kind"] for s in st] == ["decision", "decision", "press", "announced"]
    assert st[1]["pause"] and st[1]["gap_label"] == "1 Jahr, 11 Monate"
    assert st[2]["gap_label"] == "am selben Tag" and not st[2]["pause"]
    assert st[2]["url"] == "https://example.org/pm"


def test_eine_station_ist_kein_verlauf():
    assert akte_suche.zeitleiste_anzeige([_b(1, "2024-05-27")], [], []) is None


# --------------------------------------------------------------------------- #
# Die Akte der zitierten Beschlüsse: was der Server selbst anhängt
# --------------------------------------------------------------------------- #

ORTE = {"ofenerdiek", "heidbrook"}


@pytest.mark.parametrize("titel, frage, gehoert", [
    ("Stadion-Neubau: EU und Kommunalaufsicht geben endgültig grünes Licht",
     "Wie ist der Stand beim Stadionneubau?", True),
    ("Im Spätsommer bereits an den Advent denken", "Wie ist der Stand beim Stadionneubau?", False),
    # Ortsname allein reicht nicht — die Sportanlage in Ofenerdiek ist nicht der Bahnübergang.
    ("Umgestaltung der Sportanlage in Ofenerdiek gestartet",
     "Was ist aus dem Bahnübergang in Ofenerdiek geworden?", False),
    ("Bahnübergang Am Stadtrand erneut gesperrt",
     "Was ist aus dem Bahnübergang in Ofenerdiek geworden?", True),
    # Füllwörter tragen nicht.
    ("Bücher treffen Klemmbausteine: Gemeinsame Aktion",
     "Was wurde aus dem gemeinsamen Antrag zum Bahnübergang?", False),
])
def test_pressemitteilung_gehoert_nur_mit_sachwort_dazu(titel, frage, gehoert):
    sach = akte_suche._sachwoerter(frage, ORTE)
    assert akte_suche.gehoert_zum_vorgang(titel, sach, ORTE) is gehoert


def test_spaeteres_datum_in_der_antwort_genuegt():
    """Schlossplatz: Die Antwort endet im April 2026 — ein „Zuletzt: Dezember
    2025“ darunter wäre ein Rückschritt."""
    station = {"art": "beschluss", "datum": "2025-12-11", "c": {"id": 99}}
    assert akte_suche.nennt("Am 16. April 2026 erklärte die Verwaltung …", station)
    assert akte_suche.nennt("Stand: 16.04.2026.", station)
    assert not akte_suche.nennt("Im Mai 2025 hieß es …", station)


def test_kern_ohne_zitat_haengt_nichts_an(themen):
    assert akte_suche.kern(themen, [], "Frage?") == {"decisions": [], "press": [], "announced": []}


def test_kern_nimmt_die_eigene_grundakte_ganz(themen):
    """Die Grundakte eines zitierten Beschlusses gehört ganz dazu, auch ohne
    Sachwort in der Frage (Ausschuss UND Rat zur Spielleitplanung)."""
    k = akte_suche.kern(themen, [11], "Wie ging es weiter?")
    assert {d["id"] for d in k["decisions"]} >= {10, 11}


# --------------------------------------------------------------------------- #
# Eckdaten: Abstimmung, Betrag, Stand und nächster Termin — ohne Modell
# --------------------------------------------------------------------------- #

def _s(i, tag, titel, outcome="accepted", gremium="Rat", ksinr=1, **rest):
    return {"id": i, "session_date": tag, "outcome": outcome, "committee": gremium,
            "title": titel, "ksinr": ksinr, **rest}


STADION_VERGABE = _s(20947, "2026-06-01", "Stadionneubau Maastrichter Straße - Beauftragung",
                     vote="majority", no_votes=18, abstentions=2, amount_eur=57_339_000.0)
STADION_BUERGSCHAFT = _s(20949, "2026-06-01", "Ausfallbürgschaft für die Stadion Oldenburg GmbH",
                         vote="majority", no_votes=18, abstentions=2, amount_eur=44_699_000.0)
STADION_FO = _s(20987, "2026-06-01", "Stadion erst nach EU-Zusage beauftragen", "rejected",
                vote="majority", no_votes=31, amount_eur=57_339_000.0)
STADION_GRUNDSATZ = _s(19127, "2024-04-15", "Stadionneubau Maastrichter Straße", ksinr=0,
                       vote="majority", no_votes=18, abstentions=1)


def test_eckdaten_nehmen_den_juengsten_abgestimmten_beschluss():
    """Am selben Tag gewinnt der, den die Antwort zuerst zitiert; der ältere
    Grundsatzbeschluss ist nicht der Stand."""
    e = akte_suche.key_facts([STADION_GRUNDSATZ, STADION_VERGABE, STADION_BUERGSCHAFT],
                             [], [], [], "2026-10-02", "Wie ist der Stand beim Stadionneubau?")
    assert e["decision"] == {"decision_id": 20947, "date": "2026-06-01", "committee": "Rat",
                             "outcome": "accepted", "vote_label": "mehrheitlich",
                             "vote_counts": ["18 Gegenstimmen", "2 Enthaltungen"],
                             "title": "Stadionneubau Maastrichter Straße - Beauftragung"}
    assert [a["decision_id"] for a in e["amounts"]] == [20947, 20949]
    assert e["amounts"][0]["amount_eur"] == 57_339_000.0
    assert e["latest"] is None and e["next"] is None


def test_eckdaten_ohne_betrag_eines_abgelehnten_antrags():
    """Der abgelehnte Antrag nennt dieselbe Summe — sie ist der Vorschlag,
    nicht das, was gilt."""
    e = akte_suche.key_facts([STADION_FO, STADION_VERGABE], [], [], [], "2026-10-02",
                             "Wie ist der Stand beim Stadion?")
    assert e["decision"]["decision_id"] == 20947
    assert [a["decision_id"] for a in e["amounts"]] == [20947]
    nur_abgelehnt = akte_suche.key_facts([STADION_FO], [], [], [], "2026-10-02", "Stadion?")
    assert nur_abgelehnt["decision"]["outcome"] == "rejected" and nur_abgelehnt["amounts"] == []


def test_eckdaten_stand_danach_und_naechster_termin():
    presse = [{"id": 5, "date": "2026-08-12", "url": "https://example.org/pm",
               "title": "Stadion-Neubau: EU gibt grünes Licht"}]
    termine = [{"date": "2026-09-28", "committee": "Rat", "title": "Stadion: Jahresbericht"},
               {"date": "2026-11-02", "committee": "Rat", "title": "Stadion: Wirtschaftsplan"},
               {"date": "2026-10-20", "committee": "Finanzausschuss", "title": "Stadion: Kredit"}]
    e = akte_suche.key_facts([STADION_VERGABE], [], presse, termine, "2026-10-02",
                             "Wie ist der Stand beim Stadionneubau?")
    # Der 28.09. ist vorbei, aber ohne protokolliertes Ergebnis: jüngster Stand.
    assert e["latest"]["kind"] == "announced" and e["latest"]["date"] == "2026-09-28"
    assert e["next"] == {"kind": "announced", "date": "2026-10-20", "title": "Stadion: Kredit",
                         "committee": "Finanzausschuss", "outcome": None, "decision_id": None,
                         "url": None}
    ohne_termin = akte_suche.key_facts([STADION_VERGABE], [], presse, [], "2026-10-02",
                                       "Stadionneubau?")
    assert ohne_termin["latest"]["url"] == "https://example.org/pm"


def test_eckdaten_nur_mit_sachwort_der_frage():
    """Trinkwasserspender: Die Antwort zitierte am Rand das Schwimmbad — als
    jüngster Beschluss mit Abstimmung hätte es die Eckdaten angeführt."""
    btb = _s(20973, "2026-06-01", "Unterstützung Schwimmbad BTB", vote="unanimous")
    pruefung = _s(20905, "2026-04-16", "Prüfung öffentlicher Trinkwasserspender", "noted",
                  "Ausschuss für Stadtgrün, Umwelt und Klima")
    assert akte_suche.key_facts([pruefung, btb], [], [], [], "2026-10-02",
                                "Wann kommen öffentliche Trinkwasserspender?") is None


def test_eckdaten_falten_umlaute():
    """„Hebesatz“ in der Frage, „Hebesätze“ im Titel."""
    satzung = _s(20592, "2025-12-15", "Satzung über die Festsetzung der Realsteuer-Hebesätze",
                 "rejected", vote="majority", no_votes=43)
    e = akte_suche.key_facts([satzung], [], [], [], "2026-10-02",
                             "Wie hoch ist der Hebesatz der Grundsteuer B?")
    assert (e["decision"]["vote_label"], e["decision"]["vote_counts"]) == \
        ("mehrheitlich", ["43 Gegenstimmen"])


def test_pressemitteilung_die_die_antwort_nennt():
    presse = [{"id": 1, "date": "2026-07-10", "title": "Bund gibt Mittel frei"},
              {"id": 2, "date": "2025-09-18", "title": "WSA hält am Zeitplan fest"}]
    antwort = "Laut Pressemitteilung vom 10. Juli 2026 hat der Bund die Mittel freigegeben."
    assert [p["id"] for p in akte_suche.press_named(antwort, presse)] == [1]
    assert [p["id"] for p in akte_suche.press_named("Stand: 18.09.2025, laut Pressemitteilung",
                                                    presse)] == [2]
    assert akte_suche.press_named("Am 10. Juli 2026 gab der Bund Geld frei.", presse) == []


def test_tag_und_monat_ohne_jahr_genuegen():
    """Stadion: „… laut Pressemitteilung vom 12. August hat die EU …“ — ohne
    diese Erkennung hing der Server dieselbe Meldung als „Zuletzt:“ an."""
    station = {"art": "presse", "datum": "2026-08-12", "c": {}}
    assert akte_suche.nennt("Laut Pressemitteilung vom 12. August hat die EU …", station)
    assert not akte_suche.nennt("Am 2. August war Sommerpause.", station)


def test_eckdaten_wiederholen_den_angehaengten_satz_nicht():
    presse = [{"id": 5, "date": "2026-08-12", "title": "EU gibt grünes Licht", "url": None}]
    termin = [{"date": "2026-11-02", "committee": "Rat", "title": "Stadion: Wirtschaftsplan"}]
    e = akte_suche.key_facts([STADION_VERGABE], [], presse, termin, "2026-10-02", "Stadion?")
    weg = akte_suche.without_station(e, {"art": "presse", "datum": "2026-08-12", "c": {}})
    assert weg["latest"] is None and weg["next"] is not None
    assert akte_suche.without_station(e, None) is e


def test_genannte_pressemitteilung_braucht_ein_sachwort():
    """Die Antwort zur Stadion-Frage nannte den Vorverkauf des Stadionsingens."""
    presse = [{"id": 7, "date": "2026-09-30", "title": "Im Spätsommer bereits an den Advent denken",
               "url": None},
              {"id": 5, "date": "2026-08-12", "title": "Stadion-Neubau: EU gibt grünes Licht",
               "url": None}]
    e = akte_suche.key_facts([STADION_VERGABE], [], presse, [], "2026-10-02",
                             "Wie ist der Stand beim Stadionneubau?")
    assert e["latest"]["date"] == "2026-08-12"


def test_eckdaten_stellen_routine_hintan():
    """Stadion: Der Jahresabschluss der GmbH ist jünger als die Vergabe, aber
    nicht der Stand des Neubaus."""
    abschluss = _s(21027, "2026-06-29", "Stadion Oldenburg GmbH & Co. KG: Jahresabschluss 2025",
                   ksinr=2, vote="unanimous", abstentions=2, amount_eur=781_488.67)
    e = akte_suche.key_facts([STADION_VERGABE, abschluss], [abschluss], [], [], "2026-10-02",
                             "Wie ist der Stand beim Stadionneubau?")
    assert e["decision"]["decision_id"] == 20947 and e["latest"] is None
    # Fragt man nach ihm, zählt er — und ohne Alternative auch.
    assert akte_suche.key_facts([STADION_VERGABE, abschluss], [], [], [], "2026-10-02",
                                "Was steht im Jahresabschluss des Stadions?"
                                )["decision"]["decision_id"] == 21027
    assert akte_suche.key_facts([abschluss], [], [], [], "2026-10-02",
                                "Stadionneubau?")["decision"]["decision_id"] == 21027


# --------------------------------------------------------------------------- #
# Gold-Runde 03.10.2026: Teilabstimmungen, Stadtteile, Presse per Titel, Frische
# --------------------------------------------------------------------------- #

def test_teilabstimmungen_haengen_am_beschluss(tmp_path):
    """Der SPD-Änderungsantrag gehört zum Rats-TOP 5 (Beschluss 11), nicht
    zum Ausschuss-Beschluss 10 — verbunden über Sitzung und TOP."""
    st = store_bauen(tmp_path)
    teile = st.subvotes_of(st.get_decisions_by_ids([10, 11]))
    assert list(teile) == [11]
    assert teile[11][0]["title"] == "Änderungsantrag der SPD-Fraktion"


def test_teilabstimmung_steht_im_kontext():
    """Wärmewende-Beirat: „Auf Antrag der FDP auch Vermietende“ stand bisher
    nur im Suchindex, nie im Kontext der Antwort."""
    from council import qa
    beschluss = {"id": 20958, "title": "Wärmewende-Beirat", "committee": "Rat",
                 "session_date": "2026-06-01", "outcome": "accepted",
                 "subvotes": [{"title": "Änderungsantrag der FDP-Fraktion: Aufnahme der "
                                        "Vermieterseite in den Beirat", "outcome": "accepted",
                               "vote": "majority", "no_votes": 18},
                              {"title": "Geschäftsordnungsantrag der BSW-Fraktion auf Vertagung",
                               "outcome": "rejected", "vote": "majority", "no_votes": 45}]}
    ctx = qa._build_context([beschluss])
    assert ("Dazu abgestimmt: Änderungsantrag der FDP-Fraktion: Aufnahme der Vermieterseite "
            "in den Beirat (angenommen, mehrheitlich, 18 Gegenstimmen); "
            "Geschäftsordnungsantrag der BSW-Fraktion auf Vertagung "
            "(abgelehnt, mehrheitlich, 45 Gegenstimmen)") in ctx


def test_ein_stadtteil_klebt_keine_akten(themen, monkeypatch):
    """Ofenerdiek hing nur an 14 Akten — unter der Größengrenze — und klebte
    Starkregen und Bürgerhaus an den Bahnübergang."""
    from council import matters
    assert "Schlossplatz" in [e["name"] for e in matters.akte_von(themen, [20])["entities"]]
    monkeypatch.setattr(matters, "_stadtteile", lambda: {"schlossplatz"})
    assert "Schlossplatz" not in [e["name"] for e in matters.akte_von(themen, [20])["entities"]]


def test_presse_per_titel_kommt_mit_eigenem_deckel(themen, monkeypatch):
    """„Keine höheren Grundsteuern“ klebte über kein Thema an der Akte."""
    from council import qa
    monkeypatch.setattr(qa, "press_title_ids", lambda store, frage, **kw: [32, 30])
    m = akte_suche.material(themen, "Spielplatz Schlossplatz?", [{"id": 20}])
    assert [p["id"] for p in m["press"]] == [30, 32]      # Akte zuerst, Titel-Treffer dazu


@pytest.mark.parametrize("tag, bonus", [
    ("2026-10-03", 0.3), ("2025-10-03", 0.3 * 0.3679), ("", 0.0), ("2026-12-01", 0.3)])
def test_frische_bonus(tag, bonus):
    from datetime import date
    assert akte_suche.frische({"session_date": tag}, date(2026, 10, 3)) == pytest.approx(bonus, abs=1e-3)
