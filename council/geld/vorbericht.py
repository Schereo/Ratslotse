"""Der Vorbericht zum Haushaltsplan — Eckdaten mit Prognose.

Der Vorbericht stellt dem Plan Ist, Vorjahresansatz, Ansatz und Finanzplanung
gegenüber — und für das laufende Jahr eine PROGNOSE (Steuern, Ergebnis).
Genau die gibt es sonst nirgends im Bestand: „Wie viel Gewerbesteuer
erwartet die Stadt dieses Jahr?" fragt nach der Prognose, nicht nach dem
Ansatz. Bis 10/2026 stand das nur auf der Haushaltsseite.

Die Texte des Vorberichts (Erläuterungen je Teilhaushalt) kommen NICHT in
den Baustein: 170.000 Zeichen je Jahrgang, und der Teilhaushalt-Abgleich der
alten Facetten trifft dort zuverlässiger. Sie bleiben über
``budget_document`` erreichbar.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from council.store_basis import StoreBasis
from kern.dbfehler import tabelle_fehlt

NAME = "vorbericht"

#: Reihe → (Beschriftung, Muster in den gefalteten Suchbegriffen).
REIHEN: dict[str, tuple[str, re.Pattern[str]]] = {
    "tax_trade": ("Gewerbesteuer", re.compile(r"gewerbesteuer")),
    "tax_property": ("Grundsteuer", re.compile(r"grundsteuer")),
    "tax_income": ("Gemeindeanteil Einkommensteuer", re.compile(r"einkommensteuer")),
    "tax_sales": ("Gemeindeanteil Umsatzsteuer", re.compile(r"umsatzsteuer")),
    "result": ("Ergebnis des Ergebnishaushalts", re.compile(
        r"ergebnis|defizit|fehlbetrag|ueberschuss")),
    "personnel_total": ("Personalaufwand insgesamt", re.compile(r"personal")),
}
_VARIANTE = {"actual": "Ist", "forecast": "PROGNOSE", "prior_budget": "Ansatz Vorjahr",
             "budget": "Ansatz", "financial_plan": "Finanzplanung"}

_HART = re.compile(r"vorbericht|eckdaten|eckwert")
_PROGNOSE = re.compile(r"prognose|voraussichtlich|hochrechnung|\berwarte|rechnet .{0,30}mit")
_GEGENSTAND = re.compile(r"steuer|ergebnis|defizit|fehlbetrag|personal")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    if _HART.search(text):
        return True
    return bool(_PROGNOSE.search(text) and _GEGENSTAND.search(text))


class Store(StoreBasis):
    def vorbericht_context(self, terms: list[str], year: int | None = None) -> dict | None:
        """Die Eckdaten EINES Vorberichts — nur die Reihen, die die
        Suchbegriffe meinen; ohne Treffer die Steuern und das Ergebnis."""
        gemeint = geld.falte(" ".join(terms or []))
        reihen = [k for k, (_, m) in REIHEN.items() if m.search(gemeint)] or \
            ["tax_trade", "tax_property", "tax_income", "result"]
        try:
            # Das gefragte Jahr ist das Jahr der ZAHL, nicht des Plans: „Prognose
            # für 2025“ steht im Vorbericht zum Plan 2026 (der Plan 2025 kennt
            # für 2025 nur den Ansatz). Also der jüngste Plan — solange er das
            # Jahr überhaupt führt; sonst der Plan dieses Jahres.
            plan, _ = geld.jahrgang(self._conn, "council_budget_preface_figures",
                                    "plan_budget_year", None)
            if plan is None:
                return None
            abweichend = False
            if year is not None and not self._conn.execute(
                    "SELECT 1 FROM council_budget_preface_figures WHERE plan_budget_year = ? "
                    "AND year = ? LIMIT 1", (plan, year)).fetchone():
                plan, abweichend = geld.jahrgang(self._conn, "council_budget_preface_figures",
                                                 "plan_budget_year", year)
            ph = ",".join("?" * len(reihen))
            zeilen = [dict(r) for r in self._conn.execute(
                f"SELECT series, year, variant, amount, page, herkunft_id "
                f"FROM council_budget_preface_figures WHERE plan_budget_year = ? "
                f"AND series IN ({ph}) ORDER BY series, year", (plan, *reihen))]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not zeilen:
            return None
        return {"plan": plan, "anderer_jahrgang": abweichend, "reihen": reihen,
                "zeilen": zeilen, "beleg": self._beleg(zeilen[0]["herkunft_id"])}


def block(data: dict | None) -> str:
    if not data or not data.get("zeilen"):
        return ""
    zeilen = []
    for reihe in data["reihen"]:
        name = REIHEN[reihe][0]
        for z in (z for z in data["zeilen"] if z["series"] == reihe):
            if z.get("amount") is None:
                continue
            zeilen.append(f"- {name} {z['year']}, {_VARIANTE.get(z['variant'], z['variant'])}: "
                          f"{geld.de_mio(z['amount'])}")
    if not zeilen:
        return ""
    if data.get("anderer_jahrgang"):
        zeilen.append(f"- Zum gefragten Jahr gibt es keinen Vorbericht; das ist der zum Plan "
                      f"{data['plan']}.")
    return (f"\nVORBERICHT ZUM HAUSHALTSPLAN {data['plan']} — Eckdaten. Jede Zeile sagt, was "
            "die Zahl ist:\nIst = abgerechnet; PROGNOSE = Erwartung der Verwaltung beim "
            "Aufstellen des Plans\n(keine abgerechnete Zahl); Ansatz = geplant; "
            "Finanzplanung = Ausblick. NIE mit [id]:\n"
            + "\n".join(zeilen) + geld.beleg_text(data.get("beleg")) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="vorbericht_context", erkennen=recognize, block=block,
    # 2.138 Zeichen gemessen (vier Reihen, wenn keine genannt ist; 11.10.2026).
    mixin=Store, rang=58, grenze=2300,
    probefrage="Was steht im Vorbericht zum Haushaltsplan?")
