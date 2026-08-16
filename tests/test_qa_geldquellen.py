"""Welche Haushalts-Quelle zieht welche Frage? — der Messkorpus.

Tims Auftrag im Wortlaut: „bitte auch mit Tests ob die richtigen APIs auch bei
den entsprechenden Fragen angesprochen werden, auch gucken wie genau die Frage
formuliert sein muss damit die richtigen Daten dazugeholt werden."

Gemessen wird deshalb nicht, ob eine Antwort plausibel klingt, sondern welche
**Store-Methoden** eine Frage tatsächlich aufruft. Der Korpus unten ist die
Messtabelle; ``_MessStore`` protokolliert jeden Zugriff, und die
Formulierungs-Varianten prüfen, wie robust die Erkennung gegen Umformulierung
ist.

OHNE LLM-CALL. Die Suite läuft in der CI ohne API-Schlüssel (conftest.py killt
ihn bewusst), und der Fragetyp ist hier deshalb ein *Eingabewert*, kein
Messwert: ``geld_facetten`` ist genau deshalb deterministisch am Fragewortlaut
gebaut. Die Klassifikation selbst — sagt das Analyse-Modell zu „Was kostet die
Feuerwehr?" wirklich ``geld``? — prüft der manuell startbare Lauf am Dateiende::

    OPENROUTER_API_KEY=… .venv/bin/python tests/test_qa_geldquellen.py

Er ist bewusst KEIN Test: ein LLM-Call gehört nicht in eine Suite, die bei
jedem Push läuft.
"""
import pytest

from council import qa
from council.store import CouncilStore


# ---------------------------------------------------------------------------
# Der Korpus
# ---------------------------------------------------------------------------
# Je Fall: Frage, Fragetyp (wie ihn die LLM-Analyse liefern würde) und die
# Quellen, die geladen werden SOLLEN. Die Namen sind die Facetten aus
# ``qa.GELD_FACETTEN``; welche Store-Methode dahintersteht, steht in
# ``ERWARTETE_METHODEN`` weiter unten — und wird mitgeprüft, damit eine
# umbenannte Methode hier auffliegt statt still nichts mehr zu laden.

KORPUS: list[tuple[str, str, set[str]]] = [
    # --- Tims sechs Pflichtfragen ------------------------------------------
    # „Was kostet X?" ist die Frage der Produktebene: dort steht eine Aufgabe
    # mit ihren Kosten. Der Teilhaushalt (plan) trägt die grobe Summe dazu.
    ("Was kostet die Feuerwehr?", "geld", {"plan", "produkte"}),
    # Plan gegen Ist — das kann NUR der Jahresabschluss beantworten.
    ("Hat die Stadt 2024 mehr ausgegeben als geplant?", "geld", {"plan", "ist"}),
    # Das „Warum" steht in den Erläuterungen; die Steuer-Ist-Zahlen und der
    # NFAG-Dämpfer gehören dazu, sonst klingt jede Mehreinnahme nach Gewinn.
    ("Warum kam so viel mehr Gewerbesteuer rein?", "geld",
     {"gruende", "ist", "steuern", "ausgleich"}),
    # Präzise und allein: eine Prüfbericht-Frage will keinen Haushaltsplan.
    ("Was hat das Rechnungsprüfungsamt beanstandet?", "thema", {"pruefung"}),
    # „Insgesamt" ist das Stichwort für den Konzern: der Kernhaushalt
    # antwortet mit 799 Mio., der Gesamtabschluss mit 1.242 Mio.
    ("Was kostet die Stadt insgesamt?", "geld", {"plan", "produkte", "konzern"}),
    # Keine Betragsfrage — eine Rechtsfrage. Nur die Produktebene führt die
    # Auftragsgrundlage je Aufgabe.
    ("Muss die Stadt das Theater betreiben?", "thema", {"produkte"}),

    # --- Weitere echte Fragen ----------------------------------------------
    ("Wie viel gibt Oldenburg für Soziales aus?", "geld", {"plan", "produkte"}),
    ("Wie hoch ist der Hebesatz der Grundsteuer?", "geld", {"steuern", "ausgleich"}),
    ("Wie steht Oldenburg im Vergleich zu Osnabrück da?", "geld", {"vergleich"}),
    ("Welche Aufgaben könnte die Stadt streichen?", "thema", {"produkte"}),
    # „Steuereinnahmen" trägt „einnahm" und zieht damit auch die Plan-Seite —
    # gewollt: Die Antwort kann Ist und Ansatz nebeneinanderstellen.
    ("Wie hoch waren die Steuereinnahmen?", "geld",
     {"plan", "ansatz", "steuern", "ausgleich"}),

    # --- Negativfälle -------------------------------------------------------
    # Ohne diese Zeilen optimiert man auf „lädt immer alles" und überflutet
    # den Kontext. Jede Frage hier muss GAR KEINE Haushaltsquelle ziehen.
    ("Wie ist der Stand beim Stadion?", "verlauf", set()),
    ("Was wurde zum Stadion beschlossen?", "thema", set()),
    ("Wer stimmte gegen den Stadionumbau?", "partei", set()),
    ("Wie lief die Debatte um das Stadion?", "verlauf", set()),
    ("Was ist am Fliegerhorst geplant?", "thema", set()),
    ("Was wurde zum Radweg an der Donnerschweer Straße beschlossen?", "thema", set()),
    ("Wann tagt der Rat das nächste Mal?", "thema", set()),
    ("Was sagte die SPD zum Klimaschutz?", "partei", set()),
    ("Was ist die GSG?", "thema", set()),
    ("Wer ist im Verwaltungsausschuss?", "thema", set()),
]

