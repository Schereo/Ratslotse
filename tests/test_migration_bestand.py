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

**Was er NICHT sieht.** Die Auszüge tragen keine Daten, also auch keinen
einzigen Wert. Alles, was von Inhalten abhängt, bleibt außerhalb: eine
Werte-Migration, die an einem doppelten Eintrag scheitert; ein Umzug, der auf
zwei gefüllte Tabellen trifft und deshalb absichtlich nichts tut; ein
``NOT NULL`` ohne Vorgabewert auf einer nicht leeren Tabelle. Für diese Klasse
bleibt die Probe auf einer echten Kopie das Mittel der Wahl.
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
