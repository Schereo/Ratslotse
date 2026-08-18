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
    # Dieselbe Frage als KOMPOSITUM. `\bkost` trifft nur „kostet"/„Kosten" am
    # Wortanfang; „Personalkosten", „Baukosten", „Betriebskosten" gingen bis
    # zum 17.08. leer aus — gemessen, nicht vermutet. Die Endung `kosten\b`
    # fängt sie. Beim Personal kommt der Stellenplan dazu, und das ist die
    # bessere Antwort: Personalausgaben ohne die Stellen dahinter sind eine
    # Zahl ohne Erklärung.
    ("Wie hoch sind die Personalkosten?", "geld", {"plan", "produkte", "stellenplan"}),
    ("Was sind die Baukosten der Schule?", "geld", {"plan", "produkte"}),
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

    # --- Die vier Schichten, die die KI-Frage bis 17.08. nicht kannte -------
    # Vorher zog jede dieser Fragen die falsche Quelle oder gar keine; die
    # Messung dazu steht im Kopf von `test_neue_facetten_ziehen_allein`.
    #
    # Schulden sind ein BESTAND. Vorher: {"plan"} — der Ergebnishaushalt, in
    # dem der Schuldenstand nicht vorkommt.
    ("Wie viel Schulden hat Oldenburg?", "geld", {"schulden"}),
    # Der ANDERE Haushalt. Vorher: {} bzw. {"plan"}.
    #
    # Seit 17.08. IMMER BEIDE: `investitionen` ist der Plan aus dem
    # Haushaltsplan, `gebaut` das Ist aus dem Statistischen Jahrbuch. Die
    # Frage sagt fast nie, welches von beidem gemeint ist — und die Regel
    # „nie voneinander abziehen" hinge an einer Zahl, die gar nicht im
    # Kontext steht, wenn nur eine der beiden käme.
    ("Was wird gebaut?", "thema", {"investitionen", "gebaut"}),
    ("Wie viel investiert die Stadt?", "geld", {"investitionen", "gebaut"}),
    # Stellen statt Euro. Vorher: {} — Personalfragen bekamen Aufwendungen.
    ("Wie viele Stellen sind unbesetzt?", "thema", {"stellenplan"}),
    ("Wie viele Mitarbeiter hat die Stadt?", "thema", {"stellenplan"}),
    # Die Änderungslisten. Vorher: {"plan", "ansatz"} — die Plan-Zahlen des
    # Haushalts, aber kein Wort darüber, wer ihn ändern wollte.
    ("Wer wollte den Haushalt ändern?", "thema", {"plan", "ansatz", "antraege"}),
    ("Welche Änderungslisten gab es zum Haushalt 2026?", "thema",
     {"plan", "ansatz", "antraege"}),

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
    # Die Gegenprobe zu den vier Neuzugängen: Wörter, die ihnen nahekommen,
    # ohne sie zu meinen. „Anträge stellen" ist das Verb, keine Planstelle;
    # „Debatte" ohne Haushalts-Anker ist kein Haushaltsstreit.
    ("Wie viele Anträge stellen die Fraktionen?", "thema", set()),
    ("Wer stellte den Antrag zum Radweg?", "thema", set()),
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
    "schulden": "schulden_kontext",
    "investitionen": "investitionen_fuer_begriffe",
    "gebaut": "investitionen_ist_kontext",
    "stellenplan": "stellenplan_kontext",
    "antraege": "haushaltsantraege_kontext",
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

    def schulden_kontext(self):
        return self._merken("schulden_kontext", None)

    def investitionen_fuer_begriffe(self, b, limit=3):
        return self._merken("investitionen_fuer_begriffe", None)

    def investitionen_ist_kontext(self):
        return self._merken("investitionen_ist_kontext", None)

    def stellenplan_kontext(self, jahrgang=None):
        return self._merken("stellenplan_kontext", None)

    def haushaltsantraege_kontext(self, jahr=None, limit=8):
        self.jahr_argument = jahr
        return self._merken("haushaltsantraege_kontext", None)


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


# ---------------------------------------------------------------------------
# 1b. Die vier Schichten der 17.08.-Runde
# ---------------------------------------------------------------------------
# Gemessen vor dem Umbau: 0 von 20 dieser Fragen zog ihre Quelle. Vier davon
# zogen eine FALSCHE — „Wie viel Schulden hat Oldenburg?" bekam den
# Ergebnishaushalt, in dem der Schuldenstand gar nicht vorkommt. Nach dem
# Umbau: 20 von 20, und jede allein (s. den Test darunter).

