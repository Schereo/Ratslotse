"""Der Haushalts-Bereich zieht neue Jahrgänge selbst nach.

Geprüft wird der Cron ``scripts/check_finanzdaten.py`` gegen eine Datenbank,
in der ein Jahrgang künstlich fehlt — und zwar auf die drei Eigenschaften, die
ihn unbeaufsichtigt tragen:

1. Er **holt nach**, was fehlt (und findet den Jahrgang über das Dokument,
   nicht über den Kalender).
2. Er **tut beim zweiten Mal nichts** — verglichen wird der komplette
   Tabelleninhalt, nicht bloß eine Kennzahl.
3. Er **verliert nichts**. Was eine Pflicht-Probe reißt, kommt nicht herein;
   was schon in der Tabelle steht, wird nicht gegen ein leeres oder
   geschrumpftes Parse-Ergebnis getauscht.

Die Fixtures sind im Layout der echten Jahresabschlüsse ab 2019 gebaut
(dieselben Spalten, dieselbe Schreibweise der Summenzeilen), aber mit
gerechneten Zahlen — so lässt sich ein Jahrgang gezielt kaputtmachen, ohne
einen 400.000-Zeichen-Extrakt ins Repo zu legen.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from council import finanzquellen  # noqa: E402
from council.store import CouncilStore  # noqa: E402

# `scripts/` ist kein Paket — dieselbe Ladeweise wie in test_render_plaene.py.
_spec = importlib.util.spec_from_file_location(
    "check_finanzdaten", ROOT / "scripts" / "check_finanzdaten.py")
check_finanzdaten = importlib.util.module_from_spec(_spec)
sys.modules["check_finanzdaten"] = check_finanzdaten
_spec.loader.exec_module(check_finanzdaten)


# --- Fixtures ---------------------------------------------------------------

def eur(x: float) -> str:
    """Deutsche Schreibweise, wie sie im PDF-Extrakt steht."""
    return f"{x:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")


def jahresabschluss(jahr: int, e_plan: float, e_ist: float,
                    a_plan: float, a_ist: float,
                    ve: float, va: float, mit_thh: bool = True) -> str:
    """Ein Jahresabschluss-Extrakt, der alle vier Proben besteht.

    ``ve``/``va`` sind die Ist-Werte des Vorjahres (Posten 12 und 20) — sie
    stehen in der Vorjahresspalte und schließen damit die Kette zum
    Vorgängerjahrgang."""
    r_plan, r_ist, r_vor = e_plan - a_plan, e_ist - a_ist, ve - va
    text = f"""3.1 Ergebnisrechnung Kernverwaltung
Erträge und Aufwendungen Ergebnis des
Vorjahres
{jahr - 1}
Ansätze des
Haushaltsjahres
{jahr}
Veränderung
durch Nachtrag
Ergebnis des
Haushaltsjahres
{jahr}
mehr (+) /
weniger (-)4)
{jahr}
 - Euro -
1 2 3 4 5 6 7
ordentliche Erträge
01. Steuern und ähnliche Abgaben {eur(ve * 0.4)} {eur(e_plan * 0.4)}  {eur(e_ist * 0.4)} {eur(e_ist * 0.4 - e_plan * 0.4)}
12. = Summe ordentliche Erträge {eur(ve)} {eur(e_plan)}  {eur(e_ist)} {eur(e_ist - e_plan)}
ordentliche Aufwendungen
13. Personalaufwendungen {eur(va * 0.2)} {eur(a_plan * 0.2)}  {eur(a_ist * 0.2)} {eur(a_ist * 0.2 - a_plan * 0.2)}
20. = Summe ordentliche
Aufwendungen {eur(va)} {eur(a_plan)}  {eur(a_ist)} {eur(a_ist - a_plan)}
21. ordentliches Ergebnis {eur(r_vor)} {eur(r_plan)}  {eur(r_ist)} {eur(r_ist - r_plan)}
"""
    if mit_thh:
        # Ein einziger Teilhaushalt, der die Gesamtrechnung trägt — so geht
        # die Summenprobe auf, ohne zwölf Blöcke zu erfinden.
        text += f"""
A. Teil-Ergebnisrechnung   THH01 Verwaltungsführung
Erträge und Aufwendungen Ergebnis des
Vorjahres
{jahr - 1}
Ansätze des
Haushaltsjahres
{jahr}
Veränderung
durch Nachtrag
Ergebnis des
Haushaltsjahres
{jahr}
mehr (+) /
weniger (-)4)
{jahr}
 - Euro -
