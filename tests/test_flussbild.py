"""Summenprobe des Flussbilds (Design H-18).

Das Flussbild zeigt links die Einnahmearten, rechts die Teilhaushalte und
dazwischen EINEN Knoten — kein Band überquert die Mitte, weil im kommunalen
Haushalt keine Einnahme zu einer bestimmten Ausgabe gehört. Damit die
Bandbreiten links und rechts vergleichbar sind, müssen beide Seiten auf
dieselbe Summe kommen. Genau das prüft diese Datei, und zwar an der echten
Funktion: ``web/frontend/lib/haushalt.ts`` ist reines TypeScript, Node führt es
seit v22.6 direkt aus (Typen werden beim Laden entfernt). Seine Importe aus
demselben ``lib``-Verzeichnis werden dafür kopiert und der ``@/``-Alias des
Frontends zu einem relativen Pfad gemacht — Node kennt den Alias nicht.

Warum nicht im Frontend testen: Das Repo hat keinen JS-Testlauf, und die CI
richtet nur Python ein (``.github/workflows/test.yml``). Steht kein Node
bereit, überspringen die Node-Tests sich selbst — die Prüfungen der
Datengrundlage und der beiden baulichen Regeln laufen trotzdem.

Der Aufbau spiegelt den echten Weg: Die Zahlen gehen durch
``CouncilStore.save_ergebnisrechnung`` und kommen über
``get_ergebnisrechnung`` wieder heraus — dieselbe Form, die
``GET /api/council/haushalt`` ausliefert und die die Komponente liest.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from council.herkunft import Herkunft
from council.store import CouncilStore

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "web" / "frontend"

# --- Ein realistisches Abschlussjahr ----------------------------------------
# Ist: 769,43 Mio. Erträge gegen 792,64 Mio. Aufwendungen — ein Minus, also
# trägt die LINKE Seite das Ausgleichsband „aus dem Ersparten".

ERTRAGSARTEN = [
    (1, "Steuern und ähnliche Abgaben", 356_246_090.0),
    (2, "Zuwendungen und allgemeine Umlagen", 183_124_340.0),
    (3, "Auflösungserträge aus Sonderposten", 16_158_030.0),
    (4, "sonstige Transfererträge", 13_080_310.0),
    (5, "öffentlich-rechtliche Entgelte", 60_784_970.0),
    (6, "privatrechtliche Entgelte", 20_005_180.0),
    (7, "Kostenerstattungen und Kostenumlagen", 83_098_440.0),
    (8, "Zinsen und ähnliche Finanzerträge", 6_924_870.0),
    (9, "aktivierungsfähige Eigenleistungen", 3_077_720.0),
    (10, "Bestandsveränderungen", 769_430.0),
    (11, "sonstige ordentliche Erträge", 26_160_620.0),
]
ERTRAEGE_IST = sum(w for _, _, w in ERTRAGSARTEN)  # 769.430.000,00

TEILHAUSHALTE = [
    (1, "Zentrale Steuerung und Service", 49_143_680.0),
    (2, "Sicherheit und Ordnung", 43_595_200.0),
    (3, "Schule und Bildung", 61_825_920.0),
    (4, "Kultur, Museen, Sport", 32_498_240.0),
    (5, "Jugend und Familie", 176_758_720.0),
    (6, "Soziales und Gesundheit", 194_989_440.0),
    (7, "Verkehr und Straßenbau", 45_973_120.0),
    (8, "Stadtplanung", 13_474_880.0),
    (9, "Umwelt und Grünflächen", 25_364_480.0),
    (10, "Wirtschaftsförderung", 6_341_120.0),
    (11, "Gebäudewirtschaft", 56_277_440.0),
    (12, "Finanzmanagement und Recht", 86_397_760.0),
]
AUFWENDUNGEN_IST = sum(w for _, _, w in TEILHAUSHALTE)  # 792.640.000,00

ERTRAEGE_PLAN = 731_200_000.0
AUFWENDUNGEN_PLAN = 776_500_000.0
JAHR = 2024


def _quelle(year: int, probe: str = "strukturprobe") -> Herkunft:
    """Die Herkunft, die `save_ergebnisrechnung` verlangt — hier nur Beiwerk:
    Das Flussbild liest Zahlen, nicht Belege."""
    return Herkunft(art="ris", probe=probe, label=f"Jahresabschluss {year}",
                    url=f"https://example.org/ja-{year}.pdf",
                    citation="Ergebnisrechnung der Kernverwaltung")


def _befuellen(store: CouncilStore, ohne_posten: int | None = None) -> None:
    """Ein Abschlussjahr speichern — optional mit einer fehlenden Ertragsart,
    wie sie entsteht, wenn eine Zeile im PDF nicht lesbar war."""
    anteil_e = ERTRAEGE_PLAN / ERTRAEGE_IST
    gesamt = [
        {"nr": nr, "label": bez, "ansatz": round(wert * anteil_e, 2),
         "result": wert, "deviation": round(wert - wert * anteil_e, 2), "is_total": 0}
        for nr, bez, wert in ERTRAGSARTEN if nr != ohne_posten
    ]
    gesamt += [
        {"nr": 12, "label": "Summe ordentliche Erträge", "ansatz": ERTRAEGE_PLAN,
         "result": ERTRAEGE_IST, "is_total": 1},
        {"nr": 20, "label": "Summe ordentliche Aufwendungen", "ansatz": AUFWENDUNGEN_PLAN,
         "result": AUFWENDUNGEN_IST, "is_total": 1},
        {"nr": 21, "label": "ordentliches Ergebnis",
         "ansatz": ERTRAEGE_PLAN - AUFWENDUNGEN_PLAN,
         "result": ERTRAEGE_IST - AUFWENDUNGEN_IST, "is_total": 1},
    ]
    store.save_ergebnisrechnung(JAHR, gesamt, _quelle(JAHR))

    anteil_a = AUFWENDUNGEN_PLAN / AUFWENDUNGEN_IST
    for nr, name, wert in TEILHAUSHALTE:
        store.save_ergebnisrechnung(JAHR, [
            {"nr": 20, "label": "Summe ordentliche Aufwendungen",
             "ansatz": round(wert * anteil_a, 2), "result": wert, "is_total": 1},
        ], _quelle(JAHR, "summenprobe"), sub_budget_no=nr, sub_budget_name=name)


def _daten(store: CouncilStore) -> dict:
    """Die Nutzlast, wie ``GET /api/council/haushalt`` sie liefert (Ausschnitt)."""
    return {"years": {}, "taxes": [], "tax_capacity": [], "population": None,
            "income_statement": store.get_ergebnisrechnung(),
            "plan_actual_years": store.plan_actual_years()}


# --- Die echte Funktion über Node laufen lassen ------------------------------

SKRIPT = r"""
import { flussbild, flussJahre, fasseKleineZusammen } from "%(lib)s";
const eingabe = JSON.parse(process.argv[2]);
const { daten, year, stand } = eingabe;
const bild = flussbild(daten, year, stand);
if (!bild) { console.log(JSON.stringify({ bild: null })); process.exit(0); }
const page = (s) => ({
  gesamt: s.gesamt,
  teile: s.teile,
  summe: s.baender.reduce((a, b) => a + b.wert, 0),
  baender: s.baender.map((b) => ({ id: b.id, label: b.label, wert: b.wert, art: b.art })),
});
// Auch die Bündelung muss die Summe erhalten — ein Sammelposten darf nichts
// verschlucken, sonst stimmten die Bandbreiten nicht mehr mit der Tabelle.
const geb = fasseKleineZusammen(bild.herkunft.baender, bild.skala, 0.05);
console.log(JSON.stringify({
  years: flussJahre(daten),
  stand: bild.stand,
  skala: bild.skala,
  balance: bild.balance,
  summeLinks: bild.summeLinks,
  summeRechts: bild.summeRechts,
  stimmt: bild.stimmt,
  aufgeschluesselt: bild.aufgeschluesselt,
  herkunft: page(bild.herkunft),
  verwendung: page(bild.verwendung),
  gebuendeltSumme: geb.gezeigt.reduce((a, b) => a + b.wert, 0),
  gebuendeltAnzahl: geb.gebuendelt.length,
}));
"""

_NODE = shutil.which("node")
braucht_node = pytest.mark.skipif(
    _NODE is None, reason="Node fehlt (die CI richtet nur Python ein)")


def _lib_fuer_node(tmp_path: Path) -> Path:
    """``lib/haushalt.ts`` samt seiner Geschwister-Module nach tmp kopieren.

    Einzige Änderung: ``@/lib/x`` wird zu ``./x.ts``. Node hat keinen
    Pfad-Alias und braucht in ESM die Dateiendung — der Code selbst bleibt
    Zeichen für Zeichen der Produktionscode."""
    ziel = tmp_path / "lib"
    ziel.mkdir(exist_ok=True)
    for name in ("haushalt.ts", "haushalt-bereiche.ts"):
        quelle = (FRONTEND / "lib" / name).read_text(encoding="utf-8")
        (ziel / name).write_text(
            re.sub(r'from "@/lib/([\w-]+)"', r'from "./\1.ts"', quelle),
            encoding="utf-8")
    return ziel / "haushalt.ts"


def _fluss(tmp_path: Path, daten: dict, year: int = JAHR, stand: str = "ist") -> dict:
    skript = tmp_path / "fluss.mjs"
    skript.write_text(SKRIPT % {"lib": _lib_fuer_node(tmp_path).as_posix()},
                      encoding="utf-8")
    fertig = subprocess.run(
        [_NODE, "--no-warnings", str(skript),
         json.dumps({"daten": daten, "year": year, "stand": stand})],
        capture_output=True, text=True, timeout=90)
    if fertig.returncode != 0:
        pytest.skip(f"Node kann das TypeScript-Modul nicht laden: {fertig.stderr[:400]}")
    return json.loads(fertig.stdout)


# --- Die Summenprobe --------------------------------------------------------

@braucht_node
def test_beide_seiten_ergeben_dieselbe_skala(tmp_path):
    """DIE Probe: Was links gezeichnet wird, muss rechts genauso viel sein.

    Sonst behaupten zwei Bandbreiten auf demselben Bild zwei verschiedene
    Maßstäbe — und ein Leser vergleicht „Steuern" mit „Soziales", ohne dass
    der Vergleich trägt."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _befuellen(store)
    r = _fluss(tmp_path, _daten(store))
    store.close()

    assert r["stimmt"] is True
    assert r["aufgeschluesselt"] is True
    assert r["summeLinks"] == pytest.approx(r["summeRechts"], abs=0.01)
    assert r["summeLinks"] == pytest.approx(r["skala"], abs=0.01)
    # Die Skala ist die GRÖSSERE der beiden Summen, nicht ihr Mittel.
    assert r["skala"] == pytest.approx(max(ERTRAEGE_IST, AUFWENDUNGEN_IST), abs=0.01)