NEUE_FACETTEN = [
    ("schulden", [
        "Wie viel Schulden hat Oldenburg?",
        "Wie hoch sind die Schulden der Stadt?",
        "Wie hat sich der Schuldenstand entwickelt?",
        "Wie viele Schulden hat die Stadt pro Kopf?",
        "Ist Oldenburg verschuldet?",
    ]),
    ("investitionen", [
        "Was wird gebaut?",
        "Wie viel investiert die Stadt?",
        "Was sind die größten Investitionen?",
        "Wie hoch ist das Investitionsvolumen?",
        "Was will die Stadt bauen und kaufen?",
    ]),
    ("stellenplan", [
        "Wie viele Stellen sind unbesetzt?",
        "Wie viele Stellen hat die Stadtverwaltung?",
        "Wie viele Mitarbeiter hat die Stadt?",
        "Wie hoch ist der Besetzungsgrad im Stellenplan?",
        "Sucht die Stadt Personal?",
    ]),
    ("antraege", [
        "Wer wollte den Haushalt ändern?",
        "Welche Änderungslisten gab es zum Haushalt?",
        "Wer hat Änderungsanträge zum Haushalt gestellt?",
        "Wie umstritten war der Haushalt 2026?",
        "Kam die CDU mit ihren Haushaltsanträgen durch?",
    ]),
]


@pytest.mark.parametrize("facette,fragen", NEUE_FACETTEN, ids=[f[0] for f in NEUE_FACETTEN])
def test_neue_facetten_werden_erkannt(facette, fragen):
    """Fünf Formulierungen je Schicht — alle müssen ihre Quelle ziehen."""
    for frage in fragen:
        gefunden = qa.geld_facetten(frage, "thema")
        assert facette in gefunden, f"„{frage}“ → {sorted(gefunden)}"


@pytest.mark.parametrize("facette,fragen", NEUE_FACETTEN, ids=[f[0] for f in NEUE_FACETTEN])
def test_neue_facetten_ziehen_sich_nicht_gegenseitig(facette, fragen):
    """Die Gegenrichtung, und sie ist der wichtigere Teil der Messung.

    Zu viele Bausteine sind so schädlich wie zu wenige: Eine Schuldenfrage,
    die den Stellenplan mitzieht, verbraucht Kontext für etwas, wonach
    niemand gefragt hat — und stellt dem Modell zwei Zahlenwerke nebeneinander,
    die es dann in Beziehung setzt.

    Die drei Bestands-Schichten stehen für sich allein. `antraege` ist die
    Ausnahme und darf `plan`/`ansatz` mitbringen: „Wer wollte den Haushalt
    ändern?" trägt „Haushalt" im Wortlaut, und die Plan-Zahlen sind dort der
    Gegenstand des Streits, nicht Beiwerk.
    """
    zusatz = {"antraege": {"plan", "ansatz"},
              # Plan und Ist derselben Frage — sie MÜSSEN zusammen kommen,
              # sonst hinge die Regel „nie voneinander abziehen" an einer
              # Zahl, die nicht im Kontext steht (council/qa.py).
              "investitionen": {"gebaut"}}
    erlaubt = {facette} | zusatz.get(facette, set())
    for frage in fragen:
        gefunden = qa.geld_facetten(frage, "thema")
        fremde = gefunden - erlaubt
        assert not fremde, f"„{frage}“ zieht zusätzlich {sorted(fremde)}"


def test_schuldenfrage_zieht_weder_plan_noch_stellenplan():
    """Der namentlich benannte Befund: „Wie viel Schulden hat Oldenburg?" wurde
    vom Ergebnishaushalt beantwortet — der falschen Quelle.

    Schulden sind ein Bestand am Stichtag. Weder `plan` (Teilhaushalte) noch
    `ansatz` (Gesamtergebnishaushalt) führen sie; beide zu laden hieße, dem
    Modell Jahresbeträge neben einen Bestand zu legen."""
    f = qa.geld_facetten("Wie viel Schulden hat Oldenburg?", "geld")
    assert f == {"schulden"}
    assert "plan" not in f and "ansatz" not in f and "stellenplan" not in f


def test_investitionsfrage_zieht_nicht_den_ergebnishaushalt():
    """Im Ergebnishaushalt steht keine einzige Investition.

    Sie zieht den Finanzhaushalt — und zwar in beiden Fassungen: den Plan
    aus dem Haushaltsplan und das Ist aus dem Statistischen Jahrbuch."""
    f = qa.geld_facetten("Wie viel investiert die Stadt?", "geld")
    assert f == {"investitionen", "gebaut"}
    assert "plan" not in f and "ansatz" not in f


def test_stellen_als_verb_zieht_den_stellenplan_nicht():
    """„Anträge stellen" ist das Verb, keine Planstelle.

    Ohne diese Unterscheidung hinge der ganze Stellenplan an einem der
    häufigsten deutschen Verben."""
    assert qa.geld_facetten("Wie viele Anträge stellen die Fraktionen?", "thema") == set()
    assert qa.geld_facetten("Wer stellte den Antrag zum Radweg?", "thema") == set()
    # Die echte Zählfrage bleibt erkannt.
    assert "stellenplan" in qa.geld_facetten("Wie viele Stellen hat die Stadt?", "thema")


