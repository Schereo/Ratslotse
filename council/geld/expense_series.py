"""Die lange Ausgabenreihe seit 1972 — Datensatz 1102.

54 Jahrgänge, eine Zeile je Jahr, eine einzige Größe: was die Stadt in diesem
Jahr ausgegeben hat (``council/expense_series.py``). Sie ist die einzige
Quelle des Bestands, die weiter zurückreicht als die Jahresabschlüsse — die
beginnen 2017. Für „Wie viel gab die Stadt 2005 aus?" gibt es sonst nichts.

DIE NAHT 2009/2010 IST DER GRUND, WARUM DIESE FACETTE EINEN EIGENEN BAUSTEIN
BRAUCHT. Zum 1. Januar 2010 stellte die Stadt von kameraler auf doppische
Buchführung um. Links davon steht das Anordnungssoll des Verwaltungshaushalts,
rechts die ordentlichen Aufwendungen der Gesamtergebnisrechnung — zwei Begriffe
aus zwei Rechnungswesen, die nur zufällig beide „was die Stadt ausgibt" heißen.
Ein Sprachmodell, dem das niemand sagt, rechnet „von 76 auf 850 Millionen" als
eine Entwicklung. Die Übersichtsseite zieht deshalb keine Linie über die Naht
(``NahtSaeulen``), und dieser Baustein schreibt sie an.

ZWEI BEFUNDE GEHÖREN DAZU, beide Eigenschaften der Quelle:

* **2021 widersprechen sich zwei amtliche Veröffentlichungen** (PDF 608,9 gegen
  CSV 613,6 Mio. €). Aufgelöst ist der Fall — die CSV-Zeile widerspricht ihrer
  eigenen Pro-Kopf-Spalte, der PDF-Wert steht so im Jahresabschluss —, aber
  still korrigiert wird er nicht: Der andere Wert steht als
  ``conflict_amount`` daneben, und der Baustein nennt ihn.
* **Das jüngste Jahr gibt es hier vor seinem Jahresabschluss.** Tabelle 1102
  führt 2025 bereits, der Abschluss 2025 wird frühestens Mitte 2026
  beschlossen. Diese Zahl ist deshalb an einer Stelle aktueller als jede
  andere im Bestand — und trägt eine Probe weniger.

KEINE INFLATIONSBEREINIGUNG, und das ist keine Lücke, sondern eine Angabe: Ein
Anstieg kann auch auf höhere Preise oder Tarifabschlüsse zurückgehen. Steht das
nicht dabei, liest sich die Reihe als Leistungsausweitung.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from kern.dbfehler import tabelle_fehlt

NAME = "expense_series"

#: Ein Geld-Anker aus dem Wortlaut selbst — für die Fälle, in denen weder
#: ``plan`` noch ``ist`` erkannt wurde.
#:
#: „gab … aus" steht mit dabei, und das ist ein gemessener Fund: „Wie viel gab
#: die Stadt 2005 aus?" ist die Musterfrage dieser Facette und trug bis dahin
#: keinen einzigen Treffer — ``_F_PLAN`` in ``qa.py`` kennt „gibt … aus" und
#: „geben … aus", aber nicht die Vergangenheitsform, und ohne „ausgab" als
#: Wortstamm greift auch dieses Muster nicht.
_GELD = re.compile(
    r"ausgab|einnahm|haushalt|\betat\b|budget|aufwend|gab[^.?!]{0,30}\baus\b")

#: Die Langzeit-Frage. „im laufe", „ueber die jahre" als Wendung, weil die
#: Einzelwörter nichts aussagen.
_LANGZEIT = re.compile(
    r"\bseit\b|entwickl|langfristig|ueber die jahre|jahrzehnt|historisch|"
    r"frueher|damals|verlauf|im laufe|gestiegen|gewachsen|verdoppelt|"
    r"verdreifacht|vervielfacht")

#: Ein Jahr, das VOR den Jahresabschlüssen liegt (die beginnen 2017). Fragt
#: jemand nach 2005, ist diese Reihe die einzige Quelle — dann braucht es kein
#: Langzeit-Wort mehr, die Jahreszahl ist eines.
_ALTES_JAHR = re.compile(r"\b(?:19\d\d|20(?:0\d|1[0-6]))\b")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    """Geld-Anker UND Langzeit-Frage — beides.

    Ohne Geld-Anker zöge „Wie haben sich die Fahrgastzahlen entwickelt?" eine
    Ausgabenreihe in eine Frage nach dem Nahverkehr; ohne Langzeit-Wort hinge
    sie an „Was kostet die Feuerwehr?", wo eine Gesamtsumme der Stadt nichts
    beantwortet. ``rang`` 900 stellt sie hinter die alten Facetten: Sie ist
    Hintergrund für deren Zahlen, nicht ihr Ersatz.

    Als Anker zählt ``plan`` und NICHT ``ist``, und das ist ein gemessener
    Fund: ``ist`` wird in ``qa.py`` auch von der Warum-Regel gesetzt, ohne dass
    im Wortlaut Geld vorkäme. „Warum ist die Grundsteuer gestiegen?" trug damit
    einen Anker und ein Langzeit-Wort („gestiegen") und zog die
    54-Jahre-Ausgabenreihe in eine Frage nach einer Einnahme.
    """
    if "plan" not in facets and not _GELD.search(text):
        return False
    return bool(_LANGZEIT.search(text) or _ALTES_JAHR.search(text))


class Store:
    """Mixin für ``CouncilStore`` — die lange Reihe, gerafft."""

    def expense_series_context(self, terms: list[str],
                               year: int | None = None) -> dict | None:
        """Anfang, Ende, Jahrzehnt-Stützstellen, Höchstwert — und die Naht.

        Nicht die ganze Reihe: 54 Zeilen wären der halbe Kontext, und die
        Aussage steckt in den Stützstellen. Das gefragte Jahr kommt mit seinen
        beiden Nachbarn dazu — ein einzelner Wert ohne Nachbarn lässt sich
        weder einordnen noch als Ausreißer erkennen.

        ``terms`` bleibt ungenutzt, und das ist kein Versehen: Die Reihe kennt
        keine Bereiche, sie hat je Jahr genau eine Zahl. Ein Begriffs-Abgleich
        hätte hier nichts zu filtern.
        """
        try:
            zeilen = [dict(r) for r in self._conn.execute(
                "SELECT year, accounting_system, amount, source, "
                "conflict_amount, conflict_source, herkunft_id "
                "FROM council_expense_series ORDER BY year")]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not zeilen:
            return None
        nach_jahr = {r["year"]: r for r in zeilen}
        anker_jahr, abweichend = geld.jahrgang(
            self._conn, "council_expense_series", "year", year)
        anker = nach_jahr.get(anker_jahr)
        stuetzen = [nach_jahr[j] for j in (1980, 1990, 2000, 2010, 2020)
                    if j in nach_jahr]
        umbruch = next((r["year"] for r in zeilen
                        if r["accounting_system"] == "doppik"), None)
        nachbarn = [nach_jahr[j] for j in (anker_jahr - 1, anker_jahr, anker_jahr + 1)
                    if j in nach_jahr] if anker_jahr else []
        return {
            "first": zeilen[0], "last": zeilen[-1],
            "peak": max(zeilen, key=lambda r: r["amount"]),
            "supports": stuetzen,
            "asked_year": year, "year_deviates": abweichend,
            "anchor": anker, "neighbours": nachbarn,
            "break_from": umbruch,
            "conflicts": [r for r in zeilen if r["conflict_amount"] is not None],
            "beleg": self._beleg((anker or zeilen[-1]).get("herkunft_id")),
        }


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


def _punkte(zeilen: list[dict]) -> str:
    """„1980: 142,7 Mio. € · 1990: 216,1 Mio. €" — Stützstellen in einer Zeile."""
    return " · ".join(f"{r['year']}: {geld.de_mio(r['amount'])}" for r in zeilen)


def block(daten: dict | None) -> str:
    """Der Prompt-Baustein: die Reihe, und die Naht quer durch sie."""
    if not daten or not daten.get("first"):
        return ""
    erst, letzt, hoch = daten["first"], daten["last"], daten["peak"]
    zeilen = [f"- Anfang und Ende der Reihe: {_punkte([erst, letzt])}"]
    if daten.get("supports"):
        zeilen.append(f"- Dazwischen: {_punkte(daten['supports'])}")
    if hoch["year"] not in (erst["year"], letzt["year"]):
        zeilen.append(f"- Höchster Wert: {_punkte([hoch])}")
    # Die Nachbarjahre nur, wenn wirklich nach einem Jahr gefragt wurde: Ohne
    # Frage ist der Anker das jüngste Jahr, und „um das gefragte Jahr herum"
    # stünde dann über einer Zahl, nach der niemand gefragt hat.
    nachbarn = (daten.get("neighbours") or []) if daten.get("asked_year") else []
    gezeigt = {r["year"] for r in [erst, letzt, hoch]
               + (daten.get("supports") or []) + nachbarn}
    if nachbarn and any(r["year"] not in {erst["year"], letzt["year"]}
                        for r in nachbarn):
        zeilen.append(f"- Um das gefragte Jahr herum: {_punkte(nachbarn)}")
    if daten.get("year_deviates"):
        zeilen.append(f"- Zu {daten['asked_year']} führt die Reihe keine Zeile; "
                      f"das jüngste Jahr ist {letzt['year']}.")
    # Der Widerspruch gehört an SEINE Zahl. Steht das Jahr nicht im Baustein,
    # wäre er eine Warnung vor einem Wert, den niemand sieht — 240 Zeichen, die
    # in jeder Ausgaben-Frage stünden und in fast keiner etwas erklärten.
    for k in daten.get("conflicts") or []:
        if k["year"] not in gezeigt:
            continue
        zeilen.append(
            f"- Für {k['year']} widersprechen sich zwei amtliche "
            f"Veröffentlichungen: {geld.de_mio(k['amount'])} gegen "
            f"{geld.de_mio(k['conflict_amount'])}. Hier steht der erste Wert — "
            "nur er passt zur Pro-Kopf-Spalte derselben Zeile und zum "
            "Jahresabschluss. Nenne beide, wenn du dieses Jahr nennst.")
    naht = ""
    if daten.get("break_from"):
        j = daten["break_from"]
        naht = (f"\nDIE NAHT {j - 1}/{j}: Zum 1. Januar {j} stellte die Stadt "
                f"von der Kameralistik auf die doppelte Buchführung um. Bis "
                f"{j - 1} zählt die Reihe das Anordnungssoll des "
                f"Verwaltungshaushalts, ab {j} die ordentlichen Aufwendungen "
                "der Gesamtergebnisrechnung. Werte von beiden Seiten der Naht "
                "sind NICHT direkt vergleichbar: keine gemeinsame Steigerung, "
                "kein Faktor, kein Durchschnitt über sie hinweg.")
    return (
        f"\nAUSGABEN DER STADT SEIT {erst['year']} (Datensatz 1102 der Stadt) "
        "— die längste Reihe des Bestands, eine Zahl je Jahr. Für die "
        "Entwicklung über die Jahre und für Jahre vor 2017, zu denen es keinen "
        "Jahresabschluss gibt. Es ist die Reihe der Stadt, KEINE "
        "Jahresabschluss-Zahl.\nNICHT INFLATIONSBEREINIGT: Ein Anstieg kann "
        "auf höhere Preise oder Tarifabschlüsse zurückgehen und heißt nicht "
        "automatisch mehr Leistung. NIE mit [id]"
        + _beleg_zeile(daten.get("beleg")) + ":\n"
        + "\n".join(zeilen) + naht + "\n")


FACETTE = geld.Facette(
    name=NAME,
    methode="expense_series_context",
    erkennen=recognize,
    block=block,
    mixin=Store,
    rang=900,
    grenze=1600,
    probefrage="Wie haben sich die Ausgaben der Stadt seit 1972 entwickelt?",
)
