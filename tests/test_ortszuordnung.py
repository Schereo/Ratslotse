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


def test_fremde_wegstuecke_werden_abgeschnitten():
    """Der Fehler, den erst der Prod-Durchlauf zeigte.

    Overpass sucht Straßen in einem RECHTECK um Oldenburg, und das ist größer
    als die Stadt. Bei häufigen Namen kommt der gleichnamige Weg der
    Nachbargemeinde mit, alle Segmente werden verschmolzen, und der Mittelpunkt
    liegt dazwischen — in keinem Ortsbereich. „Alter Postweg" war so für den
    Stadtteil-Filter verloren, obwohl sein Oldenburger Teil in Kreyenbrück liegt.
    """
    drin = geo.ortsbereich_center("Kreyenbrück")
    gemischt = {"type": "MultiLineString", "coordinates": [
        [[drin[1], drin[0]], [drin[1] + 0.002, drin[0] + 0.002]],   # Oldenburg
        [[8.2077, 53.0400], [8.2080, 53.0405]],                      # weit südlich, außerhalb
    ]}
    beschnitten = geo.auf_stadtgebiet_beschneiden(gemischt)
    assert beschnitten and len(beschnitten["coordinates"]) == 1
    assert geo.ortsbereich_der_geometrie(beschnitten) == "Kreyenbrück"
    # Die Mischung liefert hier zufällig dasselbe — entscheidend ist, dass das
    # fremde Stück draußen bleibt und den Mittelpunkt nicht mehr verzieht.
    assert len(gemischt["coordinates"]) == 2


def test_komplett_fremde_geometrie_ist_kein_treffer():
    """Liegt nichts davon in Oldenburg, ist der Treffer keiner — „Postweg"
    und „Wallring" waren auf Prod durchweg Fremdtreffer."""
    fremd = {"type": "MultiLineString",
             "coordinates": [[[8.2077, 53.0400], [8.2080, 53.0405]]]}
    assert geo.auf_stadtgebiet_beschneiden(fremd) is None


def test_beschneiden_laesst_flaechen_und_unsinn_in_ruhe():
    """Polygone kommen aus Nominatim, das schon begrenzt sucht — und kaputte
    Eingaben dürfen keinen Lauf töten."""
    flaeche = {"type": "Polygon", "coordinates": [[[8.2, 53.14], [8.21, 53.14], [8.2, 53.15]]]}
    assert geo.auf_stadtgebiet_beschneiden(flaeche) == flaeche
    for wert in (None, "", "kein json", 42):
        assert geo.auf_stadtgebiet_beschneiden(wert) is None


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


def test_stadtweit_erkennt_das_hinterglied_im_kompositum():
    """Der Fehler, den erst die Stichprobe am echten Bestand zeigte.

    Die Regel begann mit ``\bprogramm\b`` — und traf damit „Programm", aber
    kein einziges Kompositum. Im Deutschen ist das Kompositum die Regel: Genau
    „Rad- und Fußverkehrsprogramm" und „Wohnungsbauförderungsprogramm", die
    Musterfälle der Regel, fielen durch. Der Kasinoplatz hing dadurch am
    Fußverkehrsprogramm, die Hannah-Arendt-Straße an einer Förderrichtlinie.
    """
    for titel in ("Rad- und Fußverkehrsprogramm 2019",
                  "Richtlinie - Wohnungsbauförderungsprogramm für Oldenburg",
                  "Änderung der Satzung über die Erhebung von Marktgebühren",
                  "Klimaschutzkonzept der Stadt Oldenburg",
                  "Verordnung zur Änderung der Verordnung über das Maß der Nutzung",
                  "Oldenburger Leitfaden für die Einrichtung von Fahrradstraßen",
                  "Berufung eines Lehrervertreters in den Schulausschuss",
                  "Leitantrag Fridays for Future - Workshop Verkehr"):
        assert locations.affects_whole_city(titel), titel


