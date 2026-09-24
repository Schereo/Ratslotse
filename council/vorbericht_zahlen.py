"""Die Zahlen im Vorbericht (Anlage 001) — Personalaufwand, Steuerarten,
Fehlbeträge — mit Prognose und Finanzplanung (Plan Haushalt-Datenquellen,
PR 5, zweiter Teil).

Der Wortlaut des Vorberichts steht seit #1549 auf der Bereichsseite
(``council/vorbericht.py``). Drei Kapitel tragen daneben Zahlen, die sonst
nirgends im Bestand stehen:

* **2.4.1.3 Gesamtstädtische Personalaufwendungen** — eine Tabelle:
  Ergebnis des Vorvorjahres und Ansätze bis zum Ende der Finanzplanung für
  aktives Personal, Versorgung, Summe, „davon Zuführungen zu
  Personalrückstellungen" und „ohne Rückstellungen". Die Rückstellungen und
  der Aufwand ohne sie stehen im Ergebnishaushalt nicht.
* **2.2 Steuerarten** — je Steuer ein Diagramm: Ist des Vorvorjahres, Plan
  UND PROGNOSE des laufenden Jahres, Plan und Finanzplanung. Die Prognose
  der Kämmerei und die Finanzplanung je Steuerart stehen sonst nirgends.
* **2.1.1 Fehlbeträge und Überschüsse** — ein Diagramm: Jahresergebnisse
  (Ist), die Prognose des laufenden Jahres, Plan und Finanzplanung.

DIAGRAMME als Text: Die Beschriftungen stehen in der Textebene in fester
Folge — zuerst die Werte an den Balken, dann die Achsenteilung, dann die
Kategorien („2024", „2025 / Plan", „2025 / Prognose", „2026" …), zuletzt der
Titel. Gelesen werden so viele Werte, wie es Kategorien gibt; was danach
kommt, muss eine gleichmäßige Achse sein, sonst ist das Diagramm anders
gebaut als gedacht und wird verworfen. Was eine nackte Jahreszahl meint (Ist,
Plan, Prognose), sagt die Bildunterschrift („2024 Ist, 2025 Plan/Prognose,
ab 2026 Plan").

DIE PROBEN, gegen den Ergebnishaushalt desselben Plans
(``council_income_budget``):

* Personal: aktiv + Versorgung = Summe, Summe − Rückstellungen = ohne
  Rückstellungen (je Spalte auf 2 €); der Ansatz des Planjahres für aktives
  Personal und Versorgung = Zeilen 13 und 14 (die Fußnote der Tabelle sagt
  es selbst).
* Fehlbeträge: die Planwerte = ordentliches + außerordentliches Ergebnis
  (Zeilen 21 und 24), auf 0,1 Mio. €.
* Steuern: die Achse ist gleichmäßig. Die Ist-Werte prüft der Ingest gegen
  das Statistische Jahrbuch — außer der Gewerbesteuer, die das Jahrbuch nach
  Abzug der Umlage zählt, der Vorbericht davor.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

PROBE = "budget_preface_figures"

#: Diagrammtitel → Reihe. Der Titel kann über zwei Zeilen laufen
#: („Entwicklung des Gemeindeanteils an der Einkommenssteuer / in Millionen Euro").
DIAGRAMME = {
    "tax_property": re.compile(r"Grundsteuer A\s*\+\s*B", re.I),
    "tax_trade": re.compile(r"Gewerbesteuer", re.I),
    "tax_income": re.compile(r"Einkommens?steuer", re.I),
    "tax_sales": re.compile(r"Umsatzsteuer", re.I),
    "result": re.compile(r"Fehlbetr", re.I),
}
PERSONAL_ZEILEN = {
    "personnel_active": re.compile(r"^Personalaufwand für aktives Personal"),
    "personnel_pension": re.compile(r"^Aufwand für Versorgung"),
    "personnel_total": re.compile(r"^Summe der Personalaufwendungen"),
    "personnel_provisions": re.compile(r"^davon (Zuführungen zu|Rückstellungen)"),
    "personnel_net": re.compile(r"^Personalaufwand ohne Rückstellungen"),
}
_ZAHL = re.compile(r"^-?\d{1,3}(?:\.\d{3})*(?:,\d+)?$")


class ZahlenFehler(ValueError):
    """Eine Tabelle oder ein Diagramm ist anders gebaut als gedacht."""


@dataclass
class Wert:
    series: str
    year: int
    variant: str           # actual | prior_budget | forecast | budget | financial_plan
    amount: float          # Euro
    page: int


@dataclass
class Lesung:
    plan_year: int | None = None
    werte: list[Wert] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)


def _zahl(s: str) -> float | None:
    s = s.strip()
    return float(s.replace(".", "").replace(",", ".")) if _ZAHL.match(s) else None


def _variante(jahr: int, plan_jahr: int, art: str) -> str:
    art = art.lower()
    if "ergebnis" in art or art == "ist":
        return "actual"
    if "prognose" in art:
        return "forecast"
    if jahr < plan_jahr:
        return "prior_budget"
    return "budget" if jahr == plan_jahr else "financial_plan"


def lies_personal(text: str, plan_jahr: int, seite: int) -> list[Wert]:
    """Die Tabelle aus 2.4.1.3 — Spalten aus den Köpfen „Ergebnis 2024",
    „Ansatz 2025" …, je Zeile so viele Zahlen, wie es Spalten gibt."""
    start = text.find("Aufwendungen für aktives")
    if start < 0:
        raise ZahlenFehler("keine Personaltabelle")
    t = text[start:]
    spalten = [(m.group(1), int(m.group(2)))
               for m in re.finditer(r"(Ergebnis|Ansatz)\s+(20\d\d)", t[:600])]
    if len(spalten) < 3:
        raise ZahlenFehler(f"Personaltabelle: {len(spalten)} Spaltenköpfe")
    zeilen = [z.strip() for z in t.splitlines() if z.strip()]
    aus: list[Wert] = []
    for reihe, muster in PERSONAL_ZEILEN.items():
        i = next((k for k, z in enumerate(zeilen) if muster.match(z)), None)
        if i is None:
            raise ZahlenFehler(f"Personaltabelle: Zeile {reihe} fehlt")
        zahlen: list[float] = []
        for z in zeilen[i + 1:]:
            # Mehrere Zahlen in einer Zeile kommen vor („156.724.671 159.343.875
            # 162.307.762", 2021 und 2025) — sie werden einzeln gezählt.
            werte = [_zahl(t) for t in z.split()]
            if not werte or any(w is None for w in werte):
                if zahlen:
                    break
                continue          # Umbruch in der Beschriftung („Personalrückstellungen:**")
            zahlen += [w for w in werte if w is not None]
            if len(zahlen) >= len(spalten):
                break
        zahlen = zahlen[:len(spalten)]
        if len(zahlen) != len(spalten):
            raise ZahlenFehler(f"Personaltabelle: {reihe} hat {len(zahlen)} statt {len(spalten)} Werte")
        aus += [Wert(reihe, jahr, _variante(jahr, plan_jahr, art), w, seite)
                for (art, jahr), w in zip(spalten, zahlen)]
    return aus


