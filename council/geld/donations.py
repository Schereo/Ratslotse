"""Spenden an die Stadt — die Einnahmeart, die sonst nirgends steht.

Zuwendungen sind Geld- oder Sachspenden an die Stadt; nach § 111 Abs. 8
NKomVG darf die Verwaltung sie nicht allein annehmen. Deshalb erscheint
mehrmals im Jahr der Tagesordnungspunkt „Annahme von Zuwendungen", und nur
über diese Beschlüsse wird die Gesamthöhe öffentlich nachvollziehbar — weder
der Haushaltsplan noch die Ergebnisrechnung weisen Zuwendungen getrennt aus.

**Wer gespendet hat, steht nicht im Bestand, und das ist keine Lücke, die
sich schließt.** Die Namen und die Zwecke stehen ausschließlich in der Anlage
„Zuwendungsliste" der jeweiligen Vorlage; die lesen wir nicht ein. Die
Tabelle hat deshalb gar keine Spalte dafür (``council/store.py``, Kommentar
über ``council_donations``), die API kann keine liefern und die Seite keine
zeigen. Der Baustein sagt das ausdrücklich — nicht als Fußnote, sondern als
Anweisung: Ein Sprachmodell, das eine Spendensumme im Kontext hat und nach
dem „Wer" gefragt wird, füllt die Lücke sonst mit Plausiblem.

Das kostet diese Facette ihren Begriffsfilter: Es gibt in der Tabelle keinen
Text, gegen den sich ``_trifft`` richten ließe. Die Begriffe entscheiden hier
deshalb nur, ob die verworfenen Zeilen mit ihrer Begründung ausgeschrieben
werden — die Summen kommen so oder so.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from kern.dbfehler import tabelle_fehlt
from council.store_basis import StoreBasis

NAME = "donations"

#: „spende" fängt gefaltet auch Spender, spendet und gespendet — das Wort
#: steckt in allen. „sponsor" und „schenkung" stehen daneben, weil beide in
#: Ratsvorlagen für dieselbe Sache benutzt werden.
_SPENDE = re.compile(r"spende|\bsponsor|schenkung|maezen")
#: „Zuwendung" allein feuert NICHT, und das ist gemessen und nicht Geschmack:
#: Das Wort trägt in der Kommunalfinanzierung zwei Bedeutungen, und die
#: häufigere ist die andere — „Zuwendungen des Landes" sind Schlüssel-
#: zuweisungen und gehören der Facette `ausgleich`. Erst zusammen mit dem
#: Annehmen ist es die Spende: So heißt der Tagesordnungspunkt („Annahme von
#: Zuwendungen"), und so fragt auch, wer ihn meint.
_ZUWENDUNG = re.compile(
    r"(annahme|angenommen|erhalten|bekommen|entgegengenommen)[^?.!]{0,25}zuwendung|"
    r"zuwendung[^?.!]{0,25}(annahme|angenommen|erhalten|bekommen|entgegengenommen)")
#: Nach der Ablehnung gefragt? Dann werden die verworfenen Zeilen mit ihrer
#: Begründung ausgeschrieben statt nur gezählt. Geprüft auf den gefalteten
#: Suchbegriffen und nicht mit ``_trifft``: Dessen Kappung auf sechs Zeichen
#: taugt zum Finden, nicht zum Unterscheiden.
_LUECKE = re.compile(
    r"abgelehnt|ablehn|verworfen|\bluecke|widerspruch|fehlen|fehlt|"
    r"nicht enthalten")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    return bool(_SPENDE.search(text) or _ZUWENDUNG.search(text))


class Store(StoreBasis):
    """Mixin für ``CouncilStore`` — die Spendenreihe für den Antwort-Prompt."""

    def donations_context(self, terms: list[str],
                          year: int | None = None) -> dict | None:
        """Angenommene Zuwendungen: das gefragte Jahr, die Reihe, die Lücken.

        Ohne Jahresangabe kommt der jüngste Jahrgang — der läuft in aller
        Regel noch, und der Baustein schreibt das dazu, statt sieben
        Beschlüsse aus sieben Monaten neben zwanzig aus zwölf zu stellen.

        ``terms`` filtert hier NICHTS heraus: Die Tabelle führt weder Gebende
        noch Zweck noch ein empfangendes Amt (Begründung im Modul-Docstring),
        es gibt also keinen Text, gegen den ``_trifft`` laufen könnte. Sie
        entscheiden nur über die Ausführlichkeit der Lücken-Zeilen.
        """
        try:
            jahr, abweichend = geld.jahrgang(
                self._conn, "council_donations", "year", year)
            if jahr is None:
                return None
            reihe = self._conn.execute(
                "SELECT year, COUNT(*) anzahl, SUM(amount) summe "
                "FROM council_donations GROUP BY year ORDER BY year").fetchall()
            groesste = self._conn.execute(
                "SELECT template_number, amount, committee, herkunft_id "
                "FROM council_donations WHERE year = ? "
                "ORDER BY amount DESC LIMIT 1", (jahr,)).fetchone()
            gremien = self._conn.execute(
                "SELECT committee, COUNT(*) anzahl FROM council_donations "
                "WHERE year = ? AND committee IS NOT NULL "
                "GROUP BY committee ORDER BY anzahl DESC", (jahr,)).fetchall()
            luecken = self._conn.execute(
                "SELECT template_number, session_date, reason "
                "FROM council_donations_rejected ORDER BY session_date").fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not reihe or groesste is None:
            return None
        dieses = next((r for r in reihe if r["year"] == jahr), None)
        # Der jüngste Jahrgang ist fast immer ein angefangenes Jahr. Ihn
        # ungekennzeichnet neben volle Jahre zu stellen, erzeugt einen
        # Rückgang, den es nicht gibt (so steht es auch auf der Seite).
        laufend = jahr == max(r["year"] for r in reihe)
        return {
            "year": jahr,
            "anderer_jahrgang": abweichend,
            "laufend": laufend,
            "anzahl": dieses["anzahl"] if dieses else 0,
            "summe": dieses["summe"] if dieses else None,
            "groesste": dict(groesste),
            "gremien": [dict(g) for g in gremien],
            "reihe": [dict(r) for r in reihe],
            "luecken": [dict(z) for z in luecken],
            "luecken_ausschreiben": bool(
                _LUECKE.search(geld.falte(" ".join(terms or [])))),
            "beleg": self._beleg(groesste["herkunft_id"]),
        }


def block(data: dict | None) -> str:
    """Der Baustein — und die Namensregel als Anweisung, nicht als Fußnote."""
    if not data or data.get("summe") is None:
        return ""
    kopf = (f"- {data['year']}: {data['anzahl']} Beschlüsse über zusammen "
            f"{geld.de_euro(data['summe'])}")
    if data.get("gremien"):
        kopf += " (" + ", ".join(f"{x['committee']} {x['anzahl']}"
                                 for x in data["gremien"]) + ")"
    if data["laufend"]:
        kopf += (" — dieses Jahr LÄUFT NOCH und ist nicht mit vollen Jahren "
                 "vergleichbar")
    zeilen = [kopf]
    if data.get("anderer_jahrgang"):
        zeilen.append(f"- Zum gefragten Jahr gibt es keine Beschlüsse im "
                      f"Bestand; die Zahlen oben sind die von {data['year']}.")
    g = data["groesste"]
    zeilen.append(f"- Größte einzelne Vorlage {data['year']}: "
                  f"{geld.de_euro(g.get('amount'))} (Vorlage {g.get('template_number')})"
                  + geld.beleg_text(data.get("beleg")))
    zeilen.append("- Wer entscheidet, hängt an der EINZELNEN Zuwendung: bis "
                  "100 € die Oberbürgermeisterin oder der Oberbürgermeister, bis "
                  "2.000 € der Verwaltungsausschuss, darüber der Rat.")
    ausschreiben = data.get("luecken_ausschreiben") and data.get("luecken")
    # Die Jahresreihe fällt weg, wenn nach den Lücken gefragt wurde: Dann sind
    # die Begründungen die Antwort, und beides zusammen sprengte das
    # Zeichenbudget aller Geld-Bausteine zusammen.
    if not ausschreiben:
        reihe = ", ".join(f"{r['year']}: {geld.de_euro(r['summe'])}"
                          for r in data["reihe"])
        zeilen.append(f"- Summe je Jahr — {reihe}")
    if data.get("luecken"):
        n = len(data["luecken"])
        zeilen.append(f"- NICHT in diesen Summen: {n} Beschlüsse, deren Betrag "
                      "in Vorlage und Protokoll auseinandergeht oder ganz fehlt. "
                      "Sie sind keine Null — die Höhe steht nicht zweifelsfrei "
                      "fest.")
        if ausschreiben:
            for z in data["luecken"][:3]:
                zeilen.append(f"  - Vorlage {z['template_number']}: {z['reason']}")
    return ("\nSPENDEN AN DIE STADT (Ratsbeschlüsse „Annahme von Zuwendungen“, "
            "§ 111\nAbs. 8 NKomVG). Für Fragen nach Spenden, Schenkungen und "
            "Sponsoring: Weder\nHaushaltsplan noch Ergebnisrechnung weisen "
            "Zuwendungen als eigene Einnahmeart\naus — öffentlich wird die Summe "
            "nur über diese Beschlüsse.\nWER GESPENDET HAT UND WOFÜR, WEISS DIESE "
            "QUELLE NICHT: Namen und Zwecke stehen\nallein in der Anlage "
            "„Zuwendungsliste“, die nicht im Bestand ist. Nenne keine\nGebenden, "
            "rate keine und leite auch keine aus dem Zusammenhang ab.\nGezählt "
            "wird, was BESCHLOSSEN wurde, nicht was gebucht ist — keine Position "
            "der\nErgebnisrechnung. NIE mit [id]:\n"
            + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME,
    methode="donations_context",
    erkennen=recognize,
    block=block,
    mixin=Store,
    rang=30,
    grenze=1850,
    probefrage="Wie viel Geld hat die Stadt 2024 an Spenden angenommen?",
)
