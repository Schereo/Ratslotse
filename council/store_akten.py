"""Grundakten: Rohdaten für den Aufbau, Schreiben und Abfragen.

Die Logik — was zu welcher Akte gehört — steht in ``council/matters.py``;
hier nur die Abfragen (``council/CLAUDE.md``: neue Abfragen gehören in ein
Store-Modul). Plan: ``docs/plan-akte.md``.
"""
from __future__ import annotations

from council.store_basis import StoreBasis


class AktenMixin(StoreBasis):
    """Die Grundakten-Abfragen — nur zum Mitvererben."""

    # --- Rohdaten für den Aufbau ------------------------------------------

    def matter_templates(self) -> list[tuple]:
        """(kvonr, template_number, title, raw_text) je Vorlage."""
        return [tuple(r) for r in self._conn.execute(
            "SELECT kvonr, template_number, title, raw_text FROM council_templates")]

    def matter_decisions(self) -> list[tuple]:
        """(id, ksinr, item_number, title, template_number, kind, parent_item,
        session_date) je Beschluss, älteste zuerst."""
        return [tuple(r) for r in self._conn.execute(
            "SELECT d.id, d.ksinr, d.item_number, d.title, d.template_number, d.kind, "
            "d.parent_item, s.session_date FROM council_decisions d "
            "JOIN council_sessions s ON s.ksinr = d.ksinr ORDER BY s.session_date, d.id")]

    def matter_deliberations(self) -> list[tuple]:
        """(id, kvonr, date) je Station der Beratungsfolge."""
        return [tuple(r) for r in self._conn.execute(
            "SELECT id, kvonr, date FROM council_deliberations")]

    def matter_agenda_items(self) -> list[tuple]:
        """(id, ksinr, item_number, title, template_number, kvonr, session_date)."""
        return [tuple(r) for r in self._conn.execute(
            "SELECT a.id, a.ksinr, a.item_number, a.title, a.template_number, a.kvonr, "
            "s.session_date FROM council_agenda_items a "
            "JOIN council_sessions s ON s.ksinr = a.ksinr")]

    # --- Schreiben ---------------------------------------------------------

    def replace_matters(self, meta: list[tuple], items: list[tuple],
                        edges: list[tuple], built_at: str) -> dict[str, int]:
        """Grundakten vollständig ersetzen, in EINER Transaktion.

        ``meta``: (key, kind, title, first_date, last_date);
        ``items``: (item_type, item_id, key, source);
        ``edges``: (key_a, key_b, source). Bestehende Schlüssel behalten ihre
        id; Akten ohne Inhalt werden geräumt. Gibt key → id zurück.
        """
        with self._conn:
            self._conn.executemany(
                "INSERT OR IGNORE INTO council_matters (key, kind, built_at) VALUES (?, ?, ?)",
                [(m[0], m[1], built_at) for m in meta])
            self._conn.executemany(
                "UPDATE council_matters SET kind = ?, title = ?, first_date = ?, last_date = ?, "
                "built_at = ? WHERE key = ?",
                [(kind, titel, von, bis, built_at, k) for k, kind, titel, von, bis in meta])
            ids: dict[str, int] = {
                k: i for k, i in self._conn.execute("SELECT key, id FROM council_matters")}
            self._conn.execute("DELETE FROM council_matter_items")
            self._conn.executemany(
                "INSERT INTO council_matter_items (item_type, item_id, matter_id, source) "
                "VALUES (?, ?, ?, ?)",
                [(art, iid, ids[k], quelle) for art, iid, k, quelle in items])
            self._conn.execute("DELETE FROM council_matter_edges")
            self._conn.executemany(
                "INSERT OR IGNORE INTO council_matter_edges (matter_a, matter_b, source) "
                "VALUES (?, ?, ?)",
                [(ids[a], ids[b], q) for a, b, q in edges if a in ids and b in ids])
            self._conn.execute(
                "DELETE FROM council_matters WHERE id NOT IN "
                "(SELECT DISTINCT matter_id FROM council_matter_items)")
        return ids

    # --- Phase 2: Entitäten über Grundakten ---------------------------------

    def entity_name_variants(self) -> list[tuple]:
        """(slug, name, kind, n) — jede Schreibweise jeder Entität, Aliasse auf
        ihren Kanon gefaltet (dieselbe Regel wie ``rebuild_entities_from_obs``)."""
        alias = {r[0]: r[1] for r in self._conn.execute(
            "SELECT slug, canonical_slug FROM council_entity_aliases")}
        ents = {r["slug"]: (r["kind"], r["n"]) for r in self._conn.execute(
            "SELECT slug, kind, n FROM council_entities")}
        out = {(s, r[1]) for s, r in ((alias.get(r[0], r[0]), r) for r in self._conn.execute(
            "SELECT DISTINCT slug, name FROM council_entity_obs")) if s in ents and r[1]}
        out |= {(r["slug"], r["name"]) for r in self._conn.execute(
            "SELECT slug, name FROM council_entities") if r["name"]}
        return sorted((s, name, ents[s][0], ents[s][1]) for s, name in out)

    def speech_texts(self) -> list[tuple]:
        """(id, Text samt Antwort) je Wortbeitrag."""
        return [tuple(r) for r in self._conn.execute(
            "SELECT id, coalesce(text, '') || ' ' || coalesce(answer, '') FROM council_speeches")]

    def press_leads(self, zeichen: int) -> list[tuple]:
        """(id, Titel, Anfang) je Pressemitteilung — ohne den Fuß mit Ort und Zeit."""
        return [tuple(r) for r in self._conn.execute(
            "SELECT id, coalesce(title, ''), substr(coalesce(text, ''), 1, ?) "
            "FROM council_press", (zeichen,))]

    def entity_matter_pairs(self) -> list[tuple]:
        """(slug, Name, matter_id, Akten-Titel): jede Entität an jeder Grundakte,
        in der einer ihrer Beschlüsse liegt."""
        return [tuple(r) for r in self._conn.execute(
            "SELECT DISTINCT e.slug, e.name, i.matter_id, m.title FROM council_entity_links l "
            "JOIN council_entities e ON e.id = l.entity_id "
            "JOIN council_matter_items i ON i.item_type = 'decision' AND i.item_id = l.decision_id "
            "JOIN council_matters m ON m.id = i.matter_id")]

    def replace_entity_akten(self, matters: list[tuple], mentions: list[tuple]) -> None:
        """Beide Phase-2-Tabellen vollständig ersetzen, in EINER Transaktion."""
        with self._conn:
            self._conn.execute("DELETE FROM council_entity_matters")
            self._conn.executemany(
                "INSERT OR IGNORE INTO council_entity_matters (slug, matter_id) VALUES (?, ?)",
                matters)
            self._conn.execute("DELETE FROM council_entity_mentions")
            self._conn.executemany(
                "INSERT OR IGNORE INTO council_entity_mentions (slug, item_type, item_id) "
                "VALUES (?, ?, ?)", mentions)

    # --- Akte zusammenstellen ---------------------------------------------

    def matters_of_decisions(self, decision_ids: list[int]) -> set[int]:
        if not decision_ids:
            return set()
        return {r[0] for r in self._conn.execute(
            f"SELECT matter_id FROM council_matter_items WHERE item_type = 'decision' "
            f"AND item_id IN ({','.join('?' * len(decision_ids))})", decision_ids)}

    def entities_of_matters(self, matter_ids: list[int]) -> list[dict]:
        """slug, name, kind, n der Entitäten an diesen Grundakten."""
        if not matter_ids:
            return []
        return [dict(r) for r in self._conn.execute(
            f"SELECT DISTINCT e.slug, e.name, e.kind, e.n FROM council_entity_matters m "
            f"JOIN council_entities e ON e.slug = m.slug "
            f"WHERE m.matter_id IN ({','.join('?' * len(matter_ids))})", matter_ids)]

    def matters_of_entities(self, slugs: list[str]) -> set[int]:
        if not slugs:
            return set()
        return {r[0] for r in self._conn.execute(
            f"SELECT matter_id FROM council_entity_matters WHERE slug IN "
            f"({','.join('?' * len(slugs))})", slugs)}

    def mentions_of_entities(self, slugs: list[str]) -> list[tuple]:
        """(item_type, item_id) der Erwähnungen dieser Entitäten."""
        if not slugs:
            return []
        return [tuple(r) for r in self._conn.execute(
            f"SELECT DISTINCT item_type, item_id FROM council_entity_mentions WHERE slug IN "
            f"({','.join('?' * len(slugs))})", slugs)]

    def deliberations_by_ids(self, ids: list[int]) -> list[dict]:
        """Stationen der Beratungsfolge samt Vorlage: id, date, committee,
        result (die BeratungsART — Vorberatung/Entscheidung/Kenntnisnahme, kein
        Ergebnis), template_number, title."""
        if not ids:
            return []
        return [dict(r) for r in self._conn.execute(
            f"SELECT d.id, d.date, d.committee, d.result, t.template_number, t.title "
            f"FROM council_deliberations d LEFT JOIN council_templates t ON t.kvonr = d.kvonr "
            f"WHERE d.id IN ({','.join('?' * len(ids))})", ids)]

    def hauptbeschluesse(self, decision_ids: list[int]) -> list[int]:
        """Die ids darunter, die keine Teilabstimmung sind (``kind = 'decision'``)."""
        if not decision_ids:
            return []
        return [r[0] for r in self._conn.execute(
            f"SELECT id FROM council_decisions WHERE kind = 'decision' AND id IN "
            f"({','.join('?' * len(decision_ids))})", decision_ids)]

    def items_of_matters(self, matter_ids: list[int]) -> list[tuple]:
        """(item_type, item_id) aller Zeilen dieser Grundakten."""
        if not matter_ids:
            return []
        return [tuple(r) for r in self._conn.execute(
            f"SELECT item_type, item_id FROM council_matter_items WHERE matter_id IN "
            f"({','.join('?' * len(matter_ids))})", matter_ids)]

    # --- Abfragen ----------------------------------------------------------

    def matter_of(self, item_type: str, item_id: int) -> dict | None:
        """Die Grundakte einer Zeile (``decision``, ``speech``, …) — oder None."""
        r = self._conn.execute(
            "SELECT m.id, m.key, m.kind, m.title, m.first_date, m.last_date "
            "FROM council_matter_items i JOIN council_matters m ON m.id = i.matter_id "
            "WHERE i.item_type = ? AND i.item_id = ?", (item_type, item_id)).fetchone()
        return dict(r) if r else None

    def matter_items(self, matter_id: int) -> list[dict]:
        """Alle Zeilen einer Grundakte: item_type, item_id, source."""
        return [dict(r) for r in self._conn.execute(
            "SELECT item_type, item_id, source FROM council_matter_items WHERE matter_id = ? "
            "ORDER BY item_type, item_id", (matter_id,))]

    def matter_neighbours(self, matter_id: int) -> list[dict]:
        """Grundakten, auf die diese verweist oder die auf sie verweisen."""
        return [dict(r) for r in self._conn.execute(
            "SELECT m.id, m.key, m.title, e.source FROM council_matter_edges e "
            "JOIN council_matters m ON m.id = CASE WHEN e.matter_a = ? THEN e.matter_b "
            "ELSE e.matter_a END WHERE e.matter_a = ? OR e.matter_b = ?",
            (matter_id, matter_id, matter_id))]
