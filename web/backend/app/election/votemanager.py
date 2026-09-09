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

**Wenn die CSV nicht liefert, liefert die Website.** Die Ergebnisdarstellung
des Votemanagers lädt ihre Zahlen aus JSON-Dateien (``presentation.py``); je
Wahlbereich stehen dort dieselben Größen samt Personenstimmen in
Listenreihenfolge. Fehlt einem Wahlbereich in der CSV noch die
Personenstimme (oder die Datei ganz), wird die JSON-Fassung geholt und
übernommen, wo sie weiter ist. Die CSV bleibt die erste Quelle: Ihre Spalten
sind nummeriert, die JSON-Listen tragen nur Namen.

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

from . import crosscheck, presentation
from .register import load as load_register

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
#: Vor dem Wahlabend liegen die CSVs leer da; sie jede Minute zu holen, wäre
#: Lärm beim Votemanager und bei uns. Bis Sonntag 18 Uhr reicht ein
#: Viertelstundentakt — danach greift der Minutentakt.
TTL_SECONDS_BEFORE = 15 * 60
#: 13.09.2026, 18:00 Uhr in Oldenburg (MESZ = UTC+2).
ELECTION_NIGHT_START = datetime(2026, 9, 13, 16, 0, tzinfo=timezone.utc)


def ttl_seconds(now: datetime | None = None) -> int:
    """Wie lange ein Abruf gilt: 60 s am Wahlabend, 15 min davor."""
    now = now or datetime.now(timezone.utc)
    return TTL_SECONDS if now >= ELECTION_NIGHT_START else TTL_SECONDS_BEFORE
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
    roman = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}
    m = re.search(r"Wahlbereich\s+(\d|[IVX]+)\b", name)
    if m:
        return int(m.group(1)) if m.group(1).isdigit() else roman.get(m.group(1))
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
    #: Sitze je Liste (Slug), wie der Votemanager sie auf der Stadt-Ebene
    #: ausweist — ``None``, solange er keine zeigt. Nur zur Gegenprobe.
    official_seats: dict[str, int] | None = None


# ------------------------------------------------------------------ Ersatz: die Ergebnisdarstellung

def row_from_presentation(area: presentation.PresentationArea, label: str, number: int | None,
                          resolve: presentation.Resolver) -> tuple[AreaRow | None, list[str]]:
    """Ein Gebiet der Ergebnisdarstellung als ``AreaRow`` — oder ``None`` mit
    Begründung, wenn eine Liste keinem Register-Eintrag zuzuordnen ist. Halb
    ist hier schlechter als gar nicht: Eine fehlende Liste zählte in der
    Zuteilung als null Stimmen."""
    lists: dict[int, ListRow] = {}
    for pl in area.lists:
        index = resolve(pl.name)
        if index is None:
            return None, [f"{label}: Die Liste ‚{pl.name}‘ der Ergebnisdarstellung passt zu keinem "
                          f"Eintrag im Register — der Wahlbereich bleibt außen vor."]
        if index in lists:
            return None, [f"{label}: Die Liste ‚{pl.name}‘ der Ergebnisdarstellung trifft dieselbe "
                          f"Spalte D{index} wie eine andere — der Wahlbereich bleibt außen vor."]
        cands = {k: v for k, v in enumerate(pl.candidates, start=1)} if pl.candidates is not None else None
        lists[index] = ListRow(index, pl.total, pl.list_votes, pl.candidate_sum, cands)
    return AreaRow(
        name=label, number=number,
        reports_expected=area.reports_expected, reports_received=area.reports_received,
        eligible=area.eligible, voters=area.voters, invalid_ballots=area.invalid_ballots,
        valid_ballots=area.valid_ballots, valid_votes=area.valid_votes, lists=lists,
    ), []


def _has_persons(row: AreaRow) -> bool:
    return any(lr.candidates is not None for lr in row.lists.values())


def _needs_presentation(areas: list[AreaRow] | None) -> bool:
    """Fehlt die Wahlbereichsdatei, oder fehlt einem Wahlbereich noch die
    Personenstimme? Dann lohnt der Blick in die Ergebnisdarstellung."""
    if not areas:
        return True
    return any(not _has_persons(r) for r in areas)


def _better(csv_row: AreaRow | None, json_row: AreaRow) -> bool:
    """Übernommen wird die JSON-Fassung, wo die CSV-Zeile fehlt — oder wo
    sie weiter ist: ausgezählt mit Personenstimmen, während die CSV-Zeile
    keine trägt."""
    if csv_row is None:
        return True
    return json_row.counted and _has_persons(json_row) and not _has_persons(csv_row)


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
#: Der letzte gute Stand aus der Ergebnisdarstellung: Wahlbereich -> Zeile,
#: dazu ``0`` für die Stadt. Überlebt wie ``_good`` den Minuten-Cache.
_pres: dict[int, AreaRow] = {}
_pres_seats: dict[str, int] | None = None


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


