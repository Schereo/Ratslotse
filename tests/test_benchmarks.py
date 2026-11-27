"""Der Benchmark-Bereich: Katalog, Laufformat, Bewertung, Endpunkt.

Was hier festgehalten wird, bliebe sonst still:

- **Jedes KI-Feature gehört genau einer Pipeline** (``kern/benchmarks.py``).
  Ein neues ``_feature="…"`` ohne Eintrag stünde im Admin-Panel nirgends —
  und gerade ungemessene Stufen soll der Bereich zeigen.
- **Jedes Rohergebnis unter ``eval/results/`` hat einen Lauf.** Sonst lägen
  Messungen wieder irgendwo im Repo, ohne dass jemand sie sieht — der Anlass
  für den ganzen Bereich (Tim, 26.11.2026).
- **Jeder Lauf ist gültig** und sein Rohergebnis existiert.
- **„Aktuell" heißt: mit der heutigen Besetzung gemessen.** Ein Kandidat, der
  später lief, verdrängt die Messung des Betriebs nicht; ein Modellwechsel
  macht sie überholt.
- **Nur Admins** sehen die Routen.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from kern import benchmarks as bm  # noqa: E402

QUELLEN = ("council", "kern", "scripts", "web/backend")


def _features_im_code() -> set[str]:
    """Dieselbe Suche wie ``tests/test_feature_namen.py`` — ohne ``eval/``:
    Die Messläufe verbuchen unter eigenen Namen (``eval_cities_*``)."""
    aus: set[str] = set()
    for wz in QUELLEN:
        for pfad in (WURZEL / wz).rglob("*.py"):
            aus |= set(re.findall(r'_feature\s*=\s*"([a-z_0-9]+)"', pfad.read_text()))
    from council.cities.annotators import ANNOTATORS
    aus |= {a.feature for a in ANNOTATORS.values()}
    return aus


# --------------------------------------------------------------- Katalog

def test_jedes_ki_feature_gehoert_genau_einer_pipeline():
    code = _features_im_code()
    assert len(code) > 40, "Der Sucher findet kaum Features — dann prüft dieser Test nichts."
    zuordnung = [f for p in bm.PIPELINES for s in p.steps for f in s.features]
    doppelt = sorted({f for f in zuordnung if zuordnung.count(f) > 1})
    assert not doppelt, f"Features in zwei Stufen/Pipelines: {doppelt}"
    fehlt = sorted(code - set(zuordnung) - set(bm.OUTSIDE_PIPELINES))
    assert not fehlt, (
        "Diese KI-Features gehören zu keiner Pipeline — im Benchmark-Bereich stünden sie nirgends:\n  "
        + "\n  ".join(fehlt)
        + "\nBeheben: als Step in die passende Pipeline in kern/benchmarks.py::PIPELINES "
          "(oder mit Grund nach OUTSIDE_PIPELINES).")
    weg = sorted((set(zuordnung) | set(bm.OUTSIDE_PIPELINES)) - code)
    assert not weg, f"Im Katalog, aber nicht (mehr) im Code — Tippfehler oder Rest: {weg}"


def test_katalog_ist_in_sich_stimmig():
    pipes = [p.key for p in bm.PIPELINES]
    benches = [b.key for b in bm.BENCHMARKS]
    assert len(pipes) == len(set(pipes)) and len(benches) == len(set(benches))
    for p in bm.PIPELINES:
        stufen = [s.key for s in p.steps]
        assert len(stufen) == len(set(stufen)), p.key
    for b in bm.BENCHMARKS:
        assert b.pipeline in pipes, b.key
        assert all(a in pipes and a != b.pipeline for a in b.also), b.key
        erlaubt = {s.key for p in (b.pipeline, *b.also) for s in bm.pipeline(p).steps}
        assert b.steps and set(b.steps) <= erlaubt, f"{b.key}: Stufen {set(b.steps) - erlaubt}"
        assert b.metric.unit in {"share", "count", "seconds", "ratio", "none"}, b.key
        assert b.runs_on in {"local", "server", "both"}, b.key
        assert b.measures and b.command, b.key
        for pfad in b.cases:
            assert (WURZEL / pfad).is_file(), f"{b.key}: Falldatei {pfad} fehlt"
        if b.log:
            assert (WURZEL / b.log).is_file(), f"{b.key}: Messbuch {b.log} fehlt"


def test_jede_pruefstand_suite_hat_ihren_benchmark():
    """Der Prüfstand schreibt seine Läufe unter dem Suite-Namen."""
    from eval import pruefstand
    fehlt = [s.name for s in pruefstand.REGISTER if s.name not in {b.key for b in bm.BENCHMARKS}]
    assert not fehlt, f"Prüfstand-Suiten ohne Benchmark in kern/benchmarks.py: {fehlt}"


def test_jedes_modell_laesst_sich_ablesen():
    from app.routers.benchmarks import resolve_model
    offen = [f"{p.key}/{s.key}: {s.model}" for p in bm.PIPELINES for s in p.steps
             if s.model and not resolve_model(s.model)]
    assert not offen, "Modell-Verweise ohne Ziel (Modul oder Attribut umbenannt?):\n  " + "\n  ".join(offen)


# --------------------------------------------------------------- Läufe

def test_alle_laeufe_im_repo_sind_gueltig():
    laeufe = bm.load_runs(bm.REPO_RUNS)
    assert len(laeufe) > 300, "eval/runs/ ist (fast) leer — python eval/runs_backfill.py --schreiben"
    kaputt = [f"{r['id']}: {'; '.join(r['problems'])}" for r in laeufe if r.get("problems")]
    assert not kaputt, "Ungültige Läufe:\n  " + "\n  ".join(kaputt)
    fehlt = [f"{r['id']}: {p}" for r in laeufe for p in [r.get("raw"), *(r.get("raw_extra") or [])]
             if p and not p.startswith("server:") and not (WURZEL / p).exists()]
    assert not fehlt, "Läufe zeigen auf Rohergebnisse, die es nicht gibt:\n  " + "\n  ".join(fehlt)


def test_jedes_rohergebnis_hat_einen_lauf():
    from eval.runs_backfill import OHNE_LAUF, vom_pruefstand
    abgedeckt: set[str] = set(vom_pruefstand())
    for r in bm.load_runs(bm.REPO_RUNS):
        abgedeckt |= {p for p in [r.get("raw"), *(r.get("raw_extra") or [])] if p}
    roh = sorted(p.relative_to(WURZEL).as_posix() for p in (WURZEL / "eval" / "results").rglob("*")
                 if p.is_file() and p.suffix in (".json", ".md"))
    ohne = [p for p in roh if p not in abgedeckt and not any(p.startswith(a) for a in OHNE_LAUF)]
    assert not ohne, ("Rohergebnisse ohne Lauf — im Admin-Panel unsichtbar:\n  " + "\n  ".join(ohne[:20])
                      + "\nBeheben: python eval/runs_backfill.py --schreiben (oder die Suite schreibt "
                        "ihren Lauf selbst über kern.benchmarks.write_run).")
    leer = [a for a in OHNE_LAUF if not any(p.startswith(a) for p in roh)]
    assert not leer, f"Ausnahmen in OHNE_LAUF ohne Dateien — streichen: {leer}"


def test_write_run_legt_ab_und_weist_ungueltiges_ab(tmp_path: Path):
    rec = bm.new_run("watcher", metrics={bm.QUALITY: 0.9}, environment="local",
                     models={"council_watcher": "openai/gpt-5.6-luna"}, code={}, label="probe")
    assert rec["dataset"]["path"] == "eval/cases_watcher.json" and rec["dataset"]["sha256"]
    pfad = bm.write_run(rec, tmp_path)
    assert pfad.parent.name == "watcher" and "probe" in pfad.name
    assert bm.write_run(rec, tmp_path) != pfad, "zwei Läufe derselben Sekunde überschreiben sich"
    geladen = bm.load_runs(tmp_path)
    assert len(geladen) == 2 and not any(r.get("problems") for r in geladen)
    with pytest.raises(ValueError, match="Hauptkennzahl"):
        bm.write_run({**rec, "metrics": {}}, tmp_path)
    with pytest.raises(ValueError, match="unbekannte Stufe"):
        bm.write_run({**rec, "models": {"qa_answer": "x"}}, tmp_path)


def test_umgebung_aus_der_adresse(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    for adresse, erwartet in (("https://ratslotse.de", "prod"), ("https://dev.ratslotse.de", "dev"),
                              ("http://localhost:3000", "local"), ("", "local")):
        monkeypatch.setenv("APP_BASE_URL", adresse)
        assert bm.detect_environment() == erwartet, adresse


# --------------------------------------------------------------- Bewertung

def _lauf(tag: str, wert: float | None, modell: str, **mehr: object) -> dict:
    rec = bm.new_run("watcher", metrics={bm.QUALITY: wert}, environment="local", code={},
                     started_at=datetime.fromisoformat(f"{tag}T10:00:00"),
                     models={"council_watcher": modell}, **mehr)  # type: ignore[arg-type]
    rec["id"] = f"watcher/{tag}-{modell}"
    return rec


HEUTE = date(2026, 11, 26)
WATCHER = bm.benchmark("watcher")


def test_kandidat_verdraengt_nicht_die_messung_des_betriebs():
    laeufe = [_lauf("2026-11-01", 0.8, "luna"), _lauf("2026-11-10", 0.7, "luna"), _lauf("2026-11-20", 0.95, "haiku")]
    a = bm.assess(WATCHER, laeufe, current_models={"council_watcher": "luna"}, current_cases={}, today=HEUTE)
    assert a.status == "ok"
    assert a.latest and a.latest["metrics"][bm.QUALITY] == 0.7
    assert a.previous and a.previous["metrics"][bm.QUALITY] == 0.8


def test_modellwechsel_macht_die_messung_ueberholt():
    a = bm.assess(WATCHER, [_lauf("2026-11-01", 0.8, "gemini")],
                  current_models={"council_watcher": "luna"}, current_cases={}, today=HEUTE)
    assert a.status == "stale"
    assert a.reasons == [{"kind": "model", "step": "council_watcher", "then": "gemini", "now": "luna"}]


def test_geaenderte_faelle_und_alter():
    lauf = _lauf("2026-07-01", 0.8, "luna")
    sha = lauf["dataset"]["sha256"]
    a = bm.assess(WATCHER, [lauf], current_models={"council_watcher": "luna"},
                  current_cases={"eval/cases_watcher.json": "anders"}, today=HEUTE)
    assert {g["kind"] for g in a.reasons} == {"cases", "age"} and a.status == "stale"
    b = bm.assess(WATCHER, [_lauf("2026-11-01", 0.8, "luna")], current_models={"council_watcher": "luna"},
                  current_cases={"eval/cases_watcher.json": sha}, today=HEUTE)
    assert b.status == "ok" and not b.reasons


def test_teillaeufe_und_leere_zaehlen_nicht():
    assert bm.assess(WATCHER, [], current_models={}, current_cases={}, today=HEUTE).status == "none"
    a = bm.assess(WATCHER, [_lauf("2026-11-01", 0.8, "luna", comparable=False, sample=3)],
                  current_models={"council_watcher": "luna"}, current_cases={}, today=HEUTE)
    assert a.status == "stale" and a.reasons == [{"kind": "not_comparable"}]


def test_uebersicht_nennt_ungemessene_stufen():
    o = bm.overview([], current_models={}, usage={"qa_answer": {"calls": 7, "cost": 0.5, "models": ["m"]}})
    ask = next(p for p in o["pipelines"] if p["key"] == "ask")
    antwort = next(s for s in ask["steps"] if s["key"] == "qa_answer")
    assert antwort["calls_30d"] == 7 and antwort["models_30d"] == ["m"] and antwort["benchmarks"]
    assert any(not s["benchmarks"] for s in ask["steps"]), "party_opinions/qa_simple sind ungemessen"
    assert all(b["status"] == "none" for b in o["benchmarks"])


# --------------------------------------------------------------- Endpunkt

def test_jede_benchmark_route_verlangt_admin():
    from tests.test_endpunkt_schutz import _endpunkte
    routen = [(m, p, n) for m, p, n in _endpunkte() if p.startswith("/api/admin/benchmarks")]
    assert len(routen) >= 2
    ohne = sorted(f"{m.upper()} {p}" for m, p, n in routen if "require_admin" not in n)
    assert not ohne, f"Ohne require_admin: {ohne}"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app
    for base in (os.environ["RATSLOTSE_DB"], os.environ["COUNCIL_DB"]):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    return TestClient(app)


def test_nur_admins_sehen_die_benchmarks(client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from kern.store import Store
    monkeypatch.setattr(bm, "SERVER_RUNS", tmp_path / "keine")
    assert client.get("/api/admin/benchmarks").status_code == 401
    r = client.post("/api/auth/register", json={"display_name": "T", "email": "bench@example.org",
                                                "password": "password123"})
    assert r.status_code == 201
    assert client.get("/api/admin/benchmarks").status_code == 403
    store = Store(os.environ["RATSLOTSE_DB"])
    try:
        store.set_web_user_roles(store.get_web_user_by_email("bench@example.org")["id"], ["admin"])
    finally:
        store.close()
    out = client.get("/api/admin/benchmarks")
    assert out.status_code == 200
    body = out.json()
    assert body["runs_total"] > 300 and not body["invalid"]
    ask = next(p for p in body["pipelines"] if p["key"] == "ask")
    assert ask["headline"] == "ask-gold" and ask["steps"][0]["model"]
    gold = client.get("/api/admin/benchmarks/ask-gold").json()
    assert gold["runs"] and gold["runs"][0]["started_at"] >= gold["runs"][-1]["started_at"]
    assert client.get("/api/admin/benchmarks/gibt-es-nicht").status_code == 404
