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

SCHEMA_VERSION = 6

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
-- Die Gegenrichtung: von der VORLAGE zu ihrer Gruppe. Der Primärschlüssel
-- führt model, version, paper_id — paper_id steht hinten und ist allein
-- nicht benutzbar. Ohne diesen Index wählt SQLite für die Dubletten-Prüfung
-- der Ideen-Liste `SCAN k2` über alle Cluster-Zeilen: EIN Zähler brauchte
-- damit 14,3 Sekunden (gemessen 09.09.2026, 3.641 Zeilen), mit Index
-- Millisekunden. Ein Endpunkt, der 14 Sekunden braucht, ist kaputt.
CREATE INDEX IF NOT EXISTS idx_idea_clusters_paper ON idea_clusters(paper_id);

-- Der Status einer IDEE je Stadt — die Mehrheit ihrer Vorlagen, nicht die
-- jüngste. `fit` urteilt je Vorlage, und dieselbe Stadt bekommt für dieselbe
-- Sache zweimal „fehlt" und einmal „vorhanden": Gemessen am 10.09.2026 waren
-- 119 von 1.062 Gruppen uneinheitlich, und bei 14 davon widersprach die
-- jüngste Vorlage der Mehrheit. Als lebende Abfrage kostete die Mehrheit
-- 0,65 s je Seitenaufruf — deshalb liegt sie hier, geschrieben vom
-- Cluster-Schritt, gelesen von den Ideen-Abfragen.
CREATE TABLE IF NOT EXISTS idea_group_status (
    model         TEXT NOT NULL,
    version       TEXT NOT NULL,
    body_id       TEXT NOT NULL,
    cluster_id    INTEGER NOT NULL,
    fit_version   TEXT NOT NULL,
    status        TEXT NOT NULL,
    members       INTEGER NOT NULL,
    agreeing      INTEGER NOT NULL,
    -- Die Aggregate über die ANDEREN Städte derselben Gruppe. Sie standen als
    -- Unterabfragen in der Zeilen-Abfrage und kosteten 0,7 s je Seite, weil
    -- die Sortierung sie für jede Kandidatin rechnet, nicht nur für die
    -- dreißig gezeigten (gemessen 10.09.2026). Hier einmal je Cron-Lauf.
    peers         INTEGER NOT NULL DEFAULT 0,
    peer_for      INTEGER NOT NULL DEFAULT 0,
    peer_against  INTEGER NOT NULL DEFAULT 0,
    peer_review   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (model, version, body_id, cluster_id, fit_version)
);


-- ---------------------------------------------------------------- Schicht 5
-- Was MENSCHEN zu einem Urteil sagen. Die einzige Tabelle hier, die weder aus
-- einer Quelle noch aus einem Modell entsteht.
--
-- **Warum sie das Wichtigste im Speicher werden kann.** Der Maßstab für jedes
-- Urteil sind vierzig Fälle, die EIN Mensch an einem Tag beurteilt hat — und
-- in vier von sieben Pull Requests war genau dieser Maßstab der Fehler, nicht
-- das Modell. Vierhundert Rückmeldungen von zwei Ratsmitgliedern wären ein
-- besserer, und sie kosten niemanden Arbeit: ein Klick an der Karte, die
-- ohnehin gelesen wird.
--
-- Ein Konto gibt je Urteil EINE Rückmeldung; eine zweite ersetzt die erste.
-- Es gibt nur „richtig" und „falsch" — eine Skala mit fünf Stufen beantwortet
-- niemand ehrlich, und für einen Maßstab braucht es ohnehin nur die Kante.
CREATE TABLE IF NOT EXISTS feedback (
    object_kind  TEXT NOT NULL,
    object_id    TEXT NOT NULL,
    annotator    TEXT NOT NULL,
    version      TEXT NOT NULL,
    user_id      INTEGER NOT NULL,
    verdict      TEXT NOT NULL CHECK (verdict IN ('right', 'wrong')),
    note         TEXT,
    created_at   TEXT NOT NULL,
    PRIMARY KEY (object_kind, object_id, annotator, version, user_id)
);
CREATE INDEX IF NOT EXISTS feedback_verdict ON feedback(annotator, version, verdict);

