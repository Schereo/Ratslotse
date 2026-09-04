#!/usr/bin/env python3
"""Sucht im Frontend und in der App nach Werten, die es nicht mehr gibt.

**Das Problem.** ``scripts/pruefe_wertreste.py`` fragt von der Datenbank aus:
Kommt jeder gespeicherte Wert im Code noch vor? Die umgekehrte Lücke sieht es
nicht — und die ist die teurere. Benennt ein Schnitt einen Wert um
(``council_budget_amendments_totals.kind`` von ``entwurf`` auf ``draft``)
und zieht das Web-Frontend nicht nach, dann sucht dort weiter jemand
``s.kind === "entwurf"``. Der Vergleich wird nie wahr, die Karte verliert ihre
Zeile, **und nichts schlägt an**: Der Typ ist ``string``, TypeScript ist
zufrieden, die Testfixtures des Backends kennen den neuen Wert und die
Frontend-Tests laufen gegen erfundene Daten.

Genau so standen am 01.09.2026 sieben Stellen tot: die Entwurfs- und
Summenzeilen der Änderungslisten, die Reihenfolge der Verwaltungslisten, die
Einheit „Personen" der Kennzahlen, die Abweichungs-Fahne der Beschlussseite,
der Ratsbeschluss-Kanal der Nachbewilligungen, die drei Anwesenheitsrollen der
Beschlussseite und das Quiz-Gebiet „Thema" — im Web wie in der App.

**Der Ansatz.** Die Migrationspaare in ``council/store.py`` sind die Wahrheit
darüber, was einmal so hieß. Für jedes Paar ``(alt, neu)`` wird gesucht, ob
``alt`` in den Oberflächen noch als **allein stehende Zeichenkette** vorkommt.
Allein stehend heißt: ``"entwurf"``, nicht „Der Entwurf steht im Ratsinfo" —
Anzeigetexte bleiben deutsch und sollen es bleiben.

Was übrig bleibt, ist entweder ein toter Vergleich oder ein Wert, der aus
gutem Grund deutsch ist. Der zweite Fall gehört in :data:`ERLAUBT`, mit
Begründung — die Liste ist die Dokumentation dessen, was der Umbau bewusst
stehen lässt.

Aufruf::

    python scripts/pruefe_alte_werte.py

Exit 1, sobald ein Fund vorliegt.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]

#: Die Oberflächen. Das Backend steht nicht dabei: Dort benennt derselbe
#: Schnitt um, der die Migration schreibt, und die Testsuite deckt es.
QUELLEN = ("web/frontend/app", "web/frontend/components", "web/frontend/lib",
           "ios/Packages", "ios/RatslotseAppTests")
ENDUNGEN = {".ts", ".tsx", ".swift"}

#: Dateien, die nie mitgeprüft werden.
#: ``.test.ts`` sind die vitest-Logiktests neben ihrem Modul. Sie arbeiten mit
#: ERFUNDENEN Nutzlasten — ``{ titel: "x" }`` prüft, dass der Wrapper einen
#: Körper durchreicht, und behauptet nichts über ein Feld im Vertrag. Ein Fund
#: dort wäre immer falsch. Die Browsertests (``.spec.ts``) bleiben drin: Die
#: rufen echte Pfade auf und sollen mitgeprüft werden.
UEBERSPRINGEN = ("node_modules", "web/frontend/lib/api-schema.ts",
                 "web/frontend/ios", "/kommunalwahl/", ".test.ts")

#: Erlaubte Vorkommen: ``wert -> Begründung``. Ein Eintrag hier heißt: Das
#: Wort steht in den Oberflächen, und zwar zu Recht.
ERLAUBT = {
    # Anzeigetexte. Der gespeicherte Wert ist englisch, die Beschriftung
    # daneben deutsch — genau so soll es sein.
    "angenommen": "Beschriftung der Ergebnis-Punkte (council-analysis.tsx)",
    "abgelehnt": "Beschriftung der Ergebnis-Punkte; liest auch RIS-Prosa",
    "vertagt": "Beschriftung der Ergebnis-Punkte",
    "einstimmig": "Beschriftung in VOTE_LABEL/voteLabel",
    "mehrheitlich": "Beschriftung in VOTE_LABEL/voteLabel",
    # Vokabulare, die im Backend (noch) deutsch sind. Wer sie umbenennt,
    # streicht den Eintrag hier — und findet die Oberflächen-Stellen sofort.
    "rat": "Rollen der Haushaltsdebatte und `art` der Personen-Bausteine",
    "verwaltung": "dieselben Rollen; dazu `typ` des Personen-Profils",
    "beratend": "`art` der Personen-Bausteine",
    "beteiligung": "Dateinamen und Prosa der Beteiligungsberichte (das Feld heißt `participation`)",
    "leitung": "Rolle der Haushaltsdebatte",
    "thema": "Pfad-Teil der Link-Vorschau (/preview/thema/…) und `kind` der Nachbarn",
    "stadt": "`entity_key` des Konzerns und `art` der Personen-Bausteine",
    "vorlage": "Zielart des Beleg-Apparats (dokument|datensatz|vorlage|ris|webseite)",
    "gruppe": "Suchwort der Beschluss-Seite, kein gespeicherter Wert",
    "anlage": "Anker-Präfix der Anlagen-Blöcke",
    "liste": "Absatzart des Antwort-Renderers (kopf|unterkopf|liste|text)",
    "leicht": "Quiz-Schwierigkeit — im Backend noch deutsch",
    "unveraendert": "Quellen-Check der Kommunalwahl mit eigenem Vokabular",
    "entwurf": "nur noch in einem Doku-Kommentar in haushalt.ts",
    "schwelle": "nur noch in einem Doku-Kommentar in haushalt.ts",
    "stadtteil": "Pfad-Teil und Feldname der Ortsangabe im E2E-Fixture",
    "unbekannt": "Ersatztext für einen fehlenden Bildnachweis",
    "abgesetzt": "Wortlaut des RIS in `ergebnisArt` — dort steht der Satz, nicht der Wert",
    # Diese sechs sind im Frontend GEWOEHNLICHE Bezeichner — Variablen,
    # Eigenschaften, ein HTML-Attribut. Der Schluessel-Zweig des Musters
    # trifft sie, das Vokabular meint sie nicht.
    "alt": "das `alt`-Attribut eines Bildes",
    "sonstiges": "Themenfeld `policy_field` — bleibt deutsch (das Ortsart-`sonstiges` heisst other)",
    "wahlbereich": "Wortbestandteil in Prosa; als Wert heisst er electoral_district",
    "geaendert": "zugleich die Changelog-Kategorie (hinzugefuegt|geaendert|behoben)",
    "beides": "gewoehnliches Wort im Fliesstext",
    "entfernt": "gewoehnliches Wort im Fliesstext",
    "gesamt": "Eigenschaftsname vieler Antwort-Typen und Sortierung der Bereichstabelle",
    "posten": "Variablen-/Parametername und Bandart des Flussbilds (rein im Frontend)",
    "dagegen": "zugleich die Partei-Haltung der KI-Antwort (dafür|dagegen|offen)",
    "belegt": "zugleich das Urteil der Themen-Prüfung (belegt|plausibel|ungeeignet)",
    "bremst": "Beschriftung des Ziel-Balkens",
    "voran": "Beschriftung des Ziel-Balkens",
    "orte": "Reiter des Admin-Panels und Query-Parameter der Entitäten-Liste",
    "mittel": "Beschriftung der Quiz-Schwierigkeit",
    "schwer": "Beschriftung der Quiz-Schwierigkeit",
    "vorsitz": "`council_memberships.role` trägt den Wortlaut aus dem RIS",
    # Diese drei stehen nur in einer bestimmten Umgebung zu Recht — daneben
    # wäre jedes Vorkommen ein toter Vergleich, deshalb der Zeilen-Filter.
    "neu": "Tagesordnungs-Diff, Query-Parameter, Vorlese-Text und die "
           "Seitenangabe „neu“ aus dem Änderungslisten-PDF",
    "teilhaushalt": "Schlüssel des Beleg-Apparats (council_products)",
    "geldschulden": ("Blockname der Schulden-Antwort (council.py: \"geldschulden\": …) — "
                     "die API-Blocknamen sind ein eigener Schnitt, noch offen"),
    # Drei Wörter, die als WERT umgezogen sind, im Frontend aber Bezeichner
    # bzw. Blockname geblieben sind. Die API-Feldnamen `wortbeitraege` und
    # `recherche` heißen seit dem Feldnamen-Schnitt `speeches` und `research`.
    "wortbeitraege": ("Komponenten- und Variablenname der Personen-Seite — der WERT "
                      "`llm_usage.feature` heißt seit 01.09.2026 `speeches`"),
    "recherche": ("Modus der Gründlichen Recherche im Frontend — der WERT "
                  "`user_activity.feature` heißt seit 01.09.2026 `research`"),
    "ki_frage": ("Blockname der Admin-Antwort (`features.ki_frage`) — der WERT "
                 "`user_activity.feature` heißt seit 01.09.2026 `ai_question`"),
    "investitionen": "Schlüssel des Beleg-Apparats (council_investments)",
    "schulden": "Schlüssel des Beleg-Apparats und QA-Facette — beide bleiben deutsch",
}

#: Zusätzliche Bedingung für einen ERLAUBT-Eintrag: Nur wenn die Zeile dazu
#: passt, gilt das Vorkommen als in Ordnung. Ohne Eintrag hier gilt das Wort
#: überall.
_BELEG = re.compile(r'Beleg q=|QUELLEN|QuellenSchluessel|as const|^\s*\| "|'
                    r'"(plan|investitionsprogramm|budget_bylaw|jahresabschluss|'
                    r'stellenplan|pruefbericht|schulden)"|'
                    # Seit der Pruefer auch objektwertige Schluessel sieht,
                    # faellt das Verzeichnis selbst auf: `investitionen: {`,
                    # eine Zeile ueber `title:` und `citation:`.
                    r'^\s*\w+: \{\s*$')

#: Ein Kommentar — dort darf jedes Wort stehen.
_KOMMENTAR = re.compile(r'^\s*(//|\*|/\*)')

ERLAUBT_ZEILE = {
    "neu": re.compile(r'aria-label|sp\.get|key: "neu"|"art"|art:|kind ==|'
                      r'page_draft|case "neu"|treffer'),
    # Der Beleg-Apparat: `Beleg q="…"` und die Verzeichnis-Listen. Letztere
    # erkennt man an einem Nachbarschlüssel oder am `as const` der Liste.
    "teilhaushalt": _BELEG,
    "investitionen": _BELEG,
    # Dazu der Parametername der Zinsspannen-Rechnung in `haushalt-labor.ts`:
    # `schulden: { year: number; total: number }[]` ist eine TYP-Angabe.
    "schulden": re.compile(_BELEG.pattern + r'|: \{ year: number'),
    # Diese beiden dürfen nur noch in Fließtext-Kommentaren stehen. Stünde
    # eines wieder in einem Vergleich, wäre genau das der Fehler von #890.
    "entwurf": _KOMMENTAR,
    "schwelle": _KOMMENTAR,
    "leicht": re.compile(r'DIFF_LABEL|difficulty'),
    "unveraendert": re.compile(r'kommunalwahl|Status'),
    "stadtteil": re.compile(r'stadtteil:|/preview|"stadtteil"\s*[,:]'),
    "liste": re.compile(r'kopf|unterkopf|art ===|as const'),
    "anlage": re.compile(r'ankerPrefix'),
    "gruppe": re.compile(r'factionWords|term|gruppe:\s*string'),
    "unbekannt": re.compile(r'\|\|'),
    # `dagegen` ist daneben die Haltung einer Partei aus der KI-Antwort
    # (dafür|dagegen|offen|gewandelt) — ein eigenes Vokabular, eigener Schnitt.
    # Das Feld hieß bis 01.09.2026 `haltung`; seit dem OpenAPI-Schnitt heißt es
    # `stance`. Der WERT bleibt deutsch — er ist die Partei-Haltung der
    # KI-Antwort und steht so im Prompt.
    "dagegen": re.compile(r'haltung|stance|dafür|label: "dagegen"'),
    # `belegt` ist daneben das Urteil der Themen-Prüfung
    # (belegt|plausibel|ungeeignet) und die Beleglage einer Kernzahl.
    "belegt": re.compile(r'verdict|plausibel|beleglage|belegt:\s*Kasten'),
    "bremst": re.compile(r'label: "bremst"'),
    "voran": re.compile(r'label: "bringt voran"'),
    # `rat`, `thema` und `verwaltung` sind im Backend noch deutsch — aber je
    # in EINEM Vokabular. Der Filter nennt dessen Felder, damit ein Vergleich
    # gegen ein anderes Feld (`channel === "rat"`, `area_type === "thema"`,
    # `role === "verwaltung"`) auffällt statt durchzurutschen.
    # `role` mit dem Wert `rat` ist die Haushaltsdebatte; die Anwesenheits-
    # Rollen kennen kein `rat`, der Vergleich ist also eindeutig.
    "rat": re.compile(r'\bart\b|StreitRolle|typ\?:|\brole\b|"rat" \| "verwaltung"|'
                      # `fa` und `rat` sind die zwei Spalten der Antrags-Bilanz
                      # (`haushalt-streit.ts`) — Felder einer Zeile, kein Wert.
                      r'^\s*(//|\*)|committee ===|fa: \{ ein'),
    "thema": re.compile(r'case topic|"kind":|VorschauArt|target\?:|'
                        r'vorschauMetadata|/preview|kind: "thema"|^\s*(//|\*)'),
    "verwaltung": re.compile(r'\btyp\b|type ==|StreitRolle|\bart\b'),
    "beratend": re.compile(r'\bart\b|^\s*(//|\*)'),
    "abgesetzt": re.compile(r'e\.includes|\.test\(|contains\('),
    # `alt` ist im Frontend fast immer das Bild-Attribut.
    "alt": re.compile(r'alt:\s*(hover|"|\{|`)|alt='),
    "sonstiges": re.compile(r'sonstiges:\s*(Tag|")'),
    "wahlbereich": re.compile(r'^\s*\*|//'),
    # `gesamt`, `posten`, `beides`, `stadt`, `entfernt`, `geaendert`, `neu`
    # und `thema` sind daneben ganz gewoehnliche Woerter. Erlaubt sind sie
    # nur als Variable, Eigenschaft oder in Fliesstext — nicht als
    # Schluessel einer Zuordnungstabelle, denn genau dort sterben sie still.
    "gesamt": re.compile(r'gesamt:\s*(number|null|\{|\w+\.)|\bgesamt\b\s*[,;)]|'
                         r'const |function |Sortierung|value: "gesamt"'),
    "posten": re.compile(r'const posten|\(posten:|posten:\s*(number|\{|BonZeile)|'
                         r'\bart\b|farbe\('),
    "beides": re.compile(r'^\s*(//|\*)'),
    "entfernt": re.compile(r'^\s*(//|\*)'),
    "geaendert": re.compile(r'^\s*(//|\*)|geaendert: "Ge'),
    # `beteiligung` war bis zum Feldnamen-Schnitt auch der FELDname der
    # Beschluss-Antwort (heute `participation`); die Werte sind englisch.
    "beteiligung": re.compile(r'"beteiligung":|= "beteiligung"'),
    "orte": re.compile(r'Tab\b|tab ===|sp\.get|p\.delete|Ortskandidaten'),
    "mittel": re.compile(r'DIFF_LABEL'),
    "schwer": re.compile(r'DIFF_LABEL'),
    "leitung": re.compile(r'StreitRolle|\brole\b'),
    "stadt": re.compile(r'entity_key|\bart\b|Sortierung|sortierung|value: "stadt"|'
                        r'\brole\b|\{ stadt,|stadt:\s*string'),
    # `vorlage` war bis zum Feldnamen-Schnitt auch der FELDname der
    # Beschluss-Antwort (heute `template`); der Wert ist die Zielart.
    "vorlage": re.compile(r'Zielart|art ===|\bart\b|source:|^\s*\| "|'
                          r'return "vorlage"|"vorlage":|= "vorlage"'),
}

#: Einzelne Stellen, die keine Regel sauber trifft: ``(Dateiname, Wert)``
#: mit Begründung. Wer hier etwas einträgt, hat nachgesehen, was das Backend
#: an dieser Stelle wirklich liefert.
ERLAUBT_STELLE = {
    ("types.ts", "rat"): "Doku-Kommentar über alte gecachte Antworten",
    ("CouncilViews.swift", "vorlage"): "Tagesordnungs-Diff (neu|geaendert|verschoben|vorlage|anlagen)",
    ("TopicsAndAccountViews.swift", "thema"): "Symbolwahl über einen deutschen Feldnamen",
    ("TopicsAndAccountViews.swift", "vorlage"): "Symbolwahl über einen deutschen Feldnamen",
    ("TodayView.swift", "rat"): "Liste der deutschen Gremiumsnamen",
    ("QuestionsView.swift", "rat"): "Liste der deutschen Gremiumsnamen",
    ("QuestionsView.swift", "vorlage"): "Quellenart aus dem deutschen Quelltitel",
    ("QuestionsView.swift", "stadt"): "Beschriftung der Quellen-Herkunft",
    ("QuestionsView.swift", "beratend"): "`art` der Personen-Bausteine, im Backend deutsch",
    ("ProfileAndQuizViews.swift", "verwaltung"): "`typ` des Personen-Profils, im Backend deutsch",
    ("ProfileAndQuizViews.swift", "rat"): "`art` des Personen-Profils, im Backend deutsch",
    ("ProfileAndQuizViews.swift", "beratend"): "`art` des Personen-Profils, im Backend deutsch",
    ("RatslotseAppTests.swift", "thema"): "`qtype` der Beleg-Prüfung, im Backend deutsch",
    ("haushalt-vergleich.ts", "stadt"): "Feldname der Vergleichsstädte-Zeilen (`{stadt, was}`), kein Wert",
    ("haushalt-indicators.ts", "einwohner"): "Kennzahl-Schlüssel der Stadt (`council_indicators`) bleiben deutsch wie `steuerquote`; umbenannt wurde nur der Einwohner-Indikator des Städtevergleichs",
    ("haushalt-konzern.ts", "stadt"): "Beschriftung zum `entity_key` des Konzerns — der bleibt deutsch",
    ("haushalt-dokumente.ts", "vorlage"): "Beschriftung zur Zielart des Beleg-Apparats — die bleibt deutsch",
    ("page.tsx", "ort"): "Pfad-Teil der Link-Vorschau (/preview/ort/…) — eigener Schnitt",
    ("council-map.tsx", "ort"): "`target` der Kartenpunkte (ort|location) — eigenes Vokabular",
    ("share-metadata.ts", "ort"): "Pfad-Teil der Link-Vorschau — eigener Schnitt",
    ("types.ts", "ort"): "`target` der Kartenpunkte (thema|ort|location) — eigenes Vokabular",
    ("CouncilMapView.swift", "ort"): "`target` der Kartenpunkte — eigenes Vokabular",
    ("CouncilViews.swift", "ort"): "`target` der Kartenpunkte — eigenes Vokabular",
    ("ProfileAndQuizViews.swift", "ort"): "Pfad-Teil der Link-Vorschau — eigener Schnitt",
}

#: Werte, die nur im Code umbenannt wurden — sie stehen nirgends gespeichert,
#: sondern werden je Anfrage gerechnet. Ohne Migrationspaar wüsste der Prüfer
#: nichts von ihnen, und genau diese Sorte ist im Frontend am leichtesten zu
#: vergessen.
ZUSATZ_PAARE = {
    # `art` und `typ` der Personen-Bausteine, `role` der Haushaltsdebatte.
    ("rat", "council"), ("beratend", "advisory"), ("verwaltung", "administration"),
    ("beteiligung", "participation"), ("leitung", "leadership"),
    # Die Eimer und `art`-Werte des Tagesordnungs-Diffs. Der Bestand zieht per
    # `_agenda_diff_schluessel_neu` nach, der Wert selbst wird gerechnet.
    ("umformuliert", "reworded"), ("geaendert", "changed"), ("verschoben", "moved"),
    ("entfernt", "removed"),
}

_PAAR = re.compile(r"""\(\s*["']([a-z][a-z0-9_+]*)["']\s*,\s*["']([a-z][a-z0-9_+]*)["']\s*\)""")


def migrationspaare() -> set[tuple[str, str]]:
    """Alle ``("alt", "neu")`` aus den Werte-Migrationen BEIDER Stores.

    `kern/store.py` gehört dazu, seit dort die Quiz-Werte (#891) und die
    Feature-Namen des Kosten-Trackings umziehen: Die Konten-Datenbank hat
    eigene Werte-Vokabulare, und die Oberfläche liest sie genauso.
    """
    paare = set()
    # Alle `store*.py` beider Pakete: `council/store.py` ist seit 09/2026
    # aufgeteilt, und die Werte-Migrationen stehen jetzt in `store_schema.py`.
    # Eine feste Dateiliste hätte den Wächter still auf 39 Paare halbiert.
    quellen = sorted((WURZEL / "council").glob("store*.py")) + \
        sorted((WURZEL / "kern").glob("store*.py"))
    for quelle in quellen:
        text = quelle.read_text()
        for block in re.finditer(r"_werte_umschreiben\((.*?)\]\)", text, re.S):
            paare.update(_PAAR.findall(block.group(1)))
        # Listen-Konstanten, die mehrere Aufrufe teilen (ORTSARTEN).
        for block in re.finditer(r"^\s+[A-Z_]{4,} = \[\n(.*?)\n\s+\]$", text, re.S | re.M):
            paare.update(_PAAR.findall(block.group(1)))
    return {(a, b) for a, b in paare | ZUSATZ_PAARE if a != b}


def dateien() -> list[Path]:
    aus = []
    for quelle in QUELLEN:
        for pfad in (WURZEL / quelle).rglob("*"):
            if pfad.suffix not in ENDUNGEN or not pfad.is_file():
                continue
            if any(teil in str(pfad) for teil in UEBERSPRINGEN):
                continue
            aus.append(pfad)
    return aus


def main() -> int:
    paare = migrationspaare()
    alte = {a: b for a, b in paare}
    W = "|".join(re.escape(a) for a in sorted(alte))
    # Zwei Formen, in denen ein Wert in TS/Swift steht. Die zweite ist die
    # gefaehrlichere: Farb- und Beschriftungs-Tabellen (`OUTCOME_META`,
    # `DOT_CLS`, `LABEL`) schreiben ihre Schluessel OHNE Anfuehrungszeichen —
    # genau die Form, die in #890 acht Mal tot dastand und die dieser Pruefer
    # bis zum 01.09.2026 nicht sah.
    # Zweiter Zweig: der Schluessel einer Zuordnungstabelle, OHNE
    # Anfuehrungszeichen — `angenommen: "Angenommen"`, `neu: "border-..."`.
    # Genau diese Form stand in #890 acht Mal tot da, und genau sie sah der
    # Pruefer bis zum 01.09.2026 nicht.
    #
    # Zwei Einschraenkungen halten das Rauschen draussen, ohne die gefaehrliche
    # Form zu verlieren: Der Schluessel muss am Zeilenanfang oder hinter `{`/`,`
    # stehen (sonst traefe der Ternaer `x ? alt : y`), und rechts muss eine
    # nicht-leere ZEICHENKETTE stehen. Eine Typ-Eigenschaft (`stadt: number`),
    # eine Destrukturierung (`{ posten }`) oder ein Verweis (`rat: z.rat`) ist
    # nie eine Wertetabelle — eine Beschriftung oder Farbe immer.
    #
    # Rechts steht ausserdem manchmal ein OBJEKT statt einer Zeichenkette:
    # `BELEGLAGE` in `section-betriebe.tsx` haengt an jeden Probennamen ein
    # `{ kurz, lang }`. Dieselbe tote Zuordnung, nur eine Ebene tiefer — der
    # Pruefer sah sie bis zum 01.09.2026 nicht, weil er eine Zeichenkette
    # verlangte.
    muster = re.compile(
        rf'"(?P<zitiert>{W})"'
        rf'|(?:^|[{{,])\s*(?P<schluessel>{W})\s*:\s*(?:"[^"]|{{)')
    funde: list[str] = []
    for pfad in dateien():
        rel = pfad.relative_to(WURZEL)
        for nr, zeile in enumerate(pfad.read_text().splitlines(), start=1):
            for treffer in muster.finditer(zeile):
                alt = treffer.group("zitiert") or treffer.group("schluessel")
                if (pfad.name, alt) in ERLAUBT_STELLE:
                    continue
                if alt in ERLAUBT:
                    bedingung = ERLAUBT_ZEILE.get(alt)
                    if bedingung is None or bedingung.search(zeile):
                        continue
                funde.append(f"  {rel}:{nr}: \"{alt}\" heißt jetzt \"{alte[alt]}\"\n"
                             f"      {zeile.strip()[:110]}")
    print(f"{len(paare)} umbenannte Werte gegen {len(dateien())} Oberflächen-Dateien geprüft.")
    if funde:
        print("\nDiese Stellen lesen einen Wert, den es nicht mehr gibt:\n")
        print("\n".join(funde))
        print("\nEntweder den neuen Wert eintragen — oder, wenn das Wort zu Recht "
              "deutsch bleibt, mit Begründung in ERLAUBT aufnehmen.")
        return 1
    print("Keine Oberfläche liest einen umbenannten Wert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
