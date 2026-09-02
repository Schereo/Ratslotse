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
    r"abfallwirtschaftsbetrieb|baederbetriebsgesellschaft|baederbetrieb|"
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


class Store:
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
                "duty": _WAS_SIE_TUN.get(enterprise)}


def _beleg_text(b: dict | None) -> str:
    """„ — Beleg: Bäderbetrieb …: Wirtschaftsplan 2026, Beschlussvorschlag".

    Wortgleich mit ``qa._beleg_text``; importieren geht nicht, weil ``qa``
    dieses Paket lädt und nicht umgekehrt."""
    if not b:
        return ""
    teile = [t for t in (b.get("label"), b.get("citation")) if t]
    if b.get("page"):
        teile.append(f"S. {b['page']}")
    if not teile:
        return ""
    as_of = f", Stand {b['as_of']}" if b.get("as_of") else ""
    return f" — Beleg: {', '.join(str(t) for t in teile)}{as_of}"


def _betrag(v: float | None) -> str:
    """Millionen, aber nicht bis zur Unkenntlichkeit.

    ``geld.de_mio`` rundet auf eine Nachkommastelle — der ausgeglichene
    Erfolgsplan des EGH für 2026 (−15.621 €) wird darin zu „-0,0 Mio. €" und
    liest sich wie ein Rundungsfehler statt wie die Punktlandung, die er ist.
    Unter einer Million steht deshalb der volle Betrag."""
    if v is None:
        return "–"
    if abs(v) < 1_000_000:
        return f"{v:,.0f} €".replace(",", ".")
    return geld.de_mio(v)


def _plan_zeilen(p: dict, detail: bool) -> list[str]:
    kopf = (f"- {p['enterprise_name']}, Wirtschaftsplan {p['year']} "
            f"(Vorlage {p['template_number']}): Ergebnis {_betrag(p['result'])}")
    if p["result"] == 0:
        kopf += " (ausgeglichener Plan — der Betrieb plant weder Gewinn noch Verlust)"
    if p.get("prior"):
        kopf += (f"; im Plan {p['prior']['year']} waren es "
                 f"{_betrag(p['prior']['result'])}")
    zeilen = [kopf]
    if not detail:
        return zeilen
    if p.get("duty"):
        zeilen.append(f"  - {p['duty']}")
    if p.get("revenues") is not None and p.get("expenses") is not None:
        zeilen.append(f"  - Erfolgsplan: Erträge {_betrag(p['revenues'])}, "
                      f"Aufwendungen {_betrag(p['expenses'])}")
    else:
        zeilen.append("  - Erträge und Aufwendungen nennt diese Quelle nicht; "
                      "geprüft ist allein das Jahresergebnis.")
    vermoegen = []
    if p.get("capital_plan") is not None:
        vermoegen.append(f"Vermögensplan {_betrag(p['capital_plan'])} "
                         "(Einzahlungen = Auszahlungen)")
    if p.get("investments") is not None:
        vermoegen.append(f"davon Investitionen {_betrag(p['investments'])}")
    if p.get("commitments") is not None:
        vermoegen.append("Verpflichtungsermächtigungen "
                         f"{_betrag(p['commitments'])}")
    if vermoegen:
        zeilen.append("  - " + ", ".join(vermoegen))
    if p.get("ended"):
        zeilen.append("  - Danach legte dieser Betrieb keinen Wirtschaftsplan mehr "
                      "vor — das ist keine Lücke im Bestand, sondern das Ende der "
                      "Reihe.")
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
            "Plan oder seinem\nErgebnis gefragt ist. DAS IST EIN PLAN, KEIN "
            "JAHRESABSCHLUSS — der Vorsatz für\nein Jahr, nicht sein Ergebnis. Und "
            "diese Betriebe stehen NICHT im Kernhaushalt:\nWer dort nach ihnen sucht, "
            "findet sie nicht, und ihre Beträge sind mit denen des\nStadthaushalts "
            "nicht verrechenbar. Die Betriebe untereinander NIE addieren —\nder "
            "Eigenbetrieb Gebäudewirtschaft vermietet der Stadt ihre eigenen Gebäude, "
            "seine\nErträge sind zu großen Teilen Aufwand des Kernhaushalts. Nie mit "
            "[id] zitieren"
            # Der Beleg im Kopf NUR, wenn genau ein Plan dasteht: Jede Zeile ist
            # ein eigenes Papier, und die Herkunft des ersten wäre für die
            # anderen die falsche. Sonst trägt jede Zeile ihre Vorlagennummer.
            + (_beleg_text(data.get("beleg")) if len(data["plans"]) == 1 else "")
            + ":\n" + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="business_plans_context", erkennen=recognize, block=block,
    # 1.357 Zeichen an der dev-Datenbank gemessen (der Überblick über den
    # Jahrgang 2026); die Grenze lässt Luft für drei Betriebe mit Vermögens-
    # plan und Verpflichtungsermächtigungen nebeneinander.
    mixin=Store, rang=50, grenze=1600,
    probefrage="Was steht im Wirtschaftsplan des Abfallwirtschaftsbetriebs?")
