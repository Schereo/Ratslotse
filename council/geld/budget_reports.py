"""Die Budgetberichte an die Fachausschüsse — was aus den Investitionen im Jahr wird.

Quelle: ``council/budgetberichte.py`` (Tabelle ``council_budget_measures``),
viermal im Jahr an Jugendhilfe- und Schulausschuss: je Investitionsmaßnahme
der Ansatz, die Prognose zum Jahresende und die Begründung der Verwaltung.
Eingelesen sind nur die Teilhaushalte 11 (Jugend und Familie) und 12 (Schule
und Bildung) — für alle anderen Bereiche gibt es keine solchen Berichte.

Die Facette ergänzt ``measures`` (Investitionsprogramm, Gesamtkosten eines
Vorhabens) um den JAHRESVERLAUF: „Wird die Kita dieses Jahr fertig?", „Warum
fließt das Geld nicht ab?". Sie dockt an ``investitionen`` und ``measures``
an, liefert dann aber nur, wenn ein Begriff eine Maßnahme trifft — sonst
bliebe der Prompt jeder Investitionsfrage länger. Ausdrücklich nach Prognose
oder Budgetbericht gefragt, kommen die Summen der jüngsten Berichte.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from council.store_basis import StoreBasis
from kern.dbfehler import tabelle_fehlt

NAME = "budget_reports"

_DIREKT = re.compile(r"budgetbericht|quartalsbericht|finanz und leistungsbericht|"
                     r"prognose|abfliess|abgeflossen|mittelabfluss|"
                     r"ermaechtigungsuebertragung|haushaltsrest|"
                     r"fliess\w*[^?.!]{0,40}\bab\b|nicht ausgegeben|nicht verbaut")
_ANDOCKEN = re.compile(r"kita|krippe|kindergart|schule|schul|jugend|mensa|digitalpakt")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    if _DIREKT.search(text):
        return True
    return bool(facets & {"investitionen", "measures"}) and bool(_ANDOCKEN.search(text))


_ALLERWELT = geld.ALLERWELT | {"prognose", "jahresende", "investition", "investitionen",
                               "budgetbericht", "massnahme", "massnahmen", "dieses", "fertig",
                               "wird", "werden", "abfliessen"}
_NOTIZ = 260


class Store(StoreBasis):
    """Mixin für ``CouncilStore`` — die Maßnahmen der jüngsten Budgetberichte."""

    def budget_reports_context(self, terms: list[str], year: int | None = None) -> dict | None:
        try:
            wo = "budget_year = ?" if year is not None else "1 = 1"
            stichtage = [dict(r) for r in self._conn.execute(
                f"SELECT sub_budget_no, MAX(as_of) AS as_of FROM council_budget_measures "
                f"WHERE {wo} GROUP BY sub_budget_no", (year,) if year is not None else ())]
            if not stichtage and year is not None:
                stichtage = [dict(r) for r in self._conn.execute(
                    "SELECT sub_budget_no, MAX(as_of) AS as_of FROM council_budget_measures "
                    "GROUP BY sub_budget_no")]
            zeilen = []
            for s in stichtage:
                zeilen += [dict(r) for r in self._conn.execute(
                    "SELECT as_of, sub_budget_no, budget_year, measure_no, name, kind, planned, "
                    "       forecast, note, template_number, herkunft_id "
                    "  FROM council_budget_measures WHERE as_of = ? AND sub_budget_no = ? "
                    " ORDER BY seq", (s["as_of"], s["sub_budget_no"]))]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not zeilen:
            return None
        begriffe = [t for t in (terms or []) if geld.falte(t) not in _ALLERWELT
                    and not geld.allerwelt(t)]
        # Nach Trefferzahl, Name vor Erläuterung: „Kita Dedestraße" soll die
        # Maßnahme finden, die so heißt, nicht jede, deren Text Kitas erwähnt.
        gewertet = []
        for z in zeilen if begriffe else []:
            n_name = self._trifft(z["name"], begriffe)
            n_text = self._trifft(z["note"], begriffe)
            if n_name or n_text:
                gewertet.append((-(2 * n_name + n_text), z))
        gewertet.sort(key=lambda x: x[0])
        treffer = [z for _, z in gewertet]
        direkt = bool(_DIREKT.search(geld.falte(" ".join(terms or []))))
        if not treffer and not direkt:
            return None
        # Summen nur für die Bereiche, in denen die Frage etwas trifft — sonst
        # stünde bei jeder Kita-Frage der Schulbericht von 2023 mit im Prompt.
        bereiche = {z["sub_budget_no"] for z in treffer} or {z["sub_budget_no"] for z in zeilen}
        summen: dict[tuple, dict] = {}
        for z in zeilen:
            if z["kind"] == "A" and z["sub_budget_no"] in bereiche:
                s = summen.setdefault((z["sub_budget_no"], z["as_of"]), {
                    "sub_budget_no": z["sub_budget_no"], "as_of": z["as_of"],
                    "budget_year": z["budget_year"], "planned": 0.0, "forecast": 0.0})
                s["planned"] += z["planned"] or 0
                s["forecast"] += z["forecast"] or 0
        return {"summen": [summen[k] for k in sorted(summen)], "zeilen": treffer[:4], "weitere": max(0, len(treffer) - 4),
                "beleg": self._beleg((treffer or zeilen)[0]["herkunft_id"])}


def _datum(iso: str) -> str:
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}"


def block(data: dict | None) -> str:
    if not data:
        return ""
    bereich = {11: "Jugend und Familie", 12: "Schule und Bildung"}
    zeilen = [f"- Teilhaushalt {s['sub_budget_no']} ({bereich.get(s['sub_budget_no'], '')}), "
              f"Bericht zum {_datum(s['as_of'])}: Auszahlungen für Investitionen {s['budget_year']} "
              f"geplant {geld.de_mio(s['planned'])}, Prognose bis Jahresende {s['budget_year']} "
              f"{geld.de_mio(s['forecast'])}" for s in data["summen"]]
    for z in data["zeilen"]:
        notiz = (z.get("note") or "").strip()
        if len(notiz) > _NOTIZ:
            notiz = notiz[:_NOTIZ].rsplit(" ", 1)[0] + " …"
        art = "Einzahlung" if z["kind"] == "E" else "Auszahlung"
        zeilen.append(f"- {z['name']}" + (f" ({z['measure_no']})" if z.get("measure_no") else "")
                      + f", {art}, Bericht zum {_datum(z['as_of'])}: Ansatz {z['budget_year']} "
                      f"{geld.de_betrag(z['planned'])}, Prognose Jahresende {z['budget_year']} "
                      f"{geld.de_betrag(z['forecast'])}"
                      + (f". Begründung der Verwaltung: „{notiz}“" if notiz else ""))
    if data.get("weitere"):
        zeilen.append(f"- {data['weitere']} weitere passende Maßnahmen (nicht aufgeführt).")
    return ("\nBUDGETBERICHTE AN DIE FACHAUSSCHÜSSE (Teilfinanzrechnung, Investitionen je\n"
            "Maßnahme). Nur Jugend und Familie (11) sowie Schule und Bildung (12) — für andere\n"
            "Bereiche gibt es solche Berichte nicht. Eine Prognose über dem Ansatz ist meist\n"
            "Geld aus Vorjahren (Ermächtigungsübertragung), keine Überschreitung. Die\n"
            "Begründungen sind Wortlaut der Verwaltung. NIE mit [id]:\n" + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME,
    methode="budget_reports_context",
    erkennen=recognize,
    block=block,
    mixin=Store,
    rang=65,
    grenze=2400,
    probefrage="Wird die Kita Dedestraße dieses Jahr fertig, laut Prognose im Budgetbericht?",
)
