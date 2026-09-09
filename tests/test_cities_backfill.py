"""Der Wächter vor der Stufe `fit` — der teuerste Fehler dieses Projekts.

Am 09.09.2026 lief `fit` über 9.688 Vorlagen, während 21.700 fremde Vorlagen
keinen Vektor hatten. Zwei der fünf Beleg-Arme waren leer, das Modell
urteilte „fehlt", weil ihm nichts vorlag: 72 Minuten, $15,40, unbrauchbar —
ohne Absturz, ohne roten Test, ohne auffällige Kennzahl.

Der Wochen-Cron ruft die Stufen in fester Reihenfolge und war nie betroffen.
Wer `--stage` von Hand benutzt, hatte bis dahin keine Sicherung.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "scripts"))

import cities_backfill  # noqa: E402

from council.cities.index import EMBED_MODEL  # noqa: E402
from council.cities.model import Batch, Body, Paper  # noqa: E402
from council.cities.store import CitiesStore  # noqa: E402


@pytest.fixture()
def cities(tmp_path):
    s = CitiesStore(tmp_path / "cities.sqlite")
    s.upsert_body(Body("osnabrueck", "Osnabrück", "NI", "allris4"))
    s.upsert_batch(Batch(papers=[
        Paper("oldenburg:paper:1", "oldenburg", "Wärmeplanung", date="2025-11-20"),
        Paper("os:p:1", "osnabrueck", "Wärmenetz ausbauen", date="2026-05-01",
              kind="proposal"),
    ]))
    s.put_annotation("paper", "os:p:1", "classify", "2",
                     {"field": "klima_umwelt", "transfer": "adaptable",
                      "competence": "council", "instrument": "Wärmenetz ausbauen",
                      "summary": "."}, "h1")
    yield s
    s.close()


def _vektor(store, kind: str, kennung: str) -> None:
    import numpy as np
    v = np.array([1.0, 0.0, 0.0, 0.0], dtype="float32")
    store.put_object_embedding(kind, kennung, EMBED_MODEL, "h:" + kennung, v.tobytes())


def test_fehlende_papier_vektoren_halten_fit_an(cities):
    """Ohne Papier-Vektor gibt es keinen Nachbar-Arm."""
    befunde = cities_backfill.unterbau_pruefen(cities)
    assert any("ohne Vektor" in b for b in befunde)
    assert any("--stage index" in b for b in befunde), (
        "der Befund muss den Befehl nennen, der ihn behebt")


def test_fehlende_ideen_vektoren_halten_fit_an(cities):
    """Papier-Vektoren allein reichen nicht — ohne Ideen-Vektor keine Gruppe."""
    for p in ("oldenburg:paper:1", "os:p:1"):
        _vektor(cities, "paper", p)
    befunde = cities_backfill.unterbau_pruefen(cities)
    assert len(befunde) == 1 and "Ideen-Vektor" in befunde[0]
    assert "--stage cluster" in befunde[0]


def test_vollstaendiger_unterbau_meldet_nichts(cities):
    """Die Gegenrichtung: Ein Wächter, der immer anschlägt, ist keiner."""
    for p in ("oldenburg:paper:1", "os:p:1"):
        _vektor(cities, "paper", p)
    _vektor(cities, "idea", "os:p:1")
    assert cities_backfill.unterbau_pruefen(cities) == []
