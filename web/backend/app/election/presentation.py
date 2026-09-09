"""Die Ergebnisdarstellung des Votemanagers als Ersatzquelle.

Die Seite unter ``/praesentation/`` ist eine Vue-Anwendung; alles, was sie
zeigt, lädt sie aus JSON-Dateien unter ``/daten/api/wahl_<id>/``. Genau die
lesen wir hier — kein HTML, kein Browser. Die Dateien liegen sicher vor,
sobald die Stadt selbst etwas zeigt; ob die Open-Data-CSVs am Wahlabend
genauso zügig gefüllt werden, weiß niemand. Deshalb der zweite Weg.

Gemessen an der Ratswahl 2021 auf demselben Votemanager (die Fixtures unter
``tests/fixtures/wahlabend/praesentation-2021/``):

``wahl.json``
    ``menu_links`` — die Gebiets-Id der Stadt (``type: ergebnis``) und die
    Ebene der Wahlbereiche (``type: uebersicht``, Titel „Wahlbereiche").

``uebersicht_<ebene>_0.json``
    Eine Zeile je Wahlbereich mit ``label`` („I - Stadtmitte Nord") und
    ``link.id`` („ebene_5_id_1235"). **Vor der Auszählung ist die Datei leer**
    (nur ein Zeitstempel) — die Ids sind erst zur Laufzeit zu haben.

``ergebnis_<gebiet>_0.json``
    ``Komponente.tabelle.zeilen``: je Liste drei Zeilen — „Summe Partei- und
    Kandidaten-Stimmen", „Stimmen für die Partei", „Summe Kandidaten-Stimmen".
    Die dritte trägt ``sub_zeilen``: jede Bewerber*in mit Name und Stimmen,
    **in Listenreihenfolge** (2021, Wahlbereich I, SPD: zwölf Zeilen, Werte
    1:1 gleich den CSV-Spalten ``D1_1…D1_12``). ``Komponente.info.tabelle``
    trägt Wahlberechtigte, Wähler*innen, Stimmzettel und gültige Stimmen,
    ``info.hinweis`` den Auszählungsstand („22 von 22 Ergebnissen"). Die
    Stadt-Ebene trägt nach der Auszählung zusätzlich ``Komponente.sitze`` —
    die Sitzverteilung, wie der Votemanager sie rechnet.

Zwei Dinge unterscheiden diese Quelle von der CSV, und beide sind der Grund,
warum sie nur der Ersatz ist:

- **Die Listen stehen unter ihrem Namen, nicht unter einer Spaltennummer.**
  Eine Liste, die in einem Wahlbereich nicht antritt, fehlt dort einfach; die
  Zuordnung zum Register läuft über Schlüsselwörter (``crosscheck.KEYWORDS``).
  Passt ein Name zu keiner oder zu zwei Listen, wird der ganze Wahlbereich
  verworfen — eine fehlende Partei rechnete sich sonst still zu null Stimmen.
- **Die Bewerber*innen tragen keinen Listenplatz**, nur ihre Position in der
  Reihenfolge. Platz ``k`` ist Zeile ``k``; das hält der Vergleich gegen die
  CSV von 2021 in ``tests/test_wahlabend_praesentation.py``.

Zahlen kommen als Text mit Tausenderpunkt („1.868"); ein leerer Text heißt
„liegt noch nicht vor", nicht null — wie in der CSV.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import requests

from . import crosscheck
from .register import Register

#: Der API-Pfad der Stadtratswahl (Wahl-Id 913).
API_PATH = "/daten/api/wahl_913"
#: Gebiets-Id der Stadt und Ebene der Wahlbereiche — die Vorgabe, falls
#: ``wahl.json`` nicht zu haben ist. Beide Werte stehen dort und werden von
#: dort gelesen; die Konstanten sind der Notnagel.
DEFAULT_CITY_ID = "ebene_-6361_id_10358"
DEFAULT_AREAS_LEVEL = "ebene_-6362"
TIMEOUT = (5, 10)

_log = logging.getLogger("ratslotse.web.wahlabend")

_NUMBER = re.compile(r"-?\d{1,3}(?:\.\d{3})+|-?\d+")
_REPORTS = re.compile(r"(\d+)\s+von\s+(\d+)")


# ------------------------------------------------------------------ Modell

@dataclass(frozen=True)
class PresentationList:
    """Eine Liste in der Ergebnistabelle EINES Gebiets."""

    name: str
    total: int | None
    list_votes: int | None
    candidate_sum: int | None
    #: Stimmen je Bewerber*in in Listenreihenfolge; ``None`` = noch nicht da.
    candidates: tuple[int, ...] | None
    single: bool = False


@dataclass(frozen=True)
class PresentationArea:
    title: str
    reports_expected: int
    reports_received: int
    eligible: int | None
    voters: int | None
    invalid_ballots: int | None
    valid_ballots: int | None
    valid_votes: int | None
    lists: tuple[PresentationList, ...]
    #: Sitze je Liste, wie der Votemanager sie ausweist (nur Stadt-Ebene).
    official_seats: dict[str, int] = field(default_factory=dict)

    @property
    def counted(self) -> bool:
        return self.reports_received > 0 and self.valid_votes is not None


@dataclass(frozen=True)
class Fetched:
    """Ein Abruf: Wahlbereiche unter ihrem Label, die Stadt, die Fehler."""

    areas: dict[str, PresentationArea]
    city: PresentationArea | None
    city_payload: Any | None
    errors: list[str]


# ------------------------------------------------------------------ Parsen

def parse_number(value: Any) -> int | None:
    if not isinstance(value, str):
        return value if isinstance(value, int) and not isinstance(value, bool) else None
    text = value.strip().replace(" ", "")
    if not _NUMBER.fullmatch(text):
        return None
    return int(text.replace(".", ""))


def _component(payload: Any) -> dict[str, Any] | None:
    """``Komponente`` — ein Objekt oder eine Liste davon; ohne Tabelle ``None``."""
    if not isinstance(payload, dict):
        return None
    component = payload.get("Komponente")
    for c in component if isinstance(component, list) else [component]:
        if isinstance(c, dict) and isinstance(c.get("tabelle"), dict):
            return c
    return None


def _rows(table: Any) -> list[Any]:
    if isinstance(table, dict) and isinstance(table.get("zeilen"), list):
        return table["zeilen"]
    return []


def _reports(component: dict[str, Any]) -> tuple[int, int]:
    """„22 von 22 Ergebnissen" aus ``info.hinweis`` oder dem Fuß der Grafik."""
    texts: list[str] = []
    info = component.get("info")
    if isinstance(info, dict):
        hint = info.get("hinweis")
        texts += [h for h in hint if isinstance(h, str)] if isinstance(hint, list) else [str(hint or "")]
    graph = component.get("grafik")
    if isinstance(graph, dict) and isinstance(graph.get("footer"), str):
        texts.append(graph["footer"])
    for t in texts:
        m = _REPORTS.search(t)
        if m:
            return int(m.group(2)), int(m.group(1))
    return 0, 0


