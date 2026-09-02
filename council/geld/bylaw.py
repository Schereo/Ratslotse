"""Die Haushaltssatzung — der Rahmen, den die Zahlen des Haushalts bekommen.

Der Haushaltsplan sagt, wofür das Geld ausgegeben werden SOLL; die Satzung
sagt, was die Stadt DÜRFTE: die Gesamtbeträge beider Haushalte (§ 1), die
Kreditermächtigung für Investitionen (§ 2), die Verpflichtungsermächtigungen
(§ 3), den Höchstbetrag für Liquiditätskredite (§ 4) und die Hebesätze (§ 5).

ZWEI DINGE MUSS JEDE ANTWORT MITFÜHREN, und beide stehen deshalb im
Baustein und nicht nur hier:

* **Es ist ein Entwurf.** Im Ratsinformationssystem liegen ausschließlich
  Verwaltungsentwürfe — Deckblatt „Verwaltungsentwurf", Sitzungsdatum
  „xx.xx.JJJJ". Die beschlossene Satzung erscheint im Amtsblatt der Stadt,
  nicht im RIS. Jede Zeile trägt darum ``version = 'draft'``, und eine
  Antwort, die das wegließe, machte aus einem Vorschlag der Verwaltung einen
  Ratsbeschluss (``council/budget_bylaw.py``, Modulkopf).
* **„Nicht veranschlagt" ist keine Null.** § 2 steht in jedem gelesenen
  Jahrgang auf null, und die Satzung schreibt dort einen Satz statt einer
  Ziffer. „0 €" wäre die schlechtere Auskunft: Die Stadt hat sich keine
  Kreditermächtigung geben lassen, sie hat nicht null Euro aufgenommen.

Die Hebesätze aus § 5 kommen mit, aber immer mit dem Vorschlags-Vermerk: Was
hier steht, ist der Satz, den die Verwaltung vorgeschlagen hat. Ob der Rat
ihn beschlossen hat, sagt diese Quelle nicht — die geltenden Sätze führt die
Steuer-Schicht. Die Erkennung feuert deshalb auch nicht auf „Hebesatz".
"""
from __future__ import annotations

import re
import sqlite3

from council import geld

NAME = "bylaw"

#: Die Wörter, die nur in dieser Satzung vorkommen.
_HART = re.compile(
    r"haushaltssatzung|kreditermaechtigung|verpflichtungsermaechtigung|"
    r"liquiditaetskredit|kassenkredit|kredite fuer investitionen")
#: „Satzung", „Ermächtigung" und „Höchstbetrag" brauchen einen Haushalts-
#: Anker: Oldenburg hat eine Baumschutzsatzung, eine Gebührensatzung und ein
#: Dutzend andere, und ein Höchstbetrag steht in jeder zweiten davon.
#: (Gefaltet greift `\bsatzung` in „Baumschutzsatzung" ohnehin nicht — die
#: Wortgrenze fehlt dort; die Regel ist trotzdem die richtige.)
_WEICH = re.compile(r"\bsatzung|ermaechtigung|hoechstbetrag")
_ANKER = frozenset(("plan", "ansatz"))


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    if _HART.search(text):
        return True
    return bool(_WEICH.search(text) and (facets & _ANKER))


#: Die drei Ermächtigungen, deren Reihe über die Jahrgänge jemand meinen
#: kann — je Spalte ihr Name und das Muster, das sie in den Suchbegriffen
#: erkennt. Geprüft wird IN DIESER REIHENFOLGE, die engste zuerst; die erste,
#: die trifft, gewinnt.
#:
#: Hier steht bewusst nicht ``_trifft``, obwohl es die Hausmethode ist: Es
#: kappt Begriffe auf sechs Zeichen, und damit sind „Kassenkredit" und
#: „Kreditermächtigung" beide bloß „kredit" — die Auswahl fiel dann auf die
#: Reihe, die zufällig vorn stand (gemessen). Wo es ums UNTERSCHEIDEN geht
#: statt ums Finden, ist die Kappung genau das Falsche.
_REIHEN: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("liquidity_loans", "Höchstbetrag für Liquiditätskredite (§ 4)",
     re.compile(r"liquiditaet|kassenkredit|hoechstbetrag|dispo|zahlungsfaehig")),
    ("commitment_authorizations", "Verpflichtungsermächtigungen (§ 3)",
     re.compile(r"verpflichtungsermaecht|kuenftige jahre|vorbelast")),
    ("investment_loans", "Kredite für Investitionen (§ 2)",
     re.compile(r"kreditermaecht|\bkredit|darlehen|verschuld|aufnehmen|leihen")),
)


