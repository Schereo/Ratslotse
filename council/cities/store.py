"""``CitiesStore`` — die einzige Stelle im Städte-Speicher, die SQLite anfasst.

Eigene Datei ``data/cities.sqlite``, nicht ``council.sqlite``: anderer
Lebenszyklus (ein Vollneuaufbau der Städte darf Oldenburg nicht berühren),
andere Größe (in einem Jahr größer als die Rats-Datenbank heute), und der
lokale Abzug bleibt optional.

**Ein Schreiber je Datei.** SQLite verträgt viele Leser, aber der Probelauf
hat fünf Threads auf eine Datei losgelassen und einer starb still an
``database is locked`` — ohne Log-Zeile, weil das Schreiben des Fehlers selbst
am gesperrten Log scheiterte. Parallel ist deshalb nur die Ernte über Städte
hinweg, und die schreibt je Stadt in eine eigene Rohdatei.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from council.cities.model import Batch, Body
from council.cities.schema import MIGRATIONS, SCHEMA, SCHEMA_VERSION

#: Objektarten, die eine Annotation tragen können. Bewusst eine geschlossene
#: Liste: Ein Tippfehler im ``object_kind`` wäre sonst eine Annotation, die
#: niemand je wiederfindet.
OBJECT_KINDS = ("paper", "agenda_item", "meeting", "organization", "body")

#: Die Verschmelzung der beiden Such-Hälften (Reciprocal Rank Fusion).
#: ``RRF_K`` dämpft die Spitze — ohne ihn entschiede der erste Treffer allein.
#: 60 ist der übliche Wert und hier nicht gemessen; die Gewichte dagegen
#: sagen, was zählt: Wer die Wörter wirklich schreibt, steht vorn, die
#: Nachbarschaft ergänzt.
RRF_K = 60
FTS_GEWICHT = 1.0
NB_GEWICHT = 0.6


def _such_stufen(query: str) -> list[str]:
    """Die Anfrage als FTS5-Ausdrücke, von streng nach nachsichtig.

    Dieselbe Überlegung wie bei den Belegen (``council/cities/evidence.py``):
    Erst alle Wörter zusammen, dann das lose ODER. Ein roher Satz mit
    Bindestrichen oder Klammern ist für FTS5 Syntax und wirft.
    """
    roh = [w.strip('"„“()[],.;:?!').strip() for w in
           (query or "").replace("-", " ").replace("/", " ").split()]
    # Kurze Wörter fliegen raus — außer sie sind Großbuchstaben oder Zahlen.
    # In diesem Feld tragen genau die die Bedeutung: „Grundsteuer C" ist
    # etwas anderes als „Grundsteuer B", „B 51" eine bestimmte Straße,
    # „Tempo 30" eine bestimmte Regel. Gemessen: Ohne diese Ausnahme fand
    # „Grundsteuer C" die Kleingarten-Vorlage zur Grundsteuer B zuerst.
    woerter = [w for w in roh
               if len(w) > 2 or (w and (w.isupper() or w.isdigit()))][:8]
    if not woerter:
        return []
    stufen = [" AND ".join(f'"{w}"' for w in woerter)]
    if len(woerter) > 1:
        stufen.append(" OR ".join(f'"{w}"' for w in woerter))
    return stufen


def now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def canonical_hash(obj: Any) -> str:
    """Hash über ein JSON-Objekt, unabhängig von Schlüssel-Reihenfolge.

    Die Schnittstellen liefern dieselben Daten nicht bitgleich; ohne
    Kanonisierung erzeugte jeder Abruf eine neue Rohzeile.
    """
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


class CitiesStore:
    """Lese- und Schreibseite des Städte-Speichers."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False wie in `council/store.py`: FastAPI führt die
        # sync-Dependency und den Endpunkt in (potenziell verschiedenen)
        # Threadpool-Threads aus — die Verbindung wandert also zwischen
        # Threads. Sicher, weil jede Anfrage ihre eigene Store-Instanz
        # bekommt; EINE Verbindung wird nie parallel benutzt.
        self._conn = sqlite3.connect(str(self.path), timeout=60, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=60000")
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._sammelt = False

    # ------------------------------------------------------------------ Basis

    def _migrate(self) -> None:
        row = self._conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        stand = int(row["value"]) if row else 0
        for version, sql in MIGRATIONS:
            if version <= stand:
                continue
            with self._conn:
                self._conn.executescript(sql)
                self._conn.execute(
                    "INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(version),))
            stand = version
        if stand < SCHEMA_VERSION:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> CitiesStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Mehrere Schreibaufrufe zu EINER Transaktion klammern.

        Verschachtelt sich selbst weg: Ein innerer Aufruf innerhalb einer
        äußeren Transaktion öffnet keine zweite.
        """
        if self._sammelt:
            yield
            return
        self._sammelt = True
        try:
            with self._conn:
                yield
        finally:
            self._sammelt = False

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        if self._sammelt:
            yield self._conn
        else:
            with self._conn:
                yield self._conn

    # -------------------------------------------------------------- Schicht 0

    def put_raw_object(self, body_id: str, kind: str, oparl_id: str,
                       body_json: dict, fetched_at: str | None = None) -> bool:
        """Rohantwort ablegen. ``True``, wenn sie neu war (sonst unverändert)."""
        content = canonical_hash(body_json)
        with self._write() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO raw_objects (body_id, kind, oparl_id, fetched_at, content_hash, body_json) "
                "VALUES (?,?,?,?,?,?)",
                (body_id, kind, oparl_id, fetched_at or now(), content,
                 json.dumps(body_json, ensure_ascii=False)))
        return cur.rowcount > 0

    def latest_raw(self, oparl_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT body_json FROM raw_objects WHERE oparl_id=? ORDER BY id DESC LIMIT 1",
            (oparl_id,)).fetchone()
        return json.loads(row["body_json"]) if row else None

    def raw_objects(self, body_id: str, kind: str) -> Iterator[dict]:
        """Je ``oparl_id`` die zuletzt geholte Fassung."""
        rows = self._conn.execute(
            "SELECT body_json FROM raw_objects WHERE id IN ("
            "  SELECT MAX(id) FROM raw_objects WHERE body_id=? AND kind=? GROUP BY oparl_id)"
            " ORDER BY id", (body_id, kind))
        for row in rows:
            yield json.loads(row["body_json"])

    def raw_count(self, body_id: str, kind: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(DISTINCT oparl_id) AS n FROM raw_objects WHERE body_id=? AND kind=?",
            (body_id, kind)).fetchone()
        return int(row["n"])

    def put_raw_file(self, sha256: str, bytes_: int, mime: str | None, path: str,
                     first_seen: str | None = None) -> None:
        with self._write() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO raw_files (sha256, bytes, mime, first_seen, path) VALUES (?,?,?,?,?)",
                (sha256, bytes_, mime, first_seen or now(), path))

    def raw_file(self, sha256: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM raw_files WHERE sha256=?", (sha256,)).fetchone()
        return dict(row) if row else None

    def raw_files(self) -> list[dict]:
        return [dict(r) for r in self._conn.execute("SELECT * FROM raw_files")]

    # -------------------------------------------------------------- Schicht 1

    def upsert_body(self, body: Body) -> None:
        with self._write() as conn:
            conn.execute(
                "INSERT INTO bodies (id, name, state, ris_vendor, oparl_url, license, population, first_fetched, last_fetched) "
                "VALUES (?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, state=excluded.state, "
                "  ris_vendor=excluded.ris_vendor, oparl_url=excluded.oparl_url, "
                "  license=COALESCE(excluded.license, bodies.license), "
                "  population=COALESCE(excluded.population, bodies.population), "
                "  last_fetched=excluded.last_fetched",
                (body.id, body.name, body.state, body.ris_vendor, body.oparl_url,
                 body.license, body.population, now(), now()))

    def bodies(self) -> list[dict]:
        return [dict(r) for r in self._conn.execute("SELECT * FROM bodies ORDER BY name")]

    def body(self, body_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM bodies WHERE id=?", (body_id,)).fetchone()
        return dict(row) if row else None

    def upsert_batch(self, batch: Batch) -> dict[str, int]:
        """Einen ganzen Adapter-Batch schreiben — in EINER Transaktion."""
        with self.transaction():
            conn = self._conn
            conn.executemany(
                "INSERT INTO organizations (id, body_id, name, kind_raw, kind) VALUES (?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, kind_raw=excluded.kind_raw, kind=excluded.kind",
                [(o.id, o.body_id, o.name, o.kind_raw, str(o.kind)) for o in batch.organizations])
            conn.executemany(
                'INSERT INTO meetings (id, body_id, organization_id, name, start, "end", state_raw, cancelled) '
                "VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id, name=excluded.name, "
                '  start=excluded.start, "end"=excluded."end", state_raw=excluded.state_raw, cancelled=excluded.cancelled',
                [(m.id, m.body_id, m.organization_id, m.name, m.start, m.end, m.state_raw, int(m.cancelled))
                 for m in batch.meetings])
            conn.executemany(
                "INSERT INTO agenda_items (id, meeting_id, number, position, name, public, result_raw, outcome, resolution_text) "
                "VALUES (?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET meeting_id=excluded.meeting_id, number=excluded.number, "
                "  position=excluded.position, name=excluded.name, public=excluded.public, "
                "  result_raw=excluded.result_raw, outcome=excluded.outcome, "
                "  resolution_text=COALESCE(excluded.resolution_text, agenda_items.resolution_text)",
                [(a.id, a.meeting_id, a.number, a.position, a.name, int(a.public),
                  a.result_raw, str(a.outcome), a.resolution_text) for a in batch.agenda_items])
            conn.executemany(
                "INSERT INTO papers (id, body_id, reference, name, date, paper_type_raw, kind, "
                "  originator_org_id, under_direction_of_id, web) VALUES (?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET reference=excluded.reference, name=excluded.name, "
                "  date=excluded.date, paper_type_raw=excluded.paper_type_raw, kind=excluded.kind, "
                "  originator_org_id=COALESCE(excluded.originator_org_id, papers.originator_org_id), "
                "  under_direction_of_id=COALESCE(excluded.under_direction_of_id, papers.under_direction_of_id), "
                "  web=COALESCE(excluded.web, papers.web)",
                [(p.id, p.body_id, p.reference, p.name, p.date, p.paper_type_raw, str(p.kind),
                  p.originator_org_id, p.under_direction_of_id, p.web) for p in batch.papers])
            conn.executemany(
                "INSERT INTO files (id, body_id, paper_id, agenda_item_id, meeting_id, role, name, mime, size, access_url, sha256) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET paper_id=COALESCE(excluded.paper_id, files.paper_id), "
                "  agenda_item_id=COALESCE(excluded.agenda_item_id, files.agenda_item_id), "
                "  meeting_id=COALESCE(excluded.meeting_id, files.meeting_id), role=excluded.role, "
                "  name=excluded.name, mime=excluded.mime, size=excluded.size, access_url=excluded.access_url, "
                "  sha256=COALESCE(files.sha256, excluded.sha256)",
                [(f.id, f.body_id, f.paper_id, f.agenda_item_id, f.meeting_id, str(f.role),
                  f.name, f.mime, f.size, f.access_url, f.sha256) for f in batch.files])
            conn.executemany(
                "INSERT INTO consultations (id, paper_id, meeting_id, agenda_item_id, organization_id, role_raw, authoritative) "
                "VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET meeting_id=COALESCE(excluded.meeting_id, consultations.meeting_id), "
                "  agenda_item_id=COALESCE(excluded.agenda_item_id, consultations.agenda_item_id), "
                "  organization_id=COALESCE(excluded.organization_id, consultations.organization_id), "
                "  role_raw=excluded.role_raw, authoritative=excluded.authoritative",
                [(c.id, c.paper_id, c.meeting_id, c.agenda_item_id, c.organization_id,
                  c.role_raw, None if c.authoritative is None else int(c.authoritative))
                 for c in batch.consultations])
        return batch.counts()

    def paper(self, paper_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
        return dict(row) if row else None

    def papers(self, body_id: str | None = None, kind: str | None = None,
               since: str | None = None, until: str | None = None,
               limit: int | None = None) -> list[dict]:
        sql = "SELECT * FROM papers WHERE 1=1"
        args: list[Any] = []
        if body_id:
            sql += " AND body_id=?"; args.append(body_id)
        if kind:
            sql += " AND kind=?"; args.append(kind)
        if since:
            sql += " AND date >= ?"; args.append(since)
        if until:
            sql += " AND date <= ?"; args.append(until)
        sql += " ORDER BY date DESC, id"
        if limit:
            sql += " LIMIT ?"; args.append(limit)
        return [dict(r) for r in self._conn.execute(sql, args)]

    def paper_count(self, body_id: str | None = None) -> int:
        if body_id:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM papers WHERE body_id=?", (body_id,)).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM papers").fetchone()
        return int(row["n"])

    def organizations(self, body_id: str, kind: str | None = None) -> list[dict]:
        if kind:
            rows = self._conn.execute(
                "SELECT * FROM organizations WHERE body_id=? AND kind=? ORDER BY name", (body_id, kind))
        else:
            rows = self._conn.execute(
                "SELECT * FROM organizations WHERE body_id=? ORDER BY name", (body_id,))
        return [dict(r) for r in rows]

    def meetings(self, body_id: str, since: str | None = None) -> list[dict]:
        if since:
            rows = self._conn.execute(
                "SELECT * FROM meetings WHERE body_id=? AND start >= ? ORDER BY start DESC", (body_id, since))
        else:
            rows = self._conn.execute(
                "SELECT * FROM meetings WHERE body_id=? ORDER BY start DESC", (body_id,))
        return [dict(r) for r in rows]

    def agenda_items(self, meeting_id: str) -> list[dict]:
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM agenda_items WHERE meeting_id=? ORDER BY position, number", (meeting_id,))]

    def files_for_paper(self, paper_id: str) -> list[dict]:
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM files WHERE paper_id=? ORDER BY CASE role WHEN 'main' THEN 0 ELSE 1 END, id",
            (paper_id,))]

    def files_without_bytes(self, body_id: str | None = None,
                            roles: Sequence[str] = ("main",),
                            limit: int | None = None) -> list[dict]:
        """Dateien mit URL, aber ohne geladene Bytes — die Arbeitsliste von ``fetch``."""
        marks = ",".join("?" * len(roles))
        sql = (f"SELECT * FROM files WHERE sha256 IS NULL AND access_url IS NOT NULL AND role IN ({marks})")
        args: list[Any] = list(roles)
        if body_id:
            sql += " AND body_id=?"; args.append(body_id)
        sql += " ORDER BY id"
        if limit:
            sql += " LIMIT ?"; args.append(limit)
        return [dict(r) for r in self._conn.execute(sql, args)]

    def file_shas(self, body_id: str | None = None) -> list[tuple[str, str]]:
        """``(file_id, sha256)`` für alles, dessen Bytes schon geholt sind."""
        sql = "SELECT id, sha256 FROM files WHERE sha256 IS NOT NULL"
        args: list[Any] = []
        if body_id:
            sql += " AND body_id=?"; args.append(body_id)
        return [(r["id"], r["sha256"]) for r in self._conn.execute(sql, args)]

    def set_file_sha(self, file_id: str, sha256: str) -> None:
        with self._write() as conn:
            conn.execute("UPDATE files SET sha256=? WHERE id=?", (sha256, file_id))

    def outcome_for_paper(self, paper_id: str) -> dict | None:
        """Das Ergebnis, unter dem ein Papier entschieden wurde.

        ``authoritative`` zuerst (die entscheidende Station der Beratungsfolge),
        danach die späteste Sitzung mit einem Ergebnis. Ohne Treffer ``None`` —
        das ist bei rund der Hälfte der Papiere normal und kein Fehler.
        """
        row = self._conn.execute(
            "SELECT a.outcome, a.result_raw, a.name, m.start, m.name AS meeting_name "
            "FROM consultations c "
            "JOIN agenda_items a ON a.id = c.agenda_item_id "
            "LEFT JOIN meetings m ON m.id = a.meeting_id "
            "WHERE c.paper_id = ? AND a.outcome != 'none' "
            "ORDER BY COALESCE(c.authoritative, 0) DESC, m.start DESC LIMIT 1",
            (paper_id,)).fetchone()
        return dict(row) if row else None

    # -------------------------------------------------------------- Schicht 2

    def put_text(self, file_id: str, extractor: str, version: str, text: str,
                 n_pages: int | None, quality: str) -> None:
        with self._write() as conn:
            conn.execute(
                "INSERT INTO texts (file_id, extractor, version, text, n_pages, quality, extracted_at) "
                "VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(file_id, extractor, version) DO UPDATE SET text=excluded.text, "
                "  n_pages=excluded.n_pages, quality=excluded.quality, extracted_at=excluded.extracted_at",
                (file_id, extractor, version, text, n_pages, quality, now()))

    def text_for_file(self, file_id: str, extractor: str, version: str) -> str | None:
        row = self._conn.execute(
            "SELECT text FROM texts WHERE file_id=? AND extractor=? AND version=?",
            (file_id, extractor, version)).fetchone()
        return row["text"] if row else None

    def text_for_paper(self, paper_id: str, extractor: str | None = None,
                       version: str | None = None) -> str | None:
        """Der Volltext eines Papiers — Hauptdokument zuerst.

        Ohne ``extractor`` gilt der zuletzt geschriebene Text; so bleibt die
        Leseseite arbeitsfähig, während ein neuer Extraktor erst einen Teil des
        Bestands erneuert hat.
        """
        sql = ("SELECT t.text FROM files f JOIN texts t ON t.file_id = f.id "
               "WHERE f.paper_id = ? AND length(t.text) > 0")
        args: list[Any] = [paper_id]
        if extractor:
            sql += " AND t.extractor=?"; args.append(extractor)
        if version:
            sql += " AND t.version=?"; args.append(version)
        sql += (" ORDER BY CASE f.role WHEN 'main' THEN 0 ELSE 1 END, "
                "length(t.text) DESC LIMIT 1")
        row = self._conn.execute(sql, args).fetchone()
        return row["text"] if row else None

    def files_with_text(self, body_id: str | None = None,
                        limit: int | None = None) -> list[dict]:
        """Dateien, für die irgendein Extraktor Text geliefert hat."""
        sql = ("SELECT DISTINCT f.* FROM files f JOIN texts t ON t.file_id = f.id "
               "WHERE length(t.text) > 0")
        args: list[Any] = []
        if body_id:
            sql += " AND f.body_id=?"; args.append(body_id)
        sql += " ORDER BY f.id"
        if limit:
            sql += " LIMIT ?"; args.append(limit)
        return [dict(r) for r in self._conn.execute(sql, args)]

    def text_for_file_any(self, file_id: str) -> str | None:
        """Der längste vorliegende Text zu einer Datei, egal von welchem Extraktor."""
        row = self._conn.execute(
            "SELECT text FROM texts WHERE file_id=? AND length(text) > 0 "
            "ORDER BY length(text) DESC LIMIT 1", (file_id,)).fetchone()
        return row["text"] if row else None

    def files_without_text(self, extractor: str, version: str,
                           body_id: str | None = None,
                           limit: int | None = None) -> list[dict]:
        sql = ("SELECT f.* FROM files f WHERE f.sha256 IS NOT NULL AND NOT EXISTS ("
               "  SELECT 1 FROM texts t WHERE t.file_id = f.id AND t.extractor=? AND t.version=?)")
        args: list[Any] = [extractor, version]
        if body_id:
            sql += " AND f.body_id=?"; args.append(body_id)
        sql += " ORDER BY f.id"
        if limit:
            sql += " LIMIT ?"; args.append(limit)
        return [dict(r) for r in self._conn.execute(sql, args)]

    # -------------------------------------------------------------- Schicht 3

    def put_annotation(self, object_kind: str, object_id: str, annotator: str, version: str,
                       payload: dict, source_hash: str, model: str | None = None,
                       cost_usd: float | None = None) -> None:
        if object_kind not in OBJECT_KINDS:
            raise ValueError(f"unbekannte Objektart {object_kind!r}; erlaubt: {OBJECT_KINDS}")
        with self._write() as conn:
            conn.execute(
                "INSERT INTO annotations (object_kind, object_id, annotator, version, payload, "
                "  source_hash, model, cost_usd, created_at) VALUES (?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(object_kind, object_id, annotator, version) DO UPDATE SET "
                "  payload=excluded.payload, source_hash=excluded.source_hash, model=excluded.model, "
                "  cost_usd=excluded.cost_usd, created_at=excluded.created_at",
                (object_kind, object_id, annotator, version,
                 json.dumps(payload, ensure_ascii=False), source_hash, model, cost_usd, now()))

    def annotation(self, object_kind: str, object_id: str, annotator: str,
                   version: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM annotations WHERE object_kind=? AND object_id=? AND annotator=? AND version=?",
            (object_kind, object_id, annotator, version)).fetchone()
        if not row:
            return None
        out = dict(row)
        out["payload"] = json.loads(out["payload"])
        return out

    def annotations_for(self, annotator: str, version: str,
                        object_kind: str = "paper") -> dict[str, dict]:
        """Alle Annotationen eines Annotators, nach ``object_id``."""
        rows = self._conn.execute(
            "SELECT object_id, payload FROM annotations WHERE annotator=? AND version=? AND object_kind=?",
            (annotator, version, object_kind))
        return {r["object_id"]: json.loads(r["payload"]) for r in rows}

    # ------------------------------------------------------- Ideen-Abfrage

    #: Die Fassungen, aus denen die Ideen-Seite liest. Sie stehen hier und
    #: nicht am Aufrufer, weil die Abfrage sie im SQL braucht — und weil ein
    #: Wechsel der Fassung genau hier auffallen soll.
    IDEEN_CLASSIFY = ("classify", "2")
    #: Die Oberfläche zeigt weiter Fassung 1, bis der Bestand in Fassung 2
    #: durchgerechnet ist (PR 22). Beide liegen nebeneinander — genau dafür
    #: gibt es den Fassungs-Schlüssel.
    IDEEN_FIT = ("fit", "1")
    #: Die Aufwandsklasse hängt als LEFT JOIN dran, nicht als JOIN: Sie ist
    #: jünger als die Urteile, und eine Idee ohne sie soll sichtbar bleiben,
    #: statt aus der Liste zu fallen, bis der Cron nachgezogen hat.
    IDEEN_EFFORT = ("effort", "1")

    # ---- Die drei Abfragen der Ideen-Seite ------------------------------
    #
    # Sie stehen als GANZE, STATISCHE Anweisungen da — mit dreifach
    # wiederholtem FROM, kein zusammengesetztes SQL, kein ``{}``, kein
    # ``%s``. Das ist Absicht, und die Wiederholung ist ihr Preis:
    #
    # ``tests/test_sql_spalten.py`` hält jedes SQL-Literal gegen das Schema.
    # Ein Bruchstück wie ``"SELECT COUNT(*) "`` erkennt er als unvollständig
    # und lässt es durch; ``"SELECT json_extract(f.payload, …)"`` dagegen ist
    # für SQLite ein gültiger SELECT ohne FROM — und meldet sich als „no such
    # column". Und alles mit Platzhaltern im Text überspringt er ganz. Beide
    # Auswege hätten den Wächter genau dort blind gemacht, wo die neueste
    # Abfrage steht.
    #
    # Leere Filter drücken sich als leere Zeichenkette aus: ``''`` heißt
    # „alle". Sonst steht dort eine Liste in Kommas (``,missing,partial,``),
    # und ``instr`` prüft die Zugehörigkeit. Das geht, weil beide Vokabulare
    # geschlossen und kurz sind (``FIT_STATUS``, ``FIT_WORTH``).

    _IDEEN_ZAEHLEN = (
        "SELECT COUNT(*) "
        "FROM papers p "
        "JOIN annotations f ON f.object_kind='paper' AND f.object_id=p.id "
        "  AND f.annotator=? AND f.version=? "
        "JOIN annotations c ON c.object_kind='paper' AND c.object_id=p.id "
        "  AND c.annotator=? AND c.version=? "
        "LEFT JOIN annotations e ON e.object_kind='paper' AND e.object_id=p.id "
        "  AND e.annotator=? AND e.version=? "
        "LEFT JOIN bodies b ON b.id = p.body_id "
        "WHERE json_extract(c.payload, '$.field') = ? "
        "  AND p.body_id != 'oldenburg' "
        "  AND (? = '' OR instr(?, ',' || json_extract(f.payload,'$.status') || ',') > 0) "
        "  AND (? = '' OR instr(?, ',' || json_extract(f.payload,'$.worth') || ',') > 0) "
        "  AND (? = '' OR instr(?, ',' || COALESCE(json_extract(e.payload,'$.effort'), '') || ',') > 0) "
        "  AND (? = '' OR p.body_id = ?)")

    _IDEEN_JE_STATUS = (
        "SELECT json_extract(f.payload, '$.status') AS status, COUNT(*) AS n "
        "FROM papers p "
        "JOIN annotations f ON f.object_kind='paper' AND f.object_id=p.id "
        "  AND f.annotator=? AND f.version=? "
        "JOIN annotations c ON c.object_kind='paper' AND c.object_id=p.id "
        "  AND c.annotator=? AND c.version=? "
        "LEFT JOIN annotations e ON e.object_kind='paper' AND e.object_id=p.id "
        "  AND e.annotator=? AND e.version=? "
        "LEFT JOIN bodies b ON b.id = p.body_id "
        "WHERE json_extract(c.payload, '$.field') = ? "
        "  AND p.body_id != 'oldenburg' "
        "  AND (? = '' OR instr(?, ',' || json_extract(f.payload,'$.status') || ',') > 0) "
        "  AND (? = '' OR instr(?, ',' || json_extract(f.payload,'$.worth') || ',') > 0) "
        "  AND (? = '' OR instr(?, ',' || COALESCE(json_extract(e.payload,'$.effort'), '') || ',') > 0) "
        "  AND (? = '' OR p.body_id = ?)"
        " GROUP BY 1")

    #: Die Reihenfolge beantwortet „was soll ich lesen": erst was sich lohnt,
    #: dann was fehlt, dann worauf sich das Modell verlässt, zuletzt das
    #: Neueste. Sie steht im SQL, damit Blättern und Zählen dieselbe sehen.
    _IDEEN_ZEILEN = (
        "SELECT p.*, c.payload AS classify_json, f.payload AS fit_json, "
        "       e.payload AS effort_json, b.name AS body_name "
        "FROM papers p "
        "JOIN annotations f ON f.object_kind='paper' AND f.object_id=p.id "
        "  AND f.annotator=? AND f.version=? "
        "JOIN annotations c ON c.object_kind='paper' AND c.object_id=p.id "
        "  AND c.annotator=? AND c.version=? "
        "LEFT JOIN annotations e ON e.object_kind='paper' AND e.object_id=p.id "
        "  AND e.annotator=? AND e.version=? "
        "LEFT JOIN bodies b ON b.id = p.body_id "
        "WHERE json_extract(c.payload, '$.field') = ? "
        "  AND p.body_id != 'oldenburg' "
        "  AND (? = '' OR instr(?, ',' || json_extract(f.payload,'$.status') || ',') > 0) "
        "  AND (? = '' OR instr(?, ',' || json_extract(f.payload,'$.worth') || ',') > 0) "
        "  AND (? = '' OR instr(?, ',' || COALESCE(json_extract(e.payload,'$.effort'), '') || ',') > 0) "
        "  AND (? = '' OR p.body_id = ?)"
        " ORDER BY CASE json_extract(f.payload, '$.worth') "
        "            WHEN 'yes' THEN 0 WHEN 'maybe' THEN 1 ELSE 2 END, "
        "          CASE json_extract(f.payload, '$.status') "
        "            WHEN 'missing' THEN 0 WHEN 'partial' THEN 1 ELSE 2 END, "
        "          CASE json_extract(f.payload, '$.confidence') "
        "            WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, "
        "          COALESCE(p.date, '') DESC, p.id LIMIT ? OFFSET ?")

    def _ideen_args(self, field: str, status: Sequence[str], worth: Sequence[str],
                    body_id: str | None, effort: Sequence[str] = ()) -> list[Any]:
        """Die Platzhalter der Ideen-Abfragen, in ihrer Reihenfolge.

        **Alle drei Anweisungen haben dieselbe Reihenfolge**, und diese
        Funktion ist der einzige Ort, an dem sie steht. Wer eine Anweisung um
        einen Filter ergänzt, ergänzt alle drei — sonst zählt die eine anders,
        als die andere liest, und das Blättern springt.
        """
        c_ann, c_ver = self.IDEEN_CLASSIFY
        f_ann, f_ver = self.IDEEN_FIT
        e_ann, e_ver = self.IDEEN_EFFORT
        st = "," + ",".join(status) + "," if status else ""
        wo = "," + ",".join(worth) + "," if worth else ""
        ef = "," + ",".join(effort) + "," if effort else ""
        bo = body_id or ""
        return [f_ann, f_ver, c_ann, c_ver, e_ann, e_ver,
                field, st, st, wo, wo, ef, ef, bo, bo]

    def ideas(self, field: str, status: Sequence[str] = (), worth: Sequence[str] = (),
              body_id: str | None = None, limit: int = 30, offset: int = 0,
              effort: Sequence[str] = ()) -> tuple[list[dict], int, dict[str, int]]:
        """``(zeilen, gesamt, zahl je status)`` für ein Themenfeld.

        **Alles im SQL, nichts in Python.** Die naheliegende Fassung wäre
        ``annotations_for`` zweimal aufzurufen und in Python zu filtern — das
        lädt bei 9.000 Papieren und 1.300 Urteilen den halben Speicher in
        jeden Request. Filtern, Sortieren und Zählen gehören ins Backend
        (Wurzel-``CLAUDE.md``), und hier heißt Backend: in die Abfrage.
        """
        args = self._ideen_args(field, status, worth, body_id, effort)
        gesamt = int(self._conn.execute(self._IDEEN_ZAEHLEN, args).fetchone()[0])
        zaehler = {r["status"]: r["n"]
                   for r in self._conn.execute(self._IDEEN_JE_STATUS, args)}
        rows = self._conn.execute(self._IDEEN_ZEILEN, args + [limit, offset])
        return [dict(r) for r in rows], gesamt, zaehler

    #: Die Volltextsuche über fremde Vorlagen, samt Urteil wo vorhanden.
    #: Wieder als GANZE Anweisung, aus demselben Grund wie oben.
    _SUCHE = (
        "SELECT p.*, b.name AS body_name, c.payload AS classify_json, "
        # Spaltengewichte statt nacktem bm25: paper_id und body_id zählen gar
        # nicht, der TITEL zehnfach, die Zusammenfassung vierfach, das
        # Aktenzeichen dreifach, der Volltext einfach.
        #
        # Gemessen: Ohne Gewichte stand unter „Hitzeaktionsplan" die
        # Osnabrücker „Kommunale Wärmeplanung" auf Platz eins — ein langes
        # Dokument, das das Wort im Fließtext streift —, und Braunschweigs
        # „Konzept zur Hitzeaktionsplanung" gar nicht in den ersten drei.
        "       f.payload AS fit_json, "
        "       bm25(papers_fts, 0.0, 0.0, 10.0, 3.0, 1.0, 4.0) AS rang "
        "FROM papers_fts x "
        "JOIN papers p ON p.id = x.paper_id "
        "LEFT JOIN bodies b ON b.id = p.body_id "
        "LEFT JOIN annotations c ON c.object_kind='paper' AND c.object_id=p.id "
        "  AND c.annotator=? AND c.version=? "
        "LEFT JOIN annotations f ON f.object_kind='paper' AND f.object_id=p.id "
        "  AND f.annotator=? AND f.version=? "
        "WHERE papers_fts MATCH ? AND p.body_id != 'oldenburg' "
        "  AND (? = '' OR p.body_id = ?) "
        "ORDER BY rang LIMIT ?")

    #: Ein Papier samt Urteil, für die zweite Hälfte der Suche.
    _EIN_PAPIER = (
        "SELECT p.*, b.name AS body_name, c.payload AS classify_json, "
        "       f.payload AS fit_json, 0.0 AS rang "
        "FROM papers p "
        "LEFT JOIN bodies b ON b.id = p.body_id "
        "LEFT JOIN annotations c ON c.object_kind='paper' AND c.object_id=p.id "
        "  AND c.annotator=? AND c.version=? "
        "LEFT JOIN annotations f ON f.object_kind='paper' AND f.object_id=p.id "
        "  AND f.annotator=? AND f.version=? "
        "WHERE p.id = ?")

    def search_ideas(self, query: str, model: str, body_id: str | None = None,
                     limit: int = 30, nachbarn_je: int = 4) -> list[dict]:
        """Freie Suche über fremde Vorlagen — Volltext plus Nachbarschaft.

        **Warum keine Vektor-Suche über die Anfrage.** Sie bräuchte
        ``fastembed`` im Web-Dienst, und das ist es bewusst nicht (Wurzel-
        ``CLAUDE.md``): Der Deploy und der laufende Dienst sollen von einem
        220-MB-Modell unberührt bleiben. Die KI-Frage fällt aus demselben
        Grund auf Stichwortsuche zurück, wenn es fehlt.

        **Was stattdessen die zweite Hälfte macht.** Die Nachbarschaften sind
        schon gerechnet und liegen in der Datenbank. Zu den besten
        Volltexttreffern kommen deshalb deren nächste Verwandte aus ANDEREN
        Städten dazu. Das fängt genau den Fall, den der Probelauf als Schwäche
        reiner Stichwortsuche gemessen hat: Wer „Hitzeschutz" tippt, findet
        über den Text nur, was so heißt — über die Nachbarschaft aber auch den
        „Hitzeaktionsplan".

        Verschmolzen wird nach umgekehrtem Rang (RRF): Ein Treffer, der auf
        beiden Wegen auftaucht, steigt; die Gewichte stehen als Konstanten da,
        damit man sie messen kann statt sie zu raten.
        """
        c_ann, c_ver = self.IDEEN_CLASSIFY
        f_ann, f_ver = self.IDEEN_FIT
        vorne = [c_ann, c_ver, f_ann, f_ver]
        bo = body_id or ""

        volltext: list[dict] = []
        for anfrage in _such_stufen(query):
            try:
                volltext = [dict(r) for r in self._conn.execute(
                    self._SUCHE, vorne + [anfrage, bo, bo, limit * 2])]
            except sqlite3.OperationalError:
                continue          # kaputte FTS-Syntax ist kein Serverfehler
            if volltext:
                break

        punkte: dict[str, float] = {}
        zeilen: dict[str, dict] = {}
        for rang, r in enumerate(volltext, 1):
            punkte[r["id"]] = punkte.get(r["id"], 0.0) + FTS_GEWICHT / (RRF_K + rang)
            zeilen[r["id"]] = r

        # Zweite Hälfte: die Nachbarn der besten Volltexttreffer.
        #
        # Je Papier zählt der BESTE Nachbarschafts-Beitrag, nicht die Summe.
        # Gemessen: Addiert man sie, sammelt ein Papier, das Nachbar mehrerer
        # Ausgangstreffer ist, mehr Punkte als ein echter Volltexttreffer —
        # unter „Hitzeaktionsplan" stand so die Osnabrücker „Kommunale
        # Wärmeplanung" auf Platz eins, ohne das Wort überhaupt zu enthalten.
        nachbar_punkte: dict[str, float] = {}
        for r in volltext[:3]:
            for rang, n in enumerate(self.neighbors("paper", r["id"], model,
                                                    limit=nachbarn_je), 1):
                if not n.get("body_id") or n["body_id"] == "oldenburg":
                    continue
                wert = NB_GEWICHT / (RRF_K + rang)
                if wert > nachbar_punkte.get(n["b_id"], 0.0):
                    nachbar_punkte[n["b_id"]] = wert
                if n["b_id"] not in zeilen:
                    zeile = self._conn.execute(self._EIN_PAPIER, vorne + [n["b_id"]]).fetchone()
                    if zeile:
                        zeilen[n["b_id"]] = dict(zeile)
        for kennung, wert in nachbar_punkte.items():
            punkte[kennung] = punkte.get(kennung, 0.0) + wert

        beste = sorted((i for i in punkte if i in zeilen),
                       key=lambda i: -punkte[i])[:limit]
        return [dict(zeilen[i], score=round(punkte[i], 5)) for i in beste]

    def idea_fields(self) -> list[dict]:
        """Je Themenfeld die Zahlen für die Übersicht.

        Eine Abfrage statt zwölf: Die Seite zeigt alle Felder nebeneinander,
        und zwölf Rundreisen für zwölf Kacheln wären genau die Sorte
        Frontend-Logik, die nicht ins Frontend gehört.
        """
        c_ann, c_ver = self.IDEEN_CLASSIFY
        f_ann, f_ver = self.IDEEN_FIT
        rows = self._conn.execute(
            "SELECT json_extract(c.payload, '$.field') AS field, COUNT(*) AS total, "
            "  SUM(json_extract(f.payload,'$.status')='missing') AS missing, "
            "  SUM(json_extract(f.payload,'$.status')='partial') AS partial, "
            "  SUM(json_extract(f.payload,'$.status')='present') AS present, "
            "  SUM(json_extract(f.payload,'$.worth')='yes') AS worth_yes "
            "FROM papers p "
            "JOIN annotations f ON f.object_kind='paper' AND f.object_id=p.id "
            "  AND f.annotator=? AND f.version=? "
            "JOIN annotations c ON c.object_kind='paper' AND c.object_id=p.id "
            "  AND c.annotator=? AND c.version=? "
            "WHERE p.body_id != 'oldenburg' AND field IS NOT NULL "
            "GROUP BY 1 ORDER BY worth_yes DESC, total DESC",
            (f_ann, f_ver, c_ann, c_ver))
        return [dict(r) for r in rows]

    def annotations_missing(self, object_kind: str, annotator: str, version: str,
                            body_id: str | None = None, limit: int | None = None,
                            source_hashes: dict[str, str] | None = None) -> list[dict]:
        """Objekte ohne Annotation dieses Annotators.

        Mit ``source_hashes`` (id → Hash der Eingabe) kommen zusätzlich die
        Objekte zurück, deren Eingabe sich seit dem letzten Lauf geändert hat —
        so rechnet ein Lauf nur, was nötig ist.
        """
        if object_kind != "paper":
            raise NotImplementedError("bisher nur für Papiere gebraucht")
        sql = ("SELECT p.* FROM papers p WHERE NOT EXISTS ("
               "  SELECT 1 FROM annotations a WHERE a.object_kind='paper' AND a.object_id=p.id "
               "    AND a.annotator=? AND a.version=?)")
        args: list[Any] = [annotator, version]
        if body_id:
            sql += " AND p.body_id=?"; args.append(body_id)
        sql += " ORDER BY p.date DESC, p.id"
        if limit:
            sql += " LIMIT ?"; args.append(limit)
        offen = [dict(r) for r in self._conn.execute(sql, args)]
        if source_hashes:
            bekannt = {r["object_id"]: r["source_hash"] for r in self._conn.execute(
                "SELECT object_id, source_hash FROM annotations WHERE object_kind=? AND annotator=? AND version=?",
                (object_kind, annotator, version))}
            veraltet = [oid for oid, h in source_hashes.items()
                        if oid in bekannt and bekannt[oid] != h]
            if veraltet:
                marks = ",".join("?" * len(veraltet))
                offen += [dict(r) for r in self._conn.execute(
                    f"SELECT * FROM papers WHERE id IN ({marks})", veraltet)]
        return offen

    def annotation_values(self, annotator: str, version: str, key: str,
                          object_kind: str = "paper") -> list[tuple[str, Any]]:
        """``(object_id, payload[key])`` für alle Annotationen — für Auswertungen."""
        rows = self._conn.execute(
            "SELECT object_id, json_extract(payload, '$.' || ?) AS value FROM annotations "
            "WHERE annotator=? AND version=? AND object_kind=?",
            (key, annotator, version, object_kind))
        return [(r["object_id"], r["value"]) for r in rows]

    # -------------------------------------------------------------- Schicht 4

    def put_chunks(self, file_id: str, chunks: Sequence[tuple[int, str, int, int]]) -> None:
        with self._write() as conn:
            conn.executemany(
                "INSERT INTO chunks (file_id, chunk_idx, chunk_text, span_start, span_end, text_hash) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(file_id, chunk_idx) DO UPDATE SET "
                "  chunk_text=excluded.chunk_text, span_start=excluded.span_start, "
                "  span_end=excluded.span_end, text_hash=excluded.text_hash",
                [(file_id, idx, text, start, end, text_hash(text))
                 for idx, text, start, end in chunks])

    def chunks_for_file(self, file_id: str) -> list[dict]:
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM chunks WHERE file_id=? ORDER BY chunk_idx", (file_id,))]

    def chunks_without_embedding(self, model: str, limit: int | None = None) -> list[dict]:
        sql = ("SELECT c.* FROM chunks c WHERE NOT EXISTS ("
               "  SELECT 1 FROM chunk_embeddings e WHERE e.file_id=c.file_id "
               "    AND e.chunk_idx=c.chunk_idx AND e.model=? AND e.text_hash=c.text_hash)"
               " ORDER BY c.file_id, c.chunk_idx")
        args: list[Any] = [model]
        if limit:
            sql += " LIMIT ?"; args.append(limit)
        return [dict(r) for r in self._conn.execute(sql, args)]

    def chunk_matrix(self, model: str, body_id: str) -> tuple[list[str], list[int], bytes]:
        """Alle Chunk-Vektoren einer Stadt am Stück — Papier, Chunk, Rohbytes.

        **Warum am Stück und nicht je Anfrage.** Der Beleg-Lauf fragt zehntausend
        Mal nach den nächsten Chunks; jedes Mal einzeln zu lesen hieße, dieselben
        34.000 Vektoren zehntausendmal von der Platte zu holen. Der Aufrufer hält
        die Matrix, so wie ``council.embeddings._matrix`` es für die KI-Frage tut.

        Ein Chunk gehört einer Datei, eine Datei einem Papier — der Beleg ist
        aber immer das Papier. Deshalb kommt die Papier-Kennung schon hier mit
        heraus und nicht erst nach einem zweiten Rundgang.
        """
        rows = self._conn.execute(
            "SELECT f.paper_id, e.chunk_idx, e.vector FROM chunk_embeddings e "
            "JOIN files f ON f.id = e.file_id "
            "JOIN papers p ON p.id = f.paper_id "
            "WHERE e.model = ? AND p.body_id = ? "
            "ORDER BY f.paper_id, e.chunk_idx", (model, body_id)).fetchall()
        papiere = [r["paper_id"] for r in rows]
        indizes = [r["chunk_idx"] for r in rows]
        return papiere, indizes, b"".join(r["vector"] for r in rows)

    def chunk_text(self, paper_id: str, chunk_idx: int) -> str | None:
        """Der Wortlaut eines Chunks — für den Beleg, der ihn zitiert."""
        row = self._conn.execute(
            "SELECT c.chunk_text FROM chunks c JOIN files f ON f.id = c.file_id "
            "WHERE f.paper_id = ? AND c.chunk_idx = ? LIMIT 1",
            (paper_id, chunk_idx)).fetchone()
        return row["chunk_text"] if row else None

    def put_chunk_embeddings(self, rows: Sequence[tuple[str, int, str, str, bytes]]) -> None:
        with self._write() as conn:
            conn.executemany(
                "INSERT INTO chunk_embeddings (file_id, chunk_idx, model, text_hash, vector) VALUES (?,?,?,?,?) "
                "ON CONFLICT(file_id, chunk_idx, model) DO UPDATE SET text_hash=excluded.text_hash, vector=excluded.vector",
                list(rows))

    def put_object_embedding(self, object_kind: str, object_id: str, model: str,
                             source_hash: str, vector: bytes) -> None:
        with self._write() as conn:
            conn.execute(
                "INSERT INTO object_embeddings (object_kind, object_id, model, source_hash, vector) "
                "VALUES (?,?,?,?,?) ON CONFLICT(object_kind, object_id, model) DO UPDATE SET "
                "  source_hash=excluded.source_hash, vector=excluded.vector",
                (object_kind, object_id, model, source_hash, vector))

    def object_embedding_hashes(self, model: str, object_kind: str = "paper") -> dict[str, str]:
        return {r["object_id"]: r["source_hash"] for r in self._conn.execute(
            "SELECT object_id, source_hash FROM object_embeddings WHERE model=? AND object_kind=?",
            (model, object_kind))}

    def object_embeddings(self, model: str, object_kind: str = "paper") -> tuple[list[str], list[str], bytes]:
        """``(ids, body_ids, vektorpuffer)`` — der Puffer wird beim Aufrufer zur Matrix."""
        rows = self._conn.execute(
            "SELECT e.object_id, COALESCE(p.body_id, '') AS body_id, e.vector FROM object_embeddings e "
            "LEFT JOIN papers p ON p.id = e.object_id "
            "WHERE e.model=? AND e.object_kind=? ORDER BY e.object_id", (model, object_kind)).fetchall()
        ids = [r["object_id"] for r in rows]
        bodies = [r["body_id"] for r in rows]
        buf = b"".join(bytes(r["vector"]) for r in rows)
        return ids, bodies, buf

    def replace_neighbors(self, model: str, a_kind: str, a_id: str,
                          rows: Sequence[tuple[str, str, float]]) -> None:
        with self._write() as conn:
            conn.execute("DELETE FROM neighbors WHERE model=? AND a_kind=? AND a_id=?",
                         (model, a_kind, a_id))
            conn.executemany(
                "INSERT INTO neighbors (model, a_kind, a_id, b_kind, b_id, score, computed_at) "
                "VALUES (?,?,?,?,?,?,?)",
                [(model, a_kind, a_id, b_kind, b_id, score, now()) for b_kind, b_id, score in rows])

    def neighbors(self, a_kind: str, a_id: str, model: str, limit: int = 8,
                  exclude_body: str | None = None) -> list[dict]:
        sql = ("SELECT n.b_kind, n.b_id, n.score, p.body_id, p.name, p.reference, p.date, "
               "       p.kind, p.web, p.paper_type_raw "
               "FROM neighbors n LEFT JOIN papers p ON p.id = n.b_id "
               "WHERE n.a_kind=? AND n.a_id=? AND n.model=?")
        args: list[Any] = [a_kind, a_id, model]
        if exclude_body:
            sql += " AND COALESCE(p.body_id,'') != ?"; args.append(exclude_body)
        sql += " ORDER BY n.score DESC LIMIT ?"; args.append(limit)
        return [dict(r) for r in self._conn.execute(sql, args)]

    def replace_idea_clusters(self, model: str, version: str,
                              zeilen: list[tuple[str, str, int, str, float]]) -> int:
        """Die Cluster einer Fassung ersetzen — alles oder nichts.

        Halbe Cluster wären schlimmer als keine: Eine Auswertung, die „in vier
        Städten" sagt, weil die fünfte gerade beim Schreiben verloren ging,
        führt in die Irre. Deshalb Löschen und Schreiben in EINER Transaktion.
        """
        with self._write() as conn:
            conn.execute("DELETE FROM idea_clusters WHERE model=? AND version=?",
                         (model, version))
            conn.executemany(
                "INSERT INTO idea_clusters (model, version, cluster_id, paper_id, score) "
                "VALUES (?,?,?,?,?)", zeilen)
        return len(zeilen)

    def cluster_of(self, paper_id: str, model: str, version: str = "1") -> list[dict]:
        """Alle Mitglieder des Clusters, in dem dieses Papier liegt.

        Mit Stadt, Titel, Datum, Art und ERGEBNIS — das Ergebnis ist der Grund
        für die Abfrage: „Wie ging dieselbe Idee anderswo aus?" lässt sich ohne
        es nicht beantworten. Leer, wenn das Papier in keinem Cluster ist, und
        das ist der Normalfall.

        Ganze statische Anweisung, kein zusammengesetztes SQL — sonst prüft
        ``tests/test_sql_spalten.py`` sie nicht (s. die Ideen-Abfragen oben).
        """
        rows = self._conn.execute(
            "SELECT p.id, p.body_id, p.name, p.date, p.kind, p.web, "
            "       b.name AS body_name, k.score, k.cluster_id, "
            "       c.payload AS classify_json "
            "FROM idea_clusters k "
            "JOIN idea_clusters eigen ON eigen.model = k.model "
            "  AND eigen.version = k.version AND eigen.cluster_id = k.cluster_id "
            "  AND eigen.paper_id = ? "
            "JOIN papers p ON p.id = k.paper_id "
            "LEFT JOIN bodies b ON b.id = p.body_id "
            "LEFT JOIN annotations c ON c.object_kind='paper' AND c.object_id=p.id "
            "  AND c.annotator='classify' AND c.version='2' "
            "WHERE k.model = ? AND k.version = ? "
            "ORDER BY k.score DESC, p.date DESC",
            (paper_id, model, version))
        return [dict(r) for r in rows]

    def cluster_stats(self, model: str, version: str = "1") -> list[dict]:
        """Je Cluster: Mitglieder, Städte, und ob Oldenburg dabei ist.

        Die letzte Spalte ist die eigentliche Frage: Ein Cluster OHNE
        Oldenburger Mitglied ist eine Idee, die mehrere Städte haben und
        Oldenburg nicht — und das ist die Liste, um die es geht.
        """
        rows = self._conn.execute(
            "SELECT k.cluster_id, COUNT(*) AS members, "
            "       COUNT(DISTINCT p.body_id) AS cities, "
            "       MAX(CASE WHEN p.body_id='oldenburg' THEN 1 ELSE 0 END) AS has_oldenburg "
            "FROM idea_clusters k JOIN papers p ON p.id = k.paper_id "
            "WHERE k.model = ? AND k.version = ? "
            "GROUP BY k.cluster_id ORDER BY cities DESC, members DESC",
            (model, version))
        return [dict(r) for r in rows]

    def fts_upsert(self, paper_id: str, body_id: str, name: str, reference: str | None,
                   text: str | None, summary: str | None) -> None:
        with self._write() as conn:
            conn.execute("DELETE FROM papers_fts WHERE paper_id=?", (paper_id,))
            conn.execute(
                "INSERT INTO papers_fts (paper_id, body_id, name, reference, text, summary) VALUES (?,?,?,?,?,?)",
                (paper_id, body_id, name, reference or "", (text or "")[:20000], summary or ""))

    def fts_search(self, query: str, body_id: str | None = None, limit: int = 20) -> list[dict]:
        sql = ("SELECT f.paper_id, f.body_id, p.name, p.date, p.kind, p.reference, p.web, "
               "       bm25(papers_fts) AS rank FROM papers_fts f "
               "JOIN papers p ON p.id = f.paper_id WHERE papers_fts MATCH ?")
        args: list[Any] = [query]
        if body_id:
            sql += " AND f.body_id=?"; args.append(body_id)
        sql += " ORDER BY rank LIMIT ?"; args.append(limit)
        try:
            return [dict(r) for r in self._conn.execute(sql, args)]
        except sqlite3.OperationalError:
            # Kaputte FTS-Syntax in einer Nutzerfrage ist kein Serverfehler.
            return []

    # ------------------------------------------------------------- Pipeline

    def stage_done(self, object_kind: str, object_id: str, stage: str, version: str) -> bool:
        row = self._conn.execute(
            "SELECT status FROM stages WHERE object_kind=? AND object_id=? AND stage=? AND version=?",
            (object_kind, object_id, stage, version)).fetchone()
        return bool(row) and row["status"] == "done"

    def mark_stage(self, object_kind: str, object_id: str, stage: str, version: str,
                   status: str, error: str | None = None) -> None:
        with self._write() as conn:
            conn.execute(
                "INSERT INTO stages (object_kind, object_id, stage, version, status, error, at) "
                "VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(object_kind, object_id, stage, version) DO UPDATE SET "
                "  status=excluded.status, error=excluded.error, at=excluded.at",
                (object_kind, object_id, stage, version, status, error, now()))

    def unmapped_outcomes(self, body_id: str, limit: int = 10) -> list[dict]:
        """Ergebnistexte einer Stadt, die auf ``none`` fallen — häufigste zuerst.

        Womit man eine neue Stadt anschließt: Was hier oben steht, versteht
        ``council.cities.model.outcome`` nicht. Manches gehört dorthin
        („schriftliche Stellungnahme" ist wirklich kein Ergebnis), manches ist
        eine Lücke in der Regel — und eine tausendfache Lücke macht die halbe
        Beschlusslage einer Stadt unsichtbar.
        """
        rows = self._conn.execute(
            "SELECT a.result_raw, COUNT(*) AS n FROM agenda_items a "
            "JOIN meetings m ON m.id = a.meeting_id "
            "WHERE m.body_id = ? AND a.outcome = 'none' "
            "  AND a.result_raw IS NOT NULL AND length(trim(a.result_raw)) > 0 "
            "GROUP BY a.result_raw ORDER BY n DESC LIMIT ?", (body_id, limit))
        return [dict(r) for r in rows]

    def stage_counts(self, stage: str, version: str) -> dict[str, int]:
        return {r["status"]: r["n"] for r in self._conn.execute(
            "SELECT status, COUNT(*) AS n FROM stages WHERE stage=? AND version=? GROUP BY status",
            (stage, version))}

    def stats(self, embed_model: str | None = None) -> list[dict]:
        """Kennzahlen je Stadt — für den Cron und das Admin-Panel.

        ``papers_unclassified`` und ``papers_unembedded`` sind der **Rückstand**:
        Ein Papier ohne Einordnung ist für den Vergleich unsichtbar, eines ohne
        Vektor hat keine Nachbarn und kann deshalb weder Beleg sein noch einen
        bekommen. Beide Zahlen wachsen still — der Wochen-Cron ordnet nur
        ``CITIES_ANNOTATE_MAX`` Vorlagen je Lauf ein, und nach einem Backfill
        der Historie steht plötzlich das Zehnfache an. Am 08.09.2026 waren 19 %
        des Bestands eingeordnet, ohne dass es irgendwo aufgefallen wäre.
        """
        modell = embed_model or ""
        rows = self._conn.execute(
            "SELECT b.id, b.name, b.state, b.ris_vendor, b.license, b.last_fetched, "
            "  (SELECT COUNT(*) FROM papers p WHERE p.body_id=b.id) AS papers, "
            "  (SELECT COUNT(*) FROM papers p WHERE p.body_id=b.id AND NOT EXISTS ("
            "     SELECT 1 FROM annotations a WHERE a.object_kind='paper' "
            "       AND a.object_id=p.id AND a.annotator='classify')) AS papers_unclassified, "
            "  (SELECT COUNT(*) FROM papers p WHERE p.body_id=b.id AND NOT EXISTS ("
            "     SELECT 1 FROM object_embeddings o WHERE o.object_kind='paper' "
            "       AND o.object_id=p.id AND o.model=?)) AS papers_unembedded, "
            "  (SELECT COUNT(DISTINCT p.id) FROM papers p JOIN files f ON f.paper_id=p.id "
            "     JOIN texts t ON t.file_id=f.id WHERE p.body_id=b.id AND length(t.text) > 0) "
            "   AS papers_with_text, "
            "  (SELECT COUNT(*) FROM meetings m WHERE m.body_id=b.id) AS meetings, "
            "  (SELECT COUNT(*) FROM agenda_items a JOIN meetings m ON m.id=a.meeting_id "
            "     WHERE m.body_id=b.id) AS agenda_items, "
            "  (SELECT COUNT(*) FROM agenda_items a JOIN meetings m ON m.id=a.meeting_id "
            "     WHERE m.body_id=b.id AND a.outcome != 'none') AS agenda_items_with_outcome, "
            "  (SELECT COUNT(DISTINCT c.paper_id) FROM consultations c "
            "     JOIN papers p ON p.id=c.paper_id "
            "     JOIN agenda_items a ON a.id=c.agenda_item_id "
            "     WHERE p.body_id=b.id AND a.outcome != 'none') AS papers_with_outcome, "
            "  (SELECT COUNT(DISTINCT c.paper_id) FROM consultations c "
            "     JOIN papers p ON p.id=c.paper_id "
            "     WHERE p.body_id=b.id) AS papers_with_consultation, "
            "  (SELECT COUNT(*) FROM annotations an JOIN papers p ON p.id=an.object_id "
            "     WHERE p.body_id=b.id) AS annotations "
            "FROM bodies b ORDER BY b.name", (modell,))
        return [dict(r) for r in rows]