def test_debatte_ohne_haushalt_ist_kein_haushaltsstreit():
    """`antraege` braucht einen Haushalts-Anker; „Debatte" allein reicht nicht."""
    assert "antraege" not in qa.geld_facetten("Wie lief die Debatte um das Stadion?", "verlauf")
    assert "antraege" in qa.geld_facetten("Wie lief die Haushaltsdebatte?", "thema")


def test_jahrgang_aus_der_frage_geht_an_die_aenderungslisten():
    """„Wer wollte den Haushalt 2024 ändern?" meint 2024, nicht den jüngsten
    Jahrgang — und das Jahr kommt aus der FRAGE, nicht aus den expandierten
    Begriffen (die streuen Jahreszahlen ein, die niemand getippt hat)."""
    assert qa.haushaltsjahr("Wer wollte den Haushalt 2024 ändern?") == 2024
    assert qa.haushaltsjahr("Wer wollte den Haushalt ändern?") is None
    store = _MessStore()
    qa.geld_kontext(store, "Wer wollte den Haushalt 2024 ändern?", "Haushalt 2026 Etat", "thema")
    assert store.jahr_argument == 2024
    store = _MessStore()
    qa.geld_kontext(store, "Wer wollte den Haushalt ändern?", "Haushalt 2026 Etat", "thema")
    assert store.jahr_argument is None


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
        # Der Betrag als Parameter, nicht als Literal: Pythons
        # Unterstrich-Schreibweise (999_000_000.0) ist KEIN SQL. Neuere
        # SQLite-Versionen schlucken sie klaglos, die der CI nicht — lokal
        # grün, in der CI 17 Fehler (16.08.).
        store._conn.execute(
            "INSERT INTO council_ergebnishaushalt (plan_jahrgang, jahr, art, nr, bezeichnung, "
            " betrag, ist_summe, fetched_at, herkunft_id) "
            "VALUES (2026, 2029, 'finanzplanung', 12, 'Summe ordentliche Erträge', "
            " ?, 1, '', 1)", (999_000_000.0,))
        store._conn.execute(
            "INSERT INTO council_haushalt (year, bereich, ertraege, aufwendungen, ergebnis, "
            " is_summe, fetched_at) VALUES "
            "(2026, 'Brandschutz und Rettungsdienst', 2000000, 31000000, -29000000, 0, '')")
        # --- Die vier Schichten der 17.08.-Runde ---------------------------
        # Schulden: Reihenanfang, Höchststand, Vorjahr, jüngstes Jahr. Vier
        # Zeilen reichen — der Baustein zeigt genau diese vier Bezugspunkte.
        store._conn.executemany(
            "INSERT INTO council_schulden (jahr, kreditmarkt, sondermittel, "
            " gebietskoerperschaften, eigenbetriebe, insgesamt, je_einwohner, "
            " revidiert, herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,0,3,'')",
            [(1995, None, None, None, None, 198_000_000.0, 1_420.0),
             (2013, None, None, None, None, 512_400_000.0, 3_180.0),
             (2024, 214_000_000.0, 1_200_000.0, 8_600_000.0, 109_000_000.0,
              332_800_000.0, 1_910.0),
             (2025, 219_400_000.0, 1_100_000.0, 8_300_000.0, 108_600_000.0,
              337_400_000.0, 1_932.0)])
        # Investitionen: Summenzeile, drei Teilhaushalte und die Bezugsgröße
        # `finanzhaushalt` — die darf NICHT im Kontext landen (ungeprüft).
        store._conn.executemany(
            "INSERT INTO council_investitionen (jahr, ebene, thh_nr, bezeichnung, "
            " einzahlungen, auszahlungen, herkunft_id, fetched_at) VALUES (2026,?,?,?,?,?,4,'')",
            [("investitionen", 0, "Summe Investitionstätigkeit", 22_300_000.0, 80_800_000.0),
             ("teilhaushalt", 4, "Schule und Sport", 6_100_000.0, 24_600_000.0),
             ("teilhaushalt", 7, "Verkehr und Straßenbau", 3_400_000.0, 10_500_000.0),
             ("teilhaushalt", 9, "Feuerwehr", 200_000.0, 3_900_000.0),
             ("finanzhaushalt", 0, "Gesamtbetrag des Finanzhaushaltes",
              871_000_000.0, 903_000_000.0)])
        # Stellenplan: beide Teile, nur die Gesamtzeilen. besetzt +
        # nicht_besetzt = stellen_vorjahr (die Besetzungsprobe des Plans).
        store._conn.executemany(
            "INSERT INTO council_stellenplan (jahrgang, teil, zeile, art, bezeichnung, "
            " stellen_plan, stellen_vorjahr, besetzt, nicht_besetzt, stichtag, "
            " herkunft_id, fetched_at) VALUES (2026,?,0,'gesamt',?,?,?,?,?,'30.06.2025',?,'')",
            [("A", "Gesamt Teil A", 815.50, 802.00, 761.25, 40.75, 5),
             ("B", "Gesamt Teil B", 1_702.25, 1_688.50, 1_579.00, 109.50, 6)])
        # Der Streit ums Geld: eine Runde zum Haushalt 2026 mit zwei
        # Stationen. Die Titel sind die echten Anker (`_STREIT_SATZUNG`,
        # `_STREIT_SAMMEL`) — an ihnen hängt die ganze Erkennung.
        store._conn.executemany(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
            " location, fetched_at) VALUES (?,?,?,'16:00','Rathaus','')",
            [(9001, "Ausschuss für Finanzen und Beteiligungen", "2026-02-10"),
             (9002, "Rat", "2026-02-23")])
        eintraege = []
        for ksinr, top in ((9001, "6"), (9002, "7")):
            eintraege.append((ksinr, 0, "decision", top, "Haushalt 2026", None, None))
            eintraege.append((ksinr, 1, "decision", f"{top}.9",
                              "Haushaltssatzung und Haushaltsplan 2026",
                              "angenommen", "mehrheitlich"))
        for ksinr, top, lauf in ((9001, "6", 10), (9002, "7", 10)):
            listen = [
                ("Änderungsliste Verwaltung I zum Ergebnishaushalt", "angenommen"),
                ("Änderungsliste der CDU-Fraktion zum Ergebnishaushalt", "abgelehnt"),
                ("Änderungsliste der CDU-Fraktion zum Finanzhaushalt", "abgelehnt"),
                ("Änderungsliste der Fraktionen SPD und Bündnis 90/Die Grünen "
                 "zum Ergebnishaushalt", "angenommen"),
                ("Änderungsliste der Gruppe FDP/Volt zum Ergebnishaushalt", "abgelehnt"),
                ("So geänderter Ergebnishaushalt einschließlich der Änderungslisten",
                 "angenommen"),
            ]
            for i, (titel, ergebnis) in enumerate(listen):
                eintraege.append((ksinr, lauf + i, "subvote", f"{top}.{i + 1}",
                                  titel, ergebnis, "mehrheitlich"))
        store._conn.executemany(
            "INSERT INTO council_decisions (ksinr, position, kind, item_number, title, "
            " outcome, vote) VALUES (?,?,?,?,?,?,?)", eintraege)
        store._conn.executemany(
            "INSERT INTO council_herkunft (id, schluessel, art, label, url, fundstelle, "
            " probe, stand, fetched_at) VALUES (?,?,'ris',?,?,?,?,?,'2026-08-17')",
            [(3, "k3", "Statistisches Jahrbuch, Tabelle 1108",
              "https://example.org/1108", "Tabelle 1108", "prokopfprobe", "2025"),
             (4, "k4", "Haushaltsplan 2026, Finanzhaushalt",
              "https://example.org/hh2026", "Gesamtfinanzhaushalt", "summenprobe", "2026"),
             (5, "k5", "Haushaltsplan 2026, Stellenplan Teil A",
              "https://example.org/sp-a", "Anlage 21", "besetzungsprobe", "30.06.2025"),
             (6, "k6", "Haushaltsplan 2026, Stellenplan Teil B",
              "https://example.org/sp-b", "Anlage 22", "besetzungsprobe", "30.06.2025")])
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


