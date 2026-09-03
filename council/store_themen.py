"""Themen und Entitäten: Katalog, Aliasse, Steckbriefe, Verwandtschaft.

Sechster Schnitt an ``store.py``. Ein „Thema" ist hier die Entität, die aus
den Beschlüssen aufsteigt (Stadion, Fliegerhorst, Radverkehr) — mit ihren
Schreibweisen (``council.aliases``), ihrer Beschreibung und ihren Nachbarn.

Zwei Nachbarn sind ausdrücklich NICHT mitgekommen: ``search_decisions_fts``
und ``embeddings_version`` gehören der Suche, auch wenn die Themen-Seite sie
benutzt. Die Ortsangaben einer Entität liegen seit dem zweiten Schnitt in
``store_orte.py``.
"""
from __future__ import annotations

import json

from council.parties import order_key
from council.store_helfer import _dedup_keys

class ThemenMixin:
    """Die Themen-Abfragen — nur zum Mitvererben."""

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

    def local_reason_titles(self, slugs: list[str], place, date_from: str) -> dict[str, str]:
        """Je Entität der Titel des JÜNGSTEN Beschlusses, der sie mit DIESEM
        Ortsbereich verbindet.

        Das ist die Antwort auf „warum steht das hier?". Bei der Kommunalen
        Wärmeplanung unter Kreyenbrück ist sie „Maßnahme Machbarkeitsstudien"
        — ein stadtweites Vorhaben mit einer Machbarkeitsstudie genau dort
        (Tims Befund, 03.09.2026: „es bräuchte manchmal nur eine ganz kurze
        Erklärung und dann wird man direkt verstehen, warum es diesen Bezug
        gibt").

        Der Beleg aus ``council_decision_locations.evidence`` taugt dafür
        NICHT: Dort steht der Textschnipsel, an dem die Zuordnung hing
        („Stadtteils Kreyenbrück") — er wiederholt nur den Ortsnamen. Der
        Beschlusstitel sagt, was dort passiert.
        """
        if not slugs:
            return {}
        platz = ",".join("?" * len(slugs))
        rows = self._conn.execute(
            f"""SELECT e.slug, d.title, cs.session_date
                  FROM council_entities e
                  JOIN council_entity_links el ON el.entity_id = e.id
                  JOIN council_decisions d ON d.id = el.decision_id
                  JOIN council_sessions cs ON cs.ksinr = d.ksinr
                  JOIN council_decision_locations dl ON dl.decision_id = d.id
                  JOIN council_locations l ON l.slug = dl.location_slug
                 WHERE e.slug IN ({platz}) AND cs.session_date >= ?
                   AND (l.place_id = ? OR l.local_area_id = ? OR l.district = ?)
                 ORDER BY cs.session_date DESC, d.id DESC""",
            (*slugs, date_from, place.id, place.id, place.name)).fetchall()
        # Der erste Treffer je Slug gewinnt — die Abfrage ist absteigend
        # sortiert, ein GROUP BY mit MAX() über zwei Spalten wäre in SQLite
        # zwar erlaubt, aber die Sortierung hier ist die, die auch der
        # Vorschlag selbst benutzt.
        neueste: dict[str, str] = {}
        for r in rows:
            neueste.setdefault(r["slug"], r["title"] or "")
        return {k: v for k, v in neueste.items() if v}

    def decision_texts_since(self, date_from: str) -> list[str]:
        """Titel und Zusammenfassung jedes Beschlusses seit ``date_from`` — das
        Zählgut der Stadtthemen (``council.city_topics``). Nur echte
        Beschlüsse, keine Unterpunkte: Ein Beschluss soll ein Thema einmal
        zählen, nicht je Absatz."""
        rows = self._conn.execute(
            """SELECT d.title, d.summary FROM council_decisions d
               JOIN council_sessions s ON s.ksinr = d.ksinr
               WHERE s.session_date >= ? AND d.kind = 'decision'""",
            (date_from,),
        ).fetchall()
        return [f"{r[0] or ''} {r[1] or ''}" for r in rows]

    def suggested_entity_topics(self, days_back: int = 365, limit: int = 12,
                                place_id: str | None = None) -> list[dict]:
        """Konkrete Orte/Projekte mit jüngster Ratsaktivität — Futter für die
        Themen-Vorschläge. Ersetzt die reine Schlagwort-Häufigkeit, die
        Verwaltungsvokabeln belohnte („Bericht", „Annahme"): Menschen
        interessieren sich für ein Bauprojekt oder ihre Straße, nicht für
        Beschluss-Formalien. Sortiert nach jüngster Aktivität, bei Gleichstand
        gewinnt der interessantere Stoff (Interest-Score, neutral 50)."""
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()
        # Auf einen Ortsbereich eingeschränkt: „was ist gerade in MEINEM
        # Stadtteil los?". Die Bedingung sitzt auf dem Beschluss, nicht auf der
        # Entität — eine Entität hat selbst keinen Ort, sie erbt ihn von den
        # Beschlüssen, in denen sie vorkommt.
        #
        # Und genau deshalb HIER der Hauptbereich (``nur_hauptbereich=True``):
        # Erbt eine Entität den Ort über jeden mitgenannten Ortsbezug, dann
        # reicht eine lange Straße, um fremde Themen einzuschleppen. Siehe
        # ``_place_location_condition``.
        ort_bedingung, ort_params = "", []
        if place_id:
            place = self.resolve_place(place_id)
            if not place:
                return []
            bedingung, params = self._place_location_condition(
                place, nur_hauptbereich=True)
            # Zweiter Weg, eng und ohne Einschleppen: Die Entität IST ein Ort,
            # der in diesem Bereich liegt. Das gilt auch für die
            # Mehrfach-Zugehörigkeit — und genau dafür ist es da: Die
            # Alexanderstraße hat als Hauptbereich Bürgerfelde, verläuft aber
            # auch durchs Ehnernviertel, den Ziegelhof, Alexandersfeld und
            # Dietrichsfeld. Als Vorschlag ist sie dort richtig, denn sie liegt
            # dort. Der Unterschied zur weiten Bedingung: Vorgeschlagen wird
            # nur, was SELBST im Bereich liegt, nicht alles, was einmal im
            # selben Beschluss danebenstand.
            ort_bedingung = (
                " AND (EXISTS (SELECT 1 FROM council_decision_locations dl "
                "JOIN council_locations l ON l.slug = dl.location_slug "
                f"WHERE dl.decision_id = d.id AND {bedingung})"
                " OR e.slug IN (SELECT location_slug FROM council_location_districts "
                "WHERE place_id = ? OR district = ?))"
            )
            ort_params = [*params, place.id, place.name]
        rows = self._conn.execute(
            f"""SELECT e.slug, e.name, e.kind, m.description,
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
               WHERE e.kind IN ('place', 'project') AND cs.session_date >= ?{ort_bedingung}
               GROUP BY e.id
               HAVING n_recent >= 2
               ORDER BY n_recent DESC, avg_interest DESC, e.name
               LIMIT ?""",
            # Mit Ortsfilter großzügig holen und ERST DANACH sieben. Das Limit
            # greift auf der rohen Reihenfolge (Häufigkeit), und die führen im
            # Stadtteil die Adressen aus Bebauungsplänen an: Bei ``LIMIT 16``
            # füllten sie die Liste, und nach dem Sieben blieb fast nichts übrig
            # — auf dem Prod-Auszug lieferte Osternburg so EINEN Vorschlag statt
            # sechs. Die Obergrenze bleibt als Riegel gegen einen Ausreißer.
            (cutoff, cutoff, *ort_params, 400 if place_id else limit),
        ).fetchall()
        kandidaten = [dict(r) for r in rows]
        if not place_id:
            return kandidaten
        return self._rank_local_suggestions(kandidaten, place, cutoff)[:limit]

    @classmethod
    def _looks_like_street(cls, name: str) -> bool:
        kern = name.split("/")[0].strip()
        return bool(cls._STRASSE.search(kern)) or bool(cls._STRASSE_VORNE.match(kern))

    def _rank_local_suggestions(self, kandidaten: list[dict], place, cutoff: str) -> list[dict]:
        """Aussieben und ordnen, was für EINEN Ortsbereich vorgeschlagen wird.

        Die rohe Abfrage liefert alles, was in einem Beschluss mit Ortsbezug
        vorkam — und das ist zu grob. Am Prod-Bestand nachgemessen (01.09.2026)
        standen unter „Osternburg" ganz oben „Sandweg, Ostweg, Danziger Straße",
        die Cäcilienbrücke gar nicht; unter „Eversten" stand „Fliegerhorst".
        Drei Ursachen, drei Regeln:

        1. **Ein anderer Ortsbereich** ist kein Vorschlag für diesen. „Kreyenbrück-
           Nord" unter Osternburg entsteht, weil ein Beschluss beide berührt.
        2. **Stadtweite Programme** streuen über die halbe Stadt („Startchancen-
           Programm" in 8 Ortsbereichen). Sie gehören in die stadtweite Liste,
           nicht unter einen Stadtteil — dort sind sie das Gegenteil von
           „ach, das betrifft mich".
        3. **Koordinaten schlagen Nennung.** Wo eine Entität geocodiert ist
           (gut die Hälfte), entscheidet ihr Punkt, nicht der Beschluss, in dem
           sie erwähnt wurde. Ohne Koordinaten bleibt es bei der Nennung — die
           Regel korrigiert nur nachweislich Falsches.

        Und die Reihenfolge: Straßennamen nach hinten. Adressen aus Bebauungs-
        plänen sind zwar Orte, aber nichts, dem man folgen möchte; sie bleiben
        drin (manche Straße IST ein Vorhaben), stehen aber hinter allem anderen.
        """
        from council import geo, places

        eigener = place.name.casefold()
        # ALLE Ortsbereichsnamen raus, auch der eigene. Ein anderer Ortsbereich
        # ist kein Vorschlag für diesen; und der eigene ist längst gewählt —
        # die Stadtteil-Liste gibt es ja nur, weil er in Schritt 2 angeklickt
        # wurde. „✓ Bümmerstede" als erster Vorschlag unter Bümmerstede sagte
        # nichts, und „Kreyenbrück · Kreyenbrück" unter Nebenan las sich wie
        # ein Fehler (Tims Bild, 02.09.2026).
        ortsbereiche = {p.name.casefold() for p in places.primary_places()}
        kandidaten = [k for k in kandidaten if (k.get("name") or "").casefold() not in ortsbereiche]
        if not kandidaten:
            return []

        # Breite NUR für die Kandidaten bestimmen — über alle Entitäten wäre es
        # ein Full-Scan im Web-Request.
        slugs = [k.get("slug") or "" for k in kandidaten]
        platz = ",".join("?" * len(slugs))
        breite = {r["slug"]: r["orte"] for r in self._conn.execute(
            # ABSICHTLICH die eine Hauptspalte und NICHT die Zugehörigkeits-
            # Tabelle: Hier wird gemessen, wie breit ein Thema streut, um
            # stadtweite Themen aus den Stadtteil-Listen zu halten. Zählte man
            # jede berührte Zugehörigkeit mit, machte eine einzige lange Straße
            # ihr Thema „stadtweit" — und die Alexanderstraße verschwände aus
            # allen fünf Vierteln, statt in allen fünf zu stehen.
            f"""SELECT e.slug, COUNT(DISTINCT COALESCE(l.local_area_id, l.district)) AS orte
                  FROM council_entities e
                  JOIN council_entity_links el ON el.entity_id = e.id
                  JOIN council_decisions d ON d.id = el.decision_id
                  JOIN council_sessions cs ON cs.ksinr = d.ksinr
                  JOIN council_decision_locations dl ON dl.decision_id = d.id
                  JOIN council_locations l ON l.slug = dl.location_slug
                 WHERE e.slug IN ({platz}) AND cs.session_date >= ?
                 GROUP BY e.slug""", (*slugs, cutoff)).fetchall()}

        # Ist die Entität selbst ein Ort, wissen wir genau, wo sie liegt — aus
        # dem ganzen Verlauf statt aus einem Punkt. Das ist die beste Auskunft,
        # die es gibt, und sie schlägt beide Heuristiken darunter.
        zugehoerig = self.location_districts(slugs)

        punkte = {r["slug"]: (r["lat"], r["lon"]) for r in self._conn.execute(
            f"SELECT slug, lat, lon FROM council_entity_meta "
            f"WHERE slug IN ({platz}) AND lat IS NOT NULL AND lon IS NOT NULL",
            slugs).fetchall()}

        from council.locations import affects_whole_city

        behalten = []
        for k in kandidaten:
            slug = k.get("slug") or ""
            name = k.get("name") or ""
            # Klingt der NAME nach einem stadtweiten Vorgang („TSH Konzept
            # Berlin", „Mobilitätsplan 2030"), gehört er nicht unter einen
            # Stadtteil — dieselbe Vokabel wie bei der Ortszuordnung. Die
            # Breiten-Regel unten fängt das nur, wenn der Bestand schon breit
            # genug ist; auf dev war er es nicht.
            if affects_whole_city(name):
                continue
            # Ein bloßer Straßenname mit zwei, drei Erwähnungen ist kein
            # Vorschlag, dem jemand folgen will. Straßen bleiben nur, wenn an
            # ihnen wirklich etwas passiert — dann sind sie ein Vorhaben mit
            # Adresse (Sandweg: 33 Beschlüsse). Und auch dann stehen sie hinten.
            if self._looks_like_street(name) and (k.get("n_recent") or 0) < self.STRASSE_MINDESTENS:
                continue
            bereiche = zugehoerig.get(slug)
            if bereiche is not None:
                # Wir wissen, wo dieses Ding liegt. Dann entscheidet das — und
                # sonst nichts. Die Breiten-Regel darf hier NICHT greifen: Eine
                # Straße durch fünf Ortsbereiche ist kein stadtweites Programm,
                # sondern eine lange Straße, und in jedem dieser fünf ein
                # richtiger Vorschlag. Und der Mittelpunkt der Entität erst
                # recht nicht: Für den Sandweg liegt er in Osternburg, einem
                # Bereich, den die Straße überhaupt nicht berührt — dieselbe
                # Bounding-Box-Falle wie bei den Orten selbst.
                if eigener not in bereiche:
                    continue
                behalten.append(k)
                continue
            if breite.get(slug, 1) >= self.CITYWIDE_FROM_DISTRICTS:
                continue
            punkt = punkte.get(slug)
            if punkt:
                liegt_in = geo.ortsbereich_for(punkt[0], punkt[1])
                if liegt_in and liegt_in.casefold() != eigener:
                    continue
            behalten.append(k)

        behalten.sort(key=lambda k: (
            self._looks_like_street(k.get("name") or ""),
            -(k.get("avg_interest") or 50),
            -(k.get("n_recent") or 0),
            k.get("name") or "",
        ))
        return behalten

    def entity_title_with_parenthetical(self, slug: str) -> str | None:
        """Der jüngste Beschlusstitel dieser Entität, der eine Klammer trägt.

        Für eine Plannummer ist die Klammer die einzige lesbare Einordnung
        („Bebauungsplan 865 (Quartier am Krusenbusch)"), und sie steht nicht in
        jedem Titel: Der jüngste heißt oft nur „… - Satzungsbeschluss". Dann
        zeigte der Chip die nackte Nummer (Tims Bild, 02.09.2026). Ein
        Beschluss weiter zurück trägt sie fast immer."""
        row = self._conn.execute(
            """SELECT d.title FROM council_entities e
                 JOIN council_entity_links el ON el.entity_id = e.id
                 JOIN council_decisions d ON d.id = el.decision_id
                 JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE e.slug = ? AND d.title LIKE '%(%'
                ORDER BY cs.session_date DESC, d.id DESC LIMIT 1""", (slug,)).fetchone()
        return row["title"] if row else None

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
