"""Regex-Ernte (council/ernte.py) + ihre Verdrahtung im Store.

Reine Regex-Logik plus SQLite-Integration — kein Netz, kein LLM.
"""
from council import ernte
from council.store import CouncilStore

VORLAGE_TEXT = """\
  Ausdruck vom: 12.04.2022
  Seite: 1/2

  07.04.2022

Stadtplanungsamt Vorlagen-Nr:
22/0262

öffentlich

Vergnügungsstättenkonzept

Beschlussvorschlag:
Das Vergnügungsstättenkonzept wird beschlossen.
Die Verwaltung wird mit der Umsetzung beauftragt.

Sachverhalt:
Es begab sich aber zu der Zeit.

Auswirkungen:

a) Finanzen
Kosten von 50.000 Euro im Haushalt 2022.
b) Klima
Prüfungsrelevant: Ja, das Konzept steuert den Verkehr in der Innenstadt.

Begründung:
Weil es sein muss.
"""


def test_auswirkungen_und_klima_relevant():
    aus = ernte.auswirkungen(VORLAGE_TEXT)
    assert aus["finanzen"] == "Kosten von 50.000 Euro im Haushalt 2022."
    assert aus["klima"].startswith("Prüfungsrelevant: Ja, das Konzept")
    assert ernte.klima_relevant(aus["klima"]) is True
    assert ernte.klima_relevant("Nein, die Vorlage ist nicht prüfungsrelevant.") is False
    assert ernte.klima_relevant("Der Vermerk fehlt hier völlig.") is None
    assert ernte.klima_relevant(None) is None


def test_auswirkungen_floskeln_zaehlen_nicht():
    text = "Auswirkungen: \n \na) Finanzen \nKeine  \n \nb) Klima \n./. \n \nc) Weitere \nKeine"
    aus = ernte.auswirkungen(text)
    assert aus == {"finanzen": None, "klima": None}
    assert ernte.auswirkungen("Ganz ohne Abschnitt.") == {"finanzen": None, "klima": None}


def test_klima_schneidet_an_der_satzgrenze():
    # Lange Klima-Vermerke wurden mitten im Wort gekappt („Maastrichter Stra").
    satz = "Die Stadionfläche wird aufgewertet und bleibt klimaneutral. "
    text = "b) Klima\nPrüfungsrelevant: Ja. " + satz * 120 + "\nSachverhalt:\nEgal."
    klima = ernte.auswirkungen(text)["klima"]
    assert len(klima) <= 2500
    assert klima.endswith(".") and not klima.endswith("…")


def test_federfuehrendes_amt_einzeilig():
    assert ernte.federfuehrendes_amt(VORLAGE_TEXT) == "Stadtplanungsamt"
    # „Ausdruck vom:"-Zeilen und Datumszeilen sind keine Ämter.
    assert ernte.federfuehrendes_amt("  Ausdruck vom: 24.01.2018\n  Seite: 1/3") is None


def test_federfuehrendes_amt_mehrzeilig_umbrochen():
    text = ("  Ausdruck vom: 22.12.2017\n  20.12.2017\n"
            "Eigenbetrieb Gebäudewirtschaft und\nHochbau\nVorlagen-Nr:\n17/1033\n")
    assert ernte.federfuehrendes_amt(text) == "Eigenbetrieb Gebäudewirtschaft und Hochbau"


def test_sitzungsort():
    text = ("Protokoll über die Sitzung\n\nSitzungsdatum: Donnerstag, den 17.09.2020\n\n"
            "Sitzungsort: Alte Fleiwa, Industriestraße 1d, Sitzungssaal 1/2  \n\nTeilnahme:")
    assert ernte.sitzungsort(text) == "Alte Fleiwa, Industriestraße 1d, Sitzungssaal 1/2"
    assert ernte.sitzungsort("Protokoll ohne Ortsangabe") is None
    # Review-Befund E1: Ein leeres Ort-Feld darf nicht die Folgezeile ernten —
    # der location=''-Guard würde den falschen Wert sonst dauerhaft zementieren.
    assert ernte.sitzungsort("Sitzungsort:\nSitzungsdauer: 17:00 - 19:35 Uhr") is None
    assert ernte.sitzungsort("Sitzungsort:   \nTeilnahme:") is None


def test_blockende_feuert_nicht_mitten_im_satz():
    # Review-Befund E3: „Anlagen" nach PDF-Zeilenumbruch ist KEIN Abschnitts-
    # Header — nur mit Doppelpunkt oder allein auf der Zeile endet der Block.
    text = ("b) Klima\nPrüfungsrelevant: Ja, der Bau von Photovoltaik-\n"
            "Anlagen spart CO2 im Betrieb.\nSachverhalt:\nEgal.")
    assert ernte.auswirkungen(text)["klima"] == (
        "Prüfungsrelevant: Ja, der Bau von Photovoltaik- Anlagen spart CO2 im Betrieb.")
    text2 = ("Beschlussvorschlag:\nDie Prüfung erfolgt gemäß\nAnlage 1 und wird beauftragt.\n"
             "Sachverhalt:\nEgal.")
    assert ernte.proposed_decision(text2) == "Die Prüfung erfolgt gemäß Anlage 1 und wird beauftragt."


