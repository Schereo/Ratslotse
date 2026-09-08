"""Die Ereignis-Zähler (Plan „Sehen und Zurückholen", Teil A / PR 3).

Der Fehler, gegen den der Wächter hier gebaut ist, ist schon einmal passiert:
Bis zum 01.09.2026 versprach das Admin-Panel Zähler für Suche, Analyse und
Karte, aber die ``record_activity``-Aufrufe dazu gab es nie. Für jedes Konto
stand dort „nie" — und nichts schlug an, weil eine 0 aussieht wie eine Messung.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from kern.store import Store

WURZEL = Path(__file__).resolve().parents[1]
BACKEND = WURZEL / "web" / "backend" / "app"


def _geschrieben() -> set[str]:
    """Jeder Wert, den das Backend tatsächlich in ``user_activity`` schreibt."""
    werte = set()
    for datei in BACKEND.rglob("*.py"):
        for treffer in re.finditer(r'record_activity\(\s*[^,]+,\s*"([a-z_]+)"', datei.read_text(encoding="utf-8")):
            werte.add(treffer.group(1))
    return werte


def test_jeder_gezaehlte_wert_wird_auch_geschrieben():
    """Ein Zähler ohne Schreibstelle steht dauerhaft auf 0 und sieht aus wie
    eine Messung. Genau das war der Zustand von Design 20a bis zum 01.09.2026."""
    versprochen = {key for key, _ in Store.EREIGNISSE}
    ohne_quelle = sorted(versprochen - _geschrieben())
    assert not ohne_quelle, (
        "Diese Werte stehen in Store.EREIGNISSE, aber niemand schreibt sie — "
        f"sie stünden dauerhaft auf 0: {ohne_quelle}"
    )


def test_jeder_geschriebene_wert_wird_auch_gezeigt():
    """Und die Gegenrichtung: ein Zähler, der niemandem auffällt, ist keiner."""
    gezeigt = {key for key, _ in Store.EREIGNISSE}
    unsichtbar = sorted(_geschrieben() - gezeigt)
    assert not unsichtbar, (
        "Diese Werte schreibt das Backend, aber Store.EREIGNISSE kennt sie "
        f"nicht — sie tauchen nirgends auf: {unsichtbar}"
    )


def _zaehle(store: Store, uid: int, feature: str, n: int = 1, tag: date | None = None) -> None:
    with store._conn:
        store._conn.execute(
            "INSERT INTO user_activity (owner_id, day, feature, client, count)"
            " VALUES (?, ?, ?, 'web', ?)"
            " ON CONFLICT(owner_id, day, feature, client) DO UPDATE SET count = count + ?",
            (uid, (tag or date.today()).isoformat(), feature, n, n))


def test_anteile_beziehen_sich_auf_die_fragen(tmp_path):
    store = Store(tmp_path / "r.sqlite")
    _zaehle(store, 1, "ai_question", 10)
    _zaehle(store, 1, "ai_question_chip", 4)
    _zaehle(store, 1, "ai_answer_empty", 1)

    d = store.ereignisse()

    assert d["chip_share"] == 0.4
    assert d["empty_share"] == 0.1
    store.close()


def test_ohne_fragen_gibt_es_keinen_anteil(tmp_path):
    """Ein Anteil aus null Fragen ist keine 0 %, sondern keine Aussage."""
    store = Store(tmp_path / "r.sqlite")
    d = store.ereignisse()
    assert d["chip_share"] is None and d["empty_share"] is None
    store.close()


def test_konten_werden_getrennt_gezaehlt(tmp_path):
    """Hundert Fragen aus einem Konto sind etwas anderes als aus zwanzig."""
    store = Store(tmp_path / "r.sqlite")
    _zaehle(store, 1, "ai_question", 90)
    _zaehle(store, 2, "ai_question", 10)

    fragen = next(e for e in store.ereignisse()["events"] if e["key"] == "ai_question")

    assert fragen["n"] == 100 and fragen["users"] == 2
    store.close()


def test_alte_tage_fallen_aus_dem_fenster(tmp_path):
    store = Store(tmp_path / "r.sqlite")
    _zaehle(store, 1, "ai_question", 5, date.today() - timedelta(days=40))
    _zaehle(store, 1, "ai_question", 2)
    assert next(e for e in store.ereignisse(30)["events"]
                if e["key"] == "ai_question")["n"] == 2
    store.close()