1 2 3 4 5 6 7
Ordentliche Erträge
12. =Summe ordentliche Erträge {eur(ve)} {eur(e_plan)}  {eur(e_ist)} {eur(e_ist - e_plan)}
Ordentliche Aufwendungen
20. =Summe ordentliche Aufwendungen {eur(va)} {eur(a_plan)}  {eur(a_ist)} {eur(a_ist - a_plan)}
"""
    return text


#: Drei aufeinanderfolgende Jahrgänge; die Vorjahresspalte jedes Jahres trägt
#: das Ist des Vorgängers, damit die Vorjahres-Kette schließt.
JAHRGAENGE = {
    2023: dict(e_plan=664_000_000.0, e_ist=732_000_000.0,
               a_plan=674_000_000.0, a_ist=683_000_000.0,
               ve=696_000_000.0, va=661_000_000.0),
    2024: dict(e_plan=693_000_000.0, e_ist=799_000_000.0,
               a_plan=727_000_000.0, a_ist=764_000_000.0,
               ve=732_000_000.0, va=683_000_000.0),
    2025: dict(e_plan=710_000_000.0, e_ist=815_000_000.0,
               a_plan=750_000_000.0, a_ist=790_000_000.0,
               ve=799_000_000.0, va=764_000_000.0),
}


def teilhaushalt_plan(thh_nr: int, thh_name: str, produkte: list[tuple],
                      jahr: int) -> str:
    """Ein Teilhaushalts-Plan im Layout der echten Dokumente.

    Die Beträge stehen in **deutscher** Schreibweise mit Tausenderpunkt — so
    stehen sie im PDF-Extrakt, und nur so liest ``_thh_zahlen`` sie als eine
    Zahl. „6900" zerfiele dort in 690 und 0."""
    text = ""
    for produkt_nr, name, amt, ertraege, aufwendungen in produkte:
        ergebnis = ertraege - aufwendungen
        text += (
            f"Teilergebnishaushalt THH{thh_nr:02d}: {thh_name}\n"
            f"Produkt: {name} ({produkt_nr})\n"
            f"{amt}\n"
            f"Erträge und Aufwendungen Ergebnis {jahr - 1}\n- Euro -\n"
            f"Ansatz {jahr}\n- Euro -\nAnsatz {jahr + 1}\n- Euro -\n"
            f"12. = Summe ordentliche Erträge {eur(ertraege - 100)} {eur(ertraege)}"
            f" {eur(ertraege + 50)}\n"
            f"20. = Summe ordentliche Aufwendungen {eur(aufwendungen - 100)}"
            f" {eur(aufwendungen)} {eur(aufwendungen + 50)}\n"
            f"21. ordentliches Ergebnis {eur(ergebnis - 0)} {eur(ergebnis)}"
            f" {eur(ergebnis - 50)}\n"
            "Kurzbeschreibung:\n")
    return text


#: Vier Teilhaushalte eines Jahrgangs — so wie sie im Bestand liegen: als vier
#: getrennte Anlagen, die einzeln und zu verschiedenen Zeiten lesbar werden.
THH_PLAENE = {
    1: ("Verwaltungsführung", [("P11.100", "Ratsangelegenheiten", "Amt 10", 4_000.0, 9_000.0),
                               ("P11.101", "Presse", "Amt 10", 1_000.0, 3_000.0)]),
    2: ("Finanzen", [("P12.200", "Kämmerei", "Amt 20", 5_000.0, 12_000.0)]),
    3: ("Jugend", [("P36.300", "Kitas", "Amt 51", 2_000.0, 80_000.0)]),
    4: ("Kultur", [("P25.400", "Museen", "Amt 41", 300.0, 7_000.0)]),
}


def anlage(store: CouncilStore, document_id: int, label: str,
           text: str, n_pages: int = 300) -> None:
    with store._conn:  # noqa: SLF001
        store._conn.execute(  # noqa: SLF001
            "INSERT OR REPLACE INTO council_anlagen "
            "(document_id, kvonr, label, url, raw_text, n_pages, fetched_at, status) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (document_id, 1, label, f"https://example.org/{document_id}.pdf",
             text, n_pages, "2026-08-10T00:00:00", "ok"))


@pytest.fixture()
def bestand(tmp_path):
    """Council-DB mit drei Jahresabschlüssen als Anlage — noch nichts eingelesen."""
    store = CouncilStore(tmp_path / "council.sqlite")
    for i, (jahr, werte) in enumerate(sorted(JAHRGAENGE.items())):
        anlage(store, 100 + i, f"15 Jahresabschluss {jahr} Stadt Oldenburg",
               jahresabschluss(jahr, **werte))
    return store


