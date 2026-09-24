"""Zuschüsse an Dritte — wer aus dem Haushalt Geld bekommt.

Die Übersicht in Anlage 003 des Haushaltsplans (``council/uebersichten.py``,
Tabelle ``council_grants``) führt je Zuschuss die Beschreibung (meist mit dem
Empfänger: „Zuschuss Reparaturrat"), den Ansatz im Planjahr und im Vorjahr,
den Teilhaushalt und das Produkt. Vereine und Träger stehen mit Namen darin
(Tims Entscheidung 24.09.2026); Privatpersonen führt die Übersicht nicht.

ZWEI DINGE REISEN MIT JEDER ZAHL und stehen deshalb im Baustein:

1. **Es ist der Entwurf der Verwaltung.** Die Anlage hängt an der
   Einbringungs-Vorlage; was der Rat später ändert, steht nicht darin.
2. **Ansatz, nicht Auszahlung.** Was tatsächlich geflossen ist, sagt die
   Übersicht nicht.

Erkannt wird am Wort „Zuschuss" (auch „bezuschusst") und an „Zuwendungen an";
„Zuwendung" allein gehört der Facette ``donations`` (Annahme von Spenden) oder
den Landeszuweisungen, nicht dieser.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from council.store_basis import StoreBasis
from kern.dbfehler import tabelle_fehlt

NAME = "grants"

#: Gefaltet heißt es „zuschuss", „zuschuesse", „bezuschusst" — der gemeinsame
#: Stamm ist „zuschu".
_ZUSCHUSS = re.compile(r"zuschu|zuwendungen an\b|foerdert die stadt|"
                       r"von der stadt gefoerdert|freie traeger")
#: Fördermittel VON AUSSEN (EU, Bund) sind die andere Richtung — die gehören
#: der Facette ``grants_received``.
_VON_AUSSEN = re.compile(r"\b(eu|efre|esf|bund|bundes\w*|land)\b[^?.!]{0,30}zuschu|"
                         r"zuschu\w*[^?.!]{0,30}\b(eu|bund|bundes\w*)\b")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    return bool(_ZUSCHUSS.search(text)) and not _VON_AUSSEN.search(text)


#: Wörter, die jede Zuschussfrage trägt und die deshalb keine Zeile auswählen.
_ALLERWELT = geld.ALLERWELT | {"zuschuss", "zuschuesse", "zuschuessen", "bekommt",
                               "bekommen", "erhaelt", "erhalten", "verein", "vereine",
                               "traeger", "welche", "wer", "stadt"}


class Store(StoreBasis):
    """Mixin für ``CouncilStore`` — die Zuschüsse für den Antwort-Prompt."""

    def grants_context(self, terms: list[str], year: int | None = None) -> dict | None:
        """Die Zuschüsse eines Plans, die zu den Suchbegriffen passen.

        Ohne passenden Begriff kommt nur die Summe des Plans — und bei einer
        Rangfrage („Wer bekommt am meisten?") die fünf größten Zuschüsse,
        ausdrücklich als solche benannt."""
        try:
            jahr, abweichend = geld.jahrgang(self._conn, "council_grants", "budget_year", year)
            if jahr is None:
                return None
            zeilen = [dict(r) for r in self._conn.execute(
                "SELECT description, note, product_name, sub_budget_no, amount, amount_prior, "
                "       herkunft_id FROM council_grants WHERE budget_year = ?", (jahr,))]
            summe = self._conn.execute(
                "SELECT COUNT(*), SUM(COALESCE(amount, 0)) FROM council_grants "
                "WHERE budget_year = ?", (jahr,)).fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not zeilen:
            return None
        begriffe = [t for t in (terms or []) if not geld.allerwelt(t)
                    and geld.falte(t) not in _ALLERWELT and not geld.RANG_WORT.match(geld.falte(t))]
        treffer = []
        if begriffe:
            for z in zeilen:
                n = self._trifft(" ".join(filter(None, (z["description"], z["note"], z["product_name"]))),
                                 begriffe)
                if n:
                    treffer.append((n, z))
            treffer.sort(key=lambda x: (-x[0], -(x[1]["amount"] or 0)))
        rang = geld.rangfrage(terms) and not treffer
        auswahl = ([z for _, z in treffer[:6]] if treffer
                   else sorted(zeilen, key=lambda z: -(z["amount"] or 0))[:5] if rang else [])
        return {
            "year": jahr, "anderer_jahrgang": abweichend,
            "anzahl": summe[0], "summe": summe[1],
            "zeilen": auswahl, "rangfolge": rang, "weitere": max(0, len(treffer) - 6),
            "beleg": self._beleg(auswahl[0]["herkunft_id"] if auswahl else zeilen[0]["herkunft_id"]),
        }


def block(data: dict | None) -> str:
    if not data:
        return ""
    j = data["year"]
    zeilen = [f"- Plan {j}: {data['anzahl']} Zuschüsse an Dritte über zusammen "
              f"{geld.de_mio(data['summe'])}" + geld.beleg_text(data.get("beleg"))]
    if data.get("anderer_jahrgang"):
        zeilen.append(f"- Für das gefragte Jahr gibt es keine Übersicht; die Zahlen sind aus dem Plan {j}.")
    if data["rangfolge"]:
        zeilen.append(f"- Die fünf größten Zuschüsse im Plan {j}:")
    for z in data["zeilen"]:
        vorjahr = (f", im Plan {j - 1} {geld.de_betrag(z['amount_prior'])}"
                   if z.get("amount_prior") is not None else "")
        notiz = (z.get("note") or "")[:140].rsplit(" ", 1)[0] + (" …" if len(z.get("note") or "") > 140 else "")
        text = f"{z['description']}" + (f" ({notiz})" if notiz else "")
        zeilen.append(f"- {text}: Plan {j} {geld.de_betrag(z['amount'])}{vorjahr} — Teilhaushalt "
                      f"{z['sub_budget_no']}" + (f", {z['product_name']}" if z.get("product_name") else ""))
    if data.get("weitere"):
        zeilen.append(f"- {data['weitere']} weitere passende Zuschüsse im Plan {j} (nicht aufgeführt).")
    if not data["zeilen"]:
        zeilen.append("- Zu den Begriffen der Frage passt kein einzelner Zuschuss; nenne keinen.")
    return ("\nZUSCHÜSSE AN DRITTE (Übersicht in Anlage 003 des Haushaltsplans). Vereine und\n"
            "Träger stehen dort mit Namen. Es ist der ENTWURF der Verwaltung: Änderungen des\n"
            "Rates stehen nicht darin. Die Beträge sind ANSÄTZE, nicht das tatsächlich\n"
            "Ausgezahlte. NIE mit [id]:\n" + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME,
    methode="grants_context",
    erkennen=recognize,
    block=block,
    mixin=Store,
    rang=40,
    grenze=1800,
    probefrage="Welchen Zuschuss bekommt der Reparaturrat von der Stadt?",
)
