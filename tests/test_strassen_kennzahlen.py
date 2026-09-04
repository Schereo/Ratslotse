"""Die Straßen-Kennzahlen müssen in ``job_runs`` ankommen.

**Der Fall.** ``geocode_decision_locations.process`` rechnet seit 09/2026
``overpass_fehler``, ``overpass_nicht_erreichbar`` und
``strassen_ohne_vollgeometrie`` aus und schreibt im eigenen Quelltext, das
gehöre „in die Kennzahlen, nicht ins Log". Nur nahm ``check_protocols`` sie
nie entgegen: Sein Rückgabe-dict trug allein die eigenen Anzeige-Namen, und
``geostats`` steuerte genau einen Schlüssel bei. Am 04.09.2026 auf Prod
nachgesehen — in keinem einzigen ``job_runs``-Eintrag stand je eine davon.

Die Folge war nicht nur eine fehlende Zahl. Weil der Ausfall nirgends
sichtbar war, musste er als **Mail** auffallen; und weil eine Mail an einem
Tag mit zwei neuen Straßen sonst nie käme, war ihre Schwelle so tief gesetzt,
dass ein einzelner 429 der öffentlichen Overpass-Instanz sie auslöste. Eine
unsichtbare Kennzahl erzeugt einen schreckhaften Alarm.
"""
from __future__ import annotations

import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

#: Was der Straßen-Weg misst — und was folglich in ``job_runs`` landen muss.
#: Die Liste wird in BEIDE Richtungen geprüft: Fehlt hier etwas, das
#: ``process`` liefert, meldet der zweite Test es.
STRASSEN_KENNZAHLEN = {
    "overpass_fehler",
    "overpass_nicht_erreichbar",
    # Trennt „der Dienst hat versagt" von „OSM führt diesen Namen nicht" —
    # der Unterschied zwischen einem Vorfall und den 286 Namen wie
    # „91er-Straße", die dauerhaft übrig bleiben.
    "overpass_ohne_treffer",
    "strassen_ohne_vollgeometrie",
    "strassen_aus_schnappschuss",
}


def _kennzahlen_eines_leerlaufs(tmp_path) -> dict:
    """``process`` gegen eine leere Datenbank — kein Netz, keine Zeile."""
    from scripts.geocode_decision_locations import process

    return process(tmp_path / "council.sqlite", sleep=0)


def test_process_liefert_die_strassen_kennzahlen(tmp_path):
    """Sie müssen überhaupt entstehen — sonst kann sie niemand weiterreichen."""
    stats = _kennzahlen_eines_leerlaufs(tmp_path)
    fehlend = STRASSEN_KENNZAHLEN - set(stats)
    assert not fehlend, (
        f"{sorted(fehlend)} fehlen im Rückgabewert von "
        f"geocode_decision_locations.process — dort ergänzen.")


def test_keine_kennzahl_bleibt_liegen(tmp_path):
    """Die Ausnahmeliste darf nicht schrumpfen, ohne dass es auffällt.

    Kommt in ``process`` eine Straßen-Kennzahl dazu, gehört sie hierher UND
    nach ``check_protocols`` — sonst wiederholt sich der stille Verlust.
    """
    stats = _kennzahlen_eines_leerlaufs(tmp_path)
    kandidaten = {k for k in stats
                  if k.startswith("overpass_") or k.startswith("strassen_")}
    vergessen = kandidaten - STRASSEN_KENNZAHLEN
    assert not vergessen, (
        f"{sorted(vergessen)} misst process(), steht aber in keiner Liste. "
        f"In STRASSEN_KENNZAHLEN aufnehmen und in check_protocols durchreichen.")


def test_check_protocols_reicht_sie_durch():
    """Ausgerechnet lassen und wegwerfen ist schlimmer als gar nicht messen:
    Der Quelltext behauptet dann eine Beobachtbarkeit, die es nicht gibt."""
    quelle = (WURZEL / "scripts" / "check_protocols.py").read_text(encoding="utf-8")
    fehlend = [k for k in sorted(STRASSEN_KENNZAHLEN) if k not in quelle]
    assert not fehlend, (
        f"check_protocols.main() gibt {fehlend} nicht zurück — damit stehen sie "
        f"in keinem job_runs-Eintrag und das Admin-Panel zeigt sie nie. "
        f"Ins Rückgabe-dict aufnehmen (scripts/check_protocols.py).")