def test_satzungsbeschluss_ist_kein_stadtweiter_vorgang():
    """Die Wortgrenze HINTEN ist die Sicherung der geöffneten Regel.

    Jedes Bebauungsplan-Verfahren endet auf „- Satzungsbeschluss" — der
    ortsbezogenste Vorgang, den es gibt. Er endet nicht auf „satzung" und
    bleibt deshalb unangetastet. Genauso darf sich „…plan" nicht öffnen, sonst
    zöge es den Bebauungsplan selbst herein.
    """
    for titel in ("Bebauungsplan 831 (Stadion Maastrichter Straße) - Satzungsbeschluss",
                  "Bebauungsplan 869 (Gewerbegebiet Brokhausen) - Aufstellungsbeschluss",
                  "Änderung 84 des Flächennutzungsplanes (nördlich Eßkamp)",
                  "Ausbau Ziegelhofstraße von Auguststraße bis Würzburger Straße",
                  "Erneuerung Brücke Tweelbäker See - Beschlussantrag",
                  "Neugestaltung des Außengeländes an der IGS Kreyenbrück"):
        assert not locations.affects_whole_city(titel), titel


def test_falscher_stadtteil_wird_von_der_geometrie_korrigiert(tmp_path):
    """Füllen allein reicht nicht — Falsches muss auch geradegerückt werden.

    ``backfill_location_districts`` fasst nur leere Felder an. Auf Prod standen
    deshalb 20 Orte mit 205 Zuordnungen dauerhaft falsch: „Am Bahndamm" (65)
    auf Drielake, obwohl die Straße in Drielaker-Moor verläuft.
    """
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        mitte = geo.ortsbereich_center("Ohmstede")
        linie = json.dumps({"type": "LineString", "coordinates": [
            [mitte[1], mitte[0]], [mitte[1] + 0.001, mitte[0] + 0.001],
            [mitte[1] + 0.002, mitte[0] + 0.002]]})
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_locations (slug,name,kind,district,geojson,updated_at) "
                "VALUES ('a','Testweg','street','Eversten',?,'2026-09-01')", (linie,))
        assert store.fix_contradicting_districts() == 1
        assert store._conn.execute(
            "SELECT district FROM council_locations WHERE slug='a'").fetchone()["district"] == "Ohmstede"
    finally:
        store.close()


def test_mehrbereichs_strasse_bleibt_wie_eingetragen(tmp_path):
    """Eine Straße durch drei Bereiche, eingetragen mit einem davon, ist nicht
    falsch — nur unvollständig. Die Korrektur darf sie nicht anfassen."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        a = geo.ortsbereich_center("Innenstadt")
        b = geo.ortsbereich_center("Osternburg")
        linie = json.dumps({"type": "LineString",
                            "coordinates": [[a[1], a[0]], [b[1], b[0]]]})
        beruehrt = geo.ortsbereiche_der_geometrie(json.loads(linie))
        eingetragen = sorted(beruehrt)[0]
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_locations (slug,name,kind,district,geojson,updated_at) "
                "VALUES ('b','Langstraße','street',?,?,'2026-09-01')", (eingetragen, linie))
        assert store.fix_contradicting_districts() == 0
    finally:
        store.close()


def test_gleichnamiger_ort_ist_der_stadtteil(tmp_path):
    """Ein Ort namens „Drielake" IST Drielake — auf Prod stand er auf
    „Drielaker-Moor", weil der Geocoder eine Fläche nebenan fand. Bei exakter
    Namensgleichheit ist der Katalog stärker als jede Geokodierung."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_locations (slug,name,kind,district,updated_at) "
                "VALUES ('d','Drielake','area','Drielaker-Moor','2026-09-01')")
            # Ein Teiltreffer bleibt unangetastet: Eine Schule kann im
            # Nachbarbereich stehen.
            store._conn.execute(
                "INSERT INTO council_locations (slug,name,kind,district,updated_at) "
                "VALUES ('g','Grundschule Drielake','building','Osternburg','2026-09-01')")
        assert store.fix_eponymous_districts() == 1
        namen = {r["slug"]: r["district"] for r in store._conn.execute(
            "SELECT slug, district FROM council_locations")}
        assert namen == {"d": "Drielake", "g": "Osternburg"}
    finally:
        store.close()


