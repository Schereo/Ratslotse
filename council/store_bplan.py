"""Bebauungsplan-Umringe (``council_bplan_outlines``) — Lese- und Schreibseite.

Gefüllt vom Wochenlauf (``scripts/fetch_bplan_outlines.py``) aus den offenen
Geodaten der Stadt (``council/bplan.py``), gelesen von „Mein Viertel", das
die Fläche eines Plans an das Vorhaben hängt, dessen Beschlusstitel die
Plannummer nennt. Je Lauf wird der Bestand ersetzt — die Stadt pflegt den
Datensatz, wir spiegeln ihn nur.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from council.store_basis import StoreBasis
from kern.dbfehler import tabelle_fehlt

_SPALTEN = ("key", "nr", "name", "status", "art", "verfahren", "note", "resolution_date", "adoption_date",
            "effective_date", "drawing_code", "stol_id", "geojson", "lat", "lon")


class BplanMixin(StoreBasis):

    def replace_bplan_outlines(self, rows: list[dict]) -> int:
        """Den Bestand durch den frischen Abzug ersetzen — in EINER Transaktion,
        damit zwischen Löschen und Einfügen keine leere Tabelle sichtbar ist."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute("DELETE FROM council_bplan_outlines")
            self._conn.executemany(
                f"INSERT OR REPLACE INTO council_bplan_outlines ({', '.join(_SPALTEN)}, updated_at) "
                f"VALUES ({', '.join('?' * len(_SPALTEN))}, ?)",
                [tuple(r.get(s) for s in _SPALTEN) + (now,) for r in rows])
        return len(rows)

    def bplan_outlines_by_keys(self, keys: list[str]) -> dict[str, dict]:
        """Umringe zu Vergleichsschlüsseln (``bplan.schluessel``) — nur solche
        mit Geometrie, denn ohne Fläche gibt es nichts zu zeigen."""
        keys = [k for k in dict.fromkeys(keys) if k]
        if not keys:
            return {}
        ph = ",".join("?" * len(keys))
        try:
            rows = self._conn.execute(
                f"SELECT * FROM council_bplan_outlines WHERE key IN ({ph}) AND geojson IS NOT NULL",
                keys).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return {}
        return {r["key"]: dict(r) for r in rows}

    def bplan_outline_stats(self) -> dict:
        try:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n, SUM(geojson IS NOT NULL) AS mit_flaeche, MAX(updated_at) AS stand "
                "FROM council_bplan_outlines").fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return {"n": 0, "mit_flaeche": 0, "stand": None}
        return {"n": row["n"], "mit_flaeche": row["mit_flaeche"] or 0, "stand": row["stand"]}
