from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import sqlite3

from .scraper import CouncilSession, AgendaItem
from .parties import order_key, parties_for_faction


def _norm_title(t: str) -> str:
    """Normalised title for dedup: drops amounts, years, doc-suffixes and punctuation
    so the same matter across committees ('… - Beschluss' vs '…') and recurring series
    ('… 11.716.000 Euro …' vs '… 10.632.200 Euro …') collapse to one key."""
    t = (t or "").lower()
    t = re.sub(r"[\d.,]+", " ", t)  # amounts, years, budget numbers
    t = re.sub(r"\b(euro|eur|mio|mrd|beschluss|bericht|antrag|vorlage)\b", " ", t)
    t = re.sub(r"[^a-zäöüß ]", " ", t)  # punctuation, €, dashes
    return re.sub(r"\s+", " ", t).strip()


def _dedup_keys(title: str, vorlage_nr, decision_id: int) -> list[str]:
    """Collapse keys for a decision: the base Vorlage-Nr (strongest signal — same
    matter across committees/revisions, '22/0348' == '22/0348/1', and robust to title
    spelling variants) and the normalised title (catches recurring series under
    different Vorlagen). Two rows collapse if they share EITHER. Short/sparse titles
    fall back to the id so distinct tiny-title decisions are never merged."""
    keys: list[str] = []
    if vorlage_nr and str(vorlage_nr).strip():
        # Keep the base Vorlage (first two segments): "22/0348/1" → "22/0348".
        keys.append("v:" + "/".join(str(vorlage_nr).strip().split("/")[:2]))
    nt = _norm_title(title)
    keys.append("t:" + nt if len(nt) >= 12 else f"\x00id{decision_id}")
    return keys


def _int_or_none(v) -> int | None:
    """Coerce an LLM value to int, tolerating strings/None/non-numerics."""
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

SCHEMA = """
CREATE TABLE IF NOT EXISTS council_sessions (
    ksinr         INTEGER PRIMARY KEY,
    committee     TEXT NOT NULL,
    session_date  TEXT NOT NULL,
    session_time  TEXT NOT NULL,
    location      TEXT NOT NULL,
    fetched_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cs_date ON council_sessions(session_date DESC);

CREATE TABLE IF NOT EXISTS council_agenda_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ksinr        INTEGER NOT NULL,
    item_number  TEXT NOT NULL,
    title        TEXT NOT NULL,
    vorlage_nr   TEXT,
    kvonr        INTEGER,
    is_public    INTEGER NOT NULL DEFAULT 1,
    UNIQUE(ksinr, item_number),
    FOREIGN KEY(ksinr) REFERENCES council_sessions(ksinr)
);

-- Dokument-Anhänge je TOP von der Sitzungsseite (Tims Befund 12.08.):
-- Fraktions-Anträge ohne Vorlage hängen NUR hier.
CREATE TABLE IF NOT EXISTS council_agenda_anlagen (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ksinr        INTEGER NOT NULL,
    item_number  TEXT NOT NULL,
    label        TEXT NOT NULL,
    url          TEXT NOT NULL,
    UNIQUE(ksinr, item_number, url)
);

-- Terminierte Sitzungen aus dem Sitzungskalender, noch ohne veröffentlichte
-- Tagesordnung (und damit ohne ksinr — SessionNet verlinkt erst bei
-- Veröffentlichung). Wird bei jedem Scrape komplett ersetzt; abgesagte
-- Termine verschwinden so von selbst.
CREATE TABLE IF NOT EXISTS council_scheduled_sessions (
    committee     TEXT NOT NULL,
    session_date  TEXT NOT NULL,
    session_time  TEXT NOT NULL DEFAULT '',
    location      TEXT NOT NULL DEFAULT '',
    fetched_at    TEXT NOT NULL,
    PRIMARY KEY (committee, session_date, session_time)
);

CREATE TABLE IF NOT EXISTS council_alerts_sent (
    ksinr    INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    sent_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, topic_id)
);

CREATE TABLE IF NOT EXISTS committee_notifications (
    ksinr        INTEGER NOT NULL,
    owner_id     INTEGER NOT NULL,
    agenda_hash  TEXT NOT NULL DEFAULT '',
    sent_at      TEXT NOT NULL,
    PRIMARY KEY(ksinr, owner_id)
);

CREATE TABLE IF NOT EXISTS committees (
    kgrnr   INTEGER,
    name    TEXT NOT NULL,
    UNIQUE(name)
);

-- Verwaist seit dem NWZ-Rückbau: Der Sitzungs-Nachbericht
-- (scripts/session_followup.py) ist weg, die Leser dieser Tabelle sind es
-- inzwischen auch. Sie bleibt trotzdem stehen — `_migrate_owner_id` prüft sie
-- zusammen mit committee_notifications (die weiter benutzt wird), und ohne die
-- Tabelle liefe diese Migration auf bestehenden Datenbanken ins Leere.
CREATE TABLE IF NOT EXISTS session_followups_sent (
    ksinr    INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    sent_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, owner_id)
);

CREATE TABLE IF NOT EXISTS committee_summaries (
    ksinr       INTEGER NOT NULL,
    agenda_hash TEXT NOT NULL,
    summary     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, agenda_hash)
);

-- Kurze KI-Zusammenfassung je TOP (Tims Wunsch 12.08.) — dieselben Sätze,
-- die auch in der Tagesordnungs-Mail stehen; hier je Punkt statt als
-- HTML-Block, damit die App sie unter dem Titel zeigen kann.
CREATE TABLE IF NOT EXISTS agenda_item_summaries (
    ksinr       INTEGER NOT NULL,
    item_number TEXT NOT NULL,
    summary     TEXT NOT NULL,
    agenda_hash TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, item_number)
);

-- Tragweite eines Tagesordnungspunkts (0–100), dieselbe Rubrik wie bei den
-- Beschlüssen (council/impact.py). Eigene Tabelle statt Spalte, weil
-- save_session die Items einer Sitzung ERSETZT — eine Spalte wäre bei jeder
-- Tagesordnungs-Änderung weg und müsste neu bezahlt werden.
CREATE TABLE IF NOT EXISTS agenda_item_impact (
    ksinr       INTEGER NOT NULL,
    item_number TEXT NOT NULL,
    impact      INTEGER NOT NULL,
    reason      TEXT,           -- Grund in einfacher Sprache, steht auf der Karte
    created_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, item_number)
);

-- Tagesordnungs-Stand je (Sitzung, Hash) — die Vergleichsbasis der
-- Änderungs-Meldung (Tims Wunsch 12.08.): save_session ERSETZT die Items,
-- der alte Stand wäre sonst weg, sobald sich die Tagesordnung ändert.
CREATE TABLE IF NOT EXISTS agenda_snapshots (
    ksinr       INTEGER NOT NULL,
    agenda_hash TEXT NOT NULL,
    items_json  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, agenda_hash)
);

-- Parsed public session protocols (Niederschriften). One row per session.
CREATE TABLE IF NOT EXISTS council_protocols (
    ksinr         INTEGER PRIMARY KEY,
    document_id   INTEGER,
    document_url  TEXT,
    protocol_nr   TEXT,
    session_start TEXT,
    session_end   TEXT,
    raw_text      TEXT,
    n_pages       INTEGER,
    -- Zeichen-Offsets der PDF-Seitenanfänge im raw_text (JSON-Liste) — die
    -- Grundlage der seitengenauen Protokoll-Links. NULL im Altbestand
    -- (Backfill: scripts/backfill_protokoll_seiten.py).
    page_offsets  TEXT,
    model         TEXT,
    extracted_at  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'ok'   -- ok | failed
);

-- One row per decision / agenda item extracted from a protocol.
CREATE TABLE IF NOT EXISTS council_decisions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ksinr        INTEGER NOT NULL,
    position     INTEGER NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'decision', -- decision | subvote
    parent_item  TEXT,                          -- TOP number a subvote belongs to
    item_number  TEXT,
    title        TEXT,
    beschluss    TEXT,
    outcome      TEXT,                          -- angenommen|abgelehnt|vertagt|zur_kenntnis|kein_beschluss
    vote         TEXT,                          -- einstimmig|mehrheitlich|null
    gegenstimmen INTEGER,
    enthaltungen INTEGER,
    factions     TEXT,                          -- JSON array
    vorlage_nr   TEXT,
    kvonr        INTEGER,
    raw_result   TEXT,
    policy_field TEXT,                          -- one key from council.topics.POLICY_FIELDS
    policy_tags  TEXT,                          -- JSON array of finer-grained tags
    summary      TEXT,                          -- one-line neutral summary
    amount_eur   REAL,                          -- largest € amount in the text (council.money)
    importance   INTEGER,                       -- Wichtigkeits-Score 0–100 (council.importance), per Backfill
    simple_summary TEXT,                        -- „Lotti erklärt's einfach": 2–3 bürgernahe Sätze (RL-904)
    interest     INTEGER,                       -- Interessantheit 0–100 (council.interest, LLM), per Backfill
    interest_reason TEXT                        -- 1-Satz-Begründung des Interest-Scores
);
CREATE INDEX IF NOT EXISTS idx_decisions_ksinr ON council_decisions(ksinr);
-- NB: the policy_field index is created in _migrate(), not here — on an existing
-- DB this whole SCHEMA runs (via executescript) BEFORE the migration adds the
-- column, so indexing policy_field here would fail with "no such column".

-- Fundstück des Tages (RL-U11): je Ausspiel-Tag EIN kuratierter Archiv-Fund
-- mit 1-Satz-Story — vorab generiert von scripts/generate_fundstuecke.py.
CREATE TABLE IF NOT EXISTS council_fundstuecke (
    day         TEXT PRIMARY KEY,               -- Ausspiel-Datum (ISO)
    decision_id INTEGER NOT NULL,
    kicker      TEXT NOT NULL,                  -- „Heute vor N Jahren" | „Aus dem Archiv"
    story       TEXT NOT NULL,                  -- der eine Satz
    created_at  TEXT NOT NULL
);

-- One row per attendee per session.
CREATE TABLE IF NOT EXISTS council_attendance (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ksinr   INTEGER NOT NULL,
    name    TEXT,
    party   TEXT,
    role    TEXT,                               -- vorsitz|mitglied|verwaltung|protokoll|gast
    note    TEXT
);
CREATE INDEX IF NOT EXISTS idx_attendance_ksinr ON council_attendance(ksinr);

-- Goal tracking: which decisions concern an overarching city goal, and whether
-- they advance / hinder / are neutral toward it (council.goals).
CREATE TABLE IF NOT EXISTS council_goal_links (
    goal        TEXT NOT NULL,
    decision_id INTEGER NOT NULL,
    relevant    INTEGER NOT NULL DEFAULT 0,
    stance      TEXT,                              -- voran|bremst|neutral
    rationale   TEXT,
    PRIMARY KEY (goal, decision_id)
);
CREATE INDEX IF NOT EXISTS idx_goal_links_goal ON council_goal_links(goal);

-- Precomputed nearest neighbours per decision (semantic embeddings, council.embeddings).
CREATE TABLE IF NOT EXISTS council_similar (
    decision_id INTEGER NOT NULL,
    neighbor_id INTEGER NOT NULL,
    rank        INTEGER NOT NULL,
    score       REAL NOT NULL,
    PRIMARY KEY (decision_id, neighbor_id)
);
CREATE INDEX IF NOT EXISTS idx_similar_decision ON council_similar(decision_id);

-- Raw decision embedding vectors (float32 blob) for query-time semantic search.
CREATE TABLE IF NOT EXISTS council_embeddings (
    decision_id INTEGER PRIMARY KEY,
    vector      BLOB NOT NULL
);

-- Auto-generated LLM recap per policy field ("Was bewegte den Rat im Bereich X?",
-- council.recaps). One row per field, replaced when regenerated (≈ monthly via cron).
CREATE TABLE IF NOT EXISTS council_field_recaps (
    policy_field TEXT PRIMARY KEY,
    summary      TEXT NOT NULL,
    n_decisions  INTEGER NOT NULL,
    period_from  TEXT NOT NULL DEFAULT '',
    period_to    TEXT NOT NULL DEFAULT '',
    generated_at TEXT NOT NULL
);

"""


#: Tabellen dieser Datenbank, die an einem Konto hängen.
#:
#: Die Konto-Löschung wohnt in ``kern.store`` und räumte lange nur die dortigen
#: Tabellen ab — der Wächter-Test (``test_account_deletion``) prüfte ebenfalls
#: nur jenes Schema und konnte diese Lücke also gar nicht sehen. Hier liegen
#: aber Verhaltensspuren: *welche* Sitzungen jemandem gemeldet wurden. Das ist
#: personenbezogen und muss beim Löschen mit weg (DSGVO, Recht auf Löschung).
COUNCIL_USER_OWNED_TABLES: tuple[tuple[str, str], ...] = (
    ("committee_notifications", "owner_id"),
    ("session_followups_sent", "owner_id"),
    # KI-Feedback (5a/I-03): Frage und Grund sind Freitext und können
    # Persönliches tragen — beim Konto-Löschen mit weg, kein Sonderfall.
    ("council_qa_feedback", "user_id"),
)