def _official_seats(payload: object) -> dict[str, int]:
    """Die Sitzverteilung des Votemanagers aus der Stadt-Tabelle, je Slug."""
    city = presentation.parse_area(payload)
    seats: dict[str, int] = {}
    for name, n in (city.official_seats if city else {}).items():
        slugs = crosscheck.slugs_for(name)
        if len(slugs) == 1:
            seats[next(iter(slugs))] = n
    return seats


def _crosscheck(session: requests.Session, base: str, snap: Snapshot, payload: object | None) -> list[str]:
    """Die vierte, OPTIONALE Datei. Ein Fehler hier ändert ``ok`` nicht.

    Nebenbei die Sitzverteilung, die der Votemanager selbst ausweist — sie
    steht in derselben Datei und wandert als ``official_seats`` in den Stand,
    damit ``service.compose`` sie gegen die eigene Zuteilung halten kann."""
    global _pres_seats
    try:
        header = _good["areas"].header if "areas" in _good else None
        counted = any(r.reports_received > 0 for r in snap.areas) or any(r.reports_received > 0 for r in snap.city)
        if payload is None and counted:
            payload = crosscheck.fetch_table(session, base)
        if payload is not None:
            seats = _official_seats(payload)
            if seats:
                _pres_seats = seats
        snap.official_seats = _pres_seats
        return crosscheck.run(session, base, header, counted=counted, payload=payload)
    except Exception:  # eine Zugabe darf den Abend nicht umbringen
        _log.exception("Wahlabend: Spaltenprobe fehlgeschlagen")
        return []


def _from_presentation(session: requests.Session, base: str) -> tuple[list[str], object | None]:
    """Die Ergebnisdarstellung holen und in ``_pres`` übernehmen, was weiter
    ist. Zurück kommen Hinweise für die Seite und die Stadt-Tabelle für die
    Spaltenprobe. Wirft nie."""
    notes: list[str] = []
    try:
        reg = load_register()
        resolve = presentation.resolver(reg)
        got = presentation.fetch(session, base)
        for label, area in got.areas.items():
            number = _area_number(label, None)
            if number is None:
                continue  # die Übersicht führt auch die Stadt selbst
            row, why = row_from_presentation(area, label, number, resolve)
            notes += why
            if row is not None:
                _pres[number] = row
        if got.city is not None:
            row, why = row_from_presentation(got.city, got.city.title or "Stadt Oldenburg", None, resolve)
            notes += why
            if row is not None:
                _pres[0] = row
        if got.errors:
            _log.info("Wahlabend: Ergebnisdarstellung teilweise ohne Antwort — %s", "; ".join(got.errors)[:400])
        return notes, got.city_payload
    except Exception:  # der Ersatz darf den Hauptweg nicht mitnehmen
        _log.exception("Wahlabend: Ersatzpfad über die Ergebnisdarstellung fehlgeschlagen")
        return notes, None


def _merge_presentation(snap: Snapshot) -> list[str]:
    """Wo die Ergebnisdarstellung weiter ist als die CSV, ihre Zeilen einsetzen."""
    by_number = {r.number: r for r in snap.areas if r.number is not None}
    taken: list[str] = []
    for number in sorted(n for n in _pres if n > 0):
        json_row = _pres[number]
        if _better(by_number.get(number), json_row):
            by_number[number] = json_row
            taken.append(json_row.name)
    if taken:
        untouched = [r for r in snap.areas if r.number is None]
        snap.areas = [by_number[n] for n in sorted(by_number)] + untouched
    city_json = _pres.get(0)
    city_csv = snap.city[0] if snap.city else None
    if city_json is not None and (city_csv is None or (not city_csv.counted and city_json.counted)):
        snap.city = [city_json]
        taken.append("Stadt")
    if not taken:
        return []
    return [f"{', '.join(taken)}: Zahlen aus der Ergebnisdarstellung des Votemanagers — die Open-Data-CSV "
            f"trägt dort noch keine Personenstimmen."]


def fetch(force: bool = False) -> Snapshot:
    """Die drei CSVs, höchstens einmal je Minute vom Server.

    Jede für sich: Was frisch kommt, wird übernommen; was scheitert, bleibt
    beim letzten guten Stand. Erst danach die Spaltenprobe.
    """
    global _cache
    with _lock:
        now = time.monotonic()
        if _cache and not force and now - _cache[0] < ttl_seconds():
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
            payload: object | None = None
            notes: list[str] = []
            if _needs_presentation(areas.rows if areas else None):
                notes, payload = _from_presentation(session, base)
                notes += _merge_presentation(snap)
            snap.warnings = _crosscheck(session, base, snap, payload) + notes
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
    global _cache, _pres_seats
    with _lock:
        _cache = None
        _good.clear()
        _pres.clear()
        _pres_seats = None
        presentation.reset()
