"""ALLRIS classic — gegen echte Seiten aus Hildesheim.

Die Fixtures sind Antworten von ``stadt-hildesheim.de/allris`` (geholt am
11.09.2026), gekürzt um Skripte, Stile und die 105 kB Navigation, und mit
unkenntlich gemachten Personenfeldern. Sonst unverändert: Beim HTML-Lesen
scheitert man nicht an der Struktur, die man sich ausdenkt, sondern an der,
die die Anwendung wirklich ausliefert.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from council.cities.adapters import get_adapter
from council.cities.adapters._common import SYNTHETISCHE_KENNUNG
from council.cities.adapters.allris_classic import (AllrisClassicAdapter,
                                                    _grunddaten, _iso, _monate)
from council.cities.model import PaperKind
from council.cities.registry import BODIES
from council.cities.store import CitiesStore

FIXTURES = Path(__file__).parent / "fixtures" / "cities"
WURZEL = "https://www.stadt-hildesheim.de/allris"
SITZUNG = f"{WURZEL}/to010.asp?SILFDNR=3712"
VORLAGE = f"{WURZEL}/vo020.asp?VOLFDNR=8000"


def _suppe(name: str) -> BeautifulSoup:
    return BeautifulSoup((FIXTURES / name).read_text(encoding="utf-8"), "html.parser")


@pytest.fixture()
def batch(tmp_path):
    store = CitiesStore(tmp_path / "raw.sqlite")
    store.put_raw_object("hildesheim", "meeting", SITZUNG, {
        "id": SITZUNG,
        "html": (FIXTURES / "hildesheim_to010.html").read_text(encoding="utf-8")})
    store.put_raw_object("hildesheim", "paper", VORLAGE, {
        "id": VORLAGE,
        "html": (FIXTURES / "hildesheim_vo020.html").read_text(encoding="utf-8")})
    yield get_adapter("allris_classic").normalize("hildesheim", store)
    store.close()


def test_die_sitzung_bekommt_namen_datum_und_uhrzeit(batch):
    (sitzung,) = batch.meetings
    assert sitzung.name == "Sitzung des Rates der Stadt Hildesheim"
    # „Mo, 31.03.2025" und „18:00 - 22:00" stehen in zwei Feldern und müssen
    # zusammenfinden — eine Sitzung ohne Startzeit gilt als undatiert.
    assert sitzung.start == "2025-03-31T18:00:00"


def test_die_tagesordnung_kommt_ueber_die_zellklassen(batch):
    """Die Datenzeilen tragen mehr Zellen als die Kopfzeile.

    ALLRIS classic füllt mit Platzhaltern auf; ein Abzählen der Spalten ginge
    schief. Gelesen wird über ``td.text4`` (die Nummer) und die erste Zelle
    mit Text danach.
    """
    punkte = sorted(batch.agenda_items, key=lambda a: a.position)
    assert len(punkte) == 33
    assert [p.number for p in punkte[:4]] == ["1", "2", "3", "4"]
    assert punkte[0].name == "Eröffnung der Sitzung"


def test_der_buchstabe_vor_der_nummer_sagt_ob_der_punkt_oeffentlich_ist(batch):
    """Hildesheim trennt JE ZEILE (``Ö 1`` / ``N 1``).

    Andere Städte setzen dafür eine Zwischenüberschrift „Nicht öffentlicher
    Teil"; wer nur danach sucht, hält hier jeden Punkt für öffentlich.
    """
    oeffentlich = [a for a in batch.agenda_items if a.public]
    nicht = [a for a in batch.agenda_items if not a.public]
    assert oeffentlich and nicht, "beide Sorten müssen vorkommen"
    # Die nichtöffentlichen stehen hinten — der Teil kommt am Ende.
    assert min(a.position for a in nicht) > max(a.position for a in oeffentlich)


def test_ein_beratener_punkt_traegt_seine_auszugs_adresse(batch):
    """``to020.asp?TOLFDNR=…`` gibt es wirklich — das ist die echte Kennung.

    ``#top-`` ist projektweit die Marke einer selbst gebauten Kennung. Stünde
    sie an allen Punkten, hielte ``zwillinge_zusammenfuehren`` jeden Punkt
    dieses Dialekts für erfunden.
    """
    echte = [a for a in batch.agenda_items if SYNTHETISCHE_KENNUNG not in a.id]
    assert echte, "kein einziger Punkt mit Auszug"
    assert all("to020.asp?TOLFDNR=" in a.id for a in echte)


def test_die_vorlage_erbt_ihr_datum_aus_der_beratungsfolge(batch):
    (vorlage,) = batch.papers
    assert vorlage.reference == "23/224"
    assert vorlage.name.startswith("Bundesprogramm zur Anpassung")
    # Die Vorlagenseite trägt selbst kein Datum; genommen wird die früheste
    # Station — der Tag, an dem die Sache in den Gang kam.
    assert vorlage.date == "2023-06-14"


def test_ein_weggelassenes_feld_wandert_ins_nachbarfeld(batch):
    """``Verfasser:`` wird nicht gespeichert, muss die Regel aber beenden.

    Der erste Entwurf ließ es einfach weg — und damit lief der Wert des
    Feldes DAVOR weiter: Jede Vorlage bekam als Art „Mitteilungsvorlage
    Verfasser: …" samt Namen. Ein weggelassenes Feld verschwindet nicht.
    """
    (vorlage,) = batch.papers
    assert vorlage.paper_type_raw == "Mitteilungsvorlage"
    assert vorlage.kind is PaperKind.NOTICE


def test_keine_namen_von_verwaltungsmitarbeitenden(batch):
    """Ratsmitglieder dürfen benannt werden, Beschäftigte nicht."""
    kopf = _grunddaten(_suppe("hildesheim_vo020.html"))
    assert "Verfasser" not in kopf and "Bearbeiter/-in" not in kopf
    (vorlage,) = batch.papers
    assert "Nachname" not in (vorlage.paper_type_raw or "")
    assert "Nachname" not in vorlage.name


def test_die_beratungsfolge_liest_zwei_zeilen_je_station():
    """Zeile A trägt Gremium und Rolle, Zeile B Datum, Sitzung und Ergebnis.

    Wer Zeile für Zeile liest, bekommt lauter halbe Stationen.
    """
    stationen = AllrisClassicAdapter._beratungsfolge(_suppe("hildesheim_vo020.html"))
    assert len(stationen) == 2
    erste = stationen[0]
    assert erste["gremium"] == "Ausschuss für Stadtentwicklung, Umwelt und Mobilität"
    assert erste["rolle"] == "Information"
    assert erste["datum"] == "2023-06-14"
    assert erste["sitzung"] == "3358"
    assert erste["ergebnis"] == "zur Kenntnis genommen"


def test_die_beratung_haengt_an_ihrem_punkt(batch):
    """Beide entstehen aus derselben Tabellenzeile — nie zu raten."""
    punkte = {a.id for a in batch.agenda_items}
    assert batch.consultations
    for c in batch.consultations:
        assert c.agenda_item_id in punkte
        assert c.meeting_id == SITZUNG
        assert "VOLFDNR=" in c.paper_id


def test_der_vorlagentext_steht_in_der_seite(tmp_path):
    """An Hildesheims Vorlagen hängt kein einziger Datei-Verweis."""
    store = CitiesStore(tmp_path / "raw.sqlite")
    store.put_raw_object("hildesheim", "paper", VORLAGE, {
        "id": VORLAGE,
        "html": (FIXTURES / "hildesheim_vo020.html").read_text(encoding="utf-8")})
    texte = list(AllrisClassicAdapter().inline_texts(store, "hildesheim"))
    assert len(texte) == 1
    kennung, text = texte[0]
    assert kennung == f"{VORLAGE}#text"
    assert len(text) > 2000
    assert text.startswith("Mit der Vorlage")
    # Der Formularblock am Ende gehört nicht zum Sachverhalt.
    assert "Finanzielle Auswirkungen" not in text
    store.close()


def test_der_text_haengt_an_einer_datei_die_die_vorlage_kennt(batch):
    """`papers_with_text` verbindet über ``files.paper_id`` — ohne diese

    synthetische Hauptdatei bliebe der über ``inline_texts`` geschriebene
    Text für jede Auswertung unsichtbar, obwohl er in ``texts`` steht.
    Gemessen an Hannover: 25.729 Vorlagen, 0 % „mit Text" trotz
    erfolgreichem ``extract_inline`` — bis diese Datei dazukam (11.09.2026).
    """
    (vorlage,) = batch.papers
    (datei,) = batch.files
    assert datei.id == f"{vorlage.id}#text"
    assert datei.paper_id == vorlage.id
    assert datei.role.value == "main"


def test_der_kalender_wird_monat_fuer_monat_rueckwaerts_gelesen():
    """Neueste zuerst — ein abgebrochener Lauf hat dann die Gegenwart schon."""
    monate = _monate("2026-06")
    assert monate[0] > monate[-1], "neueste zuerst"
    assert monate[-1] == (2026, 6)
    assert len(_monate("2007-01")) > 200, "die ganze Historie passt hinein"


@pytest.mark.parametrize("roh,zeit,erwartet", [
    ("Mo, 31.03.2025", "18:00 - 22:00", "2025-03-31T18:00:00"),
    ("14.06.2023", None, "2023-06-14"),
    ("kein Datum", None, None),
])
def test_datum_und_uhrzeit(roh, zeit, erwartet):
    assert _iso(roh, zeit) == erwartet


def test_die_registry_nennt_die_wurzel_und_holt_keine_dateien():
    """Der Text steht in der Seite — PDFs zu holen gäbe es dort gar nicht."""
    spec = BODIES["hildesheim"]
    assert spec.dialect == "allris_classic"
    assert spec.system_url and spec.system_url.endswith("/allris")
    assert not spec.fetch_files
    assert not spec.active, "erst nach einem Probelauf einschalten"


# ------------------------------------------------------- Der Auszug je Punkt

AUSZUG = f"{WURZEL}/to020.asp?TOLFDNR=76127"


@pytest.fixture()
def mit_auszug(tmp_path):
    """Sitzung, Vorlage **und** der Auszug eines ihrer Punkte."""
    store = CitiesStore(tmp_path / "raw.sqlite")
    for kind, kennung, datei in (
            ("meeting", SITZUNG, "hildesheim_to010.html"),
            ("paper", VORLAGE, "hildesheim_vo020.html"),
            ("excerpt", AUSZUG, "hildesheim_to020.html")):
        store.put_raw_object("hildesheim", kind, kennung, {
            "id": kennung,
            "html": (FIXTURES / datei).read_text(encoding="utf-8")})
    yield store
    store.close()


def test_der_auszug_zerfaellt_in_seine_drei_abschnitte():
    """ALLRIS bettet sie als eigene, aus RTF konvertierte Dokumente ein.

    Verschachtelte ``<html>``-Bäume mitten in der Seite — ein einzelner
    Parser-Lauf über das Ganze verlöre die Grenzen zwischen ihnen.
    """
    html = (FIXTURES / "hildesheim_to020.html").read_text(encoding="utf-8")
    teile = AllrisClassicAdapter.zerlege_auszug(html)
    assert set(teile) == {"WP", "BS", "AE"}
    assert teile["WP"].endswith("referierte die Vorlage.")
    assert teile["BS"].startswith("Beschluss:")
    assert teile["AE"] == "Abstimmungsergebnis: einstimmig mit zwei Enthaltungen"


def test_der_seitenfuss_haengt_nicht_am_letzten_abschnitt():
    """Ohne Schnitt endet die Abstimmung auf „zurück Nach oben Seite drucken"."""
    html = (FIXTURES / "hildesheim_to020.html").read_text(encoding="utf-8")
    teile = AllrisClassicAdapter.zerlege_auszug(html)
    for text in teile.values():
        assert "Nach oben" not in text and "Seite drucken" not in text


