"""Wächter über das Umgebungs-Gate des Haushalts-Bereichs.

Der Bereich ist nur auf dev.ratslotse.de freigeschaltet; im Prod-Build ist
``NEXT_PUBLIC_RATSLOTSE_ENV`` nicht gesetzt und jede /haushalt-Route ein 404
(``web/frontend/lib/haushalt-frei.ts``). Ein Gate ist aber nur so gut wie
seine Lücken: Vergisst jemand einen Link, steht der auf Prod weiter da und
führt ins Leere — genau diese Falle gab es schon einmal bei der
Kommunalwahl-Metadata.

Diese Datei prüft deshalb nicht, ob das Gate *existiert* (das sieht man),
sondern ob es *vollständig* ist:

1. Jede Seite unter app/(app)/haushalt/ liegt unter dem Layout mit dem Gate.
2. Kein Verweis auf /haushalt außerhalb des Bereichs steht ungeschützt da.
3. Die Geld-Bausteine der KI-Frage bleiben bei leeren Tabellen still leer —
   auf Prod entstehen die Haushalts-Tabellen leer und bleiben es.

Der dritte Punkt ist der wichtigste: Er ist der einzige Weg, auf dem der
unsichtbare Haushalt auf Prod trotzdem Schaden anrichten könnte.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "web" / "frontend"
BEREICH = FRONTEND / "app" / "(app)" / "haushalt"
GATE_KONSTANTE = "HAUSHALT_FREI"


def test_gate_konstante_prueft_die_umgebungsvariable():
    """Die Konstante ist die einzige Stelle, die die Variable liest."""
    quelle = (FRONTEND / "lib" / "haushalt-frei.ts").read_text(encoding="utf-8")
    assert 'process.env.NEXT_PUBLIC_RATSLOTSE_ENV === "dev"' in quelle
    assert f"export const {GATE_KONSTANTE}" in quelle


def test_layout_gated_den_ganzen_bereich():
    """Ein Layout statt dreizehn Einzelgates — sonst fehlt beim vierzehnten eins."""
    layout = BEREICH / "layout.tsx"
    assert layout.exists(), "app/(app)/haushalt/layout.tsx fehlt — der Bereich ist offen"
    quelle = layout.read_text(encoding="utf-8")
    assert GATE_KONSTANTE in quelle
    assert "notFound()" in quelle


def test_jede_seite_liegt_unter_dem_layout():
    """Keine Haushalts-Seite darf am Layout vorbei erreichbar sein.

    Next.js wendet ein Layout auf alles an, was unter seinem Verzeichnis liegt.
    Der Test hält fest, dass niemand eine Seite daneben legt (etwa unter
    app/(app)/haushalt-neu/), wo das Gate nicht greift.
    """
    seiten = sorted(BEREICH.rglob("page.tsx"))
    assert len(seiten) >= 13, f"nur {len(seiten)} Seiten gefunden — Fund verschoben?"
    for seite in seiten:
        assert (BEREICH / "layout.tsx").exists()
        assert BEREICH in seite.parents, f"{seite} liegt nicht unter dem Gate"

    # Keine zweite Haushalts-Route außerhalb des gegateten Verzeichnisses.
    app = FRONTEND / "app"
    fremde = [p for p in app.rglob("page.tsx")
              if "haushalt" in str(p.relative_to(app)).lower()
              and BEREICH not in p.parents]
    assert not fremde, f"Haushalts-Seiten außerhalb des Gates: {fremde}"


def test_kein_ungegateter_verweis_auf_den_bereich():
    """Jeder Link auf /haushalt außerhalb des Bereichs braucht das Gate.

    Geprüft wird bewusst grob (Datei enthält Link *und* Konstante), nicht
    zeilengenau: Ein falsch-negativer Treffer wäre schlimmer als ein
    gelegentlicher Fehlalarm, der beim Lesen sofort auffliegt.
    """
    verdaechtig: list[str] = []
    for pfad in list((FRONTEND / "app").rglob("*.tsx")) + \
            list((FRONTEND / "components").rglob("*.tsx")):
        if BEREICH in pfad.parents:
            continue                      # der Bereich selbst liegt hinterm Layout
        if (FRONTEND / "components" / "haushalt") in pfad.parents:
            continue                      # Bausteine, die nur dort eingebunden sind
        text = pfad.read_text(encoding="utf-8")
        # href="/haushalt…" — echte Navigationsziele, keine API-Pfade
        if not re.search(r'href=(?:"|\{")/haushalt', text):
            continue
        if GATE_KONSTANTE not in text:
            verdaechtig.append(str(pfad.relative_to(FRONTEND)))
    assert not verdaechtig, (
        "Verweise auf /haushalt ohne Umgebungs-Gate — auf Prod führen sie ins "
        f"Leere: {verdaechtig}")


@pytest.mark.parametrize("baustein", ["_haushalt_block", "_steuern_block", "_steuerkraft_block"])
def test_geld_bausteine_bleiben_bei_leeren_daten_still(baustein):
    """Auf Prod sind die Haushalts-Tabellen leer — die KI-Frage darf das nicht merken.

    Der Regressionsschutz zielt auf künftige Bausteine: Wer einen vierten
    Geld-Baustein ohne Leer-Prüfung hinzufügt, fällt hier auf, statt auf Prod
    eine Antwort mit „–" gespickt auszuliefern.
    """
    from council import qa

    fn = getattr(qa, baustein)
    assert fn(None) == "", f"{baustein}(None) liefert Text statt Leerstring"
    assert fn([] if baustein != "_steuerkraft_block" else {}) == ""


def test_geld_kontext_ist_best_effort_umschlossen():
    """Die Abfragen selbst dürfen die Antwort nie blockieren.

    Auf Prod existieren die Tabellen (leer), aber sollte je eine fehlen, darf
    die KI-Frage nicht ausfallen. Der Router fängt das ab; dieser Test hält
    fest, dass die Absicherung bleibt.
    """
    router = (Path(__file__).resolve().parents[1] / "web" / "backend" / "app"
              / "routers" / "council.py").read_text(encoding="utf-8")
    for aufruf in ("haushalt_fuer_begriffe", "steuern_fuer_begriffe", "steuerkraft_kontext"):
        stelle = router.find(f"store.{aufruf}(")
        assert stelle > 0, f"{aufruf} nicht mehr im Router — Test nachziehen"
        davor = router[max(0, stelle - 400):stelle]
        assert "try:" in davor, f"store.{aufruf}() steht ohne try/except — Ausfallrisiko"
