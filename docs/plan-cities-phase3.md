# Umsetzungsplan Phase 3: von tausend Urteilen zu den zwanzig Ideen, die zählen

Stand: 08.09.2026. Dieser Plan folgt auf
[`plan-cities-phase2.md`](plan-cities-phase2.md) (acht PRs, #1194–#1203,
alle gemergt) und ist wie seine Vorgänger geschrieben: **ohne das Gespräch
dahinter ausführbar**. Jeder Abschnitt ist ein Pull Request, nennt Dateien,
Signaturen, Tests, Kosten und woran man erkennt, dass er fertig ist. Wo etwas
gemessen ist, steht die Zahl und in Anhang C der Befehl, der sie liefert.

Wer das umsetzt, liest **vorher** vollständig: die Wurzel-`CLAUDE.md`,
`council/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, dazu §0 der
beiden Vorgängerpläne (die Regeln 1–13 gelten unverändert), die Bewertung
[`bewertung-staedte-speicher.md`](bewertung-staedte-speicher.md) und die
Docstrings von `council/cities/evidence.py`, `fit.py`, `annotators.py`,
`index.py` und `store.py` — sie erklären, warum die Dinge so gebaut sind, wie
sie sind, und dieser Plan wiederholt das nicht.

## 0. Die Richtung, die Tim vorgegeben hat

> „Ich würde erstmal noch nicht so viel Frontend bauen, sondern erst wirklich
> hinbekommen, dass die Daten geil sind, wir geil mit den Daten arbeiten
> können, da wirklich was Sinnvolles rauskommt." (Tim, 08.09.2026)

Daraus folgen vier Regeln, die zu 1–13 dazukommen:

14. **Kein PR dieses Plans baut eine Oberfläche.** Die Seiten aus Phase 2
    bleiben, wie sie sind; was hier entsteht, sehen sie erst, wenn PR 22
    die Konstanten umstellt. Ein PR, der etwas Neues sichtbar machen will,
    wartet auf Phase 4.
15. **Jeder PR endet mit einer Messung gegen den Bestand**, und die Messung
    steht im PR-Text als Tabelle „vorher / nachher". Was nicht messbar ist,
    wird nicht behauptet. Die Messskripte liegen in `scripts/` oder `eval/`
    und sind wiederholbar — kein Einmalcode im Scratchpad.
16. **Das Golden Set wächst, es wird nicht ersetzt.** Neue Fälle kommen zu
    den vierzig dazu; jeder trägt einen Satz Begründung. Wer ein altes
    Urteil ändert, schreibt in den Satz, warum — zwei Korrekturen stehen in
    §2 schon an.
17. **Ein neuer Annotator oder eine neue Fassung liegt neben der alten**
    (`(annotator, version)` im Schlüssel), bis die Messung entschieden hat.
    Die alte wird erst gelöscht, wenn keine Oberfläche mehr auf sie zeigt.

## 1. Zielbild

Heute: 1.168 Einzelurteile „fehlt / lohnt sich", jedes für sich belegt, in
Summe aber wenig aussagekräftig — **51 % aller Urteile lauten „fehlt" +
„lohnt sich"**. Eine Liste, auf der jede zweite Idee ein Volltreffer ist, ist
keine Liste, sondern ein Katalog. Und beim Durchgehen der vierzig
Prüffälle waren die Belege in **11 von 40** Fällen erkennbar unpassend
(Ernährungsstrategie als Beleg beim Notruf, Ferienpass bei
Zweckentfremdung, Klävemann-Stiftung beim Straßenbau).

Am Ende dieses Plans beantwortet der Speicher drei Fragen, jede mit Zahlen
belegt:

```
  ┌───────────────────────────┐ ┌───────────────────────────┐ ┌──────────────────────────┐
  │ A  Welche IDEE kommt in   │ │ B  Hat Oldenburg das —    │ │ C  Wie ging es DORT aus? │
  │    mehreren Städten vor,  │ │    und wie sicher wissen  │ │    Oldenburgs vertagte   │
  │    und Oldenburg hat sie  │ │    wir das? (Belegsuche,  │ │    Sachen, gespiegelt an │
  │    nicht?  (Cluster)      │ │    Mehrheitsurteil)       │ │    den Beschlüssen der   │
  │                           │ │                           │ │    anderen               │
  └─────────────┬─────────────┘ └─────────────┬─────────────┘ └────────────┬─────────────┘
                │                             │                            │
  ┌─────────────┴─────────────────────────────┴────────────────────────────┴─────────────┐
  │ Städte-Speicher, VOLLSTÄNDIG eingeordnet und indiziert (heute: 19 % / 47 %)          │
  │ + Aufwandsklasse je Idee  + Ideen-Cluster über Städte  + Belegsuche wie die KI-Frage │
  └──────────────────────────────────────────────────────────────────────────────────────┘
