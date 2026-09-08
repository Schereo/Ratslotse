"""Schema des Städte-Speichers — fünf Schichten, streng getrennt.

```
0  raw_objects, raw_files    was die Schnittstelle lieferte, unverändert, append-only
1  bodies … consultations    die acht OParl-Objekte, kanonisiert
2  texts                     Volltext, versioniert nach Extraktor
3  annotations               was ein Modell oder eine Regel dazu sagt
4  chunks … neighbors, FTS   Indizes, je Modell getrennt
```

**Die Regel, die alles zusammenhält:** Jede Schicht ist aus der darunter
vollständig neu berechenbar. Wer 2 bis 4 löscht, verliert Rechenzeit und ein
paar Dollar, keine Daten.

**Warum Schicht 0 append-only ist.** Ein Papier ändert sich: Das Ergebnis wird
Wochen nach der Sitzung nachgetragen, ein Titel korrigiert, eine Anlage
ergänzt. Wer die Zeile überschreibt, verliert die Frage „wann kam das
Ergebnis?" — und zwar bevor sie jemand stellt. ``UNIQUE(oparl_id,
content_hash)`` sorgt dafür, dass ein unveränderter Abruf keine neue Zeile
erzeugt; der Wochenlauf kostet also nichts, solange sich nichts tut.

**Schema und Migration sind zwei Stellen** (``council/CLAUDE.md``): Eine
frische Datenbank entsteht aus ``SCHEMA``, eine gewachsene aus
``MIGRATIONS``. Wer nur eine anfasst, baut einen Fehler, den kein Test sieht.
"""
from __future__ import annotations

SCHEMA_VERSION = 2

