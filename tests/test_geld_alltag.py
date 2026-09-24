"""Lotti versteht Haushaltsfragen in Alltagssprache.

Anlass (24.09.2026): 36 Laienfragen durch Lottis echtes Fenster. Rund die
Hälfte half zu wenig — nicht wegen falscher Zahlen, sondern weil die Zahl
gar nicht im Prompt stand: Die Facetten erkannten Fachwörter, die Produkt-
und Teilhaushalts-Suche hing an „Stadt" (→ STADTplanung), und die Seite
selbst gab ihre Kernzahlen nicht mit. Drei Bausteine halten die Reparatur:

* ``council/geld/alltag.py`` — Wortfelder der Alltagssprache → Facetten und
  Suchbegriffe in der Sprache der Quellen;
* ``geld.ALLERWELT`` — Wörter, die nie einen Teilhaushalt oder ein Produkt
  auswählen dürfen;
* ``assistant.SEITEN_KERN`` — je Haushaltsseite die Kernzahlen, hinter der
  Frage und mit eigenem Deckel.

Dazu die Weiche ins Archiv für die Preisfrage nach einem Vorhaben
(``assistant.projekt_ins_archiv``).
"""
from __future__ import annotations

import pytest

from council import assistant as lotti
from council import qa
from council.geld import alltag
from council.store import CouncilStore
from kern import knowledge

#: Die 36 Fragen aus dem Befund, wie sie im Fenster gestellt wurden.
LAIENFRAGEN = [
    ("/haushalt", "wie viele schulden hat die stadt"),
    ("/haushalt", "was gibt die stadt eigentlich so aus"),
    ("/haushalt", "hat die stadt genug geld"),
    ("/haushalt", "wo kann die stadt sparen"),
    ("/haushalt", "warum ist die stadt pleite"),
    ("/haushalt", "wieviel geld hat oldenburg im jahr"),
    ("/haushalt", "was kostet mich die stadt pro jahr"),
    ("/haushalt", "wofür geht das meiste geld drauf"),
    ("/haushalt", "was ist ein haushalt überhaupt"),
    ("/haushalt", "kann sich die stadt das neue stadion leisten"),
    ("/haushalt/schulden", "ist das schlimm?"),
    ("/haushalt/schulden", "ist das viel oder wenig"),
    ("/haushalt/schulden", "wer muss das alles zurückzahlen"),
    ("/haushalt/schulden", "wann sind die schulden weg"),
    ("/haushalt/schulden", "warum macht die stadt überhaupt schulden"),
    ("/haushalt/schulden", "wie hoch sind die schulen pro einwohner"),
    ("/haushalt/einnahmen", "woher hat die stadt ihr geld"),
    ("/haushalt/einnahmen", "zahlen wir zu viele steuern"),
    ("/haushalt/einnahmen", "bekommt die stadt geld vom land"),
    ("/haushalt/investitionen", "was wird gebaut"),
    ("/haushalt/investitionen", "wird was für schulen gemacht"),
    ("/haushalt/investitionen", "warum dauern die baustellen immer so lange"),
    ("/haushalt/pflicht", "was muss die stadt bezahlen und was nicht"),
    ("/haushalt/pflicht", "könnte man nicht einfach das theater streichen"),
    ("/haushalt/produkte", "was kostet die feuerwehr"),
    ("/haushalt/produkte", "wie viel geld geht in kitas"),
    ("/haushalt/personal", "wie viele leute arbeiten bei der stadt"),
    ("/haushalt/personal", "sind das nicht zu viele"),
    ("/haushalt/plan-ist", "hat die stadt mehr ausgegeben als geplant"),
    ("/haushalt/konzern", "was sind eigenbetriebe"),
    ("/haushalt/konzern", "verdient die stadt mit den bädern geld"),
    ("/haushalt/vergleich", "sind wir ärmer als osnabrück"),
    ("/haushalt/steuer", "warum ist die grundsteuer so hoch"),
    ("/haushalt/mitreden", "kann ich mitbestimmen wofür das geld ausgegeben wird"),
    ("/haushalt", "stimmt es dass für kitas kein geld mehr da ist"),
    ("/haushalt", "was bedeutet defizit"),
]

#: Was die FRAGE jetzt zieht, und was sie am 24.09.2026 nicht zog (gemessen
#: mit ``qa.geld_facetten`` vor dieser Änderung).
FEHLTE = {
    "wieviel geld hat oldenburg im jahr": {"plan"},               # vorher: nichts
    "hat die stadt genug geld": {"plan", "ist"},
    "woher hat die stadt ihr geld": {"ansatz", "taxes"},
    "bekommt die stadt geld vom land": {"ansatz", "ausgleich"},
    "was wird gebaut": {"measures", "investitionen", "gebaut"},
    "warum dauern die baustellen immer so lange": {"investitionen", "measures"},
    "verdient die stadt mit den bädern geld": {"business_plans"},
    "wie viel geld geht in kitas": {"produkte"},
    "stimmt es dass für kitas kein geld mehr da ist": {"produkte"},
    "könnte man nicht einfach das theater streichen": {"produkte"},
    "zahlen wir zu viele steuern": {"taxes", "vergleich"},
    "was kostet mich die stadt pro jahr": {"plan", "population"},
}


