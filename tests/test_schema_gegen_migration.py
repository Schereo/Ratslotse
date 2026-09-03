"""Das frische Schema und eine migrierte Datenbank müssen dieselbe Form haben.

Hintergrund: Beim Umbau auf englische Spaltennamen bekommt jede Umbenennung ein
Paar in ``_GELD_SPALTEN`` & Co. Steht die Spalte im ``CREATE TABLE`` daneben
weiter unter ihrem ALTEN Namen, driften zwei Formen auseinander:

* **frisch** (Tests, CI, neue Umgebung) — ``CREATE TABLE`` legt den alten
  Namen an, es gibt nichts umzubenennen, und der Code, der ihn nennt, läuft.
* **gewachsen** (dev, Prod) — die Migration hat die Spalte längst umbenannt,
  und derselbe Code stirbt im ``OperationalError``.

**Kein Test kann das sehen**, weil jeder Test auf einer frischen Datenbank
läuft — genau der Form, in der es funktioniert. Am 01.09.2026 stand so
``save_integrierte_schulden`` scharf: ``CREATE TABLE`` sagte ``sonstige``, die
Migration ``other``, der ``INSERT`` nannte ``sonstige``. Auf dev und Prod wäre
der nächste Lauf der integrierten Schulden gestorben; ein Schema-Vergleich
zwischen einer frisch angelegten und der dev-Datenbank zeigte es als einzige
Abweichung unter 120 Tabellen.

Der Wächter dreht das um: Er legt eine frische Datenbank an und hält jede
Spalte gegen die ALTE Seite aller Umbenennungspaare.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council.store import CouncilStore  # noqa: E402
from council.store_schema import (  # noqa: E402
    _FACH_SPALTEN,
    _GELD_SPALTEN,
    _REST_SPALTEN,
    _STRUKTUR_SPALTEN,
)

#: Alle vier Listen zusammen — sie werden in `_migrate` nacheinander angewandt.
LISTEN = (_GELD_SPALTEN, _STRUKTUR_SPALTEN, _REST_SPALTEN, _FACH_SPALTEN)


def _paare() -> dict[str, dict[str, str]]:
    """``{tabelle: {alt: neu}}`` über alle Umbenennungslisten."""
    aus: dict[str, dict[str, str]] = {}
    for liste in LISTEN:
        for tabelle, paare in liste:
            for alt, neu in paare:
                if alt != neu:
                    aus.setdefault(tabelle, {})[alt] = neu
    return aus


def _frisches_schema(pfad: Path) -> dict[str, set[str]]:
    store = CouncilStore(pfad)
    try:
        conn: sqlite3.Connection = store._conn
        tabellen = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {t: {r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')} for t in tabellen}
    finally:
        store.close()


def test_es_gibt_ueberhaupt_paare_zu_pruefen():
    """Ohne Paare wäre der Wächter darunter grün und wertlos."""
    paare = _paare()
    assert len(paare) > 40
    assert sum(len(v) for v in paare.values()) > 100


def test_keine_frische_spalte_traegt_noch_ihren_alten_namen(tmp_path):
    """Der eigentliche Wächter.

    Schlägt er an, heißt das: `CREATE TABLE` legt eine Spalte an, die die
    Migration sofort wieder umbenennt. Frische und gewachsene Datenbank haben
    dann verschiedene Schemata — und jeder SQL-Satz, der die Spalte nennt,
    läuft in genau einer der beiden Formen ins Leere."""
    schema = _frisches_schema(tmp_path / "frisch.sqlite")
    befunde = []
    for tabelle, paare in _paare().items():
        vorhanden = schema.get(tabelle)
        if not vorhanden:
            continue                       # Tabelle gibt es (noch) nicht
        for alt, neu in paare.items():
            if alt in vorhanden:
                befunde.append(
                    f"{tabelle}.{alt} steht im CREATE TABLE, wird aber nach "
                    f"{neu!r} migriert — auf dev/Prod heißt sie längst {neu!r}")
    assert not befunde, (
        "Frisches Schema und Migration widersprechen sich:\n  "
        + "\n  ".join(befunde))


def test_die_migration_fuehrt_eine_alte_form_in_die_frische_ueber(tmp_path):
    """Die Gegenrichtung, an einem echten Fall gemessen.

    Eine Datenbank in der ALTEN Form muss nach dem Öffnen genau die Spalten
    tragen, die eine frisch angelegte hat — sonst ist eine der beiden Formen
    für den Code unerreichbar."""
    alt_pfad = tmp_path / "alt.sqlite"
    conn = sqlite3.connect(alt_pfad)
    conn.execute(
        "CREATE TABLE council_integrated_debt ("
        "year INTEGER PRIMARY KEY, ars TEXT NOT NULL, population REAL, "
        "insgesamt REAL NOT NULL, per_capita REAL, core_budget REAL, "
        "extra_budgets REAL, sonstige REAL, extra_under_50 REAL, "
        "other_below_50 REAL, change REAL, probes TEXT NOT NULL, "
        "herkunft_id INTEGER, fetched_at TEXT NOT NULL)")
    conn.commit()
    conn.close()

    gewachsen = _frisches_schema(alt_pfad)["council_integrated_debt"]
    frisch = _frisches_schema(tmp_path / "frisch.sqlite")["council_integrated_debt"]
    assert gewachsen == frisch, (
        "Nach der Migration hat die gewachsene Datenbank andere Spalten als "
        f"eine frische: nur gewachsen {sorted(gewachsen - frisch)}, "
        f"nur frisch {sorted(frisch - gewachsen)}")