@pytest.fixture()
def thh_bestand(tmp_path):
    """Council-DB mit vier Teilhaushalts-Plänen **eines** Jahrgangs (2027).

    Zwei davon tragen noch keinen Volltext — die Ausgangslage im Betrieb:
    ``check_protocols`` legt die Anlage mit ``n_pages=0`` und ``status='listed'``
    an, den Text holt ``backfill_anlagen_texte.py`` später und tranchenweise."""
    store = CouncilStore(tmp_path / "council.sqlite")
    for i, (nr, (name, produkte)) in enumerate(sorted(THH_PLAENE.items())):
        anlage(store, 500 + i,
               f"2028 {7 + i:03d} Vw THH{nr:02d} Haushalt 2028 Verwaltungsentwurf",
               teilhaushalt_plan(nr, name, produkte, 2027))
    with store._conn:  # noqa: SLF001
        store._conn.execute(  # noqa: SLF001
            "UPDATE council_anlagen SET raw_text = '', n_pages = 0, status = 'listed' "
            "WHERE document_id IN (502, 503)")
    return store


def produkt_einheiten(store: CouncilStore) -> list[tuple]:
    """(Jahr, Teilhaushalt) — die Einheiten, in denen die Produkte hereinkommen."""
    return sorted(tuple(r) for r in store._conn.execute(  # noqa: SLF001
        "SELECT DISTINCT jahr, thh_nr FROM council_produkte"))


def inhalt(store: CouncilStore) -> dict:
    """Kompletter Inhalt der Zieltabellen ohne ``fetched_at`` — die Grundlage
    für „der zweite Lauf tut nichts". Eine Kennzahl zu vergleichen genügte
    nicht: Ein Lauf, der jede Zeile identisch neu schreibt, sähe daran gleich
    aus."""
    aus = {}
    for tabelle in ("council_ergebnisrechnung", "council_abweichungsgruende",
                    "council_produkte", "council_pruefberichte",
                    "council_pruefbericht_quellen"):
        rows = store._conn.execute(f"SELECT * FROM {tabelle}").fetchall()  # noqa: SLF001
        aus[tabelle] = sorted(
            repr({k: r[k] for k in r.keys() if k != "fetched_at"}) for r in rows)
    return aus


# --- Die Quellendefinition --------------------------------------------------

def test_erkennung_ist_eine_quelle_fuer_skript_und_cron():
    """Label-Muster, Mindestseitenzahl und Ausschlüsse stehen an genau einer
    Stelle — sonst gäbe es zwei Antworten auf „ist das ein Jahresabschluss?"."""
    e = finanzquellen.QUELLEN["jahresabschluss"].erkennung
    wo, werte = e.where()
    assert "label LIKE ?" in wo and "n_pages > ?" in wo
    assert wo.count("label NOT LIKE ?") == 2
    assert werte == ["%Jahresabschluss%", 100, "%Rechenschaft%", "%Schlussbericht%"]


def test_rechenschaftsbericht_und_schlussbericht_sind_keine_jahresabschluesse(bestand):
    """Beide tragen dieselbe Jahreszahl im Titel und sind ein anderes Dokument."""
    anlage(bestand, 200, "15 Rechenschaftsbericht 2025 Stadt Oldenburg", "x")
    anlage(bestand, 201, "Schlussbericht zum Jahresabschluss 2025", "x")
    anlage(bestand, 202, "Jahresabschluss 2025 Auszug", "x", n_pages=4)

    gefunden = {r["document_id"] for r in
                finanzquellen.QUELLEN["jahresabschluss"].kandidaten(bestand)}
    assert gefunden == {100, 101, 102}


def test_teilhaushalt_jahrgang_kommt_aus_der_ansatzspalte():
    """Der Plan „2024 … THH01" ist der Haushaltsplan 2024, seine erste
    Ansatzspalte trägt aber 2023 — und genau die übernimmt der Parser. Wer
    hier das Label läse, suchte einen Jahrgang, den die Tabelle nie liefert."""
    kopf = ("Teilergebnishaushalt THH01: Verwaltungsführung\n"
            "Erträge und Aufwendungen Ergebnis 2022\n- Euro -\nAnsatz 2023\n"
            "- Euro -\nAnsatz 2024\n- Euro -\n")
    assert finanzquellen.teilhaushalt_jahrgang(kopf) == 2023
    assert finanzquellen.teilhaushalt_jahrgang("ohne Tabelle") is None


def test_teilhaushalt_nummer_aus_dem_label():
    """Die zweite Hälfte des Schlüssels. Die Schreibweise schwankt über die
    Jahrgänge — führende Null, Leerzeichen, Präfixe davor."""
    for label, erwartet in (("007 THH01", 1), ("2024 007 IVw THH01", 1),
                            ("TOP 5 - Anlage III - THH 08", 8),
                            ("2019 THH 08", 8), ("THH11", 11),
                            ("Anlage 4 THH11", 11), ("ohne Nummer", None)):
        assert finanzquellen.teilhaushalt_nummer(label) == erwartet


