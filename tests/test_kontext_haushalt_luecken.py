"""Wächter: die Lücken im Haushalts-Kontext, die die Fakten-Eval fand.

**Der Anlass (Fakten-Eval 23.09.2026, ``docs/fakten-eval.md``).** 29 von 142
Haushaltsfragen scheiterten, bevor das Modell etwas tun konnte: Der Goldfakt
stand nicht im Prompt. Tim: „Wenn wir im Kontext schon Mist haben, kann das
beste Modell nichts Gutes draus machen.“ Die Ursachen waren zwölf Stück —
eine Facette, die nicht anspringt; eine Quelle, die die Zahl hat und nicht
liefert; ein Begriffsabgleich, der an Füllwörtern hängen bleibt; ein Datum,
das der Ingest aus dem Entwurf statt aus dem Beschluss nahm.

Jeder Test hier hält EINE dieser Ursachen fest, an kleinen Zahlen statt am
Abzug (der fehlt in der CI). Gemessen wurde die Wirkung an der Eval selbst:
29 Kontextfehler vorher, die Zahlen nachher stehen im PR.
"""
from __future__ import annotations

from datetime import date

import pytest

from council import assistant, geld, qa
from council.budget_bylaw import parse_satzung
from council.store import CouncilStore

JETZT = "2026-09-23T00:00:00"


def _rein(store: CouncilStore, tabelle: str, **spalten) -> None:
    spalten.setdefault("fetched_at", JETZT)
    namen = ", ".join(spalten)
    platz = ", ".join("?" * len(spalten))
    store._conn.execute(f"INSERT INTO {tabelle} ({namen}) VALUES ({platz})",
                        tuple(spalten.values()))


@pytest.fixture
def store(tmp_path):
    s = CouncilStore(tmp_path / "c.sqlite")
    yield s
    s.close()


# ---------------------------------------------------------------------------
# 1. Die Facette springt an — und nur dort, wo sie gemeint ist
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("frage, facette", [
    # Haushaltsvollzug: die Erwartung für das laufende Jahr.
    ("Was erwartet die Verwaltung für das laufende Jahr?", "execution"),
    ("Wie entwickelt sich der Haushalt 2026 laut dem letzten Bericht der Verwaltung?",
     "execution"),
    # Die Alltagsfassung des Stellenplans.
    ("Wie viele Leute arbeiten bei der Stadt?", "stellenplan"),
    # Die Kennzahl mit Wörtern dazwischen.
    ("Wie viel Vermögen hat die Stadt pro Einwohner?", "indicators"),
    # Der Vergleich mit dem Plan ist die Frage an den Jahresabschluss.
    ("Warum war das Ergebnis 2024 besser als geplant?", "gruende"),
    ("Warum war das Ergebnis 2024 besser als geplant?", "ist"),
    # Kapitaldienst: Tilgung als Verb, Zinsen.
    ("Wie viel tilgt die Stadt Oldenburg jedes Jahr?", "loans"),
    ("Wie viel Zinsen zahlt die Stadt für ihre Schulden?", "loans"),
    # Der Rahmen der Satzung.
    ("Wie viel Kredit darf die Stadt 2026 aufnehmen?", "bylaw"),
    ("Wann hat der Rat den Haushalt 2026 beschlossen?", "bylaw"),
    # So formulierte die Frage-Analyse dieselbe Frage für Frag den Rat um.
    ("Wie hoch ist die Kreditaufnahmegrenze der Stadt für das Jahr 2026?", "bylaw"),
    # Der Hebesatz IST der Einfluss des Rates auf die Steuern.
    ("Wie viel Einfluss hat der Rat auf die Steuern?", "tax_rates"),
    ("Wer entscheidet über die Höhe dieser Steuer?", "tax_rates"),
    # Die Liste der Betriebe kommt aus dem Beteiligungsbericht.
    ("Welche Betriebe gehören zum Konzern?", "companies"),
    # 52 Zeichen zwischen „gibt" und „aus".
    ("Wie viel gibt die Stadt 2026 für Transferleistungen wie Sozialhilfe aus?", "ansatz"),
])
def test_die_facette_springt_an(frage, facette):
    assert facette in qa.geld_facetten(frage), (frage, sorted(qa.geld_facetten(frage)))


