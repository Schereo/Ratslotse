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
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    topic_id    INTEGER NOT NULL,
    catalog     INTEGER NOT NULL,
    refid       TEXT NOT NULL,
    pub_date    TEXT NOT NULL,
    title       TEXT NOT NULL,
    summary     TEXT NOT NULL,
    matched_at  TEXT NOT NULL,
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
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
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

    def search(
        self,
        query: str,
        limit: int = 40,
        category: str = "",
        date_from: str = "",
        date_to: str = "",
    ) -> list[SearchResult]:
        if not query.strip():
            return self._recent_articles(limit, category, date_from, date_to)

        # Append * to last token for prefix matching on incomplete words
        terms = query.strip().split()
        fts_query = " ".join(terms[:-1] + [terms[-1] + "*"]) if terms else query

        cat_filter = "AND f.category_name = ?" if category else ""
        date_from_filter = "AND f.pub_date >= ?" if date_from else ""
        date_to_filter = "AND f.pub_date <= ?" if date_to else ""

        params: list[Any] = [fts_query]
        if category:
            params.append(category)
        if date_from:
            params.append(date_from)
        if date_to:
            params.append(date_to)
        params.append(limit)

        sql = f"""
            SELECT f.catalog, f.refid, f.pub_date, f.category_name,
                   f.title, f.subtitle, f.authors,
                   snippet(articles_fts, 7, '<mark>', '</mark>', '…', 24) AS excerpt,
                   rank
            FROM articles_fts f
            WHERE articles_fts MATCH ?
            {cat_filter} {date_from_filter} {date_to_filter}
            ORDER BY rank
            LIMIT ?
        """
        rows = self._conn.execute(sql, params).fetchall()
        return [SearchResult(**dict(r)) for r in rows]

    def _recent_articles(
        self,
        limit: int,
        category: str,
        date_from: str,
        date_to: str,
    ) -> list[SearchResult]:
        filters = []
        params: list[Any] = []
        if category:
            filters.append("a.category_name = ?")
            params.append(category)
        if date_from:
            filters.append("e.publication_date >= ?")
            params.append(date_from)
        if date_to:
            filters.append("e.publication_date <= ?")
            params.append(date_to)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        params.append(limit)
        rows = self._conn.execute(
            f"""SELECT a.catalog, a.refid, e.publication_date AS pub_date,
                       a.category_name, a.title, a.subtitle, a.authors,
                       substr(a.content_text, 1, 200) AS excerpt,
                       0.0 AS rank
                FROM articles a
                JOIN editions e ON e.catalog = a.catalog
                {where}
                ORDER BY e.publication_date DESC, a.priority DESC
                LIMIT ?""",
            params,
        ).fetchall()
        return [SearchResult(**dict(r)) for r in rows]

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

    def save_article_matches(self, chat_id: int, matches: list[dict]) -> None:
        """Persist GPT match results. matches: [{"topic_id", "catalog", "refid", "pub_date", "title", "summary"}]"""
        if not matches:
            return
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.executemany(
                """INSERT OR IGNORE INTO article_topic_matches
                   (chat_id, topic_id, catalog, refid, pub_date, title, summary, matched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (chat_id, m["topic_id"], m["catalog"], m["refid"],
                     m["pub_date"], m["title"], m["summary"], now)
                    for m in matches
                ],
            )

    def get_article_matches(self, chat_id: int, topic_id: int, limit: int = 30) -> list[dict]:
        rows = self._conn.execute(
            """SELECT catalog, refid, pub_date, title, summary, matched_at
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
                          a.subtitle, a.authors, a.content_text, a.priority
                   FROM articles a
                   JOIN editions e ON e.catalog = a.catalog
                   WHERE e.publication_date = ?
                   ORDER BY a.priority DESC""",
                (publication_date,),
            ).fetchall()
        ]

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