def test_der_auszug_traegt_ergebnis_und_beschlusstext(mit_auszug):
    """Er ist die bessere Quelle als die Beratungsfolge der Vorlage.

    Er nennt die Beschlussart des Punktes selbst — und gilt auch für Punkte,
    an denen gar keine Vorlage hängt.
    """
    batch = get_adapter("allris_classic").normalize("hildesheim", mit_auszug)
    (punkt,) = [a for a in batch.agenda_items if a.id == AUSZUG]
    assert punkt.result_raw == "ungeändert beschlossen"
    assert punkt.outcome.value == "accepted"
    # Die Beschriftung gehört nicht in den Beschlusstext.
    assert punkt.resolution_text == "Der Annahme der Zuwendungen wird zugestimmt."


def test_offen_ist_kein_ergebnis(tmp_path):
    """„(offen)" ist ALLRIS' Wort für „noch nichts entschieden".

    Als Ergebnis geführt wäre es die Behauptung, es gäbe eines.
    """
    html = (FIXTURES / "hildesheim_to020.html").read_text(encoding="utf-8")
    store = CitiesStore(tmp_path / "raw.sqlite")
    store.put_raw_object("hildesheim", "meeting", SITZUNG, {
        "id": SITZUNG,
        "html": (FIXTURES / "hildesheim_to010.html").read_text(encoding="utf-8")})
    store.put_raw_object("hildesheim", "excerpt", AUSZUG, {
        "id": AUSZUG,
        "html": html.replace("ungeändert beschlossen", "(offen)")})
    batch = get_adapter("allris_classic").normalize("hildesheim", store)
    (punkt,) = [a for a in batch.agenda_items if a.id == AUSZUG]
    assert punkt.result_raw is None
    assert punkt.outcome.value == "none"
    store.close()


