"""Oldenburg im Bundesvergleich — drei Kennzahlen je Einwohner*in für
vergleichbare kreisfreie Städte (Plan Haushalt-Blickwinkel, B3).

QUELLE ist der Wegweiser Kommune der Bertelsmann Stiftung (Daten der
Statistischen Ämter, frei nutzbar). Die Seite „Daten" verlinkt je Thema einen
Export als CSV, mehrere Kommunen in einer Datei:
``/data-api/rest/export/<thema>+<kommune>+<kommune>+2019-2023+tabelle.csv``.
Zwei Themen werden gebraucht: „finanzen" für die Kennzahlen,
„demografische-entwicklung" für die Einwohnerzahl, an der die
Vergleichsgruppe hängt.

DIE VERGLEICHSGRUPPE (Entscheidung 4 im Plan): alle kreisfreien Städte mit
100.000 bis 250.000 Einwohner*innen im jüngsten Jahr, dazu alle kreisfreien
Städte Niedersachsens, auch die kleineren und Braunschweig. Die Regel steht
hier im Code, die Liste entsteht bei jedem Lauf aus den Einwohnerzahlen —
eine Stadt, die über die Grenze wächst, wandert von selbst hinein.

DIE KENNZAHLEN, und welche NICHT (gemessen 24.09.2026 an Oldenburgs eigenen
Reihen, Toleranz 3 %):

* **Einkommensteuer** je Einwohner*in — gegen den Einkommensteueranteil aus
  dem Statistischen Jahrbuch: 0,8–1,8 % Abstand.
* **Grundsteuer B** je Einwohner*in — gegen Grundsteuer A+B des Jahrbuchs
  (A ist klein): 0,5–1 %.
* **Liquiditätskredite** je Einwohner*in — Oldenburg führt 2019–2023 keine;
  die Probe ist der Liquiditätsstand zum Jahresende aus den Grafiken der
  Kämmerei: Ist er positiv, muss hier 0 stehen.
* NICHT die **Gewerbesteuer**: Der Wegweiser zählt sie netto nach der
  Kassenstatistik, das Jahrbuch anders; der Abstand wechselt das Vorzeichen
  (2019 +4 %, 2021 −15 %, 2023 +13 %). Welche Abgrenzung der Unterschied ist,
  lässt sich aus den Dokumenten nicht klären — also erscheint der Wert nicht.
* NICHT die **Verschuldung im Kernhaushalt**, obwohl sie die Probe besteht:
  Die Seite /haushalt/vergleich erklärt ausführlich, warum ein Vergleich von
  Kernhaushalten zuerst misst, wie viel eine Stadt ausgelagert hat.

Besteht Oldenburgs Wert in einem Jahr die Probe nicht, fällt die Kennzahl für
dieses Jahr ganz heraus: Ein Streifen ohne geprüften Oldenburger Punkt hat
auf dieser Seite nichts zu suchen.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

SERIES = "wegweiser"
PROBE = "federal_comparison_own_series"
BASIS = "https://www.wegweiser-kommune.de"
DATEN_SEITE = BASIS + "/daten"
REGIONEN_URL = BASIS + "/data-api/rest/region/list?max=20000"
JAHRE = "2019-2023"
OLDENBURG = "oldenburg-oldenburg"
LAND_NI = "03"
EW_VON, EW_BIS = 100_000, 250_000
TOLERANZ = 0.03

#: Kennzahl → Zeilenkopf im Export.
INDIKATOREN = {
    "income_tax": "Einkommensteuer (Euro je Einwohner:in)",
    "property_tax_b": "Grundsteuer B (Euro je Einwohner:in)",
    "liquidity_loans": "Liquiditätskredite (Euro je Einwohner:in)",
}
BEVOELKERUNG = "Bevölkerung (Anzahl)"


def export_url(thema: str, slugs: list[str]) -> str:
    return f"{BASIS}/data-api/rest/export/{thema}+{'+'.join(slugs)}+{JAHRE}+tabelle.csv"


class VergleichFehler(ValueError):
    """Ein Export lässt sich nicht eindeutig lesen."""


def _zahl(roh: str) -> float | None:
    s = (roh or "").strip().replace(".", "").replace(",", ".")
    if not s or s in ("-", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def lies_export(text: str, slugs: list[str], namen: dict[str, str],
                zeilen_koepfe: list[str]) -> dict[tuple[str, str, int], float]:
    """Ein Export → ``{(slug, zeilenkopf, jahr): wert}``.

    Die Spalten heißen „2019\\nOldenburg (Oldenburg)" — Jahr außen, Kommune
    innen, in der Reihenfolge der Anfrage. Zugeordnet wird über diese
    Reihenfolge; der Name in der Spalte muss dazu passen, sonst ist die
    Datei anders gebaut als gedacht und nichts wird gelesen."""
    zeilen = list(csv.reader(io.StringIO(text), delimiter=";"))
    kopf = next((z for z in zeilen if z and z[0] == "Indikatoren"), None)
    if kopf is None:
        raise VergleichFehler("Export ohne Kopfzeile „Indikatoren“")
    spalten: list[tuple[str, int]] = []
    for i, k in enumerate(kopf[1:]):
        jahr, _, name = k.partition("\n")
        slug = slugs[i % len(slugs)]
        erwartet = namen[slug].split(" (")[0]
        if erwartet not in name:
            raise VergleichFehler(f"Spalte {i + 1}: „{name}“ statt {erwartet}")
        spalten.append((slug, int(jahr)))
    aus: dict[tuple[str, str, int], float] = {}
    for z in zeilen:
        if not z or z[0] not in zeilen_koepfe:
            continue
        for (slug, jahr), roh in zip(spalten, z[1:]):
            wert = _zahl(roh)
            if wert is not None:
                aus[(slug, z[0], jahr)] = wert
    return aus


def gruppe(regionen: list[dict], einwohner: dict[str, float]) -> list[dict]:
    """Die Vergleichsgruppe aus Regionenliste und Einwohnerzahl (jüngstes
    Jahr): ``[{slug, name, ags, population}]``."""
    aus = []
    for r in regionen:
        if r.get("type") != "KREISFREIE_STADT":
            continue
        ew = einwohner.get(r["friendlyUrl"])
        if ew is None:
            continue
        if EW_VON <= ew <= EW_BIS or r["ags"][:2] == LAND_NI:
            aus.append({"slug": r["friendlyUrl"], "name": r["name"],
                        "ags": r["ags"][:8], "population": ew})
    return aus


@dataclass
class Probe:
    bestanden: set[tuple[str, int]] = field(default_factory=set)
    hinweise: list[str] = field(default_factory=list)


def pruefe_oldenburg(werte: dict[tuple[str, int], float], einwohner: dict[int, float],
                     eigene: dict[str, dict[int, float]]) -> Probe:
    """Oldenburgs Wegweiser-Werte gegen die eigenen Reihen.

    ``werte``: ``{(kennzahl, jahr): €/EW}`` aus dem Export,
    ``einwohner``: Oldenburgs Einwohnerzahl je Jahr aus demselben Portal,
    ``eigene``: ``income_tax`` und ``property_tax_b`` in Euro je Jahr,
    ``liquidity_year_end`` der Liquiditätsstand zum 31.12."""
    p = Probe()
    for (kennzahl, jahr), wert in sorted(werte.items()):
        if kennzahl == "liquidity_loans":
            stand = eigene.get("liquidity_year_end", {}).get(jahr)
            if stand is None:
                p.hinweise.append(f"{kennzahl} {jahr}: kein Liquiditätsstand zum Jahresende")
            elif stand >= 0 and wert == 0:
                p.bestanden.add((kennzahl, jahr))
            else:
                p.hinweise.append(f"{kennzahl} {jahr}: {wert:.0f} €/EW, Liquiditätsstand {stand:,.0f} €")
            continue
        betrag, ew = eigene.get(kennzahl, {}).get(jahr), einwohner.get(jahr)
        if not betrag or not ew:
            p.hinweise.append(f"{kennzahl} {jahr}: keine eigene Reihe zum Prüfen")
            continue
        je_ew = betrag / ew
        if abs(wert - je_ew) <= TOLERANZ * je_ew:
            p.bestanden.add((kennzahl, jahr))
        else:
            p.hinweise.append(f"{kennzahl} {jahr}: {wert:.0f} €/EW, eigene Reihe {je_ew:.0f} €/EW")
    return p


def kennwerte(werte: list[float]) -> dict:
    """Spannweite, Quartile und Median — linear interpoliert wie Excel/numpy —
    und wie viele Städte genau 0 haben (bei den Liquiditätskrediten die Regel)."""
    s = sorted(werte)
    n = len(s)
    if not n:
        return {"n": 0, "zero": 0, "min": None, "p25": None, "median": None, "p75": None, "max": None}

    def q(p: float) -> float:
        pos = p * (n - 1)
        u = int(pos)
        o = min(u + 1, n - 1)
        return s[u] + (s[o] - s[u]) * (pos - u)
    return {"n": n, "zero": sum(1 for v in s if v == 0), "min": s[0], "p25": q(0.25),
            "median": q(0.5), "p75": q(0.75), "max": s[-1]}