#: Welche Store-Methode eine Facette anfasst. Die zweite Hälfte der Messung:
#: „richtige Quelle" heißt richtige Facette UND richtiger Datenzugriff.
ERWARTETE_METHODEN = {
    "plan": "haushalt_fuer_begriffe",
    "ansatz": "ansatz_fuer_begriffe",
    "ist": "ergebnis_ist_fuer_begriffe",
    "gruende": "abweichungsgruende_fuer_begriffe",
    "pruefung": "pruefberichte_fuer_begriffe",
    "produkte": "produkte_fuer_begriffe",
    "steuern": "steuern_fuer_begriffe",
    "ausgleich": "steuerkraft_kontext",
    "konzern": "konzern_kontext",
    "vergleich": "staedtevergleich_kontext",
}


class _MessStore:
    """Store-Attrappe, die jeden Zugriff protokolliert.

    Liefert absichtlich leere Ergebnisse: Gemessen wird, WAS gefragt wird —
    nicht, was zufällig in einer Test-Datenbank steht. Die Inhalte prüfen die
    Bausteine-Tests weiter unten an einer echten (tmp_path-)Datenbank."""

    def __init__(self, steuern_treffer: bool = False):
        self.aufrufe: list[str] = []
        self._steuern_treffer = steuern_treffer

    def _merken(self, name, wert):
        self.aufrufe.append(name)
        return wert

    def haushalt_fuer_begriffe(self, b, limit=3):
        return self._merken("haushalt_fuer_begriffe", [])

    def ansatz_fuer_begriffe(self, b, limit=4):
        return self._merken("ansatz_fuer_begriffe", None)

    def steuern_fuer_begriffe(self, b):
        return self._merken(
            "steuern_fuer_begriffe",
            [{"art": "insgesamt", "jahr": 2025, "betrag": 1.0}] if self._steuern_treffer else [])

    def steuerkraft_kontext(self):
        return self._merken("steuerkraft_kontext", None)

    def ergebnis_ist_fuer_begriffe(self, b, limit=2):
        return self._merken("ergebnis_ist_fuer_begriffe", None)

    def abweichungsgruende_fuer_begriffe(self, b, limit=3):
        return self._merken("abweichungsgruende_fuer_begriffe", [])

    def pruefberichte_fuer_begriffe(self, b, limit=4):
        return self._merken("pruefberichte_fuer_begriffe", None)

    def produkte_fuer_begriffe(self, b, limit=4):
        return self._merken("produkte_fuer_begriffe", None)

    def konzern_kontext(self):
        return self._merken("konzern_kontext", None)

    def staedtevergleich_kontext(self, reihe="steuerkraft"):
        return self._merken("staedtevergleich_kontext", None)


# ---------------------------------------------------------------------------
# 1. Die Messtabelle
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("frage,typ,erwartet", KORPUS,
                         ids=[f"{k[0][:44]}" for k in KORPUS])
def test_korpus_zieht_die_richtigen_quellen(frage, typ, erwartet):
    """Erkennung: zieht diese Frage genau die Quellen, die sie beantworten?"""
    assert qa.geld_facetten(frage, typ) == erwartet


@pytest.mark.parametrize("frage,typ,erwartet", KORPUS,
                         ids=[f"{k[0][:44]}" for k in KORPUS])
def test_korpus_ruft_die_richtigen_store_methoden(frage, typ, erwartet):
    """Verdrahtung: wird zu jeder erkannten Facette auch wirklich die
    zugehörige Store-Methode aufgerufen — und keine andere?

    Der Test, der bei einem Umbau als Erster ausschlägt: Eine Facette, die
    zwar erkannt wird, deren Abfrage aber niemand mehr auslöst, sähe an
    ``geld_facetten`` allein völlig gesund aus."""
    store = _MessStore()
    kontext = qa.geld_kontext(store, frage, "Suchbegriffe der Expansion", typ)
    assert set(kontext["facetten"]) == erwartet
    erwartete_calls = {ERWARTETE_METHODEN[f] for f in erwartet}
    # `steuerkraft_kontext` läuft nur bei echtem Steuer-Treffer oder bei
    # ausdrücklicher NFAG-Frage — der Attrappen-Store liefert keinen Treffer.
    if "ausgleich" in erwartet and "steuerkraft_kontext" not in set(store.aufrufe):
        erwartete_calls.discard("steuerkraft_kontext")
    assert set(store.aufrufe) == erwartete_calls


