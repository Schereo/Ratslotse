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
