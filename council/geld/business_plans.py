"""Die Wirtschaftspläne der Eigenbetriebe — der Haushalt neben dem Haushalt.

Der Rat beschließt nicht nur den Stadthaushalt, sondern daneben je einen
Wirtschaftsplan für Gebäudewirtschaft, Abfall, Bäder und Stadion. Diese Zahlen
stehen in KEINEM Haushaltsplan — wer im Kernhaushalt nach der Müllabfuhr
sucht, findet sie deshalb nicht, und bis 09/2026 antwortete die KI-Frage
genau so: mit dem Ergebnishaushalt, in dem der Betrieb nicht vorkommt.

Die Seite dazu ist der dritte Abschnitt von /haushalt/konzern
(`components/haushalt/section-betriebe.tsx`); ihre drei Entscheidungen gelten
hier wörtlich weiter:

* **Nicht addieren, und das laut sagen.** Der Eigenbetrieb Gebäudewirtschaft
  vermietet der Stadt ihre eigenen Gebäude; seine Erträge sind zu großen
  Teilen Aufwand des Kernhaushalts. Eine Summe über die Betriebe zählte
  dasselbe Geld zweimal — herausgerechnet wird die Verflechtung erst im
  Gesamtabschluss (Facette `konzern`).
* **Leere Zellen bleiben leer.** Nur zwei der sieben Betriebe nennen Erträge
  und Aufwendungen in prüfbarer Form; bei den übrigen ist das Jahresergebnis
  die einzige geprüfte Zahl. Eine 0 dort wäre eine Behauptung.
* **Plan ist nicht Abschluss.** Ein Wirtschaftsplan ist der Vorsatz für ein
  Jahr, nicht sein Ergebnis. Was am Ende herauskam, steht im
  Beteiligungsbericht (Facette `companies`) — und weicht regelmäßig ab.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from kern.dbfehler import tabelle_fehlt
from council.store_basis import StoreBasis

NAME = "business_plans"

#: Die Betriebe beim Namen — kuratiert aus `council_business_plans` (sieben
#: Betriebe, Jahrgänge 2019–2026) und `wirtschaftsplan.BETRIEBE`.
#:
#: NICHT DRIN: „stadion" allein (in Oldenburg ein Thema, keine Gesellschaft —
#: „Wie ist der Stand beim Stadion?" ist keine Wirtschaftsplan-Frage),
#: „klinikum" (eine AöR ohne Wirtschaftsplan im Bestand; ihre Zahlen kommen
#: aus dem Beteiligungsbericht), „theater" (das Staatstheater ist Sache des
#: Landes) und „hafen" allein (steckt in „Flughafen").
_BETRIEBE = (
    r"abfallwirtschaftsbetrieb|baederbetriebsgesellschaft|baederbetrieb|\bbaeder\b|"
    r"gebaeudewirtschaft|stadionplanungsgesellschaft|stadion oldenburg|"
    r"stadthafen|eigenbetrieb hafen|\bawb\b|\bbbgo\b|\bbbo\b|\begh\b"
)
#: „Wirtschaft" und „Betrieb" allein sagen nichts über einen Eigenbetrieb —
#: „Wirtschaftsförderung" und „Betriebskosten" sind die häufigeren Wörter.
#: Deshalb ist hier jedes Muster ein ganzes Wort und keine Silbe.
_TRIFFT = re.compile(
    r"eigenbetrieb|wirtschaftsplan|wirtschaftsplaen|erfolgsplan|"
    r"vermoegensplan|betriebsplan|" + _BETRIEBE)

#: Auslöser sind keine Suchbegriffe: „Was planen die Eigenbetriebe?" trüge
#: sonst „Eigenbetriebe" in den Abgleich und träfe über den Wortstamm
#: „eigenb…" nichts — oder, schlimmer, über „betrieb" jeden der sieben und
#: damit drei geratene statt des Überblicks.
_KEIN_SUCHWORT = {
    "eigenbetrieb", "eigenbetriebe", "eigenbetrieben", "wirtschaftsplan",
    "wirtschaftsplaene", "erfolgsplan", "vermoegensplan", "betrieb",
    "betriebe", "betrieben", "stadt", "oldenburg", "plan", "planung",
}

#: Was ein Betrieb tut — wortgleich mit der Seite
#: (`section-betriebe.tsx`, `WAS_SIE_TUN`), damit die Antwort der KI-Frage
#: und die Karte im Haushaltsbereich denselben Satz sagen. Redaktionell und
#: bewusst kurz: Der ausführliche Auftrag steht im Beteiligungsbericht.
_WAS_SIE_TUN = {
    "egh": "Baut und unterhält die städtischen Gebäude — Schulen, Kitas, Rathäuser.",
    "awb": "Müllabfuhr, Straßenreinigung und Winterdienst. Aus diesem Plan werden "
           "die Abfallgebühren kalkuliert.",
    "bbo": "Verwaltet das Bäder-Vermögen und verpachtet es an die "
           "Betriebsgesellschaft; der laufende Betrieb liegt seit 2005 dort.",
    "bbgo": "Betreibt die Bäder — OLantis und die übrigen Standorte.",
    "stadion": "Betreibt das künftige Stadion.",
    "stadion_planung": "Hat den Stadionbau geplant.",
    "hafen": "Betrieb den Stadthafen — Liegeplätze, Anleger und Umschlag.",
}


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    """Fragt der Wortlaut nach einem Eigenbetrieb oder seinem Plan?"""
    return bool(_TRIFFT.search(text))


class Store(StoreBasis):
    """Store-Mixin: die Wirtschaftspläne zu einer Frage."""

    def business_plans_context(self, terms: list[str],
                               year: int | None = None) -> dict | None:
        """Bis zu drei Betriebe zur Frage — oder alle des jüngsten Jahrgangs.

        Ein Betrieb, ein Haushaltsjahr, ein Plan: Zu jedem Treffer kommt das
        Vorjahr als Vergleich, denn ein Ergebnis von −10,1 Mio. € sagt allein
        nicht, ob das viel ist. Endet die Reihe eines Betriebs vor dem
        gefragten Jahr (Stadthafen 2020, Stadionplanung 2024), steht sein
        letzter Plan da — mit dem Jahr, das er trägt.
        """
        try:
            jahr, weicht = geld.jahrgang(
                self._conn, "council_business_plans", "year", year)
            if jahr is None:
                return None
            alle = self._conn.execute(
                "SELECT enterprise, enterprise_name FROM council_business_plans "
                "GROUP BY enterprise ORDER BY enterprise").fetchall()
            woerter = [w for w in terms
                       if geld.falte(w) not in _KEIN_SUCHWORT and len(w) > 2]
            punkte = [(self._trifft(f"{r['enterprise_name']} {r['enterprise']} "
                                    f"{_WAS_SIE_TUN.get(r['enterprise'], '')}", woerter), r)
                      for r in alle]
            # Nur der höchste Punktestand zählt: Sonst ritte bei „Was steht im
            # Wirtschaftsplan des Abfallwirtschaftsbetriebs?" der aufgelöste
            # Stadthafen mit, der ein einziges Wort teilt.
            beste = max((p[0] for p in punkte), default=0)
            treffer = [r for n, r in punkte if n and n == beste]
            if treffer:
                plaene = [p for p in (self._plan(r["enterprise"], jahr)
                                      for r in treffer[:3]) if p]
            else:
                # Der Überblick zeigt den JAHRGANG, nicht den Bestand: Ein
                # Betrieb, den es 2026 nicht mehr gibt, gehört nicht in die
                # Antwort auf „Was planen die Eigenbetriebe?" — sein letzter
                # Plan stünde dort neben lauter aktuellen.
                plaene = [p for p in (self._plan(r["enterprise"], jahr)
                                      for r in alle) if p and p["year"] == jahr]
                # Ohne Begriffstreffer zählt die Größe des Ausschlags: Wer
                # allgemein nach den Eigenbetrieben fragt, will zuerst den,
                # der am weitesten von der Null entfernt ist.
                plaene.sort(key=lambda p: -abs(p["result"]))
            if not plaene:
                return None
            # `year_asked` steht NUR da, wenn der gefragte Jahrgang fehlt —
            # die Konvention aller Geld-Facetten seit 09/2026 (`qa._jahr_hinweis`).
            return {"year": jahr, **({"year_asked": year} if weicht else {}),
                    "plans": plaene, "detail": bool(treffer),
                    "beleg": self._beleg(plaene[0]["herkunft_id"])}
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None

    def _plan(self, enterprise: str, jahr: int) -> dict | None:
        """Der Plan eines Betriebs für das Jahr — oder sein letzter davor."""
        zeile = self._conn.execute(
            "SELECT * FROM council_business_plans WHERE enterprise = ? AND year <= ? "
            "ORDER BY year DESC LIMIT 1", (enterprise, jahr)).fetchone()
        if not zeile:
            return None
        davor = self._conn.execute(
            "SELECT year, result FROM council_business_plans "
            "WHERE enterprise = ? AND year < ? ORDER BY year DESC LIMIT 1",
            (enterprise, zeile["year"])).fetchone()
        letztes = self._conn.execute(
            "SELECT MAX(year) FROM council_business_plans WHERE enterprise = ?",
            (enterprise,)).fetchone()[0]
        return {**dict(zeile), "prior": dict(davor) if davor else None,
                # Endet die Reihe VOR dem Jahrgang des Bereichs, ist das keine
                # Lücke im Bestand: Dann gibt es schlicht keinen weiteren Plan.
                "ended": letztes < jahr,
                "duty": _WAS_SIE_TUN.get(enterprise),
                "actual": self._abschluss(enterprise, zeile["year"])}

    def _abschluss(self, enterprise: str, jahr: int) -> dict | None:
        """Das Ist zum Plan: der geprüfte Jahresabschluss desselben Jahres —
        oder, wenn der noch fehlt, der jüngste davor (``council_enterprise_accounts``,
        seit #981). „Plan ist nicht Abschluss" bleibt die Regel des Bausteins;
        wo der Abschluss vorliegt, steht er als eigene Zeile daneben, damit
        die Antwort auf „Wie lief das Jahr?" nicht beim Vorsatz endet."""
        try:
            jahr_ist = self._conn.execute(
                "SELECT MAX(year) FROM council_enterprise_accounts WHERE enterprise = ? "
                "AND year <= ? AND metric = 'result'", (enterprise, jahr)).fetchone()[0]
            if jahr_ist is None:
                return None
            rows = self._conn.execute(
                "SELECT metric, value, report_year, confirmations, herkunft_id "
                "FROM council_enterprise_accounts WHERE enterprise = ? AND year = ?",
                (enterprise, jahr_ist)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        werte = {r["metric"]: r["value"] for r in rows}
        ergebnis = next((r for r in rows if r["metric"] == "result"), None)
        return {"year": jahr_ist, "same_year": jahr_ist == jahr, "values": werte,
                "report_year": ergebnis["report_year"] if ergebnis else None,
                "confirmations": ergebnis["confirmations"] if ergebnis else None,
                "beleg": self._beleg(ergebnis["herkunft_id"]) if ergebnis else None}


def _plan_zeilen(p: dict, detail: bool) -> list[str]:
    kopf = (f"- {p['enterprise_name']}, Wirtschaftsplan {p['year']} "
            f"(Vorlage {p['template_number']}): Ergebnis {geld.de_betrag(p['result'])}")
    if p["result"] == 0:
        kopf += " (ausgeglichener Plan — der Betrieb plant weder Gewinn noch Verlust)"
    if p.get("prior"):
        kopf += (f"; im Plan {p['prior']['year']} waren es "
                 f"{geld.de_betrag(p['prior']['result'])}")
    zeilen = [kopf]
    if not detail:
        return zeilen
    if p.get("duty"):
        zeilen.append(f"  - {p['duty']}")
    if p.get("revenues") is not None and p.get("expenses") is not None:
        zeilen.append(f"  - Erfolgsplan: Erträge {geld.de_betrag(p['revenues'])}, "
                      f"Aufwendungen {geld.de_betrag(p['expenses'])}")
    else:
        zeilen.append("  - Erträge und Aufwendungen nennt diese Quelle nicht; "
                      "geprüft ist allein das Jahresergebnis.")
    vermoegen = []
    if p.get("capital_plan") is not None:
        vermoegen.append(f"Vermögensplan {geld.de_betrag(p['capital_plan'])} "
                         "(Einzahlungen = Auszahlungen)")
    if p.get("investments") is not None:
        vermoegen.append(f"davon Investitionen {geld.de_betrag(p['investments'])}")
    if p.get("commitments") is not None:
        vermoegen.append("Verpflichtungsermächtigungen "
                         f"{geld.de_betrag(p['commitments'])}")
    if vermoegen:
        zeilen.append("  - " + ", ".join(vermoegen))
    if p.get("ended"):
        zeilen.append("  - Danach legte dieser Betrieb keinen Wirtschaftsplan mehr "
                      "vor — das ist keine Lücke im Bestand, sondern das Ende der "
                      "Reihe.")
    if p.get("actual"):
        a = p["actual"]
        w = a["values"]
        teile = [f"Jahresergebnis {geld.de_betrag(w.get('result'))}"]
        if w.get("revenues") is not None:
            teile.insert(0, f"Umsatzerlöse {geld.de_betrag(w['revenues'])}")
        if w.get("balance_total") is not None:
            teile.append(f"Bilanzsumme {geld.de_betrag(w['balance_total'])}")
        if w.get("equity") is not None:
            teile.append(f"Eigenkapital {geld.de_betrag(w['equity'])}")
        satz = (f"  - IST laut geprüftem Jahresabschluss {a['year']}: " + ", ".join(teile))
        if a["same_year"]:
            satz += f" — gegenüber dem Plan-Ergebnis {geld.de_betrag(p['result'])}"
        else:
            satz += f" (jüngster Abschluss; für {p['year']} liegt noch keiner vor)"
        if a.get("confirmations") and a["confirmations"] > 1:
            satz += f"; {a['confirmations']} Berichte nennen dieselbe Zahl"
        satz += geld.beleg_text(a.get("beleg"))
        zeilen.append(satz)
    return zeilen


def block(data: dict | None) -> str:
    """Der Prompt-Baustein — Betriebe einzeln oder alle des Jahrgangs."""
    if not data or not data.get("plans"):
        return ""
    detail = bool(data.get("detail"))
    zeilen = [z for p in data["plans"] for z in _plan_zeilen(p, detail)]
    if data.get("year_asked"):
        zeilen.append(f"- ACHTUNG: Einen Wirtschaftsplan-Jahrgang {data['year_asked']} "
                      f"gibt es nicht; oben steht der jüngste ({data['year']}). Sag das "
                      f"ausdrücklich dazu und gib die Zahlen nicht für "
                      f"{data['year_asked']} aus.")
    return (f"\nWIRTSCHAFTSPLÄNE DER EIGENBETRIEBE (Jahrgang {data['year']}, je eine "
            "eigene\nRatsvorlage). Nutze das, wenn nach einem Eigenbetrieb, seinem "
            "Plan oder seinem\nErgebnis gefragt ist. DIE ERSTE ZEILE JE BETRIEB IST EIN "
            "PLAN, KEIN\nJAHRESABSCHLUSS — der Vorsatz für ein Jahr, nicht sein Ergebnis; "
            "wo eine\nZeile „IST laut geprüftem Jahresabschluss“ dabeisteht, ist DAS das "
            "Ergebnis. Und "
            "diese Betriebe stehen NICHT im Kernhaushalt:\nWer dort nach ihnen sucht, "
            "findet sie nicht, und ihre Beträge sind mit denen des\nStadthaushalts "
            "nicht verrechenbar. Die Betriebe untereinander NIE addieren —\nder "
            "Eigenbetrieb Gebäudewirtschaft vermietet der Stadt ihre eigenen Gebäude, "
            "seine\nErträge sind zu großen Teilen Aufwand des Kernhaushalts. Nie mit "
            "[id] zitieren"
            # Der Beleg im Kopf NUR, wenn genau ein Plan dasteht: Jede Zeile ist
            # ein eigenes Papier, und die Herkunft des ersten wäre für die
            # anderen die falsche. Sonst trägt jede Zeile ihre Vorlagennummer.
            + (geld.beleg_text(data.get("beleg"), stand=True) if len(data["plans"]) == 1 else "")
            + ":\n" + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="business_plans_context", erkennen=recognize, block=block,
    # 1.357 Zeichen an der dev-Datenbank gemessen (der Überblick über den
    # Jahrgang 2026); die Grenze lässt Luft für drei Betriebe mit Vermögens-
    # plan und Verpflichtungsermächtigungen nebeneinander.
    # Mit der IST-Zeile je Betrieb (Jahresabschluss, seit #981) wächst der
    # Baustein um rund 200 Zeichen je Betrieb: 1.600 für einen Betrieb mit
    # Abschluss, an der dev-Kopie gemessen (02.09.2026).
    mixin=Store, rang=50, grenze=2200,
    probefrage="Was steht im Wirtschaftsplan des Abfallwirtschaftsbetriebs?")