def _totals(component: dict[str, Any]) -> dict[str, int | None]:
    out: dict[str, int | None] = {k: None for k in ("eligible", "voters", "invalid_ballots", "valid_ballots", "valid_votes")}
    info = component.get("info")
    for row in _rows(info.get("tabelle") if isinstance(info, dict) else None):
        label = (crosscheck.label_of(row) or "").lower()
        value = parse_number(row.get("zahl")) if isinstance(row, dict) else None
        if label.startswith("wahlberechtigte"):
            out["eligible"] = value
        elif label.startswith("wähler"):
            out["voters"] = value
        elif "ungültige stimmzettel" in label:
            out["invalid_ballots"] = value
        elif "gültige stimmzettel" in label:
            out["valid_ballots"] = value
        elif "gültige stimmen" in label:
            out["valid_votes"] = value
    return out


def _candidates(row: dict[str, Any]) -> tuple[int, ...] | None:
    sub = row.get("sub_zeilen")
    if not isinstance(sub, list) or not sub:
        return None
    values = [parse_number(s.get("zahl")) if isinstance(s, dict) else None for s in sub]
    if any(v is None for v in values):
        return None
    return tuple(v for v in values if v is not None)


def _lists(component: dict[str, Any]) -> tuple[PresentationList, ...]:
    order: list[str] = []
    fields: dict[str, dict[str, Any]] = {}

    def entry(name: str) -> dict[str, Any]:
        if name not in fields:
            order.append(name)
            fields[name] = {"total": None, "list_votes": None, "candidate_sum": None, "candidates": None, "single": False}
        return fields[name]

    for row in _rows(component.get("tabelle")):
        label = crosscheck.label_of(row)
        if not label or not isinstance(row, dict):
            continue
        name, sep, suffix = label.rpartition(" - ")
        kind = crosscheck.suffix_kind(suffix) if sep else None
        value = parse_number(row.get("zahl"))
        if kind == crosscheck.TOTAL:
            entry(name.strip())["total"] = value
        elif kind == crosscheck.LIST:
            entry(name.strip())["list_votes"] = value
        elif kind == crosscheck.CANDIDATES:
            e = entry(name.strip())
            e["candidate_sum"] = value
            e["candidates"] = _candidates(row)
        elif "einzelwahlvorschlag" in label.lower():
            e = entry(name.strip() if sep and "einzelwahlvorschlag" in suffix.lower() else label)
            e["total"] = value
            e["single"] = True
    return tuple(PresentationList(name, **fields[name]) for name in order)


def _official_seats(component: dict[str, Any]) -> dict[str, int]:
    seats = component.get("sitze")
    pie = seats.get("tortenDiagramm") if isinstance(seats, dict) else None
    entries = pie.get("entries") if isinstance(pie, dict) else None
    out: dict[str, int] = {}
    for e in entries if isinstance(entries, list) else []:
        if isinstance(e, dict) and isinstance(e.get("label"), str) and isinstance(e.get("sitze"), int):
            out[e["label"]] = e["sitze"]
    return out


