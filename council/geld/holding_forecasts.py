"""Die Quartalsberichte der Beteiligungen — Plan und Hochrechnung im laufenden Jahr.

Die Frage „Hält das Klinikum dieses Jahr seinen Plan?" landete bis 11/2026 im
Haushaltsvollzug der Kernverwaltung (``execution``): Dessen harte Wörter
„Quartalsbericht“ und „Hochrechnung“ gehören aber genauso den Berichten der
Geschäftsführungen an den Finanzausschuss. Die Antwort sprach dann über den
Stadthaushalt, wo es um ein Unternehmen ging (gemessen mit „Hochrechnung
Klinikum 2025“).

Diese Facette ist die Gegenrichtung: **ein Unternehmen, seine Stationen im
Jahr** — Plan, jede Hochrechnung mit ihrem Stichtag, daneben der Satz, mit dem
der Bericht selbst sagt, ob der Wirtschaftsplan eingehalten wird
(``council/holding_quarterly.py``).

DREI GRENZEN, DIE IM BAUSTEIN SELBST STEHEN MÜSSEN:

* **Hochrechnung ist kein Ist.** „Stand 30.09.“ ist die Erwartung der
  Geschäftsführung für den 31.12., nicht ein Neunmonatsergebnis. Das Ist steht
  erst im Jahresabschluss, ein bis zwei Jahre später.
* **Mehrere Hochrechnungen stehen nebeneinander.** Eine spätere ersetzt die
  frühere nicht, und der Abstand zwischen zwei Ständen oder zum Abschluss ist
  keine „Fehlprognose“ — die Ursache steht im Bericht, nicht hier.
* **Plan heißt zweierlei.** Ursprünglicher oder geänderter Plan: Die Art steht
  an jedem Wert, und bei einem Widerspruch zwischen Tabelle und Seitentext
  stehen beide da.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld, holding_quarterly
from council.store_basis import StoreBasis
from kern.dbfehler import tabelle_fehlt

NAME = "holding_forecasts"

#: Die Wörter, die NUR diesen Bericht meinen können. Jedes davon braucht ein
#: Unternehmen in der Frage — ohne bleibt es beim Haushaltsvollzug.
_HART = re.compile(
    r"quartalsbericht|\bquartal|hochrechnung|hochgerechnet|"
    r"(?:haelt|halten|einhalten|eingehalten|eingehalt)\b[^.?!]{0,40}\bplan|"
    r"\bplan\b[^.?!]{0,40}(?:haelt|halten|einhalten|eingehalten)|nach plan|"
    r"wirtschaftsplan[^.?!]{0,40}\blaufend\w* jahr")
#: „Wie steht das Klinikum dieses Jahr da?“ — Gegenwart plus ein Finanzwort.
_WEICH = re.compile(
    r"(?:laufend\w* (?:geschaefts|haushalts)?jahr|dieses (?:geschaefts)?jahr|aktuell)"
    r"[^.?!]{0,60}(?:ergebnis|plan|verlust|defizit|fehlbetrag|prognos|erwart)|"
    r"(?:ergebnis|plan|verlust|defizit|fehlbetrag|prognos|erwart)\w*"
    r"[^.?!]{0,60}(?:laufend\w* (?:geschaefts|haushalts)?jahr|dieses (?:geschaefts)?jahr)")
#: So viele Unternehmen höchstens — der Baustein bleibt klein, und wer zwei
#: Unternehmen nennt, will beide.
MAX_FIRMEN = 2


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    return bool(holding_quarterly.firmen_in(text)
                and (_HART.search(text) or _WEICH.search(text)))


def _tag(iso: str) -> str:
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}"


class Store(StoreBasis):
    """Store-Mixin: Plan und Hochrechnungen eines Unternehmens im Jahr."""

    def holding_forecasts_context(self, terms: list[str],
                                  year: int | None = None) -> dict | None:
        firmen = holding_quarterly.firmen_in(geld.falte(" ".join(terms or [])))[:MAX_FIRMEN]
        if not firmen:
            return None
        try:
            ausgabe = []
            jahr_abweichung = False
            for firma in firmen:
                jahr, weicht = geld.jahrgang(
                    self._conn, "council_holding_forecasts", "fiscal_year", year,
                    wo=f"company = '{firma}'")
                if jahr is None:
                    continue
                jahr_abweichung = jahr_abweichung or weicht
                stationen = [dict(r) for r in self._conn.execute(
                    "SELECT as_of, quarter, plan, plan_kind, plan_text, plan_other, "
                    "plan_other_kind, forecast, conflict, deviation_gap, basis, statement, "
                    "template_number, herkunft_id FROM council_holding_forecasts "
                    "WHERE company = ? AND fiscal_year = ? ORDER BY as_of", (firma, jahr))]
                ausgabe.append({"company": firma,
                                "name": holding_quarterly.NAMEN.get(firma, firma),
                                "year": jahr, "stations": stationen,
                                "beleg": self._beleg(stationen[-1]["herkunft_id"])})
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not ausgabe:
            return None
        return {"companies": ausgabe,
                **({"year_asked": year} if jahr_abweichung and year else {})}


_ART = {"original": "Plan", "adjusted": "geänderter Plan", None: "Plan (Art im Bericht nicht genannt)"}


def _station(s: dict, jahr: int) -> str:
    art = _ART.get(s.get("plan_kind"), "Plan")
    zeile = (f"  - Stand {_tag(s['as_of'])} (Vorlage {s['template_number']}): "
             f"{art} {jahr} {geld.de_euro(s['plan'])}, "
             f"Hochrechnung {jahr} {geld.de_euro(s['forecast'])}")
    if s.get("conflict") and s.get("plan_text") not in (None, s["plan"]):
        zeile += (f" — der Seitentext des Berichts nennt den Plan {jahr} mit "
                  f"{geld.de_euro(s['plan_text'])}, die Tabelle mit {geld.de_euro(s['plan'])}")
    elif s.get("conflict") and s.get("deviation_gap"):
        zeile += (f" — die gedruckte Abweichung weicht um "
                  f"{geld.de_euro(abs(s['deviation_gap']))} von der Rechnung ab")
    if s.get("plan_other") is not None:
        zeile += (f"; der Seitentext nennt daneben auch {_ART.get(s['plan_other_kind'], 'Plan')} "
                  f"{jahr} {geld.de_euro(s['plan_other'])}")
    if s.get("statement"):
        zeile += f"; der Bericht schreibt: „{s['statement']}“"
    return zeile


def block(data: dict | None) -> str:
    if not data or not data.get("companies"):
        return ""
    zeilen: list[str] = []
    for c in data["companies"]:
        ziel = ("Gesamtzuschussbedarf (Jahresfehlbetrag vor der Ausgleichszahlung der Stadt, "
                "samt Verzinsung des EWE-Anteils)"
                if any(s["basis"] == "subsidy_need" for s in c["stations"])
                else "Jahresergebnis")
        zeilen.append(f"- {c['name']} — {ziel}, Berichte zum Wirtschaftsjahr {c['year']}"
                      + geld.beleg_text(c.get("beleg")) + ":")
        zeilen += [_station(s, c["year"]) for s in c["stations"]]
    if data.get("year_asked"):
        zeilen.append(f"- ACHTUNG: Für {data['year_asked']} liegt kein Quartalsbericht vor; "
                      "oben stehen die Berichte des jüngsten Jahres. Sag das ausdrücklich dazu "
                      f"und gib die Zahlen nicht für {data['year_asked']} aus.")
    return ("\nQUARTALSBERICHTE DER BETEILIGUNGEN (Berichte der Geschäftsführungen an den "
            "Ausschuss für\nFinanzen und Beteiligungen, Handbuch Beteiligungen S. 32). Die "
            "HOCHRECHNUNG ist die Erwartung der\nGeschäftsführung für den 31. Dezember — "
            "KEIN IST: „Stand 30.09.“ ist kein Neunmonatsergebnis. Das\nIst steht erst im "
            "Jahresabschluss, ein bis zwei Jahre später. Plan und Hochrechnung stehen\n"
            "nebeneinander und werden NIE verrechnet. Mehrere Hochrechnungen eines Jahres "
            "sind\nmehrere Stände derselben Erwartung — keine ersetzt die andere, und ein "
            "Abstand zwischen ihnen\nist keine „Fehlprognose“. Zahlen des Unternehmens, "
            "nicht des Stadthaushalts. Geltung:\nBeteiligungen über 50 % und die "
            "Eigenbetriebe (GSG, GOL und TGO Besitz fehlen im Bericht). Nie mit [id]:\n"
            + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="holding_forecasts_context", erkennen=recognize, block=block,
    mixin=Store, rang=14, grenze=2400,
    probefrage="Hält das Klinikum dieses Jahr seinen Plan laut Quartalsbericht?")
