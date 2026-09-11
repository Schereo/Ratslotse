# Regeln für `council/cities/`

Der Städte-Speicher: Ratsdokumente anderer Kommunen, gegen Oldenburg
gehalten. Alles Übrige: [`../CLAUDE.md`](../CLAUDE.md) und
[`../../CLAUDE.md`](../../CLAUDE.md).

## Ein Adapter je Ratsinformationssystem, nicht je Stadt

Vier Hersteller bedienen die deutschen Kommunen; Städte desselben Herstellers
antworten in derselben Sprache, mit denselben Eigenheiten. Deshalb gibt es
**einen Adapter je System**, und jede Reparatur kommt allen Städten dieses
Systems zugute — auch denen, die noch niemand angeschlossen hat.

| Datei | Zeilen | angeschlossen | wartet in der Registry |
|---|---:|---|---|
| `adapters/_common.py` | 418 | alle | alle |
| `adapters/allris4.py` | 226 | Osnabrück, Braunschweig, Potsdam | Leipzig, Bonn, Langenhagen, Peine |
| `adapters/allris4_html.py` | 627 | Wolfsburg | Laatzen, Lüneburg |
| `adapters/allris_classic.py` | 511 | — | Hildesheim |
| `adapters/session.py` | 164 | Münster, Magdeburg | Köln, Dresden, Wuppertal, Düsseldorf |
| `adapters/rubin.py` | 87 | — | Freiburg, Darmstadt |
| `adapters/oldenburg.py` | 310 | Oldenburg (liest `council.sqlite`) | — |

**Derselbe Hersteller kann DREI Adapter brauchen.** Neben ALLRIS 4 (mit und
ohne Schnittstelle) gibt es die ältere Generation **ALLRIS classic**:
statische `.asp`-Seiten, ISO-8859-1, kein Seitenzustand, kein OParl. Sie ist
die einfachere Welt — der Index ist ein schlichter GET
(`si010_e.asp?YY=2026&MM=09`, 10 bis 18 Sitzungen je Monat, Historie ab etwa
2007), es gibt keine Wicket-Selbstaufrufe und keine CDATA. Gemessen an
Hildesheim (11.09.2026).

Zwei Eigenheiten, die es sonst nirgends gibt:

- **Der Vorlagentext steht IN der Seite.** An Hildesheims Vorlagen hängt kein
  einziger Datei-Verweis; der Sachverhalt ist der Seiteninhalt. Deshalb
  `fetch_files=False` und der Text über `inline_texts` — dieselbe Bahn, die
  Oldenburg und more! rubin schon benutzen.
- **Zu jedem beratenen Punkt gibt es einen „Auszug"** (`to020.asp?TOLFDNR=…`)
  mit Wortprotokoll, Beschluss und Abstimmungsergebnis, je Punkt schon
  getrennt. Gemessen: **2.075 von 3.728** Punkten haben einen. Das ist das
  „Warum" ohne das Schneiden einer Niederschrift — und es ist zugleich die
  echte Kennung des Punktes, denn die Tagesordnung selbst vergibt keine
  (ihr `TOLFDNR` ist auf jeder Zeile dieselbe Zahl).

**Und zwei Fallen, die es nur hier gibt:**

- **Die Stadt-Website ist um ALLRIS herumgebaut.** 105 der 280 kB jeder Seite
  sind Navigation, und die verlinkt dieselben `au020.asp`-Adressen unter
  **generischen** Namen: „Der Ortsrat" unter dem Menüpunkt „Achtum / Uppen".
  Ungefiltert gewinnen diese über die echten — und 42 von 198 Sitzungen
  finden ihr Gremium nicht mehr. `_inhalt()` schneidet den Rahmen weg, bevor
  irgendetwas gelesen wird; danach 175 von 198.
- **Ein weggelassenes Feld verschwindet nicht, es wandert ins Nachbarfeld.**
  `Verfasser:` und `Bearbeiter/-in:` nennen Namen von
  Verwaltungsmitarbeitenden und werden bewusst nicht gespeichert. Sie standen
  deshalb im ersten Entwurf gar nicht in der Feldliste — und damit lief der
  Wert des Feldes DAVOR bis zum nächsten bekannten Wort weiter: Jede Vorlage
  bekam als Art „Mitteilungsvorlage Verfasser: …" samt Namen. Ein Feld, das
  man nicht will, muss trotzdem als **Grenze** in der Regel stehen
  (`_GRENZEN`).

