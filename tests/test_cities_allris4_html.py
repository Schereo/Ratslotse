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


# --------------------------------------------------------- Der Index (si018)

class _Antworten:
    """Ein Client-Ersatz, der vorbereitete Seiten liefert und mitschreibt."""

    def __init__(self, seiten: dict[str, str]):
        self.seiten = seiten
        self.body_id = "teststadt"
        self.gerufen: list[str] = []

    def get_text(self, url: str, headers: dict | None = None) -> str:
        self.gerufen.append(url)
        if url not in self.seiten:
            raise LookupError(url)
        return self.seiten[url]


def _huelle(version: str) -> str:
    return f'<script>Wicket.Ajax.ajax({{"u":"./si018?{version}.0-form-searchPanel-search"}});</script>'


def _seite(silinks: list[str], weiter: str | None) -> str:
    zeilen = "".join(f'<tr><td><a id="silink_{n}">Sitzung {n}</a></td></tr>' for n in silinks)
    nav = f'<script>Wicket.Ajax.ajax({{"u":"{weiter}"}});</script>' if weiter else ""
    return f"<table>{zeilen}</table>{nav}"


def test_der_index_blaettert_bis_zum_ende():
    W = "https://beispiel.example.org/public"
    client = _Antworten({
        f"{W}/si018": _huelle("0-1"),
        f"{W}/si018?0-1.0-": _seite(
            ["11", "12"], f"{W}/si018?0-1.1-navigator-next"),
        f"{W}/si018?0-1.1-navigator-next": _seite(
            ["13"], f"{W}/si018?0-1.2-navigator-next"),
        # Die letzte Seite wiederholt, was schon da ist — so hört ALLRIS auf.
        f"{W}/si018?0-1.2-navigator-next": _seite(["13"], None),
    })
    assert Allris4HtmlAdapter.sitzungsindex(client, W) == {"11", "12", "13"}


def test_die_seitenversion_wird_gelesen_nicht_gesetzt():
    """Wicket zählt sie je Sitzung hoch — festgeschrieben liefert sie nichts.

    Genau daran ist die erste Fassung gescheitert: Nach einem
    vorangegangenen Abruf stand die Übersicht bei Seite 6, der fest
    verdrahtete Aufruf `si018?0-1.0-` bekam eine leere Antwort, und
    Wolfsburg galt mit „0 Sitzungen" als nicht erntbar statt mit 652.
    """
    W = "https://beispiel.example.org/public"
    client = _Antworten({
        f"{W}/si018": _huelle("6-1"),
        f"{W}/si018?6-1.0-": _seite(["99"], None),
    })
    assert Allris4HtmlAdapter.sitzungsindex(client, W) == {"99"}
    assert f"{W}/si018?0-1.0-" not in client.gerufen


def test_der_index_liest_beide_kennungsformen():
    """Wolfsburg setzt ``silink_<n>``, Laatzen echte ``SILFDNR=<n>``-Adressen."""
    W = "https://beispiel.example.org/public"
    gemischt = ('<a id="silink_11">a</a>'
                '<a href="to010?SILFDNR=22">b</a>')
    client = _Antworten({
        f"{W}/si018": _huelle("0-1"),
        f"{W}/si018?0-1.0-": gemischt,
    })
    assert Allris4HtmlAdapter.sitzungsindex(client, W) == {"11", "22"}


def test_ohne_uebersicht_bleibt_der_index_leer_statt_zu_stuerzen():
    """Eine Stadt ohne ``si018`` darf den Lauf nicht mitnehmen."""
    client = _Antworten({})
    assert Allris4HtmlAdapter.sitzungsindex(client, "https://x.example.org") == set()


# --------------------------------------------------- Die Gremien (gr010)

class _MitAblage(_Antworten):
    """Wie ``_Antworten``, aber mit einer Rohablage, in die der Adapter legt."""

    def __init__(self, seiten: dict[str, str], store: CitiesStore):
        super().__init__(seiten)
        self.raw = store
        self.body_id = "teststadt"


