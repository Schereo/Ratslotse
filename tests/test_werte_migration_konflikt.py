"""Eine Werte-Migration darf nicht abbrechen, wenn der neue Wert schon da ist.

Der Fall vom 02.09.2026 (dev): `scripts/ingest_finanzen_opendata.py` schrieb
mit neuem Code `council_taxes.kind = 'total'`, die alten Zeilen mit
`'insgesamt'` blieben liegen. Die Migration `insgesamt → total` lief danach
bei JEDEM Store-Start auf den Primärschlüssel (year, kind) und brach mit
IntegrityError ab — Crons und Ingests starben, der Ops-Lauf blieb rot.
"""
import sqlite3

from council.store import CouncilStore


def _bestand(db):
    store = CouncilStore(db)
    with store._conn:  # noqa: SLF001
        store._conn.executemany(  # noqa: SLF001
            "INSERT OR REPLACE INTO council_taxes (year, kind, amount, fetched_at) "
            "VALUES (?,?,?,?)",
            [
                # Konflikt: beide Schreibweisen für dasselbe Jahr — die neue
                # trägt den jüngeren Ingest und einen anderen Betrag.
                (2024, "insgesamt", 1.0, "2026-08-01"),
                (2024, "total", 2.0, "2026-09-02"),
                # Kein Konflikt: nur die alte Schreibweise.
                (2023, "insgesamt", 3.0, "2026-08-01"),
                # Unbeteiligt.
                (2024, "Gewerbesteuer (-umlage)", 4.0, "2026-09-02"),
            ])
    store.close()


def _zeilen(db):
    con = sqlite3.connect(db)
    try:
        return sorted(con.execute("SELECT year, kind, amount FROM council_taxes"))
    finally:
        con.close()


def test_die_alte_zeile_weicht_der_neuen(tmp_path):
    db = tmp_path / "council.sqlite"
    _bestand(db)
    # Das zweite Öffnen läuft die Migration erneut — genau der Start, der
    # auf dev abbrach.
    CouncilStore(db).close()
    assert _zeilen(db) == [
        (2023, "total", 3.0),
        (2024, "Gewerbesteuer (-umlage)", 4.0),
        (2024, "total", 2.0),
    ]


def test_ohne_schluesselwissen_bleibt_der_fehler(tmp_path):
    """Wo der Wert NICHT im Primärschlüssel steht, gibt es keinen
    verlässlichen Zwilling — dann darf die Migration nicht raten."""
    db = tmp_path / "council.sqlite"
    store = CouncilStore(db)
    with store._conn:  # noqa: SLF001
        store._conn.execute(  # noqa: SLF001
            "CREATE TABLE probe (id INTEGER PRIMARY KEY, kind TEXT, UNIQUE(kind))")
        store._conn.executemany(  # noqa: SLF001
            "INSERT INTO probe (kind) VALUES (?)", [("alt",), ("neu",)])
    try:
        try:
            store._werte_umschreiben("probe", "kind", [("alt", "neu")])  # noqa: SLF001
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("Konflikt ohne Schlüsselwissen muss ein Fehler bleiben")
    finally:
        store.close()
