"""Die geografische Zuordnung von Beschlüssen — drei nachgemessene Fehler.

Alle drei stammen aus einer Prüfung des Prod-Bestands am 01.09.2026 (lesend).
Sie sind hier festgenagelt, weil keiner davon in einer frischen Testdatenbank
von selbst auffällt: Sie brauchen echte Geometrie, echte Vorlagentexte und
Ortsnamen, die kein Geocoder kennt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from council import geo, locations  # noqa: E402
from council.store import CouncilStore  # noqa: E402


# ------------------------------------------------- 1) Geometrie statt Punkt ---

def test_strasse_liegt_im_stadtteil_auch_ohne_passenden_mittelpunkt():
    """Der Kern des ersten Fehlers.

    Eine Straße, die um eine Ecke geht, hat den Mittelpunkt ihrer Bounding-Box
    NEBEN sich. Auf Prod lag „Alter Postweg" deshalb in keinem Ortsbereich,
    obwohl die Straße vollständig in Kreyenbrück verläuft.
    """
    mitte = geo.ortsbereich_center("Kreyenbrück")
    assert mitte, "Kreyenbrück muss ein Polygon haben"
    lat, lon = mitte
    # Eine L-förmige Linie, deren Bounding-Box-Mitte außerhalb der Linie liegt.
    linie = {"type": "LineString",
             "coordinates": [[lon, lat], [lon + 0.004, lat], [lon + 0.004, lat + 0.004]]}
    assert geo.ortsbereich_der_geometrie(linie) == "Kreyenbrück"
    assert geo.ortsbereiche_der_geometrie(linie)["Kreyenbrück"] > 0


def test_geometrie_nennt_alle_beruehrten_bereiche():
    """Ein Fluss läuft durch mehrere Stadtteile — das ist keine Ungenauigkeit,
    sondern die Wahrheit, und die Funktion darf sie nicht unterschlagen."""
    a = geo.ortsbereich_center("Innenstadt")
    b = geo.ortsbereich_center("Osternburg")
    linie = {"type": "LineString", "coordinates": [[a[1], a[0]], [b[1], b[0]]]}
    beruehrt = geo.ortsbereiche_der_geometrie(linie)
    assert len(beruehrt) >= 2
    # Der überwiegende gewinnt, und zwar reproduzierbar.
    assert geo.ortsbereich_der_geometrie(linie) == max(
        sorted(beruehrt), key=lambda n: (beruehrt[n], [-ord(c) for c in n]))


def test_kaputte_geometrie_wirft_nicht(tmp_path):
    """Der Wert kommt aus einer Fremdquelle — Unsinn darf keinen Lauf töten."""
    for wert in (None, "", "kein json", "{}", '{"type":"Dings"}', json.dumps({"type": "Point"})):
        assert geo.ortsbereich_der_geometrie(wert) is None


def test_backfill_nutzt_geometrie_vor_punkt(tmp_path):
    """Der Store zieht die Geometrie der Bounding-Box-Mitte vor."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        mitte = geo.ortsbereich_center("Ohmstede")
        linie = json.dumps({"type": "LineString", "coordinates": [
            [mitte[1], mitte[0]], [mitte[1] + 0.003, mitte[0] + 0.003]]})
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_locations (slug,name,kind,lat,lon,geojson,updated_at) "
                # lat/lon absichtlich weit weg (Nordsee): Nur die Geometrie kann retten.
                "VALUES ('l1','Testweg','street',53.9,8.0,?,'2026-09-01')", (linie,))
        assert store.backfill_location_districts() == 1
        row = store._conn.execute("SELECT district FROM council_locations WHERE slug='l1'").fetchone()
        assert row["district"] == "Ohmstede"
    finally:
        store.close()


# ------------------------------------------------- 2) Stadtteil aus dem Namen ---

def test_stadtteil_aus_dem_namen(tmp_path):
    """„GS Drielake" findet kein Geocoder — der Name sagt es trotzdem."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        with store._conn:
            for slug, name in [("a", "Oberschule Ofenerdiek"), ("b", "GS Drielake"),
                               ("c", "Bürgerhaus Ofenerdiek")]:
                store._conn.execute(
                    "INSERT INTO council_locations (slug,name,kind,updated_at) "
                    "VALUES (?,?,'building','2026-09-01')", (slug, name))
        assert store.backfill_location_districts_from_name() == 3
        namen = {r["slug"]: r["district"] for r in store._conn.execute(
            "SELECT slug, district FROM council_locations")}
        assert namen == {"a": "Ofenerdiek", "b": "Drielake", "c": "Ofenerdiek"}
    finally:
        store.close()


def test_mehrdeutiger_name_bleibt_lieber_ohne_stadtteil(tmp_path):
    """„Entlastungsstraße Fliegerhorst-Wechloy" nennt zwei — dann keinen.

    Eine geratene Zuordnung wäre schlechter als gar keine: Sie sähe genauso
    aus wie eine gemessene und wäre nicht mehr als falsch erkennbar.
    """
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_locations (slug,name,kind,updated_at) "
                "VALUES ('x','Entlastungsstraße Fliegerhorst-Wechloy','street','2026-09-01')")
        assert store.backfill_location_districts_from_name() == 0
    finally:
        store.close()


def test_namensregel_fasst_verortetes_nicht_an(tmp_path):
    """Wo Koordinaten vorliegen, sind sie verlässlicher als ein Wortlaut."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_locations (slug,name,kind,lat,lon,updated_at) "
                "VALUES ('y','Halle Ofenerdiek','building',53.15,8.21,'2026-09-01')")
        assert store.backfill_location_districts_from_name() == 0
    finally:
        store.close()