-- Der Abschnitt der Niederschrift, der zu EINEM Tagesordnungspunkt gehört
-- (Schicht 2: was in der Quelle steht, nicht was ein Modell daraus liest).
--
-- Warum eine eigene Tabelle und keine Spalte an `agenda_items`: Der
-- Schnitt hat eine Fassung (`splitter`). Wird die Regel besser, liegt die
-- neue Zerlegung neben der alten, und beide lassen sich messen — dieselbe
-- Regel wie bei `texts` und `annotations`. Eine Spalte könnte das nicht.
--
-- `agenda_item_id` ist Teil des Schlüssels und nicht optional: Ein
-- Abschnitt ohne Punkt ist für die Auswertung wertlos, und ihn trotzdem
-- abzulegen hieße, ihn später wieder herausfiltern zu müssen.
CREATE TABLE IF NOT EXISTS protocol_sections (
    file_id         TEXT NOT NULL,
    meeting_id      TEXT NOT NULL,
    agenda_item_id  TEXT NOT NULL,
    splitter        TEXT NOT NULL,
    ord             INTEGER NOT NULL,
    number          TEXT NOT NULL,
    title           TEXT NOT NULL,
    text            TEXT NOT NULL,
    PRIMARY KEY (agenda_item_id, splitter)
);
CREATE INDEX IF NOT EXISTS idx_protocol_sections_meeting
    ON protocol_sections(meeting_id, splitter);

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
    # 6 — Die Niederschrift je Tagesordnungspunkt (10.09.2026). Der Absatz am
    # SCHEMA sagt, warum eine Tabelle mit Fassung und keine Spalte.
    (6, """
    CREATE TABLE IF NOT EXISTS protocol_sections (
        file_id         TEXT NOT NULL,
        meeting_id      TEXT NOT NULL,
        agenda_item_id  TEXT NOT NULL,
        splitter        TEXT NOT NULL,
        ord             INTEGER NOT NULL,
        number          TEXT NOT NULL,
        title           TEXT NOT NULL,
        text            TEXT NOT NULL,
        PRIMARY KEY (agenda_item_id, splitter)
    );
    CREATE INDEX IF NOT EXISTS idx_protocol_sections_meeting
        ON protocol_sections(meeting_id, splitter);
    """),
    # 5 — Der Mehrheits-Status je Stadt und Ideen-Gruppe (10.09.2026). Der
    # Absatz am SCHEMA sagt, warum eine Tabelle und keine Abfrage.
    (5, """
    CREATE TABLE IF NOT EXISTS idea_group_status (
        model         TEXT NOT NULL,
        version       TEXT NOT NULL,
        body_id       TEXT NOT NULL,
        cluster_id    INTEGER NOT NULL,
        fit_version   TEXT NOT NULL,
        status        TEXT NOT NULL,
        members       INTEGER NOT NULL,
        agreeing      INTEGER NOT NULL,
        -- Die Aggregate über die ANDEREN Städte derselben Gruppe. Sie standen als
        -- Unterabfragen in der Zeilen-Abfrage und kosteten 0,7 s je Seite, weil
        -- die Sortierung sie für jede Kandidatin rechnet, nicht nur für die
        -- dreißig gezeigten (gemessen 10.09.2026). Hier einmal je Cron-Lauf.
        peers         INTEGER NOT NULL DEFAULT 0,
        peer_for      INTEGER NOT NULL DEFAULT 0,
        peer_against  INTEGER NOT NULL DEFAULT 0,
        peer_review   INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (model, version, body_id, cluster_id, fit_version)
    );
    """),
    # 4 — Der Weg von der Vorlage zu ihrer Ideen-Gruppe (09.09.2026). Die
    # Ideen-Liste zieht Dubletten je Stadt zusammen und fragt dafür je Zeile
    # „liegt eine jüngere Schwester im selben Cluster?". Ohne Index wählt
    # SQLite `SCAN k2` über alle Cluster-Zeilen — ein Zähler brauchte 14,3
    # Sekunden statt Millisekunden.
    (4, """
    CREATE INDEX IF NOT EXISTS idx_idea_clusters_paper ON idea_clusters(paper_id);
    """),
    # 3 — Rückmeldungen von Menschen zu einem Urteil (09.09.2026). Der Absatz
    # am SCHEMA sagt, warum: Der Maßstab für jedes Urteil sind vierzig
    # handgeurteilte Fälle, und der war viermal der Fehler.
    (3, """
    CREATE TABLE IF NOT EXISTS feedback (
        object_kind  TEXT NOT NULL,
        object_id    TEXT NOT NULL,
        annotator    TEXT NOT NULL,
        version      TEXT NOT NULL,
        user_id      INTEGER NOT NULL,
        verdict      TEXT NOT NULL CHECK (verdict IN ('right', 'wrong')),
        note         TEXT,
        created_at   TEXT NOT NULL,
        PRIMARY KEY (object_kind, object_id, annotator, version, user_id)
    );
    CREATE INDEX IF NOT EXISTS feedback_verdict
        ON feedback(annotator, version, verdict);
    """),
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
