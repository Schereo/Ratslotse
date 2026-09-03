"""Der Straßen-Schnappschuss: ein Overpass-Aufruf statt fünfhundert.

**Der Zustand, gegen den das steht.** Am 03.09.2026 lief ein Reparaturlauf
über 513 Straßen und meldete ``located=513, missed=2, failed=0`` — er hatte
aber nur 15 von ihnen wirklich vollständig geholt. Overpass war von beiden VPS
aus gar nicht erreichbar, der Rückfall auf Nominatim stumm, und ein
Einzelsegment sieht in der Datenbank aus wie eine Straße. Deshalb prüfen diese
Tests genau zwei Dinge: dass aus dem Schnappschuss die GANZE Straße wird, und
dass ein zweiter Lauf nichts mehr anfasst.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council.store import CouncilStore  # noqa: E402
from scripts.strassen_snapshot import _nach_namen, anwenden  # noqa: E402

#: Zwei Segmente EINER Straße, das eine in Krusenbusch, das andere in
#: Tweelbäke — der Fall aus Tims Befund. Dazu ein gleichnamiger Weg weit
#: außerhalb Oldenburgs, wie ihn das Overpass-Rechteck mitliefert.
SCHNAPPSCHUSS = {"elements": [
    {"type": "way", "id": 1, "tags": {"name": "Tweelbäker Tredde"},
     "geometry": [{"lon": 8.2450, "lat": 53.1000}, {"lon": 8.2480, "lat": 53.0990},
                  {"lon": 8.2500, "lat": 53.1010}, {"lon": 8.2560, "lat": 53.1015}]},
    {"type": "way", "id": 2, "tags": {"name": "Tweelbäker Tredde"},
     "geometry": [{"lon": 8.2690, "lat": 53.1025}, {"lon": 8.2762, "lat": 53.1022}]},
    {"type": "way", "id": 3, "tags": {"name": "Tweelbäker Tredde"},
     "geometry": [{"lon": 8.4000, "lat": 52.9000}, {"lon": 8.4100, "lat": 52.9000}]},
    {"type": "way", "id": 4, "tags": {"name": "Nur Ein Punkt"},
     "geometry": [{"lon": 8.2000, "lat": 53.1400}]},
]}


def _saat(db: Path) -> None:
    store = CouncilStore(db)
    jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_locations (slug,name,kind,lat,lon,geojson,district,"
            "geo_tried,updated_at) VALUES (?,?,?,?,?,?,?,1,?)",
            ("tweelbaeker-tredde", "Tweelbäker Tredde", "street", 53.1023, 8.2726,
             # Genau das, was Nominatim liefert: EIN Segment, ganz in Tweelbäke.
             json.dumps({"type": "LineString",
                         "coordinates": [[8.2690, 53.1025], [8.2762, 53.1022]]}),
             "Tweelbäke", jetzt))
    store.close()


def test_aus_dem_schnappschuss_wird_die_ganze_strasse(tmp_path):
    db = tmp_path / "c.sqlite"
    _saat(db)
    datei = tmp_path / "snap.json"
    datei.write_text(json.dumps(SCHNAPPSCHUSS), encoding="utf-8")

    stand = anwenden(db, datei)
    assert stand["orte_neu"] == 1, stand

    store = CouncilStore(db)
    try:
        row = store._conn.execute(
            "SELECT geojson, district FROM council_locations WHERE slug='tweelbaeker-tredde'"
        ).fetchone()
        geom = json.loads(row["geojson"])
        # Alle Segmente, nicht eines — und der Weg außerhalb Oldenburgs ist weg.
        assert geom["type"] == "MultiLineString"
        assert len(geom["coordinates"]) == 2, geom
        assert all(p[1] > 53.0 for linie in geom["coordinates"] for p in linie)
        # Und der Hauptbereich folgt der Mehrheit der Stützpunkte.
        assert row["district"] == "Krusenbusch"
        # Beide berührten Bereiche stehen in der Zugehörigkeits-Tabelle: Genau
        # daran hing „direkt nebenan" — mit nur einem Segment fehlte Krusenbusch.
        bereiche = {r["district"] for r in store._conn.execute(
            "SELECT district FROM council_location_districts "
            "WHERE location_slug='tweelbaeker-tredde'")}
        assert bereiche == {"Krusenbusch", "Tweelbäke"}, bereiche
    finally:
        store.close()


def test_zweiter_lauf_faesst_nichts_an(tmp_path):
    """Ops-Läufe werden im Zweifel zweimal gestartet."""
    db = tmp_path / "c.sqlite"
    _saat(db)
    datei = tmp_path / "snap.json"
    datei.write_text(json.dumps(SCHNAPPSCHUSS), encoding="utf-8")

    erster = anwenden(db, datei)
    store = CouncilStore(db)
    try:
        vorher = store._conn.execute(
            "SELECT geojson, updated_at FROM council_locations "
            "WHERE slug='tweelbaeker-tredde'").fetchone()["geojson"]
    finally:
        store.close()
    zweiter = anwenden(db, datei)
    assert erster["orte_neu"] == 1 and zweiter["orte_neu"] == 0, zweiter
    # Der Ort ist aus der Nachbesserungsliste heraus — sie fragt nach fehlender
    # Vollgeometrie, und die hat er jetzt.
    assert zweiter["orte_offen"] == 0, zweiter
    store = CouncilStore(db)
    try:
        assert store._conn.execute(
            "SELECT geojson FROM council_locations WHERE slug='tweelbaeker-tredde'"
        ).fetchone()["geojson"] == vorher
    finally:
        store.close()


def test_trockenlauf_schreibt_nicht(tmp_path):
    db = tmp_path / "c.sqlite"
    _saat(db)
    datei = tmp_path / "snap.json"
    datei.write_text(json.dumps(SCHNAPPSCHUSS), encoding="utf-8")

    stand = anwenden(db, datei, trocken=True)
    assert stand["orte_neu"] == 1
    store = CouncilStore(db)
    try:
        geom = json.loads(store._conn.execute(
            "SELECT geojson FROM council_locations WHERE slug='tweelbaeker-tredde'"
        ).fetchone()["geojson"])
        assert geom["type"] == "LineString", "der Trockenlauf hat geschrieben"
    finally:
        store.close()


def test_namen_werden_exakt_gruppiert():
    """„Sandweg" und „Am Sandweg" sind zwei Straßen — ein unscharfer Abgleich
    hängte ihre Segmente aneinander. Groß-/Kleinschreibung ist gleichgültig,
    mehr nicht. Und ein Weg mit einem einzigen Punkt ist keine Linie."""
    nach_namen = _nach_namen({"elements": [
        {"tags": {"name": "Sandweg"}, "geometry": [{"lon": 8.2, "lat": 53.1},
                                                   {"lon": 8.21, "lat": 53.1}]},
        {"tags": {"name": "sandweg"}, "geometry": [{"lon": 8.22, "lat": 53.1},
                                                   {"lon": 8.23, "lat": 53.1}]},
        {"tags": {"name": "Am Sandweg"}, "geometry": [{"lon": 8.3, "lat": 53.1},
                                                      {"lon": 8.31, "lat": 53.1}]},
        {"tags": {"name": "Einzelpunkt"}, "geometry": [{"lon": 8.4, "lat": 53.1}]},
    ]})
    assert set(nach_namen) == {"sandweg", "am sandweg"}
    assert len(nach_namen["sandweg"]) == 2


def test_halber_schnappschuss_wird_abgewiesen(monkeypatch):
    """Lieber kein Schnappschuss als ein halber.

    Overpass unter Last liefert abgeschnittene Antworten. Für den Abgleich
    sähe das aus wie „diese Straßen gibt es nicht mehr" — und er würde gute
    Geometrien überschreiben.
    """
    import pytest

    from scripts import strassen_snapshot as snap

    class Antwort:
        status_code = 200
        content = b"{}"

        @staticmethod
        def raise_for_status():
            pass

        @staticmethod
        def json():
            return {"elements": [
                {"tags": {"name": f"Weg {i}"},
                 "geometry": [{"lon": 8.2, "lat": 53.1}, {"lon": 8.21, "lat": 53.1}]}
                for i in range(10)]}

    monkeypatch.setattr(snap.requests, "post", lambda *a, **k: Antwort())
    with pytest.raises(SystemExit) as fehler:
        snap.holen()
    assert "unvollständig" in str(fehler.value)


def test_lauf_ohne_jeden_treffer_meldet_fehler(tmp_path, monkeypatch, capsys):
    """Ein Schnappschuss, der zu keiner bekannten Straße passt, ist die falsche
    Datei — und darf nicht als grüner Lauf durchgehen.

    Gemessen wird die ÜBERDECKUNG mit dem ganzen Bestand, nicht die Zahl der
    Änderungen: Ist alles Reparierbare repariert, ändert der richtige
    Schnappschuss null Zeilen. Die erste Fassung dieses Riegels schlug genau
    dann an und hätte jeden Wochenlauf rot gemacht — auf Prod aufgefallen,
    nicht im Test."""
    from scripts import strassen_snapshot as snap

    db = tmp_path / "c.sqlite"
    _saat(db)
    datei = tmp_path / "fremd.json"
    datei.write_text(json.dumps({"elements": [
        {"tags": {"name": "Gibtesnichtstraße"},
         "geometry": [{"lon": 8.2, "lat": 53.1}, {"lon": 8.21, "lat": 53.1}]}]}),
        encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["x", "anwenden", "--db", str(db), "--datei", str(datei)])
    assert snap.main() == 1
    assert "steht KEINE im Schnappschuss" in capsys.readouterr().err


class _Antwort:
    def __init__(self, status, wege=0):
        self.status_code = status
        self._wege = wege
        self.content = b"x" * 100
        self.text = "Fehlertext"

    def json(self):
        return {"elements": [
            {"tags": {"name": f"Weg {i}"},
             "geometry": [{"lon": 8.2, "lat": 53.1}, {"lon": 8.21, "lat": 53.1}]}
            for i in range(self._wege)]}


def test_ueberlastete_instanz_wird_wiederholt(monkeypatch):
    """Gemessen am 03.09.2026: fünf identische Abfragen ergaben 2× 200 und
    3× 504, drei schwere hintereinander endeten mit 429. Die Instanz ist nicht
    gesperrt, sie ist ausgelastet — dagegen hilft warten."""
    from scripts import strassen_snapshot as snap

    antworten = [_Antwort(504), _Antwort(429), _Antwort(200, wege=3500)]
    pausen = []
    monkeypatch.setattr(snap.requests, "post", lambda *a, **k: antworten.pop(0))
    monkeypatch.setattr(snap.time, "sleep", pausen.append)

    daten = snap.holen()
    assert len(daten["elements"]) == 3500
    # Zwei Pausen für zwei Fehlschläge, und die zweite ist länger.
    assert len(pausen) == 2 and pausen[1] > pausen[0]


def test_eigene_kaputte_abfrage_wird_nicht_wiederholt(monkeypatch):
    """400 heißt: Die Abfrage ist falsch. Sie wird beim vierten Mal nicht
    besser — und ein Wiederholungslauf verdeckte nur die Ursache."""
    import pytest

    from scripts import strassen_snapshot as snap

    versuche = {"n": 0}

    def einmal(*a, **k):
        versuche["n"] += 1
        return _Antwort(400)

    monkeypatch.setattr(snap.requests, "post", einmal)
    monkeypatch.setattr(snap.time, "sleep", lambda s: None)
    with pytest.raises(SystemExit) as fehler:
        snap.holen()
    assert versuche["n"] == 1
    assert "unsere Abfrage" in str(fehler.value)


def test_ipv6_trugschluss_steht_in_der_meldung(monkeypatch):
    """„Network is unreachable" kommt vom LETZTEN Versuch (IPv6, das diese
    Maschinen nicht haben) — nicht von der Ursache. Genau daran ist am
    03.09.2026 eine Stunde draufgegangen; die Meldung sagt es jetzt dazu."""
    import pytest
    import requests as req

    from scripts import strassen_snapshot as snap

    def kaputt(*a, **k):
        raise req.ConnectionError(
            "HTTPSConnectionPool(host='overpass-api.de', port=443): "
            "Failed to establish a new connection: [Errno 101] Network is unreachable")

    monkeypatch.setattr(snap.requests, "post", kaputt)
    monkeypatch.setattr(snap.time, "sleep", lambda s: None)
    with pytest.raises(SystemExit) as fehler:
        snap.holen()
    text = str(fehler.value)
    assert "kein globales IPv6" in text and "curl -4" in text


def test_fertiger_bestand_ist_kein_fehler(tmp_path, monkeypatch, capsys):
    """Der Gegentest zum Riegel: Ist alles Reparierbare repariert, ändert der
    RICHTIGE Schnappschuss null Zeilen — und der Lauf ist trotzdem grün.

    Genau das war auf Prod der Fall (291 offene Straßen, alle mit Namen, die
    OSM nicht kennt: „Huntemannstr", „Otto-Modersohn-Str"). Die erste Fassung
    des Riegels hätte hier jeden Wochenlauf rot gemacht.
    """
    from scripts import strassen_snapshot as snap

    db = tmp_path / "c.sqlite"
    _saat(db)
    datei = tmp_path / "snap.json"
    datei.write_text(json.dumps(SCHNAPPSCHUSS), encoding="utf-8")
    anwenden(db, datei)                      # erster Lauf repariert

    # Dazu eine Straße, die OSM unter diesem Namen nicht kennt — sie bleibt für
    # immer offen, ohne dass etwas kaputt ist.
    store = CouncilStore(db)
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_locations (slug,name,kind,geo_tried,updated_at) "
            "VALUES ('huntemannstr','Huntemannstr','street',1,'2026-09-03T00:00:00Z')")
    store.close()

    monkeypatch.setattr(sys, "argv", ["x", "anwenden", "--db", str(db), "--datei", str(datei)])
    assert snap.main() == 0
    ausgabe = capsys.readouterr().out
    assert "orte_neu=0" in ausgabe and "abgleichbar=1" in ausgabe
