"""Die Open-Data-CSVs des Votemanagers lesen — live und als Referenz von 2021.

Drei Dateien je Wahl: Stadt, Wahlbereiche, Wahlbezirke. Alle drei haben
denselben Kopf; je Wahlvorschlag ``n`` stehen darin (Schema 2026)::

    D<n>_1      Listenstimmen              (2021: D<n>_liste)
    D<n>_3      Summe der Personenstimmen  (2021: D<n>_summe_kandidaten)
    D<n>_4      Gesamt = Liste + Personen  (2021: D<n>_summe_liste_kandidaten)
    D<n>_2_<k>  Stimmen für Listenplatz k  (2021: D<n>_<k>)

Ein Einzelwahlvorschlag hat nur ``D<n>_4``. Davor: ``A`` Wahlberechtigte,
``B`` Wähler*innen, ``C1``/``C2`` ungültige/gültige Stimmzettel, ``D`` gültige
Stimmen, und ``max-schnellmeldungen`` / ``anz-schnellmeldungen`` als
Auszählungsstand des Gebiets. **Leer heißt „liegt noch nicht vor"**, nicht null.

Der Abruf hält ein Ergebnis 60 s (so lange cacht auch der Votemanager).

**Jede Datei hat ihr eigenes Gedächtnis.** Vorher hing der ganze Abruf an der
schwächsten der drei: Ein Aussetzer bei den Wahlbezirken ließ auch die frisch
gemeldeten Wahlbereiche liegen, und die Seite stand still, obwohl zwei Drittel
der Daten da waren. Jetzt wird jede Datei einzeln geholt; scheitert eine, gilt
für SIE der letzte gute Stand, die anderen ziehen weiter. ``Snapshot.ok`` ist
dann ``False`` und ``Snapshot.error`` nennt die Datei beim Namen.

**Status 200 heißt nicht, dass es die Datei ist.** Ein Reverse-Proxy antwortet
im Zweifel mit einer HTML-Wartungsseite, ein halb geschriebener Export mit
nichts. Beides parst ``csv`` klaglos zu null Zeilen — und null Zeilen sehen
aus wie „noch nicht ausgezählt". Deshalb prüft ``_header_of`` die Antwort,
bevor sie den letzten guten Stand ersetzt.
"""
from __future__ import annotations

import csv
import io
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests

from . import crosscheck

DEFAULT_BASE = "https://votemanager.kdo.de/20260913/03403000"
PRESENTATION_PATH = "/praesentation/"
FILES = {
    "city": "/daten/opendata/Open-Data-03403000-Stadtratswahl-Stadt.csv",
    "areas": "/daten/opendata/Open-Data-03403000-Stadtratswahl-Wahlbereiche.csv",
    "districts": "/daten/opendata/Open-Data-03403000-Stadtratswahl-Wahlbezirk.csv",
}
#: Anzeigename je Datei — ein Fehlertext muss sagen, WELCHE Datei klemmt.
FILE_NAMES = {"city": "Stadt", "areas": "Wahlbereiche", "districts": "Wahlbezirke"}
#: Spalten, ohne die eine Antwort keine Ergebnis-CSV ist.
REQUIRED_COLUMNS = ("gebiet-name", "max-schnellmeldungen")
TTL_SECONDS = 60
#: (verbinden, lesen). Drei Dateien nacheinander, jede Minute eine Runde: Ein
#: langes Lese-Zeitlimit hielte den Request-Thread fest, während die Seite
#: schon längst den alten Stand hätte zeigen können.
TIMEOUT = (5, 10)
UA = "Ratslotse-Wahlabend/1.0 (+https://ratslotse.de/wahlabend)"

_log = logging.getLogger("ratslotse.web.wahlabend")


def base_url() -> str:
    return os.environ.get("WAHLABEND_VOTEMANAGER_URL", DEFAULT_BASE).rstrip("/")


def presentation_url() -> str:
    return base_url() + PRESENTATION_PATH


# ------------------------------------------------------------------ Parsen

@dataclass(frozen=True)
class ListRow:
    """Ein Wahlvorschlag in einer CSV-Zeile (Stadt, Wahlbereich oder Bezirk)."""

    index: int
    total: int | None
    list_votes: int | None
    candidate_sum: int | None
    candidates: dict[int, int] | None