def test_die_gremien_stehen_in_gr010_und_zwar_in_cdata(tmp_path):
    """``gr020`` ohne Kennung antwortet bei allen drei Städten mit HTTP 500.

    Die Liste steht in ``gr010``, kommt erst auf den Selbstaufruf hin, und
    ihre Namen liegen in CDATA — als HTML gelesen findet man dort kein
    einziges ``<a>``.
    """
    W = "https://beispiel.example.org/public"
    ajax = (
        '<?xml version="1.0" encoding="UTF-8"?><ajax-response>'
        '<component id="id7"><![CDATA['
        f'<a href="{W}/gr020?GRLFDNR=3" id="gr_3">Rat der Stadt</a>'
        f'<a href="{W}/to010?SILFDNR=99" id="grLast_3">Sitzung öffnen</a>'
        f'<a href="{W}/gr020?GRLFDNR=5" id="gr_5">Verwaltungsausschuss</a>'
        ']]></component></ajax-response>')
    store = CitiesStore(tmp_path / "raw.sqlite")
    client = _MitAblage({
        f"{W}/gr010": '<script>Wicket.Ajax.ajax({"u":"./gr010?2-1.0-"});</script>',
        f"{W}/gr010?2-1.0-": ajax,
    }, store)
    gremien = list(Allris4HtmlAdapter().iter_organizations(
        client, {"id": W}))
    assert [g["name"] for g in gremien] == ["Rat der Stadt", "Verwaltungsausschuss"]
    # Der „Sitzung öffnen"-Verweis daneben ist keins.
    assert all("GRLFDNR=" in g["id"] for g in gremien)
    store.close()


def test_ohne_cdata_wird_die_antwort_direkt_gelesen():
    """Nicht jede Fassung packt ihre Stücke ein — beides muss gehen."""
    from council.cities.adapters.allris4_html import _cdata
    assert _cdata("<a>x</a>") == ["<a>x</a>"]
    assert _cdata("<r><![CDATA[<a>x</a>]]><![CDATA[<b>y</b>]]></r>") == [
        "<a>x</a>", "<b>y</b>"]


def test_nichtoeffentliche_sitzungen_werden_kein_objekt(tmp_path):
    """ALLRIS antwortet für sie mit HTTP 200 und einer Absage-Hülle.

    Daraus eine Sitzung zu bauen hieße, einen Geist anzulegen: namens
    „Sitzung", ohne Datum, ohne Tagesordnung — und der zählt in jeder
    Kennzahl mit, als fehlten UNS die Daten. Gemessen an Wolfsburg: 77 von
    255 Sitzungen sind so.
    """
    store = CitiesStore(tmp_path / "raw.sqlite")
    zu = f"{WURZEL}/to010?SILFDNR=1003196"
    store.put_raw_object("wolfsburg", "meeting", zu, {
        "id": zu,
        "html": "<main><h1>Keine Information verfügbar</h1><p>Zu den von Ihnen "
                "gewählten Elementen ist keine weiterführende Information "
                "verfügbar, oder Sie sind nicht berechtigt.</p></main>"})
    store.put_raw_object("wolfsburg", "meeting", SITZUNG, {
        "id": SITZUNG,
        "html": (FIXTURES / "laatzen_to010.html").read_text(encoding="utf-8")})
    batch = get_adapter("allris4_html").normalize("wolfsburg", store)
    assert [m.id for m in batch.meetings] == [SITZUNG]
    store.close()


def test_die_ergebnisspalte_heisst_je_stadt_anders():
    """Laatzen schreibt „Zuständigkeit", Wolfsburg „Beschlussart".

    Ein Rückfall auf eine feste Spaltennummer traf bei Wolfsburg ins Leere:
    0 von 1.358 Beratungen mit Ergebnis, ohne Fehler und ohne Auffälligkeit.
    """
    suppe = BeautifulSoup(
        '<table id="toTreeTable">'
        '<tr><th>+/-</th><th>TOP</th><th>Betreff</th><th>Vorlage</th>'
        '<th>Beschlussart</th></tr>'
        '<tr><td></td><td>Ö 1</td><td>Ein Antrag</td><td></td>'
        '<td>ungeändert beschlossen</td></tr>'
        "</table>", "html.parser")
    punkte = Allris4HtmlAdapter()._punkte(suppe, "m1", "wolfsburg", [])
    assert [p.result_raw for p in punkte] == ["ungeändert beschlossen"]
    assert punkte[0].outcome is Outcome.ACCEPTED