def test_ein_abschnitt_ist_alles_was_zu_dem_punkt_passierte(mit_auszug):
    """Beratung, Beschluss und Abstimmung zusammen.

    So liefert ihn der Schnitt einer Niederschrift bei den anderen Städten
    auch. Getrennt abgelegt läse das Modell zum „Warum" die halbe Geschichte.
    """
    zeilen = AllrisClassicAdapter().auszug_abschnitte(mit_auszug, "hildesheim")
    assert len(zeilen) == 1
    file_id, meeting_id, _ord, punkt_id, nummer, titel, text = zeilen[0]
    # Die Auszugs-Adresse IST das Dokument.
    assert file_id == AUSZUG and punkt_id == AUSZUG
    assert meeting_id == SITZUNG
    assert nummer and titel
    assert "referierte die Vorlage" in text
    assert "Der Annahme der Zuwendungen wird zugestimmt" in text
    assert "einstimmig mit zwei Enthaltungen" in text


def test_das_fenster_schuetzt_vor_zehntausend_abrufen():
    """Ein Auszug je beratenem Punkt heißt seit 2007 über 10.000 Seiten."""
    from datetime import date

    from council.cities.adapters.allris_classic import AUSZUG_MONATE, _fenster
    assert AUSZUG_MONATE == 24
    assert _fenster(24, date(2026, 9, 11)) == "2024-09-01"
    # Über den Jahreswechsel hinweg darf nicht Monat 0 herauskommen.
    assert _fenster(24, date(2026, 1, 15)) == "2024-01-01"
