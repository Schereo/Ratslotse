"""ALLRIS 4 über die Oberfläche — gegen echte Seiten aus Laatzen.

Die beiden Fixtures sind unveränderte Antworten von
``ratsinfo.laatzen.de`` (geholt am 10.09.2026), nur ohne Skripte, Stile und
Personennamen. Das ist der Grund, warum diese Tests etwas beweisen: Beim
HTML-Lesen scheitert man nicht an der Struktur, die man sich ausdenkt,
sondern an der, die die Anwendung wirklich ausliefert.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from council.cities.adapters import get_adapter
from council.cities.adapters._common import SYNTHETISCHE_KENNUNG
from council.cities.adapters.allris4_html import Allris4HtmlAdapter, _grunddaten
from council.cities.model import FileRole, Outcome, PaperKind
from council.cities.registry import BODIES
from council.cities.store import CitiesStore

FIXTURES = Path(__file__).parent / "fixtures" / "cities"
WURZEL = "https://ratsinfo.laatzen.de/public"
SITZUNG = f"{WURZEL}/to010?SILFDNR=1000073"
VORLAGE = f"{WURZEL}/vo020?VOLFDNR=1000238"


@pytest.fixture()
def batch(tmp_path):
    store = CitiesStore(tmp_path / "raw.sqlite")
    store.put_raw_object("laatzen", "meeting", SITZUNG, {
        "id": SITZUNG,
        "html": (FIXTURES / "laatzen_to010.html").read_text(encoding="utf-8")})
    store.put_raw_object("laatzen", "paper", VORLAGE, {
        "id": VORLAGE,
        "html": (FIXTURES / "laatzen_vo020.html").read_text(encoding="utf-8")})
    yield get_adapter("allris4_html").normalize("laatzen", store)
    store.close()


def test_die_sitzung_bekommt_titel_datum_und_uhrzeit(batch):
    (sitzung,) = batch.meetings
    assert sitzung.name == "Sitzung des Schulausschusses"
    # Datum und Uhrzeit stehen in zwei Feldern und müssen zusammenfinden —
    # eine Sitzung ohne Startzeit gilt der ALLRIS-Blätterung als undatiert.
    assert sitzung.start == "2026-09-01T18:00:00"


def test_die_tagesordnung_kommt_vollstaendig_mit_ergebnis(batch):
    punkte = sorted(batch.agenda_items, key=lambda a: a.position)
    assert [p.number for p in punkte] == ["1", "2", "3", "4"]
    assert all(p.public for p in punkte), "der öffentliche Teil ist öffentlich"
    assert punkte[3].outcome is Outcome.NOTED, punkte[3].result_raw


def test_ein_punkt_mit_inhalt_traegt_seine_echte_adresse(batch):
    """Sonst hielte ``zwillinge_zusammenfuehren`` jeden Punkt für erfunden.

    ``#top-`` ist projektweit die Marke für eine selbst gebaute Kennung. Die
    Punkte, die ALLRIS eine ``TOLFDNR`` gibt, haben eine echte — und die ist
    die Adresse, unter der der Punkt wirklich steht.
    """
    echte = [a for a in batch.agenda_items if SYNTHETISCHE_KENNUNG not in a.id]
    assert [a.number for a in echte] == ["3", "4"]
    assert all("to020?TOLFDNR=" in a.id for a in echte)
    # Die beiden Formalpunkte haben keine — dort ist die Marke richtig.
    erfunden = [a for a in batch.agenda_items if SYNTHETISCHE_KENNUNG in a.id]
    assert [a.number for a in erfunden] == ["1", "2"]


def test_die_vorlage_erbt_ihr_datum_aus_der_beratungsfolge(batch):
    (vorlage,) = batch.papers
    assert vorlage.name.startswith("Bildungscampus Laatzen")
    assert vorlage.reference == "1000238"
    # Die Vorlagenseite trägt selbst kein Datum; genommen wird die früheste
    # Station — der Tag, an dem die Sache in den Gang kam.
    assert vorlage.date == "2026-06-29"


def test_die_art_heisst_vorlageart_ohne_n(batch):
    """Ein Buchstabe, und jede Vorlage des Dialekts wäre „other"."""
    (vorlage,) = batch.papers
    assert vorlage.paper_type_raw == "Antrag"
    assert vorlage.kind is PaperKind.MOTION


def test_genau_ein_hauptdokument_je_vorlage(batch):
    """An jeder Laatzener Vorlage hängen „Vorlage" UND „Sammeldokument"."""
    haupt = [f for f in batch.files if f.role == FileRole.MAIN]
    assert [f.name for f in haupt] == ["Vorlage"]
    buendel = [f for f in batch.files if f.name == "Sammeldokument"]
    assert buendel and all(f.role == FileRole.AUXILIARY for f in buendel)


def test_die_beratung_haengt_an_ihrem_punkt_und_ihrer_vorlage(batch):
    """Beide entstehen aus derselben Tabellenzeile — nie zu raten."""
    punkte = {a.id for a in batch.agenda_items}
    assert batch.consultations
    for c in batch.consultations:
        assert c.agenda_item_id in punkte
        assert c.meeting_id == SITZUNG
        assert "VOLFDNR=" in c.paper_id
    # Die „Zuständigkeit" der Tagesordnung ist die Rolle der Station.
    assert {c.role_raw for c in batch.consultations} == {"Vorberatung",
                                                         "Kenntnisnahme"}


def test_die_beratungsfolge_liest_zwei_zeilen_je_station():
    """ALLRIS setzt Status/Gremium/Beschluss und Datum/Sitzung untereinander.

    Wer Zeile für Zeile liest, bekommt lauter halbe Stationen.
    """
    suppe = BeautifulSoup(
        (FIXTURES / "laatzen_vo020.html").read_text(encoding="utf-8"),
        "html.parser")
    stationen = Allris4HtmlAdapter._beratungsfolge(suppe)
    assert stationen, "keine Beratungsfolge gelesen"
    for s in stationen:
        assert s["gremium"], s
    assert any(s["datum"] for s in stationen), "keine Station mit Datum"


def test_grunddaten_ueberleben_einen_umbau_der_tabelle():
    """Gelesen wird der Fließtext, nicht eine bestimmte Auszeichnung."""
    suppe = BeautifulSoup(
        (FIXTURES / "laatzen_to010.html").read_text(encoding="utf-8"),
        "html.parser")
    kopf = _grunddaten(suppe)
    assert kopf["Gremium"] == "Schulausschuss"
    assert kopf["Datum"].endswith("01.09.2026")
    assert kopf["Uhrzeit"] == "18:00"


@pytest.mark.parametrize("stadt", ["laatzen", "lueneburg", "wolfsburg"])
def test_die_registry_nennt_die_wurzel_nicht_ein_oparl_system(stadt):
    """Der Dialekt liest die Oberfläche — ``/oparl/system`` gäbe es dort nicht."""
    spec = BODIES[stadt]
    assert spec.dialect == "allris4_html"
    assert spec.system_url and not spec.system_url.endswith("/oparl/system")
    assert not spec.active, "erst nach einem Probelauf einschalten"