def test_einheit_eines_teilhaushalts_plans_ist_der_teilhaushalt():
    """Nicht der Jahrgang: Ein Produkt-Jahrgang verteilt sich auf rund neun
    Anlagen. Wer den Jahrgang als Einheit führt, sperrt ihn nach dem ersten
    Dokument und verliert die anderen acht."""
    q = finanzquellen.QUELLEN["teilhaushalt"]
    row = {"label": "2028 010 Vw THH04 Haushalt 2028 Verwaltungsentwurf",
           "kopf": "Erträge und Aufwendungen Ergebnis 2026\nAnsatz 2027\nAnsatz 2028\n"}
    assert q.einheiten_von(row) == {(2027, 4)}
    assert q.einheit == "Teilhaushalte"


# --- Die gemeinsame Ursache: Bestand je Einheit, nicht je Jahr ---------------

def test_nachgereichter_volltext_wird_beim_naechsten_lauf_gelesen(thh_bestand):
    """Der Fall aus dem Betrieb, und der teuerste: Zwei von vier
    Teilhaushalts-Plänen tragen beim ersten Lauf noch keinen Volltext (sie
    fallen durch den Mindestseiten-Filter). Kommt er später — durch
    ``backfill_anlagen_texte.py``, das wöchentlich eine Tranche nachzieht —,
    muss der nächste Lauf sie holen.

    Mit einem Bestand je **Jahrgang** passiert das nie: Der Jahrgang steht
    nach Lauf 1 in der Tabelle und gilt für immer als erledigt. Gemeldet
    würde auch nichts, denn ``ueberfaellig`` fragt nach Jahrgängen."""
    p = finanzquellen.Protokoll(still=True)
    lauf1 = finanzquellen.lies_teilhaushalte(thh_bestand, p, nur_fehlende=True)
    assert produkt_einheiten(thh_bestand) == [(2027, 1), (2027, 2)]
    assert lauf1["neue_einheiten"] == [(2027, 1), (2027, 2)]
    assert lauf1["neue_jahrgaenge"] == [2027]

    # Der Handlauf zieht die beiden fehlenden PDFs nach.
    for document_id, nr in ((502, 3), (503, 4)):
        name, produkte = THH_PLAENE[nr]
        with thh_bestand._conn:  # noqa: SLF001
            thh_bestand._conn.execute(  # noqa: SLF001
                "UPDATE council_anlagen SET raw_text = ?, n_pages = 300, status = 'ok' "
                "WHERE document_id = ?", (teilhaushalt_plan(nr, name, produkte, 2027),
                                          document_id))

    p2 = finanzquellen.Protokoll(still=True)
    lauf2 = finanzquellen.lies_teilhaushalte(thh_bestand, p2, nur_fehlende=True)
    # Zuerst der Bestand selbst: DAS ist der Befund. (Ohne die Korrektur steht
    # hier weiter nur [(2027, 1), (2027, 2)] — der Jahrgang gilt als erledigt.)
    assert produkt_einheiten(thh_bestand) == [(2027, 1), (2027, 2), (2027, 3), (2027, 4)]
    assert lauf2["neue_einheiten"] == [(2027, 3), (2027, 4)]

    # Und erst jetzt ist Ruhe.
    vorher = inhalt(thh_bestand)
    p3 = finanzquellen.Protokoll(still=True)
    lauf3 = finanzquellen.lies_teilhaushalte(thh_bestand, p3, nur_fehlende=True)
    try:
        assert lauf3["neue_einheiten"] == []
        assert inhalt(thh_bestand) == vorher
    finally:
        thh_bestand.close()


def test_cron_zieht_den_nachgereichten_teilhaushalt_nach(thh_bestand, tmp_path):
    """Dasselbe durch den Cron hindurch — dort stand das Jahres-Gate, das
    ``einlesen`` gar nicht erst aufrief."""
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_teilhaushalte(thh_bestand, p, nur_fehlende=True)
    for document_id, nr in ((502, 3), (503, 4)):
        name, produkte = THH_PLAENE[nr]
        with thh_bestand._conn:  # noqa: SLF001
            thh_bestand._conn.execute(  # noqa: SLF001
                "UPDATE council_anlagen SET raw_text = ?, n_pages = 300, status = 'ok' "
                "WHERE document_id = ?", (teilhaushalt_plan(nr, name, produkte, 2027),
                                          document_id))
    thh_bestand.close()

    bericht = check_finanzdaten.main(db=str(tmp_path / "council.sqlite"),
                                     heute=date(2028, 12, 1), still=True)

    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        assert produkt_einheiten(store) == [(2027, 1), (2027, 2), (2027, 3), (2027, 4)]
    finally:
        store.close()
    assert bericht["Neue Einheiten"] == 2


