"""Pflicht und Kür — die Zuordnung und ihr Abgleich mit der Selbstauskunft.

Zwei Dinge auf `/haushalt/pflicht` können still falsch werden, und beide
prüft diese Datei an der echten Funktion aus ``web/frontend/lib``:

1. **Die Zuordnung darf keinen Jahrgangswechsel überleben, ohne ihn zu
   überleben.** Sie war bis 08/2026 auf den exakten Bereichsnamen des
   Haushaltsplans geschlüsselt. Teilhaushalt 9 heißt aber je nach Jahrgang
   „Umwelt, Bauordnung, Grün  u. Friedhöfe", „Klima, Umwelt, Bauordnung, Grün"
   oder „Klima/Umwelt/Mobilität/Bau/Grün/Friedh." — beim nächsten Nachzug wäre
   er aus jeder Summe gefallen, ohne dass irgendwo ein Fehler sichtbar gewesen
   wäre. Getestet wird deshalb JEDE Schreibweise, die das Wörterbuch kennt.

2. **Der Abgleich mit der Stadt darf nicht schönrechnen.** Ein Teilhaushalt
   ohne Produktebene ist keine Übereinstimmung, ein Gleichstand keine
   dominante Stufe, und gewichtet wird nach Aufwand statt nach Kopfzahl — sonst
   wögen drei kleine Beratungsangebote schwerer als 54 Mio. € Rechtsanspruch.

Wie in ``test_flussbild.py`` läuft der Produktionscode selbst: Node führt das
TypeScript seit v22.6 direkt aus, der ``@/``-Alias wird beim Kopieren zu einem
relativen Pfad. Ohne Node überspringen sich die Prüfungen — die CI richtet nur
Python ein.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "web" / "frontend"

_NODE = shutil.which("node")
braucht_node = pytest.mark.skipif(
    _NODE is None, reason="Node fehlt (die CI richtet nur Python ein)")

MODULE = ("haushalt.ts", "haushalt-bereiche.ts", "haushalt-pflicht.ts")

SKRIPT = """
import {
  PFLICHT_NACH_SCHLUESSEL, PFLICHT_ZUORDNUNG, STUFE_ERWARTET,
  abgleich, pflichtFuer, spielraumBefunde,
} from "%(lib)s";
import { BEREICHE } from "%(bereiche)s";

const ein = JSON.parse(process.argv[2]);

const befunde = spielraumBefunde(ein.produkte ?? [], ein.year ?? 2023);
const alsObjekt = {};
for (const [k, b] of befunde) {
  alsObjekt[k] = {
    produkte: b.produkte, expense: b.expense, anteil: b.anteil,
    dominant: b.dominant, groesste: b.groesste ? b.groesste.product_no : null,
  };
}

// Jede Schreibweise jedes Jahrgangs muss dieselbe Einordnung finden.
const ueberAliase = {};
for (const b of BEREICHE) {
  for (const a of b.aliase) {
    ueberAliase[a] = {
      ueberNamen: PFLICHT_ZUORDNUNG[a]?.stufe ?? null,
      ueberFunktion: pflichtFuer(a)?.stufe ?? null,
      erwartet: PFLICHT_NACH_SCHLUESSEL[b.schluessel]?.stufe ?? null,
    };
  }
}

const urteile = {};
for (const [name, stufe] of Object.entries(ein.urteile ?? {})) {
  const schluessel = ein.schluessel[name];
  urteile[name] = abgleich(stufe, befunde.get(schluessel));
}

