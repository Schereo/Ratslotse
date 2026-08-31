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
    source = (FRONTEND / "lib" / "haushalt-frei.ts").read_text(encoding="utf-8")
    assert 'process.env.NEXT_PUBLIC_RATSLOTSE_ENV === "dev"' in source
    assert f"export const {GATE_KONSTANTE}" in source


def test_layout_gated_den_ganzen_bereich():
    """Ein Layout statt dreizehn Einzelgates — sonst fehlt beim vierzehnten eins."""
    layout = BEREICH / "layout.tsx"
    assert layout.exists(), "app/(app)/haushalt/layout.tsx fehlt — der Bereich ist offen"
    source = layout.read_text(encoding="utf-8")
    assert GATE_KONSTANTE in source
    assert "notFound()" in source


def test_jede_seite_liegt_unter_dem_layout():
    """Keine Haushalts-Seite darf am Layout vorbei erreichbar sein.

    Next.js wendet ein Layout auf alles an, was unter seinem Verzeichnis liegt.
    Der Test hält fest, dass niemand eine Seite daneben legt (etwa unter
    app/(app)/haushalt-neu/), wo das Gate nicht greift.
    """
    seiten = sorted(BEREICH.rglob("page.tsx"))
    assert len(seiten) >= 13, f"nur {len(seiten)} Seiten gefunden — Fund verschoben?"
    for page in seiten:
        assert (BEREICH / "layout.tsx").exists()
        assert BEREICH in page.parents, f"{page} liegt nicht unter dem Gate"

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


def _alle_bausteine():
    """Jede Kontext-Bausteinfunktion in qa.py, aus dem Quelltext gelesen.

    Bewusst nicht als Liste von Namen: Die erste Fassung zählte drei Bausteine
    auf und versprach im selben Atemzug, „den vierten" zu fangen. Als sie
    geschrieben wurde, gab es fünf; inzwischen sind es sechzehn, und keiner der
    dreizehn neuen war je geprüft. Wer eine Prüfung an eine Aufzählung bindet,
    prüft ab dem nächsten Commit die Vergangenheit.
    """
    from council import qa

    source = Path(qa.__file__).read_text(encoding="utf-8")
    gefunden = set(re.findall(r"^def (_\w+_block)\(", source, re.M))
    return sorted(gefunden - AUSNAHMEN)


#: Bausteine, die ohne Daten absichtlich Text liefern — geprüft, nicht geraten.
#:
#: ``_bisher_block`` ist der einzige: Er reicht keine Daten durch, sondern eine
#: Anweisung ans Modell. Liegt keine frühere Antwort vor (ältere App-Versionen
#: schicken das Feld nicht mit), sagt er das ausdrücklich — sonst hantierte das
#: Modell mit einem leeren Zitat-Block. Wer hier etwas einträgt, muss denselben
#: Nachweis führen: Der Text ist Anweisung, nicht Inhalt.
AUSNAHMEN = {"_bisher_block"}


def test_die_bausteinliste_ist_nicht_leer():
    """Sicherung gegen den stillen Ausfall: Findet der Regex nichts, liefe die
    Prüfung darunter über eine leere Liste und wäre grün, ohne etwas zu tun."""
    assert len(_alle_bausteine()) >= 10


@pytest.mark.parametrize("baustein", _alle_bausteine())
def test_bausteine_bleiben_bei_leeren_daten_still(baustein):
    """Ohne Daten kein Text — für jeden Baustein, nicht nur die Geld-Bausteine.

    Auf Prod sind die Haushalts-Tabellen leer (Umgebungs-Gate), und auch sonst
    kann jede Quelle einmal nichts liefern. Ein Baustein, der daraus eine
    Überschrift ohne Inhalt oder eine Zeile aus „–" macht, verschlechtert die
    Antwort, statt sie zu ergänzen.
    """
    from council import qa

    fn = getattr(qa, baustein)
    assert fn(None) == "", f"{baustein}(None) liefert Text statt Leerstring"


def test_jede_geld_quelle_wird_abgesichert_abgefragt():
    """Die Abfragen selbst dürfen die Antwort nie blockieren.

    Auf Prod existieren die Haushalts-Tabellen (leer), aber sollte je eine
    fehlen, darf die KI-Frage nicht ausfallen.

    Die erste Fassung dieses Tests suchte die Aufrufe im Router und ihr
    ``try:`` davor. Das war zu eng an einer Struktur festgemacht: #543 hat sie
    nach ``qa.geld_kontext`` gebündelt, wo jede Quelle in ``_sicher(...)``
    steht — die Absicherung blieb, der Test fiel trotzdem. Er prüft jetzt die
    Eigenschaft statt den Ort.
    """
    from council import qa

    source = (Path(__file__).resolve().parents[1] / "council" / "qa.py").read_text(encoding="utf-8")
    körper = source[source.index("def geld_kontext("):]
    körper = körper[:körper.index("\ndef ", 1)]

    ungeschützt = [
        row.strip()
        for row in körper.splitlines()
        if "store." in row and "_sicher(" not in row and not row.strip().startswith("#")
    ]
    assert not ungeschützt, (
        "Store-Abfrage in geld_kontext() ohne _sicher() — bei fehlender Tabelle "
        f"fällt die ganze Antwort aus: {ungeschützt}")

    # Und der Wrapper tut, was sein Name sagt.
    assert qa._sicher(lambda: 1 / 0, standard=[]) == []
