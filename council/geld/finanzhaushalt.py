"""Der Finanzhaushalt — die Zahlungsströme des Haushaltsplans.

Der Ergebnishaushalt sagt, was die Stadt an Erträgen und Aufwendungen PLANT
(Abschreibungen, Rückstellungen eingeschlossen); der Finanzhaushalt sagt, was
an Geld tatsächlich fließen soll: Ein- und Auszahlungen aus laufender
Verwaltung, für Investitionen, für Kredite — und als Ergebnis den
Finanzmittelüberschuss oder -fehlbetrag. Dazu drei Jahre Finanzplanung.

Bis 10/2026 stand der Bestand nur auf der Investitionsseite (und dort nur
seine Investitionszeilen); die KI-Frage kannte ihn nicht. Der Baustein bringt
die SUMMENZEILEN (``role``) — die Einzelposten sind über ``budget_document``
erreichbar und hier Ballast.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from council.store_basis import StoreBasis
from kern.dbfehler import tabelle_fehlt

NAME = "finanzhaushalt"

_WORT = re.compile(
    r"finanzhaushalt|finanzmittel(?:fehlbetrag|ueberschuss|veraenderung|bestand)?\b|"
    r"investitionstaetigkeit|finanzierungstaetigkeit|verwaltungstaetigkeit|"
    r"finanzplanung|mittelfristige? (?:finanz|planung)|zahlungsstroem|"
    r"\b(?:ein|aus)zahlungen\b")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    return bool(_WORT.search(text))


#: Die Summenzeilen in Lesereihenfolge — Rolle → Beschriftung im Baustein.
ROLLEN: tuple[tuple[str, str], ...] = (
    ("total_in_operating", "Einzahlungen aus laufender Verwaltungstätigkeit"),
    ("total_out_operating", "Auszahlungen aus laufender Verwaltungstätigkeit"),
    ("balance_operating", "Saldo aus laufender Verwaltungstätigkeit"),
    ("total_in_capital", "Einzahlungen für Investitionstätigkeit"),
    ("total_out_capital", "Auszahlungen für Investitionstätigkeit"),
    ("balance_capital", "Saldo aus Investitionstätigkeit"),
    ("cash_surplus", "Finanzmittelüberschuss/-fehlbetrag"),
    ("balance_financing", "Saldo aus Finanzierungstätigkeit (Kredite, Tilgung)"),
    ("cash_change", "Veränderung des Finanzmittelbestands"),
)
#: Für die Jahre der Finanzplanung nur diese drei — der Rest wäre Länge ohne Frage.
_KURZ = ("balance_operating", "total_out_capital", "cash_surplus")


class Store(StoreBasis):
    def finanzhaushalt_context(self, terms: list[str], year: int | None = None) -> dict | None:
        """Der Finanzhaushalt EINES Plans: Ansatzjahr vollständig, die Jahre
        der Finanzplanung mit drei Kernzeilen. ``year`` wählt den Plan; liegt
        es nur in der Finanzplanung des jüngsten Plans, kommt dieser."""
        try:
            plan, abweichend = geld.jahrgang(self._conn, "council_finance_budget",
                                             "plan_budget_year", year)
            if plan is None:
                return None
            zeilen = [dict(r) for r in self._conn.execute(
                "SELECT year, kind, role, amount, herkunft_id FROM council_finance_budget "
                "WHERE plan_budget_year = ? AND role IS NOT NULL ORDER BY year, nr", (plan,))]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not zeilen:
            return None
        if abweichend and year is not None and any(z["year"] == year for z in zeilen):
            abweichend = False  # das Jahr steht in der Finanzplanung dieses Plans
        return {"plan": plan, "anderer_jahrgang": abweichend, "gefragt": year,
                "zeilen": zeilen, "beleg": self._beleg(zeilen[0]["herkunft_id"])}


def block(data: dict | None) -> str:
    if not data or not data.get("zeilen"):
        return ""
    plan = data["plan"]
    namen = dict(ROLLEN)
    je_jahr: dict[int, dict[str, dict]] = {}
    for z in data["zeilen"]:
        je_jahr.setdefault(int(z["year"]), {})[z["role"]] = z
    zeilen = []
    for jahr in sorted(je_jahr):
        art = "Ansatz" if jahr == plan else "Finanzplanung"
        rollen = [r for r, _ in ROLLEN] if jahr == plan else list(_KURZ)
        for rolle in rollen:
            z = je_jahr[jahr].get(rolle)
            if z is None or z.get("amount") is None:
                continue
            zeilen.append(f"- {namen[rolle]} {jahr} ({art}): {geld.de_mio(z['amount'])}")
    if not zeilen:
        return ""
    if data.get("anderer_jahrgang"):
        zeilen.append(f"- Zum gefragten Jahr liegt kein Plan vor; das ist der Plan {plan}.")
    return (f"\nFINANZHAUSHALT laut Haushaltsplan {plan} (PLAN, ZAHLUNGEN — nicht der "
            "Ergebnishaushalt mit\nErträgen und Aufwendungen; die Jahre nach "
            f"{plan} sind Finanzplanung, keine Beschlüsse).\n"
            "Ein negativer Saldo heißt: Es fließt mehr Geld hinaus als herein. NIE mit [id]:\n"
            + "\n".join(zeilen) + geld.beleg_text(data.get("beleg")) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="finanzhaushalt_context", erkennen=recognize, block=block,
    # 1.725 Zeichen gemessen (Plan 2026, Abzug vom 11.10.2026).
    mixin=Store, rang=55, grenze=1900,
    probefrage="Wie hoch ist der Finanzmittelfehlbetrag im Finanzhaushalt 2026?")