def parse_area(payload: Any) -> PresentationArea | None:
    """Ein Gebiets-JSON — ``None``, solange es keine ``Komponente`` trägt
    (vor der Auszählung liegt dort nur ein Zeitstempel)."""
    component = _component(payload)
    if component is None:
        return None
    info = component.get("info")
    raw_title = info.get("titel") if isinstance(info, dict) else None
    title = raw_title.strip() if isinstance(raw_title, str) else ""
    expected, received = _reports(component)
    totals = _totals(component)
    return PresentationArea(
        title=title, reports_expected=expected, reports_received=received,
        eligible=totals["eligible"], voters=totals["voters"], invalid_ballots=totals["invalid_ballots"],
        valid_ballots=totals["valid_ballots"], valid_votes=totals["valid_votes"],
        lists=_lists(component), official_seats=_official_seats(component),
    )


def area_links(payload: Any) -> list[tuple[str, str]]:
    """(Label, Gebiets-Id) je Wahlbereich aus der Übersicht — leer vor der Auszählung."""
    out: list[tuple[str, str]] = []
    if not isinstance(payload, dict):
        return out
    for row in _rows(payload.get("tabelle")):
        if not isinstance(row, dict):
            continue
        link = row.get("link")
        label = row.get("label")
        if isinstance(link, dict) and link.get("type") == "ergebnis" and isinstance(link.get("id"), str) \
                and isinstance(label, str) and label.strip():
            out.append((label.strip(), link["id"]))
    return out


def ids_of(payload: Any) -> tuple[str | None, str | None]:
    """(Gebiets-Id der Stadt, Ebene der Wahlbereiche) aus ``wahl.json``."""
    city: str | None = None
    areas: str | None = None
    links = payload.get("menu_links") if isinstance(payload, dict) else None
    for link in links if isinstance(links, list) else []:
        if not isinstance(link, dict) or not isinstance(link.get("id"), str):
            continue
        title = str(link.get("title") or "").lower()
        if link.get("type") == "ergebnis" and city is None:
            city = link["id"]
        elif link.get("type") == "uebersicht" and "wahlbereich" in title and areas is None:
            areas = link["id"]
    return city, areas


# ------------------------------------------------------------------ Zuordnung

Resolver = Callable[[str], int | None]


def resolver(reg: Register) -> Resolver:
    """Listenname des Votemanagers -> Spaltenindex im Register, über die
    Schlüsselwörter der Spaltenprobe. Genau EIN Treffer, sonst ``None``."""

    def resolve(name: str) -> int | None:
        slugs = crosscheck.slugs_for(name)
        if len(slugs) != 1:
            return None
        party = reg.by_slug(next(iter(slugs)))
        return party.index if party else None

    return resolve


# ------------------------------------------------------------------ Abruf

_ids: tuple[str, str] | None = None


def _get_json(session: requests.Session, url: str) -> Any:
    resp = session.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def resolve_ids(session: requests.Session, base: str) -> tuple[str, str]:
    """Stadt-Id und Wahlbereichs-Ebene, einmal aus ``wahl.json`` gelesen und
    dann behalten. Ohne Antwort die Vorgabe — und beim nächsten Mal ein neuer
    Versuch."""
    global _ids
    if _ids is not None:
        return _ids
    try:
        city, areas = ids_of(_get_json(session, base + API_PATH + "/wahl.json"))
    except (requests.RequestException, ValueError) as exc:
        _log.info("Wahlabend: wahl.json ohne Antwort (%s: %s) — Vorgabe-Ids", type(exc).__name__, exc)
        return DEFAULT_CITY_ID, DEFAULT_AREAS_LEVEL
    _ids = (city or DEFAULT_CITY_ID, areas or DEFAULT_AREAS_LEVEL)
    return _ids


def fetch(session: requests.Session, base: str) -> Fetched:
    """Übersicht, je Wahlbereich ein JSON, die Stadt. Wirft nie; was scheitert,
    steht in ``errors``."""
    errors: list[str] = []
    areas: dict[str, PresentationArea] = {}
    city: PresentationArea | None = None
    city_payload: Any | None = None
    city_id, level = resolve_ids(session, base)
    try:
        links = area_links(_get_json(session, f"{base}{API_PATH}/uebersicht_{level}_0.json"))
    except (requests.RequestException, ValueError) as exc:
        links = []
        errors.append(f"Übersicht: {type(exc).__name__}: {exc}"[:160])
    for label, gid in links:
        try:
            area = parse_area(_get_json(session, f"{base}{API_PATH}/ergebnis_{gid}_0.json"))
        except (requests.RequestException, ValueError) as exc:
            errors.append(f"{label}: {type(exc).__name__}: {exc}"[:160])
            continue
        if area is not None:
            areas[label] = area
    try:
        city_payload = _get_json(session, f"{base}{API_PATH}/ergebnis_{city_id}_0.json")
        city = parse_area(city_payload)
    except (requests.RequestException, ValueError) as exc:
        errors.append(f"Stadt: {type(exc).__name__}: {exc}"[:160])
    return Fetched(areas, city, city_payload, errors)


def reset() -> None:
    """Die gemerkten Ids vergessen (für Tests)."""
    global _ids
    _ids = None
