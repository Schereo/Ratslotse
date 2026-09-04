"""Das Quiz: Fragen auswählen, zählen, zurückziehen.

Vierter Schnitt an ``store.py``. Die drei ``_migrate_quiz_*`` sind bewusst
NICHT mitgekommen — Migrationen gehören der Datenbank als Ganzem und bleiben
neben dem übrigen Schema.

``list_entities`` und ``entity_detail`` ebenso wenig: Das Quiz fragt Themen ab,
besitzt sie aber nicht.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from council.store_basis import StoreBasis

class QuizMixin(StoreBasis):
    """Die Quiz-Abfragen — nur zum Mitvererben."""

    # Themen ohne Entität dahinter (kuratierte Spezial-Gebiete) → Anzeigename.
    _THEMA_LABELS = {"haushalt": "Stadt-Haushalt"}

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
                    (r["area_type"], r["area_key"], r["category"], r.get("difficulty", "medium"),
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
            "WHERE q.area_type = 'topic' AND q.status = 'active'").fetchall()
        return [{"area_key": r["area_key"],
                 "label": r["name"] or self._THEMA_LABELS.get(r["area_key"], r["area_key"]),
                 "lat": r["lat"], "lon": r["lon"]}
                for r in rows]

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
