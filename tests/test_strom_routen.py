"""Ereignisströme, die über einen Next-Route-Handler laufen, dürfen nicht puffern.

Next 14 behandelte ein ``fetch`` mit GET in einem Route-Handler als
zwischenspeicherbar und las die Antwort dann ganz ein, bevor es sie
weitergab. Für JSON ist das egal, für einen Ereignisstrom heißt es: alles auf
einmal am Ende. Genau so stand die Fortschrittskarte der gründlichen Recherche
bis zum 09.11.2026 die ganze Recherche über auf dem ersten Schritt — dev und
Prod, unbemerkt, weil der Bericht am Ende ja kam.

Seit Next 15 speichert ``fetch`` nicht mehr von selbst zwischen, und unter
16.4.6 kam der Strom im Versuch auch ohne die Zeile einzeln an. Der Test hält
sie trotzdem fest: Die Vorgabe hat sich schon einmal geändert, und der Fehler
zeigt sich in keiner Prüfung, nur beim Zusehen.
"""
import re
from pathlib import Path

ROUTEN = Path(__file__).resolve().parent.parent / "web" / "frontend" / "app" / "api"


def _strom_routen() -> list[Path]:
    return [p for p in ROUTEN.rglob("route.ts") if "text/event-stream" in p.read_text()]


def test_es_gibt_strom_routen():
    """Sonst prüfte der Test unten nichts — etwa nach einem Umzug der Routen."""
    assert len(_strom_routen()) >= 2


def test_strom_routen_mit_get_puffern_nicht():
    fehlt = [
        str(p.relative_to(ROUTEN))
        for p in _strom_routen()
        if re.search(r"export async function GET\b", p.read_text())
        and 'export const fetchCache = "force-no-store"' not in p.read_text()
    ]
    assert not fehlt, f"GET-Strom ohne fetchCache = \"force-no-store\": {fehlt}"
