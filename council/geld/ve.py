"""Verpflichtungsermächtigungen nach Fälligkeit — wie ein Plan spätere Jahre bindet.

Die Haushaltssatzung (Facette ``bylaw``) nennt die SUMME der
Verpflichtungsermächtigungen (§ 3). Der Haushaltsplan sagt dazu, in welchen
Jahren sie voraussichtlich fällig werden — das ist die Antwort auf „Wie stark
belastet der Haushalt die nächsten Jahre?". Bis 10/2026 nur auf der
Schuldenseite.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from council.store_basis import StoreBasis
from kern.dbfehler import tabelle_fehlt

NAME = "ve"

_WORT = re.compile(
    r"verpflichtungsermaecht|vorbelast|\bve\b|kuenftige (?:jahre|haushalte|haushaltsjahre)|"
    r"spaetere (?:jahre|haushalte)")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    return bool(_WORT.search(text))


class Store(StoreBasis):
    def ve_context(self, terms: list[str], year: int | None = None) -> dict | None:
        try:
            plan, abweichend = geld.jahrgang(self._conn, "council_commitments", "budget_year", year)
            if plan is None:
                return None
            zeilen = [dict(r) for r in self._conn.execute(
                "SELECT due_year, amount, herkunft_id FROM council_commitments "
                "WHERE budget_year = ? AND plan_year = budget_year ORDER BY due_year", (plan,))]
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
    zeilen = [f"- im Plan {plan} ermächtigt, fällig {z['due_year']}: {geld.de_mio(z['amount'])}"
              for z in data["zeilen"] if z.get("amount") is not None]
    if not zeilen:
        return ""
    if data.get("anderer_jahrgang"):
        zeilen.append(f"- Zum gefragten Jahr gibt es keinen Plan; das ist der Plan {plan}.")
    return (f"\nVERPFLICHTUNGSERMÄCHTIGUNGEN DES HAUSHALTSPLANS {plan} nach dem Jahr, in dem "
            "sie\nvoraussichtlich zu Auszahlungen führen. Eine Ermächtigung ist eine ERLAUBNIS, "
            "Verträge\nzu Lasten späterer Jahre zu schließen — keine Ausgabe. NIE mit [id]:\n"
            + "\n".join(zeilen) + geld.beleg_text(data.get("beleg")) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="ve_context", erkennen=recognize, block=block,
    mixin=Store, rang=22, grenze=700,
    probefrage="Wie viele Verpflichtungsermächtigungen werden 2027 fällig?")