def test_schulden_block_traegt_die_abgrenzung_woertlich(tmp_path):
    """Die Abgrenzung ist an dieser Zahl keine Fußnote, sondern ihre Bedeutung:
    „Schulden der Stadt" heißen zwei Zahlen, die sich um ein Vielfaches
    unterscheiden. Der Wortlaut kommt aus ``council.schulden.ABGRENZUNG`` —
    eine zweite Formulierung daneben wäre eine dritte Zahl."""
    from council import schulden

    store = _befuellter_store(tmp_path)
    s = store.schulden_kontext()
    text = qa._schulden_block(s)
    assert s["jahr"] == 2025
    assert "337.400.000" in text and "1.932 €" in text        # Stand und Pro-Kopf
    assert "332.800.000" in text                              # das Jahr davor
    assert "2013 mit 512.400.000" in text                     # Höchststand der Reihe
    assert "sie beginnt 1995" in text
    assert schulden.ABGRENZUNG in text                        # wörtlich, nicht nachgebaut
    assert "Eigenbetriebe" in text and "Klinikum" in text
    # Die Bestands-Regel steht ausdrücklich drin — sonst wird die Zahl als
    # Jahresbetrag gelesen und gegen den Haushalt gerechnet.
    assert "BESTAND am Stichtag" in text and "nie mit Aufwendungen" in text
    assert "[id]" in text
    assert "Tabelle 1108" in text                             # Beleg
    assert qa._schulden_block(None) == ""
    store.close()


