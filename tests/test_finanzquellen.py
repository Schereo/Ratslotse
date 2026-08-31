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


def jahresabschluss(year: int, e_plan: float, e_ist: float,
                    a_plan: float, a_ist: float,
                    commitment_authorizations: float, va: float, mit_thh: bool = True) -> str:
    """Ein Jahresabschluss-Extrakt, der alle vier Proben besteht.

    ``commitment_authorizations``/``va`` sind die Ist-Werte des Vorjahres (Posten 12 und 20) — sie
    stehen in der Vorjahresspalte und schließen damit die Kette zum
    Vorgängerjahrgang."""
    r_plan, r_ist, r_vor = e_plan - a_plan, e_ist - a_ist, commitment_authorizations - va
    text = f"""3.1 Ergebnisrechnung Kernverwaltung
Erträge und Aufwendungen Ergebnis des
Vorjahres
{year - 1}
Ansätze des
Haushaltsjahres
{year}
Veränderung
durch Nachtrag
Ergebnis des
Haushaltsjahres
{year}
mehr (+) /
weniger (-)4)
{year}
 - Euro -
1 2 3 4 5 6 7
ordentliche Erträge
01. Steuern und ähnliche Abgaben {eur(commitment_authorizations * 0.4)} {eur(e_plan * 0.4)}  {eur(e_ist * 0.4)} {eur(e_ist * 0.4 - e_plan * 0.4)}
12. = Summe ordentliche Erträge {eur(commitment_authorizations)} {eur(e_plan)}  {eur(e_ist)} {eur(e_ist - e_plan)}
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
{year - 1}
Ansätze des
Haushaltsjahres
{year}
Veränderung
durch Nachtrag
Ergebnis des
Haushaltsjahres
{year}
mehr (+) /
weniger (-)4)
{year}
 - Euro -
1 2 3 4 5 6 7
Ordentliche Erträge
12. =Summe ordentliche Erträge {eur(commitment_authorizations)} {eur(e_plan)}  {eur(e_ist)} {eur(e_ist - e_plan)}
Ordentliche Aufwendungen
20. =Summe ordentliche Aufwendungen {eur(va)} {eur(a_plan)}  {eur(a_ist)} {eur(a_ist - a_plan)}
"""
    return text


#: Drei aufeinanderfolgende Jahrgänge; die Vorjahresspalte jedes Jahres trägt
#: das Ist des Vorgängers, damit die Vorjahres-Kette schließt.
JAHRGAENGE = {
    2023: dict(e_plan=664_000_000.0, e_ist=732_000_000.0,
               a_plan=674_000_000.0, a_ist=683_000_000.0,
               commitment_authorizations=696_000_000.0, va=661_000_000.0),
    2024: dict(e_plan=693_000_000.0, e_ist=799_000_000.0,
               a_plan=727_000_000.0, a_ist=764_000_000.0,
               commitment_authorizations=732_000_000.0, va=683_000_000.0),
    2025: dict(e_plan=710_000_000.0, e_ist=815_000_000.0,
               a_plan=750_000_000.0, a_ist=790_000_000.0,
               commitment_authorizations=799_000_000.0, va=764_000_000.0),
}


def teilhaushalt_plan(sub_budget_no: int, sub_budget_name: str, produkte: list[tuple],
                      year: int) -> str:
    """Ein Teilhaushalts-Plan im Layout der echten Dokumente.

    Die Beträge stehen in **deutscher** Schreibweise mit Tausenderpunkt — so
    stehen sie im PDF-Extrakt, und nur so liest ``_thh_zahlen`` sie als eine
    Zahl. „6900" zerfiele dort in 690 und 0."""
    text = ""
    for product_no, name, office, revenues, expenses in produkte:
        result = revenues - expenses
        text += (
            f"Teilergebnishaushalt THH{sub_budget_no:02d}: {sub_budget_name}\n"
            f"Produkt: {name} ({product_no})\n"
            f"{office}\n"
            f"Erträge und Aufwendungen Ergebnis {year - 1}\n- Euro -\n"
            f"Ansatz {year}\n- Euro -\nAnsatz {year + 1}\n- Euro -\n"
            f"12. = Summe ordentliche Erträge {eur(revenues - 100)} {eur(revenues)}"
            f" {eur(revenues + 50)}\n"
            f"20. = Summe ordentliche Aufwendungen {eur(expenses - 100)}"
            f" {eur(expenses)} {eur(expenses + 50)}\n"
            f"21. ordentliches Ergebnis {eur(result - 0)} {eur(result)}"
            f" {eur(result - 50)}\n"
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
def balance(tmp_path):
    """Council-DB mit drei Jahresabschlüssen als Anlage — noch nichts eingelesen."""
    store = CouncilStore(tmp_path / "council.sqlite")
    for i, (year, werte) in enumerate(sorted(JAHRGAENGE.items())):
        anlage(store, 100 + i, f"15 Jahresabschluss {year} Stadt Oldenburg",
               jahresabschluss(year, **werte))
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
        "SELECT DISTINCT year, sub_budget_no FROM council_produkte"))


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


