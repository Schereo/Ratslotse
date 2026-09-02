"""Hebesätze und Gewerbesteuerstatistik — was der Rat beschließt, und wie viele
Betriebe es betrifft.

Zwei Tabellen, eine Frage: „Wie hoch ist die Gewerbesteuer in Oldenburg?" meint
fast nie das Aufkommen (das steht in der Facette ``taxes``), sondern den
**Hebesatz** — den einen Prozentwert, den der Rat mit der Haushaltssatzung
selbst beschließt.

* ``council_tax_rates`` (Tabelle 1105, ``council/steuertabellen.py``): die
  Realsteuer-Hebesätze seit 1980. Neun Zeilen für 45 Jahre, denn die Tabelle
  führt **nur die Änderungsjahre** — das ist eine Treppe, keine Kurve, und
  zwischen zwei Stufen wird nichts interpoliert.
* ``council_trade_tax_statistics`` (Statistik 735 11 des Landesamts,
  ``council/trade_tax_statistics.py``): wie viele Betriebe und
  Betriebsstätten die Gewerbesteuer überhaupt aufbringen. Sie kommt nur mit,
  wenn die Frage danach klingt — sonst stünde neben einem Prozentsatz eine
  zweite Zahlenwelt, die niemand wollte.

DIE ZWEI SÄTZE, OHNE DIE DIE ZAHLEN IRREFÜHREN, stehen im Baustein:

1. **Ein Hebesatz ist kein Aufkommen.** Er wirkt auf eine
   Bemessungsgrundlage, die Bund und Land festlegen — und die kann sich
   gleichzeitig ändern. 2025 ist der Beweis: Der Grundsteuer-B-Satz stieg um
   21 %, das Aufkommen SANK um 4,6 %, weil die Grundsteuerreform alle
   Messbeträge neu festsetzte (``components/haushalt/rate-treppe.tsx`` sagt
   das an derselben Stelle).
2. **Ein Steuermessbetrag ist kein Aufkommen.** Die Statistik misst die
   Veranlagung eines Erhebungsjahres, nicht die Kasse; Messbetrag mal Hebesatz
   lag gegen das kassenmäßige Ist zwischen +27 % und −13 % daneben. Aus ihr
   wird deshalb kein Euro-Betrag gerechnet — sie liefert einen **Nenner**.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld

NAME = "tax_rates"

#: Der Hebesatz beim Namen — und die Frageform, die ihn meint, ohne ihn zu
#: nennen („Warum ist die Grundsteuer gestiegen?"). „grundsteuer a" mit
#: Wortgrenze hinten, sonst zöge „Grundsteuer Aufkommen" die Treppe.
_HEBESATZ = re.compile(
    r"hebesatz|hebesaetze|gewerbesteuersatz|grundsteuersatz|"
    r"grundsteuer [ab]\b|"
    r"(?:grund|gewerbe)steuer[^.?!]{0,40}"
    r"(?:prozent|hoehe\b|hoeher|erhoeh|gesenkt|senkung|angehoben|gestiegen|"
    r"steigt|teurer)|"
    r"(?:erhoeh|gesenkt|angehoben|gestiegen|prozent)[^.?!]{0,40}"
    r"(?:grund|gewerbe)steuer")

#: Die Statistik beim Namen. Diese Wörter kommen sonst nirgends im Bestand vor
#: und brauchen deshalb keinen Steuer-Anker.
_STATISTIK = re.compile(
    r"messbetrag|steuermessbetrag|gewerbesteuerpflichtig|groessenklasse|"
    r"zerlegung|betriebsstaette")

#: „Wie viele Betriebe zahlen Gewerbesteuer?" — die Zählfrage. Sie braucht
#: einen Steuer-Anker: „Wie viele Betriebe gibt es im Fliegerhorst?" ist keine
#: Steuerfrage und hätte sonst eine Veranlagungsstatistik im Kontext.
_BETRIEBE = re.compile(
    r"(?:viele|anzahl|zahl der)[^.?!]{0,40}"
    r"(?:betriebe|unternehmen|firmen|gewerbe\b)")

#: Woran die Store-Methode erkennt, dass die Statistik gefragt ist. Gemessen
#: an den Begriffen, nicht am Wortlaut — die Facette steht dann schon fest, es
#: geht nur noch darum, WAS sie liefert.
_STATISTIK_BEGRIFFE = ("betrieb", "unternehm", "firma", "firmen", "messbetrag",
                       "statistik", "zerleg", "veranlag", "gewerbesteuerpflicht")

#: Die drei Arten in der Reihenfolge, in der der Steckbrief sie zeigt.
_ARTEN = ("Grundsteuer A", "Grundsteuer B", "Gewerbesteuer")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    """Hebesatz- oder Betriebe-Frage?

    ``ausgleich`` feuert bei „hebesatz" ebenfalls (die fiktiven Hebesätze des
    Finanzausgleichs) — das ist gewollt: Der Dämpfer erklärt, warum von einer
    Erhöhung nur ein Teil bei der Stadt bleibt, und diese Facette sagt, wie
    hoch der Satz überhaupt ist. Zwei Hälften derselben Antwort.
    """
    if _HEBESATZ.search(text) or _STATISTIK.search(text):
        return True
    return bool(_BETRIEBE.search(text)) and ("taxes" in facets or "steuer" in text)


class Store:
    """Mixin für ``CouncilStore`` — Hebesätze, und auf Wunsch der Nenner."""

    def tax_rates_context(self, terms: list[str],
                          year: int | None = None) -> dict | None:
        """Die drei Hebesätze mit ihrer Änderungstreppe, dazu die Statistik.

        Geliefert werden **alle drei** Arten und nicht nur die gefragte: Die
        Treppen sind zusammen keine 500 Zeichen, und „Grundsteuer" allein
        trifft A und B gleichermaßen — welche gemeint ist, entscheidet sonst
        ein Begriffs-Abgleich über eine Frage, die er nicht entscheiden kann.

        ``seit`` ist das letzte Jahr, in dem sich der Satz WIRKLICH geändert
        hat. Das ist nicht dasselbe wie die jüngste Zeile: 2025 führt die
        Tabelle alle drei Arten, geändert haben sich dort nur die beiden
        Grundsteuern — die Gewerbesteuer steht seit 2015 auf 439 %. Die
        Unterscheidung kommt aus ``prior_rate`` und ist keine Rechnung.
        """
        try:
            zeilen = [dict(r) for r in self._conn.execute(
                "SELECT year, kind, rate, prior_rate, herkunft_id "
                "FROM council_tax_rates ORDER BY kind, year")]
        except sqlite3.OperationalError:
            return None
        if not zeilen:
            return None
        arten = []
        for art in _ARTEN:
            reihe = [r for r in zeilen if r["kind"] == art]
            if not reihe:
                continue
            stufen = [r for r in reihe
                      if r["prior_rate"] is None or r["rate"] != r["prior_rate"]]
            letzte = stufen[-1] if stufen else reihe[-1]
            eintrag = {"kind": art, "rate": reihe[-1]["rate"],
                       "since": letzte["year"], "prior_rate": letzte["prior_rate"],
                       "stufen": [(r["year"], r["rate"]) for r in stufen]}
            if year is not None:
                galt = [r for r in stufen if r["year"] <= year]
                eintrag["asked_rate"] = galt[-1]["rate"] if galt else None
                eintrag["asked_since"] = galt[-1]["year"] if galt else None
            arten.append(eintrag)
        if not arten:
            return None
        aus = {"kinds": arten, "asked_year": year,
               "series_from": zeilen[0]["year"],
               "beleg": self._beleg(zeilen[-1].get("herkunft_id"))}
        stat = self._trade_tax_statistics(terms, year)
        if stat:
            aus["statistics"] = stat
        return aus

    def _trade_tax_statistics(self, terms: list[str],
                              year: int | None) -> dict | None:
        """Der Nenner — nur wenn die Begriffe ihn verlangen.

        Nur die Zeile für Oldenburg: Die Tabelle führt acht kreisfreie Städte
        (der Städtevergleich ist eine andere Facette), und sieben fremde
        Zeilen neben einem Oldenburger Hebesatz sind Streuung, keine Antwort.
        """
        gefragt = " ".join(geld.falte(w) for w in terms)
        if not any(w in gefragt for w in _STATISTIK_BEGRIFFE):
            return None
        jahr, abweichend = geld.jahrgang(
            self._conn, "council_trade_tax_statistics", "year", year,
            "city = 'Oldenburg'")
        if jahr is None:
            return None
        try:
            r = self._conn.execute(
                "SELECT * FROM council_trade_tax_statistics "
                "WHERE year = ? AND city = 'Oldenburg'", (jahr,)).fetchone()
        except sqlite3.OperationalError:
            return None
        if not r:
            return None
        d = dict(r)
        d["year_deviates"] = abweichend
        d["asked_year"] = year
        d["beleg"] = self._beleg(d.get("herkunft_id"))
        return d


def _beleg_zeile(b: dict | None) -> str:
    """„ — Beleg: Dokument, Stelle". Ohne Fundstelle keine Zahl.

    Ohne das ``as_of`` von ``qa._beleg_text``, und das ist gemessen: Bei den
    Haushalts-Herkünften steht dort die Abgrenzung — bei Tabelle 1105 wörtlich
    derselbe Satz, den der Kopf dieses Bausteins schon als Anweisung führt. Ihn
    ein drittes Mal anzuhängen kostete 230 Zeichen und sagte nichts Neues."""
    if not b:
        return ""
    teile = [str(t) for t in (b.get("label"), b.get("citation")) if t]
    if b.get("page"):
        teile.append(f"S. {b['page']}")
    return f" — Beleg: {', '.join(teile)}" if teile else ""


def _statistik_text(s: dict) -> str:
    """Der Nenner als eigener Absatz — mit seiner Abgrenzung, nie ohne."""
    zeilen = [
        f"- Erfasste Betriebe und Betriebsstätten {s['year']}: "
        f"{geld.de_zahl(s['cases'])}, davon mit positivem Steuermessbetrag "
        f"{geld.de_zahl(s['cases_positive'])}",
    ]
    if s.get("tax_base_eur") is not None:
        zeilen.append(f"- Steuermessbetrag zusammen: "
                      f"{geld.de_mio(s['tax_base_eur'])}")
    if s.get("apportionments") is not None:
        zeilen.append(
            f"- davon zerlegte Betriebsstätten (Firmen mit mehreren Standorten, "
            f"§ 28 GewStG): {geld.de_zahl(s['apportionments'])} Fälle mit "
            f"{geld.de_mio(s.get('apportioned_assessment_eur'))} Messbetrag")
    # Der Verzug steht IMMER dabei, nicht nur bei abweichendem Jahrgang: Neben
    # einer Aufkommensreihe bis 2025 ist ein Nenner von 2021 sonst eine
    # Aktualität, die er nicht hat.
    gefragt = (f"Zu {s['asked_year']} gibt es sie nicht"
               if s.get("year_deviates") else "Jüngeres gibt es nicht")
    zeilen.append(f"- {gefragt}: Eine Veranlagung ist erst nach den "
                  "Betriebsprüfungen endgültig, der Bericht erscheint rund "
                  "fünf Jahre später.")
    return ("\nWIE VIELE BETRIEBE ES SIND (Gewerbesteuerstatistik des "
            "Landesamts für Statistik Niedersachsen, nur Oldenburg).\n"
            "STEUERMESSBETRAG IST NICHT AUFKOMMEN: Gezählt wird die "
            "Veranlagung des Erhebungsjahres, nicht die Kasse. Messbetrag mal "
            "Hebesatz ergibt NICHT das Aufkommen — gemessen lag diese Rechnung "
            "zwischen 27 % zu hoch und 13 % zu niedrig. Rechne daraus keinen "
            "Euro-Betrag. NIE mit [id]" + _beleg_zeile(s.get("beleg")) + ":\n"
            + "\n".join(zeilen) + "\n")


def block(daten: dict | None) -> str:
    """Der Prompt-Baustein: die Treppe, und was ein Hebesatz nicht ist."""
    if not daten or not daten.get("kinds"):
        return ""
    zeilen = []
    for k in daten["kinds"]:
        stufen = ", ".join(f"{r} % ({j})" for j, r in k["stufen"])
        s = f"- {k['kind']}: aktuell {k['rate']} %, unverändert seit {k['since']}"
        if k.get("prior_rate") is not None:
            s += f" (davor {k['prior_rate']} %)"
        zeilen.append(s + f" — alle Änderungen: {stufen}")
    hinweis = ""
    jahr = daten.get("asked_year")
    if jahr is not None:
        galt = [k for k in daten["kinds"] if k.get("asked_rate") is not None]
        if galt:
            wer = ", ".join(f"{k['kind']} {k['asked_rate']} % (beschlossen "
                            f"{k['asked_since']})" for k in galt)
            hinweis = (f"\n- Im Jahr {jahr} galten: {wer}. Die Tabelle führt "
                       f"{jahr} nur dann als eigene Zeile, wenn sich dort etwas "
                       "geändert hat — sonst gilt die letzte Stufe weiter.")
        else:
            hinweis = (f"\n- Für {jahr} gibt es keinen Satz in dieser Quelle: "
                       f"Die Reihe beginnt {daten['series_from']}.")
    kopf = (
        "\nHEBESÄTZE DER REALSTEUERN (Statistisches Jahrbuch, Tabelle 1105) — "
        "die Prozentsätze, die der Rat mit der Haushaltssatzung beschließt.\n"
        "DIE REIHE IST EINE TREPPE: nur die Änderungsjahre; dazwischen gilt "
        "der Satz unverändert weiter. Nichts interpolieren, nichts mitteln.\n"
        "EIN HEBESATZ IST KEIN AUFKOMMEN: Er wirkt auf eine "
        "Bemessungsgrundlage, die Bund und Land festlegen. 2025 stieg der "
        "Grundsteuer-B-Satz um 21 % und das Aufkommen sank trotzdem. Aus einem "
        "Satz nie einen Euro-Betrag rechnen. NIE mit [id]"
        + _beleg_zeile(daten.get("beleg")) + ":\n")
    text = kopf + "\n".join(zeilen) + hinweis + "\n"
    if daten.get("statistics"):
        text += _statistik_text(daten["statistics"])
    return text


FACETTE = geld.Facette(
    name=NAME,
    methode="tax_rates_context",
    erkennen=recognize,
    block=block,
    mixin=Store,
    rang=70,
    grenze=2500,
    probefrage="Wie hoch ist der Hebesatz für die Grundsteuer B?",
)