def _beleg_text(b: dict | None) -> str:
    if not b:
        return ""
    teile = [str(t) for t in (b.get("label"), b.get("citation")) if t]
    return f" — Beleg: {', '.join(teile)}" if teile else ""


def _betrag(v: float | None) -> str:
    """Beträge der Satzung — mit dem Satz statt der Ziffer für die Null.

    § 2 steht in jedem Jahrgang auf null, und „nicht veranschlagt" ist die
    Auskunft, die dort im Dokument steht (so hält es auch die Seite)."""
    if v is None:
        return "sagt die Satzung nichts dazu"
    if v == 0:
        return "nicht veranschlagt"
    return geld.de_mio(v)


class Store:
    """Mixin für ``CouncilStore`` — die Satzungs-Jahrgänge für den Prompt."""

    def bylaw_context(self, terms: list[str],
                      year: int | None = None) -> dict | None:
        """Die Haushaltssatzung eines Jahrgangs, dazu eine Reihe auf Wunsch.

        Nachträge (``supplement > 0``) liest die Schicht nicht; abgefragt
        wird deshalb nur die Satzung selbst.

        ``terms`` wählen die eine Kennzahl aus, deren Reihe über alle
        Jahrgänge mitkommt — nach der Kreditermächtigung zu fragen und in
        JEDEM Jahrgang „nicht veranschlagt" zu lesen, IST die Antwort. Ohne
        Treffer bleibt es beim gefragten Jahrgang.
        """
        try:
            jahr, abweichend = geld.jahrgang(
                self._conn, "council_budget_bylaw", "year", year,
                wo="supplement = 0")
            if jahr is None:
                return None
            zeile = self._conn.execute(
                "SELECT * FROM council_budget_bylaw "
                "WHERE year = ? AND supplement = 0", (jahr,)).fetchone()
            jahrgaenge = [r[0] for r in self._conn.execute(
                "SELECT year FROM council_budget_bylaw WHERE supplement = 0 "
                "ORDER BY year")]
            gemeint = geld.falte(" ".join(terms or []))
            gewaehlt = next(((spalte, name) for spalte, name, muster in _REIHEN
                             if muster.search(gemeint)), None)
            reihe = [dict(r) for r in self._conn.execute(
                f"SELECT year, {gewaehlt[0]} AS wert FROM council_budget_bylaw "
                "WHERE supplement = 0 ORDER BY year")] if gewaehlt else []
        except sqlite3.OperationalError:
            return None
        if zeile is None:
            return None
        return {
            "year": jahr,
            "anderer_jahrgang": abweichend,
            "zeile": dict(zeile),
            # Eine Lücke ist eine Auskunft: 2022 fehlt im Bestand, und ohne
            # den Satz liest ein Modell die Reihe als geschlossen.
            "fehlend": [j for j in range(min(jahrgaenge), max(jahrgaenge) + 1)
                        if j not in jahrgaenge],
            "reihe": {"name": gewaehlt[1], "werte": reihe} if gewaehlt else None,
            "beleg": self._beleg(zeile["herkunft_id"]),
        }