def test_rechenschaftsbericht_und_schlussbericht_sind_keine_jahresabschluesse(balance):
    """Beide tragen dieselbe Jahreszahl im Titel und sind ein anderes Dokument."""
    anlage(balance, 200, "15 Rechenschaftsbericht 2025 Stadt Oldenburg", "x")
    anlage(balance, 201, "Schlussbericht zum Jahresabschluss 2025", "x")
    anlage(balance, 202, "Jahresabschluss 2025 Auszug", "x", n_pages=4)

    gefunden = {r["document_id"] for r in
                finanzquellen.QUELLEN["jahresabschluss"].kandidaten(balance)}
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
    assert q.unit == "Teilhaushalte"


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


def test_fehlende_teilhaushalts_ebene_wird_nachgezogen(balance, tmp_path):
    """Ein Jahresabschluss trägt zwei Ebenen. Die Summenprobe kann die zweite
    verwerfen, während die erste steht — dann ist der Jahrgang in der Tabelle,
    aber halb. ``ergebnisrechnung_jahre()`` („irgendeine Zeile") hielte ihn
    für fertig."""
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_jahresabschluesse(balance, p)
    vollstaendig = inhalt(balance)

    # Der Zustand nach einem Lauf, in dem nur die Teilhaushalte scheiterten.
    with balance._conn:  # noqa: SLF001
        balance._conn.execute(  # noqa: SLF001
            "DELETE FROM council_ergebnisrechnung WHERE year = 2024 AND sub_budget_no IS NOT NULL")
        balance._conn.execute(  # noqa: SLF001
            "DELETE FROM council_abweichungsgruende WHERE year = 2024")
    assert 2024 in balance.ergebnisrechnung_jahre(), "die Gesamtrechnung steht noch"
    assert 2024 not in balance.plan_actual_years()
    balance.close()

    bericht = check_finanzdaten.main(db=str(tmp_path / "council.sqlite"),
                                     heute=date(2026, 8, 16), still=True)

    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        # Ohne die Korrektur bleibt 2024 für immer ohne Teilhaushalte.
        assert 2024 in store.plan_actual_years()
        # Die Erläuterungen reiten mit: Sie hängen am selben Dokument.
        assert inhalt(store) == vollstaendig
    finally:
        store.close()
    assert bericht["Neue Einheiten"] == 1


# --- Derselbe Teilhaushalt in zwei Dokumenten -------------------------------
#
# Der Befund aus dem Bestand (08/2026): Sechs (Jahrgang, Teilhaushalt)-Paare
# hängen an zwei Vorlagen — dieselbe PDF-Datei, ein zweites Mal unter einem
# anderen Tagesordnungspunkt hochgeladen. Nachgemessen an den echten Daten:
# der Volltext ist Byte für Byte derselbe, die Zahlen also auch.


def _zwei_dokumente_ein_teilhaushalt(tmp_path, zweite_produkte=None):
    """Ein Teilhaushalt, zweimal im Anlagenbestand — wie im echten Bestand:
    dasselbe Dokument unter zwei Labels, das zweite später hochgeladen
    (höhere ``document_id``) und mit dem tagesordnungs-spezifischen Label."""
    store = CouncilStore(tmp_path / "council.sqlite")
    name, produkte = THH_PLAENE[1]
    anlage(store, 600, "007 THH01", teilhaushalt_plan(1, name, produkte, 2027))
    anlage(store, 640, "TOP 5 - Anlage III - THH 01",
           teilhaushalt_plan(1, name, zweite_produkte or produkte, 2027))
    return store


def test_zweites_dokument_zum_selben_teilhaushalt_wird_uebersprungen(tmp_path):
    """Ohne Regel entschied die Sortierung der Kandidaten, welches Dokument in
    der Zeile als Quelle steht — und nebenbei entstand je Lauf ein
    Herkunfts-Datensatz, auf den am Ende keine Zeile mehr zeigt."""
    store = _zwei_dokumente_ein_teilhaushalt(tmp_path)
    try:
        p = finanzquellen.Protokoll(still=True)
        lauf = finanzquellen.lies_teilhaushalte(store, p)

        assert lauf["dokumente"] == 2          # beide gefunden …
        assert lauf["dubletten"] == 1          # … eines davon übersprungen
        assert lauf["produkte"] == lauf["in_tabelle"] == 2
        assert not p.warnungen                 # gleiche Zahlen: keine Meldung

        # Es gilt das ERSTE Dokument — die Anlage der Haushaltsvorlage selbst,
        # nicht die Zweitveröffentlichung unter einem Tagesordnungspunkt.
        quellen = {r[0] for r in store._conn.execute(  # noqa: SLF001
            "SELECT DISTINCT source_label FROM council_produkte")}
        assert quellen == {"007 THH01"}
        dokumente = {r[0] for r in store._conn.execute(  # noqa: SLF001
            "SELECT DISTINCT h.document_id FROM council_produkte p "
            "JOIN council_herkunft h ON h.id = p.herkunft_id")}
        assert dokumente == {600}

        # Und keine Herkunft, auf die niemand zeigt: Genau daran ist der
        # Befund aufgefallen (`herkunft_verwaist` meldete sechs je Lauf).
        assert store.herkunft_aufraeumen() == 0
    finally:
        store.close()


