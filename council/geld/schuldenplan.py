"""Die Schuldenübersicht des Haushaltsplans — womit die Stadt ins Planjahr geht.

Jeder Haushaltsplan nennt je Einheit (Kernhaushalt, Eigenbetriebe) den
Schuldenstand zu Beginn des Vorjahres und den VORAUSSICHTLICHEN zu Beginn des
Planjahres, nach Schuldenarten. Das ist keine abgerechnete Zahl: Der
abgerechnete Stand kommt aus dem Jahrbuch (Facette ``schulden``), und genau
diese Verwechslung soll der Baustein verhindern.

Ausgelöst wird nur, wenn die Frage nach einer erwarteten oder geplanten
Entwicklung fragt oder die Übersicht/Eigenbetriebe nennt — „Wie hoch sind
die Schulden?" bleibt bei ``schulden``.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from council.store_basis import StoreBasis
from kern.dbfehler import tabelle_fehlt

NAME = "schuldenplan"

_SCHULD = re.compile(r"schulden|verschuld|verbindlichkeit|\bkredit")
_PLAN = re.compile(
    r"voraussichtlich|erwartet|geplant|planung|kuenftig|zukunft|\bwird\b|\bwerden\b|"
    r"steigen|anwachsen|zum jahresende|ende des jahres|beginn des|eigenbetrieb|"
    r"schuldenuebersicht|uebersicht")
_HART = re.compile(r"schuldenuebersicht")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    if _HART.search(text):
        return True
    return bool(_SCHULD.search(text) and _PLAN.search(text))


#: Die Zeilen, die in den Baustein kommen: Summe und Investitionskredite.
_CODES = {"total": "Schulden insgesamt", "1.2": "davon Kredite für Investitionen"}


class Store(StoreBasis):
    def schuldenplan_context(self, terms: list[str], year: int | None = None) -> dict | None:
        try:
            plan, abweichend = geld.jahrgang(self._conn, "council_debt_plan", "budget_year", year)
            if plan is None:
                return None
            zeilen = [dict(r) for r in self._conn.execute(
                "SELECT entity, code, start_prior, start_expected, herkunft_id "
                "FROM council_debt_plan WHERE budget_year = ? AND code IN ('total', '1.2') "
                "ORDER BY entity, code DESC", (plan,))]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not zeilen:
            return None
        return {"plan": plan, "anderer_jahrgang": abweichend, "zeilen": zeilen,
                "beleg": self._beleg(zeilen[0]["herkunft_id"])}


def block(data: dict | None) -> str:
    if not data or not data.get("zeilen"):
        return ""
    plan = data["plan"]
    # Je Einheit und STICHTAG: erst die Summe, darunter ihr „davon“ mit
    # demselben Datum. Eingerückt unter einem anderen Stichtag läse ein Modell
    # die Investitionskredite 2024 als Teil der Summe 2025
    # (tests/test_geld_gliederung.py).
    zeilen = []
    je_einheit: dict[str, dict[str, dict]] = {}
    for z in data["zeilen"]:
        je_einheit.setdefault(z["entity"], {})[z["code"]] = z
    for einheit, codes in je_einheit.items():
        for spalte, wann in (("start_prior", f"Stand 31.12.{plan - 2}"),
                             ("start_expected", f"VORAUSSICHTLICH 31.12.{plan - 1}")):
            for code in ("total", "1.2"):
                z = codes.get(code)
                if z is None or z.get(spalte) is None:
                    continue
                einr = "" if code == "total" else "  "
                zeilen.append(f"{einr}- {einheit}, {_CODES[code]}, {wann}: "
                              f"{geld.de_mio(z[spalte])}")
    if not zeilen:
        return ""
    if data.get("anderer_jahrgang"):
        zeilen.append(f"- Zum gefragten Jahr gibt es keinen Plan; das ist der Plan {plan}.")
    return (f"\nSCHULDENÜBERSICHT DES HAUSHALTSPLANS {plan} — womit Kernhaushalt und "
            "Eigenbetriebe\nvoraussichtlich ins Planjahr gehen. Die Zeilen „VORAUSSICHTLICH“ "
            "sind eine Erwartung beim\nAufstellen des Plans, KEIN abgerechneter Stand; den "
            "nennt das Statistische Jahrbuch. NIE mit [id]:\n"
            + "\n".join(zeilen) + geld.beleg_text(data.get("beleg")) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="schuldenplan_context", erkennen=recognize, block=block,
    # VOR den alten Facetten: Sie löst nur bei ausdrücklichen Planungsfragen
    # aus, und dann ist sie die Antwort. Mit Rang 520 fiel sie bei „Mit welchen
    # Schulden geht die Gebäudewirtschaft voraussichtlich ins Jahr 2026?“
    # hinten aus dem Deckel — Gesellschaften, Wirtschaftspläne und der
    # Jahrbuch-Schuldenstand hatten ihn schon gefüllt (Messung 21.10.2026).
    mixin=Store, rang=18, grenze=1700,  # 1.501 gemessen (drei Einheiten, Plan 2026)
    probefrage="Wie hoch werden die Schulden der Eigenbetriebe voraussichtlich sein?")
