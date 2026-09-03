"""Wächter über das Vergleichswerkzeug selbst.

**Warum das ein Test ist.** Ein Werkzeug, das zwei Umgebungen vergleicht, hat
einen Fehlermodus, der schlimmer ist als kaputt: Es erklärt denselben Bestand
für verschieden und schickt jemanden auf die Suche nach einem Fehler, den es
nicht gibt. Genau das ist am 03.09.2026 passiert — die erste Fassung verkettete
die Spaltenwerte in der Reihenfolge von ``PRAGMA table_info``, und die ist die
PHYSISCHE Reihenfolge. Sie hängt an der Migrationsgeschichte: Auf dev waren
Spalten einzeln per ALTER TABLE gewachsen, auf Prod am Stück aus dem ``SCHEMA``
entstanden. ``council_products`` trug dieselben 19 Spalten mit denselben Werten
in anderer Folge — und der Vergleich meldete alle 623 Zeilen als abweichend.

Die Tests hier halten die drei Eigenschaften fest, auf denen die Aussagekraft
beruht: Spaltenreihenfolge egal, Umbenennung NICHT egal, echte Unterschiede
werden gefunden.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "scripts"))

from haushalt_fingerprint import fingerabdruck, spaltenabdruck  # noqa: E402
from haushalt_vergleich import bericht, lesen  # noqa: E402


def _db(pfad: Path, spaltenfolge: list[str], zeilen: list[dict]) -> sqlite3.Connection:
    """Eine Mini-Datenbank mit frei wählbarer SPALTENREIHENFOLGE.

    Der Punkt der Fixture: Dieselben Werte, andere Folge — nur so lässt sich
    die Eigenschaft prüfen, um die es geht.
    """
    conn = sqlite3.connect(pfad)
    ddl = ", ".join(f'"{s}" TEXT' for s in spaltenfolge)
    conn.executescript(f'''
        CREATE TABLE council_provenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL, probe TEXT NOT NULL, fetched_at TEXT NOT NULL);
        CREATE TABLE zahlen ({ddl});
    ''')
    for z in zeilen:
        spalten = [s for s in spaltenfolge if s in z]
        conn.execute(
            f'INSERT INTO zahlen ({", ".join(chr(34) + s + chr(34) for s in spalten)}) '
            f'VALUES ({", ".join("?" * len(spalten))})',
            [z[s] for s in spalten])
    conn.commit()
    return conn


ZEILEN = [
    {"year": "2024", "betrag": "1000", "titel": "Brücke", "herkunft_id": None},
    {"year": "2025", "betrag": "2000", "titel": "Schule", "herkunft_id": None},
]


def test_spaltenreihenfolge_aendert_den_abdruck_nicht(tmp_path):
    """DER Test dieser Datei. Ohne ihn wäre der Vergleich zwischen zwei
    gewachsenen Datenbanken wertlos."""
    a = _db(tmp_path / "a.sqlite",
            ["year", "betrag", "titel", "herkunft_id"], ZEILEN)
    b = _db(tmp_path / "b.sqlite",
            ["titel", "herkunft_id", "year", "betrag"], ZEILEN)
    try:
        _, ha, _ = fingerabdruck(a, "zahlen")
        _, hb, _ = fingerabdruck(b, "zahlen")
        assert ha == hb, (
            "Derselbe Bestand ergibt zwei verschiedene Abdrücke, sobald die "
            "Spalten anders herum im Schema stehen. Genau das war der Fehler "
            "vom 03.09.2026 — `_ausdruck()` muss nach Spaltennamen sortieren.")
    finally:
        a.close(); b.close()


def test_umbenannte_spalte_faellt_auf(tmp_path):
    """Die Gegenprobe zum Test darüber: Namenssortierung darf nicht dazu
    führen, dass eine Umbenennung stillschweigend durchgeht. Der Name gehört
    deshalb MIT in den Hash und ist nicht bloß Sortierkriterium."""
    a = _db(tmp_path / "a.sqlite", ["year", "betrag", "herkunft_id"], ZEILEN)
    b = _db(tmp_path / "b.sqlite", ["year", "summe", "herkunft_id"],
            [{"year": z["year"], "summe": z["betrag"]} for z in ZEILEN])
    try:
        _, ha, _ = fingerabdruck(a, "zahlen")
        _, hb, _ = fingerabdruck(b, "zahlen")
        assert ha != hb, ("Eine umbenannte Spalte ergibt denselben Abdruck — "
                          "dann verschweigt das Werkzeug Schema-Abweichungen.")
    finally:
        a.close(); b.close()


def test_ein_geaenderter_wert_wird_gefunden(tmp_path):
    """Und das Selbstverständliche, weil ein Werkzeug, das immer „gleich" sagt,
    auch alle Tests darüber besteht."""
    a = _db(tmp_path / "a.sqlite", ["year", "betrag", "herkunft_id"], ZEILEN)
    geaendert = [dict(ZEILEN[0], betrag="1001"), ZEILEN[1]]
    b = _db(tmp_path / "b.sqlite", ["year", "betrag", "herkunft_id"], geaendert)
    try:
        na, ha, za = fingerabdruck(a, "zahlen")
        nb, hb, zb = fingerabdruck(b, "zahlen")
        assert ha != hb
        assert na == nb == 2
        # Genau EINE Zeile weicht ab — das ist die Zahl, an der die Diagnose
        # hängt (ein Einzelfall vs. eine systematische Ursache).
        assert len(set(za) - set(zb)) == 1
    finally:
        a.close(); b.close()


def test_null_und_leerstring_sind_nicht_dasselbe(tmp_path):
    """Ein Feld, das nie gefüllt wurde, und ein Feld, das leer gelesen wurde,
    sind zwei verschiedene Befunde — der Abdruck darf sie nicht verwischen."""
    a = _db(tmp_path / "a.sqlite", ["year", "titel", "herkunft_id"],
            [{"year": "2024", "titel": None}])
    b = _db(tmp_path / "b.sqlite", ["year", "titel", "herkunft_id"],
            [{"year": "2024", "titel": ""}])
    try:
        _, ha, _ = fingerabdruck(a, "zahlen")
        _, hb, _ = fingerabdruck(b, "zahlen")
        assert ha != hb
    finally:
        a.close(); b.close()


def test_spaltenabdruck_nennt_die_schuldige_spalte(tmp_path):
    """Der Schritt nach einem Befund: Weicht jede Zeile ab, soll der
    Spalten-Abdruck sagen, an welcher Spalte es liegt."""
    a = _db(tmp_path / "a.sqlite", ["year", "betrag", "titel", "herkunft_id"], ZEILEN)
    geaendert = [dict(z, titel=z["titel"] + " (neu)") for z in ZEILEN]
    b = _db(tmp_path / "b.sqlite", ["year", "betrag", "titel", "herkunft_id"], geaendert)
    try:
        sa = dict(spaltenabdruck(a, "zahlen"))
        sb = dict(spaltenabdruck(b, "zahlen"))
        abweichend = {k for k in sa if sa[k] != sb[k]}
        assert abweichend == {"titel"}, abweichend
    finally:
        a.close(); b.close()


# --------------------------------------------------------- die Auswertung

def test_vergleich_liest_seine_eigene_ausgabe(tmp_path):
    """`haushalt_vergleich.lesen()` muss die Schlusszeile des Fingerabdrucks
    („56 Tabellen, 0 Zeilen ohne Herkunft") NICHT als Tabelle lesen — sie hat
    drei Felder wie eine echte Zeile."""
    p = tmp_path / "fp.txt"
    p.write_text(
        "council_budget                                 98  " + "a" * 64 + "\n"
        "    council_budget\t" + "b" * 64 + "\n"
        "\n56 Tabellen, 0 Zeilen ohne Herkunft\n", encoding="utf-8")
    tab, zeilen = lesen(str(p))
    assert list(tab) == ["council_budget"]
    assert tab["council_budget"][1] == 98
    assert zeilen == {"council_budget": {"b" * 64}}


def test_bericht_meldet_gleichstand_und_unterschied(tmp_path):
    gleich = tmp_path / "a.txt"
    gleich.write_text("t1  10  " + "a" * 64 + "\n", encoding="utf-8")
    anders = tmp_path / "b.txt"
    anders.write_text("t1  10  " + "c" * 64 + "\n", encoding="utf-8")

    text, code = bericht(str(gleich), str(gleich))
    assert code == 0 and "Identisch" in text

    text, code = bericht(str(anders), str(gleich))
    assert code == 1 and "`t1`" in text


def test_bericht_meldet_eine_leere_ausgabe_als_aufrufproblem(tmp_path):
    """Eine leere Datei darf nicht als „identisch" durchgehen — das wäre ein
    grüner Vergleich, der nichts verglichen hat."""
    leer = tmp_path / "leer.txt"
    leer.write_text("", encoding="utf-8")
    voll = tmp_path / "voll.txt"
    voll.write_text("t1  10  " + "a" * 64 + "\n", encoding="utf-8")
    _, code = bericht(str(leer), str(voll))
    assert code == 2


def test_fehlende_tabelle_wird_getrennt_gemeldet(tmp_path):
    """Eine Tabelle, die es nur auf einer Seite gibt, ist kein Zahlenproblem,
    sondern ein fehlender Ingest — und soll nicht in derselben Zeile stehen."""
    a = tmp_path / "a.txt"
    a.write_text("t1  10  " + "a" * 64 + "\nt2  5  " + "b" * 64 + "\n", encoding="utf-8")
    b = tmp_path / "b.txt"
    b.write_text("t1  10  " + "a" * 64 + "\n", encoding="utf-8")
    text, code = bericht(str(a), str(b))
    assert code == 1
    assert "Nur in einer Umgebung vorhanden" in text and "`t2`" in text
