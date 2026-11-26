"""Der Benchmark-Bereich des Admin-Panels — wie gut die KI-Pipelines gerade sind.

Katalog, Laufformat und Bewertung stehen in ``kern/benchmarks.py``; hier
passiert nur, was ``kern`` nicht darf: die Modelle aus den ``council``-Modulen
ablesen, so wie dieser Dienst sie beim Import gebunden hat.

**Nur für Admins**, jede Route hier: Die Läufe nennen Modelle, Kosten und
Commits — nichts Persönliches, aber Betriebsinterna. ``tests/test_benchmarks.py``
hält das für jede Route fest.
"""
from __future__ import annotations

import importlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from kern import benchmarks as bm
from kern import usage

from ..antworten import AdminBenchmarkRuns, AdminBenchmarks
from ..deps import require_admin

router = APIRouter(prefix="/api/admin/benchmarks", tags=["admin"])


def resolve_model(ref: str | None) -> str | None:
    """``"modul:ATTRIBUT"`` oder ``"cities:<annotator>"`` → Modell-Id; ``None``, wenn es nicht geht."""
    if not ref:
        return None
    try:
        if ref.startswith("cities:"):
            from council.cities.annotators import get
            return str(get(ref.split(":", 1)[1]).model)
        modul, attribut = ref.split(":", 1)
        return str(getattr(importlib.import_module(modul), attribut))
    except Exception:  # noqa: BLE001 — ein fehlendes Modell heißt „unbekannt", kein 500er
        return None


def current_models() -> dict[str, dict[str, str | None]]:
    return {p.key: {s.key: resolve_model(s.model) for s in p.steps} for p in bm.PIPELINES}


def all_runs() -> list[dict[str, Any]]:
    return bm.load_runs(bm.REPO_RUNS, "repo") + bm.load_runs(bm.SERVER_RUNS, "server")


@router.get("")
def benchmarks_overview(_admin: dict = Depends(require_admin)) -> AdminBenchmarks:
    """Alle Pipelines mit ihren Stufen (Modell heute, Nutzung 30 Tage) und alle
    Benchmarks mit Status und ihren Läufen in Kurzform."""
    return bm.overview(all_runs(), current_models=current_models(),  # type: ignore[return-value]
                       usage=usage.per_feature(30))


@router.get("/{key}")
def benchmark_runs(key: str, _admin: dict = Depends(require_admin)) -> AdminBenchmarkRuns:
    """Die Läufe eines Benchmarks vollständig, neueste zuerst."""
    try:
        b = bm.benchmark(key)
    except KeyError:
        raise HTTPException(404, "Unbekannter Benchmark") from None
    jetzt: dict[str, str | None] = {}
    for p, stufen in current_models().items():
        if p in (b.pipeline, *b.also):
            jetzt.update(stufen)
    runs = [r for r in all_runs() if r.get("benchmark") == key and not r.get("problems")]
    runs.sort(key=lambda r: r["started_at"], reverse=True)
    return {"key": key, "runs": [{**r, "current": bm.is_current(r, b, jetzt)} for r in runs]}
