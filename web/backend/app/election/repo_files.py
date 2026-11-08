"""Wahldateien aus dem Repo — je Fassung einmal gelesen.

Was unter ``kommunalwahl/`` liegt (die Kandidaturen der OB-Wahl, die
eingefrorenen Stände, ihre Meta-Dateien), ändert sich mit einem Deploy oder
wenn ``scripts/wahl_einfrieren.py`` einen Stand neu schreibt — sonst nie.
Gelesen wurde es trotzdem bei jedem Aufruf: die Stichwahl je Anfrage zweimal
399 KB JSON (über 80 % ihrer Rechenzeit), die Übersicht ``/api/wahlen`` gut
dreißig Dateien.

**Der Schlüssel ist nicht der Pfad allein**, sondern Pfad, Änderungszeit und
Größe (``stamp``). Schreibt jemand eine Datei neu, gilt beim nächsten Aufruf
die neue Fassung — ohne Neustart. Ein ``stat`` kostet Mikrosekunden, das Lesen
und Parsen eine Millisekunde und mehr.

Was zur Laufzeit geschrieben wird — der Verlauf des Wahlabends — gehört NICHT
hierher; den hält ``history.py`` selbst.

**Was hier herauskommt, teilen sich alle Aufrufer.** Nie verändern: Wer
daraus etwas anderes bauen will, baut eine Kopie.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

#: (Pfad, Änderungszeit in ns, Größe) — eine Fassung einer Datei.
Stamp = tuple[str, int, int]


def stamp(path: Path) -> Stamp:
    """Die Fassung einer Datei. Wirft ``OSError``, wenn es sie nicht gibt —
    wie das Lesen selbst es täte."""
    st = path.stat()
    return (str(path), st.st_mtime_ns, st.st_size)


def json_file(path: Path) -> Any:
    """Eine JSON-Datei, geparst — einmal je Fassung. Nicht verändern."""
    return _json(stamp(path))


@lru_cache(maxsize=32)
def _json(key: Stamp) -> Any:
    return json.loads(Path(key[0]).read_text(encoding="utf-8"))


def reset() -> None:
    """Alles vergessen (für Tests)."""
    _json.cache_clear()