def test_abweichende_zahlen_im_zweiten_dokument_werden_gemeldet(tmp_path):
    """Die Gegenprobe zum Befund: Heute tragen die Doppel-Dokumente
    identische Zahlen. Täten sie es einmal nicht — ein Nachtragshaushalt
    ändert einen Ansatz wirklich —, wäre das eine Entscheidung, die niemand
    nebenbei in einem unbeaufsichtigten Lauf treffen soll."""
    name, produkte = THH_PLAENE[1]
    geaendert = [(nr, n, office, revenues + 1_000, expenses)
                 for nr, n, office, revenues, expenses in produkte]
    store = _zwei_dokumente_ein_teilhaushalt(tmp_path, zweite_produkte=geaendert)
    try:
        p = finanzquellen.Protokoll(still=True)
        finanzquellen.lies_teilhaushalte(store, p)

        assert len(p.warnungen) == 1
        meldung = p.warnungen[0]
        assert "ANDERE Zahlen" in meldung
        assert "2027 THH1" in meldung
        # Beide Dokumente werden benannt — ohne sie ist die Meldung nicht
        # nachprüfbar.
        assert "600" in meldung and "640" in meldung

        # Gemeldet, nicht überschrieben: Es gilt weiter das erste Dokument.
        revenues = sorted(r[0] for r in store._conn.execute(  # noqa: SLF001
            "SELECT revenues FROM council_produkte"))
        assert revenues == [1_000.0, 4_000.0]
    finally:
        store.close()


def test_kandidaten_kommen_in_veroeffentlichungs_reihenfolge():
    """Die Regel „das erste Dokument versorgt den Teilhaushalt" braucht ein
    Kriterium, das etwas bedeutet. ``document_id`` ist die getfile-Nummer des
    Ratsinformationssystems und steigt mit jedem Upload; nach ``label``
    sortiert gewänne der Zufall der Schreibweise — im echten Bestand hieße
    das „2019 THH 08" am Plan für 2018."""
    sql, _ = finanzquellen.QUELLEN["teilhaushalt"].erkennung.abfrage("document_id")
    assert sql.endswith("ORDER BY document_id")


# --- Der Lauf ---------------------------------------------------------------

def test_holt_den_fehlenden_jahrgang_nach(balance, tmp_path):
    """Erst alles einlesen, dann einen Jahrgang löschen — der Job zieht ihn
    zurück, ohne dass ihm jemand sagt, welcher es ist."""
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_jahresabschluesse(balance, p)
    assert balance.ergebnisrechnung_jahre() == [2023, 2024, 2025]
    vollstaendig = inhalt(balance)

    with balance._conn:  # noqa: SLF001
        balance._conn.execute(  # noqa: SLF001
            "DELETE FROM council_ergebnisrechnung WHERE year = 2024")
    assert balance.ergebnisrechnung_jahre() == [2023, 2025]
    balance.close()

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


def test_zweiter_lauf_aendert_nichts(balance, tmp_path):
    balance.close()
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


def test_dokument_das_die_probe_reisst_kommt_nicht_herein(balance, tmp_path):
    """Die Strukturprobe (12 − 20 = 21) ist keine Formalie: Sie ist der
    Unterschied zwischen einer gelesenen und einer geratenen Tabelle. Ein
    automatischer Lauf darf sie nicht lockern — er ist der Grund, warum sie
    existiert."""
    kaputt = jahresabschluss(2026, e_plan=1e6, e_ist=2e6, a_plan=5e5, a_ist=6e5,
                             commitment_authorizations=815_000_000.0, va=790_000_000.0)
    # Ordentliches Ergebnis verfälscht: 12 − 20 geht nicht mehr auf 21 auf.
    kaputt = kaputt.replace("21. ordentliches Ergebnis 25.000.000,00 500.000,00",
                            "21. ordentliches Ergebnis 25.000.000,00 111.111,11")
    anlage(balance, 110, "15 Jahresabschluss 2026 Stadt Oldenburg", kaputt)
    balance.close()

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


def test_job_laesst_bestand_stehen_wenn_der_parser_nichts_mehr_liefert(balance, tmp_path):
    """Ändert die Stadt ihr Tabellenlayout, liefert der Parser irgendwann
    nichts — dann bleibt der alte Stand stehen und der Lauf meldet es."""
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_jahresabschluesse(balance, p)
    vorher = inhalt(balance)

    # Alle drei Dokumente unleserlich machen — der Bestand bleibt.
    with balance._conn:  # noqa: SLF001
        balance._conn.execute(  # noqa: SLF001
            "UPDATE council_anlagen SET raw_text = 'Layout geändert'")

    p2 = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_jahresabschluesse(balance, p2)
    try:
        assert inhalt(balance) == vorher
        assert balance.ergebnisrechnung_jahre() == [2023, 2024, 2025]
    finally:
        balance.close()
    assert any("keine Summenzeilen" in z for z in p2.warnungen)


