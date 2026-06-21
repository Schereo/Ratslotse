from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Any

from .api import Edition
from .parse import Article

SCHEMA = """
CREATE TABLE IF NOT EXISTS editions (
    catalog          INTEGER PRIMARY KEY,
    customer         TEXT NOT NULL,
    folder           INTEGER NOT NULL,
    title            TEXT NOT NULL,
    publication_date TEXT NOT NULL,
    pages            INTEGER NOT NULL,
    content_version  INTEGER NOT NULL,
    fetched_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_editions_folder_date
    ON editions(folder, publication_date DESC);

CREATE TABLE IF NOT EXISTS articles (
    catalog          INTEGER NOT NULL,
    refid            TEXT NOT NULL,
    external_id      TEXT,
    page             INTEGER,
    category_number  INTEGER,
    category_name    TEXT,
    title            TEXT,
    subtitle         TEXT,
    authors          TEXT,
    content_html     TEXT,
    content_text     TEXT,
    priority         INTEGER,
    PRIMARY KEY (catalog, refid),
    FOREIGN KEY (catalog) REFERENCES editions(catalog)
);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category_name);

-- Full-text search (unicode61 handles German umlauts)
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    catalog    UNINDEXED,
    refid      UNINDEXED,
    pub_date   UNINDEXED,
    category_name,
    title,
    subtitle,
    authors,
    content_text,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS users (
    chat_id    INTEGER PRIMARY KEY,
    username   TEXT NOT NULL DEFAULT '',
    added_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL DEFAULT 0,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS committee_subscriptions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id        INTEGER NOT NULL,
    committee_name TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    UNIQUE(chat_id, committee_name)
);

CREATE TABLE IF NOT EXISTS article_topic_matches (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id          INTEGER NOT NULL,
    topic_id         INTEGER NOT NULL,
    catalog          INTEGER NOT NULL,
    refid            TEXT NOT NULL,
    pub_date         TEXT NOT NULL,
    title            TEXT NOT NULL,
    summary          TEXT NOT NULL,
    is_continuation  INTEGER NOT NULL DEFAULT 0,
    matched_at       TEXT NOT NULL,
    UNIQUE(chat_id, topic_id, catalog, refid)
);
CREATE INDEX IF NOT EXISTS idx_atm_lookup ON article_topic_matches(chat_id, topic_id, pub_date DESC);

CREATE TABLE IF NOT EXISTS topic_classified_editions (
    chat_id     INTEGER NOT NULL,
    topic_id    INTEGER NOT NULL,
    pub_date    TEXT NOT NULL,
    classified_at TEXT NOT NULL,
    PRIMARY KEY(chat_id, topic_id, pub_date)
);

-- Web frontend accounts (separate from the Telegram whitelist `users`).
CREATE TABLE IF NOT EXISTS web_users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    email            TEXT NOT NULL UNIQUE,
    password_hash    TEXT NOT NULL,
    role             TEXT NOT NULL DEFAULT 'user',
    status           TEXT NOT NULL DEFAULT 'pending',
    telegram_chat_id INTEGER,
    nwz_username     TEXT,
    nwz_verified_at  TEXT,
    token_version    INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL
);

-- One-time codes that link a web account to a Telegram chat via the bot.
CREATE TABLE IF NOT EXISTS link_codes (
    code        TEXT PRIMARY KEY,
    web_user_id INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);
"""


@dataclass
class SearchResult:
    catalog: int
    refid: str
    pub_date: str
    category_name: str
    title: str
    subtitle: str
    authors: str
    excerpt: str
    rank: float


@dataclass
class TopicRow:
    id: int
    chat_id: int
    name: str
    description: str
    created_at: str