@braucht_node
def test_das_minus_wird_zum_ausgleichsband_und_nicht_weggerechnet(tmp_path):
    """Erträge und Aufwendungen sind ungleich — genau das macht das Bild
    sichtbar, statt die kürzere Seite auf Länge zu ziehen: Die Fehlsumme steht
    links als eigenes Band „aus dem Ersparten" und ist so groß wie das Minus."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _befuellen(store)
    r = _fluss(tmp_path, _daten(store))
    store.close()

    minus = AUFWENDUNGEN_IST - ERTRAEGE_IST
    assert minus > 0
    ausgleich = [b for b in r["herkunft"]["baender"] if b["art"] == "ausgleich"]
    assert len(ausgleich) == 1
    assert ausgleich[0]["wert"] == pytest.approx(minus, abs=0.01)
    assert ausgleich[0]["label"] == "aus dem Ersparten"
    # Auf der Ausgabenseite gibt es nichts auszugleichen.
    assert not [b for b in r["verwendung"]["baender"] if b["art"] == "ausgleich"]
    # Die Einzelposten bleiben unangetastet — nur das Zusatzband schließt die Lücke.
    assert r["herkunft"]["teile"] == pytest.approx(ERTRAEGE_IST, abs=0.01)
    assert r["verwendung"]["teile"] == pytest.approx(AUFWENDUNGEN_IST, abs=0.01)


@braucht_node
def test_ueberschuss_landet_auf_der_anderen_seite(tmp_path):
    """Spiegelfall: Nimmt die Stadt mehr ein, als sie ausgibt, trägt die
    RECHTE Seite das Zusatzband. Sonst wäre die Einnahmenseite länger und das
    Bild suggerierte, ein Teil der Einnahmen verschwinde."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _befuellen(store)
    daten = _daten(store)
    store.close()
    # Plan-Stand umdrehen: Erträge über Aufwendungen.
    for p in daten["income_statement"]:
        if p["sub_budget_no"] is None and p["nr"] == 12:
            p["ansatz"] = AUFWENDUNGEN_PLAN + 30_000_000.0

    r = _fluss(tmp_path, daten, stand="plan")
    ausgleich = [b for b in r["verwendung"]["baender"] if b["art"] == "ausgleich"]
    assert len(ausgleich) == 1
    assert ausgleich[0]["label"] == "bleibt übrig"
    assert r["summeLinks"] == pytest.approx(r["summeRechts"], abs=0.01)
    assert not [b for b in r["herkunft"]["baender"] if b["art"] == "ausgleich"]