def test_leerer_prueferbericht_loescht_die_feststellungen_nicht(tmp_path, source):
    """Dieselbe Regel für die Prüfungsfeststellungen — die Tabelle, an der der
    Beinahe-Unfall hing. ``save_pruefbericht`` leert den Jahrgang, bevor es
    schreibt; gegen ein leeres Ergebnis darf es dazu gar nicht erst kommen."""
    store = CouncilStore(tmp_path / "council.sqlite")
    store.save_pruefbericht(2023, [
        {"seq": i, "mark": "H", "mark_name": "Hinweis", "text_number": "1.1",
         "section": "Prüfungsauftrag", "text": f"Feststellung {i}"}
        for i in range(1, 21)], source("Schlussbericht 2023",
                                       "https://example.org/sb2023.pdf",
                                       probe="legende_und_verzeichnis"))
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

def test_ein_jahrgang_landet_ganz_oder_gar_nicht(balance, monkeypatch):
    """Ohne gemeinsame Klammer braucht ein Jahresabschluss 1 + n + 1
    Transaktionen. Bricht der Lauf dazwischen ab, bleibt der Jahrgang halb in
    der Datenbank — und halb sieht für den nächsten Lauf aus wie fertig."""
    echt = CouncilStore.save_ergebnisrechnung

    def platzt(self, year, posten, *a, **kw):
        # Nach der Gesamtrechnung, mitten in den Teilhaushalten von 2024.
        if year == 2024 and kw.get("sub_budget_no") is not None:
            raise RuntimeError("Verbindung weg")
        return echt(self, year, posten, *a, **kw)

    monkeypatch.setattr(CouncilStore, "save_ergebnisrechnung", platzt)
    p = finanzquellen.Protokoll(still=True)
    with pytest.raises(RuntimeError):
        finanzquellen.lies_jahresabschluesse(balance, p)

    try:
        # 2023 war vor dem Abbruch fertig und bleibt es.
        assert 2023 in balance.ergebnisrechnung_jahre()
        # 2024 ist komplett zurückgerollt — keine halbe Gesamtrechnung, keine
        # halben Teilhaushalte, die den nächsten Lauf glauben ließen, es stünde.
        assert 2024 not in balance.ergebnisrechnung_jahre()
        assert 2024 not in balance.plan_actual_years()
        assert balance.get_abweichungsgruende(2024) == []
    finally:
        balance.close()


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
    source = Path(modul.__file__).read_text()
    assert "--auch-schrumpfen" in source
    assert "schuetzen=schuetzen" in source


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

    as_of = {z["key"]: z for z in finanzquellen.datenstand(thh_bestand, date(2028, 12, 1))}
    sub_budget = as_of["teilhaushalt"]
    try:
        assert sub_budget["jahrgaenge"] == [2026, 2027]
        assert sub_budget["einheiten"] == {"2026": 4, "2027": 2}
        assert sub_budget["einheiten_voll"] == 4
        assert sub_budget["teilweise"] == [2027], "2027 hat nur zwei von vier Teilhaushalten"
        assert sub_budget["unit"] == "Teilhaushalte"
    finally:
        thh_bestand.close()


def test_hinweis_meldet_liegengebliebene_einheiten(thh_bestand, tmp_path, monkeypatch):
    """Der Fall, der bisher gar nichts meldete: Der Jahrgang steht in der
    Tabelle, ist also nicht überfällig — aber ein Dokument dafür liegt
    ungelesen daneben."""
    from kern.store import Store

    ratslotse = tmp_path / "ratslotse.sqlite"
    Store(ratslotse).close()
    monkeypatch.setenv("RATSLOTSE_DB", str(ratslotse))
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