def test_investitionen_block_warnt_vor_dem_zweiten_haushalt(tmp_path):
    """Zwei Millionenbeträge im selben Kontext, die nichts miteinander zu tun
    haben, addiert ein Sprachmodell bereitwillig. Ohne die Warnung wäre der
    Baustein schädlicher als sein Fehlen."""
    store = _befuellter_store(tmp_path)
    i = store.investitionen_fuer_begriffe(["Schule", "Sport"])
    text = qa._investitionen_block(i)
    assert i["jahr"] == 2026
    assert "80.800.000" in text                        # Summenzeile der Datei
    assert "Schule und Sport" in text                  # der getroffene Teilhaushalt
    assert "ZWEI HAUSHALTE, NICHT EINER" in text
    assert "keine einzige Investition" in text and "Abschreibung" in text
    assert "nie addieren" in text
    assert "KEIN einzelnes Vorhaben" in text           # sagt nicht, welche Straße
    # Der Gesamtbetrag des Finanzhaushaltes ist von keiner Probe gedeckt und
    # steht deshalb bewusst NICHT im Prompt — er läge dort neben geprüften
    # Zahlen und sähe aus wie eine von ihnen.
    assert "903.000.000" not in text and "Gesamtbetrag des Finanzhaushaltes" not in text
    assert qa._investitionen_block(None) == ""
    store.close()


def test_stellenplan_block_bindet_die_besetzung_an_das_vorjahr(tmp_path):
    """`Stellen − besetzt` ist die Rechnung, die einem Modell am nächsten
    liegt und die in keinem Dokument steht: Sie mischt zwei Stichtage.

    815,50 − 761,25 wären 54,25 „unbesetzte" Stellen. Im Plan stehen 40,75 —
    weil sich die Besetzung auf die 802,00 Stellen des Vorjahres bezieht."""
    store = _befuellter_store(tmp_path)
    s = store.stellenplan_kontext()
    text = qa._stellenplan_block(s)
    assert s["jahrgang"] == 2026 and s["stichtag"] == "30.06.2025"
    assert "815,50 Stellen im Haushaltsjahr 2026" in text
    assert "Im Vorjahr waren es 802,00 Stellen" in text
    assert "761,25 besetzt und 40,75 nicht besetzt" in text
    assert "54,25" not in text                      # die verbotene Differenz
    assert "VORJAHRESSPALTE, Stichtag 30.06.2025" in text
    assert "minus besetzt" in text and "mischt zwei Stichtage" in text
    assert "Beamtinnen und Beamte" in text and "Arbeitnehmerinnen" in text
    # Stellen sind keine Köpfe, und es ist nur die Kernverwaltung.
    assert "keine Köpfe" in text and "Kernverwaltung" in text
    assert "addiere die Teile nicht" in text
    assert not s["fehlend"]
    assert qa._stellenplan_block(None) == ""
    store.close()


def test_stellenplan_nennt_den_fehlenden_teil(tmp_path):
    """Ein Jahrgang mit nur einem Teil sähe sonst wie ein ganzer aus — und
    eine Antwort, die dann „815 Stellen" sagt, unterschlägt 1.700."""
    store = _befuellter_store(tmp_path)
    with store._conn:
        store._conn.execute("DELETE FROM council_stellenplan WHERE teil = 'B'")
    text = qa._stellenplan_block(store.stellenplan_kontext())
    assert "NICHT im Bestand: der Teil für Arbeitnehmerinnen und Arbeitnehmer" in text
    assert "nicht der ganze Stellenplan" in text
    store.close()


def test_antraege_block_sagt_wer_und_zieht_die_grenze(tmp_path):
    """Wer wollte ändern und kam durch — und der ausdrückliche Satz, dass der
    INHALT der Listen nicht im Bestand ist.

    Ohne ihn füllt das Modell die Lücke mit Plausiblem: „Die CDU wollte bei
    den Sozialausgaben kürzen" steht nirgends und ließe sich auch nicht
    widerlegen."""
    store = _befuellter_store(tmp_path)
    a = store.haushaltsantraege_kontext()
    text = qa._antraege_block(a)
    assert a["jahr"] == 2026
    # Beide Stationen: Der Ausschuss stimmt über dieselben Listen ab wie der
    # Rat, oft mit anderem Ergebnis.
    assert "Ausschuss für Finanzen und Beteiligungen" in text and "Rat," in text
    assert "CDU: 2 — davon 0 angenommen, 2 abgelehnt" in text
    # Gemeinsame Listen zählen für BEIDE Fraktionen, nicht für die erstgenannte.
    assert "SPD: 1" in text and "Grüne: 1" in text
    assert "FDP/Volt: 1" in text
    # Die Verwaltungsliste ist kein Fraktionsantrag.
    assert "1 der Verwaltung" in text and "kein Fraktionsantrag" in text
    # Die Schlussabstimmung über die Sache selbst.
    assert "Schlussabstimmung über die Haushaltssatzung: angenommen" in text
    # Und die Grenze der Quelle.
    assert "WER etwas ändern" in text and "nicht WAS genau" in text
    assert "erfinde" in text and "nicht als Text vor" in text
    assert "nicht\naddierbar" in text
    # „So geänderter Ergebnishaushalt …" ist die Sammelabstimmung, kein Antrag.
    assert "So geänderter" not in text
    assert qa._antraege_block(None) == ""
    store.close()