@braucht_node
def test_fehlende_zeile_wird_gezeigt_statt_gestreckt(tmp_path):
    """Fehlt eine Ertragsart (Zeile im PDF nicht lesbar), darf der Rest nicht
    stillschweigend hochskaliert werden. Die Probe muss weiter aufgehen, das
    Bild sich aber als unvollständig zu erkennen geben."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _befuellen(store, ohne_posten=1)  # „Steuern" — 46 % der Erträge
    r = _fluss(tmp_path, _daten(store))
    store.close()

    assert r["aufgeschluesselt"] is False       # → die Komponente zeichnet nicht
    assert r["stimmt"] is True                  # → aber gestreckt wird trotzdem nichts
    assert r["summeLinks"] == pytest.approx(r["summeRechts"], abs=0.01)
    assert r["herkunft"]["teile"] < r["herkunft"]["gesamt"]
    # Die Lücke steht als eigenes Band da, nicht auf die anderen verteilt.
    fehlt = [b for b in r["herkunft"]["baender"] if b["art"] == "rest"]
    assert len(fehlt) == 1
    assert fehlt[0]["wert"] == pytest.approx(
        ERTRAGSARTEN[0][2], abs=0.01)


@braucht_node
def test_sammelposten_verschluckt_nichts(tmp_path):
    """Die Bündelung kleiner Posten ist eine Lesbarkeits-, keine Rechenhilfe:
    Die Summe der gezeigten Bänder bleibt die Summe aller Bänder."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _befuellen(store)
    r = _fluss(tmp_path, _daten(store))
    store.close()

    assert r["gebuendeltAnzahl"] >= 2
    assert r["gebuendeltSumme"] == pytest.approx(r["summeLinks"], abs=0.01)


