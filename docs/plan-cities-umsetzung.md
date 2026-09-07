# Umsetzungsplan: der Städte-Speicher (`council/cities/`)

Stand: 07.09.2026. Dieser Plan setzt den Vorschlag aus
[`vorschlag-staedte-speicher.md`](vorschlag-staedte-speicher.md) in Arbeit um.
Er ist so geschrieben, dass er **ohne das Gespräch dahinter** ausführbar ist:
Jeder Abschnitt ist ein Pull Request, nennt die Dateien, das Schema, die
Signaturen, die Tests und woran man erkennt, dass er fertig ist. Wo etwas
gemessen ist, steht die Zahl; wo eine Entscheidung offen wäre, ist sie hier
getroffen.

Wer das umsetzt, liest **vorher** vollständig: die Wurzel-`CLAUDE.md`,
`council/CLAUDE.md`, `web/backend/CLAUDE.md`, `scripts/CLAUDE.md`,
`tests/CLAUDE.md`, und für PR 6/7 `web/frontend/CLAUDE.md`, `ios/CLAUDE.md`
und `web/frontend/DESIGNSPRACHE.md`. Die Rezepte in `REZEPTE.md` gelten; dieser
Plan wiederholt sie nicht, er verweist.

## 0. Regeln, die für jeden Pull Request gelten

1. **Ein PR, ein Zweig von `dev`, Squash-Merge, keine gestapelten PRs.** Die
   sieben PRs unten sind sequenziell; PR n+1 beginnt, wenn PR n gemergt ist.
   Mergen mit `python scripts/merge_wenn_gruen.py`, nie von Hand.