def test_fehlende_teilhaushalts_ebene_wird_nachgezogen(bestand, tmp_path):
    """Ein Jahresabschluss trägt zwei Ebenen. Die Summenprobe kann die zweite
    verwerfen, während die erste steht — dann ist der Jahrgang in der Tabelle,
    aber halb. ``ergebnisrechnung_jahre()`` („irgendeine Zeile") hielte ihn
    für fertig."""
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_jahresabschluesse(bestand, p)
    vollstaendig = inhalt(bestand)

    # Der Zustand nach einem Lauf, in dem nur die Teilhaushalte scheiterten.
    with bestand._conn:  # noqa: SLF001
        bestand._conn.execute(  # noqa: SLF001
            "DELETE FROM council_ergebnisrechnung WHERE jahr = 2024 AND thh_nr IS NOT NULL")
        bestand._conn.execute(  # noqa: SLF001
            "DELETE FROM council_abweichungsgruende WHERE jahr = 2024")
    assert 2024 in bestand.ergebnisrechnung_jahre(), "die Gesamtrechnung steht noch"
    assert 2024 not in bestand.plan_ist_jahre()
    bestand.close()

    bericht = check_finanzdaten.main(db=str(tmp_path / "council.sqlite"),
                                     heute=date(2026, 8, 16), still=True)

    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        # Ohne die Korrektur bleibt 2024 für immer ohne Teilhaushalte.
        assert 2024 in store.plan_ist_jahre()
        # Die Erläuterungen reiten mit: Sie hängen am selben Dokument.
        assert inhalt(store) == vollstaendig
    finally:
        store.close()
    assert bericht["Neue Einheiten"] == 1


# --- Der Lauf ---------------------------------------------------------------

def test_holt_den_fehlenden_jahrgang_nach(bestand, tmp_path):
    """Erst alles einlesen, dann einen Jahrgang löschen — der Job zieht ihn
    zurück, ohne dass ihm jemand sagt, welcher es ist."""
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_jahresabschluesse(bestand, p)
    assert bestand.ergebnisrechnung_jahre() == [2023, 2024, 2025]
    vollstaendig = inhalt(bestand)

    with bestand._conn:  # noqa: SLF001
        bestand._conn.execute(  # noqa: SLF001
            "DELETE FROM council_ergebnisrechnung WHERE jahr = 2024")
    assert bestand.ergebnisrechnung_jahre() == [2023, 2025]
    bestand.close()

    bericht = check_finanzdaten.main(db=str(tmp_path / "council.sqlite"),
                                     heute=date(2026, 8, 16), still=True)
    assert bericht["Neue Jahrgänge"] == 1
    assert bericht["Jahresabschluss"] == "2024"

    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        assert store.ergebnisrechnung_jahre() == [2023, 2024, 2025]
        # Bit für Bit derselbe Stand wie vor dem Löschen — nicht bloß „wieder da".
        assert inhalt(store) == vollstaendig
    finally:
        store.close()


def test_zweiter_lauf_aendert_nichts(bestand, tmp_path):
    bestand.close()
    db = str(tmp_path / "council.sqlite")
    check_finanzdaten.main(db=db, heute=date(2026, 8, 16), still=True)

    store = CouncilStore(tmp_path / "council.sqlite")
    vorher = inhalt(store)
    store.close()

    bericht = check_finanzdaten.main(db=db, heute=date(2026, 8, 16), still=True)
    assert bericht["Neue Jahrgänge"] == 0

    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        assert inhalt(store) == vorher
    finally:
        store.close()


def test_dokument_das_die_probe_reisst_kommt_nicht_herein(bestand, tmp_path):
    """Die Strukturprobe (12 − 20 = 21) ist keine Formalie: Sie ist der
    Unterschied zwischen einer gelesenen und einer geratenen Tabelle. Ein
    automatischer Lauf darf sie nicht lockern — er ist der Grund, warum sie
    existiert."""
    kaputt = jahresabschluss(2026, e_plan=1e6, e_ist=2e6, a_plan=5e5, a_ist=6e5,
                             ve=815_000_000.0, va=790_000_000.0)
    # Ordentliches Ergebnis verfälscht: 12 − 20 geht nicht mehr auf 21 auf.
    kaputt = kaputt.replace("21. ordentliches Ergebnis 25.000.000,00 500.000,00",
                            "21. ordentliches Ergebnis 25.000.000,00 111.111,11")
    anlage(bestand, 110, "15 Jahresabschluss 2026 Stadt Oldenburg", kaputt)
    bestand.close()

    p = finanzquellen.Protokoll(still=True)
    bericht = check_finanzdaten.main(db=str(tmp_path / "council.sqlite"),
                                     heute=date(2027, 11, 1), still=True, protokoll=p)

    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        assert 2026 not in store.ergebnisrechnung_jahre()
    finally:
        store.close()
    # Nicht still übergangen: Der Lauf sagt, dass ein Jahrgang liegen blieb.
    assert any("Strukturprobe" in z for z in p.warnungen)
    assert any("nicht übernommen" in z and "2026" in z for z in p.warnungen)
    assert "jahresabschluss:2026" in bericht["ausbleibend"]


# --- Bestandsschutz ---------------------------------------------------------