def test_beschlussvorschlag_endet_am_sachverhalt():
    v = ernte.proposed_decision(VORLAGE_TEXT)
    assert v == ("Das Vergnügungsstättenkonzept wird beschlossen. "
                 "Die Verwaltung wird mit der Umsetzung beauftragt.")


def test_abweichung_containment_statt_ratio():
    lang = ("Das Vergnügungsstättenkonzept wird in der vorliegenden Fassung beschlossen "
            "und die Verwaltung mit der Umsetzung sowie der jährlichen Berichterstattung "
            "an den Ausschuss für Stadtplanung und Bauen beauftragt.")
    # Der extrahierte Beschluss ist oft nur der Anfang des Vorschlags — reine
    # Kürzung darf nicht als Änderung zählen (die symmetrische Ratio täte das).
    assert ernte.deviation(lang, lang[:80]) == "unchanged"
    assert ernte.deviation(lang, lang) == "unchanged"
    assert ernte.deviation(lang, "Der Tagesordnungspunkt wird auf die nächste Sitzung vertagt.") == "strong"
    assert ernte.deviation(lang, "zu kurz") is None
    assert ernte.deviation(None, lang) is None


def _session(store, ksinr=1):
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
            "VALUES (?, 'Rat', '2026-01-01', '18:00', '', '')", (ksinr,))


PROTOKOLL_TEXT = "Protokoll\nSitzungsort: Kulturzentrum PFL, Peterstraße 3\nTeilnahme:"


def test_save_vorlage_erntet_felder(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    store.save_vorlage({"kvonr": 7, "template_number": "22/0262", "raw_text": VORLAGE_TEXT})
    v = store.get_vorlage(7)
    assert v["office"] == "Stadtplanungsamt"
    assert v["climate_impact"].startswith("Prüfungsrelevant: Ja")
    assert v["financial_impact"].startswith("Kosten von 50.000")
    assert v["proposed_decision"].startswith("Das Vergnügungsstättenkonzept")
    store.close()


def test_save_protocol_setzt_ort_kvonr_und_abweichung(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _session(store)
    store.save_vorlage({"kvonr": 7, "template_number": "22/0262", "raw_text": VORLAGE_TEXT})
    store.save_protocol(
        1, {"document_id": 1, "url": "u"}, {}, PROTOKOLL_TEXT, 1, "m",
        decisions=[{"item_number": "6.1", "title": "Vergnügungsstättenkonzept",
                    "official_text": "Der Tagesordnungspunkt wird auf die nächste Sitzung vertagt, "
                                 "da weiterer Beratungsbedarf besteht.",
                    "outcome": "accepted", "template_number": "22/0262"}],
        attendance=[])
    row = store._conn.execute(
        "SELECT d.kvonr, d.deviation, s.location FROM council_decisions d "
        "JOIN council_sessions s USING (ksinr)").fetchone()
    assert row["kvonr"] == 7                      # über die Vorlagen-Nr. verknüpft
    assert row["deviation"] == "strong"           # Vertagung ≠ Beschlussvorschlag
    assert row["location"] == "Kulturzentrum PFL, Peterstraße 3"
    store.close()


def test_vorlage_nach_protokoll_zieht_abweichung_nach(tmp_path):
    # check_protocols lädt Vorlagen-Volltexte NACH dem Protokoll-Import — die
    # Abweichung muss dann vom save_vorlage-Pfad nachgezogen werden.
    store = CouncilStore(tmp_path / "c.sqlite")
    _session(store)
    store.save_protocol(
        1, {"document_id": 1, "url": "u"}, {}, PROTOKOLL_TEXT, 1, "m",
        decisions=[{"item_number": "6.1", "title": "Vergnügungsstättenkonzept",
                    "official_text": "Das Vergnügungsstättenkonzept wird beschlossen. "
                                 "Die Verwaltung wird mit der Umsetzung beauftragt.",
                    "outcome": "accepted", "template_number": "22/0262"}],
        attendance=[])
    assert store._conn.execute("SELECT deviation FROM council_decisions").fetchone()[0] is None
    store.save_vorlage({"kvonr": 7, "template_number": "22/0262", "raw_text": VORLAGE_TEXT})
    assert store._conn.execute("SELECT deviation FROM council_decisions").fetchone()[0] == "unchanged"
    store.close()


def test_qa_kontext_traegt_ernte_felder(tmp_path):
    from council import qa

    ctx = qa._build_context([{
        "id": 5, "title": "Konzept", "committee": "Rat", "session_date": "2026-01-01",
        "outcome": "accepted", "official_text": "Wird beschlossen.",
        "office": "Stadtplanungsamt",
        "climate_impact": "Prüfungsrelevant: Ja, steuert den Verkehr.",
        "deviation": "strong",
    }])
    assert "Federführung: Stadtplanungsamt" in ctx
    assert "Klima-Check der Verwaltung: Prüfungsrelevant: Ja" in ctx
    assert "wich deutlich vom Beschlussvorschlag" in ctx
    # „Nein"-Vermerke bleiben draußen — sie helfen keiner Antwort.
    ctx2 = qa._build_context([{
        "id": 6, "title": "Bericht", "committee": "Rat", "session_date": "2026-01-01",
        "outcome": "accepted", "official_text": "Kenntnis.",
        "climate_impact": "Nein, nicht prüfungsrelevant.", "deviation": "unchanged",
    }])
    assert "Klima-Check" not in ctx2 and "Beschlussvorschlag" not in ctx2
