"""Die frischen Beispielfragen auf der leeren Fragen-Seite.

Am 10.09.2026 stand dort „Was wurde zu ‚Beratung von nichtöffentlichen
Tagesordnungspunkten im …' entschieden?". Zwei Ursachen, und nur eine davon
sieht nach Textproblem aus:

* Die Sitzung dahinter hatte einen einzigen Tagesordnungspunkt. Ihr
  „wichtigster Beschluss" ist dann zwangsläufig der, der da ist — und das ist
  Verfahrenskram. Kein Titel-Putz repariert das.
* Und der Titel wurde in jedem Client einzeln zurechtgeschnitten: im Web an
  der Wortgrenze, in der App hart bei 69 Zeichen mitten im Wort.

Beides macht jetzt der Server. Hier steht, dass er es tut.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from council.scraper import CouncilSession  # noqa: E402
from council.store import CouncilStore  # noqa: E402

WURZEL = Path(__file__).resolve().parents[1]
COUNCIL_DB = os.environ["COUNCIL_DB"]
RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]


@pytest.fixture(autouse=True)
def fresh_dbs():
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    yield


def _bestand() -> None:
    """Eine dünne Sitzung mit Verfahrenskram, eine mit Substanz."""
    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(CouncilSession(1, "Ausschuss für Allgemeine Angelegenheiten",
                                   "2026-08-17", "17:00", "Rathaus"))
    cs.save_session(CouncilSession(2, "Rat", "2026-06-29", "17:00", "Rathaus"))
    with cs._conn:
        cs._conn.execute(
            "INSERT INTO council_decisions (id,ksinr,position,item_number,title,kind,importance)"
            " VALUES (1,1,1,'1','Beratung von nichtöffentlichen Tagesordnungspunkten"
            " im Verwaltungsausschuss','decision',10)")
        for i in range(6):
            cs._conn.execute(
                "INSERT INTO council_decisions (id,ksinr,position,item_number,title,kind,importance)"
                " VALUES (?,2,?,?,?,'decision',?)",
                (10 + i, i, str(i),
                 "Neubau Sechsfeldhalle am Standort Kennedystraße (Fraktionen SPD, "
                 "Bündnis 90/Die Grünen, CDU und FDP vom 31.03.2026)" if i == 0
                 else f"Weiterer Punkt {i}", 90 - i))
    cs.close()


def test_dünne_sitzungen_liefern_keine_beispielfrage():
    """Die AUSWAHL ist der Fehler gewesen, nicht der Schnitt."""
    _bestand()
    rows = TestClient(app).get("/api/council/qa-beispiele").json()["sessions"]

    assert [r["committee"] for r in rows] == ["Rat"]
    assert all(r["n"] >= 5 for r in rows)


def test_der_titel_kommt_schon_als_gegenstand():
    """Ohne Antragsteller-Klammer — und ohne dass ein Client schneiden muss."""
    _bestand()
    rows = TestClient(app).get("/api/council/qa-beispiele").json()["sessions"]

    assert rows[0]["top_titel"] == "Neubau Sechsfeldhalle am Standort Kennedystraße"


def test_die_app_liest_den_schluessel_den_der_server_sendet():
    """`sitzungen` statt `sessions` — von der Einführung des Endpunkts (#950)
    bis zum 10.09.2026. Der Aufruf steht unter `try?`, das Decodieren
    scheiterte also still, und die App zeigte immer nur ihre eingebauten
    Beispiele.

    `scripts/ios_vertrag.py` hält das inzwischen selbst (es liest seit dem
    10.09. auch `try?`-Aufrufstellen, und `QaExamples` beschreibt seinen Inhalt
    statt `Any`). Der Test hier ist die zweite Naht: Er nennt beim Bruch
    unmissverständlich DIESES Feature, während der Vertragsbericht eine Zeile
    unter 33 anderen zeigt.
    """
    swift = (WURZEL / "ios" / "Packages" / "RatslotseFeatures" / "Sources"
             / "RatslotseFeatures" / "QuestionsView.swift").read_text(encoding="utf-8")
    rumpf = re.search(r"struct QuestionExamplesEnvelope[^{]*\{(.*?)\n\}", swift, re.S)
    assert rumpf, "QuestionExamplesEnvelope nicht gefunden"

    _bestand()
    schluessel = set(TestClient(app).get("/api/council/qa-beispiele").json())
    gelesen = set(re.findall(r"let (\w+):", rumpf.group(1)))

    assert gelesen <= schluessel, (
        f"Die App liest {sorted(gelesen - schluessel)}, der Server sendet "
        f"{sorted(schluessel)}.")
