"""Erläuterungen zur Bilanz der Stadt — was hinter einer Bilanzposition steckt.

Die Bilanzzahlen selbst führt die alte Facette ``bilanz``; der Anhang des
Jahresabschlusses erklärt sie (Rückstellungen, Sonderposten, liquide Mittel …).
Bis 10/2026 nur auf der Haushaltsseite.

Ausgelöst wird nur, wenn eine Position UND eine Frage nach dem Warum oder
Was genannt ist — „Wie hoch ist das Anlagevermögen?" bleibt bei den Zahlen.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from council.store_basis import StoreBasis
from kern.dbfehler import tabelle_fehlt

NAME = "bilanz_erlaeuterung"

#: Position → Muster im gefalteten Wortlaut (auch in den Suchbegriffen).
POSITIONEN: dict[str, re.Pattern[str]] = {
    "Immaterielles Vermögen": re.compile(r"immateriell"),
    "Sachvermögen": re.compile(r"sachvermoegen|anlagevermoegen"),
    "Finanzvermögen": re.compile(r"finanzvermoegen|forderung"),
    "Liquide Mittel": re.compile(r"liquide mittel|\bliquiditaet"),
    "Aktive Rechnungsabgrenzung": re.compile(r"aktive rechnungsabgrenzung"),
    "Nettoposition": re.compile(r"nettoposition|eigenkapital|sonderposten|ruecklage"),
    "Schulden": re.compile(r"verbindlichkeit"),
    "Rückstellungen": re.compile(r"rueckstellung|pension"),
    "Passive Rechnungsabgrenzung": re.compile(r"passive rechnungsabgrenzung"),
}
_FRAGT = re.compile(
    r"erlaeuter|warum|wieso|weshalb|was (?:ist|sind|bedeutet|bedeuten|steckt|gehoert)|"
    r"wie (?:kommt|entsteht|entstehen|setzt|ergibt)|woraus|zusammensetz|begruend|erklaer")


def _welche(text: str) -> list[str]:
    return [p for p, m in POSITIONEN.items() if m.search(text)]


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    return bool(_welche(text) and _FRAGT.search(text) and
                ("bilanz" in text or "stadt" in text or "jahresabschluss" in text))


#: So viel Erläuterungstext je Position — der Anhang ist lang, die Frage eng.
TEXT_MAX = 900


class Store(StoreBasis):
    def bilanz_erlaeuterung_context(self, terms: list[str],
                                    year: int | None = None) -> dict | None:
        welche = _welche(geld.falte(" ".join(terms or [])))
        if not welche:
            return None
        try:
            jahr, abweichend = geld.jahrgang(self._conn, "council_balance_sheet_notes",
                                             "year", year)
            if jahr is None:
                return None
            ph = ",".join("?" * len(welche))
            zeilen = [dict(r) for r in self._conn.execute(
                f"SELECT heading, text, herkunft_id FROM council_balance_sheet_notes "
                f"WHERE year = ? AND heading IN ({ph}) ORDER BY nr", (jahr, *welche))]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not zeilen:
            return None
        return {"year": jahr, "anderer_jahrgang": abweichend, "zeilen": zeilen[:2],
                "beleg": self._beleg(zeilen[0]["herkunft_id"])}


def block(data: dict | None) -> str:
    if not data or not data.get("zeilen"):
        return ""
    teile = []
    for z in data["zeilen"]:
        text = " ".join((z.get("text") or "").split())
        if len(text) > TEXT_MAX:
            text = text[:TEXT_MAX].rsplit(" ", 1)[0] + " …"
        teile.append(f"- {z['heading']} (Erläuterung zur Bilanz {data['year']}): {text}")
    if data.get("anderer_jahrgang"):
        teile.append(f"- Zum gefragten Jahr gibt es keine Erläuterung; das ist {data['year']}.")
    return (f"\nERLÄUTERUNGEN ZUR BILANZ DER STADT ({data['year']}, Anhang des "
            "Jahresabschlusses). Erklärt,\nwas eine Position enthält — die Beträge stehen in "
            "der Bilanz selbst. NIE mit [id]:\n"
            + "\n".join(teile) + geld.beleg_text(data.get("beleg")) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="bilanz_erlaeuterung_context", erkennen=recognize, block=block,
    mixin=Store, rang=530, grenze=2200,
    probefrage="Was sind die Rückstellungen in der Bilanz der Stadt?")