SCHEMA = """
-- ---------------------------------------------------------------- Schicht 0
-- Rohablage: nur INSERT. Kein UPDATE, kein DELETE (tests/test_cities_guards.py).
CREATE TABLE IF NOT EXISTS raw_objects (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    body_id       TEXT NOT NULL,
    kind          TEXT NOT NULL,
    oparl_id      TEXT NOT NULL,
    fetched_at    TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    body_json     TEXT NOT NULL,
    UNIQUE (oparl_id, content_hash)
);
CREATE INDEX IF NOT EXISTS idx_raw_objects_body_kind ON raw_objects(body_id, kind);
CREATE INDEX IF NOT EXISTS idx_raw_objects_oparl ON raw_objects(oparl_id);

CREATE TABLE IF NOT EXISTS raw_files (
    sha256      TEXT PRIMARY KEY,
    bytes       INTEGER NOT NULL,
    mime        TEXT,
    first_seen  TEXT NOT NULL,
    path        TEXT NOT NULL
);

-- ---------------------------------------------------------------- Schicht 1
-- Normalisiert. Trägt KEINE Meinung: kein Themenfeld, keine Zusammenfassung,
-- keine Bewertung. Was ein Modell sagt, steht in annotations.
CREATE TABLE IF NOT EXISTS bodies (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    state          TEXT NOT NULL,
    ris_vendor     TEXT NOT NULL,
    oparl_url      TEXT,
    license        TEXT,
    population     INTEGER,
    first_fetched  TEXT,
    last_fetched   TEXT
);

CREATE TABLE IF NOT EXISTS organizations (
    id        TEXT PRIMARY KEY,
    body_id   TEXT NOT NULL,
    name      TEXT NOT NULL,
    kind_raw  TEXT,
    kind      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_organizations_body ON organizations(body_id, kind);

CREATE TABLE IF NOT EXISTS meetings (
    id               TEXT PRIMARY KEY,
    body_id          TEXT NOT NULL,
    organization_id  TEXT,
    name             TEXT NOT NULL,
    start            TEXT,
    "end"            TEXT,
    state_raw        TEXT,
    cancelled        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_meetings_body_start ON meetings(body_id, start);

CREATE TABLE IF NOT EXISTS agenda_items (
    id               TEXT PRIMARY KEY,
    meeting_id       TEXT NOT NULL,
    number           TEXT,
    position         INTEGER,
    name             TEXT NOT NULL,
    public           INTEGER NOT NULL DEFAULT 1,
    result_raw       TEXT,
    outcome          TEXT NOT NULL DEFAULT 'none',
    resolution_text  TEXT
);
CREATE INDEX IF NOT EXISTS idx_agenda_items_meeting ON agenda_items(meeting_id);

CREATE TABLE IF NOT EXISTS papers (
    id                     TEXT PRIMARY KEY,
    body_id                TEXT NOT NULL,
    reference              TEXT,
    name                   TEXT NOT NULL,
    date                   TEXT,
    paper_type_raw         TEXT,
    kind                   TEXT NOT NULL,
    originator_org_id      TEXT,
    under_direction_of_id  TEXT,
    web                    TEXT
);
CREATE INDEX IF NOT EXISTS idx_papers_body_date ON papers(body_id, date);
CREATE INDEX IF NOT EXISTS idx_papers_kind ON papers(kind);

CREATE TABLE IF NOT EXISTS files (
    id              TEXT PRIMARY KEY,
    body_id         TEXT NOT NULL,
    paper_id        TEXT,
    agenda_item_id  TEXT,
    meeting_id      TEXT,
    role            TEXT NOT NULL,
    name            TEXT,
    mime            TEXT,
    size            INTEGER,
    access_url      TEXT,
    sha256          TEXT
);
CREATE INDEX IF NOT EXISTS idx_files_paper ON files(paper_id);
CREATE INDEX IF NOT EXISTS idx_files_sha ON files(sha256);
CREATE INDEX IF NOT EXISTS idx_files_body_role ON files(body_id, role);

CREATE TABLE IF NOT EXISTS consultations (
    id               TEXT PRIMARY KEY,
    paper_id         TEXT NOT NULL,
    meeting_id       TEXT,
    agenda_item_id   TEXT,
    organization_id  TEXT,
    role_raw         TEXT,
    authoritative    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_consultations_paper ON consultations(paper_id);
CREATE INDEX IF NOT EXISTS idx_consultations_agenda ON consultations(agenda_item_id);

-- ---------------------------------------------------------------- Schicht 2
CREATE TABLE IF NOT EXISTS texts (
    file_id       TEXT NOT NULL,
    extractor     TEXT NOT NULL,
    version       TEXT NOT NULL,
    text          TEXT NOT NULL,
    n_pages       INTEGER,
    quality       TEXT NOT NULL,
    extracted_at  TEXT NOT NULL,
    PRIMARY KEY (file_id, extractor, version)
);
CREATE INDEX IF NOT EXISTS idx_texts_quality ON texts(extractor, version, quality);

-- ---------------------------------------------------------------- Schicht 3
-- Eine Tabelle für alles, was jemand über ein Objekt sagt. Eine neue Frage an
-- die Dokumente ist ein neuer Annotator — keine Schemaänderung.
CREATE TABLE IF NOT EXISTS annotations (
    object_kind  TEXT NOT NULL,
    object_id    TEXT NOT NULL,
    annotator    TEXT NOT NULL,
    version      TEXT NOT NULL,
    payload      TEXT NOT NULL,
    source_hash  TEXT NOT NULL,
    model        TEXT,
    cost_usd     REAL,
    created_at   TEXT NOT NULL,
    PRIMARY KEY (object_kind, object_id, annotator, version)
);
CREATE INDEX IF NOT EXISTS idx_annotations_annotator ON annotations(annotator, version);

-- ---------------------------------------------------------------- Schicht 4
CREATE TABLE IF NOT EXISTS chunks (
    file_id     TEXT NOT NULL,
    chunk_idx   INTEGER NOT NULL,
    chunk_text  TEXT NOT NULL,
    span_start  INTEGER NOT NULL,
    span_end    INTEGER NOT NULL,
    text_hash   TEXT NOT NULL,
    PRIMARY KEY (file_id, chunk_idx)
);

CREATE TABLE IF NOT EXISTS chunk_embeddings (
    file_id    TEXT NOT NULL,
    chunk_idx  INTEGER NOT NULL,
    model      TEXT NOT NULL,
    text_hash  TEXT NOT NULL,
    vector     BLOB NOT NULL,
    PRIMARY KEY (file_id, chunk_idx, model)
);

CREATE TABLE IF NOT EXISTS object_embeddings (
    object_kind  TEXT NOT NULL,
    object_id    TEXT NOT NULL,
    model        TEXT NOT NULL,
    source_hash  TEXT NOT NULL,
    vector       BLOB NOT NULL,
    PRIMARY KEY (object_kind, object_id, model)
);

CREATE TABLE IF NOT EXISTS neighbors (
    model        TEXT NOT NULL,
    a_kind       TEXT NOT NULL,
    a_id         TEXT NOT NULL,
    b_kind       TEXT NOT NULL,
    b_id         TEXT NOT NULL,
    score        REAL NOT NULL,
    computed_at  TEXT NOT NULL,
    PRIMARY KEY (model, a_kind, a_id, b_kind, b_id)
);
CREATE INDEX IF NOT EXISTS idx_neighbors_a ON neighbors(a_kind, a_id, score);

CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    paper_id UNINDEXED,
    body_id UNINDEXED,
    name,
    reference,
    text,
    summary,
    tokenize = 'unicode61 remove_diacritics 2'
);

-- ------------------------------------------------------------------ Betrieb
CREATE TABLE IF NOT EXISTS stages (
    object_kind  TEXT NOT NULL,
    object_id    TEXT NOT NULL,
    stage        TEXT NOT NULL,
    version      TEXT NOT NULL,
    status       TEXT NOT NULL,
    error        TEXT,
    at           TEXT NOT NULL,
    PRIMARY KEY (object_kind, object_id, stage, version)
);
CREATE INDEX IF NOT EXISTS idx_stages_stage ON stages(stage, version, status);

CREATE TABLE IF NOT EXISTS idea_clusters (
    model       TEXT NOT NULL,
    version     TEXT NOT NULL,
    cluster_id  INTEGER NOT NULL,
    paper_id    TEXT NOT NULL REFERENCES papers(id),
    score       REAL NOT NULL,
    PRIMARY KEY (model, version, paper_id)
);
CREATE INDEX IF NOT EXISTS idx_idea_clusters ON idea_clusters(model, version, cluster_id);

CREATE TABLE IF NOT EXISTS meta (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
"""