@pytest.mark.parametrize("frage, erwartet", sorted(FEHLTE.items()))
def test_alltagsfragen_ziehen_ihre_quellen(frage, erwartet):
    assert erwartet <= qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("route, frage", LAIENFRAGEN)
def test_wortfelder_nennen_nur_bekannte_facetten(route, frage):
    """Ein Tippfehler in einer Facette wäre dauerhaft wirkungslos und sähe
    aus wie „die Quelle hat nichts"."""
    assert alltag.facetten(qa._falte(frage)) <= set(qa.GELD_FACETTEN)


def test_jede_zeile_hat_einen_namen_und_trifft_etwas():
    namen = [w.name for w in alltag.WORTFELDER]
    assert len(namen) == len(set(namen))
    getroffen = {w.name for _r, f in LAIENFRAGEN for w in alltag.treffer(qa._falte(f))}
    # Jede Zeile ist an mindestens einer echten Laienfrage gemessen.
    assert getroffen == set(namen)


@pytest.mark.parametrize("frage", [
    # Aus dem Korpus der KI-Frage: Diese Fragen dürfen durch die Wortfelder
    # keinen Plan bekommen (tests/test_qa_geldquellen.py pinnt sie).
    "Wie viel Geld ist 2024 tatsächlich geflossen?",
    "Wie ist der Stand beim Stadion?",
    "Wie viele Schulden hat die Stadt pro Kopf?",
    # Kein Bad im Badezimmer, kein Land im Landkreis-Beschluss.
    "Wer hat das Badezimmer im Rathaus saniert?",
    "Was hat der Landkreis beschlossen?",
])
def test_wortfelder_bleiben_eng(frage):
    assert not ({"plan", "business_plans", "ausgleich"} & alltag.facetten(qa._falte(frage)))


def test_kita_sucht_unter_dem_namen_des_produkts():
    assert "Kindertagesbetreuung" in alltag.begriffe(qa._falte("Was kosten die Kitas?"))


# ---------------------------------------------------------------------------
# Allerweltswörter: „Stadt" wählt keinen Teilhaushalt
# ---------------------------------------------------------------------------

def _store(tmp_path) -> CouncilStore:
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, citation, probe, "
            "as_of, fetched_at) VALUES (1, 'k1', 'plan', 'Beschlossener Haushaltsplan 2026', "
            "'https://example.org/hh', 'Übersicht Ergebnishaushalt', 'sum_check', "
            "'Haushaltsjahr 2026', '2026-09-01')")
        for area, ertrag, aufwand, summe in (
                ("Summe", 812.9e6, 883.9e6, 1),
                ("Soziales und Gesundheit", 169.9e6, 283.1e6, 0),
                ("Jugend und Familie", 39.3e6, 169.2e6, 0),
                ("Stadtplanung", 0.6e6, 7.4e6, 0)):
            store._conn.execute(
                "INSERT INTO council_budget (year, area, revenues, expenses, result, is_total, "
                "source_url, fetched_at, herkunft_id) VALUES (2026, ?, ?, ?, ?, ?, "
                "'https://example.org/hh', '2026-09-01', 1)",
                (area, ertrag, aufwand, ertrag - aufwand, summe))
    return store


def test_stadt_trifft_nicht_die_stadtplanung(tmp_path):
    store = _store(tmp_path)
    try:
        # Die Laienfrage UND die Überschrift der Übersicht, wie Lotti sie sucht.
        begriffe = ("was gibt die Stadt eigentlich so aus Oldenburg plant Ausgaben "
                    "von 883,9 Millionen Euro").split()
        assert store.haushalt_fuer_begriffe(begriffe) == []
        # „Stadtplanung" selbst trifft weiterhin.
        assert [r["area"] for r in store.haushalt_fuer_begriffe(["Stadtplanung"])] == ["Stadtplanung"]
    finally:
        store.close()


def test_plan_zeilen_tragen_ihren_beleg(tmp_path):
    store = _store(tmp_path)
    try:
        zeilen = store.haushalt_fuer_begriffe(["haushalt", "meisten"])
        assert zeilen[0]["area"] == "Summe" and zeilen[1]["rang"] == 1
        block = qa._haushalt_block(zeilen)
        assert "Summe (2026): Aufwendungen 883.900.000 €" in block
        # Die Fundstelle EINMAL, nicht je Zeile.
        assert block.count("Beleg: Beschlossener Haushaltsplan 2026") == 1
        assert qa.geld_belege({"haushalt": zeilen, "facets": ["plan"]})[0]["label"] \
            == "Beschlossener Haushaltsplan 2026"
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Seiten-Kernzahlen
# ---------------------------------------------------------------------------