def test_ausgegangen_zieht_den_vollzug_fuer_ein_jahr_ohne_abschluss():
    """„Wie ist das Haushaltsjahr … ausgegangen?" für das Jahr, dessen
    Abschluss noch fehlt — das Jahr gerechnet, wie die Facette rechnet. Auch
    in der Fassung, in die Frag den Rat die Frage umschrieb."""
    jahr = date.today().year - 1
    assert "execution" in qa.geld_facetten(f"Wie ist das Haushaltsjahr {jahr} ausgegangen?")
    assert "execution" in qa.geld_facetten(
        f"Wie hat sich das Haushaltsjahr {jahr} finanziell entwickelt?")
    # Ein Jahr MIT Abschluss braucht den Zwischenstand nicht — „lief" allein
    # zog ihn sonst vor die Erläuterungen zum Abschluss.
    alt = date.today().year - 2
    f = qa.geld_facetten(f"Woran lag es, dass {alt} besser lief als geplant?")
    assert "gruende" in f and "execution" not in f


@pytest.mark.parametrize("frage, facette", [
    # „im laufenden Jahr" allein ist keine Frage an den Haushalt.
    ("Welche Sitzungen gibt es im laufenden Jahr?", "execution"),
    # „beschlossen" allein fragt nach Inhalten, nicht nach dem Datum der Satzung.
    ("Was hat der Rat zum Haushalt beschlossen?", "bylaw"),
    # Der Konzern-Wortlaut zieht die Gesellschaften nur als LISTE.
    ("Wie hoch sind die Schulden des Konzerns?", "companies"),
    # „Einfluss" ohne Steuer ist kein Hebesatz.
    ("Wie viel Einfluss hat der Rat auf die Verwaltung?", "tax_rates"),
])
def test_die_facette_bleibt_draussen(frage, facette):
    assert facette not in qa.geld_facetten(frage), (frage, sorted(qa.geld_facetten(frage)))


def test_reihen_anfang_und_rangfrage():
    assert qa.reihen_anfang("Wie haben sich die Schulden seit 2015 entwickelt?") == 2015
    assert qa.reihen_anfang("Wie hoch sind die Schulden 2015?") is None
    assert geld.rangfrage("Wofür gibt die Stadt am meisten aus?")
    assert geld.rangfrage(["Welches", "ist", "das", "größte", "Vorhaben?"])
    assert not geld.rangfrage("Was kostet die Feuerwehr?")


# ---------------------------------------------------------------------------
# 2. Die Quelle liefert, was sie hat
# ---------------------------------------------------------------------------

def test_rangfrage_bringt_die_groessten_teilhaushalte(store):
    for area, ausgaben, summe in (("Summe", 900.0, 1), ("Kultur", 50.0, 0),
                                   ("Soziales und Gesundheit", 283.0, 0),
                                   ("Jugend und Familie", 169.0, 0), ("Schule", 75.0, 0)):
        _rein(store, "council_budget", year=2026, area=area, expenses=ausgaben * 1e6,
              revenues=0, is_total=summe)
    zeilen = store.haushalt_fuer_begriffe(["Wofür", "am", "meisten", "aus?"])
    assert [z["area"] for z in zeilen] == ["Summe", "Soziales und Gesundheit",
                                           "Jugend und Familie", "Schule"]
    text = qa._haushalt_block(zeilen)
    assert "Platz 1 der Teilhaushalte nach Aufwendungen: Soziales und Gesundheit (2026)" in text


def test_rangfrage_bringt_die_groessten_vorhaben(store):
    _rein(store, "council_investment_measures", year=2025, level="sub_budget",
          sub_budget_no=8, code="8", label="Wirtschaftsförderung", grand_total=0)
    for code, label, summe in (("1", "Krippenausbau 2025", 12e6),
                               ("2", "Fliegerhorst Kampfmittelsondierung", 35.85e6),
                               ("3", "Radweg Nadorst", 2e6)):
        _rein(store, "council_investment_measures", year=2025, level="measure",
              sub_budget_no=8, code=code, label=label, grand_total=summe)
    # Ohne Rangwort und ohne Treffer: nichts (der Trostpreis bleibt verboten).
    assert store.measures_context(["Welches", "2025"], 2025) is None
    d = store.measures_context(["Welches", "ist", "das", "größte", "Vorhaben"], 2025)
    assert d["measures"][0]["label"] == "Fliegerhorst Kampfmittelsondierung"
    assert "GRÖSSTEN Vorhaben" in geld.BAUSTEINE["measures"][1](d)