#: Jede spätere Schemaänderung ist ein Paar ``(version, sql)``. Der Stand
#: steht in ``meta.schema_version``; jede Migration läuft genau einmal und
#: muss ein zweites Mal folgenlos bleiben (``CREATE … IF NOT EXISTS``,
#: ``ALTER TABLE`` nur nach Prüfung per ``PRAGMA table_info``).
#:
MIGRATIONS: list[tuple[int, str]] = [
    # 2 — Ideen-Cluster über Stadtgrenzen (09.09.2026).
    #
    # Ein Papier gehört in höchstens EINEN Cluster je (Modell, Fassung); das
    # steht im Primärschlüssel, damit eine zweite Fassung neben der ersten
    # liegen kann, ohne dass jemand aufräumen muss.
    #
    # Warum überhaupt eine Tabelle und nicht `neighbors`: Eine Nachbarschaft
    # ist paarweise und gerichtet, ein Cluster ist eine Menge. Aus Kanten die
    # Menge jedes Mal neu zu rechnen hieße, die Gruppierung im Request zu
    # machen — und die Gruppierung ist der teure Teil.
    (2, """
    CREATE TABLE IF NOT EXISTS idea_clusters (
        model       TEXT NOT NULL,
        version     TEXT NOT NULL,
        cluster_id  INTEGER NOT NULL,
        paper_id    TEXT NOT NULL REFERENCES papers(id),
        score       REAL NOT NULL,
        PRIMARY KEY (model, version, paper_id)
    );
    CREATE INDEX IF NOT EXISTS idx_idea_clusters
        ON idea_clusters(model, version, cluster_id);
    """),
]