def test_antraege_folgen_dem_jahrgang_aus_der_frage(tmp_path):
    """Das Haushaltsjahr ist nicht das Sitzungsjahr — und ein Jahrgang, den es
    nicht gibt, fällt auf den jüngsten zurück statt ins Leere."""
    store = _befuellter_store(tmp_path)
    assert store.haushaltsantraege_kontext(2026)["jahr"] == 2026
    assert store.haushaltsantraege_kontext(1999)["jahr"] == 2026
    store.close()


def test_leere_datenbank_liefert_leere_bausteine(tmp_path):
    """Eine frische Datenbank ohne Ingest-Lauf darf die Antwort nicht kosten.

    Auf Prod ist das der Normalfall und kein Randfall: Der Haushalts-Bereich
    steht dort hinter dem Umgebungs-Gate, die Tabellen entstehen leer und
    bleiben es. Jede der vierzehn Quellen muss das aushalten — deshalb hier
    zwei Fragen, die zusammen alle vier Neuzugänge ziehen."""
    store = CouncilStore(tmp_path / "leer.sqlite")
    for frage in ("Was kostet die Stadt insgesamt?",
                  "Wie viel Schulden hat Oldenburg, was wird gebaut, wie viele "
                  "Stellen sind unbesetzt und wer wollte den Haushalt ändern?"):
        kontext = qa.geld_kontext(store, frage, "", "geld")
        assert qa.geld_block(kontext) == "", frage
        assert qa.geld_regeln(kontext) == "", frage
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


#: Obergrenze je NEUEM Baustein, gemessen am 17.08. an einer Datenbank im
#: Zuschnitt des Prod-Bestands (die Werte in Klammern sind die Messung):
#:
#:     schulden       1.046   stellenplan    1.044
#:     investitionen    955   antraege       1.379
#:
#: Die Grenzen liegen bewusst knapp darüber. Sie sind keine Willkür, sondern
#: die Antwort auf Tims Frage „wie viel brauchen die neuen Bausteine wirklich,
#: BEVOR Du sie alle zuschaltest": Zusammen sind es rund 4.400 Zeichen — das
#: ganze Budget. Sie feuern nur nie zusammen (s. die Gegenrichtungs-Tests
#: oben), und genau deshalb ist der Deckel bei 4.500 geblieben.
NEUE_BAUSTEIN_GRENZEN = {
    "schulden": 1200,
    "stellenplan": 1200,
    "investitionen": 1100,
    "antraege": 1600,
}


@pytest.mark.parametrize("facette,grenze", sorted(NEUE_BAUSTEIN_GRENZEN.items()))
def test_neuer_baustein_bleibt_in_seiner_groesse(facette, grenze, tmp_path):
    """Jeder neue Baustein einzeln vermessen — wächst einer davon, fällt es
    hier auf und nicht erst, wenn er im Prompt die Beschlüsse verdrängt."""
    store = _befuellter_store(tmp_path)
    frage = {"schulden": "Wie viel Schulden hat Oldenburg?",
             "stellenplan": "Wie viele Stellen sind unbesetzt?",
             "investitionen": "Was wird gebaut?",
             "antraege": "Welche Änderungslisten gab es zum Haushalt 2026?"}[facette]
    kontext = qa.geld_kontext(store, frage, frage, "thema")
    schluessel, bauer = qa._GELD_BAUSTEINE[facette]
    text = bauer(kontext.get(schluessel))
    assert text, f"{facette} liefert nichts — Fixture verrutscht?"
    assert len(text) <= grenze, f"{facette}: {len(text)} Zeichen (Grenze {grenze})"
    store.close()


def test_echte_fragen_bleiben_weit_unter_dem_deckel(tmp_path):
    """Die Messung, die zählt: nicht der Vollausschlag, sondern was echte
    Fragen wirklich kosten.

    Gemessen am 17.08.: 616–1.755 Zeichen. Der Deckel bei 4.500 ist damit für
    den Normalfall keine Fessel — er greift erst bei Fragen, die ein halbes
    Dutzend Quellen auf einmal ziehen, und genau dafür ist er da."""
    store = _befuellter_store(tmp_path)
    for frage in ["Wie viel Schulden hat Oldenburg?",
                  "Was wird gebaut?",
                  "Wie viele Stellen sind unbesetzt?",
                  "Wer wollte den Haushalt 2026 ändern?",
                  "Wie viel gibt die Stadt für Personal aus?",
                  "Was kostet die Feuerwehr?",
                  "Warum kam so viel mehr Gewerbesteuer rein?"]:
        kontext = qa.geld_kontext(store, frage, frage, "thema")
        laenge = len(qa.geld_block(kontext))
        assert 0 < laenge <= 2200, f"„{frage}“: {laenge} Zeichen"
    store.close()


