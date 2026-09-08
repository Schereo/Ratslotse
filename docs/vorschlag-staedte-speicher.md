# Vorschlag: ein Speicher für die Ratsdokumente vieler Städte

Stand: 07.09.2026. Antwort auf die Frage, wie sich die Dokumente anderer Städte
so einlesen lassen, dass spätere Auswertungen nicht an heutige Entscheidungen
gebunden sind. Die Zahlen stammen aus dem Probelauf
([`phase0-andere-staedte.md`](phase0-andere-staedte.md)).

## Die Antwort in drei Sätzen

**Rohes und Abgeleitetes strikt trennen.** Was die Schnittstellen liefern,
wird verlustfrei und unverändert abgelegt; alles, was wir daraus rechnen —
Text, Einordnung, Embeddings, Nachbarschaften — liegt daneben als versionierte
Annotation und ist jederzeit aus dem Rohen neu berechenbar.

**OParl ist das Datenmodell.** Vier Hersteller liefern es bereits, und
Oldenburgs eigener SessionNet-Bestand bildet sich verlustfrei darauf ab. Wir
erfinden kein eigenes Schema, wir übernehmen das, auf das sich die Branche
2016 geeinigt hat.

**Oldenburg ist Stadt Nummer null im selben Speicher.** Nur so ist jeder
Vergleich symmetrisch — „was fehlt uns?" und „was haben wir, was andere nicht
haben?" sind dann dieselbe Rechnung mit vertauschten Rollen.

## 1. Warum deine Sorge berechtigt ist