def test_negativfaelle_fassen_die_datenbank_nicht_an():
    """Der wichtigste Test des Korpus: Eine Frage ohne Geld-Bezug darf keine
    einzige Haushalts-Abfrage auslösen.

    Ohne ihn optimiert man auf „lädt immer alles" — der Kontext ist knapp, und
    jede geladene Quelle verdrängt Beschlüsse, nach denen gefragt wurde."""
    for frage, typ, erwartet in KORPUS:
        if erwartet:
            continue
        store = _MessStore()
        kontext = qa.geld_kontext(store, frage, "Stadion Neubau Finanzierung Kosten", typ)
        assert store.aufrufe == [], f"{frage} fasste {store.aufrufe} an"
        assert qa.geld_block(kontext) == ""
        assert qa.geld_regeln(kontext) == ""


def test_expansion_darf_die_facetten_nicht_verschieben():
    """Der Wortlaut entscheidet, OB eine Quelle gefragt wird — nicht die
    Query-Expansion.

    Das ist keine Kosmetik: Der Analyse-Prompt verlangt ausdrücklich eine
    Umformulierung „aus anderem Blickwinkel — z. B. die Sachstands-Frage
    zusätzlich als Finanzierungs-Frage". Wer die Facetten an den expandierten
    Begriffen festmacht, zieht damit den halben Haushalt in jede
    Stadion-Frage."""
    store = _MessStore()
    qa.geld_kontext(store, "Wie ist der Stand beim Stadion?",
                    "Stadion Neubau Kosten Haushalt Finanzierung Zuschuss", "verlauf")
    assert store.aufrufe == []


STADION_FRAGEN = [
    "Wie ist der Stand beim Stadion?",
    "Was wurde zum Stadion beschlossen?",
    "Wer stimmte gegen den Stadionumbau?",
    "Wie lief die Debatte um das Stadion?",
    "Wie geht es mit dem Stadion weiter?",
    "Was kostete der Stadionumbau?",
]


@pytest.mark.parametrize("frage", STADION_FRAGEN)
def test_stadion_regression(frage, tmp_path):
    """Tims stehende Direktive: Jede Verbesserung an der Suche wird an den
    Stadion-Fragen geprüft.

    Für diese Runde heißt das: Der Antwort-Prompt einer Stadion-Frage darf
    keine Haushaltszahl enthalten. Fünf der sechs Fragen ziehen gar keine
    Quelle; „Was kostete der Stadionumbau?" fragt zwar nach Kosten und
    befragt deshalb die Produkt- und Plan-Ebene — findet dort aber nichts
    (ein Stadionumbau ist weder ein Produkt noch ein Teilhaushalt) und
    schreibt folglich kein Zeichen in den Prompt. Genau so ist es gebaut:
    Die Facette entscheidet, ob GEFRAGT wird, die Quelle, ob etwas
    ZURÜCKKOMMT."""
    store = _befuellter_store(tmp_path)
    kontext = qa.geld_kontext(store, frage, "Stadion Neubau Finanzierung Kosten", "thema")
    assert qa.geld_block(kontext) == "", sorted(kontext["facetten"])
    messages, _ = qa._answer_messages(
        frage, [{"id": 5, "title": "Stadion Marschweg", "beschluss": "Zugestimmt.",
                 "amount_eur": 4_200_000}], typ="thema", geld=kontext)
    prompt = messages[0]["content"]
    assert "Volumen: 4.200.000 €" in prompt          # der Beschluss-Betrag bleibt
    for kopf in ("STADTHAUSHALT", "GEPLANT UND TATSÄCHLICH", "RECHNUNGSPRÜFUNGSAMT",
                 "DER KONZERN STADT", "AUFGABEN DER STADT", "HAUSHALTSANSATZ"):
        assert kopf not in prompt, kopf
    store.close()


def test_typ_geld_bleibt_das_auffangnetz():
    """Rückwärtskompatibilität: Sagt das Modell ``geld`` und trifft kein
    Muster, kommen die Plan-Zahlen — genau wie vor dieser Runde."""
    assert qa.geld_facetten("Wie hoch fiel das aus?", "geld") == {"plan"}
    assert qa.geld_facetten("Wie hoch fiel das aus?", "thema") == set()


# ---------------------------------------------------------------------------
# 2. Formulierungs-Varianten
# ---------------------------------------------------------------------------
# „auch gucken wie genau die Frage formuliert sein muss" — hier steht die
# Antwort. Fällt eine Variante durch, ist genau das der Befund.