class CouncilStore:
    def __init__(self, path: str | Path, nwz_db_path: str | Path | None = None):
        self._path = path
        # Sibling nwz.sqlite holds the chat_id→owner_id map for the migration.
        if nwz_db_path is None and isinstance(path, (str, Path)) and str(path) != ":memory:":
            nwz_db_path = Path(path).parent / "nwz.sqlite"
        self._nwz_db_path = nwz_db_path
        # check_same_thread=False wie im nwz-Store: FastAPI führt sync-Dependencies
        # und Endpoint in (potenziell verschiedenen) Threadpool-Threads aus — die
        # Verbindung wandert also zwischen Threads. Sicher, weil jede Anfrage ihre
        # eigene Store-Instanz bekommt (keine parallele Nutzung EINER Verbindung).
        self._conn = sqlite3.connect(path, timeout=15, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # WAL + busy_timeout: scraper cron and the web API share this file.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(committee_notifications)").fetchall()}
        if "agenda_hash" not in cols:
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE committee_notifications ADD COLUMN agenda_hash TEXT NOT NULL DEFAULT ''"
                )
        # council_decisions gained sub-vote columns (kind / parent_item).
        dec_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_decisions)").fetchall()}
        if dec_cols:
            with self._conn:
                if "kind" not in dec_cols:
                    self._conn.execute(
                        "ALTER TABLE council_decisions ADD COLUMN kind TEXT NOT NULL DEFAULT 'decision'"
                    )
                if "parent_item" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN parent_item TEXT")
                # Topic classification (council.topics) — additive.
                for col in ("policy_field", "policy_tags", "summary"):
                    if col not in dec_cols:
                        self._conn.execute(f"ALTER TABLE council_decisions ADD COLUMN {col} TEXT")
                if "amount_eur" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN amount_eur REAL")
                # Wichtigkeits-Score (council.importance) — additiv, per Backfill befüllt.
                if "importance" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN importance INTEGER")
                # „Lotti erklärt's einfach" (RL-904) — additiv, per Backfill befüllt.
                if "simple_summary" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN simple_summary TEXT")
                # Interessantheit (RL-U11, council.interest) — LLM-Score fürs Fundstück.
                if "interest" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN interest INTEGER")
                if "interest_reason" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN interest_reason TEXT")
                # Tragweite (RL-U16, council.impact) — LLM-Score für die Priorität;
                # fließt 50/50 in den Wichtig-Wert ein, sobald befüllt.
                if "impact" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN impact INTEGER")
                if "impact_reason" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN impact_reason TEXT")
                # Abweichung des Beschlusses vom Beschlussvorschlag der Verwaltung
                # (Regex-Ernte, council.ernte): unveraendert | leicht | stark.
                if "abweichung" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN abweichung TEXT")
                self._conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_decisions_field ON council_decisions(policy_field)"
                )
                self._conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_decisions_importance ON council_decisions(importance)"
                )
        # Full-text index for hybrid (BM25 + vector) retrieval. rowid = decision id;
        # diacritics folded so "Radweg"/"radweg" and German umlauts match. Populated by
        # scripts/build_decisions_fts.py (and the daily cron).
        self._conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS council_decisions_fts "
            "USING fts5(content, tokenize=\"unicode61 remove_diacritics 2\")"
        )
        # Named entities (projects/places/organizations) and their decision links —
        # the basis for the entity ("Themen-") pages. Rebuilt by scripts/extract_entities.py.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_entities ("
            "id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, "
            "kind TEXT, n INTEGER NOT NULL DEFAULT 0)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_entity_links ("
            "entity_id INTEGER NOT NULL, decision_id INTEGER NOT NULL, "
            "PRIMARY KEY (entity_id, decision_id))"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_entlink_dec ON council_entity_links(decision_id)")
        # Per-entity enrichment (LLM description + geocoding) keyed by *slug* so it
        # survives the full rebuild of council_entities by extract_entities.py.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_entity_meta ("
            "slug TEXT PRIMARY KEY, description TEXT, "
            "lat REAL, lon REAL, geojson TEXT, geo_tried INTEGER NOT NULL DEFAULT 0)"
        )
        # Raw, append-only entity observations (one row per slug×decision) — the
        # source of truth so incremental NER runs (scripts/extract_entities.py) can
        # re-derive council_entities/links with the min-n threshold WITHOUT re-scanning
        # old decisions, and so an entity seen once now + again later still crosses the
        # threshold (its early observation is retained). council_entity_scanned records
        # every decision already passed through the LLM (incl. those yielding no entity)
        # so it is never re-scanned.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_entity_obs ("
            "decision_id INTEGER NOT NULL, slug TEXT NOT NULL, name TEXT NOT NULL, "
            "kind TEXT, PRIMARY KEY (decision_id, slug))"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_entobs_slug ON council_entity_obs(slug)")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_entity_scanned (decision_id INTEGER PRIMARY KEY)"
        )
        # Entity duplicates (council.aliases): the NER names the same thing differently
        # from batch to batch ("Bäderbetrieb Oldenburg" / "Bäderbetrieb der Stadt
        # Oldenburg"), producing several Themen pages for one subject. This maps the
        # alias slug onto the canonical one; rebuild_entities_from_obs applies it when
        # deriving council_entities. Keyed by *slug* (like council_entity_meta) so it
        # survives the rebuild. Reversible: the raw council_entity_obs stay untouched,
        # so deleting a row and re-deriving restores the previous state.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_entity_aliases ("
            "slug TEXT PRIMARY KEY, canonical_slug TEXT NOT NULL, source TEXT NOT NULL, "
            "reason TEXT, created_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_entalias_canon "
            "ON council_entity_aliases(canonical_slug)"
        )
        # Vagheits-Urteil je Themen-Vorschlag (Design 26a). Die Prüfung ist ein
        # LLM-Aufruf — ungecacht würde jeder Aufruf der Themen-Seite ein Dutzend
        # davon auslösen. Ergebnis hält, bis der Name sich ändert; keyed by
        # *slug*, überlebt also den Entitäten-Rebuild.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_topic_vagueness ("
            "slug TEXT PRIMARY KEY, name TEXT NOT NULL, vague INTEGER NOT NULL, "
            "hint TEXT, suggestion TEXT, checked_at TEXT NOT NULL)"
        )
        # Related entities ("Hängt zusammen mit…") — precomputed by council.related
        # via scripts/build_entity_relations.py. rel_type separates the two sources:
        # 'belegt' = co-occurrence in shared decisions (evidence = how many),
        # 'aehnlich' = embedding neighbour used only to fill up to top-K. Keyed by
        # *slug* (like council_entity_meta) so it survives the entity rebuild.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_entity_related ("
            "slug TEXT NOT NULL, neighbor_slug TEXT NOT NULL, rel_type TEXT NOT NULL, "
            "rank INTEGER NOT NULL, score REAL NOT NULL, evidence INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (slug, neighbor_slug))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_entrelated_slug ON council_entity_related(slug, rank)"
        )
        # Vorlagen full text (council.vorlagen): the Sachverhalt/Begründung behind a
        # decision. Keyed by kvonr (the SessionNet document id); vorlage_nr is the
        # human number ("26/0330") decisions/agenda items reference.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_vorlagen ("
            "kvonr INTEGER PRIMARY KEY, vorlage_nr TEXT, title TEXT, art TEXT, "
            "document_id INTEGER, document_url TEXT, raw_text TEXT, n_pages INTEGER, "
            "fetched_at TEXT NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'ok', "  # ok | empty | no_pdf | failed
            "anlagen_scanned INTEGER NOT NULL DEFAULT 0)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_vorlagen_nr ON council_vorlagen(vorlage_nr)")
        # anlagen_scanned kam nach dem ersten Deploy der Tabelle dazu.
        vcols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_vorlagen)").fetchall()}
        if "anlagen_scanned" not in vcols:
            self._conn.execute(
                "ALTER TABLE council_vorlagen ADD COLUMN anlagen_scanned INTEGER NOT NULL DEFAULT 0"
            )
        # Regex-Ernte aus dem Volltext (council.ernte): federführendes Amt,
        # Auswirkungen-Abschnitte, Beschlussvorschlag der Verwaltung.
        for col in ("amt", "klima_check", "finanz_check", "beschlussvorschlag"):
            if col not in vcols:
                self._conn.execute(f"ALTER TABLE council_vorlagen ADD COLUMN {col} TEXT")
        # Nutzer-Feedback zu KI-Antworten (5a/I-03) — der einzige Qualitäts-
        # messer außerhalb der Eval-Gold-Fälle. Bewusst schlank: Frage,
        # Antwort-Anfang, Daumen, optionaler Freitext-Grund.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_qa_feedback ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, frage TEXT NOT NULL, "
            "antwort_auszug TEXT, bewertung TEXT NOT NULL, grund TEXT, "
            "user_id INTEGER, created TEXT NOT NULL)"
        )
        # Anlagen zu Vorlagen: alle als Label+Link, Fraktions-Anträge zusätzlich mit
        # PDF-Text und erkannten Antragstellern (council.vorlagen/_build_anlage_rows).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_anlagen ("
            "document_id INTEGER PRIMARY KEY, kvonr INTEGER NOT NULL, label TEXT, "
            "url TEXT, is_antrag INTEGER NOT NULL DEFAULT 0, antragsteller TEXT, "
            "raw_text TEXT, n_pages INTEGER, fetched_at TEXT NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'listed')"  # listed | ok | empty | failed
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_anlagen_kvonr ON council_anlagen(kvonr)")
        # Gerenderte Planzeichnung (scripts/render_plaene.py): 0 = offen,
        # 1 = Bild liegt unter data/plaene/<document_id>.jpg, -1 = fehlgeschlagen.
        acols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_anlagen)").fetchall()}
        if "bild" not in acols:
            self._conn.execute(
                "ALTER TABLE council_anlagen ADD COLUMN bild INTEGER NOT NULL DEFAULT 0")
        # Beratungsfolge je Vorlage (council.stammdaten): die offiziellen
        # Stationen einer Vorlage durch die Gremien — inkl. geplanter künftiger
        # Beratungen (ergebnis dann NULL). Je kvonr komplett ersetzt, weil
        # Stationen dazukommen und Ergebnisse nachgetragen werden.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_beratungen ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, kvonr INTEGER NOT NULL, "
            "datum TEXT, gremium TEXT NOT NULL DEFAULT '', top TEXT, "
            "is_public INTEGER, ergebnis TEXT, ksinr INTEGER, "
            "fetched_at TEXT NOT NULL)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_beratungen_kvonr ON council_beratungen(kvonr)")
        # Mandatsträger + Gremien-Mitgliedschaften (council.stammdaten). Die
        # Fraktion ist nur der AKTUELLE RIS-Stand — SessionNet überschreibt
        # Fraktionen rückwirkend; die Historie liefert council_attendance.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_persons ("
            "kpenr INTEGER PRIMARY KEY, name TEXT NOT NULL, "
            "fraktion_aktuell TEXT, fetched_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_memberships ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, kpenr INTEGER NOT NULL, "
            "kgrnr INTEGER, gremium TEXT NOT NULL, rolle TEXT, "
            "von TEXT, bis TEXT, fetched_at TEXT NOT NULL)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_memberships_kpenr ON council_memberships(kpenr)")
        # Quizfragen (council.quiz): generierte Multiple-Choice-Fragen je Gebiet
        # (Stadtteil/Wahlbereich/Thema), gegroundet in Wikipedia/Stadt-Website/
        # Ratsdaten. status='retired' fliegt aus den Runden (schlecht bewertet).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_quiz_questions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "area_type TEXT NOT NULL, area_key TEXT NOT NULL, "  # stadtteil|wahlbereich|thema
            "category TEXT NOT NULL, "                            # geschichte|orte|menschen|ratspolitik|schaetzen
            "difficulty TEXT NOT NULL DEFAULT 'mittel', "         # leicht|mittel|schwer
            "question TEXT NOT NULL, options TEXT NOT NULL, "     # options = JSON-Array (4); [] bei estimate
            "correct_index INTEGER NOT NULL, explanation TEXT, "
            "source_type TEXT, source_ref TEXT, "                # wikipedia|stadt|ratsinfo · URL/id
            "content_hash TEXT UNIQUE, "                          # Dedup
            "status TEXT NOT NULL DEFAULT 'active', "             # active|retired
            "qtype TEXT NOT NULL DEFAULT 'mc', "                  # mc | estimate (Schätzfrage-Slider)
            "answer_value REAL, answer_unit TEXT, "              # estimate: richtige Zahl + Einheit
            "range_min REAL, range_max REAL, "                   # estimate: Slider-Grenzen
            "detail TEXT, hint TEXT, topic TEXT, chart TEXT, "     # „Mehr dazu" + Tipp + Beschluss-Stichwort + Diagramm (JSON)
            "lat REAL, lon REAL, place_label TEXT, geojson TEXT, "  # Locator-Karte (Punkt, Linie oder Gebiets-Polygon)
            "image_url TEXT, image_author TEXT, image_license TEXT, "  # Foto (Wikimedia Commons)
            "image_license_url TEXT, image_source_url TEXT, "    # Bildnachweis
            "generated_at TEXT NOT NULL)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_quiz_area ON council_quiz_questions(area_type, area_key)")
        # Stadt-Haushalt (council.haushalt): Ergebnishaushalt je Teilhaushalt und
        # Jahr, geparst aus den offiziellen Haushaltsplan-PDFs (oldenburg.de).
        # Grundlage der Haushalts-Quizfragen samt Diagramm.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_haushalt ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "year INTEGER NOT NULL, "
            "bereich TEXT NOT NULL, "                             # Teilhaushalt-Name; 'Summe' = Gesamtzeile
            "ertraege REAL, aufwendungen REAL, ergebnis REAL, "  # ordentlich, in Euro
            "is_summe INTEGER NOT NULL DEFAULT 0, "
            "source_url TEXT, fetched_at TEXT NOT NULL, "
            "UNIQUE(year, bereich))"
        )
        # Vorlagen-Volltexte semantisch auffindbar machen: je Vorlage mehrere
        # Chunk-Vektoren (Sachverhalt/Begründung), die die Hybrid-Suche auf die
        # zugehörigen Beschlüsse abbildet. text_hash = SHA-256 des Volltexts —
        # macht das Embedding-Skript idempotent (nur Geändertes wird neu embedded).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_vorlage_embeddings ("
            "vorlage_nr TEXT NOT NULL, "
            "chunk_idx INTEGER NOT NULL, "
            "text_hash TEXT NOT NULL, "
            "chunk_text TEXT NOT NULL, "   # der Reranker bekommt die FUNDSTELLE zu sehen
            "vector BLOB NOT NULL, "
            "PRIMARY KEY (vorlage_nr, chunk_idx))"
        )
        # Anlagen-Chunks (Task 33): Gutachten, Konzepte, Stellungnahmen — die
        # Volltexte lädt scripts/backfill_anlagen_texte.py, die Vektoren baut
        # scripts/embed_anlagen.py. Kanal NUR der Gründlichen Recherche (RG-10);
        # die schnelle Frage bleibt von der zusätzlichen Matrix unberührt.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_anlage_embeddings ("
            "document_id INTEGER NOT NULL, "
            "chunk_idx INTEGER NOT NULL, "
            "text_hash TEXT NOT NULL, "
            "chunk_text TEXT NOT NULL, "
            "vector BLOB NOT NULL, "
            "PRIMARY KEY (document_id, chunk_idx))"
        )
        # Pressemitteilungen der Stadt (council/presse.py): Volltext intern für
        # Suche/Embedding, angezeigt werden Titel/Datum/Auszug/Link. Dazu ein
        # eigener FTS-Index und Chunk-Vektoren analog den Vorlagen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_presse ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "url TEXT NOT NULL UNIQUE, "
            "news_id INTEGER, "
            "titel TEXT NOT NULL, "
            "datum TEXT, "
            "text TEXT NOT NULL, "
            "fetched_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS council_presse_fts "
            "USING fts5(content, tokenize=\"unicode61 remove_diacritics 2\")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_presse_embeddings ("
            "presse_id INTEGER NOT NULL, "
            "chunk_idx INTEGER NOT NULL, "
            "text_hash TEXT NOT NULL, "
            "chunk_text TEXT NOT NULL, "
            "vector BLOB NOT NULL, "
            "PRIMARY KEY (presse_id, chunk_idx))"
        )
        # Wortbeiträge aus den Protokollen (Task 16): Redebeiträge, „Anfragen
        # und Anregungen", Einwohnerfragestunde und Zusagen der Verwaltung —
        # die Debatten-Substanz, die in den Beschluss-Floskeln fehlt
        # (Fliegerhorst-Befund). Jeder Beitrag ist sein eigener Such-Chunk.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_wortbeitraege ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ksinr INTEGER NOT NULL, "
            "position INTEGER NOT NULL, "
            "art TEXT NOT NULL, "            # rede | anfrage | einwohnerfrage | zusage
            "top TEXT, "
            "sprecher TEXT, "
            "partei TEXT, "
            "text TEXT NOT NULL, "
            "antwort TEXT, "                 # Verwaltungsantwort bei Anfragen
            "extracted_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_wb_ksinr ON council_wortbeitraege(ksinr)")
        # Chronik der Tagesordnungs-Änderungen (Tims Wunsch 18.08.): Die Push
        # sagt nur noch den Satz — WAS sich geändert hat, zeigt die
        # Sitzungsseite aus dieser Tabelle. Eine Zeile je neuem Stand,
        # unabhängig davon, wer wann benachrichtigt wurde.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS agenda_changes ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ksinr INTEGER NOT NULL, "
            "changed_at TEXT NOT NULL, "
            "diff_json TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agenda_changes_ksinr ON agenda_changes(ksinr)")
        self._conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS council_wortbeitraege_fts "
            "USING fts5(content, tokenize=\"unicode61 remove_diacritics 2\")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_wortbeitraege_embeddings ("
            "wb_id INTEGER PRIMARY KEY, "
            "text_hash TEXT NOT NULL, "
            "vector BLOB NOT NULL)"
        )
        # Server-Cache des Parteien-Bausteins (Task 30): Schlüssel ist der Hash
        # der verdichteten Beitrags-IDs — verschieden formulierte Fragen zum
        # selben Thema treffen denselben Eintrag, ein NEUER Beitrag zum Thema
        # ändert den Hash und erzwingt die Nachverdichtung von selbst.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_partei_meinungen_cache ("
            "schluessel TEXT PRIMARY KEY, frage TEXT, ergebnis TEXT NOT NULL, "
            "created_at TEXT NOT NULL)"
        )
        # Erledigt-Marker der Wortbeitrags-Extraktion am Protokoll: auch ein
        # leeres Ergebnis (Formalien-Niederschrift) zählt als erledigt — ohne
        # den Marker fräße jedes davon dauerhaft einen nächtlichen LLM-Call.
        wcols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_protocols)").fetchall()}
        if "wortbeitraege_extracted_at" not in wcols:
            self._conn.execute(
                "ALTER TABLE council_protocols ADD COLUMN wortbeitraege_extracted_at TEXT")
        if "page_offsets" not in wcols:
            # Seitengenaue Protokoll-Links (18.08.2026): Offsets der PDF-
            # Seitenanfänge im raw_text; Altbestand bleibt NULL bis zum
            # Backfill (scripts/backfill_protokoll_seiten.py).
            self._conn.execute("ALTER TABLE council_protocols ADD COLUMN page_offsets TEXT")
        wb_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_wortbeitraege)")}
        if wb_cols and "seite" not in wb_cols:
            # PDF-Seite der Fundstelle (über Sprecher-Anker aufgelöst);
            # NULL = nicht eindeutig gefunden → Link ohne #page.
            self._conn.execute("ALTER TABLE council_wortbeitraege ADD COLUMN seite INTEGER")
        # Aus raw_result geparste Teilvoten: welche Fraktion stimmte laut
        # Protokoll dagegen / enthielt sich. faction steht wie protokolliert
        # (Gruppen nicht aufgelöst — Fraktion≠Partei, siehe council/parties.py).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_decision_votes ("
            "decision_id INTEGER NOT NULL, "
            "faction TEXT NOT NULL, "
            "stance TEXT NOT NULL, "                    # dagegen | enthaltung
            "PRIMARY KEY (decision_id, faction, stance))"
        )
        self._migrate_quiz_estimate()
        self._migrate_quiz_media()
        self._migrate_quiz_hint()
        self._migrate_owner_id()

    def _migrate_quiz_estimate(self) -> None:
        """Schätzfrage-Slider: numerische Felder für qtype='estimate' in
        bestehende Quiz-Tabellen nachrüsten (idempotent)."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_quiz_questions)").fetchall()}
        adds = [("qtype", "TEXT NOT NULL DEFAULT 'mc'"), ("answer_value", "REAL"),
                ("answer_unit", "TEXT"), ("range_min", "REAL"), ("range_max", "REAL")]
        with self._conn:
            for name, decl in adds:
                if name not in cols:
                    self._conn.execute(f"ALTER TABLE council_quiz_questions ADD COLUMN {name} {decl}")

    def _migrate_quiz_media(self) -> None:
        """„Reichere Antworten": Detailtext, Locator-Karte und Bild (mit
        Bildnachweis) in bestehende Quiz-Tabellen nachrüsten (idempotent)."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_quiz_questions)").fetchall()}
        adds = [("detail", "TEXT"), ("lat", "REAL"), ("lon", "REAL"), ("place_label", "TEXT"),
                ("geojson", "TEXT"),
                ("image_url", "TEXT"), ("image_author", "TEXT"), ("image_license", "TEXT"),
                ("image_license_url", "TEXT"), ("image_source_url", "TEXT")]
        with self._conn:
            for name, decl in adds:
                if name not in cols:
                    self._conn.execute(f"ALTER TABLE council_quiz_questions ADD COLUMN {name} {decl}")

    def _migrate_quiz_hint(self) -> None:
        """„Tipp" (vor dem Auflösen) + „topic" (Such-Stichwort für „Beschlüsse
        dazu") + „chart" (Diagramm-JSON der Auflösung) — idempotent in
        bestehende Quiz-Tabellen nachgerüstet."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_quiz_questions)").fetchall()}
        with self._conn:
            for name in ("hint", "topic", "chart"):
                if name not in cols:
                    self._conn.execute(f"ALTER TABLE council_quiz_questions ADD COLUMN {name} TEXT")

    def _migrate_owner_id(self) -> None:
        """Re-key the per-recipient dedup tables from Telegram chat_id to the
        canonical owner_id (=web_users.id). The map lives in the sibling
        nwz.sqlite; existing rows are backfilled via it. Idempotent."""
        cn_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(committee_notifications)").fetchall()}
        sf_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(session_followups_sent)").fetchall()}
        if "owner_id" in cn_cols and "owner_id" in sf_cols:
            return  # already migrated

        # Build chat_id -> owner_id from kern.sqlite if available.
        chat_to_owner: dict[int, int] = {}
        nwz_path = self._nwz_db_path
        if nwz_path is not None and Path(str(nwz_path)).exists():
            try:
                src = sqlite3.connect(str(nwz_path), timeout=15)
                chat_to_owner = {
                    r[0]: r[1] for r in src.execute(
                        "SELECT telegram_chat_id, id FROM web_users WHERE telegram_chat_id IS NOT NULL"
                    ).fetchall()
                }
                src.close()
            except sqlite3.Error:
                chat_to_owner = {}

        with self._conn:
            if "owner_id" not in cn_cols:
                old = self._conn.execute(
                    "SELECT ksinr, chat_id, agenda_hash, sent_at FROM committee_notifications"
                ).fetchall()
                self._conn.execute("DROP TABLE committee_notifications")
                self._conn.execute(
                    "CREATE TABLE committee_notifications ("
                    " ksinr INTEGER NOT NULL, owner_id INTEGER NOT NULL,"
                    " agenda_hash TEXT NOT NULL DEFAULT '', sent_at TEXT NOT NULL,"
                    " PRIMARY KEY(ksinr, owner_id))"
                )
                for r in old:
                    owner = chat_to_owner.get(r[1])
                    if owner is not None:
                        self._conn.execute(
                            "INSERT OR IGNORE INTO committee_notifications (ksinr, owner_id, agenda_hash, sent_at) "
                            "VALUES (?, ?, ?, ?)", (r[0], owner, r[2], r[3])
                        )
            if "owner_id" not in sf_cols:
                old = self._conn.execute(
                    "SELECT ksinr, chat_id, sent_at FROM session_followups_sent"
                ).fetchall()
                self._conn.execute("DROP TABLE session_followups_sent")
                self._conn.execute(
                    "CREATE TABLE session_followups_sent ("
                    " ksinr INTEGER NOT NULL, owner_id INTEGER NOT NULL, sent_at TEXT NOT NULL,"
                    " PRIMARY KEY(ksinr, owner_id))"
                )
                for r in old:
                    owner = chat_to_owner.get(r[1])
                    if owner is not None:
                        self._conn.execute(
                            "INSERT OR IGNORE INTO session_followups_sent (ksinr, owner_id, sent_at) "
                            "VALUES (?, ?, ?)", (r[0], owner, r[2])
                        )

    def delete_owner_data(self, owner_id: int) -> int:
        """Alles aus dieser Datenbank löschen, was an einem Konto hängt.

        Gegenstück zu ``Store.delete_web_user``: Die Konto-Löschung muss beide
        Datenbanken abräumen, es gibt zwischen ihnen keine Fremdschlüssel, die
        das von allein täten. Gibt die Zahl gelöschter Zeilen zurück.
        """
        n = 0
        with self._conn:
            for tabelle, spalte in COUNCIL_USER_OWNED_TABLES:
                cur = self._conn.execute(f"DELETE FROM {tabelle} WHERE {spalte} = ?", (owner_id,))
                n += cur.rowcount or 0
        return n

    def close(self) -> None:
        self._conn.close()

    def admin_stats(self) -> dict:
        """Council counts for the admin dashboard (read-only)."""
        c = self._conn

        def one(sql: str, *p):
            row = c.execute(sql, p).fetchone()
            return row[0] if row else 0

        # „Läuft der Scraper?“ ist eine andere Frage als „gab es neue Sitzungen?“:
        # council_sessions wird nur beschrieben, wenn eine Sitzung mit
        # veröffentlichter Tagesordnung im Kalender steht — in der sitzungsfreien
        # Zeit also wochenlang gar nicht. Der Terminplan dagegen wird bei jedem
        # Lauf neu geschrieben und ist damit der verlässliche Puls.
        last_session_import = one("SELECT MAX(fetched_at) FROM council_sessions") or None
        last_scheduled = one("SELECT MAX(fetched_at) FROM council_scheduled_sessions") or None
        last_fetch = max([t for t in (last_session_import, last_scheduled) if t], default=None)
        return {
            "sessions": one("SELECT COUNT(*) FROM council_sessions"),
            "upcoming": one("SELECT COUNT(*) FROM council_sessions WHERE session_date >= date('now')"),
            "agenda_items": one("SELECT COUNT(*) FROM council_agenda_items"),
            "committees": one("SELECT COUNT(*) FROM committees"),
            # Design 20a — Ratsinfo-Import-Karte:
            "decisions": one("SELECT COUNT(*) FROM council_decisions"),
            "decisions_with_ki": one("SELECT COUNT(*) FROM council_decisions WHERE policy_field IS NOT NULL"),
            "last_fetch": last_fetch,
            # Stunden seit dem letzten Lauf — die Ampel darf nicht „heute schon
            # gelaufen?“ fragen, sonst steht sie jeden Morgen vor dem 8-Uhr-Cron
            # auf Rot, obwohl alles läuft (Läufe: 8 und 14 Uhr → max. ~18 h).
            "hours_since_fetch": (
                round((datetime.utcnow() - datetime.fromisoformat(last_fetch)).total_seconds() / 3600, 1)
                if last_fetch else None),
            "last_session_import": last_session_import,
            "next_session": one(
                "SELECT MIN(session_date) FROM ("
                " SELECT session_date FROM council_sessions WHERE session_date >= date('now')"
                " UNION ALL"
                " SELECT session_date FROM council_scheduled_sessions WHERE session_date >= date('now'))") or None,
            "fetched_today": one(
                "SELECT (SELECT COUNT(*) FROM council_sessions WHERE substr(fetched_at,1,10) = date('now'))"
                " + (SELECT COUNT(*) FROM council_scheduled_sessions WHERE substr(fetched_at,1,10) = date('now'))"),
        }

    def public_stats(self) -> dict:
        """Headline aggregate counts for the public landing page (no content)."""
        c = self._conn

        def one(sql: str) -> int:
            row = c.execute(sql).fetchone()
            return row[0] if row else 0

        return {
            "decisions": one("SELECT COUNT(*) FROM council_decisions WHERE kind = 'decision'"),
            "sessions": one("SELECT COUNT(*) FROM council_sessions"),
            "entities": one("SELECT COUNT(*) FROM council_entities"),
        }
    def save_session(self, session: CouncilSession) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                """INSERT OR REPLACE INTO council_sessions
                   (ksinr, committee, session_date, session_time, location, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session.ksinr, session.committee, session.session_date,
                 session.session_time, session.location, now),
            )
            self._conn.execute(
                "DELETE FROM council_agenda_items WHERE ksinr = ?", (session.ksinr,)
            )
            self._conn.executemany(
                """INSERT OR IGNORE INTO council_agenda_items
                   (ksinr, item_number, title, vorlage_nr, kvonr, is_public)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (session.ksinr, i.item_number, i.title,
                     i.vorlage_nr, i.kvonr, int(i.is_public))
                    for i in session.agenda_items
                ],
            )
            self._conn.execute(
                "DELETE FROM council_agenda_anlagen WHERE ksinr = ?", (session.ksinr,)
            )
            self._conn.executemany(
                """INSERT OR IGNORE INTO council_agenda_anlagen
                   (ksinr, item_number, label, url) VALUES (?, ?, ?, ?)""",
                [
                    (session.ksinr, i.item_number, a.get("label") or "Anlage", a.get("url") or "")
                    for i in session.agenda_items
                    for a in (getattr(i, "anlagen", None) or [])
                    if a.get("url")
                ],
            )

    def alert_already_sent(self, ksinr: int, topic_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM council_alerts_sent WHERE ksinr = ? AND topic_id = ?",
            (ksinr, topic_id),
        ).fetchone()
        return row is not None

    def mark_alert_sent(self, ksinr: int, topic_id: int) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO council_alerts_sent (ksinr, topic_id, sent_at) VALUES (?,?,?)",
                (ksinr, topic_id, now),
            )
    def replace_scheduled_sessions(self, rows: list) -> None:
        """Terminplan komplett ersetzen (rows: ScheduledSession-Objekte).

        Voller Austausch statt Upsert: Der Kalender ist die Quelle der
        Wahrheit — verlegte oder abgesagte Termine verschwinden so mit.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute("DELETE FROM council_scheduled_sessions")
            self._conn.executemany(
                """INSERT OR REPLACE INTO council_scheduled_sessions
                   (committee, session_date, session_time, location, fetched_at)
                   VALUES (?, ?, ?, ?, ?)""",
                [(r.committee, r.session_date, r.session_time, r.location, now) for r in rows],
            )

    # Kommende Sitzungen kommen aus ZWEI Quellen: echten Sitzungen mit
    # Tagesordnung und bloß terminierten aus dem Kalender. Liste und Zählung
    # müssen dieselbe Menge meinen — deshalb steht die Bedingung genau einmal
    # hier und wird von beiden benutzt.
    _UPCOMING_FROM = """
        FROM (
            SELECT cs.ksinr, cs.committee, cs.session_date, cs.session_time, cs.location,
                   COUNT(ci.id) AS n_items
            FROM council_sessions cs
            LEFT JOIN council_agenda_items ci ON ci.ksinr = cs.ksinr
            WHERE cs.session_date >= ?
            GROUP BY cs.ksinr
            UNION ALL
            SELECT NULL AS ksinr, ss.committee, ss.session_date, ss.session_time, ss.location,
                   0 AS n_items
            FROM council_scheduled_sessions ss
            WHERE ss.session_date >= ?
              AND NOT EXISTS (
                  SELECT 1 FROM council_sessions cs2
                  WHERE cs2.committee = ss.committee AND cs2.session_date = ss.session_date
              )
        )
    """

    def sessions_on(self, tag: str) -> list[dict]:
        """Alle Sitzungen an einem Kalendertag — für die Vorabend-Erinnerung
        (Design 30a, N5). Terminierte ohne Tagesordnung kommen mit; der Aufrufer
        entscheidet, ob er sie braucht."""
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM council_sessions WHERE session_date = ? ORDER BY session_time",
            (tag,))]

    def upcoming_sessions(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """Kommende Sitzungen: echte (mit ksinr/Tagesordnung) plus terminierte
        aus dem Kalender (ksinr NULL), solange keine echte Sitzung desselben
        Gremiums am selben Tag existiert."""
        from datetime import date
        today = date.today().isoformat()
        rows = self._conn.execute(
            f"""SELECT * {self._UPCOMING_FROM}
                ORDER BY session_date ASC, session_time ASC
                LIMIT ? OFFSET ?""",
            (today, today, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    #: Tagesordnungspunkte, die in jeder Sitzung stehen und niemanden
    #: interessieren. Am Bestand gemessen: 20 von 53 kommenden TOPs.
    #: „- Bericht der Verwaltung" ist ein ZUSATZ, kein Punkt: Er hängt an den
    #: spannendsten Titeln der Woche („Ermittlungen Abfallentsorgung
    #: Fliegerhorst (CDU-Fraktion) - Bericht der Verwaltung"). Ein auf das
    #: Zeilenende verankertes Muster warf davon neun weg, darunter fast alle
    #: Fraktionsanträge — deshalb greift die Formalie nur, wenn der Punkt
    #: NICHTS ANDERES ist als diese Floskel.
    _FORMALIE_RE = re.compile(
        r"Beschlussf[äa]higkeit|Genehmigung der Tagesordnung|Genehmigung des Protokolls|"
        r"Einwohnerfragestunde|^Mitteilungen|Anfragen und Anregungen|Verschiedenes|"
        r"^\s*Bericht(?:e)? der Verwaltung\s*$|Wahl der Schriftf[üu]hrung",
        re.IGNORECASE)

    #: „(CDU-Fraktion vom 10.06.2026)", „(Fraktionen BSW und SPD)", „(FDP-Fraktion …)"
    _ANTRAG_RE = re.compile(r"\(\s*(?:die\s+)?(?:Fraktion(?:en)?|Gruppe|Ratsherr|Ratsfrau)\b|"
                            r"[A-ZÄÖÜ][\wÄÖÜäöüß/. ]{1,24}-Fraktion\b", re.IGNORECASE)

    _PERSONALIE_RE = re.compile(
        r"Berufung|Umbesetzung|Bestellung\s+(?:eines|einer)|"
        r"Wahl\s+(?:des|der|eines|einer)\s+(?:stellv|Vorsitz|Schriftf)|"
        r"beratende[sn]?\s+Mitglied", re.IGNORECASE)

    #: Bindende Gegenstände: Was hier greift, wirkt über den Tag hinaus —
    #: Satzungen, Gebühren, Haushalt, Bauleitplanung, Verträge, Grundsätze.
    #: Genau die Rubrik „Bindungswirkung" des Tragweite-Prompts, nur als Regel.
    _BINDEND_RE = re.compile(
        r"Satzung|Geb[üu]hren|Beitrags|Entgelt|Haushalt|Nachtragshaushalt|"
        r"Bebauungsplan|Fl[äa]chennutzungsplan|Bauleitplan|Grundsatzbeschluss|"
        r"Vertrag|Vereinbarung|Konzession|Verordnung|Richtlinie", re.IGNORECASE)

    #: Wo entschieden wird, wiegt schwerer als wo vorberaten wird. Der Rat und
    #: der Verwaltungsausschuss binden die Stadt, ein Fachausschuss bereitet vor.
    _GREMIUM_GEWICHT = ((("stadtrat", "rat der stadt"), 1.5), (("verwaltungsausschuss",), 1.0))

    #: Ab hier gilt ein Punkt als Schwerpunkt der Woche und wird hervorgehoben.
    #: Darunter zeigt die Karte ihre Zeilen ohne Hervorhebung — lieber kein
    #: Schwerpunkt als ein behaupteter.
    TOP_MINDEST = 60

    #: Mehr als zwei Hervorhebungen entwerten sich gegenseitig.
    TOP_MAX = 2

    #: Unter diesem Wert kommt ein Punkt gar nicht auf die Karte. Skala ist die
    #: Tragweite (0–100, s. council/impact.py): 20 ≈ Bericht zur Kenntnis,
    #: 35 ≈ Maßnahme an einer Einrichtung. Darunter lohnt keine Zeile.
    WICHTIG_MINDEST = 30

    #: Alte Heuristik-Schwelle — nur noch für die Umrechnung relevant.
    RANG_MINDEST = 1.5

    #: Lazy geladener Wiederkehr-Zähler (s. _wiederkehr).
    _wiederkehr_cache: dict[str, int] | None = None

    #: „(CDU-Fraktion vom 14.07.2026)" → Antragsteller „CDU-Fraktion"; der
    #: Zusatz frisst sonst die halbe Zeile auf der Karte (im Browser gesehen).
    _ANTRAGSTELLER_RE = re.compile(
        r"\s*\(\s*(?:die\s+)?(?P<wer>[^)]*?)\s*(?:vom\s+\d{1,2}\.\d{1,2}\.\d{2,4})?\s*\)")
    #: Verfahrens-Anhängsel am Titelende, die auf der Karte nichts erklären.
    _TITEL_ANHANG_RE = re.compile(
        r"\s*[-–]\s*(?:\w*[Aa]ntrag mit Bericht der Verwaltung|Bericht(?:e)? der Verwaltung|"
        r"Beschlussantrag|Berichtsantrag|Antrag|Bericht|Beschluss|Vorlage|Kenntnisnahme)\s*$",
        re.IGNORECASE)

    @classmethod
    def _titel_zerlegen(cls, titel: str) -> tuple:
        """Antragsteller heraustrennen und den Titel fürs Anzeigen kürzen.

        „Bildende Kunst im Stadtmuseum (CDU-Fraktion vom 07.07.2026) - Bericht
        der Verwaltung" → („CDU-Fraktion", „Bildende Kunst im Stadtmuseum").
        Der Antragsteller gehört als eigenes Merkmal neben den Titel, nicht
        mitten hinein — sonst bleibt vom Gegenstand nichts übrig.
        """
        wer = None
        m = cls._ANTRAGSTELLER_RE.search(titel or "")
        if m and cls._ANTRAG_RE.search(m.group(0)):
            wer = " ".join((m.group("wer") or "").split()) or None
            titel = (titel[:m.start()] + titel[m.end():]).strip()
        kurz = cls._TITEL_ANHANG_RE.sub("", titel or "").strip(" -–;,")
        return wer, kurz or (titel or "")

    def _punkte_bewerten(self, punkte: list[dict]) -> None:
        """Wichtigkeit je Tagesordnungspunkt — deterministisch, ohne Modell.

        Die Karte trägt fünf Zeilen, die Woche bringt gut dreißig inhaltliche
        Punkte (gemessen). Es braucht also eine Auswahl, und „hat eine
        Kurzfassung" ist keine. Vier Signale, alle am Bestand geprüft:

        * **Behandlungsart** aus der Beratungsfolge — die amtliche Einstufung
          der Verwaltung: ``Entscheidung`` wiegt schwerer als ``Vorberatung``,
          die schwerer als ``Kenntnisnahme``. Kein Titel-Raten.
        * **Fraktionsantrag**: Was eine Fraktion beantragt, ist strittig und
          damit meist bedeutsamer als ein Verwaltungsbericht (Tims Beobachtung
          12.08.) — aber eben nur meist, deshalb ein Gewicht und kein Filter.
        * **Themen-Gewicht**: Nennt der Titel eine bekannte Entität, zählt
          deren Beschluss-Historie (Fliegerhorst 166, Stadtmuseum 30) —
          gedämpft, damit ein Dauerthema nicht jede Woche alles verdrängt.
        * **Vorgeschichte**: eine frühere Station derselben Vorlage. Selten
          (diese Woche 1 von 22), aber wenn, dann ein echter Hinweis.

        Bewusst NICHT verwendet: frühere BESCHLÜSSE zur selben Vorlage. Neue
        Vorlagen haben per Definition keine, und ältere erreichen uns erst mit
        dem Protokoll — gemessen 0 von 33 Punkten.
        """
        import math

        entitaeten = []
        try:
            entitaeten = [(self._falte_namen(r["name"]), r["n"]) for r in self._conn.execute(
                "SELECT name, n FROM council_entities WHERE n >= 5")
                if len(r["name"] or "") >= 4]
        except Exception:  # noqa: BLE001 — ohne Entitäten fehlt nur ein Signal
            pass

        for p in punkte:
            rang = 0.0
            art = (p.get("behandlung") or "").lower()
            if "entscheid" in art:
                rang += 3.0
            elif "vorberat" in art:
                rang += 2.0
            elif art:
                rang += 0.5          # Kenntnisnahme: informativ, nicht folgenlos
            if self._ANTRAG_RE.search(p["title"]):
                rang += 1.5
            # Bindungswirkung: Satzung, Gebühren, Haushalt, Bauleitplan — das
            # Signal, das dem Modell komplett fehlte. Eine Satzungsänderung
            # verlor gegen einen Museumsbericht, weil „Bericht + bekannter
            # Name" mehr Nebenpunkte sammelte als „Entscheidung" (Tim, 15.08.).
            if self._BINDEND_RE.search(p["title"]):
                rang += 2.0
            titel_gefaltet = f" {self._falte_namen(p['title'])} "
            gewicht = max((n for name, n in entitaeten if name and f" {name} " in titel_gefaltet),
                          default=0)
            if gewicht:
                # Gedeckelt auf 1.0: Das Gewicht misst BEKANNTHEIT („Stadtmuseum
                # kam in 30 Beschlüssen vor"), nicht die Bedeutung des heutigen
                # Punktes. Als 2.0-Bonus hat es ganze Ränge gedreht.
                rang += min(1.0, math.log10(gewicht))
            if p.get("vorgeschichte"):
                rang += 1.0
            if p.get("summary"):
                rang += 0.4          # erklärbar schlägt unerklärt bei Gleichstand
            if p.get("vorlage_nr"):
                rang += 0.2
            for namen, bonus in self._GREMIUM_GEWICHT:
                if any(n in (p.get("committee") or "").lower() for n in namen):
                    rang += bonus
                    break
            # Gremien-Personalien sind formal Entscheidungen, aber für die
            # Öffentlichkeit selten der Rede wert („Berufung Beratendes
            # Mitglied …") — sie landeten sonst allein wegen der Behandlungsart
            # ganz oben.
            if self._PERSONALIE_RE.search(p["title"]):
                rang -= 2.0
            # Die Behandlungsart ist eine SCHRANKE, kein Summand mehr: Ein
            # Bericht zur Kenntnis kann sich nicht mehr über Nebensignale an
            # einer Entscheidung vorbeischieben. Die Deckel entsprechen den
            # Ankern des Tragweite-Prompts (Kenntnisnahme ≈ 20 von 100).
            if art and "entscheid" not in art and "vorberat" not in art:
                rang = min(rang, 2.5)
            p["rang"] = round(max(rang, 0.0), 2)
            # Auf die Tragweite-Skala heben (0–100), damit Heuristik und
            # LLM-Bewertung vergleichbar sind: 2.5 → 30, 5 → 60, 8 → 95.
            p["wichtig"] = min(95, round(p["rang"] * 12))
            p["wichtig_quelle"] = "regeln"

    def sitzungen_im_fenster(self, tage: int = 7) -> list[dict]:
        """Jede Sitzung der kommenden ``tage`` Tage — die Grundlage der
        Wochen-Karte.

        ``location`` und die Punktzahl gehören dazu: Design 14 zeigt auf dem
        Desktop „17:00 · Ratssaal" und leitet aus ``n_items == 0`` die Zeile
        „nicht öffentlich" ab — eine Sitzung ohne einen einzigen öffentlichen
        Tagesordnungspunkt ist genau das.

        Eigene Methode, weil der Router die ksinr-Liste **vor** der Vorschau
        braucht: Die Themen-Treffer stehen in der anderen Datenbank und lassen
        sich nicht im selben SQL mitnehmen.
        """
        from datetime import date, timedelta

        heute = date.today()
        bis = (heute + timedelta(days=tage)).isoformat()
        return [dict(r) for r in self._conn.execute(
            "SELECT cs.ksinr, cs.committee, cs.session_date, cs.session_time, "
            "       cs.location, COUNT(ci.id) AS n_items "
            "FROM council_sessions cs "
            "LEFT JOIN council_agenda_items ci ON ci.ksinr = cs.ksinr AND ci.is_public = 1 "
            "WHERE cs.session_date >= ? AND cs.session_date <= ? "
            "GROUP BY cs.ksinr ORDER BY cs.session_date, cs.session_time",
            (heute.isoformat(), bis))]

    def wochenvorschau(self, tage: int = 7, max_punkte: int = 5,
                       meine: dict[int, list[dict]] | None = None) -> dict:
        """Was steht in den nächsten Tagen im Rat an? — „Diese Woche im Rat".

        Bewusst nach VORN gerichtet: Beschlüsse erreichen uns erst mit dem
        Protokoll, und das dauert im Median 119 Tage (am Bestand gemessen).
        Ein Wochenrückblick aus Beschlüssen wäre also ein Rückblick auf den
        vorletzten Monat. Tagesordnungen dagegen liegen vor der Sitzung vor —
        für die kommende Woche stehen sie heute schon da.

        Ausgewählt werden inhaltliche Punkte (Formalien fliegen raus), bevorzugt
        solche mit Kurzfassung und Vorlage, und höchstens zwei je Sitzung, damit
        eine große Tagesordnung die Ausgabe nicht auffrisst.

        ``meine`` sind die Tagesordnungs-Treffer der eigenen Themen
        (``{ksinr: [{item_number, topic_name}]}``, kommt aus der anderen
        Datenbank und wird deshalb hereingereicht). Wer ein Thema getroffen
        hat, ist relevant — solche Punkte umgehen die Rang-Schwelle. Design 14
        baut darauf auf: Sitzungen mit eigenen Treffern klappen ihre Punkte
        auf, alle anderen bleiben eine ruhige Zeile.
        """
        from datetime import date, timedelta

        heute = date.today()
        bis = (heute + timedelta(days=tage)).isoformat()
        sitzungen = self.sitzungen_im_fenster(tage)
        if not sitzungen:
            return {"found": False, "von": heute.isoformat(), "bis": bis,
                    "sitzungen": [], "punkte": []}

        ph = ",".join("?" * len(sitzungen))
        rohe = self._conn.execute(
            f"SELECT a.ksinr, a.item_number, a.title, a.vorlage_nr, a.kvonr, s.summary "
            f"FROM council_agenda_items a "
            f"LEFT JOIN agenda_item_summaries s ON s.ksinr = a.ksinr AND s.item_number = a.item_number "
            f"WHERE a.ksinr IN ({ph}) AND a.is_public = 1 ORDER BY a.id",
            [s["ksinr"] for s in sitzungen]).fetchall()
        nach_sitzung = {s["ksinr"]: s for s in sitzungen}

        kandidaten = []
        for r in rohe:
            titel = (r["title"] or "").strip()
            if not titel or self._FORMALIE_RE.search(titel):
                continue
            sitz = nach_sitzung[r["ksinr"]]
            kandidaten.append({
                "ksinr": r["ksinr"], "item_number": r["item_number"], "title": titel,
                "summary": (r["summary"] or "").strip() or None,
                "vorlage_nr": r["vorlage_nr"], "kvonr": r["kvonr"],
                "committee": sitz["committee"], "session_date": sitz["session_date"],
            })

        # Behandlungsart und Vorgeschichte aus der Beratungsfolge — sie kommt
        # direkt aus dem Ratsinformationssystem und hängt NICHT am Protokoll.
        kvonrs = [k["kvonr"] for k in kandidaten if k["kvonr"]]
        stationen: dict[int, list] = {}
        if kvonrs:
            ph2 = ",".join("?" * len(kvonrs))
            for b in self._conn.execute(
                    f"SELECT kvonr, datum, ergebnis FROM council_beratungen "
                    f"WHERE kvonr IN ({ph2}) ORDER BY datum", kvonrs):
                stationen.setdefault(b["kvonr"], []).append(dict(b))
        for k in kandidaten:
            reihe = stationen.get(k["kvonr"] or 0, [])
            heutige = next((b for b in reihe if b["datum"] == k["session_date"]), None)
            k["behandlung"] = (heutige or {}).get("ergebnis")
            k["vorgeschichte"] = sum(1 for b in reihe if (b["datum"] or "9999") < k["session_date"])
            k["antragsteller"], k["titel_kurz"] = self._titel_zerlegen(k["title"])

        # Eigene Themen-Treffer anheften. Der Abgleich läuft über (ksinr,
        # item_number) — dieselbe Kennung, die auch die Benachrichtigungen
        # benutzen.
        treffer = {(ksinr, m["item_number"]): m.get("topic_name")
                   for ksinr, ms in (meine or {}).items() for m in ms}
        for k in kandidaten:
            k["topic_name"] = treffer.get((k["ksinr"], k["item_number"]))

        self._punkte_bewerten(kandidaten)
        # Wo eine LLM-Tragweite vorliegt, schlägt sie die Regeln: Die Regeln
        # kennen Verfahrenssignale, die Bewertung kennt Betroffene, Geld und
        # Bindungswirkung. Beide liegen auf derselben 0–100-Skala.
        bewertet = {(r["ksinr"], r["item_number"]): (r["impact"], r["reason"])
                    for r in self._conn.execute(
                        f"SELECT ksinr, item_number, impact, reason FROM agenda_item_impact "
                        f"WHERE ksinr IN ({ph})", [s["ksinr"] for s in sitzungen])}
        for k in kandidaten:
            eintrag = bewertet.get((k["ksinr"], k["item_number"]))
            if eintrag:
                k["wichtig"], k["wichtig_grund"] = eintrag[0], eintrag[1]
                k["wichtig_quelle"] = "tragweite"
        # Treffer zuerst, danach nach Rang: Ein Punkt zu einem eigenen Thema ist
        # relevanter als jeder gut bewertete Fremdpunkt.
        kandidaten.sort(key=lambda p: (0 if p["topic_name"] else 1, -p["wichtig"], p["session_date"]))
        je_sitzung: dict[int, int] = {}
        punkte = []
        for p in kandidaten:
            # Wer ein eigenes Thema trifft, ist per Definition relevant — die
            # Rang-Schwelle gilt nur für die allgemeine Auswahl.
            if not p["topic_name"] and p["wichtig"] < self.WICHTIG_MINDEST:
                continue
            # Höchstens drei je Sitzung: Eine volle Tagesordnung soll die
            # Ausgabe nicht auffressen, aber Qualität schlägt Streuung — der
            # frühere Deckel von zwei zog schwache Punkte herein.
            if je_sitzung.get(p["ksinr"], 0) >= 3:
                continue
            je_sitzung[p["ksinr"]] = je_sitzung.get(p["ksinr"], 0) + 1
            punkte.append(p)
            if len(punkte) >= max_punkte:
                break
        # Hervorgehoben wird, was wirklich schwer wiegt — keiner, einer oder
        # zwei. Design 14a sah genau EINEN vor; das erzwang eine Hervorhebung
        # auch in Wochen, in denen der beste Punkt ein Bericht mit 30 war, und
        # deckelte sie in Wochen mit mehreren großen Entscheidungen (Tim,
        # 15.08.). Die Schwelle liegt an den Ankern des Prompts: 55 ≈ neue
        # Richtlinie, 75 ≈ Bebauungsplan fürs Quartier.
        for p in punkte:
            p["top"] = False
        gesetzt: list[set[str]] = []
        # Ein Punkt zum eigenen Thema wird immer hervorgehoben, egal wie die
        # allgemeine Bewertung ausfällt: Für wen ein Thema angelegt ist, ist
        # genau das der Grund hinzusehen. Der Rest der Plätze geht an das,
        # was für die ganze Stadt schwer wiegt.
        eigene = sorted((p for p in punkte if p.get("topic_name")),
                        key=lambda p: -p["wichtig"])
        if eigene:
            eigene[0]["top"] = True
            gesetzt.append({w for w in self._falte_namen(eigene[0]["title"]).split()
                            if len(w) >= 6})
        for p in sorted(punkte, key=lambda p: -p["wichtig"]):
            if p["top"]:
                continue
            if len(gesetzt) >= self.TOP_MAX or p["wichtig"] < self.TOP_MINDEST:
                break
            # Nicht zweimal dieselbe Sache: In der Stadion-Woche standen der
            # Bebauungsplan UND die Flächennutzungsplan-Änderung ganz oben —
            # zwei Hervorhebungen, ein Vorgang. Zwei geteilte Schlagwörter
            # reichen als Beleg (gemessen an echten Wochen).
            worte = {w for w in self._falte_namen(p["title"]).split() if len(w) >= 6}
            if any(len(worte & frueher) >= 2 for frueher in gesetzt):
                continue
            p["top"] = True
            gesetzt.append(worte)
        punkte.sort(key=lambda p: (p["session_date"], p["item_number"] or ""))

        # Wie viele relevante Punkte hätte jede Sitzung — VOR dem Anzeige-
        # Deckel. Design 14 braucht das zweimal: für das Abzeichen („3 für
        # dich") und für die ehrliche Restzeile („1 weiterer Punkt"). Ohne die
        # Rohzahl würde die Karte verschweigen statt zu verkürzen, und genau
        # das verbietet Prinzip ② der Dichte-Matrix.
        relevant: dict[int, int] = {}
        # Getrennt gezählt, weil es zwei verschiedene Dinge sind: „passt zu
        # deinem Thema" und „ist allgemein wichtig". Die Karte trug beides als
        # „N für dich" — bei jemandem ohne passendes Thema war das schlicht
        # falsch (Tims Befund 15.08.).
        treffer_je_sitzung: dict[int, int] = {}
        for k in kandidaten:
            if k["topic_name"]:
                treffer_je_sitzung[k["ksinr"]] = treffer_je_sitzung.get(k["ksinr"], 0) + 1
            if k["topic_name"] or k["wichtig"] >= self.WICHTIG_MINDEST:
                relevant[k["ksinr"]] = relevant.get(k["ksinr"], 0) + 1
        return {
            # Seit Design 14 trägt die Karte auch die Sitzungen ohne relevante
            # Punkte (sie ersetzt „Nächste Sitzungen"). Sie hat also Inhalt,
            # sobald überhaupt eine Sitzung ansteht — vorher hing das an den
            # Punkten, und eine Woche ohne Highlight ließ die Karte verschwinden.
            "found": bool(sitzungen),
            "von": heute.isoformat(), "bis": bis,
            "sitzungen": sitzungen,
            "punkte": punkte,
            "relevant_je_sitzung": relevant,
            "treffer_je_sitzung": treffer_je_sitzung,
            "treffer_gesamt": sum(1 for k in kandidaten if k["topic_name"]),
            "inhaltlich_gesamt": len(kandidaten),
        }

    def count_upcoming_sessions(self) -> int:
        from datetime import date
        today = date.today().isoformat()
        return self._conn.execute(
            f"SELECT COUNT(*) {self._UPCOMING_FROM}", (today, today)
        ).fetchone()[0]

    def recent_sessions(self, limit: int = 10, offset: int = 0) -> list[dict]:
        from datetime import date
        today = date.today().isoformat()
        rows = self._conn.execute(
            """SELECT cs.ksinr, cs.committee, cs.session_date, cs.session_time, cs.location,
                      COUNT(ci.id) AS n_items
               FROM council_sessions cs
               LEFT JOIN council_agenda_items ci ON ci.ksinr = cs.ksinr
               WHERE cs.session_date < ?
               GROUP BY cs.ksinr
               ORDER BY cs.session_date DESC
               LIMIT ? OFFSET ?""",
            (today, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_recent_sessions(self) -> int:
        from datetime import date
        today = date.today().isoformat()
        return self._conn.execute(
            "SELECT COUNT(*) FROM council_sessions WHERE session_date < ?", (today,)
        ).fetchone()[0]

    def mark_notified(self, ksinr: int, owner_id: int, agenda_hash: str = "") -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO committee_notifications (ksinr, owner_id, agenda_hash, sent_at) VALUES (?, ?, ?, ?)",
                (ksinr, owner_id, agenda_hash, now),
            )
    def get_last_notified_hash(self, ksinr: int, owner_id: int) -> str | None:
        """Return the agenda_hash that was last used when notifying this owner, or None if never notified.
        An empty string means the row predates hash tracking and should not trigger a re-notification."""
        row = self._conn.execute(
            "SELECT agenda_hash FROM committee_notifications WHERE ksinr = ? AND owner_id = ?",
            (ksinr, owner_id),
        ).fetchone()
        return row[0] if row is not None else None

    def get_cached_summary(self, ksinr: int, agenda_hash: str) -> str | None:
        """Return the cached summary for this session+agenda, or None on cache miss.
        A cached empty string ('') means 'only routine items' and is a valid hit."""
        row = self._conn.execute(
            "SELECT summary FROM committee_summaries WHERE ksinr = ? AND agenda_hash = ?",
            (ksinr, agenda_hash),
        ).fetchone()
        return row[0] if row is not None else None

    def save_item_summaries(self, ksinr: int, agenda_hash: str, punkte: list[dict]) -> None:
        """TOP-Zusammenfassungen ersetzen (eine Tagesordnung, ein Stand)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute("DELETE FROM agenda_item_summaries WHERE ksinr = ?", (ksinr,))
            self._conn.executemany(
                "INSERT OR REPLACE INTO agenda_item_summaries "
                "(ksinr, item_number, summary, agenda_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                [(ksinr, p["number"], p["summary"], agenda_hash, now)
                 for p in punkte if p.get("number") and p.get("summary")])

    def save_agenda_snapshot(self, ksinr: int, agenda_hash: str, items: list[dict]) -> None:
        """Öffentliche Tagesordnungspunkte zu diesem Hash einfrieren — die
        Vergleichsbasis für die Diff-Änderungsmeldung. INSERT OR IGNORE:
        Derselbe Stand wird nie überschrieben."""
        import json as _json
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO agenda_snapshots (ksinr, agenda_hash, items_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                (ksinr, agenda_hash, _json.dumps(items, ensure_ascii=False), now))

    def get_agenda_snapshot(self, ksinr: int, agenda_hash: str) -> list[dict] | None:
        import json as _json
        row = self._conn.execute(
            "SELECT items_json FROM agenda_snapshots WHERE ksinr = ? AND agenda_hash = ?",
            (ksinr, agenda_hash)).fetchone()
        if row is None:
            return None
        try:
            return _json.loads(row[0])
        except ValueError:
            return None

    def get_latest_agenda_snapshot(self, ksinr: int) -> list[dict] | None:
        """Der jüngste eingefrorene Stand — die Vergleichsbasis der
        Änderungs-Chronik (unabhängig davon, wer benachrichtigt wurde)."""
        import json as _json
        row = self._conn.execute(
            "SELECT items_json FROM agenda_snapshots WHERE ksinr = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1", (ksinr,)).fetchone()
        if row is None:
            return None
        try:
            return _json.loads(row[0])
        except ValueError:
            return None

    def save_agenda_change(self, ksinr: int, diff: dict) -> None:
        """Eine erkannte Tagesordnungs-Änderung in die Chronik schreiben —
        die Sitzungsseite zeigt daraus „Zuletzt geändert"."""
        import json as _json
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT INTO agenda_changes (ksinr, changed_at, diff_json) VALUES (?, ?, ?)",
                (ksinr, now, _json.dumps(diff, ensure_ascii=False)))

    def agenda_changes(self, ksinr: int, limit: int = 3) -> list[dict]:
        """Die jüngsten Änderungen einer Sitzung, neueste zuerst:
        ``[{changed_at, diff}]`` — der Diff in der Form von
        ``agenda_diff.diff_tagesordnung`` (Paare als 2er-Listen)."""
        import json as _json
        rows = self._conn.execute(
            "SELECT changed_at, diff_json FROM agenda_changes "
            "WHERE ksinr = ? ORDER BY id DESC LIMIT ?", (ksinr, limit)).fetchall()
        out: list[dict] = []
        for r in rows:
            try:
                out.append({"changed_at": r["changed_at"], "diff": _json.loads(r["diff_json"])})
            except ValueError:
                continue
        return out

    def save_summary(self, ksinr: int, agenda_hash: str, summary: str) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO committee_summaries (ksinr, agenda_hash, summary, created_at) VALUES (?, ?, ?, ?)",
                (ksinr, agenda_hash, summary, now),
            )

    def save_committees(self, committees: list[tuple[str, int | None]]) -> None:
        with self._conn:
            self._conn.executemany(
                "INSERT OR REPLACE INTO committees (name, kgrnr) VALUES (?, ?)",
                [(name, kgrnr) for name, kgrnr in committees],
            )

    def get_all_committee_names(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT name FROM committees ORDER BY name"
        ).fetchall()
        if rows:
            return [r[0] for r in rows]
        # Fallback: derive names from scraped sessions
        rows = self._conn.execute(
            "SELECT DISTINCT committee FROM council_sessions ORDER BY committee"
        ).fetchall()
        return [r[0] for r in rows]

    def agenda_summaries_for(self, ksinr: int) -> dict[str, str]:
        """{item_number: KI-Kurzfassung} einer Sitzung.

        Für TOPs ohne Vorlage ist die Kurzfassung die einzige Inhaltsangabe,
        die es gibt — und damit das einzige, woran die Themen-Zuordnung sich
        gegenprüfen lässt (siehe ``watcher._pruefe_am_text``).
        """
        return {r["item_number"]: r["summary"] for r in self._conn.execute(
            "SELECT item_number, summary FROM agenda_item_summaries WHERE ksinr = ?",
            (ksinr,)) if r["summary"]}

    def agenda_items(self, ksinr: int) -> list[dict]:
        rows = self._conn.execute(
            """SELECT item_number, title, vorlage_nr, kvonr, is_public
               FROM council_agenda_items WHERE ksinr = ?
               ORDER BY id""",
            (ksinr,),
        ).fetchall()
        out = [dict(r) for r in rows]
        # Anhänge je TOP dazulegen (Tims Befund 12.08.) — ein Query, gruppiert.
        anl: dict[str, list[dict]] = {}
        for r in self._conn.execute(
                "SELECT item_number, label, url FROM council_agenda_anlagen "
                "WHERE ksinr = ? ORDER BY id", (ksinr,)):
            anl.setdefault(r["item_number"], []).append({"label": r["label"], "url": r["url"]})
        zus = {r["item_number"]: r["summary"] for r in self._conn.execute(
            "SELECT item_number, summary FROM agenda_item_summaries WHERE ksinr = ?", (ksinr,))}
        for item in out:
            item["anlagen"] = anl.get(item["item_number"], [])
            item["summary"] = zus.get(item["item_number"])
        return out

    def get_session(self, ksinr: int) -> dict | None:
        row = self._conn.execute(
            """SELECT cs.ksinr, cs.committee, cs.session_date, cs.session_time, cs.location,
                      COUNT(ci.id) AS n_items
               FROM council_sessions cs
               LEFT JOIN council_agenda_items ci ON ci.ksinr = cs.ksinr
               WHERE cs.ksinr = ?
               GROUP BY cs.ksinr""",
            (ksinr,),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _session_where(query: str, committee: str, date_from: str, date_to: str) -> tuple[str, list]:
        """Filter der Sitzungssuche — eine Quelle für Liste UND Zählung. Liefen
        die auseinander, zeigte die Blätterleiste eine andere Menge an, als die
        Seiten hergeben (Muster wie _decision_where)."""
        filters: list[str] = []
        params: list = []
        if query:
            filters.append(
                """(cs.committee LIKE ? OR cs.ksinr IN (
                       SELECT ksinr FROM council_agenda_items
                       WHERE title LIKE ? OR vorlage_nr LIKE ?))"""
            )
            like = f"%{query}%"
            params += [like, like, like]
        if committee:
            filters.append("cs.committee = ?")
            params.append(committee)
        if date_from:
            filters.append("cs.session_date >= ?")
            params.append(date_from)
        if date_to:
            filters.append("cs.session_date <= ?")
            params.append(date_to)
        return ("WHERE " + " AND ".join(filters)) if filters else "", params

    def count_sessions(self, query: str = "", committee: str = "",
                       date_from: str = "", date_to: str = "") -> int:
        where, params = self._session_where(query, committee, date_from, date_to)
        # Ohne den Agenda-Join: der GROUP BY der Liste faltet ihn ohnehin wieder
        # auf eine Zeile je Sitzung zusammen.
        return self._conn.execute(
            f"SELECT COUNT(*) FROM council_sessions cs {where}", params
        ).fetchone()[0]

    def search_sessions(
        self,
        query: str = "",
        committee: str = "",
        date_from: str = "",
        date_to: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Search sessions by committee name or agenda item text. Empty query lists by date."""
        where, params = self._session_where(query, committee, date_from, date_to)
        params = [*params, limit, offset]
        rows = self._conn.execute(
            f"""SELECT cs.ksinr, cs.committee, cs.session_date, cs.session_time, cs.location,
                       COUNT(ci.id) AS n_items
                FROM council_sessions cs
                LEFT JOIN council_agenda_items ci ON ci.ksinr = cs.ksinr
                {where}
                GROUP BY cs.ksinr
                ORDER BY cs.session_date DESC
                LIMIT ? OFFSET ?""",
            params,
        ).fetchall()
        sessions = [dict(r) for r in rows]
        # When searching by text, attach the agenda items that match the query so
        # the UI can show them inline (and highlight them) without a second fetch.
        if query and sessions:
            ksinrs = [s["ksinr"] for s in sessions]
            placeholders = ",".join("?" * len(ksinrs))
            like = f"%{query}%"
            matched = self._conn.execute(
                f"""SELECT ksinr, item_number, title, vorlage_nr, kvonr, is_public
                    FROM council_agenda_items
                    WHERE ksinr IN ({placeholders}) AND (title LIKE ? OR vorlage_nr LIKE ?)
                    ORDER BY ksinr, id""",
                [*ksinrs, like, like],
            ).fetchall()
            by_ksinr: dict[int, list[dict]] = {}
            for r in matched:
                d = dict(r)
                by_ksinr.setdefault(d.pop("ksinr"), []).append(d)
            for s in sessions:
                s["matched_items"] = by_ksinr.get(s["ksinr"], [])
        return sessions

    # ---- protocols / decisions / attendance ----

    def has_protocol(self, ksinr: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM council_protocols WHERE ksinr = ? AND status = 'ok'", (ksinr,)
        ).fetchone()
        return row is not None

    def _insert_decision(self, ksinr, position, kind, parent_item, item_number, title,
                         beschluss, outcome, vote, gegenstimmen, enthaltungen, factions,
                         vorlage_nr, kvonr, raw_result) -> None:
        cur = self._conn.execute(
            "INSERT INTO council_decisions "
            "(ksinr, position, kind, parent_item, item_number, title, beschluss, outcome, "
            " vote, gegenstimmen, enthaltungen, factions, vorlage_nr, kvonr, raw_result) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ksinr, position, kind, parent_item, item_number, title, beschluss, outcome,
             vote, _int_or_none(gegenstimmen), _int_or_none(enthaltungen),
             json.dumps(factions or [], ensure_ascii=False),
             vorlage_nr, _int_or_none(kvonr), raw_result),
        )
        # Nennt der Abstimmungssatz Fraktionen ausdrücklich (Gegenstimmen/
        # Enthaltungen), landen sie strukturiert in council_decision_votes —
        # neue Protokolle tragen ihre Teilvoten damit ab Import.
        if raw_result:
            from council.votes import parse_raw_result
            parsed = parse_raw_result(raw_result)
            if parsed:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO council_decision_votes (decision_id, faction, stance) "
                    "VALUES (?, ?, ?)",
                    [(cur.lastrowid, f, s) for f, s in parsed],
                )

    def save_protocol(
        self,
        ksinr: int,
        document: dict,
        meta: dict,
        raw_text: str,
        n_pages: int,
        model: str,
        decisions: list[dict],
        attendance: list[dict],
        status: str = "ok",
        page_offsets: list[int] | None = None,
    ) -> None:
        """Persist a parsed protocol with its decisions + attendance (replacing any
        prior rows for this session). One transaction."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_protocols "
                "(ksinr, document_id, document_url, protocol_nr, session_start, session_end, "
                " raw_text, n_pages, page_offsets, model, extracted_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ksinr, document.get("document_id"), document.get("url"), meta.get("protocol_nr"),
                 meta.get("session_start"), meta.get("session_end"), raw_text, n_pages,
                 json.dumps(page_offsets) if page_offsets else None, model, now, status),
            )
            # Teilvoten hängen an den decision-ids — vor dem Ersetzen der
            # Beschlüsse mitlöschen, sonst bleiben Waisen zurück (dieselbe
            # Falle wie bei den Themen-Treffern, #340).
            self._conn.execute(
                "DELETE FROM council_decision_votes WHERE decision_id IN "
                "(SELECT id FROM council_decisions WHERE ksinr = ?)", (ksinr,))
            self._conn.execute("DELETE FROM council_decisions WHERE ksinr = ?", (ksinr,))
            self._conn.execute("DELETE FROM council_attendance WHERE ksinr = ?", (ksinr,))
            pos = 0
            for d in decisions:
                self._insert_decision(ksinr, pos, "decision", None,
                                      d.get("item_number"), d.get("title"), d.get("beschluss"),
                                      d.get("outcome"), d.get("vote"), d.get("gegenstimmen"),
                                      d.get("enthaltungen"), d.get("factions"),
                                      d.get("vorlage_nr"), d.get("kvonr"), d.get("raw_result"))
                pos += 1
                for sv in d.get("sub_votes") or []:
                    self._insert_decision(ksinr, pos, "subvote", d.get("item_number"),
                                          d.get("item_number"), sv.get("description"), None,
                                          sv.get("outcome"), sv.get("vote"), sv.get("gegenstimmen"),
                                          sv.get("enthaltungen"), sv.get("factions"),
                                          None, None, sv.get("raw_result"))
                    pos += 1
            for a in attendance:
                self._conn.execute(
                    "INSERT INTO council_attendance (ksinr, name, party, role, note) VALUES (?, ?, ?, ?, ?)",
                    (ksinr, a.get("name"), a.get("party"), a.get("role"), a.get("note")),
                )
            # Regex-Ernte (council.ernte): Sitzungsort aus dem Protokollkopf in die
            # Session übernehmen (der Terminplan liefert ihn leer) und Beschlüsse
            # über die Vorlagen-Nummer an ihre kvonr hängen.
            from council import ernte

            ort = ernte.sitzungsort(raw_text)
            if ort:
                self._conn.execute(
                    "UPDATE council_sessions SET location = ? WHERE ksinr = ? AND location = ''",
                    (ort, ksinr),
                )
            # Auch Revisions-Zitate („22/0348/1") an die Basis-Vorlage
            # („22/0348") hängen — exakter Treffer gewinnt vor dem Präfix
            # (Review-Befund E2: sonst blieben kvonr und abweichung NULL,
            # obwohl get_vorlage_by_nr die Vorlage längst auflöst).
            self._conn.execute(
                "UPDATE council_decisions SET kvonr = COALESCE("
                "(SELECT MAX(v.kvonr) FROM council_vorlagen v WHERE v.vorlage_nr = council_decisions.vorlage_nr), "
                "(SELECT MAX(v.kvonr) FROM council_vorlagen v "
                " WHERE instr(council_decisions.vorlage_nr, v.vorlage_nr || '/') = 1)) "
                "WHERE ksinr = ? AND kvonr IS NULL AND vorlage_nr IS NOT NULL",
                (ksinr,),
            )
        self.refresh_abweichung(ksinr=ksinr)

    def refresh_abweichung(self, ksinr: int | None = None, vorlage_nr: str | None = None) -> int:
        """Beschluss ↔ Beschlussvorschlag vergleichen (council.ernte.abweichung)
        und das Ergebnis an den Beschlüssen ablegen. Zwei Auslöser, weil Vorlage
        und Protokoll in beliebiger Reihenfolge eintreffen: nach save_protocol
        (per ksinr) und nach save_vorlage (per vorlage_nr). Nur angenommene
        Beschlüsse — eine Vertagung oder Ablehnung ist keine Textänderung."""
        from council import ernte

        sql = ("SELECT id, vorlage_nr, beschluss FROM council_decisions "
               "WHERE kind = 'decision' AND outcome = 'angenommen' "
               "AND beschluss IS NOT NULL AND vorlage_nr IS NOT NULL")
        args: tuple = ()
        if ksinr is not None:
            sql += " AND ksinr = ?"
            args = (ksinr,)
        elif vorlage_nr is not None:
            # Auch Beschlüsse, die eine REVISION dieser Nummer zitieren
            # („22/0348/1" bei gespeicherter Basis „22/0348") — der
            # get_vorlage_by_nr-Fallback löst sie ohnehin auf (Befund E2).
            base = "/".join(vorlage_nr.split("/")[:2])
            sql += " AND (vorlage_nr IN (?, ?) OR vorlage_nr LIKE ? || '/%')"
            args = (vorlage_nr, base, vorlage_nr)
        vorschlaege: dict[str, str | None] = {}
        updates = []
        for did, nr, beschluss in self._conn.execute(sql, args).fetchall():
            if nr not in vorschlaege:
                v = self.get_vorlage_by_nr(nr)
                vorschlaege[nr] = (v or {}).get("beschlussvorschlag")
            updates.append((ernte.abweichung(vorschlaege[nr], beschluss), did))
        if updates:
            with self._conn:
                self._conn.executemany(
                    "UPDATE council_decisions SET abweichung = ? WHERE id = ?", updates)
        return len(updates)

    def mark_protocol_failed(self, ksinr: int, document: dict) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_protocols "
                "(ksinr, document_id, document_url, extracted_at, status) VALUES (?, ?, ?, ?, 'failed')",
                (ksinr, document.get("document_id"), document.get("url"), now),
            )

    def get_decisions(self, ksinr: int) -> list[dict]:
        # Sitzungs-Spalten mitziehen wie in get_decision(): sonst fehlten
        # committee/session_date/protocol_url ausgerechnet hier, obwohl der
        # Frontend-Typ CouncilDecision sie überall zusichert.
        rows = self._conn.execute(
            """SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
               WHERE d.ksinr = ? ORDER BY d.position""",
            (ksinr,),
        ).fetchall()
        return [self._decision_row(r) for r in rows]

    def get_attendance(self, ksinr: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT name, party, role, note FROM council_attendance WHERE ksinr = ? ORDER BY id", (ksinr,)
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _decision_row(r) -> dict:
        d = dict(r)
        for key in ("factions", "policy_tags"):
            try:
                d[key] = json.loads(d.get(key) or "[]")
            except (json.JSONDecodeError, TypeError):
                d[key] = []
        # Normalised Antragsteller parties (real factions only, deduped).
        # Multi-Mapping: ein Gruppen-Label („FDP/Volt") zählt für jede Partei.
        d["parties"] = sorted({p for f in d["factions"] for p in parties_for_faction(f)}, key=order_key)
        return d

    # Outcomes grouped into "real votes" vs "reports / no decision".
    _VOTE_OUTCOMES = ("angenommen", "abgelehnt", "vertagt")
    _REPORT_OUTCOMES = ("zur_kenntnis", "kein_beschluss")

    def decision_ids_for_party(self, party: str) -> list[int]:
        """IDs of main decisions whose Antragsteller includes ``party`` —
        Gruppen-Labels („FDP/Volt") matchen für jede beteiligte Partei."""
        ids = []
        for row in self._conn.execute("SELECT id, factions FROM council_decisions WHERE kind = 'decision'"):
            try:
                arr = json.loads(row["factions"] or "[]")
            except (json.JSONDecodeError, TypeError):
                arr = []
            if any(party in parties_for_faction(f) for f in arr):
                ids.append(row["id"])
        return ids

    def _decision_where(self, query, committee, outcome, faction, date_from, date_to,
                        kind, category, field="", party_ids=None, include_subvotes=False,
                        only_ids=None):
        """Build the WHERE clause + params shared by search and count."""
        filters: list[str] = []
        params: list = []
        if only_ids is not None:
            # Design 28a/S4: Vorgegebene Beschluss-Menge (die semantischen Treffer
            # eines Nutzer-Themas). Die Zuordnung liegt in nwz.sqlite, also in
            # einer anderen Datei — ein JOIN ist unmöglich, der Router reicht
            # die ids herein. Bewusst getrennt von party_ids, damit sich beide
            # Einschränkungen kombinieren lassen.
            if only_ids:
                filters.append(f"d.id IN ({','.join('?' * len(only_ids))})")
                params += list(only_ids)
            else:
                filters.append("0")  # Thema ohne Treffer
        if party_ids is not None:
            # Restrict to a party's decisions (ids precomputed via normalisation).
            if party_ids:
                filters.append(f"d.id IN ({','.join('?' * len(party_ids))})")
                params += party_ids
            else:
                filters.append("0")  # party given but no matches
        if query:
            filters.append("(d.title LIKE ? OR d.beschluss LIKE ? OR d.summary LIKE ?)")
            like = f"%{query}%"
            params += [like, like, like]
        if committee:
            filters.append("cs.committee = ?")
            params.append(committee)
        if field:
            filters.append("d.policy_field = ?")
            params.append(field)
        if outcome:
            filters.append("d.outcome = ?")
            params.append(outcome)
        if category == "vote":
            filters.append(f"d.outcome IN ({','.join('?' * len(self._VOTE_OUTCOMES))})")
            params += list(self._VOTE_OUTCOMES)
        elif category == "report":
            filters.append(f"(d.outcome IN ({','.join('?' * len(self._REPORT_OUTCOMES))}) OR d.outcome IS NULL)")
            params += list(self._REPORT_OUTCOMES)
        if kind:
            filters.append("d.kind = ?")
            params.append(kind)
        elif not include_subvotes:
            # Design 23a: Änderungsanträge (kind='subvote') tauchen standardmäßig
            # NICHT als eigene Treffer auf — sie hängen als Kontext am Ursprungs-
            # beschluss. include_subvotes=True (Filter „einzeln zeigen") bringt sie
            # zurück; ein expliziter kind-Filter behält Vorrang.
            filters.append("d.kind = 'decision'")
        if faction:
            filters.append("d.factions LIKE ?")
            params.append(f"%{faction}%")
        if date_from:
            filters.append("cs.session_date >= ?")
            params.append(date_from)
        if date_to:
            filters.append("cs.session_date <= ?")
            params.append(date_to)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        return where, params

    def search_decisions(
        self,
        query: str = "",
        committee: str = "",
        outcome: str = "",
        faction: str = "",
        date_from: str = "",
        date_to: str = "",
        kind: str = "",
        category: str = "",
        sort: str = "date_desc",
        field: str = "",
        party: str = "",
        limit: int = 50,
        offset: int = 0,
        include_subvotes: bool = False,
        only_ids: list[int] | None = None,
    ) -> list[dict]:
        """Search extracted decisions, joined with their session (committee + date).
        ``category`` is "vote" (decided) or "report" (zur Kenntnis / no decision).
        ``field`` filters by policy field, ``party`` by normalised Antragsteller;
        ``sort`` ∈ {date_desc, date_asc, faction, importance}."""
        order = {
            "date_asc": "cs.session_date ASC, d.position",
            # Non-empty factions first ('["…' < '[]'), grouped, newest within.
            "faction": "d.factions ASC, cs.session_date DESC",
            # Wichtigste zuerst — mit Alters-Dämpfung. Ohne sie dominieren die
            # Haushaltsbeschlüsse: Sie haben strukturell die höchste Tragweite
            # und verdrängen alles Aktuelle, egal wie alt sie sind. Der Wert
            # halbiert sich nach 2 Jahren (1 / (1 + Alter/2 Jahre)) — bewusst
            # hyperbolisch statt exponentiell, damit historische Großbeschlüsse
            # nach hinten rutschen, aber nicht völlig verschwinden.
            # MAX(0, …) fängt künftig datierte Sitzungen ab (kein Auftrieb).
            "importance": (
                "d.importance IS NULL, "
                "d.importance / (1.0 + MAX(0.0, julianday('now') - julianday(cs.session_date)) / 730.0) DESC, "
                "cs.session_date DESC"
            ),
            # RL-U15: Unterhaltungs-Sortierung — Gesprächswert statt Priorität.
            "interest": "d.interest IS NULL, d.interest DESC, cs.session_date DESC",
        }.get(sort, "cs.session_date DESC, d.position")
        party_ids = self.decision_ids_for_party(party) if party else None
        where, params = self._decision_where(query, committee, outcome, faction,
                                              date_from, date_to, kind, category, field, party_ids,
                                              include_subvotes=include_subvotes, only_ids=only_ids)
        rows = self._conn.execute(
            f"""SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
                FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
                {where}
                ORDER BY {order}
                LIMIT ? OFFSET ?""",
            [*params, limit, offset],
        ).fetchall()
        return [self._decision_row(r) for r in rows]

    def backfill_importance(self, only_missing: bool = False) -> int:
        """(Neu-)Berechnung des Wichtigkeits-Scores (``council.importance``) für
        alle Beschlüsse → Spalte ``council_decisions.importance``. Braucht das
        Gremium (JOIN Sitzung) und die Länge der Beratungsfolge (COUNT über
        ``kvonr``). Idempotent; gibt die Zahl aktualisierter Zeilen zurück.
        Läuft in ``scripts/weekly_enrich.py`` (nach dem Scrapen von Beschlüssen
        und Beratungen) und im Erstlauf-Skript ``scripts/score_importance.py``."""
        from council import importance as _imp
        where = "WHERE d.importance IS NULL" if only_missing else ""
        rows = self._conn.execute(
            f"""SELECT d.*, cs.committee,
                       (SELECT COUNT(*) FROM council_beratungen b WHERE b.kvonr = d.kvonr) AS n_beratungen
                FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                {where}"""
        ).fetchall()
        n = 0
        with self._conn:
            for r in rows:
                d = dict(r)
                score = _imp.importance_score(d, n_beratungen=(d.get("n_beratungen") or None))
                # RL-U16: Tragweite (LLM) mischt 50/50 in den Wichtig-Wert,
                # sobald sie befüllt ist — die Heuristik bleibt der Boden.
                # Vor dem ersten rate_impact-Lauf ändert sich damit nichts.
                if d.get("impact") is not None:
                    score = round((score + int(d["impact"])) / 2)
                self._conn.execute(
                    "UPDATE council_decisions SET importance = ? WHERE id = ?", (score, d["id"]))
                n += 1
        return n

    def count_decisions(
        self, query="", committee="", outcome="", faction="", date_from="", date_to="",
        kind="", category="", field="", party="", include_subvotes=False,
        only_ids: list[int] | None = None,
    ) -> int:
        party_ids = self.decision_ids_for_party(party) if party else None
        where, params = self._decision_where(query, committee, outcome, faction,
                                             date_from, date_to, kind, category, field, party_ids,
                                             include_subvotes=include_subvotes, only_ids=only_ids)
        row = self._conn.execute(
            f"""SELECT COUNT(*) FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr {where}""",
            params,
        ).fetchone()
        return row[0] if row else 0

    def decisions_needing_simple_summary(self, limit: int | None = None) -> list[dict]:
        """Beschlüsse ohne „einfach erklärt"-Kurzfassung (RL-904): nur echte
        Beschlüsse mit substanziellem Beschlusstext, neueste zuerst — so holt
        ein limitierter Backfill die relevantesten zuerst nach."""
        sql = """SELECT d.id, d.title, d.beschluss, d.summary, cs.committee, cs.session_date
                 FROM council_decisions d
                 JOIN council_sessions cs ON cs.ksinr = d.ksinr
                 WHERE d.kind = 'decision' AND d.simple_summary IS NULL
                   AND d.beschluss IS NOT NULL AND length(d.beschluss) >= 200
                 ORDER BY cs.session_date DESC, d.id"""
        args: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            args = (limit,)
        return [dict(r) for r in self._conn.execute(sql, args).fetchall()]

    def save_simple_summary(self, decision_id: int, text: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE council_decisions SET simple_summary = ? WHERE id = ?",
                (text, decision_id),
            )

    # ---- Interessantheit + Fundstück (RL-U11) --------------------------------

    def decisions_needing_interest(self, limit: int | None = None) -> list[dict]:
        """Beschlüsse ohne Interessantheits-Score: nur echte Beschlüsse mit
        Titel, neueste zuerst (ein limitierter Backfill holt die relevantesten
        zuerst nach — wie bei „einfach erklärt")."""
        sql = """SELECT d.id, d.title, d.beschluss, d.summary, d.outcome, d.amount_eur,
                        cs.committee, cs.session_date
                 FROM council_decisions d
                 JOIN council_sessions cs ON cs.ksinr = d.ksinr
                 WHERE d.kind = 'decision' AND d.interest IS NULL
                   AND d.title IS NOT NULL AND length(d.title) >= 8
                 ORDER BY cs.session_date DESC, d.id"""
        args: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            args = (limit,)
        return [dict(r) for r in self._conn.execute(sql, args).fetchall()]

    def save_interest(self, decision_id: int, score: int, reason: str | None) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE council_decisions SET interest = ?, interest_reason = ? WHERE id = ?",
                (max(0, min(100, int(score))), reason, decision_id),
            )

    def decisions_needing_impact(self, limit: int | None = None) -> list[dict]:
        """Beschlüsse ohne Tragweite-Score (RL-U16), neueste zuerst — mit den
        Struktur-Signalen, die der Prompt neben dem Text sehen soll."""
        sql = """SELECT d.id, d.title, d.beschluss, d.summary, d.outcome, d.kind,
                        d.amount_eur, d.vote, d.gegenstimmen, cs.committee, cs.session_date
                 FROM council_decisions d
                 JOIN council_sessions cs ON cs.ksinr = d.ksinr
                 WHERE d.kind IN ('decision', 'subvote') AND d.impact IS NULL
                   AND d.title IS NOT NULL AND length(d.title) >= 8
                 ORDER BY cs.session_date DESC, d.id"""
        args: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            args = (limit,)
        return [dict(r) for r in self._conn.execute(sql, args).fetchall()]

    #: Titel auf seinen Kern eindampfen, damit „Annahme von Zuwendungen durch
    #: den Rat - Beschluss (ungeändert beschlossen)" und dieselbe Zeile drei
    #: Sitzungen später als EIN Punkt zählen: Klammern raus, Zahlen zu #,
    #: Ergebniszusatz weg.
    _WIEDERKEHR_UNWICHTIG = re.compile(
        r"\([^)]*\)|\b(?:ungeändert|geändert)\s+beschlossen\b|"
        r"\s+-\s+(?:beschluss|bericht|antrag|vorlage)\b", re.IGNORECASE)

    def _wiederkehr(self) -> dict[str, int]:
        """Wie oft stand dieselbe Formulierung schon auf einer Tagesordnung?

        Das Signal, das jedem Modell fehlt: „Annahme von Zuwendungen durch den
        Rat" kam 101× vor, die Haushaltssatzung 3× (einmal im Jahr). Ohne den
        Zähler hält ein Sprachmodell den Zuwendungs-Punkt für eine
        Geldentscheidung — er ist aber Verwaltungsalltag (Tim, 15.08.).
        """
        if getattr(self, "_wiederkehr_cache", None) is None:
            zaehler: dict[str, int] = {}
            for (titel,) in self._conn.execute(
                    "SELECT title FROM council_agenda_items "
                    "WHERE is_public = 1 AND title IS NOT NULL"):
                schluessel = self._wiederkehr_schluessel(titel)
                if schluessel:
                    zaehler[schluessel] = zaehler.get(schluessel, 0) + 1
            self._wiederkehr_cache = zaehler
        return self._wiederkehr_cache

    @classmethod
    def _wiederkehr_schluessel(cls, titel: str | None) -> str:
        roh = cls._WIEDERKEHR_UNWICHTIG.sub(" ", (titel or "").lower())
        roh = re.sub(r"\d+", "#", roh)
        return " ".join(re.sub(r"[^a-zäöüß# ]+", " ", roh).split())

    def agenda_items_needing_impact(self, limit: int | None = None,
                                    tage_voraus: int = 21) -> list[dict]:
        """Öffentliche Tagesordnungspunkte kommender Sitzungen ohne Tragweite.

        Nur nach vorn: Die Wochen-Karte schaut voraus, und für vergangene
        Sitzungen gibt es später den Beschluss samt eigener Bewertung. Der
        Auszug kommt aus der Kurzfassung, ersatzweise aus dem Vorlagentext —
        beides liegt vor der Sitzung vor.
        """
        from datetime import date, timedelta

        heute = date.today().isoformat()
        bis = (date.today() + timedelta(days=tage_voraus)).isoformat()
        sql = """SELECT a.ksinr, a.item_number, a.title, a.vorlage_nr, a.kvonr,
                        s.summary, cs.committee, cs.session_date,
                        v.beschlussvorschlag, v.finanz_check, v.amt,
                        (SELECT COUNT(*) FROM council_beratungen b WHERE b.kvonr = a.kvonr)
                            AS stationen,
                        substr(v.raw_text, 1, 1200) AS sachverhalt
                 FROM council_agenda_items a
                 JOIN council_sessions cs ON cs.ksinr = a.ksinr
                 LEFT JOIN agenda_item_summaries s
                        ON s.ksinr = a.ksinr AND s.item_number = a.item_number
                 LEFT JOIN council_vorlagen v ON v.kvonr = a.kvonr
                 LEFT JOIN agenda_item_impact i
                        ON i.ksinr = a.ksinr AND i.item_number = a.item_number
                 WHERE a.is_public = 1 AND i.impact IS NULL
                   AND cs.session_date >= ? AND cs.session_date <= ?
                   AND a.title IS NOT NULL AND length(a.title) >= 8
                 ORDER BY cs.session_date, a.id"""
        args: tuple = (heute, bis)
        if limit is not None:
            # Großzügig holen und ERST danach kürzen: Die Formalien fliegen in
            # Python raus, und von 20 Zeilen sind gut die Hälfte „Genehmigung
            # der Tagesordnung" — ein SQL-LIMIT lieferte sonst eine halb leere
            # Tranche.
            sql += " LIMIT ?"
            args = (heute, bis, limit * 3)
        roh = [dict(r) for r in self._conn.execute(sql, args).fetchall()]
        # Formalien kosten nur Geld — dieselbe Regel wie in der Wochen-Karte.
        echte = [r for r in roh if not self._FORMALIE_RE.search(r["title"] or "")]
        zaehler = self._wiederkehr()
        for r in echte:
            r["wiederkehr"] = zaehler.get(self._wiederkehr_schluessel(r["title"]), 1)
            r["antragsteller"], _ = self._titel_zerlegen(r["title"] or "")
            reihe = [dict(b) for b in self._conn.execute(
                "SELECT datum, ergebnis FROM council_beratungen WHERE kvonr = ? ORDER BY datum",
                (r["kvonr"] or 0,))]
            heutige = next((b for b in reihe if b["datum"] == r["session_date"]), None)
            r["behandlung"] = (heutige or {}).get("ergebnis")
        return echte[:limit] if limit is not None else echte

    def save_agenda_impact(self, ksinr: int, item_number: str,
                           score: int, reason: str | None) -> None:
        from datetime import datetime, timezone

        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO agenda_item_impact "
                "(ksinr, item_number, impact, reason, created_at) VALUES (?, ?, ?, ?, ?)",
                (ksinr, item_number, max(0, min(100, int(score))), reason,
                 datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )

    def save_impact(self, decision_id: int, score: int, reason: str | None) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE council_decisions SET impact = ?, impact_reason = ? WHERE id = ?",
                (max(0, min(100, int(score))), reason, decision_id),
            )

    def fundstueck_candidates(
        self, *, mmdd: str | None = None, exclude_ids: set[int] | None = None, limit: int = 10
    ) -> list[dict]:
        """Kandidaten fürs Fundstück, bestes Interest zuerst. ``mmdd`` („07-22")
        filtert auf Jahrestage (gleicher Kalendertag, früheres Jahr)."""
        exclude = exclude_ids or set()
        sql = """SELECT d.id, d.title, d.beschluss, d.summary, d.outcome, d.vote,
                        d.amount_eur, d.interest, cs.committee, cs.session_date
                 FROM council_decisions d
                 JOIN council_sessions cs ON cs.ksinr = d.ksinr
                 WHERE d.kind = 'decision' AND d.interest IS NOT NULL
                   AND cs.session_date < date('now')"""
        args: list = []
        if mmdd:
            sql += " AND strftime('%m-%d', cs.session_date) = ?"
            args.append(mmdd)
        sql += " ORDER BY d.interest DESC, cs.session_date DESC LIMIT ?"
        args.append(limit + len(exclude))
        rows = [dict(r) for r in self._conn.execute(sql, args).fetchall()]
        return [r for r in rows if r["id"] not in exclude][:limit]

    def get_fundstueck(self, day: str) -> dict | None:
        """Fundstück eines Tages inklusive Beschluss-Metadaten."""
        row = self._conn.execute(
            """SELECT f.day, f.kicker, f.story, f.decision_id,
                      d.title, d.outcome, d.vote, cs.committee, cs.session_date
               FROM council_fundstuecke f
               JOIN council_decisions d ON d.id = f.decision_id
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE f.day = ?""",
            (day,),
        ).fetchone()
        return dict(row) if row else None

    def save_fundstueck(self, day: str, decision_id: int, kicker: str, story: str) -> None:
        with self._conn:
            self._conn.execute(
                """INSERT INTO council_fundstuecke (day, decision_id, kicker, story, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(day) DO UPDATE SET
                     decision_id = excluded.decision_id, kicker = excluded.kicker,
                     story = excluded.story, created_at = excluded.created_at""",
                (day, decision_id, kicker, story, datetime.now().isoformat(timespec="seconds")),
            )

    def fundstueck_days_present(self, days: list[str]) -> set[str]:
        if not days:
            return set()
        marks = ",".join("?" for _ in days)
        rows = self._conn.execute(
            f"SELECT day FROM council_fundstuecke WHERE day IN ({marks})", days
        ).fetchall()
        return {r["day"] for r in rows}

    def recent_fundstueck_decision_ids(self, within_days: int = 180) -> set[int]:
        """Zuletzt verwendete Beschlüsse — nicht zweimal kurz nacheinander zeigen."""
        rows = self._conn.execute(
            "SELECT decision_id FROM council_fundstuecke WHERE day >= date('now', ?)",
            (f"-{int(within_days)} days",),
        ).fetchall()
        return {r["decision_id"] for r in rows}

    def get_decision(self, decision_id: int) -> dict | None:
        row = self._conn.execute(
            """SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
               WHERE d.id = ?""",
            (decision_id,),
        ).fetchone()
        return self._decision_row(row) if row else None

    def get_subvotes(self, ksinr: int, parent_item: str) -> list[dict]:
        rows = self._conn.execute(
            """SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
               WHERE d.ksinr = ? AND d.kind = 'subvote' AND d.parent_item = ?
               ORDER BY d.position""",
            (ksinr, parent_item),
        ).fetchall()
        return [self._decision_row(r) for r in rows]

    def subvote_summaries(self, pairs: list[tuple[int, str]]) -> dict[tuple[int, str], dict]:
        """Design 23a: je Ursprungsbeschluss (ksinr, item_number) eine kompakte
        Änderungsantrags-Zusammenfassung für die Trefferliste — Anzahl,
        beteiligte Fraktionen, Ergebnisse. So kann die Karte „n Änderungsantrag ·
        Fraktion · angenommen" als Unterzeile zeigen, ohne die subvotes selbst
        als eigene Treffer zu listen."""
        wanted = {(int(k), str(i)) for k, i in pairs if i}
        if not wanted:
            return {}
        ksinrs = sorted({k for k, _ in wanted})
        ph = ",".join("?" * len(ksinrs))
        rows = self._conn.execute(
            f"SELECT ksinr, parent_item, factions, outcome FROM council_decisions "
            f"WHERE kind = 'subvote' AND ksinr IN ({ph}) ORDER BY position",
            ksinrs,
        ).fetchall()
        out: dict[tuple[int, str], dict] = {}
        for r in rows:
            key = (r["ksinr"], r["parent_item"])
            if key not in wanted:
                continue
            e = out.setdefault(key, {"count": 0, "factions": [], "outcomes": []})
            e["count"] += 1
            try:
                for f in json.loads(r["factions"] or "[]"):
                    if f and f not in e["factions"]:
                        e["factions"].append(f)
            except (ValueError, TypeError):
                pass
            if r["outcome"] and r["outcome"] not in e["outcomes"]:
                e["outcomes"].append(r["outcome"])
        return out

    def vorlage_journey(self, vorlage_nr: str) -> list[dict]:
        """All sessions where a Vorlage appears on the agenda — its path through
        the committees and the council, oldest first."""
        rows = self._conn.execute(
            """SELECT DISTINCT cs.ksinr, cs.committee, cs.session_date, ci.item_number
               FROM council_agenda_items ci
               JOIN council_sessions cs ON cs.ksinr = ci.ksinr
               WHERE ci.vorlage_nr = ?
               ORDER BY cs.session_date""",
            (vorlage_nr,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Vorlagen (full text of proposal documents, council.vorlagen) ----------

    def missing_vorlage_kvonrs(self, limit: int | None = None) -> list[int]:
        """kvonrs referenced by agenda items but not ingested yet, newest sessions
        first (so the daily capped run always covers the current business). Rows
        with status 'failed' count as missing — they get retried."""
        sql = (
            "SELECT ci.kvonr FROM council_agenda_items ci "
            "JOIN council_sessions cs ON cs.ksinr = ci.ksinr "
            "WHERE ci.kvonr IS NOT NULL AND ci.kvonr NOT IN "
            "  (SELECT kvonr FROM council_vorlagen WHERE status != 'failed') "
            "GROUP BY ci.kvonr ORDER BY MAX(cs.session_date) DESC"
        )
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r[0] for r in self._conn.execute(sql).fetchall()]

    def save_vorlage(self, row: dict) -> None:
        from council import ernte

        now = datetime.utcnow().isoformat(timespec="seconds")
        # Regex-Ernte direkt beim Speichern — so tragen neue Vorlagen die
        # Felder automatisch, das Backfill-Skript ist nur für den Bestand.
        text = row.get("raw_text") or ""
        aus = ernte.auswirkungen(text)
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_vorlagen "
                "(kvonr, vorlage_nr, title, art, document_id, document_url, "
                " raw_text, n_pages, fetched_at, status, amt, klima_check, "
                " finanz_check, beschlussvorschlag) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["kvonr"], row.get("vorlage_nr"), row.get("title"), row.get("art"),
                 row.get("document_id"), row.get("document_url"), row.get("raw_text"),
                 row.get("n_pages"), now, row.get("status", "ok"),
                 ernte.federfuehrendes_amt(text), aus["klima"], aus["finanzen"],
                 ernte.beschlussvorschlag(text)),
            )
        if row.get("vorlage_nr"):
            self.refresh_abweichung(vorlage_nr=row["vorlage_nr"])

    def mark_vorlage_failed(self, kvonr: int) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_vorlagen (kvonr, fetched_at, status) "
                "VALUES (?, ?, 'failed')", (kvonr, now),
            )

    def get_vorlage_by_nr(self, vorlage_nr: str) -> dict | None:
        """The Vorlage row for a decision's vorlage_nr. Falls back to the base
        number ("22/0348/1" → "22/0348") because protocols sometimes cite a
        revision the agenda linked under its base document."""
        nr = (vorlage_nr or "").strip()
        if not nr:
            return None
        base = "/".join(nr.split("/")[:2])
        row = self._conn.execute(
            "SELECT * FROM council_vorlagen WHERE vorlage_nr IN (?, ?) "
            "ORDER BY (vorlage_nr = ?) DESC, kvonr DESC LIMIT 1",
            (nr, base, nr),
        ).fetchone()
        return dict(row) if row else None

    def get_vorlage(self, kvonr: int) -> dict | None:
        """Die Vorlage zu ihrer Ratsinfo-Id. Gegenstück zu get_vorlage_by_nr —
        für alles, was am Vorgang selbst hängt (Design 28a/W1: verfolgen)."""
        row = self._conn.execute(
            "SELECT * FROM council_vorlagen WHERE kvonr = ?", (kvonr,)
        ).fetchone()
        return dict(row) if row else None

    def vorlage_texts_for(self, vorlage_nrs: list[str]) -> dict[str, str]:
        """Batch raw texts for Q&A context enrichment: exact vorlage_nr → text
        (only rows that actually have text). Best-effort — no base-nr fallback."""
        nrs = sorted({(n or "").strip() for n in vorlage_nrs if n and str(n).strip()})
        if not nrs:
            return {}
        ph = ",".join("?" * len(nrs))
        rows = self._conn.execute(
            f"SELECT vorlage_nr, raw_text FROM council_vorlagen "
            f"WHERE vorlage_nr IN ({ph}) AND status = 'ok'", nrs,
        ).fetchall()
        return {r["vorlage_nr"]: r["raw_text"] for r in rows if r["raw_text"]}

    # --- Anlagen (documents attached to a Vorlage, incl. fraction motions) -----

    def save_anlagen(self, kvonr: int, rows: list[dict]) -> int:
        """Store the Anlagen of one Vorlage and mark it scanned. Existing
        document_ids are kept (their text was ingested earlier); only new ones
        are inserted — so daily re-scans of recent sessions stay cheap."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        new = 0
        with self._conn:
            for r in rows:
                cur = self._conn.execute(
                    "INSERT OR IGNORE INTO council_anlagen "
                    "(document_id, kvonr, label, url, is_antrag, antragsteller, "
                    " raw_text, n_pages, fetched_at, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (r["document_id"], kvonr, r.get("label"), r.get("url"),
                     r.get("is_antrag", 0),
                     json.dumps(r.get("antragsteller") or [], ensure_ascii=False),
                     r.get("raw_text"), r.get("n_pages"), now, r.get("status", "listed")),
                )
                new += cur.rowcount
            self._conn.execute(
                "UPDATE council_vorlagen SET anlagen_scanned = 1 WHERE kvonr = ?", (kvonr,)
            )
        return new

    def kvonrs_without_anlagen_scan(self, limit: int | None = None) -> list[int]:
        """Ingested Vorlagen whose page has not been scanned for Anlagen yet,
        newest first (kvonr is monotonic enough for that)."""
        sql = ("SELECT kvonr FROM council_vorlagen WHERE anlagen_scanned = 0 "
               "ORDER BY kvonr DESC")
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r[0] for r in self._conn.execute(sql).fetchall()]

    def kvonrs_for_anlagen_rescan(self, days_back: int = 45) -> list[dict]:
        """Vorlagen on agendas of recent/upcoming sessions — re-scanned daily
        because Änderungsanträge often land on the page days after the Vorlage.
        Returns ``[{kvonr, known_ids}]`` so the fetcher skips known documents."""
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()
        rows = self._conn.execute(
            """SELECT DISTINCT ci.kvonr FROM council_agenda_items ci
               JOIN council_sessions cs ON cs.ksinr = ci.ksinr
               WHERE ci.kvonr IS NOT NULL AND cs.session_date >= ?""", (cutoff,),
        ).fetchall()
        out = []
        for r in rows:
            known = [k[0] for k in self._conn.execute(
                "SELECT document_id FROM council_anlagen WHERE kvonr = ?", (r[0],)).fetchall()]
            out.append({"kvonr": r[0], "known_ids": known})
        return out

    def anlagen_for_vorlage_nr(self, vorlage_nr: str) -> list[dict]:
        """Anlagen for a decision's Vorlage (base-nr fallback like
        ``get_vorlage_by_nr``), motions first, each with parsed Antragsteller."""
        v = self.get_vorlage_by_nr(vorlage_nr)
        if not v:
            return []
        rows = self._conn.execute(
            "SELECT document_id, label, url, is_antrag, antragsteller, status, bild "
            "FROM council_anlagen WHERE kvonr = ? ORDER BY is_antrag DESC, label",
            (v["kvonr"],),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["antragsteller"] = json.loads(d.get("antragsteller") or "[]")
            except (json.JSONDecodeError, TypeError):
                d["antragsteller"] = []
            out.append(d)
        return out

    # --- Beratungsfolge (official per-Vorlage consultation path) ---------------

    def save_beratungen(self, kvonr: int, rows: list[dict]) -> int:
        """Replace the Beratungsfolge of one Vorlage. Full replace per kvonr —
        stations get added over time and results are filled in afterwards, so a
        merge would leave stale planned rows behind."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute("DELETE FROM council_beratungen WHERE kvonr = ?", (kvonr,))
            for r in rows:
                self._conn.execute(
                    "INSERT INTO council_beratungen "
                    "(kvonr, datum, gremium, top, is_public, ergebnis, ksinr, fetched_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (kvonr, r.get("datum"), r.get("gremium") or "", r.get("top"),
                     None if r.get("is_public") is None else int(bool(r.get("is_public"))),
                     r.get("ergebnis"), r.get("ksinr"), now),
                )
        return len(rows)

    def get_beratungen(self, kvonr: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT datum, gremium, top, is_public, ergebnis, ksinr "
            "FROM council_beratungen WHERE kvonr = ? "
            "ORDER BY datum IS NULL, datum", (kvonr,),
        ).fetchall()
        return [dict(r) for r in rows]

    def geplante_beratungen_fuer(self, kvonrs: list[int]) -> list[dict]:
        """Künftige Stationen (Datum ab heute) der Vorlagen — der „Wie es
        weitergeht"-Stoff.

        Das Datum entscheidet, NICHT das Ergebnis-Feld. Die erste Fassung
        verlangte zusätzlich ein leeres ``ergebnis`` — und lieferte damit
        dauerhaft nichts: Bei künftigen Stationen trägt das Feld die geplante
        BEHANDLUNG („Vorberatung", „Kenntnisnahme"), kein Resultat. Am
        11.08.2026 nachgemessen: 22 Termine ab heute, davon 0 mit leerem
        ``ergebnis`` — der Block blieb also immer leer, auch im
        Recherche-Bericht. Die Behandlungsart kommt als ``art`` mit; sie sagt
        dem Leser, was dort passieren soll.
        """
        kvonrs = [k for k in kvonrs if k]
        if not kvonrs:
            return []
        ph = ",".join("?" * len(kvonrs))
        rows = self._conn.execute(
            f"SELECT b.kvonr, b.datum, b.gremium, b.ergebnis AS art, "
            f"       v.vorlage_nr, v.title AS vorlage_titel "
            f"FROM council_beratungen b JOIN council_vorlagen v ON v.kvonr = b.kvonr "
            f"WHERE b.kvonr IN ({ph}) AND b.datum >= date('now') ORDER BY b.datum",
            kvonrs).fetchall()
        return [dict(r) for r in rows]

    #: Wörter, die in fast jeder Frage stehen und jede Tagesordnung treffen
    #: würden. „stand" ist der Klassiker: Als Teilwort-Suche traf es
    #: „Sachstandsbericht" und „Baumstandort" und hängte einer Frage nach der
    #: Cäcilienbrücke einen EU-Verordnungs-Termin an (gemessen 11.08.).
    _AUSBLICK_STOPP = {
        "stand", "sachstand", "aktuell", "beschluss", "beschlusse", "beschluesse",
        "stadt", "oldenburg", "planung", "bericht", "vorlage", "thema", "themen",
    }

    def kommende_beratungen(self, begriffe: list[str], limit: int = 3) -> list[dict]:
        """Kommende Beratungen, deren Vorlagen-Titel zur Frage passt.

        Der Ausblick über die zitierten Vorlagen allein läuft ins Leere, und
        zwar systematisch: Auf der Tagesordnung stehen die Vorlagen, über die
        noch NICHT entschieden wurde — die Suche findet aber Beschlüsse. Am
        11.08.2026 gemessen: 22 Termine ab heute, keiner davon zu einer
        Vorlage mit vorhandenem Beschluss.

        Deshalb hier der zweite Weg: Titel-Abgleich gegen die Suchbegriffe der
        Frage. Deterministisch (kein Modell, kein Embedding), und die Menge ist
        winzig — es geht nur um die nächsten Sitzungen.
        """
        worte = {self._falte_namen(w) for w in begriffe if len(w) >= 5}
        worte -= self._AUSBLICK_STOPP
        if not worte:
            return []
        rows = self._conn.execute(
            "SELECT b.kvonr, b.datum, b.gremium, b.ergebnis AS art, "
            "       v.vorlage_nr, v.title AS vorlage_titel "
            "FROM council_beratungen b JOIN council_vorlagen v ON v.kvonr = b.kvonr "
            "WHERE b.datum >= date('now') ORDER BY b.datum").fetchall()
        bewertet: dict[int, tuple[int, dict]] = {}
        for r in rows:
            titel_worte = re.split(r"[^a-z0-9]+", self._falte_namen(r["vorlage_titel"] or ""))
            n = sum(1 for w in worte if any(tw.startswith(w) for tw in titel_worte if tw))
            if not n:
                continue
            # Je Vorlage nur die nächste Station (nach Datum sortiert gelesen).
            if r["kvonr"] not in bewertet:
                bewertet[r["kvonr"]] = (n, dict(r))
        beste = sorted(bewertet.values(), key=lambda t: (-t[0], t[1]["datum"]))
        return [d for _n, d in beste[:limit]]

    def kvonrs_without_beratungen(self, limit: int | None = None) -> list[int]:
        """Ingested Vorlagen whose Beratungsfolge has never been fetched,
        newest first."""
        sql = ("SELECT v.kvonr FROM council_vorlagen v "
               "WHERE v.kvonr NOT IN (SELECT DISTINCT kvonr FROM council_beratungen) "
               "ORDER BY v.kvonr DESC")
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r[0] for r in self._conn.execute(sql).fetchall()]

    def kvonrs_for_beratungen_rescan(self, days_back: int = 45, days_ahead: int = 120) -> list[int]:
        """Vorlagen whose Beratungsfolge is likely still moving: on an agenda of
        a recent session OR with a planned/unresolved station (future date or
        missing result) — those get re-fetched daily so nachgetragene
        Ergebnisse und neue Stationen ankommen."""
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()
        horizon = (date.today() + timedelta(days=days_ahead)).isoformat()
        rows = self._conn.execute(
            """SELECT DISTINCT ci.kvonr FROM council_agenda_items ci
               JOIN council_sessions cs ON cs.ksinr = ci.ksinr
               WHERE ci.kvonr IS NOT NULL AND cs.session_date >= ?
               UNION
               SELECT DISTINCT b.kvonr FROM council_beratungen b
               WHERE (b.ergebnis IS NULL AND b.datum <= ?) OR b.datum >= ?""",
            (cutoff, horizon, date.today().isoformat()),
        ).fetchall()
        return [r[0] for r in rows]

    # --- Personen-Stammdaten (Mandatsträger + Mitgliedschaften) ----------------

    def save_person(self, kpenr: int, name: str, fraktion_aktuell: str | None) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT INTO council_persons (kpenr, name, fraktion_aktuell, fetched_at) "
                "VALUES (?,?,?,?) ON CONFLICT(kpenr) DO UPDATE SET "
                "name=excluded.name, fraktion_aktuell=excluded.fraktion_aktuell, "
                "fetched_at=excluded.fetched_at",
                (kpenr, name, fraktion_aktuell, now),
            )

    def save_memberships(self, kpenr: int, rows: list[dict]) -> int:
        """Replace all Gremien-Mitgliedschaften of one person (full refresh)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute("DELETE FROM council_memberships WHERE kpenr = ?", (kpenr,))
            for r in rows:
                self._conn.execute(
                    "INSERT INTO council_memberships "
                    "(kpenr, kgrnr, gremium, rolle, von, bis, fetched_at) VALUES (?,?,?,?,?,?,?)",
                    (kpenr, r.get("kgrnr"), r.get("gremium") or "", r.get("rolle"),
                     r.get("von"), r.get("bis"), now),
                )
        return len(rows)
    def person_stammdaten_for_names(self, names: list[str]) -> dict | None:
        """RIS-Stammdaten für eine Person, gematcht über die Namens-Slugs der
        Anwesenheitsdaten: aktuelle Fraktion (RIS-Stand) + offizielle
        Gremien-Mitgliedschaften mit von/bis, neueste zuerst."""
        if not names:
            return None
        want = {self._person_slug(n) for n in names}
        person = None
        for r in self._conn.execute("SELECT kpenr, name, fraktion_aktuell FROM council_persons"):
            if self._person_slug(r["name"]) in want:
                person = dict(r)
                break
        if not person:
            return None
        ms = self._conn.execute(
            "SELECT kgrnr, gremium, rolle, von, bis FROM council_memberships "
            "WHERE kpenr = ? ORDER BY (bis IS NULL) DESC, COALESCE(bis,'9999') DESC, von DESC",
            (person["kpenr"],),
        ).fetchall()
        person["memberships"] = [dict(r) for r in ms]
        return person

    def stammdaten_stats(self) -> dict:
        one = lambda sql: self._conn.execute(sql).fetchone()[0]  # noqa: E731
        return {
            "personen": one("SELECT COUNT(*) FROM council_persons"),
            "mitgliedschaften": one("SELECT COUNT(*) FROM council_memberships"),
            "vorlagen_mit_beratungen": one("SELECT COUNT(DISTINCT kvonr) FROM council_beratungen"),
            "beratungen": one("SELECT COUNT(*) FROM council_beratungen"),
            "geplante_beratungen": one(
                "SELECT COUNT(*) FROM council_beratungen WHERE datum > date('now')"),
        }

    # --- Quiz (generierte Fragen je Gebiet) -----------------------------------

    def save_quiz_questions(self, rows: list[dict]) -> int:
        """Neue Quizfragen speichern; Duplikate (gleicher content_hash) werden
        übersprungen. Gibt die Zahl neu eingefügter Fragen zurück."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        new = 0
        with self._conn:
            for r in rows:
                cur = self._conn.execute(
                    "INSERT OR IGNORE INTO council_quiz_questions "
                    "(area_type, area_key, category, difficulty, question, options, "
                    " correct_index, explanation, source_type, source_ref, content_hash, "
                    " status, qtype, answer_value, answer_unit, range_min, range_max, "
                    " detail, hint, topic, chart, lat, lon, place_label, geojson, image_url, image_author, image_license, "
                    " image_license_url, image_source_url, generated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["area_type"], r["area_key"], r["category"], r.get("difficulty", "mittel"),
                     r["question"], json.dumps(r.get("options", []), ensure_ascii=False),
                     int(r.get("correct_index", 0)), r.get("explanation"),
                     r.get("source_type"), r.get("source_ref"), r.get("content_hash"),
                     r.get("status", "active"), r.get("qtype", "mc"),
                     r.get("answer_value"), r.get("answer_unit"),
                     r.get("range_min"), r.get("range_max"),
                     r.get("detail"), r.get("hint"), r.get("topic"), r.get("chart"),
                     r.get("lat"), r.get("lon"), r.get("place_label"), r.get("geojson"),
                     r.get("image_url"), r.get("image_author"), r.get("image_license"),
                     r.get("image_license_url"), r.get("image_source_url"), now),
                )
                new += cur.rowcount
        return new

    @staticmethod
    def _quiz_row(r: sqlite3.Row, *, with_answer: bool) -> dict:
        try:
            options = json.loads(r["options"])
        except (json.JSONDecodeError, TypeError):
            options = []
        keys = r.keys()
        qtype = (r["qtype"] if "qtype" in keys else None) or "mc"
        out = {
            "id": r["id"], "area_type": r["area_type"], "area_key": r["area_key"],
            "category": r["category"], "difficulty": r["difficulty"],
            "question": r["question"], "options": options, "qtype": qtype,
            "source_type": r["source_type"], "source_ref": r["source_ref"],
        }
        # Tipp gehört zur Frage (vor dem Auflösen anzeigbar), nicht zur Lösung.
        if "hint" in keys and r["hint"]:
            out["hint"] = r["hint"]
        if qtype == "estimate":
            # Slider-Grenzen + Einheit gehören zur Frage (nicht die Lösung).
            out["unit"] = r["answer_unit"]
            out["range_min"] = r["range_min"]
            out["range_max"] = r["range_max"]
        if with_answer:
            out["correct_index"] = r["correct_index"]
            out["explanation"] = r["explanation"]
            # Such-Stichwort für „Beschlüsse dazu" (verwandte Ratsbeschlüsse).
            if "topic" in keys and r["topic"]:
                out["topic"] = r["topic"]
            # Diagramm der Auflösung (z. B. Haushalts-Balken) — JSON-Spalte.
            if "chart" in keys and r["chart"]:
                try:
                    out["chart"] = json.loads(r["chart"])
                except (json.JSONDecodeError, TypeError):
                    pass
            if qtype == "estimate":
                out["answer_value"] = r["answer_value"]
            # „Mehr dazu" — Detailtext, Locator-Karte und Bild gehören zur
            # Auflösung (nicht in die Runde). Nur wenn die Spalten existieren.
            if "detail" in keys:
                out["detail"] = r["detail"]
                if r["lat"] is not None and r["lon"] is not None:
                    from council import geo  # lokal: store bleibt ohne Geo-Pflicht importierbar
                    m = {"lat": r["lat"], "lon": r["lon"], "label": r["place_label"]}
                    gj = r["geojson"] if "geojson" in keys else None
                    if gj:
                        try:
                            m["geojson"] = json.loads(gj)
                        except (json.JSONDecodeError, TypeError):
                            pass
                    # Punkt-Pin, der nur „Oldenburg" als Ganzes markiert, trägt
                    # nichts — unterdrücken (heilt auch schon gespeicherte Fragen).
                    if "geojson" in m or not geo.is_city_generic(m["label"]):
                        out["map"] = m
                if r["image_url"]:
                    out["image"] = {"url": r["image_url"], "author": r["image_author"],
                                    "license": r["image_license"], "license_url": r["image_license_url"],
                                    "source_url": r["image_source_url"]}
        return out

    def get_quiz_question(self, question_id: int, *, with_answer: bool = True) -> dict | None:
        """Eine Frage (per id) — inkl. Lösung, für die Auswertung."""
        r = self._conn.execute(
            "SELECT * FROM council_quiz_questions WHERE id = ? AND status = 'active'",
            (question_id,),
        ).fetchone()
        return self._quiz_row(r, with_answer=with_answer) if r else None

    def pick_quiz_questions(self, areas: list[tuple[str, str]], categories: list[str] | None,
                            exclude_ids: list[int] | None, limit: int) -> list[dict]:
        """Fragen für eine Runde: aus den gewählten Gebieten (area_type, area_key),
        optional auf Kategorien gefiltert, ohne die schon beantworteten
        (exclude_ids) — aufgefüllt mit beantworteten, falls sonst zu wenige.
        OHNE Lösung (die kommt beim Auswerten). Zufällige Reihenfolge."""
        if not areas:
            return []
        area_clause = " OR ".join("(area_type = ? AND area_key = ?)" for _ in areas)
        params: list = [x for pair in areas for x in pair]
        sql = f"SELECT * FROM council_quiz_questions WHERE status = 'active' AND ({area_clause})"
        if categories:
            sql += " AND category IN (%s)" % ",".join("?" * len(categories))
            params += categories
        rows = self._conn.execute(sql, params).fetchall()
        seen = set(exclude_ids or [])
        fresh = [r for r in rows if r["id"] not in seen]
        used = [r for r in rows if r["id"] in seen]
        import random  # deterministische Reihenfolge ist hier unerwünscht
        random.shuffle(fresh)
        random.shuffle(used)
        picked = (fresh + used)[:limit]
        return [self._quiz_row(r, with_answer=False) for r in picked]

    def pick_quiz_questions_by_ids(self, ids: list[int], limit: int) -> list[dict]:
        """Aktive Fragen (OHNE Lösung) zu einer Id-Liste, gemischt und gedeckelt —
        für den „Meine Fehler"-Wiederholmodus. Retirte Fragen fallen raus."""
        if not ids:
            return []
        ph = ",".join("?" * len(ids))
        rows = list(self._conn.execute(
            f"SELECT * FROM council_quiz_questions WHERE id IN ({ph}) AND status = 'active'",
            ids).fetchall())
        import random
        random.shuffle(rows)
        return [self._quiz_row(r, with_answer=False) for r in rows[:limit]]

    def daily_quiz_questions(self, day: str, n: int = 5) -> list[dict]:
        """Die Tages-Challenge: n aus dem Datum deterministisch geseedete Fragen,
        OHNE Lösung — derselbe Satz für alle an einem Tag. Über alle Gebiete."""
        ids = [r[0] for r in self._conn.execute(
            "SELECT id FROM council_quiz_questions WHERE status = 'active' ORDER BY id"
        ).fetchall()]
        if not ids:
            return []
        import random
        pick = random.Random(day).sample(ids, min(n, len(ids)))
        ph = ",".join("?" * len(pick))
        by_id = {r["id"]: r for r in self._conn.execute(
            f"SELECT * FROM council_quiz_questions WHERE id IN ({ph})", pick).fetchall()}
        return [self._quiz_row(by_id[i], with_answer=False) for i in pick if i in by_id]

    def quiz_area_counts(self) -> dict:
        """Aktive Fragen je Gebiet: {(area_type, area_key): n}."""
        rows = self._conn.execute(
            "SELECT area_type, area_key, COUNT(*) n FROM council_quiz_questions "
            "WHERE status = 'active' GROUP BY area_type, area_key"
        ).fetchall()
        return {(r["area_type"], r["area_key"]): r["n"] for r in rows}

    def quiz_counts_below(self, target: int) -> dict:
        """Aktive Fragenzahl je Gebiet (für idempotenten Backfill: nur Gebiete
        unter dem Ziel neu befüllen)."""
        return {k: v for k, v in self.quiz_area_counts().items() if v < target}

    def retire_quiz_question(self, question_id: int) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE council_quiz_questions SET status = 'retired' WHERE id = ?", (question_id,))

    def quiz_questions_by_ids(self, ids: list[int]) -> list[dict]:
        """Aktive Fragen (mit Lösung) zu einer Id-Liste — für die Admin-Sichtung.
        Bereits ausgemusterte Fragen fallen raus, damit sie nach dem Ausmustern
        aus der Bewertungs-Liste verschwinden (ihre Alt-Bewertungen bleiben in
        nwz.sqlite, laufen aber ins Leere)."""
        if not ids:
            return []
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT * FROM council_quiz_questions WHERE id IN ({ph}) AND status = 'active'",
            ids).fetchall()
        return [self._quiz_row(r, with_answer=True) for r in rows]

    def quiz_stats_total(self) -> dict:
        one = lambda sql: self._conn.execute(sql).fetchone()[0]  # noqa: E731
        return {
            "fragen": one("SELECT COUNT(*) FROM council_quiz_questions WHERE status='active'"),
            "gebiete": one("SELECT COUNT(DISTINCT area_type||area_key) FROM council_quiz_questions WHERE status='active'"),
        }

    # Themen ohne Entität dahinter (kuratierte Spezial-Gebiete) → Anzeigename.
    _THEMA_LABELS = {"haushalt": "Stadt-Haushalt"}

    def quiz_themes(self) -> list[dict]:
        """Themen-Gebiete mit aktiven Fragen: {area_key(slug), label(name),
        lat, lon}. Der Anzeigename kommt aus council_entities (Fallback:
        kuratierte Labels, dann slug); lat/lon aus der Entity-Geo (RL-U13:
        der Router ordnet darüber den Stadtteil zu — Themen ohne Geo gelten
        als stadtweit)."""
        rows = self._conn.execute(
            "SELECT DISTINCT q.area_key, e.name, m.lat, m.lon "
            "FROM council_quiz_questions q "
            "LEFT JOIN council_entities e ON e.slug = q.area_key "
            "LEFT JOIN council_entity_meta m ON m.slug = q.area_key "
            "WHERE q.area_type = 'thema' AND q.status = 'active'").fetchall()
        return [{"area_key": r["area_key"],
                 "label": r["name"] or self._THEMA_LABELS.get(r["area_key"], r["area_key"]),
                 "lat": r["lat"], "lon": r["lon"]}
                for r in rows]

    # --- Stadt-Haushalt (council.haushalt) -----------------------------------

    def save_haushalt(self, year: int, rows: list[dict], source_url: str) -> int:
        """Ergebnishaushalt eines Jahres speichern — ersetzt den bisherigen
        Stand des Jahres komplett (Re-Ingest idempotent)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute("DELETE FROM council_haushalt WHERE year = ?", (year,))
            for r in rows:
                self._conn.execute(
                    "INSERT INTO council_haushalt (year, bereich, ertraege, aufwendungen, "
                    " ergebnis, is_summe, source_url, fetched_at) VALUES (?,?,?,?,?,?,?,?)",
                    (year, r["bereich"], r.get("ertraege"), r.get("aufwendungen"),
                     r.get("ergebnis"), int(r.get("is_summe", 0)), source_url, now))
        return len(rows)

    def get_haushalt(self, year: int) -> list[dict]:
        """Ergebnishaushalt eines Jahres (Teilhaushalte + Summenzeile)."""
        rows = self._conn.execute(
            "SELECT bereich, ertraege, aufwendungen, ergebnis, is_summe, source_url "
            "FROM council_haushalt WHERE year = ? ORDER BY is_summe, aufwendungen DESC",
            (year,)).fetchall()
        return [dict(r) for r in rows]

    def haushalt_years(self) -> list[int]:
        """Alle eingelesenen Haushaltsjahre (aufsteigend) — für Trend-Fragen."""
        return [r[0] for r in self._conn.execute(
            "SELECT DISTINCT year FROM council_haushalt ORDER BY year")]

    def refresh_quiz_payloads(self, rows: list[dict]) -> int:
        """Deterministisch erzeugte Fragen (gleicher content_hash — die Haushalts-
        Fragen nutzen STABILE Schlüssel statt des Fragetexts) auffrischen: Frage,
        Tipp, Optionen, Chart, Erklärung, Detail und Schätzwerte aktualisieren —
        z. B. wenn neue Haushaltsjahre die Trendlinie verlängern oder Texte
        nachgebessert werden. Neue Fragen legt weiterhin save_quiz_questions an
        (INSERT OR IGNORE)."""
        n = 0
        with self._conn:
            for r in rows:
                if not r.get("content_hash"):
                    continue
                cur = self._conn.execute(
                    "UPDATE council_quiz_questions SET question = ?, hint = ?, "
                    "options = ?, correct_index = ?, chart = ?, explanation = ?, "
                    "detail = ?, answer_value = ?, range_min = ?, range_max = ? "
                    "WHERE content_hash = ? AND status = 'active'",
                    (r.get("question"), r.get("hint"),
                     json.dumps(r.get("options") or [], ensure_ascii=False),
                     r.get("correct_index"), r.get("chart"), r.get("explanation"),
                     r.get("detail"), r.get("answer_value"), r.get("range_min"),
                     r.get("range_max"), r["content_hash"]))
                n += cur.rowcount
        return n

    def top_amount_since(self, date_from: str) -> dict | None:
        """Größter im Beschlusstext erkannter Betrag seit ``date_from`` — die
        „Zahl der Woche" fürs Heute-Briefing (RL-905)."""
        row = self._conn.execute(
            """SELECT d.id, d.title, d.amount_eur, s.session_date
               FROM council_decisions d
               JOIN council_sessions s ON s.ksinr = d.ksinr
               WHERE s.session_date >= ? AND d.amount_eur IS NOT NULL
                 AND d.kind = 'decision'
               ORDER BY d.amount_eur DESC LIMIT 1""",
            (date_from,),
        ).fetchone()
        return dict(row) if row else None

    def count_decisions_since(self, date_from: str) -> int:
        """Anzahl Beschlüsse seit ``date_from`` (Fallback der Zahl der Woche)."""
        return int(self._conn.execute(
            """SELECT COUNT(*) FROM council_decisions d
               JOIN council_sessions s ON s.ksinr = d.ksinr
               WHERE s.session_date >= ?""",
            (date_from,),
        ).fetchone()[0])

    def antrag_stats(self) -> dict:
        """Erfolgsquoten der Fraktions-Anträge: Antrag-Anlage → Vorlage → deren
        Beschlüsse. Gezählt wird je Antragsteller-Partei der KLARE Endstand der
        Vorlage — bevorzugt der Beschluss des Rats selbst, sonst der letzte
        Ausschuss-Beschluss mit angenommen/abgelehnt. Mehrparteien-Anträge zählen
        für jede Partei. Methodik entspricht bewusst politik-vor-ort (Rat zuerst,
        nur klare Outcomes), aber über unsere volle Historie."""
        from council.parties import CANONICAL_ORDER, order_key

        antraege = self._conn.execute(
            """SELECT a.document_id, a.antragsteller, v.vorlage_nr
               FROM council_anlagen a JOIN council_vorlagen v ON v.kvonr = a.kvonr
               WHERE a.is_antrag = 1 AND a.antragsteller != '[]'
                 AND v.vorlage_nr IS NOT NULL AND v.vorlage_nr != ''""",
        ).fetchall()

        per_party: dict[str, dict] = {}
        n_mit_beschluss = 0
        for row in antraege:
            base = "/".join(row["vorlage_nr"].split("/")[:2])
            # Trägt eine Vorlage mehrere Antrag-Anlagen (Änderungsanträge mehrerer
            # Parteien), zählt der Vorlagen-Endstand für jeden dieser Anträge.
            decision = self._conn.execute(
                """SELECT d.outcome, cs.committee FROM council_decisions d
                   JOIN council_sessions cs ON cs.ksinr = d.ksinr
                   WHERE d.kind = 'decision' AND d.outcome IN ('angenommen','abgelehnt')
                     AND (d.vorlage_nr = ? OR d.vorlage_nr LIKE ?)
                   ORDER BY (cs.committee LIKE 'Rat%') DESC, cs.session_date DESC
                   LIMIT 1""", (base, base + "/%"),
            ).fetchone()
            if not decision:
                continue
            n_mit_beschluss += 1
            try:
                parties = json.loads(row["antragsteller"] or "[]")
            except (json.JSONDecodeError, TypeError):
                parties = []
            for p in parties:
                # Nur anerkannte Parteien zählen — in älteren Anlagen-Zeilen
                # können inzwischen entfernte Labels (z. B. WFO/LKR) stehen.
                if p not in CANONICAL_ORDER:
                    continue
                s = per_party.setdefault(p, {"party": p, "n": 0, "angenommen": 0, "abgelehnt": 0})
                s["n"] += 1
                s[decision["outcome"]] += 1

        stats = sorted(per_party.values(), key=lambda s: (-s["n"], order_key(s["party"])))
        return {
            "parties": stats,
            "n_antraege": len(antraege),
            "n_mit_beschluss": n_mit_beschluss,
        }

    def get_unclassified_decisions(self, limit: int | None = None) -> list[dict]:
        """Decisions without a policy field yet — for the classification backfill/cron.
        Returns id + the fields the classifier needs (title, beschluss, committee)."""
        sql = ("SELECT d.id, d.title, d.beschluss, cs.committee "
               "FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr "
               "WHERE d.policy_field IS NULL ORDER BY d.id")
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [dict(r) for r in self._conn.execute(sql).fetchall()]

    def set_classifications(self, results: dict) -> int:
        """Bulk-write classification results: id -> {field, tags, summary}."""
        rows = [
            (r["field"], json.dumps(r.get("tags") or [], ensure_ascii=False), r.get("summary"), did)
            for did, r in results.items()
        ]
        with self._conn:
            self._conn.executemany(
                "UPDATE council_decisions SET policy_field = ?, policy_tags = ?, summary = ? WHERE id = ?",
                rows,
            )
        return len(rows)

    def reset_classifications(self) -> None:
        """Clear all topic classifications — for a full re-classify (e.g. taxonomy change)."""
        with self._conn:
            self._conn.execute(
                "UPDATE council_decisions SET policy_field = NULL, policy_tags = NULL, summary = NULL"
            )

    def rebuild_fts(self) -> int:
        """(Re)build the full-text index from all main decisions (title + beschluss +
        summary + the first chunk of the Vorlage text + the first chunk of attached
        motion texts, so Sachverhalt AND original Antrag wording are findable). The
        joins are grouped because distinct kvonrs can in theory share a vorlage_nr —
        duplicate rowids would break the FTS insert."""
        with self._conn:
            self._conn.execute("DELETE FROM council_decisions_fts")
            self._conn.execute(
                "INSERT INTO council_decisions_fts(rowid, content) "
                "SELECT d.id, REPLACE(COALESCE(d.title,'') || ' ' || COALESCE(d.beschluss,'') || ' ' "
                "|| COALESCE(d.summary,'') || ' ' || COALESCE(sv.stext,'') || ' ' "
                "|| COALESCE(v.vtext,'') || ' ' || COALESCE(an.atext,''), "
                "'ß', 'ss') "  # unicode61 folds ä/ö/ü but not ß
                "FROM council_decisions d "
                "LEFT JOIN (SELECT vorlage_nr, substr(MAX(raw_text), 1, 8000) AS vtext "
                "           FROM council_vorlagen WHERE status = 'ok' GROUP BY vorlage_nr) v "
                "  ON v.vorlage_nr = d.vorlage_nr "
                "LEFT JOIN (SELECT cv.vorlage_nr, substr(GROUP_CONCAT(a.raw_text, ' '), 1, 4000) AS atext "
                "           FROM council_anlagen a JOIN council_vorlagen cv ON cv.kvonr = a.kvonr "
                "           WHERE a.is_antrag = 1 AND a.status = 'ok' GROUP BY cv.vorlage_nr) an "
                "  ON an.vorlage_nr = d.vorlage_nr "
                # Teilabstimmungen (Änderungsanträge) haben keine eigene FTS-Zeile —
                # ihre Titel zählen zum Haupt-TOP, damit „Änderungsantrag der X zu Y"
                # den zitierfähigen Hauptbeschluss findet (Design 23a: subvote-Inhalt
                # steht im title, beschluss ist immer NULL).
                "LEFT JOIN (SELECT ksinr, parent_item, substr(GROUP_CONCAT(title, ' '), 1, 2000) AS stext "
                "           FROM council_decisions WHERE kind = 'subvote' AND parent_item IS NOT NULL "
                "           GROUP BY ksinr, parent_item) sv "
                "  ON sv.ksinr = d.ksinr AND sv.parent_item = d.item_number "
                "WHERE d.kind = 'decision'"
            )
        return self._conn.execute("SELECT COUNT(*) FROM council_decisions_fts").fetchone()[0]

    def search_decisions_fts(self, query: str, limit: int = 40) -> list[tuple]:
        """BM25 keyword search → ``[(decision_id, score, snippet)]`` (larger = better).
        Terms are OR-combined for recall; returns ``[]`` on an empty or invalid query.

        Das FTS5-``snippet()`` liefert die FUNDSTELLE im indexierten Text — bei
        Treffern tief im Vorlagen-Volltext ist das der Kontext, den der Reranker
        sehen muss (der Textanfang verrät dort nichts über den Match)."""
        terms = [t for t in re.findall(r"[0-9a-zäöü]+", query.lower().replace("ß", "ss")) if len(t) >= 3][:12]
        if not terms:
            return []
        match = " OR ".join(terms)
        try:
            rows = self._conn.execute(
                "SELECT rowid, rank, snippet(council_decisions_fts, 0, '', '', ' … ', 16) "
                "FROM council_decisions_fts WHERE council_decisions_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (match, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        # FTS5 rank is negative (more negative = better); flip so larger = better.
        return [(r[0], -float(r[1]), r[2] or "") for r in rows]

    def decisions_for_entities(self) -> list[dict]:
        """Main decisions (id, title, beschluss) for the entity-extraction backfill."""
        return [dict(r) for r in self._conn.execute(
            "SELECT id, title, beschluss FROM council_decisions WHERE kind = 'decision'")]

    def save_entities(self, entities: list[tuple], links: list[tuple]) -> int:
        """Full rebuild of the entity tables. ``entities`` = (slug, name, kind, n);
        ``links`` = (slug, decision_id)."""
        with self._conn:
            self._conn.execute("DELETE FROM council_entity_links")
            self._conn.execute("DELETE FROM council_entities")
            self._conn.executemany(
                "INSERT INTO council_entities(slug, name, kind, n) VALUES (?,?,?,?)", entities)
            id_by_slug = {r["slug"]: r["id"] for r in self._conn.execute("SELECT id, slug FROM council_entities")}
            rows = [(id_by_slug[s], d) for s, d in links if s in id_by_slug]
            self._conn.executemany(
                "INSERT OR IGNORE INTO council_entity_links(entity_id, decision_id) VALUES (?,?)", rows)
        return len(entities)

    def scanned_entity_decision_ids(self) -> set[int]:
        """Decision ids already passed through entity NER — lets extract_entities.py
        scan only new decisions on incremental runs."""
        return {r[0] for r in self._conn.execute("SELECT decision_id FROM council_entity_scanned")}

    def add_entity_observations(self, obs: list[tuple], scanned_ids: list[int]) -> None:
        """Append raw (decision_id, slug, name, kind) entity observations and mark the
        given decisions scanned. Idempotent per (decision, slug) / decision."""
        with self._conn:
            self._conn.executemany(
                "INSERT OR IGNORE INTO council_entity_obs(decision_id, slug, name, kind) "
                "VALUES (?,?,?,?)", obs)
            self._conn.executemany(
                "INSERT OR IGNORE INTO council_entity_scanned(decision_id) VALUES (?)",
                [(i,) for i in scanned_ids])

    def rebuild_entities_from_obs(self, min_n: int = 2) -> tuple[int, int]:
        """Re-derive council_entities + links from the raw observations, keeping slugs
        seen in >= min_n distinct decisions (most frequent name/kind spelling wins).
        Cheap — no LLM — so it runs after every incremental NER pass.

        Confirmed duplicates (council_entity_aliases) are folded into their canonical
        slug here, so one subject yields one Themen page with all its decisions and
        money. Name/kind are taken from the canonical slug's own observations — an
        alias must not outvote the canonical spelling. Since the observations stay
        untouched, removing an alias row and re-deriving undoes the merge.
        """
        from collections import Counter, defaultdict
        alias_map = self.entity_aliases()
        names: dict = defaultdict(Counter)
        kinds: dict = defaultdict(Counter)
        dec_ids: dict = defaultdict(set)
        for did, slug, name, kind in self._conn.execute(
                "SELECT decision_id, slug, name, kind FROM council_entity_obs"):
            canon = alias_map.get(slug, slug)
            dec_ids[canon].add(did)
            if canon != slug:
                continue          # Anzeigename kommt vom Kanon, nicht vom Alias
            names[canon][name] += 1
            if kind:
                kinds[canon][kind] += 1
        # Sonderfall: der Kanon selbst wurde nie beobachtet (nur seine Aliasse) —
        # dann darf die Gruppe nicht namenlos verschwinden.
        for canon in list(dec_ids):
            if names[canon]:
                continue
            for slug, target in alias_map.items():
                if target == canon:
                    for name, kind in self._conn.execute(
                            "SELECT name, kind FROM council_entity_obs WHERE slug = ?", (slug,)):
                        names[canon][name] += 1
                        if kind:
                            kinds[canon][kind] += 1
        ent_rows, link_rows = [], []
        for slug, ids in dec_ids.items():
            if len(ids) < min_n:
                continue
            kind = kinds[slug].most_common(1)[0][0] if kinds[slug] else None
            ent_rows.append((slug, names[slug].most_common(1)[0][0], kind, len(ids)))
            link_rows.extend((slug, did) for did in ids)
        self.save_entities(ent_rows, link_rows)
        return len(ent_rows), len(link_rows)

    def reset_entity_obs(self) -> None:
        """Clear raw observations + scan marks for a full re-scan (extract_entities --full)."""
        with self._conn:
            self._conn.execute("DELETE FROM council_entity_obs")
            self._conn.execute("DELETE FROM council_entity_scanned")

    def list_entities(self, limit: int = 300, kind: str = "") -> list[dict]:
        """Entities for the directory, most-referenced first — angereichert um
        Aktualität (letzte Sitzung, Beschlüsse der letzten 12 Monate), damit das
        Frontend nach „gerade aktiv" statt nur nach Lebenszeit-Summe (seit 2018)
        priorisieren kann."""
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=365)).isoformat()
        sql = (
            "SELECT e.slug, e.name, e.kind, e.n, MAX(cs.session_date) AS last_date, "
            "SUM(CASE WHEN cs.session_date >= ? THEN 1 ELSE 0 END) AS n_recent "
            "FROM council_entities e "
            "LEFT JOIN council_entity_links l ON l.entity_id = e.id "
            "LEFT JOIN council_decisions d ON d.id = l.decision_id "
            "LEFT JOIN council_sessions cs ON cs.ksinr = d.ksinr "
        )
        params: list = [cutoff]
        if kind:
            sql += "WHERE e.kind = ? "
            params.append(kind)
        sql += "GROUP BY e.id ORDER BY e.n DESC, e.name LIMIT ?"
        params.append(limit)
        rows = [dict(r) for r in self._conn.execute(sql, params)]
        for r in rows:
            r["n_recent"] = r["n_recent"] or 0
        return rows

    def trending_tags(self, days_back: int = 180, limit: int = 12) -> list[dict]:
        """Häufigste policy_tags der letzten Monate — Futter für anklickbare
        Themen-Vorschläge („was gerade den Rat beschäftigt")."""
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()
        rows = self._conn.execute(
            """SELECT je.value AS tag, COUNT(*) AS n
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr, json_each(d.policy_tags) je
               WHERE d.kind = 'decision' AND d.policy_tags IS NOT NULL
                 AND cs.session_date >= ?
               GROUP BY je.value ORDER BY n DESC, tag LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
        return [{"tag": r["tag"], "n": r["n"]} for r in rows]

    def most_interesting_recent(self, days_back: int = 7) -> dict | None:
        """RL-U15 (13a-A): der interessanteste Beschluss der letzten Tage —
        füllt auf „Heute" den Treffer-Leerzustand („Diese Woche im Rat")."""
        row = self._conn.execute(
            """SELECT d.id, d.title, d.outcome, d.interest_reason, cs.committee, cs.session_date
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE d.kind = 'decision' AND d.interest IS NOT NULL
                 AND cs.session_date >= date('now', ?)
               ORDER BY d.interest DESC, cs.session_date DESC LIMIT 1""",
            (f"-{int(days_back)} days",),
        ).fetchone()
        return dict(row) if row else None

    def suggested_entity_topics(self, days_back: int = 365, limit: int = 12) -> list[dict]:
        """Konkrete Orte/Projekte mit jüngster Ratsaktivität — Futter für die
        Themen-Vorschläge. Ersetzt die reine Schlagwort-Häufigkeit, die
        Verwaltungsvokabeln belohnte („Bericht", „Annahme"): Menschen
        interessieren sich für ein Bauprojekt oder ihre Straße, nicht für
        Beschluss-Formalien. Sortiert nach jüngster Aktivität, bei Gleichstand
        gewinnt der interessantere Stoff (Interest-Score, neutral 50)."""
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()
        rows = self._conn.execute(
            """SELECT e.slug, e.name, e.kind, m.description,
                      COUNT(DISTINCT el.decision_id) AS n_recent,
                      AVG(COALESCE(d.interest, 50)) AS avg_interest
               FROM council_entities e
               JOIN council_entity_links el ON el.entity_id = e.id
               JOIN council_decisions d ON d.id = el.decision_id
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               LEFT JOIN council_entity_meta m ON m.slug = e.slug
               WHERE e.kind IN ('ort', 'projekt') AND cs.session_date >= ?
               GROUP BY e.id
               HAVING n_recent >= 2
               ORDER BY n_recent DESC, avg_interest DESC, e.name
               LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_entities_geo(self) -> list[dict]:
        """Geocoded entities (points) for the city-wide map — slug, name, kind, n, lat, lon."""
        return [dict(r) for r in self._conn.execute(
            "SELECT e.slug, e.name, e.kind, e.n, m.lat, m.lon "
            "FROM council_entities e JOIN council_entity_meta m ON m.slug = e.slug "
            "WHERE m.lat IS NOT NULL AND m.lon IS NOT NULL ORDER BY e.n DESC")]

    def entities_for_decision(self, decision_id: int) -> list[dict]:
        """Entities mentioned in a decision (shown on its detail page)."""
        return [dict(r) for r in self._conn.execute(
            "SELECT e.slug, e.name, e.kind FROM council_entity_links el "
            "JOIN council_entities e ON e.id = el.entity_id WHERE el.decision_id = ? ORDER BY e.n DESC",
            (decision_id,))]

    def entity_detail(self, slug: str) -> dict | None:
        """An entity with all its decisions (newest first) and aggregates.

        A slug merged away as a duplicate resolves to its canonical entity, so links
        and bookmarks from before the merge keep working instead of 404-ing. The
        result carries ``merged_from`` in that case, for a redirect in the UI.
        """
        from collections import Counter

        ent = self._conn.execute(
            "SELECT id, slug, name, kind, n FROM council_entities WHERE slug = ?", (slug,)).fetchone()
        merged_from = None
        if not ent:
            canonical = self.entity_aliases().get(slug)
            if canonical:
                ent = self._conn.execute(
                    "SELECT id, slug, name, kind, n FROM council_entities WHERE slug = ?",
                    (canonical,)).fetchone()
                merged_from = slug
        if not ent:
            return None
        rows = self._conn.execute(
            """SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
               FROM council_entity_links el JOIN council_decisions d ON d.id = el.decision_id
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
               WHERE el.entity_id = ? ORDER BY cs.session_date DESC""", (ent["id"],)).fetchall()
        decisions = [self._decision_row(r) for r in rows]
        # Recognised € deduped: the same matter decided in Ausschuss + Rat (shared
        # Vorlage / title) counts ONCE, and accounting/treasury docs (balance-sheet
        # totals, not spending) are excluded — so the entity total isn't double-counted
        # or inflated (e.g. Alexanderstraße 600k once, not 1,2 Mio).
        _seen: set = set()
        money = 0.0
        for d in sorted((x for x in decisions if x.get("amount_eur")), key=lambda x: -x["amount_eur"]):
            if any(k in (d.get("title") or "").lower() for k in self._NON_SPENDING_TITLES):
                continue
            keys = _dedup_keys(d.get("title"), d.get("vorlage_nr"), d["id"])
            if any(k in _seen for k in keys):
                continue
            _seen.update(keys)
            money += d["amount_eur"]
        parties = sorted({p for d in decisions for p in d.get("parties", [])}, key=order_key)
        fieldc = Counter(d["policy_field"] for d in decisions if d.get("policy_field"))
        meta = self._conn.execute(
            "SELECT description, lat, lon, geojson FROM council_entity_meta WHERE slug = ?", (slug,)).fetchone()
        geo = None
        if meta and meta["lat"] is not None and meta["lon"] is not None:
            geo = {"lat": meta["lat"], "lon": meta["lon"],
                   "geojson": json.loads(meta["geojson"]) if meta["geojson"] else None}
        return {
            "entity": {"slug": ent["slug"], "name": ent["name"], "kind": ent["kind"], "n": ent["n"]},
            "description": meta["description"] if meta else None,
            "geo": geo,
            "decisions": decisions,
            "money": round(money) if money else 0,
            "parties": parties,
            "fields": [{"field": f, "n": c} for f, c in fieldc.most_common()],
            "merged_from": merged_from,
        }

    def entity_titles(self, limit: int = 3) -> dict[int, list[str]]:
        """A few decision titles per entity — grounding context for the duplicate check."""
        from collections import defaultdict
        out: dict[int, list[str]] = defaultdict(list)
        for r in self._conn.execute(
                """SELECT el.entity_id AS eid, d.title FROM council_entity_links el
                   JOIN council_decisions d ON d.id = el.decision_id
                   WHERE d.title IS NOT NULL AND d.title <> ''"""):
            if len(out[r["eid"]]) < limit:
                out[r["eid"]].append(r["title"])
        return dict(out)

    def entities_without_description(self) -> list[dict]:
        """Entities still lacking an LLM description, most-decisions first — for the
        describe backfill. Description/geo live in council_entity_meta (keyed by slug)
        so they survive the full rebuild of council_entities."""
        rows = self._conn.execute(
            "SELECT e.slug, e.name, e.kind, e.n FROM council_entities e "
            "LEFT JOIN council_entity_meta m ON m.slug = e.slug "
            "WHERE m.description IS NULL OR m.description = '' ORDER BY e.n DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def entity_decisions_brief(self, slug: str, limit: int = 40) -> list[dict]:
        """Lightweight decision list (title/summary/field/date) of an entity — the
        grounding context for the description prompt."""
        rows = self._conn.execute(
            """SELECT d.title, d.summary, d.policy_field, cs.session_date
               FROM council_entities e
               JOIN council_entity_links el ON el.entity_id = e.id
               JOIN council_decisions d ON d.id = el.decision_id
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE e.slug = ? ORDER BY cs.session_date DESC LIMIT ?""", (slug, limit)).fetchall()
        return [dict(r) for r in rows]

    def set_entity_descriptions(self, rows: list[tuple]) -> int:
        """Upsert (slug, description) into entity meta, preserving the geo columns."""
        with self._conn:
            self._conn.executemany(
                "INSERT INTO council_entity_meta(slug, description) VALUES (?, ?) "
                "ON CONFLICT(slug) DO UPDATE SET description = excluded.description", rows)
        return len(rows)

    # --- entity duplicates (council.aliases) + related entities (council.related) ---
    def entity_rows(self) -> list[dict]:
        """All entities (id/slug/name/kind/n) — input for both backfills."""
        return [dict(r) for r in self._conn.execute(
            "SELECT id, slug, name, kind, n FROM council_entities")]

    def entity_link_rows(self) -> list[tuple]:
        """All (entity_id, decision_id) links — input for both backfills."""
        return [(r["entity_id"], r["decision_id"]) for r in self._conn.execute(
            "SELECT entity_id, decision_id FROM council_entity_links")]

    def entity_aliases(self) -> dict[str, str]:
        """{alias slug -> canonical slug}, chains resolved and cycles dropped."""
        from council.aliases import resolve_chains
        raw = {r["slug"]: r["canonical_slug"] for r in self._conn.execute(
            "SELECT slug, canonical_slug FROM council_entity_aliases")}
        return resolve_chains(raw)

    # --- Entitäts-Anker der Suche (Akkuratheits-Paket, 10.08.26) -------------

    def entity_suchindex(self) -> list[tuple[int, str, int]]:
        """(entity_id, suchbarer Name, n Beschlüsse) für den deterministischen
        Frage-Anker: alle Entitäts-Namen PLUS die Alias-Slugs aus
        council_entity_aliases — dort leben auch die frei kuratierten
        Glossar-Einträge („caeci" → caecilienbruecke, source='glossar'),
        dieselbe Tabelle wie die Themen-Dubletten des Admin-Panels."""
        rows = [(r["id"], r["name"], r["n"]) for r in self._conn.execute(
            "SELECT id, name, n FROM council_entities")]
        rows += [(r["id"], r["alias"], r["n"]) for r in self._conn.execute(
            "SELECT e.id, a.slug AS alias, e.n FROM council_entity_aliases a "
            "JOIN council_entities e ON e.slug = a.canonical_slug")]
        return rows

    def entity_steckbriefe(self, entity_ids: list[int]) -> list[dict]:
        """Kurzbeschreibungen der erkannten Entitäten — Hintergrund für die
        Antwort.

        Die Beschreibungen liegen längst in ``council_entity_meta`` (1.114
        Stück, erzeugt aus den Beschlüssen der jeweiligen Entität), wurden von
        der KI-Frage aber nie gelesen. Genau sie beantworten die „Was ist
        eigentlich X?"-Fragen, an denen reine Beschluss-Zitate scheitern.
        """
        ids = [i for i in entity_ids if i]
        if not ids:
            return []
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT e.id, e.name, e.slug, e.kind, m.description "
            f"FROM council_entities e JOIN council_entity_meta m ON m.slug = e.slug "
            f"WHERE e.id IN ({ph}) AND m.description IS NOT NULL AND m.description != ''",
            ids).fetchall()
        nach_id = {r["id"]: dict(r) for r in rows}
        return [nach_id[i] for i in ids if i in nach_id]   # Reihenfolge der Anker

    def decision_ids_for_entities(self, entity_ids: list[int], je: int = 12) -> list[int]:
        """Beschluss-ids der Entitäten, NEUESTE zuerst, dedupliziert — der
        gesetzte Kandidaten-Sockel neben der semantischen Suche."""
        if not entity_ids:
            return []
        ph = ",".join("?" * len(entity_ids))
        rows = self._conn.execute(
            f"SELECT l.entity_id, l.decision_id FROM council_entity_links l "
            f"JOIN council_decisions d ON d.id = l.decision_id "
            f"JOIN council_sessions cs ON cs.ksinr = d.ksinr "
            f"WHERE l.entity_id IN ({ph}) ORDER BY cs.session_date DESC",
            entity_ids).fetchall()
        out, zaehler, gesehen = [], {}, set()
        for r in rows:
            if r["decision_id"] in gesehen:
                continue
            if zaehler.get(r["entity_id"], 0) >= je:
                continue
            zaehler[r["entity_id"]] = zaehler.get(r["entity_id"], 0) + 1
            gesehen.add(r["decision_id"])
            out.append(r["decision_id"])
        return out

    def neueste_stationen_fuer(self, kvonrs: list[int],
                               vorlage_basen: list[str]) -> list[dict]:
        """Alle Beschlüsse (id, kvonr, vorlage_nr, session_date, committee) der
        genannten Vorlagen-Familien — Grundlage für den „ältere Station"-Marker:
        derselbe Text durchläuft mehrere Gremien (gleiches kvonr), Revisionen
        hängen ein Suffix an die Vorlagen-Nummer (26/0100 → 26/0100-1)."""
        kvonrs = sorted({k for k in kvonrs if k})
        basen = sorted({(b or "").strip() for b in vorlage_basen if b and str(b).strip()})
        if not kvonrs and not basen:
            return []
        teile, params = [], []
        if kvonrs:
            teile.append(f"d.kvonr IN ({','.join('?' * len(kvonrs))})")
            params += kvonrs
        for b in basen[:60]:
            teile.append("d.vorlage_nr = ? OR d.vorlage_nr LIKE ?")
            params += [b, b + "-%"]
        rows = self._conn.execute(
            "SELECT d.id, d.kvonr, d.vorlage_nr, cs.session_date, cs.committee "
            "FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr "
            "WHERE " + " OR ".join(teile), params).fetchall()
        return [dict(r) for r in rows]

    def session_dates_fuer(self, decision_ids: list[int]) -> dict[int, str]:
        """id → session_date (ISO) — für den Recency-Bonus im Ranking."""
        if not decision_ids:
            return {}
        ph = ",".join("?" * len(decision_ids))
        rows = self._conn.execute(
            f"SELECT d.id, cs.session_date FROM council_decisions d "
            f"JOIN council_sessions cs ON cs.ksinr = d.ksinr WHERE d.id IN ({ph})",
            decision_ids).fetchall()
        return {r["id"]: r["session_date"] for r in rows if r["session_date"]}

    def list_entity_aliases(self) -> list[dict]:
        """All merges with both display names — for the admin list.

        The alias itself no longer exists in council_entities after the rebuild, so
        its name comes from the raw observations.

        The stored ``canonical_slug`` can be a chain link (A→B where B was later
        merged into C). We report the *resolved* end target so the admin sees the
        real destination name — otherwise the row shows a blank target (the middle
        link is gone from council_entities) and the UI, which groups by
        canonical_slug, would split one subject across two groups.
        """
        resolved = self.entity_aliases()  # {slug -> end canonical}, chains applied
        rows = self._conn.execute(
            """SELECT a.slug, a.canonical_slug, a.source, a.reason, a.created_at,
                      (SELECT name FROM council_entity_obs o WHERE o.slug = a.slug LIMIT 1) AS alias_name
               FROM council_entity_aliases a ORDER BY a.created_at DESC, a.slug""").fetchall()
        out: list[dict] = []
        for r in rows:
            d = dict(r)
            canon = resolved.get(r["slug"], r["canonical_slug"])
            end = self._conn.execute(
                "SELECT name, n FROM council_entities WHERE slug = ?", (canon,)).fetchone()
            d["canonical_slug"] = canon
            d["canonical_name"] = end["name"] if end else None
            d["canonical_n"] = end["n"] if end else None
            out.append(d)
        return out

    # --- Vagheits-Urteile für Themen-Vorschläge (26a) ------------------------
    def topic_vagueness_verdicts(self, slugs: list[str]) -> dict[str, dict]:
        """Gecachte Urteile zu diesen Slugs → ``{slug: {name, vague, hint, suggestion}}``."""
        if not slugs:
            return {}
        q = ",".join("?" * len(slugs))
        rows = self._conn.execute(
            f"SELECT slug, name, vague, hint, suggestion FROM council_topic_vagueness "
            f"WHERE slug IN ({q})", slugs).fetchall()
        return {r["slug"]: dict(r) for r in rows}

    def save_topic_vagueness(self, slug: str, name: str, verdict: dict) -> None:
        """Urteil merken. ``name`` wird mitgespeichert, damit ein umbenanntes
        Thema (Zusammenführung!) neu geprüft wird statt ein Urteil zu erben,
        das zu einem anderen Namen gefällt wurde."""
        from datetime import datetime

        with self._conn:
            self._conn.execute(
                "INSERT INTO council_topic_vagueness (slug, name, vague, hint, suggestion, checked_at) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET "
                "name = excluded.name, vague = excluded.vague, hint = excluded.hint, "
                "suggestion = excluded.suggestion, checked_at = excluded.checked_at",
                (slug, name, 1 if verdict.get("vague") else 0, verdict.get("hint") or "",
                 verdict.get("suggestion") or "", datetime.utcnow().isoformat(timespec="seconds")))

    def save_entity_aliases(self, rows: list[tuple], replace: bool = False) -> int:
        """Upsert merges. ``rows`` = (slug, canonical_slug, source, reason, created_at).

        Manual decisions win: an automatic run never overwrites source='manuell'.
        """
        with self._conn:
            if replace:
                self._conn.execute("DELETE FROM council_entity_aliases WHERE source <> 'manuell'")
            self._conn.executemany(
                "INSERT INTO council_entity_aliases "
                "(slug, canonical_slug, source, reason, created_at) VALUES (?,?,?,?,?) "
                "ON CONFLICT(slug) DO UPDATE SET "
                "  canonical_slug = excluded.canonical_slug, source = excluded.source, "
                "  reason = excluded.reason, created_at = excluded.created_at "
                "WHERE council_entity_aliases.source <> 'manuell'", rows)
        return len(rows)

    def delete_entity_alias(self, slug: str) -> bool:
        """Undo one merge. The entity reappears on the next rebuild from observations."""
        with self._conn:
            cur = self._conn.execute("DELETE FROM council_entity_aliases WHERE slug = ?", (slug,))
        return cur.rowcount > 0

    def known_entity_slugs(self) -> set[str]:
        """Every slug ever observed — the alias targets must exist among these."""
        return {r[0] for r in self._conn.execute("SELECT DISTINCT slug FROM council_entity_obs")}

    def decision_texts(self) -> list[dict]:
        """(id, text) per decision for the text match — title + Beschluss + summary."""
        rows = self._conn.execute(
            "SELECT id, title, beschluss, summary FROM council_decisions").fetchall()
        return [{"id": r["id"],
                 "text": " ".join(x for x in (r["title"], r["beschluss"], r["summary"]) if x)}
                for r in rows]

    def committee_names(self) -> set[str]:
        """Lower-cased committee names — used to keep bodies out of the topic graph."""
        return {(r[0] or "").strip().lower()
                for r in self._conn.execute("SELECT name FROM committees") if r[0]}

    def save_entity_relations(self, rows: list[tuple]) -> int:
        """Replace all related-entity rows.

        ``rows`` = (slug, neighbor_slug, rel_type, rank, score, evidence).
        """
        with self._conn:
            self._conn.execute("DELETE FROM council_entity_related")
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_entity_related "
                "(slug, neighbor_slug, rel_type, rank, score, evidence) VALUES (?,?,?,?,?,?)", rows)
        return len(rows)

    def related_entities(self, slug: str, limit: int = 5) -> list[dict]:
        """Neighbours of an entity, proven ones first (rank order from the backfill)."""
        rows = self._conn.execute(
            """SELECT r.neighbor_slug AS slug, e.name, e.kind, e.n,
                      r.rel_type, r.score, r.evidence
               FROM council_entity_related r
               JOIN council_entities e ON e.slug = r.neighbor_slug
               WHERE r.slug = ? ORDER BY r.rank LIMIT ?""", (slug, limit)).fetchall()
        return [dict(r) for r in rows]

    def entities_to_geocode(self) -> list[dict]:
        """Place/street/area entities not yet geocoded — for the geocode backfill."""
        rows = self._conn.execute(
            "SELECT e.slug, e.name, e.kind FROM council_entities e "
            "LEFT JOIN council_entity_meta m ON m.slug = e.slug "
            "WHERE e.kind = 'ort' AND (m.geo_tried IS NULL OR m.geo_tried = 0) ORDER BY e.n DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def set_entity_geo(self, slug: str, lat: float | None, lon: float | None, geojson: str | None) -> None:
        """Store geocoding result (or mark as tried with NULLs) for an entity slug."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO council_entity_meta(slug, lat, lon, geojson, geo_tried) VALUES (?,?,?,?,1) "
                "ON CONFLICT(slug) DO UPDATE SET lat=excluded.lat, lon=excluded.lon, "
                "geojson=excluded.geojson, geo_tried=1", (slug, lat, lon, geojson))

    def reset_geo(self) -> int:
        """Clear all geocoding (lat/lon/geojson, geo_tried) so it can be recomputed —
        e.g. after improving the geocoder. Keeps descriptions. Returns rows reset."""
        with self._conn:
            cur = self._conn.execute(
                "UPDATE council_entity_meta SET lat=NULL, lon=NULL, geojson=NULL, geo_tried=0 "
                "WHERE geo_tried=1 OR lat IS NOT NULL")
        return cur.rowcount

    # --- Personen-Paket (10.08.26): Stammdaten für Auflösung + Fragetyp -----

    # Vertretungs- und Zeit-Notizen sind keine Ämter („Für Oberbürgermeister
    # Krogmann", „bis TOP 8.2") — nur echte Amtsbezeichnungen zählen.
    _ROLLEN_RE = re.compile(
        r"(?i)^(erste[rn]?\s+)?(oberbürgermeister(in)?|stadtkämmer(er|in)|"
        r"stadtbaur(at|ätin)|stadtr(at|ätin))$")

    def personen_lexikon(self) -> list[dict]:
        """Das Personen-Lexikon für die Badges im Antwort-Text (Tims Wunsch
        12.08.): Ratsmitglieder aus dem Verzeichnis (Partei, Zeitraum,
        Personen-Seite) plus Verwaltungsleute aus den Anwesenheitslisten —
        deren Amt kommt aus den Protokoll-Notizen selbst („Stadtkämmerin",
        „Oberbürgermeister"), nicht aus Weltwissen. `aktiv` heißt: in den
        letzten zwölf Monaten in einer Anwesenheitsliste — dieselbe
        selbstheilende Regel wie bei der Parteien-Zeile; Ehemalige zeigen
        ehrlich nur den belegten Zeitraum."""
        from collections import Counter, defaultdict
        from datetime import date, timedelta
        stichtag = (date.today() - timedelta(days=365)).isoformat()

        def falte(t: str) -> str:
            t = t.lower()
            for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
                t = t.replace(a, b)
            return t

        def namensteile(anzeige: str) -> tuple[str, str]:
            """(vorname_gefaltet, nachname_gefaltet) — Nachname ist das letzte
            Token (Bindestrich-Namen sind EIN Token), Titel zählen nicht als
            Vorname."""
            toks = [t for t in anzeige.replace(".", " ").split()
                    if t.lower().rstrip(".") not in self._HONORIFICS]
            if not toks:
                return "", ""
            return falte(toks[0]) if len(toks) > 1 else "", falte(toks[-1])

        out: list[dict] = []
        gesehen: set[str] = set()
        for m in self.list_members():
            vor, nach = namensteile(m["name"])
            if not nach:
                continue
            gesehen.add(m["slug"])
            out.append({
                "slug": m["slug"], "name": m["name"], "vorname": vor,
                "nachname": nach, "art": "rat", "partei": m["party"],
                "rolle": None,
                "aktiv": bool(m["last"] and m["last"] >= stichtag),
                "von": (m["first"] or "")[:4] or None,
                "bis": (m["last"] or "")[:4] or None,
            })

        rows = self._conn.execute(
            """SELECT a.name, a.note, cs.session_date
               FROM council_attendance a JOIN council_sessions cs ON cs.ksinr = a.ksinr
               WHERE a.role = 'verwaltung' AND a.name IS NOT NULL AND a.name != ''"""
        ).fetchall()
        g: dict = defaultdict(lambda: {"names": Counter(), "rollen": Counter(),
                                       "first": None, "last": None})
        for r in rows:
            sl = self._person_slug(r["name"])
            if not sl:
                continue
            e = g[sl]
            e["names"][r["name"]] += 1
            note = " ".join((r["note"] or "").split())
            if note and self._ROLLEN_RE.match(note):
                e["rollen"][note] += 1
            d = r["session_date"]
            e["first"] = d if e["first"] is None else min(e["first"], d)
            e["last"] = d if e["last"] is None else max(e["last"], d)
        for sl, e in g.items():
            if sl in gesehen:  # Ratsmandat gewinnt über Gast-Auftritte der Verwaltung
                continue
            gesehen.add(sl)
            anzeige = self._person_anzeige(e["names"].most_common(1)[0][0])
            vor, nach = namensteile(anzeige)
            if not nach:
                continue
            out.append({
                "slug": sl, "name": anzeige, "vorname": vor, "nachname": nach,
                "art": "stadt", "partei": None,
                "rolle": e["rollen"].most_common(1)[0][0] if e["rollen"] else None,
                "aktiv": bool(e["last"] and e["last"] >= stichtag),
                "von": (e["first"] or "")[:4] or None,
                "bis": (e["last"] or "")[:4] or None,
            })

        # Blocker (Tims Oltmanns-Befund 12.08.): Gäste, Protokollführung und
        # beratende Mitglieder bekommen NIE ein Badge — aber ihr Nachname macht
        # einen kahlen Nachnamen im Text MEHRDEUTIG. „Herr Oltmanns" (Gast vom
        # Wasserstraßen-Amt, 2019) trug sonst das Badge des einzigen
        # Lexikon-Oltmanns — eines beratenden NABU-Mitglieds von 2026.
        for (name,) in self._conn.execute(
                "SELECT DISTINCT name FROM council_attendance "
                "WHERE role NOT IN ('mitglied','vorsitz','verwaltung') "
                "AND name IS NOT NULL AND name != ''"):
            sl = self._person_slug(name)
            if not sl or sl in gesehen:
                continue
            gesehen.add(sl)
            _, nach = namensteile(self._person_anzeige(name))
            if nach:
                out.append({"slug": sl, "name": None, "vorname": "", "nachname": nach,
                            "art": "blocker", "partei": None, "rolle": None,
                            "aktiv": False, "von": None, "bis": None})
        return out

    def personen_suchindex(self) -> list[tuple[str, str]]:
        """(Name, Partei) aller Ratspersonen mit bekannter Fraktion — Grundlage
        für die FDP/Volt-Auflösung und den Personen-Fragetyp. Die Stammdaten
        führen die EINZEL-Partei (Lükermann=Volt, Pfeiffer=FDP), während die
        Protokolle nur das Gruppen-Label kennen."""
        return [(r["name"], r["fraktion_aktuell"]) for r in self._conn.execute(
            "SELECT name, fraktion_aktuell FROM council_persons "
            "WHERE fraktion_aktuell IS NOT NULL AND fraktion_aktuell != ''")]

    def wortbeitraege_von_sprecher(self, nachname: str, limit: int = 120) -> list[dict]:
        """Alle Wortbeiträge, deren Sprecher-Feld den Nachnamen trägt —
        Kandidaten für den Personen-Fragetyp (der Cross-Encoder wählt daraus
        die zur Frage passenden). Zwei LIKE-Varianten, weil Protokolle
        Umlaute mal ausschreiben („Luekermann") und SQLite-lower() bei
        Umlauten nichts tut."""
        varianten = {nachname}
        gefaltet = nachname
        for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
                     ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue")):
            gefaltet = gefaltet.replace(a, b)
        varianten.add(gefaltet)
        teile = " OR ".join(["w.sprecher LIKE ?"] * len(varianten))
        rows = self._conn.execute(
            f"SELECT w.id, w.ksinr, w.seite, w.sprecher, w.partei, w.art, w.top, w.text, "
            f"       cs.committee, cs.session_date "
            f"FROM council_wortbeitraege w JOIN council_sessions cs ON cs.ksinr = w.ksinr "
            f"WHERE {teile} ORDER BY cs.session_date DESC LIMIT ?",
            [f"%{v}%" for v in varianten] + [limit]).fetchall()
        return [dict(r) for r in rows]

    #: Anreden, die vor einem Namen stehen dürfen, ohne ihn zu einem anderen zu
    #: machen. Ohne die Liste hielte „Ratsfrau Hufeland" einen Vornamen für
    #: vorhanden und fiele aus der Zuordnung.
    #: Rollen zählen mit: „Ratsvorsitzender Harms" ist eine Funktion plus
    #: Nachname, kein zweiter Name — genau wie „Ratsherr Harms".
    _ANREDEN = {"ratsfrau", "ratsherr", "frau", "herr", "ratsmitglied",
                "oberbuergermeister", "oberbürgermeister", "buergermeister",
                "bürgermeister", "stadtrat", "staedtrat",
                "ratsvorsitzender", "ratsvorsitzende", "vorsitzender", "vorsitzende",
                "ausschussvorsitzender", "ausschussvorsitzende"}

    @classmethod
    def _spricht_diese_person(cls, sprecher: str, vorname: str, nachname: str) -> bool:
        """Gehört dieser Sprecher-Eintrag zu genau dieser Person?

        Die Protokolle schreiben denselben Menschen mal „Andrea Hufeland", mal
        „Hufeland", mal „Ratsfrau Hufeland" — der Nachname allein muss also
        reichen. Er reicht aber NICHT, wenn der Eintrag einen anderen Vornamen
        trägt: „Dr. Ingo Harms" ist nicht „Tim Harms". Gemessen am Bestand ist
        das selten (5 von 279 Treffern bei Harms), aber auf einer Seite, die
        *alle* Beiträge zeigt, fällt jeder Fremdbeitrag auf.

        Mehrere Sprecher in einem Eintrag („Christoph Baak, Dr. Esther
        Niewerth-Baumann") gelten für beide — da haben tatsächlich beide geredet.
        """
        if not nachname:
            return False
        roh = cls._falte_namen(sprecher)
        if cls._falte_namen(nachname) not in roh:
            return False
        if not vorname:
            return True
        v = cls._falte_namen(vorname)
        if v in roh:
            return True
        # Kein passender Vorname: nur durchlassen, wenn der Eintrag überhaupt
        # keinen führt (reiner Nachname, ggf. mit Anrede oder Titel).
        rest = [t for t in re.split(r"[^\wäöüß]+", sprecher.lower()) if len(t) > 1]
        nach_teile = set(re.split(r"[^\wäöüß]+", nachname.lower()))
        for t in rest:
            if t in nach_teile or t.rstrip(".") in cls._HONORIFICS or t in cls._ANREDEN:
                continue
            return False   # ein fremder Namensbestandteil → andere Person
        return True

    @staticmethod
    def _falte_namen(s: str) -> str:
        s = s.lower()
        for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
            s = s.replace(a, b)
        return s

    def wortbeitraege_person(self, name: str, gremium: str | None = None,
                             offset: int = 0, limit: int = 20) -> dict:
        """Wortbeiträge einer Person — seitenweise und nach Gremium filterbar.

        Gefiltert wird in Python statt in SQL: Die Zuordnung Sprecher→Person
        kennt Schreibvarianten (s. ``_spricht_diese_person``), die keine
        LIKE-Bedingung abbildet. Der Rohbestand je Person ist klein genug
        (Vielredner kommen auf ~800 Beiträge), um ihn einmal zu holen.

        Rückgabe: ``items`` (die angeforderte Seite), ``total`` (nach
        Gremien-Filter), ``gesamt`` (ohne Filter) und ``gremien`` als Facetten
        mit Anzahl — damit die Oberfläche gleich sagen kann, wo etwas zu holen
        ist.
        """
        teile = [t for t in name.replace(".", " ").replace(",", " ").split()
                 if t.lower().rstrip(".") not in self._HONORIFICS
                 and t.lower() not in self._ANREDEN]
        if not teile:
            return {"items": [], "total": 0, "gesamt": 0, "gremien": []}
        nachname, vorname = teile[-1], (teile[0] if len(teile) > 1 else "")
        roh = self.wortbeitraege_von_sprecher(nachname, limit=5000)
        meine = [w for w in roh
                 if self._spricht_diese_person(w.get("sprecher") or "", vorname, nachname)]

        from collections import Counter
        zaehler = Counter(w["committee"] for w in meine if w.get("committee"))
        gefiltert = [w for w in meine if not gremium or w.get("committee") == gremium]
        seite = gefiltert[max(0, offset): max(0, offset) + max(1, min(limit, 100))]
        return {
            "items": [{"art": w["art"], "top": w["top"], "text": w["text"],
                       "committee": w["committee"], "session_date": w["session_date"]}
                      for w in seite],
            "total": len(gefiltert),
            "gesamt": len(meine),
            "gremien": [{"committee": k, "n": n} for k, n in zaehler.most_common()],
        }

    # --- Council members (from attendance: who sits on the council) ------------------
    _MEMBER_ROLES = ("mitglied", "vorsitz")  # exclude verwaltung/protokoll/gast/beratend
    # Titel UND Anreden: „Herr Jens Freymuth" und „Jens Freymuth" sind dieselbe
    # Person — ohne die Anreden entstanden Dubletten im Mitglieder-Verzeichnis
    # (Tims Befund 10.08.). Adelspartikel („zu", „von") bleiben absichtlich
    # stehen — sie gehören zum Nachnamen.
    _HONORIFICS = {"prof", "dr", "dipl", "ing", "med",
                   "herr", "frau", "ratsherr", "ratsfrau"}
    _ANREDEN = {"herr", "frau", "ratsherr", "ratsfrau"}

    @staticmethod
    def _person_anzeige(name: str) -> str:
        """Anzeige-Name ohne führende Anrede („Herr Jens Freymuth" → „Jens
        Freymuth") — Titel wie „Dr." bleiben, die gehören zum Namen."""
        toks = name.split()
        while toks and toks[0].lower().rstrip(".") in CouncilStore._ANREDEN:
            toks.pop(0)
        return " ".join(toks) or name

    @staticmethod
    def _person_slug(name: str) -> str:
        s = name.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        toks = [t for t in re.split(r"[^a-z0-9]+", s) if t and t not in CouncilStore._HONORIFICS]
        return "-".join(toks)

    def list_members(self) -> list[dict]:
        """Council members from attendance (role mitglied/vorsitz), grouped by *slug* so
        title variants of the same person ("Dr. X" and "X") merge into ONE entry (and the
        React list gets unique keys). Per person: canonical (most-frequent) name, die
        **letzte aktive Fraktion** (nicht die häufigste — Wechsler wie FDP→Volt oder
        Linke→BSW würden sonst ewig unter der alten laufen), distinct sessions attended
        and committees served. The member directory."""
        from collections import Counter, defaultdict
        from council.parties import classify_faction
        rows = self._conn.execute(
            """SELECT a.name, a.ksinr, a.party, cs.committee, cs.session_date
               FROM council_attendance a JOIN council_sessions cs ON cs.ksinr = a.ksinr
               WHERE a.role IN ('mitglied','vorsitz') AND a.name IS NOT NULL AND a.name != ''"""
        ).fetchall()
        g: dict = defaultdict(lambda: {"names": Counter(), "ksinrs": set(), "committees": set(),
                                       "first": None, "last": None, "party_at": None})
        for r in rows:
            sl = self._person_slug(r["name"])
            if not sl:
                continue
            e = g[sl]
            e["names"][r["name"]] += 1
            e["ksinrs"].add(r["ksinr"])
            e["committees"].add(r["committee"])
            d = r["session_date"]
            e["first"] = d if e["first"] is None else min(e["first"], d)
            e["last"] = d if e["last"] is None else max(e["last"], d)
            # Nur Partei/Gruppe als „aktuelle" Zugehörigkeit merken (gruppen-bewusst:
            # „FDP/Volt"→Gruppe, nicht →FDP); blanke Streusitzungen (parteilos)
            # nicht, damit das Verzeichnis nicht auf einen Ausreißer umklappt.
            c = classify_faction(r["party"])
            p = c["label"] if c["kind"] in ("partei", "gruppe") else None
            if p and (e["party_at"] is None or d >= e["party_at"][0]):
                e["party_at"] = (d, p)
        out = [{"slug": sl, "name": self._person_anzeige(e["names"].most_common(1)[0][0]),
                "party": e["party_at"][1] if e["party_at"] else None,
                "n": len(e["ksinrs"]), "committees": len(e["committees"]),
                "first": e["first"], "last": e["last"]}
               for sl, e in g.items()]
        out.sort(key=lambda m: -m["n"])
        return out

    def member_name(self, slug: str) -> str | None:
        """Der kanonische (häufigste) Name zu einem Slug — die schlanke Auskunft
        für Endpunkte, die nicht das ganze Profil brauchen. Ohne Anrede, wie in
        ``member_detail`` und im Verzeichnis (#419)."""
        from collections import Counter
        namen = [r["name"] for r in self._conn.execute(
            "SELECT name FROM council_attendance WHERE role IN ('mitglied','vorsitz') "
            "AND name IS NOT NULL AND name != ''")]
        passend = [n for n in namen if self._person_slug(n) == slug]
        return self._person_anzeige(Counter(passend).most_common(1)[0][0]) if passend else None

    def member_detail(self, slug: str) -> dict | None:
        """One member — all name variants merged by slug: party, sessions, active span,
        committees served (with counts and chair flag) and their most recent sessions."""
        from collections import Counter
        from council.parties import classify_faction
        names = [r["name"] for r in self._conn.execute(
            "SELECT DISTINCT name FROM council_attendance WHERE role IN ('mitglied','vorsitz') "
            "AND name IS NOT NULL AND name != ''")]
        matched = [n for n in names if self._person_slug(n) == slug]
        if not matched:
            return None
        ph = ",".join("?" * len(matched))
        name = self._person_anzeige(Counter(  # canonical = most-frequent spelling
            r["name"] for r in self._conn.execute(
                f"SELECT name FROM council_attendance WHERE name IN ({ph}) AND role IN ('mitglied','vorsitz')",
                matched)).most_common(1)[0][0])
        chairs = {r["committee"] for r in self._conn.execute(
            f"SELECT DISTINCT cs.committee FROM council_attendance a JOIN council_sessions cs ON cs.ksinr=a.ksinr "
            f"WHERE a.name IN ({ph}) AND a.role='vorsitz'", matched)}
        committees = self._conn.execute(
            f"""SELECT cs.committee, COUNT(DISTINCT a.ksinr) n
                FROM council_attendance a JOIN council_sessions cs ON cs.ksinr = a.ksinr
                WHERE a.name IN ({ph}) AND a.role IN ('mitglied','vorsitz')
                GROUP BY cs.committee ORDER BY n DESC""", matched).fetchall()
        span = self._conn.execute(
            f"""SELECT COUNT(DISTINCT a.ksinr) n, MIN(cs.session_date) first, MAX(cs.session_date) last
                FROM council_attendance a JOIN council_sessions cs ON cs.ksinr = a.ksinr
                WHERE a.name IN ({ph}) AND a.role IN ('mitglied','vorsitz')""", matched).fetchone()
        recent = self._conn.execute(
            f"""SELECT cs.ksinr, cs.committee, cs.session_date FROM council_attendance a
                JOIN council_sessions cs ON cs.ksinr = a.ksinr
                WHERE a.name IN ({ph}) AND a.role IN ('mitglied','vorsitz')
                ORDER BY cs.session_date DESC LIMIT 12""", matched).fetchall()
        # Fraktions-/Gruppen-Verlauf aus der Anwesenheit: aufeinanderfolgende
        # Sitzungen derselben Zugehörigkeit zu Phasen zusammengefasst — die einzige
        # echte Zeitreihe, denn das Ratsinfo überschreibt Fraktionen rückwirkend.
        # Wichtig: `classify_faction` hält GRUPPEN als Gruppen fest (statt sie auf
        # eine Partei zu kollabieren) und blanke Label als „parteilos" — sonst
        # erschiene z. B. ein „FDP/Volt"-Gruppenmitglied fälschlich als FDP.
        runs: list[dict] = []
        for r in self._conn.execute(
            f"""SELECT cs.session_date d, a.party FROM council_attendance a
                JOIN council_sessions cs ON cs.ksinr = a.ksinr
                WHERE a.name IN ({ph}) AND a.role IN ('mitglied','vorsitz')
                ORDER BY cs.session_date""", matched):
            c = classify_faction(r["party"])
            if c["kind"] == "unbekannt":
                continue
            label = c["label"]
            if runs and runs[-1]["label"] == label:
                runs[-1]["last"] = r["d"]
                runs[-1]["n"] += 1
            else:
                runs.append({"label": label, "kind": c["kind"], "parties": c["parties"],
                             "first": r["d"], "last": r["d"], "n": 1})
        # Einzelne Ausreißer-Sitzungen (Tippfehler/fehlende Extraktion) zwischen
        # zwei gleichen Phasen glätten, dann angrenzende Phasen mergen.
        cleaned = [run for i, run in enumerate(runs)
                   if not (run["n"] == 1 and 0 < i < len(runs) - 1
                           and runs[i - 1]["label"] == runs[i + 1]["label"] != run["label"])]
        timeline: list[dict] = []
        for run in cleaned:
            if timeline and timeline[-1]["label"] == run["label"]:
                timeline[-1]["last"] = run["last"]
                timeline[-1]["n"] += run["n"]
            else:
                timeline.append(dict(run))
        # Wortbeiträge der Person (Personen-Paket 10.08.26): die jüngsten
        # Beiträge in voller Länge — das Beleg-Versprechen gilt auch hier.
        # Nachname = letztes Namens-Token ohne Titel (Umlaute intakt fürs LIKE).
        # Erste Seite der Wortbeiträge gleich mitliefern (die Seite soll ohne
        # zweiten Rundlauf etwas zeigen); weitere Seiten und der Gremien-Filter
        # laufen über /person/{slug}/wortbeitraege.
        wb = self.wortbeitraege_person(name, limit=10)
        return {
            "name": name, "slug": slug,
            # Aktuelle Zugehörigkeit (Ende der geglätteten Zeitreihe) — nicht die
            # häufigste: Wechsler (FDP/Volt→Volt, Linke→BSW) zeigen sonst die alte.
            "party": timeline[-1]["label"] if timeline else None,
            "n_sessions": span["n"], "active_from": span["first"], "active_to": span["last"],
            "faction_timeline": timeline,
            "ris": self.person_stammdaten_for_names(matched),
            "committees": [{"committee": r["committee"], "n": r["n"], "chair": r["committee"] in chairs}
                           for r in committees],
            "recent": [{"ksinr": r["ksinr"], "committee": r["committee"], "session_date": r["session_date"]}
                       for r in recent],
            "wortbeitraege": wb["items"],
            "wortbeitraege_gesamt": wb["gesamt"],
            "wortbeitraege_gremien": wb["gremien"],
        }

    def decisions_for_amount(self, only_missing: bool = False) -> list[dict]:
        """Main decisions with their text, for the € extraction backfill."""
        sql = "SELECT id, title, beschluss FROM council_decisions WHERE kind = 'decision'"
        if only_missing:
            sql += " AND amount_eur IS NULL"
        return [dict(r) for r in self._conn.execute(sql)]

    def set_amounts(self, rows: list[tuple]) -> int:
        """Bulk-write amount_eur. rows = (amount_or_None, decision_id)."""
        with self._conn:
            self._conn.executemany("UPDATE council_decisions SET amount_eur = ? WHERE id = ?", rows)
        return len(rows)

    # Titles excluded from the "largest" view: accounting / whole-budget reports
    # (balance totals, not a discrete decision) and treasury operations (debt
    # refinancing / credit reporting) — neither is "the city spends X on Y".
    _NON_SPENDING_TITLES = (
        "jahresabschluss", "lagebericht", "gesamtabschluss", "wirtschaftsplan",
        "haushaltsplan", "haushaltssatzung", "nachtragshaushalt", "finanzbericht",
        "beteiligungsbericht", "jahresrechnung", "quartalsbericht", "zwischenbericht",
        "umschuldung", "kreditrichtlinie", "kassenkredite",
    )

    def activity_trends(self, quarters: int = 12) -> dict:
        """Council activity over time for the trends view: decisions and recognised €
        volume per quarter (split by the busiest policy fields), plus the most active
        tags in the recent quarters."""
        from collections import Counter

        q_expr = ("substr(cs.session_date,1,4) || '-Q' || "
                  "((CAST(substr(cs.session_date,6,2) AS INTEGER)+2)/3)")
        rows = self._conn.execute(
            f"""SELECT {q_expr} AS q, d.policy_field AS field, COUNT(*) AS n
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND cs.session_date IS NOT NULL
                      AND d.policy_field IS NOT NULL
                GROUP BY q, field"""
        ).fetchall()
        all_q = sorted({r["q"] for r in rows})[-quarters:]
        qset = set(all_q)
        per_field: dict[str, dict] = {}
        for r in rows:
            if r["q"] not in qset:
                continue
            per_field.setdefault(r["field"], {q: 0 for q in all_q})[r["q"]] = r["n"]
        top_fields = sorted(per_field, key=lambda f: -sum(per_field[f].values()))[:6]

        # Recognised € per quarter — exclude accounting/treasury docs (Haushaltsplan,
        # Jahresabschluss …) so the bars reflect actual spending, not budget volumes.
        mclauses = " AND ".join(["LOWER(d.title) NOT LIKE ?"] * len(self._NON_SPENDING_TITLES))
        mparams = [f"%{k}%" for k in self._NON_SPENDING_TITLES]
        money = {q: 0.0 for q in all_q}
        for r in self._conn.execute(
            f"""SELECT {q_expr} AS q, COALESCE(SUM(d.amount_eur), 0) AS eur
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.amount_eur IS NOT NULL
                      AND cs.session_date IS NOT NULL AND {mclauses}
                GROUP BY q""",
            mparams,
        ):
            if r["q"] in qset:
                money[r["q"]] = r["eur"] or 0

        # Procedural tags aren't "topics" — keep them out of the emerging list.
        procedural = {"bericht", "annahme", "vertagung", "kenntnisnahme", "beschluss",
                      "antrag", "anfrage", "mitteilung", "vorlage", "abstimmung", "resolution"}
        recent = set(all_q[-2:])
        tagc: Counter = Counter()
        for r in self._conn.execute(
            f"""SELECT d.policy_tags AS tags, {q_expr} AS q
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.policy_tags IS NOT NULL
                      AND cs.session_date IS NOT NULL"""
        ):
            if r["q"] in recent:
                try:
                    for t in json.loads(r["tags"] or "[]"):
                        t = str(t).strip()
                        if t and t.lower() not in procedural:
                            tagc[t] += 1
                except (ValueError, TypeError):
                    pass

        # Biggest single financial decision per quarter (excl. accounting, reusing the
        # filter above) — the factual "what drove this quarter" behind the money bars.
        drivers: dict[str, dict] = {}
        for r in self._conn.execute(
            f"""SELECT {q_expr} AS q, d.id AS id, d.title AS title, d.amount_eur AS eur
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.amount_eur IS NOT NULL
                      AND cs.session_date IS NOT NULL AND {mclauses}
                ORDER BY d.amount_eur DESC""",
            mparams,
        ):
            if r["q"] in qset and r["q"] not in drivers:
                drivers[r["q"]] = {"id": r["id"], "title": r["title"], "eur": round(r["eur"] or 0)}

        return {
            "quarters": all_q,
            "fields": top_fields,
            "by_field": {f: [per_field[f][q] for q in all_q] for f in top_fields},
            "money": [round(money[q]) for q in all_q],
            "money_drivers": [drivers.get(q) for q in all_q],
            "emerging": [{"tag": t, "n": c} for t, c in tagc.most_common(12) if c >= 2],
        }

    def largest_financial_decisions(self, limit: int = 25) -> list[dict]:
        """Decisions with the largest recognised € amount, deduped across committees
        (same Vorlage decided in Ausschuss + Rat → one entry) and excluding
        accounting/treasury items."""
        clauses = " AND ".join(["LOWER(d.title) NOT LIKE ?"] * len(self._NON_SPENDING_TITLES))
        params = [f"%{k}%" for k in self._NON_SPENDING_TITLES]
        rows = self._conn.execute(
            f"""SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
                FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.amount_eur IS NOT NULL AND {clauses}
                ORDER BY d.amount_eur DESC LIMIT 300""",
            params,
        ).fetchall()
        seen: set = set()
        out: list[dict] = []
        for r in rows:
            # Collapse the same matter (shared Vorlage across committees/revisions) and
            # recurring series (same title, different Vorlage). Rows are amount-desc, so
            # the kept entry is the largest.
            keys = _dedup_keys(r["title"], r["vorlage_nr"], r["id"])
            if any(k in seen for k in keys):
                continue
            seen.update(keys)
            out.append(self._decision_row(r))
            if len(out) >= limit:
                break
        return out

    def money_by_field(self) -> list[dict]:
        """Recognised € volume per policy field (excl. accounting/treasury), deduped
        like the largest-list so the same matter across committees/revisions isn't
        double-counted. For the 'Wofür fließt das Geld?' breakdown."""
        clauses = " AND ".join(["LOWER(d.title) NOT LIKE ?"] * len(self._NON_SPENDING_TITLES))
        params = [f"%{k}%" for k in self._NON_SPENDING_TITLES]
        rows = self._conn.execute(
            f"""SELECT d.id, d.title, d.vorlage_nr, d.policy_field AS field, d.amount_eur AS eur
                FROM council_decisions d
                WHERE d.kind = 'decision' AND d.amount_eur IS NOT NULL
                      AND d.policy_field IS NOT NULL AND {clauses}
                ORDER BY d.amount_eur DESC""",
            params,
        ).fetchall()
        seen: set = set()
        agg: dict[str, dict] = {}
        for r in rows:
            keys = _dedup_keys(r["title"], r["vorlage_nr"], r["id"])
            if any(k in seen for k in keys):
                continue
            seen.update(keys)
            a = agg.setdefault(r["field"], {"field": r["field"], "total": 0.0, "n": 0})
            a["total"] += r["eur"] or 0
            a["n"] += 1
        out = sorted(agg.values(), key=lambda x: -x["total"])
        for a in out:
            a["total"] = round(a["total"])
        return out

    def policy_field_stats(self) -> list[dict]:
        """Count of classified decisions per policy field, most frequent first."""
        rows = self._conn.execute(
            "SELECT policy_field AS field, COUNT(*) AS count FROM council_decisions "
            "WHERE policy_field IS NOT NULL GROUP BY policy_field ORDER BY count DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def party_analysis(self, top_parties: int = 8) -> dict:
        """Aggregate party behaviour from motions (Antragsteller = the ``factions``
        on a decision): a party × policy-field heatmap, per-party success rates,
        per-field contention and party co-sponsorships. Only ~13 % of decisions name
        an Antragsteller, so this reflects *active motions*, not every vote."""
        from collections import Counter
        from itertools import combinations

        from council.parties import order_key, parties_for_faction

        rows = self._conn.execute(
            "SELECT factions, policy_field, outcome, gegenstimmen, enthaltungen "
            "FROM council_decisions WHERE kind = 'decision'"
        ).fetchall()

        party_field: dict[str, Counter] = {}
        party_outcome: dict[str, Counter] = {}
        party_total: Counter = Counter()
        field_motion: Counter = Counter()      # motions per field (heatmap columns)
        field_total: Counter = Counter()       # decided votes per field (contention)
        field_contested: Counter = Counter()
        pairs: Counter = Counter()
        with_factions = 0

        for fac, field, outcome, gegen, enth in rows:
            if field and outcome in ("angenommen", "abgelehnt", "vertagt"):
                field_total[field] += 1
                if (gegen or 0) > 0 or (enth or 0) > 0:
                    field_contested[field] += 1
            try:
                arr = json.loads(fac or "[]")
            except (json.JSONDecodeError, TypeError):
                arr = []
            # Multi-Mapping: „Gruppe FDP/Volt" zählt für FDP UND Volt.
            parties = sorted({p for x in arr for p in parties_for_faction(x)}, key=order_key)
            if not parties:
                continue
            with_factions += 1
            for p in parties:
                party_total[p] += 1
                if field:
                    party_field.setdefault(p, Counter())[field] += 1
                    field_motion[field] += 1
                if outcome:
                    party_outcome.setdefault(p, Counter())[outcome] += 1
            for a, b in combinations(parties, 2):
                pairs[(a, b)] += 1

        top = sorted((p for p, _ in party_total.most_common(top_parties)), key=order_key)
        fields_present = [f for f, _ in field_motion.most_common()]
        matrix = {p: {f: party_field.get(p, Counter()).get(f, 0) for f in fields_present} for p in top}

        success = []
        for p in party_total:
            oc = party_outcome.get(p, Counter())
            decided = oc["angenommen"] + oc["abgelehnt"]
            success.append({
                "party": p, "motions": party_total[p],
                "angenommen": oc["angenommen"], "abgelehnt": oc["abgelehnt"], "vertagt": oc["vertagt"],
                "rate": round(oc["angenommen"] / decided, 3) if decided else None,
            })
        success.sort(key=lambda s: s["motions"], reverse=True)

        contention = [
            {"field": f, "total": field_total[f], "contested": field_contested[f],
             "contested_rate": round(field_contested[f] / field_total[f], 3)}
            for f in sorted(field_total, key=lambda f: field_total[f], reverse=True)
        ]
        alliances = [{"a": a, "b": b, "count": c} for (a, b), c in pairs.most_common(12)]

        return {
            "coverage": {"with_factions": with_factions, "total": len(rows)},
            "topic_matrix": {"parties": top, "fields": fields_present, "matrix": matrix},
            "success_rates": success,
            "contention": contention,
            "alliances": alliances,
        }

    # --- Goal tracking ------------------------------------------------------
    def get_goal_candidates(self, keywords: list[str], limit: int = 400,
                            exclude_goal: str | None = None) -> list[dict]:
        """Decisions whose text/tags match any of a goal's keywords (candidates
        for LLM relevance + stance assessment). With ``exclude_goal`` set, skips
        decisions already linked to that goal — for the incremental daily cron."""
        if not keywords:
            return []
        clause = " OR ".join(
            ["d.title LIKE ? OR d.beschluss LIKE ? OR d.summary LIKE ? OR d.policy_tags LIKE ?"] * len(keywords)
        )
        params: list = []
        for kw in keywords:
            p = f"%{kw}%"
            params += [p, p, p, p]
        exclude_sql = ""
        if exclude_goal:
            exclude_sql = " AND d.id NOT IN (SELECT decision_id FROM council_goal_links WHERE goal = ?)"
            params.append(exclude_goal)
        params.append(limit)
        rows = self._conn.execute(
            f"""SELECT d.id, d.title, d.beschluss, d.summary, d.outcome, cs.session_date
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND ({clause}){exclude_sql}
                ORDER BY cs.session_date DESC LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def save_goal_links(self, goal: str, results: dict) -> int:
        """Upsert assessment results for a goal: id -> {relevant, stance, grund}."""
        rows = [(goal, did, 1 if r.get("relevant") else 0, r.get("stance"), r.get("grund"))
                for did, r in results.items()]
        with self._conn:
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_goal_links (goal, decision_id, relevant, stance, rationale) "
                "VALUES (?, ?, ?, ?, ?)", rows,
            )
        return len(rows)

    def clear_goal_links(self, goal: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM council_goal_links WHERE goal = ?", (goal,))

    def linked_decision_ids(self, goal: str) -> set:
        """Decision ids already linked to a goal (any relevance) — for incremental runs."""
        return {r[0] for r in self._conn.execute(
            "SELECT decision_id FROM council_goal_links WHERE goal = ?", (goal,))}

    def goal_summary(self) -> dict:
        """Per goal: counts of relevant decisions by stance."""
        agg: dict[str, dict] = {}
        for goal, stance, c in self._conn.execute(
            "SELECT goal, stance, COUNT(*) FROM council_goal_links WHERE relevant = 1 GROUP BY goal, stance"
        ):
            g = agg.setdefault(goal, {"voran": 0, "bremst": 0, "neutral": 0, "total": 0})
            g[stance] = c
            g["total"] += c
        return agg

    def goal_detail(self, goal: str) -> list[dict]:
        """Relevant decisions linked to a goal, newest first, with stance + rationale."""
        rows = self._conn.execute(
            """SELECT d.id, d.title, d.summary, d.policy_field, d.outcome,
                      cs.session_date, cs.committee, gl.stance, gl.rationale
               FROM council_goal_links gl
               JOIN council_decisions d ON d.id = gl.decision_id
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE gl.goal = ? AND gl.relevant = 1
               ORDER BY cs.session_date DESC""",
            (goal,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Semantic similarity (precomputed offline) --------------------------
    def decisions_for_embedding(self) -> list[dict]:
        """All main decisions with a short text for embedding (id + text).

        Teilabstimmungs-Titel (Änderungsanträge, Design 23a) zählen zum Text des
        Haupt-TOPs — sie tragen oft die konkreten Begriffe („Änderungsantrag der
        Fraktion X: Tempo 30 auf …"), die im knappen Hauptbeschluss fehlen."""
        rows = self._conn.execute(
            "SELECT d.id, d.title, d.summary, d.beschluss, sv.stext FROM council_decisions d "
            "LEFT JOIN (SELECT ksinr, parent_item, substr(GROUP_CONCAT(title, ' · '), 1, 400) AS stext "
            "           FROM council_decisions WHERE kind = 'subvote' AND parent_item IS NOT NULL "
            "           GROUP BY ksinr, parent_item) sv "
            "  ON sv.ksinr = d.ksinr AND sv.parent_item = d.item_number "
            "WHERE d.kind = 'decision'"
        ).fetchall()
        out = []
        for r in rows:
            text = f"{r['title'] or ''}. {r['summary'] or r['beschluss'] or ''}".strip()[:500]
            if r["stext"]:
                text = f"{text} · {r['stext']}"[:800]
            out.append({"id": r["id"], "text": text})
        return out

    def set_similar(self, rows: list[tuple]) -> int:
        """Replace all similarity links. ``rows`` = (decision_id, neighbor_id, rank, score)."""
        with self._conn:
            self._conn.execute("DELETE FROM council_similar")
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_similar (decision_id, neighbor_id, rank, score) "
                "VALUES (?, ?, ?, ?)", rows,
            )
        return len(rows)

    def save_embeddings(self, rows: list[tuple]) -> int:
        """Replace all decision vectors. ``rows`` = (decision_id, float32 bytes)."""
        with self._conn:
            self._conn.execute("DELETE FROM council_embeddings")
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_embeddings (decision_id, vector) VALUES (?, ?)", rows,
            )
        return len(rows)

    def get_embeddings(self) -> list:
        """All (decision_id, vector-blob) rows — caller rebuilds the matrix."""
        return self._conn.execute(
            "SELECT decision_id, vector FROM council_embeddings ORDER BY decision_id"
        ).fetchall()

    def embeddings_version(self) -> tuple:
        """Billiger Versionsschlüssel des Embedding-Bestands. Der Matrix-Cache in
        council/embeddings.py lädt neu, sobald sich der Wert ändert — ohne den
        früher nötigen Service-Neustart nach embed_decisions.py. ``data_version``
        deckt dabei auch ein Re-Embedding ab, das Anzahl und ids unverändert
        lässt (Modellwechsel): Es zählt hoch, sobald ein *anderer* Prozess die
        DB-Datei geschrieben hat."""
        count, max_id = self._conn.execute(
            "SELECT COUNT(*), COALESCE(MAX(decision_id), 0) FROM council_embeddings"
        ).fetchone()
        data_version = self._conn.execute("PRAGMA data_version").fetchone()[0]
        return (count, max_id, data_version)

    # ---- Vorlagen-Chunk-Embeddings (semantische Suche im Sachverhalt) ----

    def vorlagen_missing_embeddings(self) -> list[dict]:
        """Vorlagen (mit Text, an ≥1 Beschluss hängend), deren Chunk-Vektoren
        fehlen oder deren Text sich seit dem letzten Embedding geändert hat.
        Der Abgleich läuft über den SHA-256 des Volltexts (text_hash)."""
        import hashlib

        stored = dict(self._conn.execute(
            "SELECT vorlage_nr, MIN(text_hash) FROM council_vorlage_embeddings GROUP BY vorlage_nr"
        ).fetchall())
        rows = self._conn.execute(
            "SELECT v.vorlage_nr, MAX(v.raw_text) AS raw_text FROM council_vorlagen v "
            "WHERE v.status = 'ok' AND v.vorlage_nr IN "
            "  (SELECT DISTINCT vorlage_nr FROM council_decisions "
            "   WHERE kind = 'decision' AND vorlage_nr IS NOT NULL AND vorlage_nr != '') "
            "GROUP BY v.vorlage_nr"
        ).fetchall()
        out = []
        for r in rows:
            text = r["raw_text"] or ""
            if not text.strip():
                continue
            h = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
            if stored.get(r["vorlage_nr"]) != h:
                out.append({"vorlage_nr": r["vorlage_nr"], "raw_text": text, "text_hash": h})
        return out

    def replace_vorlage_embeddings(self, vorlage_nr: str, text_hash: str,
                                   chunks: list[tuple[str, bytes]]) -> None:
        """Chunk-Text+Vektor einer Vorlage komplett ersetzen (alte Chunk-Anzahl
        kann abweichen, deshalb erst löschen)."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_vorlage_embeddings WHERE vorlage_nr = ?", (vorlage_nr,))
            self._conn.executemany(
                "INSERT INTO council_vorlage_embeddings "
                "(vorlage_nr, chunk_idx, text_hash, chunk_text, vector) VALUES (?, ?, ?, ?, ?)",
                [(vorlage_nr, i, text_hash, text, vec) for i, (text, vec) in enumerate(chunks)],
            )

    def get_vorlage_embeddings(self) -> list:
        """Alle (vorlage_nr, chunk_text, vector)-Zeilen — der Aufrufer baut die Matrix."""
        return self._conn.execute(
            "SELECT vorlage_nr, chunk_text, vector FROM council_vorlage_embeddings "
            "ORDER BY vorlage_nr, chunk_idx"
        ).fetchall()

    def vorlage_embeddings_version(self) -> tuple:
        """Versionsschlüssel analog embeddings_version(), für den Chunk-Matrix-Cache."""
        count = self._conn.execute(
            "SELECT COUNT(*) FROM council_vorlage_embeddings").fetchone()[0]
        data_version = self._conn.execute("PRAGMA data_version").fetchone()[0]
        return (count, data_version)

    # ---- Anlagen-Embeddings (Task 33, Kanal der Gründlichen Recherche) -----

    def anlagen_missing_embeddings(self, limit: int | None = None) -> list[dict]:
        """Anlagen mit Text, deren Chunk-Vektoren fehlen oder deren Text sich
        geändert hat (SHA-256-Abgleich wie bei den Vorlagen). Neueste zuerst —
        frisches Material zuerst durchsuchbar."""
        import hashlib

        stored = dict(self._conn.execute(
            "SELECT document_id, MIN(text_hash) FROM council_anlage_embeddings "
            "GROUP BY document_id").fetchall())
        rows = self._conn.execute(
            "SELECT document_id, label, raw_text FROM council_anlagen "
            "WHERE status = 'ok' AND raw_text IS NOT NULL AND raw_text != '' "
            "ORDER BY document_id DESC").fetchall()
        out = []
        for r in rows:
            h = hashlib.sha256(r["raw_text"].encode("utf-8")).hexdigest()[:16]
            if stored.get(r["document_id"]) != h:
                out.append({"document_id": r["document_id"], "label": r["label"],
                            "raw_text": r["raw_text"], "text_hash": h})
                if limit and len(out) >= limit:
                    break
        return out

    def replace_anlage_embeddings(self, document_id: int, text_hash: str,
                                  chunks: list[tuple[str, bytes]]) -> None:
        """Chunk-Text+Vektor einer Anlage komplett ersetzen."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_anlage_embeddings WHERE document_id = ?", (document_id,))
            self._conn.executemany(
                "INSERT INTO council_anlage_embeddings "
                "(document_id, chunk_idx, text_hash, chunk_text, vector) VALUES (?, ?, ?, ?, ?)",
                [(document_id, i, text_hash, text, vec) for i, (text, vec) in enumerate(chunks)],
            )

    def get_anlage_embeddings(self) -> list:
        """Alle (document_id, chunk_text, vector)-Zeilen für die Matrix."""
        return self._conn.execute(
            "SELECT document_id, chunk_text, vector FROM council_anlage_embeddings "
            "ORDER BY document_id, chunk_idx"
        ).fetchall()

    def anlage_embeddings_version(self) -> tuple:
        count = self._conn.execute(
            "SELECT COUNT(*) FROM council_anlage_embeddings").fetchone()[0]
        data_version = self._conn.execute("PRAGMA data_version").fetchone()[0]
        return (count, data_version)

    def anlagen_by_ids(self, document_ids: list[int]) -> list[dict]:
        """Anzeige-Zeilen der Anlagen-Treffer, Reihenfolge der ids bleibt:
        Label, PDF-Link und die Vorlage (Nummer + Titel), zu der sie gehören."""
        if not document_ids:
            return []
        ph = ",".join("?" * len(document_ids))
        rows = self._conn.execute(
            f"SELECT a.document_id, a.label, a.url, a.kvonr, "
            f"       v.vorlage_nr, v.title AS vorlage_titel "
            f"FROM council_anlagen a LEFT JOIN council_vorlagen v ON v.kvonr = a.kvonr "
            f"WHERE a.document_id IN ({ph})", document_ids).fetchall()
        by_id = {r["document_id"]: dict(r) for r in rows}
        return [by_id[i] for i in document_ids if i in by_id]

    def decision_ids_for_vorlagen(self, vorlage_nrs: list[str]) -> dict[str, list[int]]:
        """vorlage_nr → Beschluss-ids (alle Beratungsstationen), neueste zuerst.
        Bildet Vorlagen-Chunk-Treffer der semantischen Suche auf zitierbare
        Beschlüsse ab."""
        nrs = sorted({(n or "").strip() for n in vorlage_nrs if n and str(n).strip()})
        if not nrs:
            return {}
        ph = ",".join("?" * len(nrs))
        rows = self._conn.execute(
            f"""SELECT d.vorlage_nr, d.id FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.vorlage_nr IN ({ph})
                ORDER BY cs.session_date DESC, d.id DESC""",
            nrs,
        ).fetchall()
        out: dict[str, list[int]] = {}
        for r in rows:
            out.setdefault(r["vorlage_nr"], []).append(r["id"])
        return out

    # ---- Laufende Bauleitplan-Beteiligungen (council/beteiligung.py) ----

    def save_beteiligungen(self, rows: list[dict]) -> dict:
        """Stand einpflegen und Verschwundenes als beendet markieren.

        Früher wurde die Tabelle je Lauf geleert und neu befüllt. Das war
        bequem, aber es vernichtete Wissen: Das Portal der Stadt zeigt
        ausschließlich Verfahren, zu denen GERADE eine Beteiligung möglich ist
        („zum aktuellen Zeitpunkt", so der Seitentitel) — abgeschlossene sind
        dort spurlos weg, auch über die direkte Adresse (geprüft 12.08.2026:
        ältere Planfall-IDs liefern nur noch eine leere Hülle). Wer die Zeile
        löscht, sobald sie aus der Liste fällt, hat sie für immer verloren.

        Deshalb: Bekanntes aktualisieren, Neues anlegen, Fehlendes auf
        `beendet` setzen (mit Datum des Laufs). So wächst über die Monate eine
        Historie, die es sonst nirgends gibt.
        """
        from datetime import datetime as _dt
        now = _dt.utcnow().isoformat(timespec="seconds")
        heute = now[:10]
        with self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS council_beteiligungen ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, titel TEXT NOT NULL, "
                "ort TEXT, schritt TEXT, von TEXT, bis TEXT, url TEXT NOT NULL, "
                "plan_nrs TEXT NOT NULL, fetched_at TEXT NOT NULL)"
            )
            # Nachrüsten für Bestände aus der Zeit vor der Historie.
            spalten = {r[1] for r in self._conn.execute("PRAGMA table_info(council_beteiligungen)")}
            if "status" not in spalten:
                self._conn.execute(
                    "ALTER TABLE council_beteiligungen ADD COLUMN status TEXT NOT NULL DEFAULT 'laufend'")
            if "beendet_am" not in spalten:
                self._conn.execute("ALTER TABLE council_beteiligungen ADD COLUMN beendet_am TEXT")
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_beteiligung_url_schritt "
                "ON council_beteiligungen(url, schritt)")

            neu = akt = 0
            gesehen: list[tuple[str, str]] = []
            for r in rows:
                url, schritt = r["url"], (r.get("schritt") or "")
                gesehen.append((url, schritt))
                cur = self._conn.execute(
                    "UPDATE council_beteiligungen SET titel = ?, ort = ?, von = ?, bis = ?, "
                    "plan_nrs = ?, fetched_at = ?, status = 'laufend', beendet_am = NULL "
                    "WHERE url = ? AND schritt = ?",
                    (r["titel"], r.get("ort"), r.get("von"), r.get("bis"),
                     json.dumps(r.get("plan_nrs") or [], ensure_ascii=False), now, url, schritt))
                if cur.rowcount:
                    akt += 1
                    continue
                self._conn.execute(
                    "INSERT INTO council_beteiligungen "
                    "(titel, ort, schritt, von, bis, url, plan_nrs, fetched_at, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'laufend')",
                    (r["titel"], r.get("ort"), schritt, r.get("von"), r.get("bis"), url,
                     json.dumps(r.get("plan_nrs") or [], ensure_ascii=False), now))
                neu += 1

            # Was nicht mehr in der Liste steht, ist gelaufen — nicht gelöscht.
            if gesehen:
                bedingung = " AND ".join(["NOT (url = ? AND schritt = ?)"] * len(gesehen))
                args: list = [heute]
                for u, sch in gesehen:
                    args += [u, sch]
                cur = self._conn.execute(
                    "UPDATE council_beteiligungen SET status = 'beendet', beendet_am = ? "
                    f"WHERE status = 'laufend' AND {bedingung}", args)
            else:
                cur = self._conn.execute(
                    "UPDATE council_beteiligungen SET status = 'beendet', beendet_am = ? "
                    "WHERE status = 'laufend'", (heute,))
            beendet = cur.rowcount
        return {"laufend": len(rows), "neu": neu, "aktualisiert": akt, "beendet": beendet}

    def list_beteiligungen(self, nur_laufende: bool = True) -> list[dict]:
        """Beteiligungen (plan_nrs als Liste) — die Handvoll Zeilen matcht der
        Aufrufer in Python gegen Beschluss-Titel. Standardmäßig nur laufende;
        mit ``nur_laufende=False`` auch die beendeten (Historie)."""
        try:
            spalten = {r[1] for r in self._conn.execute("PRAGMA table_info(council_beteiligungen)")}
            hat_status = "status" in spalten
            felder = "titel, ort, schritt, von, bis, url, plan_nrs" + (
                ", status, beendet_am" if hat_status else "")
            sql = f"SELECT {felder} FROM council_beteiligungen"
            if nur_laufende and hat_status:
                sql += " WHERE status = 'laufend'"
            rows = self._conn.execute(sql).fetchall()
        except sqlite3.OperationalError:  # Tabelle entsteht erst mit dem ersten Lauf
            return []
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["plan_nrs"] = json.loads(d.get("plan_nrs") or "[]")
            except ValueError:
                d["plan_nrs"] = []
            out.append(d)
        return out

    # ---- Haushalt als Geldfragen-Quelle (Tim, 09.08.) ----

    def haushalt_fuer_begriffe(self, begriffe: list[str], limit: int = 3) -> list[dict]:
        """Teilhaushalts-Zeilen des neuesten Jahres, deren Bereich einen der
        Suchbegriffe trägt („Verkehr" → „Verkehr und Straßenbau"); fragt jemand
        nach dem Haushalt insgesamt, kommt die Summenzeile. Für den
        Geld-Kontext der KI-Frage — Plan-Zahlen, klar getrennt von Beschlüssen."""
        try:
            jahr = self._conn.execute("SELECT MAX(year) FROM council_haushalt").fetchone()[0]
        except sqlite3.OperationalError:
            return []
        if not jahr:
            return []
        woerter = [w.lower() for w in begriffe if len(w) >= 4][:10]
        rows = self._conn.execute(
            "SELECT year, bereich, ertraege, aufwendungen, ergebnis, is_summe "
            "FROM council_haushalt WHERE year = ?", (jahr,)).fetchall()
        out = []
        for r in rows:
            b = (r["bereich"] or "").lower()
            if r["is_summe"]:
                if any(w in ("haushalt", "gesamthaushalt", "haushaltsplan") for w in woerter):
                    out.append(dict(r))
                continue
            if any(w in b for w in woerter):
                out.append(dict(r))
        return out[:limit]

    # ---- Teilvoten aus raw_result (welche Fraktion stimmte wie) ----

    def save_decision_votes(self, decision_id: int, votes: list[tuple[str, str]]) -> None:
        """Geparste (faction, stance)-Zeilen eines Beschlusses ersetzen."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_decision_votes WHERE decision_id = ?", (decision_id,))
            self._conn.executemany(
                "INSERT OR IGNORE INTO council_decision_votes (decision_id, faction, stance) "
                "VALUES (?, ?, ?)",
                [(decision_id, f, s) for f, s in votes],
            )

    def decision_votes_for(self, decision_ids: list[int]) -> dict[int, list[dict]]:
        """decision_id → [{faction, stance}] für Anzeige/Auswertung."""
        if not decision_ids:
            return {}
        ph = ",".join("?" * len(decision_ids))
        rows = self._conn.execute(
            f"SELECT decision_id, faction, stance FROM council_decision_votes "
            f"WHERE decision_id IN ({ph}) ORDER BY faction", decision_ids,
        ).fetchall()
        out: dict[int, list[dict]] = {}
        for r in rows:
            out.setdefault(r["decision_id"], []).append(
                {"faction": r["faction"], "stance": r["stance"]})
        return out

    def decisions_with_raw_result(self) -> list[dict]:
        """Alle Beschlüsse mit Abstimmungssatz — Eingabe für den Teilvoten-Backfill."""
        return [dict(r) for r in self._conn.execute(
            "SELECT id, raw_result FROM council_decisions "
            "WHERE raw_result IS NOT NULL AND raw_result != ''"
        ).fetchall()]

    # ---- Pressemitteilungen der Stadt (council/presse.py) ----

    def save_presse(self, url: str, news_id: int | None, titel: str,
                    datum: str | None, text: str) -> int:
        """Upsert einer Pressemitteilung (Schlüssel: url) inkl. FTS-Zeile.
        Liefert die Zeilen-id."""
        from datetime import datetime as _dt
        now = _dt.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT INTO council_presse (url, news_id, titel, datum, text, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(url) DO UPDATE SET news_id=excluded.news_id, "
                "titel=excluded.titel, datum=excluded.datum, text=excluded.text, "
                "fetched_at=excluded.fetched_at",
                (url, news_id, titel, datum, text, now),
            )
            pid = self._conn.execute(
                "SELECT id FROM council_presse WHERE url = ?", (url,)).fetchone()[0]
            self._conn.execute("DELETE FROM council_presse_fts WHERE rowid = ?", (pid,))
            self._conn.execute(
                "INSERT INTO council_presse_fts(rowid, content) VALUES (?, REPLACE(?, 'ß', 'ss'))",
                (pid, f"{titel} {text[:8000]}"),
            )
        return pid

    def presse_urls(self) -> set[str]:
        """Alle bekannten PM-URLs — der Backfill überspringt Vorhandenes."""
        return {r[0] for r in self._conn.execute("SELECT url FROM council_presse").fetchall()}

    def presse_by_ids(self, ids: list[int]) -> list[dict]:
        """PM-Zeilen (ohne Volltext-Riesen: Text auf 600 Zeichen gekürzt) in id-Reihenfolge."""
        if not ids:
            return []
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT id, url, titel, datum, substr(text, 1, 600) AS auszug "
            f"FROM council_presse WHERE id IN ({ph})", ids).fetchall()
        by_id = {r["id"]: dict(r) for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    def search_presse_fts(self, query: str, limit: int = 20) -> list[tuple]:
        """BM25 über Pressemitteilungen → [(presse_id, score, snippet)] wie bei
        den Beschlüssen (search_decisions_fts)."""
        terms = [t for t in re.findall(r"[0-9a-zäöü]+", query.lower().replace("ß", "ss")) if len(t) >= 3][:12]
        if not terms:
            return []
        try:
            rows = self._conn.execute(
                "SELECT rowid, rank, snippet(council_presse_fts, 0, '', '', ' … ', 16) "
                "FROM council_presse_fts WHERE council_presse_fts MATCH ? ORDER BY rank LIMIT ?",
                (" OR ".join(terms), limit)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [(r[0], -float(r[1]), r[2] or "") for r in rows]

    def presse_missing_embeddings(self) -> list[dict]:
        """PMs, deren Chunk-Vektoren fehlen oder deren Text sich geändert hat
        (SHA-256-Abgleich, analog vorlagen_missing_embeddings)."""
        import hashlib
        stored = dict(self._conn.execute(
            "SELECT presse_id, MIN(text_hash) FROM council_presse_embeddings GROUP BY presse_id"
        ).fetchall())
        out = []
        for r in self._conn.execute("SELECT id, titel, text FROM council_presse").fetchall():
            blob = f"{r['titel']}\n{r['text']}"
            h = hashlib.sha256(blob.encode("utf-8", "replace")).hexdigest()
            if stored.get(r["id"]) != h:
                out.append({"id": r["id"], "text": blob, "text_hash": h})
        return out

    def replace_presse_embeddings(self, presse_id: int, text_hash: str,
                                  chunks: list[tuple[str, bytes]]) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_presse_embeddings WHERE presse_id = ?", (presse_id,))
            self._conn.executemany(
                "INSERT INTO council_presse_embeddings "
                "(presse_id, chunk_idx, text_hash, chunk_text, vector) VALUES (?, ?, ?, ?, ?)",
                [(presse_id, i, text_hash, t, v) for i, (t, v) in enumerate(chunks)],
            )

    def get_presse_embeddings(self) -> list:
        return self._conn.execute(
            "SELECT presse_id, chunk_text, vector FROM council_presse_embeddings "
            "ORDER BY presse_id, chunk_idx").fetchall()

    def presse_embeddings_version(self) -> tuple:
        count = self._conn.execute("SELECT COUNT(*) FROM council_presse_embeddings").fetchone()[0]
        data_version = self._conn.execute("PRAGMA data_version").fetchone()[0]
        return (count, data_version)

    # ---- field recaps (auto-generated LLM summaries per policy field) ----

    def save_field_recap(self, policy_field: str, summary: str, n_decisions: int,
                         period_from: str, period_to: str, generated_at: str) -> None:
        """Upsert the recap for one policy field (replaces the previous one)."""
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_field_recaps "
                "(policy_field, summary, n_decisions, period_from, period_to, generated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (policy_field, summary, n_decisions, period_from, period_to, generated_at),
            )

    def get_field_recaps(self) -> list[dict]:
        """All field recaps, busiest field first."""
        rows = self._conn.execute(
            "SELECT policy_field, summary, n_decisions, period_from, period_to, generated_at "
            "FROM council_field_recaps ORDER BY n_decisions DESC, policy_field"
        ).fetchall()
        return [dict(r) for r in rows]

    def field_recaps_by_key(self) -> dict[str, dict]:
        """{policy_field: recap-row} — for the cron's freshness check."""
        return {r["policy_field"]: r for r in self.get_field_recaps()}

    def get_similar(self, decision_id: int, limit: int = 5) -> list[dict]:
        """The most similar decisions to ``decision_id`` (precomputed), best first.
        Near-duplicate twins (the same matter in another committee, or a recurring
        series) are collapsed via the normalised title, so the neighbours shown are
        genuinely distinct rather than the Ausschuss/Rat copy of this very decision."""
        base = self._conn.execute(
            "SELECT title, vorlage_nr FROM council_decisions WHERE id = ?", (decision_id,)
        ).fetchone()
        rows = self._conn.execute(
            """SELECT d.id, d.title, d.vorlage_nr, d.summary, d.policy_field, d.outcome,
                      cs.session_date, cs.committee, sl.score
               FROM council_similar sl
               JOIN council_decisions d ON d.id = sl.neighbor_id
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE sl.decision_id = ? ORDER BY sl.rank LIMIT ?""",
            (decision_id, limit * 5),
        ).fetchall()
        seen = set(_dedup_keys(base["title"], base["vorlage_nr"], decision_id)) if base else set()
        out: list[dict] = []
        for r in rows:
            keys = _dedup_keys(r["title"], r["vorlage_nr"], r["id"])
            if any(k in seen for k in keys):
                continue
            seen.update(keys)
            out.append(dict(r))
            if len(out) >= limit:
                break
        return out

    def orte_fuer_decisions(self, ids: list[int]) -> dict[int, dict]:
        """Erste verortete Orts-Entität je Beschluss (5a/I-10) — Futter für die
        Mini-Karte unter KI-Antworten. Nur kind='ort': der Sitz einer
        Organisation wäre als Pin irreführend. Größte Entität (n) zuerst."""
        if not ids:
            return {}
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"""SELECT l.decision_id, e.name, m.lat, m.lon
                FROM council_entity_links l
                JOIN council_entities e ON e.id = l.entity_id
                JOIN council_entity_meta m ON m.slug = e.slug
                WHERE l.decision_id IN ({ph}) AND m.lat IS NOT NULL
                  AND e.kind = 'ort'
                ORDER BY e.n DESC""",
            ids,
        ).fetchall()
        out: dict[int, dict] = {}
        for r in rows:
            out.setdefault(r["decision_id"], {"ort_name": r["name"],
                                              "lat": r["lat"], "lon": r["lon"]})
        return out

    # ---- Wortbeiträge aus Protokollen (Task 16) ----------------------------

    def save_wortbeitraege(self, ksinr: int, rows: list[dict]) -> int:
        """Beiträge einer Sitzung ersetzen (ein Protokoll = eine Wahrheit) —
        FTS und Embeddings der alten Zeilen werden mit abgeräumt. Auch ein
        LEERES Ergebnis markiert das Protokoll als erledigt (Formalien-
        Niederschriften), sonst kostete es jede Nacht erneut einen LLM-Call."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            # DELETEs per Subquery über ksinr, NICHT über eine vorab gelesene
            # ID-Liste: Läuft ein zweiter Save desselben Protokolls parallel,
            # wäre die Liste beim eigenen BEGIN schon veraltet und FTS-/
            # Embedding-Zeilen des anderen blieben als Waisen zurück
            # (Review-Befund zu #387).
            self._conn.execute(
                "DELETE FROM council_wortbeitraege_fts WHERE rowid IN "
                "(SELECT id FROM council_wortbeitraege WHERE ksinr = ?)", (ksinr,))
            self._conn.execute(
                "DELETE FROM council_wortbeitraege_embeddings WHERE wb_id IN "
                "(SELECT id FROM council_wortbeitraege WHERE ksinr = ?)", (ksinr,))
            self._conn.execute("DELETE FROM council_wortbeitraege WHERE ksinr = ?", (ksinr,))
            self._conn.execute(
                "UPDATE council_protocols SET wortbeitraege_extracted_at = ? WHERE ksinr = ?",
                (now, ksinr))
            n = 0
            for pos, r in enumerate(rows):
                text = (r.get("text") or "").strip()
                if not text:
                    continue
                cur = self._conn.execute(
                    "INSERT INTO council_wortbeitraege "
                    "(ksinr, position, art, top, sprecher, partei, text, antwort, extracted_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (ksinr, pos, r.get("art") or "rede", r.get("top"),
                     r.get("sprecher"), r.get("partei"), text[:2000],
                     (r.get("antwort") or "").strip()[:2000] or None, now))
                inhalt = " ".join(x for x in (r.get("sprecher"), r.get("partei"), r.get("top"),
                                              text, r.get("antwort")) if x)
                self._conn.execute(
                    "INSERT INTO council_wortbeitraege_fts(rowid, content) VALUES (?, REPLACE(?, 'ß', 'ss'))",
                    (cur.lastrowid, inhalt))
                n += 1
            return n

    def aktive_fraktionen(self, monate: int = 12, min_beitraege: int = 5) -> list[str]:
        """Fraktions-Labels mit nennenswerten Wortbeiträgen im Zeitraum — die
        deterministische „Wer sitzt gerade im Rat"-Liste für die Vollständig-
        keits-Zeile des Parteien-Bausteins (Tims Direktive 10.08.), ohne
        kuratierte Stammdaten."""
        rows = self._conn.execute(
            "SELECT w.partei, COUNT(*) n FROM council_wortbeitraege w "
            "JOIN council_sessions s ON s.ksinr = w.ksinr "
            "WHERE w.partei IS NOT NULL AND w.partei != '' "
            "AND s.session_date >= date('now', ?) "
            "GROUP BY w.partei HAVING n >= ? ORDER BY n DESC",
            (f"-{int(monate)} months", int(min_beitraege))).fetchall()
        return [r[0] for r in rows]

    def protocol_raw_text(self, ksinr: int) -> str | None:
        row = self._conn.execute(
            "SELECT raw_text FROM council_protocols WHERE ksinr = ?", (ksinr,)).fetchone()
        return row[0] if row else None

    def ksinr_ohne_wortbeitraege(self, limit: int = 0) -> list[int]:
        """Protokolle mit Text, deren Wortbeitrags-Extraktion noch aussteht.
        Marker-Spalte statt NOT EXISTS: auch ein leeres Ergebnis gilt als
        erledigt; nur echte Fehlschläge (kein Save) kommen wieder dran."""
        sql = ("SELECT p.ksinr FROM council_protocols p "
               "WHERE p.raw_text IS NOT NULL AND p.status = 'ok' "
               "AND p.wortbeitraege_extracted_at IS NULL "
               "ORDER BY p.ksinr DESC")
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r[0] for r in self._conn.execute(sql).fetchall()]

    def wortbeitrag_ids_nach_art(self, art: str) -> list[int]:
        """Alle Wortbeitrags-ids einer Art — Filter für den Zusagen-Kanal.
        Klein genug (1.437 Zusagen), um sie je Frage zu holen."""
        return [r[0] for r in self._conn.execute(
            "SELECT id FROM council_wortbeitraege WHERE art = ?", (art,))]

    def wortbeitraege_by_ids(self, ids: list[int]) -> list[dict]:
        if not ids:
            return []
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"""SELECT w.id, w.ksinr, w.seite, w.art, w.top, w.sprecher, w.partei,
                       w.text, w.antwort, cs.committee, cs.session_date
                FROM council_wortbeitraege w
                LEFT JOIN council_sessions cs ON cs.ksinr = w.ksinr
                WHERE w.id IN ({ph})""", ids).fetchall()
        by_id = {r["id"]: dict(r) for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    def protokoll_seiten_grundlage(self, ksinr: int) -> tuple[str, list[int]] | None:
        """(raw_text, page_offsets) eines Protokolls — oder None, wenn die
        Offsets fehlen (Altbestand vor dem Backfill)."""
        row = self._conn.execute(
            "SELECT raw_text, page_offsets FROM council_protocols WHERE ksinr = ?",
            (ksinr,)).fetchone()
        if row is None or not row["raw_text"] or not row["page_offsets"]:
            return None
        try:
            offsets = json.loads(row["page_offsets"])
        except (ValueError, TypeError):
            return None
        if not isinstance(offsets, list) or not offsets:
            return None
        return row["raw_text"], [int(o) for o in offsets]

    def wortbeitraege_ohne_seite(self, ksinr: int) -> list[dict]:
        """Beiträge eines Protokolls, deren Fundstellen-Seite noch fehlt."""
        return [dict(r) for r in self._conn.execute(
            "SELECT id, sprecher, text FROM council_wortbeitraege "
            "WHERE ksinr = ? AND seite IS NULL", (ksinr,))]

    def set_wortbeitrag_seite(self, wb_id: int, seite: int) -> None:
        with self._conn:
            self._conn.execute("UPDATE council_wortbeitraege SET seite = ? WHERE id = ?",
                               (seite, wb_id))

    def ksinr_mit_beitraegen_ohne_offsets(self, limit: int = 0) -> list[int]:
        """Protokolle mit Wortbeiträgen, aber ohne Seiten-Offsets — die
        Arbeitsliste des Backfills (Re-Download nötig)."""
        sql = ("SELECT DISTINCT w.ksinr FROM council_wortbeitraege w "
               "JOIN council_protocols p ON p.ksinr = w.ksinr "
               "WHERE p.page_offsets IS NULL AND p.document_url IS NOT NULL "
               "ORDER BY w.ksinr DESC")
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r[0] for r in self._conn.execute(sql)]

    def replace_protocol_text(self, ksinr: int, raw_text: str, n_pages: int,
                              page_offsets: list[int]) -> None:
        """Backfill: Volltext + Seiten-Offsets gemeinsam ersetzen — die
        Offsets gelten exakt für DIESEN Text, getrennt gespeichert wären
        sie wertlos."""
        with self._conn:
            self._conn.execute(
                "UPDATE council_protocols SET raw_text = ?, n_pages = ?, page_offsets = ? "
                "WHERE ksinr = ?",
                (raw_text, n_pages, json.dumps(page_offsets), ksinr))

    def protokoll_urls_fuer(self, ksinrs: list[int | None]) -> dict[int, str]:
        """ksinr → getfile-URL des öffentlichen Protokoll-PDFs. Macht die
        Wortbeitrags-Belege der KI-Frage nachlesbar: Jeder Beitrag stammt aus
        genau einem Protokoll, und dessen URL steht längst in der DB."""
        ids = sorted({int(k) for k in ksinrs if k})
        if not ids:
            return {}
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT ksinr, document_url FROM council_protocols "
            f"WHERE ksinr IN ({ph}) AND document_url IS NOT NULL", ids).fetchall()
        return {r["ksinr"]: r["document_url"] for r in rows}

    # Sammel-TOPs: Hier landet alles, was sonst nirgends hingehört. Ein Treffer
    # darauf koppelt keine Debatte ZUR SACHE, sondern eine Wundertüte.
    _SAMMEL_TOPS = ("anfragen und anregungen", "einwohnerfragestunde",
                    "genehmigung der tagesordnung", "mitteilungen",
                    "verschiedenes", "niederschrift")

    @staticmethod
    def _top_schluessel(text: str | None) -> tuple[str | None, str]:
        """TOP-Angabe → (Nummer, normalisierter Titel).

        Die Extraktion schreibt mal „10 Fliegerhorst …“, mal nur den Titel, mal
        „Ö 6.1“ — und die Tagesordnung führt denselben Punkt gern mit Zusatz
        („- Bericht“, „- Beschluss“). Beides wird hier eingeebnet, damit
        Beschluss und Wortbeitrag über dieselbe Station zusammenfinden.
        """
        t = " ".join((text or "").split())
        m = re.match(r"^(?:ö|n|ö\.|n\.)?\s*(\d+(?:\.\d+)*)\b[\s.:-]*(.*)$", t, re.I)
        nummer, rest = (m.group(1), m.group(2)) if m else (None, t)
        rest = re.sub(r"\s*[-–]\s*(bericht|beschluss|sachstandsbericht|antrag|"
                      r"vorlage|sachstand)\s*$", "", rest, flags=re.I)
        rest = re.sub(r"[^0-9a-zäöüß]+", " ", rest.lower().replace("ß", "ss")).strip()
        return nummer, rest

    def wortbeitraege_zu_beschluessen(self, decisions: list[dict], max_gesamt: int = 6,
                                      max_je_top: int = 4) -> list[dict]:
        """Die Debatte, die zu diesen Beschlüssen GEHÖRT — über die Station,
        nicht über Wortähnlichkeit.

        Warum es das braucht: Die semantische Suche findet nur Beiträge, die im
        Wortfeld der Frage liegen. Die Aussprache zu einem Bericht benutzt aber
        die Sprache der Sache — auf die Frage „Sondermüll im Schießstand?“
        antwortet das Protokoll mit Vinylchlorid, Zu- und Abstrom, Messpunkten.
        Diese Beiträge fielen durch jedes Wortfeld-Raster, obwohl sie zum
        zitierten Bericht gehören (Befund an der Fliegerhorst-Antwort vom
        10.08.2026). Zugehörigkeit ist hier das bessere Signal als Ähnlichkeit.

        Gekoppelt wird über Sitzung (ksinr) UND Tagesordnungspunkt; Sammel-TOPs
        („Anfragen und Anregungen“) bleiben außen vor, und die Menge ist hart
        gedeckelt — der Kanal soll ergänzen, nicht den Kontext fluten.
        """
        stationen: dict[int, list[tuple[str | None, str, int]]] = {}
        for d in decisions:
            ks = d.get("ksinr")
            if not ks:
                continue
            nummer, titel = self._top_schluessel(d.get("title"))
            # item_number ist die verlässlichere Nummer (title trägt sie selten).
            nr = str(d.get("item_number") or "").strip() or nummer
            if not titel or any(s in titel for s in self._SAMMEL_TOPS):
                continue
            stationen.setdefault(int(ks), []).append((nr, titel, d["id"]))
        if not stationen:
            return []
        ph = ",".join("?" * len(stationen))
        rows = self._conn.execute(
            f"""SELECT w.id, w.ksinr, w.seite, w.art, w.top, w.sprecher, w.partei,
                       w.text, w.antwort, cs.committee, cs.session_date
                FROM council_wortbeitraege w
                LEFT JOIN council_sessions cs ON cs.ksinr = w.ksinr
                WHERE w.ksinr IN ({ph}) AND w.top IS NOT NULL
                ORDER BY cs.session_date DESC, w.id""", list(stationen)).fetchall()
        treffer: list[dict] = []
        je_top: dict[tuple[int, str], int] = {}
        for r in rows:
            w_nr, w_titel = self._top_schluessel(r["top"])
            if not w_titel or any(s in w_titel for s in self._SAMMEL_TOPS):
                continue
            for d_nr, d_titel, did in stationen[r["ksinr"]]:
                # Titel-Enthaltensein in beide Richtungen: Die Tagesordnung
                # kürzt mal den Beschluss-, mal den Protokoll-Titel.
                passt = (d_titel in w_titel or w_titel in d_titel) or (
                    bool(w_nr) and bool(d_nr) and w_nr == d_nr)
                if not passt:
                    continue
                key = (r["ksinr"], d_titel)
                if je_top.get(key, 0) >= max_je_top:
                    break
                je_top[key] = je_top.get(key, 0) + 1
                treffer.append({**dict(r), "zu_beschluss": did})
                break
            if len(treffer) >= max_gesamt:
                break
        return treffer

    def search_wortbeitraege_fts(self, query: str, limit: int = 20) -> list[tuple]:
        """BM25 über die Beiträge → ``[(wb_id, score)]``; Fehler → leer.
        Term-Aufbereitung wie bei search_presse_fts (OR-Verknüpfung)."""
        terms = [t for t in re.findall(r"[0-9a-zäöü]+", query.lower().replace("ß", "ss"))
                 if len(t) >= 3][:12]
        if not terms:
            return []
        try:
            rows = self._conn.execute(
                "SELECT rowid, rank FROM council_wortbeitraege_fts "
                "WHERE council_wortbeitraege_fts MATCH ? ORDER BY rank LIMIT ?",
                (" OR ".join(terms), limit)).fetchall()
            return [(r[0], -float(r[1])) for r in rows]
        except sqlite3.OperationalError:
            return []

    def wortbeitraege_missing_embeddings(self) -> list[dict]:
        rows = self._conn.execute(
            """SELECT w.id, w.text, w.sprecher, w.top FROM council_wortbeitraege w
               LEFT JOIN council_wortbeitraege_embeddings e ON e.wb_id = w.id
               WHERE e.wb_id IS NULL""").fetchall()
        return [dict(r) for r in rows]

    def replace_wortbeitrag_embedding(self, wb_id: int, text_hash: str, vector: bytes) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_wortbeitraege_embeddings (wb_id, text_hash, vector) "
                "VALUES (?, ?, ?)", (wb_id, text_hash, vector))

    def wortbeitraege_embedding_rows(self) -> list[tuple]:
        return self._conn.execute(
            "SELECT wb_id, vector FROM council_wortbeitraege_embeddings").fetchall()

    def partei_meinungen_cache_get(self, schluessel: str, max_age_days: int = 14):
        row = self._conn.execute(
            "SELECT ergebnis FROM council_partei_meinungen_cache "
            "WHERE schluessel = ? AND created_at >= datetime('now', ?)",
            (schluessel, f"-{int(max_age_days)} days")).fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except (ValueError, TypeError):
            return None

    def partei_meinungen_cache_set(self, schluessel: str, frage: str, ergebnis) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_partei_meinungen_cache "
                "(schluessel, frage, ergebnis, created_at) VALUES (?, ?, ?, datetime('now'))",
                (schluessel, frage[:300], json.dumps(ergebnis, ensure_ascii=False)))
            # Alt-Einträge räumen sich beim Schreiben mit weg (klein halten).
            self._conn.execute(
                "DELETE FROM council_partei_meinungen_cache "
                "WHERE created_at < datetime('now', '-30 days')")

    def wortbeitraege_embeddings_version(self) -> str:
        """Billiger Cache-Schlüssel für die In-Memory-Matrix."""
        row = self._conn.execute(
            "SELECT COUNT(*), COALESCE(MAX(wb_id), 0) "
            "FROM council_wortbeitraege_embeddings").fetchone()
        return f"{row[0]}-{row[1]}"

    def save_qa_feedback(self, frage: str, antwort_auszug: str | None,
                         bewertung: str, grund: str | None,
                         user_id: int | None = None) -> None:
        """Daumen hoch/runter zu einer KI-Antwort (5a/I-03).

        Ein Konto hat je Frage **eine** Stimme: Der nachgereichte Grund und die
        korrigierte Bewertung (Daumen runter → hoch) überschreiben die frühere
        Zeile, statt sich als widersprüchliches Paar in der Tabelle zu stapeln —
        sonst zählte jede Meinungsänderung doppelt. Anonyme Rückmeldungen haben
        keinen Schlüssel und werden weiterhin angehängt.
        """
        if bewertung not in ("up", "down"):
            raise ValueError(f"bewertung muss up/down sein, nicht {bewertung!r}")
        now = datetime.utcnow().isoformat(timespec="seconds")
        werte = (frage[:300], (antwort_auszug or "")[:500] or None, bewertung,
                 (grund or "").strip()[:500] or None, user_id, now)
        with self._conn:
            if user_id is not None:
                vorher = self._conn.execute(
                    "SELECT id FROM council_qa_feedback WHERE user_id = ? AND frage = ? "
                    "ORDER BY id DESC LIMIT 1", (user_id, werte[0])).fetchone()
                if vorher:
                    self._conn.execute(
                        "UPDATE council_qa_feedback SET antwort_auszug = ?, bewertung = ?, "
                        "grund = ?, created = ? WHERE id = ?",
                        (werte[1], bewertung, werte[3], now, vorher[0]))
                    return
            self._conn.execute(
                "INSERT INTO council_qa_feedback (frage, antwort_auszug, bewertung, grund, user_id, created) "
                "VALUES (?, ?, ?, ?, ?, ?)", werte,
            )

    def juengste_sitzungen_mit_beschluessen(self, limit: int = 2) -> list[dict]:
        """Die jüngsten vergangenen Sitzungen, zu denen Beschlüsse extrahiert
        sind — Futter für frische KI-Beispielfragen (5a/I-07). ``top_titel``
        nennt den wichtigsten Beschluss der Sitzung, damit ein Vorschlag
        konkret nach dem Inhalt fragen kann statt nur nach dem Datum."""
        rows = self._conn.execute(
            """SELECT cs.committee, cs.session_date, COUNT(*) AS n,
                      (SELECT d2.title FROM council_decisions d2
                       WHERE d2.ksinr = cs.ksinr AND d2.kind = 'decision'
                         AND d2.title IS NOT NULL
                       ORDER BY COALESCE(d2.importance, 0) DESC, d2.id LIMIT 1) AS top_titel
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE d.kind = 'decision'
               GROUP BY d.ksinr ORDER BY cs.session_date DESC LIMIT ?""",
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_decisions_by_ids(self, ids: list[int]) -> list[dict]:
        """Fetch decisions by id, preserving the given order (for Q&A citations).

        Liefert auch Abstimmung (vote/gegenstimmen/enthaltungen/raw_result) und
        amount_eur mit: raw_result geht bei strittigen Beschlüssen in den
        QA-Kontext (dort stehen oft die Fraktionen der Gegenstimmen), und die
        Fallback-Folgefragen in council/qa.py prüfen gegenstimmen/amount_eur —
        ohne diese Felder liefen die Zweige ins Leere."""
        if not ids:
            return []
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"""SELECT d.id, d.title, d.summary, d.beschluss, d.vorlage_nr,
                       d.kvonr,
                       -- ksinr + item_number: Adresse der Station in der
                       -- Sitzung — darüber koppelt wortbeitraege_zu_beschluessen
                       -- die Aussprache an den Beschluss.
                       d.ksinr, d.item_number,
                       d.policy_field, d.outcome, d.impact, d.impact_reason,
                       d.vote, d.gegenstimmen, d.enthaltungen, d.raw_result,
                       d.amount_eur, d.factions, d.abweichung,
                       v.amt, v.klima_check,
                       cs.session_date, cs.committee
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                LEFT JOIN council_vorlagen v ON v.kvonr = d.kvonr
                WHERE d.id IN ({ph})""",
            ids,
        ).fetchall()
        by_id = {r["id"]: dict(r) for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    def antrag_decision_ids(self, party: str, terms: str = "", limit: int = 12) -> list[int]:
        """Beschluss-ids, bei denen die Fraktion/Gruppe ``party`` als Antragsteller
        auftritt — aus dem factions-Feld des Protokolls ODER über eine als Antrag
        erkannte Anlage der Vorlage. Mit ``terms`` wird thematisch eingegrenzt
        (Schnitt mit der FTS-Trefferliste), sonst kommen die neuesten zuerst.
        Für das Fragetyp-Routing der KI-Frage (typ=partei)."""
        like = f'%{party.strip()}%'
        rows = self._conn.execute(
            """SELECT DISTINCT d.id FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               LEFT JOIN council_vorlagen v ON v.vorlage_nr = d.vorlage_nr
               LEFT JOIN council_anlagen a ON a.kvonr = v.kvonr AND a.is_antrag = 1
               WHERE d.kind = 'decision'
                 AND (d.factions LIKE ? OR a.antragsteller LIKE ?)
               ORDER BY cs.session_date DESC, d.id DESC LIMIT 400""",
            (like, like),
        ).fetchall()
        ids = [r["id"] for r in rows]
        if terms:
            fts = {i for i, *_ in self.search_decisions_fts(terms, limit=250)}
            thematisch = [i for i in ids if i in fts]
            # Thematischer Schnitt zuerst; ohne Schnitt-Treffer die neuesten Anträge
            # der Fraktion — besser als gar kein Partei-Signal im Kandidaten-Pool.
            ids = thematisch or ids
        return ids[:limit]

    def find_decision_ids(self, *, vorlage_nr: str | None = None, committee: str | None = None,
                          session_date: str | None = None, title_like: str | None = None) -> list[int]:
        """Beschluss-ids über natürliche Schlüssel statt AUTOINCREMENT-ids.

        Für DB-portable Eval-Gold-Cases (eval/cases_qa.json): Vorlagen-Nummer,
        Sitzungsdatum und Titel sind auf jeder Kopie der Datenbank gleich, die
        ids nicht. Filter sind UND-verknüpft, mindestens einer ist Pflicht;
        Teilabstimmungen bleiben außen vor (nicht eigenständig zitierbar)."""
        conds, params = ["d.kind = 'decision'"], []
        if vorlage_nr:
            conds.append("d.vorlage_nr = ?"); params.append(str(vorlage_nr).strip())
        if committee:
            conds.append("cs.committee LIKE ?"); params.append(f"%{committee.strip()}%")
        if session_date:
            conds.append("cs.session_date = ?"); params.append(str(session_date).strip())
        if title_like:
            conds.append("d.title LIKE ?"); params.append(f"%{title_like.strip()}%")
        if len(conds) == 1:
            raise ValueError("find_decision_ids braucht mindestens einen Filter")
        rows = self._conn.execute(
            f"""SELECT d.id FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE {' AND '.join(conds)}
                ORDER BY cs.session_date DESC, d.id DESC""",
            params,
        ).fetchall()
        return [r["id"] for r in rows]

    def get_protocols_raw(self) -> list[dict]:
        """All stored protocols with their raw text — for re-extraction without
        re-downloading the PDFs."""
        rows = self._conn.execute(
            "SELECT ksinr, document_id, document_url, raw_text, n_pages "
            "FROM council_protocols WHERE raw_text IS NOT NULL AND raw_text != ''"
        ).fetchall()
        return [dict(r) for r in rows]