```

**Die eine Erkenntnis, die den Plan ordnet:** Oldenburg liegt als Stadt
Nummer null im selben Speicher. Sobald *alle* Oldenburger Vorlagen eingeordnet
sind und die Ideen über Städte geclustert werden, steht „hat Oldenburg das?"
zum ersten Mal **strukturell** da — ein Cluster mit einem Oldenburger
Mitglied — und nicht nur als Modellmeinung. Das ist der zweite, unabhängige
Kanal zu `fit`, und die beiden müssen übereinstimmen.

## 2. Was gemessen ist und den Plan trägt

Alle Zahlen vom 08.09.2026 gegen `data/cities.sqlite` (596 MB) und
`data/council.sqlite`; Befehle in Anhang C.

| Befund | Zahl | trägt |
|---|---|---|
| Papiere im Speicher / davon eingeordnet (`classify`/2) | 19.166 / 3.714 (19 %) | PR 16 |
| Oldenburger Papiere / davon eingeordnet | 5.945 / 710 | PR 16, 19 |
| Papiere mit Objektvektor (MiniLM) / (mpnet, verworfen) | 8.949 / 16.585 | PR 16 |
| Osnabrück: Papiere / mit Text | 2.864 / 843 | PR 16 |
| Magdeburg: TOPs mit Ergebnis / Papiere mit Ergebnis | 5.982 / **0** | PR 16 |
| Potsdam: Papiere / mit Beratungsstation | 700 / 498 | PR 16 |
| Osnabrück: Papiere / TOPs überhaupt | 2.864 / 2.700 | PR 16 |
| Übertragbare Papiere (`adaptable`+`direct`) | 1.511 | PR 18–20 |
| davon Anfragen/Antworten (`inquiry`+`answer`) | 463 (31 %) | PR 18 |
| Verschiedene Instrument-Texte / in ≥ 2 Städten wortgleich | 1.461 / **5** | PR 19 |
| `fit`-Urteile / davon `missing`+`yes` | 1.168 / 599 (51 %) | PR 20 |
| Golden Set: erwarteter Beleg unter den fünf nächsten Nachbarn | 19 / 23 | PR 17 |
| Golden Set: Status-Treffer / `worth`-Treffer (`flash`, Mittel aus 7 Läufen) | 62–70 % / 55–60 % | PR 17, 20 |
| Golden Set: falsches „vorhanden" in 7 Läufen | 0 | Schranke bleibt |
| Bestandslauf: verworfene Urteile in 750 / davon erfundene Kennung | 4 / 0 | Schranke bleibt |
| Kosten `classify` / `fit` je 1.000 Papiere (`deepseek-v4-flash`) | 0,26 $ / 0,64 $ | Anhang A |

**Zwei Korrekturen am Golden Set stehen an** (aus meinem Durchgang der
vierzig Fälle am 08.09. — [`bewertung-40-ideen.md`](bewertung-40-ideen.md),
Tim liest gegen): Fall „Zuschussvereinbarungen
freie Kulturträger" (Osnabrück) von `worth: maybe` auf `yes` — Oldenburg hat
Verstetigungsvereinbarungen im Sozialen (29782), die Form auf Kultur zu
übertragen ist ein naheliegender Antrag. Fall „THG-Bilanz Kernverwaltung"
(Münster) von `status: present` auf `partial` — Oldenburg bilanziert
gesamtstädtisch (27588), eine eigene Verwaltungsbilanz ist nicht belegt; das
Modell hatte hier recht. Beide gehören in PR 17, mit dem Satz dazu.

## PR 16 — Der Bestand wird vollständig, und drei Datenlücken schließen sich

Kein Konzept, kein Prompt — Rechenzeit, rund 4 $, und drei Reparaturen. Ohne
diesen PR misst jeder spätere gegen einen Fünftel-Bestand.

### 16.1 Warum der Bestand hinterherhinkt

PR 9 hat die Historie geholt (Münster, Magdeburg, Potsdam liefen noch, als
Phase 2 endete), aber `check_cities.py` ordnet je Lauf höchstens
`ANNOTATE_MAX = 3000` ein und der Index läuft danach — beides ist für den
Wochentakt richtig und für einen Backfill zu klein. Ergebnis: 15.452 Papiere
ohne Einordnung, 10.217 ohne Vektor. Und `fit` prüft nur Kandidaten mit
Einordnung, sieht also nur ein Fünftel der Städte.

### 16.2 Backfill-Stufen für Einordnung und Index (`scripts/cities_backfill.py`)

`--stage` bekommt zwei Werte dazu: `annotate` und `index`.

```python
p.add_argument("--stage", action="append",
               choices=("fetch", "normalize", "extract", "annotate", "index"))
p.add_argument("--annotate-max", type=int, default=None,
               help="Deckel je Lauf (Vorgabe: kein Deckel — das ist der Backfill)")
```

`annotate` ruft `pipeline.annotate(main, body_id=…, limit=a.annotate_max)`
für die Annotatoren **ohne** `needs_index`, `index` ruft
`pipeline.index_all(main, body_id=…)`. `fit` läuft hier bewusst nicht — es
kommt in PR 20 mit neuer Fassung und würde sonst zweimal bezahlt.

**Reihenfolge auf der Kommandozeile ist die Reihenfolge der Stufen**, die
Vorgabe bleibt `fetch,normalize,extract`; wer alles will, sagt es. Der
Bericht (ohne `--run`) bekommt zwei Spalten dazu: `ohne Einordnung`, `ohne
Vektor` — aus zwei neuen Zahlen in `CitiesStore.stats()`:

```python
def stats(self) -> list[dict]:
    # … bestehende Spalten …
    #   papers_unclassified: Papiere ohne Annotation `classify` (jede Fassung)
    #   papers_unembedded:   Papiere ohne Objektvektor unter EMBED_MODEL
```

`tests/test_cities_store.py::test_stats_zaehlt_den_rueckstand` legt zwei
Papiere an, ordnet eins ein, und erwartet `papers_unclassified == 1`.

### 16.3 Osnabrück: Text für 2.021 Papiere nachziehen

Die Ernte brach am 08.09. nach 2.864 Vorlagen an einem `\uda00` ab
(`text.clean` wirft Surrogate seit #1195 weg); die Stufe `extract` ist für
Osnabrück nie durchgelaufen. Dateien und SHA sind da (2.864 / 2.864), Text
fehlt bei 2.021. Kein Code: `--run --body osnabrueck --stage extract`. Der
PR trägt die Zahl danach.

### 16.4 Magdeburg: Beratungsstationen führen ins Leere

Magdeburg hat 9.416 Tagesordnungspunkte, 5.982 davon mit Ergebnis — und
**null** Papiere, die darüber ein Ergebnis bekommen. Der Grund ist gemessen
(Anhang C.3): Die Stationen zeigen auf
`…/oparl/bodies/0001/agendaitems/516027`, die Tagesordnungspunkte in
`agenda_items` heißen aber `…/oparl/bodies/0001/meetings/123925#top-0` — der
Session-Adapter (`council/cities/adapters/session.py`) **erzeugt** die
TOP-Kennung aus Sitzung und Position, statt die OParl-`id` des `agendaItem`
zu übernehmen. Bei Münster fällt das nicht auf, weil Münsters Stationen
offenbar dieselbe erzeugte Form tragen oder der Adapter dort einen anderen
Weg nimmt (1.918 von 2.957 Papieren haben ein Ergebnis).

Vorgehen: Im Adapter die `id` des `agendaItem`-Objekts nehmen, wo eine da
ist, und die erzeugte Form nur als Rückfall (der Fall ohne `id` existiert:
`#top-` ohne Nummer steht schon im Bestand). Danach `normalize` für Magdeburg
und Münster neu — die Rohablage bleibt, `upsert_batch` ersetzt. Ein Test in
`tests/test_cities_adapters.py` hält ein Magdeburger `meeting`-Rohobjekt mit
zwei TOPs samt `id` fest (gekürzt, ohne Personen) und erwartet, dass die
Station aus einem `paper`-Rohobjekt ihren TOP findet.