Phase 0 hat genau den Fehler gemacht, vor dem du warnst. Die Tabelle `papers`
bekam feste Spalten `field`, `instrument`, `transfer`, `competence`. Als der
geschärfte Prompt kam, hieß das: alle 2.906 Vorlagen neu rechnen und die
alten Werte überschreiben — der Vergleich beider Fassungen war nur möglich,
weil ich den Modellnamen mit einem `#v2` verunstaltet habe. Ein zweiter
Annotator (etwa „welche Geldbeträge stehen drin?") hätte eine weitere Spalte
gebraucht, ein drittes Embedding-Modell eine weitere Tabelle.

Die Oldenburger Datenbank hat dieselbe Bauform: `policy_field`,
`simple_summary`, `interest`, `importance`, `amount_eur` sitzen als Spalten in
`council_decisions`. Jede neue Auswertung war ein `ALTER TABLE` samt Migration,
und eine alte Fassung einer Einordnung gibt es nicht mehr, sobald die neue
geschrieben ist. Für einen Bestand aus einer Stadt ging das. Für zwanzig
Städte, deren Auswertungen sich noch ändern werden, geht es nicht.

## 2. Das Modell: OParl, plus Oldenburg als Adapter

OParl kennt acht Objekte, und sie decken alles ab, was ein
Ratsinformationssystem hat:

| OParl-Objekt | Was es ist | Oldenburg heute |
|---|---|---|
| Body | die Stadt | — (implizit) |
| LegislativeTerm | Wahlperiode | `council_memberships.von/bis` |
| Organization | Rat, Ausschuss, Ortsrat, Fraktion, Amt | `committees`, `council/parties.py` |
| Meeting | Sitzung | `council_sessions` |
| AgendaItem | Tagesordnungspunkt mit Ergebnis und Beschlusstext | `council_agenda_items` + `council_decisions` |
| Paper | Vorlage, Antrag, Anfrage, Mitteilung | `council_templates` + Anträge in `council_attachments` |
| File | PDF mit Rolle: Hauptdokument, Anlage, Beschlussausfertigung, Einladung, Protokoll | `council_attachments`, `council_protocols` |
| Consultation | Beratungsfolge: welches Papier in welcher Sitzung mit welcher Rolle | `council_deliberations` |

Person lassen wir bewusst weg (§ 7 unten).

**Warum das Modell und nicht ein eigenes:** Die Dialekte der Hersteller
(Somacos legt Dateien unter `auxiliaryFile`, ALLRIS unter `mainFile`, Magdeburg
nennt falsche URLs, Oldenburg hat gar kein OParl) gehören in **Adapter**, nicht
ins Schema. Ein Adapter je Dialekt liefert dieselben acht Objekte; einer davon
liest statt aus dem Netz aus `council.sqlite`. Danach weiß keine Auswertung
mehr, woher ein Papier kam — und muss es auch nicht.

## 3. Fünf Schichten

```
0  Rohablage      jede Antwort der Schnittstelle, jedes PDF — unverändert, append-only
1  Normalisiert   die acht OParl-Objekte in Tabellen, mit kanonischen Zusatzfeldern
2  Text           extrahierter Volltext, versioniert nach Extraktor
3  Annotationen   alles, was ein Modell oder eine Regel dazu sagt — versioniert, JSON
4  Indizes        Chunks, Embeddings je Modell, Volltextindex, Nachbarschaften
   Anwendungen    Suche, Lücken, Trends, Benachrichtigungen — lesen 1–4, schreiben nichts
```

Die Regel, die alles zusammenhält: **Jede Schicht ist aus der darunter
vollständig neu berechenbar.** Wer Schicht 2 bis 4 löscht, verliert
Rechenzeit und ein paar Dollar, keine Daten.

### Schicht 0: Rohablage

```sql
raw_objects   source TEXT, url TEXT, kind TEXT, fetched_at TEXT,
              content_hash TEXT, body JSON            -- die OParl-Antwort, wie sie kam
raw_files     sha256 TEXT PRIMARY KEY, bytes INTEGER, mime TEXT,
              first_seen TEXT, path TEXT               -- die Datei liegt auf Platte
```

Zwei Entscheidungen darin:

**Append-only.** Ein Papier, das sich ändert (Ergebnis nachgetragen, Titel
korrigiert, Anlage ergänzt), erzeugt eine neue Zeile mit neuem `fetched_at`.
Damit ist die Geschichte eines Vorgangs da — wann kam das Ergebnis? — ohne dass
das je jemand geplant haben muss.

**PDF-Bytes behalten, auf Platte, nach Inhalt adressiert.** Die
Textextraktion ist eine abgeleitete Sicht: heute `pypdf`, morgen ein
Layout-Parser, der Tabellen und den Abschnitt „Beschlussvorschlag" erkennt,
übermorgen OCR für die 19 Dokumente ohne Textebene. Ohne die Bytes ist jede
Verbesserung ein erneuter Abruf bei fünf bis zwanzig Städten. Kosten: ~150 KB
je Datei, bei 30.000 Papieren im Jahr rund 4,5 GB — auf dem VPS unter
`data/cities-files/<sha[:2]>/<sha>.pdf`, nicht im Abzug für die lokale Arbeit.
Wer das nicht will, setzt eine Aufbewahrungsfrist; die Rohablage merkt sich
dann nur den Hash.

### Schicht 1: Normalisiert

Die acht Objekte als Tabellen, Spaltennamen wie im OParl-Schema, dazu **wenige
kanonische Felder**, jeweils mit dem Rohwert daneben:

```sql
bodies          id, name, state, ris_vendor, oparl_url, license, population
organizations   id, body_id, name, kind_raw, kind         -- council|committee|district|faction|administration|other
meetings        id, body_id, organization_id, name, start, end, state_raw, cancelled
agenda_items    id, meeting_id, number, position, name, public,
                result_raw, outcome,                       -- accepted|amended|rejected|postponed|noted|referred|withdrawn|none
                resolution_text, resolution_file_id
papers          id, body_id, reference, name, date, paper_type_raw,
                kind,                                      -- motion|amendment|inquiry|answer|proposal|report|notice|petition|other
                originator_org_id, under_direction_of_id
files           id, paper_id | agenda_item_id | meeting_id, role,   -- main|auxiliary|resolution|invitation|protocol
                name, mime, size, access_url, sha256
consultations   id, paper_id, meeting_id, agenda_item_id, organization_id, role_raw, authoritative
```

Die kanonischen Felder (`kind`, `outcome`, `organizations.kind`) sind
absichtlich **kurze, stabile Listen** — dieselben, die Oldenburg heute schon
benutzt (`council_decisions.outcome` kennt genau diese Werte). Sie werden per
Regel aus dem Rohwert abgeleitet, und der Rohwert bleibt stehen, damit eine
bessere Regel später neu ableiten kann.

Was hier **nicht** steht: Themenfeld, Instrument, Übertragbarkeit,
Zusammenfassung, Beträge, Orte. Das alles sind Meinungen eines Modells und
gehören in Schicht 3.

### Schicht 2: Text

```sql
texts   file_id, extractor, version, text, n_pages, quality, extracted_at,
        PRIMARY KEY (file_id, extractor, version)
```

`extractor` ist heute `pypdf`, `quality` sagt, ob Textebene vorhanden war.
Ein neuer Extraktor schreibt eine neue Zeile; welche Fassung die Anwendungen
lesen, entscheidet eine Registry (§ 6), nicht die Tabelle.

### Schicht 3: Annotationen — der Kern der Flexibilität

```sql
annotations   object_kind TEXT, object_id TEXT,
              annotator TEXT, version TEXT,
              payload JSON, source_hash TEXT,
              model TEXT, cost_usd REAL, created_at TEXT,
              PRIMARY KEY (object_kind, object_id, annotator, version)
```

Eine Tabelle für alles, was jemand über ein Objekt sagt. Beispiele für
`annotator`: `policy_field`, `instrument`, `transferability`, `summary`,
`amounts`, `locations`, `actors`, `deadline`, `legal_basis`. Jede neue Frage
an die Dokumente ist ein neuer Annotator — **keine Schemaänderung, keine
Migration.** Der Prompt-Wechsel aus Phase 0 wäre hier `version: "2"` neben
`version: "1"`, beide vorhanden, das Golden Set vergleicht sie, die Anwendung
liest die als aktiv markierte.

Drei Details, die das tragen:

- **`source_hash`** ist der Hash des Eingabetexts. Ein Lauf rechnet nur, was
  sich geändert hat oder noch fehlt — dasselbe Muster wie `council.viertel`
  heute. Ein Neustart nach Absturz kostet nichts.
- **`payload` ist JSON**, seine Form definiert der Leser. Wer nach einem Feld
  filtern will, legt einen Ausdrucksindex an:
  `CREATE INDEX … ON annotations(json_extract(payload,'$.field'))` — SQLite
  kann das seit 3.9. Für die heißen Pfade materialisiert eine View
  `annotation_values(object_id, annotator, key, value)`.
- **Annotationen gelten für jede Objektart.** Ein Papier bekommt ein
  Themenfeld, eine Sitzung eine Zusammenfassung, eine Fraktion ein Profil, ein
  Tagesordnungspunkt eine Tragweite — dieselbe Tabelle, derselbe Mechanismus.

### Schicht 4: Indizes

```sql
chunks             text_id, chunk_idx, chunk_text, span_start, span_end, text_hash
chunk_embeddings   text_id, chunk_idx, model, vector BLOB
object_embeddings  object_kind, object_id, model, source_hash, vector BLOB
neighbors          model, a_kind, a_id, b_kind, b_id, score, computed_at
papers_fts         FTS5 über name, reference, text, summary
```

Zwei Punkte gegenüber heute: **`model` ist Teil des Schlüssels**, damit das
heutige MiniLM (384 Dimensionen) und ein besseres multilinguales Modell
nebeneinander liegen und ein Eval sie vergleicht, bevor eins gewinnt. Und
**`neighbors` kennt keine Städtegrenze**: Nachbar eines Oldenburger Beschlusses
kann ein Osnabrücker Antrag sein und umgekehrt — das ist der Block „Anderswo
beschlossen" auf der Beschluss-Seite, und er ist symmetrisch.

Zur Größe: 30.000 Papiere im Jahr × ~8 Chunks × 1,5 KB Vektor ≈ 360 MB im
Jahr. In den Arbeitsspeicher gehören nur die Dokument-Vektoren (45 MB), die
Chunk-Vektoren werden je Stadt geladen. Wächst es über fünf Jahrgänge und
zwanzig Städte hinaus, ist `sqlite-vec` der nächste Schritt — dieselbe Datei,
ein Index statt einer Matrix. Nicht jetzt.

## 4. Die Pipeline: sechs Stufen, jede für sich neu startbar

```
fetch → normalize → extract → chunk+embed → annotate → index
```

Jede Stufe liest die Tabellen der vorigen und schreibt ihre eigenen; ihr
Fortschritt steht je Objekt in

```sql
stages   object_kind, object_id, stage, version, status, error, at
```

Damit lässt sich jede Stufe einzeln wiederholen — neuer Extraktor: nur
`extract` und alles danach; neuer Prompt: nur `annotate` für diesen Annotator;
neues Embedding-Modell: nur `chunk+embed` mit neuem `model`. Kein Lauf fasst
Schicht 0 an außer `fetch`.

**Ein Schreiber je Datei.** Phase 0 hat fünf Threads auf eine SQLite-Datei
losgelassen; einer starb still. Die Pipeline arbeitet Stadt für Stadt oder
schreibt je Stadt eine eigene Datei und führt am Ende zusammen — beides ist
im Probelauf erprobt.

**Adapter je Dialekt**, mit den vier gemessenen Fallen eingebaut: ALLRIS 4
(alt→neu, `limit` ignoriert, Filter tot, undatierte Altpapiere), Somacos
Session (`next` verliert den Filter ab Seite 3, Dateien unter `auxiliaryFile`),
more! rubin (OParl 1.0, Volltext im File-Objekt, keine Filter), Magdeburg
(`getfile.asp?id=…&type=do` statt der genannten URLs). Und ein fünfter Adapter
liest Oldenburg aus `council.sqlite` — kein Netz, dieselben acht Objekte.

**Erste Füllung** aus dem Probelauf: `~/.cache/ratslotse/phase0/peers.sqlite`
enthält bereits die Rohantworten (`papers.raw`) und Texte von 2.967 Vorlagen;
sie wandern per Skript in Schicht 0 und 1, ohne erneut zu ernten.

## 5. Was damit möglich wird — ohne dass es geplant war

Der Test für die Flexibilität ist, ob Fragen beantwortbar sind, die heute
niemand stellt. Eine Auswahl, jede nur Lesezugriffe auf Schicht 1 bis 4:

- **Gezielte Suche** über den vorhandenen Stack der KI-Frage — Query-Expansion,
  BM25 plus Vektor, Cross-Encoder, Antwort mit Belegen. Technisch ein weiterer
  Kanal in `RESEARCH_CHANNELS` (`council/qa.py`); die Oldenburger KI-Frage kann
  dann „in Osnabrück wurde dazu 2026 beschlossen …" mitantworten.
- **Lücken in beide Richtungen.** Instrument-Cluster über Bodies; „fehlt in
  Oldenburg" und „fehlt in Osnabrück" sind ein Parameter.
- **Wellen.** Wann tauchte „Hitzeaktionsplan" wo zuerst auf, wie lange bis zum
  Beschluss, in welcher Reihenfolge übernahmen es die Städte? Aus `papers.date`,
  `consultations` und dem Annotator `instrument`.
- **Fraktionsprofile über Städte.** Was beantragen Grüne in Münster, das Grüne
  in Oldenburg nicht beantragen? `originator_org_id` × `policy_field`.
- **Erfolgsquoten je Stadt und Art.** `kind` × `outcome` — Oldenburgs
  Antrags-Erfolgsquote hat so erstmals einen Vergleichswert.
- **Verwaltungsantworten als Wissensquelle.** Anfragen samt Antworten sind in
  Magdeburg und Potsdam die Hälfte des Bestands; sie erklären, wie eine
  Verwaltung ein Problem sieht. Heute nutzt das niemand. Es liegt da.
- **Benachrichtigung** „Neu in Osnabrück zu deinem Thema" über
  `notify.einreihen`, gespeist aus `neighbors`.

Keine dieser Fragen braucht eine neue Tabelle. Die meisten brauchen einen
neuen Annotator, also einen Prompt und eine Zeile in der Registry.

## 6. Die Registry: Annotatoren als Code

Wie `kern/features.py` und `city_topics.py`: eine Liste in Python, im Pull
Request sichtbar, mit Wächter-Test.

```python
ANNOTATORS = {
    "policy_field":    Annotator(version="1", model="deepseek/deepseek-v4-flash",
                                 prompt="peer_policy_field", schema=PolicyFieldPayload,
                                 applies_to=("paper",), active=True),
    "transferability": Annotator(version="2", ..., active=True),
    "transferability_v1": ...(version="1", active=False),   # bleibt für den Eval
}
```

Jeder Eintrag nennt Prompt (aus `kern/prompts.py`), Modell, Payload-Form
(pydantic, damit der API-Vertrag und die Typprüfung sie kennen), Objektart und
ob er aktiv ist. `tests/` prüft: kein Annotator ohne Prompt, kein Payload ohne
Schema, kein aktiver Annotator ohne Golden-Set-Eintrag in `eval/`.

## 7. Was bewusst nicht gespeichert wird

- **Personen.** `oparl:Person`, `originatorPerson`, Kontaktdaten,
  Mitgliedschaften. Für die Frage „welche Fraktion" reicht die Organisation.
  Ratsmitglieder anderer Städte gehören nicht in unsere Datenbank; das ist
  dieselbe Linie, die `stammdaten.py` für Oldenburg zieht.
- **Nichtöffentliches.** Nur `public = true`; OParl 1.1 kennt `omit_internal`.
- **Nutzerdaten.** Diese Datei trägt keine Konten; sie fällt damit von selbst
  aus `COUNCIL_USER_OWNED_TABLES` und dem Konto-Löschen heraus.

## 8. Speicherort und Verdrahtung

Eigene Datei **`data/cities.sqlite`** neben den beiden bestehenden. Gründe:
anderer Lebenszyklus (Vollneuaufbau darf Oldenburg nicht berühren), andere
Größe (in einem Jahr größer als `council.sqlite` heute), und der lokale Abzug
bleibt optional. Store-Klasse `council/cities/store.py` nach den Regeln aus
`council/CLAUDE.md` (Schema und Migration getrennt), Anbindung ans Backend wie
die anderen beiden. Englische Bezeichner durchgehend — `cities`, nicht
`staedte`.

Oldenburg liegt **doppelt**: einmal wie heute in `council.sqlite` (dort hängt
die ganze Anwendung dran), einmal als Body in `cities.sqlite` über den
Adapter. Das ist Absicht und billig: 9.000 Beschlüsse, 5.000 Vorlagen. Erst
wenn `cities.sqlite` sich bewährt hat, ist die Frage erlaubt, ob die
Oldenburg-Auswertungen umziehen.

## 9. Regeln, die die Flexibilität schützen — als Tests

1. **Schicht 1 trägt keine Meinung.** Ein Wächter kennt die erlaubten Spalten
   von `papers` und Co.; eine neue Spalte muss dort eingetragen werden, und die
   Begründung muss sagen, warum es keine Annotation ist.
2. **Jede Annotation hat `version` und `source_hash`.** Ohne beides keine Zeile.
3. **Jede Stufe ist idempotent.** Zweimal laufen lassen ändert nichts — ein
   Test führt jede Stufe doppelt auf einem kleinen Bestand aus und vergleicht.
4. **Rohes wird nie gelöscht, nur ergänzt.** Kein `DELETE`/`UPDATE` auf
   `raw_*` außerhalb einer Aufbewahrungsregel für Bytes.
5. **Kein Personen-Objekt.** Ein Test hält die Liste der Objektarten fest.

## 10. Reihenfolge

| Schritt | Inhalt | Aufwand |
|---|---|---|
| 1 | Schicht 0–2: Store, fünf Adapter plus Oldenburg-Adapter, `fetch`/`normalize`/`extract`, Übernahme des Phase-0-Bestands, wöchentlicher Cron mit Kennzahlen | 5–7 Tage |
| 2 | Schicht 3–4: Registry, die drei Annotatoren aus Phase 0 als erste Kunden, Chunks, Embeddings, FTS, Nachbarn über Städte; Golden Set nach `eval/` | 4–5 Tage |
| 3 | Erste Anwendung: Block „Anderswo beschlossen" auf der Beschluss-Seite und in der App, Kanal in der KI-Frage — hinter dem Schalter `andere-staedte` | 4–5 Tage |
| 4 | Lücken in beide Richtungen, Wellen, Benachrichtigung | danach |

Schritt 1 ist der, der die Flexibilität festlegt. Alles danach ist
austauschbar — das ist der Punkt.

## Zur Bewertung, die du nicht abgeben konntest

Dass du die 50 Fundstücke nicht inhaltlich beurteilen kannst, ist kein
Rückschlag, sondern der Hinweis, wer das Produkt braucht: Menschen, die
Oldenburgs Verwaltung kennen — Ratsmitglieder, Fraktionsgeschäftsstellen. Für
die Technik reicht eine andere Frage, die du beantworten kannst: **Passt der
Treffer zur Frage?** Das ist die Trefferqualität der Suche, nicht die
Sinnhaftigkeit der Politik, und sie lässt sich mit 20 Fragen in einer halben
Stunde messen — wie bei den Stadion-Fragen. Die inhaltliche Prüfung machen
dann die ersten zwei, drei Nutzer*innen mit Mandat, wenn der Block auf dev
steht.