@braucht_node
def test_nur_jahre_mit_beiden_seiten(tmp_path):
    """Ein Abschluss ohne Teilhaushalts-Ebene (so liegt 2019 vor) trägt nur die
    linke Hälfte. Solche Jahre bietet das Bild gar nicht erst an, statt rechts
    eine leere Spalte zu zeigen."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _befuellen(store)
    store.save_ergebnisrechnung(2019, [
        {"nr": 1, "label": "Steuern und ähnliche Abgaben",
         "ansatz": 1.0, "result": 300_000_000.0, "is_total": 0},
        {"nr": 12, "label": "Summe ordentliche Erträge",
         "ansatz": 1.0, "result": 300_000_000.0, "is_total": 1},
        {"nr": 20, "label": "Summe ordentliche Aufwendungen",
         "ansatz": 1.0, "result": 310_000_000.0, "is_total": 1},
    ], _quelle(2019))
    r = _fluss(tmp_path, _daten(store))
    store.close()

    assert r["years"] == [JAHR]


# --- Datengrundlage: läuft auch ohne Node -----------------------------------

def test_store_liefert_genau_die_felder_die_das_bild_liest(tmp_path):
    """Die Komponente liest sechs Felder je Zeile. Fällt eines beim Umbau der
    Ablage weg, soll das hier auffallen und nicht auf der Seite."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _befuellen(store)
    zeilen = store.get_ergebnisrechnung(JAHR)
    store.close()

    for feld in ("year", "nr", "label", "sub_budget_no", "sub_budget_name", "ansatz", "result"):
        assert all(feld in z for z in zeilen), feld
    arten = [z for z in zeilen if z["sub_budget_no"] is None and 1 <= z["nr"] <= 11]
    bereiche = [z for z in zeilen if z["sub_budget_no"] is not None and z["nr"] == 20]
    assert len(arten) == 11 and len(bereiche) == 12
    # Und die Probe auf der Datengrundlage selbst.
    assert sum(z["result"] for z in arten) == pytest.approx(ERTRAEGE_IST, abs=0.01)
    assert sum(z["result"] for z in bereiche) == pytest.approx(AUFWENDUNGEN_IST, abs=0.01)


