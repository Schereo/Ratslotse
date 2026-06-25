from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import sqlite3

from .scraper import CouncilSession, AgendaItem
from .parties import normalize_party, order_key


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
    amount_eur   REAL                           -- largest € amount in the text (council.money)
);
CREATE INDEX IF NOT EXISTS idx_decisions_ksinr ON council_decisions(ksinr);
-- NB: the policy_field index is created in _migrate(), not here — on an existing
-- DB this whole SCHEMA runs (via executescript) BEFORE the migration adds the
-- column, so indexing policy_field here would fail with "no such column".

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

-- Press coverage: NWZ articles matched to a decision (semantic + temporal).
CREATE TABLE IF NOT EXISTS council_news_links (
    decision_id INTEGER NOT NULL,
    catalog     INTEGER NOT NULL,
    refid       TEXT NOT NULL,
    title       TEXT,
    pub_date    TEXT,
    score       REAL NOT NULL,
    PRIMARY KEY (decision_id, catalog, refid)
);
CREATE INDEX IF NOT EXISTS idx_news_decision ON council_news_links(decision_id);
"""


class CouncilStore:
    def __init__(self, path: str | Path, nwz_db_path: str | Path | None = None):
        self._path = path
        # Sibling nwz.sqlite holds the chat_id→owner_id map for the migration.
        if nwz_db_path is None and isinstance(path, (str, Path)) and str(path) != ":memory:":
            nwz_db_path = Path(path).parent / "nwz.sqlite"
        self._nwz_db_path = nwz_db_path
        self._conn = sqlite3.connect(path, timeout=15)
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
                self._conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_decisions_field ON council_decisions(policy_field)"
                )
        # Full-text index for hybrid (BM25 + vector) retrieval. rowid = decision id;
        # diacritics folded so "Radweg"/"radweg" and German umlauts match. Populated by
        # scripts/build_decisions_fts.py (and the daily cron).
        self._conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS council_decisions_fts "
            "USING fts5(content, tokenize=\"unicode61 remove_diacritics 2\")"
        )
        self._migrate_owner_id()

    def _migrate_owner_id(self) -> None:
        """Re-key the per-recipient dedup tables from Telegram chat_id to the
        canonical owner_id (=web_users.id). The map lives in the sibling
        nwz.sqlite; existing rows are backfilled via it. Idempotent."""
        cn_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(committee_notifications)").fetchall()}
        sf_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(session_followups_sent)").fetchall()}
        if "owner_id" in cn_cols and "owner_id" in sf_cols:
            return  # already migrated

        # Build chat_id -> owner_id from nwz.sqlite if available.
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

    def close(self) -> None:
        self._conn.close()

    def admin_stats(self) -> dict:
        """Council counts for the admin dashboard (read-only)."""
        c = self._conn

        def one(sql: str, *p):
            row = c.execute(sql, p).fetchone()
            return row[0] if row else 0

        return {
            "sessions": one("SELECT COUNT(*) FROM council_sessions"),
            "upcoming": one("SELECT COUNT(*) FROM council_sessions WHERE session_date >= date('now')"),
            "agenda_items": one("SELECT COUNT(*) FROM council_agenda_items"),
            "committees": one("SELECT COUNT(*) FROM committees"),
        }

    def has_session_with_agenda(self, ksinr: int) -> bool:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM council_agenda_items WHERE ksinr = ?", (ksinr,)
        ).fetchone()
        return row and row[0] > 0

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

    def followup_already_sent(self, ksinr: int, owner_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM session_followups_sent WHERE ksinr = ? AND owner_id = ?",
            (ksinr, owner_id),
        ).fetchone()
        return row is not None

    def mark_followup_sent(self, ksinr: int, owner_id: int) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO session_followups_sent (ksinr, owner_id, sent_at) VALUES (?, ?, ?)",
                (ksinr, owner_id, now),
            )

    def past_sessions_in_window(self, date_from: str, date_to: str) -> list[dict]:
        """Sessions that took place between date_from and date_to (inclusive)."""
        rows = self._conn.execute(
            """SELECT cs.ksinr, cs.committee, cs.session_date, cs.session_time, cs.location
               FROM council_sessions cs
               WHERE cs.session_date BETWEEN ? AND ?
               ORDER BY cs.session_date DESC""",
            (date_from, date_to),
        ).fetchall()
        return [dict(r) for r in rows]

    def upcoming_sessions(self, limit: int = 20) -> list[dict]:
        from datetime import date
        today = date.today().isoformat()
        rows = self._conn.execute(
            """SELECT cs.ksinr, cs.committee, cs.session_date, cs.session_time, cs.location,
                      COUNT(ci.id) AS n_items
               FROM council_sessions cs
               LEFT JOIN council_agenda_items ci ON ci.ksinr = cs.ksinr
               WHERE cs.session_date >= ?
               GROUP BY cs.ksinr
               ORDER BY cs.session_date ASC
               LIMIT ?""",
            (today, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def recent_sessions(self, limit: int = 10) -> list[dict]:
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
               LIMIT ?""",
            (today, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_notified(self, ksinr: int, owner_id: int, agenda_hash: str = "") -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO committee_notifications (ksinr, owner_id, agenda_hash, sent_at) VALUES (?, ?, ?, ?)",
                (ksinr, owner_id, agenda_hash, now),
            )

    def was_notified(self, ksinr: int, owner_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM committee_notifications WHERE ksinr = ? AND owner_id = ?",
            (ksinr, owner_id),
        ).fetchone()
        return row is not None

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

    def agenda_items(self, ksinr: int) -> list[dict]:
        rows = self._conn.execute(
            """SELECT item_number, title, vorlage_nr, kvonr, is_public
               FROM council_agenda_items WHERE ksinr = ?
               ORDER BY id""",
            (ksinr,),
        ).fetchall()
        return [dict(r) for r in rows]

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

    def search_sessions(
        self,
        query: str = "",
        committee: str = "",
        date_from: str = "",
        date_to: str = "",
        limit: int = 50,
    ) -> list[dict]:
        """Search sessions by committee name or agenda item text. Empty query lists by date."""
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
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        params.append(limit)
        rows = self._conn.execute(
            f"""SELECT cs.ksinr, cs.committee, cs.session_date, cs.session_time, cs.location,
                       COUNT(ci.id) AS n_items
                FROM council_sessions cs
                LEFT JOIN council_agenda_items ci ON ci.ksinr = cs.ksinr
                {where}
                GROUP BY cs.ksinr
                ORDER BY cs.session_date DESC
                LIMIT ?""",
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
        self._conn.execute(
            "INSERT INTO council_decisions "
            "(ksinr, position, kind, parent_item, item_number, title, beschluss, outcome, "
            " vote, gegenstimmen, enthaltungen, factions, vorlage_nr, kvonr, raw_result) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ksinr, position, kind, parent_item, item_number, title, beschluss, outcome,
             vote, _int_or_none(gegenstimmen), _int_or_none(enthaltungen),
             json.dumps(factions or [], ensure_ascii=False),
             vorlage_nr, _int_or_none(kvonr), raw_result),
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
    ) -> None:
        """Persist a parsed protocol with its decisions + attendance (replacing any
        prior rows for this session). One transaction."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_protocols "
                "(ksinr, document_id, document_url, protocol_nr, session_start, session_end, "
                " raw_text, n_pages, model, extracted_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ksinr, document.get("document_id"), document.get("url"), meta.get("protocol_nr"),
                 meta.get("session_start"), meta.get("session_end"), raw_text, n_pages, model, now, status),
            )
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

    def mark_protocol_failed(self, ksinr: int, document: dict) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_protocols "
                "(ksinr, document_id, document_url, extracted_at, status) VALUES (?, ?, ?, ?, 'failed')",
                (ksinr, document.get("document_id"), document.get("url"), now),
            )

    def get_decisions(self, ksinr: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM council_decisions WHERE ksinr = ? ORDER BY position", (ksinr,)
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
        d["parties"] = sorted({p for p in (normalize_party(f) for f in d["factions"]) if p}, key=order_key)
        return d

    # Outcomes grouped into "real votes" vs "reports / no decision".
    _VOTE_OUTCOMES = ("angenommen", "abgelehnt", "vertagt")
    _REPORT_OUTCOMES = ("zur_kenntnis", "kein_beschluss")

    def decision_ids_for_party(self, party: str) -> list[int]:
        """IDs of main decisions whose Antragsteller (normalised) includes ``party``."""
        from council.parties import normalize_party
        ids = []
        for row in self._conn.execute("SELECT id, factions FROM council_decisions WHERE kind = 'decision'"):
            try:
                arr = json.loads(row["factions"] or "[]")
            except (json.JSONDecodeError, TypeError):
                arr = []
            if any(normalize_party(f) == party for f in arr):
                ids.append(row["id"])
        return ids

    def _decision_where(self, query, committee, outcome, faction, date_from, date_to,
                        kind, category, field="", party_ids=None):
        """Build the WHERE clause + params shared by search and count."""
        filters: list[str] = []
        params: list = []
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
    ) -> list[dict]:
        """Search extracted decisions, joined with their session (committee + date).
        ``category`` is "vote" (decided) or "report" (zur Kenntnis / no decision).
        ``field`` filters by policy field, ``party`` by normalised Antragsteller;
        ``sort`` ∈ {date_desc, date_asc, faction}."""
        order = {
            "date_asc": "cs.session_date ASC, d.position",
            # Non-empty factions first ('["…' < '[]'), grouped, newest within.
            "faction": "d.factions ASC, cs.session_date DESC",
        }.get(sort, "cs.session_date DESC, d.position")
        party_ids = self.decision_ids_for_party(party) if party else None
        where, params = self._decision_where(query, committee, outcome, faction,
                                              date_from, date_to, kind, category, field, party_ids)
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

    def count_decisions(
        self, query="", committee="", outcome="", faction="", date_from="", date_to="",
        kind="", category="", field="", party="",
    ) -> int:
        party_ids = self.decision_ids_for_party(party) if party else None
        where, params = self._decision_where(query, committee, outcome, faction,
                                             date_from, date_to, kind, category, field, party_ids)
        row = self._conn.execute(
            f"""SELECT COUNT(*) FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr {where}""",
            params,
        ).fetchone()
        return row[0] if row else 0

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
            "SELECT * FROM council_decisions WHERE ksinr = ? AND kind = 'subvote' AND parent_item = ? ORDER BY position",
            (ksinr, parent_item),
        ).fetchall()
        return [self._decision_row(r) for r in rows]

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
        """(Re)build the full-text index from all main decisions (title + beschluss + summary)."""
        with self._conn:
            self._conn.execute("DELETE FROM council_decisions_fts")
            self._conn.execute(
                "INSERT INTO council_decisions_fts(rowid, content) "
                "SELECT id, REPLACE(COALESCE(title,'') || ' ' || COALESCE(beschluss,'') || ' ' "
                "|| COALESCE(summary,''), 'ß', 'ss') "  # unicode61 folds ä/ö/ü but not ß
                "FROM council_decisions WHERE kind = 'decision'"
            )
        return self._conn.execute("SELECT COUNT(*) FROM council_decisions_fts").fetchone()[0]

    def search_decisions_fts(self, query: str, limit: int = 40) -> list[tuple]:
        """BM25 keyword search → ``[(decision_id, score)]`` (larger = better). Terms are
        OR-combined for recall; returns ``[]`` on an empty or invalid query."""
        terms = [t for t in re.findall(r"[0-9a-zäöü]+", query.lower().replace("ß", "ss")) if len(t) >= 3][:12]
        if not terms:
            return []
        match = " OR ".join(terms)
        try:
            rows = self._conn.execute(
                "SELECT rowid, rank FROM council_decisions_fts WHERE council_decisions_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (match, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        # FTS5 rank is negative (more negative = better); flip so larger = better.
        return [(r[0], -float(r[1])) for r in rows]

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

        from council.parties import normalize_party, order_key

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
            parties = sorted({p for p in (normalize_party(x) for x in arr) if p}, key=order_key)
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
        """All main decisions with a short text for embedding (id + text)."""
        rows = self._conn.execute(
            "SELECT id, title, summary, beschluss FROM council_decisions WHERE kind = 'decision'"
        ).fetchall()
        out = []
        for r in rows:
            text = f"{r['title'] or ''}. {r['summary'] or r['beschluss'] or ''}".strip()
            out.append({"id": r["id"], "text": text[:500]})
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

    def decision_dates(self) -> dict:
        """{decision_id: session_date} for main decisions (temporal news matching)."""
        return {r["id"]: r["session_date"] for r in self._conn.execute(
            "SELECT d.id, cs.session_date FROM council_decisions d "
            "JOIN council_sessions cs ON cs.ksinr = d.ksinr WHERE d.kind = 'decision'")}

    def set_news_links(self, rows: list[tuple]) -> int:
        """Replace all press links. rows = (decision_id, catalog, refid, title, pub_date, score)."""
        with self._conn:
            self._conn.execute("DELETE FROM council_news_links")
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_news_links "
                "(decision_id, catalog, refid, title, pub_date, score) VALUES (?, ?, ?, ?, ?, ?)", rows)
        return len(rows)

    def get_news_for_decision(self, decision_id: int, limit: int = 4) -> list[dict]:
        rows = self._conn.execute(
            "SELECT catalog, refid, title, pub_date, score FROM council_news_links "
            "WHERE decision_id = ? ORDER BY score DESC LIMIT ?", (decision_id, limit)).fetchall()
        return [dict(r) for r in rows]

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

    def get_decisions_by_ids(self, ids: list[int]) -> list[dict]:
        """Fetch decisions by id, preserving the given order (for Q&A citations)."""
        if not ids:
            return []
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"""SELECT d.id, d.title, d.summary, d.policy_field, d.outcome,
                       cs.session_date, cs.committee
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.id IN ({ph})""",
            ids,
        ).fetchall()
        by_id = {r["id"]: dict(r) for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    def get_protocols_raw(self) -> list[dict]:
        """All stored protocols with their raw text — for re-extraction without
        re-downloading the PDFs."""
        rows = self._conn.execute(
            "SELECT ksinr, document_id, document_url, raw_text, n_pages "
            "FROM council_protocols WHERE raw_text IS NOT NULL AND raw_text != ''"
        ).fetchall()
        return [dict(r) for r in rows]

    def protocol_stats(self) -> dict:
        c = self._conn

        def one(sql: str) -> int:
            row = c.execute(sql).fetchone()
            return row[0] if row else 0

        return {
            "protocols": one("SELECT COUNT(*) FROM council_protocols WHERE status='ok'"),
            "decisions": one("SELECT COUNT(*) FROM council_decisions"),
            "attendance": one("SELECT COUNT(*) FROM council_attendance"),
        }
