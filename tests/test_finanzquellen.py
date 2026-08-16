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
    assert any("2026 nicht übernommen" in z for z in p.warnungen)
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
    ohne = check_finanzdaten._hinweis_text(stand, {}, date(2027, 11, 1))
    assert "kein passendes Dokument" in ohne

    gesehen = {"jahresabschluss": {z for z in range(2000, 2100)}}
    mit = check_finanzdaten._hinweis_text(stand, gesehen, date(2027, 11, 1))
    assert "wird aber nicht übernommen" in mit
    bestand.close()
