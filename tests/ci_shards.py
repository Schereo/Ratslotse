"""Die Testsuite in Teile schneiden — für die CI (``pytest --shard i/n``).

**Warum.** Die Suite ist rechengebunden: rund 9.700 Tests, auf zehn Kernen gut
zwei Minuten, auf den vier Kernen eines CI-Läufers über fünf (gemessen
22.11.2026: ``Run tests`` 5:10 min). Kein einzelner Test ist der Engpass, also
hilft nur mehr Rechner — zwei Läufer, jeder mit der Hälfte der DATEIEN.

**Ganze Dateien, nie einzelne Tests.** Modul-Fixtures und die Reihenfolge
innerhalb einer Datei bleiben damit, wie sie sind.

**Über eine Prüfsumme des Dateinamens, nicht über eine Liste.** Eine neue
Testdatei landet von selbst in genau einem Teil; es gibt nichts nachzuziehen
und nichts, was man vergessen könnte. Der Preis ist, dass die Teile nicht auf
die Sekunde gleich lang sind — bei 600 Dateien mittelt sich das aus
(gemessen, s. ``.github/workflows/test.yml``).

**Die Wächter laufen weiter ALLE.** Geschnitten wird die Menge der Dateien,
nicht nach „was hat sich geändert": Viele Tests hier lesen quer durchs Repo
(Frontend-Quelltext, Workflows, Doku) und hängen an keiner Python-Datei, die
ein Auswahl-Werkzeug sehen könnte.
"""
from __future__ import annotations

import zlib


def parse_shard(spec: str) -> tuple[int, int]:
    """``"2/3"`` → ``(2, 3)``. Wirft bei allem, was kein Teil von n ist."""
    try:
        index, total = (int(part) for part in spec.split("/"))
    except ValueError:
        raise ValueError(f"--shard erwartet i/n, etwa 1/2 — nicht {spec!r}") from None
    if total < 1 or not 1 <= index <= total:
        raise ValueError(f"--shard {spec}: der Teil muss zwischen 1 und {total} liegen")
    return index, total


def shard_of(test_file: str, total: int) -> int:
    """Der Teil (ab 1), in dem diese Testdatei läuft.

    ``crc32`` und nicht ``hash()``: Pythons eigener Hash ist je Prozess
    gesalzen — jeder xdist-Arbeiter schnitte anders, und Tests liefen doppelt
    oder gar nicht.
    """
    return zlib.crc32(test_file.encode("utf-8")) % total + 1