VARIANTEN = [
    ("Kosten einer Aufgabe",
     ["Was kostet die Feuerwehr?",
      "Wie teuer ist die Feuerwehr?",
      "Feuerwehr Kosten",
      "Was gibt die Stadt für die Feuerwehr aus?",
      "Wie viel gibt Oldenburg für die Feuerwehr aus?"],
     {"plan", "produkte"}),
    ("Plan gegen Ist",
     ["Hat die Stadt 2024 mehr ausgegeben als geplant?",
      "Wurde der Haushalt 2024 eingehalten?",
      "Was ist aus dem Haushaltsplan tatsächlich geworden?",
      "Wie hoch war das Defizit im Jahresabschluss?"],
     None),  # None = „mindestens `ist`", der Rest darf variieren
    ("Prüfbericht",
     ["Was hat das Rechnungsprüfungsamt beanstandet?",
      "Welche Beanstandungen gab es?",
      "Was steht im Schlussbericht des Rechnungsprüfungsamts?",
      "Was hat der Rechnungsprüfer gerügt?"],
     None),
    ("Pflichtaufgabe",
     ["Muss die Stadt das Theater betreiben?",
      "Ist das Theater eine Pflichtaufgabe?",
      "Welche Rechtsgrundlage hat das Theater?",
      "Könnte die Stadt das Theater streichen?"],
     None),
]


@pytest.mark.parametrize("name,fragen,erwartet", VARIANTEN, ids=[v[0] for v in VARIANTEN])
def test_umformulierungen_landen_bei_derselben_quelle(name, fragen, erwartet):
    """Dieselbe Frage, vier Formulierungen — dieselben Quellen.

    Die Erkennung darf nicht an der Wortwahl hängen: Wer „Wie teuer ist die
    Feuerwehr?" tippt, bekommt sonst eine andere Antwortgrundlage als wer
    „Feuerwehr Kosten" tippt, und niemand sähe warum."""
    leitfacette = {"Kosten einer Aufgabe": "produkte", "Plan gegen Ist": "ist",
                   "Prüfbericht": "pruefung", "Pflichtaufgabe": "produkte"}[name]
    for frage in fragen:
        f = qa.geld_facetten(frage, "thema")
        assert leitfacette in f, f"„{frage}“ verfehlt die Quelle {leitfacette} (fand {sorted(f)})"
        if erwartet is not None:
            assert f == erwartet, f"„{frage}“ → {sorted(f)}"


# ---------------------------------------------------------------------------
# 3. Die Bausteine: Inhalt, Beleg, Jahr
# ---------------------------------------------------------------------------

