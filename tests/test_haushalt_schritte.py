"""Wächter über die Schritt-Nummern des Haushalts-Bereichs.

Der Wegweiser (``components/haushalt/wegweiser.tsx``) rechnet die Nummern
durch: Er zählt die Ziele seiner vier Stufen von oben nach unten. Vier Seiten
schreiben ihre Nummer aber **selbst** in ihren Kicker („Stadtfinanzen
Oldenburg · Schritt 9"), weil sie dort oben steht, wo keine Komponente sie
einsetzt.

Damit gibt es zwei Wahrheiten für dieselbe Zahl — und sobald eine Seite
dazukommt, gehen sie auseinander. Das ist am 16.08.2026 **viermal** passiert:
Mit „Was wird gebaut?", dem Stellenplan, den Beteiligungen und den Schulden
rutschte jedes Mal alles Nachfolgende um eins, und jedes Mal blieb mindestens
ein Kicker oder ein Kommentar auf dem alten Stand stehen. Einmal standen
sogar zwei Kommentare nebeneinander, die sich gegenseitig widersprachen
(„konzern steht auf Schritt 8" gegen „konzern behält Schritt 7").

Auffallen kann das niemandem: Der Wegweiser zeigt die richtige Nummer, die
Seite die falsche, und beide sehen für sich stimmig aus. Genau dafür ist
dieser Test da.

Warum in Python: Das Repo hat keinen JS-Testlauf, die CI richtet nur Python
ein (``.github/workflows/test.yml``). Gelesen wird deshalb der Quelltext —
dieselbe Machart wie ``tests/test_haushalt_gate.py``.
"""
from __future__ import annotations

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "web" / "frontend"
BEREICH = FRONTEND / "app" / "(app)" / "haushalt"
WEGWEISER = FRONTEND / "components" / "haushalt" / "wegweiser.tsx"
#: Die Technik-Doku führt dieselbe Reihenfolge als Tabelle — die **dritte**
#: Wahrheit für dieselbe Zahl, und die einzige außerhalb des Codes.
DOKU = (Path(__file__).resolve().parents[1]
        / "docs-site" / "src" / "content" / "docs" / "haushalt.md")

#: Der Kicker, den die Seiten schreiben: „Stadtfinanzen Oldenburg · Schritt 9".
#: Bewusst eng: Ein Kommentar, der beiläufig „Schritt 1" erwähnt (etwa über
#: das Verwaltungsverfahren in ``jahr/page.tsx``), ist keine Wegweiser-Nummer
#: und darf hier nicht mitgezählt werden.
KICKER = re.compile(r"Stadtfinanzen Oldenburg\s*·\s*Schritt (\d+)")

#: Eine Zeile der Routen-Tabelle in der Doku::
#:
#:     | `/haushalt/konzern` | Schritt 11 — Kernverwaltung gegen …
#:
#: Der Query-Parameter-Anhang mancher Routen (``[?jahr=<jahr>]``) gehört zur
#: Schreibweise der Tabelle und nicht zum Seitennamen.
DOKU_ZEILE = re.compile(
    r"^\|\s*`/haushalt/([a-z-]+)(?:\[[^\]]*\])?`\s*\|\s*Schritt (\d+)", re.MULTILINE)


def wegweiser_reihenfolge() -> list[str]:
    """Die Ziele des Wegweisers in der Reihenfolge, in der er sie nummeriert.

    Gelesen wird nur der ``STUFEN``-Block: Weiter unten stehen Links, die
    keine Schritte sind (etwa die beiden Steckbriefe am Fuß).
    """
    quelle = WEGWEISER.read_text(encoding="utf-8")
    anfang = quelle.index("const STUFEN:")
    ende = quelle.index("STUFEN_NUMMERIERT")
    return re.findall(r'href: "/haushalt/([a-z-]+)"', quelle[anfang:ende])


def test_der_wegweiser_ist_lesbar():
    """Sicherung gegen den stillen Ausfall: Findet der Regex nichts, liefe die
    Prüfung darunter über eine leere Liste und wäre grün, ohne zu prüfen."""
    reihenfolge = wegweiser_reihenfolge()
    assert len(reihenfolge) >= 10, f"nur {len(reihenfolge)} Ziele gefunden — Aufbau geändert?"
    assert len(set(reihenfolge)) == len(reihenfolge), "ein Ziel steht zweimal im Wegweiser"