@dataclass(frozen=True)
class AreaRow:
    name: str
    number: int | None
    reports_expected: int
    reports_received: int
    eligible: int | None
    voters: int | None
    invalid_ballots: int | None
    valid_ballots: int | None
    valid_votes: int | None
    lists: dict[int, ListRow] = field(default_factory=dict)

    @property
    def counted(self) -> bool:
        return self.reports_received > 0 and self.valid_votes is not None


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    return int(value) if re.fullmatch(r"-?\d+", value) else None


def _area_number(name: str, number: str | None) -> int | None:
    """Wahlbereich 1…6 aus „Wahlbereich 1", „I - Stadtmitte Nord" oder ``gebiet-nr``."""
    if number and number.strip().isdigit():
        n = int(number)
        if 1 <= n <= 6:
            return n
    m = re.search(r"Wahlbereich\s+(\d)", name)
    if m:
        return int(m.group(1))
    roman = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}
    m = re.match(r"([IVX]+)\s*[-–]", name)
    return roman.get(m.group(1)) if m else None


def district_number(name: str, number: str | None) -> int | None:
    """Nummer des Wahlbezirks (101…966) aus ``gebiet-nr`` oder dem Namen."""
    if number and number.strip().isdigit():
        return int(number)
    m = re.match(r"(\d{3})\b", name)
    return int(m.group(1)) if m else None


def area_of_district(number: int) -> int | None:
    """Wahlbezirk -> Wahlbereich. Urnenbezirke tragen den Wahlbereich als
    Hunderter (101…115 = I, 400…416 = IV), Briefwahlbezirke als Zehner hinter
    der 9 (910…916 = I, 960…966 = VI). Gemessen an allen 133 Bezirken 2021."""
    if 100 <= number < 700:
        return number // 100
    if 910 <= number < 970:
        return (number - 900) // 10
    return None


def parse(text: str) -> list[AreaRow]:
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿")), delimiter=";"))
    if not rows:
        return []
    header = list(rows[0].keys())
    old_scheme = any(h.endswith("_liste") for h in header)
    indices = sorted({int(m.group(1)) for h in header for m in [re.match(r"D(\d+)_", h)] if m})
    out = []
    for r in rows:
        lists: dict[int, ListRow] = {}
        for n in indices:
            if old_scheme:
                total = _int(r.get(f"D{n}_summe_liste_kandidaten"))
                lv = _int(r.get(f"D{n}_liste"))
                cs = _int(r.get(f"D{n}_summe_kandidaten"))
                pat = re.compile(rf"D{n}_(\d+)$")
            else:
                total = _int(r.get(f"D{n}_4"))
                lv = _int(r.get(f"D{n}_1"))
                cs = _int(r.get(f"D{n}_3"))
                pat = re.compile(rf"D{n}_2_(\d+)$")
            cands: dict[int, int] = {}
            for h in header:
                m = pat.match(h)
                if m:
                    v = _int(r.get(h))
                    if v is not None:
                        cands[int(m.group(1))] = v
            lists[n] = ListRow(n, total, lv, cs, cands if cands else None)
        name = (r.get("gebiet-name") or "").strip()
        out.append(AreaRow(
            name=name,
            number=_area_number(name, r.get("gebiet-nr")),
            reports_expected=_int(r.get("max-schnellmeldungen")) or 0,
            reports_received=_int(r.get("anz-schnellmeldungen")) or 0,
            eligible=_int(r.get("A")),
            voters=_int(r.get("B")),
            invalid_ballots=_int(r.get("C1")),
            valid_ballots=_int(r.get("C2")),
            valid_votes=_int(r.get("D")),
            lists=lists,
        ))
    return out


# ------------------------------------------------------------------ Abruf

@dataclass
class Snapshot:
    city: list[AreaRow]
    areas: list[AreaRow]
    districts: list[AreaRow]
    fetched_at: datetime
    last_modified: str | None
    #: Sind ALLE drei Dateien frisch? Eine aus dem Gedächtnis genügt für ``False``.
    ok: bool
    #: Welche Datei mit welchem Fehler — ``None``, wenn alles frisch ist.
    error: str | None
    #: Hinweise der Spaltenprobe (``crosscheck``). Sie ändern ``ok`` NICHT: Ob
    #: die Spalten stimmen, ist eine andere Frage als ob die Zahlen da sind.
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Fetched:
    """Der letzte gute Stand EINER Datei."""

    rows: list[AreaRow]
    header: list[str]
    last_modified: str | None
    at: datetime


