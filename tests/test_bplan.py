"""Bebauungsplan-Umringe auf der Viertel-Karte (council/bplan.py, store_bplan.py).

Was hier gehalten wird:

1. Die Plannummer aus dem Beschlusstitel — in allen Schreibweisen, die die
   Verwaltung benutzt — findet ihren Plan im Datensatz der Stadt.
2. Der Schwerpunkt liegt IN der Fläche, auch bei einem L-förmigen Plan.
3. Ein Vorhaben mit Bebauungsplan-Beschluss bekommt den Geltungsbereich als
   Ort (`kind = bplan`) — aber nur, wenn der Plan im Ortsbereich liegt.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _ROOT / "web" / "backend"
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_BACKEND))

_TMP = tempfile.mkdtemp()
os.environ.setdefault("RATSLOTSE_DB", str(Path(_TMP) / "ratslotse.sqlite"))
os.environ.setdefault("COUNCIL_DB", str(Path(_TMP) / "council.sqlite"))
os.environ.setdefault("WEB_JWT_SECRET", "test-secret")
os.environ.setdefault("WEB_ADMIN_EMAIL", "admin@example.org")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("DISABLE_RATE_LIMIT", "1")

from council import bplan, geo  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = os.environ["COUNCIL_DB"]


@pytest.fixture(autouse=True)
def fresh_db():
    for suffix in ("", "-wal", "-shm"):
        Path(COUNCIL_DB + suffix).unlink(missing_ok=True)
    yield


@pytest.mark.parametrize("titel, erwartet", [
    ("Bebauungsplan N-777 G (Fliegerhorst/Hallensichel Ost/Entlastungsstraße) mit örtlichen Bauvorschriften "
     "- Prüfung der Stellungnahmen - Satzungsbeschluss", ["777G"]),
    ("Änderung 1 des Bebauungsplanes 777 D (Fliegerhorst/Offizierskasino) - Beschluss zur Veröffentlichung "
     "des Entwurfs", ["777D ÄND 1", "777D"]),
    ("Änderung Nummer 1 des Bebauungsplanes S-513 (Meerkamp/Mittagsweg) mit örtlichen Bauvorschriften "
     "- Auslegungsbeschluss", ["513 ÄND 1", "513"]),
    ("Änderung Nr. 2 des Bebauungsplanes S-367 (Eidechsenstraße) - Grundzüge der Planung", ["367 ÄND 2", "367"]),
    ("Vorhabenbezogener Bebauungsplan Nr. 64 (südlich Osternburger Markt) - Auslegungsbeschluss", ["64 VHB"]),
    ("Aufstellung vorhabenbezogener Bebauungsplan 69 (Moslestraße/Osterstraße) - Grundzüge der Planung", ["69 VHB"]),
    ("Bebauungsplan 857 A (östlich Schramperweg/nördlich Watertucht)", ["857A"]),
    ("Änderung 1 des Bebauungsplanes N-225 I (Eßkamp/Burenkamp) - Aufhebung des Aufstellungsbeschlusses",
     ["225I ÄND 1", "225I"]),
    ("Bebauungsplan S-835 MediTech Oldenburg (MTO) mit örtlichen Bauvorschriften - Satzungbeschluss", ["835"]),
    ("Interessenbekundung für das ehemalige Offizierskasino im Baugebiet Mittelweg/Fliegerhorst "
     "(Bebauungsplan N-777 D)", ["777D"]),
    ("Haushaltssatzung 2027 der Stadt Oldenburg", []),
])
def test_plannummern_im_titel(titel, erwartet):
    assert bplan.plannummern_im_titel(titel) == erwartet


@pytest.mark.parametrize("stadt, vorlage", [
    ("777 G", "N-777 G"), ("18c VhB", "Nr. 18 c VhB"), ("513 Änd. 1", "513 ÄND 1"),
    ("117 I", "S-117 I"), ("1 VhB", "1 VHB"), ("64 VhB", "64 VHB"),
])
def test_schluessel_vergleicht_beide_schreibweisen(stadt, vorlage):
    assert bplan.schluessel(stadt) == bplan.schluessel(vorlage)


def test_vhb_kuerzel_bleibt_getrennt():
    # „64 VhB" aus dem Datensatz muss den Titel „Vorhabenbezogener Bebauungsplan
    # Nr. 64" treffen — das Kürzel darf nicht an die Zahl kleben (gemessen
    # 06.09.2026: alle 36 VhB-Pläne fanden sich sonst nicht).
    assert bplan.schluessel("64 VhB") == "64 VHB"
    assert bplan.plannummern_im_titel("Vorhabenbezogener Bebauungsplan Nr. 64 (Osternburger Markt)") == ["64 VHB"]
    assert bplan.schluessel("117 III") == "117III"


def _l_form() -> dict:
    # Ein L: Bounding-Box-Mitte (1, 1) läge AUSSERHALB der Fläche.
    return {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 0.5], [0.5, 0.5], [0.5, 2], [0, 2], [0, 0]]]}


def test_schwerpunkt_liegt_in_der_flaeche():
    lat, lon = bplan.schwerpunkt(_l_form())
    assert geo._in_ring(lon, lat, _l_form()["coordinates"][0])
    assert bplan.schwerpunkt(None) is None


def test_normiere_uebersetzt_millisekunden_und_ohne_geometrie():
    z = bplan.normiere({"properties": {"Planverfahren": "777 G", "Name": "Fliegerhorst/Hallensichel-Ost",
                                       "rechtsverbindlich": 1614902400000, "Satzungsbeschluss_Rat_VA": "2020-09-28T00:00:00"},
                        "geometry": None})
    assert z["key"] == "777G" and z["effective_date"] == "2021-03-05" and z["adoption_date"] == "2020-09-28"
    assert z["geojson"] is None and z["lat"] is None and z["status"] == "effective"
    assert bplan.normiere({"properties": {"Planverfahren": "871"}, "geometry": None}, "in_procedure")["status"] == "in_procedure"
    assert bplan.normiere({"properties": {"Planverfahren": ""}}) is None


def _viereck(lon0: float, lat0: float, d: float = 0.004) -> dict:
    return {"type": "Polygon", "coordinates": [[[lon0, lat0], [lon0 + d, lat0], [lon0 + d, lat0 + d],
                                                 [lon0, lat0 + d], [lon0, lat0]]]}


def test_vorhaben_bekommt_geltungsbereich_nur_im_eigenen_ortsbereich():
    store = CouncilStore(COUNCIL_DB)
    c = store._conn
    with c:
        c.execute("INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
                  "VALUES (1, 'Rat', '2026-05-04', '18:00', 'Rathaus', '2026-05-01')")
        c.executemany(
            "INSERT INTO council_decisions (id, ksinr, position, title, summary, official_text, outcome, kind) "
            "VALUES (?, 1, ?, ?, '', '', 'angenommen', 'decision')",
            [(10, 1, "Bebauungsplan N-777 G (Fliegerhorst/Hallensichel Ost/Entlastungsstraße) - Satzungsbeschluss"),
             (11, 2, "Änderung 1 des Bebauungsplanes 777 D (Fliegerhorst/Offizierskasino) - Satzungsbeschluss"),
             (12, 3, "Bebauungsplan 999 (irgendwo in Eversten) - Satzungsbeschluss")])
    fh = geo.ortsbereich_center("Fliegerhorst")
    ev = geo.ortsbereich_center("Eversten")
    assert fh and ev
    store.replace_bplan_outlines([
        # Der Plan selbst liegt im Fliegerhorst …
        {**bplan.normiere({"properties": {"Planverfahren": "777 G", "Name": "Hallensichel-Ost",
                                          "rechtsverbindlich": "2021-03-05"},
                           "geometry": _viereck(fh[1] - 0.002, fh[0] - 0.002)})},
        # … die Änderung von 777 D gibt es nicht, nur den Ursprungsplan (Rückfall) …
        {**bplan.normiere({"properties": {"Planverfahren": "777 D", "Name": "Mittelweg"},
                           "geometry": _viereck(fh[1] - 0.001, fh[0] - 0.001)})},
        # … und 999 liegt in Eversten: nicht auf der Fliegerhorst-Tafel.
        {**bplan.normiere({"properties": {"Planverfahren": "999", "Name": "Eversten"},
                           "geometry": _viereck(ev[1] - 0.002, ev[0] - 0.002)})},
    ])
    assert store.bplan_outline_stats()["mit_flaeche"] == 3
    assert set(store.bplan_outlines_by_keys(["777G", "777D ÄND 1", "777D", "fehlt"])) == {"777G", "777D"}

    orte = store._project_locations([10, 11, 12], "fliegerhorst")
    plaene = {o["slug"]: o for o in orte if o["kind"] == "bplan"}
    assert set(plaene) == {"bplan-777g", "bplan-777d"}
    p = plaene["bplan-777g"]
    assert p["name"] == "Bebauungsplan 777 G" and p["role"] == "subject"
    assert p["geometry"]["type"] == "Polygon"
    assert p["plan"]["effective_date"] == "2021-03-05" and p["plan"]["source_url"] == bplan.QUELLE_URL
    assert geo.ortsbereich_for(p["lat"], p["lon"]) == "Fliegerhorst"
    # Auf der Eversten-Tafel erscheint nur 999.
    assert [o["slug"] for o in store._project_locations([10, 11, 12], "eversten") if o["kind"] == "bplan"] == ["bplan-999"]
    store.close()


class _Antwort:
    def __init__(self, features): self._f = features
    def raise_for_status(self): ...
    def json(self): return {"type": "FeatureCollection", "features": self._f}


def test_fetch_outlines_liest_beide_ebenen_seitenweise(monkeypatch):
    """Rechtsverbindlich (Ebene 18) und in Aufstellung (19), seitenweise; ein
    Schlüssel in beiden Ebenen bleibt rechtsverbindlich."""
    def feature(nr): return {"properties": {"Planverfahren": nr, "Name": nr}, "geometry": _viereck(8.2, 53.1)}
    seiten = {18: [[feature(str(n)) for n in range(1, bplan.SEITE + 1)], [feature("999")]],
              19: [[feature("999"), feature("871")]]}
    aufrufe: list[tuple[int, int]] = []

    def get(url, params=None, timeout=None):
        layer = int(url.rstrip("/query").rsplit("/", 1)[1])
        aufrufe.append((layer, params["resultOffset"]))
        return _Antwort(seiten[layer][params["resultOffset"] // bplan.SEITE])
    monkeypatch.setattr(bplan._session, "get", get)
    zeilen = bplan.fetch_outlines()
    assert aufrufe == [(18, 0), (18, bplan.SEITE), (19, 0)]
    nach_key = {z["key"]: z for z in zeilen}
    assert len(zeilen) == bplan.SEITE + 2
    assert nach_key["999"]["status"] == "effective" and nach_key["871"]["status"] == "in_procedure"


def test_fetch_outlines_verweigert_halben_abzug(monkeypatch):
    monkeypatch.setattr(bplan._session, "get", lambda *a, **k: _Antwort(
        [{"properties": {"Planverfahren": "1"}, "geometry": _viereck(8.2, 53.1)}]))
    with pytest.raises(RuntimeError):
        bplan.fetch_outlines()