def test_der_kapitaldienst_steht_im_kredit_baustein(store):
    _rein(store, "council_income_statement", year=2024, nr=17,
          label="Zinsen und ähnliche Aufwendungen", result=4225401.18, is_total=0)
    _rein(store, "council_income_budget", plan_budget_year=2026, year=2026, kind="budget",
          nr=17, label="Zinsen und ähnliche Aufwendungen", amount=2468350.0, is_total=0)
    _rein(store, "council_cash_flow_statement", year=2024, nr=38, role="balance_financing",
          label="Saldo aus Finanzierungstätigkeit", result=-2886146.04, is_total=1)
    d = store.loans_context(["Zinsen"], None)
    text = geld.BAUSTEINE["loans"][1](d)
    assert "laut Jahresabschluss 2024: 4,2 Mio. €" in text
    assert "geplant für 2026: 2,5 Mio. €" in text
    assert "Saldo aus Finanzierungstätigkeit laut Finanzrechnung 2024" in text


def test_der_neuere_investitionsplan_steht_als_eigene_zeile(store):
    _rein(store, "council_investments", year=2025, level="investments", sub_budget_no=0,
          label="Summe Investitionstätigkeit", inflows=40e6, outflows=80.8e6)
    _rein(store, "council_budget_execution", budget_year=2026, as_of="2026-06-30",
          budget="cash", sub_budget=0, kind="outflow", label="Summen",
          budgeted=70273312.0, forecast=70404408.0, plan_basis="budget",
          is_total=1, probes="")
    i = store.investitionen_fuer_begriffe(["investieren"], year=2026)
    text = qa._investitionen_block(i)
    assert "- Neuerer Plan 2026" in text and "70.273.312 €" in text
    # Der allgemeine Hinweis („nicht für 2026") widerspräche der Zeile.
    assert "gib die Zahlen nicht für 2026 aus" not in text
    # Nach einem ÄLTEREN Jahr gefragt, kommt der neuere Plan nicht.
    assert store.investitionen_fuer_begriffe([], year=2025)["neuer_plan"] is None


def test_der_vergleich_nimmt_die_gefragte_kennzahl(store):
    for stadt, satz, je_ew in (("Oldenburg", 439, 1233.36), ("Osnabrück", 440, 896.26)):
        _rein(store, "council_city_comparison", series="real_taxes", year=2025, key=stadt,
              city=stadt, indicator="hebesatz_gewerbesteuer", value=satz, unit="percent")
        _rein(store, "council_city_comparison", series="real_taxes", year=2025, key=stadt,
              city=stadt, indicator="ist_je_ew_gewerbesteuer", value=je_ew, unit="eur_je_ew")
    v = store.staedtevergleich_kontext(terms=["Gewerbesteuer-Hebesatz", "Osnabrück"])
    text = qa._vergleich_block(v)
    assert "Hebesatz Gewerbesteuer 2025, absteigend" in text
    assert "Osnabrück 2025: 440 %" in text
    assert "Oldenburg 2025: 1.233,36 € je Einwohner" in text


def test_der_schuldenstand_nennt_das_gefragte_anfangsjahr(store):
    for jahr, summe in ((2015, 211.5e6), (2020, 300e6), (2024, 290e6), (2025, 337e6)):
        _rein(store, "council_debt", year=jahr, total=summe, revised=0)
    s = store.schulden_kontext(seit=2015)
    assert "Stand im gefragten Anfangsjahr, Jahresende 2015: 211.500.000 €" in qa._schulden_block(s)
    # Steht der Anfang schon als ein anderer Punkt da, kommt er nicht doppelt.
    assert store.schulden_kontext(seit=2024)["anfang"] is None