def test_zeilen_ohne_herkunft_loesen_eine_mail_aus(thh_bestand, tmp_path, monkeypatch):
    """Der stillste Ausfall des Jobs: eine Zahl ohne Beleg.

    `herkunft_luecken()` wurde bis 20.08.2026 gerufen, ins Log geschrieben und
    als Kennzahl nach `job_runs` gereicht — aber der Befund stand nicht in
    `ausbleibend` und löste deshalb **nie** eine Mail aus. Ein Cron-Log liest
    niemand freiwillig, und anders als bei einem fehlenden Jahrgang vermisst
    hier nichts: Der Jahrgang steht da, die Zahl steht da, nur der Beleg
    fehlt. Auf einer Seite, deren Anspruch „jede Zahl sagt, woher sie stammt"
    ist, fällt das erst auf, wenn jemand auf den Chip tippt.

    Geprüft wird an `council_steuern`, und zwar mit Absicht: Bei den neun
    Schichten, die der Job selbst einliest, **heilt** er eine solche Lücke
    beim nächsten Lauf (die Einheit gilt als offen und wird neu geschrieben,
    mitsamt frischer Herkunft). Liegen bleibt sie genau dort, wo niemand
    automatisch nachzieht — in den sechs Schichten von außerhalb. Das ist
    zugleich der Grund, warum die Meldung überhaupt gebraucht wird.
    """
    from kern.store import Store

    ratslotse = tmp_path / "ratslotse.sqlite"
    Store(ratslotse).close()
    monkeypatch.setenv("RATSLOTSE_DB", str(ratslotse))

    # Eine Zeile aus einer von Hand gepflegten Schicht, die ihre Herkunft
    # nicht trägt — so sieht ein Schreibweg aus, der `herkunft_id` vergisst.
    with thh_bestand._conn:  # noqa: SLF001
        thh_bestand._conn.execute(  # noqa: SLF001
            "INSERT INTO council_steuern (year, kind, amount, fetched_at, herkunft_id) "
            "VALUES (2025, 'Gewerbesteuer (-umlage)', 222117000.0, '2026-08-20', NULL)")
    thh_bestand.close()

    gemeldet: list[str] = []
    monkeypatch.setattr("kern.alerts.notify_admin", lambda text, **kw: gemeldet.append(text))
    bericht = check_finanzdaten.main(db=str(tmp_path / "council.sqlite"),
                                     heute=date(2027, 1, 15), still=True)

    assert bericht["Zeilen ohne Herkunft"] == 1
    # Die ZAHL gehört in den Wiederholungs-Schlüssel, nicht nur der Name:
    # Sonst hieße „schon gemeldet" auch dann Schweigen, wenn aus einer Zeile
    # ohne Beleg dreihundert geworden sind.
    assert "herkunft:council_steuern:1" in bericht["ausbleibend"]
    assert len(gemeldet) == 1, "der Befund muss eine Mail auslösen, nicht nur das Log"
    assert "nicht sagen, woher sie kommen" in gemeldet[0]
    assert "council_steuern" in gemeldet[0]


def test_hinweis_ohne_herkunftsluecke_schweigt_darueber(balance):
    """Der Block erscheint nur, wenn es ihn zu berichten gibt — sonst stünde
    unter jeder Mail eine leere Überschrift."""
    as_of = finanzquellen.datenstand(balance, date(2027, 11, 1))
    ohne = check_finanzdaten._hinweis_text(as_of, {}, {}, date(2027, 11, 1))
    mit = check_finanzdaten._hinweis_text(as_of, {}, {}, date(2027, 11, 1),
                                          {"council_steuern": 7})
    balance.close()
    assert "woher sie kommen" not in ohne
    assert "woher sie kommen" in mit and "7 Zeile(n)" in mit


def test_datenstand_nennt_den_naechsten_jahrgang_und_wann_er_kommt(balance):
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_jahresabschluesse(balance, p)

    # Mitte August 2026: Der Abschluss 2025 kommt üblicherweise im September
    # 2026 — er ist noch nicht überfällig, sondern schlicht noch nicht da.
    as_of = {z["key"]: z for z in
             finanzquellen.datenstand(balance, date(2026, 8, 16))}
    ja = as_of["jahresabschluss"]
    assert ja["jahrgaenge"] == [2023, 2024, 2025] and ja["neuester"] == 2025
    assert ja["naechster_jahrgang"] == 2026 and ja["naechster_ab"] == "2027-09-01"
    assert ja["ueberfaellig"] == []

    # Der Haushaltsplan kommt im Oktober für das FOLGEjahr — anderer Takt,
    # deshalb steht er als eigene Zeile da.
    plan = as_of["haushaltsplan"]
    assert plan["erwarteter_monat"] == 10 and plan["automatisch"] is False
    balance.close()


def test_ueberfaellig_erst_nach_der_karenz(balance):
    """Vier Wochen Luft: Die Einbringung ist in acht Jahren zweimal um einen
    Monat verrutscht. Wer sofort meldet, meldet den Normalfall."""
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_jahresabschluesse(balance, p)

    def offen(heute: date) -> list[int]:
        as_of = {z["key"]: z for z in finanzquellen.datenstand(balance, heute)}
        return as_of["jahresabschluss"]["ueberfaellig"]

    assert offen(date(2027, 9, 15)) == []    # gerade erst fällig
    assert offen(date(2027, 9, 30)) == [2026]  # vier Wochen vorbei
    balance.close()


def test_luecken_im_bestand_bleiben_sichtbar(balance):
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_jahresabschluesse(balance, p)
    with balance._conn:  # noqa: SLF001
        balance._conn.execute(  # noqa: SLF001
            "DELETE FROM council_ergebnisrechnung WHERE year = 2024")

    as_of = {z["key"]: z for z in finanzquellen.datenstand(balance, date(2026, 8, 16))}
    assert as_of["jahresabschluss"]["luecken"] == [2024]
    balance.close()


