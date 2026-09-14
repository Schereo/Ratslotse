"""Die Niederschrift in ihre Tagesordnungspunkte schneiden.

Die Fixtures sind **echte, gekürzte** Protokolle der vier Städte, die welche
liefern — ohne die Anwesenheitsliste, und Namen durch Rollen ersetzt. Ein
selbstgebautes Beispiel hätte genau die Eigenheiten nicht, an denen der erste
Entwurf gescheitert ist: dass die Tagesordnung zweimal im Dokument steht, und
dass jeder zweite Beschlusstext mit „1. Die Verwaltung …" beginnt.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from council.cities.protocol import (MIN_TEXT, SPLITTER_VERSION, attach_sections,
                                     detect_layout, split_meeting, split_protocol)
from council.cities.store import CitiesStore

FIXTURES = Path(__file__).parent / "fixtures" / "cities"


def _text(stadt: str) -> str:
    return (FIXTURES / f"protokoll_{stadt}.txt").read_text(encoding="utf-8")


# --------------------------------------------------------- Layout erkennen

@pytest.mark.parametrize("stadt,layout", [
    ("muenster", "punkt"),        # „Punkt 4 der Tagesordnung"
    ("osnabrueck", "zu"),         # „Zu 4  Titel"
    ("braunschweig", "nummer"),   # „4. Titel"
    ("potsdam", "nummer"),        # „4 Titel"
])
def test_layout_kommt_aus_dem_text_nicht_aus_dem_hersteller(stadt, layout):
    """Osnabrück und Braunschweig sprechen beide ALLRIS 4 — und schreiben verschieden."""
    assert detect_layout(_text(stadt)) == layout


def test_ohne_erkennbare_gliederung_lieber_nichts():
    assert detect_layout("Ein Fließtext ohne jede Nummerierung.") is None
    assert split_protocol("Ein Fließtext.", [("a", "1", "Eröffnung")]) == []


# ------------------------------------------------------------- Der Schnitt

def test_muenster_die_punkte_bekommen_ihren_text():
    punkte = [("a1", "1", "Festsetzung der Tagesordnung"),
              ("a2", "2", "Anmerkungen zur Niederschrift der letzten öffentlichen Sitzung"),
              ("a3", "3", "Mitteilungen")]
    abschnitte = split_protocol(_text("muenster"), punkte)

    assert [a.key for a in abschnitte] == ["a1", "a2", "a3"]
    assert [a.number for a in abschnitte] == ["1", "2", "3"]
    # Der Abschnitt endet an der nächsten Überschrift, nicht am Dokumentende.
    assert "Punkt 2 der Tagesordnung" not in abschnitte[0].text


def test_osnabrueck_zu_vier_ist_die_ueberschrift():
    punkte = [("a1", "1", "Feststellung der Ordnungsgemäßheit der Ladung, der "
                          "Anwesenheit und der Beschlussfähigkeit"),
              ("a2", "2", "Genehmigung des Protokolls (öffentlicher Teil) über die "
                          "Sitzung vom 05.02.2026")]
    abschnitte = split_protocol(_text("osnabrueck"), punkte)

    assert [a.key for a in abschnitte] == ["a1", "a2"]
    assert "Beratungsverlauf" in abschnitte[0].text


def test_das_inhaltsverzeichnis_zaehlt_nicht_als_abschnitt():
    """Jede Niederschrift trägt ihre Tagesordnung zweimal.

    Wer die erste nimmt, bekommt Überschriften ohne Text — und ein Modell,
    das daraus ein „Warum" bauen soll, erfindet eines.
    """
    text = _text("braunschweig")
    punkte = [("a1", "1", "Eröffnung der Sitzung"), ("a2", "2", "Mitteilungen")]
    abschnitte = split_protocol(text, punkte)

    assert len(abschnitte) == 2
    # Der gewählte Anker liegt hinter dem Verzeichnis …
    verzeichnis = text.index("Tagesordnung")
    protokoll = text.rindex("Eröffnung der Sitzung")
    assert abschnitte[0].start > verzeichnis
    assert abschnitte[0].start <= protokoll
    # … und der Text ist der Protokolltext, nicht die nächste Zeile der Liste.
    assert "eröffnet die Sitzung" in abschnitte[0].text


def test_eine_beschlussaufzaehlung_ist_kein_tagesordnungspunkt():
    """„1. Die Verwaltung setzt SAP …" beginnt keinen neuen Punkt.

    Genau daran ist der erste Entwurf gescheitert: Er fand in Braunschweig
    fünf statt sieben Punkte, und die gefundenen trugen Beschlusssätze als
    Titel. Der Titel des echten Punktes entscheidet.
    """
    punkte = [("a4", "4", "SAP-Umstellung auf S/4HANA")]
    abschnitte = split_protocol(_text("braunschweig"), punkte)

    assert len(abschnitte) == 1
    assert abschnitte[0].title == "SAP-Umstellung auf S/4HANA"
    assert "Beschluss" in abschnitte[0].text


def test_eine_nummer_ohne_passenden_titel_wird_nicht_zugeordnet():
    """Lieber kein Abschnitt als der falsche."""
    punkte = [("a9", "9", "Ein Punkt, den dieses Protokoll gar nicht kennt")]
    assert split_protocol(_text("potsdam"), punkte) == []


def test_kurze_abschnitte_fallen_heraus():
    punkte = [("a1", "1", "Eröffnung der Sitzung")]
    lang = split_protocol(_text("braunschweig"), punkte)
    assert lang and len(lang[0].text) >= MIN_TEXT


# --------------------------------------------------------------- Die Ablage

def test_abschnitte_landen_in_der_datenbank_und_ueberschreiben_sich(tmp_path):
    from council.cities.model import AgendaItem, Batch, Meeting

    main = CitiesStore(tmp_path / "cities.sqlite")
    try:
        main.upsert_batch(Batch(
            meetings=[Meeting("m1", "muenster", None, "Sitzung", "2026-07-07")],
            agenda_items=[
                AgendaItem("a1", "m1", "Festsetzung der Tagesordnung", "1", 0),
                AgendaItem("a2", "m1",
                           "Anmerkungen zur Niederschrift der letzten öffentlichen Sitzung",
                           "2", 1),
            ]))
        n = split_meeting(main, "m1", "f1", _text("muenster"))
        assert n == 2

        zeile = main.protocol_section("a1", SPLITTER_VERSION)
        assert zeile is not None
        assert zeile["number"] == "1" and zeile["file_id"] == "f1"
        assert main.protocol_sections_of("m1", SPLITTER_VERSION)[0]["agenda_item_id"] == "a1"

        # Ein zweiter Lauf derselben Fassung legt nichts doppelt ab.
        assert split_meeting(main, "m1", "f1", _text("muenster")) == 2
        assert len(main.protocol_sections_of("m1", SPLITTER_VERSION)) == 2
    finally:
        main.close()


def test_arbeitsliste_kennt_nur_ungeschnittene_niederschriften(tmp_path):
    from council.cities.model import Batch, File, FileRole, Meeting
    from council.cities.text import EXTRACTOR, VERSION

    main = CitiesStore(tmp_path / "cities.sqlite")
    try:
        main.upsert_batch(Batch(
            meetings=[Meeting("m1", "muenster", None, "Sitzung", "2026-07-07")],
            files=[File("f1", "muenster", FileRole.PROTOCOL, meeting_id="m1"),
                   File("f2", "muenster", FileRole.MAIN, paper_id=None)]))
        main.put_text("f1", EXTRACTOR, VERSION, _text("muenster"), 4, "ok")
        main.put_text("f2", EXTRACTOR, VERSION, "Eine Vorlage.", 1, "ok")

        offen = main.protocols_with_text(EXTRACTOR, VERSION, SPLITTER_VERSION)
        assert [d["file_id"] for d in offen] == ["f1"], "nur Protokolle, nur mit Text"

        attach_sections(main, "m1", "f1", split_protocol(
            _text("muenster"), [("a1", "1", "Festsetzung der Tagesordnung")]))
        assert main.protocols_with_text(EXTRACTOR, VERSION, SPLITTER_VERSION) == []
    finally:
        main.close()
