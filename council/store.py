from __future__ import annotations

from datetime import datetime
from pathlib import Path

import sqlite3

from .scraper import CouncilSession, AgendaItem

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