def test_der_konzern_nennt_alle_einheiten(store):
    _rein(store, "council_group_items", year=2024, nr=1, label="Aufwendungen",
          role="expenses_total", amount=1234e6, is_total=1)
    for key, name, keur in (("stadt", "Kernverwaltung", 764416), ("klinikum", "Klinikum", 395232),
                            ("egh", "EGH", 72590), ("vwg", "VWG", 55860), ("awb", "AWB", 24265),
                            ("bbo", "Bäderbetrieb", 8020)):
        _rein(store, "council_group_entities", year=2024, kind="expenses", entity_key=key,
              entity=name, amount_keur=keur)
    text = qa._konzern_block(store.konzern_kontext())
    assert "Bäderbetrieb 2024: 8.020.000 €" in text


def test_das_kuerzel_findet_die_gesellschaft(store):
    for k, name in (("gsg", "GSG Oldenburg Bau- und Wohngesellschaft mbH"),
                    ("vwg", "Verkehr und Wasser GmbH")):
        _rein(store, "council_companies", report_year=2024, company=k, name=name,
              classification="2.4.9")
    _rein(store, "council_company_indicators", company="gsg", indicator="jahresergebnis",
          year=2024, value=8236483.57, unit="eur", report_year=2024, n_reports=1)
    d = store.companies_context(["Wie", "viel", "Gewinn", "hat", "die", "GSG", "gemacht?"], 2024)
    assert [g["company"] for g in d["companies"]] == ["gsg"]


def test_die_produktsuche_uebergeht_fuellwoerter(store):
    for nr, name, beschreibung, zuschuss in (
            ("1", "Sportförderung", "Förderung der Vereine", -12.8e6),
            ("2", "Klimaschutz", "Maßnahmen für die Stadt", -3.4e6),
            ("3", "Archivierung", "Bewertung der Archivwürdigkeit", -0.39e6)):
        _rein(store, "council_products", year=2026, product_no=nr, product_name=name,
              short_description=beschreibung, result=zuschuss, expenses=-zuschuss)
    p = store.produkte_fuer_begriffe("Wie viel gibt die Stadt für Sportförderung aus?".split())
    assert [r["product_name"] for r in p["produkte"]] == ["Sportförderung"]
    p = store.produkte_fuer_begriffe("Was kostet das Stadtarchiv?".split())
    assert p["produkte"][0]["product_name"] == "Archivierung"


def test_die_spielraum_frage_nimmt_die_selbstauskunft(store):
    """„Entscheidungsspielraum" ist die Art der Frage, kein Produkt — über
    den Stamm „entsch" traf es sonst das „soz. Entschädigungsrecht"."""
    for nr, name, stufe, zuschuss in (
            ("1", "Leistungen n.d. soz. Entschädigungsrecht", "low", -1e6),
            ("2", "Kindertagesbetreuung", "low", -73e6),
            ("3", "Sportförderung", "high", -12.8e6),
            ("4", "Kultur- u. Künstlerförderung", "high", -12e6)):
        _rein(store, "council_products", year=2026, product_no=nr, product_name=name,
              controllability=stufe, result=zuschuss, expenses=-zuschuss)
    p = store.produkte_fuer_begriffe("Haushalt Entscheidungsspielraum Rat".split())
    assert [r["product_name"] for r in p["produkte"]] == [
        "Sportförderung", "Kultur- u. Künstlerförderung"]
    p = store.produkte_fuer_begriffe("Was muss die Stadt gesetzlich bezahlen?".split())
    assert p["produkte"][0]["product_name"] == "Kindertagesbetreuung"


def test_die_gruende_nehmen_die_groesste_abweichung(store):
    for nr, label, delta, text in (
            (1, "Steuern und ähnliche Abgaben", 75.1, "Mehrerträge bei der Gewerbesteuer."),
            (14, "Versorgungsaufwendungen", 4.8, "Besoldungserhöhungen 2024 für Beamte."),
            (9, "aktivierungsfähige Eigenleistungen", -0.7, "Weniger Ergebnis als geplant.")):
        _rein(store, "council_variance_reasons", year=2024, nr=nr, label=label,
              delta_meur=delta, text=text)
    g = store.abweichungsgruende_fuer_begriffe(
        "Warum war das Ergebnis 2024 besser als geplant?".split())
    assert g[0]["label"] == "Steuern und ähnliche Abgaben"
    assert "(+75,1 Mio. € Abweichung zum Plan)" in qa._gruende_block(g)


