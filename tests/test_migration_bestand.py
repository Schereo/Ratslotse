"""Eine gewachsene Datenbank muss nach der Migration aussehen wie eine frische.

**Die Lücke, die dieser Test schließt.** Jeder andere Test in dieser Suite
arbeitet auf einer Datenbank, die gerade erst aus ``SCHEMA`` entstanden ist.
dev und Prod entstehen aber aus etwas anderem: aus einem Bestand, über den
Migration um Migration gelaufen ist. Wer eine Spalte nur ins ``CREATE TABLE``
schreibt und den ``ALTER TABLE`` in ``_migrate()`` vergisst, bekommt deshalb
eine grüne CI und einen ``OperationalError`` beim nächsten Cron-Lauf.

Genau diese Klasse stellte im Sommer 2026 einen erheblichen Teil aller Fixes:
Spalten, die nur im Code umbenannt waren; ein Migrationspaar, das durch ein
Suchen-und-Ersetzen selbstgleich wurde; eine Werte-Migration, die abbrach,
weil der neue Wert schon existierte.

**Woher der Bestand kommt.** ``tests/schema_staende/*.sql`` sind die
Schema-Auszüge der laufenden Dev-Datenbanken — nur DDL, keine einzige
Datenzeile. Sie tragen den Zustand, den keine frische Datenbank hat: Tabellen
aus abgeschalteten Features, Spalten in der Reihenfolge ihres Nachwachsens,
Indizes aus drei Umbenennungswellen.

Auffrischen, wenn sich die Form auf dem Server wirklich geändert hat::

    python scripts/schema_stand.py pfad/zur/council.sqlite \\
        > tests/schema_staende/dev-council.sql

**Wird dieser Test rot, ist die Migration unvollständig — nicht der Test zu
streng.** Die Meldung nennt Tabelle und Spalte.

**Seit 09/2026 auch MIT Daten.** Bis dahin stand hier, dass die Auszüge keine
Zeile tragen und deshalb alles Inhaltsabhängige außerhalb bleibt — eine
Werte-Migration, die an einem doppelten Eintrag scheitert; ein Umzug, der auf
zwei gefüllte Tabellen trifft und absichtlich nichts tut; ein ``NOT NULL`` ohne
Vorgabewert auf einer nicht leeren Tabelle. Das war die größere Hälfte der
Klasse, denn eine Migration auf einer leeren Datenbank hat fast nichts zu tun.

``_befuellen()`` legt deshalb in **jede** Tabelle zwei Zeilen, bevor migriert
wird. Zwei und nicht eine: Eine Werte-Migration, die auf einen bereits
vergebenen Zielwert läuft, braucht zwei Zeilen, um zu scheitern. Gemessen am
04.09.2026 erreicht das 118 von 119 Tabellen (Prod) bzw. 123 von 124 (dev);
die eine Ausnahme ist ``council_entity_scanned``, das außer seiner
rowid-Spalte nichts hat. Ein eigener Test hält diese Abdeckung fest — sonst
könnte der Wächter still zu „nichts befüllt, nichts migriert" verkommen und
bliebe grün.

**Was er weiterhin NICHT sieht.** Die Zeilen sind erfunden und einförmig:
``1``/``2`` für Zahlen, ``x1``/``x2`` für Text. Eine Migration, die an einer
bestimmten *Gestalt* echter Daten scheitert (ein Datumsformat aus 2019, ein
JSON-Feld mit altem Schlüssel), sieht auch das nicht. Dafür bleibt die Probe
auf einer echten Kopie das Mittel der Wahl.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council.store import CouncilStore  # noqa: E402
from kern.store import Store  # noqa: E402

STAENDE = WURZEL / "tests" / "schema_staende"


def _form(pfad: Path) -> dict[str, set[str]]:
    """``{tabelle: {spalte, …}}`` — die vergleichbare Form einer Datenbank."""
    conn = sqlite3.connect(pfad)
    try:
        tabellen = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'")]
        return {t: {r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')}
                for t in tabellen}
    finally:
        conn.close()


def _bestand_anlegen(ziel: Path, auszug: Path) -> None:
    """Legt eine Datenbank in der Form des eingecheckten Auszugs an."""
    conn = sqlite3.connect(ziel)
    try:
        conn.executescript(auszug.read_text())
        conn.commit()
    finally:
        conn.close()


def _befuellen(pfad: Path) -> tuple[int, int]:
    """Legt in jede Tabelle zwei Zeilen. Gibt (befüllt, gesamt) zurück.

    Die Werte sind erfunden und müssen nur zu ihrem Spaltentyp passen —
    geprüft wird die Migration, nicht der Inhalt. Fremdschlüssel stören nicht:
    SQLite erzwingt sie ohne ``PRAGMA foreign_keys=ON`` nicht, und genau so
    läuft der Store auch im Betrieb.
    """
    conn = sqlite3.connect(pfad)
    try:
        tabellen = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'")]
        befuellt = 0
        for t in tabellen:
            spalten = list(conn.execute(f'PRAGMA table_info("{t}")'))
            pks = [r for r in spalten if r[5]]
            # Nur die rowid-Alias-Spalte auslassen (EINE ganzzahlige PK). Eine
            # zusammengesetzte PK ist NOT NULL und muss gefüllt werden — an
            # dieser Unterscheidung hingen zunächst 52 leere Tabellen.
            weg = ({pks[0][1]} if len(pks) == 1
                   and "INT" in (pks[0][2] or "").upper() else set())
            cols = [(r[1], r[2]) for r in spalten if r[1] not in weg]
            if not cols:
                continue
            namen = ",".join(f'"{n}"' for n, _ in cols)
            platz = ",".join("?" * len(cols))
            for i in (1, 2):
                try:
                    conn.execute(f'INSERT INTO "{t}" ({namen}) VALUES ({platz})',
                                 [_wert(typ, name, i) for name, typ in cols])
                except sqlite3.Error:
                    break            # CHECK o. Ä. — diese Tabelle bleibt leer
                else:
                    befuellt = befuellt + 1 if i == 1 else befuellt
        conn.commit()
        return befuellt, len(tabellen)
    finally:
        conn.close()


def _wert(typ: str | None, name: str, i: int):
    t = (typ or "").upper()
    if "INT" in t:
        return i
    if any(x in t for x in ("REAL", "FLOA", "DOUB", "NUM", "DEC")):
        return float(i)
    if "BLOB" in t:
        return b"x"
    n = name.lower()
    if "date" in n or n.endswith("_at") or n in ("created", "updated"):
        return "2020-01-01"
    return f"x{i}"


#: Welcher Auszug zu welchem Store gehört.
#:
#: **Prod ist der eigentliche Prüfstein.** Am 02.09.2026 stand die
#: Produktionsdatenbank noch vor dem großen Umzug: 104 Tabellen unter ihren
#: alten, deutschen Namen, die Konten in ``nwz.sqlite``. Auf dev war beides
#: längst gelaufen. Der Release, der beide Stände zusammenbringt, fährt darum
#: Dutzende Migrationen auf einmal — und der einzige Weg, das vorher zu
#: sehen, ist, sie gegen die Prod-Form laufen zu lassen. Genau das tut dieser
#: Fall.
#:
#: (``prod-ratslotse.sql`` trägt die Form von ``nwz.sqlite`` — die Datei heißt
#: auf Prod noch so, der Inhalt ist dieselbe Konten-Datenbank.)
FAELLE = [
    pytest.param("dev-council.sql", CouncilStore, id="dev-council"),
    pytest.param("dev-ratslotse.sql", Store, id="dev-konten"),
    pytest.param("prod-council.sql", CouncilStore, id="prod-council"),
    pytest.param("prod-ratslotse.sql", Store, id="prod-konten"),
]


@pytest.mark.parametrize("auszug, klasse", FAELLE)
def test_der_bestand_erreicht_die_form_der_frischen_datenbank(auszug, klasse, tmp_path):
    """Nach der Migration darf keine Spalte fehlen, die eine frische DB hat.

    Nur diese Richtung wird geprüft: Dass eine gewachsene Datenbank ZUSÄTZLICH
    Tabellen aus abgeschalteten Features trägt, ist normal und harmlos. Dass
    ihr eine Spalte FEHLT, die der Code voraussetzt, ist der Ausfall.
    """
    bestand = tmp_path / "bestand.sqlite"
    _bestand_anlegen(bestand, STAENDE / auszug)
    klasse(bestand)                      # öffnen migriert
    frisch = tmp_path / "frisch.sqlite"
    klasse(frisch)

    soll, ist = _form(frisch), _form(bestand)

    fehlende_tabellen = sorted(set(soll) - set(ist))
    assert not fehlende_tabellen, (
        "Diese Tabellen legt das Schema an, im migrierten Bestand fehlen sie:\n  "
        + "\n  ".join(fehlende_tabellen)
    )

    fehlend = [f"{t}.{s}" for t in sorted(soll)
               for s in sorted(soll[t] - ist.get(t, set()))]
    assert not fehlend, (
        "Diese Spalten stehen im CREATE TABLE, aber keine Migration legt sie "
        "auf einer gewachsenen Datenbank an. Auf dev und Prod fehlen sie "
        "deshalb — trag einen ALTER TABLE in _migrate() nach:\n  "
        + "\n  ".join(fehlend)
    )


@pytest.mark.parametrize("auszug, klasse", FAELLE)
def test_die_migration_ist_wiederholbar(auszug, klasse, tmp_path):
    """Zweimal öffnen muss dasselbe ergeben wie einmal.

    Jeder Deploy startet die Dienste neu, jeder Cron öffnet die Datenbank
    erneut — eine Migration läuft in ihrem Leben hunderte Male. Eine, die beim
    zweiten Mal stolpert (doppelter Wert, schon vorhandene Spalte), reißt
    nicht den Umbau ab, sondern den nächsten ganz normalen Lauf.
    """
    bestand = tmp_path / "bestand.sqlite"
    _bestand_anlegen(bestand, STAENDE / auszug)
    klasse(bestand)
    nach_erstem = _form(bestand)
    klasse(bestand)                      # zweiter Lauf, muss folgenlos sein
    assert _form(bestand) == nach_erstem


@pytest.mark.parametrize("auszug, klasse", FAELLE)
def test_kein_alter_tabellenname_ueberlebt_die_migration(auszug, klasse, tmp_path):
    """Der Umzug muss auf dem Bestand wirklich stattgefunden haben.

    Die Umzugskarte wirkt nur auf gewachsenen Datenbanken — auf einer frischen
    gibt es nichts umzubenennen. Ohne diesen Test prüft niemand, ob sie greift.
    """
    modul = sys.modules[klasse.__module__]
    karte = getattr(modul, "TABELLEN_UMBENANNT", [])
    if not karte:
        pytest.skip("keine Umzugskarte in diesem Modul")

    bestand = tmp_path / "bestand.sqlite"
    _bestand_anlegen(bestand, STAENDE / auszug)
    klasse(bestand)

    vorhanden = set(_form(bestand))
    # Ein alter Name darf nur dann stehen bleiben, wenn beide Tabellen gefüllt
    # waren — das kann der Auszug ohne Daten nicht auslösen.
    geblieben = sorted(alt for alt, neu in karte if alt != neu and alt in vorhanden)
    assert not geblieben, (
        "Diese Tabellen tragen nach der Migration noch ihren alten Namen:\n  "
        + "\n  ".join(geblieben)
    )


# ---------------------------------------------------------------------------
# Dieselben Stände, aber MIT Zeilen darin.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("auszug, klasse", FAELLE)
def test_die_migration_laeuft_auch_auf_gefuellten_tabellen(auszug, klasse, tmp_path):
    """Der Fall, den die leeren Auszüge nicht erreichen.

    Eine Migration auf einer leeren Datenbank hat fast nichts zu tun: Ein
    ``UPDATE`` trifft keine Zeile, ein Umzug findet nichts zu kopieren, ein
    ``NOT NULL`` ohne Vorgabewert stört niemanden. Genau darin lagen die
    Ausfälle — eine Werte-Migration, die abbrach, weil der neue Wert schon
    vergeben war, ist auf einer leeren Tabelle unmöglich.
    """
    bestand = tmp_path / "bestand.sqlite"
    _bestand_anlegen(bestand, STAENDE / auszug)
    _befuellen(bestand)
    klasse(bestand)                      # öffnen migriert — darf nicht werfen

    frisch = tmp_path / "frisch.sqlite"
    klasse(frisch)
    soll, ist = _form(frisch), _form(bestand)
    fehlend = [f"{t}.{s}" for t in sorted(soll)
               for s in sorted(soll[t] - ist.get(t, set()))]
    assert not fehlend, (
        "Auf einer GEFÜLLTEN Datenbank fehlen nach der Migration Spalten, die "
        "eine frische hat. Ein `ALTER TABLE`, der auf leeren Tabellen "
        "durchläuft und auf gefüllten scheitert, ist fast immer ein NOT NULL "
        "ohne Vorgabewert:\n  " + "\n  ".join(fehlend))


@pytest.mark.parametrize("auszug, klasse", FAELLE)
def test_auch_auf_gefuellten_tabellen_wiederholbar(auszug, klasse, tmp_path):
    """Zweimal öffnen, diesmal mit Inhalt — der Fall aus dem Betrieb."""
    bestand = tmp_path / "bestand.sqlite"
    _bestand_anlegen(bestand, STAENDE / auszug)
    _befuellen(bestand)
    klasse(bestand)
    nach_erstem = _form(bestand)
    klasse(bestand)
    assert _form(bestand) == nach_erstem


@pytest.mark.parametrize("auszug, klasse", FAELLE)
def test_die_probe_fuellt_wirklich_fast_alles(auszug, klasse, tmp_path):
    """Der Wächter über dem Wächter.

    Bekäme ``_befuellen`` seine Zeilen nicht mehr unter (eine neue
    CHECK-Bedingung, eine geänderte Typ-Zuordnung), liefen die beiden Tests
    darüber weiter grün — sie prüften dann nur wieder leere Tabellen. Diese
    Schranke macht das sichtbar, statt es zu verschweigen.
    """
    bestand = tmp_path / "bestand.sqlite"
    _bestand_anlegen(bestand, STAENDE / auszug)
    befuellt, gesamt = _befuellen(bestand)
    assert befuellt >= gesamt - 1, (
        f"Nur {befuellt} von {gesamt} Tabellen bekamen Zeilen. Die beiden "
        "Tests darüber prüfen dann fast nichts mehr. Erlaubt ist genau eine "
        "Ausnahme (`council_entity_scanned` hat außer der rowid keine "
        "Spalte) — bei mehr gehört `_wert()` nachgezogen.")
