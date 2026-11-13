"""Das Umfeld eines Punkts (``council/punkt_umfeld.py``): Orte, ähnliche frühere
Beschlüsse, Video, Beteiligung — aus vorhandenen Daten und ohne Modell. Die
Schwellen und Filter stammen aus der Stichprobe vom 13.11.2026."""
from council import punkt_umfeld as pu


class _Store:
    def __init__(self, *, orte=None, nachbarn=None, videos=None, beteiligungen=None, felder=None):
        self.orte, self.nachbarn, self.videos = orte or {}, nachbarn or {}, videos or []
        self.beteiligungen, self.felder = beteiligungen or [], felder or {}

    def decision_locations(self, decision_id):
        return self.orte.get(decision_id, [])

    def street_locations(self):
        return [{"slug": "postweg", "name": "Postweg", "kind": "street", "lat": 53.1, "lon": 8.2, "district": "Eversten"},
                {"slug": "alter-postweg", "name": "Alter Postweg", "kind": "street", "lat": 53.2, "lon": 8.3, "district": "Osternburg"},
                {"slug": "markt", "name": "Markt", "kind": "square", "lat": 53.14, "lon": 8.21, "district": "Innenstadt"},
                {"slug": "pellwormer-weg", "name": "Pellwormer Weg", "kind": "street", "lat": 53.17, "lon": 8.25, "district": None}]

    def get_similar(self, decision_id, limit=5):
        return self.nachbarn.get(decision_id, [])[:limit]

    def get_decision(self, decision_id):
        return {"id": decision_id, "policy_field": self.felder.get(decision_id)}

    def get_video_results(self, ksinr):
        return self.videos

    def list_beteiligungen(self, nur_laufende=True):
        return self.beteiligungen


def _punkt(titel="Widmung der Straße \"Pellwormer Weg\" - Beschluss", **mehr):
    return {"ksinr": 4700, "committee": "Rat", "session_date": "2026-10-26", "decision_id": None, "history": [],
            "item": {"title": titel, "item_number": "Ö 9.1"}, **mehr}


def _ort(slug, name, sicherheit=0.9, lat=53.1):
    return {"slug": slug, "name": name, "kind": "street", "lat": lat, "lon": 8.2, "district": "Etzhorn", "confidence": sicherheit}


def _nachbar(i, titel, score, datum="2024-05-01", feld="Verkehr"):
    return {"id": i, "title": titel, "score": score, "session_date": datum, "committee": "Verkehrsausschuss",
            "policy_field": feld, "outcome": "angenommen", "summary": None}


def test_orte_kommen_aus_den_beschluessen_der_vorlage():
    s = _Store(orte={11: [_ort("etzhorner-weg", "Etzhorner Weg"), _ort("vage", "Irgendwo", sicherheit=0.3),
                          _ort("ohne-koordinate", "Ohne", lat=None)],
                     12: [_ort("etzhorner-weg", "Etzhorner Weg"), _ort("harmsweg", "Harmsweg")]})
    p = _punkt(decision_id=12, history=[{"decision_id": 11}, {"decision_id": None}])
    assert [(o["name"], o["source"]) for o in pu.places(s, p)] == [("Etzhorner Weg", "decision"), ("Harmsweg", "decision")]


def test_ohne_beschluss_zaehlt_ein_strassenname_im_titel():
    orte = pu.places(_Store(), _punkt())
    assert [(o["name"], o["source"]) for o in orte] == [("Pellwormer Weg", "title")]


def test_im_titel_gewinnt_der_laengste_name_und_markt_verortet_keine_gebuehr():
    s = _Store()
    assert [o["name"] for o in pu.places(s, _punkt("Radweg am Alter Postweg - Bericht"))] == ["Alter Postweg"]
    assert pu.places(s, _punkt("Änderung der Marktgebührensatzung - Beschluss")) == []
    assert pu.places(s, _punkt("Neuordnung am Markt - Bericht")) == []      # zu kurz für einen sicheren Treffer


def test_aehnliche_nur_frueher_sicher_und_aus_demselben_feld():
    s = _Store(felder={7: "Verkehr"}, nachbarn={7: [
        _nachbar(1, "Gehwegparken beenden - Beschluss", 0.91),
        _nachbar(2, "Gehwegparken beenden - Bericht", 0.90),                 # derselbe Kern
        _nachbar(3, "Stadttaubenhilfe - Bericht", 0.95, feld="Umwelt"),      # anderes Themenfeld
        _nachbar(4, "Parkgebühren - Beschluss", 0.72),                       # unter der Schwelle
        _nachbar(5, "E-Scooter-Parkzonen - Beschluss", 0.88, datum="2027-01-01"),   # später als diese Sitzung
        _nachbar(7, "Die eigene Station", 0.99)]})
    p = _punkt("Parken auf Sicherheitstrennstreifen - Bericht", decision_id=7)
    assert [n["id"] for n in pu.similar(s, p)] == [1]


def test_bei_bebauungsplaenen_nur_derselbe_plan():
    s = _Store(nachbarn={7: [_nachbar(1, "Bebauungsplan 847 (südlich Rohdenweg) - Beschluss zur Veröffentlichung", 0.94),
                             _nachbar(2, "Bebauungsplan 858 (Nadorster Straße) - Aufstellungsbeschluss", 0.90),
                             _nachbar(3, "Wohnraumkonzept - Bericht", 0.90)]})
    p = _punkt("Bebauungsplan 858 (Nadorster Straße / Kreyenstraße) - Beschluss zur Veröffentlichung", decision_id=7)
    assert [n["id"] for n in pu.similar(s, p)] == [2]


def test_video_nur_im_rat_und_nur_fuer_diesen_punkt():
    s = _Store(videos=[{"item_number": "9.1", "video_id": "abc", "video_seconds": 5025},
                       {"item_number": "9.2", "video_id": "abc", "video_seconds": 6000}])
    assert pu.video(s, _punkt()) == {"video_id": "abc", "seconds": 5025}
    assert pu.video(s, _punkt(committee="Verkehrsausschuss")) is None
    assert pu.video(_Store(), _punkt()) is None


def test_beteiligung_ueber_die_plannummer():
    s = _Store(beteiligungen=[{"title": "B-Plan 871", "ort": "Etzhorn", "schritt": "Öffentliche Auslegung", "valid_from": "2026-11-01",
                               "valid_until": "2026-12-01", "url": "https://example.org/871", "plan_nrs": ["bp-871"], "status": "laufend"}])
    b = pu.participation(s, _punkt("Bebauungsplan 871 (Etzhorner Weg/Harmsweg) - Aufstellungsbeschluss"))
    assert b["step"] == "Öffentliche Auslegung" and b["valid_until"] == "2026-12-01" and b["status"] == "laufend"
    assert pu.participation(s, _punkt("Bebauungsplan 87 (Anderswo) - Bericht")) is None


def test_nichts_zu_zeigen_heisst_kein_feld():
    assert pu.item_surroundings(_Store(), _punkt("Bericht des Oberbürgermeisters", committee="Kulturausschuss")) is None
    u = pu.item_surroundings(_Store(), _punkt())
    assert u["places"] and u["similar"] == [] and u["video"] is None and u["participation"] is None
