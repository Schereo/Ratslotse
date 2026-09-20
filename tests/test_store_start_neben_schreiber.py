"""Ein Store muss sich öffnen lassen, während ein anderer Prozess schreibt.

``Depends(get_store)`` baut je HTTP-Anfrage einen frischen Store, und der
läuft in ``__init__`` jede Migration noch einmal. Bis 09/2026 gehörten dazu
Dutzende ``UPDATE … WHERE spalte = 'alter Wert'`` — idempotent, beim
zweiten Lauf ohne Treffer, aber jedes einzelne holt sich die Schreibsperre
der Datei. Gemessen auf Prod am 20.09.2026: 41 Schreibanweisungen je
Anfrage an ``ratslotse.sqlite`` (73 ms, davon 23 Durchläufe der indexlosen
``llm_usage``), 385 je Anfrage an ``council.sqlite``. Eine reine Leseanfrage
wurde so zum Schreiber, und ein Schwung gleichzeitiger Anfragen — Startseite
plus Admin-Panel — stand sich gegenseitig im Weg, bis nach fünf Sekunden
``database is locked`` kam. Zwölfmal in sieben Tagen, immer bei der
ersten Anweisung des Store-Starts.

Der Wächter hält die Sperre wie ein laufender Cron und öffnet dann den Store:
Wer dabei schreiben will, wartet die ``busy_timeout`` ab und scheitert.
"""
from __future__ import annotations

import sqlite3
import time

import pytest

from council.store import CouncilStore
from kern.store import Store


@pytest.mark.parametrize("klasse, datei", [(Store, "ratslotse.sqlite"),
                                           (CouncilStore, "council.sqlite")])
def test_store_oeffnet_sich_neben_einem_schreiber(tmp_path, klasse, datei):
    db = tmp_path / datei
    klasse(db).close()  # erster Start: Schema, Migrationen, Marken

    schreiber = sqlite3.connect(db)
    schreiber.execute("BEGIN IMMEDIATE")  # hält die Schreibsperre der Datei
    try:
        start = time.perf_counter()
        try:
            klasse(db).close()
        except sqlite3.OperationalError as e:
            pytest.fail(
                f"{klasse.__name__} will beim Start schreiben, obwohl schon migriert "
                f"ist ({e}). Ein Migrationsschritt, der bei jedem Öffnen läuft, "
                "muss erst LESEN, ob es etwas zu tun gibt (s. "
                "`_werte_umschreiben`, `_marke_gesetzt`) — sonst ist jede "
                "Anfrage ein Schreiber.")
        dauer = time.perf_counter() - start
    finally:
        schreiber.rollback()
        schreiber.close()
    # Ohne Schreibversuch wartet niemand auf die Sperre; die 5 s busy_timeout
    # wären das Zeichen, dass doch einer versucht wurde und nur zufällig durchkam.
    assert dauer < 2, f"{klasse.__name__} brauchte {dauer:.1f} s neben einem Schreiber"
