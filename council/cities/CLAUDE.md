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
| `adapters/_common.py` | 366 | alle | alle |
| `adapters/allris4.py` | 181 | Osnabrück, Braunschweig, Potsdam | Leipzig, Bonn |
| `adapters/session.py` | 168 | Münster, Magdeburg | Köln, Dresden, Wuppertal, Düsseldorf |
| `adapters/rubin.py` | 90 | — | Freiburg, Darmstadt |
| `adapters/oldenburg.py` | 313 | Oldenburg (liest `council.sqlite`) | — |

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
| Magdeburgs Beratungen zeigen auf Punkte aus einem zweiten Kennungsraum | **0 von 700** Vorlagen mit Ergebnis, bei 5.982 Punkten mit einem | `link_within_meeting` |
| Magdeburg und Münster vergeben eine Beratungs-Kennung mehrfach | Stationen überschreiben sich: 575 bzw. 467 verloren | `eindeutige_beratungen` |
| Die ALLRIS-Rückwärtsblätterung fragt Sitzungen nach `date` statt `start` | jede Sitzung gilt als undatiert und damit als alt, Abbruch nach zwei Seiten: Osnabrück 137 Sitzungen zu 2.864 Vorlagen | `_datum_von` |
| „nicht empfohlen" enthält „empfohlen" | 275-mal stand das Gegenteil des Protokolls da | `_ABLEHNUNG_RE` |

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

1. **Eintrag in [`registry.py`](registry.py)**, `active=False`. ALLRIS-4-
   Instanzen laufen fast immer unter `<stadt>.sitzung-online.de/oparl/system`.
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