2. **Vor jedem Push `python scripts/pruefe.py`.** Rot heißt nicht pushen.
3. **Je PR ein Changelog-Fragment** `changelog.d/cities-<n>-<slug>.md`, Kategorie
   `hinzugefuegt`, ohne Überschrift, ohne PR-Nummer. PR 1–5 sind für
   Nutzer*innen unsichtbar — ihr Fragment beschreibt trotzdem in einem Satz,
   was entstanden ist („Grundlage für den Städtevergleich: …").
4. **Bezeichner Englisch** (Tabellen, Spalten, Funktionen, Dateien), Prosa und
   Docstrings Deutsch. Der Name der Sache ist `cities`, nicht `staedte`,
   nicht `peers`.
5. **`council/` importiert nur aus `kern/`**; `council/cities/` darf zusätzlich
   aus `council/` importieren (gleiches Paket). `tests/test_schichten.py`
   hält das.
6. **Kein `sqlite3.connect` außerhalb von `council/cities/store.py`** — auch
   nicht in Skripten. Skripte gehen über `CitiesStore`.
7. **Nie Threads auf dieselbe SQLite-Datei.** Parallel ist nur die Ernte über
   Städte hinweg, und die schreibt je Stadt in eine eigene Rohdatei (PR 2).
8. **Kein Person-Objekt, keine `originatorPerson`, keine Kontaktdaten.** Ein
   Test hält das fest (PR 1).
9. **Schicht 1 trägt keine Meinung.** Was ein Modell sagt, steht in
   `annotations`, nie als Spalte in `papers`. Ein Test hält die erlaubten
   Spalten fest (PR 1).
10. **Für PR 6 und 7 gilt Tims Regel:** Screenshot per `SendUserFile`
    schicken und Gegenlesen abwarten, bevor gemergt wird.

## 1. Zielbild in einem Bild

```
council/cities/
  __init__.py
  model.py        die acht OParl-Objekte als dataclasses + kanonische Enums
  schema.py       SCHEMA (DDL) und MIGRATIONS
  store.py        CitiesStore — die einzige Stelle mit sqlite3
  registry.py     BODIES: die Städte als Code (Slug, Endpunkt, Dialekt, Start)
  oparl.py        HTTP-Client: Drosselung, Blättern je Dialekt, Rohablage
  adapters/
    __init__.py   Adapter-Protokoll + get_adapter(dialect)
    allris4.py    Osnabrück, Braunschweig, Potsdam, Leipzig, Bonn
    session.py    Münster, Magdeburg, Köln, Dresden, Wuppertal, Düsseldorf
    rubin.py      Freiburg, Darmstadt (OParl 1.0)
    oldenburg.py  liest council.sqlite — kein Netz
  text.py         PDF → Text (pypdf), Qualitätsmaß
  pipeline.py     die Stufen fetch/normalize/extract/annotate/index + stages-Tabelle
  annotators.py   ANNOTATORS-Registry (Prompt, Modell, Payload-Form, aktiv)
  annotate.py     Batches ans Modell, JSON-Parsen, source_hash-Cache
  index.py        Chunks, Embeddings je Modell, FTS, Nachbarn über Städte
scripts/
  cities_backfill.py       Erstfüllung und Wiederholung einzelner Stufen (Bericht als Default)
  cities_import_phase0.py  Übernahme des Probelauf-Bestands (einmalig)
  check_cities.py          der wöchentliche Cron
eval/
  cases_cities_transfer.json, run_cities_transfer.py
tests/
  test_cities_store.py, test_cities_adapters.py, test_cities_pipeline.py,
  test_cities_guards.py, test_cities_annotators.py
```

Datenbank: **`data/cities.sqlite`**, Dateien: **`data/cities-files/`**,
Rohernte je Stadt: **`data/cities-raw/<slug>.sqlite`**. Alle drei Pfade kommen
aus der Konfiguration (`Settings.cities_db`, `Settings.cities_files_dir`,
`Settings.cities_raw_dir` in `web/backend/app/config.py`; für Skripte dieselben
Umgebungsvariablen `CITIES_DB`, `CITIES_FILES_DIR`, `CITIES_RAW_DIR` mit
denselben Vorgaben relativ zum Repo-Root). Nie hart schreiben.

---

## PR 1 — Store, Schema, Modell, Registry (kein Netz)

**Zweck:** Das Fundament, gegen das alle weiteren PRs bauen. Läuft komplett
offline; die Testsuite deckt ihn vollständig ab.

### 1.1 `council/cities/model.py`

```python
from dataclasses import dataclass, field
from enum import StrEnum

class PaperKind(StrEnum):
    MOTION = "motion"           # Antrag
    AMENDMENT = "amendment"     # Änderungsantrag
    INQUIRY = "inquiry"         # Anfrage
    ANSWER = "answer"           # Antwort/Stellungnahme der Verwaltung auf eine Anfrage
    PROPOSAL = "proposal"       # Beschlussvorlage der Verwaltung
    REPORT = "report"           # Informations-/Berichtsvorlage
    NOTICE = "notice"           # Mitteilung
    PETITION = "petition"       # Einwohnerantrag, Petition, Anregung nach § 24 GO NRW o. ä.
    OTHER = "other"

class Outcome(StrEnum):
    ACCEPTED = "accepted"; AMENDED = "amended"; REJECTED = "rejected"
    POSTPONED = "postponed"; NOTED = "noted"; REFERRED = "referred"
    WITHDRAWN = "withdrawn"; NONE = "none"

class OrgKind(StrEnum):
    COUNCIL = "council"; COMMITTEE = "committee"; DISTRICT = "district"
    FACTION = "faction"; ADMINISTRATION = "administration"; OTHER = "other"

class FileRole(StrEnum):
    MAIN = "main"; AUXILIARY = "auxiliary"; RESOLUTION = "resolution"
    INVITATION = "invitation"; PROTOCOL = "protocol"; OTHER = "other"

@dataclass(frozen=True)
class Body:        id: str; name: str; state: str; ris_vendor: str; oparl_url: str | None; license: str | None
@dataclass(frozen=True)
class Organization: id: str; body_id: str; name: str; kind_raw: str | None; kind: OrgKind
@dataclass(frozen=True)
class Meeting:     id: str; body_id: str; organization_id: str | None; name: str; start: str | None; end: str | None; state_raw: str | None; cancelled: bool
@dataclass(frozen=True)
class AgendaItem:  id: str; meeting_id: str; number: str | None; position: int | None; name: str; public: bool; result_raw: str | None; outcome: Outcome; resolution_text: str | None
@dataclass(frozen=True)
class Paper:       id: str; body_id: str; reference: str | None; name: str; date: str | None; paper_type_raw: str | None; kind: PaperKind; originator_org_id: str | None; under_direction_of_id: str | None; web: str | None
@dataclass(frozen=True)
class File:        id: str; body_id: str; paper_id: str | None; agenda_item_id: str | None; meeting_id: str | None; role: FileRole; name: str | None; mime: str | None; size: int | None; access_url: str | None
@dataclass(frozen=True)
class Consultation: id: str; paper_id: str; meeting_id: str | None; agenda_item_id: str | None; organization_id: str | None; role_raw: str | None; authoritative: bool | None

@dataclass
class Batch:
    """Was ein Adapter aus einer Rohernte macht — alles auf einmal, damit die
    Schreibseite in EINER Transaktion arbeiten kann."""
    organizations: list[Organization] = field(default_factory=list)
    meetings: list[Meeting] = field(default_factory=list)
    agenda_items: list[AgendaItem] = field(default_factory=list)
    papers: list[Paper] = field(default_factory=list)
    files: list[File] = field(default_factory=list)
    consultations: list[Consultation] = field(default_factory=list)
```

Dazu in derselben Datei die **kanonischen Regeln** als reine Funktionen, mit
Tests:

```python
def paper_kind(raw: str | None) -> PaperKind
def outcome(raw: str | None) -> Outcome
def org_kind(name: str, raw_type: str | None) -> OrgKind
def file_role(name: str | None, oparl_key: str) -> FileRole
```

Regeln (Kleinschreibung, Reihenfolge ist Priorität, erster Treffer gewinnt):

| Funktion | Muster → Wert |
|---|---|
| `paper_kind` | `änderungsantrag` oder `aenderungsantrag` → AMENDMENT · `antrag`, `anregung`, `resolution` → MOTION · `antwort`, `stellungnahme`, `beantwortung` → ANSWER · `anfrage` → INQUIRY · `beschlussvorlage`, `entscheidungsvorlage`, exakt `vorlage`/`vorlagen` → PROPOSAL · `informationsvorlage`, `berichtsvorlage`, `bericht`, `kenntnisnahme` → REPORT · `mitteilung` → NOTICE · `petition`, `einwohner`, `bürgerantrag` → PETITION · sonst OTHER |
| `outcome` | leer/None → NONE · `geändert beschlossen`, `geänderte empfehlung`, `mit änderung` → AMENDED · `abgelehnt`, `nicht beschlossen`, `mehrheitlich abgelehnt` → REJECTED · `vertagt`, `zurückgestellt`, `abgesetzt` → POSTPONED · `verwiesen`, `überwiesen` → REFERRED · `zurückgezogen`, `erledigt` → WITHDRAWN · `kenntnis` → NOTED · `beschlossen`, `angenommen`, `genehmigt`, `empfehlung`, `empfohlen`, `zugestimmt` → ACCEPTED · sonst NONE |
| `org_kind` | Name enthält `stadtbezirk`, `bezirksrat`, `bezirksvertretung`, `ortsrat`, `ortsbeirat`, `ortschaftsrat`, `bürgerforum` → DISTRICT · `fraktion`, `gruppe ` (mit Leerzeichen), `ratsgruppe` → FACTION · `rat der stadt`, `stadtrat`, `stadtverordnetenversammlung`, exakt `rat` → COUNCIL · `ausschuss`, `beirat`, `kommission` → COMMITTEE · `amt`, `dezernat`, `fachbereich`, `stabsstelle`, `referat`, `bereich`, `verwaltung` oder `raw_type == "Verwaltungsbereich"` → ADMINISTRATION · sonst OTHER |
| `file_role` | `oparl_key == "mainFile"` → MAIN · `resolutionFile` → RESOLUTION · `invitation` → INVITATION · `resultsProtocol`/`verbatimProtocol` → PROTOCOL · `auxiliaryFile` mit Name `sammeldokument`, `vorlage`, `antrag`, `anfrage` → MAIN (Somacos legt das Hauptdokument dort ab) · sonst AUXILIARY |

Wichtig für `outcome`: `AMENDED` und `REJECTED` **vor** `ACCEPTED` prüfen,
sonst trifft „geändert beschlossen" auf `beschlossen`. Genau das ist der Test.

### 1.2 `council/cities/schema.py`

```python
SCHEMA_VERSION = 1

SCHEMA = """
-- Schicht 0: Rohablage. Append-only. Nie UPDATE, nie DELETE.
CREATE TABLE IF NOT EXISTS raw_objects (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    body_id       TEXT NOT NULL,
    kind          TEXT NOT NULL,            -- system|body|organization|meeting|paper|file|agenda_item|consultation|list_page
    oparl_id      TEXT NOT NULL,            -- die id-URL des Objekts (bei list_page: die Seiten-URL)
    fetched_at    TEXT NOT NULL,
    content_hash  TEXT NOT NULL,            -- sha256 des kanonisierten JSON
    body_json     TEXT NOT NULL,
    UNIQUE (oparl_id, content_hash)         -- unverändertes Objekt: keine neue Zeile
);
CREATE INDEX IF NOT EXISTS idx_raw_objects_body_kind ON raw_objects(body_id, kind);
CREATE INDEX IF NOT EXISTS idx_raw_objects_oparl ON raw_objects(oparl_id);

CREATE TABLE IF NOT EXISTS raw_files (
    sha256        TEXT PRIMARY KEY,
    bytes         INTEGER NOT NULL,
    mime          TEXT,
    first_seen    TEXT NOT NULL,
    path          TEXT NOT NULL             -- relativ zu CITIES_FILES_DIR: ab/abcdef….pdf
);

-- Schicht 1: normalisiert. Trägt keine Meinung (tests/test_cities_guards.py).
CREATE TABLE IF NOT EXISTS bodies (
    id            TEXT PRIMARY KEY,         -- slug: osnabrueck, oldenburg …
    name          TEXT NOT NULL,
    state         TEXT NOT NULL,            -- NI, NW, BB, ST, SN, BW …
    ris_vendor    TEXT NOT NULL,            -- allris4|session|rubin|sessionnet
    oparl_url     TEXT,
    license       TEXT,
    population    INTEGER,
    first_fetched TEXT,
    last_fetched  TEXT
);
CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY, body_id TEXT NOT NULL, name TEXT NOT NULL,
    kind_raw TEXT, kind TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_organizations_body ON organizations(body_id, kind);
CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY, body_id TEXT NOT NULL, organization_id TEXT,
    name TEXT NOT NULL, start TEXT, "end" TEXT, state_raw TEXT,
    cancelled INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_meetings_body_start ON meetings(body_id, start);
CREATE TABLE IF NOT EXISTS agenda_items (
    id TEXT PRIMARY KEY, meeting_id TEXT NOT NULL, number TEXT, position INTEGER,
    name TEXT NOT NULL, public INTEGER NOT NULL DEFAULT 1,
    result_raw TEXT, outcome TEXT NOT NULL DEFAULT 'none', resolution_text TEXT
);
CREATE INDEX IF NOT EXISTS idx_agenda_items_meeting ON agenda_items(meeting_id);
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY, body_id TEXT NOT NULL, reference TEXT, name TEXT NOT NULL,
    date TEXT, paper_type_raw TEXT, kind TEXT NOT NULL,
    originator_org_id TEXT, under_direction_of_id TEXT, web TEXT
);
CREATE INDEX IF NOT EXISTS idx_papers_body_date ON papers(body_id, date);
CREATE INDEX IF NOT EXISTS idx_papers_kind ON papers(kind);
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY, body_id TEXT NOT NULL,
    paper_id TEXT, agenda_item_id TEXT, meeting_id TEXT,
    role TEXT NOT NULL, name TEXT, mime TEXT, size INTEGER, access_url TEXT,
    sha256 TEXT                             -- NULL, solange nicht geladen
);
CREATE INDEX IF NOT EXISTS idx_files_paper ON files(paper_id);
CREATE INDEX IF NOT EXISTS idx_files_sha ON files(sha256);
CREATE TABLE IF NOT EXISTS consultations (
    id TEXT PRIMARY KEY, paper_id TEXT NOT NULL, meeting_id TEXT, agenda_item_id TEXT,
    organization_id TEXT, role_raw TEXT, authoritative INTEGER
);
CREATE INDEX IF NOT EXISTS idx_consultations_paper ON consultations(paper_id);
CREATE INDEX IF NOT EXISTS idx_consultations_agenda ON consultations(agenda_item_id);

-- Schicht 2: Text. Abgeleitet, deshalb versioniert.
CREATE TABLE IF NOT EXISTS texts (
    file_id TEXT NOT NULL, extractor TEXT NOT NULL, version TEXT NOT NULL,
    text TEXT NOT NULL, n_pages INTEGER, quality TEXT NOT NULL,   -- ok|thin|empty|error
    extracted_at TEXT NOT NULL,
    PRIMARY KEY (file_id, extractor, version)
);

-- Schicht 3: Annotationen. Eine Tabelle für alles, was jemand über ein Objekt sagt.
CREATE TABLE IF NOT EXISTS annotations (
    object_kind TEXT NOT NULL, object_id TEXT NOT NULL,
    annotator TEXT NOT NULL, version TEXT NOT NULL,
    payload TEXT NOT NULL,                  -- JSON
    source_hash TEXT NOT NULL,
    model TEXT, cost_usd REAL, created_at TEXT NOT NULL,
    PRIMARY KEY (object_kind, object_id, annotator, version)
);
CREATE INDEX IF NOT EXISTS idx_annotations_annotator ON annotations(annotator, version);

-- Schicht 4: Indizes.
CREATE TABLE IF NOT EXISTS chunks (
    file_id TEXT NOT NULL, chunk_idx INTEGER NOT NULL,
    chunk_text TEXT NOT NULL, span_start INTEGER NOT NULL, span_end INTEGER NOT NULL,
    text_hash TEXT NOT NULL,
    PRIMARY KEY (file_id, chunk_idx)
);
CREATE TABLE IF NOT EXISTS chunk_embeddings (
    file_id TEXT NOT NULL, chunk_idx INTEGER NOT NULL, model TEXT NOT NULL,
    text_hash TEXT NOT NULL, vector BLOB NOT NULL,
    PRIMARY KEY (file_id, chunk_idx, model)
);
CREATE TABLE IF NOT EXISTS object_embeddings (
    object_kind TEXT NOT NULL, object_id TEXT NOT NULL, model TEXT NOT NULL,
    source_hash TEXT NOT NULL, vector BLOB NOT NULL,
    PRIMARY KEY (object_kind, object_id, model)
);
CREATE TABLE IF NOT EXISTS neighbors (
    model TEXT NOT NULL, a_kind TEXT NOT NULL, a_id TEXT NOT NULL,
    b_kind TEXT NOT NULL, b_id TEXT NOT NULL, score REAL NOT NULL, computed_at TEXT NOT NULL,
    PRIMARY KEY (model, a_kind, a_id, b_kind, b_id)
);
CREATE INDEX IF NOT EXISTS idx_neighbors_a ON neighbors(a_kind, a_id, score);
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    paper_id UNINDEXED, body_id UNINDEXED, name, reference, text, summary,
    tokenize = 'unicode61 remove_diacritics 2'
);

-- Fortschritt der Pipeline je Objekt und Stufe.
CREATE TABLE IF NOT EXISTS stages (
    object_kind TEXT NOT NULL, object_id TEXT NOT NULL,
    stage TEXT NOT NULL, version TEXT NOT NULL,
    status TEXT NOT NULL,                   -- done|error|skipped
    error TEXT, at TEXT NOT NULL,
    PRIMARY KEY (object_kind, object_id, stage, version)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""
```

`MIGRATIONS: list[tuple[int, str]] = []` — leer zu Beginn; jede spätere
Schemaänderung ist ein Eintrag `(n, sql)`, der genau einmal läuft (der Stand
steht in `meta.schema_version`). **Regel aus `council/CLAUDE.md`:** Eine neue
Spalte kommt ins `SCHEMA` *und* als Migration; Index auf eine migrierte
Spalte nur in die Migration.

### 1.3 `council/cities/store.py`

Eigene Klasse, **kein** Mixin von `CouncilStore` — andere Datei, anderer
Lebenszyklus.

```python
class CitiesStore:
    def __init__(self, path: str | Path): ...   # PRAGMA journal_mode=WAL, busy_timeout=60000, foreign_keys off
    def close(self) -> None
    def transaction(self) -> AbstractContextManager[None]

    # Schicht 0
    def put_raw_object(self, body_id, kind, oparl_id, body_json: dict, fetched_at) -> bool   # True = neue Zeile
    def latest_raw(self, oparl_id) -> dict | None
    def raw_objects(self, body_id, kind) -> Iterator[dict]     # nur die jeweils letzte Fassung je oparl_id
    def put_raw_file(self, sha256, bytes_, mime, path, first_seen) -> None

    # Schicht 1 — alle upsert (INSERT … ON CONFLICT(id) DO UPDATE)
    def upsert_body(self, body: Body) -> None
    def upsert_batch(self, batch: Batch) -> dict          # Zählwerte je Objektart
    def paper(self, paper_id) -> dict | None
    def papers(self, body_id=None, kind=None, since=None, until=None, limit=None) -> list[dict]
    def files_for_paper(self, paper_id) -> list[dict]
    def files_without_bytes(self, body_id=None, roles=("main",)) -> list[dict]
    def set_file_sha(self, file_id, sha256) -> None
    def outcome_for_paper(self, paper_id) -> dict | None   # über consultations→agenda_items, authoritative zuerst

    # Schicht 2
    def put_text(self, file_id, extractor, version, text, n_pages, quality) -> None
    def text_for_paper(self, paper_id, extractor, version) -> str | None    # MAIN-Datei zuerst, sonst erste mit Text
    def papers_without_text(self, extractor, version, body_id=None) -> list[dict]

    # Schicht 3
    def put_annotation(self, object_kind, object_id, annotator, version, payload: dict, source_hash, model, cost_usd) -> None
    def annotation(self, object_kind, object_id, annotator, version) -> dict | None
    def annotations_missing(self, object_kind, annotator, version, body_id=None, limit=None) -> list[dict]  # Objekte ohne Zeile ODER mit anderem source_hash
    def annotation_values(self, annotator, version, key) -> list[tuple[str, str]]   # (object_id, json_extract(payload,'$.'||key))

    # Schicht 4
    def put_chunks(self, file_id, chunks: list[tuple[int, str, int, int, str]]) -> None
    def put_chunk_embeddings(self, rows: list[tuple[str, int, str, str, bytes]]) -> None
    def put_object_embedding(self, object_kind, object_id, model, source_hash, vector: bytes) -> None
    def object_embeddings(self, model, object_kind="paper", body_id=None) -> tuple[list[str], list[str], bytes]  # ids, body_ids, buffer
    def replace_neighbors(self, model, a_kind, a_id, rows: list[tuple[str, str, float]]) -> None
    def neighbors(self, a_kind, a_id, model, limit=8, exclude_body=None) -> list[dict]
    def fts_upsert(self, paper_id, body_id, name, reference, text, summary) -> None
    def fts_search(self, query, body_id=None, limit=20) -> list[dict]

    # Pipeline
    def stage_done(self, object_kind, object_id, stage, version) -> bool
    def mark_stage(self, object_kind, object_id, stage, version, status, error=None) -> None
    def stage_counts(self, stage, version) -> dict[str, int]
    def stats(self) -> dict          # Kennzahlen für Cron und Admin: je Body Papiere, Texte, Annotationen, letzter Abruf
```

Konventionen: `row_factory = sqlite3.Row`; Rückgaben als `dict`; alle
Schreibmethoden innerhalb `with self._conn:`; `transaction()` klammert wie
`CouncilStore.transaktion`. `put_raw_object` kanonisiert das JSON mit
`json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`
vor dem Hashen.

### 1.4 `council/cities/registry.py`

```python
@dataclass(frozen=True)
class BodySpec:
    id: str; name: str; state: str; dialect: str          # allris4|session|rubin|oldenburg
    system_url: str | None; body_index: int = 0           # Potsdam hat zwei Bodies, Index 0 ist die Stadt
    since: str = "2023-01-01"                             # ab wann ernten
    active: bool = True
    notes: str = ""

BODIES: dict[str, BodySpec] = {
    "oldenburg":    BodySpec("oldenburg", "Oldenburg (Oldb)", "NI", "oldenburg", None),
    "osnabrueck":   BodySpec("osnabrueck", "Osnabrück", "NI", "allris4", "https://www.osnabrueck.sitzung-online.de/oparl/system"),
    "braunschweig": BodySpec("braunschweig", "Braunschweig", "NI", "allris4", "https://www.ratsinfo.braunschweig.sitzung-online.de/oparl/system"),
    "muenster":     BodySpec("muenster", "Münster", "NW", "session", "https://oparl.stadt-muenster.de/system"),
    "potsdam":      BodySpec("potsdam", "Potsdam", "BB", "allris4", "https://www.potsdam.sitzung-online.de/oparl/system"),
    "magdeburg":    BodySpec("magdeburg", "Magdeburg", "ST", "session", "https://ratsinfo.magdeburg.de/oparl/system",
                             notes="Datei-URLs der Schnittstelle antworten 404; Adapter schreibt sie um."),
}
```

Weitere Städte (Leipzig, Bonn, Köln, Dresden, Wuppertal, Düsseldorf, Freiburg,
Darmstadt) mit `active=False` und ihren Endpunkten aus Anhang A des Plans
eintragen — sie sind gemessen erreichbar, aber nicht Teil der ersten Füllung.

### 1.5 Konfiguration

In `web/backend/app/config.py` drei Felder:

```python
cities_db: str = str(ROOT / "data" / "cities.sqlite")
cities_files_dir: str = str(ROOT / "data" / "cities-files")
cities_raw_dir: str = str(ROOT / "data" / "cities-raw")
```

und in `web/backend/app/deps.py` ein `get_cities_store()` nach dem Muster von
`get_council_store`. Für Skripte: `council/cities/__init__.py` stellt
`default_paths()` bereit, das dieselben drei Werte aus `os.environ` mit
denselben Vorgaben liest (Skripte importieren nicht aus `web/`).

`.gitignore`: `data/cities-files/`, `data/cities-raw/` (unter `data/` ohnehin
ignoriert — prüfen).

### 1.6 Tests (PR 1)

`tests/test_cities_store.py`
- frische DB: Schema läuft, alle Tabellen da; zweimal öffnen ändert nichts
  (`sqlite_master` vor/nach identisch).
- `put_raw_object` mit demselben Objekt zweimal → eine Zeile; mit geändertem
  Feld → zwei Zeilen; `latest_raw` liefert die neuere.
- `upsert_batch` zweimal → identische Zeilenzahlen, geänderter Titel wird
  aktualisiert.
- `outcome_for_paper` bevorzugt `authoritative = 1`.
- `annotations_missing` liefert Objekte ohne Zeile **und** solche mit
  abweichendem `source_hash`.
- `fts_search` findet Umlaut-Varianten (`remove_diacritics`).

`tests/test_cities_model.py`
- Tabellen aus 1.1 als parametrisierte Fälle, inkl. der Reihenfolge-Fallen
  („geändert beschlossen" → AMENDED, „Antrag der CDU-Fraktion" → MOTION,
  „Beantwortung einer Anfrage" → ANSWER, „Anfrage" → INQUIRY).

`tests/test_cities_guards.py`
- **Schicht 1 trägt keine Meinung:** Die erlaubten Spalten je Tabelle stehen
  als Liste im Test; `PRAGMA table_info` muss exakt dazu passen. Fehlermeldung:
  „Neue Spalte X in papers — gehört das in `annotations`? Wenn nicht: Liste im
  Test ergänzen und im PR begründen."
- **Kein Person-Objekt:** Kein Tabellenname und kein `kind`-Literal in
  `council/cities/` enthält `person`; `grep` über die Quelltexte.
- **Registry:** jeder `BodySpec` mit `active=True` hat einen `system_url`
  (außer Dialekt `oldenburg`) und einen Dialekt, für den es einen Adapter gibt
  (Adapter kommen in PR 2 — bis dahin prüft der Test nur `oldenburg`-Ausnahme
  und ein `dialect in {"allris4","session","rubin","oldenburg"}`).

**Fertig, wenn:** `python scripts/pruefe.py` grün; `tests/test_schichten.py`
und `tests/test_typpruefung.py` unverändert grün (pyright: `council/cities/`
sollte von Anfang an in `include` von `pyrightconfig.json` stehen — 0 Befunde
als harter Gate, weil es neuer Code ist).

---

## PR 2 — OParl-Client, drei Adapter, Stufen `fetch`/`normalize`/`extract`

**Zweck:** Von fünf Städten alles holen, was öffentlich ist, und in Schicht
0–2 ablegen. Nach diesem PR liegt der Bestand des Probelaufs in
`data/cities.sqlite`.

### 2.1 `council/cities/oparl.py` — der Client

```python
USER_AGENT = "Ratslotse/1.0 (+https://ratslotse.de; kontakt siehe Impressum) Staedtevergleich"
RATE_SECONDS = 1.0          # je Host, hart

class OParlClient:
    def __init__(self, raw: CitiesStore, body_id: str, files_dir: Path): ...
    def get_json(self, url: str, params: dict | None = None, kind: str = "list_page") -> dict
        # GET mit UA, timeout 60, 3 Versuche (2s, 4s, 8s) bei 5xx/Timeout/ConnectionError,
        # KEIN Versuch bei 4xx. Jede Antwort → raw.put_raw_object(body_id, kind, url-oder-id, json, now).
    def get_file(self, url: str) -> tuple[bytes, str] | None
        # GET, timeout 120, 2 Versuche; None bei 4xx. Rückgabe (bytes, content-type).
    def store_file(self, data: bytes, mime: str) -> str
        # sha256 → files_dir/<sha[:2]>/<sha>.pdf schreiben (nur wenn nicht da), raw_files-Zeile, sha zurück.
```

Die Drosselung ist ein Modul-Dictionary `host → (Lock, last_call)` wie im
Probelauf, aber der Client ist **single-threaded je Prozess**. Parallelität
über Städte entsteht in `cities_backfill.py` durch **einen Prozess je Stadt**
(siehe 2.5), nie durch Threads.

### 2.2 `council/cities/adapters/__init__.py`

```python
class Adapter(Protocol):
    dialect: str
    def discover(self, client: OParlClient, spec: BodySpec) -> dict
        # system → body; gibt {"body": <json>, "paper_list": url, "meeting_list": url, "organization_list": url, "license": str|None}
    def iter_papers(self, client, body_json, since: str) -> Iterator[dict]        # rohe Paper-Objekte im Fenster, neueste zuerst
    def iter_meetings(self, client, body_json, since: str) -> Iterator[dict]      # rohe Meeting-Objekte inkl. eingebetteter agendaItem
    def iter_organizations(self, client, body_json) -> Iterator[dict]
    def normalize(self, body_id: str, raw: CitiesStore) -> Batch                  # liest raw_objects, baut Batch
    def file_url(self, file_json: dict, body_json: dict) -> str | None            # Dialekt-Korrektur der Download-URL

def get_adapter(dialect: str) -> Adapter
```

`normalize` ist **rein**: liest nur `raw.raw_objects(body_id, kind)`, kein
Netz. So ist die Stufe wiederholbar, und die Tests füttern sie mit
eingecheckten Rohfixtures.

Gemeinsame Hilfen in `adapters/_common.py`:

```python
def obj_id(o: dict) -> str                     # o["id"]
def ref(o: dict, key: str) -> str | None       # Verweis kann String oder eingebettetes Objekt sein
def refs(o: dict, key: str) -> list[str]
def embedded_or_ref(o, key) -> list[dict|str]
def parse_date(s) -> str | None                # ISO-Datum, Zeit abschneiden; "2000-01-01" bei ALLRIS = unbekannt → None
def normalize_common(body_id, raw) -> Batch    # der Teil, der bei allen gleich ist:
    # organizations ← raw kind=organization
    # meetings + agenda_items ← raw kind=meeting (agendaItem eingebettet: Liste von dicts)
    # papers + files + consultations ← raw kind=paper
    #   files: mainFile (dict) → role MAIN; auxiliaryFile[] → file_role(name, "auxiliaryFile")
    #   consultations: paper["consultation"][] (dicts) → Consultation(id, paper_id, meeting, agendaItem, organization[0], role, authoritative)
    #   originator_org_id: paper["originatorOrganization"][0] falls vorhanden — sonst None (Fraktion steht nur im Titel; Annotator "originator" in PR 4)
```

### 2.3 Die drei Dialekte — was gemessen ist und deshalb hart im Code steht

**`allris4.py`** (Osnabrück, Braunschweig, Potsdam; auch Leipzig, Bonn):

- `system_url` → `system["body"]` → Liste; `body_index` wählt.
- **Listen sind alt→neu sortiert, Seitengröße fest 10, `limit` wird
  ignoriert, `created_since`/`modified_since` sind unbrauchbar** (`created`
  und `modified` stehen bei allen Objekten auf `2000-01-01`). Deshalb:
  erste Seite holen, `links.last` lesen, dann **rückwärts** über
  `page=N` blättern (URL: `re.sub(r"page=\d+", f"page={n}", last)`).
- Abbruch: sobald auf einer Seite **alle** Objekte entweder `date < since`
  haben **oder gar kein `date`** tragen (alte Osnabrücker Papiere sind
  undatiert; wer sie als „unbekannt = drin" zählt, blättert bis 1997).
  Sicherheitsdeckel: höchstens 600 Seiten je Lauf.
- `meeting.agendaItem` ist eine Liste **eingebetteter** dicts mit `result`
  und `resolutionFile`, **ohne** `consultation`. Die Brücke Papier → Ergebnis
  läuft über `paper.consultation[].agendaItem` — die ist bei ALLRIS **oft
  leer**, solange das Papier nicht terminiert ist. Fallback in `normalize`:
  Wenn ein Papier über `consultation` keinen `agendaItem` hat, dann
  Tagesordnungspunkt per **normalisiertem Titelvergleich** in derselben
  Sitzungsperiode suchen (`re.sub(r"[^a-zäöüß0-9 ]", " ", s.lower())[:120]`,
  exakt gleich). Nur als Fallback, und im `Consultation.id` als
  `<paper_id>#title-match#<agenda_item_id>` kenntlich.
- Dateien: `mainFile` ist ein Sammel-PDF („Sammeldokument öffentlich"), URL
  `…/publickiosk/doc?DOCTYP=130&DOLFDNR=…` bzw. `…/public/doc?…`. Lädt ohne
  Cookie. `file_url` gibt `accessUrl` unverändert zurück.
- HTML-Seiten derselben Hosts zeigen „Zugriff prüfen"; die OParl-Pfade nicht.
  Nie die HTML-Seiten abrufen.
- Für Meetings ebenfalls rückwärts über `links.last`; Meetings mit
  `meetingState == "terminiert"` (Zukunft) mitnehmen — sie tragen die
  Beratungsfolge künftiger Vorlagen.

**`session.py`** (Münster, Magdeburg; auch Köln, Dresden, Wuppertal, Düsseldorf):

- `limit=100` funktioniert; `created_since` funktioniert **nur, wenn er bei
  jeder Anfrage selbst gesetzt wird**: Der `next`-Link trägt ihn auf Seite 2
  noch und ab Seite 3 **nicht mehr**. Also nie `links.next` folgen, sondern
  `page=N` hochzählen mit `params={"limit":100, "created_since": since+"T00:00:00+02:00", "page": n}`;
  Abbruch bei leerer Seite oder weniger als 100 Objekten. Deckel 80 Seiten.
- Kein `mainFile`; Dateien liegen unter `auxiliaryFile[]` als dicts mit
  `name`, `accessUrl`, `downloadUrl`, `fileName`. `file_role` erkennt das
  Hauptdokument am Namen (`Antrag`, `Vorlage`, `Beschlussvorlage`, `Anfrage`,
  `Sammeldokument`).
- **Magdeburg:** `accessUrl` **und** `downloadUrl` antworten 404. `file_url`
  baut aus `fileName` (`00692749.pdf`) die Zahl ohne führende Nullen und
  liefert `https://ratsinfo.magdeburg.de/getfile.asp?id=692749&type=do`
  (Content-Type `application/pdf`, gemessen). Dieser Umbau gilt nur, wenn
  `body_json["id"]` mit `https://ratsinfo.magdeburg.de/` beginnt — ein
  Dict `FILE_URL_FIX: dict[host_prefix, Callable]` im Adapter, damit die
  nächste Stadt mit kaputten URLs eine Zeile ist.
- Meetings: `meeting.agendaItem` eingebettet (Münster) **oder fehlend in der
  Liste** (Magdeburg: nur per Einzelabruf `GET meeting["id"]`). Regel: Wenn
  `agendaItem` in der Liste fehlt, das Meeting-Objekt einzeln holen
  (`kind="meeting"`). Das kostet Magdeburg ~2.500 Anfragen je Jahr — hinnehmbar
  bei 1/s im Wochentakt, weil nur neue/geänderte Meetings (`modified_since`
  funktioniert hier) geholt werden.
- `agendaItem.consultation` ist bei Session vorhanden → die Brücke Papier →
  Ergebnis läuft direkt.

**`rubin.py`** (Freiburg, Darmstadt; OParl 1.0):

- Zeitfilter werden ignoriert; `limit=100` geht; `links.last` vorhanden →
  rückwärts wie ALLRIS, Abbruch per `date`.
- `mainFile.text` trägt bereits den Volltext: `extract` übernimmt ihn als
  `extractor="oparl-text"` statt zu laden.
- Kein `body.agendaItem`; Tagesordnungspunkte nur über Meetings; dort sind
  `result` und `resolutionText` da.
- In PR 2 nur so weit bauen, dass `tests/test_cities_adapters.py` mit einem
  Fixture grün ist; Freiburg bleibt `active=False`.

### 2.4 `council/cities/text.py`

```python
EXTRACTOR = "pypdf"; VERSION = "1"
MAX_PAGES = 60; MAX_CHARS = 80_000
def extract(pdf_bytes: bytes) -> tuple[str, int, str]
    # (text, n_pages, quality); quality: "ok" ≥ 200 Zeichen je Seite im Schnitt, "thin" < 200, "empty" 0, "error" bei Exception
    # Aufräumen wie council/vorlagen.py: Seitenkopf/-fuß-Muster ("Seite: 1/2", "1 von 3 in Zusammenstellung") raus, \n{3,} → \n\n
```

Kein OCR in diesem PR. Dateien mit `quality="empty"` bleiben mit ihrem
`sha256` liegen — ein späterer Extraktor findet sie über `texts.quality`.

### 2.5 `council/cities/pipeline.py`

```python
STAGES = ("fetch", "normalize", "extract", "annotate", "index")

def fetch(spec: BodySpec, raw_path: Path, files_dir: Path, since: str, what=("organizations","meetings","papers","files")) -> dict
    # öffnet CitiesStore(raw_path) — die ROHDATEI DER STADT, nicht die Hauptdatenbank —
    # discover → organizations → meetings → papers → für jede MAIN-Datei ohne sha256: get_file+store_file
    # gibt Zähler zurück: {"pages": n, "papers_seen": n, "papers_new": n, "meetings_seen": n, "files_fetched": n, "files_failed": n}

def normalize(spec: BodySpec, raw_path: Path, main: CitiesStore) -> dict
    # Adapter.normalize(body_id, raw=CitiesStore(raw_path)) → Batch → main.upsert_batch in EINER Transaktion;
    # kopiert außerdem raw_files-Zeilen in die Hauptdatenbank (die Bytes liegen ohnehin in files_dir)

def extract(main: CitiesStore, files_dir: Path, body_id: str | None = None, limit: int | None = None) -> dict
    # für jede Datei mit sha256 und ohne texts-Zeile (pypdf/1): Bytes lesen, text.extract, put_text, mark_stage

def run(spec, main, raw_path, files_dir, since, stages=STAGES) -> dict   # ruft die Stufen in Reihenfolge, sammelt Zähler
```

Warum die Rohdatei je Stadt: Die Ernte darf über Städte parallel laufen (fünf
Prozesse, fünf Hosts, fünf Dateien), die Hauptdatenbank hat **einen**
Schreiber — den `normalize`-Schritt, der Städte nacheinander einliest.

### 2.6 `scripts/cities_backfill.py`

```
python scripts/cities_backfill.py                       # Bericht: was fehlt je Stadt und Stufe, ändert nichts
python scripts/cities_backfill.py --run                 # alle aktiven Städte, alle Stufen, since aus der Registry
python scripts/cities_backfill.py --run --body osnabrueck --stage fetch --since 2025-09-01
python scripts/cities_backfill.py --run --parallel 5    # fetch je Stadt als eigener Subprozess (multiprocessing), danach normalize+extract sequenziell
```

Default ist Bericht, nicht Ausführung (`scripts/CLAUDE.md`). Fortschritt alle
50 Objekte auf stdout mit `flush=True` (Probelauf-Lehre: gepufferte Ausgabe
in Hintergrundläufen sieht wie Stillstand aus). Am Ende `main.stats()` als
Tabelle.

### 2.7 `scripts/cities_import_phase0.py`

Einmalig: liest `~/.cache/ratslotse/phase0/peers.sqlite` (Pfad als Argument),
schreibt je Zeile `papers.raw` als `raw_objects(kind="paper")` und je
`agenda`-Zeile ein synthetisches Meeting-Objekt mit eingebettetem
`agendaItem`, `texts` direkt aus `papers.text` (Extraktor `pypdf`, Version
`0`, Quality nach Länge). Damit ist die Rohablage sofort gefüllt und
`normalize` läuft darüber wie über eine echte Ernte. `raw_files` bleibt leer
(der Probelauf hat keine Bytes behalten); `fetch` holt sie beim ersten
Wochenlauf nach.

### 2.8 Tests (PR 2)

`tests/fixtures/cities/<dialect>/` — je Dialekt **echte** Rohobjekte aus
`peers.sqlite` (`papers.raw`, ein Meeting mit `agendaItem`, drei
Organisationen), auf je ~5 KB gekürzt, ohne Personennamen in `name`-Feldern
(Fraktion ja, Person nein — prüfen).

`tests/test_cities_adapters.py`
- je Dialekt: Fixtures in eine Roh-`CitiesStore` (Temp-Datei) → `normalize`
  → Batch mit erwarteten Zählwerten, Paper-Kinds, File-Roles; Magdeburg-URL
  wird umgebaut; ALLRIS-Titel-Fallback verbindet Papier und TOP.
- Client-Blätterlogik mit dem Paket `responses` (steht in
  `requirements-dev.txt`): Session-Blättern setzt
  `created_since` auf **jeder** Seite (assert auf den Query-String von Seite 3);
  ALLRIS-Blättern beginnt bei `last` und hört bei undatierter Seite auf.

`tests/test_cities_pipeline.py`
- `normalize` zweimal über dieselbe Rohdatei → `stats()` identisch, keine
  neue `raw_objects`-Zeile, `stages` unverändert.
- `extract` mit einem 2-Seiten-PDF-Fixture (per `pypdf` im Test erzeugt) →
  `quality == "ok"`.

**Fertig, wenn:** alles grün **und** ein echter Lauf
`python scripts/cities_backfill.py --run --parallel 5 --since 2025-09-01` auf
dem Entwicklungsrechner in unter 90 Minuten durchläuft und danach
`stats()` je Stadt mindestens diese Werte zeigt (Probelauf, 12 Monate):
Osnabrück 555 Papiere / 555 mit Text, Braunschweig 636 / 635, Münster 376 /
376, Potsdam 700 / 694, Magdeburg 700 / 691 — wobei PR 2 **keine** Obergrenze
je Stadt hat (der Probelauf hatte 700), die Zahlen also größer sein dürfen,
nie kleiner. Ergebnisquote an Tagesordnungspunkten 46–67 %.

---

## PR 3 — Oldenburg-Adapter, der Cron, Kennzahlen

### 3.1 `council/cities/adapters/oldenburg.py`

Liest `council.sqlite` über `CouncilStore` (Pfad: `Settings.council_db` bzw.
`COUNCIL_DB`), kein Netz. `discover` liefert ein synthetisches Body-JSON;
`iter_*` schreiben die Zeilen als Rohobjekte, damit auch Oldenburg durch
dieselbe `normalize`-Stufe läuft (so bleibt die Rohablage vollständig und
die Regel „Schicht 1 entsteht nur aus Schicht 0" ohne Ausnahme).

ID-Schema (stabil, sprechend):

| Objekt | id | Quelle |
|---|---|---|
| Body | `oldenburg` | — |
| Organization | `oldenburg:org:<kgrnr>` | `committees`; dazu je Partei aus `council/parties.py` `oldenburg:faction:<slug>` |
| Meeting | `oldenburg:meeting:<ksinr>` | `council_sessions` (`name` = committee, `start` = `session_date`+`T`+`session_time`) |
| AgendaItem | `oldenburg:agenda:<ksinr>:<item_number>` | `council_agenda_items` (Titel, `is_public`) + `council_decisions` mit `kind='decision'` (`result_raw` = `raw_result`, `outcome` direkt aus `outcome`: `accepted/rejected/postponed/noted/no_decision→none`; `resolution_text` = `official_text`) |
| Paper | `oldenburg:paper:<kvonr>` | `council_templates` (`reference` = `template_number`, `paper_type_raw` = `kind`, ohne die Klammer „(bis 31.12.2022)"; `kind` über `paper_kind`) — **und** je Antrag aus `council_attachments` mit `is_motion=1`: `oldenburg:paper:att:<document_id>`, `kind=MOTION`, `paper_type_raw="Antrag (Anlage)"`, `originator_org_id` aus `applicants[0]` → `oldenburg:faction:<slug>` |
| File | `oldenburg:file:<document_id>` | `council_templates.document_id/document_url` (MAIN) und `council_attachments` (AUXILIARY bzw. MAIN für den Antrag selbst) |
| Consultation | `oldenburg:cons:<id>` | `council_deliberations` (`kvonr`, `ksinr`, `top` → agenda_item_id, `committee` → org, `result` → role_raw) |

Text: `council_templates.raw_text` und `council_attachments.raw_text` gehen
direkt in `texts` (Extraktor `council`, Version `1`), kein PDF-Abruf. Bytes
werden für Oldenburg **nicht** in `cities-files` kopiert — die Quelle liegt
ohnehin im Repo-Betrieb; `files.sha256` bleibt NULL.

**Nicht übernehmen:** `policy_field`, `summary`, `simple_summary`, `interest`,
`importance`, `impact` — das sind Annotationen und kommen, wenn überhaupt, in
PR 4 als eigener Annotator `oldenburg_legacy` mit `version="import"`, damit
sie vergleichbar neben den neuen liegen.

### 3.2 `scripts/check_cities.py`

```python
def main() -> dict:
    # für jede aktive Stadt: fetch(since = heute − 60 Tage) in die Rohdatei, dann normalize, extract;
    # Oldenburg: iter_* über council.sqlite (voll, ist billig), normalize, extract
    # dann (ab PR 4/5) annotate, index
    # Rückgabe: {"bodies": n, "papers_new": n, "files_fetched": n, "texts_new": n, "errors": n, "seconds": n}
if __name__ == "__main__":
    run_guarded("check_cities", main)
```

60 Tage Rückschau statt „seit letztem Lauf", weil Ergebnisse und
Beschlussausfertigungen Wochen nach der Sitzung nachgetragen werden und die
Rohablage Änderungen ohnehin dedupliziert.

`kern/jobs.py`:

```python
{"key": "check_cities", "label": "Andere Städte",
 "description": "Vorlagen, Sitzungen und Ergebnisse aus den Vergleichsstädten (OParl) plus Oldenburg in den Städte-Speicher.",
 "schedule": "sonntags 3 Uhr", "max_age_h": 8 * 24},
```

crontab auf dem Server (nicht im Repo): `0 3 * * 0 …/scripts/check_cities.py`.
Der Lauf gehört auf die **Prod-VM** (auf dev laufen keine Crons; wer dort
Daten will, nimmt `cities_backfill.py`).

### 3.3 Admin-Kennzahlen

Der Admin-Bereich zeigt `job_runs` ohnehin. Zusätzlich in
`web/backend/app/routers/admin.py` einen Block „Städte" in der bestehenden
Statistik-Antwort: je Body Papiere, mit Text, letzter Abruf — aus
`CitiesStore.stats()`. Antwortform in `antworten.py` ergänzen (`CitiesStats`),
Vertrag neu schneiden.

### 3.4 Tests (PR 3)

- `tests/test_cities_oldenburg.py`: frische `council.sqlite` aus dem Schema,
  drei Sitzungen, fünf Beschlüsse, zwei Vorlagen, ein Antrag als Anlage →
  Adapter → `normalize` → erwartete IDs, Outcome-Abbildung, Antrag mit
  Fraktion.
- `tests/test_jobs.py` fängt den Registry-Eintrag automatisch.
- `tests/test_api_vertrag.py` fängt die Antwortform.

**Fertig, wenn:** `check_cities.py` lokal einmal durchläuft (Oldenburg aus dem
Abzug, die anderen mit `--since` klein gehalten über eine Umgebungsvariable
`CITIES_SINCE_DAYS`, Default 60) und im Admin-Panel die sechs Bodies stehen.

---

## PR 4 — Annotationen: Registry, Prompts, Stufe `annotate`, Eval

### 4.1 Prompts nach `kern/prompts.py`

Drei Einträge, wörtlich übernommen aus `~/.cache/ratslotse/phase0/`:

| Schlüssel | Quelle | Platzhalter |
|---|---|---|
| `cities_classify_system` | `classify.py` → `SYSTEM_V2` (die **zweite** Fassung, mit der Liste der Pflichtgeschäfte) | `{fields}` |
| `cities_classify_user` | `classify.py` → `batch_text()`-Format | `{items}` |
| `cities_gap_check_system` | `gaps.py` → `SYSTEM` | — |

`{fields}` wird aus `council.topics.POLICY_FIELDS` gebaut — **dieselben zwölf
Themenfelder wie Oldenburg**, keine eigene Liste. Geschweifte Klammern in
JSON-Beispielen verdoppeln (`{{`/`}}`), sonst wirft `render`.

### 4.2 `kern/llm.py`: zwei Zeilen

```python
"deepseek/deepseek-v4-flash-0731": {"min_max_tokens": DEEPSEEK_MIN_MAX_TOKENS},
```

in `MODEL_PARAMS` — der Name fehlte; ohne Boden antwortet das Modell leer.
Und den Kommentar über `MODEL_PARAMS` um den Satz ergänzen: „Jedes
DeepSeek-Modell, das hier fehlt, liefert bei langen Prompts leere Antworten
mit Status 200."

### 4.3 `council/cities/annotators.py`

```python
@dataclass(frozen=True)
class Annotator:
    key: str; version: str; applies_to: tuple[str, ...]      # ("paper",)
    prompt_system: str; prompt_user: str                     # Schlüssel in kern/prompts.py
    model: str; payload: type                                # pydantic-Modell für die Antwort
    batch_size: int = 6; max_tokens: int = 16000; temperature: float = 0.2
    input_chars: int = 2200
    active: bool = True
    routing_free: bool = True   # Tims Entscheidung 07.09.2026: nur öffentliche Ratsdokumente → kein ZDR-Zwang

class PaperClassification(BaseModel):
    field: Literal[...POLICY_FIELDS keys...]
    instrument: str | None
    transfer: Literal["local", "one_off", "jurisdiction", "adaptable", "direct"]
    competence: Literal["council", "administration", "utility", "holding", "state"]
    originator: str | None
    summary: str

ANNOTATORS: dict[str, Annotator] = {
    "classify": Annotator("classify", "2", ("paper",), "cities_classify_system", "cities_classify_user",
                          "deepseek/deepseek-v4-flash", PaperClassification),
}
def active(key: str) -> Annotator
```

Ein Annotator, sechs Felder — bewusst **ein** Aufruf je Batch wie im
Probelauf, weil die Felder sich gegenseitig stützen (Instrument hilft der
Übertragbarkeit). Wer später ein Feld getrennt rechnen will, legt einen
zweiten Annotator an; die Tabelle bleibt.

### 4.4 `council/cities/annotate.py`

```python
def source_hash(paper: dict, text: str | None, ann: Annotator) -> str
    # sha256 über name + date + paper_type_raw + text[:ann.input_chars] + ann.version + ann.prompt_system

def run(main: CitiesStore, ann: Annotator, body_id: str | None = None, limit: int | None = None,
        workers: int = 8) -> dict
    # 1. main.annotations_missing(...) → Objekte (id, name, date, paper_type_raw, body_id) + text_for_paper
    # 2. Batches à ann.batch_size; ThreadPoolExecutor(workers) für die HTTP-Aufrufe —
    #    aber ALLE Schreibzugriffe über eine Queue in den Hauptthread (ein Schreiber!)
    # 3. je Batch: llm.chat_complete(model=ann.model, response_format={"type":"json_object"},
    #       messages=[system, user], max_tokens=ann.max_tokens, temperature=ann.temperature,
    #       extra_body={"provider": {"sort": "price"}} if ann.routing_free else {},
    #       _feature=f"cities_{ann.key}")
    #    Antwort parsen mit parse_json (Zaun ```json``` abstreifen, sonst äußersten {…}-Block nehmen),
    #    je Ergebnis: id muss im Batch sein, payload gegen ann.payload validieren (ValidationError → Objekt als error markieren),
    #    put_annotation(..., source_hash, model, cost aus resp.usage.cost)
    # 4. Nachlauf: alles, was nach Schritt 3 noch fehlt, EINZELN (batch_size 1) — Modelle lassen in Batches ids aus
    # 5. Rückgabe {"annotated": n, "errors": n, "cost_usd": x, "seconds": s}
```

Warum `extra_body={"provider": {"sort": "price"}}`: `kern.llm._with_routing`
mischt das ZDR-Routing **unter** ein vom Aufrufer gegebenes `provider`; ein
eigener `provider`-Block ersetzt es für diesen Aufruf vollständig. So bleibt
die KI-Frage streng, die Städte-Einordnung nicht. Gemessen: mit Beschränkung
lieferte `gpt-5.6-luna` 53 % der Ergebnisse, ohne 100 %.

Der Fehlerfall „leere Antwort mit Status 200" (`resp.choices` leer oder
`content == ""`) wird als **Batch-Fehler** gezählt und die Objekte laufen in
den Nachlauf; er darf den Lauf nie abbrechen.

### 4.5 Stufe `annotate` in `pipeline.py` und im Cron

`pipeline.annotate(main, body_id=None)` ruft `annotate.run` für jeden
`active` Annotator. `check_cities.py` hängt sie nach `extract` an. Budget:
`CITIES_ANNOTATE_MAX` (Default 3.000 Objekte je Lauf) — mehr als das kostet
der Wochenlauf nie, ein Rückstau wird über mehrere Wochen abgebaut.

### 4.6 Eval

`eval/cases_cities_transfer.json`: die 45 Fälle aus
`~/.cache/ratslotse/phase0/gold.json` **plus** je Fall `name`, `date`,
`paper_type_raw`, `city` und `text[:2200]` aus `peers.sqlite`, damit die
Suite **ohne Datenbank** läuft. Feld `expected`: `{"field", "transfer",
"competence"}`. (Öffentliche Ratsdokumente; keine Personennamen in den
Textauszügen — vor dem Einchecken mit `scripts/lint_adressen.py` und einem
Blick prüfen.)

`eval/run_cities_transfer.py` über `eval/harness.py`: zwei binäre Scores
(`usable` = transfer ∈ {adaptable, direct}; `field` exakt) und ein
Label-Set-Score für `transfer`. `--model` und `--version` als Schalter, damit
der Vergleich aus dem Probelauf wiederholbar ist. In `eval/README.md`
eintragen. Baseline einchecken: `usable` ≥ 0,95, `field` ≥ 0,80 mit
`deepseek/deepseek-v4-flash`, Version 2 — das ist der gemessene Stand (98 % /
84 %); ein Lauf darunter ist eine Regression.

`tests/test_cities_annotators.py`: jeder Annotator hat existierende
Prompt-Schlüssel, ein Payload-Modell, und für jeden aktiven Annotator gibt es
eine Eval-Datei `eval/cases_cities_<key>*.json`. Der Parser `parse_json`
wird mit vier Antwortformen getestet (roh, Zaun, Vorrede, leer).

**Fertig, wenn:** `python eval/run_cities_transfer.py` die Baseline erreicht;
ein Lauf `annotate` über den Bestand aus PR 2 unter 2 $ bleibt (gemessen:
0,91 $ für 2.906 Vorlagen) und `annotation_values("classify","2","transfer")`
die Verteilung des Probelaufs reproduziert (rund 46 % `adaptable`+`direct`).

---

## PR 5 — Index: Chunks, Embeddings, FTS, Nachbarn über Städte

### 5.1 `council/cities/index.py`

```python
EMBED_MODEL = os.environ.get("COUNCIL_EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
CHUNK_SIZE, CHUNK_OVERLAP, MAX_CHUNKS = 1100, 120, 8

def chunk(text: str) -> list[tuple[int, str, int, int]]    # (idx, chunk, start, end); wie council.embeddings.vorlage_chunks, aber ohne excerpt() —
                                                            # die Überschriften-Heuristik dort ist Oldenburg-spezifisch; hier: erste MAX_CHUNKS Fenster über dem ganzen Text
def object_text(paper: dict, annotation: dict | None, text: str | None) -> str
    # f"{name}. {summary or text[:400]} {instrument or ''}" — dieselbe Form wie im Probelauf, damit Nachbarn vergleichbar bleiben

def run(main: CitiesStore, body_id: str | None = None) -> dict
    # 1. chunks + chunk_embeddings für Dateien mit Text ohne Zeile für EMBED_MODEL (text_hash-Cache)
    # 2. object_embeddings für Papiere (source_hash über object_text)
    # 3. fts_upsert für Papiere (name, reference, text, summary aus der aktiven classify-Annotation)
    # 4. neighbors: für jedes Papier mit neuem/geändertem Objektvektor die Top-8 über ALLE Bodies mit score ≥ 0,55,
    #    Matrix = main.object_embeddings(EMBED_MODEL) als numpy (float32, L2-normiert → dot = cosine), wie scripts/embed_decisions.py
```

fastembed ist bewusst **nicht** in `requirements.txt` (s. Wurzel-`CLAUDE.md`);
`index.run` importiert `council.embeddings.embed` lazy und wird nur vom Cron
und `cities_backfill.py` gerufen, nie vom Web-Dienst. Der Web-Dienst liest
nur `neighbors`, `papers_fts` und `annotations`.

### 5.2 Speicher und Laufzeit, gemessen und hochgerechnet

- Objektvektoren: 1,5 KB je Papier; 30.000 Papiere → 45 MB, passen in den
  Arbeitsspeicher der Prod-VM. Chunk-Vektoren (bis 8 je Datei) nur in der
  Tabelle; für die Suche in PR 6 reicht die Objektebene.
- Nachbarn: 30.000 × 30.000 Skalarprodukte in Blöcken à 256 Zeilen wie in
  `embed_decisions.py` — Sekunden, nicht Minuten.
- Erste Füllung Embeddings (13.000 Oldenburger + 3.000 fremde Objekte): unter
  10 Minuten auf dem Entwicklungsrechner (gemessen im Probelauf).

### 5.3 Tests

`tests/test_cities_index.py` mit gemocktem `embed` (liefert deterministische
Vektoren aus einem Hash): Chunks idempotent, `object_embeddings` nur für
geänderte `source_hash`, `neighbors` symmetrisch befüllt, kein Nachbar unter
0,55, `fts_search("Hitzeaktionsplan")` findet das Papier über `summary`.

**Fertig, wenn:** Für den Oldenburger Beschluss „Kommunale Wärmeplanung
(KWP): Oldenburger Wärmeplan" (`council_decisions`, 2026-06-01) liefert
`neighbors("paper", "oldenburg:paper:<kvonr>")` Braunschweigs
„Kommunale Wärmeplanung (KWP) für Braunschweig — Endbericht" mit Score ≥ 0,80
(gemessen: 0,84).

---

## PR 6 — Erste Anwendung: „Anderswo beschlossen" auf der Beschluss-Seite (Web)

Hinter dem Schalter `andere-staedte` (`kern/features.py`):

```python
"andere-staedte": Feature(
    key="andere-staedte",
    description="Auf Beschluss-Seiten: was andere Städte zu derselben Sache beantragt oder beschlossen haben.",
    fertig_wenn="Der Block lag vier Wochen auf dev, und mindestens zwei Nutzer*innen mit Mandat "
                "haben die Treffer als brauchbar bestätigt.",
),
```

### 6.1 Endpunkte (`web/backend/app/routers/cities.py`, öffentlich, `optional_user`)

```
GET /api/council/decision/{decision_id}/elsewhere      → ElsewhereResponse
GET /api/cities/bodies                                 → CitiesBodies
```

`elsewhere`: `decision_id` → `kvonr` (aus `council_decisions`) →
`oldenburg:paper:<kvonr>` → `neighbors(..., exclude_body="oldenburg", limit=6)`
→ je Treffer Paper + aktive `classify`-Annotation + `outcome_for_paper` +
Body-Name. Ohne `kvonr` (Beschluss ohne Vorlage) → über `object_embeddings`
des Beschlusstitels ist in PR 6 **nicht** vorgesehen; Antwort dann `items: []`.

Antwortform in `antworten.py`:

```python
class ElsewhereItem(TypedDict):
    body_id: str; body_name: str
    paper_id: str; reference: str | None; name: str; date: str | None
    kind: str; web: str | None
    outcome: str                     # Outcome-Wert, "none" wenn unbekannt
    score: float
    summary: NotRequired[str | None]; instrument: NotRequired[str | None]
    transfer: NotRequired[str | None]; originator: NotRequired[str | None]
class ElsewhereResponse(TypedDict):
    decision_id: int; items: list[ElsewhereItem]; bodies: list[str]
```

Nullbare Felder als `| None` (Swift-Generator!). Vertrag neu schneiden, Typen
generieren (`REZEPTE.md` → Endpunkt).

Rate-Limit wie die übrigen öffentlichen Council-Endpunkte; Antwort
`Cache-Control: public, max-age=3600` — die Daten ändern sich wöchentlich.

### 6.2 Frontend

`web/frontend/components/council/elsewhere.tsx`, eingebunden in
`app/(app)/council/decision/view.tsx` unterhalb der „Ähnlichen Beschlüsse",
nur wenn `useFeature("andere-staedte")` und `items.length > 0`. Typ aus
`lib/vertrag.ts` (`ApiAntwort<"/council/decision/{decision_id}/elsewhere">`),
Aufruf über `lib/api.ts`.

Gestaltung nach `DESIGNSPRACHE.md`, Anatomie wie die Beschluss-Karte: Zeile 1
Stadt (fett) · Datum · Art als Chip · Ergebnis als Chip (Anzeigetafel-Tönung,
keine dunkle Karte im Hellmodus — Tims Regel); Zeile 2 Titel als Link auf
`web` (neuer Tab); Zeile 3 `summary`. Überschrift des Blocks: „Anderswo
beschlossen", Unterzeile „Was andere Städte zu derselben Sache beantragt oder
beschlossen haben — aus deren Ratsinformationssystemen." Kein Ranking, keine
Prozentzahl.

Leerer Zustand: Block ausblenden, nicht „keine Treffer" zeigen.

### 6.3 Tests und Abnahme

- `tests/test_cities_router.py`: Endpunkt mit gefüllter Test-`cities.sqlite`
  (Fixture aus PR 5) → Form stimmt, `exclude_body` wirkt, unbekannte
  `decision_id` → 404.
- `web/frontend`: bestehende Browsertests laufen mit **leerer** `cities.sqlite`
  grün (der Block darf nie einen Fehler werfen, wenn die Datei fehlt —
  `get_cities_store` legt sie leer an, `neighbors` liefert `[]`).
- **Screenshot** des Blocks am Wärmeplan-Beschluss per `SendUserFile`,
  Gegenlesen abwarten (Tims Regel für jeden UI-PR).

---

## PR 7 — iOS-Nachzug

`ios/CLAUDE.md` gilt: `python scripts/ios_vertrag.py` vor und nach der
Arbeit. Neues `struct ElsewhereItem`/`ElsewhereResponse` mit `CodingKeys`
exakt nach Vertrag, alle nullbaren Felder `Optional`. Section
„Anderswo beschlossen" in der Beschluss-Ansicht, hinter demselben Schalter
(die App liest `/api/app-config`). `xcodegen generate --spec ios/project.yml`,
Ergebnis mitcommitten. Screenshot aus dem Simulator per `SendUserFile`.

---

## Anhang A — Endpunkte, gemessen am 07.09.2026

| Body | Dialekt | Endpunkt |
|---|---|---|
| osnabrueck | allris4 | `https://www.osnabrueck.sitzung-online.de/oparl/system` (CC BY 4.0) |
| braunschweig | allris4 | `https://www.ratsinfo.braunschweig.sitzung-online.de/oparl/system` |
| potsdam | allris4 | `https://www.potsdam.sitzung-online.de/oparl/system` (2 Bodies, Index 0) |
| leipzig | allris4 | `https://www.leipzig.sitzung-online.de/oparl/system` (CC BY 4.0) |
| bonn | allris4 | `https://www.bonn.sitzung-online.de/oparl/system` |
| muenster | session | `https://oparl.stadt-muenster.de/system` |
| magdeburg | session | `https://ratsinfo.magdeburg.de/oparl/system` (DL-DE-Zero; Datei-URLs kaputt) |
| koeln | session | `https://buergerinfo.stadt-koeln.de/oparl/system` |
| dresden | session | `https://oparl.dresden.de/system` (langsam: Timeout 60 s) |
| wuppertal | session | `https://oparl.wuppertal.de/oparl/system` |
| duesseldorf | session | `https://ris-oparl.itk-rheinland.de/Oparl/system` |
| freiburg | rubin | `https://ris.freiburg.de/oparl/system` (OParl 1.0, Volltext im File) |
| darmstadt | rubin | `https://darmstadt.gremien.info/oparl/system` |

Nicht erreichbar oder ohne OParl (Stand 07.09.2026): Wolfsburg (`bodies` →
500), Göttingen, Kiel, Hannover, Salzgitter, Celle, Lübeck, Regensburg,
Bielefeld, Heidelberg, Mainz, Ulm, Erfurt, Kassel, Bremen.

## Anhang B — Was der Umsetzer aus dem Probelauf wiederverwenden kann

`~/.cache/ratslotse/phase0/`:

| Datei | Wiederverwendung |
|---|---|
| `harvest.py` | Blätterlogik je Dialekt (`page_url`, Rückwärtslauf, Session-Filter je Seite), `ptype()`-Regeln, Magdeburg-URL-Umbau — als Vorlage für `oparl.py` und die Adapter |
| `classify.py` | `SYSTEM_V2` (→ Prompt), `parse_json`, Batch-Bau, Nachlauf für Ausgelassene |
| `gaps.py` | Gegenprobe-Prompt und Beleg-Sammlung (für eine spätere Lücken-Stufe) |
| `match.py` | Cluster-Schwelle 0,86 + gleiches Themenfeld (für eine spätere Lücken-Stufe) |
| `gold.json`, `sample_ids.json` | die 45 Eval-Fälle |
| `peers.sqlite` | Rohbestand für `cities_import_phase0.py` und die Test-Fixtures |
| `compare2.py` | Muster für die Eval-Tabelle |

## Anhang C — Was ausdrücklich NICHT in diesen sieben PRs liegt

- Lücken-Analyse (Cluster, Gegenprobe) und „Wellen" — erst, wenn Nutzer mit
  Mandat den Block aus PR 6 bestätigt haben.
- Freitext-Suche über die Städte als Kanal der KI-Frage (`council/qa.py`,
  `RESEARCH_CHANNELS`) — eigener PR nach PR 6, mit Eval an den
  Stadion-Fragen.
- OCR, Layout-Parser, ein zweites Embedding-Modell — die Tabellen sind dafür
  gebaut, die Arbeit ist es nicht.
- Benachrichtigungen („neu in Osnabrück zu deinem Thema") — über
  `notify.einreihen`, eigener PR.
- Aufbewahrungsregel für PDF-Bytes — erst, wenn `data/cities-files` 5 GB
  überschreitet.
