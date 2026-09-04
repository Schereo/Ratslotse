"""Ein unerreichbarer Straßen-Dienst muss sich wie ein Ausfall lesen.

**Der Fall.** Am 03.09.2026 lief ein Reparaturlauf über 513 Straßen und
meldete ``located=513, missed=2, failed=0``. Overpass war von beiden VPS aus
gar nicht erreichbar (Errno 101 über das NAT-Gateway), der Rückfall auf
Nominatim stumm — 498 Straßen bekamen ein einzelnes Segment statt der ganzen
Straße und damit nur einen Teil ihrer Ortsbereiche. Der Lauf sah erfolgreich
aus. Diese Tests halten die drei Stellen fest, die das künftig verraten: die
Erreichbarkeitsprobe, die Kennzahlen und die Meldung an den Admin.

**Der Nachschlag vom 04.09.2026.** Die Probe von oben war ein EINZELNER
Versuch — und an der öffentlichen Overpass-Instanz endet rund jede zweite
Abfrage mit 429 oder 504. Der Wächter wurde damit selbst zur Fehlerquelle:
Ein Lauf mit zwei neuen Straßen erklärte den Dienst für ausgefallen und
schickte eine Alarmmail, während dieselbe Straße in der Gegenprobe in 0,3 s
kam. Die Tests unten halten deshalb auch das Gegenstück fest — Wiederholung,
Schnappschuss vor Netz und eine Meldeschwelle.
"""
from __future__ import annotations

import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from scripts import geocode_entities as ge  # noqa: E402


def _probe_zuruecksetzen(monkeypatch=None):
    ge._overpass_bereit = None
    ge.overpass_ausfaelle.update({"fehler": 0, "ohne_treffer": 0,
                                  "nicht_erreichbar": 0, "strassen_versucht": 0,
                                  "aus_schnappschuss": 0})
    if monkeypatch is not None:
        # Kein Warten in Tests — die Wiederholung wird gezählt, nicht gesessen.
        monkeypatch.setattr(ge.time, "sleep", lambda _s: None)


def _ohne_schnappschuss(monkeypatch):
    """Kein liegender Schnappschuss — die Tests messen den Netz-Weg."""
    monkeypatch.setattr(ge, "_aus_schnappschuss", lambda name: None)


def test_probe_misst_nur_einmal(monkeypatch):
    """Die Probe ersetzt 513 vergebliche Versuche durch EINE Messung.

    „Einmal" heißt: einmal je LAUF, nicht einmal je Versuch — die Anläufe
    innerhalb der Probe zählen zusammen als die eine Messung.
    """
    _probe_zuruecksetzen(monkeypatch)
    versuche = {"n": 0}

    def kaputt(*a, **k):
        versuche["n"] += 1
        raise ge.requests.ConnectionError("Network is unreachable")

    monkeypatch.setattr(ge.requests, "post", kaputt)
    assert ge.overpass_bereit() is False
    assert ge.overpass_bereit() is False
    assert versuche["n"] == len(ge.PROBE_WARTEN) + 1


def test_probe_gibt_bei_einem_429_nicht_auf(monkeypatch):
    """Der Fehlalarm vom 04.09.2026: EIN 429 hieß „Dienst ausgefallen".

    An der öffentlichen Instanz scheitert rund jede zweite Abfrage. Wer daraus
    ohne zweiten Anlauf „nicht erreichbar" macht, schaltet den Overpass-Weg
    für den ganzen Lauf ab und alarmiert — bei einem Dienst, der läuft.
    """
    _probe_zuruecksetzen(monkeypatch)
    antworten = iter([429, 504, 200])

    class Antwort:
        def __init__(self, code):
            self.status_code = code

        def json(self):
            return {"elements": []}

        def raise_for_status(self):
            raise ge.requests.HTTPError(f"HTTP {self.status_code}")

    monkeypatch.setattr(ge.requests, "post", lambda *a, **k: Antwort(next(antworten)))
    assert ge.overpass_bereit() is True


def test_eigene_kaputte_abfrage_wird_nicht_wiederholt(monkeypatch):
    """Ein 400 ist unsere Abfrage — die wird beim vierten Mal nicht besser."""
    _probe_zuruecksetzen(monkeypatch)
    versuche = {"n": 0}

    class Antwort:
        status_code = 400

        def raise_for_status(self):
            raise ge.requests.HTTPError("HTTP 400")

    def einmal(*a, **k):
        versuche["n"] += 1
        return Antwort()

    monkeypatch.setattr(ge.requests, "post", einmal)
    assert ge.overpass_bereit() is False
    assert versuche["n"] == 1