def test_hinweis_wiederholt_sich_nicht(balance, tmp_path, monkeypatch):
    """Alle vierzehn Tage dieselbe Mail wäre eine, die niemand mehr liest.
    Verglichen wird mit dem letzten Lauf aus ``job_runs``."""
    from kern.store import Store

    ratslotse = tmp_path / "ratslotse.sqlite"
    Store(ratslotse).close()
    monkeypatch.setenv("RATSLOTSE_DB", str(ratslotse))
    balance.close()

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


def test_hinweis_trennt_spaete_stadt_von_kaputtem_muster(balance, tmp_path):
    """Der Unterschied trägt die ganze Nachricht: „kein Dokument da" heißt
    abwarten, „Dokument da, aber nicht übernommen" heißt nachsehen."""
    as_of = finanzquellen.datenstand(balance, date(2027, 11, 1))
    ohne = check_finanzdaten._hinweis_text(as_of, {}, {}, date(2027, 11, 1))
    assert "kein passendes Dokument" in ohne

    gesehen = {"jahresabschluss": {z for z in range(2000, 2100)}}
    mit = check_finanzdaten._hinweis_text(as_of, gesehen, {}, date(2027, 11, 1))
    assert "wird aber nicht übernommen" in mit
    balance.close()


# --- Städtevergleich: die Schicht, die keinen Cron hat ----------------------
#
# Sie ist der Grund, warum der Datenstand-Block überhaupt eine Fußzeile hat.
# Die beiden LSN-Tabellen erscheinen einmal im Jahr und werden von Hand
# geholt — es gibt kein Dokument im Ratsinformationssystem, an dem der Cron
# merken könnte, dass ein Jahrgang da ist. Beobachtet wird trotzdem: Ein
# Jahrgang, der nach seinem üblichen Monat plus Karenz ausbleibt, ist eine
# Meldung wert, sonst erinnert sich nach zwölf Monaten niemand.

def staedtevergleich(store: CouncilStore, series: str, years: list[int]) -> None:
    """Ein paar Zeilen je Jahrgang — der Inhalt ist hier egal, gezählt wird
    das Jahr."""
    from council import herkunft as h

    for year in years:
        store.save_staedtevergleich(series, [
            {"year": year, "key": "403000", "city": "Oldenburg (Oldb), Stadt",
             "indicator": "steuerkraftmesszahl", "value": 1.0, "unit": "teur"},
        ], h.Herkunft(kind="lsn", probe=h.UNGEPRUEFT,
                      url="https://www.statistik.niedersachsen.de/download/227086"))


@pytest.fixture()
def lsn_bestand(tmp_path):
    """Der Stand vom 16.08.2026: Finanzausgleich für das Ausgleichsjahr 2026,
    Realsteuervergleich für die Berichtsjahre 2023–2025.

    Die Jahresmengen sind verschieden groß, weil die Quellen verschieden
    gebaut sind: Eine KFA-Datei trägt genau ein Ausgleichsjahr in den Bestand
    (das zweite ist ihre Rechenprobe), ein Realsteuervergleich drei."""
    store = CouncilStore(tmp_path / "council.sqlite")
    staedtevergleich(store, "tax_capacity", [2026])
    staedtevergleich(store, "realsteuern", [2023, 2024, 2025])
    return store


def test_staedtevergleich_steht_im_datenstand(lsn_bestand):
    """Bis 08/2026 fehlte er dort: Wer /haushalt/vergleich las, erfuhr an
    keiner Stelle, bis wann die Reihe reicht."""
    as_of = {z["key"]: z for z in
             finanzquellen.datenstand(lsn_bestand, date(2026, 8, 16))}

    sk = as_of["lsn_steuerkraft"]
    assert sk["jahrgaenge"] == [2026] and sk["ueberfaellig"] == []
    rs = as_of["lsn_realsteuern"]
    assert rs["jahrgaenge"] == [2023, 2024, 2025] and rs["ueberfaellig"] == []

    # Kein Cron holt das — und die Fußzeile sagt, wo es stattdessen herkommt.
    for z in (sk, rs):
        assert z["automatisch"] is False
        assert z["source"] == "Landesamt für Statistik Niedersachsen"
    lsn_bestand.close()


def test_die_beiden_reihen_bleiben_zwei_zeilen(lsn_bestand):
    """Eine gemeinsame Zeile ergäbe die Spanne „2023–2026" — und darin meinten
    zwei Jahresangaben Verschiedenes: Das Ausgleichsjahr des Finanzausgleichs
    läuft dem Kalender voraus, das Berichtsjahr des Realsteuervergleichs
    hinkt ihm nach. Genau diese Verwechslung ist der Grund, warum der
    Städtevergleich überhaupt eine eigene Tabelle hat."""
    as_of = finanzquellen.datenstand(lsn_bestand, date(2026, 8, 16))
    zeilen = [z for z in as_of if z["tabelle"] == "council_staedtevergleich"]
    assert [z["key"] for z in zeilen] == ["lsn_steuerkraft", "lsn_realsteuern"]
    # Keine der beiden Zeilen behauptet eine Lücke, die es nicht gibt.
    assert all(z["luecken"] == [] for z in zeilen)
    lsn_bestand.close()


