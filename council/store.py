from __future__ import annotations

import contextlib
import logging
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import sqlite3

from .scraper import CouncilSession
from .parties import order_key, parties_for_faction
from . import importance as _importance
from council.kontaktdaten import maskieren



CONCRETE_LOCATION_KINDS = {
    "strasse", "platz", "gebaeude", "gewaesser",
    "anlage", "bauwerk", "verkehrsweg",
}


def _norm_title(t: str) -> str:
    """Normalised title for dedup: drops amounts, years, doc-suffixes and punctuation
    so the same matter across committees ('… - Beschluss' vs '…') and recurring series
    ('… 11.716.000 Euro …' vs '… 10.632.200 Euro …') collapse to one key."""
    t = (t or "").lower()
    t = re.sub(r"[\d.,]+", " ", t)  # amounts, years, budget numbers
    t = re.sub(r"\b(euro|eur|mio|mrd|beschluss|bericht|antrag|vorlage)\b", " ", t)
    t = re.sub(r"[^a-zäöüß ]", " ", t)  # punctuation, €, dashes
    return re.sub(r"\s+", " ", t).strip()


def _dedup_keys(title: str, template_number, decision_id: int) -> list[str]:
    """Collapse keys for a decision: the base Vorlage-Nr (strongest signal — same
    matter across committees/revisions, '22/0348' == '22/0348/1', and robust to title
    spelling variants) and the normalised title (catches recurring series under
    different Vorlagen). Two rows collapse if they share EITHER. Short/sparse titles
    fall back to the id so distinct tiny-title decisions are never merged."""
    keys: list[str] = []
    if template_number and str(template_number).strip():
        # Keep the base Vorlage (first two segments): "22/0348/1" → "22/0348".
        keys.append("v:" + "/".join(str(template_number).strip().split("/")[:2]))
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
    template_number   TEXT,
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
    -- Nur für Dringlichkeitsanträge gefüllt (council/dringlichkeit.py): Sie
    -- haben keine Vorlage, ihr ganzer Inhalt steht in DIESEM PDF. Alle
    -- anderen Zeilen-Dokumente bleiben leer — sie hängen an einem Punkt, der
    -- seine Vorlage hat, und ein Download je Anlage bei jedem Scrape wäre
    -- teuer für nichts.
    raw_text     TEXT,
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

-- Kartentext für Social Media je TOP. Eigene Tabelle aus zwei Gründen:
-- save_session ERSETZT die Items einer Sitzung (eine Spalte wäre bei jeder
-- Tagesordnungs-Änderung weg und müsste neu bezahlt werden, genau wie bei
-- agenda_item_impact), und der Text hat einen anderen Auftrag als die
-- beiden vorhandenen Felder.
--
-- Warum überhaupt ein dritter Text (Tims Vorgabe 30.08.26):
--   agenda_item_summaries.summary entsteht ALLEIN AUS DEM TITEL („Du kennst
--     nur den Titel des Punktes" steht wörtlich in seinem Prompt) — er kann
--     die Überschrift nur umformulieren.
--   agenda_item_impact.reason kennt die Vorlage, begründet aber eine
--     RANGFOLGE und wertet deshalb („Trägt ein hohes finanzielles Risiko").
--     Zum Sortieren richtig; unter einem eigenen Absender auf Instagram wird
--     daraus eine Meinung des Absenders zur Sache.
-- Dieser Text bekommt Vorlage UND Anlagen und darf nicht werten.
CREATE TABLE IF NOT EXISTS agenda_item_social (
    ksinr       INTEGER NOT NULL,
    item_number TEXT NOT NULL,
    text        TEXT NOT NULL,
    quelle      TEXT NOT NULL,  -- was das Modell sah: "vorlage+anlagen", "vorlage", "titel"
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
    official_text    TEXT,
    outcome      TEXT,                          -- angenommen|abgelehnt|vertagt|zur_kenntnis|kein_beschluss
    vote         TEXT,                          -- einstimmig|mehrheitlich|null
    no_votes INTEGER,
    abstentions INTEGER,
    factions     TEXT,                          -- JSON array
    template_number   TEXT,
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
    def __init__(self, path: str | Path, ratslotse_db_path: str | Path | None = None):
        self._path = path
        # Sibling ratslotse.sqlite holds the chat_id→owner_id map for the migration.
        if ratslotse_db_path is None and isinstance(path, (str, Path)) and str(path) != ":memory:":
            ratslotse_db_path = Path(path).parent / "ratslotse.sqlite"
        self._ratslotse_db_path = ratslotse_db_path
        # check_same_thread=False wie im Konten-Store: FastAPI führt sync-Dependencies
        # und Endpoint in (potenziell verschiedenen) Threadpool-Threads aus — die
        # Verbindung wandert also zwischen Threads. Sicher, weil jede Anfrage ihre
        # eigene Store-Instanz bekommt (keine parallele Nutzung EINER Verbindung).
        self._conn = sqlite3.connect(path, timeout=15, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Kontaktdaten aus dem Text nehmen, der in einen SUCHINDEX geht — als
        # SQLite-Funktion, damit `rebuild_fts()` eine einzige INSERT-SELECT
        # bleibt und nicht zu einer Schleife in Python wird
        # (`council/kontaktdaten.py`). Gespeichert wird weiterhin alles.
        self._conn.create_function("ohne_kontaktdaten", 1, maskieren,
                                   deterministic=True)
        # WAL + busy_timeout: scraper cron and the web API share this file.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._migrate()
        #: Läuft gerade eine geklammerte Transaktion (siehe ``transaktion``)?
        self._sammelt = False
        #: Zwischenspeicher für ``personen_kanon`` — je Instanz, also je Anfrage.
        self._kanon: dict[str, str] | None = None
        # Namensvarianten derselben Person (s. _personen_varianten): einmal je
        # Store-Instanz gebaut, also einmal je Web-Anfrage.
        self._varianten_cache: dict[str, str] | None = None
        self._runtime_places_cache: tuple | None = None
        self._place_aliases_cache: dict[str, str] | None = None

    @contextlib.contextmanager
    def transaktion(self):
        """Mehrere ``save_*``-Aufrufe zu **einer** Transaktion klammern.

        Ohne die Klammer committet jeder Aufruf für sich. Für einen
        Jahresabschluss sind das 1 + n + 1 Transaktionen (Gesamtrechnung, je
        Teilhaushalt eine, Erläuterungen) — bricht der Lauf dazwischen ab,
        bleibt der Jahrgang halb in der Datenbank stehen. Genau das darf einem
        unbeaufsichtigten Cron nicht passieren, der einen halben Jahrgang
        anschließend für erledigt hält.

        Verschachtelung ist erlaubt und tut nichts: Die innerste Klammer
        überlässt Commit und Rollback der äußersten. Die ``save_*``-Methoden
        benutzen sie deshalb selbst — ein Aufruf ohne äußere Klammer verhält
        sich wie vorher."""
        if self._sammelt:
            yield  # schon geklammert — die äußere Klammer committet
            return
        self._sammelt = True
        try:
            with self._conn:
                yield
        finally:
            self._sammelt = False
    def _spalten_umbenennen(self, tabelle: str, paare: list[tuple[str, str]]) -> None:
        """Benennt Spalten um, sofern sie noch alt heißen — idempotent.

        SQLite zieht Indizes und Fremdschlüssel selbst nach. Läuft bei jedem
        Start; nach dem ersten Mal ist es ein PRAGMA und sonst nichts.
        """
        vorhanden = {r[1] for r in self._conn.execute(f"PRAGMA table_info({tabelle})")}
        if not vorhanden:
            return
        for alt, neu in paare:
            if alt in vorhanden and neu not in vorhanden:
                with self._conn:
                    self._conn.execute(
                        f"ALTER TABLE {tabelle} RENAME COLUMN {alt} TO {neu}")
                logging.getLogger("ratslotse.council.store").warning(
                    "Spalte umbenannt: %s.%s → %s", tabelle, alt, neu)

    def _migrate(self) -> None:
        # 08/2026: Der Code spricht Englisch, die Spalten ziehen nach. Ohne
        # das bräuchte jede Abfrage einen Alias — und genau die wollen wir
        # nicht (Tims Vorgabe „ohne Mappings").
        self._spalten_umbenennen("council_decisions", [
            ("beschluss", "official_text"), ("gegenstimmen", "no_votes"),
            ("enthaltungen", "abstentions"), ("abweichung", "deviation"),
            ("vorlage_nr", "template_number")])
        for tabelle in ("council_ergebnisrechnung", "council_finanzrechnung"):
            self._spalten_umbenennen(tabelle, [("abweichung", "deviation")])
        for tabelle in ("council_agenda_items", "council_vorlagen", "council_gebuehren",
                        "council_gebuehrensaetze", "council_haushaltssatzung",
                        "council_wirtschaftsplaene", "council_nachbewilligungen",
                        "council_spenden", "council_spenden_verworfen",
                        "council_vorlage_embeddings"):
            self._spalten_umbenennen(tabelle, [("vorlage_nr", "template_number")])

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
                if "deviation" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN deviation TEXT")
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
        # Eigene Ortsdaten statt Themen-Entitäten zu überladen: Auch einmalige
        # Straßen bleiben erhalten, mehrere Orte je Beschluss sind erlaubt und
        # die Fundstelle/Qualität der Zuordnung bleibt nachprüfbar.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_locations ("
            "slug TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, "
            "lat REAL, lon REAL, geojson TEXT, stadtteil TEXT, "
            "place_id TEXT, ortsbereich_id TEXT, "
            "geo_tried INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL)"
        )
        location_cols = {r[1] for r in self._conn.execute(
            "PRAGMA table_info(council_locations)").fetchall()}
        if "place_id" not in location_cols:
            self._conn.execute("ALTER TABLE council_locations ADD COLUMN place_id TEXT")
        if "ortsbereich_id" not in location_cols:
            self._conn.execute("ALTER TABLE council_locations ADD COLUMN ortsbereich_id TEXT")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_locations_place ON council_locations(place_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_locations_ortsbereich ON council_locations(ortsbereich_id)")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_decision_locations ("
            "decision_id INTEGER NOT NULL, location_slug TEXT NOT NULL, "
            "source TEXT NOT NULL, evidence TEXT NOT NULL, method TEXT NOT NULL, "
            "confidence REAL NOT NULL, updated_at TEXT NOT NULL, "
            "PRIMARY KEY (decision_id, location_slug))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_decloc_slug "
            "ON council_decision_locations(location_slug)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_decision_location_scans ("
            "decision_id INTEGER PRIMARY KEY, source_hash TEXT NOT NULL, scanned_at TEXT NOT NULL)"
        )
        # Redaktionelle Schicht über den automatisch extrahierten Ortsnamen.
        # Die Rohbeobachtung bleibt dabei unangetastet: Admins können einen
        # Kandidaten als eigenen Katalogort freigeben, einem bestehenden Ort
        # als Alias zuordnen oder für öffentliche Flächen verwerfen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_place_reviews ("
            "location_slug TEXT PRIMARY KEY, status TEXT NOT NULL, "
            "place_id TEXT, name TEXT, kind TEXT, parent_id TEXT, "
            "aliases TEXT NOT NULL DEFAULT '[]', description TEXT, source_url TEXT, "
            "quiz_enabled INTEGER NOT NULL DEFAULT 0, canonical_place_id TEXT, note TEXT, "
            "updated_by TEXT, updated_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_place_reviews_status "
            "ON council_place_reviews(status)"
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
        # decision. Keyed by kvonr (the SessionNet document id); template_number is the
        # human number ("26/0330") decisions/agenda items reference.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_vorlagen ("
            "kvonr INTEGER PRIMARY KEY, template_number TEXT, title TEXT, art TEXT, "
            "document_id INTEGER, document_url TEXT, raw_text TEXT, n_pages INTEGER, "
            "fetched_at TEXT NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'ok', "  # ok | empty | no_pdf | failed
            "anlagen_scanned INTEGER NOT NULL DEFAULT 0)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_vorlagen_nr ON council_vorlagen(template_number)")
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
            "status TEXT NOT NULL DEFAULT 'listed')"  # listed | ok | empty | failed | ocr
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_anlagen_kvonr ON council_anlagen(kvonr)")
        # Gerenderte Planzeichnung (scripts/render_plaene.py): 0 = offen,
        # 1 = Bild liegt unter data/plaene/<document_id>.jpg, -1 = fehlgeschlagen.
        aacols = {r[1] for r in self._conn.execute(
            "PRAGMA table_info(council_agenda_anlagen)").fetchall()}
        if aacols and "raw_text" not in aacols:
            self._conn.execute("ALTER TABLE council_agenda_anlagen ADD COLUMN raw_text TEXT")

        acols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_anlagen)").fetchall()}
        if "bild" not in acols:
            self._conn.execute(
                "ALTER TABLE council_anlagen ADD COLUMN bild INTEGER NOT NULL DEFAULT 0")
        # Welches Sehmodell den Text gelesen hat (scripts/backfill_anlagen_ocr.py).
        # NULL heißt „aus der Textebene des PDF", also gar nicht geraten.
        #
        # `status='ocr'` IST KEINE BUCHHALTUNG, SONDERN EINE SPERRE: Jede Anlage
        # mit `status='ok'` zieht `anlagen_missing_embeddings()` in die
        # Chunk-Vektoren und damit in die Gründliche Recherche und in
        # Nutzerantworten. Für OCR-Text ist das die falsche Voreinstellung —
        # er ist eine schwächere Quelle als eine echte Textebene, und ein Teil
        # der betroffenen Dokumente sind Förderanträge von Vereinen mit Namen,
        # Anschriften und Unterschriften darauf. Die Finanz-Parser lesen
        # trotzdem mit: `finanzquellen.Erkennung.where()` filtert bewusst NICHT
        # auf den Status. Wer den Text später auch durchsuchbar machen will,
        # setzt ihn gezielt auf 'ok' — eine Entscheidung, kein Nebeneffekt.
        if "ocr_modell" not in acols:
            self._conn.execute(
                "ALTER TABLE council_anlagen ADD COLUMN ocr_modell TEXT")
        # `status='ocr'` gab es genau einen Tag lang (20.08.2026). Solange galt
        # gelesener Scan-Text als grundsätzlich nicht durchsuchbar — eine
        # Sperre gegen die HERKUNFT des Textes statt gegen das, was darin
        # steht, und sie schloss den AWB-Wirtschaftsplan und den Prüfbericht
        # gleich mit aus. Die Sperre sitzt jetzt an der Index-Grenze
        # (`council/kontaktdaten.py`), und diese Zeilen sind ganz normaler
        # Anlagentext. `ocr_modell` sagt weiterhin, wie sie entstanden sind.
        #
        # Gehoben statt neu gelesen: Der Text ist in Ordnung, nur sein Status
        # war es nicht. Ein erneuter OCR-Lauf kostete Geld für nichts.
        self._conn.execute(
            "UPDATE council_anlagen SET status = 'ok' WHERE status = 'ocr'")
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
        # Ist-Steuereinnahmen je Steuerart und Jahr (Open-Data-Portal der Stadt,
        # seit 1998) — Grundlage der Steuer-Steckbriefe im Haushalts-Bereich.
        # Langformat: eine Zeile je (Jahr, Steuerart), 'insgesamt' als eigene Art.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_steuern ("
            "jahr INTEGER NOT NULL, "
            "art TEXT NOT NULL, "        # z. B. 'Gewerbesteuer (-umlage)', 'insgesamt'
            "betrag REAL, "              # Euro, Ist (nicht Plan!)
            "source_url TEXT, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, art))"
        )
        # Ergebnisrechnung aus den Jahresabschlüssen (RIS-Anlagen): Ansatz UND
        # Ergebnis je Posten — die Grundlage für „geplant gegen tatsächlich"
        # und für die Aufschlüsselung der Erträge nach Arten.
        # thh_nr trennt die Ebenen: NULL = Kernverwaltung gesamt, 1–13 = der
        # jeweilige Teilhaushalt. Beide Ebenen teilen sich die Tabelle, weil
        # sie dieselben Posten tragen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_ergebnisrechnung ("
            "jahr INTEGER NOT NULL, "
            "thh_nr INTEGER, thh_name TEXT, "     # NULL = Gesamtrechnung
            "nr INTEGER NOT NULL, "               # Postennummer der Tabelle (1–24)
            "bezeichnung TEXT NOT NULL, "
            "vorjahr REAL, ansatz REAL, ergebnis REAL, deviation REAL, "
            "ist_summe INTEGER NOT NULL DEFAULT 0, "
            "quelle_label TEXT, quelle_url TEXT, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, thh_nr, nr))"
        )
        # Die Tabelle kam mit der Vorversion ohne thh_nr; SQLite kann den
        # Primärschlüssel nicht per ALTER TABLE erweitern. Neu anlegen ist
        # hier gefahrlos: Der Inhalt stammt vollständig aus council_anlagen
        # und wird von scripts/ingest_finanzberichte.py in Sekunden wieder
        # hergestellt — es geht keine Quelle verloren.
        spalten = {r[1] for r in self._conn.execute(
            "PRAGMA table_info(council_ergebnisrechnung)")}
        if spalten and "thh_nr" not in spalten:
            self._conn.execute("DROP TABLE council_ergebnisrechnung")
            self._conn.execute(
                "CREATE TABLE council_ergebnisrechnung ("
                "jahr INTEGER NOT NULL, thh_nr INTEGER, thh_name TEXT, "
                "nr INTEGER NOT NULL, bezeichnung TEXT NOT NULL, "
                "vorjahr REAL, ansatz REAL, ergebnis REAL, deviation REAL, "
                "ist_summe INTEGER NOT NULL DEFAULT 0, "
                "quelle_label TEXT, quelle_url TEXT, fetched_at TEXT NOT NULL, "
                "PRIMARY KEY (jahr, thh_nr, nr))"
            )
        # „Plan" heißt nicht in jedem Jahrgang dasselbe: 2018 ist die
        # Bezugsgröße der Abweichung die Gesamtermächtigung, 2020 der Ansatz
        # samt Nachtrag (27 Mio. Unterschied!), sonst der nackte Ansatz.
        # Deshalb steht in `ansatz` weiter der ursprüngliche Haushaltsansatz,
        # in `plan` die Bezugsgröße und in `plan_art`, welche davon gemeint
        # ist. Ohne das letzte Feld wäre eine Mehrjahres-Kurve still falsch.
        # Nachrüsten per ALTER: Der Primärschlüssel bleibt, nichts geht verloren.
        for spalte, typ in (("plan", "REAL"), ("plan_art", "TEXT")):
            if spalte not in spalten:
                try:
                    self._conn.execute(
                        f"ALTER TABLE council_ergebnisrechnung ADD COLUMN {spalte} {typ}")
                except sqlite3.OperationalError:
                    pass  # frisch angelegt — Spalte ist schon da
        # Finanzrechnung der Kernverwaltung (Abschnitt 4.1 desselben
        # Jahresabschlusses): nicht was gebucht, sondern was **gezahlt** wurde.
        # Die Ergebnisrechnung darüber weist für 2024 einen Überschuss von
        # 6,1 Mio. € aus, die Finanzrechnung im selben Heft einen
        # Finanzmittel-Fehlbetrag von 22,4 Mio. € — beides stimmt, und ohne
        # die zweite Zahl entsteht ein falscher Eindruck.
        #
        # `nr` ist die Nummer, die das Dokument vergibt; sie verschiebt sich
        # zwischen den Jahrgängen um eins (2017–2020 hat die Tabelle 42
        # Zeilen, ab 2021 nur 41). Deshalb steht daneben `rolle` — der stabile
        # Name aus `finanzberichte.ROLLEN`, an dem Frontend und Proben hängen.
        # `ermaechtigung` ist die Spalte „Ermächtigungen aus Haushalts-
        # vorjahren": Geld aus früheren Jahren, das noch ausgegeben werden
        # durfte. Sie ist NULL, wo der Jahrgang sie nicht führt oder wo ihre
        # eigene Summenprobe gerissen ist.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_finanzrechnung ("
            "jahr INTEGER NOT NULL, "
            "nr INTEGER NOT NULL, "               # Zeilennummer DES DOKUMENTS
            "rolle TEXT, "                        # stabiler Name, NULL = Einzelzeile
            "bezeichnung TEXT NOT NULL, "         # Wortlaut des Dokuments
            "vorjahr REAL, ansatz REAL, plan REAL, plan_art TEXT, "
            "ergebnis REAL, deviation REAL, ermaechtigung REAL, "
            "ist_summe INTEGER NOT NULL DEFAULT 0, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, nr))"
        )
        # Warum ein Posten vom Plan abweicht, in den Worten der Verwaltung:
        # Abschnitt 6.3.1 des Jahresabschlusses, je Posten. Übernommen wird
        # nur, was die Rechenprobe besteht (siehe finanzberichte).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_abweichungsgruende ("
            "jahr INTEGER NOT NULL, "
            "nr INTEGER NOT NULL, "                # Postennummer der Tabelle
            "bezeichnung TEXT NOT NULL, "          # so, wie der Abschnitt sie nennt
            "delta_mio REAL, prozent REAL, "       # laut Überschrift des Blocks
            "text TEXT NOT NULL, "
            "quelle_label TEXT, quelle_url TEXT, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, nr))"
        )
        # Die Bilanz der Stadt (Abschnitt 2.1 desselben Jahresabschlusses):
        # nicht was die Stadt einnimmt oder schuldet, sondern was sie **hat**
        # — und was davon schon vergeben ist. Der größte Passivposten sind
        # die Pensionsrückstellungen (2024: 311,79 Mio. € einschließlich
        # Beihilfe, 266,26 Mio. € ohne), ein Vielfaches der 43,69 Mio. €
        # Kreditschulden (council/bilanz.py).
        #
        # `rolle` ist der Schlüssel, nicht `nr`: Die Gliederungsnummer ist ab
        # 2021 auf beiden Bilanzseiten dieselbe („1.1" gibt es zweimal), und
        # bis 2020 war sie römisch. Der Name, den das Dokument der Zeile
        # gibt, ist das einzig Stabile — deshalb steht er in `bezeichnung`
        # im Wortlaut daneben.
        #
        # Kein `wert_vorjahr`: Die zweite Spalte der Bilanz ist der Stichtag
        # davor, und der ist ein **eigener Jahrgang** in dieser Tabelle. Sie
        # zusätzlich an der Zeile zu führen hieße, denselben Stand zweimal zu
        # speichern — mit der Aussicht, dass die beiden eines Tages
        # auseinanderlaufen. Gebraucht wird sie beim Einlesen (als
        # Vorjahres-Kette über Dokumentgrenzen) und beim ältesten Jahrgang,
        # der ausschließlich aus ihr stammt.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_bilanz ("
            "jahr INTEGER NOT NULL, "             # Bilanzstichtag 31.12.jahr
            "rolle TEXT NOT NULL, "               # stabiler Name (bilanz.ROLLEN)
            "seite TEXT NOT NULL, "               # 'aktiva' | 'passiva'
            "ebene INTEGER NOT NULL, "            # 1 = Hauptposten der Bilanzsumme
            "nr TEXT, "                           # Gliederungsnummer DES DOKUMENTS
            "bezeichnung TEXT NOT NULL, "         # Wortlaut des Dokuments
            "wert REAL NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, rolle))"
        )
        # Was die Verwaltung zu jedem Hauptposten schreibt: Anhang 6.2.1–6.2.9
        # desselben Dokuments, ein Abschnitt je Bilanzposition.
        #
        # Diese Tabelle ist keine Zierde, sondern eine Auflage. Die Bilanz
        # 2024 weist Schulden von 207,1 Mio. € aus nach 84,4 Mio. € im
        # Vorjahr; ohne 6.2.7 läse sich das als Verdreifachung. Der Abschnitt
        # sagt, dass es eine Bilanzverlängerung aus dem Cash-Pooling ist,
        # 138,2 Mio. €, mit Gegenposten auf der Aktivseite. **Die Zahl darf
        # ohne diesen Text nicht angezeigt werden** — dieselbe Bauart wie
        # `council_abweichungsgruende` für die Ergebnisrechnung.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_bilanz_erlaeuterungen ("
            "jahr INTEGER NOT NULL, "
            "rolle TEXT NOT NULL, "               # dieselbe Marke wie council_bilanz
            "nr INTEGER NOT NULL, "               # 6.2.N
            "ueberschrift TEXT NOT NULL, "        # Wortlaut der Abschnittsüberschrift
            "text TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, rolle))"
        )
        # Gesamtergebnishaushalt aus den Haushaltsplänen (RIS-Anlage 005):
        # dieselbe Postengliederung wie die Ergebnisrechnung, aber für Jahre,
        # die noch gar keinen Jahresabschluss haben (council/ergebnishaushalt.py).
        #
        # DREI SPALTEN, DIE ZUSAMMENGEHÖREN — und deren Trennung der ganze
        # Zweck dieser Tabelle ist:
        #
        # `jahr`          Für welches Jahr die Zahl gilt.
        # `art`           `ansatz` = das Jahr, für das dieser Plan DER Haushalt
        #                 ist. `finanzplanung` = mittelfristige Vorausschau
        #                 nach § 8 NKomVG. Das Dokument nennt beides „Ansatz";
        #                 das ist Haushaltsrecht, aber keine Beschlusslage.
        #                 Wer die Unterscheidung wegwirft, behauptet für 2029
        #                 einen Plan. (Und auch `ansatz` ist der Stand der
        #                 Einbringung, nicht der Beschluss des Rates — die
        #                 Herkunft sagt es je Zeile, die Messwerte dazu stehen
        #                 im Kopf von council/ergebnishaushalt.py.)
        # `plan_jahrgang` Aus welchem Haushalt die Zahl stammt. Sie steht im
        #                 Schlüssel, weil dasselbe Jahr in mehreren Plänen
        #                 vorkommt: 2027 ist im Haushalt 2026 die erste
        #                 Finanzplanungsstufe, im Haushalt 2027 der Ansatz.
        #                 Und die Finanzplanung wird jedes Jahr neu
        #                 geschrieben — von 23 Posten stimmen zwischen zwei
        #                 aufeinanderfolgenden Plänen 0 bis 2 überein.
        #
        # Ohne `plan_jahrgang` im Schlüssel überschriebe der jüngste Plan
        # stillschweigend, was der ältere für dasselbe Jahr sagte. Mit ihm
        # ist beides nachlesbar, und die Frage „was war der Ansatz für 2026?"
        # hat genau eine Antwort: art='ansatz'.
        #
        # Herkunft ausschließlich über `herkunft_id` — die Tabelle ist neu und
        # hat keinen Altbestand (s. council/herkunft.py).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_ergebnishaushalt ("
            "plan_jahrgang INTEGER NOT NULL, "     # Haushalt, aus dem die Zahl stammt
            "jahr INTEGER NOT NULL, "              # Jahr, für das sie gilt
            "art TEXT NOT NULL, "                  # ansatz | finanzplanung
            "nr INTEGER NOT NULL, "                # Postennummer 1–24, wie im Abschluss
            "bezeichnung TEXT NOT NULL, "
            "betrag REAL NOT NULL, "
            "ist_summe INTEGER NOT NULL DEFAULT 0, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (plan_jahrgang, jahr, nr))"
        )
        # Der Lesepfad fragt „welcher Ansatz gilt für Jahr X?" — nicht „was
        # stand im Plan Y?". Deshalb der Index auf (jahr, art).
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ergebnishaushalt_jahr "
            "ON council_ergebnishaushalt(jahr, art)")
        # Der Stellenplan (Anlage 21/22 des Haushaltsplans, council/stellenplan.py):
        # wie viele Stellen die Stadt vorhält, wie viele davon besetzt sind
        # und wie viele nicht.
        #
        # `teil`  A = Beamtinnen und Beamte, B = Arbeitnehmerinnen und
        #         Arbeitnehmer. Zwei Tabellen im Dokument, zwei Spaltensätze,
        #         zwei Rechenproben — und sie kommen einzeln herein: Im
        #         Stellenplan 2026 ist Teil B im Textextrakt Glyphen-Salat,
        #         Teil A steht sauber da. Ohne `teil` im Schlüssel wäre dieser
        #         Jahrgang entweder ganz draußen oder still halb drin.
        # `art`   posten | gruppe | gesamt — die drei Stufen der Summenzeilen.
        #         Die Summen stehen als eigene Zeilen in der Tabelle, weil sie
        #         im Dokument stehen: Eine Seite, die „815 Stellen" zeigt, soll
        #         die Zahl der Stadt zeigen und nicht unsere Addition.
        # `zeile` Laufende Nummer innerhalb von (jahrgang, teil, art) —
        #         nicht die Lfd.Nr. des Plans. Die taugt nicht als Schlüssel:
        #         Die Summenzeilen tragen keine, und zwei Teile fangen beide
        #         bei 1 an. Sie steht daneben in `lfd_nr`.
        # `stimmig` 0 heißt: In dieser Zeile ergeben besetzt + nicht besetzt
        #         nicht die Stellen des Vorjahres — so steht es im Plan. Zwei
        #         Zeilen im Bestand sind das (Begründung in
        #         `council/stellenplan.besetzungsprobe`).
        #
        # `besetzt_beamte`/`besetzt_arbeitnehmer` gibt es nur in Teil A: Eine
        # Beamtenstelle darf mit Tarifbeschäftigten besetzt werden, und der
        # Plan weist das getrennt aus. Teil B kennt die Unterscheidung nicht
        # und lässt beide Spalten leer; `besetzt` trägt in beiden Teilen die
        # Gesamtbesetzung.
        #
        # Herkunft ausschließlich über `herkunft_id` — neue Tabelle, kein
        # Altbestand (s. council/herkunft.py).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_stellenplan ("
            "jahrgang INTEGER NOT NULL, "          # Haushaltsjahr des Plans
            "teil TEXT NOT NULL, "                 # A | B
            "zeile INTEGER NOT NULL, "             # Reihenfolge im Dokument
            "art TEXT NOT NULL, "                  # posten | gruppe | gesamt
            "gruppe TEXT, "                        # Laufbahngruppe 2, Beschäftigte TVöD …
            "lfd_nr INTEGER, "                     # Nummer im Plan (Summen: NULL)
            "bezeichnung TEXT NOT NULL, "
            "besoldung TEXT, "                     # A 13, S 08 a, 15 …
            "stellen_plan REAL NOT NULL, "         # Stellen im Haushaltsjahr
            "stellen_vorjahr REAL NOT NULL, "      # Stellen im Vorjahr
            "besetzt REAL NOT NULL, "              # am Stichtag besetzt
            "besetzt_beamte REAL, "                # davon mit Beamt*innen (Teil A)
            "besetzt_arbeitnehmer REAL, "          # davon mit Tarifbeschäftigten (Teil A)
            "nicht_besetzt REAL NOT NULL, "
            "stichtag TEXT, "                      # auf welchen Tag sich die Besetzung bezieht
            "stimmig INTEGER NOT NULL DEFAULT 1, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahrgang, teil, zeile))"
        )
        # Die Seite fragt fast immer „gib mir die Summen aller Jahrgänge" —
        # eine Handvoll Zeilen aus rund tausend.
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_stellenplan_art "
            "ON council_stellenplan(art, jahrgang)")
        # Die Investitionen des Finanzhaushalts (council/investitionen.py) —
        # was die Stadt bauen und kaufen will, je Teilhaushalt. Die andere
        # Hälfte des Haushaltsplans: Im Ergebnishaushalt darüber steht keine
        # einzige Investition.
        #
        # `ebene` trennt drei Dinge, die verschieden weit reichen:
        #   `teilhaushalt`  eine der 13 Zeilen (thh_nr 1–13)
        #   `investitionen` die Summenzeile der Datei — das ZIEL der
        #                   Rechenprobe, nicht unsere Addition
        #   `finanzhaushalt` der Gesamtbetrag ALLER Ein-/Auszahlungen, also
        #                   samt laufender Verwaltungstätigkeit. Bezugsgröße,
        #                   von keiner Probe der Datei gedeckt und deshalb mit
        #                   eigener Herkunft (herkunft.UNGEPRUEFT).
        #
        # `thh_nr` ist 0 auf den beiden Summenzeilen — sie tragen keine
        # Teilhaushaltsnummer. Bewusst 0 statt NULL: SQLite lässt NULL in einer
        # PRIMARY KEY zu und hält zwei NULL-Zeilen für verschieden, der
        # Schlüssel wäre dort also gar keiner.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_investitionen ("
            "jahr INTEGER NOT NULL, "              # Haushaltsjahr (Plan)
            "ebene TEXT NOT NULL, "                # teilhaushalt|investitionen|finanzhaushalt
            "thh_nr INTEGER NOT NULL DEFAULT 0, "  # 0 = Summenzeile
            "bezeichnung TEXT NOT NULL, "
            "einzahlungen REAL NOT NULL, "
            "auszahlungen REAL NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, ebene, thh_nr))"
        )
        # Die einzelnen Vorhaben aus Anlage 004 des Haushaltsplans
        # (council/investitionsprogramm.py) — die Ebene unter
        # `council_investitionen`: nicht „Schule und Bildung: 8,3 Mio. €",
        # sondern „BBS Haarentor: Ausstattung".
        #
        # `ebene` trennt drei Zeilenarten, die zusammen aus einem Dokument
        # kommen und einander stützen:
        #   massnahme     — ein Vorhaben, mit IPSP-Element als `code`
        #   teilhaushalt  — die Gesamtsumme des Abschnitts (Ziel der Probe)
        #   gesamt        — die Gesamtsumme des Investitionsprogramms
        #
        # Gespeichert wird ausschließlich die **Gesamtinvestitionssumme**. Die
        # Jahresraten der Tabelle sind aus dem Textextrakt nicht sicher zu
        # holen, weil leere Zellen darin ersatzlos wegfallen — die Begründung
        # steht im Kopf von council/investitionsprogramm.py.
        #
        # `code` ist '' auf den beiden Summenebenen und `thh_nr` 0 auf
        # `gesamt` — bewusst leer statt NULL, aus demselben Grund wie bei
        # `council_investitionen`: SQLite hielte zwei NULL-Zeilen für
        # verschieden, der Primärschlüssel wäre dort keiner.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_investitionsmassnahmen ("
            "jahr INTEGER NOT NULL, "              # Haushaltsjahrgang (Plan)
            "ebene TEXT NOT NULL, "                # massnahme|teilhaushalt|gesamt
            "thh_nr INTEGER NOT NULL DEFAULT 0, "
            "code TEXT NOT NULL DEFAULT '', "      # IPSP-Element
            "bezeichnung TEXT NOT NULL, "
            "gesamtsumme REAL NOT NULL, "
            "details TEXT, "                       # Sachkonto-Detailnamen, " · "-getrennt
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, ebene, thh_nr, code))"
        )
        # `details` kam am 26.08.2026 dazu (Namen der Sachkonto-Detailzeilen,
        # council/investitionsprogramm.py) — additiv, füllt der nächste Ingest.
        inv_cols = {r[1] for r in self._conn.execute(
            "PRAGMA table_info(council_investitionsmassnahmen)").fetchall()}
        if inv_cols and "details" not in inv_cols:
            self._conn.execute(
                "ALTER TABLE council_investitionsmassnahmen ADD COLUMN details TEXT")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_invprog_jahr_thh "
            "ON council_investitionsmassnahmen(jahr, thh_nr)")
        # Schlussberichte des Rechnungsprüfungsamts — nur die **Fundstelle**,
        # nicht der Inhalt: „Das Rechnungsprüfungsamt hat diesen Abschluss
        # geprüft → Schlussbericht". Eine Zeile je Jahrgang.
        # `lesbar` = 0 heißt, der Volltext des PDFs ist unbrauchbar (2024).
        #
        # Der Name trägt bewusst „_quellen": Die einzelnen
        # Prüfungsfeststellungen aus denselben Berichten (Beanstandung,
        # Wiederholte Beanstandung, Hinweis) sind eine andere Ebene mit einer
        # Zeile je Feststellung und gehören in eine eigene Tabelle.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_pruefbericht_quellen ("
            "jahr INTEGER PRIMARY KEY, "
            "label TEXT, url TEXT, n_pages INTEGER, "
            "lesbar INTEGER NOT NULL DEFAULT 1, fetched_at TEXT NOT NULL)"
        )
        # Produktebene aus den Teilhaushalts-Plänen: was einzelne Aufgaben
        # kosten, mit Produktnummer und zuständigem Amt — dazu der Steckbrief,
        # den die Pläne zu jedem Produkt führen (was die Aufgabe umfasst, auf
        # welchem Gesetz sie beruht, wie viel Spielraum die Stadt bei ihr hat).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_produkte ("
            "jahr INTEGER NOT NULL, "
            "produkt_nr TEXT NOT NULL, "          # z. B. P10.111023
            "produkt_name TEXT NOT NULL, "
            "thh_nr INTEGER, thh_name TEXT, amt TEXT, "
            "ertraege REAL, aufwendungen REAL, ergebnis REAL, "
            "kurzbeschreibung TEXT, auftragsgrundlage TEXT, "
            "beeinflussbarkeit TEXT, "            # normalisiert: niedrig|mittel|hoch
            "beeinflussbarkeit_roh TEXT, "        # Wortlaut des Plans
            "wirkungskreis TEXT, zielgruppe TEXT, "
            "quelle_label TEXT, quelle_url TEXT, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, produkt_nr))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_produkte_thh ON council_produkte(jahr, thh_nr)")
        # Prüfungsfeststellungen aus den Schlussberichten des Rechnungs-
        # prüfungsamts (RIS-Anlagen): die einzige regelmäßige, förmliche
        # Kontrolle der Verwaltung durch eine eigene Stelle.
        #
        # `marke` ist die Randmarke des Berichts (B/WB/H/K), `marke_name` und
        # `marke_erlaeuterung` sind die Legende DIESES Jahrgangs — nicht unsere
        # Formulierung. Sie stehen bewusst je Zeile statt in einer zweiten
        # Tabelle: Die Legende ändert sich zwischen den Jahrgängen (2023 kennt
        # kein K mehr), und ein Bericht ohne seine eigene Legende wäre gar
        # nicht erst eingelesen worden.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_pruefberichte ("
            "jahr INTEGER NOT NULL, "              # geprüfter Jahresabschluss
            "lfd INTEGER NOT NULL, "               # Reihenfolge im Dokument
            "marke TEXT NOT NULL, "                # B | WB | H | K
            "marke_name TEXT NOT NULL, "           # 'Wiederholte Beanstandung'
            "marke_erlaeuterung TEXT, "            # Legendentext des Jahrgangs
            "textziffer TEXT NOT NULL, "           # Fundstelle, z. B. '4.5.2'
            "abschnitt TEXT NOT NULL, "            # Überschrift der Textziffer
            "kette TEXT, "                         # Schlüssel für WB-Ketten
            "seite INTEGER, "                      # Seite im Bericht
            "text TEXT NOT NULL, "
            "folgeabsatz TEXT, "                   # was im Bericht direkt folgt
            "quelle_label TEXT, quelle_url TEXT, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, lfd))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pruefberichte_kette "
            "ON council_pruefberichte(kette, jahr)")
        # Einwohnerzahl je Haushaltsjahr (Open-Data, Stichtag 31.12. des
        # Vorjahres) — Bezugsgröße für Pro-Kopf-Einordnungen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_einwohner ("
            "jahr INTEGER PRIMARY KEY, einwohner INTEGER NOT NULL, "
            "source_url TEXT, fetched_at TEXT NOT NULL)"
        )
        # Steuerkraftmesszahl + Schlüsselzuweisungen je Ausgleichsjahr (Open-Data,
        # seit 1993) — zeigt die NFAG-Mechanik: mehr Steuerkraft, weniger
        # Zuweisungen. Pflichtwissen für jede ehrliche Hebesatz-Simulation.
        # `jahr` ist das Ausgleichsjahr, nicht die Jahreszahl aus der Quelle:
        # Der Datensatz 1106 beschriftet um ein Jahr zu früh, wir rücken beim
        # Einlesen (Beleg in `council/haushalt._STEUERKRAFT_VERSATZ`). Die
        # beiden `*_je_ew`-Spalten bleiben deshalb leer — sie tragen die
        # Pro-Kopf-Rechnung der Quelle und damit deren falsches Bezugsjahr.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_steuerkraft ("
            "jahr INTEGER PRIMARY KEY, "
            "messzahl REAL, messzahl_je_ew REAL, "          # Euro bzw. Euro/Einwohner
            "zuweisungen REAL, zuweisungen_je_ew REAL, "    # Anordnungssoll
            "source_url TEXT, fetched_at TEXT NOT NULL)"
        )
        # Herkunft der Finanzzahlen — ein Datensatz je Dokument-und-Abschnitt,
        # auf den die Datenzeilen per `herkunft_id` zeigen. Warum eine eigene
        # Tabelle statt Spalten in jeder Zieltabelle, steht ausführlich im
        # Modulkopf von `council/herkunft.py`; kurz: Eine Zieltabelle trägt
        # Zeilen aus mehreren Dokumenten (bei den Beteiligungen der
        # Normalfall), ein neues Herkunftsfeld darf nicht neun ALTER TABLE
        # kosten, und ein Jahrgang schriebe dieselbe Angabe sonst 200-mal.
        #
        # `schluessel` ist der Fingerabdruck über alle Inhaltsfelder und macht
        # das Eintragen idempotent — `fetched_at` steht bewusst NICHT darin
        # (s. Herkunft.schluessel), sonst wüchse die Tabelle mit der Zahl der
        # Läufe statt mit der Zahl der Quellen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_herkunft ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "schluessel TEXT NOT NULL UNIQUE, "
            "art TEXT NOT NULL, "                  # ris | opendata | stadt
            "dokument_id INTEGER, "                # council_anlagen.document_id
            "label TEXT, url TEXT, "
            "fundstelle TEXT, seite INTEGER, "     # wo IM Dokument
            "probe TEXT NOT NULL, probe_ergebnis TEXT, "  # womit abgesichert
            "stand TEXT, "                         # Stichtag des Inhalts
            "fetched_at TEXT NOT NULL)"            # zuletzt bestätigt
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_herkunft_dokument "
            "ON council_herkunft(dokument_id)")
        # Der Konzern Stadt Oldenburg aus dem konsolidierten Gesamtabschluss
        # (council/konzernabschluss.py). Zwei Ebenen, zwei Tabellen:
        #
        # `council_konzern_posten` = die Gesamtergebnisrechnung des Konzerns,
        # Posten für Posten. `rolle` ist der Grund, warum es diese Spalte gibt:
        # Bis 2018 ist Posten 15 die Summe der ordentlichen Erträge, ab 2019
        # ist es Posten 13. Wer über Jahre hinweg nach `nr` fragt, bekommt ab
        # 2019 stillschweigend die Versorgungsaufwendungen. Gefragt wird
        # deshalb nach der Rolle; die Nummer steht nur noch als Fundstelle
        # daneben.
        #
        # BEIDE TABELLEN FÜHREN IHRE HERKUNFT AUSSCHLIESSLICH ÜBER
        # `herkunft_id` — kein `quelle_label`, kein `quelle_url`. Die neun
        # älteren Finanztabellen tragen ihre Altspalten weiter, weil ein
        # Umbau dort neun Lesepfade anfasste (s. council/herkunft.py). Diese
        # zwei sind neu und haben keinen Altbestand; sie hier trotzdem
        # anzulegen hieße, dieselbe Angabe von Anfang an doppelt zu führen —
        # mit der bekannten Folge, dass eine der beiden irgendwann veraltet.
        # Die Spalte selbst rüstet `_migrate_herkunft` über
        # `herkunft.HERKUNFT_TABELLEN` nach; sie steht hier nur mit, damit
        # eine frische Datenbank sie sofort trägt.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_konzern_posten ("
            "jahr INTEGER NOT NULL, "
            "nr INTEGER NOT NULL, "                # Postennummer DIESES Jahrgangs
            "bezeichnung TEXT NOT NULL, "
            "rolle TEXT, "                         # ertraege_summe, zinsaufwand, …
            "betrag REAL NOT NULL, vorjahr REAL, "  # Euro; vorjahr NULL = Spalte unlesbar
            "ist_summe INTEGER NOT NULL DEFAULT 0, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, nr))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_konzern_posten_rolle "
            "ON council_konzern_posten(rolle, jahr)")
        # `council_konzern_traeger` = wer den Konzern ausmacht: dieselben
        # Summen, aufgeteilt auf Kernverwaltung, Eigenbetriebe und
        # Beteiligungen, plus die Zeile „Konsolidierung" (die Verrechnung der
        # Geschäfte untereinander).
        #
        # Die Beträge stehen in **Tausend Euro**, so wie der Bericht sie
        # ausweist, und die Spalten heißen auch so. Sie in Euro umzurechnen
        # hieße, sechs Stellen Genauigkeit zu behaupten, die das Dokument
        # nicht hergibt — und niemand sähe es der Spalte `betrag` später an.
        #
        # Eigene `herkunft_id` je Zeile, nicht je Jahrgang: Diese Aufstellung
        # steht in einem anderen Abschnitt des Berichts als die Posten (4.1.1
        # statt 3.2) und ist durch andere Proben gedeckt. Und sobald die
        # Beteiligungen einmal aus ihren Einzelabschlüssen kommen, sitzen in
        # derselben Tabelle Zeilen aus verschiedenen Dokumenten — genau der
        # Fall, für den die Herkunft eine eigene Tabelle ist.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_konzern_traeger ("
            "jahr INTEGER NOT NULL, "
            "art TEXT NOT NULL, "                  # 'ertraege' | 'aufwendungen'
            "traeger_key TEXT NOT NULL, "          # stadt, klinikum, egh, konsolidierung, …
            "traeger TEXT NOT NULL, "
            "betrag_teur REAL NOT NULL, vorjahr_teur REAL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, art, traeger_key))"
        )
        # Der Beteiligungsbericht nach § 151 NKomVG
        # (council/beteiligungsbericht.py). Drei Tabellen, weil hier drei
        # verschiedene Dinge zusammenkommen — und weil sie verschieden oft
        # ihren Wert wechseln.
        #
        # ACHTUNG, NAMENSFALLE: `council_beteiligungen` ist etwas ganz
        # anderes. Dort stehen die **Bürgerbeteiligungen** an Bauleitplänen
        # (oldenburg.planungsbeteiligung.de, s. `council/beteiligung.py`).
        # Gesellschaften heißen hier deshalb Gesellschaften.
        #
        # `council_gesellschaften` = die Stammdaten je Bericht: Wie die
        # Gesellschaft heißt, an welcher Stelle sie im Bericht steht, auf
        # welcher Seite. Je Berichtsjahr eine Zeile, weil sich alles davon
        # ändern kann — die Gliederungsnummer tut es regelmäßig, sobald eine
        # Beteiligung dazukommt.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_gesellschaften ("
            "bericht_jahr INTEGER NOT NULL, "      # Berichtsjahr des Dokuments
            "gesellschaft TEXT NOT NULL, "         # stabiler Schlüssel: egh, vwg, …
            "name TEXT NOT NULL, "
            "gliederung TEXT NOT NULL, "           # '2.4.9'
            "seite INTEGER, "                      # gedruckte Seite im Bericht
            "konzern_key TEXT, "                   # → council_konzern_traeger
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (bericht_jahr, gesellschaft))"
        )
        # `council_gesellschaft_texte` = die beschreibenden Abschnitte.
        # Langformat, nicht fünf Spalten: Der Bericht führt acht Abschnitte,
        # gespeichert werden fünf, und welche das sind, ist eine Entscheidung
        # über den Nutzen — keine über das Schema. Ein sechster kostet so
        # keine Migration.
        #
        # Diese Zeilen tragen `herkunft.UNGEPRUEFT`, und das ist die ehrliche
        # Angabe: Fließtext lässt sich gegen nichts rechnen. Sie stehen
        # trotzdem mit Dokument, Fundstelle und Seite da.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_gesellschaft_texte ("
            "bericht_jahr INTEGER NOT NULL, "
            "gesellschaft TEXT NOT NULL, "
            "abschnitt TEXT NOT NULL, "            # gegenstand, aufsichtsorgane, …
            "text TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (bericht_jahr, gesellschaft, abschnitt))"
        )
        # `council_gesellschaft_personen` = wer in den Aufsichtsorganen sitzt.
        #
        # Das steht auch im Abschnittstext, und trotzdem ist es keine
        # Doppelung: Der Text ist der zweispaltige PDF-Extrakt — erst fünfzehn
        # Namen, dann fünfzehn Ämter —, und was da nebeneinander gehört,
        # entscheidet eine Rechenprobe (`beteiligungsbericht.aufsichtsorgane`).
        # Hier steht das Ergebnis dieser Probe; der Text bleibt daneben stehen,
        # damit ein Mensch nachlesen kann.
        #
        # `funktionen_zuordenbar` ist die Probe selbst und steht bewusst an
        # JEDER Zeile, obwohl sie je Gesellschaft gilt: Wer die Personen liest,
        # muss ohne zweite Abfrage wissen, ob das Amt daneben gedeckt ist.
        # Ist sie 0, sind ALLE `funktion` dieser Gesellschaft NULL — nicht
        # „die meisten". Ein falsch zugeordnetes Amt wäre eine Falschaussage
        # über eine namentlich genannte Person.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_gesellschaft_personen ("
            "bericht_jahr INTEGER NOT NULL, "
            "gesellschaft TEXT NOT NULL, "
            "reihenfolge INTEGER NOT NULL, "   # Position im Bericht
            "gremium TEXT NOT NULL, "          # Betriebsausschuss, Aufsichtsrat, …
            "name TEXT NOT NULL, "
            "funktion TEXT, "                  # NULL, wenn die Probe riss
            "vorsitz TEXT, "                   # vorsitz | stellvertretung | NULL
            "hinweis TEXT, "                   # „bis 30. Juni 2022"
            "funktionen_zuordenbar INTEGER NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (bericht_jahr, gesellschaft, reihenfolge))"
        )
        # `council_gesellschaft_eigentuemer` = wem die Gesellschaft gehört.
        #
        # Ohne die Summenzeile: „Stammkapital 22.000.000,00 100,0" sieht im
        # Extrakt aus wie ein Gesellschafter und ist die Probe, gegen die die
        # Anteile laufen. Stünde sie hier, hielte die Stadt an ihrem eigenen
        # Eigenbetrieb die Hälfte und ein „Stammkapital" die andere.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_gesellschaft_eigentuemer ("
            "bericht_jahr INTEGER NOT NULL, "
            "gesellschaft TEXT NOT NULL, "
            "reihenfolge INTEGER NOT NULL, "
            "name TEXT NOT NULL, "
            "betrag_eur REAL, "                # NULL, wo der Bericht nur % nennt
            "anteil_prozent REAL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (bericht_jahr, gesellschaft, reihenfolge))"
        )
        # `council_gesellschaft_kennzahlen` = die Zeitreihe.
        #
        # SCHLÜSSEL IST DAS BEZUGSJAHR DER KENNZAHL, NICHT DER BERICHT. Jeder
        # Bericht führt vier bis fünf Jahre; dasselbe Jahr steht also in bis
        # zu drei Berichten. Als (Bericht, Jahr) abgelegt läge es dreimal da
        # und jede Auswertung müsste sich entscheiden — mit dem Bezugsjahr als
        # Schlüssel ist es eine Zeile, und die Frage „stimmen die Berichte
        # überein?" ist beim Schreiben beantwortet statt beim Lesen.
        #
        # `berichte` hält fest, wie viele Berichte den Wert übereinstimmend
        # nennen. Das ist keine Statistik, sondern das Ergebnis der
        # Überlappungsprobe: 1 heißt „steht bisher nur in einem Bericht" und
        # damit „durch eine Dokumentprobe gedeckt, nicht durch die
        # Überlappung". Die Seite sagt es so auch.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_gesellschaft_kennzahlen ("
            "gesellschaft TEXT NOT NULL, "
            "kennzahl TEXT NOT NULL, "             # jahresergebnis|bilanzsumme|…
            "jahr INTEGER NOT NULL, "              # Bezugsjahr der Kennzahl
            "wert REAL NOT NULL, "
            "einheit TEXT NOT NULL, "              # eur | prozent
            "bericht_jahr INTEGER NOT NULL, "      # jüngster Bericht mit diesem Wert
            "berichte INTEGER NOT NULL, "          # wie viele Berichte ihn nennen
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (gesellschaft, kennzahl, jahr))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gesellschaft_kennzahlen_jahr "
            "ON council_gesellschaft_kennzahlen(jahr, kennzahl)")
        # Städtevergleich aus der amtlichen Statistik des Landesamts für
        # Statistik Niedersachsen (council/staedtevergleich.py). Langformat —
        # eine Zeile je Stadt, Jahr und Kennzahl.
        #
        # WARUM LANGFORMAT: Die beiden Quellen haben verschiedene Zuschnitte.
        # Der Finanzausgleich liefert je Stadt zwei Zahlen für EIN Jahr, der
        # Realsteuervergleich Hebesätze für das Berichtsjahr UND eine
        # Steuereinnahmekraft-Reihe über drei Jahre. Als Spaltensatz bräuchte
        # das entweder zwei Tabellen oder eine mit lauter leeren Feldern; so
        # ist es eine, und eine neunte Kennzahl kostet keine Migration.
        #
        # `jahr` ist das Bezugsjahr DER KENNZAHL, nicht der Datei: Der
        # Realsteuervergleich 2025 führt auch 2023 und 2024. Alles unter dem
        # Dateijahr abzulegen machte aus drei Jahren eines.
        #
        # UND DIE WICHTIGE ABGRENZUNG ZU `council_steuerkraft`: Beide Tabellen
        # führen Steuerkraftmesszahlen, und sie sind NICHT dasselbe. Unser
        # Open-Data-Datensatz 1106 trägt dieselben Beträge wie das LSN, aber
        # unter einer um ein Jahr verschobenen Beschriftung (drei Wertepaare
        # geprüft, zwei unabhängige Wege). Welche stimmt, ist offen. Deshalb
        # eine eigene Tabelle mit der Jahresangabe des LSN — und deshalb darf
        # kein Lesepfad die beiden zu einer Reihe mischen, solange das nicht
        # geklärt ist. Er plottete zwei Jahre gegeneinander, die nicht dasselbe
        # meinen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_staedtevergleich ("
            "reihe TEXT NOT NULL, "                # 'steuerkraft' | 'realsteuern'
            "jahr INTEGER NOT NULL, "              # Bezugsjahr der Kennzahl (LSN)
            "schluessel TEXT NOT NULL, "           # amtliche Schlüsselnr., 6-stellig
            "stadt TEXT NOT NULL, "
            "kennzahl TEXT NOT NULL, "
            "wert REAL NOT NULL, "
            "einheit TEXT NOT NULL, "              # teur | anzahl | prozent | eur_je_ew
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (reihe, jahr, schluessel, kennzahl))"
        )
        # Gewerbesteuerstatistik des LSN (council/gewerbesteuerstatistik.py) —
        # wie viele Betriebe die Gewerbesteuer überhaupt aufbringen.
        #
        # WARUM SPALTEN UND NICHT LANGFORMAT wie beim Städtevergleich daneben:
        # Diese neun Zahlen sind EINE Aussage über eine Stadt in einem Jahr,
        # und sie hängen rechnerisch aneinander (reine Festsetzungen +
        # Zerlegungen = insgesamt, dreimal). Im Langformat stünde jede Zahl in
        # einer eigenen Zeile, und die Probe, die sie zusammenhält, wäre beim
        # Lesen nicht mehr nachvollziehbar, ohne neun Zeilen wieder
        # einzusammeln. Der Städtevergleich hat den umgekehrten Zuschnitt: dort
        # kommen die Kennzahlen aus zwei verschieden gebauten Quellen.
        #
        # `messbetrag_eur` und die beiden Teilbeträge sind NULL-bar, die
        # Anzahlen nicht. Das ist der Fall der GEHEIMHALTUNG: Wo ein einzelner
        # Zahler die Gemeinde dominiert, druckt das Landesamt statt des Betrags
        # ein „g" (2021 bei Salzgitter und Wolfsburg) — die Anzahlen stehen
        # trotzdem da. NULL heißt hier also „gesperrt", nicht „null Euro", und
        # `gesperrt` sagt es noch einmal ausdrücklich, damit eine Anzeige den
        # Unterschied nicht raten muss. Wo eine Stadt vollständig gesperrt ist
        # (Jahrgang 2020), kommt sie gar nicht erst herein.
        #
        # ABGRENZUNG, OHNE DIE DIE ZAHLEN IRREFÜHREN: Der Steuermessbetrag ist
        # die VERANLAGUNG des Erhebungsjahres, nicht das Aufkommen des
        # Kalenderjahres in `council_steuern`. Messbetrag mal Hebesatz lag in
        # den drei prüfbaren Jahren zwischen 13 % unter und 27 % über dem
        # kassenmäßigen Ist. Kein Lesepfad darf die beiden zu einer Reihe
        # verbinden (ausführlich im Modulkopf).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_gewerbesteuerstatistik ("
            "jahr INTEGER NOT NULL, "              # Erhebungsjahr der Veranlagung
            "schluessel TEXT NOT NULL, "           # amtliche Schlüsselnr., 6-stellig
            "stadt TEXT NOT NULL, "
            "faelle INTEGER NOT NULL, "            # Betriebe und Betriebsstätten
            "faelle_positiv INTEGER NOT NULL, "    # davon mit positivem Messbetrag
            "messbetrag_eur INTEGER, "             # NULL = Geheimhaltung
            "festsetzungen INTEGER, "              # reine Festsetzungen
            "festsetzungen_positiv INTEGER, "
            "festsetzung_messbetrag_eur INTEGER, "
            "zerlegungen INTEGER, "                # zerlegte Betriebsstätten
            "zerlegungen_positiv INTEGER, "
            "zerlegung_messbetrag_eur INTEGER, "
            "hebesatz REAL, "                      # nachrichtlich, aus Blatt 6.2
            "gesperrt INTEGER NOT NULL DEFAULT 0, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, schluessel))"
        )
        # Schuldenstand je Jahr (Tabelle 1108 des Statistischen Jahrbuchs,
        # seit 1995). Beträge in Euro; die Quelle rechnet in Tausend Euro und
        # ist damit auf Tausend genau — mehr behauptet auch diese Tabelle nicht.
        #
        # DIE ABGRENZUNG STEHT IM MODULKOPF VON `council/schulden.py` und ist
        # die wichtigste Angabe der ganzen Schicht: Gezählt wird die Stadt als
        # RECHTSTRÄGER, also Kernhaushalt UND Eigenbetriebe — nicht der Konzern
        # mit seinen rechtlich selbstständigen Beteiligungen. Beide Zahlen
        # heißen „die Schulden der Stadt" und unterscheiden sich um ein
        # Vielfaches; kein Lesepfad darf sie zu einer Reihe mischen.
        #
        # Die vier Artenspalten sind NULL-bar, `insgesamt` nicht. Das ist kein
        # Schönheitsfehler, sondern der Fall 2022: Dort ergeben die Arten im
        # Dokument selbst 1,078 Mio. € mehr als die Summe daneben. Die Summe
        # trägt die unabhängige Pro-Kopf-Gegenprobe, die Aufteilung trägt
        # nichts — also kommt die Summe herein und die Aufteilung nicht.
        # `aufteilung_verworfen` hält fest, wie groß die Lücke war, damit die
        # Seite den leeren Balken erklären kann statt ihn zu verschweigen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_schulden ("
            "jahr INTEGER PRIMARY KEY, "
            "kreditmarkt REAL, "               # Schulden aus Kreditmarktmitteln
            "sondermittel REAL, "              # aus öffentlichen Sondermitteln
            "gebietskoerperschaften REAL, "    # bei Gebietskörperschaften
            "eigenbetriebe REAL, "             # Eigenbetriebe + innere Darlehen
            "insgesamt REAL NOT NULL, "        # die ausgewiesene Summe
            "je_einwohner REAL, "              # Euro je Einwohner*in
            "aufteilung_verworfen REAL, "      # Lücke der Summenprobe, sonst NULL
            "revidiert INTEGER NOT NULL DEFAULT 0, "   # „r" der Quelle
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Was die Stadt in einem Jahr WIRKLICH investiert hat — Tabellen 1107
        # (2003–2009) und 1107-1 (2010–2025) des Statistischen Jahrbuchs.
        # Beträge in Euro; die Quelle rechnet in Tausend Euro.
        #
        # NICHT ZU VERWECHSELN mit `council_investitionen`: Das sind die
        # PLANZAHLEN aus dem Finanzhaushalt des Haushaltsplans, gegliedert nach
        # Teilhaushalten. Hier stehen die Rechnungsergebnisse, gegliedert nach
        # Auszahlungsarten. Die beiden Summen sind verschieden abgegrenzt und
        # dürfen nicht voneinander abgezogen werden — die Begründung steht im
        # Kopf von `council/investitionen_ist.py`.
        #
        # `regelwerk` ist der Grund für die eigene Spalte statt einer stillen
        # Annahme: Zum 01.01.2010 stellte die Stadt von kameraler auf doppische
        # Buchführung um, und das Dokument trennt seine beiden Tabellen genau
        # dort — mit eigener Fußnote. Eine Kurve, die über 2009/2010 hinweg
        # durchzieht, behauptet eine Vergleichbarkeit, die die Quelle bestreitet.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_investitionen_ist ("
            "jahr INTEGER PRIMARY KEY, "
            "regelwerk TEXT NOT NULL, "        # kameral | doppik
            "insgesamt REAL NOT NULL, "        # die ausgewiesene Summenspalte
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Die Aufteilung nach Auszahlungsart — eigene Tabelle, weil die Zahl
        # der Arten vom Regelwerk abhängt (kameral vier, doppisch sechs) und
        # eine gemeinsame Spalte für „bewegliches Vermögen" zwei Begriffe aus
        # zwei Rechnungswesen unter einen Namen zwänge.
        #
        # `titel` reist mit der Zeile, statt im Frontend zu stehen: Die
        # Legende soll nicht in zwei Sprachen existieren, und die Überschrift
        # ist eine Angabe der Quelle wie der Betrag selbst.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_investitionen_ist_arten ("
            "jahr INTEGER NOT NULL, "
            "feld TEXT NOT NULL, "             # Schlüssel aus investitionen_ist.SPALTEN
            "titel TEXT NOT NULL, "            # die Überschrift der Quelle
            "reihenfolge INTEGER NOT NULL, "   # Spaltenfolge der Tabelle
            "betrag REAL NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, feld))"
        )
        # Die Jahrgänge, die es NICHT in den Bestand geschafft haben — mit
        # dem, was an ihnen gemessen wurde.
        #
        # Dieselbe Rolle wie `aufteilung_verworfen` in `council_schulden`, nur
        # eine Tabelle weiter: Dort trägt die gerettete Zeile ihre Lücke in
        # einer eigenen Spalte, hier gibt es keine Zeile, die sie tragen
        # könnte (die Probe reißt, eine zweite gibt es nicht, also fällt der
        # ganze Jahrgang — s. `council/investitionen_ist.py`).
        #
        # `differenz` ist der Grund für diese Tabelle: Ohne sie stünde die
        # gemessene Lücke nur als Fließtext im `grund` und wäre für die Seite
        # nicht mehr zu haben, ohne einen Satz zurückzuparsen. `NULL`, wo
        # nichts zu messen war (eine Zeile, die sich nicht zerlegen ließ) —
        # eine Null behauptete dort „es passte genau".
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_investitionen_ist_verworfen ("
            "jahr INTEGER PRIMARY KEY, "
            "regelwerk TEXT NOT NULL, "        # kameral | doppik
            "grund TEXT NOT NULL, "            # der Satz aus dem Parser
            "differenz REAL, "                 # Arten minus Summe, in Euro
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Die lange Ausgabenreihe — Datensatz 1102, ein Betrag je Jahr seit
        # 1972 (council/ausgabenreihe.py). Beträge in Euro; die Quelle rechnet
        # in Tausend Euro.
        #
        # `regelwerk` trennt die beiden Größen an der Naht 2009/2010, genau
        # wie in `council_investitionen_ist` und aus derselben Fußnote
        # derselben Quelle: Links steht das Anordnungssoll des
        # Verwaltungshaushalts, rechts die ordentlichen Aufwendungen der
        # Gesamtergebnisrechnung.
        #
        # WAS HIER BEWUSST NICHT STEHT: die Einwohnerzahl und der Betrag je
        # Einwohner*in, obwohl beide Quellen sie führen und die Pro-Kopf-Probe
        # sie braucht. Sie bleiben im Parser. Der Grund ist keine Sparsamkeit,
        # sondern eine Sperre: Läge der Divisor in dieser Tabelle, wäre die
        # naheliegendste Grafik der Seite „Ausgaben pro Kopf seit 1972" — und
        # die wäre falsch, weil die Einwohnerreihe zwei Zensus-Brüche hat
        # (2011 und 2022, s. die Fußnote auf /haushalt/schulden). Was die API
        # nicht liefern kann, kann das Frontend nicht versehentlich zeichnen.
        #
        # `konflikt_betrag` ist der Betrag, den die ANDERE Quelle für dieses
        # Jahr nennt — gefüllt nur, wo PDF und CSV sich widersprechen (2021).
        # Dieselbe Rolle wie `differenz` in
        # `council_investitionen_ist_verworfen`: Er macht aus „hier gab es
        # einen Widerspruch" eine Zahl, die die Seite anschreiben kann.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_ausgabenreihe ("
            "jahr INTEGER PRIMARY KEY, "
            "regelwerk TEXT NOT NULL, "        # kameral | doppik
            "betrag REAL NOT NULL, "           # in Euro
            "quelle TEXT NOT NULL, "           # pdf | csv — wer den Wert lieferte
            "proben TEXT NOT NULL, "           # bestandene Proben, kommagetrennt
            "konflikt_betrag REAL, "           # was die andere Quelle sagt
            "konflikt_quelle TEXT, "
            "revidiert INTEGER NOT NULL DEFAULT 0, "   # „r" der Quelle
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Der Bürgschaftsbestand aus dem Jahresabschluss (council/
        # buergschaften.py) — wofür die Stadt geradesteht, nicht was sie
        # schuldet. 2024: 220,3 Mio. € gegen 43,7 Mio. € eigene Geldschulden.
        #
        # `genau` und `aus_folgejahr` sind keine Technik, sondern Angaben über
        # die Zahl: Die Quelle nennt den Betrag 2019/2020 auf den Cent und ab
        # 2022 nur noch gerundet („rd. 220,3 Millionen"), und 2021 nennt sie
        # ihn überhaupt nicht — dieser Wert steht allein im Dokument des
        # Folgejahres. Ohne beide Spalten sähen sechs verschieden belegte
        # Jahrgänge in der Anzeige gleich aus.
        # Die Gebührenbedarfsberechnung (`council/gebuehren.py`) — die
        # Rechnung, aus der die Abfall- und Straßenreinigungsgebühren
        # entstehen. Von allen Zahlen des Haushalts landet keine so direkt im
        # Portemonnaie.
        #
        # `gebuehr` und `bezugsmenge` sind NULLBAR, und das ist eine Aussage:
        # Die Abfallsammlung erhebt eine Grundgebühr UND eine Gebühr je Liter
        # Behältervolumen, dort gibt es keine einzelne Division. Eine 0 wäre
        # dort eine Behauptung, und eine erfundene Division wäre schlimmer als
        # keine. Die Kaskade ist trotzdem geprüft — welche Proben liefen,
        # steht je Zeile in `proben`.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_gebuehren ("
            "jahr INTEGER NOT NULL, "
            "bereich TEXT NOT NULL, "          # Kürzel aus gebuehren.BEREICHE
            "bereich_name TEXT NOT NULL, "
            "kostenkalkulation REAL NOT NULL, "
            "abzuege REAL NOT NULL, "          # negativ
            "zu_deckende_kosten REAL NOT NULL, "
            "bezugsmenge REAL, "
            "bezugseinheit TEXT, "
            "gebuehr REAL, "                   # die errechnete, 3 Nachkommast.
            "gebuehrenvorschlag REAL, "        # die gerundete an den Rat
            "template_number TEXT, "
            "proben TEXT NOT NULL, "
            "herkunft_id INTEGER, "
            "fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, bereich))"
        )
        # Die zwölf konkreten Verwaltungsvorschläge aus Anlage 4. Eine eigene
        # Tabelle ist nötig, weil die Abfallsammlung nicht EINEN Satz hat:
        # Grundgebühr, Litergebühr, Karten und Anlieferungsmengen dürfen nicht
        # in eine erfundene Durchschnittsgebühr gepresst werden.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_gebuehrensaetze ("
            "jahr INTEGER NOT NULL, "
            "schluessel TEXT NOT NULL, "
            "bereich TEXT NOT NULL, "
            "bezeichnung TEXT NOT NULL, "
            "betrag REAL NOT NULL, "
            "einheit TEXT NOT NULL, "
            "vorjahr REAL, "
            "veraenderung_prozent REAL, "
            "template_number TEXT, "
            "proben TEXT NOT NULL, "
            "herkunft_id INTEGER, "
            "fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, schluessel))"
        )

        # Die Haushaltssatzung — der Rahmen, den der Haushaltsplan bekommt
        # (`council/haushaltssatzung.py`). Drei Größen standen bis 08/2026
        # nirgends im Bereich: die Kreditermächtigung (§ 2), der Höchstbetrag
        # für Liquiditätskredite (§ 4) und der Finanzhaushalt als Ganzes
        # (§ 1.2) — bisher wurden daraus nur die Investitionen gelesen.
        #
        # `fassung` IST KEIN TECHNIKFELD. Alle Satzungen im
        # Ratsinformationssystem sind **Verwaltungsentwürfe**; die beschlossene
        # Fassung erscheint im Amtsblatt. Eine Anzeige, die das wegließe,
        # machte aus einem Vorschlag der Verwaltung einen Ratsbeschluss.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_haushaltssatzung ("
            "jahr INTEGER NOT NULL, "
            "nachtrag INTEGER NOT NULL DEFAULT 0, "   # 0 = die Satzung selbst
            "fassung TEXT NOT NULL, "                 # entwurf | unbekannt
            "ordentliche_ertraege REAL NOT NULL, "
            "ordentliche_aufwendungen REAL NOT NULL, "
            "ao_ertraege REAL NOT NULL, "
            "ao_aufwendungen REAL NOT NULL, "
            "ein_laufend REAL NOT NULL, aus_laufend REAL NOT NULL, "
            "ein_invest REAL NOT NULL, aus_invest REAL NOT NULL, "
            "ein_finanz REAL NOT NULL, aus_finanz REAL NOT NULL, "
            # Die beiden „Nachrichtlich"-Zeilen. Sie stehen NICHT nur als
            # Bequemlichkeit hier: Sie sind die Probe, an der die sechs Zeilen
            # darüber hängen, und wer sie mitspeichert, kann sie nachrechnen,
            # ohne das PDF noch einmal zu holen.
            "ein_gesamt REAL NOT NULL, aus_gesamt REAL NOT NULL, "
            # Nullbar, weil ein fehlender Paragraph etwas anderes ist als eine
            # Null: `kredite_investitionen = 0` heißt „nicht veranschlagt" (so
            # steht es dort in jedem gelesenen Jahrgang), NULL hieße „die
            # Satzung sagt dazu nichts".
            "kredite_investitionen REAL, "
            "verpflichtungsermaechtigungen REAL, "
            "liquiditaetskredite REAL, "
            # Ab dem Jahrgang 2025 nennt § 5 nur noch die Gewerbesteuer und
            # verweist für die Grundsteuer auf eine eigene Satzung.
            "hebesatz_grundsteuer_a INTEGER, "
            "hebesatz_grundsteuer_b INTEGER, "
            "hebesatz_gewerbesteuer INTEGER, "
            "sitzung_am TEXT, "                       # NULL bei „xx.xx.JJJJ"
            "template_number TEXT, "
            "proben TEXT NOT NULL, "
            "herkunft_id INTEGER, "
            "fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, nachtrag))"
        )

        # Die Änderungslisten zum Haushalt (council/aenderungslisten.py) —
        # was am Verwaltungsentwurf im Verfahren noch geändert wurde, Position
        # für Position. Je Zeile EIN Planjahr: Dieselbe Maßnahme steht im
        # Dokument je betroffenem Jahr noch einmal, mit eigenem Betrag.
        #
        # `thh` ist NULLBAR, und das ist eine Aussage: Der 2019er-Jahrgang
        # führt pauschale Minderausgaben über „alle" Teilhaushalte.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_haushalt_aenderungen ("
            "jahrgang INTEGER NOT NULL, "      # Haushaltsjahrgang der Liste
            "liste TEXT NOT NULL, "            # verwaltung_1..3 | afb_beschlossen
            "jahr INTEGER NOT NULL, "          # Planjahr der Position
            "lfd INTEGER NOT NULL, "
            "thh INTEGER, "                    # NULL = „alle" (pauschal)
            "seite_entwurf INTEGER, "
            "produkt TEXT, "
            "bezeichnung TEXT NOT NULL, "
            "ertrag REAL, "                    # Euro; NULL = kein Betrag in
            "aufwand REAL, "                   # dieser Spalte (Vermerke: beide)
            "erlaeuterung TEXT, "              # die Erläuterungs-Spalte des PDFs
            # WER die Position vorgeschlagen hat — „Verw. I“, „SPD/ BÜNDNIS
            # 90/DIE GRÜNEN“. NULL, wo das Dokument die Spalte „Vorschlag
            # von“ nicht führt; das sind 17 der 18 EHH-Dokumente.
            "urheber TEXT, "
            "dokument_id INTEGER NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahrgang, liste, jahr, lfd))"
        )
        # Erläuterungs- (26.08.2026) und Urheber-Spalte (30.08.2026) kamen
        # nach dem ersten Ingest dazu — additiv, gefüllt werden sie vom
        # nächsten Ingest-Lauf (der je (jahrgang, liste) ohnehin löscht und
        # neu schreibt).
        aend_cols = {r[1] for r in self._conn.execute(
            "PRAGMA table_info(council_haushalt_aenderungen)").fetchall()}
        for spalte in ("erlaeuterung", "urheber"):
            if aend_cols and spalte not in aend_cols:
                self._conn.execute(
                    f"ALTER TABLE council_haushalt_aenderungen ADD COLUMN {spalte} TEXT")
        # Die „Zusammenstellung der Veränderungen" derselben Dokumente — der
        # Rahmen, an dem jede Positionsliste bewiesen wurde. Sie trägt auch,
        # was NUR hier steht: die politisch beschlossene Änderung mit ihrem
        # Urheber-Label („SPD/CDU/FDP  0 / −218.299") in den AFB-Dateien.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_haushalt_aenderungen_summen ("
            "jahrgang INTEGER NOT NULL, "
            "liste TEXT NOT NULL, "            # das DOKUMENT, aus dem sie stammt
            "jahr INTEGER NOT NULL, "
            "typ TEXT NOT NULL, "              # entwurf | liste | endsumme
            "label TEXT NOT NULL, "            # „Änderungsliste Verw. I", „SPD/CDU/FDP" …
            "ertraege REAL NOT NULL, "
            "aufwendungen REAL NOT NULL, "
            "saldo REAL NOT NULL, "
            # 1 = diese Zeile summiert die Positionen ihres Dokuments („die
            # eigene"); bei kumulierten Dokumenten trägt keine Zeile die 1 —
            # dort summieren die Positionen auf ALLE Listen zusammen.
            "eigene INTEGER NOT NULL DEFAULT 0, "
            "dokument_id INTEGER NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahrgang, liste, jahr, typ, label))"
        )

        # Dieselben Änderungslisten, aber für den FINANZhaushalt
        # (council/aenderungslisten_fhh.py). EIGENE Tabellen statt einer
        # Spalte „haushalt“ in den beiden darüber: Die Zeilen haben eine
        # andere Form — fünf Betragsspalten statt zwei, dazu der
        # Investitionscode. In einer gemeinsamen Tabelle wären beide Seiten
        # zur Hälfte NULL, und jede Abfrage müsste erst filtern, welche
        # Spalten sie überhaupt lesen darf.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_haushalt_aenderungen_fhh ("
            "jahrgang INTEGER NOT NULL, "
            "liste TEXT NOT NULL, "            # verwaltung_1..3 | afb_beschlossen
            "jahr INTEGER NOT NULL, "          # Planjahr der Position
            "lfd INTEGER NOT NULL, "
            "thh INTEGER, "
            # TEXT, nicht INTEGER: Die Spalte „Seite im HH-Entwurf“ trägt auch
            # „neu“ — dann steht die Position im Entwurf noch gar nicht.
            "seite_entwurf TEXT, "
            # Der Investitionscode des Programms („I10.089904.500“). Er ist
            # der Anschluss an council_investitionsmassnahmen: Über ihn lässt
            # sich sagen, WELCHES Vorhaben im Verfahren geändert wurde.
            "produkt TEXT, "
            "bezeichnung TEXT NOT NULL, "
            # Die fünf Betragsspalten. NULL = Zelle leer (reine
            # Haushaltsvermerke tragen gar keine), 0 = Gedankenstrich, also
            # eine ausdrückliche Null.
            "soll_entwurf REAL, "
            "einzahlung REAL, "
            "auszahlung REAL, "
            "ve REAL, "                        # Verpflichtungsermächtigungen
            "soll_neu REAL, "
            "erlaeuterung TEXT, "
            "urheber TEXT, "
            "dokument_id INTEGER NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahrgang, liste, jahr, lfd))"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_haushalt_aenderungen_fhh_summen ("
            "jahrgang INTEGER NOT NULL, "
            "liste TEXT NOT NULL, "
            "jahr INTEGER NOT NULL, "
            "typ TEXT NOT NULL, "              # entwurf | liste | endsumme
            "label TEXT NOT NULL, "
            "einzahlungen REAL NOT NULL, "
            "auszahlungen REAL NOT NULL, "
            "saldo REAL NOT NULL, "
            # NULL, wo das Dokument keine VE-Spalte führt (die
            # Beschluss-Dateien). Sie zählt NICHT in den Saldo.
            "ve REAL, "
            "eigene INTEGER NOT NULL DEFAULT 0, "
            "dokument_id INTEGER NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahrgang, liste, jahr, typ, label))"
        )

        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_wirtschaftsplaene ("
            "betrieb TEXT NOT NULL, "          # Kürzel aus wirtschaftsplan.BETRIEBE
            "jahr INTEGER NOT NULL, "          # Haushaltsjahr, nicht Jahr der Vorlage
            "betrieb_name TEXT NOT NULL, "
            "template_number TEXT NOT NULL, "
            # Nullbar seit 20.08.2026: Nicht jede Quelle gibt das volle Tripel.
            # Beschlusstext (EGH) und Erfolgsplan-Tabelle (AWB) liefern Erträge,
            # Aufwendungen UND Ergebnis; bei Bäderbetriebsgesellschaft, Stadion
            # und Bäderbetrieb nennt nur die **Kernzahl** eine geprüfte Zahl —
            # das Jahresergebnis, das der Rat beschließt. Eine 0 dort wäre eine
            # Behauptung, ein NULL ist die Auskunft „diese Quelle sagt es nicht".
            "ertraege REAL, "                  # Erfolgsplan, in Euro
            "aufwendungen REAL, "
            "steuern REAL, "                   # bis 2020 keine eigene Zeile → 0
            "ergebnis REAL NOT NULL, "         # als einziges immer da
            "vermoegensplan REAL, "            # Ein- = Auszahlungen, eine Zahl
            # NICHT dasselbe wie `vermoegensplan`, und die Verwechslung wäre
            # teuer: Der Vermögensplan ist die Gesamtsumme (Ein- = Auszahlungen),
            # `investitionen` ein POSTEN darin — daneben stehen dort etwa
            # Tilgungsleistungen. Der Beschlusstext des Bäderbetriebs nennt nur
            # diesen Posten („Der Vermögensplan weist Investitionen in Höhe von
            # 10.752.000 Euro aus"), der des EGH nur die Summe. Zwei Spalten,
            # weil es zwei Angaben sind.
            "investitionen REAL, "
            "verpflichtungen REAL, "           # Verpflichtungsermächtigungen
            "entwurf_vom TEXT, "               # Stand des Verwaltungsentwurfs
            "proben TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            # Ein Betrieb, ein Haushaltsjahr, ein Plan. Der Schlüssel ist
            # bewusst NICHT die Vorlagen-Nummer: Zu einem Jahr kann es eine
            # Anpassung geben (eine zweite Vorlage), und die soll den Stand
            # ersetzen und nicht danebenstehen.
            "PRIMARY KEY (betrieb, jahr))"
        )
        # Bestände, die vor dem 20.08.2026 angelegt wurden, tragen `ertraege`
        # und `aufwendungen` noch als NOT NULL. SQLite kann eine Spalte nicht
        # nachträglich nullbar machen — die Tabelle muss neu gebaut und der
        # Inhalt umkopiert werden. Erkannt wird der Altstand am Schema selbst
        # (`PRAGMA table_info`, Spalte `notnull`), nicht an einer Versionsnummer:
        # So läuft der Umbau genau einmal und auf jedem Bestand von allein.
        wp_spalten = self._conn.execute(
            "PRAGMA table_info(council_wirtschaftsplaene)").fetchall()
        # `investitionen` kam am 21.08.2026 dazu (Tim: „da stehen ja ganz, ganz
        # viele Zahlen drin" — die Karte des Bäderbetriebs zeigte nur eine Null).
        # Ein schlichtes ADD COLUMN reicht: Die Spalte ist nullbar, und NULL ist
        # hier die richtige Auskunft für jeden Bestand, der sie noch nicht kennt.
        if not any(s[1] == "investitionen" for s in wp_spalten):
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE council_wirtschaftsplaene ADD COLUMN investitionen REAL")
            wp_spalten = self._conn.execute(
                "PRAGMA table_info(council_wirtschaftsplaene)").fetchall()
        if any(s[1] == "ertraege" and s[3] == 1 for s in wp_spalten):
            # `with self._conn` und nicht `self.transaktion()`: Diese Migration
            # läuft aus `_migrate()` heraus, also noch während `__init__` — der
            # Sammel-Zustand der Transaktionshilfe existiert da noch nicht.
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE council_wirtschaftsplaene RENAME TO _wp_alt")
                self._conn.execute(
                    "CREATE TABLE council_wirtschaftsplaene ("
                    "betrieb TEXT NOT NULL, jahr INTEGER NOT NULL, "
                    "betrieb_name TEXT NOT NULL, template_number TEXT NOT NULL, "
                    "ertraege REAL, aufwendungen REAL, steuern REAL, "
                    "ergebnis REAL NOT NULL, vermoegensplan REAL, "
                    "verpflichtungen REAL, entwurf_vom TEXT, proben TEXT NOT NULL, "
                    "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
                    "PRIMARY KEY (betrieb, jahr))")
                # Spaltenweise benannt und nicht `SELECT *`: Eine später
                # ergänzte Spalte in der Altfassung würde die Reihenfolge
                # verschieben, und dann landeten Beträge in Textfeldern.
                self._conn.execute(
                    "INSERT INTO council_wirtschaftsplaene "
                    "(betrieb, jahr, betrieb_name, template_number, ertraege, aufwendungen, "
                    " steuern, ergebnis, vermoegensplan, verpflichtungen, entwurf_vom, "
                    " proben, herkunft_id, fetched_at) "
                    "SELECT betrieb, jahr, betrieb_name, template_number, ertraege, "
                    " aufwendungen, steuern, ergebnis, vermoegensplan, verpflichtungen, "
                    " entwurf_vom, proben, herkunft_id, fetched_at FROM _wp_alt")
                alt_n = self._conn.execute("SELECT COUNT(*) FROM _wp_alt").fetchone()[0]
                neu_n = self._conn.execute(
                    "SELECT COUNT(*) FROM council_wirtschaftsplaene").fetchone()[0]
                if alt_n != neu_n:  # pragma: no cover — Notbremse
                    raise RuntimeError(
                        f"Umbau von council_wirtschaftsplaene: {alt_n} Zeilen vorher, "
                        f"{neu_n} nachher — nichts wird verworfen")
                self._conn.execute("DROP TABLE _wp_alt")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_buergschaften ("
            "jahr INTEGER PRIMARY KEY, "
            "bestand REAL NOT NULL, "          # in Euro
            "genau INTEGER NOT NULL, "         # 1 = auf den Cent belegt
            "aus_folgejahr INTEGER NOT NULL, " # 1 = Anfangsbestand des Folgejahrs
            "quelle TEXT NOT NULL, "           # anhang | tabelle
            "grund TEXT, "                     # Begründung im Wortlaut der Stadt
            "einzelbetrag REAL, "              # die im Grund genannte Zahl (2022)
            "proben TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Der Anlagenspiegel (council/anlagenspiegel.py): was aus Investitionen
        # wird. Je Jahr und Vermögensposition eine Zeile mit dreizehn Werten —
        # Anschaffungswerte, Abschreibungen, Buchwerte.
        #
        # `spalten` steht bewusst DRIN, obwohl es eine Eigenschaft der Vorlage
        # ist und keine der Zahlen: Bis 2020 fehlt dem Abschreibungs-Block die
        # Umbuchungs-Spalte, und ohne diese Angabe sähe eine Zeile, deren
        # Abschreibungskette gar nicht schließen KANN, aus wie eine, die es
        # nicht tut. Die Anzeige darf den Unterschied benennen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_anlagenspiegel ("
            "jahr INTEGER NOT NULL, "
            "nr TEXT NOT NULL, "               # Gliederung: 1, 1.1, 2, 2.3 …
            "bezeichnung TEXT NOT NULL, "
            "spalten INTEGER NOT NULL, "       # 12 (bis 2020) oder 13
            "ahk_anfang REAL, zugaenge REAL, abgaenge REAL, "
            "umbuchungen REAL, ahk_ende REAL, "
            "abschr_anfang REAL, abschreibung REAL, aufloesungen REAL, "
            "zuschreibungen REAL, abschr_umbuchungen REAL, abschr_ende REAL, "
            "buchwert REAL, buchwert_vorjahr REAL, "
            "proben TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, nr))"
        )
        # Die Untergliederung des Infrastrukturvermögens — Straßen, Brücken,
        # Gleisanlagen. Sie steht NICHT im Anlagenspiegel (der führt
        # Infrastruktur als eine Zeile), sondern in den Erläuterungen, und erst
        # ab 2022 in dieser Form. Eigene Tabelle statt einer Spalte: andere
        # Quelle im selben Dokument, andere Abdeckung.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_vermoegensgruppen ("
            "jahr INTEGER NOT NULL, "
            "gruppe TEXT NOT NULL, "
            "buchwert REAL NOT NULL, "
            "buchwert_vorjahr REAL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, gruppe))"
        )
        # Die dreizehn Kennzahlen (council/kennzahlen.py): die Anlage, mit der
        # jeder Rechenschaftsbericht seinen Jahresabschluss zusammenfasst.
        #
        # `bericht_jahr` STEHT IM SCHLÜSSEL, und das ist der Kern der Tabelle:
        # Jeder Bericht druckt fünf Jahre, die Jahrgänge stehen also mehrfach
        # da — und nicht immer gleich. Die Steuerquote 2021 heißt im Bericht
        # 2021 45,90 %, im Bericht 2022 49,05 % und im Bericht 2023 wieder
        # 45,92 %. Ohne den Bericht im Schlüssel überschriebe der jüngere
        # Stand den älteren still, und die Korrektur — die eigentliche
        # Nachricht — wäre weg.
        #
        # `stellen` ist die Zahl der GEDRUCKTEN Nachkommastellen. 2019 steht
        # „48%", ab 2021 „53,15%"; ohne diese Angabe meldete der Vergleich
        # zweier Berichte reihenweise Abweichungen, die nur Rundung sind.
        #
        # `fassung` nummeriert den gedruckten Rechenweg. Wechselt er, darf
        # über die Stelle keine Linie laufen: Aus „Aufwand für Personal
        # (inklusive Versorgung)" wurde „Aufwendungen für aktives Personal",
        # und die Quote fällt dadurch um rund einen Prozentpunkt.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_kennzahlen ("
            "bericht_jahr INTEGER NOT NULL, "
            "kennzahl TEXT NOT NULL, "
            "jahr INTEGER NOT NULL, "
            "label TEXT NOT NULL, "
            "wert REAL NOT NULL, "
            "einheit TEXT NOT NULL, "          # prozent | eur | anzahl
            "stellen INTEGER NOT NULL, "
            "fassung INTEGER, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (bericht_jahr, kennzahl, jahr))"
        )
        # Die gedruckten Rechenwege — „Ermittlung: Sachvermögen * 100 /
        # Bilanzsumme". Eigene Tabelle, weil sie je Bericht einmal gelten und
        # nicht je Jahrgang; und weil sie den Text tragen, den die Seite
        # zitiert, statt einer Formel, die wir uns ausgedacht hätten.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_kennzahl_formeln ("
            "bericht_jahr INTEGER NOT NULL, "
            "kennzahl TEXT NOT NULL, "
            "fassung INTEGER NOT NULL, "
            "ueberschrift TEXT NOT NULL, "
            "formel TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (bericht_jahr, kennzahl))"
        )
        # Die dritte Schuldenzahl (council/integrierte_schulden.py): was der
        # ganze „Konzern Stadt" schuldet, anteilig nach Beteiligungshöhe —
        # 31.12.2024 rund 740,3 Mio. € gegen 294,9 Mio. € der Jahrbuch-Reihe.
        #
        # EIN STICHTAG JE AUSGABE, bewusst keine Zeitreihe: Welche Unternehmen
        # mitgerechnet werden, wechselt zwischen den Ausgaben, und die
        # Statistischen Ämter raten selbst davon ab, Jahrgänge zu vergleichen.
        # Die Tabelle kann trotzdem mehrere Jahre führen — sie darf nur nicht
        # als Kurve gezeichnet werden.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_integrierte_schulden ("
            "jahr INTEGER PRIMARY KEY, "
            "ars TEXT NOT NULL, "              # Regionalschlüssel, nie der Name
            "bevoelkerung REAL, "
            "insgesamt REAL NOT NULL, je_einwohner REAL, "
            "kernhaushalt REAL, extrahaushalte REAL, sonstige REAL, "
            # Die Aufteilung nach Beteiligungshöhe — daraus rechnet sich der
            # Anteil, der KEINE Haftung begründet (2024: 58 %).
            "extra_unter_50 REAL, sonstige_unter_50 REAL, "
            # Die Veränderung, die der Band selbst ausweist. Angabe der Quelle,
            # nicht unsere Rechnung — deshalb gespeichert statt abgeleitet.
            "veraenderung REAL, "
            "proben TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Nachbewilligungen nach § 117 NKomVG (council/nachbewilligungen.py).
        # Drei Tabellen, weil hier zwei verschiedene Quellen dieselbe Sache
        # beschreiben und niemals vermischt werden dürfen:
        #
        #   council_nachbewilligungen        — was der Rat beschloss (RIS)
        #   council_nachbewilligung_jahre    — was der Rechenschaftsbericht
        #                                      fürs Jahr insgesamt ausweist
        #   council_nachbewilligung_kanaele  — dessen vier Entscheidungswege
        #
        # Die Aufteilung der beiden letzten folgt `council_investitionen_ist`
        # und `..._arten`: Die Summe steht in der einen, die Aufteilung in der
        # anderen. Sie hier zusammenzuziehen hieße, die Summenzeile des
        # Dokuments viermal zu wiederholen — und die Probe, dass die Teile sie
        # ergeben, hätte nichts mehr, wogegen sie prüfen könnte.
        #
        # `betrag` ist NULL, wo der Titel nur eine Wertgrenze nennt (die neun
        # Sammelberichte). Eine 0 stünde dort für „nichts nachbewilligt" und
        # wäre falsch; NULL heißt „diese Zeile trägt keinen Betrag".
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_nachbewilligungen ("
            "template_number TEXT PRIMARY KEY, "
            "jahr INTEGER, "                   # aus der Vorlagen-Nummer
            "titel TEXT NOT NULL, "
            "art TEXT NOT NULL, "              # bewilligung|verpflichtungs…|schwelle
            "kategorie TEXT NOT NULL, "        # ueberplanmaessig|ausser…|beides
            "betrag REAL, "                    # NULL bei art='schwelle'
            "betrag_quelle TEXT, "             # titel | beschlussvorschlag
            "beschlossen INTEGER NOT NULL DEFAULT 0, "
            # Zwei Spalten, weil es zwei verschiedene Fragen sind:
            # `im_rat` = das Plenum hat abgestimmt (die wörtliche Auskunft,
            # die auf der Seite steht). `ratsentscheidung` = der
            # Rechenschaftsbericht bucht es als „Beschluss des Rates" —
            # einschließlich der Fälle, die der Finanzausschuss abschließend
            # entscheidet. Nur die zweite darf in einen Rats-Anteil; die erste
            # liegt 2024 um 28 % daneben (s. council/nachbewilligungen.py).
            "im_rat INTEGER NOT NULL DEFAULT 0, "
            "ratsentscheidung INTEGER NOT NULL DEFAULT 0, "
            # Für den Link auf die vorhandene Beschluss-Seite
            # (/council/decision?id=). Der maßgebliche Beschluss ist der des
            # Rates, sonst der jüngste — dieselbe Ordnung wie anderswo.
            "beschluss_id INTEGER, "
            "gremien TEXT, "                   # JSON: wo sie beraten wurde
            "volltextprobe INTEGER NOT NULL DEFAULT 0, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_nachbewilligung_jahre ("
            "jahr INTEGER PRIMARY KEY, "
            # Was die Summenzeile der Tabelle selbst ausweist …
            "summe_konsumtiv REAL NOT NULL, "
            "summe_investiv REAL NOT NULL, "
            # … und was der Fließtext darüber behauptet. Beides wird
            # gespeichert, gerade WEIL es 2022 auseinanderfällt: Wer nur eine
            # der beiden Zahlen behielte, hätte den Widerspruch weggeräumt.
            "text_gesamt REAL, "
            "verpflichtungen_betrag REAL, "
            # Das Ergebnis der Tabellenprobe im Klartext — es steht auf der
            # Seite, nicht nur im Log.
            "probe_ok INTEGER NOT NULL DEFAULT 0, "
            "probe_text TEXT, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_nachbewilligung_kanaele ("
            "jahr INTEGER NOT NULL, "
            "kanal TEXT NOT NULL, "            # rat|oberbuergermeister|…
            "label TEXT NOT NULL, "            # der Wortlaut der Stadt
            "anzahl_konsumtiv INTEGER NOT NULL, "
            "betrag_konsumtiv REAL NOT NULL, "
            "anzahl_investiv INTEGER NOT NULL, "
            "betrag_investiv REAL NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, kanal))"
        )
        # Angenommene Zuwendungen je Ratsvorlage (council/spenden.py). Eine
        # Zeile je Vorlage, nicht je Jahr: Der Jahreswert entsteht erst beim
        # Lesen, und die Vorlagen-Nummer ist der Weg zur Beschluss-Seite.
        #
        # Was hier bewusst FEHLT: eine Spalte für die Gebenden. Die Namen
        # stehen nur in der Anlage „Zuwendungsliste", die nicht im Bestand ist
        # — und was die Tabelle nicht führen kann, kann die API nicht liefern
        # und das Frontend nicht versehentlich zeigen. Das ist keine
        # Sparsamkeit, sondern die Grenze: Der Ratsbeschluss macht die Summe
        # öffentlich, nicht die Liste dahinter.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_spenden ("
            "template_number TEXT PRIMARY KEY, "
            "jahr INTEGER NOT NULL, "          # Jahr der Sitzung
            "sitzung TEXT NOT NULL, "          # ISO-Datum
            "betrag REAL NOT NULL, "           # in Euro, wie beschlossen
            "gremium TEXT, "                   # Rat | Verwaltungsausschuss
            "layout TEXT, "                    # neu | alt — welcher Abschnitt trug
            "zweitstelle TEXT NOT NULL, "      # identisch | zerlegung
            "proben TEXT NOT NULL, "           # bestandene Proben, kommagetrennt
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Und die Gegenprobe: die Zeilen ohne Zweitstelle, mit dem Satz, warum.
        # Eine Lücke ist eine Auskunft — sie steht auf der Seite, statt still
        # aus der Summe zu fehlen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_spenden_verworfen ("
            "template_number TEXT PRIMARY KEY, "
            "sitzung TEXT, "
            "grund TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Was je Steuerart geplant war und was daraus wurde — Tabelle 1103 des
        # Statistischen Jahrbuchs (council/steuertabellen.py). Beträge in Euro;
        # die Quelle rechnet in Tausend Euro.
        #
        # `art` trägt GENAU die Schreibweise aus `council_steuern.art`, und das
        # ist keine Kosmetik: Der Ist-Wert dieser Tabelle muss sich dort
        # wiederfinden, sonst kommt der Jahrgang nicht herein (Probe
        # `steuerplan_istabgleich`). Zwei Schreibweisen für dieselbe Steuer
        # hießen, dass der Abgleich still ins Leere liefe.
        #
        # `vorlaeufig` ist die Angabe der Quelle über sich selbst: Die jüngste
        # Spalte heißt dort „vorläufiges Rechnungsergebnis" statt
        # „Rechnungsergebnis". Eine Zahl, die noch revidiert werden kann, soll
        # das an sich tragen und nicht nur im Fließtext einer Seite.
        #
        # WAS HIER BEWUSST NICHT STEHT: die Zeile „insgesamt" und die
        # „Finanzzuweisungen". Beide stehen in derselben Tabelle und tragen die
        # Summenprobe mit — aber sie haben in `council_steuern` keine
        # Entsprechung, gegen die sich ihre Jahresbeschriftung prüfen ließe.
        # Was die Probe nicht erreicht, wird nicht gespeichert. (Bei den
        # Finanzzuweisungen kommt hinzu, dass sie NICHT dasselbe sind wie die
        # Schlüsselzuweisungen in `council_steuerkraft` — zwei Abgrenzungen,
        # ein ähnlicher Name.)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_steuerplan ("
            "jahr INTEGER NOT NULL, "
            "art TEXT NOT NULL, "              # = council_steuern.art
            "plan REAL NOT NULL, "             # in Euro
            "ist REAL NOT NULL, "              # in Euro
            "vorlaeufig INTEGER NOT NULL DEFAULT 0, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, art))"
        )
        # Die Realsteuer-Hebesätze seit 1980 — Tabelle 1105 desselben Blatts.
        #
        # Neun Zeilen für 45 Jahre: Die Tabelle führt nur die Jahre, in denen
        # sich etwas geändert hat. Ein Satz gilt bis zur nächsten Änderung, und
        # deshalb ist das eine TREPPE und keine Kurve — zwischen zwei Stufen
        # wird nichts interpoliert, weder hier noch im Frontend
        # (`components/grafik/zeitreihe.tsx`, Modus `treppe`).
        #
        # `vorheriger` ist der Satz, der bis zu diesem Jahr galt — NULL in der
        # ersten Zeile. Er steht mit in der Tabelle, weil die Aussage der Zeile
        # die Änderung ist und nicht der Stand: „445 → 539" ist das, was ein
        # Rat beschließt. Ihn beim Lesen aus der Vorzeile zu rechnen ginge auch,
        # aber nur, solange niemand einen Ausschnitt der Reihe abfragt.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_hebesaetze ("
            "jahr INTEGER NOT NULL, "
            "art TEXT NOT NULL, "              # Grundsteuer A | B | Gewerbesteuer
            "hebesatz INTEGER NOT NULL, "      # Prozentpunkte
            "vorheriger INTEGER, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (jahr, art))"
        )
        # Vorlagen-Volltexte semantisch auffindbar machen: je Vorlage mehrere
        # Chunk-Vektoren (Sachverhalt/Begründung), die die Hybrid-Suche auf die
        # zugehörigen Beschlüsse abbildet. text_hash = SHA-256 des Volltexts —
        # macht das Embedding-Skript idempotent (nur Geändertes wird neu embedded).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_vorlage_embeddings ("
            "template_number TEXT NOT NULL, "
            "chunk_idx INTEGER NOT NULL, "
            "text_hash TEXT NOT NULL, "
            "chunk_text TEXT NOT NULL, "   # der Reranker bekommt die FUNDSTELLE zu sehen
            "vector BLOB NOT NULL, "
            "PRIMARY KEY (template_number, chunk_idx))"
        )
        # Anlagen-Chunks (Task 33): Gutachten, Konzepte, Stellungnahmen — die
        # Volltexte lädt scripts/backfill_anlagen_texte.py, die Vektoren baut
        # scripts/embed_anlagen.py. Der schnelle Fragepfad lädt diese Matrix
        # nur bei explizitem Dokumentenbedarf, Deep Research grundsätzlich.
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
        self._migrate_produkt_steckbrief()
        self._migrate_herkunft()
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

    def _migrate_produkt_steckbrief(self) -> None:
        """Produkt-Steckbrief (Kurzbeschreibung, Rechtsgrundlage, Spielraum,
        Wirkungskreis, Zielgruppe) in bestehende Produkt-Tabellen nachrüsten.

        Anders als bei ``council_ergebnisrechnung`` reicht hier ALTER TABLE:
        Der Primärschlüssel (jahr, produkt_nr) bleibt, wie er ist — es kommen
        nur Spalten dazu. Die Werte füllt der nächste Lauf von
        ``scripts/ingest_finanzberichte.py`` nach; bis dahin sind sie NULL und
        die Oberfläche zeigt den Steckbrief schlicht nicht an."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_produkte)").fetchall()}
        with self._conn:
            for name in ("kurzbeschreibung", "auftragsgrundlage", "beeinflussbarkeit",
                         "beeinflussbarkeit_roh", "wirkungskreis", "zielgruppe"):
                if name not in cols:
                    self._conn.execute(f"ALTER TABLE council_produkte ADD COLUMN {name} TEXT")

    #: Wie eine Tabelle ihre Herkunft bisher führte: (Label-Spalte,
    #: URL-Spalte, Quellenart). Drei Schreibweisen für dieselbe Sache — genau
    #: das war der Anlass für `council/herkunft.py`.
    #:
    #: Die Quellenart steht hier nur, wo sie aus der Tabelle folgt. Bei
    #: `council_haushalt` folgt sie das nicht: Ein Jahrgang kam als PDF von
    #: oldenburg.de, ein anderer als CSV aus dem Open-Data-Portal — dort
    #: entscheidet die URL (s. `_herkunft_art_aus_url`).
    _HERKUNFT_ALTFELDER: dict[str, tuple[str | None, str, str | None]] = {
        "council_haushalt":             (None, "source_url", None),
        "council_steuern":              (None, "source_url", "opendata"),
        "council_steuerkraft":          (None, "source_url", "opendata"),
        "council_einwohner":            (None, "source_url", "opendata"),
        "council_ergebnisrechnung":     ("quelle_label", "quelle_url", "ris"),
        # Neu mit der Kassensicht, ohne Altbestand — nichts nachzutragen.
        "council_finanzrechnung":       (None, None, "ris"),
        # Ebenso die Bilanz und ihre Erläuterungen: erst mit der Herkunft
        # entstanden, keine Altspalten.
        "council_bilanz":               (None, None, "ris"),
        "council_bilanz_erlaeuterungen": (None, None, "ris"),
        "council_abweichungsgruende":   ("quelle_label", "quelle_url", "ris"),
        "council_pruefbericht_quellen": ("label", "url", "ris"),
        "council_produkte":             ("quelle_label", "quelle_url", "ris"),
        "council_pruefberichte":        ("quelle_label", "quelle_url", "ris"),
        # Die beiden Konzern-Tabellen sind erst mit der Herkunft entstanden
        # und tragen gar keine Altspalten. Sie stehen hier trotzdem, weil
        # `_herkunft_nachtragen` jede Tabelle aus `HERKUNFT_TABELLEN`
        # nachschlägt; ohne URL-Spalte kehrt es sofort zurück, ohne etwas zu
        # tun. Ein Eintrag „nichts nachzutragen" ist billiger als eine
        # Ausnahme im Nachrüst-Weg.
        "council_konzern_posten":       (None, "quelle_url", "ris"),
        "council_konzern_traeger":      (None, "quelle_url", "ris"),
        # Ebenso der Städtevergleich: erst mit der Herkunft entstanden, keine
        # Altspalten, nichts nachzutragen.
        "council_staedtevergleich":     (None, "quelle_url", "lsn"),
        # Und die Gewerbesteuerstatistik, ebenfalls vom Landesamt.
        "council_gewerbesteuerstatistik": (None, "quelle_url", "lsn"),
        # Und die Planjahre aus dem Gesamtergebnishaushalt.
        "council_ergebnishaushalt":     (None, "quelle_url", "ris"),
        # Ebenso die Investitionen des Finanzhaushalts: neu, ohne Altspalten,
        # Herkunft ausschließlich über `herkunft_id`.
        "council_investitionen":        (None, "quelle_url", "opendata"),
        # Und die Maßnahmen aus Anlage 004: ebenfalls neu, ebenfalls ohne
        # Altspalten. Der Eintrag muss trotzdem stehen — `_herkunft_nachtragen`
        # schlägt hier nach, bevor es merkt, dass es nichts nachzutragen gibt.
        "council_investitionsmassnahmen": (None, "quelle_url", "ris"),
        # Das Ist-Gegenstück aus dem Statistischen Jahrbuch — anders als Plan
        # und Programm kommt es weder vom Portal noch aus dem RIS, sondern von
        # oldenburg.de.
        "council_investitionen_ist":       (None, "quelle_url", "stadt"),
        "council_investitionen_ist_arten": (None, "quelle_url", "stadt"),
        "council_investitionen_ist_verworfen": (None, "quelle_url", "stadt"),
        # Der Stellenplan — ebenfalls neu und ohne Altbestand.
        "council_stellenplan":          (None, "quelle_url", "ris"),
        # Und die Schuldenzeitreihe aus dem Statistischen Jahrbuch.
        "council_schulden":             (None, "quelle_url", "stadt"),
        # Die lange Ausgabenreihe: zwei Quellen — das Jahrbuch der Stadt und
        # das Open-Data-Portal —, deshalb keine feste Art. Nachzutragen ist
        # ohnehin nichts, die Tabelle ist neu.
        "council_ausgabenreihe":        (None, "quelle_url", None),
        # Der Bürgschaftsbestand: eine Quelle, der Jahresabschluss als Anlage
        # im Ratsinformationssystem.
        "council_buergschaften":        (None, "quelle_url", "ris"),
        "council_anlagenspiegel":       (None, "quelle_url", "ris"),
        # Die Kennzahlen und ihre Rechenwege: Anlage des Rechenschaftsberichts,
        # also ebenfalls ein Dokument im Ratsinformationssystem.
        "council_kennzahlen":           (None, "quelle_url", "ris"),
        "council_kennzahl_formeln":     (None, "quelle_url", "ris"),
        "council_vermoegensgruppen":    (None, "quelle_url", "ris"),
        # Die dritte Schuldenzahl: Tabellenband der Statistischen Ämter,
        # also weder Stadt noch Ratsinformationssystem — eigene Art "lsn"
        # wie beim Städtevergleich.
        "council_integrierte_schulden": (None, "quelle_url", "lsn"),
        # Die Nachbewilligungen: neu, ohne Altspalten. Beide Quellen liegen im
        # Ratsinformationssystem — die Vorlagen selbst und der
        # Rechenschaftsbericht als Anlage zum Jahresabschluss.
        "council_nachbewilligungen":        (None, "quelle_url", "ris"),
        "council_nachbewilligung_jahre":    (None, "quelle_url", "ris"),
        "council_nachbewilligung_kanaele":  (None, "quelle_url", "ris"),
        # Die Zuwendungen: Quelle sind Ratsvorlagen im Bürgerinfo, also „ris".
        # Nachzutragen ist nichts, beide Tabellen sind neu.
        "council_spenden":              (None, "quelle_url", "ris"),
        "council_spenden_verworfen":    (None, "quelle_url", "ris"),
        # Die beiden Steuertabellen des Jahrbuchs — neu, ohne Altbestand.
        "council_steuerplan":           (None, "quelle_url", "stadt"),
        "council_hebesaetze":           (None, "quelle_url", "stadt"),
        # Gebührenbedarf und Anlage-4-Tarife sind neu mit Herkunft entstanden;
        # sie haben keine doppelten Altspalten, die nachzutragen wären.
        "council_gebuehren":            (None, "quelle_url", "ris"),
        "council_gebuehrensaetze":      (None, "quelle_url", "ris"),
        # Der Beteiligungsbericht: ebenfalls erst mit der Herkunft entstanden.
        # Seine Dokumente kommen von oldenburg.de, nicht aus dem Bürgerinfo.
        "council_gesellschaften":            (None, "quelle_url", "stadt"),
        "council_gesellschaft_texte":        (None, "quelle_url", "stadt"),
        "council_gesellschaft_kennzahlen":   (None, "quelle_url", "stadt"),
        "council_gesellschaft_personen":     (None, "quelle_url", "stadt"),
        "council_gesellschaft_eigentuemer":  (None, "quelle_url", "stadt"),
    }

    @staticmethod
    def _herkunft_art_aus_url(url: str | None) -> str | None:
        """Quellenart aus einer gespeicherten URL — abgeleitet, nicht geraten.

        Entschieden wird an Zeichenketten, die wörtlich in der URL stehen —
        das Portal, die Stadt-Domain, das Bürgerinfo. Alles andere (etwa ein
        ``file:``-Pfad aus einem Lauf mit ``--pdf``) bleibt ohne Herkunft,
        statt eine Art zu erfinden; ``herkunft_luecken()`` zeigt es dann an."""
        if not url:
            return None
        if "opendata.oldenburg.de" in url:
            return "opendata"
        if "oldenburg.de" in url:
            return "stadt"
        if "buergerinfo" in url or "/getfile" in url:
            return "ris"
        return None

    def _migrate_herkunft(self) -> None:
        """Herkunfts-Fundament nachrüsten: `herkunft_id` an jede Zieltabelle,
        und was in den alten Feldern steht, in `council_herkunft` überführen.

        Rein additiv. Die alten Spalten (`quelle_label`, `quelle_url`,
        `source_url`, `fetched_at`) bleiben unangetastet — sie zu entfernen
        hieße, neun Tabellen neu zu schreiben, darunter vier, deren Inhalt nur
        über einen Download von oldenburg.de wiederzubeschaffen wäre. Deshalb
        genügt hier durchgehend ALTER TABLE, und kein bestehender Wert ändert
        sich.

        **Übernommen wird, was in den Daten steht: Label, URL und — neu — die
        `document_id`, die sich über die URL in `council_anlagen` eindeutig
        auflösen lässt. Fundstelle und Probe bleiben leer bzw. tragen
        `unbekannt`:** Der Altbestand sagt nicht, an welchem Abschnitt er
        gelesen wurde und welche Probe er bestanden hat. Das zu erfinden wäre
        genau die Sorte Angabe, die diese Umstellung abschaffen soll. Der
        nächste Ingest-Lauf trägt beides nach, weil er den Jahrgang ohnehin
        ersetzt."""
        from council import herkunft as _h

        with self._conn:
            for tabelle in _h.HERKUNFT_TABELLEN:
                cols = {r[1] for r in self._conn.execute(
                    f"PRAGMA table_info({tabelle})")}
                if not cols:
                    continue  # Tabelle gibt es in dieser DB (noch) nicht
                if "herkunft_id" not in cols:
                    self._conn.execute(
                        f"ALTER TABLE {tabelle} ADD COLUMN herkunft_id INTEGER")
                self._herkunft_nachtragen(tabelle)

    def _herkunft_nachtragen(self, tabelle: str) -> int:
        """Zeilen einer Tabelle ohne `herkunft_id` aus ihren Altfeldern
        versorgen. Idempotent: Wer schon eine hat, wird nicht angefasst."""
        from council import herkunft as _h

        label_spalte, url_spalte, feste_art = self._HERKUNFT_ALTFELDER[tabelle]
        cols = {r[1] for r in self._conn.execute(f"PRAGMA table_info({tabelle})")}
        if url_spalte not in cols:
            return 0
        gelesen = [label_spalte, url_spalte] if label_spalte in cols else [url_spalte]
        # Je *Kombination* aus Label und URL ein Herkunfts-Datensatz — das ist
        # die Granularität, in der der Altbestand seine Quelle kennt.
        auswahl = ", ".join(gelesen)
        gruppen = self._conn.execute(
            f"SELECT {auswahl}, MAX(fetched_at) AS zuletzt FROM {tabelle} "
            f"WHERE herkunft_id IS NULL GROUP BY {auswahl}").fetchall()
        getroffen = 0
        for g in gruppen:
            url = g[url_spalte]
            label = g[label_spalte] if label_spalte in cols else None
            art = feste_art or self._herkunft_art_aus_url(url)
            if not art or not url:
                # Ohne Verweis keine Herkunft. Lieber eine leere Spalte als
                # ein Datensatz, der auf nichts zeigt.
                continue
            hid = self.merke_herkunft(
                _h.Herkunft(art=art, probe=_h.UNBEKANNT, label=label, url=url,
                            dokument_id=self._dokument_zu_url(url)),
                fetched_at=g["zuletzt"])
            bedingung = f"{url_spalte} IS ?"
            args: list = [url]
            if label_spalte in cols:
                bedingung += f" AND {label_spalte} IS ?"
                args.append(label)
            cur = self._conn.execute(
                f"UPDATE {tabelle} SET herkunft_id = ? "
                f"WHERE herkunft_id IS NULL AND {bedingung}", [hid, *args])
            getroffen += cur.rowcount
        return getroffen

    def _dokument_zu_url(self, url: str | None) -> int | None:
        """Die `council_anlagen.document_id` zu einer Anlagen-URL.

        Der stabile Anker, den der Altbestand nicht mitführte. Nur bei einem
        **eindeutigen** Treffer — zwei Anlagen unter derselben URL wären ein
        Fall für einen Blick, nicht für eine Vermutung."""
        if not url:
            return None
        try:
            treffer = self._conn.execute(
                "SELECT document_id FROM council_anlagen WHERE url = ? LIMIT 2",
                (url,)).fetchall()
        except sqlite3.OperationalError:
            return None
        return treffer[0][0] if len(treffer) == 1 else None

    def _migrate_owner_id(self) -> None:
        """Re-key the per-recipient dedup tables from Telegram chat_id to the
        canonical owner_id (=web_users.id). The map lives in the sibling
        ratslotse.sqlite; existing rows are backfilled via it. Idempotent."""
        cn_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(committee_notifications)").fetchall()}
        sf_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(session_followups_sent)").fetchall()}
        if "owner_id" in cn_cols and "owner_id" in sf_cols:
            return  # already migrated

        # Build chat_id -> owner_id from kern.sqlite if available.
        chat_to_owner: dict[int, int] = {}
        ratslotse_path = self._ratslotse_db_path
        if ratslotse_path is not None and Path(str(ratslotse_path)).exists():
            try:
                src = sqlite3.connect(str(ratslotse_path), timeout=15)
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
                   (ksinr, item_number, title, template_number, kvonr, is_public)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (session.ksinr, i.item_number, i.title,
                     i.template_number, i.kvonr, int(i.is_public))
                    for i in session.agenda_items
                ],
            )
            self._conn.execute(
                "DELETE FROM council_agenda_anlagen WHERE ksinr = ?", (session.ksinr,)
            )
            self._conn.executemany(
                """INSERT OR IGNORE INTO council_agenda_anlagen
                   (ksinr, item_number, label, url, raw_text) VALUES (?, ?, ?, ?, ?)""",
                [
                    (session.ksinr, i.item_number, a.get("label") or "Anlage",
                     a.get("url") or "", a.get("raw_text") or None)
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

    def naechste_sitzung_je_gremium(self) -> dict[str, dict]:
        """Je Gremium der nächste anstehende Termin — für die Ausschuss-Abos,
        die zu jedem Gremium „nächste Sitzung: …" zeigen.

        Nimmt dieselbe Menge wie ``upcoming_sessions`` (``_UPCOMING_FROM``:
        echte Sitzungen plus terminierte aus dem Kalender, Dubletten am selben
        Tag verdeckt) — sonst nennt die Abo-Seite einen anderen Termin als die
        Sitzungsliste. Gremien ohne künftigen Termin fehlen im dict; der
        Aufrufer entscheidet, was er statt eines Datums schreibt.
        """
        from datetime import date
        today = date.today().isoformat()
        rows = self._conn.execute(
            f"""SELECT committee, session_date, session_time {self._UPCOMING_FROM}
                ORDER BY session_date ASC, COALESCE(NULLIF(session_time, ''), '99:99') ASC""",
            (today, today),
        ).fetchall()
        naechste: dict[str, dict] = {}
        for r in rows:
            # Erste Zeile je Gremium gewinnt — die Sortierung oben hat den
            # frühesten Termin nach vorne gelegt. Termine ohne Uhrzeit
            # (``session_time`` ist NOT NULL, aber oft leer) landen am Ende
            # des Tages, sonst verdeckt der Eintrag ohne Zeit den mit.
            naechste.setdefault(r["committee"], {
                "session_date": r["session_date"],
                "session_time": r["session_time"] or None,
            })
        return naechste

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

    #: „Ö 11.3" → Präfix „Ö", Nummer „11.3". Das Präfix ist zugleich der
    #: Öffentlichkeitsmarker (Ö/N) und gehört zur Nummer, nicht davor weg.
    _TOP_NUMMER_RE = re.compile(r"^\s*([A-Za-zÖÄÜöäü]+)\s+([\d.]+?)\.?\s*$")

    #: Wörter, die in Tagesordnungs-Überschriften stehen, ohne einen
    #: Gegenstand zu benennen — sie dürfen keine Gruppe begründen.
    _RUBRIK_WORTE = frozenset({
        "antraege", "antrag", "fraktionen", "fraktion", "gruppen", "gruppe",
        "ratsund", "ausschussmitglieder", "mitglieder", "berichte", "bericht",
        "anfragen", "anregungen", "mitteilungen", "verschiedenes", "verwaltung",
        "official_text", "beschluesse", "vorlagen", "sonstiges", "genehmigung",
        "protokolle", "protokolls", "tagesordnung", "oeffentlicher", "teil",
    })

    @classmethod
    def _titel_worte(cls, titel: str | None) -> set[str]:
        """Tragende Wörter eines Titels — die Handhabe für „ist das dieselbe
        Sache?". Kurzes und Rubrik-Vokabular fliegt raus, sonst gälte jede
        Überschrift mit dem Wort „Antrag" als Vorhaben."""
        gefaltet = cls._falte_namen(titel or "")
        worte = "".join(c if c.isalnum() else " " for c in gefaltet).split()
        return {w for w in worte if len(w) >= 5 and not w.isdigit()
                and w not in cls._RUBRIK_WORTE}

    @classmethod
    def _top_sortierung(cls, item_number: str | None) -> tuple:
        """Sortierschlüssel für eine TOP-Nummer — „Ö 5" vor „Ö 16.4".

        Lexikografisch verglichen stand „Ö 16.4" vor „Ö 5" (und „Ö 10" vor
        „Ö 2"); die Karte listete ihre Punkte damit in einer Reihenfolge, die
        es auf der Tagesordnung nicht gibt. Dieselbe Falle steht schon im
        Frontend dokumentiert (`decision/view.tsx`: „4.10 käme sonst vor 4.2").
        """
        m = cls._TOP_NUMMER_RE.match(item_number or "")
        if not m:
            return (item_number or "",), ()
        return (m.group(1),), tuple(int(t) for t in m.group(2).split(".") if t.isdigit())

    @classmethod
    def _eltern_nummer(cls, item_number: str | None) -> str | None:
        """Nummer des übergeordneten Tagesordnungspunkts — „Ö 11.3" → „Ö 11".

        ``None`` für Punkte ohne Unterebene. Bewusst rein syntaktisch: Ob es
        den Elternpunkt wirklich gibt (und ob er eine Überschrift ist), prüft
        der Aufrufer am Bestand der Sitzung.
        """
        m = cls._TOP_NUMMER_RE.match(item_number or "")
        if not m:
            return None
        praefix, nummer = m.group(1), m.group(2)
        if "." not in nummer:
            return None
        return f"{praefix} {nummer.rsplit('.', 1)[0]}"

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
            if p.get("template_number"):
                rang += 0.2
            # Beschlussvorlage heißt: Die Verwaltung legt etwas zur
            # Entscheidung vor. Das ist unabhängig davon, welches Gremium
            # formal beschließt — und genau daran scheiterte die Auswahl
            # bisher (Tims Befund 19.08.26): Die VBN-Tarifanpassung ist eine
            # Beschlussvorlage, wird im Fachausschuss aber als „Kenntnisnahme"
            # geführt, weil der Rat entscheidet. Sie landete bei 13 von 100
            # und fiel unter die Schwelle, während ein Umsatzsteuer-Bericht
            # mit 30 auf der Karte stand.
            beschlussvorlage = "beschluss" in (p.get("art") or "").lower()
            if beschlussvorlage:
                rang += 1.5
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
            #
            # Nicht aber für Beschlussvorlagen: Deren Prämisse — „hier wird
            # nichts entschieden" — ist schlicht falsch, das Gremium bereitet
            # dann nur die Entscheidung eines anderen vor.
            if (art and "entscheid" not in art and "vorberat" not in art
                    and not beschlussvorlage):
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
        from .dringlichkeit import ist_dringlichkeitsantrag

        heute = date.today()
        bis = (heute + timedelta(days=tage)).isoformat()
        sitzungen = self.sitzungen_im_fenster(tage)
        if not sitzungen:
            return {"found": False, "von": heute.isoformat(), "bis": bis,
                    "sitzungen": [], "punkte": []}

        ph = ",".join("?" * len(sitzungen))
        # ``v.art`` unterscheidet Beschluss- von Berichtsvorlage — das stärkste
        # verfügbare Signal dafür, ob überhaupt etwas entschieden werden soll.
        # Es lag bis 19.08.26 ungenutzt in der Datenbank.
        rohe = self._conn.execute(
            f"SELECT a.ksinr, a.item_number, a.title, a.template_number, a.kvonr, s.summary, "
            f"       v.art, so.text AS social_text "
            f"FROM council_agenda_items a "
            f"LEFT JOIN agenda_item_summaries s ON s.ksinr = a.ksinr AND s.item_number = a.item_number "
            f"LEFT JOIN agenda_item_social so ON so.ksinr = a.ksinr AND so.item_number = a.item_number "
            f"LEFT JOIN council_vorlagen v ON v.kvonr = a.kvonr "
            f"WHERE a.ksinr IN ({ph}) AND a.is_public = 1 ORDER BY a.id",
            [s["ksinr"] for s in sitzungen]).fetchall()
        nach_sitzung = {s["ksinr"]: s for s in sitzungen}

        # Überschriften-Punkte erkennen: „Ö 11 Bauleitplanung Gewerbegebiet
        # Brokhausen" trägt keine Vorlage, darunter hängen Ö 11.1 … Ö 11.4 als
        # Stationen DESSELBEN Vorhabens. Ohne diese Bündelung belegen vier
        # Stationen alle drei Plätze der Sitzung (Tims Befund 19.08.26) — und
        # die Karte zeigt dreimal denselben Bebauungsplan.
        eltern_von = {(r["ksinr"], r["item_number"]): self._eltern_nummer(r["item_number"])
                      for r in rohe}
        kinder_zahl: dict[tuple, int] = {}
        for (ksinr, _nr), eltern in eltern_von.items():
            if eltern:
                kinder_zahl[(ksinr, eltern)] = kinder_zahl.get((ksinr, eltern), 0) + 1
        # Nur ein Punkt OHNE eigene Vorlage ist eine reine Überschrift. Ein
        # Punkt mit Vorlage, unter dem Unterpunkte hängen, ist selbst Inhalt.
        #
        # Und nur, wenn er ein VORHABEN benennt statt einer Rubrik: „Anträge
        # der Fraktionen, Gruppen, Rats- und Ausschussmitglieder" trägt elf
        # völlig verschiedene Themen unter sich; die zu einer Gruppe zu
        # bündeln hieße, zehn davon nie zu zeigen. Beleg dafür, dass es
        # dieselbe Sache ist: ein tragendes Wort der Überschrift steht in
        # JEDEM Unterpunkt („Meerweg", „Brokhausen") — bei einer Rubrik in
        # keinem.
        kinder_worte: dict[tuple, list[set]] = {}
        for r in rohe:
            eltern = eltern_von.get((r["ksinr"], r["item_number"]))
            if eltern:
                kinder_worte.setdefault((r["ksinr"], eltern), []).append(
                    self._titel_worte(r["title"]))
        #
        # Zwei Dinge, die auseinandergehalten werden müssen: Eine KOPFZEILE
        # trägt selbst keinen Inhalt (weder Vorlage noch Gegenstand) und darf
        # nie als Punkt auftauchen — das gilt für Vorhaben UND Rubriken. Nur
        # die Vorhaben bündeln zusätzlich ihre Unterpunkte.
        kopfzeile = {(r["ksinr"], r["item_number"]) for r in rohe
                     if not r["template_number"] and (r["ksinr"], r["item_number"]) in kinder_worte}
        ueberschrift = {}
        for r in rohe:
            schl = (r["ksinr"], r["item_number"])
            if schl not in kopfzeile:
                continue
            eigene = self._titel_worte(r["title"])
            if any(all(w in kind for kind in kinder_worte[schl]) for w in eigene):
                ueberschrift[schl] = (r["title"] or "").strip()

        kandidaten = []
        for r in rohe:
            titel = (r["title"] or "").strip()
            if not titel or self._FORMALIE_RE.search(titel):
                continue
            schluessel = (r["ksinr"], r["item_number"])
            if schluessel in kopfzeile:
                continue          # trägt keinen Inhalt, nur eine Zwischenzeile
            sitz = nach_sitzung[r["ksinr"]]
            eltern = eltern_von.get(schluessel)
            gruppe_nr = eltern if (r["ksinr"], eltern) in ueberschrift else r["item_number"]
            kandidaten.append({
                "ksinr": r["ksinr"], "item_number": r["item_number"], "title": titel,
                "summary": (r["summary"] or "").strip() or None,
                # Der Kartentext für Social Media (agenda_item_social) — kennt
                # Vorlage und Anlagen und wertet nicht. Fehlt er, bleibt es bei
                # der Kurzfassung; der Bot behandelt beides gleich.
                "social_text": (r["social_text"] or "").strip() or None,
                # Ein kurzfristig eingebrachter Antrag (council/dringlichkeit.py).
                # Die Karte sagt das dazu, statt ihn wie einen Punkt der
                # amtlichen Tagesordnung zu zeigen — er steht in keiner.
                "dringlich": ist_dringlichkeitsantrag(r["item_number"]),
                "template_number": r["template_number"], "kvonr": r["kvonr"], "art": r["art"],
                "committee": sitz["committee"], "session_date": sitz["session_date"],
                "gruppe_nr": gruppe_nr,
                "gruppe_titel": ueberschrift.get((r["ksinr"], gruppe_nr)),
            })

        # Wie viele Stationen hat jede Gruppe? Die Karte sagt damit „Bauleit-
        # planung Meerweg · 2 Stationen" statt zweimal fast denselben Titel.
        gruppe_gross: dict[tuple, int] = {}
        for k in kandidaten:
            schl = (k["ksinr"], k["gruppe_nr"])
            gruppe_gross[schl] = gruppe_gross.get(schl, 0) + 1
        for k in kandidaten:
            k["gruppe_stationen"] = gruppe_gross[(k["ksinr"], k["gruppe_nr"])]

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
        from council.impact import dringlichkeits_boden, formalakt_deckel

        for k in kandidaten:
            eintrag = bewertet.get((k["ksinr"], k["item_number"]))
            if eintrag:
                k["wichtig"], k["wichtig_grund"] = eintrag[0], eintrag[1]
                k["wichtig_quelle"] = "tragweite"
            # Straßenrechtliche Formalakte (Widmung, Einziehung, Umstufung)
            # deckeln — egal ob Heuristik oder LLM sie hochgestuft hat: Die
            # Widmung „Im Technologiepark" stand als „wichtig" auf der Karte
            # (Tims Befund 18.08.). Lesezeitig, damit auch schon gespeicherte
            # Fehlbewertungen sofort verschwinden.
            deckel = formalakt_deckel(k["title"])
            if deckel is not None and k["wichtig"] > deckel:
                k["wichtig"] = deckel
                k["wichtig_grund"] = None
            # Und der Gegenpol: Dringlichkeitsanträge bekommen einen Boden.
            # Die Rubrik misst Tragweite, nicht Aktualität — dass eine
            # Fraktion die Tagesordnung für eine Sache aufmacht, wiegt sie
            # nicht mit (Tims Entscheidung 30.08.26). Der Grund des Modells
            # bleibt stehen: Er ist richtig, er wog nur die Kurzfristigkeit
            # nicht mit. Lesezeitig wie der Deckel, damit er auch für schon
            # bewertete Punkte sofort gilt.
            boden = dringlichkeits_boden(k["item_number"])
            if boden is not None and k["wichtig"] < boden:
                k["wichtig"] = boden
        # Treffer zuerst, danach nach Rang: Ein Punkt zu einem eigenen Thema ist
        # relevanter als jeder gut bewertete Fremdpunkt.
        kandidaten.sort(key=lambda p: (0 if p["topic_name"] else 1, -p["wichtig"], p["session_date"]))
        gruppen_je_sitzung: dict[int, set] = {}
        punkte = []
        for p in kandidaten:
            # Wer ein eigenes Thema trifft, ist per Definition relevant — die
            # Rang-Schwelle gilt nur für die allgemeine Auswahl.
            if not p["topic_name"] and p["wichtig"] < self.WICHTIG_MINDEST:
                continue
            # Höchstens drei GRUPPEN je Sitzung — nicht drei Punkte. Eine
            # Bauleitplanung mit vier Stationen ist ein Vorhaben und bekommt
            # einen Platz; da die Liste nach Rang sortiert ist, ist der erste
            # Treffer einer Gruppe zugleich ihr stärkster Punkt.
            gesehen = gruppen_je_sitzung.setdefault(p["ksinr"], set())
            gruppe = p["gruppe_nr"]
            if gruppe in gesehen:
                continue
            if len(gesehen) >= 3:
                continue
            gesehen.add(gruppe)
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
        punkte.sort(key=lambda p: (p["session_date"], self._top_sortierung(p["item_number"])))

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
        # Und wie viele inhaltliche Themen hat die Sitzung ÜBERHAUPT — ohne
        # Formalien, ohne Überschriften-Zeilen, Stationen eines Vorhabens als
        # eines gezählt. Das ist die Zahl für „+ N weitere Tagesordnungs-
        # punkte": Die Karte nannte bisher nur die weiteren RELEVANTEN Punkte
        # („+ 1"), obwohl auf der Tagesordnung noch 26 Themen standen — das
        # klang nach einer dünnen Sitzung statt nach einer Auswahl.
        themen_je_sitzung: dict[int, set] = {}
        for k in kandidaten:
            if k["topic_name"]:
                treffer_je_sitzung[k["ksinr"]] = treffer_je_sitzung.get(k["ksinr"], 0) + 1
            if k["topic_name"] or k["wichtig"] >= self.WICHTIG_MINDEST:
                relevant[k["ksinr"]] = relevant.get(k["ksinr"], 0) + 1
            themen_je_sitzung.setdefault(k["ksinr"], set()).add(k["gruppe_nr"])
        # Die übrigen relevanten Punkte je Sitzung MIT ausliefern (Tims Wunsch
        # 18.08.): „x weitere Punkte" soll in der Karte aufklappen statt zur
        # Tagesordnung wegzunavigieren — dafür braucht die Karte die Titel.
        # kandidaten sind bereits nach Rang sortiert, die Reihenfolge bleibt.
        gezeigt = {(p["ksinr"], p["item_number"]) for p in punkte}
        weitere_je_sitzung: dict[int, list[dict]] = {}
        for k in kandidaten:
            if (k["ksinr"], k["item_number"]) in gezeigt:
                continue
            if not (k["topic_name"] or k["wichtig"] >= self.WICHTIG_MINDEST):
                continue
            weitere_je_sitzung.setdefault(k["ksinr"], []).append({
                "ksinr": k["ksinr"], "item_number": k["item_number"],
                "title": k["title"], "titel_kurz": k["titel_kurz"],
                "antragsteller": k["antragsteller"], "topic_name": k["topic_name"],
                # Kurzfassung UND Tragweite-Grund gehen mit. Hier stand
                # `"summary": None`, um die Antwort klein zu halten — für die
                # Website reichte der Titel beim Aufklappen. Der Instagram-Bot
                # baut aus dieser Liste aber ganze Karten, und die standen
                # dadurch grundsätzlich ohne Erklärung da (Tims Befund
                # 19.08.26: „die zweite Seite hat keine Zusammenfassung").
                #
                # Und derselbe Fehler noch einmal, 30.08.26: Der neue
                # Kartentext fehlte hier, weil diese Liste Feld für Feld
                # gebaut wird. Der Dringlichkeitsantrag zur PAK-Belastung
                # stand deshalb auf der Karte — und darunter nichts. Wer hier
                # ein Feld ergänzt, muss es an BEIDEN Stellen tun.
                "summary": k["summary"], "social_text": k.get("social_text"),
                "dringlich": k.get("dringlich", False),
                "wichtig": k["wichtig"], "wichtig_grund": k.get("wichtig_grund"),
                "template_number": k["template_number"], "kvonr": k["kvonr"],
                "committee": k["committee"], "session_date": k["session_date"],
                "gruppe_nr": k["gruppe_nr"], "gruppe_titel": k["gruppe_titel"],
                "gruppe_stationen": k["gruppe_stationen"],
            })
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
            "weitere_je_sitzung": weitere_je_sitzung,
            "treffer_je_sitzung": treffer_je_sitzung,
            "treffer_gesamt": sum(1 for k in kandidaten if k["topic_name"]),
            "inhaltlich_gesamt": len(kandidaten),
            "inhaltlich_je_sitzung": {k: len(v) for k, v in themen_je_sitzung.items()},
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

    def save_social_text(self, ksinr: int, item_number: str, text: str,
                         quelle: str) -> None:
        """Kartentext eines TOP festhalten (siehe agenda_item_social)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO agenda_item_social "
                "(ksinr, item_number, text, quelle, created_at) VALUES (?, ?, ?, ?, ?)",
                (ksinr, item_number, text, quelle, now))

    def agenda_items_needing_social_text(self, limit: int | None = None,
                                         tage_voraus: int = 21,
                                         mindest_wichtig: int = 0,
                                         ksinr: int | None = None) -> list[dict]:
        """Kommende TOPs ohne Kartentext — samt allem, was das Modell sehen soll.

        Nur nach VORN. Der Text steht in einer Vorschau; für vergangene
        Sitzungen gibt es später den Beschluss.

        Mit ``ksinr`` genau EINE Sitzung, dann ohne Zeitfenster: Der Aufrufer
        hat sie schon in der Hand (die Tagesordnungs-Mail, sobald eine neue
        Tagesordnung erscheint), und ihr Termin kann weiter als drei Wochen
        entfernt liegen.

        Und sonst: **jeder inhaltliche Punkt**. Die Deckelung auf Tragweite
        ≥ 40 stammte aus dem Bild-Kanal — dort kommen von 97 öffentlichen
        TOPs einer Woche rund 20 auf eine Karte, der Rest wäre bezahlt und
        nie gelesen. Im Web wird jede Tagesordnung ganz gelesen, und dort
        stand unter den anderen 75 die titelbasierte Kurzfassung oder nichts
        (Tims Entscheidung 30.08.26). Ein Aufruf kostet Bruchteile eines
        Cents; die Deckelung war fürs Bild gedacht, nicht fürs Budget.

        Die Routine bleibt trotzdem draußen — „Feststellung der
        Beschlussfähigkeit" braucht keinen Text; dafür sorgt derselbe
        ``_FORMALIE_RE`` wie im Tragweite-Lauf. Und eine Bewertung ist keine
        Bedingung mehr, sondern nur noch die Reihenfolge: Was hoch bewertet
        ist, kommt zuerst dran, Unbewertetes danach.

        Der Vorlagentext kommt UNGEKÜRZT (die Auswahl trifft
        social_text.kontext, die kennt die Budgets); die Anlagen holt der
        Aufrufer über anlagen_fuer.
        """
        from datetime import date, timedelta

        heute = date.today().isoformat()
        bis = (date.today() + timedelta(days=tage_voraus)).isoformat()
        if ksinr is not None:
            heute, bis = "0000-00-00", "9999-99-99"
        sql = """SELECT a.ksinr, a.item_number, a.title, a.kvonr, a.template_number,
                        cs.committee, cs.session_date,
                        v.art, v.amt, v.beschlussvorschlag, v.finanz_check,
                        v.klima_check, v.raw_text,
                        i.impact,
                        -- Dringlichkeitsanträge haben keine Vorlage; ihr
                        -- ganzer Inhalt steht in dem PDF, das an der Zeile
                        -- hängt. Der Lauf holt es über diese URL nach.
                        (SELECT an.url FROM council_agenda_anlagen an
                          WHERE an.ksinr = a.ksinr AND an.item_number = a.item_number
                          LIMIT 1) AS anlage_url,
                        (SELECT an.raw_text FROM council_agenda_anlagen an
                          WHERE an.ksinr = a.ksinr AND an.item_number = a.item_number
                            AND an.raw_text IS NOT NULL LIMIT 1) AS anlage_text
                 FROM council_agenda_items a
                 JOIN council_sessions cs ON cs.ksinr = a.ksinr
                 LEFT JOIN agenda_item_impact i
                      ON i.ksinr = a.ksinr AND i.item_number = a.item_number
                 LEFT JOIN council_vorlagen v ON v.kvonr = a.kvonr
                 LEFT JOIN agenda_item_social so
                        ON so.ksinr = a.ksinr AND so.item_number = a.item_number
                 WHERE a.is_public = 1 AND so.text IS NULL
                   AND COALESCE(i.impact, 0) >= ?
                   AND cs.session_date >= ? AND cs.session_date <= ?
                   AND a.title IS NOT NULL AND length(a.title) >= 8
                   -- Nur Punkte, zu denen es überhaupt etwas zu lesen gibt.
                   -- Ohne Vorlage und ohne Anlage sähe das Modell nur den
                   -- Titel — und einen Satz aus dem Titel allein gibt es
                   -- schon: die Kurzfassung. Ein zweiter wäre bezahlt und
                   -- nicht besser. Sie kommen im nächsten Lauf wieder,
                   -- sobald der Vorlagentext nachgeladen ist.
                   AND (v.raw_text IS NOT NULL OR v.beschlussvorschlag IS NOT NULL
                        OR anlage_text IS NOT NULL)"""
        args: tuple = (mindest_wichtig, heute, bis)
        if ksinr is not None:
            sql += " AND a.ksinr = ?"
            args += (ksinr,)
        sql += " ORDER BY COALESCE(i.impact, -1) DESC, cs.session_date"
        roh = [dict(r) for r in self._conn.execute(sql, args)]
        # Formalien in Python heraus, nicht in SQL — dasselbe Muster wie in
        # `agenda_items_needing_impact`: Ein LIMIT vor dem Filter lieferte
        # sonst eine halb leere Liste, weil gut die Hälfte der Zeilen
        # „Genehmigung der Tagesordnung" heißt.
        echte = [r for r in roh if not self._FORMALIE_RE.search(r["title"] or "")]
        return echte[:limit] if limit is not None else echte

    def anlagen_fuer(self, kvonr: int) -> list[dict]:
        """Anlagen einer Vorlage mit Text — Anträge zuerst, dann die kürzeste.

        Die Reihenfolge ist die halbe Miete: Der Antrag einer Fraktion hat
        3.000 Zeichen und sagt, was jemand WILL. Der „Materialband
        Lupenpläne" derselben Vorlage hat 400.000 und ist als OCR-Text eine
        Kartensammlung. Wer nach Länge sortiert, bekommt zuerst das Argument
        und läuft nicht Gefahr, sein Budget mit Planwerk zu füllen.
        """
        return [dict(r) for r in self._conn.execute(
            "SELECT label, is_antrag, antragsteller, raw_text FROM council_anlagen "
            "WHERE kvonr = ? AND raw_text IS NOT NULL AND length(raw_text) > 0 "
            "ORDER BY is_antrag DESC, length(raw_text) ASC", (kvonr,))]

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

    def agenda_social_texts(self, ksinr: int) -> dict[str, str]:
        """{item_number: Kartentext} einer Sitzung (``agenda_item_social``).

        Der bessere der beiden Sätze: aus Vorlage UND Anlagen geschrieben,
        während die Kurzfassung nur den Titel kennt. Wer beides braucht, nimmt
        ``agenda_items`` — das legt sie nebeneinander an jeden Punkt.
        """
        return {r["item_number"]: r["text"] for r in self._conn.execute(
            "SELECT item_number, text FROM agenda_item_social WHERE ksinr = ?",
            (ksinr,)) if r["text"]}

    def agenda_items(self, ksinr: int) -> list[dict]:
        rows = self._conn.execute(
            """SELECT item_number, title, template_number, kvonr, is_public
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
        # Der bessere der beiden Texte, wo es ihn gibt (agenda_item_social):
        # Er kennt Vorlage UND Anlagen, während `summary` allein aus dem Titel
        # entsteht („Du kennst nur den Titel des Punktes" steht wörtlich in
        # deren Prompt). Beide fahren mit — der Aufrufer entscheidet, aber die
        # Reihenfolge steht hier fest, damit Web und iOS dieselbe wählen.
        kartentext = {r["item_number"]: r["text"] for r in self._conn.execute(
            "SELECT item_number, text FROM agenda_item_social WHERE ksinr = ?", (ksinr,))}
        from .dringlichkeit import ist_dringlichkeitsantrag  # noqa: PLC0415 — Ringschluss

        for item in out:
            item["anlagen"] = anl.get(item["item_number"], [])
            item["summary"] = zus.get(item["item_number"])
            item["social_text"] = kartentext.get(item["item_number"])
            # Ein abgeleiteter Punkt, kein amtlicher (council/dringlichkeit.py).
            # Das Flag entscheidet hier und nicht im Frontend, damit Web und
            # App denselben Punkt hervorheben.
            item["dringlich"] = ist_dringlichkeitsantrag(item["item_number"])
        return out

    def sitzungen_am_monatstag(self, monat_tag: str, limit: int = 8) -> list[dict]:
        """Sitzungen an einem Monatstag (``"-06-17"``) über alle Jahre, neueste
        zuerst — löst Fragen mit Datum ohne Jahr („am 17.06.") auf
        (Sitzungs-Fragetyp der KI-Frage, ``qa.finde_sitzungen``)."""
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM council_sessions WHERE session_date LIKE ? "
            "ORDER BY session_date DESC LIMIT ?", (f"%{monat_tag}", int(limit)))]

    def decision_ids_der_sitzung(self, ksinr: int) -> list[int]:
        """Beschluss-ids einer Sitzung in Tagesordnungs-Reihenfolge, ohne
        Subvotes (die hängen als Kontext am Hauptbeschluss). Sitzungs-Fragetyp
        der KI-Frage: die Sitzung kommt damit VOLLSTÄNDIG in den Kontext."""
        return [r[0] for r in self._conn.execute(
            "SELECT id FROM council_decisions WHERE ksinr = ? AND kind = 'decision' "
            "ORDER BY position", (int(ksinr),))]

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
                       WHERE title LIKE ? OR template_number LIKE ?))"""
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
                f"""SELECT ksinr, item_number, title, template_number, kvonr, is_public
                    FROM council_agenda_items
                    WHERE ksinr IN ({placeholders}) AND (title LIKE ? OR template_number LIKE ?)
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
                         official_text, outcome, vote, no_votes, abstentions, factions,
                         template_number, kvonr, raw_result) -> None:
        cur = self._conn.execute(
            "INSERT INTO council_decisions "
            "(ksinr, position, kind, parent_item, item_number, title, official_text, outcome, "
            " vote, no_votes, abstentions, factions, template_number, kvonr, raw_result) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ksinr, position, kind, parent_item, item_number, title, official_text, outcome,
             vote, _int_or_none(no_votes), _int_or_none(abstentions),
             json.dumps(factions or [], ensure_ascii=False),
             template_number, _int_or_none(kvonr), raw_result),
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
                                      d.get("item_number"), d.get("title"), d.get("official_text"),
                                      d.get("outcome"), d.get("vote"), d.get("no_votes"),
                                      d.get("abstentions"), d.get("factions"),
                                      d.get("template_number"), d.get("kvonr"), d.get("raw_result"))
                pos += 1
                for sv in d.get("sub_votes") or []:
                    self._insert_decision(ksinr, pos, "subvote", d.get("item_number"),
                                          d.get("item_number"), sv.get("description"), None,
                                          sv.get("outcome"), sv.get("vote"), sv.get("no_votes"),
                                          sv.get("abstentions"), sv.get("factions"),
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
            # (Review-Befund E2: sonst blieben kvonr und deviation NULL,
            # obwohl get_vorlage_by_nr die Vorlage längst auflöst).
            self._conn.execute(
                "UPDATE council_decisions SET kvonr = COALESCE("
                "(SELECT MAX(v.kvonr) FROM council_vorlagen v WHERE v.template_number = council_decisions.template_number), "
                "(SELECT MAX(v.kvonr) FROM council_vorlagen v "
                " WHERE instr(council_decisions.template_number, v.template_number || '/') = 1)) "
                "WHERE ksinr = ? AND kvonr IS NULL AND template_number IS NOT NULL",
                (ksinr,),
            )
        self.refresh_abweichung(ksinr=ksinr)

    def refresh_abweichung(self, ksinr: int | None = None, template_number: str | None = None) -> int:
        """Beschluss ↔ Beschlussvorschlag vergleichen (council.ernte.deviation)
        und das Ergebnis an den Beschlüssen ablegen. Zwei Auslöser, weil Vorlage
        und Protokoll in beliebiger Reihenfolge eintreffen: nach save_protocol
        (per ksinr) und nach save_vorlage (per template_number). Nur angenommene
        Beschlüsse — eine Vertagung oder Ablehnung ist keine Textänderung."""
        from council import ernte

        sql = ("SELECT id, template_number, official_text FROM council_decisions "
               "WHERE kind = 'decision' AND outcome = 'angenommen' "
               "AND official_text IS NOT NULL AND template_number IS NOT NULL")
        args: tuple = ()
        if ksinr is not None:
            sql += " AND ksinr = ?"
            args = (ksinr,)
        elif template_number is not None:
            # Auch Beschlüsse, die eine REVISION dieser Nummer zitieren
            # („22/0348/1" bei gespeicherter Basis „22/0348") — der
            # get_vorlage_by_nr-Fallback löst sie ohnehin auf (Befund E2).
            base = "/".join(template_number.split("/")[:2])
            sql += " AND (template_number IN (?, ?) OR template_number LIKE ? || '/%')"
            args = (template_number, base, template_number)
        vorschlaege: dict[str, str | None] = {}
        updates = []
        for did, nr, official_text in self._conn.execute(sql, args).fetchall():
            if nr not in vorschlaege:
                v = self.get_vorlage_by_nr(nr)
                vorschlaege[nr] = (v or {}).get("beschlussvorschlag")
            updates.append((ernte.deviation(vorschlaege[nr], official_text), did))
        if updates:
            with self._conn:
                self._conn.executemany(
                    "UPDATE council_decisions SET deviation = ? WHERE id = ?", updates)
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
                        only_ids=None, district="", location_slug=""):
        """Build the WHERE clause + params shared by search and count."""
        filters: list[str] = []
        params: list = []
        if only_ids is not None:
            # Design 28a/S4: Vorgegebene Beschluss-Menge (die semantischen Treffer
            # eines Nutzer-Themas). Die Zuordnung liegt in ratslotse.sqlite, also in
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
            filters.append("(d.title LIKE ? OR d.official_text LIKE ? OR d.summary LIKE ?)")
            like = f"%{query}%"
            params += [like, like, like]
        if committee:
            filters.append("cs.committee = ?")
            params.append(committee)
        if field:
            filters.append("d.policy_field = ?")
            params.append(field)
        if district:
            # EXISTS vermeidet doppelte Beschlusszeilen bei mehreren Ortslinks.
            # Primäre Ortsbereiche matchen die geometrisch abgeleitete Eltern-ID,
            # feinere Katalogorte ihre exakte stabile Orts-ID bzw. Alt-Aliase.
            place = self.resolve_place(district)
            if place:
                condition, place_params = self._place_location_condition(place)
                filters.append(
                    "EXISTS (SELECT 1 FROM council_decision_locations dl "
                    "JOIN council_locations l ON l.slug = dl.location_slug "
                    f"WHERE dl.decision_id = d.id AND {condition})"
                )
                params += place_params
            else:
                filters.append("0")
        if location_slug:
            filters.append(
                "EXISTS (SELECT 1 FROM council_decision_locations dl "
                "WHERE dl.decision_id=d.id AND dl.location_slug=?)"
            )
            params.append(location_slug)
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
            # official_text. include_subvotes=True (Filter „einzeln zeigen") bringt sie
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
        district: str = "",
        location_slug: str = "",
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
                                              include_subvotes=include_subvotes, only_ids=only_ids,
                                              district=district, location_slug=location_slug)
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
        only_ids: list[int] | None = None, district: str = "", location_slug: str = "",
    ) -> int:
        party_ids = self.decision_ids_for_party(party) if party else None
        where, params = self._decision_where(query, committee, outcome, faction,
                                             date_from, date_to, kind, category, field, party_ids,
                                             include_subvotes=include_subvotes, only_ids=only_ids,
                                             district=district, location_slug=location_slug)
        row = self._conn.execute(
            f"""SELECT COUNT(*) FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr {where}""",
            params,
        ).fetchone()
        return row[0] if row else 0

    def beschlusszahl_je_gremium(self, date_from: str) -> dict[str, int]:
        """Beschlüsse je Gremium ab ``date_from`` (ISO-Datum) — für die
        Ausschuss-Abos, die je Gremium „x Beschlüsse in diesem Jahr" zeigen.

        Gezählt wird nur ``kind = 'decision'``: Änderungsanträge
        (``kind = 'subvote'``) sind keine eigenen Beschlüsse, sondern hängen
        als Kontext am Ursprungsbeschluss (Design 23a) — genau so zählt auch
        ``count_decisions`` in seiner Standardform (``include_subvotes=False``).
        Zählte man sie mit, stünde neben dem Gremium eine höhere Zahl, als die
        verlinkte Beschlussliste hergibt.

        Bewusst EINE Abfrage mit ``GROUP BY`` statt eines ``count_decisions``
        je Gremium: Die Seite lädt die Liste bei jedem Aufruf, und es sind rund
        15 Gremien. Gremien ohne Beschluss fehlen im dict (der Aufrufer setzt 0).
        """
        rows = self._conn.execute(
            """SELECT cs.committee AS committee, COUNT(*) AS n
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE d.kind = 'decision' AND cs.session_date >= ?
               GROUP BY cs.committee""",
            (date_from,),
        ).fetchall()
        return {r["committee"]: r["n"] for r in rows}

    def decisions_needing_simple_summary(self, limit: int | None = None) -> list[dict]:
        """Beschlüsse ohne „einfach erklärt"-Kurzfassung (RL-904): nur echte
        Beschlüsse mit substanziellem Beschlusstext, neueste zuerst — so holt
        ein limitierter Backfill die relevantesten zuerst nach."""
        sql = """SELECT d.id, d.title, d.official_text, d.summary, cs.committee, cs.session_date
                 FROM council_decisions d
                 JOIN council_sessions cs ON cs.ksinr = d.ksinr
                 WHERE d.kind = 'decision' AND d.simple_summary IS NULL
                   AND d.official_text IS NOT NULL AND length(d.official_text) >= 200
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
        sql = """SELECT d.id, d.title, d.official_text, d.summary, d.outcome, d.amount_eur,
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
        sql = """SELECT d.id, d.title, d.official_text, d.summary, d.outcome, d.kind,
                        d.amount_eur, d.vote, d.no_votes, cs.committee, cs.session_date
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
        sql = """SELECT a.ksinr, a.item_number, a.title, a.template_number, a.kvonr,
                        s.summary, cs.committee, cs.session_date,
                        v.beschlussvorschlag, v.finanz_check, v.amt, v.art,
                        (SELECT COUNT(*) FROM council_beratungen b WHERE b.kvonr = a.kvonr)
                            AS stationen,
                        -- Großzügig: Die ersten ~300 Zeichen sind Briefkopf,
                        -- den `impact.vorlagen_kern` abschneidet. Bei 1200
                        -- blieb danach zu wenig Inhalt übrig.
                        -- Dringlichkeitsanträge haben keine Vorlage; ihr Text
                        -- steht am Zeilen-Dokument. Ohne dieses COALESCE
                        -- bewertete das Modell den Dateinamen — der
                        -- PAK-Antrag vom 31.08.26 kam so auf 55 und verpasste
                        -- die Karte, obwohl im PDF eine Schadstoffbelastung
                        -- eines Gewässers und Sofortmaßnahmen standen.
                        COALESCE(substr(v.raw_text, 1, 2500),
                                 (SELECT substr(an.raw_text, 1, 2500)
                                    FROM council_agenda_anlagen an
                                   WHERE an.ksinr = a.ksinr
                                     AND an.item_number = a.item_number
                                     AND an.raw_text IS NOT NULL
                                   LIMIT 1)) AS sachverhalt
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

    #: Gewichte des Fundwerts. Erzählbarkeit zählt etwas mehr als Tragweite
    #: — ein Haushaltsbeschluss ist bedeutend, aber kein Fundstück. Die
    #: Sperren darunter sind der eigentliche Hebel: Ohne sie gewinnt die
    #: Kuriosität, weil sie leichter hohe Interest-Werte erreicht.
    FUND_GEWICHT_INTERESSE = 0.55
    FUND_GEWICHT_TRAGWEITE = 0.45
    FUND_MIN_INTERESSE = 50
    FUND_MIN_TRAGWEITE = 50

    def fundstueck_candidates(
        self, *, mmdd: str | None = None, exclude_ids: set[int] | None = None, limit: int = 10
    ) -> list[dict]:
        """Kandidaten fürs Fundstück, bester Gesamtwert zuerst.

        ZWEI Werte, nicht einer. Bis 20.08.26 entschied allein ``interest``
        — und der misst Erzählbarkeit, nicht Bedeutung. Herausgekommen sind
        „Straßenbenennung Rotkäppchenweg" (Interesse 90, Tragweite 35) und
        „Modellvorhaben Cannabis" (Interesse 90, Tragweite 5), zweimal in
        derselben Woche sogar zwei Straßenbenennungen. Kurios, aber kein
        Fund, über den man reden will (Tims Befund).

        Ein Fundstück braucht beides: Es muss etwas BEDEUTEN und sich
        erzählen lassen. Deshalb ein gewichteter Mittelwert und ein
        Mindestmaß an Tragweite als Sperre — sonst gewinnt die Kuriosität
        wieder allein.

        ``mmdd`` („07-22") filtert auf Jahrestage (gleicher Kalendertag,
        früheres Jahr).
        """
        exclude = exclude_ids or set()
        sql = """SELECT d.id, d.title, d.official_text, d.summary, d.outcome, d.vote,
                        d.amount_eur, d.interest, d.impact, d.no_votes,
                        cs.committee, cs.session_date,
                        (? * d.interest + ? * d.impact) AS fundwert
                 FROM council_decisions d
                 JOIN council_sessions cs ON cs.ksinr = d.ksinr
                 WHERE d.kind = 'decision'
                   AND d.interest IS NOT NULL AND d.impact IS NOT NULL
                   AND d.interest >= ? AND d.impact >= ?
                   AND cs.session_date < date('now')"""
        args: list = [self.FUND_GEWICHT_INTERESSE, self.FUND_GEWICHT_TRAGWEITE,
                      self.FUND_MIN_INTERESSE, self.FUND_MIN_TRAGWEITE]
        if mmdd:
            sql += " AND strftime('%m-%d', cs.session_date) = ?"
            args.append(mmdd)
        sql += " ORDER BY fundwert DESC, cs.session_date DESC LIMIT ?"
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

    def recent_fundstueck_titles(self, within_days: int = 45) -> list[str]:
        """Titel der zuletzt gezeigten Fundstücke — Grundlage der
        Themen-Sperre.

        Die ID-Sperre allein reicht nicht: Ein Großprojekt zieht sich über
        viele EINZELNE Beschlüsse (Stadionneubau, Gründung der GmbH,
        Ausfallbürgschaft, Grundstücksübertragung, Anmietung der Halle).
        Alle haben hohe Werte, keiner wiederholt einen anderen — und
        zusammen ergäben sie eine Woche lang dieselbe Geschichte.
        """
        rows = self._conn.execute(
            """SELECT d.title FROM council_fundstuecke f
               JOIN council_decisions d ON d.id = f.decision_id
               WHERE f.day >= date('now', ?)""",
            (f"-{int(within_days)} days",),
        ).fetchall()
        return [r["title"] or "" for r in rows]

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

    def vorlage_journey(self, template_number: str) -> list[dict]:
        """All sessions where a Vorlage appears on the agenda — its path through
        the committees and the council, oldest first."""
        rows = self._conn.execute(
            """SELECT DISTINCT cs.ksinr, cs.committee, cs.session_date, ci.item_number
               FROM council_agenda_items ci
               JOIN council_sessions cs ON cs.ksinr = ci.ksinr
               WHERE ci.template_number = ?
               ORDER BY cs.session_date""",
            (template_number,),
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
                "(kvonr, template_number, title, art, document_id, document_url, "
                " raw_text, n_pages, fetched_at, status, amt, klima_check, "
                " finanz_check, beschlussvorschlag) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["kvonr"], row.get("template_number"), row.get("title"), row.get("art"),
                 row.get("document_id"), row.get("document_url"), row.get("raw_text"),
                 row.get("n_pages"), now, row.get("status", "ok"),
                 ernte.federfuehrendes_amt(text), aus["klima"], aus["finanzen"],
                 ernte.beschlussvorschlag(text)),
            )
        if row.get("template_number"):
            self.refresh_abweichung(template_number=row["template_number"])

    def mark_vorlage_failed(self, kvonr: int) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_vorlagen (kvonr, fetched_at, status) "
                "VALUES (?, ?, 'failed')", (kvonr, now),
            )

    def get_vorlage_by_nr(self, template_number: str) -> dict | None:
        """The Vorlage row for a decision's template_number. Falls back to the base
        number ("22/0348/1" → "22/0348") because protocols sometimes cite a
        revision the agenda linked under its base document."""
        nr = (template_number or "").strip()
        if not nr:
            return None
        base = "/".join(nr.split("/")[:2])
        row = self._conn.execute(
            "SELECT * FROM council_vorlagen WHERE template_number IN (?, ?) "
            "ORDER BY (template_number = ?) DESC, kvonr DESC LIMIT 1",
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
        """Batch raw texts for Q&A context enrichment: exact template_number → text
        (only rows that actually have text). Best-effort — no base-nr fallback."""
        nrs = sorted({(n or "").strip() for n in vorlage_nrs if n and str(n).strip()})
        if not nrs:
            return {}
        ph = ",".join("?" * len(nrs))
        rows = self._conn.execute(
            f"SELECT template_number, raw_text FROM council_vorlagen "
            f"WHERE template_number IN ({ph}) AND status = 'ok'", nrs,
        ).fetchall()
        return {r["template_number"]: r["raw_text"] for r in rows if r["raw_text"]}

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

    def anlagen_for_vorlage_nr(self, template_number: str) -> list[dict]:
        """Anlagen for a decision's Vorlage (base-nr fallback like
        ``get_vorlage_by_nr``), motions first, each with parsed Antragsteller."""
        v = self.get_vorlage_by_nr(template_number)
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
            f"       v.template_number, v.title AS vorlage_titel "
            f"FROM council_beratungen b JOIN council_vorlagen v ON v.kvonr = b.kvonr "
            f"WHERE b.kvonr IN ({ph}) AND b.datum >= date('now') ORDER BY b.datum",
            kvonrs).fetchall()
        return [dict(r) for r in rows]

    #: Wörter, die in fast jeder Frage stehen und jede Tagesordnung treffen
    #: würden. „stand" ist der Klassiker: Als Teilwort-Suche traf es
    #: „Sachstandsbericht" und „Baumstandort" und hängte einer Frage nach der
    #: Cäcilienbrücke einen EU-Verordnungs-Termin an (gemessen 11.08.).
    #: „strasse" (gefaltet) ist derselbe Fehler in Grün: Fragen zu einer
    #: Adresse enthalten das Wort fast immer, und es steckt in jedem zweiten
    #: Vorlagentitel — Straßenwidmungen, B-Plan-Sachstände, Straßenbau. Bei
    #: der Stadion-Frage („Maastrichter Straße") hängte es drei fremde
    #: Verkehrsausschuss-Termine an „Wie es weitergeht" (gemessen 19.08.,
    #: Tims Screenshot-Befund — nur „strasse" traf, kein n>=2 gefordert).
    _AUSBLICK_STOPP = {
        "stand", "sachstand", "aktuell", "official_text", "beschlusse", "beschluesse",
        "stadt", "oldenburg", "planung", "bericht", "vorlage", "thema", "themen",
        "strasse",
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
            "       v.template_number, v.title AS vorlage_titel "
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
        # Gefaltet auf die kanonische Namensform (:meth:`person_slug`): Das
        # Ratsinformationssystem führt seine Stammdaten unter genau einer Form,
        # die Anwesenheitslisten können eine andere nennen — ohne die Faltung
        # stünde ein Profil ohne Mandat und ohne Fraktion da.
        want = {self.person_slug(n) for n in names}
        person = None
        for r in self._conn.execute("SELECT kpenr, name, fraktion_aktuell FROM council_persons"):
            if self.person_slug(r["name"]) in want:
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
        ratslotse.sqlite, laufen aber ins Leere)."""
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

    # --- Herkunft der Finanzzahlen (council.herkunft) ------------------------

    def merke_herkunft(self, h, fetched_at: str | None = None) -> int:
        """Eine :class:`council.herkunft.Herkunft` eintragen und ihre ID
        liefern — der eine Weg, auf dem Herkunft in die Datenbank kommt.

        Idempotent über den inhaltlichen Fingerabdruck: Derselbe Abschnitt
        desselben Dokuments mit derselben Probe bekommt bei jedem Lauf
        dieselbe ID. Was sich ändert, ist `fetched_at` — „zuletzt bestätigt",
        nicht „zuerst gesehen".

        Der Zeitstempel wandert dabei nur **vorwärts** (``MAX``). Beim
        Nachrüsten teilen sich mehrere Tabellen eine Herkunft und bringen je
        einen eigenen Zeitstempel mit; ohne diese Regel gewönne schlicht die
        zuletzt bearbeitete Tabelle, und „zuletzt bestätigt" stünde auf einem
        älteren Datum als eine Zeile, die darauf zeigt.

        Läuft absichtlich **ohne** eigene Transaktion: Der Aufrufer schreibt
        Herkunft und Datenzeilen zusammen, oder gar nicht."""
        jetzt = fetched_at or datetime.utcnow().isoformat(timespec="seconds")
        schluessel = h.schluessel()
        vorhanden = self._conn.execute(
            "SELECT id FROM council_herkunft WHERE schluessel = ?",
            (schluessel,)).fetchone()
        if vorhanden:
            self._conn.execute(
                "UPDATE council_herkunft SET fetched_at = MAX(fetched_at, ?) "
                "WHERE id = ?", (jetzt, vorhanden[0]))
            return int(vorhanden[0])
        f = h.felder()
        cur = self._conn.execute(
            "INSERT INTO council_herkunft (schluessel, art, dokument_id, label, url, "
            " fundstelle, seite, probe, probe_ergebnis, stand, fetched_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (schluessel, f["art"], f["dokument_id"], f["label"], f["url"],
             f["fundstelle"], f["seite"], f["probe"], f["probe_ergebnis"],
             f["stand"], jetzt))
        return int(cur.lastrowid)

    #: Welcher Beschluss zu einem Dokument der maßgebliche ist. Der Rat zuerst
    #: — eine Vorlage läuft durch mehrere Gremien, aber verabschiedet wird sie
    #: dort. Innerhalb eines Gremiums die jüngste Sitzung: Ein vertagter Punkt
    #: kommt wieder, und es gilt, was zuletzt entschieden wurde. Dieselbe
    #: Ordnung nutzt schon `vorlage_beschluesse` (s. u. „committee LIKE 'Rat%'").
    _BESCHLUSS_ORDNUNG = ("ORDER BY (cs.committee LIKE 'Rat%') DESC, "
                          "cs.session_date DESC, d.id DESC")

    def beschluesse_zu_dokumenten(self, dokument_ids: list[int]) -> dict[int, dict]:
        """Zu jedem Dokument der Ratsbeschluss, der es verabschiedet hat.

        Der Weg ist dreigliedrig und steht so nirgends sonst im Code:
        ``council_herkunft.dokument_id`` → ``council_anlagen.kvonr`` (an
        welcher Vorlage die Anlage hängt) → ``council_decisions.kvonr`` (was
        der Rat mit dieser Vorlage gemacht hat).

        Damit wird aus „steht im Jahresabschluss 2024" ein „der Rat hat das am
        16.09.2025 beschlossen" — dieselbe Zahl, aber mit dem Vorgang dahinter
        statt nur mit dem Papier.

        **Das Ergebnis wird mitgeliefert, nicht gefiltert.** Ein Dokument, das
        an einer vertagten Vorlage hängt, ist keine Zahl ohne Beleg — es ist
        eine Zahl, deren Vorgang noch läuft, und genau das soll die Seite
        sagen können. Wer hier auf ``outcome = 'angenommen'`` einschränkte,
        ließe die interessanteren Fälle stumm verschwinden.

        Eine Anlage ohne Vorlage im Bestand liefert **keinen** Eintrag; die
        Herkunft bleibt dann bei ihrem Dokument, und der Beleg-Chip zeigt, was
        er hat. Erfundene Vorgänge wären der schlimmere Fehler.
        """
        if not dokument_ids:
            return {}
        platz = ",".join("?" * len(dokument_ids))
        try:
            rows = self._conn.execute(
                "SELECT a.document_id, d.id AS beschluss_id, d.ksinr, d.item_number, "
                "       d.title, d.outcome, d.vote, d.template_number, a.kvonr, "
                "       cs.committee, cs.session_date "
                "FROM council_anlagen a "
                "JOIN council_decisions d ON d.kvonr = a.kvonr "
                "JOIN council_sessions cs ON cs.ksinr = d.ksinr "
                f"WHERE a.document_id IN ({platz}) AND d.kind = 'decision' "
                + self._BESCHLUSS_ORDNUNG,
                list(dokument_ids)).fetchall()
        except sqlite3.OperationalError:
            return {}
        # Die Ordnung entscheidet: Der erste Treffer je Dokument gewinnt, alle
        # weiteren sind frühere Stationen derselben Vorlage.
        aus: dict[int, dict] = {}
        for r in rows:
            aus.setdefault(int(r["document_id"]), {
                "id": r["beschluss_id"], "ksinr": r["ksinr"],
                "kvonr": r["kvonr"], "top": r["item_number"],
                "titel": (r["title"] or "").strip() or None,
                "outcome": r["outcome"], "vote": r["vote"],
                "template_number": r["template_number"],
                "gremium": r["committee"], "datum": r["session_date"],
            })
        return aus

    def get_herkunft(self, ids: list[int] | None = None) -> list[dict]:
        """Herkunfts-Datensätze — alle oder eine Auswahl, mit den Erklärsätzen
        zu ihren Proben.

        Die Sätze kommen aus dem Code (``herkunft.PROBEN``) und nicht aus der
        Datenbank: Sie sind Text für Leserinnen und dürfen sich verbessern,
        ohne dass ein Jahrgang neu eingelesen werden muss."""
        from council import herkunft as _h

        try:
            if ids is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_herkunft ORDER BY id").fetchall()
            elif not ids:
                return []
            else:
                platz = ",".join("?" * len(ids))
                rows = self._conn.execute(
                    f"SELECT * FROM council_herkunft WHERE id IN ({platz}) ORDER BY id",
                    list(ids)).fetchall()
        except sqlite3.OperationalError:
            return []
        aus = []
        for r in rows:
            d = dict(r)
            d.pop("schluessel", None)   # interner Fingerabdruck, kein Lesestoff
            d["proben"] = _h.probe_texte(d.get("probe"))
            aus.append(d)
        # Der Ratsvorgang zu allen Dokumenten in EINER Abfrage — nicht je
        # Datensatz eine. Ein Beleg-Apparat zeigt neun Teilhaushalts-Anlagen
        # nebeneinander; neun Nachschläge daraus zu machen wäre ein N+1 an
        # genau der Stelle, an der die Seite ohnehin am meisten holt.
        beschluesse = self.beschluesse_zu_dokumenten(
            sorted({d["dokument_id"] for d in aus if d.get("dokument_id")}))
        for d in aus:
            d["official_text"] = beschluesse.get(d.get("dokument_id"))
        return aus

    def _herkunft_verweistabellen(self) -> list[str]:
        """Jede Tabelle **dieser Datenbank**, die eine ``herkunft_id`` führt.

        Gefragt wird das Schema und nicht ``herkunft.HERKUNFT_TABELLEN``. Die
        Liste dort ist die Arbeitsanweisung fürs Anlegen der Spalte und fürs
        Nachrüsten aus den Altfeldern; sie wird von Hand gepflegt, und der
        Modulkopf von `council/herkunft.py` nennt das Eintragen ausdrücklich
        als Schritt 3 für einen neuen Parser. Genau dieser Schritt ist der,
        den man vergisst.

        Fürs Aufräumen wäre das teuer: Eine Tabelle, die die Liste nicht
        kennt, hat aus Sicht des DELETE **keine** Verweise. Ihre Herkünfte
        gälten als verwaist und fielen weg — während ihre Zeilen weiter auf
        deren Nummern zeigen. Weil die Nummern danach neu vergeben werden
        können, zeigt so eine Zeile am Ende nicht ins Leere (das fiele auf),
        sondern auf ein **fremdes Dokument**. Und ``herkunft_luecken()``
        schwiege dazu, weil auch sie nur die Liste durchging.

        Das Schema kennt die Tabelle trotzdem. Deshalb entscheidet es."""
        aus: list[str] = []
        for (name,) in self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
            cols = {r[1] for r in self._conn.execute(f'PRAGMA table_info("{name}")')}
            if "herkunft_id" in cols:
                aus.append(name)
        return aus

    def herkunft_aufraeumen(self) -> int:
        """Herkunfts-Datensätze löschen, auf die keine Zeile mehr zeigt.

        Nötig, weil ein erneuter Einlesen-Lauf einen Jahrgang **ersetzt**: Die
        alten Zeilen verschwinden, ihre Herkunft bliebe sonst liegen. Das
        passiert planmäßig einmal beim Nachrüsten (die `unbekannt`-Datensätze
        des Altbestands werden von den echten abgelöst) und danach immer, wenn
        sich eine Fundstelle oder eine Probe ändert.

        Gefragt wird, wer wirklich zeigt — ``_herkunft_verweistabellen()``
        liest das Schema, nicht die handgepflegte Liste. Dort steht auch,
        warum: Eine vergessene Zieltabelle verlöre hier sonst ihre Herkunft.

        Läuft **nur auf Ansage** aus den Ingest-Skripten, nicht beim Öffnen der
        Datenbank: Aufräumen ist eine Schreiboperation, und die gehört nicht in
        den Startpfad eines Webservers."""
        verweise = [f'SELECT herkunft_id FROM "{t}" WHERE herkunft_id IS NOT NULL'
                    for t in self._herkunft_verweistabellen()]
        if not verweise:
            return 0
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM council_herkunft WHERE id NOT IN ("
                + " UNION ".join(verweise) + ")")
        return cur.rowcount

    def herkunft_luecken(self) -> dict[str, int]:
        """Je Zieltabelle: wie viele Zeilen ohne Herkunft dastehen.

        Das Frühwarnsystem der Umstellung. Eine Tabelle, die eine
        ``herkunft_id`` trägt, sie aber nicht füllt, taucht hier nach jedem
        Lauf auf — und die Ingest-Skripte schreiben es ins Protokoll. Genannt
        werden nur Tabellen mit Lücken; eine leere Antwort heißt „jede Zeile
        weiß, woher sie kommt".

        Der Prüfumfang kommt wie beim Aufräumen aus dem Schema: Eine Tabelle,
        die in ``HERKUNFT_TABELLEN`` vergessen wurde, ist damit **nicht**
        stillgestellt, sondern meldet sich hier — sie ist ja gerade der Fall,
        der eine Meldung verdient."""
        aus: dict[str, int] = {}
        for tabelle in self._herkunft_verweistabellen():
            n = self._conn.execute(
                f'SELECT COUNT(*) FROM "{tabelle}" WHERE herkunft_id IS NULL'
            ).fetchone()[0]
            if n:
                aus[tabelle] = n
        return aus

    #: Welches **Dokument** hinter einer Quelle des Haushalts-Bereichs steht —
    #: je Schlüssel die Tabelle, ihre Jahresspalte, eine Einschränkung und die
    #: Alt-Spalte mit der URL.
    #:
    #: Die Schlüssel sind die des Quellenverzeichnisses im Frontend
    #: (``web/frontend/lib/haushalt-quellen.ts``). Das ist Absicht und der
    #: einzige Grund, warum diese Zuordnung hier steht und nicht dort: Welche
    #: Zeile aus welchem Dokument stammt, weiß die Datenbank — das Frontend
    #: kennt nur den Absatz, der eine ganze Seite beschreibt. Wer einen
    #: Schlüssel dort ergänzt, ergänzt ihn hier; wer ihn hier vergisst,
    #: bekommt keinen kaputten Link, sondern den Rückfall auf die statische
    #: Adresse (und das Frontend schreibt dann „im Ratsinformationssystem
    #: suchen" statt „Dokument öffnen").
    #:
    #: Die Alt-Spalte ist die Rückfallebene für Bestände, die vor der
    #: Herkunfts-Vereinheitlichung (#513) geschrieben wurden: Dort steht die
    #: URL an der Datenzeile, aber noch keine ``herkunft_id``. Die beiden
    #: Konzern-Tabellen haben keine — sie sind erst mit der Herkunft
    #: entstanden (s. ``_HERKUNFT_ALTFELDER``).
    _DOKUMENT_QUELLEN: dict[str, tuple[str, str, str | None, str | None]] = {
        "plan":                 ("council_haushalt", "year", None, "source_url"),
        # Die zwei Ebenen eines Jahresabschlusses stehen in derselben Tabelle
        # und im selben Dokument, tragen aber verschiedene Herkünfte (eigene
        # Abschnitte, eigene Proben). Beide Schlüssel gibt es im Verzeichnis.
        "jahresabschluss":      ("council_ergebnisrechnung", "jahr",
                                 "thh_nr IS NULL", "quelle_url"),
        "ergebnisrechnung_thh": ("council_ergebnisrechnung", "jahr",
                                 "thh_nr IS NOT NULL", "quelle_url"),
        # Dritte Ebene desselben Dokuments: Abschnitt 4.1, die Kassensicht.
        "finanzrechnung":       ("council_finanzrechnung", "jahr", None, None),
        # Der Gesamtergebnishaushalt (Anlage 005 des Haushaltsplans) — dieselbe
        # Postengliederung für Jahre ohne Abschluss.
        #
        # Der Filter auf ``art = 'ansatz'`` ist hier PFLICHT und keine
        # Verfeinerung: Ein Dokument trägt sein Planjahr UND drei
        # Finanzplanungsjahre, dieselbe Jahreszahl kommt also in drei
        # Haushaltsplänen vor (2026 im Plan 2024 als Vorausschau, im Plan 2025
        # als Vorausschau, im Plan 2026 als Ansatz). Ohne den Filter stünden an
        # einer Ansatz-Zahl bis zu drei Dokumente, und zwei davon meinen etwas
        # anderes. Mit ihm gilt ``jahr == plan_jahrgang``, und es bleibt genau
        # eines.
        "ergebnishaushalt":     ("council_ergebnishaushalt", "jahr",
                                 "t.art = 'ansatz'", None),
        # Vierte Ebene: Abschnitt 2.1, die Bilanz. Der älteste Stichtag (2016)
        # stammt aus der Vorjahresspalte des Abschlusses 2017 — er trägt
        # deshalb dessen Dokument, mit eigener Fundstelle.
        "bilanz":               ("council_bilanz", "jahr", None, None),
        # Der einzige Schlüssel, hinter dem je Jahrgang MEHRERE Dokumente
        # stehen: Ein Produkt-Jahrgang verteilt sich auf rund neun
        # Teilhaushalts-Anlagen (s. finanzquellen.Finanzquelle).
        "teilhaushalt":         ("council_produkte", "jahr", None, "quelle_url"),
        "pruefbericht":         ("council_pruefbericht_quellen", "jahr", None, "url"),
        "gesamtabschluss":      ("council_konzern_posten", "jahr", None, None),
        # Nur die geprüften Zeilen: Die Bezugsgröße „Gesamtbetrag des
        # Finanzhaushaltes" steht in derselben Datei, aber an einer anderen
        # Fundstelle und ohne Probe — ohne diesen Filter stünden je Jahrgang
        # zwei Dokumente im Verzeichnis, wo es eines ist.
        "investitionen":        ("council_investitionen", "jahr",
                                 "t.ebene = 'teilhaushalt'", None),
        # Alle Zeilen eines Jahrgangs teilen sich eine Herkunft; die
        # `gesamt`-Zeile gibt es genau einmal und steht hier für das Dokument.
        "investitionsprogramm": ("council_investitionsmassnahmen", "jahr",
                                 "t.ebene = 'gesamt'", None),
        # Ein Jahrgang, zwei Herkünfte (Teil A und Teil B im selben PDF, aber
        # unter verschiedenen Proben). Beide zeigen auf dieselbe Datei; die
        # Fundstelle unterscheidet sie, und `DISTINCT` fasst sie deshalb nicht
        # zusammen — genau richtig, denn ein Beleg an einer Beamtenzahl soll
        # „Teil A" sagen und nicht „Stellenplan".
        "stellenplan":          ("council_stellenplan", "jahrgang", None, None),
        # Der einzige Schlüssel, dessen Jahresspalte NICHT das Datenjahr ist:
        # Ein Bericht liefert fünf Jahrgänge, gehört aber zu genau einem
        # Dokument — und das ist seines.
        "kennzahlen":           ("council_kennzahlen", "bericht_jahr", None, None),
        # Die drei Schichten vom 20.08.2026. Sie standen bis zum 21.08. NICHT
        # hier, und man hat es der Seite angesehen: Unter 33 Wirtschaftsplänen
        # aus sieben Betrieben stand eine einzige Quelle, deren Link auf die
        # Startseite des Ratsinformationssystems führte. Der Eintrag hier ist
        # der ganze Unterschied zwischen „kommt aus dem RIS" und „steht in
        # diesem PDF".
        #
        # Wie ``teilhaushalt`` tragen alle drei je Jahrgang MEHRERE Dokumente,
        # und das ist hier keine Eigenheit, sondern der Kern: Ein Jahrgang
        # Wirtschaftsplan besteht aus sieben Plänen von sieben Betrieben, und
        # jeder ist ein eigenes Papier mit eigener Vorlagennummer.
        "wirtschaftsplan":      ("council_wirtschaftsplaene", "jahr", None, None),
        # Nachträge tragen eine eigene Satzung und ein eigenes Dokument; der
        # Schlüssel unterscheidet sie nicht, die Fundstelle tut es.
        "haushaltssatzung":     ("council_haushaltssatzung", "jahr", None, None),
        "gebuehren":            ("council_gebuehren", "jahr", None, None),
        # Die Änderungslisten zum Haushalt. Wie `wirtschaftsplan` stehen je
        # Jahrgang MEHRERE Papiere dahinter (Verw. I–III und die
        # Beschluss-Datei des AFB) — die Summen-Tabelle trägt je Dokument
        # eine Herkunft, DISTINCT macht daraus die Papierliste des Jahrgangs.
        "aenderungsliste":      ("council_haushalt_aenderungen_summen",
                                 "jahrgang", None, None),
    }

    #: Jahresquellen, die KEIN Dokument im Ratsinformationssystem haben und
    #: deshalb nicht in ``_DOKUMENT_QUELLEN`` stehen — Downloads von
    #: oldenburg.de, Open Data und die Landesstatistik. Für die Frage „welche
    #: Jahrgänge deckt diese Quelle ab?" zählen sie genauso.
    _WEITERE_JAHRESQUELLEN: dict[str, tuple[str, str, str | None]] = {
        "steuern":     ("council_steuern", "jahr", None),
        "steuerkraft": ("council_steuerkraft", "jahr", None),
        "einwohner":   ("council_einwohner", "jahr", None),
        "schulden":    ("council_schulden", "jahr", None),
        "gebaut":      ("council_investitionen_ist", "jahr", None),
        "ausgabenreihe": ("council_ausgabenreihe", "jahr", None),
        "buergschaften": ("council_buergschaften", "jahr", None),
        "anlagenspiegel": ("council_anlagenspiegel", "jahr", None),
        "vermoegensgruppen": ("council_vermoegensgruppen", "jahr", None),
        "integrierte_schulden": ("council_integrierte_schulden", "jahr", None),
        "spenden":     ("council_spenden", "jahr", None),
        "steuerplan":  ("council_steuerplan", "jahr", None),
        "hebesaetze":  ("council_hebesaetze", "jahr", None),
    }

    def haushalt_jahrgaenge(self) -> dict[str, list[int]]:
        """Je Quellenschlüssel die Jahrgänge, die **wirklich** im Bestand
        stehen — aufsteigend, ohne Dubletten.

        Wofür: Das Quellenverzeichnis schrieb seine Datenstände von Hand
        („Jahresabschlüsse 2017–2024"), einundzwanzig Stück in
        ``lib/haushalt-quellen.ts``, mit der Bitte im Dateikopf, sie beim
        Nachziehen eines Haushaltsjahres zu aktualisieren. Genau das passiert
        naturgemäß nicht zuverlässig: Ein Ingest-Lauf zieht einen Jahrgang
        nach, die Seite behauptet weiter den alten Stand, und niemand merkt
        es — die Angabe steht ja nicht neben den Daten, sondern in einer
        anderen Datei.

        Bewusst **nicht** über ``haushalt_dokumente`` gerechnet: Das dort
        nötige „hat eine URL" ist eine andere Frage. Ein Jahrgang, der im
        Bestand steht, dessen Herkunft aber keine Adresse führt, ist für den
        Datenstand vorhanden und für den Dokumentlink nicht. Wer beides aus
        einer Abfrage nähme, verschwiege im Datenstand genau die Jahrgänge,
        die ohnehin schon am dünnsten belegt sind.

        Was hier fehlt, bleibt in der Konstante von Hand gepflegt: Die
        Ausgabe-Datumsangaben der Statistikstellen („Ausgabe vom 08.07.2026")
        stehen in keiner Tabelle, und zwei Quellen sind schlicht statisch
        (eine einzelne Ratsvorlage von 2018; „Sitzungen seit Januar 2018"
        ohne obere Grenze)."""
        quellen = {k: (t, j, f) for k, (t, j, f, _) in self._DOKUMENT_QUELLEN.items()}
        quellen.update(self._WEITERE_JAHRESQUELLEN)
        aus: dict[str, list[int]] = {}
        for key, (tabelle, jahrspalte, filter_) in quellen.items():
            sql = (f"SELECT DISTINCT t.{jahrspalte} AS jahr FROM {tabelle} t"
                   + (f" WHERE {filter_}" if filter_ else "")
                   + f" ORDER BY t.{jahrspalte}")
            try:
                jahre = [int(r["jahr"]) for r in self._conn.execute(sql)
                         if r["jahr"] is not None]
            except sqlite3.OperationalError:
                continue  # Tabelle oder Spalte gibt es in dieser DB (noch) nicht
            if jahre:
                aus[key] = jahre
        return aus

    def haushalt_dokumente(self) -> dict[str, list[dict]]:
        """Je Quellenschlüssel die Dokumente, Jahrgang für Jahrgang.

        Die Antwort auf die Frage, die das Quellenverzeichnis stellt: „Der
        Beleg steht an einer Zahl von 2021 — welches PDF ist das?" Ohne sie
        führte der Link auf die Startseite des Ratsinformationssystems, und
        ein Beleg, der nur zur Startseite führt, ist keiner.

        Bevorzugt wird ``council_herkunft``: Dort steht neben der URL auch die
        **Fundstelle** im Dokument („Abschnitt 3.1") — bei 300 Seiten der
        Unterschied zwischen Nachschlagen und Suchen. Fehlt die Herkunft
        (Altbestand), tritt die URL an der Datenzeile ein; fehlt auch die,
        fällt der Jahrgang weg statt mit einer erfundenen Adresse
        dazustehen.

        Jedes Dokument aus dem Ratsinformationssystem trägt zusätzlich seinen
        ``official_text`` — den Ratsvorgang, der es verabschiedet hat (s.
        :meth:`beschluesse_zu_dokumenten`). Der Beleg sagt damit nicht nur, in
        welchem Papier die Zahl steht, sondern wann der Rat darüber entschieden
        hat. Bei den Schichten von oldenburg.de und vom Landesamt bleibt das
        Feld ``None``: Die hängen an keiner Vorlage."""
        aus: dict[str, list[dict]] = {}
        for key, (tabelle, jahrspalte, filter_, alt) in self._DOKUMENT_QUELLEN.items():
            wo = [f"{filter_}"] if filter_ else []
            url = f"COALESCE(k.url, t.{alt})" if alt else "k.url"
            sql = (f"SELECT DISTINCT t.{jahrspalte} AS jahr, {url} AS url, "
                   f" k.label AS label, k.fundstelle AS fundstelle, k.seite AS seite, "
                   f" k.dokument_id AS dokument_id "
                   f"FROM {tabelle} t "
                   f"LEFT JOIN council_herkunft k ON k.id = t.herkunft_id"
                   + (" WHERE " + " AND ".join(wo) if wo else "")
                   + f" ORDER BY t.{jahrspalte}, url")
            try:
                rows = [dict(r) for r in self._conn.execute(sql)]
            except sqlite3.OperationalError:
                continue  # Tabelle oder Spalte gibt es in dieser DB (noch) nicht
            treffer = [r for r in rows if r["url"]]
            if treffer:
                aus[key] = treffer
        # Ein Nachschlag für den ganzen Bereich statt einer je Dokument: Der
        # Apparat einer Seite zeigt bis zu neun Teilhaushalts-Anlagen, und das
        # Verzeichnis am Fuß zeigt alle Quellen auf einmal.
        beschluesse = self.beschluesse_zu_dokumenten(sorted(
            {r["dokument_id"] for liste in aus.values()
             for r in liste if r.get("dokument_id")}))
        for liste in aus.values():
            for r in liste:
                # `dokument_id` war nur der Schlüssel für den Nachschlag und
                # fliegt wieder raus: Was auf die Seite geht, ist der Vorgang,
                # nicht die RIS-interne Nummer des Anhangs.
                r["official_text"] = beschluesse.get(r.pop("dokument_id", None))
        return aus

    # --- Stadt-Haushalt (council.haushalt) -----------------------------------

    def save_haushalt(self, year: int, rows: list[dict], herkunft) -> int:
        """Ergebnishaushalt eines Jahres speichern — ersetzt den bisherigen
        Stand des Jahres komplett (Re-Ingest idempotent).

        ``herkunft`` ist eine :class:`council.herkunft.Herkunft` und hat den
        früheren ``source_url``-String abgelöst: Eine URL allein sagt nicht,
        an welcher Stelle eines 300-Seiten-PDFs gelesen wurde und was die
        Zahlen absichert. ``source_url`` steht weiter in der Tabelle und wird
        aus derselben Angabe gefüllt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_haushalt WHERE year = ?", (year,))
            for r in rows:
                self._conn.execute(
                    "INSERT INTO council_haushalt (year, bereich, ertraege, aufwendungen, "
                    " ergebnis, is_summe, source_url, fetched_at, herkunft_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (year, r["bereich"], r.get("ertraege"), r.get("aufwendungen"),
                     r.get("ergebnis"), int(r.get("is_summe", 0)),
                     herkunft.url, now, hid))
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

    def save_steuereinnahmen(self, rows: list[dict], herkunft) -> int:
        """Ist-Steuereinnahmen (jahr, art, betrag) ersetzen — Re-Ingest idempotent."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_steuern "
                "(jahr, art, betrag, source_url, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?)",
                [(r["jahr"], r["art"], r.get("betrag"), herkunft.url, now, hid)
                 for r in rows])
        return len(rows)

    def get_steuereinnahmen(self) -> list[dict]:
        """Alle Ist-Steuereinnahmen, älteste zuerst (Langformat je Jahr × Art)."""
        return [dict(r) for r in self._conn.execute(
            "SELECT jahr, art, betrag FROM council_steuern ORDER BY jahr, art")]

    def save_steuerkraft(self, rows: list[dict], herkunft) -> int:
        """Steuerkraftmesszahl + Schlüsselzuweisungen je Ausgleichsjahr ersetzen.

        Anders als die Nachbar-Methoden räumt diese auch auf: Der Datensatz
        1106 liefert die **ganze** Reihe bei jedem Lauf, und seit der
        Jahres-Korrektur (``haushalt._STEUERKRAFT_VERSATZ``) trägt jede Zeile
        ein anderes Jahr als beim letzten Mal. Ein reines INSERT OR REPLACE
        ließe genau einen Jahrgang als Leiche zurück — den ältesten, den es
        nach dem Rücken nicht mehr gibt. Der stünde dann mit den Beträgen
        seines Nachfolgers in der Tabelle, und niemand käme je darauf.

        Eine leere Lieferung räumt **nichts** ab: Ein misslungener Download
        darf den Bestand nicht löschen. Der Ingest bricht in dem Fall ohnehin
        vorher ab, aber die Methode soll das auch allein aushalten.
        """
        if not rows:
            return 0
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_steuerkraft "
                "(jahr, messzahl, messzahl_je_ew, zuweisungen, zuweisungen_je_ew, "
                " source_url, fetched_at, herkunft_id) VALUES (?,?,?,?,?,?,?,?)",
                [(r["jahr"], r.get("messzahl"), r.get("messzahl_je_ew"),
                  r.get("zuweisungen"), r.get("zuweisungen_je_ew"),
                  herkunft.url, now, hid) for r in rows])
            jahre = [r["jahr"] for r in rows]
            self._conn.execute(
                "DELETE FROM council_steuerkraft WHERE jahr NOT IN "
                f"({','.join('?' * len(jahre))})", jahre)
        return len(rows)

    def save_einwohner(self, rows: list[dict], herkunft) -> int:
        """Einwohnerzahlen je Jahr ersetzen (idempotent)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_einwohner "
                "(jahr, einwohner, source_url, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?)",
                [(r["jahr"], r["einwohner"], herkunft.url, now, hid) for r in rows])
        return len(rows)

    def einwohner_aktuell(self) -> dict | None:
        """Jüngste bekannte Einwohnerzahl — Bezugsgröße für Pro-Kopf-Angaben."""
        try:
            r = self._conn.execute(
                "SELECT jahr, einwohner FROM council_einwohner ORDER BY jahr DESC LIMIT 1").fetchone()
        except sqlite3.OperationalError:
            return None
        return dict(r) if r else None

    def save_ergebnisrechnung(self, jahr: int, posten: list[dict], herkunft,
                              thh_nr: int | None = None, thh_name: str | None = None,
                              ersetzen: bool = True) -> int:
        """Ergebnisrechnung einer Ebene speichern — ohne ``thh_nr`` die
        Gesamtrechnung, sonst der jeweilige Teilhaushalt.

        ``ersetzen`` löscht vorher die betroffene Ebene dieses Jahres; beim
        Einlesen mehrerer Teilhaushalte nacheinander bleibt es an.

        ``herkunft`` steht, wo früher ``label, url`` standen. Die beiden
        Ebenen dieses Dokuments bekommen bewusst **verschiedene** Herkünfte:
        Sie stehen an verschiedenen Stellen des Jahresabschlusses und sind
        durch verschiedene Proben gedeckt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            if ersetzen:
                if thh_nr is None:
                    self._conn.execute(
                        "DELETE FROM council_ergebnisrechnung WHERE jahr = ? AND thh_nr IS NULL",
                        (jahr,))
                else:
                    self._conn.execute(
                        "DELETE FROM council_ergebnisrechnung WHERE jahr = ? AND thh_nr = ?",
                        (jahr, thh_nr))
            self._conn.executemany(
                "INSERT INTO council_ergebnisrechnung (jahr, thh_nr, thh_name, nr, bezeichnung, "
                " vorjahr, ansatz, plan, plan_art, ergebnis, deviation, ist_summe, "
                " quelle_label, quelle_url, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                # `plan` fällt auf `ansatz` zurück, wenn der Aufrufer keine
                # eigene Bezugsgröße mitbringt — und zwar auch bei
                # ausdrücklichem ``None``. `p.get("plan", …)` täte das nicht:
                # Der Vorgabewert greift nur bei fehlendem Schlüssel. Dieselbe
                # Falle stand im Lesepfad (s. `get_plan_ist.plan_von`).
                [(jahr, thh_nr, thh_name, p["nr"], p["bezeichnung"], p.get("vorjahr"),
                  p.get("ansatz"),
                  p.get("ansatz") if p.get("plan") is None else p.get("plan"),
                  p.get("plan_art"),
                  p.get("ergebnis"), p.get("deviation"),
                  p.get("ist_summe", 0), herkunft.label, herkunft.url, now, hid)
                 for p in posten])
        return len(posten)

    def save_abweichungsgruende(self, jahr: int, gruende: list[dict], herkunft) -> int:
        """Erläuterungen zu den Plan/Ist-Abweichungen eines Jahrgangs
        ersetzen. Übergeben wird nur, was die Rechenprobe bestanden hat."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_abweichungsgruende WHERE jahr = ?", (jahr,))
            self._conn.executemany(
                "INSERT INTO council_abweichungsgruende (jahr, nr, bezeichnung, "
                " delta_mio, prozent, text, quelle_label, quelle_url, fetched_at, "
                " herkunft_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(jahr, g["nr"], g["bezeichnung"], g.get("delta_mio"), g.get("prozent"),
                  g["text"], herkunft.label, herkunft.url, now, hid) for g in gruende])
        return len(gruende)

    def get_abweichungsgruende(self, jahr: int | None = None) -> list[dict]:
        """Erläuterungen — ein Jahr oder alle, in Tabellenreihenfolge."""
        try:
            if jahr is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_abweichungsgruende ORDER BY jahr, nr").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_abweichungsgruende WHERE jahr = ? ORDER BY nr",
                    (jahr,)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def save_pruefbericht_quelle(self, jahr: int, herkunft,
                                 n_pages: int | None, lesbar: bool) -> None:
        """Fundstelle des RPA-Schlussberichts eines Jahrgangs merken."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_pruefbericht_quellen "
                "(jahr, label, url, n_pages, lesbar, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?)",
                (jahr, herkunft.label, herkunft.url, n_pages,
                 1 if lesbar else 0, now, hid))

    def get_pruefbericht_quellen(self) -> list[dict]:
        """Alle bekannten Schlussberichte, ältester zuerst."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT jahr, label, url, n_pages, lesbar, herkunft_id "
                "FROM council_pruefbericht_quellen ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    def get_plan_ist(self, jahr: int) -> dict:
        """„Geplant und geworden" eines Jahres: die Summenzeilen (Erträge 12,
        Aufwendungen 20) für die Kernverwaltung und je Teilhaushalt.

        Liefert ``{gesamt: {...}, bereiche: [...]}`` — die Bereiche nach
        geplanten Aufwendungen absteigend, damit die größten oben stehen."""
        rows = [dict(r) for r in self._conn.execute(
            "SELECT thh_nr, thh_name, nr, ansatz, plan, plan_art, ergebnis, deviation "
            "FROM council_ergebnisrechnung WHERE jahr = ? AND nr IN (12, 20) "
            "ORDER BY thh_nr, nr", (jahr,))]

        def plan_von(r: dict):
            """Bezugsgröße der Abweichung — mit Rückfall auf den Ansatz.

            Der Rückfall ist kein Schönheitsfehler, sondern der Normalfall für
            jeden Bestand, der vor #510 geschrieben wurde: `plan` und
            `plan_art` kamen damals per ALTER TABLE dazu, und ALTER TABLE füllt
            nichts nach — alle vorhandenen Zeilen tragen dort seither NULL,
            obwohl `ansatz` danebensteht und richtig ist. Auf `/haushalt/
            plan-ist` hieß das: „Die Planwerte der Gesamtrechnung konnten wir
            für diesen Jahrgang nicht auslesen" für **jeden** Jahrgang, bis
            jemand von Hand neu einliest.

            Bis 16.08.2026 stand hier ``r.get("plan", r.get("ansatz"))``. Das
            sieht aus wie genau dieser Rückfall und ist keiner: `r` kommt aus
            einem ``SELECT plan, …``, der Schlüssel ist also **immer** da, und
            `dict.get` greift seinen Vorgabewert nur bei fehlendem Schlüssel
            ab — nie bei ``None``. Der Zweig war toter Code."""
            wert = r.get("plan")
            return r.get("ansatz") if wert is None else wert

        def bauen(teil: list[dict]) -> dict:
            e = next((r for r in teil if r["nr"] == 12), {})
            a = next((r for r in teil if r["nr"] == 20), {})
            # `plan` ist die Bezugsgröße der Abweichung, `ansatz` der
            # ursprüngliche Haushaltsansatz — 2018 und 2020 fallen auseinander.
            return {"ertraege_plan": plan_von(e),
                    "ertraege_ansatz": e.get("ansatz"),
                    "ertraege_ist": e.get("ergebnis"),
                    "aufwendungen_plan": plan_von(a),
                    "aufwendungen_ansatz": a.get("ansatz"),
                    "aufwendungen_ist": a.get("ergebnis"),
                    "plan_art": a.get("plan_art") or e.get("plan_art")}

        gesamt = [r for r in rows if r["thh_nr"] is None]
        bereiche = []
        for nr in sorted({r["thh_nr"] for r in rows if r["thh_nr"] is not None}):
            teil = [r for r in rows if r["thh_nr"] == nr]
            bereiche.append({"thh_nr": nr, "thh_name": teil[0]["thh_name"], **bauen(teil)})
        bereiche.sort(key=lambda b: -(b["aufwendungen_plan"] or 0))
        return {"jahr": jahr, "gesamt": bauen(gesamt) if gesamt else None, "bereiche": bereiche}

    def plan_ist_jahre(self) -> list[int]:
        """Jahre, für die Teilhaushalts-Ist vorliegt (aufsteigend)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT jahr FROM council_ergebnisrechnung "
                "WHERE thh_nr IS NOT NULL ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    def get_ergebnisrechnung(self, jahr: int | None = None) -> list[dict]:
        """Ergebnisrechnung — ein Jahr oder alle, Posten in Tabellenreihenfolge."""
        if jahr is None:
            rows = self._conn.execute(
                "SELECT * FROM council_ergebnisrechnung ORDER BY jahr, nr").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM council_ergebnisrechnung WHERE jahr = ? ORDER BY nr", (jahr,)).fetchall()
        return [dict(r) for r in rows]

    def ergebnisrechnung_jahre(self) -> list[int]:
        """Jahre mit eingelesenem Jahresabschluss (aufsteigend)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT jahr FROM council_ergebnisrechnung ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    # --- Finanzrechnung der Kernverwaltung (council.finanzberichte) ----------

    def save_finanzrechnung(self, jahr: int, zeilen: list[dict], herkunft) -> int:
        """Die Kassensicht eines Jahrgangs ersetzen.

        Übergeben wird nur, was ``finanzberichte.finanzprobe`` durchgelassen
        hat — die Funktion streicht Ketten, die nicht aufgehen, schon vorher
        heraus. Hier wird deshalb nichts mehr geprüft, nur geschrieben."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_finanzrechnung WHERE jahr = ?", (jahr,))
            self._conn.executemany(
                "INSERT INTO council_finanzrechnung (jahr, nr, rolle, bezeichnung, "
                " vorjahr, ansatz, plan, plan_art, ergebnis, deviation, "
                " ermaechtigung, ist_summe, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(jahr, z["nr"], z.get("rolle"), z["bezeichnung"], z.get("vorjahr"),
                  z.get("ansatz"), z.get("plan"), z.get("plan_art"), z.get("ergebnis"),
                  z.get("deviation"), z.get("ermaechtigung"),
                  z.get("ist_summe", 0), hid, now)
                 for z in zeilen])
        return len(zeilen)

    def get_finanzrechnung(self, jahr: int | None = None) -> list[dict]:
        """Finanzrechnung — ein Jahr oder alle, Zeilen in Dokumentreihenfolge."""
        try:
            if jahr is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_finanzrechnung ORDER BY jahr, nr").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_finanzrechnung WHERE jahr = ? ORDER BY nr",
                    (jahr,)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def finanzrechnung_jahre(self) -> list[int]:
        """Jahre mit eingelesener Finanzrechnung (aufsteigend)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT jahr FROM council_finanzrechnung ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    # --- Bilanz der Stadt (council.bilanz) -----------------------------------

    def save_bilanz(self, jahr: int, posten: list[dict], herkunft) -> int:
        """Einen Bilanzstichtag ersetzen.

        Übergeben wird nur, was ``bilanz.bilanzprobe`` durchgelassen hat —
        eine Bilanz, deren Seiten nicht aufgehen, kommt dort gar nicht erst
        heraus. Hier wird deshalb nichts mehr geprüft, nur geschrieben."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_bilanz WHERE jahr = ?", (jahr,))
            self._conn.executemany(
                "INSERT INTO council_bilanz (jahr, rolle, seite, ebene, nr, "
                " bezeichnung, wert, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(jahr, p["rolle"], p["seite"], p["ebene"], p.get("nr"),
                  p["bezeichnung"], p["wert"], hid, now) for p in posten])
        return len(posten)

    def get_bilanz(self, jahr: int | None = None) -> list[dict]:
        """Bilanzposten — ein Stichtag oder alle.

        Sortiert nach Jahr, dann Aktiva vor Passiva, dann in der Reihenfolge
        des Dokuments. ``ORDER BY seite DESC`` ist kein Tippfehler: ``aktiva``
        steht alphabetisch vor ``passiva``, und die Bilanz druckt die
        Aktivseite zuerst — absteigend sortiert kommt genau das heraus."""
        try:
            sql = ("SELECT * FROM council_bilanz {} "
                   "ORDER BY jahr, seite ASC, ebene, rolle")
            if jahr is None:
                rows = self._conn.execute(sql.format("")).fetchall()
            else:
                rows = self._conn.execute(sql.format("WHERE jahr = ?"), (jahr,)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def bilanz_jahre(self) -> list[int]:
        """Bilanzstichtage im Bestand (aufsteigend)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT jahr FROM council_bilanz ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    def get_ruecklagen(self) -> list[dict]:
        """Verfügbare Überschussrücklage nach abgeschlossenem Jahr.

        Die Bilanz zeigt den bereits umgebuchten Stand in Position 1.2.1 und
        das Ergebnis des gerade abgeschlossenen Jahres noch separat in 1.3.
        Der Vorbericht des Folgehaushalts nennt deshalb beide zusammen („unter
        Berücksichtigung des Ergebnisses"). Genau diese nachvollziehbare
        Addition liefert die Reihe; andere, zweckgebundene Rücklagen bleiben
        ausdrücklich draußen.
        """
        try:
            rows = self._conn.execute(
                "SELECT jahr, rolle, wert, herkunft_id FROM council_bilanz "
                "WHERE rolle IN ('ueberschussruecklage_ordentlich', "
                "'jahresergebnis_bilanz') ORDER BY jahr, rolle").fetchall()
        except sqlite3.OperationalError:
            return []
        jahre: dict[int, dict] = {}
        for row in rows:
            z = jahre.setdefault(row["jahr"], {
                "jahr": row["jahr"], "ruecklage": None,
                "jahresergebnis": None, "stand_nach_ergebnis": None,
                "herkunft_id": row["herkunft_id"],
            })
            if row["rolle"] == "ueberschussruecklage_ordentlich":
                z["ruecklage"] = row["wert"]
            else:
                z["jahresergebnis"] = row["wert"]
        aus = []
        for jahr in sorted(jahre):
            z = jahre[jahr]
            if z["ruecklage"] is None or z["jahresergebnis"] is None:
                continue
            z["stand_nach_ergebnis"] = z["ruecklage"] + z["jahresergebnis"]
            aus.append(z)
        return aus

    def save_bilanz_erlaeuterungen(self, jahr: int, abschnitte: list[dict],
                                   herkunft) -> int:
        """Die Erläuterungen des Anhangs zu einem Jahrgang ersetzen."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_bilanz_erlaeuterungen WHERE jahr = ?", (jahr,))
            self._conn.executemany(
                "INSERT INTO council_bilanz_erlaeuterungen (jahr, rolle, nr, "
                " ueberschrift, text, herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?)",
                [(jahr, a["rolle"], a["nr"], a["ueberschrift"], a["text"], hid, now)
                 for a in abschnitte])
        return len(abschnitte)

    def get_bilanz_posten(self, rolle: str) -> list[dict]:
        """Eine einzelne Bilanzposition über alle Stichtage.

        Für Zahlen, die außerhalb der Bilanzseite gebraucht werden und dort
        ihre Bedeutung erst bekommen — die Geldschulden neben dem
        Bürgschaftsbestand etwa (`council/buergschaften.py`). Die ganze Bilanz
        dafür zu holen und im Aufrufer zu filtern hieße, 131 Zeilen zu laden,
        um drei zu benutzen."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_bilanz WHERE rolle = ? ORDER BY jahr", (rolle,))]
        except sqlite3.OperationalError:
            return []

    def get_bilanz_erlaeuterungen(self, jahr: int | None = None) -> list[dict]:
        """Erläuterungen zur Bilanz — ein Jahrgang oder alle."""
        try:
            sql = ("SELECT * FROM council_bilanz_erlaeuterungen {} "
                   "ORDER BY jahr, nr")
            if jahr is None:
                rows = self._conn.execute(sql.format("")).fetchall()
            else:
                rows = self._conn.execute(sql.format("WHERE jahr = ?"), (jahr,)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    # --- Gesamtergebnishaushalt (Planjahre, council.ergebnishaushalt) --------

    def save_ergebnishaushalt(self, plan_jahrgang: int, zeilen: list[dict],
                              herkunft) -> int:
        """Einen Haushaltsplan-Jahrgang ersetzen — Ansatz und Finanzplanung
        zusammen, weil sie aus **einer** Tabelle eines Dokuments stammen.

        Gelöscht wird nach ``plan_jahrgang``, nicht nach ``jahr``: Was der
        Haushalt 2026 über 2027 sagt, gehört ihm; was der Haushalt 2027 über
        2027 sagt, ist eine andere Zeile und bleibt stehen.

        Übergeben wird nur, was beide Pflicht-Proben bestanden hat — diese
        Methode prüft nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_ergebnishaushalt WHERE plan_jahrgang = ?",
                (plan_jahrgang,))
            self._conn.executemany(
                "INSERT INTO council_ergebnishaushalt (plan_jahrgang, jahr, art, nr, "
                " bezeichnung, betrag, ist_summe, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(plan_jahrgang, z["jahr"], z["art"], z["nr"], z["bezeichnung"],
                  z["betrag"], 1 if z.get("ist_summe") else 0, now, hid)
                 for z in zeilen])
        return len(zeilen)

    def ergebnishaushalt_jahrgaenge(self) -> list[int]:
        """Haushaltsplan-Jahrgänge, die eingelesen sind (aufsteigend).

        Der **Plan**-Jahrgang, nicht die Jahre darin: Ein Dokument trägt sein
        Planjahr und drei Finanzplanungsjahre, und vollständig ist es erst,
        wenn alle vier dastehen — was ``save_ergebnishaushalt`` zusammen
        schreibt oder gar nicht."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT plan_jahrgang FROM council_ergebnishaushalt "
                "ORDER BY plan_jahrgang")]
        except sqlite3.OperationalError:
            return []

    def get_ergebnishaushalt(self, jahr: int | None = None,
                             art: str | None = None) -> list[dict]:
        """Planzahlen je Posten — gefiltert nach Jahr und/oder Art.

        ``art="ansatz"`` ist die Frage, die eine Seite fast immer meint: „was
        ist für dieses Jahr geplant?". Ohne Filter kommt auch die
        Finanzplanung mit; sie ist als solche beschriftet und darf nur so
        gezeigt werden."""
        wo, werte = [], []
        if jahr is not None:
            wo.append("jahr = ?")
            werte.append(jahr)
        if art is not None:
            wo.append("art = ?")
            werte.append(art)
        satz = (" WHERE " + " AND ".join(wo)) if wo else ""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_ergebnishaushalt" + satz
                + " ORDER BY jahr, art, nr", werte)]
        except sqlite3.OperationalError:
            return []

    def ansatz_jahre(self) -> list[int]:
        """Jahre, für die ein Haushaltsansatz vorliegt (aufsteigend).

        Bewusst ohne die Finanzplanungsjahre: Eine Jahresliste, die 2029
        mitführt, wird irgendwo zu einem Umschalter, und dann steht auf der
        Seite ein Jahr, für das nie ein Haushalt aufgestellt wurde."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT jahr FROM council_ergebnishaushalt "
                "WHERE art = 'ansatz' ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    # --- Stellenplan (council.stellenplan) ----------------------------------

    def save_stellenplan(self, jahrgang: int, teil: str, zeilen: list[dict],
                         herkunft, stichtag: str | None = None) -> int:
        """Einen Teil eines Stellenplan-Jahrgangs ersetzen.

        Ersetzt wird nach ``(jahrgang, teil)``, nicht nach Jahrgang: Die
        beiden Teile stehen zwar im selben PDF, kommen aber einzeln durch
        ihre Proben — im Jahrgang 2026 ist Teil B im Textextrakt unlesbar,
        Teil A tadellos. Wer nach Jahrgang löschte, risse mit dem einen den
        anderen mit.

        Übergeben wird nur, was seine Proben bestanden hat; diese Methode
        prüft nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_stellenplan WHERE jahrgang = ? AND teil = ?",
                (jahrgang, teil))
            self._conn.executemany(
                "INSERT INTO council_stellenplan (jahrgang, teil, zeile, art, "
                " gruppe, lfd_nr, bezeichnung, besoldung, stellen_plan, "
                " stellen_vorjahr, besetzt, besetzt_beamte, besetzt_arbeitnehmer, "
                " nicht_besetzt, stichtag, stimmig, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(jahrgang, teil, i, z["art"], z.get("gruppe"), z.get("lfd_nr"),
                  z["bezeichnung"], z.get("besoldung"), z["stellen_plan"],
                  z["stellen_vorjahr"], z["besetzt"], z.get("besetzt_beamte"),
                  z.get("besetzt_arbeitnehmer"), z["nicht_besetzt"], stichtag,
                  1 if z.get("stimmig", 1) else 0, now, hid)
                 for i, z in enumerate(zeilen)])
        return len(zeilen)

    def stellenplan_einheiten(self) -> set[tuple]:
        """Welche ``(Jahrgang, Teil)`` im Bestand stehen.

        Die Einheit ist der **Teil**, nicht der Jahrgang: Ein Jahrgang, von
        dem nur Teil A lesbar war, sähe sonst aus wie ein vollständiger — und
        eine Seite, die dann „2026: 815 Stellen" schreibt, unterschlüge die
        1.700 Tarifstellen, statt sie zu vermissen."""
        try:
            return {(r[0], r[1]) for r in self._conn.execute(
                "SELECT DISTINCT jahrgang, teil FROM council_stellenplan")}
        except sqlite3.OperationalError:
            return set()

    def get_stellenplan(self, art: str | None = None,
                        jahrgang: int | None = None) -> list[dict]:
        """Stellenplan-Zeilen — gefiltert nach Stufe und/oder Jahrgang.

        ``art="gesamt"`` ist die Frage, die die Übersichtsseite meint („wie
        viele Stellen, wie viele davon unbesetzt?"); ohne Filter kommen alle
        rund tausend Einzelposten mit."""
        wo, werte = [], []
        if art is not None:
            wo.append("art = ?")
            werte.append(art)
        if jahrgang is not None:
            wo.append("jahrgang = ?")
            werte.append(jahrgang)
        satz = (" WHERE " + " AND ".join(wo)) if wo else ""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_stellenplan" + satz
                + " ORDER BY jahrgang, teil, zeile", werte)]
        except sqlite3.OperationalError:
            return []

    # --- Investitionen des Finanzhaushalts (council.investitionen) ----------

    def save_investitionen(self, jahr: int, zeilen: list[dict], gesamt: dict,
                           herkunft, finanzhaushalt: dict | None = None,
                           herkunft_finanzhaushalt=None) -> int:
        """Einen Jahrgang Investitionen ersetzen — Teilhaushalte und
        Summenzeile zusammen, weil sie aus **einer** Tabelle stammen und die
        Summenzeile das Ziel der Rechenprobe ist.

        Zwei Herkünfte, weil es zwei verschiedene Aussagen sind: Die
        Investitionen sind durch die Summenprobe der Datei gedeckt, der
        *Gesamtbetrag des Finanzhaushaltes* ist es nicht (er zählt die laufende
        Verwaltungstätigkeit mit, und nichts in der Datei summiert sich auf
        ihn). Eine gemeinsame Herkunft behauptete für ihn eine Probe, die es
        nicht gibt.

        Übergeben wird nur, was die Probe bestanden hat — diese Methode prüft
        nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_investitionen WHERE jahr = ?", (jahr,))
            werte = [(jahr, "teilhaushalt", z["thh_nr"], z["bezeichnung"],
                      z["einzahlungen"], z["auszahlungen"], now, hid)
                     for z in zeilen]
            werte.append((jahr, "investitionen", 0, gesamt["bezeichnung"],
                          gesamt["einzahlungen"], gesamt["auszahlungen"], now, hid))
            if finanzhaushalt:
                hid_fh = (self.merke_herkunft(herkunft_finanzhaushalt, fetched_at=now)
                          if herkunft_finanzhaushalt is not None else hid)
                werte.append((jahr, "finanzhaushalt", 0,
                              finanzhaushalt["bezeichnung"],
                              finanzhaushalt["einzahlungen"],
                              finanzhaushalt["auszahlungen"], now, hid_fh))
            self._conn.executemany(
                "INSERT INTO council_investitionen (jahr, ebene, thh_nr, bezeichnung, "
                " einzahlungen, auszahlungen, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?)", werte)
        return len(werte)

    def investitionen_jahre(self) -> list[int]:
        """Haushaltsjahre, für die Investitionen vorliegen (aufsteigend).

        Gezählt wird an der **Summenzeile**, nicht an irgendeiner Zeile: Sie
        kommt nur in die Tabelle, wenn die Rechenprobe aufging, und ist damit
        das Kennzeichen eines vollständigen Jahrgangs."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT jahr FROM council_investitionen "
                "WHERE ebene = 'investitionen' ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    def get_investitionen(self, jahr: int | None = None,
                          ebene: str | None = None) -> list[dict]:
        """Investitionszeilen — gefiltert nach Jahr und/oder Ebene.

        Ohne Filter kommen alle drei Ebenen mit; sie sind als ``ebene``
        beschriftet und dürfen nur so gezeigt werden. Wer die Teilhaushalte
        addiert und das Ergebnis neben die Summenzeile stellt, zeigt zweimal
        dieselbe Zahl."""
        wo, werte = [], []
        if jahr is not None:
            wo.append("jahr = ?")
            werte.append(jahr)
        if ebene is not None:
            wo.append("ebene = ?")
            werte.append(ebene)
        satz = (" WHERE " + " AND ".join(wo)) if wo else ""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_investitionen" + satz
                + " ORDER BY jahr, ebene, thh_nr", werte)]
        except sqlite3.OperationalError:
            return []

    # --- Investitionsprogramm (Anlage 004 des Haushaltsplans) ---------------

    def save_investitionsprogramm(self, jahr: int, gelesen: dict,
                                  herkunft) -> int:
        """Einen Jahrgang Investitionsmaßnahmen ersetzen.

        Maßnahmen und beide Summenebenen zusammen, weil sie aus **einem**
        Dokument stammen und die Summen die Ziele der Rechenproben sind. Eine
        Herkunft für alles: Anders als beim Finanzhaushalt gibt es hier keine
        Zeile, die von den Proben nicht gedeckt wäre — was nicht aufgeht, kommt
        gar nicht erst herein (``investitionsprogramm.lies``).

        Übergeben wird nur, was die Proben bestanden hat; diese Methode prüft
        nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_investitionsmassnahmen WHERE jahr = ?",
                (jahr,))
            werte = []
            for nr, a in sorted(gelesen["abschnitte"].items()):
                for m in a["massnahmen"]:
                    werte.append((jahr, "massnahme", nr, m["code"],
                                  m["bezeichnung"], m["gesamtsumme"],
                                  " · ".join(m.get("details") or []) or None,
                                  now, hid))
                werte.append((jahr, "teilhaushalt", nr, "", a["name"],
                              a["summe"], None, now, hid))
            werte.append((jahr, "gesamt", 0, "", "Gesamtinvestitionsprogramm",
                          gelesen["kopfsumme"], None, now, hid))
            self._conn.executemany(
                "INSERT INTO council_investitionsmassnahmen "
                "(jahr, ebene, thh_nr, code, bezeichnung, gesamtsumme, "
                " details, fetched_at, herkunft_id) VALUES (?,?,?,?,?,?,?,?,?)",
                werte)
        return len(werte)

    def investitionsprogramm_jahre(self) -> list[int]:
        """Jahrgänge, für die ein Investitionsprogramm vorliegt (aufsteigend).

        Gezählt an der ``gesamt``-Zeile: Sie kommt nur in die Tabelle, wenn
        alle drei Proben aufgingen, und kennzeichnet damit einen vollständigen
        Jahrgang."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT jahr FROM council_investitionsmassnahmen "
                "WHERE ebene = 'gesamt' ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    def get_investitionsmassnahmen(self, jahr: int | None = None,
                                   thh_nr: int | None = None,
                                   ebene: str | None = None) -> list[dict]:
        """Zeilen des Investitionsprogramms — nach Jahr, Teilhaushalt, Ebene.

        Ohne ``ebene`` kommen alle drei mit. Sie sind beschriftet und dürfen
        nur so gezeigt werden: Wer die Maßnahmen addiert und das Ergebnis neben
        die ``teilhaushalt``-Zeile stellt, zeigt zweimal dieselbe Zahl."""
        wo, werte = [], []
        if jahr is not None:
            wo.append("jahr = ?")
            werte.append(jahr)
        if thh_nr is not None:
            wo.append("thh_nr = ?")
            werte.append(thh_nr)
        if ebene is not None:
            wo.append("ebene = ?")
            werte.append(ebene)
        satz = (" WHERE " + " AND ".join(wo)) if wo else ""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_investitionsmassnahmen" + satz
                + " ORDER BY jahr, thh_nr, ebene, code", werte)]
        except sqlite3.OperationalError:
            return []

    # --- Konzern Stadt Oldenburg (konsolidierter Gesamtabschluss) -----------

    def save_konzern_jahrgang(self, jahr: int, posten: list[dict],
                              traeger: list[dict], herkunft,
                              herkunft_traeger=None) -> dict:
        """Einen Jahrgang des Gesamtabschlusses ersetzen — beide Ebenen.

        Zusammen, weil sie aus **einem** Dokument stammen und ein halb
        geschriebener Jahrgang für den nächsten Lauf wie ein fertiger aussähe.
        Aber mit **zwei** Herkünften: Die Posten stehen in Abschnitt 3.2, die
        Trägeraufstellung in 4.1.1, und sie sind durch verschiedene Proben
        gedeckt. Fehlt ``herkunft_traeger``, gilt dieselbe für beide.

        Übergeben wird nur, was die Proben bestanden hat — diese Methode prüft
        nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            hid_traeger = (self.merke_herkunft(herkunft_traeger, fetched_at=now)
                           if herkunft_traeger is not None else hid)
            self._conn.execute("DELETE FROM council_konzern_posten WHERE jahr = ?", (jahr,))
            self._conn.execute("DELETE FROM council_konzern_traeger WHERE jahr = ?", (jahr,))
            self._conn.executemany(
                "INSERT INTO council_konzern_posten (jahr, nr, bezeichnung, rolle, "
                " betrag, vorjahr, ist_summe, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(jahr, p["nr"], p["bezeichnung"], p.get("rolle"), p["betrag"],
                  p.get("vorjahr"), 1 if p.get("ist_summe") else 0, now, hid)
                 for p in posten])
            self._conn.executemany(
                "INSERT INTO council_konzern_traeger (jahr, art, traeger_key, traeger, "
                " betrag_teur, vorjahr_teur, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?)",
                [(jahr, t["art"], t["traeger_key"], t["traeger"], t["betrag_teur"],
                  t.get("vorjahr_teur"), now, hid_traeger) for t in traeger])
        return {"posten": len(posten), "traeger": len(traeger)}

    def konzern_jahre(self) -> list[int]:
        """Jahrgänge mit eingelesenem Gesamtabschluss (aufsteigend)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT jahr FROM council_konzern_posten ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    def get_konzern_posten(self, jahr: int | None = None) -> list[dict]:
        """Posten der Gesamtergebnisrechnung — ein Jahrgang oder alle."""
        try:
            if jahr is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_konzern_posten ORDER BY jahr, nr").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_konzern_posten WHERE jahr = ? ORDER BY nr",
                    (jahr,)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def kernverwaltung_ist(self) -> dict[int, dict]:
        """Ist-Summen der Kernverwaltung je Jahr, aus den Jahresabschlüssen.

        Nur die beiden Summenzeilen, und bewusst über die **Bezeichnung**
        gesucht statt über die Postennummer: Diese Tabelle wird sonst nirgends
        nach Nummern gefragt, und eine Nummer, die niemand nachprüft, ist
        genau die, die beim nächsten Formatwechsel still etwas anderes meint.

        Zweck ist die Gegenprobe: Der Gesamtabschluss führt die Kernverwaltung
        als eigene Trägerzeile. Beide Zahlen stammen aus verschiedenen
        Dokumenten verschiedener Jahre — dass sie übereinstimmen, ist die
        stärkste Bestätigung, die dieser Bestand hergibt."""
        try:
            rows = self._conn.execute(
                "SELECT jahr, bezeichnung, ergebnis FROM council_ergebnisrechnung "
                "WHERE thh_nr IS NULL AND ergebnis IS NOT NULL "
                "  AND bezeichnung LIKE 'Summe ordentliche%' ORDER BY jahr").fetchall()
        except sqlite3.OperationalError:
            return {}
        aus: dict[int, dict] = {}
        for r in rows:
            art = "ertraege" if "Erträge" in r["bezeichnung"] else "aufwendungen"
            aus.setdefault(r["jahr"], {})[art] = r["ergebnis"]
        return aus

    # --- Beteiligungsbericht (§ 151 NKomVG) ---------------------------------

    def save_beteiligungsbericht(self, stammdaten: list[dict], texte: list[dict],
                                 kennzahlen: list[dict],
                                 personen: list[dict] | None = None,
                                 eigentuemer: list[dict] | None = None) -> dict:
        """Den **ganzen** Bestand des Beteiligungsberichts ersetzen.

        Ungewöhnlich für diesen Store, und mit Grund: Die Überlappungsprobe
        spannt sich über mehrere Berichte. Ob der Wert für 2022 gilt,
        entscheidet nicht der Bericht 2022 allein, sondern sein Vergleich mit
        2023 und 2024 — und `berichte` (in wie vielen er steht) ändert sich,
        sobald ein neuer Jahrgang dazukommt. Jahrgangsweise zu schreiben
        hieße, diese Zahl in jeder zweiten Zeile veralten zu lassen.

        Das Einlesen liest deshalb immer alle vorhandenen Berichte und
        übergibt das Ergebnis in einem Stück. Übergeben wird nur, was die
        Proben bestanden hat — diese Methode prüft nichts nach, sie schreibt.

        Jede Liste bringt ihre eigene ``herkunft`` je Zeile mit: Die Kennzahlen
        eines Jahres stammen aus einem anderen Bericht als die Texte daneben,
        und die Probe ist eine andere."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            for tabelle in ("council_gesellschaft_kennzahlen",
                            "council_gesellschaft_texte",
                            "council_gesellschaft_personen",
                            "council_gesellschaft_eigentuemer",
                            "council_gesellschaften"):
                self._conn.execute(f"DELETE FROM {tabelle}")
            for z in stammdaten:
                self._conn.execute(
                    "INSERT INTO council_gesellschaften (bericht_jahr, gesellschaft, "
                    " name, gliederung, seite, konzern_key, fetched_at, herkunft_id) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (z["bericht_jahr"], z["gesellschaft"], z["name"], z["gliederung"],
                     z.get("seite"), z.get("konzern_key"), now,
                     self.merke_herkunft(z["herkunft"], fetched_at=now)))
            for z in texte:
                self._conn.execute(
                    "INSERT INTO council_gesellschaft_texte (bericht_jahr, "
                    " gesellschaft, abschnitt, text, fetched_at, herkunft_id) "
                    "VALUES (?,?,?,?,?,?)",
                    (z["bericht_jahr"], z["gesellschaft"], z["abschnitt"], z["text"],
                     now, self.merke_herkunft(z["herkunft"], fetched_at=now)))
            for z in kennzahlen:
                self._conn.execute(
                    "INSERT INTO council_gesellschaft_kennzahlen (gesellschaft, "
                    " kennzahl, jahr, wert, einheit, bericht_jahr, berichte, "
                    " fetched_at, herkunft_id) VALUES (?,?,?,?,?,?,?,?,?)",
                    (z["gesellschaft"], z["kennzahl"], z["jahr"], z["wert"],
                     z["einheit"], z["bericht_jahr"], z["berichte"], now,
                     self.merke_herkunft(z["herkunft"], fetched_at=now)))
            for z in personen or []:
                self._conn.execute(
                    "INSERT INTO council_gesellschaft_personen (bericht_jahr, "
                    " gesellschaft, reihenfolge, gremium, name, funktion, "
                    " vorsitz, hinweis, funktionen_zuordenbar, fetched_at, "
                    " herkunft_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (z["bericht_jahr"], z["gesellschaft"], z["reihenfolge"],
                     z["gremium"], z["name"], z.get("funktion"), z.get("vorsitz"),
                     z.get("hinweis"), int(bool(z["funktionen_zuordenbar"])), now,
                     self.merke_herkunft(z["herkunft"], fetched_at=now)))
            for z in eigentuemer or []:
                self._conn.execute(
                    "INSERT INTO council_gesellschaft_eigentuemer (bericht_jahr, "
                    " gesellschaft, reihenfolge, name, betrag_eur, "
                    " anteil_prozent, fetched_at, herkunft_id) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (z["bericht_jahr"], z["gesellschaft"], z["reihenfolge"],
                     z["name"], z.get("betrag_eur"), z.get("anteil_prozent"), now,
                     self.merke_herkunft(z["herkunft"], fetched_at=now)))
        return {"gesellschaften": len(stammdaten), "texte": len(texte),
                "kennzahlen": len(kennzahlen), "personen": len(personen or []),
                "eigentuemer": len(eigentuemer or [])}

    def beteiligungsbericht_jahre(self) -> list[int]:
        """Berichtsjahrgänge, die eingelesen sind (aufsteigend)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT bericht_jahr FROM council_gesellschaften "
                "ORDER BY bericht_jahr")]
        except sqlite3.OperationalError:
            return []

    def get_gesellschaften(self, bericht_jahr: int | None = None) -> list[dict]:
        """Die Gesellschaften eines Berichts — ohne Angabe die des jüngsten.

        „Der jüngste" ist hier die richtige Vorgabe und nicht Bequemlichkeit:
        Die Frage „was macht die GSG?" meint den heutigen Stand, und ein
        Bericht von 2022 nennt Aufsichtsräte, die längst ausgewechselt sind."""
        try:
            if bericht_jahr is None:
                jahre = self.beteiligungsbericht_jahre()
                if not jahre:
                    return []
                bericht_jahr = jahre[-1]
            rows = self._conn.execute(
                "SELECT * FROM council_gesellschaften WHERE bericht_jahr = ? "
                "ORDER BY gliederung", (bericht_jahr,)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def get_gesellschaft_texte(self, gesellschaft: str,
                               bericht_jahr: int | None = None) -> list[dict]:
        """Die beschreibenden Abschnitte einer Gesellschaft."""
        try:
            if bericht_jahr is None:
                jahre = self.beteiligungsbericht_jahre()
                if not jahre:
                    return []
                bericht_jahr = jahre[-1]
            rows = self._conn.execute(
                "SELECT * FROM council_gesellschaft_texte WHERE gesellschaft = ? "
                "AND bericht_jahr = ?", (gesellschaft, bericht_jahr)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def _gesellschaft_zeilen(self, tabelle: str, bericht_jahr: int | None,
                             ordnung: str) -> list[dict]:
        """Alle Zeilen einer Beteiligungs-Tabelle für **einen** Berichtsjahrgang.

        Ohne Jahresangabe der jüngste — dieselbe Vorgabe wie bei
        ``get_gesellschaften``, und aus demselben Grund: Wer fragt, wer im
        Aufsichtsrat sitzt, meint heute und nicht 2022.

        Ein Lesepfad für beide Tabellen, weil die Steckbrief-Seite ohnehin
        alle Gesellschaften auf einmal zeigt: 45 Einzelabfragen für 500 Zeilen
        wären eine Schleife um nichts."""
        try:
            if bericht_jahr is None:
                jahre = self.beteiligungsbericht_jahre()
                if not jahre:
                    return []
                bericht_jahr = jahre[-1]
            rows = self._conn.execute(
                f"SELECT * FROM {tabelle} WHERE bericht_jahr = ? "
                f"ORDER BY {ordnung}", (bericht_jahr,)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def get_gesellschaft_personen(self, bericht_jahr: int | None = None) -> list[dict]:
        """Die Aufsichtsorgane eines Berichtsjahrgangs, Person für Person.

        ``funktionen_zuordenbar`` gilt je Gesellschaft: Ist es 0, ist
        ``funktion`` bei **allen** ihren Personen NULL (s. Tabellenkommentar
        und ``beteiligungsbericht.aufsichtsorgane``)."""
        return self._gesellschaft_zeilen("council_gesellschaft_personen",
                                         bericht_jahr, "gesellschaft, reihenfolge")

    def get_gesellschaft_eigentuemer(self, bericht_jahr: int | None = None) -> list[dict]:
        """Wem die Gesellschaften gehören — ohne die Stammkapital-Summenzeile."""
        return self._gesellschaft_zeilen("council_gesellschaft_eigentuemer",
                                         bericht_jahr, "gesellschaft, reihenfolge")

    def get_gesellschaft_kennzahlen(self, gesellschaft: str | None = None) -> list[dict]:
        """Die Kennzahlen-Zeitreihe — einer Gesellschaft oder aller."""
        try:
            if gesellschaft is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_gesellschaft_kennzahlen "
                    "ORDER BY gesellschaft, kennzahl, jahr").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_gesellschaft_kennzahlen "
                    "WHERE gesellschaft = ? ORDER BY kennzahl, jahr",
                    (gesellschaft,)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def get_konzern_traeger(self, jahr: int | None = None) -> list[dict]:
        """Trägeraufstellung — wer wie viel zum Konzern beiträgt, in TEUR."""
        try:
            if jahr is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_konzern_traeger ORDER BY jahr, art, "
                    "betrag_teur DESC").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_konzern_traeger WHERE jahr = ? "
                    "ORDER BY art, betrag_teur DESC", (jahr,)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    # --- Schuldenstand (Tabelle 1108 des Statistischen Jahrbuchs) ------------

    def save_schulden(self, zeilen: list[dict], herkunft) -> int:
        """Schuldenjahrgänge ersetzen — je Jahr eine Zeile.

        Ersetzt wird **nur, was die Lieferung mitbringt**, nicht die ganze
        Tabelle: Ein Lauf, dem ein Jahrgang an der Probe durchgefallen ist,
        darf den vorher gespeicherten Stand dieses Jahrgangs nicht mit
        wegräumen. Wer wirklich aufräumen will, tut das von Hand.

        Übergeben wird nur, was seine Probe bestanden hat — diese Methode
        prüft nichts nach, sie schreibt. Was die Aufteilung verloren hat
        (Fall 2022, s. ``council/schulden.py``), kommt hier mit ``None`` in
        den vier Artenspalten an und bleibt auch so stehen."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_schulden "
                "(jahr, kreditmarkt, sondermittel, gebietskoerperschaften, "
                " eigenbetriebe, insgesamt, je_einwohner, aufteilung_verworfen, "
                " revidiert, herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [(z["jahr"], z.get("kreditmarkt"), z.get("sondermittel"),
                  z.get("gebietskoerperschaften"), z.get("eigenbetriebe"),
                  z["insgesamt"], z.get("je_einwohner"),
                  z.get("aufteilung_verworfen"), int(bool(z.get("revidiert"))),
                  hid, now) for z in zeilen])
        return len(zeilen)

    def get_schulden(self) -> list[dict]:
        """Die Schuldenzeitreihe, aufsteigend nach Jahr.

        Fehlt die Tabelle (frische Datenbank ohne Ingest-Lauf), ist die Antwort
        leer statt ein Fehler — der Haushalts-Bereich zeigt die Seite dann ohne
        Zeitreihe."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM council_schulden ORDER BY jahr").fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    # --- Lange Ausgabenreihe (Datensatz 1102, seit 1972) --------------------

    def save_ausgabenreihe(self, zeilen: list[dict], herkunft) -> int:
        """Jahrgänge der langen Ausgabenreihe ersetzen — je Jahr eine Zeile.

        Ersetzt wird **nur, was die Lieferung mitbringt**, nicht die ganze
        Tabelle: Ein Lauf, dem ein Jahrgang an einer Probe durchgefallen ist,
        darf den vorher gespeicherten Stand dieses Jahrgangs nicht mit
        wegräumen (dieselbe Regel wie bei ``save_schulden``).

        Übergeben wird nur, was seine Proben bestanden hat — diese Methode
        prüft nichts nach, sie schreibt. Welche Proben das waren, kommt als
        Liste in ``proben`` an und wird kommagetrennt gespeichert; die Namen
        stehen in ``council/herkunft.PROBEN``.

        Aufgerufen wird sie einmal je Herkunfts-Gruppe, nicht einmal für die
        ganze Reihe: Ein Jahrgang von 1974 steht nur im Open-Data-Portal, einer
        von 2024 zusätzlich im Jahrbuch und im Jahresabschluss — das sind
        verschiedene Belege, und jeder soll für seine Zeilen gelten."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_ausgabenreihe "
                "(jahr, regelwerk, betrag, quelle, proben, konflikt_betrag, "
                " konflikt_quelle, revidiert, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(z["jahr"], z["regelwerk"], z["betrag"], z["quelle"],
                  ",".join(z.get("proben") or []), z.get("konflikt_betrag"),
                  z.get("konflikt_quelle"), int(bool(z.get("revidiert"))),
                  hid, now) for z in zeilen])
        return len(zeilen)

    def get_ausgabenreihe(self) -> list[dict]:
        """Die lange Ausgabenreihe, aufsteigend nach Jahr.

        ``proben`` kommt als Liste heraus, nicht als gespeicherter String —
        das Frontend soll die Trennzeichen-Konvention nicht kennen müssen.
        Fehlt die Tabelle (frische Datenbank ohne Ingest-Lauf), ist die Antwort
        leer statt ein Fehler."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_ausgabenreihe ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []
        for r in rows:
            r["proben"] = [p for p in (r.get("proben") or "").split(",") if p]
        return rows

    # --- Bürgschaften: wofür die Stadt geradesteht --------------------------

    def save_wirtschaftsplan(self, plan, herkunft) -> int:
        """Einen Wirtschaftsplan speichern — ein Betrieb, ein Haushaltsjahr.

        Aufgerufen wird sie **je Plan** und nicht für eine ganze Lieferung:
        Jeder Jahrgang steht in seiner eigenen Ratsvorlage, also hat jeder
        seine eigene Herkunft. Ein gemeinsamer Beleg wäre für sieben von acht
        Zeilen der falsche — dieselbe Überlegung wie bei
        ``save_buergschaften``.

        ``plan`` ist ein :class:`council.wirtschaftsplan.Wirtschaftsplan`; die
        Proben stehen dort und werden nicht hier noch einmal gerechnet.
        """
        # Die Proben kommen aus der HERKUNFT und stehen nicht hier: Welche
        # gelaufen sind, weiß der Parser, und es sind je nach Quelle andere —
        # der Beschlusstext prüft anders als der Erfolgsplan einer Anlage. Eine
        # feste Liste an dieser Stelle behauptete für jede Zeile dieselben.
        proben = herkunft.probe
        if not isinstance(proben, str):
            proben = ",".join(proben)

        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_wirtschaftsplaene "
                "(betrieb, jahr, betrieb_name, template_number, ertraege, aufwendungen, "
                " steuern, ergebnis, vermoegensplan, investitionen, verpflichtungen, "
                " entwurf_vom, proben, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (plan.betrieb, plan.jahr, plan.betrieb_name, plan.template_number,
                 plan.ertraege, plan.aufwendungen, plan.steuern, plan.ergebnis,
                 plan.vermoegensplan, plan.investitionen, plan.verpflichtungen,
                 plan.entwurf_vom, proben, hid, now))
        return 1

    def save_gebuehrenbedarf(self, bedarf, herkunft) -> int:
        """Einen Gebührenbereich eines Jahrgangs speichern.

        Je Bereich und Jahr eine Zeile, und je Zeile eine eigene Herkunft: Die
        drei Bereiche stehen in drei Anlagen und prüfen sich einzeln — ein
        gemeinsamer Beleg wäre für zwei von drei der falsche.
        """
        proben = herkunft.probe
        if not isinstance(proben, str):
            proben = ",".join(proben)

        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_gebuehren "
                "(jahr, bereich, bereich_name, kostenkalkulation, abzuege, "
                " zu_deckende_kosten, bezugsmenge, bezugseinheit, gebuehr, "
                " gebuehrenvorschlag, template_number, proben, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (bedarf.jahr, bedarf.bereich, bedarf.bereich_name,
                 bedarf.kostenkalkulation, bedarf.abzuege,
                 bedarf.zu_deckende_kosten, bedarf.bezugsmenge,
                 bedarf.bezugseinheit, bedarf.gebuehr,
                 bedarf.gebuehrenvorschlag, bedarf.template_number,
                 proben, hid, now))
        return 1

    def get_gebuehren(self) -> list[dict]:
        """Alle Gebührenbereiche, ältester Jahrgang zuerst."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_gebuehren ORDER BY jahr, bereich")]
        except sqlite3.OperationalError:
            return []

    def save_gebuehrensaetze(self, saetze, herkuenfte) -> int:
        """Die vollständigen zwölf Tarife eines Vorschlagsjahres ersetzen."""
        saetze, herkuenfte = list(saetze), list(herkuenfte)
        if len(saetze) != len(herkuenfte):
            raise ValueError("Jeder Gebührensatz braucht genau eine Herkunft")
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            for satz, herkunft in zip(saetze, herkuenfte, strict=True):
                proben = herkunft.probe
                if not isinstance(proben, str):
                    proben = ",".join(proben)
                hid = self.merke_herkunft(herkunft, fetched_at=now)
                self._conn.execute(
                    "INSERT OR REPLACE INTO council_gebuehrensaetze "
                    "(jahr, schluessel, bereich, bezeichnung, betrag, einheit, "
                    " vorjahr, veraenderung_prozent, template_number, proben, "
                    " herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (satz.jahr, satz.schluessel, satz.bereich, satz.bezeichnung,
                     satz.betrag, satz.einheit, satz.vorjahr,
                     satz.veraenderung_prozent, satz.template_number, proben, hid, now))
        return len(saetze)

    def get_gebuehrensaetze(self) -> list[dict]:
        """Alle konkreten Tarife, jüngster Vorschlag zuerst."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_gebuehrensaetze "
                "ORDER BY jahr DESC, bereich, schluessel")]
        except sqlite3.OperationalError:
            return []

    def gebuehren_jahre(self) -> list[int]:
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT jahr FROM council_gebuehren ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    def save_haushalt_aenderungen(self, dokument_id: int, liste: str,
                                  ergebnis, herkunft) -> int:
        """Eine geprüfte Änderungsliste speichern — Positionen und Summen.

        Ersetzt wird je ``(jahrgang, liste)``: Ein Jahrgang hat genau ein
        Verw.-I-Dokument usw. Ob zwei ANLAGEN dasselbe Dokument sind (die
        2021er-Beschlussdatei liegt doppelt im Bestand), entscheidet der
        Ingest VOR dem Speichern — diese Methode prüft nichts nach, sie
        schreibt, was seine Proben bestanden hat (council/aenderungslisten.py).
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        jahrgang = ergebnis.jahrgang
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            for tabelle in ("council_haushalt_aenderungen",
                            "council_haushalt_aenderungen_summen"):
                self._conn.execute(
                    f"DELETE FROM {tabelle} WHERE jahrgang = ? AND liste = ?",
                    (jahrgang, liste))
            self._conn.executemany(
                "INSERT INTO council_haushalt_aenderungen (jahrgang, liste, "
                " jahr, lfd, thh, seite_entwurf, produkt, bezeichnung, "
                " ertrag, aufwand, erlaeuterung, urheber, dokument_id, "
                " herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(jahrgang, liste, z.jahr, z.lfd, z.thh, z.seite_entwurf,
                  z.produkt, z.bezeichnung, z.ertrag, z.aufwand,
                  z.erlaeuterung, z.urheber, dokument_id, hid, now)
                 for z in ergebnis.zeilen])
            self._conn.executemany(
                "INSERT INTO council_haushalt_aenderungen_summen (jahrgang, "
                " liste, jahr, typ, label, ertraege, aufwendungen, saldo, "
                " eigene, dokument_id, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                [(jahrgang, liste, s.jahr, s.typ, s.label, s.ertraege,
                  s.aufwendungen, s.saldo,
                  1 if ergebnis.eigene_zeile.get(s.jahr) == s.label else 0,
                  dokument_id, hid, now) for s in ergebnis.summen])
        return len(ergebnis.zeilen)

    def save_haushalt_aenderungen_fhh(self, dokument_id: int, liste: str,
                                      ergebnis, herkunft) -> int:
        """Eine FHH-Änderungsliste speichern — Positionen und Zusammenstellung.

        Wie beim Ergebnishaushalt: Die Proben liefen im Parser
        (council/aenderungslisten_fhh.py), hier wird nur geschrieben. Je
        (Jahrgang, Liste) wird gelöscht und neu geschrieben, ein zweiter Lauf
        ersetzt den Stand also gefahrlos.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        jahrgang = ergebnis.jahrgang
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            for tabelle in ("council_haushalt_aenderungen_fhh",
                            "council_haushalt_aenderungen_fhh_summen"):
                self._conn.execute(
                    f"DELETE FROM {tabelle} WHERE jahrgang = ? AND liste = ?",
                    (jahrgang, liste))
            self._conn.executemany(
                "INSERT INTO council_haushalt_aenderungen_fhh (jahrgang, "
                " liste, jahr, lfd, thh, seite_entwurf, produkt, bezeichnung, "
                " soll_entwurf, einzahlung, auszahlung, ve, soll_neu, "
                " erlaeuterung, urheber, dokument_id, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(jahrgang, liste, z.jahr, z.lfd, z.thh, z.seite_entwurf,
                  z.produkt, z.bezeichnung, z.soll_entwurf, z.einzahlung,
                  z.auszahlung, z.ve, z.soll_neu, z.erlaeuterung, z.urheber,
                  dokument_id, hid, now) for z in ergebnis.zeilen])
            self._conn.executemany(
                "INSERT INTO council_haushalt_aenderungen_fhh_summen (jahrgang, "
                " liste, jahr, typ, label, einzahlungen, auszahlungen, saldo, "
                " ve, eigene, dokument_id, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(jahrgang, liste, s.jahr, s.typ, s.label, s.einzahlungen,
                  s.auszahlungen, s.saldo, s.ve,
                  1 if ergebnis.eigene_zeile.get(s.jahr) == s.label else 0,
                  dokument_id, hid, now) for s in ergebnis.summen])
        return len(ergebnis.zeilen)

    def get_haushalt_aenderungen_fhh(self, jahrgang: int | None = None) -> dict:
        """Positionen und Summen der FHH-Änderungslisten, älteste zuerst.

        Fehlen die Tabellen (frische Datenbank ohne Ingest-Lauf), ist die
        Antwort leer statt ein Fehler — dieselbe Auskunft wie beim EHH."""
        wo, args = ("WHERE jahrgang = ?", (jahrgang,)) if jahrgang else ("", ())
        try:
            zeilen = [dict(r) for r in self._conn.execute(
                "SELECT jahrgang, liste, jahr, lfd, thh, seite_entwurf, produkt, "
                " bezeichnung, soll_entwurf, einzahlung, auszahlung, ve, "
                " soll_neu, erlaeuterung, urheber, dokument_id, herkunft_id "
                f"FROM council_haushalt_aenderungen_fhh {wo} "
                "ORDER BY jahrgang, liste, jahr, lfd", args)]
            summen = [dict(r) for r in self._conn.execute(
                "SELECT jahrgang, liste, jahr, typ, label, einzahlungen, "
                " auszahlungen, saldo, ve, eigene, dokument_id, herkunft_id "
                f"FROM council_haushalt_aenderungen_fhh_summen {wo} "
                "ORDER BY jahrgang, liste, jahr", args)]
        except sqlite3.OperationalError:
            return {"zeilen": [], "summen": []}
        return {"zeilen": zeilen, "summen": summen}

    def get_haushalt_aenderungen(self, jahrgang: int | None = None) -> dict:
        """Positionen und Summen der Änderungslisten, älteste zuerst.

        Fehlen die Tabellen (frische Datenbank ohne Ingest-Lauf), ist die
        Antwort leer statt ein Fehler — dieselbe Auskunft wie bei den
        Nachbar-Schichten."""
        wo, args = ("WHERE jahrgang = ?", (jahrgang,)) if jahrgang else ("", ())
        try:
            zeilen = [dict(r) for r in self._conn.execute(
                "SELECT jahrgang, liste, jahr, lfd, thh, seite_entwurf, "
                " produkt, bezeichnung, ertrag, aufwand, erlaeuterung, "
                " urheber, dokument_id, herkunft_id FROM council_haushalt_aenderungen "
                f"{wo} ORDER BY jahrgang, liste, jahr, lfd", args)]
            summen = [dict(r) for r in self._conn.execute(
                "SELECT jahrgang, liste, jahr, typ, label, ertraege, "
                " aufwendungen, saldo, eigene, dokument_id, herkunft_id "
                "FROM council_haushalt_aenderungen_summen "
                f"{wo} ORDER BY jahrgang, liste, jahr", args)]
        except sqlite3.OperationalError:
            return {"zeilen": [], "summen": []}
        return {"zeilen": zeilen, "summen": summen}

    def save_haushaltssatzung(self, satzung, herkunft) -> int:
        """Eine Haushaltssatzung speichern — ein Jahrgang, eine Fassung.

        Wie bei den Wirtschaftsplänen kommen die Proben aus der HERKUNFT und
        werden hier nicht noch einmal behauptet: Ob der Hebesatz gegen das
        Statistische Jahrbuch geprüft werden konnte, hängt daran, ob dessen
        Tabelle diesen Jahrgang schon trägt — der Parser weiß das, der Store
        nicht.
        """
        proben = herkunft.probe
        if not isinstance(proben, str):
            proben = ",".join(proben)

        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_haushaltssatzung "
                "(jahr, nachtrag, fassung, ordentliche_ertraege, "
                " ordentliche_aufwendungen, ao_ertraege, ao_aufwendungen, "
                " ein_laufend, aus_laufend, ein_invest, aus_invest, "
                " ein_finanz, aus_finanz, ein_gesamt, aus_gesamt, "
                " kredite_investitionen, verpflichtungsermaechtigungen, "
                " liquiditaetskredite, hebesatz_grundsteuer_a, "
                " hebesatz_grundsteuer_b, hebesatz_gewerbesteuer, sitzung_am, "
                " template_number, proben, herkunft_id, fetched_at) "
                "VALUES (" + ",".join("?" * 26) + ")",
                (satzung.jahr, satzung.nachtrag, satzung.fassung,
                 satzung.ordentliche_ertraege, satzung.ordentliche_aufwendungen,
                 satzung.ao_ertraege, satzung.ao_aufwendungen,
                 satzung.ein_laufend, satzung.aus_laufend,
                 satzung.ein_invest, satzung.aus_invest,
                 satzung.ein_finanz, satzung.aus_finanz,
                 satzung.ein_gesamt, satzung.aus_gesamt,
                 satzung.kredite_investitionen,
                 satzung.verpflichtungsermaechtigungen,
                 satzung.liquiditaetskredite,
                 satzung.hebesatz_grundsteuer_a, satzung.hebesatz_grundsteuer_b,
                 satzung.hebesatz_gewerbesteuer, satzung.sitzung_am,
                 satzung.template_number, proben, hid, now))
        return 1

    def get_haushaltssatzungen(self) -> list[dict]:
        """Alle Satzungs-Jahrgänge, ältester zuerst."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_haushaltssatzung ORDER BY jahr, nachtrag")]
        except sqlite3.OperationalError:
            return []

    def haushaltssatzung_jahre(self) -> list[int]:
        """Jahrgänge, für die eine Satzung vorliegt."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT jahr FROM council_haushaltssatzung ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    def get_wirtschaftsplaene(self, betrieb: str | None = None) -> list[dict]:
        """Die Wirtschaftspläne, ältester zuerst — je Betrieb oder alle."""
        try:
            if betrieb is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_wirtschaftsplaene ORDER BY betrieb, jahr")
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_wirtschaftsplaene WHERE betrieb = ? "
                    "ORDER BY jahr", (betrieb,))
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []

    def wirtschaftsplan_jahre(self, betrieb: str) -> list[int]:
        """Haushaltsjahre, für die ein Plan dieses Betriebs vorliegt."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT jahr FROM council_wirtschaftsplaene WHERE betrieb = ? "
                "ORDER BY jahr", (betrieb,))]
        except sqlite3.OperationalError:
            return []

    def save_buergschaften(self, zeilen: list[dict], herkunft) -> int:
        """Bürgschafts-Jahrgänge ersetzen — je Jahr eine Zeile.

        Wie bei ``save_ausgabenreihe`` wird nur ersetzt, was die Lieferung
        mitbringt: Ein Lauf, dem ein Jahrgang durchgefallen ist, räumt den
        vorher gespeicherten Stand dieses Jahrgangs nicht mit weg.

        Aufgerufen wird sie **je Herkunfts-Gruppe**, nicht einmal für die
        ganze Reihe — jeder Jahrgang steht in seinem eigenen Jahresabschluss,
        und 2021 steht sogar in dem des Folgejahres. Ein gemeinsamer Beleg
        wäre für fünf von sechs Zeilen der falsche."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_buergschaften "
                "(jahr, bestand, genau, aus_folgejahr, quelle, grund, "
                " einzelbetrag, proben, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(z["jahr"], z["bestand"], int(bool(z.get("genau"))),
                  int(bool(z.get("aus_folgejahr"))), z["quelle"], z.get("grund"),
                  z.get("einzelbetrag"), ",".join(z.get("proben") or []),
                  hid, now) for z in zeilen])
        return len(zeilen)

    def save_kennzahlen(self, bericht_jahr: int, zeilen: list[dict],
                        formeln: list[dict], herkunft) -> int:
        """Einen Rechenschaftsbericht ersetzen — Werte und Rechenwege zusammen.

        Ersetzt wird genau **dieser Bericht**, nicht die Jahrgänge, die er
        zeigt. Der Bericht 2024 druckt 2020–2024; wer nach Datenjahr löschte,
        risse dem Bericht 2021 vier seiner fünf Spalten heraus — und mit ihnen
        die Vergleichsstände, aus denen die Korrekturen sichtbar werden.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_kennzahlen WHERE bericht_jahr = ?",
                               (bericht_jahr,))
            self._conn.execute("DELETE FROM council_kennzahl_formeln WHERE bericht_jahr = ?",
                               (bericht_jahr,))
            self._conn.executemany(
                "INSERT INTO council_kennzahlen "
                "(bericht_jahr, kennzahl, jahr, label, wert, einheit, stellen, "
                " fassung, herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(bericht_jahr, z["kennzahl"], z["jahr"], z["label"], z["wert"],
                  z["einheit"], z["stellen"], z.get("fassung"), hid, now)
                 for z in zeilen])
            self._conn.executemany(
                "INSERT INTO council_kennzahl_formeln "
                "(bericht_jahr, kennzahl, fassung, ueberschrift, formel, "
                " herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?)",
                [(bericht_jahr, f["kennzahl"], f.get("fassung") or 1,
                  f["ueberschrift"], f["formel"], hid, now) for f in formeln])
        return len(zeilen)

    def get_kennzahlen(self) -> list[dict]:
        """Alle Stände aller Berichte — die Belegkette, nicht die Anzeigereihe.

        Wer die Reihe will, nimmt ``council.kennzahlen.neueste``; wer die
        Korrekturen zeigen will, braucht alle Stände.
        """
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_kennzahlen ORDER BY kennzahl, jahr, bericht_jahr")]
        except sqlite3.OperationalError:
            return []

    def get_kennzahl_formeln(self) -> list[dict]:
        """Die gedruckten Rechenwege, ältester Bericht zuerst."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_kennzahl_formeln ORDER BY kennzahl, bericht_jahr")]
        except sqlite3.OperationalError:
            return []

    def save_anlagenspiegel(self, jahr: int, zeilen: list[dict], herkunft) -> int:
        """Den Anlagenspiegel eines Jahrgangs ersetzen.

        Je Jahrgang ein Aufruf mit einem Beleg: Die Tabelle steht in genau
        einem Dokument, anders als bei den Bürgschaften, wo ein Jahrgang im
        Abschluss des Folgejahres stehen kann.

        Ersetzt wird nur DIESER Jahrgang — ein Lauf, dem ein anderer
        durchgefallen ist, räumt dessen Stand nicht mit weg.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_anlagenspiegel WHERE jahr = ?", (jahr,))
            self._conn.executemany(
                "INSERT INTO council_anlagenspiegel "
                "(jahr, nr, bezeichnung, spalten, ahk_anfang, zugaenge, abgaenge, "
                " umbuchungen, ahk_ende, abschr_anfang, abschreibung, aufloesungen, "
                " zuschreibungen, abschr_umbuchungen, abschr_ende, buchwert, "
                " buchwert_vorjahr, proben, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(jahr, z["nr"], z["bezeichnung"], z["spalten"],
                  z["ahk_anfang"], z["zugaenge"], z["abgaenge"], z["umbuchungen"],
                  z["ahk_ende"], z["abschr_anfang"], z["abschreibung"],
                  z["aufloesungen"], z["zuschreibungen"], z["abschr_umbuchungen"],
                  z["abschr_ende"], z["buchwert"], z["buchwert_vorjahr"],
                  ",".join(z.get("proben") or []), hid, now) for z in zeilen])
        return len(zeilen)

    def get_anlagenspiegel(self) -> list[dict]:
        """Alle Zeilen, nach Jahr und Gliederung. ``proben`` als Liste."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_anlagenspiegel ORDER BY jahr, nr")]
        except sqlite3.OperationalError:
            return []
        for r in rows:
            r["proben"] = [p for p in (r.get("proben") or "").split(",") if p]
        return rows

    def save_vermoegensgruppen(self, jahr: int, gruppen: list[dict], herkunft) -> int:
        """Die Untergliederung des Infrastrukturvermögens eines Jahrgangs."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_vermoegensgruppen WHERE jahr = ?", (jahr,))
            self._conn.executemany(
                "INSERT INTO council_vermoegensgruppen "
                "(jahr, gruppe, buchwert, buchwert_vorjahr, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?)",
                [(jahr, g["gruppe"], g["buchwert"], g.get("buchwert_vorjahr"), hid, now)
                 for g in gruppen])
        return len(gruppen)

    def get_vermoegensgruppen(self) -> list[dict]:
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_vermoegensgruppen ORDER BY jahr, gruppe")]
        except sqlite3.OperationalError:
            return []

    def get_buergschaften(self) -> list[dict]:
        """Der Bürgschaftsbestand je Jahr, aufsteigend.

        ``genau`` und ``aus_folgejahr`` kommen als Wahrheitswerte heraus, nicht
        als 0/1: Sie sind Angaben über die Belegqualität und werden im Frontend
        als solche gelesen, nicht gerechnet."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_buergschaften ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []
        for r in rows:
            r["proben"] = [p for p in (r.get("proben") or "").split(",") if p]
            r["genau"] = bool(r["genau"])
            r["aus_folgejahr"] = bool(r["aus_folgejahr"])
        return rows

    def save_integrierte_schulden(self, zeile: dict, herkunft) -> int:
        """Einen Stichtag der integrierten Schulden ersetzen."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_integrierte_schulden "
                "(jahr, ars, bevoelkerung, insgesamt, je_einwohner, kernhaushalt, "
                " extrahaushalte, sonstige, extra_unter_50, sonstige_unter_50, "
                " veraenderung, proben, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (zeile["jahr"], zeile["ars"], zeile.get("bevoelkerung"),
                 zeile["insgesamt"], zeile.get("je_einwohner"),
                 zeile.get("kernhaushalt"), zeile.get("extrahaushalte"),
                 zeile.get("sonstige"), zeile.get("extra_unter_50"),
                 zeile.get("sonstige_unter_50"), zeile.get("insgesamt_veraenderung"),
                 ",".join(zeile.get("proben") or []), hid, now))
        return 1

    def get_integrierte_schulden(self) -> list[dict]:
        """Die integrierten Schulden je Stichtag, aufsteigend.

        Kommt als Liste, obwohl die Anzeige nur den jüngsten Stichtag zeigt:
        Eine zweite Ausgabe soll die erste nicht stillschweigend ersetzen —
        wer sie vergleichen will, sieht wenigstens, dass es zwei gibt (und
        findet in ``council/integrierte_schulden.KEINE_REIHE``, warum er es
        besser lässt)."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_integrierte_schulden ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []
        for r in rows:
            r["proben"] = [p for p in (r.get("proben") or "").split(",") if p]
        return rows

    # --- Nachbewilligungen nach § 117 NKomVG --------------------------------

    def anlage_text(self, document_id: int) -> str | None:
        """Der Volltext einer Anlage — oder ``None``, wenn keiner da ist.

        „Kein Text" ist der Normalfall und kein Fehler: Der Bestand führt
        Anlagen, die noch nie geladen wurden (``scripts/backfill_anlagen_texte
        .py``), und solche, die als Scan gar keinen Text hergeben. Beide
        sollen den Aufrufer nicht in einen Fehlerpfad zwingen, sondern in die
        Meldung „für dieses Jahr liegt die Quelle nicht vor"."""
        try:
            row = self._conn.execute(
                "SELECT raw_text FROM council_anlagen WHERE document_id = ?",
                (document_id,)).fetchone()
        except sqlite3.OperationalError:
            return None
        return (row["raw_text"] or None) if row else None

    def nachbewilligungs_vorlagen(self) -> tuple[list[dict], dict[str, list[dict]]]:
        """Die Rohdaten für ``council/nachbewilligungen.aus_vorlagen``.

        → ``(vorlagen, beschluesse)`` — **erst die Vorlagen, dann die nach
        Vorlagen-Nummer gruppierten Beschlusszeilen**, genau in der
        Reihenfolge, die der Parser erwartet.

        Der Filter läuft über den **Titel**, nicht über eine Vorlagenart:
        ``art`` heißt hier „Beschlussvorlage" oder „Berichtsvorlage" und sagt
        nichts über den Inhalt. Vorgefiltert wird nur grob (SQL kennt unser
        Muster nicht); die Feinentscheidung trifft
        ``nachbewilligungen.ist_nachbewilligung``.

        **Der Join läuft über ``template_number``, nicht über ``kvonr``.** Das ist
        keine Stilfrage: ``council_decisions.kvonr`` ist im gesamten Bestand
        ``NULL`` (8.369 von 8.369 Zeilen). Ein Join darüber liefert
        schweigend null Treffer — und eine Seite, die behauptet, der Rat habe
        nie über eine Nachbewilligung entschieden."""
        try:
            vorlagen = [dict(r) for r in self._conn.execute(
                "SELECT template_number, title, beschlussvorschlag, raw_text "
                "FROM council_vorlagen "
                "WHERE template_number IS NOT NULL "
                "  AND (title LIKE '%planmäßig%' OR title LIKE '%planmässig%')"
            )]
            rows = [dict(r) for r in self._conn.execute(
                "SELECT d.id, d.template_number, d.outcome, d.vote, "
                "       cs.committee, cs.session_date "
                "FROM council_decisions d "
                "JOIN council_sessions cs ON cs.ksinr = d.ksinr "
                "WHERE d.template_number IS NOT NULL AND d.kind = 'decision' "
                + self._BESCHLUSS_ORDNUNG
            )]
        except sqlite3.OperationalError:
            return [], {}
        beschluesse: dict[str, list[dict]] = {}
        for r in rows:
            beschluesse.setdefault(str(r["template_number"]), []).append(r)
        return vorlagen, beschluesse

    def save_nachbewilligungen(self, zeilen: list[dict], herkunft) -> int:
        """Die RIS-Serie ersetzen — je Vorlage eine Zeile.

        Wie bei ``save_schulden`` wird nur ersetzt, was die Lieferung
        mitbringt. Übergeben wird, was der Parser gelesen hat; diese Methode
        prüft nichts nach."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_nachbewilligungen "
                "(template_number, jahr, titel, art, kategorie, betrag, "
                " betrag_quelle, beschlossen, im_rat, ratsentscheidung, "
                " beschluss_id, gremien, "
                " volltextprobe, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(z["template_number"], z.get("jahr"), z["titel"], z["art"],
                  z["kategorie"], z.get("betrag"), z.get("betrag_quelle"),
                  int(bool(z.get("beschlossen"))), int(bool(z.get("im_rat"))),
                  int(bool(z.get("ratsentscheidung"))),
                  z.get("beschluss_id"),
                  json.dumps(z.get("gremien") or [], ensure_ascii=False),
                  int(bool(z.get("volltextprobe"))), hid, now)
                 for z in zeilen])
        return len(zeilen)

    def save_nachbewilligung_jahr(self, jahr: dict, kanaele: list[dict],
                                  herkunft) -> int:
        """Ein Jahrgang aus Kapitel 3 des Rechenschaftsberichts.

        Jahreszeile und Kanäle wandern zusammen in **eine** Transaktion: Ein
        Bestand, in dem die Summenzeile eines Jahres steht und seine vier
        Wege fehlen, wäre genau der Zustand, den die Tabellenprobe unmöglich
        machen soll."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_nachbewilligung_jahre "
                "(jahr, summe_konsumtiv, summe_investiv, text_gesamt, "
                " verpflichtungen_betrag, probe_ok, probe_text, herkunft_id, "
                " fetched_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (jahr["jahr"], jahr["summe_konsumtiv"], jahr["summe_investiv"],
                 jahr.get("text_gesamt"), jahr.get("verpflichtungen_betrag"),
                 int(bool(jahr.get("probe_ok"))), jahr.get("probe_text"),
                 hid, now))
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_nachbewilligung_kanaele "
                "(jahr, kanal, label, anzahl_konsumtiv, betrag_konsumtiv, "
                " anzahl_investiv, betrag_investiv, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(jahr["jahr"], k["kanal"], k["label"], k["anzahl_konsumtiv"],
                  k["betrag_konsumtiv"], k["anzahl_investiv"],
                  k["betrag_investiv"], hid, now) for k in kanaele])
        return len(kanaele)

    def get_nachbewilligungen(self) -> list[dict]:
        """Die RIS-Serie, chronologisch. ``gremien`` kommt als Liste heraus."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_nachbewilligungen ORDER BY template_number")]
        except sqlite3.OperationalError:
            return []
        for r in rows:
            try:
                r["gremien"] = json.loads(r.get("gremien") or "[]")
            except (TypeError, ValueError):
                r["gremien"] = []
        return rows

    def get_nachbewilligung_jahre(self) -> list[dict]:
        """Die Jahrgänge aus dem Rechenschaftsbericht, je mit ihren Kanälen.

        Die Kanäle hängen als Liste ``kanaele`` an ihrem Jahr — anders als bei
        der Herkunft, die als eigenes Verzeichnis reist: Vier Zeilen je Jahr
        sind keine Wiederholung, die sich zu vermeiden lohnte, und die Seite
        liest sie ohnehin immer zusammen."""
        try:
            jahre = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_nachbewilligung_jahre ORDER BY jahr")]
            kanaele = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_nachbewilligung_kanaele "
                "ORDER BY jahr, rowid")]
        except sqlite3.OperationalError:
            return []
        nach_jahr: dict[int, list[dict]] = {}
        for k in kanaele:
            nach_jahr.setdefault(int(k["jahr"]), []).append(k)
        for j in jahre:
            j["kanaele"] = nach_jahr.get(int(j["jahr"]), [])
        return jahre

    def ausgabenreihe_jahre(self) -> list[int]:
        """Welche Jahrgänge im Bestand stehen — Grundlage des Bestandsschutzes
        vor dem Schreiben (``council/finanzquellen.bestandsschutz``)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT jahr FROM council_ausgabenreihe ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    # --- Zuwendungen an die Stadt (aus den Ratsbeschlüssen) ----------------

    def save_spenden(self, zeilen: list[dict], verworfen: list[dict],
                     herkunft) -> int:
        """Die geprüfte Spendenreihe schreiben — je Vorlage eine Zeile.

        Anders als bei den übrigen Schichten bringt **jede Zeile ihre eigene
        Herkunft mit** (``zeile["herkunft"]``): Jede Vorlage ist ein eigenes
        PDF mit eigener Dokument-ID. ``herkunft`` ist die Rückfallebene für
        die verworfenen Zeilen und für Zeilen ohne eigenen Anker — sie
        beschreibt den Lauf, nicht ein Dokument.

        ``INSERT OR REPLACE``, kein ``DELETE FROM``: Eine Teillieferung
        (etwa nach einem abgebrochenen Volltext-Lauf) ersetzt nur, was sie
        mitbringt, und räumt den Bestand nicht ab."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            rueck = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_spenden "
                "(template_number, jahr, sitzung, betrag, gremium, layout, zweitstelle, "
                " proben, herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(z["template_number"], z["jahr"], z["sitzung"], z["betrag"], z.get("gremium"),
                  z.get("layout"), z["zweitstelle"], ",".join(z["proben"]),
                  self.merke_herkunft(z["herkunft"], fetched_at=now)
                  if z.get("herkunft") else rueck, now)
                 for z in zeilen])
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_spenden_verworfen "
                "(template_number, sitzung, grund, herkunft_id, fetched_at) VALUES (?,?,?,?,?)",
                [(v["template_number"], v.get("sitzung"), v["grund"], rueck, now)
                 for v in verworfen])
        return len(zeilen)

    def get_spenden(self) -> list[dict]:
        """Die Spendenreihe je Vorlage, aufsteigend nach Sitzungsdatum.

        ``proben`` kommt als Liste heraus. Fehlt die Tabelle (frische
        Datenbank ohne Ingest-Lauf), ist die Antwort leer statt ein Fehler."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_spenden ORDER BY sitzung, template_number")]
        except sqlite3.OperationalError:
            return []
        for r in rows:
            r["proben"] = [p for p in (r.get("proben") or "").split(",") if p]
        return rows

    def get_spenden_verworfen(self) -> list[dict]:
        """Die Zeilen ohne Zweitstelle, mit dem Satz, warum sie fehlen."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_spenden_verworfen ORDER BY sitzung, template_number")]
        except sqlite3.OperationalError:
            return []

    def spenden_jahre(self) -> list[int]:
        """Welche Jahrgänge im Bestand stehen — Grundlage des Bestandsschutzes."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT jahr FROM council_spenden ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    def zuwendungsbeschluesse(self) -> list[dict]:
        """Die Rohzeilen für ``council.spenden.lies()``.

        Absichtlich breit gefasst (``Annahme%Zuwendung%``): Das Aussieben
        macht ``spenden.erkenne()``, damit die Regel an einer Stelle steht und
        nicht halb in SQL."""
        return [dict(r) for r in self._conn.execute(
            """SELECT d.template_number, d.title AS titel, d.official_text, d.outcome,
                      s.session_date AS sitzung, s.committee AS gremiensitzung,
                      v.raw_text, v.document_id AS dokument_id,
                      v.document_url AS dokument_url
                 FROM council_decisions d
                 LEFT JOIN council_sessions s ON s.ksinr = d.ksinr
                 LEFT JOIN council_vorlagen v ON v.template_number = d.template_number
                WHERE d.kind = 'decision' AND d.title LIKE 'Annahme%Zuwendung%'
                ORDER BY s.session_date, d.template_number""")]

    # --- Steuertabellen des Jahrbuchs (1103 und 1105) -----------------------

    def save_steuerplan(self, zeilen: list[dict], herkunft) -> int:
        """Plan neben Ist je Steuerart — ersetzt, was die Lieferung mitbringt.

        Nicht die ganze Tabelle: Jede Ausgabe von 1103 führt nur **drei**
        Jahrgänge, und der Lauf legt mehrere Ausgaben nacheinander ab. Ein
        ``DELETE`` vor dem Schreiben löschte deshalb genau das, wofür das
        Archiv gebaut wurde — die Jahrgänge, die nur noch in einer älteren
        Ausgabe stehen.

        Übergeben wird nur, was seine Proben bestanden hat; diese Methode prüft
        nichts nach."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_steuerplan "
                "(jahr, art, plan, ist, vorlaeufig, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?)",
                [(z["jahr"], z["art"], z["plan"], z["ist"],
                  int(bool(z.get("vorlaeufig"))), hid, now) for z in zeilen])
        return len(zeilen)

    def get_steuerplan(self) -> list[dict]:
        """Plan und Ist je Steuerart und Jahr, aufsteigend.

        Fehlt die Tabelle (frische Datenbank ohne Ingest-Lauf), ist die Antwort
        leer statt ein Fehler — die Seite zeigt den Block dann schlicht nicht."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT jahr, art, plan, ist, vorlaeufig FROM council_steuerplan "
                "ORDER BY jahr, art")]
        except sqlite3.OperationalError:
            return []

    def steuerplan_jahre(self) -> list[int]:
        """Welche Jahrgänge im Bestand stehen — für den Bestandsschutz."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT jahr FROM council_steuerplan ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    def save_hebesaetze(self, zeilen: list[dict], herkunft) -> int:
        """Die Hebesatz-Treppe — je Änderungsjahr und Steuerart eine Zeile."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_hebesaetze "
                "(jahr, art, hebesatz, vorheriger, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?)",
                [(z["jahr"], z["art"], z["hebesatz"], z.get("vorheriger"),
                  hid, now) for z in zeilen])
        return len(zeilen)

    def get_hebesaetze(self) -> list[dict]:
        """Die Hebesätze je Änderungsjahr, aufsteigend.

        **Nur Änderungsjahre** — die Lücken dazwischen sind keine fehlenden
        Daten, sondern die Aussage: Ein Hebesatz gilt, bis der Rat ihn ändert.
        Wer diese Reihe zeichnet, zeichnet eine Treppe."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT jahr, art, hebesatz, vorheriger FROM council_hebesaetze "
                "ORDER BY jahr, art")]
        except sqlite3.OperationalError:
            return []

    def hebesatz_jahre(self) -> list[int]:
        """Welche Änderungsjahre im Bestand stehen — für den Bestandsschutz."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT jahr FROM council_hebesaetze ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    # --- Ist-Investitionen (Tabellen 1107/1107-1 des Jahrbuchs) -------------

    def save_investitionen_ist(self, zeilen: list[dict], herkunft,
                               verworfen: list[dict] | None = None) -> int:
        """Investitions-Jahrgänge ersetzen — je Jahr eine Zeile plus ihre Arten.

        Ersetzt wird **nur, was die Lieferung mitbringt**, nicht die ganze
        Tabelle: Ein Lauf, dem ein Jahrgang an der Probe durchgefallen ist,
        darf den vorher gespeicherten Stand dieses Jahrgangs nicht mit
        wegräumen (derselbe Grund wie bei ``save_schulden``).

        Die Arten eines Jahrgangs werden vorher gelöscht statt nur überschrieben:
        Wechselte die Quelle ihren Spaltenschnitt, bliebe eine abgeschaffte Art
        sonst als Karteileiche stehen und die Aufteilung summierte sich auf
        mehr als die Summe daneben.

        ``verworfen`` sind die Jahrgänge, die die Probe **nicht** bestanden
        haben (``lies()["verworfen"]``): Grund und gemessene ``differenz``
        werden mitgeschrieben, damit die Seite ihre Lücke beziffern kann
        statt sie nur zu behaupten. Ein Jahrgang, der jetzt durchkommt,
        verliert dabei seinen alten Lücken-Eintrag — sonst stünde er in
        beiden Tabellen und die Seite zeigte eine Lücke, die es nicht mehr
        gibt.

        Übergeben wird an ``zeilen`` nur, was seine Probe bestanden hat —
        diese Methode prüft nichts nach, sie schreibt."""
        from council import investitionen_ist as _ii

        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_investitionen_ist "
                "(jahr, regelwerk, insgesamt, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?)",
                [(z["jahr"], z["regelwerk"], z["insgesamt"], hid, now)
                 for z in zeilen])
            self._conn.executemany(
                "DELETE FROM council_investitionen_ist_arten WHERE jahr = ?",
                [(z["jahr"],) for z in zeilen])
            arten = []
            for z in zeilen:
                spalten = _ii.SPALTEN[z["regelwerk"]]
                for i, (feld, titel) in enumerate(spalten[:-1]):
                    if z.get(feld) is None:
                        continue
                    arten.append((z["jahr"], feld, titel, i, z[feld], hid, now))
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_investitionen_ist_arten "
                "(jahr, feld, titel, reihenfolge, betrag, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?)", arten)
            # Ein übernommener Jahrgang ist keine Lücke mehr.
            self._conn.executemany(
                "DELETE FROM council_investitionen_ist_verworfen WHERE jahr = ?",
                [(z["jahr"],) for z in zeilen])
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_investitionen_ist_verworfen "
                "(jahr, regelwerk, grund, differenz, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?)",
                [(v["jahr"], v["regelwerk"], v["grund"], v.get("differenz"),
                  hid, now) for v in (verworfen or [])])
        return len(zeilen)

    def get_investitionen_ist(self) -> list[dict]:
        """Die Ist-Reihe, aufsteigend nach Jahr, mit ihrer Aufteilung.

        Je Jahrgang ein dict mit ``arten`` — den Auszahlungsarten in der
        Spaltenfolge der Quelle. Fehlt die Tabelle (frische Datenbank ohne
        Ingest-Lauf), ist die Antwort leer statt ein Fehler."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_investitionen_ist ORDER BY jahr")]
            arten = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_investitionen_ist_arten "
                "ORDER BY jahr, reihenfolge")]
        except sqlite3.OperationalError:
            return []
        je_jahr: dict[int, list[dict]] = {}
        for a in arten:
            je_jahr.setdefault(a["jahr"], []).append(
                {"feld": a["feld"], "titel": a["titel"], "betrag": a["betrag"]})
        for r in rows:
            r["arten"] = je_jahr.get(r["jahr"], [])
        return rows

    def get_investitionen_ist_verworfen(self) -> list[dict]:
        """Die verworfenen Jahrgänge, aufsteigend — je Jahr Grund und Differenz.

        Was hier steht, steht bewusst **nicht** in der Reihe: Diese Jahrgänge
        haben ihre Probe nicht bestanden. Die Tabelle beantwortet die eine
        Frage, die eine Lücke im Bild aufwirft — „wie weit lag es
        auseinander?" — und beantwortet sie mit der gemessenen Zahl statt mit
        einem Adjektiv. Fehlt die Tabelle (frische Datenbank ohne
        Ingest-Lauf), ist die Antwort leer statt ein Fehler."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_investitionen_ist_verworfen ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    def investitionen_ist_jahre(self) -> list[int]:
        """Welche Jahrgänge im Bestand stehen — der Bestandsschutz vergleicht
        gegen diese Zahl, bevor ein Lauf sie überschreibt."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT jahr FROM council_investitionen_ist ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    def investitionen_ist_kontext(self) -> dict | None:
        """Was die Stadt zuletzt wirklich investiert hat — für die KI-Frage.

        Wenige Zeilen statt Bestand, wie bei allen Geld-Bausteinen: der
        jüngste Jahrgang mit seiner Aufteilung, das Vorjahr als Maßstab und
        der höchste Stand der doppischen Reihe.

        **Nur die doppische Reihe.** Die kameralen Jahrgänge bis 2009 zählen
        etwas anderes (s. ``council/investitionen_ist.py``); in einem
        Prompt-Baustein nebeneinander wären sie eine Einladung, sie zu einer
        Reihe zu addieren.
        """
        from council import investitionen_ist as _ii

        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_investitionen_ist "
                "WHERE regelwerk = 'doppik' ORDER BY jahr")]
        except sqlite3.OperationalError:
            return None
        if not rows:
            return None
        neu = rows[-1]
        try:
            arten = [(r["titel"], r["betrag"]) for r in self._conn.execute(
                "SELECT titel, betrag FROM council_investitionen_ist_arten "
                "WHERE jahr = ? ORDER BY reihenfolge", (neu["jahr"],))]
        except sqlite3.OperationalError:
            arten = []
        hoch = max(rows, key=lambda r: r["insgesamt"])
        # Welche Jahre die Quelle ankündigt, aber nicht belegt — die Lücke
        # gehört in den Kontext, sonst liest ein Modell die Reihe als
        # lückenlos und rechnet Durchschnitte über ein Loch.
        fehlend = [j for j in range(rows[0]["jahr"], neu["jahr"] + 1)
                   if j not in {r["jahr"] for r in rows}]
        return {
            "jahr": neu["jahr"],
            "insgesamt": neu["insgesamt"],
            "arten": arten,
            "davor": ({"jahr": rows[-2]["jahr"], "insgesamt": rows[-2]["insgesamt"]}
                      if len(rows) > 1 else None),
            "hoch": ({"jahr": hoch["jahr"], "insgesamt": hoch["insgesamt"]}
                     if hoch["jahr"] != neu["jahr"] else None),
            "reihe_ab": rows[0]["jahr"],
            "fehlend": fehlend,
            "abgrenzung": _ii.ABGRENZUNG,
            "beleg": self._beleg(neu.get("herkunft_id")),
        }

    def schulden_jahre(self) -> list[int]:
        """Welche Jahrgänge im Bestand stehen."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT jahr FROM council_schulden ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    def einwohner_je_jahr(self) -> dict[int, int]:
        """Alle bekannten Einwohnerzahlen als ``{jahr: zahl}``.

        Der Divisor der Pro-Kopf-Gegenprobe (``council/schulden.py``). Bewusst
        die ganze Reihe und nicht nur der jüngste Wert wie bei
        ``einwohner_aktuell``: Geprüft wird jeder Jahrgang gegen die
        Einwohnerzahl **seines** Jahres, nicht gegen die von heute."""
        try:
            return {r[0]: r[1] for r in self._conn.execute(
                "SELECT jahr, einwohner FROM council_einwohner")}
        except sqlite3.OperationalError:
            return {}

    # --- Städtevergleich (amtliche Statistik des LSN) ------------------------

    def save_staedtevergleich(self, reihe: str, zeilen: list[dict], herkunft) -> int:
        """Eine Reihe des Städtevergleichs ersetzen — ``steuerkraft`` oder
        ``realsteuern``.

        Ersetzt wird **je Reihe und je betroffenem Jahr**, nicht die ganze
        Tabelle: Die beiden Reihen kommen aus verschiedenen Dateien, die zu
        verschiedenen Zeiten im Jahr erscheinen. Ein Lauf, der nur den
        Realsteuervergleich neu einliest, darf die Steuerkraft-Reihe nicht
        mitnehmen — sonst hinge der Bestand davon ab, in welcher Reihenfolge
        jemand die beiden Ingests anstößt.

        Übergeben wird nur, was seine Probe bestanden hat; diese Methode prüft
        nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        jahre = {int(z["jahr"]) for z in zeilen}
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            for jahr in sorted(jahre):
                self._conn.execute(
                    "DELETE FROM council_staedtevergleich WHERE reihe = ? AND jahr = ?",
                    (reihe, jahr))
            self._conn.executemany(
                "INSERT INTO council_staedtevergleich (reihe, jahr, schluessel, "
                " stadt, kennzahl, wert, einheit, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(reihe, z["jahr"], z["schluessel"], z["stadt"], z["kennzahl"],
                  z["wert"], z["einheit"], hid, now) for z in zeilen])
        return len(zeilen)

    def get_staedtevergleich(self, reihe: str | None = None) -> list[dict]:
        """Der Städtevergleich — eine Reihe oder beide.

        Sortiert nach Jahr und Stadt, damit die Oberfläche nichts umsortieren
        muss. Fehlt die Tabelle (frische Datenbank ohne Ingest-Lauf), ist die
        Antwort leer statt ein Fehler — der Haushalts-Bereich zeigt die Seite
        dann schlicht ohne Vergleichszahlen."""
        try:
            if reihe is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_staedtevergleich "
                    "ORDER BY reihe, jahr, stadt, kennzahl").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_staedtevergleich WHERE reihe = ? "
                    "ORDER BY jahr, stadt, kennzahl", (reihe,)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def save_gewerbesteuerstatistik(self, zeilen: list[dict], herkunft) -> int:
        """Einen Erhebungsjahrgang der Gewerbesteuerstatistik ersetzen.

        Ersetzt wird **je Jahr**, nicht die ganze Tabelle: Die Jahrgänge kommen
        aus je eigenen Berichten, und ein Lauf, der 2021 nachträgt, darf 2017
        bis 2020 nicht mitnehmen. Ein Jahrgang wird dagegen vollständig
        ersetzt — das LSN gibt korrigierte Fassungen heraus (der Jahrgang 2020
        wurde am 11.02.2026 nachgebessert), und eine Korrektur, die alte Zeilen
        stehen ließe, wäre keine.

        Übergeben wird nur, was seine Proben bestanden hat; diese Methode prüft
        nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        jahre = {int(z["jahr"]) for z in zeilen}
        spalten = ("jahr", "schluessel", "stadt", "faelle", "faelle_positiv",
                   "messbetrag_eur", "festsetzungen", "festsetzungen_positiv",
                   "festsetzung_messbetrag_eur", "zerlegungen",
                   "zerlegungen_positiv", "zerlegung_messbetrag_eur",
                   "hebesatz", "gesperrt")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            for jahr in sorted(jahre):
                self._conn.execute(
                    "DELETE FROM council_gewerbesteuerstatistik WHERE jahr = ?",
                    (jahr,))
            self._conn.executemany(
                f"INSERT INTO council_gewerbesteuerstatistik "
                f"({', '.join(spalten)}, herkunft_id, fetched_at) "
                f"VALUES ({', '.join('?' * len(spalten))},?,?)",
                [tuple(z.get(s) for s in spalten) + (hid, now) for z in zeilen])
        return len(zeilen)

    def get_gewerbesteuerstatistik(self, schluessel: str | None = None) -> list[dict]:
        """Die Gewerbesteuerstatistik — eine Stadt oder alle, aufsteigend nach Jahr.

        Fehlt die Tabelle (frische Datenbank ohne Ingest-Lauf), ist die Antwort
        leer statt ein Fehler: Der Steuer-Steckbrief zeigt den Block dann ohne
        diese Zahlen, wie bei den anderen Schichten auch."""
        try:
            if schluessel is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_gewerbesteuerstatistik "
                    "ORDER BY jahr, stadt").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_gewerbesteuerstatistik "
                    "WHERE schluessel = ? ORDER BY jahr", (schluessel,)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def save_produkte(self, jahr: int, produkte: list[dict], herkunft) -> int:
        """Produkte eines Jahres einfügen/aktualisieren. Bewusst KEIN Löschen
        des Jahrgangs: Die Produkte eines Jahres verteilen sich auf mehrere
        Teilhaushalts-Dokumente, die nacheinander eingelesen werden.

        ``INSERT OR REPLACE`` ersetzt bei gleichem ``(jahr, produkt_nr)`` die
        **ganze** Zeile, samt Herkunft — wer zuletzt schreibt, gewinnt. Das ist
        hier nur deshalb ungefährlich, weil der Aufrufer dafür sorgt, dass ein
        Teilhaushalt genau einmal geschrieben wird: Sechs (Jahrgang,
        Teilhaushalt)-Paare liegen doppelt im Anlagenbestand, und welches der
        beiden Dokumente in der Zeile steht, soll keine Frage der
        Sortierreihenfolge sein. Die Regel und die Messung dazu stehen in
        ``council.finanzquellen.lies_teilhaushalte``. Wer einen zweiten
        Schreibweg zu dieser Tabelle baut, braucht dieselbe Vorentscheidung —
        die Tabelle selbst kann sie nicht treffen, sie sieht nur eine Zeile."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_produkte (jahr, produkt_nr, produkt_name, "
                " thh_nr, thh_name, amt, ertraege, aufwendungen, ergebnis, "
                " kurzbeschreibung, auftragsgrundlage, beeinflussbarkeit, "
                " beeinflussbarkeit_roh, wirkungskreis, zielgruppe, "
                " quelle_label, quelle_url, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(jahr, p["produkt_nr"], p["produkt_name"], p.get("thh_nr"), p.get("thh_name"),
                  p.get("amt"), p.get("ertraege"), p.get("aufwendungen"), p.get("ergebnis"),
                  p.get("kurzbeschreibung"), p.get("auftragsgrundlage"),
                  p.get("beeinflussbarkeit"), p.get("beeinflussbarkeit_roh"),
                  p.get("wirkungskreis"), p.get("zielgruppe"),
                  herkunft.label, herkunft.url, now, hid) for p in produkte])
        return len(produkte)

    def get_produkte(self, jahr: int, thh_nr: int | None = None,
                     suche: str | None = None, amt: str | None = None,
                     beeinflussbarkeit: str | None = None,
                     limit: int | None = None) -> list[dict]:
        """Produkte eines Jahres, teuerste zuerst (nach Zuschussbedarf).

        Suche und Filter laufen bewusst HIER und nicht im Frontend: Mit dem
        Steckbrief trägt jede Zeile mehrere hundert Zeichen Fließtext — knapp
        400 davon über die Leitung zu schicken, damit der Browser sie filtert,
        wäre Verschwendung. Gesucht wird über Name, Nummer, Amt und
        Kurzbeschreibung; ``LIKE`` genügt bei dieser Menge (kein FTS nötig)."""
        wo = ["jahr = ?"]
        args: list = [jahr]
        if thh_nr is not None:
            wo.append("thh_nr = ?")
            args.append(thh_nr)
        if amt:
            wo.append("amt = ?")
            args.append(amt)
        if beeinflussbarkeit:
            wo.append("beeinflussbarkeit = ?")
            args.append(beeinflussbarkeit)
        if suche and suche.strip():
            # Jeder Begriff muss irgendwo vorkommen (UND über die Begriffe,
            # ODER über die Felder) — so grenzt „archiv stadt" wirklich ein.
            for wort in suche.split()[:6]:
                wo.append("(produkt_name LIKE ? OR produkt_nr LIKE ? OR amt LIKE ? "
                          "OR kurzbeschreibung LIKE ?)")
                args.extend([f"%{wort}%"] * 4)
        sql = ("SELECT * FROM council_produkte WHERE " + " AND ".join(wo)
               + " ORDER BY ergebnis ASC" + (" LIMIT ?" if limit else ""))
        if limit:
            args.append(limit)
        return [dict(r) for r in self._conn.execute(sql, args)]

    def produkt(self, jahr: int, produkt_nr: str) -> dict | None:
        """Ein Produkt samt Steckbrief — die Steckbrief-Ansicht braucht es
        auch dann, wenn es durch Suche oder Filter gerade nicht in der Liste
        stünde."""
        row = self._conn.execute(
            "SELECT * FROM council_produkte WHERE jahr = ? AND produkt_nr = ?",
            (jahr, produkt_nr)).fetchone()
        return dict(row) if row else None

    def produkt_facetten(self, jahr: int) -> dict:
        """Womit sich die Produktliste filtern lässt — Ämter und Spielraum-
        Stufen mit Anzahl, plus wie viele Produkte überhaupt einen Steckbrief
        tragen. Letzteres gehört sichtbar auf die Seite: Ein Filter, der die
        halbe Liste verschluckt, muss sich erklären."""
        aemter = [{"amt": r[0], "anzahl": r[1]} for r in self._conn.execute(
            "SELECT amt, COUNT(*) FROM council_produkte WHERE jahr = ? AND amt IS NOT NULL "
            "GROUP BY amt ORDER BY COUNT(*) DESC, amt", (jahr,))]
        spielraum = {r[0]: r[1] for r in self._conn.execute(
            "SELECT beeinflussbarkeit, COUNT(*) FROM council_produkte "
            "WHERE jahr = ? AND beeinflussbarkeit IS NOT NULL "
            "GROUP BY beeinflussbarkeit", (jahr,))}
        felder = {}
        for feld in ("kurzbeschreibung", "auftragsgrundlage", "beeinflussbarkeit",
                     "wirkungskreis", "zielgruppe"):
            felder[feld] = self._conn.execute(
                f"SELECT COUNT(*) FROM council_produkte WHERE jahr = ? "
                f"AND {feld} IS NOT NULL AND {feld} != ''", (jahr,)).fetchone()[0]
        return {"aemter": aemter, "spielraum": spielraum, "mit_feld": felder}

    def produkte_jahre(self) -> list[int]:
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT jahr FROM council_produkte ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    def produkt_abdeckung(self) -> dict[str, list[int]]:
        """Je Produktnummer die Jahre, in denen sie im Bestand steht.

        Nicht jedes Jahr deckt jeden Teilhaushalt (die Pläne liegen nicht für
        jeden Jahrgang auslesbar vor) — die Trefferliste soll das je Produkt
        ehrlich anschreiben können (Abdeckungs-Badge, H4-04), statt eine
        durchgehende Reihe zu suggerieren. Eine Abfrage für alle Produkte:
        Die Liste ist klein (wenige hundert Nummern), und je Treffer einzeln
        zu fragen wäre ein N+1."""
        out: dict[str, list[int]] = {}
        try:
            rows = self._conn.execute(
                "SELECT produkt_nr, jahr FROM council_produkte ORDER BY jahr")
        except sqlite3.OperationalError:
            return out
        for nr, jahr in rows:
            out.setdefault(nr, []).append(jahr)
        return out

    def save_pruefbericht(self, jahr: int, feststellungen: list[dict], herkunft) -> int:
        """Prüfungsfeststellungen eines Schlussberichts speichern.

        Der Jahrgang wird vorher geleert: Ein Bericht ist ein Dokument, und
        ein erneuter Ingest liest dasselbe Dokument neu — Zeilen von früheren
        Läufen stehen zu lassen hieße, alte Parser-Stände zu konservieren.

        Die ``fundstelle`` der Herkunft bleibt hier bewusst grob („Randmarken
        des Berichts"): Die genaue Fundstelle einer Feststellung ist ihre
        **Textziffer** und ihre **Seite**, und die stehen je Zeile in der
        Tabelle. Die Herkunft beschreibt das Dokument, nicht die Zeile."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_pruefberichte WHERE jahr = ?", (jahr,))
            self._conn.executemany(
                "INSERT INTO council_pruefberichte (jahr, lfd, marke, marke_name, "
                " marke_erlaeuterung, textziffer, abschnitt, kette, seite, text, "
                " folgeabsatz, quelle_label, quelle_url, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(jahr, f["lfd"], f["marke"], f["marke_name"], f.get("marke_erlaeuterung"),
                  f["textziffer"], f["abschnitt"], f.get("kette"), f.get("seite"),
                  f["text"], f.get("folgeabsatz"), herkunft.label, herkunft.url, now, hid)
                 for f in feststellungen])
        return len(feststellungen)

    def get_pruefberichte(self, jahr: int | None = None) -> list[dict]:
        """Prüfungsfeststellungen — ein Jahrgang oder alle, in Dokumentreihenfolge.

        Ohne Argument alle: Die Ketten über die Jahrgänge („seit wann steht
        das offen?") lassen sich nur aus dem Gesamtbestand bilden."""
        try:
            if jahr is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_pruefberichte ORDER BY jahr, lfd").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_pruefberichte WHERE jahr = ? ORDER BY lfd",
                    (jahr,)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def pruefbericht_jahre(self) -> list[int]:
        """Jahrgänge mit eingelesenem Schlussbericht (aufsteigend)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT jahr FROM council_pruefberichte ORDER BY jahr")]
        except sqlite3.OperationalError:
            return []

    def get_steuerkraft(self) -> list[dict]:
        """Steuerkraft/Zuweisungen je Jahr, älteste zuerst."""
        return [dict(r) for r in self._conn.execute(
            "SELECT jahr, messzahl, messzahl_je_ew, zuweisungen, zuweisungen_je_ew "
            "FROM council_steuerkraft ORDER BY jahr")]

    def get_finanzausgleich(self, schluessel: str = "403000") -> list[dict]:
        """Die drei Komponenten des Finanzausgleichs für **eine** Stadt.

        Liest ``reihe='finanzausgleich'`` aus ``council_staedtevergleich`` und
        dreht sie in eine Zeile je Ausgleichsjahr: ``{jahr,
        zuweisungen_gemeindeaufgaben, zuweisungen_kreisaufgaben,
        zuweisungen_uebertragener_wirkungskreis, finanzausgleichsumlage,
        nettobetrag}``, alle in **Tausend Euro** (so führt das Blatt sie).

        Warum eine eigene Lesefunktion und nicht ``get_staedtevergleich``: Die
        Haushalts-Übersicht braucht acht Zahlen je Jahr für Oldenburg, nicht
        die 240 Zeilen aller acht Städte. Die Übersicht ist mit 1,6 MB ohnehin
        die schwerste Antwort des Bereichs; der Städtevergleich hat seinen
        eigenen Endpunkt und behält ihn.
        """
        try:
            rows = self._conn.execute(
                "SELECT jahr, kennzahl, wert FROM council_staedtevergleich "
                "WHERE reihe = 'finanzausgleich' AND schluessel = ? "
                "ORDER BY jahr", (schluessel,)).fetchall()
        except sqlite3.OperationalError:
            return []
        nach_jahr: dict[int, dict] = {}
        for r in rows:
            nach_jahr.setdefault(int(r["jahr"]), {"jahr": int(r["jahr"])})[
                r["kennzahl"]] = r["wert"]
        return [nach_jahr[j] for j in sorted(nach_jahr)]

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
            """SELECT a.document_id, a.antragsteller, v.template_number
               FROM council_anlagen a JOIN council_vorlagen v ON v.kvonr = a.kvonr
               WHERE a.is_antrag = 1 AND a.antragsteller != '[]'
                 AND v.template_number IS NOT NULL AND v.template_number != ''""",
        ).fetchall()

        per_party: dict[str, dict] = {}
        n_mit_beschluss = 0
        for row in antraege:
            base = "/".join(row["template_number"].split("/")[:2])
            # Trägt eine Vorlage mehrere Antrag-Anlagen (Änderungsanträge mehrerer
            # Parteien), zählt der Vorlagen-Endstand für jeden dieser Anträge.
            decision = self._conn.execute(
                """SELECT d.outcome, cs.committee FROM council_decisions d
                   JOIN council_sessions cs ON cs.ksinr = d.ksinr
                   WHERE d.kind = 'decision' AND d.outcome IN ('angenommen','abgelehnt')
                     AND (d.template_number = ? OR d.template_number LIKE ?)
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
        Returns id + the fields the classifier needs (title, official_text, committee)."""
        sql = ("SELECT d.id, d.title, d.official_text, cs.committee "
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
        """(Re)build the full-text index from all main decisions (title + official_text +
        summary + the first chunk of the Vorlage text + the first chunk of attached
        motion texts, so Sachverhalt AND original Antrag wording are findable). The
        joins are grouped because distinct kvonrs can in theory share a template_number —
        duplicate rowids would break the FTS insert."""
        with self._conn:
            self._conn.execute("DELETE FROM council_decisions_fts")
            self._conn.execute(
                "INSERT INTO council_decisions_fts(rowid, content) "
                "SELECT d.id, REPLACE(COALESCE(d.title,'') || ' ' || COALESCE(d.official_text,'') || ' ' "
                "|| COALESCE(d.summary,'') || ' ' || COALESCE(sv.stext,'') || ' ' "
                "|| COALESCE(v.vtext,'') || ' ' || COALESCE(an.atext,''), "
                "'ß', 'ss') "  # unicode61 folds ä/ö/ü but not ß
                "FROM council_decisions d "
                "LEFT JOIN (SELECT template_number, ohne_kontaktdaten("
                "             substr(MAX(raw_text), 1, 8000)) AS vtext "
                "           FROM council_vorlagen WHERE status = 'ok' GROUP BY template_number) v "
                "  ON v.template_number = d.template_number "
                # `ohne_kontaktdaten()` ist eine SQLite-Funktion (s.
                # `_verbinden`): Sie nimmt Kontonummern, Telefonnummern,
                # E-Mail-Adressen und Anschriften aus dem Text, BEVOR er in
                # den Volltextindex geht. Gespeichert bleibt er vollständig.
                "LEFT JOIN (SELECT cv.template_number, ohne_kontaktdaten("
                "             substr(GROUP_CONCAT(a.raw_text, ' '), 1, 4000)) AS atext "
                "           FROM council_anlagen a JOIN council_vorlagen cv ON cv.kvonr = a.kvonr "
                "           WHERE a.is_antrag = 1 AND a.status = 'ok' GROUP BY cv.template_number) an "
                "  ON an.template_number = d.template_number "
                # Teilabstimmungen (Änderungsanträge) haben keine eigene FTS-Zeile —
                # ihre Titel zählen zum Haupt-TOP, damit „Änderungsantrag der X zu Y"
                # den zitierfähigen Hauptbeschluss findet (Design 23a: subvote-Inhalt
                # steht im title, official_text ist immer NULL).
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
        """Main decisions (id, title, official_text) for the entity-extraction backfill."""
        return [dict(r) for r in self._conn.execute(
            "SELECT id, title, official_text FROM council_decisions WHERE kind = 'decision'")]

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

    # ---- Explizite Ortszuordnungen je Beschluss ---------------------------

    def decision_location_batches(self, *, batch_size: int = 12,
                                  pending_only: bool = True,
                                  limit: int | None = None):
        """Beschlüsse samt Vorlage speicherschonend in Batches liefern.

        Im Tageslauf kommen nur ungescannte Vorgänge oder solche mit einer
        später geladenen Vorlage zurück. ``pending_only=False`` ist der
        bewusste Voll-Backfill nach dem Leeren der Scan-Tabelle.
        """
        inner = """SELECT d.id, d.title, d.official_text, d.template_number,
                      COALESCE(
                        (SELECT v.raw_text FROM council_vorlagen v
                         WHERE v.kvonr = d.kvonr AND v.status = 'ok' LIMIT 1),
                        (SELECT v.raw_text FROM council_vorlagen v
                         WHERE v.status = 'ok' AND v.template_number = d.template_number
                         ORDER BY v.kvonr DESC LIMIT 1),
                        (SELECT v.raw_text FROM council_vorlagen v
                         WHERE v.status = 'ok' AND d.template_number IS NOT NULL
                           AND instr(d.template_number, v.template_number || '/') = 1
                         ORDER BY v.kvonr DESC LIMIT 1)
                      ) AS vorlage_text,
                      COALESCE(
                        (SELECT v.fetched_at FROM council_vorlagen v
                         WHERE v.kvonr = d.kvonr AND v.status = 'ok' LIMIT 1),
                        (SELECT v.fetched_at FROM council_vorlagen v
                         WHERE v.status = 'ok' AND v.template_number = d.template_number
                         ORDER BY v.kvonr DESC LIMIT 1),
                        (SELECT v.fetched_at FROM council_vorlagen v
                         WHERE v.status = 'ok' AND d.template_number IS NOT NULL
                           AND instr(d.template_number, v.template_number || '/') = 1
                         ORDER BY v.kvonr DESC LIMIT 1),
                        ''
                      ) AS vorlage_fetched_at,
                      s.source_hash AS existing_source_hash,
                      s.scanned_at
               FROM council_decisions d
               LEFT JOIN council_decision_location_scans s ON s.decision_id = d.id
               WHERE d.kind = 'decision'"""
        sql = f"SELECT * FROM ({inner}) q"
        if pending_only:
            sql += (" WHERE existing_source_hash IS NULL OR "
                    "(vorlage_fetched_at != '' AND "
                    "datetime(vorlage_fetched_at) > datetime(scanned_at))")
        sql += " ORDER BY id DESC"
        if limit is not None:
            sql += f" LIMIT {max(0, int(limit))}"
        cursor = self._conn.execute(sql)
        while True:
            rows = cursor.fetchmany(max(1, int(batch_size)))
            if not rows:
                break
            yield [dict(r) for r in rows]

    def decisions_for_location_extraction(self) -> list[dict]:
        """Kompatible Listenansicht; große Backfills nutzen die Batch-Methode."""
        return [row for batch in self.decision_location_batches(pending_only=False)
                for row in batch]

    def location_scan_hashes(self) -> dict[int, str]:
        return {r["decision_id"]: r["source_hash"] for r in self._conn.execute(
            "SELECT decision_id, source_hash FROM council_decision_location_scans")}

    def place_observations_for_decisions(self, ids: list[int]) -> dict[int, list[dict]]:
        """Einmalige alte NER-Orte als günstige Startbasis übernehmen."""
        if not ids:
            return {}
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT decision_id, name FROM council_entity_obs "
            f"WHERE kind = 'ort' AND decision_id IN ({ph})", ids).fetchall()
        out: dict[int, list[dict]] = {}
        for r in rows:
            out.setdefault(r["decision_id"], []).append({
                "name": r["name"], "kind": "sonstiges", "source": "official_text",
                "evidence": r["name"], "method": "entity_obs", "confidence": 0.86,
            })
        return out

    # ---- gemeinsamer, redaktionell erweiterbarer Ortskatalog -----------------

    def _reviewed_places(self) -> tuple:
        """Als eigene Orte freigegebene Kandidaten im Katalogformat liefern."""
        from council import places

        rows = self._conn.execute(
            """SELECT r.*, l.name AS observed_name, l.lat, l.lon
               FROM council_place_reviews r
               JOIN council_locations l ON l.slug = r.location_slug
               WHERE r.status = 'approved' ORDER BY COALESCE(r.name,l.name)"""
        ).fetchall()
        static = {place.id: place for place in places.all_places()}
        out = []
        for row in rows:
            parent = static.get(row["parent_id"])
            if parent and not parent.is_primary:
                parent = None
            try:
                aliases = tuple(str(value).strip() for value in json.loads(row["aliases"] or "[]")
                                if str(value).strip())
            except (TypeError, json.JSONDecodeError):
                aliases = ()
            observed = (row["observed_name"] or "").strip()
            if observed and observed.casefold() != (row["name"] or observed).casefold():
                aliases = tuple(dict.fromkeys((*aliases, observed)))
            out.append(places.Place(
                id=row["place_id"] or row["location_slug"],
                name=row["name"] or observed,
                kind=row["kind"] or "quartier",
                aliases=aliases,
                wahlbereiche=parent.wahlbereiche if parent else (),
                parent_ids=(parent.id,) if parent else (),
                description=row["description"] or None,
                source_ids=(),
                filterable=True,
                quiz_enabled=bool(row["quiz_enabled"]),
                lat=row["lat"], lon=row["lon"],
            ))
        return tuple(out)

    def all_places(self) -> tuple:
        """Versionierter Basiskatalog plus redaktionell freigegebene Orte."""
        from dataclasses import replace
        from council import places
        if self._runtime_places_cache is None:
            base = [*places.all_places(), *self._reviewed_places()]
            alias_values: dict[str, list[str]] = {}
            for row in self._conn.execute(
                """SELECT r.canonical_place_id,r.aliases,l.name
                   FROM council_place_reviews r
                   JOIN council_locations l ON l.slug=r.location_slug
                   WHERE r.status='alias' AND r.canonical_place_id IS NOT NULL"""
            ):
                values = [row["name"]]
                try:
                    values += [str(value).strip() for value in json.loads(row["aliases"] or "[]")
                               if str(value).strip()]
                except (TypeError, json.JSONDecodeError):
                    pass
                alias_values.setdefault(row["canonical_place_id"], []).extend(values)
            self._runtime_places_cache = tuple(
                replace(place, aliases=tuple(dict.fromkeys((*place.aliases, *alias_values[place.id]))))
                if place.id in alias_values else place
                for place in base
            )
        return self._runtime_places_cache

    def resolve_place(self, value: str | None):
        """Statische und freigegebene Orte sowie geprüfte Aliase auflösen."""
        from council import places
        from council.locations import location_slug

        static = places.resolve(value)
        if static:
            return static
        key = location_slug(value or "")
        if not key:
            return None
        for place in self.all_places():
            if key in {location_slug(v) for v in (place.id, place.name, *place.aliases)}:
                return place
        if self._place_aliases_cache is None:
            self._place_aliases_cache = {
                row["location_slug"]: row["canonical_place_id"]
                for row in self._conn.execute(
                    "SELECT location_slug,canonical_place_id FROM council_place_reviews "
                    "WHERE status='alias' AND canonical_place_id IS NOT NULL")
            }
        canonical_place_id = self._place_aliases_cache.get(key)
        if canonical_place_id:
            return next((place for place in self.all_places()
                         if place.id == canonical_place_id), None)
        return None

    def primary_parents(self, place) -> tuple:
        if not place:
            return ()
        if place.is_primary:
            return (place,)
        parents = {candidate.id: candidate for candidate in self.all_places()
                   if candidate.is_primary}
        return tuple(parents[parent_id] for parent_id in place.parent_ids
                     if parent_id in parents)

    def public_place(self, place) -> dict:
        """API-Darstellung eines statischen oder redaktionellen Orts."""
        from dataclasses import asdict
        from council import places

        if places.resolve(place.id):
            return places.public_place(place)
        row = asdict(place)
        row["kind_label"] = places.kind_label(place.kind)
        row["parents"] = [
            {"id": parent.id, "name": parent.name, "kind": parent.kind}
            for parent in self.primary_parents(place)
        ]
        review = self._conn.execute(
            "SELECT source_url FROM council_place_reviews WHERE place_id=? AND status='approved'",
            (place.id,),
        ).fetchone()
        row["sources"] = ([{"id": "redaktionell", "type": "web",
                            "title": "Redaktionell geprüfte Quelle",
                            "url": review["source_url"]}]
                          if review and review["source_url"] else [])
        return row

    def public_place_catalog(self) -> dict:
        from council import places
        data = places.public_catalog()
        data["places"] = [self.public_place(place) for place in self.all_places()]
        return data

    def location_candidates(self, status_filter: str = "pending", *, limit: int = 200,
                            min_decisions: int = 3) -> list[dict]:
        """Häufige, noch nicht statisch katalogisierte Ortsnamen samt Belegen."""
        status_filter = status_filter if status_filter in {
            "pending", "concrete", "approved", "alias", "rejected", "all"
        } else "pending"
        # Auch zur Laufzeit freigegebene Katalogorte zählen als bekannt. So
        # verschwinden nach dem Backfill nicht nur statische Stadtteile,
        # sondern ebenso Schreibvarianten neuer redaktioneller Orte aus
        # der offenen Kandidatenliste.
        known_ids = sorted(place.id for place in self.all_places())
        review_where = ""
        review_params: list = []
        if status_filter == "pending":
            review_where = "AND r.status IS NULL"
        elif status_filter != "all":
            review_where = "AND r.status = ?"
            review_params.append(status_filter)
        known_placeholders = ",".join("?" for _ in known_ids)
        known_where = (
            f"AND (r.status IS NOT NULL OR l.place_id IS NULL "
            f"OR l.place_id NOT IN ({known_placeholders}))"
            if known_ids else ""
        )
        # Die offene Liste ist eine Prioritätenliste, kein Dump aller einmalig
        # erwähnten Namen. Bereits geprüfte Einträge müssen dagegen auch dann
        # sichtbar bleiben, wenn sie nur in einem Beschluss vorkommen.
        effective_min = max(1, int(min_decisions)) if status_filter == "pending" else 1
        rows = self._conn.execute(
            f"""SELECT l.*, r.status AS review_status, r.place_id AS review_place_id,
                      r.name AS review_name, r.kind AS review_kind, r.parent_id,
                      r.aliases, r.description, r.source_url, r.quiz_enabled,
                      r.canonical_place_id, r.note, r.updated_by, r.updated_at AS reviewed_at,
                      COUNT(DISTINCT dl.decision_id) AS decision_count,
                      MAX(cs.session_date) AS last_date,
                      AVG(dl.confidence) AS avg_confidence
               FROM council_locations l
               JOIN council_decision_locations dl ON dl.location_slug=l.slug
               JOIN council_decisions d ON d.id=dl.decision_id AND d.kind='decision'
               JOIN council_sessions cs ON cs.ksinr=d.ksinr
               LEFT JOIN council_place_reviews r ON r.location_slug=l.slug
               WHERE l.kind IN ('stadtteil','gebiet','sonstiges') {review_where} {known_where}
               GROUP BY l.slug
               HAVING COUNT(DISTINCT dl.decision_id) >= ?
               ORDER BY decision_count DESC, last_date DESC, l.name
               LIMIT ?""", (*review_params, *known_ids, effective_min,
                              max(1, min(int(limit), 500)))
        ).fetchall()
        out = []
        for row in rows:
            state = row["review_status"] or "pending"
            evidence = self._conn.execute(
                """SELECT d.id,d.title,cs.session_date,dl.evidence,dl.method,dl.confidence
                   FROM council_decision_locations dl
                   JOIN council_decisions d ON d.id=dl.decision_id
                   JOIN council_sessions cs ON cs.ksinr=d.ksinr
                   WHERE dl.location_slug=? AND d.kind='decision'
                   ORDER BY cs.session_date DESC,d.id DESC LIMIT 3""",
                (row["slug"],),
            ).fetchall()
            item = dict(row)
            item["status"] = state
            try:
                item["aliases"] = json.loads(row["aliases"] or "[]")
            except (TypeError, json.JSONDecodeError):
                item["aliases"] = []
            item["evidence"] = [dict(sample) for sample in evidence]
            out.append(item)
        return out

    def review_location_candidate(self, location_slug: str, *, status: str,
                                  place_id: str | None = None, name: str | None = None,
                                  kind: str | None = None, parent_id: str | None = None,
                                  aliases: list[str] | None = None,
                                  description: str | None = None,
                                  source_url: str | None = None,
                                  quiz_enabled: bool = False,
                                  canonical_place_id: str | None = None,
                                  note: str | None = None,
                                  updated_by: str | None = None) -> dict:
        """Redaktionelles Urteil speichern und stabile IDs an Rohorte schreiben."""
        from council import places
        from council.locations import location_slug as slugify

        if status not in {"concrete", "approved", "alias", "rejected"}:
            raise ValueError("Unbekannter Prüfstatus")
        observed = self._conn.execute(
            "SELECT * FROM council_locations WHERE slug=?", (location_slug,)).fetchone()
        if not observed:
            raise KeyError(location_slug)
        allowed_kinds = {key for key in places.catalog()["kinds"] if key != "ortsbereich"}
        if status == "approved":
            place_id = slugify(place_id or name or observed["name"])
            name = (name or observed["name"]).strip()
            kind = kind or "quartier"
            if not place_id or not name or kind not in allowed_kinds:
                raise ValueError("Freigegebener Ort braucht Name, gültige ID und Ortstyp")
            if not (source_url or "").startswith(("https://", "http://")):
                raise ValueError("Freigegebener Ort braucht eine Quellen-URL")
            if places.resolve(place_id) or any(p.id == place_id for p in self._reviewed_places()
                                                if p.id != observed["place_id"]):
                raise ValueError("Orts-ID ist bereits vergeben")
            parent = places.resolve(parent_id) if parent_id else None
            if parent_id and (not parent or not parent.is_primary):
                raise ValueError("Elternort muss ein primärer Ortsbereich sein")
        elif status == "concrete":
            name = (name or observed["name"]).strip()
            if not name or kind not in CONCRETE_LOCATION_KINDS:
                raise ValueError("Konkreter Ort braucht Name und gültigen Ortstyp")
            # Konkrete Punkte bleiben exakte Fundorte und werden absichtlich
            # nicht Teil des flächigen Ortskatalogs.
            place_id = None
            canonical_place_id = None
            parent_id = observed["ortsbereich_id"]
            source_url = None
            quiz_enabled = False
        elif status == "alias":
            target = self.resolve_place(canonical_place_id)
            if not target:
                raise ValueError("Alias-Ziel ist unbekannt")
            canonical_place_id = target.id
            parents = self.primary_parents(target)
            parent_id = parents[0].id if len(parents) == 1 else None
            place_id = target.id
        else:
            place_id = None
            parent_id = None
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        clean_aliases = list(dict.fromkeys(value.strip() for value in (aliases or []) if value.strip()))
        with self._conn:
            self._conn.execute(
                """INSERT INTO council_place_reviews
                   (location_slug,status,place_id,name,kind,parent_id,aliases,description,
                    source_url,quiz_enabled,canonical_place_id,note,updated_by,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(location_slug) DO UPDATE SET
                    status=excluded.status,place_id=excluded.place_id,name=excluded.name,
                    kind=excluded.kind,parent_id=excluded.parent_id,aliases=excluded.aliases,
                    description=excluded.description,source_url=excluded.source_url,
                    quiz_enabled=excluded.quiz_enabled,
                    canonical_place_id=excluded.canonical_place_id,note=excluded.note,
                    updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
                (location_slug, status, place_id, name, kind, parent_id,
                 json.dumps(clean_aliases, ensure_ascii=False), description, source_url,
                 int(quiz_enabled), canonical_place_id, note, updated_by, now),
            )
            if status == "concrete":
                self._conn.execute(
                    "UPDATE council_locations SET place_id=NULL,updated_at=? WHERE slug=?",
                    (now, location_slug),
                )
            else:
                self._conn.execute(
                    "UPDATE council_locations SET place_id=?,ortsbereich_id=?,updated_at=? WHERE slug=?",
                    (place_id, parent_id, now, location_slug),
                )
        self._runtime_places_cache = None
        self._place_aliases_cache = None
        return next(item for item in self.location_candidates("all", limit=500)
                    if item["slug"] == location_slug)

    def delete_location_review(self, location_slug: str) -> bool:
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM council_place_reviews WHERE location_slug=?", (location_slug,))
        if not cur.rowcount:
            return False
        self._runtime_places_cache = None
        self._place_aliases_cache = None
        self.backfill_location_place_ids()
        return True

    def save_decision_locations(self, decision_id: int, rows: list[dict],
                                source_hash: str | None) -> int:
        """Zuordnungen eines Beschlusses atomar ersetzen und ggf. Scanstand merken.

        ``source_hash=None`` speichert sichere Regex-/Bestandsfunde nach einem
        LLM-Fehler, markiert den Vorgang aber nicht als fertig: der nächste
        inkrementelle Lauf versucht die semantische Ergänzung erneut.
        """
        from council.locations import location_slug

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        by_slug: dict[str, dict] = {}
        for row in rows:
            slug = row.get("slug") or location_slug(row.get("name") or "")
            if not slug:
                continue
            if slug not in by_slug or float(row.get("confidence") or 0) > float(by_slug[slug].get("confidence") or 0):
                by_slug[slug] = row
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_decision_locations WHERE decision_id = ?", (decision_id,))
            for slug, row in by_slug.items():
                place = self.resolve_place(row.get("name"))
                parents = self.primary_parents(place)
                primary = parents[0] if len(parents) == 1 else None
                self._conn.execute(
                    "INSERT INTO council_locations"
                    "(slug,name,kind,stadtteil,place_id,ortsbereich_id,updated_at) "
                    "VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT(slug) DO UPDATE SET name=excluded.name, kind=excluded.kind, "
                    "place_id=COALESCE(excluded.place_id,council_locations.place_id), "
                    "ortsbereich_id=COALESCE(excluded.ortsbereich_id,council_locations.ortsbereich_id), "
                    "stadtteil=COALESCE(excluded.stadtteil,council_locations.stadtteil), "
                    "updated_at=excluded.updated_at",
                    (slug, place.name if place else row["name"],
                     "stadtteil" if place and place.is_primary else row.get("kind") or "sonstiges",
                     primary.name if primary else None, place.id if place else None,
                     primary.id if primary else None, now),
                )
                self._conn.execute(
                    "INSERT INTO council_decision_locations "
                    "(decision_id,location_slug,source,evidence,method,confidence,updated_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (decision_id, slug, row.get("source") or "official_text",
                     (row.get("evidence") or row["name"])[:500], row.get("method") or "llm",
                     max(0.0, min(1.0, float(row.get("confidence") or 0))), now),
                )
            if source_hash is not None:
                self._conn.execute(
                    "INSERT INTO council_decision_location_scans(decision_id,source_hash,scanned_at) "
                    "VALUES (?,?,?) ON CONFLICT(decision_id) DO UPDATE SET "
                    "source_hash=excluded.source_hash, scanned_at=excluded.scanned_at",
                    (decision_id, source_hash, now),
                )
        return len(by_slug)

    def reset_decision_location_scans(self) -> None:
        """Vollständigen Neu-Lauf erlauben; Geocodes der Orte bleiben erhalten."""
        with self._conn:
            self._conn.execute("DELETE FROM council_decision_locations")
            self._conn.execute("DELETE FROM council_decision_location_scans")

    def decision_locations(self, decision_id: int) -> list[dict]:
        rows = self._conn.execute(
            """SELECT l.*, dl.source, dl.evidence, dl.method, dl.confidence
               FROM council_decision_locations dl
               JOIN council_locations l ON l.slug = dl.location_slug
               WHERE dl.decision_id = ?
               ORDER BY dl.confidence DESC, l.name""", (decision_id,)).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _place_location_condition(place) -> tuple[str, list]:
        """SQL-Bedingung auf Alias ``l`` für einen kanonischen Katalogort."""
        from council.locations import location_slug

        if place.is_primary:
            return "(l.ortsbereich_id = ? OR l.stadtteil = ?)", [place.id, place.name]
        slugs = list(dict.fromkeys(location_slug(value)
                                   for value in (place.name, *place.aliases)))
        return (f"(l.place_id = ? OR l.slug IN ({','.join('?' * len(slugs))}))",
                [place.id, *slugs])

    def decision_location_place_stats(self) -> list[dict]:
        """Belegte Katalogorte mit Beschlusszahlen, über stabile IDs gruppiert."""
        vote_ph = ",".join("?" * len(self._VOTE_OUTCOMES))
        report_ph = ",".join("?" * len(self._REPORT_OUTCOMES))
        out: list[dict] = []
        for place in self.all_places():
            if not place.filterable:
                continue
            condition, params = self._place_location_condition(place)
            row = self._conn.execute(
                f"""SELECT COUNT(DISTINCT dl.decision_id) AS count,
                           COUNT(DISTINCT CASE WHEN d.outcome IN ({vote_ph})
                                               THEN dl.decision_id END) AS vote_count,
                           COUNT(DISTINCT CASE WHEN d.outcome IN ({report_ph}) OR d.outcome IS NULL
                                               THEN dl.decision_id END) AS report_count
                    FROM council_decision_locations dl
                    JOIN council_locations l ON l.slug = dl.location_slug
                    JOIN council_decisions d ON d.id = dl.decision_id
                    WHERE {condition} AND d.kind = 'decision'""",
                [*self._VOTE_OUTCOMES, *self._REPORT_OUTCOMES, *params],
            ).fetchone()
            if row and row["count"]:
                out.append({"place_id": place.id, "name": place.name,
                            "count": row["count"], "vote_count": row["vote_count"],
                            "report_count": row["report_count"]})
        return out

    def decision_location_district_stats(self) -> list[dict]:
        """Kompatible Statistik der 31 primären Ortsbereiche."""
        primary_ids = {place.id for place in self.all_places() if place.is_primary}
        return [{key: value for key, value in row.items() if key != "place_id"}
                for row in self.decision_location_place_stats()
                if row["place_id"] in primary_ids]

    def location_matches_for_decisions(
        self,
        ids: list[int],
        *,
        district: str = "",
        location_slug: str = "",
        per_decision: int = 4,
    ) -> dict[int, list[dict]]:
        """Belegte Ortslinks eines Suchtreffers innerhalb eines Stadtteils.

        Die Fundstelle wird bewusst mitgeliefert: Der Filter soll nicht nur
        Treffer einschränken, sondern die Ortszuordnung in der Liste
        nachvollziehbar und damit manuell prüfbar machen.
        """
        if not ids or not (district or location_slug):
            return {}
        if location_slug:
            condition, condition_params = "l.slug = ?", [location_slug]
        else:
            place = self.resolve_place(district)
            if not place:
                return {}
            condition, condition_params = self._place_location_condition(place)
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"""SELECT dl.decision_id, l.name, l.stadtteil, l.place_id, l.ortsbereich_id,
                       l.lat, l.lon, dl.source,
                       dl.evidence, dl.method, dl.confidence
                FROM council_decision_locations dl
                JOIN council_locations l ON l.slug = dl.location_slug
                WHERE dl.decision_id IN ({ph}) AND {condition}
                ORDER BY dl.decision_id, dl.confidence DESC, l.name""",
            [*ids, *condition_params],
        ).fetchall()
        out: dict[int, list[dict]] = {}
        for row in rows:
            matches = out.setdefault(row["decision_id"], [])
            if len(matches) < max(1, int(per_decision)):
                matches.append({key: row[key] for key in (
                    "name", "stadtteil", "place_id", "ortsbereich_id", "lat", "lon",
                    "source", "evidence", "method", "confidence"
                )})
        return out

    def decision_ids_for_place(self, place_id: str, limit: int | None = None) -> list[int]:
        """Beschlüsse mit belegtem Bezug zu einem Katalogort, neueste zuerst."""
        place = self.resolve_place(place_id)
        if not place:
            return []
        condition, params = self._place_location_condition(place)
        sql = f"""SELECT DISTINCT dl.decision_id
                  FROM council_decision_locations dl
                  JOIN council_locations l ON l.slug = dl.location_slug
                  JOIN council_decisions d ON d.id = dl.decision_id
                  JOIN council_sessions cs ON cs.ksinr = d.ksinr
                  WHERE {condition} AND d.kind = 'decision'
                  ORDER BY cs.session_date DESC, dl.decision_id DESC"""
        if limit is not None:
            sql += " LIMIT ?"
            params.append(max(1, int(limit)))
        return [row[0] for row in self._conn.execute(sql, params).fetchall()]

    def locations_to_geocode(self, limit: int | None = None) -> list[dict]:
        sql = (
            "SELECT l.slug, l.name, l.kind, COUNT(dl.decision_id) AS n "
            "FROM council_locations l JOIN council_decision_locations dl "
            "ON dl.location_slug = l.slug WHERE l.geo_tried = 0 "
            "GROUP BY l.slug ORDER BY n DESC, l.name"
        )
        args: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            args = (int(limit),)
        return [dict(r) for r in self._conn.execute(sql, args)]

    def apply_curated_location_geocodes(self) -> int:
        """Schwierige Ratsorte vor dem freien Geocoder reproduzierbar verorten."""
        from council import geo
        from council.locations import curated_location_geocodes

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        updates = []
        for slug, point in curated_location_geocodes().items():
            lat, lon = point["lat"], point["lon"]
            stadtteil = geo.ortsbereich_for(lat, lon)
            primary = self.resolve_place(stadtteil)
            updates.append((lat, lon, stadtteil, primary.id if primary else None,
                            now, slug, lat, lon))
        if not updates:
            return 0
        with self._conn:
            before = self._conn.total_changes
            self._conn.executemany(
                """UPDATE council_locations
                   SET lat=?,lon=?,geojson=NULL,stadtteil=?,ortsbereich_id=?,
                       geo_tried=1,updated_at=?
                   WHERE slug=? AND (
                       lat IS NULL OR lon IS NULL OR ABS(lat-?) > 0.00000001
                       OR ABS(lon-?) > 0.00000001)""",
                updates,
            )
            changed = self._conn.total_changes - before
        if changed:
            self._runtime_places_cache = None
        return changed

    def hydrate_location_geo_from_entities(self) -> int:
        """Vorhandene, gleichnamige Entitäts-Geocodes ohne Netzaufruf übernehmen."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn:
            cur = self._conn.execute(
                """UPDATE council_locations
                   SET lat = (SELECT m.lat FROM council_entity_meta m
                              WHERE m.slug = council_locations.slug),
                       lon = (SELECT m.lon FROM council_entity_meta m
                              WHERE m.slug = council_locations.slug),
                       geojson = (SELECT m.geojson FROM council_entity_meta m
                                  WHERE m.slug = council_locations.slug),
                       geo_tried = 1, updated_at = ?
                   WHERE geo_tried = 0 AND EXISTS (
                       SELECT 1 FROM council_entity_meta m
                       WHERE m.slug = council_locations.slug
                         AND m.lat IS NOT NULL AND m.lon IS NOT NULL)""", (now,))
        return cur.rowcount

    def backfill_location_stadtteile(self) -> int:
        """Stadtteil für ältere oder übernommene Ortskoordinaten lokal ableiten."""
        from council import geo

        rows = self._conn.execute(
            "SELECT slug,lat,lon FROM council_locations "
            "WHERE lat IS NOT NULL AND lon IS NOT NULL "
            "AND (stadtteil IS NULL OR stadtteil = '')"
        ).fetchall()
        updates = []
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for row in rows:
            stadtteil = geo.ortsbereich_for(row["lat"], row["lon"])
            if stadtteil:
                from council import places
                place = places.resolve(stadtteil)
                updates.append((stadtteil, place.id if place else None, now, row["slug"]))
        if updates:
            with self._conn:
                self._conn.executemany(
                    "UPDATE council_locations SET stadtteil=?,ortsbereich_id=?,updated_at=? WHERE slug=?",
                    updates,
                )
        return len(updates)

    def backfill_location_place_ids(self) -> int:
        """Katalog- und Eltern-IDs für bestehende Ortsbeobachtungen nachziehen."""
        from council import geo

        rows = self._conn.execute(
            "SELECT slug,name,lat,lon,stadtteil,place_id,ortsbereich_id FROM council_locations"
        ).fetchall()
        updates = []
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for row in rows:
            exact = self.resolve_place(row["name"])
            primary = self.resolve_place(row["stadtteil"])
            if primary and not primary.is_primary:
                primary = None
            if not primary and exact:
                parents = self.primary_parents(exact)
                primary = parents[0] if len(parents) == 1 else None
            if not primary and row["lat"] is not None and row["lon"] is not None:
                primary = self.resolve_place(geo.ortsbereich_for(row["lat"], row["lon"]))
            place_id = exact.id if exact else None
            primary_id = primary.id if primary else None
            primary_name = primary.name if primary else row["stadtteil"]
            if (place_id, primary_id, primary_name) != (
                    row["place_id"], row["ortsbereich_id"], row["stadtteil"]):
                updates.append((place_id, primary_id, primary_name, now, row["slug"]))
        if updates:
            with self._conn:
                self._conn.executemany(
                    "UPDATE council_locations SET place_id=?,ortsbereich_id=?,stadtteil=?,updated_at=? "
                    "WHERE slug=?", updates)
        return len(updates)

    def set_location_geo(self, slug: str, lat: float | None, lon: float | None,
                         geojson: str | None) -> None:
        from council import geo, places

        stadtteil = geo.ortsbereich_for(lat, lon) if lat is not None and lon is not None else None
        primary = places.resolve(stadtteil)
        with self._conn:
            self._conn.execute(
                "UPDATE council_locations SET lat=?, lon=?, geojson=?, stadtteil=?, ortsbereich_id=?, "
                "geo_tried=1, updated_at=? WHERE slug=?",
                (lat, lon, geojson, stadtteil, primary.id if primary else None,
                 datetime.now(timezone.utc).isoformat(timespec="seconds"), slug),
            )

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
                      AVG(COALESCE(d.interest, 50)) AS avg_interest,
                      (SELECT d2.title
                         FROM council_entity_links el2
                         JOIN council_decisions d2 ON d2.id = el2.decision_id
                         JOIN council_sessions cs2 ON cs2.ksinr = d2.ksinr
                        WHERE el2.entity_id = e.id AND cs2.session_date >= ?
                        ORDER BY cs2.session_date DESC, d2.id DESC
                        LIMIT 1) AS latest_title
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
            (cutoff, cutoff, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_entities_geo(self) -> list[dict]:
        """Geocoded entities (points) for the city-wide map — slug, name, kind, n, lat, lon."""
        return [{**dict(r), "target": "thema"} for r in self._conn.execute(
            "SELECT e.slug, e.name, e.kind, e.n, m.lat, m.lon "
            "FROM council_entities e JOIN council_entity_meta m ON m.slug = e.slug "
            "WHERE m.lat IS NOT NULL AND m.lon IS NOT NULL ORDER BY e.n DESC")]

    def location_by_slug(self, slug: str) -> dict | None:
        row = self._conn.execute(
            "SELECT slug,name,kind,lat,lon,place_id,ortsbereich_id FROM council_locations WHERE slug=?",
            (slug,),
        ).fetchone()
        return dict(row) if row else None

    def decision_location_map_points(self, min_decisions: int = 3) -> list[dict]:
        """Belastbare Beschlussorte für die Stadtkarte.

        Konkrete Straßen, Plätze, Gebäude, Gewässer, Anlagen, Bauwerke und
        Verkehrswege werden ab drei Beschlüssen automatisch gezeigt. Unscharfe
        Gebietsbegriffe müssen erst redaktionell freigegeben werden;
        verworfene Kandidaten bleiben draußen.
        """
        rows = self._conn.execute(
            """SELECT l.slug,l.name,l.kind,l.lat,l.lon,l.place_id,l.ortsbereich_id,
                      r.status AS review_status,r.kind AS review_kind,
                      COUNT(DISTINCT dl.decision_id) AS n,
                      MAX(cs.session_date) AS last_date,
                      COUNT(DISTINCT CASE WHEN cs.session_date >= date('now','-12 months')
                                           THEN dl.decision_id END) AS n_recent
               FROM council_locations l
               JOIN council_decision_locations dl ON dl.location_slug=l.slug
               JOIN council_decisions d ON d.id=dl.decision_id AND d.kind='decision'
               JOIN council_sessions cs ON cs.ksinr=d.ksinr
               LEFT JOIN council_place_reviews r ON r.location_slug=l.slug
               WHERE l.lat IS NOT NULL AND l.lon IS NOT NULL
                 AND l.ortsbereich_id IS NOT NULL
               GROUP BY l.slug
               ORDER BY n DESC,l.name"""
        ).fetchall()
        out = []
        for row in rows:
            if row["review_status"] == "rejected":
                continue
            place = self.resolve_place(row["place_id"] or row["name"])
            approved = row["review_status"] in {"approved", "alias"}
            reviewed_concrete = row["review_status"] == "concrete"
            effective_kind = (row["review_kind"] if reviewed_concrete else row["kind"])
            # Flächendeckende Ortsbereiche sind bereits als Filter und Umriss
            # vorhanden; als riesige Sammelpunkte würden sie die exakten Orte
            # überdecken. Kuratierte Teilräume dürfen dagegen auf die Karte.
            catalog_secondary = bool(place and not place.is_primary)
            if not (approved or reviewed_concrete or catalog_secondary or
                    (effective_kind in CONCRETE_LOCATION_KINDS and
                     row["n"] >= max(1, int(min_decisions)))):
                continue
            target = "ort" if place and (approved or catalog_secondary) else "location"
            out.append({
                "slug": row["slug"], "name": place.name if place else row["name"],
                "kind": "beschlussort", "n": row["n"], "lat": row["lat"], "lon": row["lon"],
                "target": target, "place_id": place.id if target == "ort" else None,
                "location_slug": row["slug"], "ortsbereich_id": row["ortsbereich_id"],
                "last_date": row["last_date"], "n_recent": row["n_recent"],
            })
        return out

    def city_map_points(self) -> list[dict]:
        """Themen und Beschlussorte zusammenführen; der präzisere Ortslink gewinnt."""
        by_slug = {row["slug"]: row for row in self.list_entities_geo()}
        for row in self.decision_location_map_points():
            by_slug[row["slug"]] = row
        return sorted(by_slug.values(), key=lambda row: (-row["n"], row["name"]))

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
            keys = _dedup_keys(d.get("title"), d.get("template_number"), d["id"])
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
        """Alle Beschlüsse (id, kvonr, template_number, session_date, committee) der
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
            teile.append("d.template_number = ? OR d.template_number LIKE ?")
            params += [b, b + "-%"]
        rows = self._conn.execute(
            "SELECT d.id, d.kvonr, d.template_number, cs.session_date, cs.committee "
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
            "SELECT id, title, official_text, summary FROM council_decisions").fetchall()
        return [{"id": r["id"],
                 "text": " ".join(x for x in (r["title"], r["official_text"], r["summary"]) if x)}
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

    @classmethod
    def namensteile(cls, anzeige: str) -> tuple[str, str]:
        """„Dr. Ruth Regina Drügemöller" → ``("ruth", "druegemoeller")``.

        (vorname_gefaltet, nachname_gefaltet) — Nachname ist das letzte Token
        (Bindestrich-Namen sind EIN Token), Titel zählen nicht als Vorname.

        Steht hier als Klassenmethode und nicht mehr als Verschachtelung in
        :meth:`personen_lexikon`, weil sie außerhalb gebraucht wird: Wer einen
        Namen **gegen** das Lexikon hält (die Aufsichtsorgane des
        Beteiligungsberichts tun das), muss ihn genauso falten wie das Lexikon
        selbst. Eine zweite, leicht abweichende Faltung träfe an den Umlauten
        und Titeln nichts mehr — und niemand sähe es, weil ein Fehltreffer wie
        ein fehlender Eintrag aussieht.

        Titel-Erkennung mit abgestreiften Satzzeichen (``-Ing`` → ``ing``):
        ``_person_slug`` zerlegt an allem, was kein Buchstabe ist, und sah
        „Ing" deshalb schon immer als Titel — hier zählte der Bindestrich noch
        mit, und „Prof. Dr.-Ing. Manfred Weisensee" bekam den Vornamen „-ing".
        Zwei Faltungen desselben Namens dürfen nicht verschiedene Personen
        sehen: Die eine bildete den Slug ``manfred-weisensee``, die andere
        hielt ihn für einen Namensvetter von „Prof. Dr.-Ing. Weisensee"."""
        toks = [t for t in anzeige.replace(".", " ").split()
                if t.strip("-–—").lower() not in cls._HONORIFICS]
        if not toks:
            return "", ""
        return (cls._falte_namen(toks[0]) if len(toks) > 1 else "",
                cls._falte_namen(toks[-1]))

    #: Funktionsangabe des Beteiligungsberichts, die „diese Person sitzt im
    #: Stadtrat" behauptet — mit optionalem Klammerzusatz, wie ihn der Bericht
    #: auch anderswo führt („1. Kreisrat (Vorsitzender)").
    _FUNKTION_RATSMITGLIED = re.compile(r"(?i)^ratsmitglied(\s*\(.*\))?$")

    @staticmethod
    def _ein_buchstabe_abstand(a: str, b: str) -> bool:
        """Unterscheiden sich die beiden Zeichenketten um höchstens einen
        Buchstaben (Levenshtein ≤ 1)? Gleichheit zählt mit."""
        if abs(len(a) - len(b)) > 1:
            return False
        if len(a) == len(b):
            return sum(x != y for x, y in zip(a, b)) <= 1
        kurz, lang = (a, b) if len(a) < len(b) else (b, a)
        i = 0
        while i < len(kurz) and kurz[i] == lang[i]:
            i += 1
        return kurz[i:] == lang[i + 1:]   # ein Zeichen im langen übersprungen

    @classmethod
    def tippfehler_ratsmitglied(cls, vorname: str, nachname: str,
                                funktion: str | None,
                                nach_paar: dict[tuple[str, str], list[dict]]
                                ) -> dict | None:
        """Der Beteiligungsbericht schreibt ein Ratsmitglied falsch — welcher
        Lexikon-Eintrag ist gemeint? ``None``, wenn die Regel nicht greift.

        Der Bericht ist ein gesetztes PDF und hat Druckfehler: „Claudia
        Oeljeschl**e**ger" (statt -schläger) und „Jens Lükerman" (statt
        -mann). Beide sitzen im Rat und stehen längst im Verzeichnis; der
        strenge Abgleich über Vor- UND Nachnamen findet sie trotzdem nicht,
        und zwei berechtigte Links auf die Personen-Seite gehen verloren.

        Geraten wird trotzdem nicht — geheilt wird nur, wo **alle drei**
        Bedingungen zusammenkommen:

        1. **Der Bericht nennt die Funktion „Ratsmitglied".** Die Quelle
           behauptet also selbst, dass diese Person im Stadtrat sitzt; wir
           suchen dann im Verzeichnis der Ratsmitglieder nach genau der
           Person, die sie meint. Ohne diese Bedingung liefe die Regel über
           alle 116 Namen des Berichts — auch über Beschäftigtenvertretungen
           und Vertreter der Mitgesellschafter, die im Rat gar nichts zu
           suchen haben und deren Nachname zufällig um einen Buchstaben neben
           dem eines Ratsmitglieds liegen darf.
        2. **Der Vorname stimmt exakt.** Ein Druckfehler trifft selten zwei
           Wörter; zwei verschiedene Menschen unterscheiden sich dagegen fast
           immer schon im Vornamen. Ohne diese Bedingung würde aus „Meier"
           ein „Meyer" und aus zwei Familien eine.
        3. **Der Nachname weicht um höchstens einen Buchstaben ab.** Das ist
           die Reichweite eines Druckfehlers — ein fehlendes „n", ein „e"
           statt „ä". Ohne diese Bedingung (etwa bei Abstand 2) fielen
           „Schmidt" und „Schmitz" zusammen.

        Jede Bedingung für sich wäre zu lose: Funktion allein heilte jeden
        Verwechsler unter 300 Ratszeilen, Vorname allein jeden Namensvetter,
        Buchstabenabstand allein jede zufällige Nachbarschaft im Alphabet.
        Zusammen treffen sie Druckfehler und nicht zwei verschiedene Menschen.

        **Mehr als ein Kandidat heißt gescheitert.** Ein fehlender Link ist
        ein fehlender Link; ein falscher ist eine Falschaussage über einen
        namentlich genannten Menschen.
        """
        if not vorname or not nachname:
            return None
        if not (funktion and cls._FUNKTION_RATSMITGLIED.match(funktion.strip())):
            return None
        treffer = [e for (v, n), liste in nach_paar.items()
                   if v == vorname and cls._ein_buchstabe_abstand(n, nachname)
                   for e in liste if e.get("art") == "rat"]
        return treffer[0] if len(treffer) == 1 else None

    def personen_lexikon(self) -> list[dict]:
        """Das Personen-Lexikon für die Badges im Antwort-Text (Tims Wunsch
        12.08.): Ratsmitglieder aus dem Verzeichnis (Partei, Zeitraum,
        Personen-Seite) plus Verwaltungsleute aus den Anwesenheitslisten —
        deren Amt kommt aus den Protokoll-Notizen selbst („Stadtkämmerin",
        „Oberbürgermeister"), nicht aus Weltwissen. `aktiv` heißt: in den
        letzten zwölf Monaten in einer Anwesenheitsliste — dieselbe
        selbstheilende Regel wie bei der Parteien-Zeile; Ehemalige zeigen
        ehrlich nur den belegten Zeitraum.

        Dritte Quelle (Tims Auftrag 17.08.): die Aufsichtsorgane der
        städtischen Gesellschaften aus dem Beteiligungsbericht — Landrätin und
        Kreistagsmitglieder der Gemeinschaftsgesellschaften, Beschäftigten-
        und Mitgesellschafter-Vertretungen. Sie standen bis dahin namenlos da,
        weil sie in keiner Anwesenheitsliste des Stadtrats vorkommen. Ihre
        Rolle ist die **Funktion aus dem Bericht**, ihr Zeitraum sind die
        **Berichtsjahrgänge**, in denen sie vorkommen — mehr ist nicht belegt
        (s. :meth:`_beteiligungs_personen`)."""
        from collections import Counter, defaultdict
        from datetime import date, timedelta
        stichtag = (date.today() - timedelta(days=365)).isoformat()
        namensteile = self.namensteile

        out: list[dict] = []
        gesehen: set[str] = set()
        for m in self.list_members():
            vor, nach = namensteile(m["name"])
            if not nach:
                continue
            gesehen.add(m["slug"])
            out.append({
                "slug": m["slug"], "name": m["name"], "vorname": vor,
                "nachname": nach,
                # „beratend" ist KEIN Ratsmandat: Ausschüsse führen Verbände,
                # Beiräte und Fachleute als beratende Mitglieder. Das Badge
                # sagt das jetzt, statt sie als Ratsleute „parteilos" zu nennen
                # (Tims Skiba-Befund 21.08.2026).
                "art": m["art"], "partei": m["party"],
                "organisation": m["organisation"],
                # Nur bei Wechslern: Wer immer dieselbe Fraktion hatte, ist
                # über `partei` schon erkennbar — und das Lexikon lädt jede
                # Seite mit, also bleibt es schlank (13 Personen im Bestand).
                "phasen": m["phasen"] if len(m["phasen"]) > 1 else None,
                "rolle": ("Beratendes Mitglied"
                          + (f" · {m['organisation']}" if m["organisation"] else "")
                          if m["art"] == "beratend" else None),
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
            sl = self.person_slug(r["name"])
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
            anzeige = self._anzeige_name(e["names"], sl)
            vor, nach = namensteile(anzeige)
            if not nach:
                continue
            out.append({
                "slug": sl, "name": anzeige, "vorname": vor, "nachname": nach,
                "art": "stadt", "partei": None, "organisation": None, "phasen": None,
                "rolle": e["rollen"].most_common(1)[0][0] if e["rollen"] else None,
                "aktiv": bool(e["last"] and e["last"] >= stichtag),
                "von": (e["first"] or "")[:4] or None,
                "bis": (e["last"] or "")[:4] or None,
            })

        # Dritte Quelle: die Aufsichtsorgane des Beteiligungsberichts. Sie
        # kommt NACH Rat und Verwaltung, weil sie nur ergänzen darf, was fehlt
        # — sonst überschriebe ein Aufsichtsratsposten ein Ratsmandat, und aus
        # der Oberbürgermeisterei würde „Vertreter Mitgesellschafter".
        # Verglichen wird über das Namenspaar und nicht über den Slug: Das
        # Verzeichnis führt „Ruth Regina Drügemöller", der Bericht „Ruth
        # Drügemöller" — verschiedene Slugs, derselbe Mensch. Als zweiter
        # Eintrag angelegt, gewönne die Bericht-Schreibweise beim Abgleich der
        # Beteiligungsseite den Stichentscheid und nähme dem Ratsmitglied
        # seine Personen-Seite weg.
        bekannt: dict[tuple[str, str], list[dict]] = {}
        for e in out:
            if e["vorname"]:
                bekannt.setdefault((e["vorname"], e["nachname"]), []).append(e)
        for p in self._beteiligungs_personen():
            if p["slug"] in gesehen or (p["vorname"], p["nachname"]) in bekannt:
                continue
            # Und auch der Druckfehler eines bekannten Ratsmitglieds ist kein
            # neuer Mensch — sonst stünde „Claudia Oeljeschleger" neben
            # „Claudia Oeljeschläger" im Verzeichnis.
            if self.tippfehler_ratsmitglied(p["vorname"], p["nachname"], p["rolle"], bekannt):
                continue
            gesehen.add(p["slug"])
            out.append(p)

        # Blocker (Tims Oltmanns-Befund 12.08.): Gäste, Protokollführung und
        # beratende Mitglieder bekommen NIE ein Badge — aber ihr Nachname macht
        # einen kahlen Nachnamen im Text MEHRDEUTIG. „Herr Oltmanns" (Gast vom
        # Wasserstraßen-Amt, 2019) trug sonst das Badge des einzigen
        # Lexikon-Oltmanns — eines beratenden NABU-Mitglieds von 2026.
        for (name,) in self._conn.execute(
                "SELECT DISTINCT name FROM council_attendance "
                "WHERE role NOT IN ('mitglied','vorsitz','verwaltung') "
                "AND name IS NOT NULL AND name != ''"):
            sl = self.person_slug(name)
            if not sl or sl in gesehen:
                continue
            gesehen.add(sl)
            _, nach = namensteile(self._person_anzeige(name))
            if nach:
                out.append({"slug": sl, "name": None, "vorname": "", "nachname": nach,
                            "art": "blocker", "partei": None, "organisation": None,
                            "phasen": None, "rolle": None,
                            "aktiv": False, "von": None, "bis": None})
        return out

    def _beteiligungs_personen(self) -> list[dict]:
        """Lexikon-Einträge aus den Aufsichtsorganen des Beteiligungsberichts.

        Was hier steht, steht so im amtlichen, veröffentlichten Bericht —
        **Name, Funktion und Berichtsjahrgang, sonst nichts.** Keine Partei
        (der Bericht nennt keine, und aus einem Aufsichtsmandat eine
        Zugehörigkeit zu folgern wäre erfunden), keine Zusammenführung mit
        anderen Quellen, keine Anreicherung. Ein Teil dieser Menschen sind
        Privatpersonen — Betriebsratsvorsitzende, Beschäftigtenvertretungen —,
        und ein Verzeichniseintrag macht auffindbar, was der Bericht nur
        abdruckt. Deshalb genau so viel wie belegt und keine Zeile mehr.

        - ``rolle`` ist die **Funktion aus dem Bericht** („Landrätin",
          „Beschäftigtenvertreter"), die häufigste, wo mehrere dastehen —
          dieselbe Haltung wie bei den Verwaltungsleuten, deren Amt aus den
          Protokoll-Notizen kommt statt aus Weltwissen.
        - ``von``/``bis`` sind **Berichtsjahrgänge**, nicht Amtszeiten: Belegt
          ist nur, in welchen Berichten die Person vorkommt. Wann sie berufen
          wurde, sagt der Bericht nicht.
        - ``aktiv`` heißt „steht im jüngsten eingelesenen Bericht". Die Berichte
          hinken der Gegenwart um Jahre hinterher; die Zwölf-Monats-Regel der
          Anwesenheitslisten träfe hier auf niemanden zu und machte jeden
          amtierenden Aufsichtsrat zum „Ehemaligen".

        Drei Sorten Zeile werden **nicht** zu Personen:

        1. **Entsendungsrechte statt Menschen.** Die TGO Besitz benennt keine
           Personen, sondern Ansprüche: „Vertreter/in der Landessparkasse zu
           Oldenburg". Der Schrägstrich ist das Erkennungszeichen des
           Berichts für diese Form — kein Personenname trägt einen.
        2. **Namen ohne Vornamen.** „Prof. Dr. Bruder" ist derselbe Mensch wie
           „Prof. Dr. Ralph Bruder", zwei Zeilen weiter im selben Bericht —
           aber ein bloßer Nachname ist von einem Namensvetter nicht zu
           unterscheiden. Dieselbe Regel, aus der die Beteiligungsseite ihre
           Links zieht (``_lexikon_zuordnung``).
        3. **Nachnamen unter drei Buchstaben.** Der Bericht ist zweispaltig
           gesetzt, und der Extrakt bricht gelegentlich mitten im Namen um
           („Jens Lükerm an", Bericht 2023). Der Badge-Matcher übergeht solche
           Nachnamen ohnehin — im Verzeichnis wären sie nur ein Mensch, den es
           nicht gibt.
        """
        from collections import Counter, defaultdict
        try:
            rows = self._conn.execute(
                "SELECT bericht_jahr, name, funktion FROM council_gesellschaft_personen "
                "WHERE name IS NOT NULL AND name != ''").fetchall()
        except sqlite3.OperationalError:
            return []
        if not rows:
            return []
        jungster = max(r["bericht_jahr"] for r in rows)

        g: dict = defaultdict(lambda: {"names": Counter(), "rollen": Counter(),
                                       "first": None, "last": None})
        for r in rows:
            name = r["name"]
            if "/" in name:                      # Entsendungsrecht, kein Mensch
                continue
            sl = self.person_slug(name)
            if not sl:
                continue
            e = g[sl]
            e["names"][name] += 1
            if r["funktion"]:
                e["rollen"][r["funktion"]] += 1
            j = r["bericht_jahr"]
            e["first"] = j if e["first"] is None else min(e["first"], j)
            e["last"] = j if e["last"] is None else max(e["last"], j)

        out: list[dict] = []
        for sl, e in g.items():
            anzeige = self._anzeige_name(e["names"], sl)
            vor, nach = self.namensteile(anzeige)
            if not vor or len(nach) < 3:
                continue
            out.append({
                "slug": sl, "name": anzeige, "vorname": vor, "nachname": nach,
                "art": "beteiligung", "partei": None, "organisation": None, "phasen": None,
                "rolle": e["rollen"].most_common(1)[0][0] if e["rollen"] else None,
                "aktiv": e["last"] == jungster,
                "von": str(e["first"]), "bis": str(e["last"]),
            })
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
    def _spricht_diese_person(cls, sprecher: str, vorname: str, nachname: str,
                              bekannte_teile: frozenset[str] = frozenset()) -> bool:
        """Gehört dieser Sprecher-Eintrag zu genau dieser Person?

        Die Protokolle schreiben denselben Menschen mal „Andrea Hufeland", mal
        „Hufeland", mal „Ratsfrau Hufeland" — der Nachname allein muss also
        reichen. Er reicht aber NICHT, wenn der Eintrag einen anderen Vornamen
        trägt: „Dr. Ingo Harms" ist nicht „Tim Harms". Gemessen am Bestand ist
        das selten (5 von 279 Treffern bei Harms), aber auf einer Seite, die
        *alle* Beiträge zeigt, fällt jeder Fremdbeitrag auf.

        Mehrere Sprecher in einem Eintrag („Christoph Baak, Dr. Esther
        Niewerth-Baumann") gelten für beide — da haben tatsächlich beide geredet.

        ``bekannte_teile`` sind Namensteile, die zu **derselben** Person
        gehören, aber nicht in dieser Namensform stehen (s.
        :data:`council.namensformen.GRUPPEN`). Ohne sie fiele „Ratsherr Ebbeke
        Harms" durch die Fremdnamen-Prüfung, obwohl die Person genau die ist,
        deren Seite gerade aufgeschlagen wird.
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
            if (t in nach_teile or t in bekannte_teile
                    or cls._falte_namen(t) in bekannte_teile
                    or t.rstrip(".") in cls._HONORIFICS or t in cls._ANREDEN):
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

        Gesucht wird über **alle** Namensformen der Person (s.
        :data:`council.namensformen.GRUPPEN`): Die Protokolle schreiben denselben
        Menschen in einer Sitzung „Tim Harms" und in der nächsten „Ratsherr
        Ebbeke Harms" — beides gehört auf dieselbe Seite.
        """
        def zerlegen(n: str) -> tuple[str, str] | None:
            teile = [t for t in n.replace(".", " ").replace(",", " ").split()
                     if t.lower().rstrip(".") not in self._HONORIFICS
                     and t.lower() not in self._ANREDEN]
            return (teile[-1], teile[0] if len(teile) > 1 else "") if teile else None

        eigen = zerlegen(name)
        if not eigen:
            return {"items": [], "total": 0, "gesamt": 0, "gremien": []}
        formen: list[tuple[str, str]] = [eigen]
        bekannte_teile: set[str] = set()
        for weitere in self.personen_namensformen(self._person_slug(name)):
            z = zerlegen(weitere)
            if z and z not in formen:
                formen.append(z)
            for t in weitere.replace(".", " ").replace(",", " ").split():
                bekannte_teile.add(t.lower())
                bekannte_teile.add(self._falte_namen(t))
        bekannt = frozenset(bekannte_teile)

        roh: dict = {}
        for nachname in dict.fromkeys(n for n, _ in formen):
            for w in self.wortbeitraege_von_sprecher(nachname, limit=5000):
                roh[w["id"]] = w
        meine = [w for w in roh.values()
                 if any(self._spricht_diese_person(w.get("sprecher") or "", v, n, bekannt)
                        for n, v in formen)]
        meine.sort(key=lambda w: (w.get("session_date") or "", w["id"]), reverse=True)

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
    # Amtstitel gehören mit rein, wenn sie wie ein Vorname direkt VOR dem
    # Namen in der Anwesenheitsliste stehen — „Stadtkämmerin Dr. Julia
    # Figura" statt „Dr. Julia Figura" (Tims Figura-Befund 19.08.: Krogmann
    # bekam sein Stadt-Badge, weil sein voller Vorname im Sprecher-Text
    # stand und die Dublette auflöste — „Dr. Figura" allein hatte dazu
    # keine Chance). Ohne diese Wörter hier entstehen zwei _person_slug()
    # für dieselbe Person: das Frontend sieht zwei Kandidaten für den
    # Nachnamen und verweigert bei fehlendem Vornamen lieber jedes Badge,
    # statt eins zu raten. Dieselbe Wortliste wie in _ROLLEN_RE, nur ohne
    # das optionale „Erste[rn]"-Präfix (das steht nur im note-Feld, nie
    # direkt im name-Feld) — dafür in gefalteter UND ungefalteter Form,
    # weil _person_slug faltet (ä→ae) und namensteile() das nicht tut.
    _HONORIFICS = {"prof", "dr", "dipl", "ing", "med",
                   "herr", "frau", "ratsherr", "ratsfrau",
                   "oberbürgermeister", "oberbürgermeisterin",
                   "oberbuergermeister", "oberbuergermeisterin",
                   "stadtkämmerer", "stadtkämmerin",
                   "stadtkaemmerer", "stadtkaemmerin",
                   "stadtbaurat", "stadtbaurätin", "stadtbauraetin",
                   "stadtrat", "stadträtin", "stadtraetin"}
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

    # --- Eine Person, zwei Namensformen (council.namensformen) ----------------

    def personen_kanon(self) -> dict[str, str]:
        """``{Namensform → kanonische Form}`` für die geführten Gruppen.

        Welche Form kanonisch ist, entscheidet die **jüngste Fundstelle** in
        den Anwesenheitslisten — die Zuordnung selbst ist gepflegt
        (:data:`council.namensformen.GRUPPEN`), die Anzeige nicht. Zieht eine
        Quelle auf eine andere Form um, zieht die Seite beim nächsten
        Protokoll von selbst mit; niemand muss eine Liste von Anzeigenamen
        nachführen.

        Gezählt wird über ``GROUP BY name`` (rund 1.300 verschiedene Namen
        gegenüber 22.000 Zeilen) und je Instanz einmal — die Karte hängt an
        jeder Gruppierung nach Person.
        """
        if self._kanon is None:
            from council import namensformen
            fund: dict[str, tuple[str, int]] = {}
            for r in self._conn.execute(
                    """SELECT a.name, MAX(cs.session_date) d, COUNT(*) n
                       FROM council_attendance a JOIN council_sessions cs ON cs.ksinr = a.ksinr
                       WHERE a.name IS NOT NULL AND a.name != '' GROUP BY a.name"""):
                sl = self._person_slug(r["name"])
                if not sl or not r["d"]:
                    continue
                alt = fund.get(sl)
                fund[sl] = ((max(alt[0], r["d"]), alt[1] + r["n"]) if alt
                            else (r["d"], r["n"]))
            self._kanon = namensformen.kanonisch(fund)
        return self._kanon

    def person_slug(self, name: str) -> str:
        """Slug eines Namens, auf die kanonische Namensform gefaltet.

        Der Ersatz für ``_person_slug`` überall dort, wo nach Person
        **gruppiert** wird. Ohne die Faltung bekäme dieselbe Person zwei
        Einträge im Verzeichnis, zwei Personen-Seiten mit je einem Teil ihrer
        Sitzungen und kein Badge in den KI-Antworten."""
        sl = self._person_slug(name)
        return self.personen_kanon().get(sl, sl)

    def personen_namensformen(self, slug: str) -> list[str]:
        """Die belegten Schreibweisen einer Person, die der kanonischen Form
        zuerst — für Abgleiche, die auf **Namen** laufen statt auf Slugs
        (Wortbeiträge, Suche im Verzeichnis)."""
        kanon = self.personen_kanon()
        ziel = kanon.get(slug, slug)
        gefunden: dict[str, tuple[int, str]] = {}
        for (name,) in self._conn.execute(
                "SELECT DISTINCT name FROM council_attendance "
                "WHERE name IS NOT NULL AND name != ''"):
            sl = self._person_slug(name)
            if kanon.get(sl, sl) != ziel:
                continue
            anzeige = self._person_anzeige(name)
            gefunden.setdefault(anzeige, (0 if sl == ziel else 1, anzeige))
        return [n for n, _ in sorted(gefunden.items(), key=lambda p: p[1])]

    def _anzeige_name(self, namen, slug: str) -> str:
        """Die anzuzeigende Schreibweise aus einem ``Counter`` von Rohnamen.

        Zweistufig: Die **kanonische Namensform** bestimmt, welcher Name
        angezeigt wird (jüngste Fundstelle, s. :meth:`personen_kanon`);
        innerhalb dieser Form entscheidet wie eh und je die häufigste
        Schreibweise, damit ein einzelnes „Dr." mehr oder weniger die Anzeige
        nicht umwirft. Ohne Gruppe ändert sich dadurch nichts."""
        from collections import Counter
        eigene = Counter({n: c for n, c in namen.items()
                          if self._person_slug(n) == slug})
        return self._person_anzeige((eigene or namen).most_common(1)[0][0])

    #: Name des Plenar-Gremiums in den Sitzungsdaten. Es ist der Prüfstein für
    #: ein Ratsmandat (s. list_members) — die Ausschüsse führen daneben
    #: beratende Mitglieder, die dem Rat nicht angehören.
    PLENUM = "Rat"

    #: Wörter, die im Fraktions-Feld nur die ROLLE beschreiben („Beratendes
    #: Mitglied", „beratend", „Verwaltung") — sie benennen keine entsendende
    #: Organisation und taugen deshalb nicht als Herkunfts-Label.
    _ROLLEN_LABEL = re.compile(
        r"^(beratend\w*|beratende[sr]?\s+mitglied\w*|gast|gäste|verwaltung|"
        r"protokoll\w*|stellv\w*|vertretung|mitglied\w*)$", re.IGNORECASE)

    def _organisation_label(self, raw: str | None) -> str | None:
        """Die entsendende Organisation aus einem Anwesenheits-Label —
        „Fridays for Future Oldenburg", „Behindertenbeirat", „Stadtsportbund".
        None für Fraktionen, Rollenwörter und Leerwerte."""
        from council.parties import classify_faction
        if not raw or not raw.strip():
            return None
        label = " ".join(raw.split())
        if classify_faction(label)["kind"] != "unbekannt":
            return None          # Partei, Gruppe oder parteilos — keine Organisation
        if self._ROLLEN_LABEL.match(label):
            return None
        return label

    def _ris_ratsmitglieder(self) -> set[str]:
        """Slugs der Personen, die das RIS selbst als Ratsmitglied führt.
        Zweite Quelle neben der Plenums-Anwesenheit: Nachrücker:innen, die noch
        in keiner Ratssitzung protokolliert sind, gehören trotzdem dazu.
        Das RIS kennt nur die laufende Wahlperiode — frühere Ratsleute trägt
        die Anwesenheit."""
        try:
            rows = self._conn.execute(
                """SELECT DISTINCT p.name FROM council_persons p
                   JOIN council_memberships m ON m.kpenr = p.kpenr
                   WHERE m.rolle LIKE 'Ratsmitglied%' OR m.rolle LIKE 'Grundmandat%'""").fetchall()
        except sqlite3.OperationalError:   # Stammdaten noch nicht geholt
            return set()
        return {self.person_slug(r["name"]) for r in rows}

    def _ris_fraktionen(self) -> dict[str, str]:
        """``{Slug: Fraktion laut RIS-Stammdaten}`` — die Stammdaten führen die
        EINZEL-Partei, wo das Protokoll nur die Gruppe kennt."""
        try:
            rows = self._conn.execute(
                "SELECT name, fraktion_aktuell FROM council_persons "
                "WHERE fraktion_aktuell IS NOT NULL AND fraktion_aktuell != ''").fetchall()
        except sqlite3.OperationalError:
            return {}
        return {self.person_slug(r["name"]): r["fraktion_aktuell"] for r in rows}

    def _partei_der_person(self, slug: str, label: str | None,
                           phasen: dict, ris_fraktion: dict[str, str]) -> str | None:
        """Die Zugehörigkeit, die eine Person WIRKLICH hat — Gruppen-Label der
        bloßen Zusammenschlüsse aufgelöst.

        Ein Mensch ist Mitglied einer Partei, nicht einer Gruppe: „FDP/Volt"
        war ein Zusammenschluss von FDP- und Volt-Leuten, und wer ausschied,
        während es die Gruppe noch gab, blieb im Verzeichnis für immer
        „FDP/Volt" — obwohl er FDP-Mitglied ist (Tims Befund 21.08.2026).
        Aufgelöst wird über belegte Quellen: erst die RIS-Stammdaten, dann die
        eigene Anwesenheits-Historie. Ohne Beleg bleibt das Gruppen-Label
        stehen — geraten wird nicht. „Für Oldenburg" und „IBO/LiVe" sind
        eigenständige Gruppen und bleiben unangetastet (s. AUFLOESBARE_GRUPPEN).
        """
        from council.parties import AUFLOESBARE_GRUPPEN, classify_faction
        if not label:
            return None
        c = classify_faction(label)
        if c["kind"] != "gruppe" or c["label"] not in AUFLOESBARE_GRUPPEN:
            return label
        mitglieds_parteien = set(c["parties"])
        aus_ris = classify_faction(ris_fraktion.get(slug))
        if aus_ris["kind"] == "partei" and aus_ris["label"] in mitglieds_parteien:
            return aus_ris["label"]
        # Eigene Historie, jüngste zuerst: Wer irgendwann unter der Einzelpartei
        # geführt wurde, gehört ihr an.
        for lab, _zeitraum in sorted(phasen.items(), key=lambda kv: kv[1][1], reverse=True):
            if lab in mitglieds_parteien and classify_faction(lab)["kind"] == "partei":
                return lab
        return label

    def _filter_parteien(self, label: str | None) -> list[str]:
        """Unter welchen Filter-Werten diese Person erscheinen soll. Parteien
        und eigenständige Gruppen stehen für sich; ein verbliebenes
        Zusammenschluss-Label („Die Linke/Piraten", wo die Auflösung nichts
        fand) zählt für BEIDE Parteien — die Person verschwindet damit nicht
        aus dem Filter, und ihre Karte nennt weiter das ehrliche Gruppen-Label."""
        from council.parties import AUFLOESBARE_GRUPPEN, classify_faction
        if not label:
            return []
        c = classify_faction(label)
        if c["kind"] == "gruppe" and c["label"] in AUFLOESBARE_GRUPPEN:
            return list(c["parties"])
        return [c["label"]] if c["kind"] in ("partei", "gruppe") else []

    def list_members(self) -> list[dict]:
        """Council members from attendance (role mitglied/vorsitz), grouped by *slug* so
        title variants of the same person ("Dr. X" and "X") merge into ONE entry (and the
        React list gets unique keys). Per person: canonical (most-frequent) name, die
        **letzte aktive Fraktion** (nicht die häufigste — Wechsler wie FDP→Volt oder
        Linke→BSW würden sonst ewig unter der alten laufen), distinct sessions attended
        and committees served. The member directory.

        Zusammengefasst wird über :meth:`person_slug`, also einschließlich der
        Namensformen aus :data:`council.namensformen.GRUPPEN` — sonst stünde
        dieselbe Person zweimal im Verzeichnis, jedes Mal mit einem Teil ihrer
        Sitzungen. ``formen`` nennt die belegten Schreibweisen; das Verzeichnis
        findet damit auch, wer nach der älteren sucht."""
        from collections import Counter, defaultdict
        from council.parties import classify_faction
        rows = self._conn.execute(
            """SELECT a.name, a.ksinr, a.party, cs.committee, cs.session_date
               FROM council_attendance a JOIN council_sessions cs ON cs.ksinr = a.ksinr
               WHERE a.role IN ('mitglied','vorsitz') AND a.name IS NOT NULL AND a.name != ''"""
        ).fetchall()
        g: dict = defaultdict(lambda: {"names": Counter(), "ksinrs": set(), "committees": set(),
                                       "first": None, "last": None, "party_at": None,
                                       "plenum": 0, "org_at": None, "phasen": {}})
        for r in rows:
            sl = self.person_slug(r["name"])
            if not sl:
                continue
            e = g[sl]
            e["names"][r["name"]] += 1
            e["ksinrs"].add(r["ksinr"])
            e["committees"].add(r["committee"])
            if r["committee"] == self.PLENUM:
                e["plenum"] += 1
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
            if p:
                # Jede je belegte Zugehörigkeit mit ihrem Zeitraum: Wer die
                # Fraktion gewechselt hat, wird sonst in alten Protokollzeilen
                # nicht wiedererkannt („Finke (SPD)" ist Vally Finke, auch
                # wenn sie heute für „Für Oldenburg" sitzt).
                von, bis = e["phasen"].get(p, (d, d))
                e["phasen"][p] = (min(von, d), max(bis, d))
            # Entsendende Organisation der beratenden Mitglieder: dasselbe Feld
            # trägt bei ihnen keinen Fraktions-, sondern einen Verbandsnamen.
            org = self._organisation_label(r["party"])
            if org and (e["org_at"] is None or d >= e["org_at"][0]):
                e["org_at"] = (d, org)
        ris = self._ris_ratsmitglieder()
        ris_fraktion = self._ris_fraktionen()
        out = [{"slug": sl, "name": self._anzeige_name(e["names"], sl),
                "formen": sorted({self._person_anzeige(n) for n in e["names"]}),
                "party": self._partei_der_person(
                    sl, e["party_at"][1] if e["party_at"] else None, e["phasen"], ris_fraktion),
                # „beratend" ist KEIN Ratsmandat: Wer je in einer RATSSITZUNG
                # als Mitglied geführt wurde, hat eines — die Ausschüsse führen
                # daneben Verbände, Beiräte und Fachleute (Tims Skiba-Befund
                # 21.08.2026). Das RIS zählt als zweite Quelle für Nachrücker.
                "art": "rat" if (e["plenum"] or sl in ris) else "beratend",
                "organisation": e["org_at"][1] if e["org_at"] else None,
                "phasen": [{"partei": lab, "von": von[:4], "bis": bis[:4]}
                           for lab, (von, bis) in sorted(e["phasen"].items(),
                                                         key=lambda kv: kv[1][0])],
                "n": len(e["ksinrs"]), "committees": len(e["committees"]),
                "first": e["first"], "last": e["last"]}
               for sl, e in g.items()]
        for m in out:
            if m["art"] == "rat":
                m["organisation"] = None   # ein Mandat entsendet niemand
            m["filter_parteien"] = self._filter_parteien(m["party"])
        out.sort(key=lambda m: -m["n"])
        return out

    def member_name(self, slug: str) -> str | None:
        """Der kanonische (häufigste) Name zu einem Slug — die schlanke Auskunft
        für Endpunkte, die nicht das ganze Profil brauchen. Ohne Anrede, wie in
        ``member_detail`` und im Verzeichnis (#419)."""
        from collections import Counter
        slug = self.personen_kanon().get(slug, slug)
        namen = [r["name"] for r in self._conn.execute(
            "SELECT name FROM council_attendance WHERE role IN ('mitglied','vorsitz') "
            "AND name IS NOT NULL AND name != ''")]
        passend = [n for n in namen if self.person_slug(n) == slug]
        return self._anzeige_name(Counter(passend), slug) if passend else None

    def member_detail(self, slug: str) -> dict | None:
        """One member — all name variants merged by slug: party, sessions, active span,
        committees served (with counts and chair flag) and their most recent sessions.

        Der angefragte Slug wird zuerst auf die kanonische Namensform gefaltet
        (:meth:`personen_kanon`): Ein geteilter Link auf die ältere Form führt
        damit auf **dasselbe** Profil, und ``slug`` in der Antwort nennt die
        kanonische Adresse."""
        from collections import Counter
        from council.parties import classify_faction
        slug = self.personen_kanon().get(slug, slug)
        names = [r["name"] for r in self._conn.execute(
            "SELECT DISTINCT name FROM council_attendance WHERE role IN ('mitglied','vorsitz') "
            "AND name IS NOT NULL AND name != ''")]
        matched = [n for n in names if self.person_slug(n) == slug]
        if not matched:
            return None
        ph = ",".join("?" * len(matched))
        name = self._anzeige_name(Counter(  # kanonische Form, darin häufigste Schreibweise
            r["name"] for r in self._conn.execute(
                f"SELECT name FROM council_attendance WHERE name IN ({ph}) AND role IN ('mitglied','vorsitz')",
                matched)), slug)
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
        # Mandat oder beratende Mitwirkung? Dieselbe Unterscheidung wie im
        # Verzeichnis (s. list_members) — und für beratende Mitglieder ist die
        # Fraktions-Zeitreihe gegenstandslos: Ihr Anwesenheits-Label nennt die
        # entsendende Organisation, kein Fraktions-Label. Ohne diese Weiche
        # stand auf ihrer Seite „Ratsmitglied · parteilos" (Tims Befund
        # 21.08.2026) — beides falsch.
        #
        # Bewusst aus den Zeilen DIESER Person statt aus `list_members()`: Das
        # Verzeichnis scannt alle 15.000 Anwesenheitszeilen, und eine
        # Personen-Seite braucht davon genau eine Person. Der Umweg kostete
        # rund 300 ms je Aufruf (gemessen 21.08.2026).
        im_plenum = self._conn.execute(
            f"""SELECT 1 FROM council_attendance a JOIN council_sessions cs ON cs.ksinr = a.ksinr
                WHERE a.name IN ({ph}) AND a.role IN ('mitglied','vorsitz')
                  AND cs.committee = ? LIMIT 1""", matched + [self.PLENUM]).fetchone()
        # `slug` ist hier schon die kanonische Namensform (s. Kopf der Methode).
        art = "rat" if (im_plenum or slug in self._ris_ratsmitglieder()) else "beratend"
        organisation = None
        if art == "beratend":
            timeline = []
            # Jüngstes Label, das eine Organisation nennt (kein Rollenwort).
            for r in self._conn.execute(
                    f"""SELECT a.party FROM council_attendance a
                        JOIN council_sessions cs ON cs.ksinr = a.ksinr
                        WHERE a.name IN ({ph}) AND a.role IN ('mitglied','vorsitz')
                        ORDER BY cs.session_date DESC""", matched):
                organisation = self._organisation_label(r["party"])
                if organisation:
                    break
        aktuell = None
        if timeline:
            letzte = timeline[-1]
            phasen = {t["label"]: (t["first"], t["last"]) for t in timeline}
            aufgeloest = self._partei_der_person(
                slug, letzte["label"], phasen, self._ris_fraktionen())
            aktuell = ({"label": aufgeloest, "kind": "partei", "parties": [aufgeloest]}
                       if aufgeloest != letzte["label"]
                       else {"label": letzte["label"], "kind": letzte["kind"],
                             "parties": letzte["parties"]})
        return {
            "name": name, "slug": slug,
            # Aktuelle Zugehörigkeit (Ende der geglätteten Zeitreihe) — nicht die
            # häufigste: Wechsler (FDP/Volt→Volt, Linke→BSW) zeigen sonst die alte.
            "party": aktuell["label"] if aktuell else None,
            # Der Kopf der Seite nennt dieselbe Zugehörigkeit wie das
            # Verzeichnis: Zusammenschluss-Label aufgelöst, wo es belegt ist
            # („FDP/Volt" → FDP). Die Zeitreihe darunter bleibt quellentreu —
            # sie erzählt, was die Protokolle DAMALS schrieben.
            "current_affiliation": aktuell,
            "art": art,
            "organisation": organisation,
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

    def verwaltung_name(self, slug: str) -> str | None:
        """Kanonischer Name einer Verwaltungsperson zu ihrem Slug — schlanke
        Auskunft für den Wortbeiträge-Endpunkt, ohne den ganzen Lexikon-Aufbau
        aus personen_lexikon(). Gegenstück zu member_name(). Keine
        Rollen-Prüfung hier: Wer einmal einen Steckbrief hatte
        (verwaltung_detail), soll auch weitere Seiten seiner Wortbeiträge
        laden können."""
        from collections import Counter
        namen = [r["name"] for r in self._conn.execute(
            "SELECT name FROM council_attendance WHERE role = 'verwaltung' "
            "AND name IS NOT NULL AND name != ''")]
        passend = [n for n in namen if self._person_slug(n) == slug]
        return self._person_anzeige(Counter(passend).most_common(1)[0][0]) if passend else None

    def verwaltung_detail(self, slug: str) -> dict | None:
        """Schmaler Steckbrief für Verwaltungsleute mit erkanntem Amt (Tims
        Wunsch 19.08., im Anschluss an den Figura-Badge-Fund): NUR für
        Oberbürgermeister/-in, Stadtkämmerer/-in, Stadtbaurat/-rätin,
        Stadtrat/-rätin — dieselbe Erkennung wie in personen_lexikon()
        (_ROLLEN_RE übers note-Feld). Ohne erkanntes Amt gibt es keine Seite:
        „Ein toter Link ist schlimmer als kein Link" (schon in #588 so
        entschieden, für die Aufsichtsräte-Verlinkung).

        Bewusst KEIN Nachbau von member_detail(): Fraktions-Zeitleiste,
        Vorsitz-Zähler und Gremien-Präsenz passen auf ein Mandat, nicht auf
        ein Amt — ein Oberbürgermeister sitzt kraft Amtes in praktisch jedem
        Gremium, das ist keine gewählte Mitgliedschaft. Der Zeitraum ist
        ehrlich als Jahres-Spanne der Protokoll-Erwähnungen beschriftet,
        keine amtliche Amtszeit: SessionNet selbst führt Verwaltung nicht als
        Mandatsträger:innen (council/stammdaten.py:``fetch_mandatstraeger``).

        Nutzt personen_lexikon() statt einer eigenen Aggregation — dieselbe
        Gruppierung für alle Verwaltungsleute an einer Stelle, nicht zwei
        Fassungen, die auseinanderlaufen können."""
        eintrag = next((p for p in self.personen_lexikon()
                        if p["slug"] == slug and p["art"] == "stadt" and p["rolle"]), None)
        if not eintrag:
            return None
        wb = self.wortbeitraege_person(eintrag["name"], limit=10)
        return {
            "typ": "verwaltung", "name": eintrag["name"], "slug": slug,
            "rolle": eintrag["rolle"], "aktiv": eintrag["aktiv"],
            "von": eintrag["von"], "bis": eintrag["bis"],
            "wortbeitraege": wb["items"],
            "wortbeitraege_gesamt": wb["gesamt"],
            "wortbeitraege_gremien": wb["gremien"],
        }

    def decisions_for_amount(self, only_missing: bool = False) -> list[dict]:
        """Main decisions with their text, for the € extraction backfill."""
        sql = "SELECT id, title, official_text FROM council_decisions WHERE kind = 'decision'"
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
    #
    # Die Liste lebt in `council/importance.py` (Blatt-Modul, kein Zirkel) und
    # wird hier nur weitergereicht. Vorher stand sie ausschließlich hier — mit
    # der Folge, dass die drei Geld-Ansichten filterten, das Geld-Signal des
    # Wichtig-Werts aber nicht.
    _NON_SPENDING_TITLES = _importance.NON_SPENDING_TITLES

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
        procedural = {"bericht", "annahme", "vertagung", "kenntnisnahme", "official_text",
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
            keys = _dedup_keys(r["title"], r["template_number"], r["id"])
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
            f"""SELECT d.id, d.title, d.template_number, d.policy_field AS field, d.amount_eur AS eur
                FROM council_decisions d
                WHERE d.kind = 'decision' AND d.amount_eur IS NOT NULL
                      AND d.policy_field IS NOT NULL AND {clauses}
                ORDER BY d.amount_eur DESC""",
            params,
        ).fetchall()
        seen: set = set()
        agg: dict[str, dict] = {}
        for r in rows:
            keys = _dedup_keys(r["title"], r["template_number"], r["id"])
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
            "SELECT factions, policy_field, outcome, no_votes, abstentions "
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
            ["d.title LIKE ? OR d.official_text LIKE ? OR d.summary LIKE ? OR d.policy_tags LIKE ?"] * len(keywords)
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
            f"""SELECT d.id, d.title, d.official_text, d.summary, d.outcome, cs.session_date
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
            "SELECT d.id, d.title, d.summary, d.official_text, sv.stext FROM council_decisions d "
            "LEFT JOIN (SELECT ksinr, parent_item, substr(GROUP_CONCAT(title, ' · '), 1, 400) AS stext "
            "           FROM council_decisions WHERE kind = 'subvote' AND parent_item IS NOT NULL "
            "           GROUP BY ksinr, parent_item) sv "
            "  ON sv.ksinr = d.ksinr AND sv.parent_item = d.item_number "
            "WHERE d.kind = 'decision'"
        ).fetchall()
        out = []
        for r in rows:
            text = f"{r['title'] or ''}. {r['summary'] or r['official_text'] or ''}".strip()[:500]
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
            "SELECT template_number, MIN(text_hash) FROM council_vorlage_embeddings GROUP BY template_number"
        ).fetchall())
        rows = self._conn.execute(
            "SELECT v.template_number, MAX(v.raw_text) AS raw_text FROM council_vorlagen v "
            "WHERE v.status = 'ok' AND v.template_number IN "
            "  (SELECT DISTINCT template_number FROM council_decisions "
            "   WHERE kind = 'decision' AND template_number IS NOT NULL AND template_number != '') "
            "GROUP BY v.template_number"
        ).fetchall()
        out = []
        for r in rows:
            text = r["raw_text"] or ""
            if not text.strip():
                continue
            h = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
            if stored.get(r["template_number"]) != h:
                out.append({"template_number": r["template_number"], "raw_text": text, "text_hash": h})
        return out

    def replace_vorlage_embeddings(self, template_number: str, text_hash: str,
                                   chunks: list[tuple[str, bytes]]) -> None:
        """Chunk-Text+Vektor einer Vorlage komplett ersetzen (alte Chunk-Anzahl
        kann abweichen, deshalb erst löschen)."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_vorlage_embeddings WHERE template_number = ?", (template_number,))
            self._conn.executemany(
                "INSERT INTO council_vorlage_embeddings "
                "(template_number, chunk_idx, text_hash, chunk_text, vector) VALUES (?, ?, ?, ?, ?)",
                [(template_number, i, text_hash, text, vec) for i, (text, vec) in enumerate(chunks)],
            )

    def get_vorlage_embeddings(self) -> list:
        """Alle (template_number, chunk_text, vector)-Zeilen — der Aufrufer baut die Matrix."""
        return self._conn.execute(
            "SELECT template_number, chunk_text, vector FROM council_vorlage_embeddings "
            "ORDER BY template_number, chunk_idx"
        ).fetchall()

    def vorlage_embeddings_version(self) -> tuple:
        """Versionsschlüssel analog embeddings_version(), für den Chunk-Matrix-Cache."""
        count = self._conn.execute(
            "SELECT COUNT(*) FROM council_vorlage_embeddings").fetchone()[0]
        data_version = self._conn.execute("PRAGMA data_version").fetchone()[0]
        return (count, data_version)

    # ---- Anlagen-Embeddings (Task 33, Dokumentenkanal) ---------------------

    def anlagen_missing_embeddings(self, limit: int | None = None) -> list[dict]:
        """Anlagen mit Text, deren Chunk-Vektoren fehlen oder deren Text sich
        geändert hat (SHA-256-Abgleich wie bei den Vorlagen). Neueste zuerst —
        frisches Material zuerst durchsuchbar."""
        import hashlib

        stored = dict(self._conn.execute(
            "SELECT document_id, MIN(text_hash) FROM council_anlage_embeddings "
            "GROUP BY document_id").fetchall())
        # `status = 'ok'` schließt nur ungelesene und kaputte Anlagen aus. Wie
        # der Text entstanden ist — Textebene oder Sehmodell — steht in
        # `ocr_modell` und ist hier KEIN Kriterium: Ein gescannter
        # Wirtschaftsplan ist so durchsuchbar wie ein getippter.
        rows = self._conn.execute(
            "SELECT a.document_id, a.label, a.raw_text, v.template_number, "
            "       v.title AS vorlage_titel FROM council_anlagen a "
            "LEFT JOIN council_vorlagen v ON v.kvonr = a.kvonr "
            "WHERE a.status = 'ok' AND a.raw_text IS NOT NULL AND a.raw_text != '' "
            "ORDER BY a.document_id DESC").fetchall()
        out = []
        for r in rows:
            # HIER wird maskiert und nicht beim Speichern: `raw_text` bleibt
            # vollständig (die Parser brauchen ihn), aber was in die
            # Chunk-Vektoren und damit in Antworten der KI-Frage geht, trägt
            # keine Kontonummern, Telefonnummern, E-Mail-Adressen und
            # Anschriften mehr (`council/kontaktdaten.py`).
            text = maskieren(r["raw_text"])
            # v2 nimmt Metadaten in Hash und Vektor auf. Ohne Vorlagentitel
            # waren gleichnamige Umweltberichte verschiedener Baugebiete kaum
            # zu unterscheiden. Der Hash verwendet den maskierten Text: In
            # Vektoren und Antwortfundstellen gelangen weiterhin keine
            # Kontaktdaten.
            material = "\0".join(("anlage-v2", r["label"] or "",
                                  r["template_number"] or "", r["vorlage_titel"] or "",
                                  text))
            h = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
            if stored.get(r["document_id"]) != h:
                out.append({"document_id": r["document_id"], "label": r["label"],
                            "template_number": r["template_number"],
                            "vorlage_titel": r["vorlage_titel"],
                            "raw_text": text, "text_hash": h})
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
            f"       v.template_number, v.title AS vorlage_titel "
            f"FROM council_anlagen a LEFT JOIN council_vorlagen v ON v.kvonr = a.kvonr "
            f"WHERE a.document_id IN ({ph})", document_ids).fetchall()
        by_id = {r["document_id"]: dict(r) for r in rows}
        return [by_id[i] for i in document_ids if i in by_id]

    def anlagen_metadata_rows(self) -> list[dict]:
        """Kleine Metadatenliste für den lexikalischen Anlagen-Sicherungsweg.

        Volltexte und Vektoren bleiben in ihren spezialisierten Tabellen; für
        exakte Angaben wie „Bodengutachten Kaiserstraße/Bleicherstraße“ reichen
        Label, Vorlagennummer und -titel. Rund 5.000 kompakte Zeilen sind
        billiger als ein zweiter großer Suchindex.
        """
        return [dict(r) for r in self._conn.execute(
            "SELECT a.document_id, a.label, v.template_number, "
            "       v.title AS vorlage_titel FROM council_anlagen a "
            "LEFT JOIN council_vorlagen v ON v.kvonr = a.kvonr "
            "WHERE a.status = 'ok' AND a.raw_text IS NOT NULL AND a.raw_text != '' "
            "ORDER BY a.document_id DESC").fetchall()]

    def decision_ids_for_vorlagen(self, vorlage_nrs: list[str]) -> dict[str, list[int]]:
        """template_number → Beschluss-ids (alle Beratungsstationen), neueste zuerst.
        Bildet Vorlagen-Chunk-Treffer der semantischen Suche auf zitierbare
        Beschlüsse ab."""
        nrs = sorted({(n or "").strip() for n in vorlage_nrs if n and str(n).strip()})
        if not nrs:
            return {}
        ph = ",".join("?" * len(nrs))
        rows = self._conn.execute(
            f"""SELECT d.template_number, d.id FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.template_number IN ({ph})
                ORDER BY cs.session_date DESC, d.id DESC""",
            nrs,
        ).fetchall()
        out: dict[str, list[int]] = {}
        for r in rows:
            out.setdefault(r["template_number"], []).append(r["id"])
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

    #: Themenwörter, die auf einen Teilhaushalt zeigen, ohne dessen Namen zu
    #: teilen. „Kongresshalle" und „Kultur, Museen, Sport" haben keinen
    #: gemeinsamen Wortstamm — rein lexikalisch ist die Zuordnung nicht zu
    #: finden, obwohl sie eindeutig ist. Bewusst knapp gehalten: Jede Zeile
    #: ist eine Behauptung darüber, wo etwas im Haushalt steht.
    HAUSHALTS_SYNONYME = {
        "verkehr": ("mobilität", "radverkehr", "fahrrad", "bus", "parken",
                    "parkgebühren", "straßenbahn", "fußverkehr", "damm"),
        "kultur": ("veranstaltung", "kongress", "halle", "museum", "theater",
                   "bibliothek", "stadion", "schwimmbad", "bäder"),
        "klima": ("baum", "baumschutz", "grünfläche", "natur",
                  "naturschutz", "umweltschutz", "emission"),
        "stadtplanung": ("bebauungsplan", "sanierungsgebiet", "stadtentwicklung",
                         "isek", "flächennutzungsplan", "wohnraum", "leerstand"),
        "schule": ("bildung", "schulbau", "ganztag"),
        "jugend": ("kita", "kindertagesstätte", "krippe"),
    }

    @staticmethod
    def _bereich_passt(bereich: str, woerter: list[str]) -> bool:
        """Trifft eines der Suchwörter diesen Teilhaushalt?

        Der frühere Test lief in die falsche Richtung: ``wort in bereich``
        findet „Verkehr" in „Verkehr und Straßenbau", aber nicht
        „Radverkehr" — und deutsche Suchbegriffe sind fast immer die
        längeren Komposita. Gemessen am 20.08.2026: „Verkehr" traf, aber
        „Mobilitätsplan", „Radverkehr", „Kongresshalle" und
        „Baumschutzsatzung" lieferten allesamt null Zeilen, obwohl es für
        jedes einen passenden Bereich gibt.

        Deshalb wird der Bereichsname in Wortmarken zerlegt und beidseitig
        geprüft — ein Kompositum trägt sein Grundwort am Ende („Radverkehr"),
        eine Ableitung am Anfang („Mobilitätsplan").
        """
        marken = [t for t in re.split(r"[^a-zäöüß]+", bereich.lower()) if len(t) >= 4]
        for wort in woerter:
            for marke in marken:
                if wort == marke:
                    return True
                kurz, lang = sorted((wort, marke), key=len)
                # Nur Anfang oder Ende: „Transport" enthält zwar „sport",
                # aber eben nicht am Rand.
                if len(kurz) >= 5 and (lang.startswith(kurz) or lang.endswith(kurz)):
                    return True
                for kopf, synonyme in CouncilStore.HAUSHALTS_SYNONYME.items():
                    if marke.startswith(kopf) and any(
                            wort.startswith(s) or wort.endswith(s) for s in synonyme):
                        return True
        return False

    def haushalt_fuer_begriffe(self, begriffe: list[str], limit: int = 3) -> list[dict]:
        """Teilhaushalts-Zeilen des neuesten Jahres, deren Bereich zu einem der
        Suchbegriffe passt („Radverkehr" → „Verkehr und Straßenbau"); fragt
        jemand nach dem Haushalt insgesamt, kommt die Summenzeile. Für den
        Geld-Kontext der KI-Frage — Plan-Zahlen, klar getrennt von Beschlüssen."""
        try:
            jahr = self._conn.execute("SELECT MAX(year) FROM council_haushalt").fetchone()[0]
        except sqlite3.OperationalError:
            return []
        if not jahr:
            return []
        # 16 statt 10: Die Begriffe der Gründlichen Recherche kommen aus
        # mehreren Facetten, das treffende Wort steht dort oft weiter hinten.
        woerter = [w.lower() for w in begriffe if len(w) >= 4][:16]
        rows = self._conn.execute(
            "SELECT year, bereich, ertraege, aufwendungen, ergebnis, is_summe "
            "FROM council_haushalt WHERE year = ?", (jahr,)).fetchall()
        out = []
        for r in rows:
            if r["is_summe"]:
                if any(w in ("haushalt", "gesamthaushalt", "haushaltsplan") for w in woerter):
                    out.append(dict(r))
                continue
            if self._bereich_passt(r["bereich"] or "", woerter):
                out.append(dict(r))
        out = out[:limit]
        # Entwicklung mitgeben: derselbe Bereich im ältesten vorhandenen Jahr.
        # Nur bei EXAKT gleichem Namen — die Teilhaushalts-Zuschnitte ändern
        # sich über die Jahre, ein Vergleich über Zuschnittgrenzen wäre falsch.
        if out:
            frueh = self._conn.execute("SELECT MIN(year) FROM council_haushalt").fetchone()[0]
            if frueh and frueh != jahr:
                namen = [r["bereich"] for r in out]
                platz = ",".join("?" * len(namen))
                alt = {
                    r["bereich"]: r for r in self._conn.execute(
                        f"SELECT bereich, ertraege, aufwendungen FROM council_haushalt "
                        f"WHERE year = ? AND bereich IN ({platz})", (frueh, *namen))
                }
                for r in out:
                    a = alt.get(r["bereich"])
                    if a:
                        r["jahr_davor"] = frueh
                        r["aufwendungen_davor"] = a["aufwendungen"]
                        r["ertraege_davor"] = a["ertraege"]
        return out

    #: Suchbegriffe → Steuerart, wie sie im Open-Data-CSV heißt. Bewusst
    #: kuratiert statt Substring-Suche: „Steuer" allein trifft sonst jede Art,
    #: und „Grundsteuer" steckt in „Grundsteuer A+B".
    _STEUER_SYNONYME = {
        "gewerbesteuer": "Gewerbesteuer (-umlage)",
        "gewerbe": "Gewerbesteuer (-umlage)",
        "grundsteuer": "Grundsteuer A+B",
        "grundbesitz": "Grundsteuer A+B",
        "einkommensteuer": "Einkommensteueranteil",
        "einkommenssteuer": "Einkommensteueranteil",
        "umsatzsteuer": "Gemeindeanteil an der Umsatzsteuer",
        "mehrwertsteuer": "Gemeindeanteil an der Umsatzsteuer",
        "vergnügungssteuer": "Vergnügungssteuer",
        "vergnuegungssteuer": "Vergnügungssteuer",
        "getränkesteuer": "Getränkesteuer",
    }

    def steuern_fuer_begriffe(self, begriffe: list[str]) -> list[dict]:
        """IST-Steuereinnahmen zu den gefragten Steuerarten: neuester Wert plus
        der Wert von vor zehn Jahren (Entwicklung), je Art. Fragt jemand
        allgemein nach „Steuern"/„Einnahmen", kommt die Gesamtsumme.

        Klar getrennt vom Haushalt: Das hier sind ABRECHNUNGSZAHLEN, keine
        Planwerte — der Prompt-Baustein muss das benennen."""
        woerter = {w.lower().strip(".,;:!?") for w in begriffe}
        arten: list[str] = []
        for w in woerter:
            art = self._STEUER_SYNONYME.get(w)
            if art and art not in arten:
                arten.append(art)
        if not arten and woerter & {"steuern", "steuereinnahmen", "steuer",
                                    "einnahmen", "steuerkraft"}:
            arten = ["insgesamt"]
        if not arten:
            return []
        try:
            neuestes = self._conn.execute("SELECT MAX(jahr) FROM council_steuern").fetchone()[0]
        except sqlite3.OperationalError:
            return []
        if not neuestes:
            return []
        out: list[dict] = []
        for art in arten[:3]:
            rows = self._conn.execute(
                "SELECT jahr, betrag FROM council_steuern WHERE art = ? AND jahr IN (?, ?)",
                (art, neuestes, neuestes - 10)).fetchall()
            werte = {r["jahr"]: r["betrag"] for r in rows}
            if neuestes not in werte:
                continue
            out.append({"art": art, "jahr": neuestes, "betrag": werte[neuestes],
                        "jahr_davor": neuestes - 10 if (neuestes - 10) in werte else None,
                        "betrag_davor": werte.get(neuestes - 10)})
        return out

    def steuerkraft_kontext(self) -> dict | None:
        """Steuerkraftmesszahl + Schlüsselzuweisungen der beiden jüngsten Jahre.

        Für Fragen nach Hebesätzen und „mehr Steuern einnehmen": Steigt die
        eigene Steuerkraft, sinken die Zuweisungen des Landes (NFAG) — ohne
        diesen Kontext klingt jede Mehreinnahme nach vollem Gewinn."""
        try:
            rows = self._conn.execute(
                "SELECT jahr, messzahl, zuweisungen FROM council_steuerkraft "
                "WHERE messzahl IS NOT NULL AND zuweisungen IS NOT NULL "
                "ORDER BY jahr DESC LIMIT 2").fetchall()
        except sqlite3.OperationalError:
            return None
        if len(rows) < 2:
            return None
        neu, alt = dict(rows[0]), dict(rows[1])
        return {"jahr": neu["jahr"], "messzahl": neu["messzahl"], "zuweisungen": neu["zuweisungen"],
                "jahr_davor": alt["jahr"], "messzahl_davor": alt["messzahl"],
                "zuweisungen_davor": alt["zuweisungen"]}

    # ---- Der Haushalts-Bestand als Quelle der KI-Frage (Tim, 16.08.) -------
    #
    # Bis hierher kannte die KI-Frage drei Geld-Quellen: Plan (council_haushalt),
    # Ist-Steuern (council_steuern) und die NFAG-Mechanik (council_steuerkraft).
    # Der Bestand darunter — Jahresabschlüsse, Produktebene, Prüfberichte,
    # Konzern, Städtevergleich — war für sie unsichtbar.
    #
    # ZWEI REGELN GELTEN FÜR ALLE METHODEN HIER:
    #
    # 1. Jede liefert wenige Zeilen, nicht den Bestand. Der Antwort-Prompt hat
    #    ein Zeichenbudget; ein Baustein, der 377 Produkte anhängt, verdrängt
    #    die Beschlüsse, nach denen gefragt wurde.
    # 2. Jede liefert ihren **Beleg** mit (`_beleg`). Eine Zahl ohne Fundstelle
    #    ist in diesem Bereich keine Zahl, sondern eine Behauptung — und der
    #    Prompt kann nur zitieren, was im Kontext steht.

    @staticmethod
    def _falte_wort(wort: str) -> str:
        """Kleingeschrieben, Umlaute ausgeschrieben, Satzzeichen ab."""
        w = wort.lower().strip(".,;:!?\"'()[]")
        for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
            w = w.replace(a, b)
        return w

    @classmethod
    def _stamm(cls, wort: str) -> str:
        """Grober Wortstamm für den Begriffs-Abgleich — auf 6 Zeichen gekappt.

        Die Kappung ist der ganze Zweck. „Gewerbesteuer" und „Steuern und
        ähnliche Abgaben" haben kein gemeinsames Wort und in der einen
        Richtung auch keine gemeinsame Teilzeichenkette
        (``"steuern" not in "gewerbesteuer"``) — wohl aber denselben Stamm
        ``steuer``. Ohne ihn findet „Warum kam mehr Gewerbesteuer rein?" die
        zugehörige Erläuterung des Jahresabschlusses nicht."""
        return cls._falte_wort(wort)[:6]

    @classmethod
    def _trifft(cls, text: str | None, begriffe: list[str]) -> int:
        """Wie viele Suchbegriffe stecken in ``text``? 0 = kein Treffer.

        BEIDE RICHTUNGEN, und das ist nötig: Der Begriff kann im Text stecken
        („Feuerwehr" in „Brandschutz und Feuerwehr") und der Text im Begriff
        („Steuern" in „Gewerbesteuer"). Eine Richtung allein verfehlt je einen
        der beiden Fälle, und beide kommen im Bestand vor."""
        if not text:
            return 0
        worte = [w for w in re.split(r"[^\wÄÖÜäöüß]+", text) if w]
        text_voll = " ".join(cls._falte_wort(w) for w in worte)
        text_staemme = [s for s in (cls._stamm(w) for w in worte) if len(s) >= 4]
        n = 0
        for b in begriffe:
            b_voll = cls._falte_wort(b)
            b_stamm = cls._stamm(b)
            if len(b_stamm) < 4:
                continue
            if b_stamm in text_voll or any(s in b_voll for s in text_staemme):
                n += 1
        return n

    def _beleg(self, herkunft_id: int | None) -> dict | None:
        """Fundstelle einer Zahl: Dokument, Stelle darin, Stichtag.

        Bewusst ohne die Erklärsätze zu den Proben (``get_herkunft``): Die
        gehören auf die Haushalts-Seiten, wo Platz für sie ist. Im Prompt
        zählt, was die Antwort zitieren können muss — Dokument und Stelle."""
        if herkunft_id is None:
            return None
        try:
            r = self._conn.execute(
                "SELECT label, fundstelle, seite, stand, url FROM council_herkunft "
                "WHERE id = ?", (herkunft_id,)).fetchone()
        except sqlite3.OperationalError:
            return None
        return dict(r) if r else None

    def gebuehren_fuer_begriffe(self, begriffe: list[str],
                                limit_jahre: int = 4) -> dict | None:
        """Gebührenbedarfsberechnungen passend zur Frage, jüngste zuerst.

        Die Tabelle enthält drei getrennte Kalkulationen. Eine Müllfrage
        braucht beide Abfallbereiche, eine Frage zur Straßenreinigung nur
        deren Anlage; bei einer allgemeinen Gebührenfrage kommen alle drei.
        Jede Zeile trägt ihren eigenen Beleg, weil die Bereiche aus
        unterschiedlichen Anlagen stammen.
        """
        worte = {self._falte_wort(w) for w in begriffe if w}
        text = " ".join(sorted(worte))
        bereiche: list[str] = []
        if any(w in text for w in ("abfall", "muell", "tonne", "behaelter",
                                   "restmuell", "biomuell")):
            bereiche.extend(("abfallbehandlung", "abfallsammlung"))
        if any(w in text for w in ("strassenreinig", "kehrgeb", "kehrdienst")):
            bereiche.append("strassenreinigung")
        if not bereiche and any(w in text for w in ("gebuehr", "gebuehrenbedarf")):
            bereiche = ["abfallbehandlung", "abfallsammlung", "strassenreinigung"]
        bereiche = list(dict.fromkeys(bereiche))
        if not bereiche:
            return None
        try:
            platz = ",".join("?" for _ in bereiche)
            rows = [dict(r) for r in self._conn.execute(
                "SELECT jahr, bereich, bereich_name, kostenkalkulation, abzuege, "
                "zu_deckende_kosten, bezugsmenge, bezugseinheit, gebuehr, "
                "gebuehrenvorschlag, template_number, herkunft_id "
                f"FROM council_gebuehren WHERE bereich IN ({platz}) "
                "ORDER BY bereich, jahr DESC", bereiche)]
        except sqlite3.OperationalError:
            return None
        if not rows:
            return None
        gruppen: list[dict] = []
        for bereich in bereiche:
            werte = [r for r in rows if r["bereich"] == bereich][:limit_jahre]
            if not werte:
                continue
            for r in werte:
                r["beleg"] = self._beleg(r.get("herkunft_id"))
            gruppen.append({"bereich": bereich,
                            "bereich_name": werte[0]["bereich_name"],
                            "werte": werte})
        return {"bereiche": gruppen} if gruppen else None

    def ergebnis_ist_fuer_begriffe(self, begriffe: list[str], limit: int = 2) -> dict | None:
        """„Geplant und tatsächlich" aus dem jüngsten Jahresabschluss.

        Der Unterschied zu ``haushalt_fuer_begriffe`` ist das ganze Anliegen:
        Dort stehen Planwerte, hier steht, was daraus geworden ist. Geliefert
        werden die Summenzeilen der Gesamtrechnung (Erträge 12, Aufwendungen
        20) und — wenn die Frage einen Bereich nennt — bis zu ``limit``
        Teilhaushalte.

        ``plan_art`` reist mit: „Plan" heißt 2018 Gesamtermächtigung und 2020
        Ansatz samt Nachtrag. Eine Abweichung ohne ihre Bezugsgröße zu nennen,
        wäre in genau den zwei Jahrgängen falsch, in denen es darauf ankommt."""
        try:
            jahr = self._conn.execute(
                "SELECT MAX(jahr) FROM council_ergebnisrechnung "
                "WHERE ergebnis IS NOT NULL").fetchone()[0]
        except sqlite3.OperationalError:
            return None
        if not jahr:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT thh_nr, thh_name, nr, ansatz, plan, plan_art, ergebnis, deviation, "
            " herkunft_id FROM council_ergebnisrechnung "
            "WHERE jahr = ? AND nr IN (12, 20) ORDER BY thh_nr, nr", (jahr,))]
        if not rows:
            return None

        def paar(teil: list[dict]) -> dict:
            e = next((r for r in teil if r["nr"] == 12), {})
            a = next((r for r in teil if r["nr"] == 20), {})
            # `plan` fällt auf `ansatz` zurück — Zeilen von vor #510 tragen
            # dort NULL (ALTER TABLE füllt nichts nach), s. get_plan_ist.
            return {
                "name": (a.get("thh_name") or e.get("thh_name")),
                "ertraege_plan": e.get("ansatz") if e.get("plan") is None else e.get("plan"),
                "ertraege_ist": e.get("ergebnis"),
                "aufwendungen_plan": a.get("ansatz") if a.get("plan") is None else a.get("plan"),
                "aufwendungen_ist": a.get("ergebnis"),
                "plan_art": a.get("plan_art") or e.get("plan_art"),
                "herkunft_id": a.get("herkunft_id") or e.get("herkunft_id"),
            }

        gesamt = paar([r for r in rows if r["thh_nr"] is None])
        bereiche: list[dict] = []
        if begriffe:
            nach_thh: dict[int, list[dict]] = {}
            for r in rows:
                if r["thh_nr"] is not None:
                    nach_thh.setdefault(r["thh_nr"], []).append(r)
            bewertet = [(self._trifft(t[0].get("thh_name"), begriffe), paar(t))
                        for t in nach_thh.values()]
            bereiche = [b for n, b in sorted(bewertet, key=lambda x: -x[0]) if n][:limit]
        return {"jahr": jahr, "gesamt": gesamt, "bereiche": bereiche,
                "beleg": self._beleg(gesamt.get("herkunft_id"))}

    def abweichungsgruende_fuer_begriffe(self, begriffe: list[str],
                                         limit: int = 3) -> list[dict]:
        """Das *Warum* zu den Abweichungen, in den Worten der Verwaltung.

        Passt kein Begriff, kommen die **größten** Abweichungen: Wer „Warum
        wich der Haushalt ab?" fragt, meint die, über die es sich zu reden
        lohnt — und der Fragetyp-Filter davor sorgt dafür, dass diese Methode
        gar nicht erst läuft, wenn es nicht um Geld geht."""
        try:
            jahr = self._conn.execute(
                "SELECT MAX(jahr) FROM council_abweichungsgruende").fetchone()[0]
        except sqlite3.OperationalError:
            return []
        if not jahr:
            return []
        rows = [dict(r) for r in self._conn.execute(
            "SELECT jahr, nr, bezeichnung, delta_mio, prozent, text, herkunft_id "
            "FROM council_abweichungsgruende WHERE jahr = ? ORDER BY nr", (jahr,))]
        treffer = [(self._trifft(f"{r['bezeichnung']} {r['text']}", begriffe), r) for r in rows]
        passend = [r for n, r in sorted(treffer, key=lambda x: -x[0]) if n][:limit]
        if not passend:
            passend = sorted(rows, key=lambda r: -abs(r.get("delta_mio") or 0))[:limit]
        for r in passend:
            r["beleg"] = self._beleg(r.get("herkunft_id"))
        return passend

    def pruefberichte_fuer_begriffe(self, begriffe: list[str], limit: int = 4) -> dict | None:
        """Feststellungen des Rechnungsprüfungsamts zum jüngsten geprüften
        Jahrgang.

        Ohne Begriffs-Treffer kommen die **wiederholten** Beanstandungen
        zuerst: Etwas, das der Prüfer zum wiederholten Mal aufschreibt, ist der
        Kern der Frage „Was wurde beanstandet?" — eine einmalige Randnotiz
        nicht."""
        try:
            jahr = self._conn.execute(
                "SELECT MAX(jahr) FROM council_pruefberichte").fetchone()[0]
        except sqlite3.OperationalError:
            return None
        if not jahr:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT jahr, marke, marke_name, textziffer, abschnitt, kette, seite, text, "
            " herkunft_id FROM council_pruefberichte WHERE jahr = ? ORDER BY lfd", (jahr,))]
        if not rows:
            return None
        rang = {"WB": 0, "B": 1, "H": 2, "K": 3}
        bewertet = [(self._trifft(f"{r['abschnitt']} {r['text']}", begriffe), r) for r in rows]
        passend = [r for n, r in sorted(bewertet, key=lambda x: -x[0]) if n][:limit]
        if not passend:
            passend = sorted(rows, key=lambda r: rang.get(r["marke"], 9))[:limit]
        # Wie viele Feststellungen es insgesamt gibt, gehört dazu: Ohne die
        # Zahl liest sich eine Auswahl von vier wie der ganze Bericht.
        zaehl: dict[str, int] = {}
        for r in rows:
            zaehl[r["marke_name"]] = zaehl.get(r["marke_name"], 0) + 1
        return {"jahr": jahr, "feststellungen": passend, "gesamt": len(rows),
                "nach_marke": zaehl, "beleg": self._beleg(rows[0].get("herkunft_id"))}

    def produkte_fuer_begriffe(self, begriffe: list[str], limit: int = 4) -> dict | None:
        """Aufgaben der Stadt mit Kosten, Amt, **Rechtsgrundlage** und der
        Spielraum-Selbstauskunft des Plans.

        Die Rechtsgrundlage ist der Grund, warum diese Quelle in der KI-Frage
        etwas kann, das keine andere kann: „Muss die Stadt das Theater
        betreiben?" beantwortet kein Beschluss und keine Haushaltszeile —
        ``auftragsgrundlage`` schon.

        Anders als ``get_produkte(suche=…)`` verlangt diese Suche **nicht**,
        dass jeder Begriff trifft: Die Suchbegriffe kommen aus der
        Query-Expansion und enthalten Synonyme, die absichtlich nicht alle
        passen. Sortiert wird nach Trefferzahl, dann nach Zuschussbedarf."""
        try:
            jahr = self._conn.execute("SELECT MAX(jahr) FROM council_produkte").fetchone()[0]
        except sqlite3.OperationalError:
            return None
        if not jahr:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT produkt_nr, produkt_name, amt, aufwendungen, ergebnis, "
            " kurzbeschreibung, auftragsgrundlage, beeinflussbarkeit, herkunft_id "
            "FROM council_produkte WHERE jahr = ?", (jahr,))]
        bewertet = [(self._trifft(f"{r['produkt_name']} {r.get('amt') or ''} "
                                  f"{r.get('kurzbeschreibung') or ''}", begriffe), r)
                    for r in rows]
        passend = [r for n, r in sorted(bewertet, key=lambda x: (-x[0], x[1].get("ergebnis") or 0))
                   if n][:limit]
        if not passend:
            return None
        for r in passend:
            r["beleg"] = self._beleg(r.get("herkunft_id"))
        return {"jahr": jahr, "produkte": passend}

    def konzern_kontext(self) -> dict | None:
        """Der Konzern Stadt: Erträge, Aufwendungen und die größten Träger.

        Dazu die Kernverwaltung desselben Jahres aus dem Jahresabschluss — die
        Differenz ist der ganze Punkt. „Was kostet die Stadt?" beantwortet der
        Kernhaushalt zu klein, weil Klinikum, Eigenbetriebe und Beteiligungen
        nicht darin stehen."""
        try:
            jahr = self._conn.execute(
                "SELECT MAX(jahr) FROM council_konzern_posten").fetchone()[0]
        except sqlite3.OperationalError:
            return None
        if not jahr:
            return None
        # Über die ROLLE, nicht über die Nummer: Posten 15 ist bis 2018 die
        # Ertragssumme und ab 2019 der Versorgungsaufwand (s. Schema-Kommentar).
        summen = {r["rolle"]: dict(r) for r in self._conn.execute(
            "SELECT rolle, bezeichnung, betrag, herkunft_id FROM council_konzern_posten "
            "WHERE jahr = ? AND rolle IN ('ertraege_summe', 'aufwendungen_summe')", (jahr,))}
        traeger = [dict(r) for r in self._conn.execute(
            "SELECT art, traeger, betrag_teur FROM council_konzern_traeger "
            "WHERE jahr = ? AND art = 'aufwendungen' AND traeger_key != 'konsolidierung' "
            "ORDER BY betrag_teur DESC LIMIT 5", (jahr,))]
        if not summen and not traeger:
            return None
        ertraege = summen.get("ertraege_summe") or {}
        aufwand = summen.get("aufwendungen_summe") or {}
        return {"jahr": jahr, "ertraege": ertraege.get("betrag"),
                "aufwendungen": aufwand.get("betrag"), "traeger": traeger,
                "kern": self.kernverwaltung_ist().get(jahr) or {},
                "beleg": self._beleg(aufwand.get("herkunft_id")
                                     or ertraege.get("herkunft_id"))}

    def staedtevergleich_kontext(self, reihe: str = "steuerkraft") -> dict | None:
        """Die jüngste Kennzahl einer Reihe für alle acht kreisfreien Städte.

        Eine Kennzahl, nicht alle: Der Vergleich soll die Antwort einordnen
        („Oldenburg liegt auf Platz 5 von 8"), nicht eine Tabelle in den
        Prompt schreiben."""
        try:
            jahr = self._conn.execute(
                "SELECT MAX(jahr) FROM council_staedtevergleich WHERE reihe = ?",
                (reihe,)).fetchone()[0]
        except sqlite3.OperationalError:
            return None
        if not jahr:
            return None
        kennzahl = self._conn.execute(
            "SELECT kennzahl FROM council_staedtevergleich WHERE reihe = ? AND jahr = ? "
            "GROUP BY kennzahl ORDER BY COUNT(*) DESC, kennzahl LIMIT 1",
            (reihe, jahr)).fetchone()
        if not kennzahl:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT stadt, wert, einheit, herkunft_id FROM council_staedtevergleich "
            "WHERE reihe = ? AND jahr = ? AND kennzahl = ? ORDER BY wert DESC",
            (reihe, jahr, kennzahl[0]))]
        if not rows:
            return None
        return {"jahr": jahr, "reihe": reihe, "kennzahl": kennzahl[0],
                "einheit": rows[0].get("einheit"), "staedte": rows,
                "beleg": self._beleg(rows[0].get("herkunft_id"))}

    def ansatz_fuer_begriffe(self, begriffe: list[str], limit: int = 4) -> dict | None:
        """Einnahme- und Ausgabearten des jüngsten **Planjahres** aus dem
        Gesamtergebnishaushalt.

        Nur ``art='ansatz'``: Die Finanzplanungsjahre desselben Dokuments sind
        eine Vorausschau nach § 8 NKomVG und kein beschlossener Haushalt. Sie
        in einen Antwort-Kontext zu legen hieße, dem Modell einen Plan für
        2029 anzubieten, den nie jemand aufgestellt hat."""
        try:
            jahr = self._conn.execute(
                "SELECT MAX(jahr) FROM council_ergebnishaushalt "
                "WHERE art = 'ansatz'").fetchone()[0]
        except sqlite3.OperationalError:
            return None
        if not jahr:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT nr, bezeichnung, betrag, ist_summe, herkunft_id "
            "FROM council_ergebnishaushalt WHERE jahr = ? AND art = 'ansatz' ORDER BY nr",
            (jahr,))]
        if not rows:
            return None
        bewertet = [(self._trifft(r["bezeichnung"], begriffe), r) for r in rows]
        passend = [r for n, r in sorted(bewertet, key=lambda x: -x[0]) if n][:limit]
        if not passend:
            # Ohne Treffer die Summenzeilen — sie beantworten „was nimmt die
            # Stadt ein, was gibt sie aus" und sind nie daneben.
            passend = [r for r in rows if r["ist_summe"]][:limit]
        if not passend:
            return None
        return {"jahr": jahr, "posten": passend,
                "beleg": self._beleg(passend[0].get("herkunft_id"))}

    # ---- Vier Schichten, die die KI-Frage nicht kannte (Tim, 17.08.) -------
    #
    # Der Bestand ist seit der Runde oben um vier Schichten gewachsen, und die
    # KI-Frage beantwortete deren Fragen mit den Quellen, die sie schon kannte
    # — also falsch:
    #
    #   „Wie viel Schulden hat Oldenburg?"      → Ergebnishaushalt. Schulden
    #        sind ein BESTAND am Stichtag, kein Jahresverlauf; in der
    #        Ergebnisrechnung stehen sie überhaupt nicht.
    #   „Was wird gebaut?"                      → Ergebnishaushalt, in dem
    #        keine einzige Investition steht (ein Schulneubau taucht dort nur
    #        als Abschreibung auf, verteilt über Jahrzehnte).
    #   „Wie viele Stellen sind unbesetzt?"     → Personalaufwendungen in Euro.
    #   „Wer wollte den Haushalt ändern?"       → gar nichts, obwohl 664
    #        Änderungslisten im Bestand liegen.
    #
    # Es gelten dieselben zwei Regeln wie für den Abschnitt darüber: wenige
    # Zeilen statt Bestand, und jede Zahl mit ihrem Beleg.

    def schulden_kontext(self) -> dict | None:
        """Der Schuldenstand: jüngstes Jahr, Vorjahr, höchster Stand der Reihe.

        Ein **Bestand**, kein Jahresverlauf — und genau deshalb eine eigene
        Quelle. Der Haushaltsplan sagt, was die Stadt in einem Jahr einnimmt
        und ausgibt; was am 31.12. an Krediten offen ist, sagt er nicht.

        Die Abgrenzung reist als Feld mit (``council.schulden.ABGRENZUNG``)
        und ist nicht schmückendes Beiwerk: Gezählt wird die Stadt als
        Rechtsträger — Kernhaushalt und Eigenbetriebe, ohne die rechtlich
        selbstständigen Beteiligungen. Die Konzern-Zahl heißt genauso und ist
        ein Vielfaches; ohne den Satz daneben ist „337 Mio. €" eine von zwei
        Zahlen, die beide so heißen.

        Die vier Artenspalten dürfen NULL sein (Fall 2022, s.
        ``council/schulden.py``) — dann kommt die Aufteilung nicht mit, und
        ``aufteilung_verworfen`` sagt, warum.
        """
        from council import schulden as _schulden

        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_schulden ORDER BY jahr")]
        except sqlite3.OperationalError:
            return None
        if not rows:
            return None
        neu = rows[-1]
        arten = [(titel, neu[feld]) for feld, titel in _schulden.SPALTEN
                 if feld not in ("insgesamt", "je_einwohner")
                 and neu.get(feld) is not None]
        # Der höchste Stand der Reihe ist eine Angabe der Daten, keine
        # Bewertung: Er sagt, ob die jüngste Zahl im historischen Vergleich
        # oben oder unten liegt — sonst schwebt sie ohne jeden Maßstab.
        hoch = max(rows, key=lambda r: r["insgesamt"])
        return {
            "jahr": neu["jahr"],
            "insgesamt": neu["insgesamt"],
            "je_einwohner": neu.get("je_einwohner"),
            "arten": arten,
            "aufteilung_verworfen": neu.get("aufteilung_verworfen"),
            "revidiert": bool(neu.get("revidiert")),
            "davor": ({"jahr": rows[-2]["jahr"], "insgesamt": rows[-2]["insgesamt"]}
                      if len(rows) > 1 else None),
            "hoch": ({"jahr": hoch["jahr"], "insgesamt": hoch["insgesamt"]}
                     if hoch["jahr"] != neu["jahr"] else None),
            "reihe_ab": rows[0]["jahr"],
            "abgrenzung": _schulden.ABGRENZUNG,
            "beleg": self._beleg(neu.get("herkunft_id")),
            "weitere": self._schulden_abgrenzungen(),
            "buergschaften": self._buergschafts_kontext(),
        }

    def haushalts_anschluss(self, beschluss_id: int, template_number: str | None) -> dict | None:
        """Wo dieser Beschluss im Haushalts-Bereich wieder auftaucht.

        Die Beschluss-Seite verweist seit H-21 auf den Haushalt — aber
        pauschal („wie sich das im Gesamthaushalt ausnimmt"). Das ist für
        jeden Beschluss derselbe Satz und deshalb für keinen eine Auskunft.

        Hier steht nur, was **belegt** ist. Zwei Fälle gibt es im Bestand, und
        beide hängen an einer echten Verknüpfung, nicht an einer Textsuche:

        * **Nachbewilligung** — ``council_nachbewilligungen.beschluss_id``
          zeigt auf genau diese Zeile. Der Betrag steht dann in der
          Jahressumme, die ``/haushalt/plan-ist`` zeigt.
        * **Bürgschaft** — die Vorlage steht im Zeitstrahl auf
          ``/haushalt/schulden``.

        Trifft keiner der beiden zu, kommt ``None`` — und die Seite lässt die
        Karte weg, statt einen Satz zu zeigen, der überall gleich stünde.
        """
        try:
            r = self._conn.execute(
                "SELECT template_number, titel, betrag, jahr FROM council_nachbewilligungen "
                "WHERE beschluss_id = ? LIMIT 1", (beschluss_id,)).fetchone()
        except sqlite3.OperationalError:
            r = None
        if r:
            return {"art": "nachbewilligung", "href": "/haushalt/plan-ist",
                    "jahr": r["jahr"], "betrag": r["betrag"],
                    "titel": r["titel"], "template_number": r["template_number"]}

        if template_number:
            try:
                b = self._conn.execute(
                    "SELECT title FROM council_vorlagen "
                    "WHERE template_number = ? AND title LIKE '%bürgschaft%'",
                    (template_number,)).fetchone()
            except sqlite3.OperationalError:
                b = None
            if b:
                return {"art": "buergschaft", "href": "/haushalt/schulden",
                        "titel": b["title"], "template_number": template_number}
        return None

    def buergschafts_vorlagen(self, limit: int = 40) -> list[dict]:
        """Die Ratsbeschlüsse hinter dem Bürgschaftsbestand, neueste zuerst.

        DIESE BETRÄGE DÜRFEN NIE ADDIERT WERDEN, und die Liste selbst zeigt
        warum: Unter den 21 Vorlagen im Bestand ist „Verlängerung
        Ausfallbürgschaft … über 300.000 Euro für die Volkshochschule"
        (25/0826) dieselbe Bürgschaft wie 23/0112 zwei Jahre zuvor, und
        „Anpassung Ausfallbürgschaft … Weser-Ems Halle" (25/0929) ändert eine
        bestehende. Eine Summe über die Liste zählte dieselbe Zusage mehrfach.

        Was der Bestand wirklich ist, sagt nur der Jahresabschluss
        (``council_buergschaften``) — er ist eine Stichtagsgröße und keine
        Summe von Beschlüssen. Die Liste hier ist die **Geschichte** dazu:
        wann der Rat worüber entschieden hat.

        Je Vorlage der jüngste Beschluss: Finanzausschuss und Rat entscheiden
        dieselbe Sache, und zwei Zeilen für einen Vorgang wären eine Dublette
        ohne Erkenntnisgewinn.
        """
        try:
            rows = self._conn.execute(
                """SELECT v.template_number, v.title, v.document_url,
                          MAX(s.session_date) AS datum,
                          (SELECT d2.id FROM council_decisions d2
                            JOIN council_sessions s2 ON s2.ksinr = d2.ksinr
                           WHERE d2.template_number = v.template_number
                           ORDER BY s2.session_date DESC LIMIT 1) AS beschluss_id
                     FROM council_vorlagen v
                     LEFT JOIN council_decisions d ON d.template_number = v.template_number
                     LEFT JOIN council_sessions s ON s.ksinr = d.ksinr
                    WHERE v.title LIKE '%bürgschaft%'
                    GROUP BY v.template_number
                    ORDER BY datum DESC NULLS LAST, v.template_number DESC
                    LIMIT ?""", (limit,)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def _schulden_abgrenzungen(self) -> list[dict]:
        """Die ANDEREN beiden Zahlen, die auch „die Schulden der Stadt" heißen.

        Es gibt drei, sie unterscheiden sich um das Siebzehnfache, und jede
        ist für ihre Abgrenzung richtig (Stand 31.12.2024):

        * **43,7 Mio. €** — die Geldschulden des Kernhaushalts allein, wie sie
          in der Bilanz des Jahresabschlusses stehen.
        * **294,9 Mio. €** — die Stadt als Rechtsträger, also mit ihren
          Eigenbetrieben. Das ist die Reihe des Statistischen Jahrbuchs, die
          Zahl im Block darüber.
        * **740,3 Mio. €** — der ganze „Konzern Stadt", anteilig nach
          Beteiligungshöhe, aus dem Tabellenband der Statistischen Ämter.

        Ohne diese Liste beantwortet die KI-Frage „Wie hoch sind die Schulden?"
        mit **einer** Zahl, und welche das ist, entscheidet der Zufall der
        Facette. Die drei nebeneinander sind die ehrliche Antwort — addiert
        werden dürfen sie nie, sie enthalten einander.
        """
        aus: list[dict] = []
        try:
            r = self._conn.execute(
                "SELECT jahr, wert FROM council_bilanz WHERE rolle = 'geldschulden' "
                "ORDER BY jahr DESC LIMIT 1").fetchone()
            if r:
                aus.append({"art": "Kernhaushalt (nur Geldschulden)", "jahr": r["jahr"],
                            "betrag": r["wert"],
                            "quelle": "Bilanz des Jahresabschlusses"})
        except sqlite3.OperationalError:
            pass
        try:
            r = self._conn.execute(
                "SELECT jahr, insgesamt FROM council_integrierte_schulden "
                "ORDER BY jahr DESC LIMIT 1").fetchone()
            if r:
                aus.append({"art": "Konzern Stadt (anteilig, mit Beteiligungen)",
                            "jahr": r["jahr"], "betrag": r["insgesamt"],
                            "quelle": "Integrierte Schulden der Statistischen Ämter"})
        except sqlite3.OperationalError:
            pass
        return aus

    def bilanz_kontext(self) -> dict | None:
        """Was der Stadt gehört und wem es zusteht — der jüngste Stichtag.

        Die Bilanz ist die einzige Quelle des Bereichs, die einen **Stichtag**
        zählt und kein Jahr. Ihre Beträge mit Erträgen oder Aufwendungen zu
        verrechnen wäre der Fehler, gegen den diese Methode gebaut ist: „Die
        Stadt hat 1,48 Mrd. €" und „die Stadt gibt 799 Mio. € aus" sind zwei
        Sätze über zwei verschiedene Dinge.
        """
        try:
            jahr = self._conn.execute(
                "SELECT MAX(jahr) AS j FROM council_bilanz").fetchone()
        except sqlite3.OperationalError:
            return None
        if not jahr or jahr["j"] is None:
            return None
        jahr = jahr["j"]
        posten = {r["rolle"]: r["wert"] for r in self._conn.execute(
            "SELECT rolle, wert FROM council_bilanz WHERE jahr = ? AND rolle IS NOT NULL",
            (jahr,))}
        aktiva = ("immaterielles_vermoegen", "sachvermoegen", "finanzvermoegen",
                  "liquide_mittel", "aktive_rap")
        summe = sum(posten[r] for r in aktiva if r in posten) or None
        beleg = self._conn.execute(
            "SELECT herkunft_id FROM council_bilanz WHERE jahr = ? LIMIT 1",
            (jahr,)).fetchone()
        return {
            "jahr": jahr,
            "bilanzsumme": summe,
            "posten": [(r, posten[r]) for r in
                       ("sachvermoegen", "infrastrukturvermoegen", "finanzvermoegen",
                        "liquide_mittel", "nettoposition", "sonderposten",
                        "rueckstellungen", "pensionsrueckstellungen", "schulden")
                       if r in posten],
            "beleg": self._beleg(beleg["herkunft_id"] if beleg else None),
        }

    def kassensicht_kontext(self) -> dict | None:
        """Was tatsächlich geflossen ist — die Finanzrechnung (Abschnitt 4.1).

        Die zweite Rechnung desselben Jahresabschlusses, und sie kann der
        ersten scheinbar widersprechen: Für 2024 weist die Ergebnisrechnung
        einen Überschuss aus und die Finanzrechnung einen Fehlbetrag an
        Finanzmitteln. Beides stimmt — die eine bucht, wenn ein Anspruch
        entsteht, die andere, wenn Geld fließt. Ohne die zweite Zahl entsteht
        ein falscher Eindruck, und zwar in beide Richtungen.
        """
        try:
            jahr = self._conn.execute(
                "SELECT MAX(jahr) AS j FROM council_finanzrechnung").fetchone()
        except sqlite3.OperationalError:
            return None
        if not jahr or jahr["j"] is None:
            return None
        jahr = jahr["j"]
        zeilen = [dict(r) for r in self._conn.execute(
            "SELECT nr, bezeichnung, ergebnis, rolle, herkunft_id "
            "FROM council_finanzrechnung WHERE jahr = ? ORDER BY nr", (jahr,))]
        if not zeilen:
            return None
        # Nur die Summenzeilen: Die Einzelposten sind die Ertragsarten und
        # stehen schon im Ergebnisrechnungs-Block.
        summen = [z for z in zeilen if z.get("rolle")]
        return {"jahr": jahr,
                "zeilen": [(z["bezeichnung"], z["ergebnis"], z["rolle"]) for z in summen],
                "beleg": self._beleg(zeilen[0].get("herkunft_id"))}

    def nachbewilligungen_kontext(self, jahr: int | None = None) -> dict | None:
        """Was beschlossen wurde, NACHDEM der Haushalt beschlossen war (§ 117).

        Die Zahl, die der Haushaltsplan nicht kennt und der Jahresabschluss
        nur als Summe zeigt. Sie ist außerdem die einzige Stelle, an der
        sichtbar wird, wie viel der Rat selbst entschieden hat: 2022 waren es
        89 % der Nachbewilligungen, 2024 nur noch 73 %.
        """
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_nachbewilligung_jahre ORDER BY jahr")]
        except sqlite3.OperationalError:
            return None
        if not rows:
            return None
        zeile = next((r for r in rows if r["jahr"] == jahr), rows[-1])
        kanaele = []
        try:
            kanaele = [(r["kanal"], r["betrag_konsumtiv"], r["betrag_investiv"])
                       for r in self._conn.execute(
                           "SELECT kanal, betrag_konsumtiv, betrag_investiv "
                           "FROM council_nachbewilligung_kanaele WHERE jahr = ?",
                           (zeile["jahr"],))]
        except sqlite3.OperationalError:
            pass
        return {"jahr": zeile["jahr"],
                "konsumtiv": zeile.get("summe_konsumtiv"),
                "investiv": zeile.get("summe_investiv"),
                "gesamt": (zeile.get("summe_konsumtiv") or 0)
                          + (zeile.get("summe_investiv") or 0),
                "verpflichtungen": zeile.get("verpflichtungen_betrag"),
                "kanaele": kanaele,
                "probe_text": zeile.get("probe_text") if not zeile.get("probe_ok") else None,
                "beleg": self._beleg(zeile.get("herkunft_id"))}

    def kennzahlen_kontext(self, limit: int = 13) -> dict | None:
        """Die dreizehn Kennzahlen — jeweils der jüngste Stand, mit Rechenweg.

        Die einzige Quelle des Bereichs, die ihre eigenen Formeln mitliefert.
        Deshalb darf die Antwort eine Quote nennen, ohne sie zu erfinden — und
        deshalb steht der Rechenweg im Kontext, nicht nur der Wert.

        ``korrekturen`` sind die Stellen, an denen ein späterer Bericht eine
        Zahl still geändert hat. Wer nach der Steuerquote 2021 fragt, soll
        nicht die erste gedruckte Fassung bekommen, ohne dass jemand sagt,
        dass es eine zweite gab.
        """
        from council import kennzahlen as _kz

        staende = self.get_kennzahlen()
        if not staende:
            return None
        reihe = _kz.neueste(staende)
        _, funde = _kz.ueberlappungsprobe(staende)
        formeln = {}
        for f in self.get_kennzahl_formeln():
            formeln[f["kennzahl"]] = f["formel"]
        juengstes = max(z["jahr"] for z in reihe)
        aktuell = [z for z in reihe if z["jahr"] == juengstes][:limit]
        label = {k.key: k.label for k in _kz.KENNZAHLEN}
        einheit = {k.key: k.einheit for k in _kz.KENNZAHLEN}
        return {
            "jahr": juengstes,
            "werte": [(label.get(z["kennzahl"], z["kennzahl"]), z["wert"],
                       einheit.get(z["kennzahl"], "eur"), z["stellen"],
                       formeln.get(z["kennzahl"]))
                      for z in aktuell],
            # Mit Einheit, damit der Prompt-Baustein „45,90 %" schreiben kann
            # und nicht „45.9" — im deutschen Fließtext ist das ein Zahlwort
            # mit falschem Trennzeichen und ohne Einheit.
            "korrekturen": [(label.get(f["kennzahl"], f["kennzahl"]), f["jahr"],
                             f["alt"], f["alt_bericht"], f["neu"], f["neu_bericht"],
                             einheit.get(f["kennzahl"], "eur"))
                            for f in funde if f["art"] == "revision"],
            "beleg": self._beleg(aktuell[0].get("herkunft_id") if aktuell else None),
        }

    def _buergschafts_kontext(self) -> dict | None:
        """Wofür die Stadt geradesteht — die Zahl, die in keiner Schuldenreihe steht.

        Eine Bürgschaft kostet nichts, solange sie nicht gezogen wird, und
        taucht deshalb in keiner der drei Schuldenzahlen auf. Ende 2024 waren
        es 220,3 Mio. € — das Fünffache der eigenen Geldschulden des
        Kernhaushalts. Wer nach den Schulden fragt, bekommt das dazu, aber
        ausdrücklich als **eigene** Größe: Eine Bürgschaft ist keine Schuld.
        """
        try:
            r = self._conn.execute(
                "SELECT jahr, bestand, grund, herkunft_id FROM council_buergschaften "
                "ORDER BY jahr DESC LIMIT 1").fetchone()
        except sqlite3.OperationalError:
            return None
        if not r:
            return None
        rueck = None
        try:
            z = self._conn.execute(
                "SELECT wert FROM council_bilanz WHERE rolle = 'buergschaftsrueckstellung' "
                "AND jahr = ?", (r["jahr"],)).fetchone()
            rueck = z["wert"] if z else None
        except sqlite3.OperationalError:
            pass
        return {"jahr": r["jahr"], "bestand": r["bestand"], "grund": r["grund"],
                "rueckstellung": rueck, "beleg": self._beleg(r["herkunft_id"])}

    def investitionen_fuer_begriffe(self, begriffe: list[str],
                                    limit: int = 3) -> dict | None:
        """Was die Stadt bauen und kaufen will — Summenzeile und die
        Teilhaushalte, die zur Frage passen.

        Die andere Hälfte des Haushaltsplans. Sie mit dem Ergebnishaushalt in
        einem Satz zu verrechnen wäre der Fehler, gegen den diese Methode
        gebaut ist: Es sind zwei Haushalte mit zwei Zahlenwerken.

        Geliefert wird die **Summenzeile der Datei** (``ebene``
        ``investitionen``) — das Ziel der Rechenprobe, nicht unsere Addition.
        Der *Gesamtbetrag des Finanzhaushaltes* (``ebene``
        ``finanzhaushalt``) bleibt bewusst draußen: Er zählt die laufende
        Verwaltungstätigkeit mit, ist von keiner Probe der Datei gedeckt und
        stünde im Prompt direkt neben einer geprüften Zahl.
        """
        try:
            jahr = self._conn.execute(
                "SELECT MAX(jahr) FROM council_investitionen "
                "WHERE ebene = 'investitionen'").fetchone()[0]
        except sqlite3.OperationalError:
            return None
        if not jahr:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT ebene, thh_nr, bezeichnung, einzahlungen, auszahlungen, herkunft_id "
            "FROM council_investitionen WHERE jahr = ? AND ebene IN "
            "('investitionen', 'teilhaushalt') ORDER BY thh_nr", (jahr,))]
        gesamt = next((r for r in rows if r["ebene"] == "investitionen"), None)
        if not gesamt:
            return None
        teile = [r for r in rows if r["ebene"] == "teilhaushalt"]
        bewertet = [(self._trifft(r["bezeichnung"], begriffe), r) for r in teile]
        passend = [r for n, r in sorted(bewertet, key=lambda x: -x[0]) if n][:limit]
        if not passend:
            # Ohne Begriffs-Treffer die größten Brocken: „Was wird gebaut?"
            # meint die, über die zu reden sich lohnt.
            passend = sorted(teile, key=lambda r: -(r["auszahlungen"] or 0))[:limit]
        return {"jahr": jahr, "gesamt": gesamt, "teilhaushalte": passend,
                "beleg": self._beleg(gesamt.get("herkunft_id"))}

    def stellenplan_kontext(self, jahrgang: int | None = None) -> dict | None:
        """Die Gesamtzeilen des Stellenplans — Stellen, besetzt, nicht besetzt.

        Die einzige Schicht des Haushalts, die nicht in Euro rechnet. Auf
        „Wie viele Stellen sind unbesetzt?" antwortet keine Euro-Zahl.

        DREI DINGE, DIE MITREISEN MÜSSEN, weil die Zahlen sonst falsch gelesen
        werden:

        1. Die Besetzungszahlen gehören zur **Vorjahresspalte**, nicht zum
           Haushaltsjahr — geplant wird vorwärts, gezählt werden kann nur
           rückwärts (``stichtag`` sagt, auf welchen Tag). ``stellen_plan``
           minus ``besetzt`` mischt zwei Stichtage und steht in keinem
           Dokument; ``nicht_besetzt`` steht dort, und zwar als eigene Spalte.
        2. Teil A und Teil B sind zwei Tabellen mit zwei Rechenproben, und sie
           kommen einzeln herein. ``fehlend`` sagt, welcher Teil eines
           Jahrgangs **nicht** vorliegt — ohne das sähe ein halber Jahrgang
           wie ein ganzer aus.
        3. Es gibt im Plan keine Zeile „Stellen insgesamt". Diese Methode
           bildet auch keine: Was hier steht, steht so im Dokument.
        """
        try:
            jahrgang = jahrgang or self._conn.execute(
                "SELECT MAX(jahrgang) FROM council_stellenplan "
                "WHERE art = 'gesamt'").fetchone()[0]
        except sqlite3.OperationalError:
            return None
        if not jahrgang:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT teil, bezeichnung, stellen_plan, stellen_vorjahr, besetzt, "
            " nicht_besetzt, stichtag, herkunft_id FROM council_stellenplan "
            "WHERE jahrgang = ? AND art = 'gesamt' ORDER BY teil", (jahrgang,))]
        if not rows:
            return None
        from council import stellenplan as _stellenplan

        for r in rows:
            r["teil_name"] = _stellenplan.TEIL_NAMEN.get(r["teil"], r["teil"])
        fehlend = [t for t in sorted(_stellenplan.TEIL_NAMEN)
                   if t not in {r["teil"] for r in rows}]
        return {
            "jahrgang": jahrgang,
            "stichtag": next((r["stichtag"] for r in rows if r.get("stichtag")), None),
            "teile": rows,
            "fehlend": [_stellenplan.TEIL_NAMEN[t] for t in fehlend],
            "beleg": self._beleg(rows[0].get("herkunft_id")),
        }

    def haushaltsantraege_kontext(self, jahr: int | None = None,
                                  limit: int = 8) -> dict | None:
        """Wer wollte am Haushalt etwas ändern — und kam damit durch?

        Die leichte Schwester von ``haushalt_streit``: dieselben Anker, aber
        ohne Debatte und ohne Protokoll-Volltext. Die Wortbeiträge kommen im
        Antwort-Prompt ohnehin über ``_debatten_block``; das Zerlegen jedes
        Protokolls kostete in einem Web-Request mehr, als es dort einbrächte.

        Gezählt statt aufgezählt: Ein Jahrgang bringt es auf mehrere Dutzend
        Änderungslisten, und „CDU: 9 Listen, 2 angenommen, 7 abgelehnt" sagt
        dasselbe wie neun Titelzeilen, die alle „Änderungsliste der
        CDU-Fraktion zum Ergebnishaushalt" heißen.

        ``jahr`` ist das **Haushaltsjahr**, nicht das Sitzungsjahr: Der
        Haushalt 2026 wurde im Februar 2026 beschlossen, der Haushalt 2023 im
        Dezember 2022. Ohne Angabe kommt der jüngste Jahrgang.

        WAS DIESE QUELLE NICHT WEISS, und was der Baustein dazu deshalb
        ausdrücklich sagt: den **Inhalt** einer Änderungsliste. Welche Position
        um welchen Betrag — das liegt in den Anlagen-PDFs der Vorlage, die
        nicht als Volltext im Bestand sind.
        """
        from council import haushaltsdebatte as hd

        try:
            rows = self._conn.execute(
                "SELECT d.ksinr, d.item_number, d.title, d.outcome, d.vote, "
                "       cs.committee, cs.session_date "
                "FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr "
                "WHERE d.kind = 'decision' AND (d.title LIKE 'Haushaltssatzung und Haushaltsplan%' "
                "   OR d.title LIKE 'Haushalt 2%')").fetchall()
        except sqlite3.OperationalError:
            return None
        anker: dict[int, dict[int, dict]] = {}
        for r in rows:
            titel = (r["title"] or "").strip()
            satzung = self._STREIT_SATZUNG.match(titel)
            sammel = self._STREIT_SAMMEL.match(titel)
            if not satzung and not sammel:
                continue
            j = int((satzung or sammel).group(1))
            st = anker.setdefault(j, {}).setdefault(r["ksinr"], {
                "ksinr": r["ksinr"], "gremium": r["committee"],
                "datum": r["session_date"], "top": None, "official_text": None})
            if sammel:
                # Der Sammelpunkt selbst ist die verlässlichste Angabe.
                st["top"] = (r["item_number"] or "").strip() or st["top"]
            else:
                if not st["top"]:
                    st["top"] = self._streit_oberpunkt(r["item_number"])
                st["official_text"] = {"outcome": r["outcome"], "vote": r["vote"]}
        if not anker:
            return None
        gewaehlt = jahr if jahr in anker else max(anker)

        stationen = []
        for st in sorted(anker[gewaehlt].values(),
                         key=lambda s: (s["datum"], s["gremium"] == "Rat", s["ksinr"])):
            if not st["top"]:
                continue
            praefix = st["top"] + "."
            traeger: dict[str, dict] = {}
            verwaltung = gesamt = 0
            for r in self._conn.execute(
                    "SELECT ksinr, item_number, title, outcome, vote FROM council_decisions "
                    "WHERE ksinr = ? AND kind = 'subvote' ORDER BY position",
                    (st["ksinr"],)).fetchall():
                nr = (r["item_number"] or "").strip()
                if nr != st["top"] and not nr.startswith(praefix):
                    continue
                antrag = hd.antrag_aus_zeile(dict(r))
                if not antrag:
                    continue
                gesamt += 1
                if antrag.ist_verwaltung:
                    verwaltung += 1
                    continue
                # Gemeinsame Listen zählen für ALLE Beteiligten — „SPD/Grüne"
                # ist keine Fraktion, sondern zwei, die sich zusammengetan
                # haben. Sie unter einem Kunstnamen zu führen ließe die Frage
                # „Wie viele Anträge stellte die SPD?" ins Leere laufen.
                for name in (antrag.urheber or "").split(" / "):
                    if not name:
                        continue
                    e = traeger.setdefault(name, {"name": name, "anzahl": 0,
                                                  "angenommen": 0, "abgelehnt": 0})
                    e["anzahl"] += 1
                    if antrag.outcome == "angenommen":
                        e["angenommen"] += 1
                    elif antrag.outcome == "abgelehnt":
                        e["abgelehnt"] += 1
            if not gesamt:
                continue
            stationen.append({
                "gremium": st["gremium"], "datum": st["datum"],
                "urheber": sorted(traeger.values(), key=lambda u: (-u["anzahl"], u["name"]))[:limit],
                "verwaltung": verwaltung, "gesamt": gesamt,
                "official_text": st["official_text"],
            })
        if not stationen:
            return None
        # Die LETZTEN beiden Stationen, nicht die ersten: In Oldenburg sind das
        # der Ausschuss für Finanzen und Beteiligungen und der Rat, und der Rat
        # tagt zuletzt. Käme je eine dritte Station dazu, fiele damit die
        # früheste heraus — nie die entscheidende.
        return {"jahr": gewaehlt, "jahre": sorted(anker),
                "stationen": stationen[-2:]}

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
            "SELECT title, template_number FROM council_decisions WHERE id = ?", (decision_id,)
        ).fetchone()
        rows = self._conn.execute(
            """SELECT d.id, d.title, d.template_number, d.summary, d.policy_field, d.outcome,
                      cs.session_date, cs.committee, sl.score
               FROM council_similar sl
               JOIN council_decisions d ON d.id = sl.neighbor_id
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE sl.decision_id = ? ORDER BY sl.rank LIMIT ?""",
            (decision_id, limit * 5),
        ).fetchall()
        seen = set(_dedup_keys(base["title"], base["template_number"], decision_id)) if base else set()
        out: list[dict] = []
        for r in rows:
            keys = _dedup_keys(r["title"], r["template_number"], r["id"])
            if any(k in seen for k in keys):
                continue
            seen.update(keys)
            out.append(dict(r))
            if len(out) >= limit:
                break
        return out

    def orte_fuer_decisions(self, ids: list[int]) -> dict[int, dict]:
        """Bestbelegter Ort je Beschluss für die Mini-Karte.

        Die explizite Orts-Pipeline gewinnt; alte Themen-Entitäten bleiben als
        Fallback, solange der historische Backfill noch nicht vollständig ist.
        """
        if not ids:
            return {}
        ph = ",".join("?" * len(ids))
        direct = self._conn.execute(
            f"""SELECT dl.decision_id, l.name, l.lat, l.lon
                FROM council_decision_locations dl
                JOIN council_locations l ON l.slug = dl.location_slug
                WHERE dl.decision_id IN ({ph}) AND l.lat IS NOT NULL
                  AND l.stadtteil IS NOT NULL AND l.stadtteil != ''
                ORDER BY dl.confidence DESC, l.name""", ids).fetchall()
        out: dict[int, dict] = {}
        for r in direct:
            out.setdefault(r["decision_id"], {"ort_name": r["name"],
                                              "lat": r["lat"], "lon": r["lon"]})
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
        from council import geo

        for r in rows:
            # Alte Entitäts-Geocodes entstanden vor der expliziten
            # Orts-Pipeline und können Vergleichsorte außerhalb Oldenburgs
            # enthalten. Nur Koordinaten innerhalb eines Ratslotse-
            # Ortsbereichspolygons dürfen als Karten-Pin erscheinen.
            if not geo.ortsbereich_for(r["lat"], r["lon"]):
                continue
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
                                      max_je_top: int = 4,
                                      sprecher: str = "") -> list[dict]:
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
        sprecher_filter = " AND w.sprecher LIKE ?" if sprecher.strip() else ""
        params: list = list(stationen)
        if sprecher_filter:
            params.append(f"%{sprecher.strip()}%")
        rows = self._conn.execute(
            f"""SELECT w.id, w.ksinr, w.seite, w.art, w.top, w.sprecher, w.partei,
                       w.text, w.antwort, cs.committee, cs.session_date
                FROM council_wortbeitraege w
                LEFT JOIN council_sessions cs ON cs.ksinr = w.ksinr
                WHERE w.ksinr IN ({ph}) AND w.top IS NOT NULL{sprecher_filter}
                ORDER BY cs.session_date DESC, w.id""", params).fetchall()
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

        Liefert auch Abstimmung (vote/no_votes/abstentions/raw_result) und
        amount_eur mit: raw_result geht bei strittigen Beschlüssen in den
        QA-Kontext (dort stehen oft die Fraktionen der Gegenstimmen), und die
        Fallback-Folgefragen in council/qa.py prüfen no_votes/amount_eur —
        ohne diese Felder liefen die Zweige ins Leere."""
        if not ids:
            return []
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"""SELECT d.id, d.title, d.summary, d.official_text, d.template_number,
                       d.kvonr,
                       -- ksinr + item_number: Adresse der Station in der
                       -- Sitzung — darüber koppelt wortbeitraege_zu_beschluessen
                       -- die Aussprache an den Beschluss.
                       d.ksinr, d.item_number,
                       d.policy_field, d.outcome, d.impact, d.impact_reason,
                       d.vote, d.no_votes, d.abstentions, d.raw_result,
                       d.amount_eur, d.factions, d.deviation,
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
               LEFT JOIN council_vorlagen v ON v.template_number = d.template_number
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

    def find_decision_ids(self, *, template_number: str | None = None, committee: str | None = None,
                          session_date: str | None = None, title_like: str | None = None) -> list[int]:
        """Beschluss-ids über natürliche Schlüssel statt AUTOINCREMENT-ids.

        Für DB-portable Eval-Gold-Cases (eval/cases_qa.json): Vorlagen-Nummer,
        Sitzungsdatum und Titel sind auf jeder Kopie der Datenbank gleich, die
        ids nicht. Filter sind UND-verknüpft, mindestens einer ist Pflicht;
        Teilabstimmungen bleiben außen vor (nicht eigenständig zitierbar)."""
        conds, params = ["d.kind = 'decision'"], []
        if template_number:
            conds.append("d.template_number = ?"); params.append(str(template_number).strip())
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

    # ---- Der Weg eines Haushalts durch den Rat (A6, 08/2026) ---------------
    #
    # Gebaut aus dem, was das Ratsinformationssystem ohnehin führt: der
    # Beratungsfolge (`council_beratungen`), den Tagesordnungen
    # (`council_agenda_items`) und den Protokoll-Beschlüssen
    # (`council_decisions`). Kein eigener Datenbestand, kein Cron.
    #
    # `council_anlagen.fetched_at` ist hier KEINE Quelle: Bei allen
    # Finanzdokumenten steht dort der 10.08.2026 — der Tag unseres
    # Volltext-Backfills, nicht der Tag der Veröffentlichung. Das Datum einer
    # Station kommt ausschließlich aus `council_sessions.session_date`.

    #: Ein Haushaltsjahr trägt drei Sorten Vorlagen, und sie heißen nicht
    #: einheitlich. Die Jahreszahl steht immer vorn, das Wort davor variiert
    #: („Haushalt 2026", „Haushaltsentwurf 2024", „HH 2020").
    _HH_TITEL = re.compile(r"^(?:Haushaltsentwurf|Haushalt|HH)\s*(\d{4})")

    #: Woran ein Verwaltungsentwurf als Teilhaushalts-Bericht erkennbar ist —
    #: er geht in den jeweiligen Fachausschuss, nicht in den Finanzausschuss.
    _HH_TEILBERICHT = ("Teilhaushalt", "THH", "Budget", "Stiftung")

    def haushalt_weg(self, jahr: int | None = None) -> list[dict]:
        """Wann ein Haushaltsjahr welche Station im Rat durchlaufen hat.

        Je Haushaltsjahr eine Runde mit drei Abschnitten:

        - ``einbringung``: die früheste Beratung einer Entwurfs-Vorlage — der
          Moment, ab dem der Entwurf öffentlich einsehbar ist,
        - ``fachausschuesse``: die Teilhaushalts-Berichte danach, als Zeitraum
          und Gremienliste (einzeln aufzuzählen hilft niemandem, es sind rund
          ein Dutzend Termine),
        - ``stationen``: die Beratungsfolge der Sammelvorlage „Haushalt
          <jahr> - Beschluss" bis zur Entscheidung im Rat, je Station mit dem
          Ergebnis, das die Tagesordnung ausweist.

        **Die Fensterregel** (Einbringung … letzte Beschluss-Station) ist kein
        Schönheitsfilter, sondern Notwehr gegen falsch betitelte Vorlagen:
        22/0824 heißt „Haushalt 2022 …", wurde aber im November 2022 beraten
        und gehört zur Runde 2023; 25/0643 heißt „Haushalt 2025 …" und liegt
        in der Runde 2026. Ohne die Regel zöge je ein Ausreißer den Zeitraum
        der Fachausschuss-Runde um ein volles Jahr auf.

        Ohne Sammelvorlage gibt es keine Runde: Das Haushaltsjahr 2018 wurde
        vor dem Beginn unseres Bestands (Januar 2018) beschlossen.
        """
        vorlagen: dict[int, dict[str, list[dict]]] = {}
        for r in self._conn.execute(
                "SELECT kvonr, template_number, title FROM council_vorlagen "
                "WHERE title LIKE 'Haushalt%' OR title LIKE 'HH %'").fetchall():
            m = self._HH_TITEL.match(r["title"] or "")
            if not m:
                continue                      # „Haushaltsplan der …", „Haushaltsvermerk …"
            j = int(m.group(1))
            if jahr is not None and j != jahr:
                continue
            titel = r["title"]
            if "Verwaltungsentwurf" in titel:
                art = "teil" if any(k in titel for k in self._HH_TEILBERICHT) else "entwurf"
            elif "Beschluss" in titel:
                art = "official_text"
            else:
                continue
            vorlagen.setdefault(j, {"entwurf": [], "teil": [], "official_text": []})[art].append(dict(r))

        runden = []
        for j in sorted(vorlagen):
            runde = self._haushalt_runde(j, vorlagen[j])
            if runde:
                runden.append(runde)
        return runden

    def _haushalt_runde(self, jahr: int, teile: dict[str, list[dict]]) -> dict | None:
        """Eine Haushaltsrunde zusammensetzen — siehe ``haushalt_weg``."""
        beschluss_vorlagen = teile["official_text"]
        stationen = self._hh_beratungen([v["kvonr"] for v in beschluss_vorlagen])
        if not stationen:
            return None

        entwurf_beratungen = self._hh_beratungen(
            [v["kvonr"] for v in (*teile["entwurf"], *teile["teil"])])
        einbringung = entwurf_beratungen[0] if entwurf_beratungen else None

        von = einbringung["datum"] if einbringung else stationen[0]["datum"]
        bis = stationen[-1]["datum"]
        fach = [b for b in entwurf_beratungen[1:] if von <= b["datum"] <= bis]

        # Der Kernhaushalt ist der Punkt, an dem tatsächlich abgestimmt wird —
        # die Sammelvorlage bündelt daneben Stiftungen und Eigenbetriebe. Der
        # Beschluss trägt den Jahrgang im Titel, deshalb ist er ohne Raten
        # zuzuordnen: über die Sitzung, nicht über eine geratene TOP-Nummer.
        votum = {}
        for d in self._conn.execute(
                "SELECT id, ksinr, item_number, outcome, vote, no_votes, abstentions "
                "FROM council_decisions WHERE kind = 'decision' AND title LIKE ? "
                "ORDER BY id", (f"Haushaltssatzung und Haushaltsplan {jahr}%",)).fetchall():
            votum.setdefault(d["ksinr"], dict(d))

        for s in stationen:
            s["votum"] = votum.get(s["ksinr"])

        return {
            "jahr": jahr,
            "template_number": beschluss_vorlagen[0]["template_number"] if beschluss_vorlagen else None,
            "kvonr": beschluss_vorlagen[0]["kvonr"] if beschluss_vorlagen else None,
            "einbringung": einbringung,
            "fachausschuesse": {
                "von": fach[0]["datum"], "bis": fach[-1]["datum"],
                "anzahl": len(fach),
                "gremien": sorted({b["gremium"] for b in fach}),
            } if fach else None,
            "stationen": stationen,
        }

    def _hh_beratungen(self, kvonrs: list[int]) -> list[dict]:
        """Beratungen mehrerer Vorlagen, nach Datum sortiert, je mit dem
        Ergebnis aus der Tagesordnung.

        Die TOP-Nummer kommt aus `council_agenda_items` und nicht aus
        `council_beratungen.top`: Nur dort trägt sie das Präfix („Ö 6"), und
        „Ö 6" und „N 6" sind verschiedene Punkte."""
        if not kvonrs:
            return []
        platz = ",".join("?" * len(kvonrs))
        rows = self._conn.execute(
            f"""SELECT b.kvonr, b.datum, b.gremium, b.ergebnis AS rolle, b.is_public,
                       b.ksinr, v.template_number, v.title AS vorlage_titel,
                       a.item_number AS top, a.title AS top_titel
                  FROM council_beratungen b
                  JOIN council_vorlagen v ON v.kvonr = b.kvonr
             LEFT JOIN council_agenda_items a ON a.ksinr = b.ksinr AND a.kvonr = b.kvonr
                 WHERE b.kvonr IN ({platz})
              ORDER BY b.datum, b.gremium""", kvonrs).fetchall()
        out = []
        for r in rows:
            s = dict(r)
            s["ergebnis"] = self._hh_ergebnis(s.pop("top_titel"))
            # Jede Station trägt den Schlüssel, auch wenn nur die Stationen der
            # Sammelvorlage ihn je füllen — eine Station mit und eine ohne
            # `votum` wären zwei Formen derselben Sache.
            s["votum"] = None
            out.append(s)
        return out

    @staticmethod
    def _hh_ergebnis(top_titel: str | None) -> str | None:
        """Das Ergebnis, das die Tagesordnung an den Punkt schreibt —
        „geändert beschlossen", „zurückgestellt/abgesetzt", „zur Kenntnis
        genommen". Die angehängte Stimmenzählung bleibt weg: Sie steht bei
        einem Teil der Punkte und fehlt beim Rest, taugt also nicht als
        Angabe, auf die sich eine Seite verlassen könnte."""
        if not top_titel or "Beschluss: " not in top_titel:
            return None
        rest = top_titel.split("Beschluss: ", 1)[1].strip()
        return rest.split("Abstimmung:")[0].strip() or None

    # ---- Der Streit ums Geld (08/2026) ------------------------------------
    #
    # Die Zahlen des Haushalts stehen in den Finanzdokumenten; dass über sie
    # gestritten wurde, steht nur im Protokoll. Diese Methode setzt beides
    # zusammen, was die Ratsdaten dazu hergeben: welche Änderungslisten zur
    # Abstimmung standen (`council_decisions` mit `kind='subvote'`), was in
    # der Debatte gesagt wurde (`council_protocols.raw_text`, zerlegt in
    # `council.haushaltsdebatte`) und wie am Ende abgestimmt wurde.
    #
    # Kein eigener Datenbestand und kein Cron: Alles wird beim Lesen aus dem
    # gerechnet, was der Protokoll-Import ohnehin schreibt. Damit kann die
    # Seite nicht veralten, und ein nachgetragenes Protokoll erscheint ohne
    # Backfill.

    #: Die Schlussabstimmung trägt in jedem Jahrgang denselben Titel; die
    #: Jahreszahl darin ist das HAUSHALTSJAHR, nicht das Sitzungsjahr (der
    #: Haushalt 2023 wurde im Dezember 2022 beschlossen, der Haushalt 2026
    #: erst im Februar 2026).
    _STREIT_SATZUNG = re.compile(r"^Haushaltssatzung und Haushaltsplan\s+(\d{4})")
    #: Der Sammelpunkt, unter dem die Debatte geführt wird. Er steht nicht in
    #: jedem Protokoll als eigene Beschlusszeile — wo er fehlt, wird der
    #: Oberpunkt aus der Nummer der Schlussabstimmung abgeleitet.
    _STREIT_SAMMEL = re.compile(r"^Haushalt\s+(\d{4})\s*$")

    def haushalt_streit(self, jahr: int | None = None) -> list[dict]:
        """Die politische Auseinandersetzung um jeden Haushaltsjahrgang.

        Je Haushaltsjahr eine Runde mit ihren ``stationen`` — in Oldenburg
        sind das der Ausschuss für Finanzen und Beteiligungen und der Rat.
        Jede Station trägt:

        - ``antraege``: die Änderungslisten, die dort zur Abstimmung standen,
          mit ``urheber`` (Fraktion/Gruppe) und ``outcome``. Der **Inhalt**
          einer Liste — welche Position um welchen Betrag — steht nicht dabei:
          Er liegt in den Anlagen-PDFs der Vorlage, die nicht als Volltext im
          Bestand sind. Was hier steht, ist „wer wollte ändern und kam damit
          durch", nicht „was genau".
        - ``debatte``: die Wortbeiträge unter dem Sammelpunkt, in der
          Reihenfolge des Protokolls. Keine Auswahl, keine Zusammenfassung —
          wer kürzt, kürzt für alle gleich, und das tut erst die Anzeige.
        - ``official_text``: die Schlussabstimmung über die Haushaltssatzung.

        Der Ausschuss stimmt über dieselben Listen ab wie der Rat, oft mit
        anderem Ergebnis; deshalb stehen beide Stationen nebeneinander statt
        zusammengefasst.
        """
        from council import haushaltsdebatte as hd

        anker: dict[int, dict[int, dict]] = {}
        for r in self._conn.execute(
                "SELECT d.id, d.ksinr, d.item_number, d.title, d.outcome, d.vote, "
                "       d.no_votes, d.abstentions, d.raw_result, d.template_number, "
                "       cs.committee, cs.session_date "
                "FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr "
                "WHERE d.kind = 'decision' AND (d.title LIKE 'Haushaltssatzung und Haushaltsplan%' "
                "   OR d.title LIKE 'Haushalt 2%')").fetchall():
            titel = (r["title"] or "").strip()
            satzung = self._STREIT_SATZUNG.match(titel)
            sammel = self._STREIT_SAMMEL.match(titel)
            if not satzung and not sammel:
                continue
            j = int((satzung or sammel).group(1))
            if jahr is not None and j != jahr:
                continue
            eintrag = anker.setdefault(j, {}).setdefault(r["ksinr"], {
                "ksinr": r["ksinr"],
                "gremium": r["committee"],
                "datum": r["session_date"],
                "top": None,
                "official_text": None,
            })
            if satzung:
                eintrag["official_text"] = {
                    "id": r["id"], "top": r["item_number"], "titel": titel,
                    "outcome": r["outcome"], "vote": r["vote"],
                    "no_votes": r["no_votes"], "abstentions": r["abstentions"],
                    "wortlaut": (r["raw_result"] or "").strip() or None,
                    "template_number": r["template_number"],
                }
                if not eintrag["top"]:
                    eintrag["top"] = self._streit_oberpunkt(r["item_number"])
            else:
                # Der Sammelpunkt selbst — die verlässlichste Angabe für die Debatte.
                eintrag["top"] = (r["item_number"] or "").strip() or eintrag["top"]
                if eintrag["official_text"] is None:
                    eintrag["official_text"] = {
                        "id": r["id"], "top": r["item_number"], "titel": titel,
                        "outcome": r["outcome"], "vote": r["vote"],
                        "no_votes": r["no_votes"], "abstentions": r["abstentions"],
                        "wortlaut": (r["raw_result"] or "").strip() or None,
                        "template_number": r["template_number"],
                    }

        runden = []
        for j in sorted(anker):
            stationen = []
            # Am selben Tag tagt erst der Ausschuss, dann der Rat — das Datum
            # allein stellt sie sonst in beliebiger Reihenfolge nebeneinander.
            for st in sorted(anker[j].values(),
                             key=lambda s: (s["datum"], s["gremium"] == "Rat", s["ksinr"])):
                stationen.append(self._streit_station(st, hd))
            if stationen:
                runden.append({"jahr": j, "stationen": stationen})
        return runden

    @staticmethod
    def _streit_oberpunkt(item_number: str | None) -> str | None:
        """Der Sammelpunkt über einer Schlussabstimmung: „6.5" → „6",
        „7.1.7" → „7.1". Unter ihm steht die Debatte, unter seinen
        Unterpunkten stehen die Abstimmungen."""
        nr = (item_number or "").strip().rstrip(".")
        if "." not in nr:
            return nr or None
        return nr.rsplit(".", 1)[0]

    def _streit_station(self, st: dict, hd) -> dict:
        """Eine Station anreichern: Änderungslisten, Debatte, Protokoll-Link."""
        ksinr, top = st["ksinr"], st["top"]

        antraege = []
        if top:
            praefix = top + "."
            for r in self._conn.execute(
                    "SELECT ksinr, item_number, title, outcome, vote FROM council_decisions "
                    "WHERE ksinr = ? AND kind = 'subvote' ORDER BY position", (ksinr,)).fetchall():
                nr = (r["item_number"] or "").strip()
                if nr != top and not nr.startswith(praefix):
                    continue
                antrag = hd.antrag_aus_zeile(dict(r))
                if antrag:
                    antraege.append(antrag.als_dict())

        prot = self._conn.execute(
            "SELECT document_url, raw_text FROM council_protocols WHERE ksinr = ?",
            (ksinr,)).fetchone()
        debatte: list[dict] = []
        if prot and prot["raw_text"] and top:
            anwesende = [dict(a) for a in self._conn.execute(
                "SELECT name, party, role FROM council_attendance WHERE ksinr = ?", (ksinr,)).fetchall()]
            # Säubern, schneiden, zerlegen — mit Gedächtnis über den Inhalt.
            # Es bleibt beim Rechnen zur Lesezeit (s. Kopf von `haushalt_streit`);
            # nur wird dasselbe Protokoll nicht bei jedem Aufruf neu zerlegt.
            debatte = hd.debatte_zu_top(prot["raw_text"], top, anwesende)

        return {
            **st,
            "antraege": antraege,
            "debatte": debatte,
            "protokoll_url": prot["document_url"] if prot else None,
        }