def _befuellter_store(tmp_path) -> CouncilStore:
    """Eine kleine, aber echte Haushalts-Datenbank — Zahlen im Zuschnitt des
    Prod-Bestands, damit die Zeichen-Messung unten etwas aussagt."""
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_herkunft (id, schluessel, art, label, url, fundstelle, "
            " seite, probe, stand, fetched_at) VALUES "
            "(1, 'k1', 'ris', 'Jahresabschluss 2024', 'https://example.org/ja2024', "
            " 'Abschnitt 6.2 Ergebnisrechnung', 41, 'summenprobe', '31.12.2024', '2026-08-16')")
        store._conn.execute(
            "INSERT INTO council_herkunft (id, schluessel, art, label, url, fundstelle, "
            " probe, stand, fetched_at) VALUES "
            "(2, 'k2', 'ris', 'Schlussbericht RPA 2023', 'https://example.org/rpa', "
            " 'Randmarken des Berichts', 'randmarkenprobe', '2023', '2026-08-16')")
        # Ergebnisrechnung: Gesamt + ein Teilhaushalt, je Erträge (12)/Aufwendungen (20)
        for thh, name, e_plan, e_ist, a_plan, a_ist in [
                (None, None, 760_000_000.0, 781_400_000.0, 799_000_000.0, 812_300_000.0),
                (5, "Soziales und Jugend", 90_000_000.0, 93_100_000.0,
                 240_000_000.0, 251_900_000.0)]:
            store._conn.execute(
                "INSERT INTO council_ergebnisrechnung (jahr, thh_nr, thh_name, nr, bezeichnung, "
                " ansatz, plan, plan_art, ergebnis, abweichung, ist_summe, fetched_at, herkunft_id) "
                "VALUES (2024,?,?,12,'Summe ordentliche Erträge',?,?,'ansatz',?,0,1,'',1)",
                (thh, name, e_plan, e_plan, e_ist))
            store._conn.execute(
                "INSERT INTO council_ergebnisrechnung (jahr, thh_nr, thh_name, nr, bezeichnung, "
                " ansatz, plan, plan_art, ergebnis, abweichung, ist_summe, fetched_at, herkunft_id) "
                "VALUES (2024,?,?,20,'Summe ordentliche Aufwendungen',?,?,'ansatz',?,0,1,'',1)",
                (thh, name, a_plan, a_plan, a_ist))
        store._conn.execute(
            "INSERT INTO council_abweichungsgruende (jahr, nr, bezeichnung, delta_mio, "
            " prozent, text, fetched_at, herkunft_id) VALUES "
            "(2024, 1, 'Steuern und ähnliche Abgaben', 21.4, 5.2, "
            " 'Die Mehrerträge beruhen im Wesentlichen auf Nachveranlagungen bei der "
            "Gewerbesteuer aus Vorjahren.', '', 1)")
        store._conn.execute(
            "INSERT INTO council_pruefberichte (jahr, lfd, marke, marke_name, textziffer, "
            " abschnitt, kette, seite, text, fetched_at, herkunft_id) VALUES "
            "(2023, 1, 'WB', 'Wiederholte Beanstandung', '4.5.2', 'Vergabewesen', 'verg', 87, "
            " 'Die Dokumentation der Vergabeentscheidungen ist erneut unvollständig.', '', 2)")
        store._conn.execute(
            "INSERT INTO council_pruefberichte (jahr, lfd, marke, marke_name, textziffer, "
            " abschnitt, seite, text, fetched_at, herkunft_id) VALUES "
            "(2023, 2, 'H', 'Hinweis', '5.1', 'Anlagenbuchhaltung', 91, "
            " 'Es wird angeregt, die Nutzungsdauern zu überprüfen.', '', 2)")
        store._conn.execute(
            "INSERT INTO council_produkte (jahr, produkt_nr, produkt_name, amt, ertraege, "
            " aufwendungen, ergebnis, kurzbeschreibung, auftragsgrundlage, beeinflussbarkeit, "
            " fetched_at, herkunft_id) VALUES "
            "(2023, 'P12.126001', 'Brandschutz und Feuerwehr', 'Amt für Brandschutz', "
            " 1200000, 23400000, -22200000, 'Abwehrender Brandschutz und Hilfeleistung.', "
            " '§ 2 NBrandSchG', 'niedrig', '', 1)")
        store._conn.execute(
            "INSERT INTO council_produkte (jahr, produkt_nr, produkt_name, amt, ertraege, "
            " aufwendungen, ergebnis, auftragsgrundlage, beeinflussbarkeit, fetched_at, "
            " herkunft_id) VALUES "
            "(2023, 'P26.262001', 'Theater und Konzerte', 'Kulturamt', 300000, 9800000, "
            " -9500000, 'Freiwillige Leistung der Stadt', 'hoch', '', 1)")
        store._conn.executemany(
            "INSERT INTO council_konzern_posten (jahr, nr, bezeichnung, rolle, betrag, "
            " ist_summe, fetched_at, herkunft_id) VALUES (2024,?,?,?,?,1,'',1)",
            [(13, 'Summe ordentliche Erträge', 'ertraege_summe', 1_238_000_000.0),
             (21, 'Summe ordentliche Aufwendungen', 'aufwendungen_summe', 1_242_000_000.0)])
        store._conn.executemany(
            "INSERT INTO council_konzern_traeger (jahr, art, traeger_key, traeger, "
            " betrag_teur, fetched_at, herkunft_id) VALUES (2024,'aufwendungen',?,?,?,'',1)",
            [("stadt", "Stadt Oldenburg (Kernverwaltung)", 812_300.0),
             ("klinikum", "Klinikum Oldenburg AöR", 390_000.0),
             ("konsolidierung", "Konsolidierung", -120_000.0)])
        store._conn.executemany(
            "INSERT INTO council_staedtevergleich (reihe, jahr, schluessel, stadt, kennzahl, "
            " wert, einheit, herkunft_id, fetched_at) VALUES "
            "('steuerkraft',2024,?,?,'Steuerkraftmesszahl je Einwohner',?,'EUR',1,'')",
            [("03403", "Oldenburg", 1834.0), ("03404", "Osnabrück", 1712.0),
             ("03401", "Delmenhorst", 1104.0)])
        store._conn.executemany(
            "INSERT INTO council_ergebnishaushalt (plan_jahrgang, jahr, art, nr, bezeichnung, "
            " betrag, ist_summe, fetched_at, herkunft_id) VALUES (2026,2026,'ansatz',?,?,?,?,'',1)",
            [(1, "Steuern und ähnliche Abgaben", 430_000_000.0, 0),
             (12, "Summe ordentliche Erträge", 812_000_000.0, 1),
             (20, "Summe ordentliche Aufwendungen", 846_000_000.0, 1)])
        # Finanzplanungsjahr desselben Dokuments — darf NIE in den Kontext.
        store._conn.execute(
            "INSERT INTO council_ergebnishaushalt (plan_jahrgang, jahr, art, nr, bezeichnung, "
            " betrag, ist_summe, fetched_at, herkunft_id) "
            "VALUES (2026, 2029, 'finanzplanung', 12, 'Summe ordentliche Erträge', "
            " 999_000_000.0, 1, '', 1)")
        store._conn.execute(
            "INSERT INTO council_haushalt (year, bereich, ertraege, aufwendungen, ergebnis, "
            " is_summe, fetched_at) VALUES "
            "(2026, 'Brandschutz und Rettungsdienst', 2000000, 31000000, -29000000, 0, '')")
    return store