**Was Hildesheim nicht hat:** den Rat in der Gremienliste. `au010.asp` führt
Ausschüsse, Beiräte und Aufsichtsräte, aber nicht den Rat selbst — seine
Sitzungen bleiben ohne Gremium, und das ist richtig so. Ein Gremium zu
erfinden, damit eine Zahl schöner aussieht, wäre derselbe Fehler wie die
erfundenen Punkt-Kennungen aus phase0.

**Derselbe Hersteller kann zwei Adapter brauchen.** ALLRIS 4 hat ein
OParl-Modul; wo es antwortet, liest `allris4.py` die Schnittstelle. Wo es
eingebaut ist und mit HTTP 500 antwortet — gemessen bei Laatzen, Lüneburg und
Wolfsburg —, liest `allris4_html.py` dieselbe Anwendung über ihre Oberfläche.
Der Unterschied ist die Quelle, nicht die Stadt, deshalb sind es zwei
Dialekte und keine Bedingung im einen.

**Beim HTML-Lesen sind drei Fallen gemessen worden**, alle am 10.09.2026 an
Laatzen:

1. **Spalten über die Kopfzeile suchen, nie über feste Nummern.** Eine
   verschobene Spalte liefert sonst stumm den falschen Wert — die
   „Zuständigkeit" landete als Titel.
2. **Das Feld heißt `Vorlageart`, nicht `Vorlagenart`.** Ein Buchstabe, und
   jede Vorlage der Stadt steht ohne Art da; der Vergleich hält sie dann
   ausnahmslos für „other", ohne Fehler und ohne Auffälligkeit.
3. **Eine erfundene Kennung muss als solche erkennbar bleiben.** `#top-` ist
   projektweit die Marke dafür (`SYNTHETISCHE_KENNUNG`). Ein Punkt mit
   `TOLFDNR` hat eine echte Adresse und bekommt sie; nur Formalpunkte ohne
   eigene Seite tragen die Marke. Stünde sie an allen, hielte
   `zwillinge_zusammenfuehren` jeden Punkt des Dialekts für erfunden.

