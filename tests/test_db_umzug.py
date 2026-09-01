"""Der Umzug `nwz.sqlite` → `ratslotse.sqlite` und sein Stolperstein.

Die Datenbank hieß bis 08/2026 anders. Damit kein Deployment von Hand
umbenennen muss, zieht der Start die Datei selbst um. Der Umzug ist einmalig
und erkennt sich daran, dass die Zieldatei noch nicht da ist.

Genau diese Erkennung hatte eine Lücke: Eine **leere** Zieldatei zählte als
„schon umgezogen". Sie entsteht, sobald irgendetwas den neuen Pfad einmal
öffnet, ohne zu schreiben — und danach unterbleibt der Umzug für immer. Der
Start legte dann das Schema in der leeren Datei an, und die App käme mit
leeren Konten hoch, während die echten Daten unter dem alten Namen liegen.

Am 01.09.2026 stand auf Prod eine 0-Byte-`ratslotse.sqlite` neben einer
37-MB-`nwz.sqlite` mit 22 Konten. Der nächste Release nach `main` hätte
gereicht.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kern.store import _umzug_von_nwz  # noqa: E402


def _db_mit_inhalt(pfad: Path) -> None:
    conn = sqlite3.connect(pfad)
    conn.execute("CREATE TABLE web_users (id INTEGER PRIMARY KEY, email TEXT)")
    conn.execute("INSERT INTO web_users (email) VALUES ('pruef@example.org')")
    conn.commit()
    conn.close()


def test_umzug_benennt_die_alte_datei_um(tmp_path):
    """Der Normalfall, den es seit 08/2026 gibt."""
    alt, ziel = tmp_path / "nwz.sqlite", tmp_path / "ratslotse.sqlite"
    _db_mit_inhalt(alt)
    _umzug_von_nwz(ziel)
    assert ziel.exists() and not alt.exists()
    with sqlite3.connect(ziel) as c:
        assert c.execute("SELECT COUNT(*) FROM web_users").fetchone()[0] == 1


def test_eine_leere_zieldatei_blockiert_den_umzug_nicht(tmp_path):
    """Der Fehler vom 01.09.2026 — der eigentliche Grund für diese Datei."""
    alt, ziel = tmp_path / "nwz.sqlite", tmp_path / "ratslotse.sqlite"
    _db_mit_inhalt(alt)
    ziel.touch()                       # 0 Byte, wie auf Prod
    assert ziel.stat().st_size == 0
    _umzug_von_nwz(ziel)
    assert not alt.exists(), "die alte Datei muss umgezogen sein"
    with sqlite3.connect(ziel) as c:
        assert c.execute("SELECT COUNT(*) FROM web_users").fetchone()[0] == 1, \
            "die Konten müssen überlebt haben"


def test_eine_gefuellte_zieldatei_wird_nie_ueberschrieben(tmp_path):
    """Die Gegenrichtung: Ist der Umzug gelaufen, darf nichts mehr passieren —
    auch dann nicht, wenn unter dem alten Namen wieder etwas auftaucht."""
    alt, ziel = tmp_path / "nwz.sqlite", tmp_path / "ratslotse.sqlite"
    _db_mit_inhalt(ziel)
    _db_mit_inhalt(alt)
    _umzug_von_nwz(ziel)
    assert alt.exists(), "die fremde Datei bleibt liegen, statt zu verschwinden"
    with sqlite3.connect(ziel) as c:
        assert c.execute("SELECT email FROM web_users").fetchone()[0] == "pruef@example.org"


def test_ohne_alte_datei_passiert_nichts(tmp_path):
    """Frischer Checkout: Es gibt nichts umzuziehen, und eine leere Zieldatei
    darf trotzdem nicht gelöscht werden — sie ist dann die Datenbank."""
    ziel = tmp_path / "ratslotse.sqlite"
    ziel.touch()
    _umzug_von_nwz(ziel)
    assert ziel.exists()


def test_eine_leere_alte_datei_zieht_nicht_um(tmp_path):
    """Auf dev liegt seit dem Umzug eine 0-Byte-`nwz.sqlite`. Die darf die
    gefüllte Zieldatei niemals ersetzen."""
    alt, ziel = tmp_path / "nwz.sqlite", tmp_path / "ratslotse.sqlite"
    _db_mit_inhalt(ziel)
    alt.touch()
    _umzug_von_nwz(ziel)
    with sqlite3.connect(ziel) as c:
        assert c.execute("SELECT COUNT(*) FROM web_users").fetchone()[0] == 1
