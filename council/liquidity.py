"""Der Liquiditätsstand — wie viel Geld die Stadt am Monatsende auf dem Konto hat.

Die Verwaltung legt dem Finanzausschuss seit 2018 monatlich eine Grafik vor
(„Liquiditätsstand zum Monatsende"); die Vorlage selbst sagt nur „siehe
anliegende Grafik". Die Zahlen stecken im PDF der Anlage: Ein Balkendiagramm
über vier Jahrgänge, dessen Textauszug die Werte als nackte Zahlenfolge
trägt, gefolgt von den Achsenmarken (−10, 0, 10 … 200) und den Monatsnamen:

    Stand: 31.08.2025  01.09.2025 108,1 138,9 … 130,6 -10,0 0,0 10,0 … 200,0
    Januar Februar … in Mio. EUR Monatsendstand Liquiditätsstand zum
    Monatsende 2022, 2023, 2024 und 2025 im Vergleich 2022 2023 2024 2025

GEMESSEN, NICHT GERATEN — die Reihenfolge der Werte: Sie ist JAHRESWEISE,
Januar bis Dezember je Jahrgang, der laufende Jahrgang bis zum Stichtag
(gemessen an sieben Grafiken 2025/26: Der Wert für Januar 2023 steht in der
Grafik „2022–2025" an Position 13 und in der Grafik „2023–2026" an Position
1, und beide sagen 128,7). Die Zahl der Werte ist damit vorhersagbar —
zwölf je abgeschlossenem Jahrgang plus die Monate des laufenden bis zum
Stichtag — und genau das ist die Probe :data:`WERTZAHL`: Stimmt die Zahl
nicht, wird die Grafik nicht gelesen.

Die zweite Probe ist die Überlappung (:data:`UEBERLAPPUNG`): Jede Grafik
trägt vier Jahrgänge, aufeinanderfolgende Grafiken teilen sich also drei.
Derselbe Monat steht damit in bis zu 48 Grafiken, und der jüngste Beleg
gewinnt — er ist die Grafik, die der Ausschuss zuletzt gesehen hat. Weichen
die Werte ab, ist das eine KORREKTUR der Verwaltung (gemessen: Februar 2024
stand in der Grafik vom 27.02.2024 mit 151,9 Mio. €, in allen sechzehn
späteren mit 151,3): Der Monat trägt dann den jüngsten Wert, ``revised_from`` den
verdrängten, und die Überlappungsprobe gilt als nicht bestanden — der
Baustein sagt es dazu, statt den Monat zu verschweigen.

Beträge in Euro (die Grafik sagt „in Mio. EUR"); ``as_of`` ist der Stichtag
der Grafik, nicht das Datum der Vorlage.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

WERTZAHL = "liquidity_value_count"
UEBERLAPPUNG = "liquidity_overlap"
FUNDSTELLE = "Anlage „Grafik Liquiditätsstand zum Monatsende“ — die Werte des Balkendiagramms"

TITEL = re.compile(r"^Liquiditätsstand", re.IGNORECASE)
_STAND = re.compile(r"Stand:\s*(\d{2})\.(\d{2})\.(\d{4})")
_JAHRE = re.compile(r"((?:\d{4},\s*)+\d{4}\s+und\s+\d{4})\s+im Vergleich")
_JAHRE_LABEL = re.compile(r"(\d{4})\s*-\s*(\d{4})")
_ZAHL = re.compile(r"(?<![\d,.])(-?\d{1,3},\d)(?![\d])")


def erkenne(title: str | None) -> bool:
    return bool(TITEL.search(title or ""))


def jahre(text: str, label: str | None = None) -> list[int]:
    """Die Jahrgänge der Grafik — aus dem Titel im Bild, sonst aus dem Label."""
    m = _JAHRE.search(text)
    if m:
        return sorted({int(j) for j in re.findall(r"\d{4}", m.group(1))})
    m = _JAHRE_LABEL.search(label or "") or _JAHRE_LABEL.search(text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if 0 < b - a < 6:
            return list(range(a, b + 1))
    return []


def lies_grafik(text: str, label: str | None = None) -> dict | None:
    """Eine Grafik → ``{"as_of", "years", "values": {"YYYY-MM": euro}, "probes"}``.

    ``None``, wenn Stichtag oder Jahrgänge fehlen oder die Wertzahl nicht
    aufgeht — dann ist es keine Liquiditätsgrafik oder eine, deren Layout
    dieses Modul nicht kennt."""
    t = re.sub(r"\s+", " ", text or "")
    m = _STAND.search(t)
    if not m:
        return None
    tag, monat, jahr = int(m.group(1)), int(m.group(2)), int(m.group(3))
    as_of = f"{jahr:04d}-{monat:02d}-{tag:02d}"
    jg = jahre(t, label)
    if not jg:
        # Die Grafiken bis 2021 tragen weder Jahrgangs-Zeile noch Label —
        # aber immer vier Jahrgänge bis zum Stichtag. Die Wertzahl-Probe
        # unten entscheidet, ob die Annahme trägt.
        jg = [jahr - 3, jahr - 2, jahr - 1, jahr]
    if jahr not in jg:
        return None
    # Die Zahlen NACH dem Stichtag — davor stehen Seitenzahl und Kopfziffern.
    rest = t[m.end():]
    tokens = _ZAHL.findall(rest)
    erwartet = 12 * (jg.index(jahr)) + monat
    # Hinter den Werten folgen die Achsenmarken: eine Zehnerreihe (ab −70,
    # −10 oder 0, je nach Jahrgang). Sie muss GENAU an Position `erwartet`
    # beginnen — beginnt sie früher, fehlt ein Wert; später, ist einer zu viel.
    if len(tokens) < erwartet + 2:
        return None

    def zahl(s: str) -> float:
        return float(s.replace(",", "."))

    m0, m1 = zahl(tokens[erwartet]), zahl(tokens[erwartet + 1])
    if not (m0 % 10 == 0 and m1 - m0 == 10):
        return None
    if erwartet and zahl(tokens[erwartet - 1]) == m0 - 10 and zahl(tokens[erwartet - 1]) % 10 == 0:
        return None   # die Marken beginnen schon davor — ein Wert fehlt
    werte: dict[str, float] = {}
    i = 0
    for y in jg:
        if y > jahr:
            break
        bis = monat if y == jahr else 12
        for mm in range(1, bis + 1):
            werte[f"{y:04d}-{mm:02d}"] = float(tokens[i].replace(",", ".")) * 1e6
            i += 1
    return {"as_of": as_of, "years": jg, "values": werte, "probes": [WERTZAHL]}


def lies(anlagen: Iterable[dict]) -> dict:
    """Alle Grafiken → eine Monatsreihe, jüngster Beleg je Monat.

    ``anlagen``: dicts mit ``document_id``, ``label``, ``url``, ``raw_text``,
    ``template_number``. Rückgabe: ``rows`` (je Monat), ``rejected`` (je
    Grafik mit Grund), ``strittig`` (Monate mit widersprüchlichen Werten)."""
    je_monat: dict[str, list[dict]] = {}
    gelesen = 0
    rejected: list[dict] = []
    for a in anlagen:
        g = lies_grafik(a.get("raw_text") or "", a.get("label"))
        if not g:
            rejected.append({"document_id": a.get("document_id"), "template_number": a.get("template_number"),
                             "reason": "keine lesbare Liquiditätsgrafik (Stichtag, Jahrgänge oder Wertzahl fehlen)"})
            continue
        gelesen += 1
        for monat, euro in g["values"].items():
            je_monat.setdefault(monat, []).append({
                "month": monat, "year": int(monat[:4]), "amount": euro, "as_of": g["as_of"],
                "document_id": a.get("document_id"), "url": a.get("url"),
                "template_number": a.get("template_number")})
    rows: list[dict] = []
    strittig: list[dict] = []
    for monat in sorted(je_monat):
        belege = sorted(je_monat[monat], key=lambda b: b["as_of"])
        werte = {round(b["amount"]) for b in belege}
        r = dict(belege[-1])
        r["confirmations"] = len(belege)
        r["revised_from"] = None
        if len(werte) > 1:
            # Korrektur: der jüngste Wert gilt, der verdrängte reist mit.
            alt = [b["amount"] for b in belege if round(b["amount"]) != round(r["amount"])]
            r["revised_from"] = alt[-1]
            r["probes"] = [WERTZAHL]
            strittig.append({"month": monat, "values": sorted(werte),
                             "documents": [b["document_id"] for b in belege]})
        else:
            r["probes"] = [WERTZAHL] + ([UEBERLAPPUNG] if len(belege) > 1 else [])
        rows.append(r)
    return {"rows": rows, "rejected": rejected, "strittig": strittig,
            "probes": {"grafiken": gelesen, "monate": len(rows)}}


def probennachweis(result: dict) -> str:
    rows = result["rows"]
    doppelt = sum(1 for r in rows if UEBERLAPPUNG in r["probes"])
    return (f"{result['probes']['grafiken']} Grafiken gelesen, {len(rows)} Monate; die Wertzahl "
            f"jeder Grafik ging auf (zwölf je Jahrgang plus die Monate bis zum Stichtag); "
            f"{doppelt} Monate stehen in mehr als einer Grafik und stimmen überein"
            + (f"; {len(result['strittig'])} Monate von der Verwaltung später korrigiert — "
               "der jüngste Wert gilt" if result["strittig"] else "."))