def test_ist_block_nennt_jahr_plan_ist_und_beleg(tmp_path):
    store = _befuellter_store(tmp_path)
    ist = store.ergebnis_ist_fuer_begriffe(["Soziales", "Jugend"])
    text = qa._ist_block(ist)
    assert ist["jahr"] == 2024
    assert "812.300.000" in text and "799.000.000" in text   # Ist und Plan
    assert "Soziales und Jugend" in text                      # Teilhaushalt getroffen
    assert "Jahresabschluss 2024" in text and "Abschnitt 6.2" in text  # Beleg
    assert "S. 41" in text and "Stand 31.12.2024" in text
    assert "ABGERECHNETE Zahlen, nicht der Haushaltsplan" in text
    assert "[id]" in text  # die Nie-mit-[id]-Regel steht drin
    assert qa._ist_block(None) == ""
    store.close()


def test_abweichungsgrund_findet_die_steuerzeile_ueber_den_wortstamm(tmp_path):
    """Der Fall, an dem eine naive Suche scheitert: „Gewerbesteuer" und
    „Steuern und ähnliche Abgaben" haben kein gemeinsames Wort und in der
    einen Richtung auch keine gemeinsame Teilzeichenkette."""
    store = _befuellter_store(tmp_path)
    treffer = store.abweichungsgruende_fuer_begriffe(["Gewerbesteuer", "Mehreinnahmen"])
    assert treffer and treffer[0]["bezeichnung"] == "Steuern und ähnliche Abgaben"
    text = qa._gruende_block(treffer)
    assert "Nachveranlagungen" in text and "+21.4 Mio" in text
    # Es ist die Begründung der VERWALTUNG, keine Feststellung von uns.
    assert "Die Verwaltung begründet" in text
    store.close()


def test_pruefung_block_fuehrt_wiederholte_beanstandung_zuerst(tmp_path):
    store = _befuellter_store(tmp_path)
    p = store.pruefberichte_fuer_begriffe(["Haushalt"])   # kein Treffer → Rangfolge
    assert p["feststellungen"][0]["marke"] == "WB"
    text = qa._pruefung_block(p)
    assert "Wiederholte Beanstandung" in text and "Textziffer 4.5.2" in text
    assert "S. 87" in text
    assert "2023" in text and "insgesamt 2 Feststellungen" in text
    assert "AUSWAHL" in text
    store.close()


def test_produkte_block_traegt_rechtsgrundlage_und_spielraum(tmp_path):
    """Die Antwort auf „Muss die Stadt das Theater betreiben?" — sie steht in
    keinem Beschluss und in keiner Haushaltszeile, nur hier."""
    store = _befuellter_store(tmp_path)
    p = store.produkte_fuer_begriffe(["Theater"])
    text = qa._produkte_block(p)
    assert "Theater und Konzerte" in text and "Kulturamt" in text
    assert "Freiwillige Leistung der Stadt" in text
    assert "Spielraum der Stadt (Selbstauskunft des Plans): hoch" in text
    assert "kein Rechtsgutachten" in text
    assert "2023" in text  # das Jahr, in dem die Produktebene endet
    # Feuerwehr über das Amt gefunden, mit gesetzlicher Grundlage.
    assert "§ 2 NBrandSchG" in qa._produkte_block(
        store.produkte_fuer_begriffe(["Feuerwehr", "Brandschutz"]))
    assert store.produkte_fuer_begriffe(["Straßenbahn"]) is None
    store.close()


def test_konzern_block_stellt_kern_und_konzern_nebeneinander(tmp_path):
    store = _befuellter_store(tmp_path)
    k = store.konzern_kontext()
    text = qa._konzern_block(k)
    assert "1.242.000.000" in text          # Konzern
    assert "812.300.000" in text            # Kernverwaltung aus dem Abschluss
    assert "Klinikum Oldenburg AöR" in text
    assert "Konsolidierung" not in text     # die Verrechnungszeile ist kein Träger
    assert "NICHT verrechenbar" in text
    store.close()


def test_vergleich_block_bringt_alle_staedte_der_reihe(tmp_path):
    store = _befuellter_store(tmp_path)
    v = store.staedtevergleich_kontext()
    text = qa._vergleich_block(v)
    assert "Oldenburg: 1.834 EUR" in text and "Delmenhorst: 1.104 EUR" in text
    assert "Steuerkraftmesszahl je Einwohner" in text and "2024" in text
    store.close()