def test_die_neuen_facetten_verdraengen_die_alten_nicht_komplett(tmp_path):
    """Der Grund, warum `antraege` nicht vorn in GELD_FACETTEN steht.

    Zieht eine Frage alles, füllen allein die vier Neuzugänge das Budget
    (gemessen: 4.344 von 4.500 Zeichen) — mit ihnen an den ersten vier
    Plätzen blieb von den zehn älteren Quellen keine einzige übrig. Der
    Jahresabschluss aus einer Frage zu werfen, die ausdrücklich nach ihm
    fragt, wäre kein Zeichensparen, sondern ein Datenverlust."""
    store = _befuellter_store(tmp_path)
    kontext = qa.geld_kontext(
        store, "Warum kostet die Stadt insgesamt mehr als geplant, wie viele "
               "Schulden hat sie, was wird gebaut, wie viele Stellen sind "
               "unbesetzt, was hat das Rechnungsprüfungsamt beanstandet und wie "
               "ist das im Vergleich zu Osnabrück?",
        "Haushalt Soziales Theater Feuerwehr Steuern Schule", "geld")
    text = qa.geld_block(kontext)
    assert len(kontext["facetten"]) >= 10, sorted(kontext["facetten"])
    assert len(text) <= qa.GELD_MAX_CHARS
    # Die drei neuen Bestands-Quellen sind drin …
    for kopf in ("SCHULDENSTAND", "STELLENPLAN", "INVESTITIONEN"):
        assert kopf in text, kopf
    # … und mindestens zwei der älteren haben es ebenfalls geschafft.
    alt = sum(1 for kopf in ("GEPLANT UND TATSÄCHLICH", "WARUM DER PLAN NICHT AUFGING",
                             "RECHNUNGSPRÜFUNGSAMT", "AUFGABEN DER STADT")
              if kopf in text)
    assert alt >= 2, f"nur {alt} der älteren Quellen überlebten den Deckel"
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
    """Der Einzelweg haushalt=/steuern=/steuerkraft= bleibt bestehen.

    Die Deep-Research-Pipeline benutzt ihn seit dem 17.08. nicht mehr (sie
    ruft ``geld_kontext`` wie ``/ask``), aber der Parameter-Weg bleibt: Er ist
    die Rückfallebene für Aufrufer außerhalb des Routers, und ein stiller
    Verhaltenswechsel wäre der schlechtere Weg, ihn abzuräumen."""
    zeilen = [{"year": 2026, "bereich": "Verkehr und Straßenbau",
               "aufwendungen": 46194645.0, "ertraege": 17510637.0}]
    messages, _ = qa._answer_messages("Was kostet der Verkehr?", [], typ="geld",
                                      haushalt=zeilen)
    assert "STADTHAUSHALT" in messages[0]["content"]
    assert "46.194.645" in messages[0]["content"]


def test_deep_research_bekommt_denselben_geld_kontext(tmp_path):
    """Die „Gründliche Recherche" hing am Stand von vor der Facetten-Runde:
    drei fest verdrahtete Store-Aufrufe, also weder Schulden noch
    Investitionen, Stellenplan oder Änderungslisten.

    Geprüft wird beides — dass der lange Bericht die neuen Quellen jetzt sieht
    UND dass er die vier Haushalts-Regeln dazu bekommt. Die hingen bis dahin
    allein am Antwort-Prompt von ``/ask``; der Bericht bekam die Beträge ohne
    die Anweisung, Jahr und Quelle zu nennen."""
    store = _befuellter_store(tmp_path)
    kontext = qa.geld_kontext(store, "Wie viel Schulden hat Oldenburg?",
                              "Schulden Kredite", "thema")
    zusatz = qa.geld_regeln(kontext) + qa.geld_block(kontext)
    assert "SCHULDENSTAND" in zusatz
    assert "JAHR IMMER NENNEN" in zusatz and "PLAN IST NICHT IST" in zusatz
    # Die Regeln stehen VOR den Zahlen — ihr eigener Wortlaut verweist auf
    # „eigene Abschnitte unten".
    assert zusatz.index("eigene Abschnitte unten") < zusatz.index("SCHULDENSTAND")
    store.close()