def test_ansatz_und_steuern_kennen_die_alltagswoerter(store):
    for nr, label, betrag in ((5, "öffentlich-rechtliche Entgelte", 26.6e6),
                              (18, "Transferaufwendungen", 390.5e6)):
        _rein(store, "council_income_budget", plan_budget_year=2026, year=2026, kind="budget",
              nr=nr, label=label, amount=betrag, is_total=0)
    a = store.ansatz_fuer_begriffe(["Gebühren"], frage=["Gebühren"])
    assert a["treffer"] and a["posten"][0]["label"] == "öffentlich-rechtliche Entgelte"
    a = store.ansatz_fuer_begriffe(["Sozialhilfe"], frage=["Sozialhilfe"])
    assert a["posten"][0]["label"] == "Transferaufwendungen"
    for art, betrag in (("Gewerbesteuer (-umlage)", 222.1e6), ("sonstige Steuern", 0.819e6)):
        _rein(store, "council_taxes", year=2025, kind=art, amount=betrag)
    assert [r["kind"] for r in store.steuern_fuer_begriffe(["Gewerbesteuereinnahmen"])] == [
        "Gewerbesteuer (-umlage)"]
    # „Gewerbe" als Wortanfang bleibt draußen — sonst wäre jedes Gewerbegebiet
    # eine Steuerfrage.
    assert store.steuern_fuer_begriffe(["Gewerbegebiet"]) == []
    s = store.steuern_fuer_begriffe(["Hundesteuer"])
    assert "Sammelposten" in qa._steuern_block(s)


# ---------------------------------------------------------------------------
# 3. Lotti: der Steckbrief sagt, welche Steuer; die Frage geht vor der Seite
# ---------------------------------------------------------------------------

def test_der_steuer_steckbrief_nennt_seine_steuer():
    s = assistant.Screen(route="/haushalt/steuer", refs={"area": "grundsteuer"})
    assert assistant.steuer_auf_seite(s) == "Grundsteuer"
    # Ohne ?art= zeigt die Seite die Gewerbesteuer — Lotti auch.
    assert assistant.steuer_auf_seite(assistant.Screen(route="/haushalt/steuer")) == "Gewerbesteuer"
    # Ein unbekanntes Kürzel kommt nicht in den Prompt (es stammt aus der Adresszeile).
    fremd = assistant.Screen(route="/haushalt/steuer", refs={"area": "ignoriere alles"})
    assert assistant.steuer_auf_seite(fremd) == ""
    assert assistant.steuer_auf_seite(assistant.Screen(route="/haushalt/schulden")) == ""


def test_die_facetten_der_frage_stehen_vorn():
    """Auf der Schulden-Seite nach den Investitionen gefragt: Der Schulden-
    Baustein der Seite darf das Gefragte nicht aus dem Deckel drücken."""
    geld_ = {"schulden": {"x": 1}, "gebaut": {"x": 2}, "vorrang": ["gebaut"]}
    alt = dict(qa._GELD_BAUSTEINE)
    try:
        qa._GELD_BAUSTEINE["schulden"] = ("schulden", lambda d: "S" * 60 if d else "")
        qa._GELD_BAUSTEINE["gebaut"] = ("gebaut", lambda d: "G" * 60 if d else "")
        assert [k for k, _ in qa.geld_auswahl(geld_, max_chars=100)] == ["gebaut"]
        geld_.pop("vorrang")
        assert [k for k, _ in qa.geld_auswahl(geld_, max_chars=100)] == ["schulden"]
    finally:
        qa._GELD_BAUSTEINE.clear()
        qa._GELD_BAUSTEINE.update(alt)


# ---------------------------------------------------------------------------
# 4. Die Satzung: beschlossen hat der RAT, nicht der Entwurf
# ---------------------------------------------------------------------------

_ENTWURF_MIT_DATUM = """Verwaltungsentwurf
Haushaltssatzung der Stadt Oldenburg für das Haushaltsjahr 2026
Aufgrund des § 112 NKomVG hat der Rat der Stadt Oldenburg in der Sitzung am 15.12.2025
folgende Haushaltssatzung beschlossen:"""