def test_gattungsfilter_trifft_keine_eigennamen():
    """Der Fehler, den erst die große Prüfung zeigte.

    Die Präfixliste („schul", „fahrrad", „spiel") ist für den Regex-Kanal
    gedacht, wo sie auf bloße Straßenmuster trifft. Auf den LLM-Kanal
    ausgeweitet schlug sie bei ganzen Eigennamen falsch an — „Schule an der
    Kleiststraße" und „Fahrradstation Nord" sind genau die konkreten Orte,
    um die es geht.
    """
    for name in ("Schule an der Kleiststraße", "Fahrradstation Nord",
                 "Spielplatz Friedrich-August-Platz", "Fahrradsammelgarage Wechloy"):
        assert locations.valid_llm_location(name, "building", name), name
    for name in ("Gemeindestraße", "Radweg", "Monitoring", "Kunstrasenplatz"):
        assert not locations.valid_llm_location(name, "street", name), name


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
    assert locations.affects_whole_city(titel) is erwartet


def test_ortsbezug_nur_aus_der_vorlage_faellt_bei_stadtweitem_weg():
    """Der zweite Fehler: „Oldenburg Pass" hing an der Adresse der VWG."""
    kandidat = {"name": "VWG", "source": "template"}
    assert locations.location_is_incidental("Oldenburg Pass – Bericht 2021", kandidat)


def test_ort_im_titel_schuetzt_den_vorgang():
    """„Masterplan Fliegerhorst" ist stadtweit formuliert und trotzdem verortet."""
    kandidat = {"name": "Fliegerhorst", "source": "template"}
    assert not locations.location_is_incidental(
        "Masterplan Fliegerhorst - Energiekonzept", kandidat)


def test_genitiv_im_titel_schuetzt_ebenfalls():
    """Die Falle, in die die erste Fassung lief.

    „Unterschutzstellung des Heidbrooks – Sachstandsbericht" verlor ALLE
    Ortsbezüge, auch den richtigen: Der Genitiv „Heidbrooks" wird von den
    Ortsmustern nicht als Nennung erkannt.
    """
    kandidat = {"name": "Heidbrook", "source": "template"}
    assert not locations.location_is_incidental(
        "Unterschutzstellung des Heidbrooks - Sachstandsbericht", kandidat)
    # Eine Straße, die nur nebenbei in der Vorlage steht, fällt sehr wohl weg.
    assert locations.location_is_incidental(
        "Unterschutzstellung des Heidbrooks - Sachstandsbericht",
        {"name": "Ammerländer Heerstraße", "source": "template"})


def test_fund_aus_dem_titel_bleibt_immer():
    """Der Titel ist die Grenze — er sagt, worum es geht.

    Stand hier zuerst auch ``official_text``: Der Beschlusstext galt als das
    verlässlichere Papier. Die Stichprobe am Prod-Bestand hat das widerlegt,
    siehe ``test_beiwerk_gilt_auch_fuer_den_beschlusstext``. Aus dem TITEL
    bleibt ein Ort weiterhin unangetastet.
    """
    assert not locations.location_is_incidental(
        "Änderung der Marktgebührensatzung", {"name": "Rathausmarkt", "source": "title"})
    assert locations.location_is_incidental(
        "Änderung der Marktgebührensatzung", {"name": "Rathausmarkt", "source": "official_text"})


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


def test_gescheitertes_geocoding_loescht_keinen_stadtteil(tmp_path):
    """Der Fehler, den erst der Prod-Test zeigte.

    ``set_location_geo(slug, None, None, None)`` vermerkt nur „versucht" — und
    schrieb dabei bedingungslos ``district = NULL``. Der Wiederholungslauf
    löschte damit genau die Stadtteile wieder, die die Namensregel kurz zuvor
    gesetzt hatte: „Oberschule Ofenerdiek" stand danach wieder ohne.
    """
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_locations (slug,name,kind,updated_at) "
                "VALUES ('s','Oberschule Ofenerdiek','building','2026-09-01')")
        assert store.backfill_location_districts_from_name() == 1
        store.set_location_geo("s", None, None, None)      # Geocoding misslingt
        row = store._conn.execute(
            "SELECT district, ortsbereich_id, geo_tried FROM council_locations "
            "WHERE slug='s'").fetchone()
        assert row["district"] == "Ofenerdiek", "der Fehlschlag hat den Stadtteil gelöscht"
        assert row["ortsbereich_id"] == "ofenerdiek"
        assert row["geo_tried"] == 1        # als versucht vermerkt ist er trotzdem
    finally:
        store.close()