def test_jede_lesbare_haushaltsseite_hat_kernzahlen():
    ohne = {"/haushalt/bereich"}   # Der Teilhaushalt steht schon als Überschrift da.
    seiten = {r for r, k in knowledge.PAGES.items() if knowledge.im_haushalt(r)}
    assert seiten - set(lotti.SEITEN_KERN) == ohne
    for route, kern in lotti.SEITEN_KERN.items():
        assert kern.facetten and kern.facetten <= set(qa.GELD_FACETTEN), route


def test_steuer_steckbrief_nimmt_seine_steuer():
    kern = lotti.seiten_kern(lotti.Screen(route="/haushalt/steuer", refs={"area": "grundsteuer"}))
    assert kern is not None and kern.begriffe == "Grundsteuer"


def _baustein(name):
    return lambda d: f"[{name}:{d}]" if d else ""


def test_kern_steht_hinter_der_frage_und_hat_eigenen_deckel(monkeypatch):
    bausteine = {f: (f, _baustein(f)) for f in qa.GELD_FACETTEN}
    monkeypatch.setattr(qa, "_GELD_BAUSTEINE", bausteine)
    geld = {"schulden": "s" * 50, "stellenplan": "k" * 50, "measures": "m" * 500,
            "vergleich": "v" * 50, "vorrang": ["vergleich"],
            "kern": ["stellenplan", "measures"], "kern_max": 100}
    keys = [k for k, _t in qa.geld_auswahl(geld, 10_000)]
    # Frage zuerst, dann der Kern (der zu große Kern-Baustein fällt aus, OHNE
    # die Schleife zu beenden), dann der Rest.
    assert keys == ["vergleich", "stellenplan", "schulden"]


def test_kern_ergaenzt_die_frage_und_ueberschreibt_sie_nicht():
    frage = {"facets": ["produkte", "plan"], "produkte": {"x": 1},
             "haushalt": [{"area": "Jugend und Familie"}]}
    kern = {"facets": ["plan", "produkte"], "produkte": {"y": 2},
            "haushalt": [{"area": "Summe"}, {"area": "Jugend und Familie", "rang": 2}]}
    neu = lotti._kern_dazu(frage, kern)
    assert neu["produkte"] == {"x": 1}
    assert [r["area"] for r in neu["haushalt"]] == ["Jugend und Familie", "Summe"]
    assert neu["kern"] == ["plan", "produkte"] and neu["kern_max"] == lotti.KERN_MAX


# ---------------------------------------------------------------------------
# Preisfrage nach einem Vorhaben → Archiv (geprüft am Bestand)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("frage, erwartet", [
    ("kann sich die stadt das neue stadion leisten", ("stadion", True)),
    ("Was kostet das neue Stadion?", ("stadion", True)),
    ("Was kostet die Feuerwehr?", ("feuerwehr", False)),
    ("Wie teuer wird der Umbau?", ("umbau", True)),
    ("Kann sich die Stadt das leisten?", None),
    ("Was kostet das hier?", None),
    ("was kostet mich die stadt pro jahr", None),
])
def test_vorhaben_aus_dem_wortlaut(frage, erwartet):
    assert lotti.projekt_vorhaben(frage) == erwartet


class _ArchivStore:
    def __init__(self, betraege: dict[str, int], produkte: set[str]):
        self.betraege, self.produkte = betraege, produkte

    def beschluesse_mit_betrag(self, wort):
        return self.betraege.get(wort, 0)

    def produkte_fuer_begriffe(self, begriffe):
        return {"produkte": [1]} if set(begriffe) & self.produkte else None


@pytest.mark.parametrize("frage, ins_archiv", [
    # 26 Beschlüsse mit Betrag zum Stadion, keine Aufgabe im Haushalt.
    ("kann sich die stadt das neue stadion leisten", True),
    ("Was kostet das Stadion?", True),
    # Die Feuerwehr ist eine Aufgabe mit Kosten in der Produktebene.
    ("Was kostet die Feuerwehr?", False),
    # Kitas kennt das Wortfeld — sie gehören in den Haushalt.
    ("Kann sich die Stadt die neuen Kitas leisten?", False),
    # Ohne Beschlüsse mit Betrag weiß das Archiv nicht mehr.
    ("Was kostet das neue Planetarium?", False),
])
def test_projektfrage_geht_nur_mit_beleg_ins_archiv(frage, ins_archiv):
    store = _ArchivStore({"stadion": 26, "feuerwehr": 12, "kitas": 5}, {"feuerwehr"})
    assert lotti.projekt_ins_archiv(store, lotti.Screen(route="/haushalt"), frage) is ins_archiv


def test_projektfrage_auf_einer_beschluss_seite_bleibt_beim_bildschirm():
    store = _ArchivStore({"stadion": 26}, set())
    screen = lotti.Screen(route="/beschluss", refs={"decision_id": 1})
    assert not lotti.projekt_ins_archiv(store, screen, "Was kostet das neue Stadion?")
