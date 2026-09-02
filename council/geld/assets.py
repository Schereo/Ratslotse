"""Das Anlagevermögen — was die Stadt besitzt, und was es jedes Jahr an Wert
verliert.

Die Facette ``bilanz`` (alt) nennt die Bilanzsumme und das Eigenkapital; sie
sagt nicht, WORAUS das Vermögen besteht. Das steht im Anlagenspiegel des
Jahresabschlusses (``council_fixed_assets``, ``council/anlagenspiegel.py``):
je Vermögensgruppe die Anschaffungskosten, Zugänge, Abgänge, Abschreibungen
und der Buchwert am Jahresende. Dazu die Vermögensgruppen der Bilanz
(``council_vermoegensgruppen``) mit Buchwert und Vorjahr.

Der Buchwert ist KEIN Marktwert: Er ist Anschaffungskosten minus
Abschreibungen. Ein Schulgebäude von 1970 steht mit wenigen Euro in den
Büchern und ist trotzdem eine Schule. Der Baustein sagt das dazu, damit die
Antwort es nicht als „Wert der Stadt“ ausgibt.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from kern.dbfehler import tabelle_fehlt

NAME = "assets"

#: Das Vermögen beim Namen — die Gruppen des Anlagenspiegels und die Frage,
#: was die Stadt besitzt. NICHT „vermoegen“ allein: Das trifft „Vermögens-
#: plan" (Wirtschaftsplan) und „Vermögenslage“ (Beteiligungsbericht).
_VERMOEGEN = re.compile(
    r"anlagevermoegen|sachvermoegen|infrastrukturvermoegen|anlagenspiegel|"
    r"anlagennachweis|buchwert|abschreibungen|"
    r"vermoegen der stadt|staedtisches vermoegen|was besitzt die stadt|"
    r"wie viel ist die stadt wert|wert der (?:strassen|gebaeude|grundstuecke|schulen)|"
    r"(?:strassen|gebaeude|grundstuecke)[^.?!]{0,30}\bwert\b")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    return bool(_VERMOEGEN.search(text))


class Store:
    """Mixin für ``CouncilStore`` — der Anlagenspiegel eines Jahrgangs."""

    def assets_context(self, terms: list[str], year: int | None = None) -> dict | None:
        jahr, abweichend = geld.jahrgang(self._conn, "council_fixed_assets", "year", year)
        if jahr is None:
            return None
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT year, nr, label, cost_closing, additions, disposals, depreciation, "
                "depreciation_closing, book_value, herkunft_id FROM council_fixed_assets "
                "WHERE year = ? ORDER BY nr", (jahr,))]
            gruppen = [dict(r) for r in self._conn.execute(
                "SELECT group_name, book_value, book_value_prior_year FROM "
                "council_vermoegensgruppen WHERE year = ? ORDER BY book_value DESC", (jahr,))]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not rows:
            return None
        # Die Hauptgruppen (nr ohne Punkt) tragen die Summen; darunter die
        # größten Untergruppen — was Straßen, Gebäude und Grundstücke wert sind.
        haupt = [r for r in rows if r["nr"] and "." not in str(r["nr"])]
        unter = sorted((r for r in rows if r["nr"] and "." in str(r["nr"])
                        and r.get("book_value")),
                       key=lambda r: -(r["book_value"] or 0))[:6]
        gesamt = sum((r.get("book_value") or 0) for r in haupt)
        abschreibung = sum((r.get("depreciation") or 0) for r in haupt)
        zugang = sum((r.get("additions") or 0) for r in haupt)
        return {"year": jahr, "year_deviates": abweichend, "asked_year": year,
                "total_book_value": gesamt, "depreciation": abschreibung, "additions": zugang,
                "main": haupt, "largest": unter, "groups": gruppen[:6],
                "beleg": self._beleg(rows[0].get("herkunft_id"))}


def _zeile(r: dict) -> str:
    teile = [f"Buchwert {geld.de_mio(r.get('book_value'))}"]
    if r.get("additions"):
        teile.append(f"Zugänge {geld.de_mio(r['additions'])}")
    if r.get("depreciation"):
        teile.append(f"Abschreibung {geld.de_mio(abs(r['depreciation']))}")
    return f"- {str(r.get('label') or '').strip()}: " + ", ".join(teile)


def block(data: dict | None) -> str:
    if not data or not data.get("main"):
        return ""
    zeilen = [f"- Anlagevermögen gesamt zum 31.12.{data['year']}: "
              f"{geld.de_mio(data['total_book_value'])} Buchwert; Abschreibungen im Jahr "
              f"{geld.de_mio(abs(data['depreciation']))}, Zugänge {geld.de_mio(data['additions'])}"]
    zeilen += [_zeile(r) for r in data["main"]]
    if data.get("largest"):
        zeilen.append("- Die größten Posten darin:")
        zeilen += ["  " + _zeile(r) for r in data["largest"]]
    if data.get("groups"):
        zeilen.append("- Vermögensgruppen der Bilanz (Buchwert, Vorjahr): " + "; ".join(
            f"{g['group_name']} {geld.de_mio(g['book_value'])}"
            + (f" (Vorjahr {geld.de_mio(g['book_value_prior_year'])})"
               if g.get("book_value_prior_year") is not None else "")
            for g in data["groups"]))
    if data.get("year_deviates"):
        zeilen.append(f"- ACHTUNG: Einen Anlagenspiegel {data['asked_year']} gibt es nicht; "
                      f"oben steht {data['year']}. Sag das dazu.")
    return (f"\nANLAGEVERMÖGEN DER STADT {data['year']} (Anlagenspiegel des "
            "Jahresabschlusses, Kernverwaltung).\nNutze das, wenn gefragt ist, was die "
            "Stadt besitzt, was ihre Straßen, Gebäude oder Grundstücke wert sind oder "
            "wie hoch die Abschreibungen sind. BUCHWERT IST KEIN MARKTWERT: "
            "Anschaffungskosten minus Abschreibungen — ein altes Schulgebäude steht "
            "mit wenigen Euro in den Büchern. Ohne die Eigenbetriebe (Gebäudewirtschaft "
            "hält die Schulen). Nie mit [id] zitieren"
            + geld.beleg_text(data.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="assets_context", erkennen=recognize, block=block,
    mixin=Store, rang=40,
    # Drei Hauptgruppen, sechs Posten, sechs Bilanzgruppen: 2.256 Zeichen an der dev-Kopie (2024).
    grenze=2_500,
    probefrage="Wie hoch ist das Anlagevermögen der Stadt Oldenburg?",
)