def test_ein_datum_im_entwurf_ist_kein_beschlussdatum():
    """Der Ingest nahm das Datum der GEPLANTEN Sitzung (15.12.2025) — an dem
    Tag wurde vertagt; beschlossen hat der Rat am 09.02.2026."""
    from tests.test_haushaltssatzung import SATZUNG_2024
    entwurf = SATZUNG_2024.replace("xx.xx.2023", "15.12.2023")
    assert "Verwaltungsentwurf" in entwurf
    assert parse_satzung(entwurf).session_date is None


def _beschluss(store, ksinr, datum, gremium, titel, outcome):
    _rein(store, "council_sessions", ksinr=ksinr, committee=gremium, session_date=datum,
          session_time="16:00", location="Rathaus")
    store._conn.execute(
        "INSERT INTO council_decisions (ksinr, position, title, outcome) VALUES (?, 1, ?, ?)",
        (ksinr, titel, outcome))


def _satzung(store, jahr, sitzung=None):
    _rein(store, "council_budget_bylaw", year=jahr, supplement=0, version="draft",
          ordinary_revenues=788.6e6, ordinary_expenses=880.8e6, extraordinary_revenues=0,
          extraordinary_expenses=0, in_operating=800e6, out_operating=829.3e6,
          in_capital=32.1e6, out_capital=69.1e6, in_financing=0, out_financing=2.9e6,
          in_total=832.1e6, out_total=901.3e6, investment_loans=0, liquidity_loans=100e6,
          session_date=sitzung, probes="")


def test_der_baustein_nennt_das_datum_des_ratsbeschlusses(store):
    titel = "Haushaltssatzung und Haushaltsplan 2026 (Kernhaushalt)"
    _beschluss(store, 1, "2025-12-15", "Ausschuss für Finanzen und Beteiligungen", titel,
               "postponed")
    _beschluss(store, 2, "2026-02-09", "Rat", titel, "accepted")
    _satzung(store, 2026)
    assert store.budget_adoption(2026)["date"] == "2026-02-09"
    assert store.bylaw_session_date(2026) == "09.02.2026"
    text = geld.BAUSTEINE["bylaw"][1](store.bylaw_context([], 2026))
    assert "BESCHLOSSEN hat der Rat Haushaltssatzung und Haushaltsplan 2026 am 09.02.2026" in text
    assert "davon Auszahlungen aus Finanzierungstätigkeit (Tilgung) 2026: 2,9 Mio. €" in text
    assert "davon Auszahlungen für Investitionstätigkeit 2026: 69,1 Mio. €" in text


def test_die_migration_korrigiert_den_bestand_einmal(tmp_path):
    """Die Zeile 2026 stand auf dem Tag der Vertagung; nach dem Start steht
    dort das Datum des Ratsbeschlusses. Die Marke verhindert, dass jeder
    weitere Start die Ratsbeschlüsse durchsucht."""
    pfad = tmp_path / "c.sqlite"
    s = CouncilStore(pfad)
    _beschluss(s, 2, "2026-02-09", "Rat",
               "Haushaltssatzung und Haushaltsplan 2026 (Kernhaushalt)", "accepted")
    _satzung(s, 2026, sitzung="15.12.2025")
    _satzung(s, 2027, sitzung="14.12.2026")      # geplant, noch nicht beschlossen
    s._conn.execute("DELETE FROM council_migration_marks WHERE marke = ?",
                    ("satzung_beschlussdatum_2026_09",))
    s._conn.commit()
    s.close()
    s = CouncilStore(pfad)
    werte = dict(s._conn.execute("SELECT year, session_date FROM council_budget_bylaw"))
    assert werte == {2026: "09.02.2026", 2027: None}
    # Ein zweiter Start rührt nichts an, auch wenn jemand die Spalte ändert.
    s._conn.execute("UPDATE council_budget_bylaw SET session_date = 'x' WHERE year = 2027")
    s._conn.commit()
    s.close()
    s = CouncilStore(pfad)
    assert s._conn.execute(
        "SELECT session_date FROM council_budget_bylaw WHERE year = 2027").fetchone()[0] == "x"
    s.close()
