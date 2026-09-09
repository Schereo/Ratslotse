"""Der Sync des Städte-Speichers auf einen Server.

Der Plan sah zuerst einen Backfill auf der dev-VM vor — dort neu ernten und
neu beurteilen. Tims Einwand am 09.09.2026: „können wir nicht die
Arbeitsdaten von hier syncen?" Gemessen am selben Abend: Die dev-VM hat gar
keine `cities.sqlite`, Prod eine 270-KB-Hülle. Es gibt nichts zusammen-
zuführen, also ist es eine Kopie — und 14 GB PDFs neu zu holen wäre Arbeit
für nichts gewesen.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "scripts"))

import lokale_daten  # noqa: E402


@pytest.fixture()
def keine_kopie(monkeypatch, tmp_path):
    """Eine ECHTE, leere Städte-Datenbank; kopiert wird nichts.

    Echt, weil `schieb_staedte` sie mit `VACUUM INTO` kompaktiert — gegen
    eine erfundene Datei liefe der Test am Kern vorbei. Gezählt wird, welche
    Befehle abgesetzt WÜRDEN.
    """
    from council.cities.store import CitiesStore

    laeufe: list[list[str]] = []
    monkeypatch.setattr(lokale_daten, "_lauf", lambda b, *a, **k: laeufe.append(b))
    monkeypatch.setattr(lokale_daten, "WURZEL", tmp_path)
    monkeypatch.setattr(lokale_daten, "SPEICHER", tmp_path / "cache")
    (tmp_path / "data").mkdir()
    CitiesStore(tmp_path / "data" / "cities.sqlite").close()
    return laeufe


def test_weigert_sich_wenn_auf_dem_ziel_schon_daten_liegen(keine_kopie, monkeypatch):
    """Eine Rückmeldung eines Ratsmitglieds darf kein lokaler Stand
    überschreiben — und sobald der Cron dort läuft, ist der Server frischer."""
    monkeypatch.setattr(lokale_daten, "_fernbestand",
                        lambda host: {"papers": 30673, "feedback": 4})
    assert lokale_daten.schieb_staedte("prod", ja=False) == 1
    assert not keine_kopie, "es darf nichts kopiert worden sein"


def test_ja_ueberstimmt_die_weigerung(keine_kopie, monkeypatch):
    """Die Gegenrichtung: Wer wirklich ersetzen will, kann es sagen."""
    monkeypatch.setattr(lokale_daten, "_fernbestand",
                        lambda host: {"papers": 30673, "feedback": 0})
    assert lokale_daten.schieb_staedte("prod", ja=True) == 0
    assert any(b[0] == "scp" for b in keine_kopie)


def test_leeres_ziel_wird_nicht_geschuetzt(keine_kopie, monkeypatch):
    """Eine 270-KB-Hülle ohne Vorlagen ist kein Bestand, den man schützt —
    genau so sah Prod am 09.09.2026 aus."""
    monkeypatch.setattr(lokale_daten, "_fernbestand", lambda host: None)
    assert lokale_daten.schieb_staedte("dev", ja=False) == 0
    ziele = [b[-1] for b in keine_kopie if b[0] == "scp"]
    assert ziele and ziele[0].endswith("cities.sqlite")


def test_die_pdfs_bleiben_hier(keine_kopie, monkeypatch):
    """14 GB Dateien, deren Text längst in `texts` steht und die der
    Web-Dienst nie liest — sie zu kopieren wäre Arbeit für nichts."""
    monkeypatch.setattr(lokale_daten, "_fernbestand", lambda host: None)
    lokale_daten.schieb_staedte("dev", ja=False)
    assert not any("cities-files" in " ".join(b) for b in keine_kopie)
