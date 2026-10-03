"""„Mein Viertel": Datenqualität, Zähler und Fehlerwege (Review vor 3.0.0).

Gemessen am Prod-Abzug vom 01.10.2026:

1. Vier von sechs Stadt-Highlights „Im Bau“ mit abgelaufenem Zeitraum.
2. Die Stadtzahl zählte gemeldete Vorhaben mit und Grenz-Vorhaben doppelt.
3. B-Plan 858 und 837 (ganz in Nadorst) standen auch in Bürgeresch,
   Dietrichsfeld, Ofenerdiek; die Grundschule Fliegerhorst in Dietrichsfeld;
   Vorhaben ohne einen einzigen sicheren Richter-Spruch auf der Tafel.
4. „Stand" war der Zeitpunkt des Laufs, nicht der jüngste Beschluss.
5. Die Sperrungen gingen ohne Heim-Proxy ans Geoportal, der Fehler wurde
   verschluckt.
7. Der Register-Lauf endete mit Exit 0, auch wenn Viertel übersprungen wurden.

Das Sprachmodell wird gestubbt; geprüft wird, was um den Aufruf herum
entscheidet.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "web" / "backend"))
sys.path.insert(0, str(_ROOT / "scripts"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from council import bplan, geo, viertel  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from council.store_viertel import PROJECT_HIDE_REPORTS, PROJECT_MIN_CONFIDENCE  # noqa: E402

COUNCIL_DB = os.environ["COUNCIL_DB"]
RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]


@pytest.fixture(autouse=True)
def fresh_dbs():
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    yield


def _store() -> CouncilStore:
    return CouncilStore(COUNCIL_DB)


def _sitzung(store: CouncilStore, ksinr: int, datum: str) -> None:
    store._conn.execute(
        "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
        "VALUES (?, 'Rat', ?, '18:00', 'Rathaus', '2026-01-01')", (ksinr, datum))


def _beschluss(store: CouncilStore, did: int, ksinr: int, titel: str) -> None:
    store._conn.execute(
        "INSERT INTO council_decisions (id, ksinr, position, title, summary, official_text, outcome, kind) "
        "VALUES (?, ?, ?, ?, 'Kurz.', 'Der Rat beschließt.', 'angenommen', 'decision')", (did, ksinr, did, titel))


def _ort(store: CouncilStore, slug: str, name: str, kind: str, bereich: str, place_id: str,
         share: float = 1.0) -> None:
    store._conn.execute(
        "INSERT OR IGNORE INTO council_locations (slug, name, kind, district, local_area_id, updated_at) "
        "VALUES (?, ?, ?, ?, ?, '2026-01-01')", (slug, name, kind, bereich, place_id))
    store._conn.execute(
        "INSERT INTO council_location_districts (location_slug, district, place_id, share) VALUES (?, ?, ?, ?)",
        (slug, bereich, place_id, share))


def _nennt(store: CouncilStore, did: int, slug: str, source: str = "title", method: str = "regex") -> None:
    store._conn.execute(
        "INSERT INTO council_decision_locations (decision_id, location_slug, source, evidence, method, "
        "confidence, updated_at) VALUES (?, ?, ?, '', ?, 0.9, '2026-01-01')", (did, slug, source, method))


def _umring_in(name: str, d: float = 0.002) -> dict:
    lat, lon = geo.ortsbereich_center(name)
    return {"type": "Polygon", "coordinates": [[[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d],
                                                 [lon - d, lat + d], [lon - d, lat - d]]]}


def _projekt(name: str, ids: list[int], stage: str = "planning", when: str | None = None,
             confidence: int = 95) -> dict:
    return {"name": name, "what": "x", "stage": stage, "when": when, "category": "other",
            "decision_ids": ids, "confidence": confidence}


class _Antwort:
    def __init__(self, payload: dict):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]


# ------------------------------------------------------------ 1. Zeitplan


def _highlight_bestand(store: CouncilStore) -> None:
    with store._conn:
        _sitzung(store, 1, "2026-05-04")
        for did in (1, 2, 3, 4):
            _beschluss(store, did, 1, f"Beschluss {did}")
    store.replace_district_projects("eversten", [_projekt("Skateanlage Eversten", [1], "building", "bis 31. Januar 2026")])
    store.replace_district_projects("kreyenbrueck", [_projekt("IGS-Sporthalle", [2], "building", "4. Quartal 2025")])
    store.replace_district_projects("osternburg", [_projekt("Brücke", [3], "decided", "2028")])
    store.replace_district_projects("nadorst", [_projekt("Kita Eßkamp", [4], "building", "Kindergartenjahr 2026/2027")])


def test_highlights_lassen_abgelaufene_weg():
    store = _store()
    _highlight_bestand(store)
    namen = [h["name"] for h in store.district_highlights(today=date(2026, 10, 3))]
    assert namen == ["Kita Eßkamp", "Brücke"]
    # Vor Ablauf standen sie noch da — „Im Bau" zuerst.
    namen = [h["name"] for h in store.district_highlights(today=date(2025, 6, 1))]
    assert namen[:3] == ["Skateanlage Eversten", "IGS-Sporthalle", "Kita Eßkamp"]
    store.close()


def test_tafel_kennzeichnet_abgelaufene():
    store = _store()
    _highlight_bestand(store)
    p = store.district_projects("eversten")[0]
    assert p["schedule"] == "likely_done"
    assert p["when_end"] == "2026-01-31"
    assert "bis 31. Januar 2026" in p["schedule_note"]
    assert store.district_projects("nadorst")[0]["schedule"] is None
    store.close()


# ------------------------------------------------------------- 2. Zähler


def _zaehler_bestand(store: CouncilStore) -> None:
    with store._conn:
        _sitzung(store, 1, "2026-05-04")
        for did in (1, 2, 3, 4, 5):
            _beschluss(store, did, 1, f"Beschluss {did}")
    # Ein Grenz-Vorhaben (derselbe Plan, fast derselbe Name) in zwei Vierteln,
    # ein Sammelbericht (ein Beschluss, zwei verschiedene Hallen), dazu eine
    # Idee und ein gemeldetes Vorhaben.
    store.replace_district_projects("nadorst", [
        _projekt("Wohngebiet nördlich des Eßkamps", [1, 2], "decided"),
        _projekt("Sanierung der Sporthalle der Grundschule Nadorst", [3]),
        _projekt("Spielplatz Idee", [5], "idea"),
    ])
    store.replace_district_projects("ofenerdiek", [
        _projekt("Wohngebiet nördlich Eßkamp", [2], "decided"),
        _projekt("Sanierung der Sporthalle der IGS Ofenerdiek", [3]),
        _projekt("Gemeldet", [4], "building"),
    ])
    key = store._conn.execute("SELECT project_key FROM council_district_projects WHERE name = 'Gemeldet'").fetchone()[0]
    for owner in range(PROJECT_HIDE_REPORTS):
        store.save_district_project_report(key, "ofenerdiek", owner + 1, None)


def test_stadtzahl_entdoppelt_und_zaehlt_gemeldete_nicht():
    store = _store()
    _zaehler_bestand(store)
    uebersicht = store.district_projects_overview()
    assert uebersicht["nadorst"]["count"] == 3
    # Das gemeldete fehlt — auf der Tafel fehlt es auch.
    assert uebersicht["ofenerdiek"]["count"] == 2
    assert "building" not in uebersicht["ofenerdiek"]["stages"]
    stadt = store.district_city_totals()
    # 5 Tafel-Einträge, das Eßkamp-Wohngebiet zählt einmal, die Hallen zweimal.
    assert stadt == {"total": 4, "stages": {"decided": 1, "planning": 2, "idea": 1}, "shared": 1}
    assert sum(stadt["stages"].values()) == stadt["total"]
    store.close()


def _konto(client: TestClient, email: str = "leserin@example.org") -> str:
    r = client.post("/api/auth/register", json={"display_name": "Testkonto", "email": email, "password": "password123"})
    assert r.status_code == 201, r.text
    from kern.store import Store
    s = Store(RATSLOTSE_DB)
    with s._conn:
        s._conn.execute("UPDATE web_users SET status = 'active' WHERE email = ?", (email,))
    s.close()
    r = client.post("/api/auth/login", json={"email": email, "password": "password123"}, headers={"X-Client": "app"})
    return r.json()["access_token"]


def test_endpunkte_tragen_stadtzahl_und_beschluesse_bis():
    store = _store()
    _zaehler_bestand(store)
    with store._conn:
        _sitzung(store, 2, "2026-08-27")
        _beschluss(store, 9, 2, "Spätester Beschluss")
    store.save_district_reviews("nadorst", [{"decision_id": 9, "relation": "elsewhere", "confidence": 90,
                                             "source_hash": "x"}], "test")
    store.close()
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {_konto(client)}"
    u = client.get("/api/districts/projects").json()
    assert u["total"] == 4 and u["shared"] == 1
    assert sum(u["stages"].values()) == u["total"]
    assert sum(d["count"] for d in u["districts"]) == 5
    # Datenstand = jüngster beurteilter Beschluss, nicht der Laufzeitpunkt.
    assert u["decisions_until"] == "2026-08-27"
    tafel = client.get("/api/districts/nadorst/projects").json()
    assert tafel["decisions_until"] == "2026-08-27"
    assert all("schedule" in p for p in tafel["projects"])


# ----------------------------------------------------- 3. Verortung, Regeln


def _verortung_bestand(store: CouncilStore) -> None:
    with store._conn:
        _sitzung(store, 1, "2026-05-04")
        _sitzung(store, 2, "2026-06-01")
        _beschluss(store, 10, 1, "Bebauungsplan 837 (nördlich Eßkamp/östlich Südbäke) - Satzungsbeschluss")
        _beschluss(store, 11, 1, "Änderung 84 des Flächennutzungsplanes 1996 (nördlich Eßkamp/östlich Südbäke)")
        # Dieselbe Klammer, aber an einem anderen Tag — erbt nichts.
        _beschluss(store, 12, 2, "Änderung 99 des Flächennutzungsplanes (nördlich Eßkamp/östlich Südbäke)")
        _beschluss(store, 20, 1, "Neue Grundschule auf dem Gelände des ehemaligen Fliegerhorstes")
        _beschluss(store, 21, 1, "Neubau am Sportpark Osternburg")
        # Eine Straße am Rand des Plans, zu 60 % in Ofenerdiek.
        _ort(store, "esskamp", "Eßkamp", "street", "Ofenerdiek", "ofenerdiek", 0.6)
        for did in (10, 11, 12):
            _nennt(store, did, "esskamp", source="official_text")
        _ort(store, "fliegerhorst", "Fliegerhorst", "district", "Fliegerhorst", "fliegerhorst")
        _ort(store, "dietrichsfeld", "Dietrichsfeld", "district", "Dietrichsfeld", "dietrichsfeld")
        _nennt(store, 20, "fliegerhorst")
        _nennt(store, 20, "dietrichsfeld", source="template", method="llm")
        _ort(store, "osternburg", "Osternburg", "district", "Osternburg", "osternburg")
        _ort(store, "sportpark-osternburg", "Sportpark Osternburg", "area", "Tweelbäke", "tweelbaeke")
        _nennt(store, 21, "osternburg")
        _nennt(store, 21, "sportpark-osternburg")
    store.replace_bplan_outlines([bplan.normiere(
        {"properties": {"Planverfahren": "837"}, "geometry": _umring_in("Nadorst")}, "in_procedure")])


def test_bebauungsplan_entscheidet_ueber_seine_flaeche():
    store = _store()
    _verortung_bestand(store)
    ofenerdiek = store.resolve_place("ofenerdiek")
    kand = {k["id"]: k for k in store.district_candidates(ofenerdiek, since="2026-01-01")}
    # Die Straße am Rand bringt Plan und Flächennutzungsplan als Kandidaten …
    assert {10, 11, 12} <= set(kand)
    # … aber der Umring liegt ganz in Nadorst. Die F-Plan-Änderung erbt ihn
    # über Klammer und Sitzungstag; die vom anderen Tag nicht.
    assert viertel.ortsregel(kand[10], ofenerdiek) == "Bebauungsplan 837 liegt in Nadorst"
    assert viertel.ortsregel(kand[11], ofenerdiek) == "Bebauungsplan 837 liegt in Nadorst"
    assert "plan" not in kand[12] and viertel.ortsregel(kand[12], ofenerdiek) is None

    # In Nadorst ist der Plan Kandidat, obwohl keine Straße dort erkannt wurde.
    nadorst = store.resolve_place("nadorst")
    kand = {k["id"]: k for k in store.district_candidates(nadorst, since="2026-01-01")}
    assert {10, 11} <= set(kand)
    assert viertel.ortsregel(kand[10], nadorst) is None
    assert any(loc["kind"] == "bplan" and loc["strict"] for loc in kand[10]["locations"])
    store.close()


def test_titel_mit_anderem_ortsbereich():
    store = _store()
    _verortung_bestand(store)
    dietrichsfeld = store.resolve_place("dietrichsfeld")
    kand = {k["id"]: k for k in store.district_candidates(dietrichsfeld, since="2026-01-01")}
    # Die Vorlage erwähnt Dietrichsfeld, der Titel nennt den Fliegerhorst.
    assert viertel.ortsregel(kand[20], dietrichsfeld) == "Titel nennt Fliegerhorst"
    fliegerhorst = store.resolve_place("fliegerhorst")
    kand = {k["id"]: k for k in store.district_candidates(fliegerhorst, since="2026-01-01")}
    assert viertel.ortsregel(kand[20], fliegerhorst) is None
    # „Sportpark Osternburg" liegt in Tweelbäke — ein Ort aus dem Titel, der
    # hier liegt, hebt die Regel auf.
    tweelbaeke = store.resolve_place("tweelbaeke")
    kand = {k["id"]: k for k in store.district_candidates(tweelbaeke, since="2026-01-01")}
    assert viertel.ortsregel(kand[21], tweelbaeke) is None
    store.close()


def test_regel_kandidaten_gehen_nicht_an_den_richter(monkeypatch):
    store = _store()
    _verortung_bestand(store)
    gesehen: list[str] = []

    def fake(**kwargs):
        user = kwargs["messages"][1]["content"]
        gesehen.append(user)
        if "VORHABEN" in kwargs["messages"][0]["content"]:
            return _Antwort({"projects": []})
        ids = [int(z.split()[1].rstrip(":")) for z in user.splitlines() if z.startswith("id ")]
        return _Antwort({"reviews": [{"id": i, "relation": "district", "changes": True, "confidence": 95}
                                     for i in ids]})

    monkeypatch.setattr(viertel.llm, "chat_complete", fake)
    stats = viertel.build_place(store, store.resolve_place("ofenerdiek"))
    assert stats["excluded"] == 2
    assert not any("id 10:" in u or "id 11:" in u for u in gesehen)
    store.close()


def _buendel_bestand(store: CouncilStore) -> None:
    with store._conn:
        _sitzung(store, 1, "2026-05-04")
        for did in (1, 2, 3, 4, 5):
            _beschluss(store, did, 1, f"Beschluss {did}")
        _ort(store, "weg", "Ein Weg", "street", "Eversten", "eversten")
        for did in (1, 2, 3, 4, 5):
            _nennt(store, did, "weg")


def test_buendelung_braucht_richterspruch_und_veraenderung(monkeypatch):
    store = _store()
    _buendel_bestand(store)
    urteile = {1: (82, True), 2: (96, False), 3: (96, True), 4: (95, False), 5: (93, False)}

    def fake(**kwargs):
        system = kwargs["messages"][0]["content"]
        user = kwargs["messages"][1]["content"]
        if "VORHABEN" in system:
            assert "Heute ist der 03.10.2026." in user
            return _Antwort({"projects": [
                _projekt("Zweifel des Richters", [1], confidence=98),
                _projekt("Nur ein Bericht", [2], confidence=98),
                _projekt("Echtes Vorhaben", [3, 1], confidence=97),
                _projekt("Abgelehnt", [4], stage="rejected", confidence=96),
                _projekt("Fertig", [5], stage="done", confidence=95),
            ]})
        return _Antwort({"reviews": [
            {"id": i, "relation": "district", "changes": ch, "confidence": c} for i, (c, ch) in urteile.items()]})

    monkeypatch.setattr(viertel.llm, "chat_complete", fake)
    monkeypatch.setattr(viertel, "date", SimpleNamespace(today=lambda: date(2026, 10, 3)))
    viertel.build_place(store, store.resolve_place("eversten"))
    conf = {p["name"]: p["confidence"] for p in store.district_projects("eversten", min_confidence=0)}
    # Die Sicherheit ist die des Richters, nicht die der Bündelung (98).
    assert conf["Zweifel des Richters"] == 82
    assert conf["Nur ein Bericht"] == PROJECT_MIN_CONFIDENCE - 1
    # Ein sicherer Beschluss mit Veränderung reicht, auch neben einem unsicheren.
    assert conf["Echtes Vorhaben"] == 96
    # Abgelehnt ändert per Definition nichts — und bleibt trotzdem sichtbar.
    assert conf["Abgelehnt"] == 95
    # Dasselbe für Fertiges: Die Abrechnung einer fertigen Kreuzung ändert nichts mehr.
    assert conf["Fertig"] == 93
    assert {p["name"] for p in store.district_projects("eversten")} == {"Abgelehnt", "Echtes Vorhaben", "Fertig"}
    store.close()


def test_neuer_richter_prompt_macht_den_cache_ungueltig(monkeypatch):
    k = {"title": "t", "locations": [], "other_districts": []}
    vorher = viertel.source_hash(k)
    monkeypatch.setattr(viertel.prompts, "render", lambda key, **kw: "eine andere Regel")
    assert viertel.source_hash(k) != vorher


def test_sichere_treffer_ohne_vorhaben_werden_nachgetragen():
    """Die Bündelung ließ bei gleicher Eingabe einzelne sichere Beschlüsse
    liegen; sie bekommen ein eigenes Vorhaben — eins je Vorlage."""
    def treffer(did, kvonr, conf, changes=True, datum="2026-05-04"):
        return {"id": did, "kvonr": kvonr, "date": datum,
                "title": f"Spielplatz Schlossplatz (SPD-Fraktion vom 01.02.2026) - Bericht {did}",
                "review": {"confidence": conf, "changes": changes, "what": "Ein Spielplatz entsteht.",
                           "stage": "planning", "when": "2027", "category": "green"}}
    hits = [treffer(1, 500, 99), treffer(2, 500, 95, datum="2026-06-01"), treffer(3, None, 97),
            treffer(4, None, 80), treffer(5, None, 99, changes=False), treffer(6, None, 99)]
    waisen = viertel.verwaiste_vorhaben(hits, [{"decision_ids": [6]}])
    assert sorted(w["decision_ids"] for w in waisen) == [[1, 2], [3]]
    ausschuss_und_rat = next(w for w in waisen if w["decision_ids"] == [1, 2])
    assert ausschuss_und_rat["name"] == "Spielplatz Schlossplatz"
    assert ausschuss_und_rat["confidence"] == 99 and ausschuss_und_rat["when"] == "2027"


# ------------------------------------------------- 5. Sperrungen, Fehler


def test_sperrungen_gehen_ueber_den_heim_proxy(monkeypatch):
    from council import sperrungen
    monkeypatch.setenv("RATSLOTSE_PROXY_URL", "socks5h://nas.example.org:1080")
    monkeypatch.setenv("RATSLOTSE_PROXY_HOSTS", "gisportal4ol.oldenburg.de")
    gesehen: dict = {}

    class _R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"features": []}

    def fake_get(url, **kwargs):
        gesehen["url"] = url
        gesehen["proxies"] = kwargs.get("proxies")
        return _R()

    monkeypatch.setattr(sperrungen._session, "get", fake_get)
    assert sperrungen.fetch_closures() == []
    assert "gisportal4ol.oldenburg.de" in gesehen["url"]
    assert gesehen["proxies"] == {"http": "socks5h://nas.example.org:1080",
                                  "https": "socks5h://nas.example.org:1080"}


def test_stadtquellen_melden_einen_gescheiterten_teil(monkeypatch):
    import check_presse
    from council import beteiligung, presse, presse_orte, sperrungen
    from kern.alerts import JobFehler

    monkeypatch.setattr(check_presse, "COUNCIL_DB", Path(COUNCIL_DB))
    monkeypatch.setattr(presse, "fetch_feed", list)
    monkeypatch.setattr(beteiligung, "fetch_planfaelle", list)
    monkeypatch.setattr(presse_orte, "verorte", lambda store, rows: {"verortet": 0})

    def gesperrt():
        raise RuntimeError("403 Forbidden")

    monkeypatch.setattr(sperrungen, "fetch_closures", gesperrt)
    with pytest.raises(JobFehler) as fehler:
        check_presse.main()
    assert "Sperrungen" in str(fehler.value) and "403" in str(fehler.value)
    # Die Kennzahlen der übrigen Teile bleiben erhalten.
    assert fehler.value.kennzahlen["teilfehler"] == 1
    assert fehler.value.kennzahlen["sperrungen"] == -1

    monkeypatch.setattr(sperrungen, "fetch_closures", list)
    assert check_presse.main()["teilfehler"] == 0


def test_register_lauf_meldet_uebersprungene_viertel():
    import build_district_projects
    assert build_district_projects.exit_code({"übersprungen": 0}) == 0
    assert build_district_projects.exit_code({"übersprungen": 2}) == 1
