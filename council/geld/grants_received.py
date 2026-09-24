"""Fördermittel von EU und Bund — welche Vorhaben der Stadt von außen Geld bekommen.

Quelle sind die Listen der Geber selbst (``council/foerdermittel.py``, Tabelle
``council_grants_received``): die Liste der Vorhaben der EU-Strukturfonds in
Niedersachsen (EFRE, ESF) und der Förderkatalog des Bundes, gefiltert auf die
Stadt und ihre Gesellschaften.

DREI GRENZEN REISEN MIT und stehen im Baustein:

1. **Bewilligt, nicht ausgezahlt.** Unionsbeitrag bzw. Bundesanteil sind
   Zusagen.
2. **Städtebauförderung und reine Landesprogramme fehlen** — sie stehen in
   keiner der beiden Listen. „Die Stadt bekommt keine Förderung für X" folgt
   aus dem Fehlen einer Zeile also nicht.
3. **Nur die Stadt und ihre Gesellschaften**, keine Vereine oder Unternehmen
   in Oldenburg.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from council.store_basis import StoreBasis
from kern.dbfehler import tabelle_fehlt

NAME = "grants_received"

_FOERDER = re.compile(
    r"foerdermittel|foerdergeld|foerderprogramm|\befre\b|\besf\b|eu mittel|eu gelder|"
    r"strukturfonds|foerderkatalog|"
    r"\b(eu|europa\w*|bund|bundes\w*)\b[^?.!]{0,40}(gefoerdert|foerder|zuschu|finanzier|geld)|"
    r"(gefoerdert|foerderung|zuschu\w*|geld)[^?.!]{0,30}\b(von der eu|vom bund|der eu|des bundes)\b|"
    r"zuschu\w*[^?.!]{0,30}\b(eu|bund|bundes\w*)\b")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    return bool(_FOERDER.search(text))


_ALLERWELT = geld.ALLERWELT | {"foerdermittel", "foerderung", "gefoerdert", "eu", "bund",
                               "bundes", "efre", "esf", "projekte", "projekt", "vorhaben",
                               "bekommt", "bekommen", "erhalten", "welche"}


class Store(StoreBasis):
    """Mixin für ``CouncilStore`` — die geförderten Vorhaben für den Prompt."""

    def grants_received_context(self, terms: list[str], year: int | None = None) -> dict | None:
        """Passende Vorhaben (Titel, Zweck, Empfänger, Programm); ohne Treffer
        die Summen je Geber und die jüngsten Vorhaben."""
        try:
            zeilen = [dict(r) for r in self._conn.execute(
                "SELECT source, recipient, title, summary, funder, program, amount_granted, "
                "       start, end, list_as_of, herkunft_id FROM council_grants_received")]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not zeilen:
            return None
        if year is not None:
            im_jahr = [z for z in zeilen if z["start"] and z["start"][:4] <= str(year)
                       and (not z["end"] or z["end"][:4] >= str(year))]
        else:
            im_jahr = zeilen
        begriffe = [t for t in (terms or []) if geld.falte(t) not in _ALLERWELT
                    and not geld.allerwelt(t)]
        treffer = []
        if begriffe:
            for z in im_jahr:
                n = self._trifft(" ".join(filter(None, (z["title"], z["summary"], z["recipient"],
                                                        z["program"]))), begriffe)
                if n:
                    treffer.append((n, z))
            # Die meisten Treffer zuerst, bei Gleichstand das jüngste Vorhaben.
            treffer.sort(key=lambda x: (-x[0], -int((x[1]["start"] or "0")[:4])))
        auswahl = ([z for _, z in treffer[:5]] if treffer
                   else sorted(im_jahr, key=lambda z: z["start"] or "", reverse=True)[:4])
        summen: dict[str, list[float]] = {}
        for z in zeilen:
            g = "EU" if z["funder"] == "EU" else "Bund"
            s = summen.setdefault(g, [0, 0.0])
            s[0] += 1
            s[1] += z["amount_granted"] or 0
        stand = max((z["list_as_of"] for z in zeilen if z["list_as_of"]), default=None)
        return {
            "summen": summen, "zeilen": auswahl, "treffer": bool(treffer), "year": year,
            "weitere": max(0, len(treffer) - 5), "stand": stand,
            "beleg": self._beleg(auswahl[0]["herkunft_id"]) if auswahl else None,
        }


def block(data: dict | None) -> str:
    if not data:
        return ""
    zeilen = [f"- Bewilligt insgesamt ({g}): {n} Vorhaben, zusammen {geld.de_mio(s)} "
              f"(Listen der Geber, EU-Stand {data['stand'] or 'unbekannt'})"
              for g, (n, s) in sorted(data["summen"].items())]
    if not data["treffer"]:
        zeilen.append("- Zu den Begriffen der Frage passt kein einzelnes Vorhaben. Die jüngsten:")
    for z in data["zeilen"]:
        geber = "EU" if z["funder"] == "EU" else f"Bund ({z['funder']})"
        lauf = f"{(z['start'] or '?')[:4]}–{(z['end'] or '?')[:4]}"
        zeilen.append(f"- {z['title']} — {z['recipient']}, {geber}"
                      + (f", {z['program']}" if z.get("program") else "")
                      + f", Laufzeit {lauf}: bewilligt {geld.de_betrag(z['amount_granted'])}")
    if data.get("weitere"):
        zeilen.append(f"- {data['weitere']} weitere passende Vorhaben (nicht aufgeführt).")
    return ("\nFÖRDERMITTEL VON EU UND BUND je Vorhaben (Liste der Vorhaben EFRE/ESF der NBank,\n"
            "Förderkatalog des Bundes) — nur die Stadt und ihre Gesellschaften. Beträge sind\n"
            "BEWILLIGUNGEN, keine Auszahlungen. Städtebauförderung und reine Landesprogramme\n"
            "stehen in keiner der Listen: Fehlt ein Vorhaben hier, folgt daraus NICHT, dass\n"
            "es keine Förderung bekommt. NIE mit [id]:\n" + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME,
    methode="grants_received_context",
    erkennen=recognize,
    block=block,
    mixin=Store,
    rang=45,
    grenze=1900,
    probefrage="Welche Fördermittel bekommt die Stadt von der EU?",
)
