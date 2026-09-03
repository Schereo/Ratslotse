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
    """Ein Schnappschuss, der zu keinem Ort passt, ist die falsche Datei — und
    darf nicht als grüner Lauf durchgehen."""
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
    assert "KEIN Namenstreffer" in capsys.readouterr().err
