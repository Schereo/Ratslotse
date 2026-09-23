"""Kredite und Zinsen — zu welchen Bedingungen die Stadt sich Geld leiht.

Die Facette ``schulden`` sagt, wie hoch die Schulden sind; ``ist`` kennt den
Zinsaufwand des Jahres (Posten 17). Was NEUES Geld kostet und was die
Umschuldungen bringen, steht nur in den Unterrichtungen des Rates nach der
Kreditrichtlinie (``council/loans.py``): Kreditaufnahmen mit Zinssatz,
Umschuldungen mit Volumen, die Zinsersparnis, wo die Verwaltung sie beziffert.

Grenzen, die der Baustein als Anweisung mitführt: Die Konditionen je Darlehen
(Bank, Marge, Laufzeit) stehen in den Anlagen und sind nicht im Bestand; ein
Zinssatz von 0,00 % ist die Innenfinanzierung eines Betriebs durch die
Kernverwaltung, kein Marktzins; bei den Grundgeschäften nennt die Vorlage
keinen Schuldner.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from kern.dbfehler import tabelle_fehlt
from council.store_basis import StoreBasis

NAME = "loans"

_TRIFFT = re.compile(
    r"zins|\bkredit|darlehen|umschuld|prolongation|prolongier|zinsbindung|kapitalmarkt|"
    r"kreditrichtlinie|kreditaufnahme|geliehen|leiht sich|ausleihung|refinanzier|"
    # „Wie viel tilgt die Stadt?" — der Kapitaldienst gehört hierher (s.
    # `_kapitaldienst`), nicht zum Bestand der Schulden.
    r"\btilg|kapitaldienst")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    """Eigene Wörter — ``schulden`` feuert bei „kredit" ebenfalls, gewollt:
    Bestand dort, Bedingungen hier."""
    return bool(_TRIFFT.search(text))


_ART = {"loan": "Kreditaufnahme", "refinancing": "Umschuldung", "prolongation": "Prolongation",
        "disbursement": "Auszahlung einer Ausleihung", "lending": "Ausleihung", "other": "Vorgang"}


class Store(StoreBasis):
    """Mixin für ``CouncilStore`` — die jüngsten Kreditvorgänge."""

    def _kapitaldienst(self) -> dict:
        """Was die Stadt jedes Jahr an Zinsen zahlt und tilgt — Plan und Ist.

        **Warum hier und nicht im Schulden-Baustein.** Der Kopf dieses
        Bausteins schickte das Modell für den Zinsaufwand „in den
        Jahresabschluss" — der aber nur mitkam, wenn die Frage zufällig auch
        ein Ist-Wort trug. „Wie viel Zinsen zahlt die Stadt für ihre
        Schulden?" auf der Schulden-Seite bekam so die Zinssätze einzelner
        Kredite und keinen Jahresbetrag; „Wie viel tilgt die Stadt jedes
        Jahr?" gar nichts (Fakten-Eval 23.09.2026).

        Vier Zahlen, je mit eigenem Jahr und eigener Quelle: der Zinsaufwand
        (Posten 17) laut jüngstem Jahresabschluss und laut jüngstem Plan; die
        Auszahlungen aus Finanzierungstätigkeit — das ist die Tilgung der
        Investitionskredite — laut jüngster Haushaltssatzung und der Saldo
        aus Finanzierungstätigkeit laut jüngster Finanzrechnung. Jede Abfrage
        einzeln abgesichert: Fehlt eine Tabelle, fehlt nur ihre Zeile."""
        aus: dict = {}
        abfragen = {
            "zins_ist": ("SELECT year, result AS wert FROM council_income_statement "
                         "WHERE sub_budget_no IS NULL AND nr = 17 AND result IS NOT NULL "
                         "ORDER BY year DESC LIMIT 1"),
            "zins_plan": ("SELECT year, amount AS wert FROM council_income_budget "
                          "WHERE kind = 'budget' AND nr = 17 AND year = plan_budget_year "
                          "ORDER BY year DESC LIMIT 1"),
            "tilgung_plan": ("SELECT year, out_financing AS wert FROM council_budget_bylaw "
                             "WHERE supplement = 0 AND out_financing IS NOT NULL "
                             "ORDER BY year DESC LIMIT 1"),
            "finanzierung_ist": ("SELECT year, result AS wert FROM council_cash_flow_statement "
                                 "WHERE role = 'balance_financing' AND result IS NOT NULL "
                                 "ORDER BY year DESC LIMIT 1"),
        }
        for schluessel, sql in abfragen.items():
            try:
                r = self._conn.execute(sql).fetchone()
            except sqlite3.OperationalError as fehler:
                if not tabelle_fehlt(fehler) and "no such column" not in str(fehler):
                    raise
                r = None
            if r and r["wert"] is not None:
                aus[schluessel] = {"year": r["year"], "wert": r["wert"]}
        return aus

    def loans_context(self, terms: list[str], year: int | None = None) -> dict | None:
        """Die Posten mit Zinssatz (jüngste zuerst), das Umschuldungsvolumen des
        gefragten/jüngsten Jahres und die letzte bezifferte Ersparnis — und
        der jährliche Kapitaldienst (``_kapitaldienst``)."""
        kapitaldienst = self._kapitaldienst()
        try:
            jahr, abweicht = geld.jahrgang(self._conn, "council_loan_notices", "year", year)
            if jahr is None:
                return {"kapitaldienst": kapitaldienst} if kapitaldienst else None
            rows = [dict(r) for r in self._conn.execute(
                "SELECT i.*, n.period_from, n.period_to FROM council_loan_items i "
                "JOIN council_loan_notices n ON n.template_number = i.template_number "
                "ORDER BY n.period_from DESC, i.template_number DESC, i.seq")]
            notices = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_loan_notices ORDER BY period_from")]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not rows:
            return {"kapitaldienst": kapitaldienst} if kapitaldienst else None
        zins = [r for r in rows if r.get("rate_pct") is not None][:4]
        # Posten, die die Begriffe treffen (Betrieb, Bad, Umschuldung …), sonst
        # die des gefragten Jahres, sonst die jüngsten.
        getroffen = [r for r in rows if terms and self._trifft(
            f"{r['heading']} {r.get('borrower') or ''}", terms)][:3]
        im_jahr = [r for r in rows if r["year"] == jahr][:3]
        posten = getroffen or im_jahr or rows[:3]
        umschuldung = next((r for r in rows if r["kind"] == "refinancing" and r.get("amount")), None)
        ersparnis = [n for n in notices if n.get("interest_saving")]
        beleg_id = (posten[0] if posten else rows[0]).get("herkunft_id")
        return {
            "year": jahr,
            "rates": zins,
            "positions": posten,
            "latest_refinancing": umschuldung,
            "saving": ersparnis[-1] if ersparnis else None,
            "coverage": (notices[0]["period_from"], notices[-1]["period_to"]) if notices else None,
            "beleg": self._beleg(beleg_id),
            "kapitaldienst": kapitaldienst,
            **({"year_asked": year} if abweicht else {}),
        }


def _zeitraum(r: dict) -> str:
    a, b = r.get("period_from") or "", r.get("period_to") or ""
    return a if a == b else f"{a} bis {b}"


def _kapitaldienst_zeilen(k: dict | None) -> list[str]:
    """Zinsen und Tilgung im Jahr — jede Zahl mit Jahr und Quelle."""
    if not k:
        return []
    zeilen = []
    zins = [f"{w} {k[s]['year']}: {geld.de_betrag(k[s]['wert'])}"
            for s, w in (("zins_ist", "laut Jahresabschluss"), ("zins_plan", "geplant für"))
            if k.get(s)]
    if zins:
        zeilen.append("- Zinsaufwand der Kernverwaltung im Jahr (Posten 17 „Zinsen und "
                      "ähnliche Aufwendungen“), " + "; ".join(zins))
    if k.get("tilgung_plan"):
        t = k["tilgung_plan"]
        zeilen.append(f"- Tilgung (Auszahlungen aus Finanzierungstätigkeit) geplant für "
                      f"{t['year']}: {geld.de_betrag(t['wert'])} — laut Haushaltssatzung "
                      f"{t['year']}, Verwaltungsentwurf")
    if zins and k.get("tilgung_plan"):
        # Gemessen (Lotti-Eval `schwer-schuldendienst`, 23.09.2026): Mit beiden
        # Zahlen im Kontext addierte das Modell sie zu einem „Schuldendienst"
        # von 5,4 Mio. € — eine Summe, die in keinem Dokument steht und zwei
        # Zahlenwerke mischt.
        zeilen.append("  Zinsaufwand (Ergebnishaushalt) und Tilgung (Finanzhaushalt) NIE "
                      "zu einem „Schuldendienst“ addieren: Die Summe weist keine Quelle "
                      "aus — nenne beide einzeln und sag, dass die Summe nicht "
                      "ausgewiesen ist.")
    if k.get("finanzierung_ist"):
        f = k["finanzierung_ist"]
        zeilen.append(f"- Saldo aus Finanzierungstätigkeit laut Finanzrechnung {f['year']}: "
                      f"{geld.de_betrag(f['wert'])} (negativ = mehr getilgt als neu "
                      "aufgenommen)")
    return zeilen


def block(data: dict | None) -> str:
    if not data or not (data.get("rates") or data.get("positions")
                        or data.get("kapitaldienst")):
        return ""
    zeilen = _kapitaldienst_zeilen(data.get("kapitaldienst"))
    for r in data.get("rates") or []:
        s = (f"- {_ART.get(r['kind'], r['kind'])} {_zeitraum(r)}"
             + (f", {r['borrower']}" if r.get("borrower") else "")
             + (f", {geld.de_mio(r['amount'])}" if r.get("amount") is not None else "")
             + f": Zinssatz {geld.de_prozent(r['rate_pct'], 2)}")
        if r.get("fixed_years"):
            s += f", Zinsbindung {r['fixed_years']} Jahre"
        if r.get("rate_pct") == 0:
            s += " (Innenfinanzierung durch die Kernverwaltung, kein Marktzins)"
        zeilen.append(s)
    for r in data.get("positions") or []:
        if r in (data.get("rates") or []):
            continue
        zeilen.append(f"- {_ART.get(r['kind'], r['kind'])} {_zeitraum(r)}"
                      + (f", {r['borrower']}" if r.get("borrower") else " (Grundgeschäfte der Stadt und ihrer Betriebe)")
                      + (f": {geld.de_mio(r['amount'])}" if r.get("amount") is not None else ""))
    u = data.get("latest_refinancing")
    if u:
        zeilen.append(f"- Zuletzt umgeschuldet ({_zeitraum(u)}): {geld.de_mio(u['amount'])} Kommunalkredite. "
                      "Diese Kredite laufen in Dreimonats-Tranchen und werden jedes Quartal neu "
                      "ausgeschrieben — Beträge verschiedener Quartale NIE addieren, es ist dasselbe Geld.")
    sp = data.get("saving")
    if sp:
        zeilen.append(f"- Zinsersparnis laut Verwaltung (Umschuldung, Zeitraum {sp['saving_from']} bis "
                      f"{sp['saving_to']}): {geld.de_euro(sp['interest_saving'])} gegenüber herkömmlicher "
                      "Kommunalkreditfinanzierung — Angabe der Vorlage, keine Rechnung von uns")
    if data.get("year_asked"):
        zeilen.append(f"- ACHTUNG: Für {data['year_asked']} liegt keine Unterrichtung vor; oben stehen "
                      f"die jüngsten Vorgänge ({data['year']}). Sag das dazu.")
    cov = data.get("coverage")
    return ("\nKREDITE UND ZINSEN (Unterrichtungen des Rates nach § 8 der Kreditrichtlinie"
            + (f", Berichte {cov[0]} bis {cov[1]}" if cov else "") + ").\n"
            "Zu welchen Bedingungen die Stadt und ihre Eigenbetriebe sich Geld leihen und\n"
            "umschulden. Der SCHULDENSTAND steht in einem eigenen Baustein — nicht\n"
            "verrechnen; Zinsaufwand und Tilgung im Jahr stehen oben, je mit Jahr und\n"
            "Quelle, Plan und Ist nie vermischen. Bank, Marge und Laufzeit je\n"
            "Darlehen stehen in den Anlagen und sind NICHT bekannt; sag das, wenn danach\n"
            "gefragt wird. Nie mit [id]" + geld.beleg_text(data.get("beleg")) + ":\n"
            + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="loans_context", erkennen=recognize, block=block, mixin=Store,
    rang=25, grenze=1800,
    probefrage="Zu welchem Zinssatz hat die Stadt zuletzt einen Kredit aufgenommen?")
