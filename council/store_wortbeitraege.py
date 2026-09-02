"""Wortbeiträge und Videos: wer im Rat was gesagt hat.

Achter Schnitt an ``store.py``. Die Beiträge stammen aus zwei Quellen — dem
Protokoll (mit Seitenzahl) und dem Transkript des Livestreams — und werden
über dieselben Tabellen abgefragt.

``wortbeitraege_person`` liegt hier und nicht bei den Personen: Sie fragt
ÜBER eine Person, aber sie fragt nach Wortbeiträgen. Die Namensregeln, die
sie dafür braucht, kommen aus ``PersonenMixin`` — beide sitzen auf derselben
Klasse.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime

from kern.dbfehler import tabelle_fehlt

class WortbeitraegeMixin:
    """Die Wortbeitrags-Abfragen — nur zum Mitvererben."""

    def save_video_results(self, ksinr: int, video_id: str, model: str,
                           results: list[dict]) -> int:
        """Replace the stored video results for one session.

        Ein Lauf ersetzt den Bestand der Sitzung komplett — der Extraktor
        liefert immer das Gesamtbild eines Videos, und ein zweiter Lauf
        (z. B. nachdem YouTube die Untertitel nachgereicht hat) soll alte
        Teilstände nicht überleben lassen."""
        now = datetime.now().isoformat(timespec="seconds")
        with self.transaktion():
            self._conn.execute("DELETE FROM council_video_results WHERE ksinr = ?", (ksinr,))
            for r in results:
                self._conn.execute(
                    """INSERT INTO council_video_results
                       (ksinr, item_number, outcome, vote, no_votes,
                        abstentions, quote, video_id, video_seconds, model, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (ksinr, r["item_number"], r["outcome"], r.get("vote"),
                     r.get("no_votes"), r.get("abstentions"), r["quote"],
                     video_id, r.get("video_seconds"), model, now),
                )
        return len(results)

    def get_video_results(self, ksinr: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM council_video_results WHERE ksinr = ? ORDER BY id", (ksinr,)
        ).fetchall()
        return [dict(r) for r in rows]

    def sessions_needing_video_check(self, since: str) -> list[dict]:
        """Rat-Sitzungen ohne Protokoll-Beschlüsse und ohne Video-Ergebnisse.

        Nur der Stadtrat — O1 überträgt kein anderes Gremium (s. lib/live.ts
        im Frontend). Sobald das Protokoll da ist, übernehmen dessen
        Beschlüsse; die Sitzung fällt dann von selbst aus dieser Liste."""
        rows = self._conn.execute(
            """SELECT s.ksinr, s.committee, s.session_date, s.session_time
               FROM council_sessions s
               WHERE s.committee IN ('Rat', 'Stadtrat', 'Rat der Stadt Oldenburg')
                 AND s.session_date >= ?
                 AND s.session_date <= date('now')
                 AND NOT EXISTS (SELECT 1 FROM council_decisions d WHERE d.ksinr = s.ksinr)
                 AND NOT EXISTS (SELECT 1 FROM council_video_results v WHERE v.ksinr = s.ksinr)
               ORDER BY s.session_date DESC""",
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]

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
        teile = " OR ".join(["w.speaker LIKE ?"] * len(varianten))
        rows = self._conn.execute(
            f"SELECT w.id, w.ksinr, w.page, w.speaker, w.party, w.kind, w.top, w.text, "
            f"       cs.committee, cs.session_date "
            f"FROM council_speeches w JOIN council_sessions cs ON cs.ksinr = w.ksinr "
            f"WHERE {teile} ORDER BY cs.session_date DESC LIMIT ?",
            [f"%{v}%" for v in varianten] + [limit]).fetchall()
        return [dict(r) for r in rows]

    def wortbeitraege_person(self, name: str, committee: str | None = None,
                             offset: int = 0, limit: int = 20) -> dict:
        """Wortbeiträge einer Person — seitenweise und nach Gremium filterbar.

        Gefiltert wird in Python statt in SQL: Die Zuordnung Sprecher→Person
        kennt Schreibvarianten (s. ``_spricht_diese_person``), die keine
        LIKE-Bedingung abbildet. Der Rohbestand je Person ist klein genug
        (Vielredner kommen auf ~800 Beiträge), um ihn einmal zu holen.

        Rückgabe: ``items`` (die angeforderte Seite), ``total`` (nach
        Gremien-Filter), ``overall`` (ohne Filter) und ``committees`` als Facetten
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
            return {"items": [], "total": 0, "overall": 0, "committees": []}
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
                 if any(self._spricht_diese_person(w.get("speaker") or "", v, n, bekannt)
                        for n, v in formen)]
        meine.sort(key=lambda w: (w.get("session_date") or "", w["id"]), reverse=True)

        from collections import Counter
        zaehler = Counter(w["committee"] for w in meine if w.get("committee"))
        gefiltert = [w for w in meine if not committee or w.get("committee") == committee]
        page = gefiltert[max(0, offset): max(0, offset) + max(1, min(limit, 100))]
        return {
            "items": [{"kind": w["kind"], "agenda_item": w["top"], "text": w["text"],
                       "committee": w["committee"], "session_date": w["session_date"]}
                      for w in page],
            "total": len(gefiltert),
            "overall": len(meine),
            "committees": [{"committee": k, "n": n} for k, n in zaehler.most_common()],
        }

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
                "DELETE FROM council_speeches_fts WHERE rowid IN "
                "(SELECT id FROM council_speeches WHERE ksinr = ?)", (ksinr,))
            self._conn.execute(
                "DELETE FROM council_speeches_embeddings WHERE contribution_id IN "
                "(SELECT id FROM council_speeches WHERE ksinr = ?)", (ksinr,))
            self._conn.execute("DELETE FROM council_speeches WHERE ksinr = ?", (ksinr,))
            self._conn.execute(
                "UPDATE council_protocols SET contributions_extracted_at = ? WHERE ksinr = ?",
                (now, ksinr))
            n = 0
            for pos, r in enumerate(rows):
                text = (r.get("text") or "").strip()
                if not text:
                    continue
                cur = self._conn.execute(
                    "INSERT INTO council_speeches "
                    "(ksinr, position, kind, top, speaker, party, text, answer, extracted_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (ksinr, pos, r.get("kind") or "speech", r.get("top"),
                     r.get("speaker"), r.get("party"), text[:2000],
                     (r.get("answer") or "").strip()[:2000] or None, now))
                inhalt = " ".join(x for x in (r.get("speaker"), r.get("party"), r.get("top"),
                                              text, r.get("answer")) if x)
                self._conn.execute(
                    "INSERT INTO council_speeches_fts(rowid, content) VALUES (?, REPLACE(?, 'ß', 'ss'))",
                    (cur.lastrowid, inhalt))
                n += 1
            return n

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
               "AND p.contributions_extracted_at IS NULL "
               "ORDER BY p.ksinr DESC")
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r[0] for r in self._conn.execute(sql).fetchall()]

    def wortbeitrag_ids_nach_art(self, kind: str) -> list[int]:
        """Alle Wortbeitrags-ids einer Art — Filter für den Zusagen-Kanal.
        Klein genug (1.437 Zusagen), um sie je Frage zu holen."""
        return [r[0] for r in self._conn.execute(
            "SELECT id FROM council_speeches WHERE kind = ?", (kind,))]

    def wortbeitraege_by_ids(self, ids: list[int]) -> list[dict]:
        if not ids:
            return []
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"""SELECT w.id, w.ksinr, w.page, w.kind, w.top, w.speaker, w.party,
                       w.text, w.answer, cs.committee, cs.session_date
                FROM council_speeches w
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
            "SELECT id, speaker, text FROM council_speeches "
            "WHERE ksinr = ? AND page IS NULL", (ksinr,))]

    def set_wortbeitrag_seite(self, contribution_id: int, page: int) -> None:
        with self._conn:
            self._conn.execute("UPDATE council_speeches SET page = ? WHERE id = ?",
                               (page, contribution_id))

    def ksinr_mit_beitraegen_ohne_offsets(self, limit: int = 0) -> list[int]:
        """Protokolle mit Wortbeiträgen, aber ohne Seiten-Offsets — die
        Arbeitsliste des Backfills (Re-Download nötig)."""
        sql = ("SELECT DISTINCT w.ksinr FROM council_speeches w "
               "JOIN council_protocols p ON p.ksinr = w.ksinr "
               "WHERE p.page_offsets IS NULL AND p.document_url IS NOT NULL "
               "ORDER BY w.ksinr DESC")
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r[0] for r in self._conn.execute(sql)]

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
                                      speaker: str = "") -> list[dict]:
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
            nummer, title = self._top_schluessel(d.get("title"))
            # item_number ist die verlässlichere Nummer (title trägt sie selten).
            nr = str(d.get("item_number") or "").strip() or nummer
            if not title or any(s in title for s in self._SAMMEL_TOPS):
                continue
            stationen.setdefault(int(ks), []).append((nr, title, d["id"]))
        if not stationen:
            return []
        ph = ",".join("?" * len(stationen))
        sprecher_filter = " AND w.speaker LIKE ?" if speaker.strip() else ""
        params: list = list(stationen)
        if sprecher_filter:
            params.append(f"%{speaker.strip()}%")
        rows = self._conn.execute(
            f"""SELECT w.id, w.ksinr, w.page, w.kind, w.top, w.speaker, w.party,
                       w.text, w.answer, cs.committee, cs.session_date
                FROM council_speeches w
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
        """BM25 über die Beiträge → ``[(contribution_id, score)]``; Fehler → leer.
        Term-Aufbereitung wie bei search_presse_fts (OR-Verknüpfung)."""
        terms = [t for t in re.findall(r"[0-9a-zäöü]+", query.lower().replace("ß", "ss"))
                 if len(t) >= 3][:12]
        if not terms:
            return []
        try:
            rows = self._conn.execute(
                "SELECT rowid, rank FROM council_speeches_fts "
                "WHERE council_speeches_fts MATCH ? ORDER BY rank LIMIT ?",
                (" OR ".join(terms), limit)).fetchall()
            return [(r[0], -float(r[1])) for r in rows]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []

    def wortbeitraege_missing_embeddings(self) -> list[dict]:
        rows = self._conn.execute(
            """SELECT w.id, w.text, w.speaker, w.top FROM council_speeches w
               LEFT JOIN council_speeches_embeddings e ON e.contribution_id = w.id
               WHERE e.contribution_id IS NULL""").fetchall()
        return [dict(r) for r in rows]

    def replace_wortbeitrag_embedding(self, contribution_id: int, text_hash: str, vector: bytes) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_speeches_embeddings (contribution_id, text_hash, vector) "
                "VALUES (?, ?, ?)", (contribution_id, text_hash, vector))

    def wortbeitraege_embedding_rows(self) -> list[tuple]:
        return self._conn.execute(
            "SELECT contribution_id, vector FROM council_speeches_embeddings").fetchall()

    def wortbeitraege_embeddings_version(self) -> str:
        """Billiger Cache-Schlüssel für die In-Memory-Matrix."""
        row = self._conn.execute(
            "SELECT COUNT(*), COALESCE(MAX(contribution_id), 0) "
            "FROM council_speeches_embeddings").fetchone()
        return f"{row[0]}-{row[1]}"