def block(data: dict | None) -> str:
    """Der Baustein — mit dem Entwurfs-Vermerk vor den Zahlen, nicht danach."""
    if not data or not data.get("zeile"):
        return ""
    z = data["zeile"]
    ergebnis = (z.get("ordinary_revenues") or 0) - (z.get("ordinary_expenses") or 0)
    zeilen = [
        f"- Ergebnishaushalt {data['year']} (§ 1): ordentliche Erträge "
        f"{geld.de_mio(z.get('ordinary_revenues'))}, ordentliche Aufwendungen "
        f"{geld.de_mio(z.get('ordinary_expenses'))} — der Entwurf plant damit "
        f"{'einen Überschuss' if ergebnis >= 0 else 'einen Fehlbetrag'} von "
        f"{geld.de_mio(abs(ergebnis))}" + _beleg_text(data.get("beleg")),
        f"- Finanzhaushalt {data['year']} (§ 1, „Nachrichtlich“): Einzahlungen "
        f"{geld.de_mio(z.get('in_total'))}, Auszahlungen "
        f"{geld.de_mio(z.get('out_total'))}",
        f"- Kredite für Investitionen (§ 2): {_betrag(z.get('investment_loans'))} "
        "— das ist die ERMÄCHTIGUNG, sich zu verschulden, nicht der "
        "Schuldenstand",
        f"- Höchstbetrag für Liquiditätskredite (§ 4): "
        f"{_betrag(z.get('liquidity_loans'))}; Verpflichtungsermächtigungen "
        f"(§ 3): {_betrag(z.get('commitment_authorizations'))}",
    ]
    if data.get("anderer_jahrgang"):
        zeilen.append("- Zum gefragten Jahr liegt keine Satzung im Bestand; die "
                      f"Zahlen sind die des Jahrgangs {data['year']}.")
    saetze = [(n, s) for n, s in (
        ("Grundsteuer A", z.get("property_tax_a_rate")),
        ("Grundsteuer B", z.get("property_tax_b_rate")),
        ("Gewerbesteuer", z.get("trade_tax_rate"))) if s]
    if saetze:
        zeilen.append("- Hebesätze (§ 5), VORGESCHLAGEN: "
                      + ", ".join(f"{n} {s} %" for n, s in saetze)
                      + ". Ob der Rat sie so beschlossen hat, sagt diese Quelle "
                      "nicht.")
    if data.get("reihe"):
        werte = data["reihe"]["werte"]
        einzig = {r["wert"] for r in werte}
        if len(einzig) == 1:
            # Die Kreditermächtigung steht in JEDEM Jahrgang auf null. Sieben
            # gleiche Zeilen aufzuzählen wäre die schlechtere Auskunft als der
            # Satz, der die Gleichheit selbst zur Aussage macht.
            zeilen.append(f"- {data['reihe']['name']} in allen "
                          f"{len(werte)} Jahrgängen {werte[0]['year']}–"
                          f"{werte[-1]['year']}: {_betrag(einzig.pop())}")
        else:
            zeilen.append(f"- {data['reihe']['name']} über die Jahrgänge — "
                          + ", ".join(f"{r['year']}: {_betrag(r['wert'])}"
                                      for r in werte))
    if data.get("fehlend"):
        fehlt = ", ".join(str(j) for j in data["fehlend"])
        zeilen.append(f"- NICHT im Bestand: {fehlt}. Diese Jahrgänge haben "
                      "keinen Wert — weder null noch geschätzt.")
    return (f"\nHAUSHALTSSATZUNG {data['year']} (§§ 1–5). Sie sagt, was die Stadt "
            "DÜRFTE; der\nHaushaltsplan daneben, wofür sie es ausgeben will.\n"
            "ES IST DER VERWALTUNGSENTWURF, KEIN RATSBESCHLUSS, und das gehört "
            "in die\nAntwort: Im Ratsinformationssystem liegen ausschließlich "
            "Entwürfe, die\nbeschlossene Fassung erscheint im Amtsblatt und ist "
            "nicht im Bestand. Schreibe\nalso „die Verwaltung schlägt vor“, nicht "
            "„der Rat hat beschlossen“; was der Rat\ndaraus machte, steht in den "
            "Änderungslisten.\n„Nicht veranschlagt“ ist KEINE Null — die Satzung "
            "schreibt dort einen Satz statt\neiner Ziffer: Die Stadt hat sich die "
            "Ermächtigung nicht geben lassen, nicht\nnull Euro aufgenommen. NIE "
            "mit [id]:\n"
            + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME,
    methode="bylaw_context",
    erkennen=recognize,
    block=block,
    mixin=Store,
    rang=20,
    grenze=1800,
    probefrage="Was steht in der Haushaltssatzung?",
)