def test_ansatz_block_laesst_die_finanzplanung_draussen(tmp_path):
    """§-8-NKomVG-Vorausschau ist kein beschlossener Haushalt. Stünde sie im
    Kontext, böte der Prompt dem Modell einen Plan für 2029 an, den nie
    jemand aufgestellt hat."""
    store = _befuellter_store(tmp_path)
    a = store.ansatz_fuer_begriffe(["Steuern"])
    text = qa._ansatz_block(a)
    assert a["jahr"] == 2026
    assert "430.000.000" in text
    assert "999.000.000" not in text
    assert "2029" not in text
    store.close()


def test_leere_datenbank_liefert_leere_bausteine(tmp_path):
    """Eine frische Datenbank ohne Ingest-Lauf darf die Antwort nicht kosten."""
    store = CouncilStore(tmp_path / "leer.sqlite")
    kontext = qa.geld_kontext(store, "Was kostet die Stadt insgesamt?", "", "geld")
    assert qa.geld_block(kontext) == ""
    assert qa.geld_regeln(kontext) == ""
    store.close()


# ---------------------------------------------------------------------------
# 4. Das Zeichenbudget
# ---------------------------------------------------------------------------

def test_voller_geld_kontext_bleibt_im_budget(tmp_path):
    """Was kostet ein voller Geld-Kontext an Platz im Prompt?

    Der Kontext ist knapp: Neben den Geld-Bausteinen stehen dort bis zu 20
    Beschlüsse à ~600 Zeichen, Debatten, Presse und Steckbriefe. Dieser Test
    ist die laufende Messung — reißt der Deckel, fällt er auf."""
    store = _befuellter_store(tmp_path)
    # Eine Frage, die acht der zehn Quellen zieht — mehr geht in einem Satz
    # kaum, ohne ihn zu erfinden.
    kontext = qa.geld_kontext(
        store, "Warum kostet die Stadt insgesamt mehr als geplant, was hat das "
               "Rechnungsprüfungsamt dazu beanstandet, wie sehen die Erträge im "
               "Haushalt aus und wie ist das im Vergleich zu Osnabrück?",
        "Haushalt Soziales Theater Feuerwehr Steuern", "geld")
    text = qa.geld_block(kontext)
    assert len(kontext["facetten"]) >= 8, sorted(kontext["facetten"])
    assert len(text) <= qa.GELD_MAX_CHARS, f"{len(text)} Zeichen"
    # Und er ist auch nicht leer — sonst misst der Deckel nichts.
    assert len(text) > 1500, f"nur {len(text)} Zeichen"
    store.close()


def test_budget_kappt_ganze_bausteine_statt_saetze(tmp_path):
    """Reißt das Budget, fallen die HINTEREN Facetten weg — nicht alle in der
    Mitte. Ein halb abgeschnittener Prüfbericht wäre schlimmer als keiner."""
    store = _befuellter_store(tmp_path)
    kontext = qa.geld_kontext(store, "Warum gibt die Stadt insgesamt mehr aus als "
                                     "geplant und was wurde beanstandet?",
                              "Haushalt Steuern Soziales", "geld")
    voll = qa.geld_block(kontext)
    alt = qa.GELD_MAX_CHARS
    try:
        qa.GELD_MAX_CHARS = 400
        knapp = qa.geld_block(kontext)
    finally:
        qa.GELD_MAX_CHARS = alt
    assert 0 < len(knapp) < len(voll)
    # Was drin ist, ist ganz drin: der Baustein endet mit seiner letzten Zeile.
    assert knapp.endswith("\n")
    assert voll.startswith(knapp[:200])
    store.close()


# ---------------------------------------------------------------------------
# 5. Der Weg in den Prompt
# ---------------------------------------------------------------------------

def test_haushaltsregeln_haengen_am_kontext_nicht_am_fragetyp(tmp_path):
    """Der Kern der Entscheidung, ``geld`` NICHT aufzuteilen: „Was hat das
    Rechnungsprüfungsamt beanstandet?" ist für das Analyse-Modell mit gutem
    Grund ``thema`` — die Regeln müssen trotzdem im Prompt stehen."""
    store = _befuellter_store(tmp_path)
    kontext = qa.geld_kontext(store, "Was hat das Rechnungsprüfungsamt beanstandet?",
                              "Prüfbericht Beanstandung", "thema")
    messages, _ = qa._answer_messages(
        "Was hat das Rechnungsprüfungsamt beanstandet?",
        [{"id": 1, "title": "T", "beschluss": "B"}], typ="thema", geld=kontext)
    prompt = messages[0]["content"]
    assert "RECHNUNGSPRÜFUNGSAMT" in prompt
    assert "JAHR IMMER NENNEN" in prompt and "PLAN IST NICHT IST" in prompt
    # Die Beschluss-Betrags-Regel gehört hier NICHT hin.
    assert "als „Volumen: …“ markiert" not in prompt
    store.close()


