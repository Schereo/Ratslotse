"""Eine gesperrte Datenbank kostet eine Vorlage, nicht den Lauf.

Am 14.11.2026 brach der Wahlprogramm-Bestand auf dev nach 461 von 662 Vorlagen
an ``database is locked`` ab (``scripts/vorlagen_dossiers.py::Sperre``).
"""
from __future__ import annotations

import sqlite3

import pytest

from scripts import vorlagen_dossiers as vd


@pytest.fixture(autouse=True)
def _ohne_warten(monkeypatch):
    pausen: list[float] = []
    monkeypatch.setattr(vd.time, "sleep", pausen.append)
    return pausen


def _gesperrt():
    raise sqlite3.OperationalError("database is locked")


def test_gesperrte_datenbank_ueberspringt_die_vorlage(_ohne_warten):
    sperre = vd.Sperre()
    assert sperre.bauen("26/0001", _gesperrt) is None
    assert sperre.uebersprungen == 1 and _ohne_warten == [vd.SPERRE_PAUSE_SEKUNDEN]
    # Die nächste Vorlage läuft normal — und setzt die Folge zurück.
    assert sperre.bauen("26/0002", lambda: {"payload": {}}) == {"payload": {}}
    assert sperre.in_folge == 0


def test_dauerhafte_sperre_beendet_den_lauf_mit_dem_fehler():
    sperre = vd.Sperre()
    for _ in range(vd.SPERRE_MAX - 1):
        assert sperre.bauen("26/0001", _gesperrt) is None
    with pytest.raises(sqlite3.OperationalError):
        sperre.bauen("26/0001", _gesperrt)


def test_andere_datenbankfehler_bleiben_fehler():
    def kaputt():
        raise sqlite3.OperationalError("no such table: template_terms")
    with pytest.raises(sqlite3.OperationalError):
        vd.Sperre().bauen("26/0001", kaputt)


def test_alle_drei_stufen_bauen_ueber_die_sperre():
    """Wer eine vierte Stufe ergänzt, ruft ``build_for_template`` nicht nackt auf."""
    import inspect
    import re
    quelle = inspect.getsource(vd)
    aufrufe = re.findall(r"^.*\.build_for_template\(.*$", quelle, flags=re.M)
    assert len(aufrufe) == 3
    assert all("sperre.bauen(" in zeile for zeile in aufrufe), aufrufe


def test_lauf_holt_nachgetragene_vorlagen_und_schaut_zurueck(monkeypatch):
    """Der Haushaltsentwurf 2027 (26/0835) kam am Sitzungstag auf die
    Tagesordnung, nach dem Morgenlauf. Der Dossier-Lauf holt solche Vorlagen
    nach und schaut drei Tage zurück — sonst fiel die Sitzung am nächsten
    Morgen aus dem Fenster, ohne dass je ein Dossier entstand."""
    from datetime import date, timedelta

    from scripts import backfill_vorlagen

    reihenfolge: list = []
    monkeypatch.setattr(backfill_vorlagen, "process_missing",
                        lambda db, limit=None, workers=6: reihenfolge.append("vorlagen") or
                        {"fetched": 1, "no_pdf": 0, "failed": 0, "total": 1})
    monkeypatch.setattr(vd.punkt_texte, "nachladen",
                        lambda store, tage_zurueck, limit, bis_heute: reihenfolge.append(("texte", tage_zurueck, bis_heute))
                        or {"geladen": 2, "offen": 2, "antraege": 0, "fehler": 0})

    class Store:
        def __init__(self, *_):
            pass

        def vorlagen_kommender_sitzungen(self, von, bis):
            reihenfolge.append(("fenster", von, bis))
            return []

        def close(self):
            pass

    monkeypatch.setattr(vd, "CouncilStore", Store)
    monkeypatch.setattr(vd, "lauf", lambda vorlagen, max_usd: {"vorlagen": len(vorlagen)})
    monkeypatch.setattr(vd.features, "an", lambda key: False)
    k = vd.main()
    heute = date.today()
    assert reihenfolge == ["vorlagen", ("texte", vd.TAGE_ZURUECK, True),
                           ("fenster", (heute - timedelta(days=3)).isoformat(),
                            (heute + timedelta(days=21)).isoformat())]
    assert k["vorlagen_nachgeholt"] == 1 and k["punkt_texte_nachgeholt"] == 2


def test_gesperrte_datenbank_im_vorlauf_kostet_nicht_den_lauf(monkeypatch):
    """Ein langer Schreiber (FTS-Neubau von check_protocols) sperrt die Datei —
    dann fällt das Nachholen aus, die Dossiers laufen trotzdem (Review 23.11.2026)."""
    from scripts import backfill_vorlagen

    def gesperrt(*a, **k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(backfill_vorlagen, "process_missing", gesperrt)
    monkeypatch.setattr(vd.punkt_texte, "nachladen", gesperrt)

    class Store:
        def __init__(self, *_):
            pass

        def vorlagen_kommender_sitzungen(self, von, bis):
            return ["26/0835"]

        def close(self):
            pass

    monkeypatch.setattr(vd, "CouncilStore", Store)
    monkeypatch.setattr(vd, "lauf", lambda vorlagen, max_usd: {"vorlagen": len(vorlagen)})
    monkeypatch.setattr(vd.features, "an", lambda key: False)
    k = vd.main()
    assert k["vorlagen"] == 1 and k["vorlagen_nachgeholt"] == 0 and k["punkt_texte_nachgeholt"] == 0