def test_selbstgeschriebene_nummern_stimmen_mit_dem_wegweiser():
    """Jeder Kicker nennt die Nummer, die der Wegweiser für seine Seite rechnet."""
    reihenfolge = wegweiser_reihenfolge()
    nummer_von = {name: i for i, name in enumerate(reihenfolge, start=1)}

    gefunden, abweichungen = 0, []
    for seite in sorted(BEREICH.rglob("page.tsx")):
        treffer = KICKER.search(seite.read_text(encoding="utf-8"))
        if not treffer:
            continue
        gefunden += 1
        name = seite.parent.name
        geschrieben = int(treffer.group(1))
        gerechnet = nummer_von.get(name)
        if gerechnet is None:
            abweichungen.append(
                f"{name}: schreibt „Schritt {geschrieben}“, steht aber gar nicht im Wegweiser")
        elif geschrieben != gerechnet:
            abweichungen.append(
                f"{name}: schreibt „Schritt {geschrieben}“, der Wegweiser rechnet {gerechnet}")

    assert gefunden >= 3, (
        f"nur {gefunden} Seiten mit Kicker gefunden — schreibt niemand mehr seine "
        "Nummer selbst, kann dieser Test weg")
    assert not abweichungen, (
        "Selbstgeschriebene Schritt-Nummern weichen vom Wegweiser ab. Wer eine "
        "Seite einfügt, verschiebt alles danach:\n  " + "\n  ".join(abweichungen))


def test_jedes_wegweiser_ziel_existiert():
    """Kein Schritt zeigt auf eine Seite, die es nicht gibt.

    Ein toter Schritt wäre schlimmer als eine falsche Nummer: Er verschiebt
    alle folgenden Nummern *und* führt ins Leere.
    """
    fehlend = [name for name in wegweiser_reihenfolge()
               if not (BEREICH / name / "page.tsx").exists()]
    assert not fehlend, f"Wegweiser verweist auf Seiten, die es nicht gibt: {fehlend}"


def test_die_doku_tabelle_nennt_dieselbe_reihenfolge():
    """Die Routen-Tabelle der Technik-Doku stimmt mit dem Wegweiser überein.

    Bis 19.08.2026 prüfte dieser Wächter nur Code gegen Code — und genau
    deshalb driftete die **Doku** unbemerkt ab: „Die dreizehn Zahlen" (#627)
    kam mitten in die zweite Stufe, der Code zog alle folgenden Nummern nach
    (dieser Test war grün), und die Tabelle blieb auf dem alten Stand stehen.
    Sieben Zeilen nannten danach eine Nummer zu wenig, und die Seite fehlte
    ganz. Wer die Doku liest, liest sie statt des Codes; eine falsche Nummer
    dort ist deshalb genauso teuer wie eine im Kicker.
    """
    reihenfolge = wegweiser_reihenfolge()
    nummer_von = {name: i for i, name in enumerate(reihenfolge, start=1)}
    tabelle = DOKU_ZEILE.findall(DOKU.read_text(encoding="utf-8"))

    # Sicherung gegen den stillen Ausfall — dieselbe Sorge wie oben: Findet
    # der Regex nichts (Tabelle umformatiert), liefe alles Weitere leer durch.
    assert len(tabelle) >= 10, (
        f"nur {len(tabelle)} Tabellenzeilen gefunden — Aufbau der Doku geändert?")

    abweichungen = [
        f"{name}: Doku sagt „Schritt {nr}“, der Wegweiser rechnet "
        f"{nummer_von.get(name, '— steht gar nicht im Wegweiser')}"
        for name, nr in ((n, int(s)) for n, s in tabelle)
        if nummer_von.get(name) != nr
    ]
    fehlend = [name for name in reihenfolge
               if name not in {n for n, _ in tabelle}]
    if fehlend:
        abweichungen.append(
            "in der Doku-Tabelle fehlen ganz: " + ", ".join(fehlend))

    assert not abweichungen, (
        "Die Routen-Tabelle in docs-site/src/content/docs/haushalt.md weicht "
        "vom Wegweiser ab:\n  " + "\n  ".join(abweichungen))