_lock = threading.Lock()
_cache: tuple[float, Snapshot] | None = None
#: Datei -> letzter guter Stand. Überlebt den Ablauf des Minuten-Caches.
_good: dict[str, _Fetched] = {}


def _get(session: requests.Session, url: str) -> tuple[str, str | None]:
    resp = session.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text, resp.headers.get("Last-Modified")


def _header_of(text: str) -> list[str]:
    """Die Kopfzeile — und die Prüfung, dass die Antwort überhaupt eine ist.

    Wirft ``ValueError``, wenn die Antwort leer ist, nach HTML aussieht, die
    Gebietsspalten fehlen oder plötzlich keine einzige ``D<n>_``-Spalte mehr
    da ist. Jeder dieser Fälle käme sonst mit Status 200 durch und ersetzte
    einen guten Stand durch nichts.
    """
    stripped = text.lstrip("﻿").lstrip()
    if not stripped:
        raise ValueError("leere Antwort")
    if stripped.startswith("<"):
        raise ValueError("HTML statt CSV")
    header = [h.strip() for h in stripped.splitlines()[0].split(";")]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise ValueError("Kopfzeile ohne " + "/".join(missing))
    if not any(re.match(r"D\d+_", h) for h in header):
        raise ValueError("Kopfzeile ohne D<n>-Spalten")
    return header


def _crosscheck(session: requests.Session, base: str, snap: Snapshot) -> list[str]:
    """Die vierte, OPTIONALE Datei. Ein Fehler hier ändert ``ok`` nicht."""
    try:
        header = _good["areas"].header if "areas" in _good else None
        counted = any(r.reports_received > 0 for r in snap.areas) or any(r.reports_received > 0 for r in snap.city)
        return crosscheck.run(session, base, header, counted=counted)
    except Exception:  # eine Zugabe darf den Abend nicht umbringen
        _log.exception("Wahlabend: Spaltenprobe fehlgeschlagen")
        return []


def fetch(force: bool = False) -> Snapshot:
    """Die drei CSVs, höchstens einmal je Minute vom Server.

    Jede für sich: Was frisch kommt, wird übernommen; was scheitert, bleibt
    beim letzten guten Stand. Erst danach die Spaltenprobe.
    """
    global _cache
    with _lock:
        now = time.monotonic()
        if _cache and not force and now - _cache[0] < TTL_SECONDS:
            return _cache[1]
        base = base_url()
        failed: list[tuple[str, str]] = []
        with requests.Session() as session:
            session.headers.update({"User-Agent": UA})
            for key, path in FILES.items():
                try:
                    text, last_modified = _get(session, base + path)
                    header = _header_of(text)
                    _good[key] = _Fetched(parse(text), header, last_modified, datetime.now(timezone.utc))
                except (requests.RequestException, ValueError) as exc:
                    failed.append((key, f"{type(exc).__name__}: {exc}"[:160]))
            # Der Fehlertext sagt beides: welche Datei, und ob für sie noch ein
            # alter Stand da ist. „Wahlbereiche klemmen" heißt einmal „die
            # Zahlen sind eine Minute alt" und einmal „es gibt keine".
            errors = [f"{FILE_NAMES[k]}: {msg} ({'alter Stand' if k in _good else 'keine Daten'})"
                      for k, msg in failed]
            city, areas, districts = (_good.get(k) for k in ("city", "areas", "districts"))
            known = [f for f in (city, areas, districts) if f is not None]
            snap = Snapshot(
                city=city.rows if city else [],
                areas=areas.rows if areas else [],
                districts=districts.rows if districts else [],
                fetched_at=max((f.at for f in known), default=datetime.now(timezone.utc)),
                last_modified=city.last_modified if city else None,
                ok=not errors,
                error="; ".join(errors)[:400] or None,
            )
            if errors:
                _log.warning("Wahlabend: Abruf unvollständig — %s", snap.error)
            snap.warnings = _crosscheck(session, base, snap)
        _cache = (now, snap)
        return snap


def reset_cache() -> None:
    """Den Minuten-Cache verwerfen. Das Gedächtnis je Datei bleibt — genau das
    ist beim nächsten Abruf der Rückfall."""
    global _cache
    with _lock:
        _cache = None


def reset_memory() -> None:
    """Alles vergessen, auch den letzten guten Stand je Datei (für Tests)."""
    global _cache
    with _lock:
        _cache = None
        _good.clear()