def test_treffer_ausserhalb_oldenburgs_loescht_den_stadtteil(tmp_path):
    """Die Gegenprobe — und die Grenze der Regel darüber.

    Ein Fehlschlag weiß nichts und darf nichts wegnehmen. Ein Treffer, der in
    keinem Ortsbereich liegt, weiß dagegen etwas: Der Ort gehört nicht hierher.
    Beides in einer Zeile zu behandeln war der Fehler; ein Bestandstest
    (``test_location_storage_replaces_per_decision…``) hat ihn gefangen.
    """
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_locations (slug,name,kind,updated_at) "
                "VALUES ('j','Junkerstraße','street','2026-09-01')")
        store.set_location_geo("j", 53.14, 8.21, None)          # in Oldenburg
        assert store._conn.execute(
            "SELECT district FROM council_locations WHERE slug='j'").fetchone()["district"]
        store.set_location_geo("j", 52.3759, 9.7320, None)      # Hannover
        assert store._conn.execute(
            "SELECT district FROM council_locations WHERE slug='j'").fetchone()["district"] is None
    finally:
        store.close()


def test_set_location_geo_nimmt_den_verlauf_der_strasse(tmp_path):
    """Auch beim Setzen gilt: Geometrie schlägt Bounding-Box-Mittelpunkt."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_locations (slug,name,kind,updated_at) "
                "VALUES ('w','Testweg','street','2026-09-01')")
        mitte = geo.ortsbereich_center("Ohmstede")
        linie = json.dumps({"type": "LineString", "coordinates": [
            [mitte[1], mitte[0]], [mitte[1] + 0.003, mitte[0] + 0.003]]})
        # lat/lon absichtlich in der Nordsee — nur die Geometrie kann tragen.
        store.set_location_geo("w", 53.9, 8.0, linie)
        row = store._conn.execute(
            "SELECT district FROM council_locations WHERE slug='w'").fetchone()
        assert row["district"] == "Ohmstede"
    finally:
        store.close()


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


def test_stadtweit_erkennt_genitiv_und_plural():
    """Deutsche Flexion — im Titel eines Ratsvorgangs die Norm.

    Die Wortgrenze hinten traf den Nominativ und sonst nichts: „Änderung des
    Rahmenkonzept*es*", „Fortschreibung des Lärmaktionsplan*s*", „Anpassung
    der Satzung*en*". Alle drei standen so mit einem Stadtteil in den Daten.
    """
    for titel in ("Änderung des Rahmenkonzeptes „Kooperative Ganztagsbildung\"",
                  "Fortschreibung des Lärmaktionsplans - Beschluss",
                  "Anpassung der Satzungen über die Erhebung von Gebühren",
                  "Evaluation des Konzeptes",
                  "Rahmenplan Mobilität und Verkehr (RMV 2030)",
                  "Gesamtstädtisches Maßnahmenpaket für Rollsportanlagen",
                  "Armutsbericht"):
        assert locations.affects_whole_city(titel), titel


def test_stadtweite_planarten_einzeln_statt_pauschal():
    """„…plan" darf sich nicht öffnen — es zöge den Bebauungsplan mit herein.

    Am Prod-Bestand ausgezählt: Von 570 Planwörtern in Beschlusstiteln sind
    530 Bebauungs- und Flächennutzungspläne. Die stadtweiten Planarten sind
    eine kurze, zählbare Liste und stehen deshalb einzeln.
    """
    for titel in ("Mobilitätsplan Oldenburg 2030 - Stand der Planungen",
                  "Erfolgsplan EGH - Instandhaltung der Schulgebäude",
                  "Fortschreibung des Luftreinhalteplans"):
        assert locations.affects_whole_city(titel), titel
    for titel in ("Vorhabenbezogener Bebauungsplan Nr. 62 (Hohenmoorstraße)",
                  "Änderung 84 des Flächennutzungsplanes (nördlich Eßkamp)",
                  "Zeitplan für den Ausbau der Ziegelhofstraße"):
        assert not locations.affects_whole_city(titel), titel


def test_pass_bekommt_keine_endung():
    """„Oldenburg Pass" ja, „passen" nein — deshalb steht `pass` als eigener,
    strenger Zweig neben der flektierbaren Liste."""
    assert locations.affects_whole_city("Oldenburg Pass - Bericht 2021")
    assert not locations.affects_whole_city("Die Bordsteine passen nicht zum Radweg")


def test_beiwerk_gilt_auch_fuer_den_beschlusstext():
    """Die Regel nahm den Beschlusstext zuerst aus — er galt als das
    verlässlichere Papier. Falsch: Auch dort stehen Anschriften, die dem
    Vorgang nicht gehören (die der VWG unter „Jahresabschluss 2022").
    Was schützt, ist der Titel-Test, nicht die Herkunft des Fundes.
    """
    stadtweit = "Verkehr und Wasser GmbH (VWG): Jahresabschluss 2022"
    for quelle in ("template", "official_text"):
        assert locations.location_is_incidental(
            stadtweit, {"name": "Bürgerfelder Straße", "source": quelle}), quelle
    # Aus dem TITEL bleibt es: Dort steht der Ort, weil er gemeint ist.
    assert not locations.location_is_incidental(
        stadtweit, {"name": "Bürgerfelder Straße", "source": "title"})
    # Und nennt der Titel den Ort, greift die Regel für keine Quelle.
    assert not locations.location_is_incidental(
        "Masterplan Fliegerhorst", {"name": "Fliegerhorst", "source": "official_text"})


def test_nackte_kennungen_sind_keine_orte():
    """Am Prod-Bestand gefunden: Kennungen, die wie ein Ort aussehen.

    „A 293" quert die halbe Stadt und stand trotzdem auf Nadorst, „FH-24" ist
    eine Fliegerhorst-Plannummer und stand auf Bloherfelde, „26122" ist eine
    Postleitzahl. Zusammen 15 Zuordnungen — klein, aber jede einzelne führt
    jemanden in den falschen Stadtteil.
    """
    for name in ("26122", "A 293", "A293", "L865", "FH-24", "PFA 1", "M-821",
                 "Zone 1", "B 75", "K 141"):
        assert not locations.valid_llm_location(name, "street", name), name
    # Die Kennung MIT ihrem Wort bleibt — sie trägt ihren Ortsbezug im
    # Beschlusstitel, und die Vorschlagskarte schreibt ihn dazu.
    assert locations.valid_llm_location("Bebauungsplan 831", "area", "Bebauungsplan 831")
    # Und eine Hausnummer auf einer Straße ist die GENAUERE Angabe, nicht Müll:
    # die Alexanderstraße läuft durch vier Ortsbereiche.
    for name in ("Alexanderstraße 488", "Sandweg 26", "Nadorster Straße 298"):
        assert locations.valid_llm_location(name, "street", name), name


def test_kennung_behaelt_den_verweis_verliert_den_stadtteil(tmp_path):
    """Die A 293 wird in Beschlüssen erwähnt — das ist richtig. Falsch ist nur
    der Stadtteil: Eine Autobahn quert die halbe Stadt, „A 293 → Nadorst"
    schickt jemanden in ein Viertel, mit dem der Beschluss nichts zu tun hat.

    Und der Riegel muss im Nachtrag SELBST sitzen: Stünde er nur im Aufräumen,
    füllte der nächste Lauf wieder auf, was der letzte geleert hat.
    """
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        lat, lon = geo.ortsbereich_center("Nadorst")
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_locations (slug,name,kind,district,lat,lon,updated_at) "
                "VALUES ('a293','A 293','street','Nadorst',?,?,'2026-09-01')", (lat, lon))
        assert store.clear_code_only_districts() == 1
        assert store._conn.execute(
            "SELECT district FROM council_locations WHERE slug='a293'").fetchone()["district"] is None
        # Der Nachtrag darf ihn nicht wieder setzen.
        store.backfill_location_districts()
        assert store._conn.execute(
            "SELECT district FROM council_locations WHERE slug='a293'").fetchone()["district"] is None
    finally:
        store.close()


# ----------------------------------- 5) Zugehörigkeit zu MEHREREN Bereichen ---

def test_lange_strasse_gehoert_in_alle_beruehrten_stadtteile(tmp_path):
    """Eine Straße durch mehrere Ortsbereiche gehört in jeden Filter.

    Am Prod-Bestand: Die Alexanderstraße verläuft zu 38 % in Bürgerfelde, zu
    20 % in Alexandersfeld, zu 18 % im Ziegelhof, zu 13 % im Ehnernviertel und
    zu 10 % in Dietrichsfeld. Mit einer Spalte sahen vier Viertel ihre eigene
    Straße nicht.
    """
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        a = geo.ortsbereich_center("Innenstadt")
        b = geo.ortsbereich_center("Osternburg")
        # Eine Linie mit vielen Stützpunkten quer durch beide Bereiche.
        punkte = [[a[1] + (b[1] - a[1]) * i / 40, a[0] + (b[0] - a[0]) * i / 40]
                  for i in range(41)]
        linie = json.dumps({"type": "LineString", "coordinates": punkte})
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_locations (slug,name,kind,district,geojson,updated_at) "
                "VALUES ('lang','Langstraße','street','Innenstadt',?,'2026-09-01')", (linie,))
        store.rebuild_location_districts()
        bereiche = {r["district"] for r in store._conn.execute(
            "SELECT district FROM council_location_districts WHERE location_slug='lang'")}
        assert "Innenstadt" in bereiche and "Osternburg" in bereiche, bereiche
        # Die Anzeige-Spalte bleibt bei EINEM Stadtteil.
        assert store._conn.execute(
            "SELECT district FROM council_locations WHERE slug='lang'").fetchone()["district"] == "Innenstadt"
    finally:
        store.close()


def test_gleichnamiger_ort_faerbt_die_nachbarn_nicht_ein(tmp_path):
    """Die Fläche, die ein Kartendienst für „Ofenerdiek" liefert, schwappt nach
    Nadorst — aber unser Katalog-Umriss IST die Definition von Ofenerdiek.
    25 solcher Orte gibt es im Bestand; ohne die Ausnahme färbten sie ihre
    Nachbarn ein.
    """
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        a = geo.ortsbereich_center("Innenstadt")
        b = geo.ortsbereich_center("Osternburg")
        punkte = [[a[1] + (b[1] - a[1]) * i / 40, a[0] + (b[0] - a[0]) * i / 40]
                  for i in range(41)]
        linie = json.dumps({"type": "LineString", "coordinates": punkte})
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_locations (slug,name,kind,district,geojson,updated_at) "
                "VALUES ('innen','Innenstadt','area','Innenstadt',?,'2026-09-01')", (linie,))
        store.rebuild_location_districts()
        bereiche = {r["district"] for r in store._conn.execute(
            "SELECT district FROM council_location_districts WHERE location_slug='innen'")}
        assert bereiche == {"Innenstadt"}, bereiche
    finally:
        store.close()


def test_eine_angeschnittene_ecke_zaehlt_nicht(tmp_path):
    """Nur ein spürbarer Anteil zählt — sonst gehörte jede Straße, die eine
    Grenze streift, gleich in beide Viertel."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        mitte = geo.ortsbereich_center("Ohmstede")
        punkte = [[mitte[1] + i * 0.00005, mitte[0] + i * 0.00005] for i in range(41)]
        linie = json.dumps({"type": "LineString", "coordinates": punkte})
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_locations (slug,name,kind,district,geojson,updated_at) "
                "VALUES ('kurz','Kurzweg','street','Ohmstede',?,'2026-09-01')", (linie,))
        store.rebuild_location_districts()
        bereiche = {r["district"] for r in store._conn.execute(
            "SELECT district FROM council_location_districts WHERE location_slug='kurz'")}
        assert bereiche == {"Ohmstede"}, bereiche
    finally:
        store.close()