console.log(JSON.stringify({
  befunde: alsObjekt,
  ueberAliase,
  urteile,
  stufen: Object.fromEntries(
    BEREICHE.map((b) => [b.schluessel, PFLICHT_NACH_SCHLUESSEL[b.schluessel]?.stufe ?? null])),
  erwartet: STUFE_ERWARTET,
  // Groß-/Kleinschreibung und doppelte Leerzeichen fängt die Normalisierung
  // ab — der Rückfall muss trotzdem greifen, nicht raten.
  unbekannt: pflichtFuer("Amt für Raumfahrt") ?? null,
}));
"""


def _lib(tmp_path: Path) -> dict[str, str]:
    ziel = tmp_path / "lib"
    ziel.mkdir(exist_ok=True)
    for name in MODULE:
        quelle = (FRONTEND / "lib" / name).read_text(encoding="utf-8")
        (ziel / name).write_text(
            re.sub(r'from "@/lib/([\w-]+)"', r'from "./\1.ts"', quelle),
            encoding="utf-8")
    return {
        "lib": (ziel / "haushalt-pflicht.ts").as_posix(),
        "bereiche": (ziel / "haushalt-bereiche.ts").as_posix(),
    }


def _lauf(tmp_path: Path, **ein) -> dict:
    skript = tmp_path / "pflicht.mjs"
    skript.write_text(SKRIPT % _lib(tmp_path), encoding="utf-8")
    fertig = subprocess.run(
        [_NODE, "--no-warnings", str(skript), json.dumps(ein)],
        capture_output=True, text=True, timeout=90)
    if fertig.returncode != 0:
        pytest.skip(f"Node kann das TypeScript-Modul nicht laden: {fertig.stderr[:400]}")
    return json.loads(fertig.stdout)


def _p(nr: str, sub_budget: str, expense: float, stufe: str | None, year: int = 2023) -> dict:
    return {"year": year, "product_no": nr, "product_name": nr, "sub_budget_no": None,
            "sub_budget_name": sub_budget, "office": None, "revenues": None,
            "expenses": expense, "result": None,
            "controllability": stufe, "legal_basis": "SGB VIII",
            "source_label": None, "source_url": None}


# --- 1. Die Zuordnung überlebt jeden Jahrgangsnamen -------------------------

@braucht_node
def test_jede_schreibweise_findet_dieselbe_einordnung(tmp_path):
    """DIE Regression: Ein umbenannter Teilhaushalt fällt nicht heraus.

    Wäre die Zuordnung weiter auf den exakten Namen geschlüsselt, lieferten
    die drei alten Schreibweisen von Teilhaushalt 9 hier `null` — der Bereich
    stünde als „nicht eingeordnet" da und fehlte in der Gruppensumme."""
    r = _lauf(tmp_path)
    assert r["ueberAliase"], "Wörterbuch leer — der Test prüft nichts"
    for name, w in r["ueberAliase"].items():
        assert w["erwartet"] is not None, f"{name}: keine Einordnung hinterlegt"
        assert w["ueberNamen"] == w["erwartet"], f"{name}: Namenszugriff weicht ab"
        assert w["ueberFunktion"] == w["erwartet"], f"{name}: pflichtFuer weicht ab"


@braucht_node
def test_alle_dreizehn_teilhaushalte_sind_eingeordnet(tmp_path):
    """Kein Bereich ohne Stufe — sonst schrumpft die Summe unbemerkt."""
    r = _lauf(tmp_path)
    assert len(r["stufen"]) == 13
    assert all(s is not None for s in r["stufen"].values())


@braucht_node
def test_unbekannter_bereich_faellt_zurueck_statt_zu_raten(tmp_path):
    r = _lauf(tmp_path)
    assert r["unbekannt"] is None


# --- 2. Der Abgleich rechnet nicht schön ------------------------------------

@braucht_node
def test_gewichtet_nach_aufwand_nicht_nach_kopfzahl(tmp_path):
    """Drei kleine Angebote mit „viel Spielraum" schlagen keinen
    Rechtsanspruch von 54 Mio. €."""
    r = _lauf(tmp_path, year=2023, produkte=[
        _p("A", "Soziales und Gesundheit", 54_000_000, "niedrig"),
        _p("B", "Soziales und Gesundheit", 300_000, "hoch"),
        _p("C", "Soziales und Gesundheit", 200_000, "hoch"),
        _p("D", "Soziales und Gesundheit", 100_000, "hoch"),
    ])
    b = r["befunde"]["soziales"]
    assert b["produkte"] == 4
    assert b["dominant"] == "niedrig"
    assert b["anteil"]["niedrig"] == pytest.approx(0.9891, abs=1e-3)
    # Der Beleg zeigt auf die teuerste Aufgabe, nicht auf die erste Zeile.
    assert b["groesste"] == "A"