def test_lsn_takt_ist_an_den_dateien_gemessen(lsn_bestand):
    """Die Monate sind nachgesehen, nicht geschätzt (Modul-Kopf):

    - Finanzausgleich **endgültig** trägt den Stand März/April des
      Ausgleichsjahres (25.04.2023 … 26.03.2026) — April ist der späteste
      gemessene Fall und deshalb die Schwelle.
    - Der Realsteuervergleich erscheint im Folgejahr, zuletzt Juni 2022,
      August 2023, November 2024, November 2025, Juli 2026 — November.
    """
    as_of = {z["key"]: z for z in
             finanzquellen.datenstand(lsn_bestand, date(2026, 8, 16))}

    sk = as_of["lsn_steuerkraft"]
    assert sk["erwarteter_monat"] == 4
    # Das Ausgleichsjahr 2027 liegt im April 2027 vor, nicht 2028.
    assert sk["naechster_jahrgang"] == 2027 and sk["naechster_ab"] == "2027-04-01"

    rs = as_of["lsn_realsteuern"]
    assert rs["erwarteter_monat"] == 11
    # Das Berichtsjahr 2026 erscheint im November 2027 — ein Jahr später.
    assert rs["naechster_jahrgang"] == 2026 and rs["naechster_ab"] == "2027-11-01"
    lsn_bestand.close()


def test_ausbleibender_jahrgang_wird_erst_nach_der_karenz_gemeldet(lsn_bestand):
    """Fünf Monate Streuung beim Realsteuervergleich — deshalb liegt die
    Schwelle am spätesten gemessenen Monat und nicht am Durchschnitt. Ein
    Bericht, der wie 2026 schon im Juli kommt, ist nie ein Problem; einer, der
    im Dezember immer noch fehlt, schon."""
    def offen(heute: date) -> list[int]:
        as_of = {z["key"]: z for z in finanzquellen.datenstand(lsn_bestand, heute)}
        return as_of["lsn_realsteuern"]["ueberfaellig"]

    # Das Berichtsjahr 2026 wird erst im November 2027 erwartet — ein Jahr
    # nach dem Jahr, das es beschreibt.
    assert offen(date(2027, 11, 15)) == []      # üblicher Monat läuft noch
    assert offen(date(2027, 12, 15)) == [2026]  # vier Wochen Karenz vorbei
    lsn_bestand.close()


def test_hinweis_schickt_zum_richtigen_skript(lsn_bestand):
    """Der Satz stand fest verdrahtet als „Download von oldenburg.de,
    scripts/ingest_haushalt.py" — bei einer Landesbehörde schickte er den
    Leser zur falschen Stelle und zum falschen Skript."""
    heute = date(2027, 12, 15)  # beide LSN-Jahrgänge sind jetzt überfällig
    as_of = finanzquellen.datenstand(lsn_bestand, heute)
    text = check_finanzdaten._hinweis_text(as_of, {}, {}, heute)

    assert "scripts/ingest_staedtevergleich.py" in text
    assert "Landesamt für Statistik" in text
    # Der Haushaltsplan bleibt bei seinem eigenen Weg.
    plan = finanzquellen.QUELLEN["haushaltsplan"]
    assert "ingest_haushalt.py" in plan.nachschub
    lsn_bestand.close()


def test_jede_schicht_ohne_selbstlauf_sagt_wo_sie_herkommt():
    """Ohne ``nachschub`` stünde in der Meldung des Cron ein leeres Feld —
    und die Schicht wäre genau die, die man von Hand nachziehen müsste."""
    for key in finanzquellen.REIHENFOLGE:
        q = finanzquellen.QUELLEN[key]
        if not q.automatisch:
            assert q.nachschub, f"{key} sagt nicht, woher der Nachschub kommt"
        assert q.herkunft in finanzquellen.STELLEN, f"{key}: Herkunft ohne Klartext"


# --- Die Doku zählt nach, sie legt nichts fest ------------------------------

#: Zahlwörter, wie die Doku sie schreibt. Nur so weit, wie diese Zahlen
#: realistisch wachsen — eine vollständige Tabelle wäre toter Code.
ZAHLWORT = {
    "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10,
    "elf": 11, "zwölf": 12, "dreizehn": 13, "vierzehn": 14, "fünfzehn": 15,
    "sechzehn": 16, "siebzehn": 17, "achtzehn": 18, "neunzehn": 19,
    "zwanzig": 20,
}

DOKU = ROOT / "docs-site" / "src" / "content" / "docs" / "haushalt.md"
CRON = ROOT / "scripts" / "check_finanzdaten.py"


