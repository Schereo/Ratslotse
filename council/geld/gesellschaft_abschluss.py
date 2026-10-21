"""Jahresabschlüsse städtischer Gesellschaften — Bilanzsumme und Jahresergebnis.

Der Beteiligungsbericht (Facette ``companies``) erscheint ein Jahr später und
endet damit früher; die Jahresabschlüsse liegen als Ratsvorlagen vor, sobald
der Rat sie feststellt (``council/gesellschaft_abschluss.py``). Für bbgo, otm,
vhs, vwg, die Weser-Ems Halle und die Stadiongesellschaften stehen so auch die
jüngsten Jahre im Bestand. Bis 10/2026 nur auf der Konzernseite.

Das ist IST — anders als der Wirtschaftsplan (Facette ``business_plans``), der
plant. Der Baustein sagt es in seinem Kopf.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from council.store_basis import StoreBasis
from kern.dbfehler import tabelle_fehlt

NAME = "gesellschaft_abschluss"

#: Kürzel → Muster im gefalteten Wortlaut. Die Komplementärinnen (Beteiligungs-
#: GmbH) zieht nur ihr eigener Name; „Stadion" allein meint die KG.
GESELLSCHAFT: dict[str, re.Pattern[str]] = {
    "bbgo": re.compile(r"baederbetriebsgesellschaft|\bbbgo\b|baedergesellschaft"),
    "otm": re.compile(r"tourismus|\botm\b"),
    "vhs": re.compile(r"volkshochschule|\bvhs\b"),
    "vwg": re.compile(r"verkehr und wasser|\bvwg\b"),
    "weh": re.compile(r"weser ems halle(?! oldenburg beteiligung)|\bweh\b"),
    "weh_komplementaer": re.compile(r"weser ems halle oldenburg beteiligung"),
    "stadion": re.compile(r"stadion (?:oldenburg )?gmbh|stadiongesellschaft|stadion gesellschaft"),
    "stadion_komplementaer": re.compile(r"stadion oldenburg beteiligung|stadionplanungsgesellschaft"),
}
_FINANZ = re.compile(
    r"bilanzsumme|jahresergebnis|jahresueberschuss|jahresfehlbetrag|gewinn|verlust|"
    r"\bergebnis|abschluss|bilanz|\bplus\b|\bminus\b|defizit")


def _wer(text: str) -> list[str]:
    return [k for k, m in GESELLSCHAFT.items() if m.search(text)]


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    return bool(_wer(text) and _FINANZ.search(text))


_KENNZAHL = {"bilanzsumme": "Bilanzsumme", "jahresergebnis": "Jahresergebnis"}
#: So viele Geschäftsjahre je Gesellschaft — die Reihe davor kennt der
#: Beteiligungsbericht, und ``budget_document`` liefert alle.
JAHRE = 4


class Store(StoreBasis):
    def gesellschaft_abschluss_context(self, terms: list[str],
                                       year: int | None = None) -> dict | None:
        gemeint = geld.falte(" ".join(terms or []))
        wer = _wer(gemeint)
        if not wer:
            return None
        # Das Jahresergebnis ist die Frage fast immer; die Bilanzsumme nur,
        # wenn sie genannt ist — sonst verdoppelt sie den Baustein.
        kennzahlen = ["jahresergebnis"] + (["bilanzsumme"] if "bilanz" in gemeint else [])
        try:
            ph = ",".join("?" * len(wer))
            pk = ",".join("?" * len(kennzahlen))
            alle = [dict(r) for r in self._conn.execute(
                f"SELECT company, year, indicator, value, herkunft_id "
                f"FROM council_company_accounts WHERE company IN ({ph}) "
                f"AND indicator IN ({pk}) ORDER BY company, year, indicator",
                (*wer, *kennzahlen))]
            # Die letzten JAHRE je Gesellschaft (gefragtes Jahr eingeschlossen).
            zeilen = []
            for firma in wer:
                jahre = sorted({z["year"] for z in alle if z["company"] == firma})
                behalten = set(jahre[-JAHRE:]) | ({year} if year in jahre else set())
                zeilen += [z for z in alle if z["company"] == firma and z["year"] in behalten]
            namen = {r[0]: r[1] for r in self._conn.execute(
                f"SELECT company, name FROM council_companies WHERE company IN ({ph}) "
                f"ORDER BY report_year", wer)}
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not zeilen:
            return None
        # Schlüssel als TEXT: Nach einer JSON-Runde (Abzug, Zwischenspeicher)
        # wären Zahlen-Schlüssel Text, und der Beleg fehlte still.
        belege: dict[str, dict | None] = {}
        for z in zeilen:
            if str(z["herkunft_id"]) not in belege:
                belege[str(z["herkunft_id"])] = self._beleg(z["herkunft_id"])
        return {"zeilen": zeilen, "namen": namen, "belege": belege}


def block(data: dict | None) -> str:
    if not data or not data.get("zeilen"):
        return ""
    zeilen = []
    gezeigt: set = set()
    for z in data["zeilen"]:
        if z.get("value") is None:
            continue
        name = data["namen"].get(z["company"], z["company"])
        beleg = "" if z["herkunft_id"] in gezeigt else geld.beleg_text(
            data["belege"].get(str(z["herkunft_id"])))
        gezeigt.add(z["herkunft_id"])
        zeilen.append(f"- {name}, {_KENNZAHL.get(z['indicator'], z['indicator'])} "
                      f"{z['year']} (Ist, Jahresabschluss): {geld.de_mio(z['value'])}" + beleg)
    if not zeilen:
        return ""
    return ("\nJAHRESABSCHLÜSSE STÄDTISCHER GESELLSCHAFTEN (IST, vom Rat festgestellt — "
            "nicht der Wirtschaftsplan).\nEin negatives Jahresergebnis ist ein Verlust. "
            "NIE mit [id]:\n" + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="gesellschaft_abschluss_context", erkennen=recognize, block=block,
    mixin=Store, rang=52, grenze=1500,
    probefrage="Welches Jahresergebnis hatte die Bäderbetriebsgesellschaft 2025?")