def test_deepresearch_ruft_geld_kontext_statt_einzelquellen():
    """Der Verdrahtungstest: Ruft ``app/deepresearch.py`` wirklich die
    gebündelte Quelle — oder hängt es wieder an Einzelaufrufen?

    Am Quelltext gemessen und nicht an einem Lauf: Die Pipeline braucht einen
    Job, einen Thread und eine Datenbank, und der Befund („es fragt die
    falsche Stelle") steht schon in der Zeile."""
    from pathlib import Path

    quelle = (Path(__file__).resolve().parents[1] / "web" / "backend" / "app"
              / "deepresearch.py").read_text(encoding="utf-8")
    assert "qa.geld_kontext(" in quelle
    for alt in ("store.haushalt_fuer_begriffe", "store.steuern_fuer_begriffe",
                "store.steuerkraft_kontext"):
        assert alt not in quelle, f"{alt} hängt noch am alten Einzelweg"


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


def test_schuldenblock_nennt_alle_drei_abgrenzungen(tmp_path):
    """„Wie hoch sind die Schulden?" hat drei richtige Antworten.

    43,7 Mio. € (Kernhaushalt), 294,9 Mio. € (Rechtsträger mit Eigenbetrieben)
    und 740,3 Mio. € (Konzern mit Beteiligungen) — dieselbe Frage, dreimal
    anders abgegrenzt, ein Unterschied vom Siebzehnfachen. Bis zum 18.08.2026
    kannte der Baustein nur die mittlere; welche Zahl in der Antwort landete,
    entschied damit die Facette und nicht die Frage.

    Der Test hält außerdem die SPALTENNAMEN fest. Beide Abfragen stehen hinter
    einem `except sqlite3.OperationalError` — ein Tippfehler im Spaltennamen
    fiele sonst nie auf, sondern ließe die Zahl einfach weg (genau so passiert:
    `betrag` statt `insgesamt`).
    """
    from council import qa
    from council.store import CouncilStore

    store = CouncilStore(str(tmp_path / "c.sqlite"))
    c = store._conn                                       # noqa: SLF001
    c.execute("INSERT INTO council_schulden (jahr, insgesamt, je_einwohner, fetched_at) "
              "VALUES (2024, 294851000, 1673, '2026-08-18')")
    c.execute("INSERT INTO council_bilanz (jahr, rolle, seite, ebene, bezeichnung, wert, "
              " fetched_at) VALUES (2024, 'geldschulden', 'passiva', 2, 'Geldschulden', "
              " 43690972, '2026-08-18')")
    c.execute("INSERT INTO council_integrierte_schulden (jahr, ars, insgesamt, proben, "
              " fetched_at) VALUES (2024, '03403000', 740300000, '', '2026-08-18')")
    c.execute("INSERT INTO council_buergschaften (jahr, bestand, genau, aus_folgejahr, "
              " quelle, proben, fetched_at) "
              "VALUES (2024, 220300000, 1, 0, 'jahresabschluss', '', '2026-08-18')")
    c.commit()

    k = store.schulden_kontext()
    arten = {w["art"]: w["betrag"] for w in k["weitere"]}
    assert arten["Kernhaushalt (nur Geldschulden)"] == 43_690_972
    assert arten["Konzern Stadt (anteilig, mit Beteiligungen)"] == 740_300_000
    assert k["buergschaften"]["bestand"] == 220_300_000

    text = qa._schulden_block(k)
    for betrag in ("294.851.000", "43.690.972", "740.300.000", "220.300.000"):
        assert betrag in text, betrag
    # Und die Regel, ohne die drei Zahlen nebeneinander gefährlich sind.
    assert "NIE addieren" in text
    assert "KEINE Schuld" in text


def test_buergschaftsfragen_ziehen_die_schuldenquelle_ohne_oldenburg_zu_fangen():
    """„Wofür bürgt die Stadt?" — und „Oldenburg" enthält „burg".

    Die 220,3 Mio. €, für die die Stadt geradesteht, stehen in keiner der drei
    Schuldenreihen; ohne diese Wörter beantwortete die KI-Frage die Frage mit
    dem Ergebnishaushalt.

    Der Test hält vor allem die zwei Fallen fest, in die ein kurzes Muster
    läuft. `b[üu]rg` schlägt bei **Oldenburg** an — also bei fast jeder Frage
    dieses Projekts. Und weil `_falte` „ü" zu „ue" macht, beginnt
    „buergerinnen" genauso wie „buergschaft"; ein negativer Vorgriff auf „er"
    sperrt zwar die Bürger*innen aus, lässt „oldenburg" aber durch.
    """
    from council import qa

    for frage in ("Wofür bürgt die Stadt Oldenburg?",
                  "Wie hoch ist der Bürgschaftsbestand?",
                  "Für welche Kredite hat die Stadt sich verbürgt?",
                  "Welche Eventualverbindlichkeiten hat die Stadt?"):
        assert "schulden" in qa.geld_facetten(frage), frage

    for frage in ("Wie viele Bürgerinnen und Bürger hat Oldenburg?",
                  "Wie ist der Stand beim Bürgerbegehren?",
                  "Was ist in Oldenburg mit dem Stadion?",
                  "Wie viele Einwohner hat Oldenburg?"):
        assert "schulden" not in qa.geld_facetten(frage), frage