def test_schnappschuss_kommt_vor_dem_netz(monkeypatch):
    """Was schon auf der Platte liegt, wird nicht im Netz gesucht.

    Der wöchentliche Lauf holt alle benannten Wege Oldenburgs in EINEM Aufruf
    und lässt die Datei liegen. Das tägliche Orts-Geocoding ging trotzdem für
    jede neue Straße wieder ans Netz — und erntete dort die 429er, gegen die
    der Schnappschuss überhaupt gebaut wurde.
    """
    _probe_zuruecksetzen(monkeypatch)

    def kein_netz(*a, **k):
        raise AssertionError("Es wurde ans Netz gegangen, obwohl der "
                             "Schnappschuss die Straße kennt.")

    monkeypatch.setattr(ge.requests, "post", kein_netz)
    monkeypatch.setattr(ge.requests, "get", kein_netz)
    monkeypatch.setattr(ge, "_aus_schnappschuss", lambda name: (53.1, 8.2, "{}"))

    assert ge.geocode("Tweelbäker Tredde", "street") == (53.1, 8.2, "{}")
    assert ge.overpass_ausfaelle["aus_schnappschuss"] == 1
    # Und er zählt NICHT als Overpass-Versuch: Sonst löst ein Lauf, in dem
    # alles glattging, den Alarm „alle Straßen verloren" aus.
    assert ge.overpass_ausfaelle["strassen_versucht"] == 0


def test_ausfall_landet_in_den_kennzahlen(monkeypatch):
    """Nicht der Rückfall ist das Problem, sondern sein Verschweigen."""
    _probe_zuruecksetzen(monkeypatch)
    _ohne_schnappschuss(monkeypatch)
    monkeypatch.setattr(ge.requests, "post", lambda *a, **k: (_ for _ in ()).throw(
        ge.requests.ConnectionError("Network is unreachable")))
    monkeypatch.setattr(ge, "nominatim", lambda name: (53.1, 8.2, None))

    assert ge.geocode("Tweelbäker Tredde", "street") == (53.1, 8.2, None)
    assert ge.overpass_ausfaelle["strassen_versucht"] == 1
    assert ge.overpass_ausfaelle["nicht_erreichbar"] == 1
    # Ein Ort, der keine Straße ist, zählt nicht mit — er will kein Overpass.
    ge.geocode("Kulturzentrum PFL", "building")
    assert ge.overpass_ausfaelle["strassen_versucht"] == 1


def test_totalausfall_wird_gemeldet(monkeypatch):
    """Alle Straßen verloren → Mail an den Admin. Sonst nicht: An einem Tag
    ohne neue Straße soll niemand geweckt werden."""
    from scripts import geocode_decision_locations as gdl

    meldungen = []
    monkeypatch.setattr(gdl, "notify_admin",
                        lambda text, **kw: meldungen.append(text))

    _probe_zuruecksetzen(monkeypatch)
    gdl.overpass_ausfaelle.update({"strassen_versucht": 7, "nicht_erreichbar": 7})
    gdl._melde_overpass_ausfall(offen=415)
    assert len(meldungen) == 1
    assert "7 von 7" in meldungen[0] and "415" in meldungen[0]

    # Teilweise geglückt: kein Alarm, die Kennzahlen tragen es.
    meldungen.clear()
    gdl.overpass_ausfaelle.update({"strassen_versucht": 7, "nicht_erreichbar": 3,
                                   "fehler": 0})
    gdl._melde_overpass_ausfall(offen=415)
    # Gar nichts zu tun gewesen: auch kein Alarm.
    gdl.overpass_ausfaelle.update({"strassen_versucht": 0, "nicht_erreichbar": 0})
    gdl._melde_overpass_ausfall(offen=415)
    assert meldungen == []


def test_zwei_verlorene_strassen_alarmieren_nicht(monkeypatch):
    """Genau die Mail vom 04.09.2026 — sie darf so nicht mehr entstehen.

    „2 von 2" erfüllt „alle Versuche gescheitert", ist aber ein einzelner
    schlechter Moment der öffentlichen Instanz und kein Betriebsvorfall. Erst
    ab `MINDESTENS_STRASSEN` ist der Befund tragfähig.
    """
    from scripts import geocode_decision_locations as gdl

    meldungen = []
    monkeypatch.setattr(gdl, "notify_admin", lambda text, **kw: meldungen.append(text))
    gdl.overpass_ausfaelle.update({"strassen_versucht": 2, "nicht_erreichbar": 2,
                                   "fehler": 0})
    gdl._melde_overpass_ausfall(offen=292)
    assert meldungen == []


def test_meldung_erklaert_die_bestandszahl(monkeypatch):
    """Die Bestandszahl darf nicht als Aufgabe gelesen werden.

    Die alte Mail nannte „292 Straßen ohne vollständige Geometrie" direkt vor
    dem Reparatur-Workflow. Der senkt sie aber nicht: Es sind Namen, die OSM
    gar nicht führt („Huntemannstr"). Wer dem Hinweis folgte, sah `orte_neu=0`
    und lernte nichts.
    """
    from scripts import geocode_decision_locations as gdl

    meldungen = []
    monkeypatch.setattr(gdl, "notify_admin", lambda text, **kw: meldungen.append(text))
    gdl.overpass_ausfaelle.update({"strassen_versucht": 9, "nicht_erreichbar": 9,
                                   "fehler": 0})
    gdl._melde_overpass_ausfall(offen=292)
    assert len(meldungen) == 1
    assert "sinkt durch den Workflow <i>nicht</i>" in meldungen[0]
