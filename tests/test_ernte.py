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


# Vorlagen bis 2021: „Finanzielle Auswirkungen:" als eigene Überschrift statt
# „a) Finanzen", und der Block endet an der Grußformel, nicht an einem Header.
VORLAGE_ALT_TEXT = """\
Stadtplanungsamt Vorlagen-Nr:
19/0815

Beschlussvorschlag:
Der Bebauungsplan wird als Satzung beschlossen.

Sachverhalt:
Es begab sich aber zu der Zeit.

Finanzielle Auswirkungen:

Es entstehen Verfahrenskosten in üblicher Höhe, die der GSG zu 50 % über den
städtebaulichen Vertrag auferlegt werden.

In Vertretung

G a b r i e l e  N i e \u00df e n

Anlagen:
Lageplan
"""


def test_finanzen_aus_der_alten_ueberschrift():
    # 2797 der 5079 Vorlagen im Bestand tragen diese Form; ohne sie blieb die
    # Karte „Was kostet das?" auf gut der Hälfte des Bestands leer.
    aus = ernte.auswirkungen(VORLAGE_ALT_TEXT)
    assert aus["finanzen"] == (
        "Es entstehen Verfahrenskosten in üblicher Höhe, die der GSG zu 50 % "
        "über den städtebaulichen Vertrag auferlegt werden.")
    # Kein „b) Klima" in der alten Form — und der Beschlussvorschlag bleibt heil.
    assert aus["klima"] is None
    assert ernte.proposed_decision(VORLAGE_ALT_TEXT) == (
        "Der Bebauungsplan wird als Satzung beschlossen.")


def test_grussformel_und_unterschrift_beenden_den_block():
    """Ohne diese Endmarker zog der Block die Unterschrift mit — und eine
    Floskel („keine") war damit keine Floskel mehr, sondern ging als echte
    Kostenangabe durch. Gemessen: 45 Klima-Blöcke der Form „./. In Vertretung
    J a n B e m b e n n e k" verschwinden dadurch aus dem Bestand."""
    for schluss in ("In Vertretung\nJ ü r g e n  K r o g m a n n",
                    "Im  Auftrag\nW i e b k e  O n c k e n",   # PDF liefert zwei Leerzeichen
                    "J ü r g e n  K r o g m a n n"):
        text = "Finanzielle Auswirkungen:\nkeine\n\n" + schluss + "\n"
        assert ernte.auswirkungen(text)["finanzen"] is None, schluss
        text2 = "b) Klima\nDer Bau spart CO2 im Betrieb.\n\n" + schluss + "\n"
        assert ernte.auswirkungen(text2)["klima"] == "Der Bau spart CO2 im Betrieb.", schluss


def test_finanzblock_endet_am_klimarelevanz_header():
    # Die alte Form kennt „Klimarelevante Auswirkungen:" als Folgeabschnitt;
    # ohne ihn als Endmarker lief der Finanz-Block („keine") dort hinein.
    text = ("Finanzielle Auswirkungen:\nkeine\n\nKlimarelevante Auswirkungen:  \n"
            "Positive Auswirkungen: Mehr Transparenz.\n")
    assert ernte.auswirkungen(text)["finanzen"] is None


def test_gesperrte_unterschrift_kappt_keine_prosa():
    # Der Marker verlangt mindestens fünf EINZELNE Buchstaben in Folge — eine
    # normale Zeile aus kurzen Wörtern darf ihn nicht auslösen.
    text = ("b) Klima\nDie Stadt hat es zu tun und es ist gut so.\n"
            "Der Bau ist ja so wie er ist.\nSachverhalt:\nEgal.")
    assert ernte.auswirkungen(text)["klima"] == (
        "Die Stadt hat es zu tun und es ist gut so. Der Bau ist ja so wie er ist.")


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


# --- Backfill über den Bestand (scripts/ernte_backfill.py) -------------------

def _backfill():
    """Das Ops-Skript laden, ohne ``scripts`` zu einem Paket zu machen."""
    import importlib.util
    from pathlib import Path

    pfad = Path(__file__).resolve().parents[1] / "scripts" / "ernte_backfill.py"
    spec = importlib.util.spec_from_file_location("ernte_backfill", pfad)
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_backfill_holt_den_bestand_nach_und_ist_idempotent(tmp_path):
    """Der eigentliche Befund vom 08.09.2026: Die Ernte lief nur beim Scrapen,
    also trug der Bestand die Felder nicht — 95 von 5079 Vorlagen hatten ein
    Amt, obwohl die Regex 5069 davon trifft. Der zweite Lauf muss ``geaendert``
    auf 0 melden, sonst schreibt der Wochenlauf jede Woche 5000 Zeilen um."""
    db = tmp_path / "c.sqlite"
    store = CouncilStore(db)
    store.save_vorlage({"kvonr": 7, "template_number": "22/0262", "raw_text": VORLAGE_TEXT})
    store.save_vorlage({"kvonr": 8, "template_number": "19/0815", "raw_text": VORLAGE_ALT_TEXT})
    # Den Bestand von vor der Ernte nachstellen: Spalten leer, Rohtext da.
    with store._conn:
        store._conn.execute("UPDATE council_templates SET office = NULL, "
                            "climate_impact = NULL, financial_impact = NULL, "
                            "proposed_decision = NULL")
    store.close()

    backfill = _backfill()
    trocken = backfill.main(db=str(db), trocken=True)
    assert trocken["geaendert"] == 2 and trocken["finanzen"] == 2
    # Trocken heißt trocken — und eine ungerechnete Abweichung wird nicht als 0
    # gemeldet, das läse sich wie „keine einzige".
    assert "deviation" not in trocken
    store = CouncilStore(db)
    assert store.get_vorlage(7)["office"] is None
    store.close()

    erster = backfill.main(db=str(db))
    assert erster["geaendert"] == 2
    assert erster["office"] == 2 and erster["finanzen"] == 2 and erster["vorschlag"] == 2

    store = CouncilStore(db)
    assert store.get_vorlage(7)["office"] == "Stadtplanungsamt"
    assert store.get_vorlage(8)["financial_impact"].startswith("Es entstehen Verfahrenskosten")
    store.close()

    zweiter = backfill.main(db=str(db))
    assert zweiter["geaendert"] == 0, "zweiter Lauf darf nichts mehr umschreiben"
    assert zweiter["vorlagen"] == 2


def test_backfill_ist_ein_schritt_von_weekly_enrich():
    """Ein Backfill, den niemand wieder aufruft, läuft genau einmal — und jede
    spätere Verbesserung an ``council/ernte.py`` erreicht den Bestand dann nie.
    Genau so kam es zu 64 gefüllten ``financial_impact`` bei 5079 Vorlagen."""
    import ast
    from pathlib import Path

    quelle = (Path(__file__).resolve().parents[1] / "scripts" / "weekly_enrich.py").read_text()
    schritte = [e.elts[1].value for n in ast.walk(ast.parse(quelle))
                if isinstance(n, ast.AnnAssign) and getattr(n.target, "id", "") == "STEPS"
                for e in n.value.elts]
    assert "ernte_backfill.py" in schritte
    # Vor den LLM-Schritten: billig, ohne Netz, und alles Spätere sieht frische
    # Felder (``supplementary_approvals`` liest ``proposed_decision``).
    assert schritte.index("ernte_backfill.py") == 0