def test_leeres_ergebnis_ersetzt_niemals_einen_gefuellten_bestand():
    """Der Fall vom 16.08.2026: Ein Skript hätte 257 Prüfungsfeststellungen
    gelöscht, weil die Quelltabelle leer war. Unbeaufsichtigt alle zwei Wochen
    ist das der teuerste Fehler, den dieser Job machen könnte — bemerkt würde
    er erst, wenn die Seite leer ist."""
    p = finanzquellen.Protokoll(still=True)
    assert finanzquellen.bestandsschutz(p, "2023 Feststellungen", alt=257, neu=0) is False
    assert any("Bestand bleibt unangetastet" in z for z in p.warnungen)


def test_deutlich_geschrumpftes_ergebnis_wird_zurueckgewiesen():
    p = finanzquellen.Protokoll(still=True)
    # 40 von 257 — das ist kein Jahrgang, das ist ein kaputter Parser.
    assert finanzquellen.bestandsschutz(p, "2023", alt=257, neu=40) is False
    # Ein paar Zeilen weniger können echt sein: durchlassen, aber ausweisen.
    p2 = finanzquellen.Protokoll(still=True)
    assert finanzquellen.bestandsschutz(p2, "2023", alt=257, neu=250) is True
    assert any("statt bisher 257" in z for z in p2.zeilen)
    # Ein neuer Jahrgang hat keinen Vorgänger — nichts zu schützen.
    assert finanzquellen.bestandsschutz(p2, "2025", alt=0, neu=3) is True


def test_job_laesst_bestand_stehen_wenn_der_parser_nichts_mehr_liefert(bestand, tmp_path):
    """Ändert die Stadt ihr Tabellenlayout, liefert der Parser irgendwann
    nichts — dann bleibt der alte Stand stehen und der Lauf meldet es."""
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_jahresabschluesse(bestand, p)
    vorher = inhalt(bestand)

    # Alle drei Dokumente unleserlich machen — der Bestand bleibt.
    with bestand._conn:  # noqa: SLF001
        bestand._conn.execute(  # noqa: SLF001
            "UPDATE council_anlagen SET raw_text = 'Layout geändert'")

    p2 = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_jahresabschluesse(bestand, p2)
    try:
        assert inhalt(bestand) == vorher
        assert bestand.ergebnisrechnung_jahre() == [2023, 2024, 2025]
    finally:
        bestand.close()
    assert any("keine Summenzeilen" in z for z in p2.warnungen)


def test_leerer_prueferbericht_loescht_die_feststellungen_nicht(tmp_path):
    """Dieselbe Regel für die Prüfungsfeststellungen — die Tabelle, an der der
    Beinahe-Unfall hing. ``save_pruefbericht`` leert den Jahrgang, bevor es
    schreibt; gegen ein leeres Ergebnis darf es dazu gar nicht erst kommen."""
    store = CouncilStore(tmp_path / "council.sqlite")
    store.save_pruefbericht(2023, [
        {"lfd": i, "marke": "H", "marke_name": "Hinweis", "textziffer": "1.1",
         "abschnitt": "Prüfungsauftrag", "text": f"Feststellung {i}"}
        for i in range(1, 21)], "Schlussbericht 2023", None)
    assert len(store.get_pruefberichte(2023)) == 20

    # Ein Bericht, der als Dokument erkannt wird, aus dem aber nichts zu holen
    # ist (Legende gefunden, keine Marken im Text).
    anlage(store, 300,
           "Schlussbericht 2023",
           "Schlussbericht des Rechnungsprüfungsamtes über die Prüfung "
           "des Jahresabschlusses 2023 der Stadt Oldenburg (Oldb)\n"
           + "Rechnungsprüfungsamtes\n" * 5, n_pages=60)

    p = finanzquellen.Protokoll(still=True)
    bericht = finanzquellen.lies_pruefungsfeststellungen(store, p)
    try:
        assert len(store.get_pruefberichte(2023)) == 20
    finally:
        store.close()
    assert bericht["bestand_geschuetzt"] == 1
    assert any("Bestand bleibt unangetastet" in z for z in p.warnungen)


# --- Datenstand und Hinweis -------------------------------------------------

