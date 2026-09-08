# Umsetzungsplan Phase 2: vom Block zur Lückenanalyse

Stand: 08.09.2026. Dieser Plan folgt auf
[`plan-cities-umsetzung.md`](plan-cities-umsetzung.md) (sieben PRs, alle
gemergt) und setzt die Befunde aus
[`bewertung-staedte-speicher.md`](bewertung-staedte-speicher.md) in Arbeit
um. Er ist wie der erste geschrieben: **ohne das Gespräch dahinter
ausführbar**. Jeder Abschnitt ist ein Pull Request, nennt Dateien,
Signaturen, Tests und woran man erkennt, dass er fertig ist. Wo etwas
gemessen ist, steht die Zahl; wo eine Entscheidung offen wäre, ist sie
getroffen — und wo Tim sie getroffen hat, steht sein Name daneben.

Wer das umsetzt, liest **vorher** vollständig: die Wurzel-`CLAUDE.md`,
`council/CLAUDE.md`, `web/backend/CLAUDE.md`, `web/frontend/CLAUDE.md`,
`web/frontend/DESIGNSPRACHE.md`, `ios/CLAUDE.md`, `scripts/CLAUDE.md`,
`tests/CLAUDE.md` — und Abschnitt 0 des ersten Plans, dessen Regeln hier
unverändert gelten. Dazu die Bewertung, denn sie begründet jede Reihenfolge
hier.

## 0. Was gegenüber dem ersten Plan dazukommt

Die Regeln 1–9 aus `plan-cities-umsetzung.md` §0 gelten weiter. Vier kommen
hinzu, alle aus den sieben PRs gelernt:

10. **Jeder PR, der eine Oberfläche berührt, schickt Tim vor dem Merge ein
    Bild** — `SendUserFile`, Ausschnitt statt ganzer Seite, hell und dunkel,
    und wartet auf sein Gegenlesen. Das gilt für Web **und** App. Nach dem
    Gegenlesen darf gemergt werden, ohne zweites Nachfragen, wenn seine
    Anmerkungen umgesetzt sind.
11. **Web und App bleiben featuregleich.** Was das Web bekommt, bekommt die
    App im Folge-PR; nie stapeln, aber auch nie einen Web-PR ohne den
    iOS-Nachzug im Plan.
12. **Jede Zahl im PR-Text ist gegen den Bestand gemessen**, nicht geschätzt.
    Der Bestand liegt lokal (`data/cities.sqlite`, nach PR 9 auch mit
    Historie). Die Messskripte stehen am Ende der Bewertung.
