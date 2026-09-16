"""Die Antwort-Abschriften der Browsertests altern mit dem Vertrag.

`web/frontend/tests/e2e/15-wahlabend.spec.ts` mockt `/api/wahlabend` mit einer
Datei, die einmal aus `service.probe(60)` erzeugt wurde. Das ist richtig so —
in der CI ist die Ratsdatenbank leer und ein Abruf beim Votemanager der Stadt
wäre kein Test. Aber: **Kommt ein Feld dazu, weiß die Abschrift nichts davon.**

Genau das ist am 14.09.2026 passiert. `ElectionParty.areas` kam hinzu, die
Seite las `partei.areas.map(…)`, und in der Abschrift stand das Feld nicht —
die Wahlbereichs-Ansicht rannte ins Leere. Aufgefallen ist es erst in den
Browsertests der CI, sechs Minuten später, und die Fehlermeldung
(„expect(locator).toHaveCount(6) failed") zeigte auf die Oberfläche statt auf
die Ursache.

Dieser Wächter vergleicht die Schlüssel der Abschrift mit denen eines frisch
gerechneten Standes. Er prüft die FORM, nicht die Zahlen: Die dürfen
auseinanderlaufen (die Abschrift ist ein Stand von damals), die Felder nicht.

Wieder erzeugen:

    cd web/backend && ../../.venv/bin/python -c "import json; \\
      from app.election import service; print(json.dumps(service.probe(60), ensure_ascii=False))" \\
      > ../frontend/tests/e2e/fixtures/wahlabend-probe.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.antworten import ElectionCandidateDetail  # noqa: E402
from app.election import candidates, service  # noqa: E402

FIXTURES = WURZEL / "web" / "frontend" / "tests" / "e2e" / "fixtures"


@pytest.fixture(scope="module")
def probe() -> dict:
    return service.probe(60)


def _fehlt(soll: dict, ist: dict, pfad: str) -> list[str]:
    """Welche Schlüssel die Abschrift nicht kennt — rekursiv über Objekte und
    das ERSTE Element jeder Liste (die Listen sind gleichförmig)."""
    aus: list[str] = []
    for k, v in soll.items():
        if k not in ist:
            aus.append(f"{pfad}.{k}")
            continue
        if isinstance(v, dict) and isinstance(ist[k], dict):
            aus += _fehlt(v, ist[k], f"{pfad}.{k}")
        elif isinstance(v, list) and v and isinstance(v[0], dict) and isinstance(ist[k], list) and ist[k]:
            aus += _fehlt(v[0], ist[k][0], f"{pfad}.{k}[]")
    return aus


def test_die_wahlabend_abschrift_kennt_jedes_feld(probe):
    ist = json.loads((FIXTURES / "wahlabend-probe.json").read_text(encoding="utf-8"))
    fehlt = _fehlt(probe, ist, "wahlabend")
    assert not fehlt, (
        "Diese Felder fehlen in web/frontend/tests/e2e/fixtures/wahlabend-probe.json:\n  "
        + "\n  ".join(fehlt)
        + "\n\nNeu erzeugen (s. Kopf dieser Datei), sonst laufen die Browsertests "
          "gegen eine Antwort, die es so nicht mehr gibt."
    )


def test_die_kandidaten_abschrift_kennt_jedes_feld(probe):
    ist = json.loads((FIXTURES / "wahlabend-kandidaten-probe.json").read_text(encoding="utf-8"))
    fehlt = _fehlt(candidates.ranking(probe), ist, "kandidaten")
    assert not fehlt, (
        "Diese Felder fehlen in web/frontend/tests/e2e/fixtures/wahlabend-kandidaten-probe.json:\n  "
        + "\n  ".join(fehlt)
    )


def test_die_wahlbezirks_abschrift_kennt_jedes_feld():
    reg = service.load_register()
    frisch = service.districts(reg, service.probe_snapshot(reg, service.load_reference(), 60), "probe")
    ist = json.loads((FIXTURES / "wahlbezirke-probe.json").read_text(encoding="utf-8"))
    fehlt = _fehlt(frisch, ist, "wahlbezirke")
    assert not fehlt, (
        "Diese Felder fehlen in web/frontend/tests/e2e/fixtures/wahlbezirke-probe.json:\n  "
        + "\n  ".join(fehlt)
    )


def _kandidat_frisch(probe: dict) -> dict:
    """Die Abschrift einer EINZELNEN Kandidatur — dieselbe Rechnung wie in
    ``routers/wahlabend.py::wahlabend_kandidat``, für die oberste Zeile der
    Rangliste. Erzeugt die Datei, wenn man sie ausgibt."""
    reg = service.load_register()
    snap = service.probe_snapshot(reg, service.load_reference(), 60)
    z = candidates.ranking(probe)["rows"][0]
    return dict(ElectionCandidateDetail(
        dataset=probe["dataset"], phase=probe["phase"], election=probe["election"],
        party=z["party"], party_short=z["party_short"], color=z["color"], color_dark=z["color_dark"],
        area=z["area"], area_roman=z["area_roman"], area_name=z["area_name"],
        position=z["position"], name=z["name"], occupation=z["occupation"], born=z["born"],
        votes=z["votes"], elected=z["elected"],
        districts=service.candidate_districts(reg, snap, z["party"], z["area"], z["position"]),
    ))


def test_die_kandidat_abschrift_kennt_jedes_feld(probe):
    ist = json.loads((FIXTURES / "wahlabend-kandidat-probe.json").read_text(encoding="utf-8"))
    fehlt = _fehlt(_kandidat_frisch(probe), ist, "kandidat")
    assert not fehlt, (
        "Diese Felder fehlen in web/frontend/tests/e2e/fixtures/wahlabend-kandidat-probe.json:\n  "
        + "\n  ".join(fehlt)
        + "\n\nNeu erzeugen: der Rumpf von _kandidat_frisch() in dieser Datei."
    )


def test_die_abschriften_zeigen_denselben_stand(probe):
    """Beide stammen aus derselben Generalprobe — sonst zeigt die Rangliste
    im Browsertest andere Zahlen als die Tafel darüber."""
    nacht = json.loads((FIXTURES / "wahlabend-probe.json").read_text(encoding="utf-8"))
    rang = json.loads((FIXTURES / "wahlabend-kandidaten-probe.json").read_text(encoding="utf-8"))
    assert rang["dataset"] == nacht["dataset"] and rang["phase"] == nacht["phase"]
    assert rang["total"] == sum(len(p["candidates"]) for a in nacht["areas"] for p in a["parties"])
    assert [p["slug"] for p in rang["parties"]] == [p["slug"] for p in nacht["parties"]]
    bezirke = json.loads((FIXTURES / "wahlbezirke-probe.json").read_text(encoding="utf-8"))
    assert bezirke["counted"] == 60 and bezirke["phase"] == nacht["phase"]
    # Die aufgefaltete Kandidatur ist die oberste Zeile der Rangliste — und
    # ihre Bezirke summieren sich auf deren Stimmen.
    kandidat = json.loads((FIXTURES / "wahlabend-kandidat-probe.json").read_text(encoding="utf-8"))
    assert kandidat["phase"] == nacht["phase"] and kandidat["name"] == rang["rows"][0]["name"]
    assert sum(b["votes"] or 0 for b in kandidat["districts"]) == kandidat["votes"]


# ---------------------------------------------------------------- Stichwahl (S4)

@pytest.fixture
def stichwahl_probe(monkeypatch):
    from app.election import mayor
    from app.routers import wahlabend as router

    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    mayor.reset()
    yield lambda n: router.stichwahl(probe="1", counted=n)
    mayor.reset()


@pytest.mark.parametrize("n", [40, 60, 133])
def test_die_stichwahl_abschriften_kennen_jedes_feld(stichwahl_probe, n):
    """Drei Stände der Stichwahl-Probe für die Browsertests: vor dem
    Führungswechsel (40), danach (60), entschieden (133). Wieder erzeugen:

        FEATURE_FLAGS=wahlabend .venv/bin/python -c "import sys, json; sys.path.insert(0, 'web/backend'); \\
          from app.routers import wahlabend as r; print(json.dumps(r.stichwahl(probe='1', counted=N), ensure_ascii=False))" \\
          > web/frontend/tests/e2e/fixtures/stichwahl-probe-N.json
    """
    ist = json.loads((FIXTURES / f"stichwahl-probe-{n}.json").read_text(encoding="utf-8"))
    fehlt = _fehlt(stichwahl_probe(n), ist, "stichwahl")
    assert not fehlt, (
        f"Diese Felder fehlen in web/frontend/tests/e2e/fixtures/stichwahl-probe-{n}.json:\n  " + "\n  ".join(fehlt)
    )
    assert ist["reports_received"] == n
    assert ist["projection"]["decided"] is (n == 133)


def test_die_stichwahl_bezirke_abschrift_kennt_jedes_feld(stichwahl_probe):
    """Die Karte der Stichwahl (S5) mockt `/api/wahlabend/stichwahl/bezirke`
    mit dem 60er-Stand. Wieder erzeugen wie oben, mit `r.stichwahl_bezirke`."""
    from app.routers import wahlabend as router

    ist = json.loads((FIXTURES / "stichwahl-bezirke-probe-60.json").read_text(encoding="utf-8"))
    fehlt = _fehlt(router.stichwahl_bezirke(probe="1", counted=60), ist, "stichwahl-bezirke")
    assert not fehlt, "Diese Felder fehlen in stichwahl-bezirke-probe-60.json:\n  " + "\n  ".join(fehlt)
    assert ist["counted"] == 60 and ist["total"] == 133


def test_die_rangliste_abschrift_kennt_jedes_feld(monkeypatch):
    """Die Bezirks-Rangliste je Liste (15.09.2026) mockt
    `/api/wahlabend/wahlbezirke/rangliste` mit der Probe für Volt bei 60."""
    from app.election import service
    from app.routers import wahlabend as router

    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    ist = json.loads((FIXTURES / "wahlbezirke-rangliste-probe.json").read_text(encoding="utf-8"))
    soll = router.wahlabend_wahlbezirke_rangliste(party="volt", sort="share", area=None, probe="1", counted=60, wahl=None)
    fehlt = _fehlt(soll, ist, "rangliste")
    assert not fehlt, "Diese Felder fehlen in wahlbezirke-rangliste-probe.json:\n  " + "\n  ".join(fehlt)
    assert ist["party"] == "volt" and ist["counted"] == 60 and ist["total"] == 133
    assert service.DISTRICT_SORTS == ("share", "votes")


# ---------------------------------------------------------------- Stichwahl-Potenzial (P2)

def test_die_potenzial_abschrift_kennt_jedes_feld():
    """Das Wahlkampf-Werkzeug (`/stichwahl/potenzial?k=…`) mockt
    `/api/wahlabend/stichwahl/potenzial` mit der Rechnung zu den Vorgaben.
    Wieder erzeugen: der Befehl im Kopf von
    `web/frontend/tests/e2e/20-stichwahl-potenzial.spec.ts`."""
    from app.election import potential

    ist = json.loads((FIXTURES / "stichwahl-potenzial-probe.json").read_text(encoding="utf-8"))
    fehlt = _fehlt(potential.compute(), ist, "potenzial")
    assert not fehlt, "Diese Felder fehlen in stichwahl-potenzial-probe.json:\n  " + "\n  ".join(fehlt)
    assert ist["lead"] == 2225 and len(ist["districts"]) == 133
    assert ist["bundles"][0]["district_name"] == "Eversten"