def pruefe_personal(werte: list[Wert]) -> list[str]:
    """Summe und „ohne Rückstellungen" rechnen sich aus den Zeilen."""
    je = {(w.series, w.year, w.variant): w.amount for w in werte}
    fehler = []
    for (reihe, jahr, art), summe in je.items():
        if reihe != "personnel_total":
            continue
        aktiv, pension = je.get(("personnel_active", jahr, art)), je.get(("personnel_pension", jahr, art))
        rueck, netto = je.get(("personnel_provisions", jahr, art)), je.get(("personnel_net", jahr, art))
        if aktiv is None or pension is None or abs(aktiv + pension - summe) > 2:
            fehler.append(f"Personal {jahr}: aktiv + Versorgung ≠ Summe")
        if rueck is None or netto is None or abs(summe - rueck - netto) > 2:
            fehler.append(f"Personal {jahr}: Summe − Rückstellungen ≠ ohne Rückstellungen")
    return fehler


_UNTERSCHRIFT = re.compile(r"(?:ab\s+)?(20\d\d)(?:\s*[–-]\s*(20\d\d))?\s+(Ist|Plan|Prognose)(?:/(Plan|Prognose|Ist))?")


def _deutung(unterschrift: str, plan_jahr: int) -> dict[int, list[str]]:
    """„2019 – 2024 Ist, 2025 Prognose, 2026 – 2029 Plan" → Jahr → Arten."""
    aus: dict[int, list[str]] = {}
    for m in _UNTERSCHRIFT.finditer(unterschrift):
        von = int(m.group(1))
        bis = int(m.group(2)) if m.group(2) else (plan_jahr + 4 if unterschrift[m.start():m.start() + 2] == "ab" else von)
        for j in range(von, bis + 1):
            aus[j] = [a for a in (m.group(3), m.group(4)) if a]
    return aus


