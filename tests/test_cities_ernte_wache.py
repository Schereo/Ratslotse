"""Langsam ist auch kaputt — die Wache über einer laufenden Ernte.

Die Hildesheim-Ernte lief am 11.09.2026 elf Stunden und fiel dabei von 343
auf 8 Vorlagen je Stunde. Kein Fehler, kein Abbruch, keine Kennzahl: Bis der
Server ganz ausfiel, sah der Lauf aus wie Arbeit. Gemeldet hat es am Ende ein
Mensch, der die Dateigröße ansah.
"""
from __future__ import annotations

from collections import deque

import pytest

from council.cities import pipeline


class FalscherClient:
    """Nur das, was die Wache liest: die Dauern und ein Zähler."""

    def __init__(self, dauern: list[float]) -> None:
        self.dauern: deque[float] = deque(dauern, maxlen=50)
        self.requests_made = len(dauern)

    def langsam(self, schwelle: float) -> float | None:
        from council.cities.oparl import OParlClient
        return OParlClient.langsam(self, schwelle)  # type: ignore[arg-type]


def _lauf(dauern: list[float], objekte: int) -> tuple[int, dict]:
    client = FalscherClient(dauern)
    zahlen: dict = {}
    gezaehlt = sum(1 for _ in pipeline._mit_wache(
        range(objekte), client, zahlen, "Vorlagen", "teststadt"))
    return gezaehlt, zahlen


def test_ein_einbrechender_server_beendet_die_ernte():
    """50 Abrufe à 20 Sekunden — der Median liegt über der Grenze."""
    gezaehlt, zahlen = _lauf([20.0] * 50, objekte=1000)
    assert gezaehlt == pipeline.WACHE_TAKT, "nach der ersten Prüfung ist Schluss"
    assert "Antwortzeit im Median 20s" in zahlen["abgebrochen"]
    assert "Vorlagen" in zahlen["abgebrochen"], "der Abschnitt gehört in die Meldung"


def test_ein_gesunder_server_laeuft_durch():
    gezaehlt, zahlen = _lauf([1.0] * 50, objekte=1000)
    assert gezaehlt == 1000
    assert "abgebrochen" not in zahlen


def test_ein_einzelner_ausreisser_bricht_nichts_ab():
    """Ein langsamer Abruf ist Alltag; der Median deckt ihn zu."""
    gezaehlt, zahlen = _lauf([1.0] * 49 + [300.0], objekte=1000)
    assert gezaehlt == 1000
    assert "abgebrochen" not in zahlen


def test_wenige_messwerte_sind_kein_urteil():
    """Am Anfang eines Laufs gibt es nichts zu urteilen — auch nicht langsam."""
    gezaehlt, zahlen = _lauf([60.0] * 5, objekte=1000)
    assert gezaehlt == 1000, "fünf Abrufe entscheiden nicht über eine Ernte"


@pytest.mark.parametrize("stufe", ["Gremien", "Sitzungen", "Vorlagen"])
def test_jede_stufe_der_ernte_steht_unter_der_wache(stufe):
    """Der Wächter: Eine Schleife ohne Wache liefe wieder stundenlang blind.

    ``fetch`` holt in drei Abschnitten. Wer einen davon direkt über den
    Adapter laufen lässt, hat genau dort wieder den Zustand vom 11.09.2026.
    """
    import inspect
    quelle = inspect.getsource(pipeline.fetch)
    assert f'"{stufe}", spec.id' in quelle, (
        f"Der Abschnitt {stufe} läuft ohne `_mit_wache` — ein einbrechender "
        "Server fiele dort wieder niemandem auf.")