def test_ein_jahrgang_landet_ganz_oder_gar_nicht(bestand, monkeypatch):
    """Ohne gemeinsame Klammer braucht ein Jahresabschluss 1 + n + 1
    Transaktionen. Bricht der Lauf dazwischen ab, bleibt der Jahrgang halb in
    der Datenbank — und halb sieht für den nächsten Lauf aus wie fertig."""
    echt = CouncilStore.save_ergebnisrechnung

    def platzt(self, jahr, posten, *a, **kw):
        # Nach der Gesamtrechnung, mitten in den Teilhaushalten von 2024.
        if jahr == 2024 and kw.get("thh_nr") is not None:
            raise RuntimeError("Verbindung weg")
        return echt(self, jahr, posten, *a, **kw)

    monkeypatch.setattr(CouncilStore, "save_ergebnisrechnung", platzt)
    p = finanzquellen.Protokoll(still=True)
    with pytest.raises(RuntimeError):
        finanzquellen.lies_jahresabschluesse(bestand, p)

    try:
        # 2023 war vor dem Abbruch fertig und bleibt es.
        assert 2023 in bestand.ergebnisrechnung_jahre()
        # 2024 ist komplett zurückgerollt — keine halbe Gesamtrechnung, keine
        # halben Teilhaushalte, die den nächsten Lauf glauben ließen, es stünde.
        assert 2024 not in bestand.ergebnisrechnung_jahre()
        assert 2024 not in bestand.plan_ist_jahre()
        assert bestand.get_abweichungsgruende(2024) == []
    finally:
        bestand.close()


def test_handlauf_kommt_auch_an_einem_schrumpfenden_jahrgang_vorbei():
    """Der Schutz gehört an den unbeaufsichtigten Weg, nicht an den bewussten
    Handgriff: Wer einen verbesserten Parser über den Bestand zieht, will
    einen kleineren Jahrgang oft genau so. Gemeldet wird es trotzdem."""
    p = finanzquellen.Protokoll(still=True)
    assert finanzquellen.bestandsschutz(p, "2023", alt=257, neu=40,
                                        schuetzen=False) is True
    assert any("auf Ansage trotzdem ersetzt" in z for z in p.warnungen)
    # Der Cron bleibt streng.
    p2 = finanzquellen.Protokoll(still=True)
    assert finanzquellen.bestandsschutz(p2, "2023", alt=257, neu=40) is False
    # Leer bleibt in BEIDEN Wegen tabu — null Zeilen sind nie eine Absicht.
    p3 = finanzquellen.Protokoll(still=True)
    assert finanzquellen.bestandsschutz(p3, "2023", alt=257, neu=0,
                                        schuetzen=False) is False


def test_ingest_skript_reicht_auch_schrumpfen_durch():
    """Die Verdrahtung, nicht nur die Regel: ``--auch-schrumpfen`` muss beim
    Leser ankommen."""
    import importlib.util as iu

    spec = iu.spec_from_file_location("ingest_fb", ROOT / "scripts" / "ingest_finanzberichte.py")
    modul = iu.module_from_spec(spec)
    spec.loader.exec_module(modul)
    quelle = Path(modul.__file__).read_text()
    assert "--auch-schrumpfen" in quelle
    assert "schuetzen=schuetzen" in quelle


def test_teilweise_gelesener_jahrgang_gibt_sich_zu_erkennen(thh_bestand):
    """Ein zu einem Viertel gelesener Jahrgang steht sonst in derselben
    Jahresspanne wie ein vollständiger und sieht aus wie einer."""
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_teilhaushalte(thh_bestand, p, nur_fehlende=True)
    # Ein zweiter, vollständiger Jahrgang als Maßstab.
    for i, (nr, (name, produkte)) in enumerate(sorted(THH_PLAENE.items())):
        anlage(thh_bestand, 600 + i, f"2027 {7 + i:03d} Vw THH{nr:02d}",
               teilhaushalt_plan(nr, name, produkte, 2026))
    p2 = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_teilhaushalte(thh_bestand, p2, nur_fehlende=True)

    stand = {z["key"]: z for z in finanzquellen.datenstand(thh_bestand, date(2028, 12, 1))}
    thh = stand["teilhaushalt"]
    try:
        assert thh["jahrgaenge"] == [2026, 2027]
        assert thh["einheiten"] == {"2026": 4, "2027": 2}
        assert thh["einheiten_voll"] == 4
        assert thh["teilweise"] == [2027], "2027 hat nur zwei von vier Teilhaushalten"
        assert thh["einheit"] == "Teilhaushalte"
    finally:
        thh_bestand.close()


def test_hinweis_meldet_liegengebliebene_einheiten(thh_bestand, tmp_path, monkeypatch):
    """Der Fall, der bisher gar nichts meldete: Der Jahrgang steht in der
    Tabelle, ist also nicht überfällig — aber ein Dokument dafür liegt
    ungelesen daneben."""
    from kern.store import Store

    nwz = tmp_path / "nwz.sqlite"
    Store(nwz).close()
    monkeypatch.setenv("NWZ_DB", str(nwz))
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_teilhaushalte(thh_bestand, p, nur_fehlende=True)
    # THH03 bekommt Text, aber sein Inhalt ist unlesbar geworden.
    with thh_bestand._conn:  # noqa: SLF001
        thh_bestand._conn.execute(  # noqa: SLF001
            "UPDATE council_anlagen SET raw_text = ?, n_pages = 300, status = 'ok' "
            "WHERE document_id = 502",
            ("Teilergebnishaushalt THH03: Jugend\nLayout geändert\nAnsatz 2027\n",))
    thh_bestand.close()

    gemeldet: list[str] = []
    monkeypatch.setattr("kern.alerts.notify_admin", lambda text, **kw: gemeldet.append(text))
    bericht = check_finanzdaten.main(db=str(tmp_path / "council.sqlite"),
                                     heute=date(2028, 1, 15), still=True)

    assert bericht["Neue Einheiten"] == 0
    assert "teilhaushalt:offen:(2027, 3)" in bericht["ausbleibend"]
    assert len(gemeldet) == 1
    assert "nur teilweise in der Datenbank" in gemeldet[0]
    assert "2027 THH03" in gemeldet[0]