# --------------------------------------- 3) Ortsbezug bei stadtweiten Sachen ---

@pytest.mark.parametrize("titel,erwartet", [
    ("Oldenburg Pass – Bericht 2021 und Ausblick 2022", True),
    ("Umbesetzung von Ausschüssen und Gremien", True),
    ("Änderung der Satzung über die Erhebung von Marktgebühren", True),
    ("Eigenbetrieb Hafen - Jahresabschluss 2017", True),
    ("Verkehrssituation Herrenweg", False),
    ("Neubau der Cäcilienbrücke", False),
])
def test_erkennt_stadtweite_vorgaenge(titel, erwartet):
    assert locations.betrifft_ganze_stadt(titel) is erwartet


def test_ortsbezug_nur_aus_der_vorlage_faellt_bei_stadtweitem_weg():
    """Der zweite Fehler: „Oldenburg Pass" hing an der Adresse der VWG."""
    kandidat = {"name": "VWG", "source": "template"}
    assert locations.ortsbezug_ist_beiwerk("Oldenburg Pass – Bericht 2021", kandidat)


def test_ort_im_titel_schuetzt_den_vorgang():
    """„Masterplan Fliegerhorst" ist stadtweit formuliert und trotzdem verortet."""
    kandidat = {"name": "Fliegerhorst", "source": "template"}
    assert not locations.ortsbezug_ist_beiwerk(
        "Masterplan Fliegerhorst - Energiekonzept", kandidat)


def test_genitiv_im_titel_schuetzt_ebenfalls():
    """Die Falle, in die die erste Fassung lief.

    „Unterschutzstellung des Heidbrooks – Sachstandsbericht" verlor ALLE
    Ortsbezüge, auch den richtigen: Der Genitiv „Heidbrooks" wird von den
    Ortsmustern nicht als Nennung erkannt.
    """
    kandidat = {"name": "Heidbrook", "source": "template"}
    assert not locations.ortsbezug_ist_beiwerk(
        "Unterschutzstellung des Heidbrooks - Sachstandsbericht", kandidat)
    # Eine Straße, die nur nebenbei in der Vorlage steht, fällt sehr wohl weg.
    assert locations.ortsbezug_ist_beiwerk(
        "Unterschutzstellung des Heidbrooks - Sachstandsbericht",
        {"name": "Ammerländer Heerstraße", "source": "template"})


def test_fund_aus_titel_oder_beschluss_bleibt_immer():
    """Die Regel greift nur auf Funde aus dem Vorlagentext."""
    for quelle in ("title", "official_text"):
        assert not locations.ortsbezug_ist_beiwerk(
            "Änderung der Marktgebührensatzung", {"name": "Rathausmarkt", "source": quelle})


# ------------------------------------------------------ 4) Nebenbefunde ---

def test_wohnanschrift_wird_nicht_zum_ort():
    """Ein Personalbeschluss wurde nach der Privatadresse eines Mitglieds
    verortet. Doppelt falsch — sachlich und weil eine Wohnanschrift nichts in
    unserer Datenbank zu suchen hat."""
    assert not locations.valid_llm_location(
        "Le-Corbusier-Straße", "street",
        "Lasse Zink, Le-Corbusier-Straße 49, 26127 Oldenburg")
    # Dieselbe Straße ohne Anschrift bleibt ein gültiger Ort.
    assert locations.valid_llm_location(
        "Le-Corbusier-Straße", "street", "Ausbau der Le-Corbusier-Straße")


@pytest.mark.parametrize("name,generisch", [
    ("Gemeindestraße", True), ("Entlastungsstraße", True), ("Radweg", True),
    ("Kunstrasenplatz", True), ("Monitoring", True),
    ("Entlastungsstraße Fliegerhorst", False), ("Nadorster Straße", False),
    # Die gibt es in Oldenburg wirklich — sie dürfen nicht mitgesperrt werden.
    ("Hauptstraße", False), ("Ringstraße", False),
])
def test_gattungsbegriffe_sind_keine_orte(name, generisch):
    assert locations._generic_street(name) is generisch


def test_gattungsbegriff_auch_ueber_das_modell_gesperrt():
    """Der Gattungsfilter hing nur am Regex-Kanal; über das Modell kamen
    „Gemeindestraße" (51 Zuordnungen) und „Radweg" (13) ungehindert durch."""
    assert not locations.valid_llm_location(
        "Gemeindestraße", "street", "Ausbau der Gemeindestraße")


def test_gescheiterte_geocodings_lassen_sich_wiederholen(tmp_path):
    """Ohne diesen Weg blieben 706 Orte für immer liegen — ``locations_to_geocode``
    nahm nur ``geo_tried = 0``, und Overpass antwortet nicht jeden Tag gleich."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_locations (slug,name,kind,geo_tried,updated_at) "
                "VALUES ('alt','Postweg','street',1,'2026-09-01')")
            store._conn.execute(
                "INSERT INTO council_decisions (id,ksinr,position,title,kind) "
                "VALUES (1,1,1,'Ausbau','decision')")
            store._conn.execute(
                "INSERT INTO council_decision_locations "
                "(decision_id,location_slug,source,evidence,method,confidence,updated_at) "
                "VALUES (1,'alt','title','Postweg','regex',0.9,'2026-09-01')")
        assert store.locations_to_geocode() == []
        assert [r["name"] for r in store.locations_to_geocode(retry_failed=True)] == ["Postweg"]
    finally:
        store.close()