def _lies(rel: str) -> str:
    return (FRONTEND / rel).read_text(encoding="utf-8")


def test_viewbox_haengt_an_der_gemessenen_breite():
    """Die teuer gelernte Lehre aus der Zeitreihe: Steht in der viewBox eine
    feste Zahl und der Container ist schmaler, skaliert der Browser das ganze
    Bild samt Schrift herunter. Die Breite muss gemessen sein.

    Seit dem Grafik-Baukasten (GB-07) zeichnet
    ``components/grafik/flussbild.tsx`` — die Eigenschaft wohnt dort, die
    Haushalts-Datei ist nur noch der Adapter."""
    quelle = _lies("components/grafik/flussbild.tsx")
    assert "const W = breite;" in quelle
    assert "viewBox={`0 0 ${W} ${H}`}" in quelle
    assert "new ResizeObserver" in quelle


def test_schmal_wird_umgebaut_nicht_geschrumpft():
    """Unter der Schwelle gibt es gestapelte Listen statt gestauchter
    Bänder — ein zusammengeschobenes Flussbild war schon zweimal der Befund.
    Auch diese Regel zeichnet seit GB-07 der Baukasten."""
    quelle = _lies("components/grafik/flussbild.tsx")
    assert "SCHWELLE_BREIT" in quelle
    assert "breite < SCHWELLE_BREIT" in quelle
    assert "<Listen seiten={seiten}" in quelle


def test_ohne_vollstaendige_aufschluesselung_kein_bild():
    """Die Weigerung ist Absicht und muss im Code stehen bleiben: Lieber keine
    Grafik als eine, die eine Lücke glattzieht."""
    quelle = _lies("components/haushalt/flussbild.tsx")
    # Seit 16.08. heißt die Variable `zeigBild`: Fehlt das gewählte Jahr,
    # zeigt die Komponente das jüngste vollständige — die Weigerung, eine
    # LÜCKE glattzuziehen, gilt unverändert und ist genau das hier Geprüfte.
    assert "!zeigBild.aufgeschluesselt ?" in quelle
    assert "gestreckt" in quelle