def test_datenstand_nennt_den_naechsten_jahrgang_und_wann_er_kommt(bestand):
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_jahresabschluesse(bestand, p)

    # Mitte August 2026: Der Abschluss 2025 kommt üblicherweise im September
    # 2026 — er ist noch nicht überfällig, sondern schlicht noch nicht da.
    stand = {z["key"]: z for z in
             finanzquellen.datenstand(bestand, date(2026, 8, 16))}
    ja = stand["jahresabschluss"]
    assert ja["jahrgaenge"] == [2023, 2024, 2025] and ja["neuester"] == 2025
    assert ja["naechster_jahrgang"] == 2026 and ja["naechster_ab"] == "2027-09-01"
    assert ja["ueberfaellig"] == []

    # Der Haushaltsplan kommt im Oktober für das FOLGEjahr — anderer Takt,
    # deshalb steht er als eigene Zeile da.
    plan = stand["haushaltsplan"]
    assert plan["erwarteter_monat"] == 10 and plan["automatisch"] is False
    bestand.close()


def test_ueberfaellig_erst_nach_der_karenz(bestand):
    """Vier Wochen Luft: Die Einbringung ist in acht Jahren zweimal um einen
    Monat verrutscht. Wer sofort meldet, meldet den Normalfall."""
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_jahresabschluesse(bestand, p)

    def offen(heute: date) -> list[int]:
        stand = {z["key"]: z for z in finanzquellen.datenstand(bestand, heute)}
        return stand["jahresabschluss"]["ueberfaellig"]

    assert offen(date(2027, 9, 15)) == []    # gerade erst fällig
    assert offen(date(2027, 9, 30)) == [2026]  # vier Wochen vorbei
    bestand.close()


def test_luecken_im_bestand_bleiben_sichtbar(bestand):
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_jahresabschluesse(bestand, p)
    with bestand._conn:  # noqa: SLF001
        bestand._conn.execute(  # noqa: SLF001
            "DELETE FROM council_ergebnisrechnung WHERE jahr = 2024")

    stand = {z["key"]: z for z in finanzquellen.datenstand(bestand, date(2026, 8, 16))}
    assert stand["jahresabschluss"]["luecken"] == [2024]
    bestand.close()


def test_hinweis_wiederholt_sich_nicht(bestand, tmp_path, monkeypatch):
    """Alle vierzehn Tage dieselbe Mail wäre eine, die niemand mehr liest.
    Verglichen wird mit dem letzten Lauf aus ``job_runs``."""
    from kern.store import Store

    nwz = tmp_path / "nwz.sqlite"
    Store(nwz).close()
    monkeypatch.setenv("NWZ_DB", str(nwz))
    bestand.close()

    verschickt: list[str] = []
    monkeypatch.setattr("kern.alerts.notify_admin",
                        lambda text, **kw: verschickt.append(text))

    from kern.alerts import run_guarded
    db = str(tmp_path / "council.sqlite")
    run_guarded("check_finanzdaten",
                lambda: check_finanzdaten.main(db=db, heute=date(2027, 11, 1), still=True))
    assert len(verschickt) == 1, "erster Lauf meldet den ausbleibenden Jahrgang"

    run_guarded("check_finanzdaten",
                lambda: check_finanzdaten.main(db=db, heute=date(2027, 11, 15), still=True))
    assert len(verschickt) == 1, "unveränderter Stand — kein zweiter Hinweis"


def test_hinweis_trennt_spaete_stadt_von_kaputtem_muster(bestand, tmp_path):
    """Der Unterschied trägt die ganze Nachricht: „kein Dokument da" heißt
    abwarten, „Dokument da, aber nicht übernommen" heißt nachsehen."""
    stand = finanzquellen.datenstand(bestand, date(2027, 11, 1))
    ohne = check_finanzdaten._hinweis_text(stand, {}, {}, date(2027, 11, 1))
    assert "kein passendes Dokument" in ohne

    gesehen = {"jahresabschluss": {z for z in range(2000, 2100)}}
    mit = check_finanzdaten._hinweis_text(stand, gesehen, {}, date(2027, 11, 1))
    assert "wird aber nicht übernommen" in mit
    bestand.close()
