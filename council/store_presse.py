"""Presse-Mitteilungen der Stadt und Bauleitplan-Beteiligungen.

Beides füllt derselbe Cron (``scripts/check_presse.py``, täglich 5:15) aus
denselben Stadt-Quellen, und beides wird nur dort geschrieben und in der
KI-Frage gelesen. Deshalb liegen sie zusammen, obwohl es zwei Gegenstände
sind: Eine Datei mit drei Methoden je Gegenstand wäre keine Ordnung, sondern
Buchhaltung.

Dritter Schnitt an ``store.py``; das Rezept steht in ``council/CLAUDE.md``.
"""
from __future__ import annotations

import json
import re
import sqlite3

from kern.dbfehler import tabelle_fehlt
from council.store_basis import StoreBasis

class PresseMixin(StoreBasis):
    """Presse und Beteiligungen — nur zum Mitvererben."""

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
                "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
                "ort TEXT, schritt TEXT, valid_from TEXT, valid_until TEXT, url TEXT NOT NULL, "
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
                    "UPDATE council_beteiligungen SET title = ?, ort = ?, valid_from = ?, valid_until = ?, "
                    "plan_nrs = ?, fetched_at = ?, status = 'laufend', beendet_am = NULL "
                    "WHERE url = ? AND schritt = ?",
                    (r["title"], r.get("ort"), r.get("valid_from"), r.get("valid_until"),
                     json.dumps(r.get("plan_nrs") or [], ensure_ascii=False), now, url, schritt))
                if cur.rowcount:
                    akt += 1
                    continue
                self._conn.execute(
                    "INSERT INTO council_beteiligungen "
                    "(title, ort, schritt, valid_from, valid_until, url, plan_nrs, fetched_at, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'laufend')",
                    (r["title"], r.get("ort"), schritt, r.get("valid_from"), r.get("valid_until"), url,
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
            felder = "title, ort, schritt, valid_from, valid_until, url, plan_nrs" + (
                ", status, beendet_am" if hat_status else "")
            sql = f"SELECT {felder} FROM council_beteiligungen"
            if nur_laufende and hat_status:
                sql += " WHERE status = 'laufend'"
            rows = self._conn.execute(sql).fetchall()
        except sqlite3.OperationalError as fehler:  # Tabelle entsteht erst mit dem ersten Lauf
            if not tabelle_fehlt(fehler):
                raise
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

    # ------------------------------------------------------------ Sperrungen

    def save_road_closures(self, rows: list[dict]) -> dict:
        """Stand der Sperrungen (Geoportal, council/sperrungen.py) fortschreiben:
        Bekanntes aktualisieren, Neues anlegen, Verschwundenes als beendet
        markieren — wie bei den Beteiligungen: Die Stadt löscht eine Sperrung,
        sobald sie vorbei ist, wir behalten sie als Historie."""
        from datetime import datetime as _dt
        now = _dt.utcnow().isoformat(timespec="seconds")
        heute = now[:10]
        neu = akt = 0
        with self._conn:
            for r in rows:
                werte = (r["street"], r.get("reason"), r.get("kind"), r.get("kind_label"),
                         r.get("valid_from"), r.get("valid_until"), r.get("description"),
                         r.get("geojson"), r.get("lat"), r.get("lon"),
                         json.dumps(r.get("places") or [], ensure_ascii=False), now)
                cur = self._conn.execute(
                    "UPDATE council_road_closures SET street = ?, reason = ?, kind = ?, kind_label = ?, "
                    "valid_from = ?, valid_until = ?, description = ?, geojson = ?, lat = ?, lon = ?, "
                    "places = ?, fetched_at = ?, status = 'laufend', ended_at = NULL WHERE objectid = ?",
                    (*werte, r["objectid"]))
                if cur.rowcount:
                    akt += 1
                else:
                    self._conn.execute(
                        "INSERT INTO council_road_closures (objectid, street, reason, kind, kind_label, "
                        "valid_from, valid_until, description, geojson, lat, lon, places, fetched_at, status) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'laufend')", (r["objectid"], *werte))
                    neu += 1
            ids = [r["objectid"] for r in rows]
            if ids:
                ph = ",".join("?" * len(ids))
                cur = self._conn.execute(
                    f"UPDATE council_road_closures SET status = 'beendet', ended_at = ? "
                    f"WHERE status = 'laufend' AND objectid NOT IN ({ph})", (heute, *ids))
            else:
                cur = self._conn.execute(
                    "UPDATE council_road_closures SET status = 'beendet', ended_at = ? WHERE status = 'laufend'",
                    (heute,))
        return {"laufend": len(rows), "neu": neu, "aktualisiert": akt, "beendet": cur.rowcount}

    def district_road_closures(self, place_id: str, *, min_share: float = 0.2) -> list[dict]:
        """Laufende Sperrungen, deren Linie zu ``min_share`` im Ortsbereich
        liegt — die ohne Enddatum zuerst (Dauer-Sperrungen), sonst nach Ende."""
        try:
            rows = self._conn.execute(
                "SELECT objectid, street, reason, kind, kind_label, valid_from, valid_until, description, "
                "geojson, lat, lon FROM council_road_closures c WHERE c.status = 'laufend' AND EXISTS ("
                "SELECT 1 FROM json_each(c.places) je WHERE json_extract(je.value, '$.place_id') = ? "
                "AND json_extract(je.value, '$.share') >= ?) "
                "ORDER BY (valid_until IS NULL) DESC, valid_until, street", (place_id, min_share)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        out = []
        for r in rows:
            d = dict(r)
            d["id"] = d.pop("objectid")
            try:
                d["geometry"] = json.loads(d.pop("geojson") or "null")
            except ValueError:
                d["geometry"] = None
            out.append(d)
        return out

    # ------------------------------------------------------------ Presse-Orte

    def location_primary_places(self, slugs: list[str], *, min_share: float = 0.5) -> dict[str, str]:
        """Slug → Ortsbereich-ID für Orte, die die Orts-Pipeline kennt (Anteil
        ab ``min_share``; bei mehreren der größte)."""
        slugs = [s for s in dict.fromkeys(slugs) if s]
        if not slugs:
            return {}
        ph = ",".join("?" * len(slugs))
        rows = self._conn.execute(
            f"SELECT location_slug, place_id, share FROM council_location_districts "
            f"WHERE location_slug IN ({ph}) AND place_id IS NOT NULL AND share >= ? "
            f"ORDER BY share DESC", (*slugs, min_share)).fetchall()
        out: dict[str, str] = {}
        for r in rows:
            out.setdefault(r["location_slug"], r["place_id"])
        return out

    def save_press_places(self, press_id: int, rows: list[dict]) -> None:
        """Orte einer Mitteilung ersetzen; ohne Treffer bleibt EINE Zeile mit
        ``place_id`` NULL — geprüft, nichts gefunden."""
        from datetime import datetime as _dt
        now = _dt.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute("DELETE FROM council_press_places WHERE press_id = ?", (press_id,))
            if rows:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO council_press_places (press_id, place_id, via, evidence, checked_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [(press_id, r["place_id"], r.get("via"), r.get("evidence"), now) for r in rows])
            else:
                self._conn.execute(
                    "INSERT OR IGNORE INTO council_press_places (press_id, place_id, via, evidence, checked_at) "
                    "VALUES (?, NULL, NULL, NULL, ?)", (press_id, now))

    def press_without_places(self, limit: int = 500) -> list[dict]:
        """Mitteilungen, die noch nie verortet wurden — neueste zuerst."""
        try:
            rows = self._conn.execute(
                "SELECT p.id, p.title, p.text FROM council_press p WHERE NOT EXISTS ("
                "SELECT 1 FROM council_press_places pp WHERE pp.press_id = p.id) "
                "ORDER BY p.date DESC, p.id DESC LIMIT ?", (limit,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def district_press(self, place_id: str, *, days: int = 120, limit: int = 6) -> list[dict]:
        """Die jüngsten Mitteilungen der Stadt mit Bezug auf diesen Ortsbereich."""
        from datetime import date, timedelta
        seit = (date.today() - timedelta(days=days)).isoformat()
        try:
            rows = self._conn.execute(
                "SELECT p.id, p.title, p.date, p.url, substr(p.text, 1, 220) AS teaser, pp.evidence, pp.via "
                "FROM council_press_places pp JOIN council_press p ON p.id = pp.press_id "
                "WHERE pp.place_id = ? AND p.date >= ? ORDER BY p.date DESC, p.id DESC LIMIT ?",
                (place_id, seit, limit)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def save_presse(self, url: str, news_id: int | None, title: str,
                    date: str | None, text: str) -> int:
        """Upsert einer Pressemitteilung (Schlüssel: url) inkl. FTS-Zeile.
        Liefert die Zeilen-id."""
        from datetime import datetime as _dt
        now = _dt.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT INTO council_press (url, news_id, title, date, text, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(url) DO UPDATE SET news_id=excluded.news_id, "
                "title=excluded.title, date=excluded.date, text=excluded.text, "
                "fetched_at=excluded.fetched_at",
                (url, news_id, title, date, text, now),
            )
            pid = self._conn.execute(
                "SELECT id FROM council_press WHERE url = ?", (url,)).fetchone()[0]
            self._conn.execute("DELETE FROM council_press_fts WHERE rowid = ?", (pid,))
            self._conn.execute(
                "INSERT INTO council_press_fts(rowid, content) VALUES (?, REPLACE(?, 'ß', 'ss'))",
                (pid, f"{title} {text[:8000]}"),
            )
        return pid

    def presse_urls(self) -> set[str]:
        """Alle bekannten PM-URLs — der Backfill überspringt Vorhandenes."""
        return {r[0] for r in self._conn.execute("SELECT url FROM council_press").fetchall()}

    def presse_by_ids(self, ids: list[int]) -> list[dict]:
        """PM-Zeilen (ohne Volltext-Riesen: Text auf 600 Zeichen gekürzt) in id-Reihenfolge."""
        if not ids:
            return []
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT id, url, title, date, substr(text, 1, 600) AS auszug "
            f"FROM council_press WHERE id IN ({ph})", ids).fetchall()
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
                "SELECT rowid, rank, snippet(council_press_fts, 0, '', '', ' … ', 16) "
                "FROM council_press_fts WHERE council_press_fts MATCH ? ORDER BY rank LIMIT ?",
                (" OR ".join(terms), limit)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [(r[0], -float(r[1]), r[2] or "") for r in rows]

    def presse_missing_embeddings(self) -> list[dict]:
        """PMs, deren Chunk-Vektoren fehlen oder deren Text sich geändert hat
        (SHA-256-Abgleich, analog vorlagen_missing_embeddings)."""
        import hashlib
        stored = dict(self._conn.execute(
            "SELECT press_id, MIN(text_hash) FROM council_press_embeddings GROUP BY press_id"
        ).fetchall())
        out = []
        for r in self._conn.execute("SELECT id, title, text FROM council_press").fetchall():
            blob = f"{r['title']}\n{r['text']}"
            h = hashlib.sha256(blob.encode("utf-8", "replace")).hexdigest()
            if stored.get(r["id"]) != h:
                out.append({"id": r["id"], "text": blob, "text_hash": h})
        return out

    def replace_presse_embeddings(self, press_id: int, text_hash: str,
                                  chunks: list[tuple[str, bytes]]) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_press_embeddings WHERE press_id = ?", (press_id,))
            self._conn.executemany(
                "INSERT INTO council_press_embeddings "
                "(press_id, chunk_idx, text_hash, chunk_text, vector) VALUES (?, ?, ?, ?, ?)",
                [(press_id, i, text_hash, t, v) for i, (t, v) in enumerate(chunks)],
            )

    def get_presse_embeddings(self) -> list:
        return self._conn.execute(
            "SELECT press_id, chunk_text, vector FROM council_press_embeddings "
            "ORDER BY press_id, chunk_idx").fetchall()

    def presse_embeddings_version(self) -> tuple:
        count = self._conn.execute("SELECT COUNT(*) FROM council_press_embeddings").fetchone()[0]
        data_version = self._conn.execute("PRAGMA data_version").fetchone()[0]
        return (count, data_version)