@braucht_node
def test_alte_schreibweise_landet_im_selben_befund(tmp_path):
    """Produktzeilen aus zwei Jahrgängen desselben Teilhaushalts werden
    zusammengeführt — über das Wörterbuch, nicht über den Namen."""
    r = _lauf(tmp_path, year=2023, produkte=[
        _p("A", "Klima/Umwelt/Mobilität/Bau/Grün/Friedh.", 1_000_000, "niedrig"),
        _p("B", "Umwelt, Bauordnung, Grün  u. Friedhöfe", 3_000_000, "mittel"),
    ])
    assert list(r["befunde"]) == ["umwelt"]
    assert r["befunde"]["umwelt"]["produkte"] == 2
    assert r["befunde"]["umwelt"]["dominant"] == "mittel"


@braucht_node
def test_gleichstand_hat_keine_dominante_stufe(tmp_path):
    r = _lauf(tmp_path, year=2023, produkte=[
        _p("A", "Stadtplanung", 1_000_000, "niedrig"),
        _p("B", "Stadtplanung", 1_000_000, "hoch"),
    ])
    assert r["befunde"]["stadtplanung"]["dominant"] is None


@braucht_node
def test_ohne_angabe_wird_ausgewiesen_nicht_verteilt(tmp_path):
    """Fehlende Selbstauskunft ist ein eigener Anteil. Trägt sie die Mehrheit
    des Geldes, gibt es keine dominante Stufe — die Stadt hat dann nichts
    gesagt, und wir erfinden es nicht."""
    r = _lauf(tmp_path, year=2023, produkte=[
        _p("A", "Verkehr und Straßenbau", 6_000_000, None),
        _p("B", "Verkehr und Straßenbau", 4_000_000, "mittel"),
    ])
    b = r["befunde"]["verkehr"]
    assert b["anteil"]["ohne"] == pytest.approx(0.6)
    assert b["dominant"] is None


@braucht_node
def test_fremdes_jahr_zaehlt_nicht_mit(tmp_path):
    r = _lauf(tmp_path, year=2023, produkte=[
        _p("A", "Kultur, Museen, Sport", 1_000_000, "hoch", year=2023),
        _p("B", "Kultur, Museen, Sport", 9_000_000, "niedrig", year=2022),
    ])
    assert r["befunde"]["kultur"]["produkte"] == 1
    assert r["befunde"]["kultur"]["dominant"] == "hoch"


@braucht_node
def test_ohne_produktebene_ist_offen_keine_uebereinstimmung(tmp_path):
    """Der Nenner der Aussage „X von Y Bereichen decken sich" darf nur
    Bereiche enthalten, für die es überhaupt eine Angabe gibt."""
    r = _lauf(
        tmp_path, year=2023,
        produkte=[_p("A", "Kultur, Museen, Sport", 1_000_000, "hoch")],
        schluessel={"Kultur, Museen, Sport": "kultur", "Schule und Bildung": "schule"},
        urteile={"Kultur, Museen, Sport": "freiwillig", "Schule und Bildung": "spielraum"},
    )
    assert r["urteile"]["Kultur, Museen, Sport"] == "deckt"
    assert r["urteile"]["Schule und Bildung"] == "offen"


@braucht_node
def test_abweichung_wird_gemeldet_nicht_geglaettet(tmp_path):
    """„Jugend und Familie" ist der echte Fall: redaktionell „Pflicht mit
    Spielraum", die Stadt sieht für den Großteil des Geldes kaum welchen."""
    r = _lauf(
        tmp_path, year=2023,
        produkte=[
            _p("A", "Jugend und Familie", 71_100_000, "niedrig"),
            _p("B", "Jugend und Familie", 6_200_000, "mittel"),
        ],
        schluessel={"Jugend und Familie": "jugend"},
        urteile={"Jugend und Familie": "spielraum"},
    )
    assert r["stufen"]["jugend"] == "spielraum"
    assert r["befunde"]["jugend"]["dominant"] == "niedrig"
    assert r["urteile"]["Jugend und Familie"] == "weicht"


@braucht_node
def test_erwartungsabbildung_ist_offengelegt(tmp_path):
    r = _lauf(tmp_path)
    assert r["erwartet"] == {
        "pflicht": "niedrig", "spielraum": "mittel", "freiwillig": "hoch"}
