"""Die Einwohnerzahl — der Nenner hinter jeder Pro-Kopf-Zahl.

``council_einwohner`` (aus dem Open-Data-Datensatz 1102, mit dem die Stadt
ihre Aufwendungen je Einwohner*in rechnet) trägt die Einwohnerzahl je Jahr
seit 2010. Die Facetten ``bilanz`` und ``vergleich`` rechnen damit; gefragt
wird sie auch für sich: „Wie viele Einwohner hat Oldenburg?“ — und die Antwort
kam bis 09/2026 aus dem Sitzungswissen, nicht aus einer Zahl.

Die Reihe ist die der Stadt (Melderegister zum Jahresende), nicht die
Fortschreibung des Landesamts — die beiden liegen ein paar Tausend
auseinander, und der Baustein sagt, welche das hier ist.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from kern.dbfehler import tabelle_fehlt

NAME = "population"

#: NICHT „pro Kopf": Die Schulden je Einwohner*in rechnet ``schulden`` selbst,
#: das Vermögen je Kopf ``bilanz`` — dort ist die Einwohnerzahl der Nenner,
#: nicht die Frage. Der Korpus pinnt „Wie viele Schulden hat die Stadt pro
#: Kopf?" auf ``schulden`` allein.
_EINWOHNER = re.compile(
    r"einwohner|einwohnerzahl|bevoelkerung|bevoelkerungszahl|"
    r"wie viele (?:menschen|leute|personen|buerger)[^.?!]{0,30}(?:leb|wohn)")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    return bool(_EINWOHNER.search(text))


class Store:
    """Mixin für ``CouncilStore`` — die Reihe, jüngstes Jahr zuerst."""

    def population_context(self, terms: list[str], year: int | None = None) -> dict | None:
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT year, population, herkunft_id FROM council_einwohner ORDER BY year")]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not rows:
            return None
        gefragt = next((r for r in rows if year is not None and r["year"] == year), None)
        juengst = rows[-1]
        fuenf = next((r for r in rows if r["year"] == juengst["year"] - 5), None)
        return {"latest": juengst, "asked": gefragt, "asked_year": year,
                "five_years_ago": fuenf, "series": rows[-6:], "series_from": rows[0]["year"],
                "beleg": self._beleg(juengst.get("herkunft_id"))}


def block(data: dict | None) -> str:
    if not data or not data.get("latest"):
        return ""
    j = data["latest"]
    zeilen = [f"- Einwohner*innen Ende {j['year']}: {geld.de_zahl(j['population'])}"]
    if data.get("asked") and data["asked"]["year"] != j["year"]:
        a = data["asked"]
        zeilen.append(f"- Für das gefragte Jahr {a['year']}: {geld.de_zahl(a['population'])}")
    elif data.get("asked_year") and not data.get("asked"):
        zeilen.append(f"- Für {data['asked_year']} gibt es keinen Wert in der Reihe "
                      f"({data['series_from']}–{j['year']}); sag das dazu.")
    if data.get("five_years_ago"):
        f = data["five_years_ago"]
        plus = j["population"] - f["population"]
        zeilen.append(f"- Fünf Jahre zuvor ({f['year']}): {geld.de_zahl(f['population'])} — "
                      f"{'plus' if plus >= 0 else 'minus'} {geld.de_zahl(abs(plus))} "
                      f"({geld.de_prozent(plus / f['population'] * 100)})")
    zeilen.append("- Reihe: " + ", ".join(f"{r['year']} {geld.de_zahl(r['population'])}"
                                          for r in data["series"]))
    return ("\nEINWOHNERZAHL (Melderegister der Stadt zum Jahresende, Open-Data-Datensatz "
            "1102 — die Zahl, mit der die Stadt ihre Pro-Kopf-Werte rechnet; die "
            "Fortschreibung des Landesamts liegt etwas darunter).\nNutze das für "
            "„wie viele Einwohner“ und als Nenner je Kopf. Nie mit [id] zitieren"
            + geld.beleg_text(data.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="population_context", erkennen=recognize, block=block,
    mixin=Store, rang=20,
    # Vier Zeilen und ein Beleg: an der dev-Kopie gemessen.
    grenze=800,
    probefrage="Wie viele Einwohner hat Oldenburg?",
)
