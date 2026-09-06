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

Der Abruf hält ein Ergebnis 60 s (so lange cacht auch der Votemanager) und
behält bei einem Netzfehler den letzten guten Stand — mit Fehlervermerk.
"""
from __future__ import annotations

import csv
import io
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests

DEFAULT_BASE = "https://votemanager.kdo.de/20260913/03403000"
PRESENTATION_PATH = "/praesentation/"
FILES = {
    "city": "/daten/opendata/Open-Data-03403000-Stadtratswahl-Stadt.csv",
    "areas": "/daten/opendata/Open-Data-03403000-Stadtratswahl-Wahlbereiche.csv",
    "districts": "/daten/opendata/Open-Data-03403000-Stadtratswahl-Wahlbezirk.csv",
}
TTL_SECONDS = 60
TIMEOUT = (5, 20)
UA = "Ratslotse-Wahlabend/1.0 (+https://ratslotse.de/wahlabend)"


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
    ok: bool
    error: str | None


_lock = threading.Lock()
_cache: tuple[float, Snapshot] | None = None


def _get(session: requests.Session, url: str) -> tuple[str, str | None]:
    resp = session.get(url, timeout=TIMEOUT, headers={"User-Agent": UA})
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text, resp.headers.get("Last-Modified")


def fetch(force: bool = False) -> Snapshot:
    """Die drei CSVs, höchstens einmal je Minute vom Server."""
    global _cache
    with _lock:
        now = time.monotonic()
        if _cache and not force and now - _cache[0] < TTL_SECONDS:
            return _cache[1]
        previous = _cache[1] if _cache else None
        try:
            with requests.Session() as s:
                city, lm = _get(s, base_url() + FILES["city"])
                areas, _ = _get(s, base_url() + FILES["areas"])
                districts, _ = _get(s, base_url() + FILES["districts"])
            snap = Snapshot(parse(city), parse(areas), parse(districts), datetime.now(timezone.utc), lm, True, None)
        except (requests.RequestException, ValueError) as exc:
            if previous is None:
                snap = Snapshot([], [], [], datetime.now(timezone.utc), None, False, f"{type(exc).__name__}: {exc}"[:200])
            else:
                snap = Snapshot(previous.city, previous.areas, previous.districts, previous.fetched_at,
                                previous.last_modified, False, f"{type(exc).__name__}: {exc}"[:200])
        _cache = (now, snap)
        return snap


def reset_cache() -> None:
    global _cache
    with _lock:
        _cache = None
