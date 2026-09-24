"""Alltagssprache → Haushalts-Facetten und Suchbegriffe.

**Warum es das gibt.** Die Facetten in ``council/qa.py`` und in den Modulen
dieses Pakets erkennen FACHWÖRTER: „Aufwendungen", „Zuweisungen",
„Wirtschaftsplan", „Investitionen". Tim, 24.09.2026: „Die meisten Leute
stellen keine technisch perfekten Fragen: wie viele Schulden gibt es, was
gibt die Stadt aus, hat die Stadt genug Geld für irgendwas, wo kann die Stadt
sparen … Trotzdem müssen wir gute Antworten geben."

Gemessen am selben Tag an 36 Laienfragen durch Lottis echtes Fenster: „Wie
viel Geld hat Oldenburg im Jahr?" zog **keine einzige** Facette, „Verdient
die Stadt mit den Bädern Geld?" den Kultur-Teilhaushalt statt der
Bäder-Wirtschaftspläne („Bädern" ist nicht „Bäder"), „Stimmt es, dass für
Kitas kein Geld mehr da ist?" den Teilhaushalt Jugend und Familie, aber nicht
das Produkt Kindertagesbetreuung (87,9 Mio. €) — „Kita" steht in keinem
Produktnamen.

**Wie es wirkt.** Eine Zeile = ein Wortfeld der Alltagssprache. Trifft sie,
kommen zwei Dinge dazu:

* ``facetten`` — Facetten, die ``qa.geld_facetten`` zusätzlich setzt. Die
  Erkennung der übrigen Facetten bleibt unverändert; hier wird nur ergänzt,
  nie gestrichen.
* ``begriffe`` — Suchbegriffe in der Sprache der Quellen („Kita" →
  „Kindertagesbetreuung"), die ``qa.geld_kontext`` an die Begriffe hängt. Die
  Quellen suchen nach Namen; ein Alltagswort, das in keinem Namen steht,
  findet sonst nichts, auch wenn die Facette stimmt.

**Regeln für neue Zeilen** (``council/CLAUDE.md`` „Deutsche Wörter in
Regexen"): Gesucht wird auf dem GEFALTETEN Text (klein, ä→ae, nur a–z0–9).
Komposita tragen ihr Grundwort hinten („Schwimmbad", „Hallenbad") — deshalb
steht dort keine Wortgrenze vorn. Kurze Wörter bekommen Grenzen („\\bbad\\b"
steckt sonst in „Badezimmer"). Und jede Zeile ist eine Behauptung darüber, wo
im Haushalt etwas steht: lieber eine Zeile zu wenig als eine, die eine
Laienfrage in die falsche Quelle schickt. ``tests/test_geld_alltag.py`` hält
die 36 Fragen fest.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Wortfeld:
    #: Kurzname — für Tests und Messprotokolle.
    name: str
    muster: re.Pattern[str]
    facetten: frozenset[str]
    begriffe: tuple[str, ...] = ()


def _w(name: str, muster: str, facetten: set[str], begriffe: tuple[str, ...] = ()) -> Wortfeld:
    return Wortfeld(name, re.compile(muster), frozenset(facetten), begriffe)


#: Die gepflegte Abbildung. Reihenfolge ist egal — alle Treffer zählen.
WORTFELDER: tuple[Wortfeld, ...] = (
    # „Wie viel Geld hat Oldenburg im Jahr?", „Was gibt die Stadt so aus?",
    # „Wofür geht das Geld drauf?" — die Frage nach dem Haushalt als GANZEM.
    # „haushalt" als Begriff wählt die Summenzeile des Plans
    # (`store.haushalt_fuer_begriffe`); die Teilhaushalte bringt die Übersicht
    # als Seiten-Kernzahl mit (`assistant.SEITEN_KERN`).
    _w("haushalt_ganz",
       # „wie viel Geld HAT/BEKOMMT/BRAUCHT" — nicht „wie viel Geld ist 2024
       # geflossen": Das ist die Kassensicht, und der Korpus pinnt sie ohne
       # Plan (tests/test_qa_geldquellen.py).
       r"(?:wie ?viel|wieviel) geld (?:hat|haben|bekommt|braucht|verbraucht)\b|"
       r"\bgeld\b[^.?!]{0,25}\b(?:im|pro|je|jedes) jahr\b|"
       r"\bgibt\b[^.?!]{0,40}\baus\b|\bausgeb|\bausgaben\b|geld [^.?!]{0,20}\bdrauf\b|"
       r"geht [^.?!]{0,20}\bgeld\b",
       {"plan"}, ("haushalt",)),
    # „Hat die Stadt genug Geld?", „Ist die Stadt pleite?", „kein Geld mehr da"
    # — die Frage nach der Lage: Plan-Ergebnis, Abschluss, Kasse. `pleite`
    # zieht `liquidity` schon selbst (council/geld/liquidity.py).
    _w("finanzlage",
       r"genug geld|kein geld|\bklamm\b|finanzlage|finanziell|\bfinanzen\b|"
       r"steht [^.?!]{0,20}finanziell|ueber die runden|\bpleite\b|"
       r"zahlungsfaehig",
       {"plan", "ist"}, ("haushalt",)),
    # „Was kostet MICH die Stadt?", „Was zahle ich?" — der Haushalt je Kopf.
    # Die Rechnung macht die Einordnung (`assistant._einordnung`), die dafür
    # die Einwohnerzahl braucht. „pro Kopf" steht bewusst NICHT hier: Das
    # rechnen `schulden` und `bilanz` selbst, und der Korpus pinnt „Schulden
    # pro Kopf" auf `schulden` allein (tests/test_geld_population.py).
    _w("mich",
       r"kostet mich|kosten mich|zahle ich|bezahle ich|jeden von uns",
       {"plan", "population"}, ("haushalt",)),
    # „Woher hat die Stadt ihr Geld?", „Wovon lebt die Stadt?" — die
    # Ertragsarten des Plans. Die Begriffe sind die Posten-Namen des
    # Gesamtergebnishaushalts (`council_income_budget`).
    _w("einnahmen",
       r"woher [^.?!]{0,30}\bgeld\b|wovon lebt|\bgeld (?:her|rein)\b|"
       r"\bnimmt [^.?!]{0,25}\bein\b|\beinnahm|\bbekommt [^.?!]{0,25}\bgeld\b",
       # `plan` + „haushalt": die Summe der Erträge des Plans (812,9 Mio. €
       # für 2026). Ohne sie trafen die Posten-Namen unten die Ertragsarten,
       # und „Wie viel nimmt die Stadt 2026 ein?" bekam keine Gesamtsumme
       # mehr (Fakten-Eval 24.09.2026, hh-plan-ertrag-2026-lotti).
       {"ansatz", "taxes", "plan"},
       ("Steuern", "Zuwendungen", "Kostenerstattungen", "öffentlich-rechtliche", "einnahmen",
        "haushalt")),
    # „Bekommt die Stadt Geld vom Land?" — Schlüsselzuweisungen (Ausgleich)
    # und der Posten „Zuwendungen und allgemeine Umlagen".
    _w("land",
       r"\bvom land\b|\bdes landes\b|\bdas land\b[^.?!]{0,30}\b(?:geld|zahlt|gibt)|"
       r"\blandesmittel|\bvom bund\b|\bzuschuss [^.?!]{0,10}\bland",
       {"ansatz", "ausgleich"}, ("Zuwendungen", "Schlüsselzuweisungen")),
    # „Was wird gebaut?", „Warum dauern die Baustellen so lange?" — Plan und
    # Ist der Investitionen und das Investitionsprogramm. KEIN Rangwort als
    # Begriff: Die Überschrift der Investitions-Seite („Was gebaut wird")
    # reist im Suchtext mit, und „Wird was für Schulen gemacht?" bekam damit
    # die fünf größten Vorhaben statt der Schul-Posten (gemessen 24.09.2026).
    # Die größten Vorhaben bringt die Seite selbst mit (`SEITEN_KERN`).
    _w("bauen",
       r"\bgebaut\b|\bbaut\b|\bbauen\b|baustelle|bauprojekt",
       {"investitionen", "gebaut", "measures"}),
    # Bäder: „Bädern", „Schwimmbad", „Hallenbad", „OLantis" — die
    # Wirtschaftspläne der Bäderbetriebe. `\bbaeder\b` in business_plans.py
    # verfehlt den Dativ.
    _w("baeder",
       r"\bbaeder|schwimmbad|schwimmbaeder|hallenbad|freibad|\bolantis",
       {"business_plans"}, ("Bäder",)),
    # Kitas: Das Produkt heißt „Kindertagesbetreuung", der Teilhaushalt
    # „Jugend und Familie" — beides sagt kein Mensch.
    _w("kita",
       r"\bkitas?\b|kindergart|kinderkrippe|\bkrippe|kinderbetreuung|kindertages",
       {"produkte", "plan"}, ("Kindertagesbetreuung", "Kita")),
    # Theater, Museen, Kultur: Das Staatstheater ist Sache des Landes; im
    # Haushalt steht die Kulturförderung und der Teilhaushalt „Kultur, Museen,
    # Sport". „Theater" steht in keinem Produktnamen.
    _w("kultur",
       r"theater|\boper\b|museum|museen|\bkultur|konzert",
       {"produkte"}, ("Kultur",)),
    # „Zahlen wir zu viele Steuern?" — die Steuereinnahmen UND der Vergleich
    # mit den anderen kreisfreien Städten (Hebesätze): Der Maßstab ist die
    # Antwort, die keine Bewertung ist.
    _w("steuern_zahlen",
       r"zahlen wir [^.?!]{0,20}steuer|zu viele? steuer|steuern? (?:so|zu) hoch",
       {"taxes", "vergleich"}, ("steuern",)),
)


def treffer(text: str) -> list[Wortfeld]:
    """Die Wortfelder, die im GEFALTETEN ``text`` stehen."""
    return [w for w in WORTFELDER if w.muster.search(text)]


def facetten(text: str) -> set[str]:
    """Zusätzliche Facetten für den gefalteten ``text``."""
    return {f for w in treffer(text) for f in w.facetten}


def begriffe(text: str) -> list[str]:
    """Zusätzliche Suchbegriffe für den gefalteten ``text``, ohne Dubletten."""
    return list(dict.fromkeys(b for w in treffer(text) for b in w.begriffe))