def lies_diagramme(text: str, plan_jahr: int, seite: int) -> tuple[list[Wert], list[str]]:
    """Die Diagramme einer Seite, die in :data:`DIAGRAMME` vorkommen."""
    zeilen = [z.strip() for z in text.splitlines() if z.strip()]
    aus: list[Wert] = []
    hinweise: list[str] = []
    for i, z in enumerate(zeilen):
        # „in Millionen Euro" — 2020 noch „in Mio. EUR".
        einheit = re.compile(r"in (Millionen|Mio\.)")
        titel = z if einheit.search(z) else (
            f"{z} {zeilen[i + 1]}" if i + 1 < len(zeilen) and einheit.match(zeilen[i + 1]) else None)
        if not titel:
            continue
        reihe = next((k for k, m in DIAGRAMME.items() if m.search(titel)), None)
        if reihe is None:
            continue
        # Rückwärts: Kategorien, dann Zahlen (Werte + Achse).
        k = i - 1
        kategorien: list[tuple[int, str]] = []
        while k >= 0 and (re.fullmatch(r"20\d\d", zeilen[k]) or zeilen[k] in ("Plan", "Prognose", "Ist")):
            if re.fullmatch(r"20\d\d", zeilen[k]):
                folge = zeilen[k + 1] if zeilen[k + 1] in ("Plan", "Prognose", "Ist") else ""
                kategorien.insert(0, (int(zeilen[k]), folge))
            k -= 1
        zahlen: list[float] = []
        while k >= 0:
            teile = zeilen[k].split()
            werte = [_zahl(t) for t in teile]
            if not teile or any(w is None for w in werte):
                break
            zahlen = [w for w in werte if w is not None] + zahlen
            k -= 1
        n = len(kategorien)
        if n < 3 or len(zahlen) < n + 3:
            hinweise.append(f"S. {seite} {reihe}: {n} Kategorien, {len(zahlen)} Zahlen")
            continue
        daten, achse = zahlen[:n], zahlen[n:]
        schritte = {round(b - a, 3) for a, b in zip(achse, achse[1:])}
        if len(schritte) != 1:
            hinweise.append(f"S. {seite} {reihe}: Achse nicht gleichmäßig ({sorted(schritte)[:3]})")
            continue
        unterschrift = " ".join(zeilen[max(0, k - 40):k + 1])
        u = re.findall(r"[^()]*\(Grafik \d+\)", unterschrift)
        deutung = _deutung(u[-1] if u else "", plan_jahr)
        for (jahr, folge), wert in zip(kategorien, daten):
            art = folge or (deutung.get(jahr, [""])[0] if len(deutung.get(jahr, [])) == 1 else "")
            aus.append(Wert(reihe, jahr, _variante(jahr, plan_jahr, art or ("Ist" if jahr < plan_jahr - 1 else "")),
                            round(wert * 1e6, 0), seite))
    return aus, hinweise


def lies(seiten: list[str], plan_jahr: int) -> Lesung:
    """Alle Seiten eines Vorberichts (Text) → die drei Zahlenteile."""
    aus = Lesung(plan_year=plan_jahr)
    for nr, text in enumerate(seiten, 1):
        if "Personalaufwand für aktives Personal" in text and "Summe der Personalaufwendungen" in text:
            try:
                aus.werte += lies_personal(text, plan_jahr, nr)
            except ZahlenFehler as fehler:
                aus.hinweise.append(str(fehler))
        if "in Millionen" in text or "in Mio." in text:
            werte, hinweise = lies_diagramme(text, plan_jahr, nr)
            aus.werte += werte
            aus.hinweise += hinweise
    # Ein Diagramm doppelt (Inhaltsverzeichnis, Wiederholung): das erste gilt.
    gesehen: set[tuple] = set()
    eindeutig = []
    for w in aus.werte:
        k = (w.series, w.year, w.variant)
        if k not in gesehen:
            gesehen.add(k)
            eindeutig.append(w)
    aus.werte = eindeutig
    aus.hinweise += pruefe_personal([w for w in aus.werte if w.series.startswith("personnel")])
    return aus


def pruefe_gegen_plan(lesung: Lesung, ergebnishaushalt: dict[tuple[int, int], float]) -> list[str]:
    """``ergebnishaushalt``: (Jahr, Zeile) → Betrag des Plans desselben Jahrgangs."""
    fehler = []
    for w in lesung.werte:
        if w.variant not in ("budget", "financial_plan"):
            continue
        if w.series in ("personnel_active", "personnel_pension"):
            soll = ergebnishaushalt.get((w.year, 13 if w.series == "personnel_active" else 14))
            if soll is not None and abs(soll - w.amount) > 2:
                fehler.append(f"{w.series} {w.year}: {w.amount:,.0f} ≠ Ergebnishaushalt {soll:,.0f}")
        if w.series == "result":
            ord_, aord = ergebnishaushalt.get((w.year, 21)), ergebnishaushalt.get((w.year, 24))
            if ord_ is not None and aord is not None and abs(ord_ + aord - w.amount) > 60_000:
                fehler.append(f"Ergebnis {w.year}: {w.amount / 1e6:.1f} ≠ Ergebnishaushalt {(ord_ + aord) / 1e6:.1f}")
    return fehler
