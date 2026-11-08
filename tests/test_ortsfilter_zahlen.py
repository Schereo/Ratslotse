"""Die Zahlen am Ortsfilter: eine Abfrage für alle Orte statt einer je Ort.

``OrteMixin.decision_location_place_stats`` lief bis 11/2026 je filterbarem
Ort eine eigene ``COUNT(DISTINCT …)``-Abfrage — 118 Stück, zusammen 95 ms,
und ``/api/council/districts`` war damit die letzte Anfrage der Ratsseite.
Jetzt liest sie die Ortslinks einmal und sortiert in Python.

Die Gefahr dabei ist nicht die Geschwindigkeit, sondern dass Filter und Zahl
am Filter auseinanderlaufen: Der Filter selbst fragt weiter mit
``_place_location_condition``. Dieser Test hält deshalb die alte Fassung
(dieselbe Bedingung, je Ort eine Abfrage) als Referenz daneben — auf einem
Bestand, der jeden Zweig der Bedingung einzeln trifft, und auf den Fallen
einer Umstellung: Spalten nicht verwechseln (``local_area_id`` gegen die
Kennung, ``district`` gegen den Namen), Zugehörigkeit über die Tabelle,
Aliase, ``kind != 'decision'``, Ergebnis ``NULL``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council.store import CouncilStore  # noqa: E402


def _referenz(store: CouncilStore) -> list[dict]:
    """Die Fassung vor 11/2026, wörtlich: je Ort eine Abfrage."""
    vote_ph = ",".join("?" * len(store._VOTE_OUTCOMES))
    report_ph = ",".join("?" * len(store._REPORT_OUTCOMES))
    out = []
    for place in store.all_places():
        if not place.filterable:
            continue
        condition, params = store._place_location_condition(place)
        row = store._conn.execute(
            f"""SELECT COUNT(DISTINCT dl.decision_id) AS count,
                       COUNT(DISTINCT CASE WHEN d.outcome IN ({vote_ph})
                                           THEN dl.decision_id END) AS vote_count,
                       COUNT(DISTINCT CASE WHEN d.outcome IN ({report_ph}) OR d.outcome IS NULL
                                           THEN dl.decision_id END) AS report_count
                FROM council_decision_locations dl
                JOIN council_locations l ON l.slug = dl.location_slug
                JOIN council_decisions d ON d.id = dl.decision_id
                WHERE {condition} AND d.kind = 'decision'""",
            [*store._VOTE_OUTCOMES, *store._REPORT_OUTCOMES, *params],
        ).fetchone()
        if row and row["count"]:
            out.append({"place_id": place.id, "name": place.name,
                        "count": row["count"], "vote_count": row["vote_count"],
                        "report_count": row["report_count"]})
    return out


@pytest.fixture()
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    c = s._conn
    with c:
        c.execute("INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
                  "location, fetched_at) VALUES (1, 'Rat', '2026-05-04', '18:00', 'Rathaus', '2026-05-01')")
        # Je Ergebnisart einer, dazu NULL, ein unbekanntes und eine Nicht-Entscheidung.
        c.executemany(
            "INSERT INTO council_decisions (id, ksinr, position, title, outcome, kind) "
            "VALUES (?, 1, ?, ?, ?, ?)",
            [(1, 1, "a", "accepted", "decision"), (2, 2, "b", "rejected", "decision"),
             (3, 3, "c", "noted", "decision"), (4, 4, "d", None, "decision"),
             (5, 5, "e", "something_else", "decision"), (6, 6, "f", "accepted", "agenda"),
             (7, 7, "g", "settled", "decision"), (8, 8, "h", "postponed", "decision")])
        c.executemany(
            "INSERT INTO council_locations (slug, name, kind, district, local_area_id, place_id, "
            "updated_at) VALUES (?, ?, 'street', ?, ?, ?, '2026-01-01')",
            [
                # Hauptbereich über die Spalte local_area_id …
                ("strasse-a", "Straße A", None, "eversten", None),
                # … über die Spalte district (Name) …
                ("strasse-b", "Straße B", "Bornhorst", None, None),
                # … und nur über die Zugehörigkeits-Tabelle.
                ("strasse-c", "Straße C", None, None, None),
                ("strasse-d", "Straße D", None, None, None),
                # Fallen: Name in local_area_id, Kennung in district — beides
                # trifft in der Bedingung NICHT.
                ("falle-1", "Falle 1", "eversten", "Eversten", None),
                # Nicht-Hauptbereich über place_id …
                ("eversten-west-x", "Irgendwo", None, None, "eversten-west"),
                # … und über den Slug eines Aliases.
                ("everstenholz", "Everstenholz", None, None, None),
            ])
        c.executemany(
            "INSERT INTO council_location_districts (location_slug, district, place_id, share) "
            "VALUES (?, ?, ?, ?)",
            [("strasse-c", "Bloherfelde", "bloherfelde", 1.0),
             # place_id leer, nur der Name: trifft über ``district = name``.
             ("strasse-d", "Bornhorst", None, 0.5),
             # eine Straße durch zwei Bereiche
             ("strasse-a", "Bloherfelde", "bloherfelde", 0.3)])
        c.executemany(
            "INSERT INTO council_decision_locations (decision_id, location_slug, source, evidence, "
            "method, confidence, updated_at) VALUES (?, ?, 'title', 'x', 'regex', 0.9, '2026-01-01')",
            [(1, "strasse-a"), (2, "strasse-a"), (6, "strasse-a"),
             (3, "strasse-b"), (4, "strasse-b"), (1, "strasse-b"),
             (5, "strasse-c"), (7, "strasse-c"),
             (8, "strasse-d"), (4, "strasse-d"),
             (7, "falle-1"),
             (3, "eversten-west-x"), (8, "everstenholz"), (1, "everstenholz")])
    try:
        yield s
    finally:
        s.close()


def test_ein_durchlauf_zaehlt_wie_die_bedingung_des_filters(store):
    neu = store.decision_location_place_stats()
    assert neu == _referenz(store)
    # Der Bestand trifft wirklich jeden Zweig — sonst bewiese die Gleichheit
    # oben wenig.
    nach_ort = {r["place_id"]: r for r in neu}
    assert {"eversten", "bornhorst", "bloherfelde", "eversten-west", "eversten-holz"} <= set(nach_ort)
    # Die Falle zählt nicht mit: Eversten hat nur Straße A (1, 2; 6 ist keine
    # Entscheidung), nicht Beschluss 7 über „falle-1" — dort steht der Name in
    # local_area_id und die Kennung in district, und das trifft die Bedingung
    # nicht. Wer die Spalten in einen Topf wirft, zählt hier 3.
    assert nach_ort["eversten"] == {"place_id": "eversten", "name": "Eversten",
                                    "count": 2, "vote_count": 2, "report_count": 0}
    # Ergebnis NULL zählt als Bericht, ein unbekanntes Ergebnis zu keinem.
    assert nach_ort["bornhorst"]["report_count"] == 2
    assert nach_ort["bloherfelde"] == {"place_id": "bloherfelde", "name": "Bloherfelde",
                                       "count": 4, "vote_count": 2, "report_count": 1}


def test_zwei_abfragen_statt_einer_je_ort(store):
    store.all_places()  # Katalog vorab, er zählt nicht zur Zählung
    abfragen: list[str] = []
    store._conn.set_trace_callback(abfragen.append)
    store.decision_location_place_stats()
    store._conn.set_trace_callback(None)
    assert len(abfragen) == 2, abfragen
