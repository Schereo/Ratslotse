"""Die einzelnen Nachbewilligungen — welche Vorlage wie viel Geld außerhalb des
Haushalts bewilligt hat.

Die Facette ``supplementary_approvals`` (alt) nennt die SUMME je Jahr aus dem
Rechenschaftsbericht — wie viel insgesamt über- und außerplanmäßig bewilligt
wurde, und von wem. Sie sagt nicht, WOFÜR. Das steht in den Vorlagen selbst
(``council_supplementary_approvals``, ``scripts/ingest_nachbewilligungen.py``):
je Beschluss Titel, Betrag, Art (über- oder außerplanmäßig, Verpflichtungs-
ermächtigung) und ob der Rat ihn beschlossen hat.

Beide Facetten feuern bei „Nachbewilligung“ gemeinsam — die eine liefert die
Summe, diese die Posten; zwei Hälften derselben Antwort.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from kern.dbfehler import tabelle_fehlt

NAME = "approvals"

_BEWILLIGUNG = re.compile(
    r"ueberplanmaessig|ausserplanmaessig|nachbewilligung|nachtragsbewilligung|"
    r"nachbewilligt|(?:welche|wofuer|wo)[^.?!]{0,40}(?:bewilligung|bewilligt)|"
    r"bewilligung[^.?!]{0,40}(?:ausserhalb|zusaetzlich|nachtraeglich)")

_ARTEN = {"approval": "Bewilligung", "commitment_authorization": "Verpflichtungsermächtigung",
          "threshold": "Unterrichtung (unter 50.000 €)"}
_KATEGORIEN = {"excess": "überplanmäßig", "unbudgeted": "außerplanmäßig", "both": "über- und außerplanmäßig"}


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    return bool(_BEWILLIGUNG.search(text))


class Store:
    """Mixin für ``CouncilStore`` — die Posten eines Jahrgangs, größte zuerst."""

    def approvals_context(self, terms: list[str], year: int | None = None) -> dict | None:
        jahr, abweichend = geld.jahrgang(self._conn, "council_supplementary_approvals", "year", year)
        if jahr is None:
            return None
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT template_number, year, title, kind, category, amount, decided, "
                "in_plenary, herkunft_id FROM council_supplementary_approvals WHERE year = ? "
                "ORDER BY amount IS NULL, amount DESC", (jahr,))]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not rows:
            return None
        # Die Begriffe der Frage ziehen passende Posten nach vorn („Klävemann“,
        # „Feuerwehr“); ohne Treffer bleiben die größten.
        treffer = [r for r in rows if self._trifft(r.get("title"), terms)]
        gewaehlt = (treffer + [r for r in rows if r not in treffer])[:8]
        summe = sum((r.get("amount") or 0) for r in rows if r.get("kind") == "approval")
        return {"year": jahr, "year_deviates": abweichend, "asked_year": year,
                "count": len(rows), "sum_approvals": summe,
                "items": gewaehlt, "matched": len(treffer),
                "beleg": self._beleg(rows[0].get("herkunft_id"))}


def _posten(r: dict) -> str:
    art = _ARTEN.get(r.get("kind"), r.get("kind") or "")
    kat = _KATEGORIEN.get(r.get("category"), "")
    betrag = geld.de_betrag(r["amount"]) if r.get("amount") is not None else "Betrag nicht im Titel"
    stand = "vom Rat beschlossen" if r.get("decided") else "Beschluss nicht bestätigt"
    titel = re.sub(r"\s*-\s*Beschluss\s*-?\s*$", "", (r.get("title") or "").strip())
    return f"- {betrag} — {titel} (Vorlage {r['template_number']}; {kat} {art}, {stand})"


def block(data: dict | None) -> str:
    if not data or not data.get("items"):
        return ""
    zeilen = [_posten(r) for r in data["items"]]
    kopfzeile = (f"- {data['count']} Vorlagen im Jahr {data['year']}, Bewilligungen mit "
                 f"Betrag zusammen {geld.de_betrag(data['sum_approvals'])}"
                 + (f"; {data['matched']} passen zu den Suchbegriffen und stehen zuerst"
                    if data.get("matched") else "; die größten zuerst"))
    if data.get("year_deviates"):
        zeilen.append(f"- ACHTUNG: Für {data['asked_year']} gibt es keine Nachbewilligungs-"
                      f"Vorlagen im Bestand; oben steht {data['year']}. Sag das dazu.")
    return (f"\nEINZELNE NACHBEWILLIGUNGEN {data['year']} (Vorlagen nach § 117 NKomVG, "
            "Titel und Betrag aus der Vorlage).\nNutze das, wenn gefragt ist, WOFÜR die "
            "Stadt außerhalb des Haushalts Geld bewilligt hat. Eine "
            "Verpflichtungsermächtigung bindet künftige Jahre und gehört in keine "
            "Summe mit den Bewilligungen. Nie mit [id] zitieren"
            + geld.beleg_text(data.get("beleg")) + ":\n" + kopfzeile + "\n"
            + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="approvals_context", erkennen=recognize, block=block,
    mixin=Store, rang=45,
    # Acht Posten mit Titel (bis 150 Zeichen), Kopf und Beleg: an der dev-Kopie gemessen.
    grenze=2_400,
    probefrage="Wofür hat die Stadt 2024 außerplanmäßig Geld bewilligt?",
)