13. **Was ein Modell über Oldenburg sagt, trägt seine Belege bei sich.** Ein
    Urteil ohne Beleg-Kennungen wird nicht gespeichert (PR 10). Das ist die
    Verlängerung von Regel 9 („Schicht 1 trägt keine Meinung") auf Schicht 3.

## 1. Zielbild

Drei Dinge, die Nutzer*innen sehen, und ein Fundament darunter:

```
  ┌─────────────────────────┐  ┌──────────────────────────────┐  ┌────────────────┐
  │ A  „Anderswo beschlossen"│  │ B  „Ideen aus anderen Städten"│  │ C  Freie Suche │
  │    auf der Beschluss-    │  │    je Themenfeld: was andere  │  │   „Was haben   │
  │    Seite (gibt es; wird  │  │    haben und Oldenburg fehlt, │  │    andere zu…?"│
  │    zehnmal so oft        │  │    mit Urteil und Belegen     │  │                │
  │    erscheinen)           │  │                               │  │                │
  └────────────┬────────────┘  └──────────────┬───────────────┘  └───────┬────────┘
               │                              │                          │
  ┌────────────┴──────────────────────────────┴──────────────────────────┴────────┐
  │ Städte-Speicher (council/cities): Oldenburg VOLLSTÄNDIG seit 2018,            │
  │ fünf Städte seit 2023; Einordnung `classify` + neu `fit` (Oldenburg-Eignung); │
  │ Nachbarschaften über Stadtgrenzen; Volltextindex                              │
  └───────────────────────────────────────────────────────────────────────────────┘
```

A gibt es; PR 8 repariert seine Brücke und schärft ihn. B ist die Idee aus
dem ursprünglichen Auftrag („Wo gibt es Lücken in Oldenburg, die andere
schon angegangen sind?") und braucht das Fundament aus PR 9 und das Urteil
aus PR 10. C ist der Volltextindex mit einem Fenster nach vorn.

**Die eine Entscheidung, die alles ordnet:** Das Urteil „hat Oldenburg das
schon, und lohnt sich ein Antrag?" fällt ein Modell, nicht ein Ratsmitglied
(Tim, 08.09.2026). Damit ist PR 10 kein Warten auf jemanden, sondern ein
Annotator wie `classify` — mit Golden Set, Eval und Regressionsschwelle.
Was das Modell nicht darf: ohne Beleg urteilen.

## 2. Was gemessen ist und den Plan trägt

Aus der Bewertung, hier nur die Zahlen, an denen ein PR hängt:

| Befund | Zahl | trägt |
|---|---|---|
| Beschlüsse mit `kvonr` / mit `template_number` | 274 / 6.553 von 9.059 | PR 8 |
| Block erscheint heute / über die Vorlagennummer | 50 / 486 Seiten | PR 8 |
| Stichprobe 12: gut / schwach / Gattungs-Rauschen | 6 / 2 / 4 | PR 8 |
| Rauschfälle mit `local`/`one_off` auf der fremden Seite | 4 von 4 | PR 8 |
| Vorlagen im Fenster mit Block: heute / nur übertragbare Treffer | 361 / 190 | PR 8 |
| Oldenburger Vorlagen mit Beschluss seit 2018 / im Speicher | 4.864 / 512 | PR 9 |
| Oldenburger Anträge im Speicher (nur als Anlage) | 62 | PR 9 |
| Fremde übertragbare Papiere / ohne Oldenburger Gegenstück | 1.290 / 922 | PR 10 |
| Kanten 0,70–0,75 / ≥ 0,85 | 1.290 / 80 von 2.416 | PR 14 |
| Treffer aus Osnabrück + Braunschweig | 1.371 von 2.416 | Anhang B |
| Gegenprobe Phase 0: 54 Cluster → fehlt/teilweise/vorhanden | 29 / 13 / 11 für 0,014 $ | PR 10 |

## PR 8 — Die Brücke, der Filter, die Bewertung

Klein, ohne Netz, ohne Schema. Repariert einen Fehler, setzt einen
Produktentscheid um, legt die Bewertung ins Repo.

### 8.1 Brücke über die Vorlagennummer (`web/backend/app/routers/council.py`)

Heute in `decision_elsewhere`:

```python
kvonr = beschluss.get("kvonr")
if not kvonr:
    return {"decision_id": decision_id, "items": [], "bodies": []}
```

Neu — die Vorlage über ihre Nummer auflösen, `kvonr` nur als Rückfall:

```python
kvonr = beschluss.get("kvonr")
if not kvonr and beschluss.get("template_number"):
    vorlage = store.get_vorlage_by_nr(beschluss["template_number"])
    kvonr = vorlage["kvonr"] if vorlage else None
if not kvonr:
    return {"decision_id": decision_id, "items": [], "bodies": []}
```

`get_vorlage_by_nr` gibt es (`council/store.py`), sie fällt von „22/0348/1"
auf „22/0348" zurück — genau die Fälle, in denen das Protokoll eine Fassung
zitiert, die die Tagesordnung unter der Grundnummer führt. **Reihenfolge
beachten:** `kvonr` am Beschluss ist, wo gesetzt, die genauere Angabe; die
Nummer ist der Rückfall, nicht umgekehrt.

Kein neues Feld im Vertrag, `ElsewhereResponse` bleibt. Die App braucht
nichts — das ist der Vorteil von Regel „Logik ins Backend".

### 8.2 Filter auf übertragbare Treffer

Im selben Endpunkt, direkt nach dem bestehenden `one_off`-Filter:

```python
from council.cities.annotators import USABLE   # ("adaptable", "direct")
…
if annotation.get("transfer") not in USABLE:
    continue
```

**Das ist ein Produktentscheid**, und er steht so hier, weil Tim der
Empfehlung nicht widersprochen hat (08.09.2026): Der Block zeigt nur noch,
was die Einordnung als übertragbar führt. Preis: Abdeckung im Fenster von
361 auf 190 Vorlagen. Gewinn: Alle vier Rauschfälle der Stichprobe fallen
weg, alle sechs guten bleiben. **Die eigene Seite (die Oldenburger Vorlage)
wird NICHT gefiltert** — das kostete Fall 1 (Satzung Mittagsverpflegung →
Braunschweiger Förderrichtlinie) und Fall 3 (Parkgebühren), gerade die
beiden, für die der Block da ist.

Ein Papier ohne Annotation (`transfer` fehlt) fällt damit ebenfalls raus.
Das ist richtig: Es ist noch nicht eingeordnet, der nächste Cron holt es
nach. Ein Test hält das fest (unten).

Der Kommentar über dem Filter nennt die Zahlen und den Grund („Gattung
statt Thema: B-Plan → B-Plan 0,84, Haushaltsvollzug → Haushaltssatzung
0,86; die Einordnung sieht es, eine Schwelle nicht").

### 8.3 Die Bewertung ins Repo

`docs/bewertung-staedte-speicher.md` liegt fertig im Worktree
`web-onboarding-ios-parity-7fdefe`, untracked. In diesen PR aufnehmen; ein
Verweis darauf in `docs/plan-cities-umsetzung.md` unter Anhang C („Was
danach kam") — eine Zeile.

### 8.4 Tests (PR 8)

`tests/test_cities_router.py`, drei neue Fälle im Stil der elf vorhandenen:

- `test_brücke_über_die_vorlagennummer`: Beschluss ohne `kvonr`, mit
  `template_number` „26/0468", `council_templates` kennt sie mit kvonr 4711
  → Treffer erscheinen. Dazu die Rückfall-Variante „26/0468/1".
- `test_kvonr_am_beschluss_gewinnt`: beides gesetzt, widersprüchlich →
  `kvonr` zählt.
- `test_nur_übertragbare_treffer`: drei Nachbarn mit `local`, `adaptable`,
  ohne Annotation → nur der `adaptable` erscheint.

`test_beschluss_ohne_vorlage_bekommt_eine_leere_liste` bleibt: Wahlen haben
weder `kvonr` noch `template_number`.

### 8.5 Abnahme

Gegen den echten Bestand, Server lokal mit `FEATURE_FLAGS=andere-staedte`:

```bash
# Wie viele Beschluss-Seiten zeigen jetzt einen Block? (Skript in der Bewertung)
# Erwartung vor dem Filter: ≥ 480; nach dem Filter: > 200 Beschlüsse
```

Und die zwölf Stichproben-Fälle aus der Bewertung nachziehen: 28300, 27983,
28403, 28229 zeigen **nichts** mehr; 28119, 28070, 28293, 28291, 29772, 29953
zeigen weiter ihre guten Treffer. Bild an Tim: die Beschluss-Seite 28119
(Mittagsverpflegung), die vorher **keinen** Block hatte, weil ihr die
`kvonr` fehlte.

**Fertig, wenn:** `pruefe.py` grün, die zwölf Fälle stimmen, Tims Gegenlesen
da ist. Changelog-Fragment `changelog.d/cities-8-bruecke.md`, Kategorie
`behoben`: „**„Anderswo beschlossen" erscheint jetzt auf zehnmal so vielen
Beschluss-Seiten** …“.

## PR 9 — Die Historie: Oldenburg vollständig, fünf Städte seit 2023

Fast kein Code. Ein Lauf, der Stunden dauert, und die Messung, ob er
gebracht hat, was er soll.

### 9.1 Warum der Bestand nur zwölf Monate hat

Die Registry sagt für alle Städte `since="2023-01-01"` und für Oldenburg
`since="2018-01-01"`; der Wochen-Cron ruft für die fremden Städte 60 Tage
Rückschau, für Oldenburg gar kein Fenster. Trotzdem liegen im Speicher zwölf
Monate: Er wurde aus der Phase-0-Datenbank befüllt
(`scripts/cities_import_phase0.py`, September 2025 bis September 2026), und
ein Backfill mit dem Registry-`since` ist **nie gelaufen**. Für Oldenburg
gilt dasselbe — wer nur den Cron laufen lässt, sieht keinen Fehler, nur
einen kleinen Bestand.

**Erst messen, dann laufen lassen:** Der Umsetzer prüft vor dem Backfill,
was der Oldenburg-Adapter aus der Rats-Datenbank für `since="2018-01-01"`
liefern würde, ohne zu schreiben — `pipeline.fetch(spec, …, since=None)`
gegen eine Kopie, dann `normalize` in eine Wegwerf-`CitiesStore` unter
`tmp_path`, dann `paper_count("oldenburg")`. Erwartung: nahe 5.090
(`council_templates`) plus die Anträge aus Anlagen. Liegt die Zahl weit
darunter, ist der Adapter der Verdächtige (`iter_papers`, die
Datumsprüfung), nicht die Daten.

### 9.2 Der Lauf

Nacheinander, nie parallel auf eine Datei (Regel 7):

```bash
# Oldenburg: kein Netz, Minuten
python scripts/cities_backfill.py --run --body oldenburg
# Die vier mit OParl: je Stadt Stunden — ein Aufruf je Sekunde je Host
python scripts/cities_backfill.py --run --body osnabrueck --since 2023-01-01
python scripts/cities_backfill.py --run --body braunschweig --since 2023-01-01
python scripts/cities_backfill.py --run --body muenster --since 2023-01-01
python scripts/cities_backfill.py --run --body potsdam --since 2023-01-01
python scripts/cities_backfill.py --run --body magdeburg --since 2023-01-01
# dann, einmal über alles:
python -c "…pipeline.annotate(store)…"    # rund 3–4 $ (gemessen: 0,27 $ je 1.000)
python -c "…pipeline.index_all(store)…"   # Minuten
```

`--parallel` existiert und erntet mehrere Städte gleichzeitig in getrennte
Rohdateien; das ist erlaubt (Regel 7 verbietet nur mehrere Schreiber auf
**eine** Datei). Wer es nutzt, achtet auf die `session`-Adapter — Münster
und Magdeburg sind langsam.

**Was nach dem Lauf zu erwarten ist**, hochgerechnet aus den zwölf
Monaten: Osnabrück ~1.800, Braunschweig ~1.900, Potsdam ~2.100, Magdeburg
~2.100, Münster ~1.100, Oldenburg ~5.500 (davon Anträge aus Anlagen im
hohen Hundert-Bereich statt 62). Zusammen rund 14.000 Papiere; die
Nachbarschaftsrechnung ist dafür gebaut (Blöcke von 256, „bei 30.000
Papieren Sekunden, nicht Minuten"). `cities.sqlite` wächst von 166 MB auf
grob 600 MB.

### 9.3 Was sich im Code ändert

- **`scripts/check_cities.py`** bekommt eine Kennzahl `papers_total` und
  `papers_oldenburg` im Rückgabe-dict, damit das Admin-Panel den Bestand
  zeigt und ein stiller Rückfall auf zwölf Monate auffiele.
- **`scripts/lokale_daten.py`** lernt `--mit-staedten`: `hol` und `setz`
  nehmen `cities.sqlite` mit, wenn gesetzt. Ohne den Schalter bleibt alles
  wie heute (600 MB will nicht jede*r). Test in `tests/test_lokale_daten.py`,
  falls vorhanden; sonst ein kurzer.
- **`docs-site`**: die Betriebsseite bekommt einen Absatz „Städte-Speicher:
  Backfill einmalig, danach Wochen-Cron“ mit den Befehlen oben.

### 9.4 Auf den Servern

**Auf dev laufen keine Crons** (Wurzel-`CLAUDE.md`). Der Block auf
dev.ratslotse.de zeigt also nur, was dort einmal von Hand geerntet wurde.
Der Backfill läuft auf dev deshalb einmal per `nohup` im Screen (Stunden),
mit demselben Befehl. Auf Prod übernimmt danach der Wochen-Cron; der erste
Prod-Lauf ist ebenfalls der Backfill und gehört in ein Wartungsfenster
angekündigt (Platte: `check_herzschlag.py` schaut auf den freien Platz —
600 MB müssen da sein).

### 9.5 Messung danach

Die Skripte aus der Bewertung erneut, und die Zahlen ins PR:

- Oldenburger Vorlagen mit Beschluss im Speicher: **≥ 4.500 von 4.864**.
- Oldenburger Anträge (`att:`): **> 300**.
- Abdeckung „Block erscheint": Beschluss-Seiten mit Block, vorher/nachher.
- Gegenrichtung: übertragbare fremde Papiere ohne Oldenburger Gegenstück —
  die Zahl **sinkt** gegenüber 922 von 1.290, weil Oldenburgs Geschichte
  jetzt Gegenstücke liefert. Sinkt sie nicht, stimmt etwas nicht.

**Fertig, wenn:** die vier Zahlen im PR stehen, `pruefe.py` grün, und die
Zwölf-Stichprobe aus der Bewertung erneut gezogen (gleicher `seed`) nicht
schlechter aussieht als vorher. Kein Bild nötig — keine Oberfläche ändert
sich. Changelog `changelog.d/cities-9-historie.md`, `geaendert`.

## PR 10 — Der Annotator `fit`: Hat Oldenburg das schon, und lohnt es sich?

Das Herzstück. Ein zweiter Annotator neben `classify`, nach demselben Muster
(Registry, Prompt als Code, pydantic-Nutzlast, `source_hash`, Eval mit
Golden Set). Der Unterschied: **Er bekommt Belege aus Oldenburg mit** und
darf ohne sie nicht urteilen.

### 10.1 Auf welche Papiere

Nur fremde Papiere mit `classify.transfer ∈ USABLE` — nach PR 9 grob 4.000
bis 5.000. Für alles andere ist die Frage sinnlos (ein Münsteraner
B-Plan „fehlt" Oldenburg nicht). Die Auswahl steht als Funktion
`annotate.candidates_for(main, ann)` und ist testbar; für `classify` gibt
sie alle Papiere zurück, für `fit` die Teilmenge.

### 10.2 Die Belege (`council/cities/evidence.py`, neu)

```python
@dataclass(frozen=True)
class Evidence:
    kind: Literal["neighbor", "fts", "recap"]
    id: str                 # paper-id (oldenburg:…) oder "recap:<field>"
    title: str
    date: str | None
    outcome: str | None
    text: str               # Zusammenfassung/Auszug, ≤ 500 Zeichen
    score: float | None

def evidence_for(main: CitiesStore, rats: CouncilStore, paper: dict,
                 classification: dict, model: str = EMBED_MODEL,
                 k_neighbors: int = 5, k_fts: int = 3) -> list[Evidence]:
```

Drei Quellen, in dieser Reihenfolge, dedupliziert nach `id`:

1. **Die nächsten Oldenburger Papiere** aus `main.neighbors(…, body=…)` —
   Achtung: `neighbors` liefert heute nur fremde Nachbarn
   (`cross_body_only=True` im Index). Für die Belege braucht es die Kanten
   **zu** Oldenburg: `neighbors("paper", <fremde id>)` gibt genau die,
   denn die Tabelle ist gerichtet und für ein fremdes Papier sind
   Oldenburgs Papiere die fremden. Die fünf besten, mit `score`.
   Zusammenfassung und Ergebnis aus der Rats-Datenbank: über die
   `kvonr` in der Kennung `oldenburg:paper:<kvonr>` →
   `rats.get_vorlage(kvonr)` (Titel) und die zugehörigen Beschlüsse
   (`summary`/`simple_summary`, `outcome`, `session_date`) — dafür eine
   kleine Store-Methode `decisions_for_kvonr(kvonr)` in
   `council/store.py`, falls es sie nicht gibt (prüfen; `vorlage_journey`
   liefert Stationen, nicht Zusammenfassungen).
2. **Volltextsuche** nach dem `instrument` der Einordnung über
   `main.fts_search(instrument, body_id="oldenburg")` — die drei besten.
   Das ist der Weg, auf dem Phase 0 „Zweckentfremdungssatzung: bisher nur
   politische Anträge" gefunden hat.
3. **Der Themenfeld-Rückblick** aus `council_field_recaps` (12 Zeilen, je
   Themenfeld eine Zusammenfassung der letzten Periode) als Kontext, was
   Oldenburg in dem Feld gerade beschäftigt. Kennung `recap:<field>`.

Ohne mindestens einen Beleg der Art 1 oder 2 wird **nicht** gefragt; das
Papier bekommt keine `fit`-Annotation und zählt als `skipped` mit Grund
`no_evidence` — das ist selbst eine Aussage (Oldenburg hat nichts auch nur
entfernt Ähnliches), aber keine, die ein Modell treffen sollte.

### 10.3 Die Nutzlast (`council/cities/annotators.py`)

```python
FIT_STATUS = ("present", "partial", "missing")
FIT_WORTH = ("yes", "maybe", "no")

class OldenburgFit(BaseModel):
    """Was ein Modell über die Eignung einer fremden Vorlage für Oldenburg sagt."""
    #: Hat Oldenburg GENAU dieses Instrument schon?
    status: Literal[FIT_STATUS]
    #: Kennungen der Belege, auf die sich der Befund stützt — nur aus den
    #: mitgegebenen; leer nur bei "missing".
    evidence: list[str] = Field(default_factory=list, max_length=3)
    reason: str = Field(max_length=300)
    #: Lohnt ein Antrag in Oldenburg? Unabhängig vom Status: Auch "partial"
    #: kann ein klares "yes" sein, wenn der Unterschied die Idee ist.
    worth: Literal[FIT_WORTH]
    why_worth: str = Field(max_length=300)
    #: Was dagegen spricht — Zuständigkeit (Land, Landkreis, Versorger),
    #: fehlende Struktur, schon gescheitert. Leer, wenn nichts.
    obstacles: str | None = Field(default=None, max_length=200)
    confidence: Literal["high", "medium", "low"]
```

**Validierung über pydantic hinaus**, in `annotate.py` vor dem Speichern:
Jede Kennung in `evidence` muss unter den mitgegebenen Belegen sein — sonst
wird der Eintrag verworfen und gezählt (`hallucinated_evidence`). Bei
`status != "missing"` muss `evidence` mindestens eine Kennung tragen. Regel
13 in Code.

### 10.4 Der Prompt (`kern/prompts.py`)

Zwei Schlüssel, `cities_fit_system` und `cities_fit_user`, Registrierung wie
bei `classify` (Wächter `test_prompt_schluessel` kennt `prompt_system=`).

Der System-Prompt baut auf `SYSTEM` aus `~/.cache/ratslotse/phase0/gaps.py`
auf — der hat in Phase 0 funktioniert („Sei streng: Ein Beleg, der nur
dasselbe Themenfeld berührt, ist NICHT vorhanden") — und bekommt drei
Ergänzungen:

1. **Ein Oldenburg-Steckbrief** als Konstante `OLDENBURG_STECKBRIEF` in
   `council/cities/evidence.py`, zehn Zeilen: kreisfreie Stadt in
   Niedersachsen, Einwohnerzahl, NKomVG, was städtisch ist und was nicht
   (Versorger, Verkehrsbetrieb, Krankenhaus, Wohnungsgesellschaft), Rat und
   Ausschüsse, Besonderheiten (Universität, Fahrradanteil). **Nicht aus dem
   Gedächtnis schreiben**: aus `council_entities`/Steckbriefen der
   Rats-Datenbank und der Website der Stadt ableiten, Quelle je Zeile als
   Kommentar, **und Tim liest den Steckbrief gegen, bevor er in den Prompt
   geht** — hier entscheidet sich, ob „obstacles" etwas taugt.
2. **Die Frage nach dem Lohnen**, mit drei Beispielen, was „yes" heißt
   (ein konkretes Instrument, das Oldenburg nicht hat und das in seine
   Zuständigkeit fällt), was „maybe" (hat etwas Verwandtes, der Unterschied
   könnte ein Antrag sein) und was „no" (hat es, oder nicht zuständig, oder
   schon abgelehnt).
3. **Die Beleg-Disziplin**: „Nenne nur Kennungen aus der Liste. Erfinde
   keine. Ist die Liste leer oder trifft nichts, ist der Status `missing`
   und `evidence` leer."

Der User-Prompt trägt: die fremde Vorlage (Stadt, Titel, Datum, Art,
Ergebnis, `summary`, `instrument`, `field`, `competence`), dann die Belege
nummeriert mit Kennung, dann die Frage. `input_chars` 3.500 (mehr Kontext
als `classify`), `batch_size` **1** — jedes Papier hat eigene Belege, ein
Batch teilte sie nicht.

### 10.5 Registrierung, Modell, `source_hash`

```python
"fit": Annotator(
    key="fit", version="1", applies_to=("paper",),
    prompt_system="cities_fit_system", prompt_user="cities_fit_user",
    model=os.environ.get("CITIES_FIT_MODEL", "deepseek/deepseek-v4-flash"),
    payload=OldenburgFit, batch_size=1, input_chars=3500, max_tokens=4000,
    gut_wenn="eval/run_cities_fit.py: Status-Treffer ≥ 75 % (drei Klassen mit "
             "echter Unschärfe), Beleg-Disziplin 100 %.",
),
```

**Das Modell wird gemessen, nicht gewählt.** `classify` hat gezeigt, dass
der Prompt mehr bewegt als das Modell (73 → 87 %). `fit` ist aber eine
Schlussfolgerung über Kontext, kein Etikett; hier kann ein größeres Modell
den Unterschied machen. Der Eval (10.6) läuft mit `deepseek-v4-flash` und
`deepseek-v4-pro`, je dreimal (die ±7 Punkte aus Phase 0 gelten hier
genauso). Gewinnt `pro` um mehr als die Streuung, wird es das Modell;
sonst `flash`. Beides ohne ZDR-Routing (`routing_free=True`, Tims
Entscheidung vom 07.09.).

**`source_hash` für `fit`** muss mehr abdecken als bei `classify`: das
fremde Papier **plus** die sortierten Beleg-Kennungen **plus** den Hash des
Rückblicks. Wächst Oldenburgs Geschichte (PR 9 läuft nach, ein Cron holt
Neues), ändern sich die Belege, und das Urteil ist neu zu fällen — genau so
merkt `annotations_missing` es. Ein Test: gleiches Papier, neuer
Oldenburger Nachbar → `fit` gilt als fehlend.

Kosten, hochgerechnet: ~3.000 Token Eingabe, ~250 Ausgabe je Papier; bei
5.000 Papieren und `flash` rund **5 $**, bei `pro` das Sechsfache. Beides
einmalig; danach nur Neues und Geändertes.

### 10.6 Golden Set und Eval — das Urteil, das Tim delegiert hat

Tim hat entschieden, dass die Bewertung „taugt das für Oldenburg?" beim
Modell liegt (08.09.2026) — und dass die Maßstäbe dafür der umsetzende
Agent setzt, der Oldenburgs Anträge und Beschlüsse inzwischen kennt. Das
heißt konkret:

**`eval/cases_cities_fit.json`, 40 Fälle, von Hand geurteilt.** Der
Umsetzer zieht 40 fremde übertragbare Papiere, geschichtet: je Themenfeld
mindestens drei, alle fünf Städte, und — das ist der Punkt — so gewählt,
dass etwa 10 `present`, 10 `partial`, 20 `missing` herauskommen. Für jeden
Fall liest er die Belege selbst (die `evidence_for`-Ausgabe, plus Suche in
der Rats-Datenbank, plus im Zweifel die Vorlagentexte) und schreibt: Status,
Kennungen, `worth`, und **einen Satz Begründung**. Die Begründung ist
Pflicht — sie ist es, die Tim gegenlesen kann, ohne 40 Vorlagen zu lesen.

Drei Regeln fürs Urteilen, damit 40 Fälle einen Maßstab ergeben:

- `present` heißt **genau das Instrument**, nicht das Thema. Oldenburg hat
  einen Wärmeplan; eine Braunschweiger Vorlage „Wärmeplan Teil 2:
  Umsetzungsgebiete" ist trotzdem `partial`, wenn Oldenburg diesen Schritt
  nicht hat.
- `worth: yes` verlangt Zuständigkeit **und** einen erkennbaren Unterschied.
  Was das Land regelt, ist `no`, so gut die Idee sei; was Oldenburg schon
  abgelehnt hat (Rats-Datenbank fragen), ist `maybe` mit Hinweis.
- Bei Zweifel zwischen zwei Stufen die **vorsichtigere** (`partial` statt
  `present`, `maybe` statt `yes`), und das im Satz sagen.

**`eval/run_cities_fit.py`** nach dem Muster von `run_cities_transfer.py`:
ruft den Annotator gegen die 40 Fälle, misst Status-Treffer (Ziel ≥ 75 %),
`worth`-Treffer getrennt (Ziel ≥ 70 %), Beleg-Disziplin (jede genannte
Kennung war mitgegeben: **100 %**, sonst ist es rot) und die
Verwechslungsmatrix. Läuft dreimal je Modell; das PR nennt Mittel und
Spanne. `tests/test_cities_guards.py` hält fest, dass `fit` einen
`gut_wenn`-Text hat und die Eval-Datei existiert.

**Was Tim gegenliest:** die 40 Sätze, nicht den Code. Sie stehen im PR-Text
als Tabelle (Stadt, Titel, Status, Lohnt?, Satz). Wo er widerspricht, wird
der Fall geändert und der Eval neu gefahren — der Maßstab ist damit seiner,
die Arbeit war die des Modells.

### 10.7 Stufe, Cron, Kennzahlen

`pipeline.annotate` läuft alle aktiven Annotatoren; `fit` reiht sich ein,
läuft aber **nach** `index_all` — es braucht die Nachbarschaften. Also im
Cron (`check_cities.py`): fetch → normalize → extract → annotate(classify)
→ index → annotate(fit). Dafür bekommt `Annotator` ein Feld
`needs_index: bool = False`, und `pipeline.annotate` bekommt einen
Parameter `phase: Literal["before_index", "after_index"]`. Kennzahlen:
`fit_annotated`, `fit_skipped_no_evidence`, `fit_hallucinated_evidence`,
`fit_cost_usd`.

### 10.8 Tests (PR 10)

`tests/test_cities_fit.py`, gemockt wie `test_cities_annotators.py`:

- `evidence_for` liefert Nachbarn, FTS-Treffer und Rückblick, dedupliziert,
  in dieser Reihenfolge; ohne Nachbarn und FTS-Treffer leer.
- Ohne Belege wird nicht gefragt (kein `chat_complete`-Aufruf), `skipped`
  zählt hoch.
- Eine Antwort mit erfundener Kennung wird verworfen und gezählt.
- `status="present"` ohne `evidence` wird verworfen.
- `source_hash` ändert sich, wenn ein Oldenburger Nachbar dazukommt.
- `candidates_for(fit)` enthält nur `USABLE`-Papiere fremder Städte.
- Der Cron ruft `fit` nach `index_all` (Reihenfolge der Stufen als Liste
  prüfen).

**Fertig, wenn:** Eval-Ziele erreicht und im PR dokumentiert (Mittel,
Spanne, Modell), die 40 Sätze von Tim gegengelesen, ein voller Lauf über den
Bestand gelaufen (Kosten im PR), `pruefe.py` grün. Kein Bild — keine
Oberfläche. Changelog `changelog.d/cities-10-fit.md`, `hinzugefuegt`,
sichtbar wird es erst mit PR 11.

## PR 11 — „Ideen aus anderen Städten": die Seite (Web)

Die Anwendung von PR 10. Eine Seite je Themenfeld: was andere Städte haben,
was Oldenburg davon fehlt, mit Urteil, Belegen und Weg zum Original.

### 11.1 Endpunkt (`web/backend/app/routers/council.py`)

```
GET /api/council/cities/ideas
    ?field=<policy_field>      # Pflicht — ohne Feld keine Liste (Lesebreite!)
    &status=missing|partial|present   # Vorgabe: missing,partial
    &worth=yes|maybe|no               # Vorgabe: yes,maybe
    &body=<body_id>                   # optional
    &page=1&per_page=30
→ IdeasResponse
```

```python
class IdeaEvidence(TypedDict):
    decision_id: int | None      # wenn ein Beschluss dahintersteht → interner Link
    kvonr: int | None
    title: str
    date: str | None
    outcome: str | None

class Idea(TypedDict):
    paper_id: str; body_id: str; body_name: str
    name: str; date: str | None; kind: str; web: str | None
    outcome: str
    field: str; instrument: str | None; summary: str | None
    transfer: str; competence: str
    status: str; reason: str; worth: str; why_worth: str
    obstacles: str | None; confidence: str
    evidence: list[IdeaEvidence]
    originator: str | None       # display_originator, wie in PR 6

class IdeasResponse(TypedDict):
    field: str; total: int; page: int; per_page: int
    counts: dict[str, int]       # je status, für die Chips
    items: list[Idea]
```

Sortierung: `worth` (yes, maybe, no), dann `status` (missing, partial,
present), dann `confidence`, dann Datum absteigend. Alles serverseitig
(Regel „Logik ins Backend"), auch die Zähler für die Chips. Die Belege
werden aus `evidence`-Kennungen aufgelöst: `oldenburg:paper:<kvonr>` →
Beschluss-Id über `decisions_for_kvonr` (die neueste Station), damit die
Karte intern verlinken kann. Öffentlich wie die Beschluss-Seite, Eintrag in
`OEFFENTLICH` mit Begründung; `optional_user` nicht nötig.

Ein zweiter, kleiner: `GET /api/council/cities/ideas/fields` → je Themenfeld
die Zähler (`missing`, `partial`, `present`, `worth_yes`), für die Übersicht
und die Navigation. Beide hinter dem Schalter `ideen-anderswo` (neu in
`kern/features.py`, `fertig_wenn`: „vier Wochen auf dev, Tim hat zwei
Themenfelder durchgesehen und die Urteile für tragfähig erklärt").

### 11.2 Seiten (`web/frontend/app/(app)/council/ideen/`)

`page.tsx` (Hülle, Kurzschlusszeile für den Export), `view.tsx` (Client).
Zwei Zustände:

- **Ohne `?feld=`**: die Übersicht — zwölf Themenfeld-Karten mit den
  Zählern („Verkehr — 41 Ideen, 12 lohnen sich"), Klick führt ins Feld.
  Dieselbe Kachel-Bauform wie die Themenfeld-Übersicht unter `/council?tab=analysis`
  (dort nachsehen, nichts Neues erfinden).
- **Mit `?feld=verkehr`**: Filter-Chips oben (Status, Lohnt?, Stadt), darunter
  die Liste. Je Idee eine Karte: Stadt · Art · Datum · Ergebnis (wie in
  `elsewhere.tsx`), Titel, `instrument` als Kicker, dann **das Urteil** —
  Status-Marke (fehlt/teilweise/vorhanden in Anzeigetafel-Tönung, nie
  dunkel im Hellen), ein Satz `reason`, darunter „Lohnt sich: ja/vielleicht/
  nein — `why_worth`", `obstacles` in Mutedtone. Belege als
  `DecisionLinkCard` (interner Chevron, weil unsere Seite), das Original
  als externer Link mit `ArrowUpRight` und Zeigerhand nur mit Ziel. Ohne
  `web` kein Anker (PR 6-Regel).

Typen aus `lib/vertrag.ts` (`ApiAntwort<"/council/cities/ideas">`),
Anfragen über `lib/api.ts`, `useFeature("ideen-anderswo")`. Navigation:
ein Eintrag in `nav.tsx` neben „Analyse" — Label **„Ideen"**, Icon
`Lightbulb`, aktiv bei `pathname.startsWith("/council/ideen")`; hinter dem
Schalter ausgeblendet (ein Gate braucht seine Einstiegspunkte).

**Kein Ranking-Wert, keine Prozentzahl** — wie im Block. Was das Modell
sicher ist, zeigt `confidence` als Wort, nicht als Zahl.

### 11.3 Tests und Abnahme

`tests/test_cities_ideas_router.py`: Sortierung, Chips-Zähler, Auflösung
der Belege auf Beschluss-Ids, leere Datenbank → 200 mit leeren Listen, der
Schalter, `OEFFENTLICH`. Frontend: nichts Renderndes (Regel aus
`web/frontend/CLAUDE.md`), die Logik der Chip-Zustände in `lib/ideen.ts` mit
`vitest`, falls es welche gibt. Browsertest `tests/e2e/04-council`: die
Seite antwortet mit Übersicht **oder** sagt, dass noch keine Ideen da sind —
in der CI ist die Städte-Datenbank leer.

**Bilder an Tim, vor dem Merge:** die Übersicht, ein Themenfeld (Verkehr —
dort gibt es 138 Kandidaten), eine Karte mit Belegen, hell und dunkel, und
390 px. `14-layout.spec` muss die neue Seite mitlaufen (keine seitliche
Scrollbahn).

**Fertig, wenn:** Tims Gegenlesen da, `pruefe.py` grün, Browsertests grün
gegen leer und gegen Daten. Changelog `changelog.d/cities-11-ideen.md`,
`hinzugefuegt`.

## PR 12 — „Ideen" in der App

Regel 11. `IdeasResponse`, `Idea`, `IdeaEvidence` als Swift-`struct`s mit
`CodingKeys` (alles außer Kennungen optional, PR-7-Lehre), ein `IdeasView`
mit Themenfeld-Übersicht und Liste, Chips als `Pill`, Status-Marke wie
`OutcomeBadge` aber mit eigener Tabelle (die `default`-Kapitalisierung dort
liefert Englisch), Belege als Navigation auf `.decision(id:)`, Original per
`Link`. Einstieg im „Mehr"-Hub und in der iPad-Sidebar unter Rat.

Vor und nach der Arbeit `python scripts/ios_vertrag.py` — mit
**ausgeschriebener Typangabe** und `try await` an jeder Aufrufstelle, sonst
sieht der Wächter die Bindung nicht (PR-7-Lehre; Gegenprobe: ein
verfälschter Schlüssel muss die Befundzahl erhöhen). `.task(id:)` über dem
Schalterwert, weil `/api/app-config` nach der Ansicht kommt. `xcodegen
generate --spec ios/project.yml` nach jeder neuen Datei. Bilder aus dem
Simulator an Tim.

## PR 13 — Freie Suche: „Was haben andere Städte zu …?"

Der Volltextindex (`cities_fts`) hat kein Fenster nach vorn. Klein halten:
**eine Suchzeile oben auf der Ideen-Seite**, keine eigene Seite.

`GET /api/council/cities/search?q=&body=&field=&page=` → dieselbe `Idea`-Form
(mit `fit`, wo vorhanden, sonst `status: null`), hybrid: `fts_search` **und**
Objektvektor-Nähe (Anfrage einbetten — `council/embeddings.embed`, wie die
KI-Frage es tut), Rangfolge per Reciprocal Rank Fusion mit festen
Gewichten, die im Code begründet stehen. Phase 0 hat gemessen, dass Nähe
allein formulierungsempfindlich ist („Hitzeschutz … für die Stadt" holt
**Wärme**planung) — deshalb FTS dazu, deshalb kein Vektor allein.

**Abnahme nach der Stadion-Regel** (`stadion-validierung-direktive`): Jede
Suche-Verbesserung wird an den bekannten Stadion-Fragen geprüft. Hier heißt
das: zehn Fragen, die Tim aus dem Ratsalltag kennt („Hitzeaktionsplan",
„Nette Toilette", „Bewohnerparken", „Schulmittagessen kostenlos", …), je die
fünf besten Treffer im PR-Text, mit Urteil des Umsetzers (trifft / trifft
nicht). Bild an Tim.

App: Suchfeld über der Ideen-Liste, derselbe Endpunkt.

## PR 14 — Ein zweites Embedding-Modell, gemessen

1.290 von 2.416 Kanten liegen zwischen 0,70 und 0,75. Das Modell
(`paraphrase-multilingual-MiniLM-L12-v2`, 384 Dimensionen) ist das
kleinste, das für Oldenburgs eigene Ähnlichkeit reicht. Der Speicher hält
mehrere Modelle nebeneinander — genau für diesen PR.

**Kandidat:** `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
(768 Dimensionen, dieselbe Familie, dreimal so groß) — vorher mit
`TextEmbedding.list_supported_models()` prüfen, dass fastembed ihn hat;
falls nicht, `intfloat/multilingual-e5-large`. **Nur Objektvektoren**, keine
Chunks (das Vierfache an Zeilen für eine Messung lohnt nicht).

```bash
python -c "…index.embed_objects(store, model='<B>'); index.build_neighbors(store, model='<B>')…"
```

**Messung**, beides gegen dieselben Fälle: die zwölf Stichproben-Vorlagen
aus der Bewertung (Urteil „handelt von derselben Sache", Precision@3) und
die 40 Fälle des `fit`-Golden-Sets (Rang des richtigen Oldenburger Belegs).
Dazu die Verteilung der Nähe: Wie viele Kanten liegen bei B über 0,80? Der
PR nennt beide Tabellen. **Gewechselt wird nur**, wenn B bei Precision@3
mindestens zwei Fälle besser ist und bei den Belegen nicht schlechter —
sonst bleibt A, und die Messung steht als Wissen im PR.

Wechsel heißt: `EMBED_MODEL` in `council/cities/index.py` auf B (die Umgebung
`COUNCIL_EMBED_MODEL` teilt sich der Speicher mit Oldenburgs eigenen
Embeddings — **nicht** diese Variable umsetzen, sondern eine eigene
`CITIES_EMBED_MODEL` einführen, Vorgabe B), `fit` läuft nach (der
`source_hash` merkt geänderte Belege), Kosten wie 10.5. Kein Bild — nichts
sieht anders aus, nur besser sortiert.

## PR 15 — Auf Prod

Kein Code, eine Reihenfolge:

1. Nach PR 8 auf dev: `FEATURE_FLAGS` auf Prod um `andere-staedte`
   ergänzen — sobald der Block vier Wochen auf dev lag und Tim ihn
   freigibt (`fertig_wenn` in der Registry). Voraussetzung: `cities.sqlite`
   auf Prod gefüllt (PR 9, 9.4).
2. `ideen-anderswo` nach seinem `fertig_wenn`.
3. Danach die beiden Schalter aus der Registry nehmen (ein Schalter ist eine
   Schuld) — eigener kleiner PR, `tests/test_features.py` meldet den Rest.

## Anhang A — Reihenfolge, Aufwand, Kosten

| PR | Was | Netz/LLM | Kosten | Bild an Tim |
|---|---|---|---|---|
| 8 | Brücke, Filter, Bewertung | nein | 0 | ja (28119) |
| 9 | Historie | Ernte Stunden, Einordnung | ~4 $ | nein |
| 10 | Annotator `fit` + Golden Set + Eval | ja | ~5 $ (`flash`) bis ~30 $ (`pro`) | die 40 Sätze |
| 11 | Ideen-Seite Web | nein | 0 | ja |
| 12 | Ideen-Seite App | nein | 0 | ja |
| 13 | Freie Suche | Einbettung der Anfrage | ~0 | ja |
| 14 | Zweites Embedding-Modell | lokal CPU | 0 (+ `fit` nach, ~5 $) | nein |
| 15 | Prod | — | 0 | — |

Sequenziell, nie gestapelt. 8 und 9 sind unabhängig voneinander, 10 braucht
9, 11 braucht 10, 12 braucht 11, 13 braucht 11, 14 braucht 10 (für die
Messung). Wer parallel arbeiten kann: 8 und 9 zugleich, dann 10, dann 11
und 14 zugleich.

## Anhang B — Was ausdrücklich NICHT in diesem Plan liegt

- **Mehr Städte.** Osnabrück und Braunschweig liefern die Hälfte der
  Treffer; eine sechste Stadt bringt weniger als das dritte Jahr der
  vorhandenen. Wenn doch: Niedersachsen zuerst, und vorher messen, welche
  niedersächsischen Städte OParl anbieten — die Registry trägt in Ring 3
  Städte anderer Länder (`active=False`, gemessen erreichbar), keine
  weiteren aus NI.
- **Benachrichtigungen** („neue Idee in deinem Themenfeld"). Erst, wenn die
  Ideen-Seite vier Wochen gelebt hat und klar ist, ob jemand sie liest.
  Wenn: über `notify.einreihen`, nie daran vorbei.
- **Die Personenebene.** Keine `originatorPerson`, keine Kontaktdaten, und
  auf Eingaben kein Urheber (PR 6, Tims Entscheidung 08.09.). Namen von
  Ratsmitgliedern anderer Städte an Anträgen bleiben stehen.
- **Ein Bewertungsbogen für Ratsmitglieder.** Der aus Phase 0 bleibt
  erreichbar, ist aber kein Gate mehr: Das Urteil fällt das Modell, den
  Maßstab setzt der Golden-Set-Autor, gegen gelesen von Tim.

## Anhang C — Was der Umsetzer aus dem Bestand wiederverwendet

- `~/.cache/ratslotse/phase0/gaps.py`: der Gegenprobe-Prompt (Zeilen 26–43)
  und die Cluster-Regel — Vorlage für `cities_fit_system`.
- `docs/bewertung-staedte-speicher.md`, letzter Abschnitt: die Messskripte;
  nach PR 9 erneut laufen lassen, Zahlen ins PR.
- `eval/run_cities_transfer.py`: Muster für `run_cities_fit.py` (argparse,
  dreifacher Lauf, Verwechslungsmatrix).
- `web/frontend/components/elsewhere.tsx`: die Karten-Kopfzeile (Stadt · Art
  · Datum · Ergebnis) und die Regel „ohne `web` kein Anker" — für die
  Ideen-Karte übernehmen, nicht neu bauen.
- `ios/Packages/RatslotseFeatures/Sources/RatslotseFeatures/CouncilViews.swift`,
  `ElsewhereSection`/`ElsewhereRow`: dieselbe Kopfzeile in Swift, samt der
  Lehre zur Ergebnis-Marke (fest oben rechts, Kopfzeile bricht um).