@dataclass
class UserRow:
    chat_id: int
    username: str
    added_at: str


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # WAL allows concurrent readers/writer (bot + cron + web API share this
        # file); busy_timeout lets writers wait instead of failing immediately.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(topics)").fetchall()}
        if "chat_id" not in cols:
            admin = int(os.environ.get("TELEGRAM_CHAT_ID", 0))
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE topics ADD COLUMN chat_id INTEGER NOT NULL DEFAULT 0"
                )
                if admin:
                    self._conn.execute("UPDATE topics SET chat_id = ?", (admin,))
                    now = datetime.utcnow().isoformat(timespec="seconds")
                    self._conn.execute(
                        "INSERT OR IGNORE INTO users (chat_id, username, added_at) VALUES (?, ?, ?)",
                        (admin, "admin", now),
                    )
        # Reassign orphaned topics (chat_id=0) to admin — covers topics added
        # before chat_id was properly set in add_topic().
        orphan_count = self._conn.execute(
            "SELECT COUNT(*) FROM topics WHERE chat_id = 0"
        ).fetchone()[0]
        if orphan_count > 0:
            admin = int(os.environ.get("TELEGRAM_CHAT_ID", 0))
            if admin:
                with self._conn:
                    self._conn.execute(
                        "UPDATE topics SET chat_id = ? WHERE chat_id = 0", (admin,)
                    )
        atm_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(article_topic_matches)").fetchall()}
        if atm_cols and "is_continuation" not in atm_cols:
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE article_topic_matches ADD COLUMN is_continuation INTEGER NOT NULL DEFAULT 0"
                )
        # web_users gained status / NWZ-verification columns after the first cut.
        wu_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(web_users)").fetchall()}
        if wu_cols:
            with self._conn:
                if "status" not in wu_cols:
                    # Existing accounts predate approval — treat them as active.
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
                if "nwz_username" not in wu_cols:
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN nwz_username TEXT")
                if "nwz_verified_at" not in wu_cols:
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN nwz_verified_at TEXT")
                if "token_version" not in wu_cols:
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_topics_chat ON topics(chat_id)"
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ---- users ----

    def get_users(self) -> list[UserRow]:
        rows = self._conn.execute(
            "SELECT chat_id, username, added_at FROM users ORDER BY added_at"
        ).fetchall()
        return [UserRow(**dict(r)) for r in rows]

    def is_user(self, chat_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM users WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return row is not None

    def add_user(self, chat_id: int, username: str = "") -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO users (chat_id, username, added_at) VALUES (?, ?, ?)",
                (chat_id, username, now),
            )

    def remove_user(self, chat_id: int) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM topics WHERE chat_id = ?", (chat_id,))
            self._conn.execute("DELETE FROM users WHERE chat_id = ?", (chat_id,))
            self._conn.execute(
                "UPDATE web_users SET telegram_chat_id = NULL WHERE telegram_chat_id = ?",
                (chat_id,),
            )

    # ---- web accounts ----

    def create_web_user(self, email: str, password_hash: str, role: str = "user", status: str = "pending") -> int:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO web_users (email, password_hash, role, status, created_at) VALUES (?, ?, ?, ?, ?)",
                (email.lower().strip(), password_hash, role, status, now),
            )
        return cur.lastrowid

    def set_web_user_status(self, user_id: int, status: str) -> None:
        with self._conn:
            self._conn.execute("UPDATE web_users SET status = ? WHERE id = ?", (status, user_id))

    def set_nwz_verified(self, user_id: int, nwz_username: str) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "UPDATE web_users SET nwz_username = ?, nwz_verified_at = ? WHERE id = ?",
                (nwz_username, now, user_id),
            )

    def get_web_user_by_email(self, email: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM web_users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
        return dict(row) if row else None

    def get_web_user_by_id(self, user_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM web_users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_web_users(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, email, role, status, telegram_chat_id, nwz_username, nwz_verified_at, created_at "
            "FROM web_users ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]

    def set_web_user_role(self, user_id: int, role: str) -> None:
        with self._conn:
            self._conn.execute("UPDATE web_users SET role = ? WHERE id = ?", (role, user_id))

    def count_web_users(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM web_users").fetchone()[0]

    def increment_token_version(self, user_id: int) -> int:
        """Bump token_version so all existing JWTs for this user become invalid."""
        with self._conn:
            self._conn.execute(
                "UPDATE web_users SET token_version = token_version + 1 WHERE id = ?", (user_id,)
            )
        row = self._conn.execute("SELECT token_version FROM web_users WHERE id = ?", (user_id,)).fetchone()
        return row[0] if row else 0

    def update_password_hash(self, user_id: int, password_hash: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE web_users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
            )

    def get_users_with_topic_count(self) -> list[dict]:
        """Return telegram users with their topic count in a single query (avoids N+1)."""
        rows = self._conn.execute(
            """
            SELECT u.chat_id, u.username, u.added_at,
                   COUNT(t.id) AS topic_count
            FROM users u
            LEFT JOIN topics t ON t.chat_id = u.chat_id
            GROUP BY u.chat_id, u.username, u.added_at
            ORDER BY u.added_at
            """
        ).fetchall()
        return [dict(r) for r in rows]

    def get_topic_for_user(self, chat_id: int, topic_id: int) -> TopicRow | None:
        """Fetch a single topic belonging to chat_id — O(1) vs scanning all topics."""
        row = self._conn.execute(
            "SELECT id, chat_id, name, description, created_at FROM topics WHERE id = ? AND chat_id = ?",
            (topic_id, chat_id),
        ).fetchone()
        return TopicRow(**dict(row)) if row else None

    def create_link_code(self, web_user_id: int, code: str, ttl_minutes: int = 15) -> None:
        from datetime import timedelta
        now = datetime.utcnow()
        expires = now + timedelta(minutes=ttl_minutes)
        with self._conn:
            # one active code per user — replace any previous
            self._conn.execute("DELETE FROM link_codes WHERE web_user_id = ?", (web_user_id,))
            self._conn.execute(
                "INSERT INTO link_codes (code, web_user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (code, web_user_id, now.isoformat(timespec="seconds"), expires.isoformat(timespec="seconds")),
            )

    def admin_stats(self) -> dict:
        """Aggregate counts for the admin dashboard (read-only)."""
        c = self._conn

        def one(sql: str, *p) -> Any:
            row = c.execute(sql, p).fetchone()
            return row[0] if row else 0

        categories = [
            {"name": r[0] or "—", "count": r[1]}
            for r in c.execute(
                "SELECT category_name, COUNT(*) FROM articles GROUP BY category_name ORDER BY 2 DESC LIMIT 8"
            ).fetchall()
        ]
        return {
            "articles": {
                "total": one("SELECT COUNT(*) FROM articles"),
                "editions": one("SELECT COUNT(*) FROM editions"),
                "fts": one("SELECT COUNT(*) FROM articles_fts"),
                "oldest": one("SELECT MIN(publication_date) FROM editions"),
                "newest": one("SELECT MAX(publication_date) FROM editions"),
            },
            "categories": categories,
            "web_users": {
                "total": one("SELECT COUNT(*) FROM web_users"),
                "admins": one("SELECT COUNT(*) FROM web_users WHERE role = 'admin'"),
                "active": one("SELECT COUNT(*) FROM web_users WHERE status = 'active'"),
                "pending": one("SELECT COUNT(*) FROM web_users WHERE status = 'pending'"),
                "nwz_verified": one("SELECT COUNT(*) FROM web_users WHERE nwz_verified_at IS NOT NULL"),
                "linked": one("SELECT COUNT(*) FROM web_users WHERE telegram_chat_id IS NOT NULL"),
            },
            "telegram_users": one("SELECT COUNT(*) FROM users"),
            "topics": {
                "total": one("SELECT COUNT(*) FROM topics"),
                "users_with_topics": one("SELECT COUNT(DISTINCT chat_id) FROM topics"),
                "matches": one("SELECT COUNT(*) FROM article_topic_matches"),
                "classified_editions": one("SELECT COUNT(*) FROM topic_classified_editions"),
                "subscriptions": one("SELECT COUNT(*) FROM committee_subscriptions"),
            },
        }

    # ---- web account linking ----

    def redeem_link_code(self, code: str, chat_id: int, username: str = "") -> str | None:
        """Link a web account to this Telegram chat via a one-time code.

        On success: sets web_users.telegram_chat_id, whitelists the chat in
        `users`, deletes the code, and returns the linked account's email.
        Returns None if the code is unknown or expired.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        row = self._conn.execute(
            "SELECT web_user_id, expires_at FROM link_codes WHERE code = ?", (code,)
        ).fetchone()
        if row is None:
            return None
        if row["expires_at"] < now:
            with self._conn:
                self._conn.execute("DELETE FROM link_codes WHERE code = ?", (code,))
            return None
        web_user_id = row["web_user_id"]
        email_row = self._conn.execute(
            "SELECT email FROM web_users WHERE id = ?", (web_user_id,)
        ).fetchone()
        if email_row is None:
            return None
        with self._conn:
            self._conn.execute(
                "UPDATE web_users SET telegram_chat_id = ? WHERE id = ?",
                (chat_id, web_user_id),
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO users (chat_id, username, added_at) VALUES (?, ?, ?)",
                (chat_id, username, now),
            )
            self._conn.execute("DELETE FROM link_codes WHERE code = ?", (code,))
        return email_row[0]

    # ---- editions ----

    def has_edition(self, catalog: int, content_version: int) -> bool:
        row = self._conn.execute(
            "SELECT content_version FROM editions WHERE catalog = ?", (catalog,)
        ).fetchone()
        return row is not None and row[0] >= content_version

    def save_edition(self, edition: Edition, articles: list[Article]) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                """INSERT OR REPLACE INTO editions
                   (catalog, customer, folder, title, publication_date, pages,
                    content_version, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    edition.catalog, edition.customer, edition.folder,
                    edition.title, edition.publication_date, edition.pages,
                    edition.content_version, now,
                ),
            )
            # Remove old FTS rows for this catalog
            self._conn.execute("DELETE FROM articles WHERE catalog = ?", (edition.catalog,))
            self._conn.execute(
                "DELETE FROM articles_fts WHERE catalog = ?", (edition.catalog,)
            )
            rows: list[tuple[Any, ...]] = []
            fts_rows: list[tuple[Any, ...]] = []
            for a in articles:
                rows.append((
                    edition.catalog, a.refid, a.external_id, a.page,
                    a.category_number, a.category_name, a.title, a.subtitle,
                    "|".join(a.authors), a.content_html, a.content_text, a.priority,
                ))
                fts_rows.append((
                    edition.catalog, a.refid, edition.publication_date,
                    a.category_name, a.title, a.subtitle,
                    " ".join(a.authors), a.content_text,
                ))
            self._conn.executemany(
                """INSERT INTO articles
                   (catalog, refid, external_id, page, category_number, category_name,
                    title, subtitle, authors, content_html, content_text, priority)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            self._conn.executemany(
                """INSERT INTO articles_fts
                   (catalog, refid, pub_date, category_name, title, subtitle,
                    authors, content_text)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                fts_rows,
            )

    # ---- search ----

    @staticmethod
    def _cat_condition(col: str, category: str, categories: list[str] | None) -> tuple[str, list[str]]:
        """Build a category filter (single value or IN-list) for `col`."""
        cats = list(categories) if categories else ([category] if category else [])
        if not cats:
            return "", []
        return f"{col} IN ({','.join('?' * len(cats))})", cats

    def search(
        self,
        query: str,
        limit: int = 40,
        category: str = "",
        date_from: str = "",
        date_to: str = "",
        offset: int = 0,
        categories: list[str] | None = None,
    ) -> list[SearchResult]:
        if not query.strip():
            return self._recent_articles(limit, category, date_from, date_to, offset, categories)

        # Append * to last token for prefix matching on incomplete words
        terms = query.strip().split()
        fts_query = " ".join(terms[:-1] + [terms[-1] + "*"]) if terms else query

        cond, cat_params = self._cat_condition("f.category_name", category, categories)
        cat_filter = f"AND {cond}" if cond else ""
        date_from_filter = "AND f.pub_date >= ?" if date_from else ""
        date_to_filter = "AND f.pub_date <= ?" if date_to else ""

        params: list[Any] = [fts_query, *cat_params]
        if date_from:
            params.append(date_from)
        if date_to:
            params.append(date_to)
        params.append(limit)
        params.append(offset)

        sql = f"""
            SELECT f.catalog, f.refid, f.pub_date, f.category_name,
                   f.title, f.subtitle, f.authors,
                   snippet(articles_fts, 7, '<mark>', '</mark>', '…', 24) AS excerpt,
                   rank
            FROM articles_fts f
            WHERE articles_fts MATCH ?
            {cat_filter} {date_from_filter} {date_to_filter}
            ORDER BY rank, f.catalog, f.refid
            LIMIT ? OFFSET ?
        """
        rows = self._conn.execute(sql, params).fetchall()
        return [SearchResult(**dict(r)) for r in rows]

    def _recent_articles(
        self,
        limit: int,
        category: str,
        date_from: str,
        date_to: str,
        offset: int = 0,
        categories: list[str] | None = None,
    ) -> list[SearchResult]:
        filters = []
        params: list[Any] = []
        cond, cat_params = self._cat_condition("a.category_name", category, categories)
        if cond:
            filters.append(cond)
            params.extend(cat_params)
        if date_from:
            filters.append("e.publication_date >= ?")
            params.append(date_from)
        if date_to:
            filters.append("e.publication_date <= ?")
            params.append(date_to)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        params.append(limit)
        params.append(offset)
        rows = self._conn.execute(
            f"""SELECT a.catalog, a.refid, e.publication_date AS pub_date,
                       a.category_name, a.title, a.subtitle, a.authors,
                       substr(a.content_text, 1, 200) AS excerpt,
                       0.0 AS rank
                FROM articles a
                JOIN editions e ON e.catalog = a.catalog
                {where}
                ORDER BY e.publication_date DESC, a.priority DESC, a.catalog DESC, a.refid DESC
                LIMIT ? OFFSET ?""",
            params,
        ).fetchall()
        return [SearchResult(**dict(r)) for r in rows]

    def count_results(
        self,
        query: str,
        category: str = "",
        date_from: str = "",
        date_to: str = "",
        categories: list[str] | None = None,
    ) -> int:
        """Total articles a search() with these filters matches (all pages)."""
        if not query.strip():
            filters = []
            params: list[Any] = []
            cond, cat_params = self._cat_condition("a.category_name", category, categories)
            if cond:
                filters.append(cond)
                params.extend(cat_params)
            if date_from:
                filters.append("e.publication_date >= ?")
                params.append(date_from)
            if date_to:
                filters.append("e.publication_date <= ?")
                params.append(date_to)
            where = ("WHERE " + " AND ".join(filters)) if filters else ""
            return self._conn.execute(
                f"SELECT COUNT(*) FROM articles a JOIN editions e ON e.catalog = a.catalog {where}",
                params,
            ).fetchone()[0]

        terms = query.strip().split()
        fts_query = " ".join(terms[:-1] + [terms[-1] + "*"]) if terms else query
        cond, cat_params = self._cat_condition("f.category_name", category, categories)
        cat_filter = f"AND {cond}" if cond else ""
        date_from_filter = "AND f.pub_date >= ?" if date_from else ""
        date_to_filter = "AND f.pub_date <= ?" if date_to else ""
        params = [fts_query, *cat_params]
        if date_from:
            params.append(date_from)
        if date_to:
            params.append(date_to)
        return self._conn.execute(
            f"SELECT COUNT(*) FROM articles_fts f WHERE articles_fts MATCH ? {cat_filter} {date_from_filter} {date_to_filter}",
            params,
        ).fetchone()[0]

    def search_any_terms(
        self,
        terms: list[str],
        date_from: str = "",
        date_to: str = "",
        limit: int = 20,
    ) -> list[dict]:
        """FTS5 search with OR logic: any of the given terms must appear.
        Returns raw article dicts with pub_date and a 600-char content preview."""
        if not terms:
            return []
        fts_query = " OR ".join(terms)
        date_from_filter = "AND f.pub_date >= ?" if date_from else ""
        date_to_filter = "AND f.pub_date <= ?" if date_to else ""
        params: list[Any] = [fts_query]
        if date_from:
            params.append(date_from)
        if date_to:
            params.append(date_to)
        params.append(limit)
        rows = self._conn.execute(
            f"""SELECT f.catalog, f.refid, f.pub_date, f.category_name,
                       f.title, f.subtitle, substr(f.content_text, 1, 600) AS content_text
                FROM articles_fts f
                WHERE articles_fts MATCH ?
                {date_from_filter} {date_to_filter}
                ORDER BY rank
                LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def get_article(self, catalog: int, refid: str) -> dict | None:
        row = self._conn.execute(
            """SELECT a.*, e.publication_date, e.title AS edition_title
               FROM articles a
               JOIN editions e ON e.catalog = a.catalog
               WHERE a.catalog = ? AND a.refid = ?""",
            (catalog, refid),
        ).fetchone()
        return dict(row) if row else None

    def categories(self) -> list[str]:
        return [
            r[0] for r in self._conn.execute(
                "SELECT DISTINCT category_name FROM articles ORDER BY category_name"
            ).fetchall()
            if r[0]
        ]

    def edition_dates(self) -> list[str]:
        return [
            r[0] for r in self._conn.execute(
                "SELECT DISTINCT publication_date FROM editions ORDER BY publication_date DESC"
            ).fetchall()
        ]

    # ---- topics ----

    def get_topics(self, chat_id: int) -> list[TopicRow]:
        rows = self._conn.execute(
            "SELECT id, chat_id, name, description, created_at FROM topics WHERE chat_id = ? ORDER BY id",
            (chat_id,),
        ).fetchall()
        return [TopicRow(**dict(r)) for r in rows]

    def get_all_user_topics(self) -> dict[int, list[TopicRow]]:
        """Return {chat_id: [topics]} for all users that have at least one topic."""
        rows = self._conn.execute(
            "SELECT id, chat_id, name, description, created_at FROM topics ORDER BY chat_id, id"
        ).fetchall()
        result: dict[int, list[TopicRow]] = {}
        for r in rows:
            t = TopicRow(**dict(r))
            result.setdefault(t.chat_id, []).append(t)
        return result

    def add_topic(self, chat_id: int, name: str, description: str) -> TopicRow:
        now = datetime.utcnow().isoformat(timespec="seconds")
        cur = self._conn.execute(
            "INSERT INTO topics (chat_id, name, description, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, name.strip(), description.strip(), now),
        )
        self._conn.commit()
        return TopicRow(id=cur.lastrowid, chat_id=chat_id, name=name, description=description, created_at=now)

    def delete_topic(self, topic_id: int) -> None:
        self._conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
        self._conn.commit()

    def update_topic(self, topic_id: int, name: str, description: str) -> None:
        self._conn.execute(
            "UPDATE topics SET name = ?, description = ? WHERE id = ?",
            (name.strip(), description.strip(), topic_id),
        )
        self._conn.commit()

    def reset_topic_for_reclassify(self, chat_id: int, topic_id: int) -> None:
        """Drop a topic's matches and classified-editions cache so it re-runs from scratch."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM article_topic_matches WHERE chat_id = ? AND topic_id = ?",
                (chat_id, topic_id),
            )
            self._conn.execute(
                "DELETE FROM topic_classified_editions WHERE chat_id = ? AND topic_id = ?",
                (chat_id, topic_id),
            )

    # ---- committee subscriptions ----

    def subscribe(self, chat_id: int, committee_name: str) -> bool:
        now = datetime.utcnow().isoformat(timespec="seconds")
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO committee_subscriptions (chat_id, committee_name, created_at) VALUES (?, ?, ?)",
                    (chat_id, committee_name, now),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def unsubscribe(self, chat_id: int, committee_name: str) -> bool:
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM committee_subscriptions WHERE chat_id = ? AND committee_name = ?",
                (chat_id, committee_name),
            )
        return cur.rowcount > 0

    def get_subscriptions(self, chat_id: int) -> list[str]:
        rows = self._conn.execute(
            "SELECT committee_name FROM committee_subscriptions WHERE chat_id = ? ORDER BY committee_name",
            (chat_id,),
        ).fetchall()
        return [r[0] for r in rows]

    def get_all_subscriptions(self) -> dict[int, list[str]]:
        rows = self._conn.execute(
            "SELECT chat_id, committee_name FROM committee_subscriptions ORDER BY chat_id, committee_name"
        ).fetchall()
        result: dict[int, list[str]] = {}
        for r in rows:
            result.setdefault(r[0], []).append(r[1])
        return result

    # ---- article topic matches ----

    def save_article_matches(self, chat_id: int, matches: list[dict]) -> dict[str, int]:
        """Persist GPT match results. Returns {refid: db_id} for use in Telegram buttons.

        matches: [{"topic_id", "catalog", "refid", "pub_date", "title", "summary", "is_continuation"}]
        """
        if not matches:
            return {}
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.executemany(
                """INSERT OR IGNORE INTO article_topic_matches
                   (chat_id, topic_id, catalog, refid, pub_date, title, summary, is_continuation, matched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (chat_id, m["topic_id"], m["catalog"], m["refid"],
                     m["pub_date"], m["title"], m["summary"],
                     int(m.get("is_continuation", False)), now)
                    for m in matches
                ],
            )
        refid_to_id: dict[str, int] = {}
        for m in matches:
            row = self._conn.execute(
                "SELECT id FROM article_topic_matches WHERE chat_id=? AND topic_id=? AND catalog=? AND refid=?",
                (chat_id, m["topic_id"], m["catalog"], m["refid"]),
            ).fetchone()
            if row:
                refid_to_id[m["refid"]] = row[0]
        return refid_to_id

    def get_full_article_for_match(self, match_id: int) -> dict | None:
        """Return full article text + metadata for a given article_topic_matches.id."""
        row = self._conn.execute(
            """SELECT atm.title, atm.pub_date, atm.summary,
                      a.content_text, a.category_name, a.page, a.subtitle
               FROM article_topic_matches atm
               LEFT JOIN articles a ON a.catalog = atm.catalog AND a.refid = atm.refid
               WHERE atm.id = ?""",
            (match_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_article_matches(self, chat_id: int, topic_id: int, limit: int = 30) -> list[dict]:
        rows = self._conn.execute(
            """SELECT catalog, refid, pub_date, title, summary, is_continuation, matched_at
               FROM article_topic_matches
               WHERE chat_id = ? AND topic_id = ?
               ORDER BY pub_date DESC, id DESC
               LIMIT ?""",
            (chat_id, topic_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_article_matches(self, chat_id: int, topic_id: int) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM article_topic_matches WHERE chat_id = ? AND topic_id = ?",
            (chat_id, topic_id),
        ).fetchone()
        return row[0] if row else 0

    def mark_edition_classified(self, chat_id: int, topic_id: int, pub_date: str) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO topic_classified_editions (chat_id, topic_id, pub_date, classified_at) VALUES (?, ?, ?, ?)",
                (chat_id, topic_id, pub_date, now),
            )

    def classified_pub_dates_for_topic(self, chat_id: int, topic_id: int) -> set[str]:
        """Return edition dates already classified for this (chat_id, topic_id) pair."""
        rows = self._conn.execute(
            "SELECT pub_date FROM topic_classified_editions WHERE chat_id = ? AND topic_id = ?",
            (chat_id, topic_id),
        ).fetchall()
        return {r[0] for r in rows}

    # ---- misc ----

    def articles_for_recent_editions(self, limit_editions: int = 3, max_articles: int = 150) -> list[dict]:
        """Return articles from the N most recent editions, newest first, capped at max_articles."""
        dates = self._conn.execute(
            "SELECT publication_date FROM editions ORDER BY publication_date DESC LIMIT ?",
            (limit_editions,),
        ).fetchall()
        if not dates:
            return []
        placeholders = ",".join("?" * len(dates))
        date_values = [r[0] for r in dates]
        return [
            dict(r)
            for r in self._conn.execute(
                f"""SELECT a.catalog, a.refid, a.page, a.category_name, a.title,
                           a.subtitle, a.authors, a.content_text, a.priority,
                           e.publication_date
                    FROM articles a
                    JOIN editions e ON e.catalog = a.catalog
                    WHERE e.publication_date IN ({placeholders})
                    ORDER BY e.publication_date DESC, a.priority DESC
                    LIMIT ?""",
                date_values + [max_articles],
            ).fetchall()
        ]

    def articles_for_date(self, publication_date: str) -> list[dict]:
        return [
            dict(r)
            for r in self._conn.execute(
                """SELECT a.catalog, a.refid, a.page, a.category_name, a.title,
                          a.subtitle, a.authors, a.content_html, a.content_text, a.priority
                   FROM articles a
                   JOIN editions e ON e.catalog = a.catalog
                   WHERE e.publication_date = ?
                   ORDER BY a.priority DESC""",
                (publication_date,),
            ).fetchall()
        ]

    def articles_in_range(self, date_from: str, date_to: str, limit: int = 300) -> list[dict]:
        """Return all articles from editions in the given date range, sorted by page (ascending)."""
        rows = self._conn.execute(
            """SELECT a.page, a.category_name, a.title, e.publication_date
               FROM articles a
               JOIN editions e ON e.catalog = a.catalog
               WHERE e.publication_date >= ? AND e.publication_date <= ?
               ORDER BY e.publication_date DESC, COALESCE(a.page, 999) ASC, a.priority DESC
               LIMIT ?""",
            (date_from, date_to, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_weekly_matches(self, chat_id: int, date_from: str, date_to: str) -> list[dict]:
        """Return all article matches for a user in the given date range, with page info."""
        rows = self._conn.execute(
            """SELECT atm.topic_id, t.name AS topic_name, atm.catalog, atm.refid,
                      atm.pub_date, atm.title, atm.summary, atm.is_continuation,
                      a.page
               FROM article_topic_matches atm
               JOIN topics t ON t.id = atm.topic_id AND t.chat_id = atm.chat_id
               LEFT JOIN articles a ON a.catalog = atm.catalog AND a.refid = atm.refid
               WHERE atm.chat_id = ? AND atm.pub_date >= ? AND atm.pub_date <= ?
               ORDER BY t.id ASC, atm.pub_date DESC, COALESCE(a.page, 999) ASC""",
            (chat_id, date_from, date_to),
        ).fetchall()
        return [dict(r) for r in rows]

    def edition_summary(self) -> list[tuple]:
        return self._conn.execute(
            """SELECT e.publication_date, e.title, e.pages,
                      COUNT(a.refid) AS n_articles,
                      SUM(LENGTH(a.content_text)) AS body_chars
               FROM editions e
               LEFT JOIN articles a ON a.catalog = e.catalog
               GROUP BY e.catalog
               ORDER BY e.publication_date DESC"""
        ).fetchall()
