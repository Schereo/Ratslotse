"""Stehende Datenprüfungen: die Abfragen.

Die Regeln — was nie vorkommen darf und ab wann gemeldet wird — stehen in
``council/datenpruefung.py``; hier nur das Lesen (``council/CLAUDE.md``: neue
Abfragen gehören in ein Store-Modul). Plan: ``docs/plan-akte.md``, Phase 6.
"""
from __future__ import annotations

import sqlite3

from council.store_basis import StoreBasis
from kern.dbfehler import tabelle_fehlt


class PruefungMixin(StoreBasis):
    """Die Abfragen der Datenprüfung — nur zum Mitvererben."""

    def pruef_hauptbeschluesse(self, seit_datum: str | None = None) -> list[dict]:
        """id, outcome, raw_result, summary, simple_summary, session_date je
        Hauptpunkt (``kind = 'decision'``), ab ``seit_datum`` (Sitzungstag)."""
        sql = ("SELECT d.id, d.outcome, d.raw_result, d.summary, d.simple_summary, "
               "s.session_date FROM council_decisions d "
               "JOIN council_sessions s ON s.ksinr = d.ksinr WHERE d.kind = 'decision'")
        params: tuple = ()
        if seit_datum:
            sql += " AND s.session_date >= ?"
            params = (seit_datum,)
        return [dict(r) for r in self._conn.execute(sql, params)]

    def pruef_beitraege_seit(self, seit: str) -> list[dict]:
        """id, ksinr, kind, speaker, party, answer der Wortbeiträge, die seit
        ``seit`` (UTC, ISO) extrahiert wurden."""
        return [dict(r) for r in self._conn.execute(
            "SELECT id, ksinr, kind, speaker, party, answer FROM council_speeches "
            "WHERE extracted_at >= ?", (seit,))]

    def pruef_sitzungen_ohne_beschluss(self, von: str, bis: str) -> list[dict]:
        """ksinr, committee, session_date der Sitzungen von ``von`` bis ``bis``
        (Sitzungstag), die eine Tagesordnung, aber keinen einzigen Beschluss
        haben — das Protokoll fehlt."""
        return [dict(r) for r in self._conn.execute(
            "SELECT s.ksinr, s.committee, s.session_date FROM council_sessions s "
            "WHERE s.session_date BETWEEN ? AND ? "
            "AND EXISTS (SELECT 1 FROM council_agenda_items a WHERE a.ksinr = s.ksinr) "
            "AND NOT EXISTS (SELECT 1 FROM council_decisions d WHERE d.ksinr = s.ksinr) "
            "ORDER BY s.session_date", (von, bis))]

    # --- Akten (B9) ----------------------------------------------------------

    def pruef_akten_stand(self) -> str | None:
        """Wann die Grundakten zuletzt gebaut wurden — None, wenn es keine gibt."""
        try:
            r = self._conn.execute("SELECT max(built_at) FROM council_matters").fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):           # vor Phase 1 gibt es sie nicht
                raise
            return None
        return r[0] if r else None

    def pruef_akten_waisen(self, seit_datum: str) -> list[int]:
        """Hauptpunkte ab ``seit_datum`` (Sitzungstag) ohne Grundakte."""
        return [r[0] for r in self._conn.execute(
            "SELECT d.id FROM council_decisions d JOIN council_sessions s ON s.ksinr = d.ksinr "
            "WHERE d.kind = 'decision' AND s.session_date >= ? AND NOT EXISTS ("
            "SELECT 1 FROM council_matter_items i WHERE i.item_type = 'decision' "
            "AND i.item_id = d.id)", (seit_datum,))]

    def pruef_beitraege_ohne_akte(self, seit_datum: str) -> tuple[int, int]:
        """(alle, ohne Grundakte) der Wortbeiträge ab ``seit_datum`` (Sitzungstag)."""
        r = self._conn.execute(
            "SELECT count(*), coalesce(sum(NOT EXISTS (SELECT 1 FROM council_matter_items i "
            "WHERE i.item_type = 'speech' AND i.item_id = w.id)), 0) FROM council_speeches w "
            "JOIN council_sessions s ON s.ksinr = w.ksinr WHERE s.session_date >= ?",
            (seit_datum,)).fetchone()
        return int(r[0]), int(r[1])