def test_geldregeln_treten_bei_punktfragen_zurueck(tmp_path):
    """Punktfrage („Wie hoch war X?") — die Kürze-Regel gewinnt, es bleibt die
    Pflicht, Jahr und Quelle zu nennen."""
    store = _befuellter_store(tmp_path)
    kontext = qa.geld_kontext(store, "Was kostet die Feuerwehr?", "Feuerwehr Brandschutz", "geld")
    messages, _ = qa._answer_messages("Was kostet die Feuerwehr?", [], typ="geld",
                                      geld=kontext, eng=True)
    prompt = messages[0]["content"]
    assert "HÖCHSTENS 3 Sätzen" in prompt
    assert "JAHR IMMER NENNEN" not in prompt
    assert "laut Jahresabschluss 2024" in prompt   # die kurze Belegregel
    store.close()


def test_alter_aufrufweg_bleibt_unveraendert():
    """Die Deep-Research-Pipeline reicht haushalt=/steuern=/steuerkraft=
    einzeln durch (``app/deepresearch.py``, nicht Teil dieser Runde). Ohne
    ``geld=`` muss dabei exakt das Alte herauskommen."""
    zeilen = [{"year": 2026, "bereich": "Verkehr und Straßenbau",
               "aufwendungen": 46194645.0, "ertraege": 17510637.0}]
    messages, _ = qa._answer_messages("Was kostet der Verkehr?", [], typ="geld",
                                      haushalt=zeilen)
    assert "STADTHAUSHALT" in messages[0]["content"]
    assert "46.194.645" in messages[0]["content"]


def test_facetten_stehen_im_kontext_zum_mitloggen():
    store = _MessStore()
    kontext = qa.geld_kontext(store, "Was kostet die Feuerwehr?", "Feuerwehr", "geld")
    assert kontext["facetten"] == sorted({"plan", "produkte"})


def test_alle_facetten_haben_baustein_und_methode():
    """Wer eine Facette hinzufügt, ohne sie zu verdrahten, fliegt hier auf."""
    assert set(qa.GELD_FACETTEN) == set(qa._GELD_BAUSTEINE)
    assert set(qa.GELD_FACETTEN) == set(ERWARTETE_METHODEN)
    for methode in ERWARTETE_METHODEN.values():
        assert callable(getattr(CouncilStore, methode)), methode
        assert hasattr(_MessStore, methode), methode


def test_wortstamm_faltet_umlaute_und_kappt():
    assert CouncilStore._stamm("Gewerbesteuer") == "gewerb"
    assert CouncilStore._stamm("Steuern") == "steuer"
    assert CouncilStore._trifft("Steuern und ähnliche Abgaben", ["Gewerbesteuer"]) == 1
    assert CouncilStore._trifft("Brandschutz und Feuerwehr", ["Feuerwehr", "Brandschutz"]) == 2
    assert CouncilStore._trifft("Verkehr und Straßenbau", ["Kita"]) == 0
    assert CouncilStore._trifft(None, ["Kita"]) == 0
    # Zu kurze Begriffe zählen nicht — „aus", „für" träfen sonst überall.
    assert CouncilStore._trifft("Aus dem Ausschuss", ["aus"]) == 0


# ===========================================================================
# Manuell startbarer Lauf: stimmt die LLM-Klassifikation?
# ===========================================================================
# Kein Test — ein Messlauf. Braucht OPENROUTER_API_KEY und kostet echte
# Calls; deshalb steht er hier unten und nicht in der Suite:
#
#     OPENROUTER_API_KEY=… .venv/bin/python tests/test_qa_geldquellen.py
#
# Er beantwortet die eine Frage, die der Korpus oben bewusst NICHT stellt:
# Welchen Fragetyp liefert `analyse_query` wirklich? Wichtig ist dabei die
# letzte Spalte — sie zeigt, dass die Quellen auch dann stimmen, wenn das
# Modell einen anderen Typ nennt als erwartet. Genau dafür hängen die
# Facetten am Wortlaut und nicht am Typ.

def _messlauf() -> int:
    import os

    if not os.environ.get("OPENROUTER_API_KEY"):
        print("Kein OPENROUTER_API_KEY — der Lauf braucht echte LLM-Calls.")
        return 2
    kopf = f"{'Frage':52} {'Typ (LLM)':12} {'erwartet':10} Quellen"
    print(kopf)
    print("-" * len(kopf))
    abweichungen = 0
    for frage, erwartet_typ, erwartete_facetten in KORPUS:
        analyse = qa.analyse_query(frage)
        typ = analyse["typ"]
        facetten = qa.geld_facetten(analyse["frage"], typ)
        passt = facetten == erwartete_facetten
        abweichungen += 0 if passt else 1
        print(f"{frage[:52]:52} {typ:12} {erwartet_typ:10} "
              f"{'OK ' if passt else 'ABW'} {sorted(facetten)}")
    print(f"\n{len(KORPUS) - abweichungen}/{len(KORPUS)} Fälle mit den erwarteten Quellen.")
    return 1 if abweichungen else 0


if __name__ == "__main__":  # pragma: no cover — manueller Lauf
    import sys

    sys.exit(_messlauf())