**Der Index ist ``si018``, nicht der Kalender.** ``si010`` ist ein
Monatsraster: Seine Zellen tragen keine Sitzungskennung, und die
Monatsnavigation hängt an einer Seitenversion, die der Server hochzählt.
``si018`` („Sitzungen Übersicht") ist eine Liste, deren Blätterung sich
selbst beschreibt — jede Antwort nennt das Ziel für „weiter". Gemessen am
10.09.2026: Wolfsburg 652 Sitzungen in 28 Abrufen, Lüneburg 778 in 33,
**ohne einen Browser**.

Drei Eigenheiten, die dabei jede für sich den ganzen Index leer aussehen
lassen:

- **Die Seitenversion wird gelesen, nicht gesetzt.** Wicket zählt sie je
  Sitzung hoch. Ein fest verdrahtetes ``si018?0-1.0-`` funktioniert nur,
  solange davor nichts anderes geholt wurde — nach dem (bei Wolfsburg
  ohnehin scheiternden) Gremien-Abruf stand die Seite bei 6, und die
  Antwort war leer. Ergebnis: „0 Sitzungen" statt 652, ohne Fehler.
- **Die Kennung steht in zwei Formen da.** Wolfsburg setzt Wicket-Verweise
  ohne ``href`` und identifiziert sie über ``id="silink_1003198"``; Laatzen
  setzt in derselben Tabelle echte ``SILFDNR=``-Adressen. Wer nur eine Form
  sucht, hält den Index der anderen Stadt für leer.
- **Das „weiter"-Ziel ist mal absolut, mal relativ.** Wolfsburg schreibt die
  volle Adresse, Lüneburg ``./si018?…``.

**Die Gremien kommen aus ``gr010``, nicht aus ``gr020``.** ``gr020`` ist die
Seite EINES Gremiums und antwortet ohne ``GRLFDNR`` mit HTTP 500 — bei allen
drei gemessenen Städten. Dieselbe Selbstaufruf-Mechanik wie beim Index, plus
eine eigene Falle: **Die Namen liegen in CDATA.** Wer die AJAX-Antwort als
HTML parst, findet dort kein einziges ``<a>`` und hält die Stadt für
gremienlos. Gemessen: Wolfsburg 43, Lüneburg 66, Laatzen 15.

**Und eine nichtöffentliche ANLAGE auch.** Derselbe Satz kommt mit HTTP 200
statt einer PDF-Datei zurück, wenn eine Vorlage nicht öffentlich ist.
Ungeprüft landet die Seite als ``.pdf`` im Dateispeicher, und die Textstufe
meldet bei jedem Lauf aufs Neue „invalid pdf header" — Fehler, die wie ein
Parserproblem aussehen und in Wahrheit eine Zugangsbeschränkung sind.
Gemessen an Wolfsburg: **444 von 1.798**. `get_file` weist deshalb ab, was
als Webseite zurückkommt: **Ein Dokument-Abruf, der HTML liefert, ist nie das
Dokument.**

**Normalisieren löscht nicht.** ``upsert_batch`` legt an und aktualisiert; ein
Objekt, das der Adapter nicht mehr baut, bleibt liegen. Nach der Reparatur
der Geister oben standen die 199 immer noch in ``cities.sqlite`` und
drückten „Vorlagen je Sitzung" von 3,5 auf 2,4 — die Kennzahl, an der die
Plausibilitätsprüfung hängt. Wer eine Regel ändert, die entscheidet, ob ein
Objekt überhaupt entsteht, muss den Altbestand von Hand aufräumen.

**Eine nichtöffentliche Sitzung sieht aus wie ein Fehler.** ALLRIS antwortet
für sie mit HTTP 200 und einer 13.701-Byte-Hülle; der einzige Unterschied zu
einem technischen Fehler ist der Satz „Keine Information verfügbar … oder Sie
sind nicht berechtigt". Wer ihn nicht liest, baut je Fall einen Geist: eine
Sitzung namens „Sitzung", ohne Datum, ohne Tagesordnung — und die zählt in
jeder Kennzahl mit, als fehlten UNS die Daten, statt dass es sie öffentlich
gar nicht gibt. Gemessen an Wolfsburg: **77 von 255**. Abgelegt wird die
Absage trotzdem (die Rohschicht hält fest, was der Server gesagt hat);
aussortiert wird beim Normalisieren.

**Dieselbe Spalte heißt je Stadt anders.** Die Ergebnisspalte der
Tagesordnung heißt bei Laatzen „Zuständigkeit", bei Wolfsburg
„Beschlussart" — und ein Rückfall auf eine feste Spaltennummer trifft dort
ins Leere, weil die Tabelle sechs Spalten hat. Gemessen: **0 von 1.358**
Beratungen mit Ergebnis, ohne Fehler und ohne Auffälligkeit. Nach der
Reparatur 1.344.

**Ohne Sitzungs-Cookie antwortet der Selbstaufruf mit einer leeren Hülle.**
Der Client hält eine ``requests.Session``, das genügt — aber der erste Abruf
auf ``si018`` muss trotzdem passieren.

**Und die Beratungsfolge steht über zwei Zeilen je Station** — Status,
Gremium, Beschluss in der ersten, Datum und Sitzungsname in der zweiten. Wer
Zeile für Zeile liest, bekommt lauter halbe Stationen.

**Eine Eigenheit gehört in den Adapter, nie in eine Stadt-Bedingung.** Ein
`if body_id == "magdeburg"` im Normalisieren heißt: Die nächste Somacos-Stadt
läuft in denselben Fehler, und niemand weiß mehr, warum die Zeile da steht.
Was allen Dialekten gemeinsam ist, steht in `_common.py`.

## Was schiefgeht, geht STUMM schief

Am 08.09.2026 lagen vier Fehler gleichzeitig im Bestand. Kein Lauf ist
abgestürzt, kein Test war rot, keine Kennzahl sah verdächtig aus — die Daten
waren nur falsch:

| Fehler | Wirkung | jetzt |
|---|---|---|
| ~~Magdeburgs Beratungen zeigen auf Punkte aus einem zweiten Kennungsraum~~ | **0 von 700** Vorlagen mit Ergebnis, bei 5.982 Punkten mit einem | war eine Fehldiagnose, s. u. |
| Magdeburg und Münster vergeben eine Beratungs-Kennung mehrfach | Stationen überschreiben sich: 575 bzw. 467 verloren | `eindeutige_beratungen` |
| Die ALLRIS-Rückwärtsblätterung fragt Sitzungen nach `date` statt `start` | jede Sitzung gilt als undatiert und damit als alt, Abbruch nach zwei Seiten: Osnabrück 137 Sitzungen zu 2.864 Vorlagen | `_datum_von` |
| „nicht empfohlen" enthält „empfohlen" | 275-mal stand das Gegenteil des Protokolls da | `_ABLEHNUNG_RE` |
| Die Übernahme des Probelaufs erfand Punkt-Kennungen | 22.152 Punkte lagen doppelt, ein Fünftel des Bestands | `zwillinge_zusammenfuehren`, Migration 7 |

Am 10.09.2026 kam ein fünfter dazu, und er stand nicht in den Daten der
Städte, sondern in unseren eigenen: **22.152 Tagesordnungspunkte lagen
doppelt** — ein Fünftel des Bestands, in fünf von sechs Städten (Oldenburg,
das aus `council.sqlite` liest, in keiner einzigen Zeile).

`scripts/cities_import_phase0.py` hat den Probelauf vom 07.09. in die
Rohablage übernommen und dabei je Punkt eine Kennung **erfunden**:
`<sitzung>#top-<nummer>`. Kein Ratsinformationssystem vergibt so etwas —
gegen die Schnittstellen geprüft, liefern alle fünf Städte ausschließlich
`…/agendaitems/<n>`. Die echte Ernte brachte dieselben Punkte danach unter
ihrer eigenen Kennung, und weil `upsert_batch` auf der Kennung aufsetzt,
blieben beide liegen: 4.507 in Braunschweig, 9.416 in Magdeburg, 2.788 in
Münster, 2.194 in Osnabrück, 3.247 in Potsdam.

**Das Tückische daran ist, wo es NICHT auffiel.** `stats()` zählt Zeilen, und
Zeilen gab es ja; `papers_with_outcome` zählt `DISTINCT paper_id` und blieb
deshalb richtig. Alle vier Bänder oben messen Anteile *je Vorlage* — sie
konnten gar nicht anschlagen. Was falsch war, waren `agenda_items` und
`agenda_items_with_outcome` im Admin-Panel (Magdeburg 35.226 statt 25.810),
und die Reihenfolge, in der `agenda_items(meeting_id)` die Punkte einer
Sitzung liefert: Bei den ALLRIS-Städten sortierte die erfundene Zeile vor die
echte, und wer den ersten Treffer nahm — der Niederschriften-Schnitt tut das
—, bekam die Zeile ohne Ergebnis.

Zwei Stellen halten das jetzt: `zwillinge_zusammenfuehren` in
[`adapters/_common.py`](adapters/_common.py) (damit keine neuen entstehen)
und Migration 7 (die 22.152, die schon lagen). Und `pruefung.py` hat ein
fünftes Band, `anteil_doppelter_punkte` — vorher 31 bis 53 % je Stadt,
nachher 0,0 bis 0,1 %.

**Und der erste der vier Fehler oben war gar keiner.** „Magdeburgs
Beratungen zeigen auf einen zweiten Kennungsraum" beschrieb denselben
phase0-Rest von der anderen Seite: Die *Sitzungen* trugen die erfundenen
Kennungen, die Beratungen die echten. Die Reparatur von damals
(`link_within_meeting`, ein Titelabgleich innerhalb der Sitzung) ist deshalb
mit ausgebaut. Gemessen band sie **null**, und zwar aus einem strukturellen
Grund, nicht zufällig: Sie greift nur, wenn eine Beratung einen Punkt nennt,
den ihre Sitzung nicht kennt — mit **einem** Kennungsraum heißt das, dass die
Sitzung ihre Tagesordnung gar nicht mitliefert (Magdeburg 29 Fälle, alle 29
mit leerer Tagesordnung; die vier anderen Städte 0). Ein Titelabgleich gegen
eine leere Tagesordnung hat nichts zu vergleichen.

Was seine Stelle einnimmt, ist ein Wächter statt einer Reparatur:
`test_magdeburg_bindet_ueber_die_kennung_allein` hält fest, dass jede
Somacos-Beratung ihren Punkt über die Kennung findet. Fällt er, verweist eine
Instanz doch wieder ins Leere — und dann gehört ein Notnagel gebaut, der zu
dem passt, was dann wirklich schiefgeht.

**Die Sitzungs-Fixture war selbst betroffen.** `magdeburg_meetings.json` trug
erfundene `#top-`-Kennungen und einen Gremien-Link als Sitzungsnamen — sie war
nachgebaut, nicht geholt, und bewies deshalb genau den Fehler, den sie prüfen
sollte. Sie ist jetzt ein gekürzter, aber unveränderter Abzug der beiden
echten Sitzungen. Das ist der Grund für Schritt 5 im Rezept oben, und hier hat
er gefehlt.

Daraus folgt die Regel, die hier am meisten wert ist: **Nach jeder Ernte die
Plausibilität prüfen, nicht nur die Zahlen ansehen.**

```bash
python scripts/cities_backfill.py --pruefen
```

[`pruefung.py`](pruefung.py) hält jede Stadt gegen Bänder, die aus dem
Bestand gemessen sind (Vorlagen je Sitzung, Anteil mit Ergebnis, mit Text,
mit Beratung). Ein Befund heißt nicht „kaputt", sondern „sieh nach, bevor du
diese Stadt benutzt". Dieselbe Prüfung läuft im Wochen-Cron und schreibt
`implausibel` in die Kennzahlen (`job_runs`), damit ein neuer stummer Fehler
eine Zahl bekommt statt gar nichts.

Derselbe Aufruf zeigt das **unbekannte Ergebnis-Vokabular** je Stadt: die
häufigsten `result_raw`-Texte, die `model.outcome` auf `none` abbildet. Was
dort oft vorkommt, ist entweder wirklich kein Ergebnis („schriftliche
Stellungnahme", „eingebracht") oder eine Lücke in der Regel — und eine
tausendfache Lücke macht die halbe Beschlusslage einer Stadt unsichtbar.

## Eine neue Stadt anschließen

0. **Den Host von der Rathaus-Seite holen, nie raten.** Am 10.09.2026 galt
   Wolfsburg eine Stunde als technisch nicht erntbar — gemessen gegen
   `ratsinfo.wolfsburg.de`, einen Host, der **nicht einmal im DNS steht**.
   Die Stadt verlinkt von `wolfsburg.de/politik` auf
   `ratsinfob.stadt.wolfsburg.de`, ohne `/public`; dort ist alles in
   Ordnung. Dieselbe Falle bei Lüneburg
   (`buergerinfo.stadt.lueneburg.de/public`) — und dort trägt der Name
   „buergerinfo" obendrein die Handschrift von Somacos, während gemessen
   ALLRIS 4 läuft. **Das Produkt steht im Seiteninhalt, nicht im Domainnamen.**
1. **Eintrag in [`registry.py`](registry.py)**, `active=False`. ALLRIS-4-
   Instanzen laufen oft, aber längst nicht immer unter
   `<stadt>.sitzung-online.de/oparl/system`.
2. **Ernten und normalisieren**, erst mit kurzem Fenster:
   `--run --body <stadt> --since 2025-01-01 --stage fetch --stage normalize`.
3. **`--pruefen`.** Das ist der Schritt, den man nicht auslassen darf: Alle
   vier Fehler oben hätten hier gestanden. Ein Befund heißt, dass der Dialekt
   etwas anders macht als gedacht — nachsehen, bevor mehr geerntet wird.
4. **Vokabular durchgehen** (dieselbe Ausgabe). Was ein Ergebnis ist, gehört
   in `_OUTCOME_RULES`; was keins ist, bleibt liegen.
5. **Rohobjekte als Fixture** nach `tests/fixtures/cities/<stadt>_papers.json`
   (gekürzt, **ohne Personen**) und in `STAEDTE` in
   `tests/test_cities_adapters.py`. Ein selbstgebautes Beispiel hätte genau
   die Eigenheiten nicht, an denen der Probelauf scheitert.
6. Erst dann `active=True` und die volle Historie holen.

## Die Niederschrift ist die einzige Quelle für das „Warum"

Was ein fremder Rat beschlossen hat, steht in der Beratungsfolge. **Warum** er
so entschieden hat, steht nur in der Niederschrift der Sitzung — und die
liegt als PDF **an der Sitzung**, nicht am Papier (`files.role='protocol'`,
`meeting_id` gesetzt, `paper_id` leer).

Drei Regeln, alle aus Messungen vom 10.09.2026:

1. **Geschnitten wird entlang der Tagesordnung, die schon da ist.**
   `protocol.py` sucht zu jedem bekannten Punkt *seine* Überschrift im Text.
   Der erste Entwurf suchte nur nach Überschriften und fand in Braunschweig
   Beschlussaufzählungen („1. Die Verwaltung setzt SAP …") für
   Tagesordnungspunkte. Gemessen: 5 statt 7 Punkte, mit Beschlusssätzen als
   Titel. Mit dem Abgleich gegen die Tagesordnung: **82 %** der Punkte
   bekommen ihren Abschnitt (929 von 1.134, 38 Niederschriften, fünf Städte).
2. **Das Layout steht im Text, nicht im Herstellernamen.** Osnabrück und
   Braunschweig sprechen beide ALLRIS 4 und schreiben verschieden (`Zu 4
   Titel` gegen `4. Titel`); Münster schreibt `Punkt 4 der Tagesordnung`.
   `detect_layout` entscheidet am Text — ein Herstellerwechsel ändert daran
   nichts.
3. **Jede Niederschrift enthält ihre Tagesordnung zweimal**, erst als
   Verzeichnis, dann als Protokolltext. Bei mehreren Fundstellen derselben
   Nummer gewinnt die **hintere** mit passendem Titel.
4. **Zwei Fallen, die beide unsichtbar zuschlagen.** Osnabrück rückt seine
   Nummern seit 2024 um ein Leerzeichen ein (`` 3.1. Titel``) — eine Regel
   auf `^\d` fand dort 0 von 194 Punkten, während dieselbe Stadt 2026 zu
   82 % traf. Und die Textextraktion hat einen Deckel: 5 von 38 Protokollen
   liefen gegen die 80.000 Zeichen, die für **Vorlagen** gewählt sind.
   Abgeschnitten werden die HINTEREN Tagesordnungspunkte, und niemand
   vermisst, was nie dastand — deshalb haben Niederschriften seit 09/2026
   eigene Deckel (`MAX_*_PROTOKOLL`).

**Und die Regel, die über allem steht:** Ein Modell darf wiedergeben, was im
Protokoll steht. Es darf nicht erschließen, warum ein Rat entschieden hat.
Der Annotator `reason` trägt dafür `grounded` — seine eigene Auskunft, ob im
Abschnitt überhaupt eine Begründung steht. Ist sie falsch, zeigt die Karte
eine erfundene Begründung für einen echten Ratsbeschluss; im Prüfstand steht
diese Zahl deshalb bei **null**, wie die erfundenen Beleg-Kennungen bei `fit`.

## Die fünf Schichten und ihre Grenze

`raw_objects` → `papers`/`meetings`/… → `texts` → `annotations` → `neighbors`
und `papers_fts`. Alles ist auf `(…, model)` bzw. `(annotator, version)`
eindeutig, damit zwei Fassungen nebeneinander liegen und sich messen lassen.

**Schicht 1 trägt keine Meinung.** Was ein Modell über ein Objekt sagt, steht
in `annotations` — nie als Spalte in `papers`. `tests/test_cities_guards.py`
hält die Grenze, und `tests/test_sql_spalten.py` verlangt, dass Abfragen als
**ganze statische Anweisungen** geschrieben sind (zusammengesetztes SQL
überspringt es und prüft dann nichts).

## Kein `sqlite3.connect` außerhalb von `store.py`

Auch nicht in Skripten. Über den Store laufen Schema, Migration und
Transaktionsverhalten mit. Und: **nie zwei Prozesse gleichzeitig schreibend**
auf `cities.sqlite` — die Ernte darf parallel laufen, weil sie je Stadt in
eine eigene Rohdatei schreibt; alles ab `normalize` hat genau einen Schreiber.
