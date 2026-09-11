"""Hannover SIM — gegen echte Seiten des Notes/Domino-Sitzungsmanagements.

Die Fixtures sind Antworten von
``e-government.hannover-stadt.de/lhhsimwebre.nsf`` (geholt am 11.09.2026),
gekürzt um Skripte, Stile und die Kopf-/Fußzeilen-Navigation der
Stadt-Website, mit unkenntlich gemachten Anreden. Sonst unverändert: Beim
HTML-Lesen scheitert man nicht an der Struktur, die man sich ausdenkt,
sondern an der, die die Anwendung wirklich ausliefert.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from council.cities.adapters import get_adapter
from council.cities.adapters._common import normalize_title
from council.cities.adapters.hannover_sim import (HannoverSimAdapter, _ergebnis_einordnen,
                                                   _iso)
from council.cities.model import Outcome, PaperKind
from council.cities.registry import BODIES
from council.cities.store import CitiesStore

FIXTURES = Path(__file__).parent / "fixtures" / "cities"
WURZEL = "https://e-government.hannover-stadt.de/lhhsimwebre.nsf"
SITZUNG = f"{WURZEL}/TM/20260622_AJHA"
VORLAGE = f"{WURZEL}/DS/0728-2026"
VORLAGE_OFFEN = f"{WURZEL}/DS/1418-2026"


def _suppe(name: str) -> BeautifulSoup:
    return BeautifulSoup((FIXTURES / name).read_text(encoding="utf-8"), "html.parser")


@pytest.fixture()
def batch(tmp_path):
    store = CitiesStore(tmp_path / "raw.sqlite")
    # Die drei Gremien, die in der Sitzungs- und Vorlagen-Fixture vorkommen —
    # ohne sie fände die Beratungsfolge kein passendes Gremium.
    for kennung, name in (
            (f"{WURZEL}/Ausschuss/AJHA", "Jugendhilfeausschuss"),
            (f"{WURZEL}/Ausschuss/AKultur", "Kulturausschuss"),
            (f"{WURZEL}/Stadtbezirk/TermineSTBR02", "Stadtbezirksrat Vahrenwald-List")):
        store.put_raw_object("hannover", "organization", kennung, {
            "id": kennung, "name": name, "meetings_url": kennung})
    store.put_raw_object("hannover", "meeting", SITZUNG, {
        "id": SITZUNG,
        "html": (FIXTURES / "hannover_meeting.html").read_text(encoding="utf-8")})
    store.put_raw_object("hannover", "paper", VORLAGE, {
        "id": VORLAGE,
        "html": (FIXTURES / "hannover_paper.html").read_text(encoding="utf-8")})
    yield get_adapter("hannover_sim").normalize("hannover", store)
    store.close()


def test_die_sitzung_bekommt_gremium_datum_und_uhrzeit(batch):
    (sitzung,) = batch.meetings
    assert sitzung.name == "Jugendhilfeausschuss am 22.06.2026"
    assert sitzung.start == "2026-06-22T15:00:00"
    assert sitzung.organization_id == f"{WURZEL}/Ausschuss/AJHA"


def test_die_tagesordnung_kommt_ueber_dezimalnummern(batch):
    """Datenzeilen haben mehr Struktur als eine Kopfzeile hergibt.

    Gelesen wird über die letzten beiden Zellen jeder Tabellenzeile — Nummer
    und Inhalt —, nicht über eine feste Spaltenzahl.
    """
    punkte = sorted(batch.agenda_items, key=lambda a: a.position)
    assert len(punkte) == 32
    assert punkte[0].number == "1"
    assert punkte[0].name.startswith("Eröffnung der Sitzung")
    assert punkte[1].number == "1.1"


def test_roemische_ziffern_und_die_gebuendelte_marke_fallen_heraus():
    """„I." (Abschnitts-Überschrift) und „24. ff." (nichtöffentliche Punkte,
    gebündelt) haben keine reine Dezimalnummer — derselbe Filter erledigt
    beide Fälle, ohne die Icon-Dateinamen des Seitenaufbaus zu kennen.
    """
    suppe = _suppe("hannover_meeting.html")
    nummern = [n for n, _, _ in HannoverSimAdapter._punkte(suppe)]
    assert "I" not in nummern and "I." not in nummern
    assert not any("ff" in n for n in nummern)


def test_alle_punkte_gelten_als_oeffentlich(batch):
    """Hannover zeigt nichtöffentliche Punkte nie einzeln, nur den einen

    Sammelverweis „Nichtöffentliche Tagesordnungspunkte" je Sitzung — der
    fällt schon über die Nummer heraus (s. oben). Was übrig bleibt, ist
    ausnahmslos der öffentliche Teil.
    """
    assert batch.agenda_items and all(a.public for a in batch.agenda_items)


def test_die_vorlage_liest_art_aktenzeichen_und_titel_aus_der_ueberschrift(batch):
    (vorlage,) = batch.papers
    assert vorlage.paper_type_raw == "Drucksache"
    assert vorlage.kind is PaperKind.PROPOSAL
    assert vorlage.reference == "0728/2026"
    assert vorlage.name.startswith("Umstrukturierungen des Betreuungsangebotes")
    # Die Vorlagenseite trägt selbst kein Datum — genommen wird die früheste
    # Station der Beratungsfolge.
    assert vorlage.date == "2026-05-04"


def test_die_beratungsfolge_verlinkt_ihre_sitzung_wo_sie_veroeffentlicht_ist():
    """Jede Station verlinkt — wenn die Sitzung existiert — direkt auf sie.

    Darüber lässt sich Beratung und Ergebnis eindeutig zuordnen, ohne einen
    Titel zu vergleichen wie bei anderen Städten.
    """
    stationen = HannoverSimAdapter()._beratungsfolge(_suppe("hannover_paper.html"))
    assert len(stationen) == 3
    erste = stationen[0]
    assert erste["gremium"] == "Stadtbezirksrat Vahrenwald-List"
    assert erste["datum"] == "2026-05-04"
    assert erste["meeting_id"] == f"{WURZEL}/TM/20260504_STBR02"
    assert erste["ergebnis"] == "Einstimmig"


def test_der_verwaltungsausschuss_hat_keine_sitzungsseite():
    """Die dritte Station nennt den Verwaltungsausschuss OHNE Verweis.

    Er steht in keiner der drei Sitzungslisten und hat kein Kürzel — seine
    Beratungen werden trotzdem erfasst (Datum, Ergebnis), nur ohne
    Sitzungsbezug. Was nicht veröffentlicht ist, bleibt unveröffentlicht.
    """
    stationen = HannoverSimAdapter()._beratungsfolge(_suppe("hannover_paper.html"))
    letzte = stationen[-1]
    assert letzte["gremium"] == "Verwaltungsausschuss"
    assert letzte["meeting_id"] is None
    assert letzte["ergebnis"] == "Einstimmig"


def test_die_beratung_traegt_ergebnis_und_wird_an_den_punkt_zurueckgeschrieben(batch):
    """Die Vorlage steht als Punkt 22.1 auf der Tagesordnung dieser Sitzung.

    Über die Verknüpfung — den Verweis der Beratungsfolge auf die Sitzung —
    findet die Beratung ihren Punkt eindeutig, nie über einen Titelabgleich.
    Ihr Ergebnis wird an GENAU diesen Punkt zurückgeschrieben.
    """
    (beratung,) = [c for c in batch.consultations if c.meeting_id == SITZUNG]
    assert beratung.role_raw == "Einstimmig"
    assert beratung.organization_id == f"{WURZEL}/Ausschuss/AJHA"
    assert beratung.agenda_item_id is not None

    (punkt,) = [a for a in batch.agenda_items if a.id == beratung.agenda_item_id]
    assert punkt.number == "22.1"
    assert punkt.result_raw == "Einstimmig"
    assert punkt.outcome is Outcome.ACCEPTED


def test_zukuenftige_ueberweisungen_ohne_datum_werden_nicht_erfasst():
    """„Zukünftig: Verwaltungsausschuss" — noch keine Sitzung, an die die

    Überweisung gehören könnte.
    """
    stationen = HannoverSimAdapter()._beratungsfolge(_suppe("hannover_paper_unresolved.html"))
    assert all(s["gremium"] != "" for s in stationen)
    assert not any(s["datum"] is None and s["meeting_id"] is None
                   and s["gremium"].strip() == "" for s in stationen)
    # Genau die terminierten Stationen — die Fixture hat vier, keine sechs
    # (zwei „Zukünftig:"-Zeilen fallen heraus).
    assert len(stationen) == 4


def test_eine_erzaehlende_verfahrensfrage_wird_nicht_als_sachentscheidung_gelesen():
    """„4 Ja-Stimmen, 6 Nein-Stimmen … nicht die erforderliche 2/3-Mehrheit"

    ist eine Dringlichkeits-Abstimmung über die Tagesordnung, kein
    Sachbeschluss über die Vorlage selbst — sie bleibt ohne Ergebnis.
    """
    stationen = HannoverSimAdapter()._beratungsfolge(_suppe("hannover_paper_unresolved.html"))
    erste = stationen[0]
    assert "2/3 Mehrheit" in erste["ergebnis"]
    assert _ergebnis_einordnen(erste["ergebnis"]) is Outcome.NONE


@pytest.mark.parametrize("text,erwartet", [
    ("6 Stimmen dafür, 5 Stimmen dagegen, 0 Enthaltungen", Outcome.ACCEPTED),
    ("4 Stimmen dafür, 7 Stimmen dagegen, 0 Enthaltungen", Outcome.REJECTED),
    ("5 Stimmen dafür, 5 Stimmen dagegen, 0 Enthaltungen", Outcome.NONE),
    ("Einstimmig", Outcome.ACCEPTED),
    ("Mit 38 Nein-Stimmen abgelehnt.", Outcome.REJECTED),
    ("Zur Kenntnis genommen", Outcome.NOTED),
    ("Beantwortet", Outcome.NONE),
])
def test_ergebnis_einordnen(text, erwartet):
    """Reine Stimmenzahlen ohne Zustimmungs- oder Ablehnungswort kennt

    ``model.outcome`` nicht — hier werden sie direkt verglichen. Bei
    Stimmengleichheit wird NICHTS vermutet. „Beantwortet" bleibt bewusst
    unklassifiziert: Hannovers Wort für eine beantwortete Anfrage ist noch
    nicht gemessen genug, um es einer der bestehenden Kategorien zuzuordnen —
    es taucht im Vokabular-Bericht von ``--pruefen`` auf.
    """
    assert _ergebnis_einordnen(text) is erwartet


def test_sondersitzung_findet_ihr_gremium_trotz_klammerzusatz():
    """„Ratsversammlung (Sondersitzung)" ist dieselbe Ratsversammlung.

    Ohne den Nachschlag ohne Klammer fanden zwei von 119 Sitzungen einer
    Stichprobe ihr Gremium nicht (11.09.2026).
    """
    gremien = {normalize_title("Ratsversammlung"): "kennung-rat"}
    treffer = HannoverSimAdapter._gremium_id(gremien, "Ratsversammlung (Sondersitzung)")
    assert treffer == "kennung-rat"


def test_eine_echte_gemeinsame_sitzung_bleibt_absichtlich_ohne_gremium():
    """Eine gemeinsame Sitzung mehrerer Gremien EINEM davon zuzuschlagen

    wäre erfunden — das Klammer-Entfernen träfe hier nichts, weil kein
    einzelnes Gremium den ganzen Namen trägt.
    """
    gremien = {normalize_title("Stadtentwicklungs- und Bauausschuss"): "kennung-abau"}
    text = ("Stadtentwicklungs- und Bauausschuss gemeinsam mit Stadtbezirksrat "
            "Nord, Ausschuss für Arbeitsmarkt- Wirtschafts- und "
            "Liegenschaftsangelegenheiten (Sondersitzung)")
    assert HannoverSimAdapter._gremium_id(gremien, text) is None


def test_der_verwaltungsausschuss_findet_kein_gremium():
    """Er steht in keiner der drei Sitzungslisten — absichtlich kein Treffer."""
    gremien = {normalize_title(n): f"k-{i}" for i, n in enumerate(
        ("Ratsversammlung", "Jugendhilfeausschuss", "Stadtbezirksrat Nord"))}
    assert HannoverSimAdapter._gremium_id(gremien, "Verwaltungsausschuss") is None


def test_der_inhalt_der_drucksache_steht_in_der_seite(tmp_path):
    """An Hannovers Vorlagen hängt eine PDF, aber der Text steht schon da —

    dieselbe Bahn wie bei Hildesheim. Die Kennung ist die der synthetischen
    Hauptdatei (``{paper_id}#text``), nicht die Vorlage selbst — ``put_text``
    erwartet eine Datei-Kennung.
    """
    store = CitiesStore(tmp_path / "raw.sqlite")
    store.put_raw_object("hannover", "paper", VORLAGE, {
        "id": VORLAGE,
        "html": (FIXTURES / "hannover_paper.html").read_text(encoding="utf-8")})
    texte = list(HannoverSimAdapter().inline_texts(store, "hannover"))
    assert len(texte) == 1
    kennung, text = texte[0]
    assert kennung == f"{VORLAGE}#text"
    assert len(text) > 2000
    assert "Kita Gethsemane" in text
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


def test_die_ausschussliste_liest_kuerzel_und_namen():
    """``grem=<Kürzel>`` aus ``Ausschuesse.xsp`` — Namensduplikate bleiben

    zwei eigene Gremien (zwei Kürzel, ein angezeigter Name kommt vor:
    AIntegration/AInternational — historisch zwei Kennungen für denselben
    Ausschuss).
    """
    suppe = _suppe("hannover_ausschuesse.html")
    treffer = {(re.search(r"grem=([^&\"]+)", a["href"]).group(1), a.get_text(" ", strip=True))
               for a in suppe.find_all("a", href=re.compile(r"grem="))
               if a.get_text(strip=True)}
    kuerzel = {k for k, _ in treffer}
    assert "AJHA" in kuerzel and "ABau" in kuerzel
    assert len(kuerzel) >= 30, "Hannover führt 33 Ausschüsse"


def test_die_stadtbezirksliste_liest_view_kuerzel_ohne_grem():
    """``view=TermineSTBRxx`` — anderes Muster als die Ausschüsse, kein

    ``grem=`` dabei.
    """
    suppe = _suppe("hannover_stadtbezirke.html")
    treffer = [re.search(r"view=(Termine\w+)", a["href"]).group(1)
               for a in suppe.find_all("a", href=re.compile(r"view=Termine"))]
    assert len(treffer) == 13, "Hannover führt 13 Stadtbezirksräte"
    assert "TermineSTBR02" in treffer


@pytest.mark.parametrize("roh,zeit,erwartet", [
    ("22.06.2026", "15:00 Uhr", "2026-06-22T15:00:00"),
    ("04.05.2026", None, "2026-05-04"),
    ("kein Datum", None, None),
])
def test_datum_und_uhrzeit(roh, zeit, erwartet):
    assert _iso(roh, zeit) == erwartet


def test_die_registry_nennt_die_wurzel_und_holt_keine_dateien():
    """Der Text steht in der Seite — eine PDF-Ernte gäbe es dort gar nicht."""
    spec = BODIES["hannover"]
    assert spec.dialect == "hannover_sim"
    assert spec.system_url and spec.system_url.endswith(".nsf")
    assert not spec.fetch_files
    assert not spec.active, "erst nach einem Probelauf einschalten"
