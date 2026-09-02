"""Die Gebührensätze — was eine Mülltonne, eine Sperrmüllkarte, ein Meter
Straßenreinigung kostet.

Die Facette ``fees`` (alt, in ``qa.py``) beantwortet, WARUM die Gebühr so hoch
ist: die Bedarfsberechnung, Kosten geteilt durch Menge. Diese hier beantwortet
die Frage davor: WAS es kostet. Quelle ist die Anlage 4 der
Gebührenbedarfsberechnung (``council_fee_rates``, ``council/fees.py``): zwölf
Sätze je Jahrgang, mit Vorjahr und Änderung in Prozent, seit 2023.

Die Sätze haben verschiedene Einheiten — je Liter Behältervolumen, je
Kubikmeter Anlieferung, je Meter Quadratwurzel der Grundstücksfläche, je
Tonne Abfall — und der Baustein schreibt jede dazu. Ohne Einheit liest sich
„0,0323 €“ wie ein Fehler; es ist der Preis eines Liters Restmüll.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from kern.dbfehler import tabelle_fehlt

NAME = "fee_rates"

#: Die Gebühr beim Namen — Tonne, Karte, Anlieferung, Liter, Grundgebühr —
#: oder die Frage, was etwas kostet, das die Stadt per Satzung bepreist.
_SATZ = re.compile(
    r"muelltonne|restmuell|restabfall|biotonne|biomuell|sperrmuell|gruengut|"
    r"grundgebuehr|litergebuehr|liter behaeltervolumen|abfallgebuehr|muellgebuehr|"
    r"strassenreinigungsgebuehr|gebuehrensatz|gebuehrensaetze|"
    r"was kostet[^.?!]{0,40}(?:muell|abfall|tonne|sperrmuell|strassenreinigung)|"
    r"(?:muell|abfall|strassenreinigung)[^.?!]{0,30}(?:teurer|billiger|gestiegen|erhoeht|preis)")

_AREAS = {"waste_collection": "Abfallsammlung", "waste_treatment": "Abfallbehandlung",
          "street_cleaning": "Straßenreinigung"}


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    return bool(_SATZ.search(text))


class Store:
    """Mixin für ``CouncilStore`` — die Sätze eines Jahrgangs mit Vorjahr."""

    def fee_rates_context(self, terms: list[str],
                          year: int | None = None) -> dict | None:
        jahr, abweichend = geld.jahrgang(self._conn, "council_fee_rates", "year", year)
        if jahr is None:
            return None
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT year, key, area, label, amount, unit, prior_year, change_pct, "
                "template_number, herkunft_id FROM council_fee_rates WHERE year = ? "
                "ORDER BY CASE area WHEN 'waste_collection' THEN 0 WHEN 'waste_treatment' "
                "THEN 1 ELSE 2 END, key", (jahr,))]
            spanne = self._conn.execute(
                "SELECT MIN(year), MAX(year) FROM council_fee_rates").fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not rows:
            return None
        return {"year": jahr, "year_deviates": abweichend, "asked_year": year,
                "rates": rows, "series_from": spanne[0], "series_to": spanne[1],
                "beleg": self._beleg(rows[0].get("herkunft_id"))}


def _satz(r: dict) -> str:
    betrag = (f"{r['amount']:,.4f}".rstrip("0").rstrip(".")
              if r["amount"] < 1 else f"{r['amount']:,.2f}")
    betrag = betrag.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    einheit = f" je {r['unit']}" if r.get("unit") and r["unit"] != r["label"] else ""
    zeile = f"- {r['label']} ({_AREAS.get(r['area'], r['area'])}): {betrag} €{einheit}"
    if r.get("prior_year") is not None and r.get("change_pct") is not None:
        vor = (f"{r['prior_year']:,.4f}".rstrip("0").rstrip(".")
               if r["prior_year"] < 1 else f"{r['prior_year']:,.2f}")
        vor = vor.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
        zeile += f" (Vorjahr {vor} €, {geld.de_prozent(r['change_pct'])})"
    return zeile


def block(data: dict | None) -> str:
    if not data or not data.get("rates"):
        return ""
    zeilen = [_satz(r) for r in data["rates"]]
    if data.get("year_deviates"):
        zeilen.append(f"- ACHTUNG: Für {data['asked_year']} gibt es keine Gebührensätze im "
                      f"Bestand (Reihe {data['series_from']}–{data['series_to']}); oben steht "
                      f"{data['year']}. Sag das dazu.")
    return (f"\nGEBÜHRENSÄTZE {data['year']} (Anlage 4 der Gebührenbedarfsberechnung, vom "
            "Rat beschlossen).\nNutze das, wenn jemand fragt, was Müll, Sperrmüll, "
            "Grüngut oder Straßenreinigung KOSTEN — je Satz mit seiner Einheit; ein "
            "Liter Behältervolumen ist kein Liter Müll, sondern das Tonnenvolumen je "
            "Leerung. Die Bedarfsberechnung dahinter (warum so hoch) steht in einem "
            "eigenen Baustein. Nie mit [id] zitieren"
            + geld.beleg_text(data.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="fee_rates_context", erkennen=recognize, block=block,
    mixin=Store, rang=30,
    # Zwölf Sätze mit Vorjahr, Kopf und Beleg: an der dev-Kopie gemessen.
    grenze=1_700,
    probefrage="Was kostet eine Restmülltonne in Oldenburg?",
)
