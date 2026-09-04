"""Der Liquiditätsstand — wie viel Geld die Stadt am Monatsende auf dem Konto hat.

Weder Bilanz noch Jahresabschluss beantworten „Ist Oldenburg flüssig?" für
den laufenden Monat; die Grafik der Verwaltung tut es (``council/
liquidity.py``, monatlich seit 2015). Der Baustein trägt den jüngsten Stand,
Tief und Hoch der letzten zwölf Monate, die Dezember-Stände der letzten
Jahre und den tiefsten Stand der Reihe — und die Grenze: Es ist ein
KONTOSTAND, kein Vermögen; den Rahmen für ein Minus setzt § 4 der
Haushaltssatzung (Facette ``bylaw``).
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from kern.dbfehler import tabelle_fehlt
from council.store_basis import StoreBasis

NAME = "liquidity"

_TRIFFT = re.compile(
    r"liquidit|kontostand|kassenstand|kassenlage|zahlungsfaehig|zahlungsunfaehig|"
    r"fluessige mittel|auf dem konto|geld auf dem konto|geld in der kasse|"
    r"ebbe in der kasse|kassenkredit|liquiditaetskredit|pleite|bankrott|"
    r"(?:wie viel|wieviel) geld hat die stadt")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    """Eigene Wörter; ``bylaw`` (Kassenkredit) und ``kassensicht``
    (liquide) feuern daneben — gewollt, sie sind die Nachbarn."""
    return bool(_TRIFFT.search(text))


_MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
           "September", "Oktober", "November", "Dezember")


def _monat(ym: str) -> str:
    return f"{_MONATE[int(ym[5:7]) - 1]} {ym[:4]}"


class Store(StoreBasis):
    """Mixin für ``CouncilStore`` — der Kontostand."""

    def liquidity_context(self, terms: list[str], year: int | None = None) -> dict | None:
        """Jüngster Stand, letzte zwölf Monate, Dezember-Stände, Tiefpunkt —
        und bei einem gefragten Jahr dessen Monate."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT month, year, amount, as_of, confirmations, revised_from, herkunft_id "
                "FROM council_liquidity ORDER BY month")]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not rows:
            return None
        jahre = sorted({r["year"] for r in rows})
        gefragt = year if year in jahre else None
        abweicht = year is not None and gefragt is None
        letzte12 = rows[-12:]
        im_jahr = [r for r in rows if r["year"] == gefragt] if gefragt else []
        return {
            "year": gefragt or rows[-1]["year"],
            "latest": rows[-1],
            "min12": min(letzte12, key=lambda r: r["amount"]),
            "max12": max(letzte12, key=lambda r: r["amount"]),
            "year_ends": [r for r in rows if r["month"].endswith("-12")][-4:],
            "lowest": min(rows, key=lambda r: r["amount"]),
            "asked_year_rows": im_jahr,
            "coverage": (rows[0]["month"], rows[-1]["month"]),
            "beleg": self._beleg(rows[-1].get("herkunft_id")),
            **({"year_asked": year} if abweicht else {}),
        }


def block(data: dict | None) -> str:
    if not data or not data.get("latest"):
        return ""
    lt = data["latest"]
    zeilen = [f"- Kontostand Ende {_monat(lt['month'])}: {geld.de_mio(lt['amount'])} "
              f"(Grafik mit Stichtag {lt['as_of']})"]
    if data.get("min12") and data.get("max12"):
        zeilen.append(f"- Letzte zwölf Monate: tiefster Stand {geld.de_mio(data['min12']['amount'])} "
                      f"(Ende {_monat(data['min12']['month'])}), höchster "
                      f"{geld.de_mio(data['max12']['amount'])} (Ende {_monat(data['max12']['month'])})")
    if data.get("year_ends"):
        zeilen.append("- Stand jeweils Ende Dezember: " + ", ".join(
            f"{r['year']}: {geld.de_mio(r['amount'])}" for r in data["year_ends"]))
    lo = data.get("lowest")
    if lo:
        zeilen.append(f"- Tiefster Stand der Reihe seit {data['coverage'][0][:4]}: "
                      f"{geld.de_mio(lo['amount'])} Ende {_monat(lo['month'])}"
                      + (" — unter null, also mit Liquiditätskredit überbrückt" if lo["amount"] < 0 else ""))
    for r in data.get("asked_year_rows") or []:
        if r["month"].endswith(("-03", "-06", "-09", "-12")):
            zeilen.append(f"  - Ende {_monat(r['month'])}: {geld.de_mio(r['amount'])}")
    if lt.get("revised_from") is not None:
        zeilen.append(f"- Der Wert für {_monat(lt['month'])} wurde von der Verwaltung korrigiert "
                      f"(früher {geld.de_mio(lt['revised_from'])})")
    if data.get("year_asked"):
        zeilen.append(f"- ACHTUNG: Für {data['year_asked']} liegt keine Grafik vor; oben stehen die "
                      "jüngsten Stände. Sag das dazu.")
    cov = data["coverage"]
    return ("\nLIQUIDITÄTSSTAND (Grafik „Liquiditätsstand zum Monatsende“, die die Verwaltung dem\n"
            f"Finanzausschuss monatlich vorlegt; Monate {cov[0]} bis {cov[1]}). Das ist der\n"
            "KONTOSTAND der Stadt am Monatsende — kein Vermögen, kein Haushaltsergebnis, kein\n"
            "Schuldenstand; nie mit diesen verrechnen. Er schwankt im Jahr um Dutzende\n"
            "Millionen (Steuertermine, Zuweisungen), ein einzelner Monat sagt wenig — nenne\n"
            "das Datum. Den Rahmen für ein Minus setzt § 4 der Haushaltssatzung (Höchstbetrag\n"
            "der Liquiditätskredite, eigener Baustein). Nie mit [id]"
            + geld.beleg_text(data.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="liquidity_context", erkennen=recognize, block=block, mixin=Store,
    rang=15, grenze=1700,
    probefrage="Wie viel Geld hat die Stadt Oldenburg gerade auf dem Konto?")