Dieselbe Prüfung für Potsdam (498 von 700 mit Station, ALLRIS — anderer
Adapter, vermutlich andere Ursache).

**Osnabrück ist ein Fenster-Problem, kein Kennungs-Problem:** 137 Sitzungen,
alle ab 2025-09 — die Papiere reichen bis 2022-11, die Sitzungen wurden nur
im Fenster der ersten Ernte geholt. Ob `since` im ALLRIS-Adapter
(`adapters/allris4.py`) auch auf `meeting` wirkt, ist zu prüfen; dann
`--stage fetch --since 2022-11-01` für Osnabrück, und danach `normalize`.
Erwartung: Papiere mit Ergebnis von 444 auf > 1.200 (die Registry-Notiz
sagt „Ergebnis an 46 % der TOPs").

### 16.5 Aufräumen im Vorbeigehen

`council/cities/evidence.py` definiert `OLDENBURG_STECKBRIEF` **zweimal**
wortgleich untereinander (Zeilen ~52 und ~78; die zweite Zuweisung gewinnt).
Eine Definition bleibt. Kein Verhalten ändert sich, `source_hash` bleibt
gleich.

### 16.6 Abnahme

Der PR-Text trägt die Tabelle aus §2, Zeilen 1–7, als „vorher / nachher".
Ziel: Papiere ohne Einordnung < 100 (Reste sind leere Texte), ohne Vektor 0,
Osnabrück mit Text > 2.700, Magdeburg Papiere mit Ergebnis > 400. Dazu die
Kosten des Laufs aus `annotations.cost_usd` (erwartet: 15.452 × 0,26 $ ≈
4 $).

## PR 17 — Belegsuche wie die KI-Frage

Der Engpass aus §1. Heute sucht `evidence_for` drei Dinge: die fünf nächsten
Oldenburger *Papiere* (Objektvektor über den ganzen Text), Volltext auf die
Wörter des Instruments (drei Stufen), den Themenfeld-Rückblick. Was fehlt,
weiß die KI-Frage längst: **Suchbegriffe vom Modell erweitern lassen**
(`council/qa.py::expand_query`, Prompt `qa_search_terms`), **auf Chunk-Ebene
suchen** statt nur auf Objekt-Ebene (34.000 Chunk-Vektoren liegen ungenutzt
in `chunk_embeddings`), und **die Rats-Datenbank selbst befragen**
(`council_decisions_fts`, Vorlagen-Embeddings) — dort stehen Beschlusstexte
und Ergebnisse, die der Städte-Speicher für Oldenburg nicht trägt.

### 17.1 Die vier Arme (`council/cities/evidence.py`)

```python
EvidenceKind = Literal["neighbor", "chunk", "fts", "decision", "recap"]
TRAGENDE_ARTEN = ("neighbor", "chunk", "fts", "decision")   # in fit.py

MAX_EVIDENCE = 8          # statt 5 + 3; die Fusion ordnet, nicht die Quelle
MIN_NEIGHBOR_SCORE = 0.70 # bleibt — modellspezifisch, s. index.py
MIN_CHUNK_SCORE = 0.62    # Chunks sind kürzer, ihre Nähe streut breiter; GEMESSEN
                          # am Golden Set festlegen, nicht raten (17.4)

def search_terms(classification: dict, paper: dict) -> list[str]:
    """Drei bis fünf Suchbegriffe je Idee — vom Modell, mit Cache.

    Wie ``qa.expand_query``, aber mit eigenem Prompt ``cities_evidence_terms``:
    Eingabe sind Instrument, Zusammenfassung und Titel; Ausgabe sind Wörter,
    die in einem OLDENBURGER Vorlagentitel stünden — Synonyme und
    Verwaltungsdeutsch („Sondernutzung" für „Außengastronomie",
    „Schulbegleitung" für „Lernbegleiter"). Ohne Ortsnamen. Bei Fehler:
    ``_woerter(instrument)`` wie heute.
    """

def evidence_for(main, rats, paper, classification, model, *,
                 k: int = MAX_EVIDENCE) -> list[Evidence]:
    """Vier Arme, dann Reciprocal Rank Fusion (RRF_K = 60 wie in store.py):

    1. neighbor — wie heute, Oldenburg-Kanten ≥ 0,70
    2. chunk    — Anfragevektor aus (instrument + summary) gegen
                  chunk_embeddings der Oldenburger Dateien; Treffer werden
                  auf ihr Papier abgebildet, je Papier zählt der beste Chunk
    3. fts      — Volltext im Städte-Speicher über die Suchbegriffe aus
                  search_terms(), dieselben drei Stufen wie heute
    4. decision — rats.search_decisions_fts(" ".join(terms)) → Beschlüsse;
                  Kennung ``oldenburg:decision:<id>``; Titel, Datum, Ergebnis,
                  Fraktionen und simple_summary aus rats.get_decision
    Der Rückblick kommt wie heute als fünfte, nicht tragende Zeile dazu.
    """
```

Das Chunk-Suchen braucht eine Store-Methode, die es noch nicht gibt —
`search_ideas` in `store.py` sucht über Objektvektoren, nicht über Chunks:

```python
def chunk_search(self, vector: bytes, model: str, body_id: str,
                 limit: int = 40) -> list[dict]:
    """Nächste Chunks eines Körpers zum Anfragevektor.

    Liest die Matrix je (model, body_id) EINMAL in den Prozess und hält sie
    (wie ``council.embeddings._matrix``); der Backfill ruft das zehntausend
    Mal, ein Request nie. → [{file_id, chunk_index, paper_id, score, text}]
    """
```

`decision`-Belege lösen sich in der Oberfläche anders auf als Papiere:
`_belege_aufloesen` im Router (`web/backend/app/routers/council.py`) bekommt
den Zweig `oldenburg:decision:<id>` → Link auf `/council/decision/<id>`.
Das ist die **einzige** Berührung einer Oberflächen-Datei in diesem Plan und
bleibt unsichtbar, bis PR 22 die Fassung umstellt (Regel 14).

### 17.2 Was sich am Urteil ändert

Nichts am Prompt. `fit` v1 bekommt bessere Belege und sonst dieselbe Frage.
**Aber:** `source_hash` enthält die Beleg-Kennungen — jede Vorlage bekommt
also neue Belege und wird neu beurteilt. Das ist gewollt und kostet den
vollen Preis (1.511 × 0,64 $ ≈ 1 $ für die heutigen Kandidaten, nach PR 16
das Vierfache). Deshalb läuft der Bestandslauf **nicht** in diesem PR, sondern
erst in PR 20 mit der neuen Fassung; hier wird nur gemessen.

### 17.3 Das Golden Set trägt seine Belege — die müssen neu

`eval/cases_cities_fit.json` bettet die Belege ein, damit der Eval ohne
Datenbank läuft. Nach diesem PR sind sie veraltet. Deshalb:

```bash
python eval/run_cities_fit.py --belege-neu    # braucht data/cities.sqlite + council.sqlite
```

schreibt für jeden Fall `evidence` neu aus `evidence_for` und lässt
`expected`, `judgment`, `paper` unverändert. Ein Fall, dessen
`expected.evidence` danach nicht mehr in `evidence` vorkommt, wird **als
Zeile gemeldet, nicht still repariert** — das ist genau die Messung, um die es
geht. Die Datei wird committet; der Diff zeigt, was die neue Suche findet.

Die zwei Korrekturen aus §2 kommen im selben Commit in `expected` und
`judgment`.

### 17.4 Der Eval, der ohne Modell auskommt (`eval/run_cities_evidence.py`, neu)

```bash
python eval/run_cities_evidence.py          # 0 $, Sekunden
```

Für jeden Fall mit `expected.evidence`: Steht jede erwartete Kennung unter
den ersten `MAX_EVIDENCE` Belegen, und auf welchem Rang? Für Fälle mit
`status: missing`: Wie viele Belege kommen zurück (Rauschmaß — mehr als vier
für etwas, das Oldenburg nicht hat, sind verdächtig)?

| Kennzahl | heute (Nachbarn allein) | Schwelle |
|---|---|---|
| erwartete Belege gefunden | 19 / 23 | ≥ 22 / 23 |
| mittlerer Rang des erwarteten Belegs | 1,9 | ≤ 2,0 |
| Belege je `missing`-Fall (Median) | — messen | ≤ 4 |

`MIN_CHUNK_SCORE` wird hier festgelegt: den Wert wählen, bei dem die erste
Zeile ihr Maximum hat, ohne dass die dritte über 4 geht. Der gewählte Wert
steht mit seiner Messung als Kommentar an der Konstante.

Dann `eval/run_cities_fit.py` mit den neuen Belegen, dreimal: Erwartung ist
Status ≥ 70 % (heute 62–70), `worth` unverändert, falsches „vorhanden"
weiter 0. Bleibt der Status unter 65, ist der PR nicht fertig — dann sind die
Belege besser, aber das Modell kann sie nicht lesen, und die Prompt-Zeile
„Ein Beleg der Art decision trägt das Ergebnis der Abstimmung" fehlt.

### 17.5 Tests (PR 17)

- `tests/test_cities_fit.py`: `test_belege_kommen_aus_vier_quellen` (ersetzt
  „drei"), `test_chunk_treffer_werden_auf_ihr_papier_abgebildet`,
  `test_beschluss_belege_tragen_ihre_kennung` (`oldenburg:decision:<id>`
  wird von `pruefe` als erlaubt erkannt, `kvonr_aus` gibt `None`),
  `test_suchbegriffe_fallen_auf_die_instrumentwoerter_zurueck` (LLM-Fehler →
  `_woerter`).
- `tests/test_cities_store.py`: `test_chunk_search_findet_den_naechsten_chunk`
  mit drei handgeschriebenen Vektoren.
- `tests/test_prompt_schluessel.py` kennt `cities_evidence_terms`.
- `tests/test_cities_router.py`: `_belege_aufloesen` löst eine
  Beschluss-Kennung auf.

## PR 18 — Die Aufwandsklasse: Anfrage ist nicht Antrag ist nicht Programm

31 % der übertragbaren Papiere sind Anfragen oder deren Antworten. „Eine
Anfrage zu Fußwegbreiten stellen" und „ein Darlehensprogramm für
Genossenschaften einführen" stehen heute gleichberechtigt auf einer Liste.
Ein Ratsmitglied unterscheidet das sofort — nach *Aufwand* und nach *Hebel*.

### 18.1 Ein neuer Annotator, keine neue `classify`-Fassung

Eine dritte `classify`-Fassung hieße 19.166 Papiere neu für 5 $. Die
Aufwandsklasse braucht nur die 1.511 übertragbaren (nach PR 16: ~6.000) —
also ein eigener Annotator, nach dem Muster, das `annotators.py` dafür
vorsieht („eine neue Frage ist ein Eintrag hier plus ein Prompt"):

```python
EFFORT_VALUES = ("inquiry", "review", "resolution", "decision", "budget")
#  inquiry     eine Anfrage an die Verwaltung (Antwort, Bericht) — kostet nichts
#  review      ein Prüfauftrag: „die Verwaltung möge prüfen und berichten"
#  resolution  eine Resolution an Land/Bund — keine eigene Zuständigkeit
#  decision    ein Beschluss mit unmittelbarer Wirkung (Satzung, Richtlinie,
#              Konzept, Programm) ohne nennenswerten Haushaltsposten
#  budget      ein Beschluss, der Geld bindet (Förderprogramm, Stelle, Bau)

class IdeaEffort(BaseModel):
    effort: Literal[EFFORT_VALUES]
    #: Der Adressat in Oldenburg, wenn es die Stadt nicht selbst ist:
    #: „Eigenbetrieb Gebäudewirtschaft", „VWG", „Großleitstelle" — sonst None.
    #: Frei, aber kurz (≤ 60 Zeichen), damit er als Hinweis taugt.
    addressee: str | None = None

ANNOTATORS["effort"] = Annotator(
    key="effort", version="1", applies_to=("paper",),
    payload=IdeaEffort, prompt_system="cities_effort_system",
    prompt_user="cities_effort_user", batch_size=8, input_chars=1500,
    max_tokens=2000, only_usable=True)
```

`only_usable: bool = False` ist ein neues Feld an `Annotator`;
`pipeline.annotate` schränkt die Kandidaten damit auf `classify.transfer in
USABLE` ein — dieselbe Regel wie `fit.candidates_for`, an einer Stelle.

### 18.2 Prompt und Golden Set

`PROMPT_CITIES_EFFORT` in `kern/prompts.py`, mit sechs erfundenen Beispielen
(nicht aus dem Prüfstand — die Lehre aus PR 10). Golden Set
`eval/cases_cities_effort.json` mit 40 Fällen, aus den vorhandenen vierzig
`fit`-Fällen abgeleitet (sie sind schon gelesen; die Aufwandsklasse steht in
meiner Bewertung vom 08.09. implizit drin: 14 davon sind Anfragen).
`eval/run_cities_effort.py` nach dem Muster von `run_cities_transfer.py`,
Schwelle 85 % (fünf Klassen mit klaren Kanten; das ist einfacher als
`transfer`).

### 18.3 Was die Aufwandsklasse sofort ermöglicht

Nichts sichtbar (Regel 14), aber `CitiesStore.ideas()` bekommt den Filter
`effort: Sequence[str] = ()` — als whole-statement-SQL wie die anderen (die
Falle mit `test_sql_spalten.py` steht in `store.py` dokumentiert) — und
`idea_fields()` zählt je Feld auch je Klasse. PR 20 nutzt die Klasse im
Urteil, PR 22 zeigt sie.

### 18.4 Abnahme

Verteilung über die übertragbaren Papiere als Tabelle im PR; Erwartung nach
der Stichprobe: `inquiry` ~30 %, `review` ~20 %, `decision` ~30 %, `budget`
~15 %, `resolution` ~5 %. Weicht es stark ab, ist eher der Prompt falsch als
der Bestand.

## PR 19 — Ideen-Cluster über Städte

Das stärkste Signal, das der Speicher hergeben kann, und heute unerreichbar:
1.461 verschiedene Instrument-Texte, nur **fünf** davon wortgleich in zwei
Städten. „Zweckentfremdungssatzung erlassen" steht siebenmal so da — und
„Satzung gegen Zweckentfremdung von Wohnraum", „Zweckentfremdungsverbot
prüfen" daneben, ungezählt.

### 19.1 Ideen einbetten, nicht Papiere

Der Objektvektor eines Papiers trägt den ganzen Text — Ortsnamen, Datum,
Antragsteller. Für die Frage „ist das dieselbe Idee?" ist das Rauschen. Die
Idee ist `instrument` + `summary` aus `classify`, und nur die wird
eingebettet:

```python
# council/cities/clusters.py (neu)
IDEA_KIND = "idea"           # object_kind in object_embeddings; kein Schema
CLUSTER_VERSION = "1"

def idea_text(classification: dict) -> str:
    return f"{classification['instrument']}. {classification.get('summary', '')}"

def embed_ideas(main: CitiesStore, model: str = EMBED_MODEL) -> int:
    """Objektvektor unter object_kind='idea' für jedes übertragbare Papier
    ALLER Städte — Oldenburg eingeschlossen. Hash über idea_text, wie
    embed_objects: unverändert = nicht neu gerechnet."""

def build_clusters(main: CitiesStore, model: str = EMBED_MODEL,
                   threshold: float = IDEA_THRESHOLD) -> dict:
    """Agglomerativ (average linkage) über die Kosinus-Nähe; ein Cluster ist
    eine Menge von Papieren, deren paarweise Nähe im Mittel ≥ threshold liegt.
    Schreibt idea_clusters neu (ersetzt die Fassung unter (model, version)).
    Cluster mit einem Mitglied werden NICHT gespeichert — sie sind keine."""
```

**`IDEA_THRESHOLD` wird gemessen, nicht geraten** (19.3). Erste Erwartung
0,80 auf MiniLM — deutlich über den 0,70 der Papier-Nachbarschaft, weil die
Texte kürzer und gleichförmiger sind.

### 19.2 Schema — eine Tabelle, ein Annotator

```sql
CREATE TABLE idea_clusters (
  model TEXT NOT NULL, version TEXT NOT NULL,
  cluster_id INTEGER NOT NULL,          -- fortlaufend je (model, version)
  paper_id TEXT NOT NULL REFERENCES papers(id),
  score REAL NOT NULL,                  -- Nähe zum Cluster-Zentrum
  PRIMARY KEY (model, version, paper_id)
);
CREATE INDEX idea_clusters_cluster ON idea_clusters(model, version, cluster_id);
```

Migration in `CitiesStore._migrate`, `schema_version` 1 → 2. Der Name des
Clusters kommt vom Modell — als Annotation auf `object_kind='cluster'`,
`object_id = f"{version}:{cluster_id}"`:

```python
class ClusterLabel(BaseModel):
    label: str = Field(max_length=80)        # „Zweckentfremdungssatzung"
    #: Was die Mitglieder gemeinsam haben, ein Satz — und was nicht.
    summary: str = Field(default="", max_length=300)

ANNOTATORS["cluster_label"] = Annotator(key="cluster_label", version="1",
    applies_to=("cluster",), payload=ClusterLabel, batch_size=10, …)
```

`annotations_missing` wirft heute `NotImplementedError` für alles außer
`paper` — der Zweig für `cluster` kommt dazu (liest aus `idea_clusters`
`DISTINCT cluster_id`).

### 19.3 Messung, die den Schwellwert festlegt (`scripts/cities_cluster_bericht.py`)

```bash
python scripts/cities_cluster_bericht.py --threshold 0.78 0.80 0.82 0.85
```

Je Schwelle: Zahl der Cluster, Mitglieder gesamt, Cluster mit ≥ 2 Städten,
Cluster mit Oldenburg-Mitglied — **und zwei Kontrollen**: Die sieben
„Zweckentfremdungssatzung erlassen" und die fünf „Kommunale Wärmeplanung
beschließen" müssen je in EINEM Cluster liegen (Recall), und dreißig
zufällige Cluster werden ausgedruckt und von Hand gelesen (Precision — Tim
oder das umsetzende Modell; das Ergebnis steht als Zahl im PR). Die Schwelle
ist die höchste, bei der die beiden Kontrollgruppen noch zusammenliegen.

Der Bericht ist danach das Werkzeug, mit dem man **Frage A** beantwortet:

```
Cluster 217  „Verpackungssteuer / Mehrweg"                    4 Städte, 6 Papiere
   osnabrueck  2026-03  Antrag   accepted   Mehrweg fördern – Müll, Kosten …
   muenster    2025-11  Antrag   referred   Einführung einer Verpackungssteuer
   potsdam     2026-01  Anfrage  —          Kommunale Verpackungssteuer
   oldenburg   2025-05  Bericht  noted      Informationen zur Verpackungssteuer
```

`--ohne-oldenburg` listet nur Cluster ohne Oldenburger Mitglied, nach Zahl
der Städte sortiert — das ist die Liste der zwanzig Ideen aus dem Titel
dieses Plans, zum ersten Mal.

### 19.4 Was der Cluster für `fit` bedeutet

Ein Oldenburger Mitglied im Cluster ist ein Beleg der stärksten Sorte: gleiche
Idee, in Oldenburgs eigenem Rat. PR 20 gibt ihn als `Evidence(kind="cluster")`
ins Urteil — tragend. Und ein Cluster **ohne** Oldenburger Mitglied ist eine
Aussage, die das Modell heute nicht bekommt: „In 5.945 Oldenburger Vorlagen
seit 2018 ist keine mit dieser Idee." Das steht dann als Zeile im Prompt.

### 19.5 Tests (PR 19)

- `tests/test_cities_index.py`: `test_ideen_werden_nicht_als_papiere_eingebettet`
  (object_kind), `test_cluster_mit_einem_mitglied_wird_nicht_gespeichert`,
  `test_zwei_gleiche_ideen_liegen_in_einem_cluster` (handgeschriebene
  Vektoren, kein fastembed).
- `tests/test_cities_store.py`: Migration 1 → 2 idempotent;
  `annotations_missing("cluster", …)`.
- `tests/test_cities_guards.py::test_schicht_1_traegt_keine_meinung` kennt die
  neue Tabelle als Schicht 4.

## PR 20 — `fit` Fassung 2: Cluster, Aufwand, Mehrheit, und ein strengeres „lohnt sich"

Die drei Signale aus PR 17–19 fließen ins Urteil, und das Urteil wird dreimal
gefällt.

### 20.1 Was das Modell zusätzlich erfährt (Prompt `PROMPT_CITIES_FIT` v2)

Drei neue Zeilen im Nutzer-Prompt, aus dem Bestand gerechnet, nicht vom
Modell:

```
Aufwandsklasse: decision (Beschluss ohne nennenswerten Haushaltsposten)
Gleiche Idee in anderen Städten: 3 (Osnabrück 2026 angenommen, Münster 2025
  verwiesen, Potsdam 2026 offen)
In Oldenburgs 5.945 Vorlagen seit 2018: KEINE mit dieser Idee (Cluster ohne
  Oldenburger Mitglied) — bzw. — 2 Oldenburger Vorlagen mit dieser Idee,
  siehe Belege der Art cluster
```

Dafür bekommt `EvidenceKind` den Wert `"cluster"` (tragend), und
`evidence_for` legt Oldenburger Cluster-Mitglieder als erste Belege vor —
vor den Nachbarn, denn sie sind die genaueren. Jeder Annotator dieses Plans
trägt außerdem sein `gut_wenn` (das Feld gibt es schon): für `fit`/2 die
Schwellen aus 20.4 in einem Satz.

Und ein strengeres `worth`. Heute lautet die Anweisung sinngemäß „lohnt sich,
wenn Oldenburg es nicht hat und es in seiner Zuständigkeit liegt" — das
trifft auf die Hälfte zu. Neu, als geschlossene Bedingungen im Prompt:

- `yes` **nur**, wenn (a) die Idee in ≥ 2 Städten vorkommt ODER ein
  Oldenburger Anknüpfungspunkt belegt ist (ein vertagter Antrag, ein
  Prüfauftrag, ein Beschluss, der genau das offen lässt) UND (b) die
  Aufwandsklasse nicht `resolution` ist UND (c) kein Adressat außerhalb der
  Stadt (`effort.addressee`) die Sache allein entscheidet.
- `maybe` für alles, was fehlt und übertragbar ist, aber weder (a) noch einen
  Oldenburger Anlass hat.
- `no` wie heute, plus: Aufwandsklasse `inquiry` ohne jeden Oldenburger
  Anlass — eine Anfrage, die niemand gestellt hat, ist keine Idee.

Erwartung: `missing`+`yes` fällt von 51 % auf 15–20 %. Das ist die Zahl, die
der PR-Text trägt.

### 20.2 Mehrheit aus drei (`council/cities/fit.py`)

```python
VOTES = 3            # je Vorlage drei Aufrufe, temperature=0.3
def majority(urteile: list[OldenburgFit]) -> OldenburgFit | None:
    """Status und worth je per Mehrheit; bei 1-1-1 gewinnt der vorsichtigere
    Wert (missing < partial < present; maybe < yes/no). Belege: Vereinigung
    der genannten, aber nur die, die ≥ 2 Urteile nennen. reason/why_worth
    vom Urteil, das der Mehrheit entspricht und die höchste confidence trägt.
    confidence: high nur bei 3-0."""
```

`pruefe` läuft je Einzelurteil **vor** der Mehrheit — ein verworfenes zählt
nicht mit; bleibt eins übrig, wird es gespeichert mit `confidence=low`.
Kosten: 3 × 0,64 $ ≈ 2 $ je 1.000, bei ~6.000 Kandidaten nach PR 16 rund
12 $ für den Bestand. Ob die Mehrheit die Streuung halbiert, misst 20.4;
tut sie es nicht, bleibt `VOTES = 1` und der Code, mit der Messung als
Kommentar.

### 20.3 Registrierung

`ANNOTATORS["fit"]` bekommt `version="2"`; v1 bleibt in der Tabelle, bis
PR 22 die Oberfläche umstellt (`IDEEN_FIT = ("fit", "2")` in `store.py`) und
danach ein Aufräumlauf `DELETE FROM annotations WHERE annotator='fit' AND
version='1'` — als Stufe in `cities_backfill.py --stage prune`, nicht von
Hand.

### 20.4 Golden Set auf 80, Eval mit Streuungsmaß

Vierzig neue Fälle, gezogen nach PR 16 **stratifiziert**: je Themenfeld drei
bis vier, je Aufwandsklasse mindestens fünf, mindestens zehn aus Clustern mit
≥ 2 Städten, mindestens acht mit Oldenburger Cluster-Mitglied. Jeder mit
Satz. Die fünf ⚠-Fälle aus meiner Bewertung (Sozialmonitoring,
Hundefreiläufe, Welcome Center, Ernährungsstrategie, Armutsbericht) werden
dabei **nachrecherchiert** — in der Rats-Datenbank, nicht im Gedächtnis — und
ihr `expected` festgelegt.

`eval/run_cities_fit.py --laeufe 5` läuft fünfmal und meldet neben den
Quoten die **Spannweite** über die Läufe. Schwellen neu:

| | v1 heute | Schwelle v2 |
|---|---|---|
| Status-Treffer (3 Klassen) | 62–70 % | ≥ 72 % |
| `worth`-Treffer | 55–60 % | ≥ 65 % |
| Spannweite Status über 5 Läufe | 12 Punkte | ≤ 6 |
| falsches „vorhanden" | 0 | 0 |
| erfundene Kennung | 0 | 0 |
| Anteil `missing`+`yes` im Bestand | 51 % | 15–25 % |

### 20.5 Tests (PR 20)

`test_mehrheit_nimmt_den_vorsichtigeren_wert_bei_patt`,
`test_verworfene_einzelurteile_zaehlen_nicht`,
`test_cluster_beleg_ist_tragend`, `test_prompt_traegt_die_drei_zeilen`
(Aufwand, Städtezahl, Oldenburg-Zeile), `test_v1_und_v2_liegen_nebeneinander`.

## PR 21 — Die Gegenrichtung: Wie ging es dort aus?

Frage C. Oldenburg hat die Zweckentfremdungssatzung vertagt (29787), die
Grundsteuer C berichtet (30125), die Verpackungssteuer geprüft (27723). Ein
Ratsmitglied will am Abend vor der Sitzung wissen: *Was haben die anderen
daraus gemacht, und woran ist es gescheitert?* Die Daten liegen nach PR 16
und 19 da — Cluster mit Ergebnis je Mitglied. Was fehlt, ist die Begründung.

### 21.1 Die Store-Frage (`council/cities/store.py`)

```python
def cluster_of(self, paper_id: str, model: str, version: str = CLUSTER_VERSION
               ) -> list[dict]:
    """Alle Mitglieder des Clusters, in dem dieses Papier liegt — mit
    body_id, name, date, kind, web und dem Ergebnis aus outcome_for_paper.
    Leer, wenn das Papier in keinem Cluster ist. Whole-statement-SQL."""
```

Für Oldenburger Papiere ist das die Antwort auf C in Rohform; für fremde ist
es die Zeile „Gleiche Idee in anderen Städten" aus PR 20.

### 21.2 Warum ein Beschluss so ausging (Annotator `outcome_reason`)

Für fremde Papiere mit `outcome in (rejected, postponed, amended, referred)`
— nach PR 16 einige hundert — extrahiert ein Annotator aus dem Papiertext
**und dem Text der Beschlussausfertigung**, falls die Stadt eine liefert
(Münster: `auxiliaryFile`; ALLRIS: `result_raw` am TOP ist oft ein Satz),
warum:

```python
class OutcomeReason(BaseModel):
    reason: str = Field(max_length=300)     # „Verwaltung sah keine Rechtsgrundlage
                                            #  nach § 12 NKomVG; verwiesen in den
                                            #  Finanzausschuss"
    #: Woraus das stammt — damit die Oberfläche später zeigen kann, ob es
    #: aus dem Protokoll oder nur aus dem Antragstext gelesen ist.
    source: Literal["result_text", "paper_text", "unknown"]
```

Ohne `result_raw` und ohne Ausfertigung liefert der Annotator
`source="unknown"` und `reason=""` — **er rät nicht** aus dem Antrag, wie die
Abstimmung ausging. Golden Set 25 Fälle, Eval nach Muster, Schwelle: `source`
zu 90 % richtig, `reason` von Hand gelesen (25 Sätze).

### 21.3 Der Bericht, der Tim die Antwort gibt (`scripts/cities_gegenrichtung.py`)

```bash
python scripts/cities_gegenrichtung.py --kvonr 29787
python scripts/cities_gegenrichtung.py --offen     # alle vertagten/verwiesenen
                                                   # Oldenburger Anträge seit 2024
```

Druckt je Oldenburger Papier seinen Cluster mit Ergebnis und Grund je Stadt.
Das ist noch keine Oberfläche (Regel 14), aber die Probe, ob C funktioniert:
Von den Oldenburger Anträgen mit `outcome='postponed'` seit 2024 sollen
**mindestens ein Drittel** einen Cluster mit ≥ 1 fremdem Mitglied haben, das
ein Ergebnis trägt. Ist es weniger, liegt es an PR 16.4 (Ergebnisse fehlen),
nicht an PR 19.

## PR 22 — Cron, Kennzahlen, Umstellung

### 22.1 `check_cities.py` lernt die neuen Stufen

Nach `index_all` und vor `fit`: `clusters.embed_ideas`, `clusters.build_clusters`
(Minuten, lokal), dann `cluster_label`, `effort`, `outcome_reason` über
`pipeline.annotate`, dann `fit` v2 (`nach_index=True` wie heute). Neue
Kennzahlen im Rückgabe-dict: `clusters`, `clusters_multi_city`,
`clusters_without_oldenburg`, `judged_votes`, `effort_*` je Klasse. In
`kern/jobs.py` bleibt der Takt (wöchentlich); `max_age_h` prüfen, der Lauf
wird länger (Schätzung: +40 Minuten für den Cluster-Schritt bei 6.000 Ideen).

### 22.2 Die Oberflächen zeigen auf die neuen Fassungen

`IDEEN_FIT = ("fit", "2")`, `IDEEN_CLASSIFY` bleibt. Zwei Felder kommen an
`Idea` im Vertrag dazu, **ohne Layoutänderung**: `effort` (Aufwandsklasse)
und `peers` (Zahl der Städte im Cluster) — die Ideen-Seite und die App
bekommen dafür je ein kleines Etikett neben dem Status, mehr nicht. Das ist
der einzige sichtbare Schritt des Plans, und er ist bewusst am Ende: Erst
wenn die Zahlen stimmen, lohnt ein Pixel. Bild an Tim (Regel 10), Web und
App (Regel 11), `ios_vertrag.py` (zwei neue optionale Felder — die
ausgelieferte App bricht nicht).

### 22.3 Prune

`cities_backfill.py --run --stage prune` löscht `fit`/1 und die
Objektvektoren des verworfenen mpnet-Modells (16.585 Zeilen, 131.726 Kanten
— ein Drittel der Datei). Vorher Bericht, was fällt.

## Anhang A — Reihenfolge, Aufwand, Kosten

| PR | Was | Netz/LLM | Kosten | Bild an Tim |
|---|---|---|---|---|
| 16 | Bestand vollständig, drei Datenlücken | Ernte, Einordnung, Index | ~4 $ + Stunden CPU | nein |
| 17 | Belegsuche mit vier Armen, Eval ohne Modell | Suchbegriffe (`flash-lite`, ~0,05 $/1.000) | < 1 $ | nein |
| 18 | Aufwandsklasse `effort` | ja | ~1,5 $ (6.000 × 0,25 $) | nein |
| 19 | Ideen-Cluster | lokal CPU + `cluster_label` | ~0,3 $ | nein (30 Cluster lesen) |
| 20 | `fit` v2, Mehrheit, Golden Set 80 | ja | ~12 $ (3 Stimmen) | die 40 neuen Sätze |
| 21 | Gegenrichtung, `outcome_reason` | ja | ~0,5 $ | nein |
| 22 | Cron, Umstellung, zwei Etiketten | nein | 0 | ja (Web + App) |

Sequenziell: 16 zuerst, alles andere misst gegen ihn. 17 und 18 sind
voneinander unabhängig, 19 braucht 16 (Oldenburg eingeordnet), 20 braucht
17, 18 und 19, 21 braucht 16.4 und 19, 22 braucht alle. Wer parallel
arbeiten kann: 17 und 18 zugleich, dann 19, dann 20 und 21 zugleich.

Gesamt rund 20 $ an Modellkosten und zwei bis drei Arbeitstage.

## Anhang B — Was ausdrücklich NICHT in diesem Plan liegt

- **Neue Städte.** Leipzig, Kiel, Lübeck stehen erreichbar in der Registry.
  Erst wenn die sechs sauber sind (PR 16), lohnt eine siebte — und dann ist
  es ein Registry-Eintrag plus Backfill, kein PR.
- **Antragsentwürfe schreiben lassen.** „Formuliere aus der Münsteraner
  Vorlage einen Antrag für Oldenburg" ist naheliegend und liegt eine Stufe
  über dem, was hier gesichert wird: Erst wenn `worth: yes` verlässlich ist,
  darf ein Modell darauf aufbauen.
- **Ein Rückkanal aus der Oberfläche** („stimmt / stimmt nicht" je Urteil).
  Das wäre das billigste Golden Set der Welt, aber es ist Frontend, und es
  braucht Nutzer*innen mit Mandat auf Prod — beides ist Phase 4.
- **Zeitreihen** („welche Idee taucht 2026 neu auf?"). Die Daten liegen nach
  PR 19 da (Cluster + Datum je Mitglied); die Frage ist ein Bericht, kein
  Bau. Wer sie stellen will, erweitert `cities_cluster_bericht.py` um
  `--seit`.
- **Ein anderes Sprachmodell für `fit`.** Gemessen in PR 10: `pro` bringt
  +8 Punkte Status für den elffachen Preis und −14 auf `worth`. Vor einem
  neuen Versuch müssen 17–20 durch sein; sie verschieben die Grundlage.

## Anhang C — Messbefehle

Alle gegen den lokalen Bestand; Python 3.12 aus `.venv`, oder `python3` mit
`sqlite3` allein für C.1–C.3.

### C.1 Rückstand je Stadt (die Zeilen 1–4 aus §2)

```python
import sqlite3; c = sqlite3.connect("data/cities.sqlite")
for r in c.execute("""
  SELECT p.body_id, count(*),
    sum(NOT EXISTS(SELECT 1 FROM annotations a WHERE a.object_id=p.id AND a.annotator='classify')),
    sum(NOT EXISTS(SELECT 1 FROM object_embeddings o WHERE o.object_id=p.id AND o.model LIKE '%MiniLM%')),
    sum(NOT EXISTS(SELECT 1 FROM files f JOIN texts t ON t.file_id=f.id WHERE f.paper_id=p.id))
  FROM papers p GROUP BY 1"""): print(r)   # Stadt, Papiere, ohne Einordnung, ohne Vektor, ohne Text
```

### C.2 Ergebnisse je Stadt (Zeile 5–7)

```python
for r in c.execute("""
  SELECT m.body_id, count(a.id), sum(a.outcome!='none'),
    (SELECT count(DISTINCT c2.paper_id) FROM consultations c2 JOIN papers p2 ON p2.id=c2.paper_id
      WHERE p2.body_id=m.body_id),
    (SELECT count(DISTINCT c3.paper_id) FROM consultations c3 JOIN agenda_items a3 ON a3.id=c3.agenda_item_id
      JOIN papers p3 ON p3.id=c3.paper_id WHERE p3.body_id=m.body_id AND a3.outcome!='none')
  FROM agenda_items a JOIN meetings m ON m.id=a.meeting_id GROUP BY 1"""): print(r)
# Stadt, TOPs, TOPs mit Ergebnis, Papiere mit Station, Papiere mit Ergebnis
```

### C.3 Magdeburg: wohin zeigen die Stationen? (PR 16.4)

```python
print(c.execute("""SELECT agenda_item_id FROM consultations c JOIN papers p ON p.id=c.paper_id
  WHERE p.body_id='magdeburg' LIMIT 2""").fetchall())
print(c.execute("""SELECT a.id FROM agenda_items a JOIN meetings m ON m.id=a.meeting_id
  WHERE m.body_id='magdeburg' LIMIT 2""").fetchall())
# Gemessen 08.09.2026:
#   Station → …/oparl/bodies/0001/agendaitems/516027
#   TOP     → …/oparl/bodies/0001/meetings/123925#top-0
```

Die Rohobjekte dazu liegen in `raw_objects.body_json` (`kind='meeting'`
bzw. `'paper'`, `body_id='magdeburg'`).

### C.4 Instrument-Überschneidung (Zeile 10)

```python
import collections
inst = collections.defaultdict(set)
for body, pl in c.execute("""SELECT p.body_id, a.payload FROM annotations a JOIN papers p ON p.id=a.object_id
  WHERE a.annotator='classify' AND json_extract(a.payload,'$.transfer') IN ('adaptable','direct')"""):
    i = (json.loads(pl).get("instrument") or "").strip().lower()
    if i: inst[i].add(body)
print(len(inst), sum(len(s) >= 2 for s in inst.values()))
```

### C.5 Urteilsverteilung (Zeile 11)

```python
for r in c.execute("""SELECT json_extract(payload,'$.status'), json_extract(payload,'$.worth'), count(*)
  FROM annotations WHERE annotator='fit' AND version='1' GROUP BY 1,2 ORDER BY 3 DESC"""): print(r)
```

### C.6 Golden-Set-Belege (Zeile 12) und Urteile (13–14)

```bash
python scripts/cities_modellvergleich.py --modell sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
python eval/run_cities_fit.py --model deepseek/deepseek-v4-flash   # ~0,03 $ je Lauf
```