def test_die_doku_nennt_die_richtige_zahl_der_schichten():
    """„Fünfzehn Datenschichten … Neun liest er selbst" muss stimmen.

    Diese Zahlen standen zweimal falsch in der Doku: erst „sechs", dann
    „dreizehn … die sieben", während ``REIHENFOLGE`` längst weitergewachsen
    war (Befund 19.08.2026 — real 15/9/6). Sie stehen im Fließtext und lassen
    sich beim Lesen nicht widerlegen; wer den Bereich kennenlernt, glaubt sie.

    Der Test prüft die Aussage, nicht den Wortlaut: Er sucht das Zahlwort vor
    „Datenschichten" und vergleicht es mit ``REIHENFOLGE``.
    """
    import re

    gesamt = len(finanzquellen.REIHENFOLGE)
    automatisch = sum(1 for k in finanzquellen.REIHENFOLGE
                      if finanzquellen.QUELLEN[k].automatisch)

    doku = DOKU.read_text(encoding="utf-8")
    treffer = re.search(r"\*\*(\w+)\*\* Datenschichten", doku)
    assert treffer, (
        'Der Satz "**N** Datenschichten" steht nicht mehr in haushalt.md — '
        'wurde er umformuliert, gehört dieser Test nachgezogen')
    genannt = ZAHLWORT.get(treffer.group(1).lower())
    assert genannt == gesamt, (
        f'haushalt.md nennt "{treffer.group(1)} Datenschichten", '
        f'finanzquellen.REIHENFOLGE führt {gesamt}')

    # Dieselbe Zahl im Docstring des Jobs, der sie abarbeitet.
    cron = CRON.read_text(encoding="utf-8")
    im_cron = re.search(r"von (\w+) Datenschichten", cron)
    assert im_cron and ZAHLWORT.get(im_cron.group(1).lower()) == gesamt, (
        f"check_finanzdaten.py nennt eine andere Zahl als die {gesamt} aus "
        "REIHENFOLGE")

    # Und die Aufteilung: wie viele der Job selbst nachzieht.
    selbst = re.search(r"holt die \*\*(\w+)\*\*", cron)
    assert selbst and ZAHLWORT.get(selbst.group(1).lower()) == automatisch, (
        f"check_finanzdaten.py sagt nicht, dass es {automatisch} automatische "
        "Schichten sind")


# --------------------------------------------------------------------------
# Die UND-Falle in Erkennung.where()
# --------------------------------------------------------------------------

def test_jede_erkennung_findet_ein_dokument_das_zu_ihr_passt(tmp_path):
    """Ein Label, das EIN Muster einer Quelle erfüllt, muss sie auch finden.

    `Erkennung.where()` verknüpft Muster mit UND, solange `oder` nicht gesetzt
    ist. Bei EINEM Muster ist das egal, bei mehreren fast nie richtig: Die
    Wirtschaftsplan-Quelle führte drei Schreibweisen desselben Worts
    („Wirtschaftsplan", „Wirtschafts- und Finanzplan", „Wirtschafts-und
    Finanzplan"). Ein Label hätte alle drei gleichzeitig tragen müssen — die
    Erkennung traf also nie ein einziges Dokument, von 08/2026 bis zum 20.08.

    Gemerkt hat es niemand, weil damals nur `finanz_muster()` diese Muster las
    und sich sein ODER selbst baut. Der erste Aufruf über den normalen Weg
    (`source.dokumente()`) bekam eine leere Liste — ohne Fehler, ohne Warnung.

    Dieser Test geht den normalen Weg für JEDE Quelle mit Erkennung.
    """
    store = CouncilStore(tmp_path / "erkennung.sqlite")
    try:
        blind: list[str] = []
        for key in finanzquellen.REIHENFOLGE:
            erkennung = getattr(finanzquellen.QUELLEN[key], "erkennung", None)
            if erkennung is None:
                continue
            muster = tuple(getattr(erkennung, "label_muster", None) or ())
            if not muster:
                continue          # Quellen, die am Text erkennen, prüft dieser Test nicht
            with store._conn:
                store._conn.execute("DELETE FROM council_anlagen")
                for i, m in enumerate(muster):
                    # Aus dem LIKE-Muster ein Label bauen, das genau IHM genügt.
                    label = m.replace("%", "")
                    store._conn.execute(
                        "INSERT INTO council_anlagen (document_id, kvonr, label, url, "
                        "raw_text, n_pages, fetched_at, status) "
                        "VALUES (?, 1, ?, 'https://x', 'x', 999, datetime('now'), 'ok')",
                        (1000 + i, label))
            sql, werte = erkennung.abfrage("document_id")
            treffer = store._conn.execute(sql, werte).fetchall()
            if not treffer:
                blind.append(f"{key} (Muster: {', '.join(muster)})")
        assert not blind, ("Diese Quellen finden kein Dokument, das eines ihrer "
                           "eigenen Label-Muster erfüllt — vermutlich fehlt "
                           "`oder=True`: " + "; ".join(blind))
    finally:
        store.close()
