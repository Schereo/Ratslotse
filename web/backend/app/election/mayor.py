"""Die OB-Wahl aus der Ergebnisdarstellung des Votemanagers.

Anders als die Ratswahl hat die Wahl der Oberbürgermeisterin/des
Oberbürgermeisters **keine Open-Data-CSV** — gemessen am 11.09.2026: acht
Namensmuster probiert (``Oberbuergermeisterwahl-Stadt.csv`` und Varianten),
alle 404, auch im Archiv von 2021. Die Zahlen kommen deshalb ausschließlich
aus der Ergebnisdarstellung (``presentation.py``), aber mit einer anderen
Wahl-Id und einer flachen Tabelle: Jede Zeile IST eine Kandidatur, nicht drei
Zeilen je Liste wie bei der Ratswahl.

Gemessen an der Ratswahl 2021 auf demselben Votemanager
(``wahl_223/ergebnis_ebene_3_id_513_0.json``, Fixture unter
``tests/fixtures/wahlabend/ob-2021.json``)::

    Komponente.tabelle.zeilen[]      je Kandidatur: label.labelKurz „Krogmann, SPD",
                                      zahl „29.564", prozent „40,92 %"
    Komponente.info.hinweis[]        „133 von 133 Ergebnissen"  ← Auszählungsstand
    Komponente.info.tabelle.zeilen[] Wahlberechtigte / Wählerinnen/Wähler /
                                      ungültige Stimmen / gültige Stimmen
    Komponente.gewaehlte_kandidaten  bei einer Stichwahl: title + items[].label

**Falle beim Wiederverwenden von ``presentation._totals``:** Die Info-Tabelle
der OB-Wahl trägt nur VIER Zeilen („ungültige Stimmen" / „gültige Stimmen"),
nicht fünf wie bei der Ratswahl („ungültige Stimmzettel" / „gültige
Stimmzettel" / „gültige Stimmen"). ``presentation._totals`` prüft
``"gültige stimmen" in label`` — und das ist auch in „**un**gültige Stimmen"
enthalten. Nur weil die Zeilen in der richtigen Reihenfolge stehen (die
gültige-Zeile kommt NACH der ungültigen und überschreibt den falschen Wert),
kommt ``valid_votes`` dort zufällig richtig heraus; ``invalid_ballots"
bliebe für die OB-Wahl aber immer ``None``. Deshalb hier eine eigene, robustere
Prüfung mit ``startswith`` statt ``in``, und "ungültige" VOR "gültige".

Die neun Kandidaturen selbst kommen — wie von Tim verlangt — nicht aus einer
zweiten Handschrift, sondern aus ``kommunalwahl/wahl-fakten.json``
(``ob_kandidaten``); ein Slug wird aus dem Nachnamen abgeleitet (``slug_of``).
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from . import crosscheck, presentation
from .register import KOMMUNALWAHL
from .votemanager import TIMEOUT, UA, ttl_seconds

#: Wahl-Id der OB-Wahl 2026 (gemessen 11.09.2026: ``daten/api/termin.json``).
WAHL_ID = 2552
#: Gebiets-Id der Stadt für diese Wahl — Vorgabe, falls ``termin.json`` einmal
#: nicht zu haben ist; wird sonst daraus gelesen (``resolve_ids``).
DEFAULT_CITY_ID = "ebene_-6360_id_10357"
API_PATH = f"/daten/api/wahl_{WAHL_ID}"
TERMIN_PATH = "/daten/api/termin.json"

_log = logging.getLogger("ratslotse.web.wahlabend")

_PERCENT = re.compile(r"-?\d+(?:,\d+)?")
_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                          "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})


# ------------------------------------------------------------------ Modell

@dataclass(frozen=True)
class MayorCandidate:
    slug: str
    name: str
    #: Kurzform der vorschlagenden Partei/Wählergruppe, leer bei Einzel-
    #: wahlvorschlägen. Aus dem Register, NICHT aus der Ergebnisdarstellung.
    party: str
    votes: int | None
    share_pct: float | None


@dataclass(frozen=True)
class MayorResult:
    #: "before" (nichts ausgezählt) | "counting" | "complete".
    phase: str
    reports_expected: int
    reports_received: int
    turnout_pct: float | None
    valid_votes: int | None
    invalid_ballots: int | None
    candidates: tuple[MayorCandidate, ...]
    #: Slugs der beiden Kandidaturen einer Stichwahl — leer ohne Stichwahl-Satz.
    runoff: tuple[str, ...]
    fetched_at: str | None
    ok: bool
    error: str | None
    notes: tuple[str, ...] = ()


# ------------------------------------------------------------------ Die neun Kandidaturen (aus wahl-fakten.json)

def slug_of(name: str) -> str:
    """Nachname -> Slug: Umlaute ausgeschrieben, alles klein, nur ``a-z0-9-``.

    „Sebastian Fröhlich" -> „froehlich", „Byanca Küßner" -> „kuessner" — der
    NACHNAME reicht als Schlüssel, die neun Kandidaturen von 2026 tragen
    keinen doppelten (siehe ``tests/test_prediction_mayor.py``)."""
    nachname = name.strip().split()[-1] if " " in name.strip() else name.strip()
    text = nachname.translate(_UMLAUTE).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _party_kurz(vorgeschlagen_von: str) -> str:
    """Aus „BÜNDNIS 90/DIE GRÜNEN (GRÜNE)" wird „GRÜNE"; ein Einzelwahl-
    vorschlag bleibt, wie er dasteht — er ist keine Partei."""
    if "einzelwahlvorschlag" in vorgeschlagen_von.lower():
        return "Einzelwahlvorschlag"
    klammer = re.search(r"\(([^)]+)\)\s*$", vorgeschlagen_von)
    return klammer.group(1) if klammer else vorgeschlagen_von


def candidates() -> tuple[MayorCandidate, ...]:
    """Die neun OB-Kandidaturen aus ``kommunalwahl/wahl-fakten.json`` —
    Stimmen und Anteil noch ``None``, die liefert erst ``fetch``/``probe``."""
    raw = json.loads((KOMMUNALWAHL / "wahl-fakten.json").read_text(encoding="utf-8"))
    out = []
    for k in raw["ob_kandidaten"]:
        out.append(MayorCandidate(
            slug=slug_of(k["name"]), name=k["name"],
            party=_party_kurz(k["vorgeschlagen_von"]), votes=None, share_pct=None,
        ))
    return tuple(out)


# ------------------------------------------------------------------ Parsen der Ergebnisdarstellung

def _percent(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    m = _PERCENT.search(value)
    return float(m.group(0).replace(",", ".")) if m else None


def _totals(component: dict[str, Any]) -> dict[str, int | None]:
    """Wie ``presentation._totals``, aber mit den vier Zeilen der OB-Wahl
    (kein „Stimmzettel" getrennt von „Stimmen") und ``startswith`` statt
    ``in`` — sonst matcht „ungültige Stimmen" versehentlich auf „…gültige
    Stimmen" (s. Modul-Docstring)."""
    out: dict[str, int | None] = {"eligible": None, "voters": None, "invalid_ballots": None, "valid_votes": None}
    info = component.get("info")
    for row in presentation._rows(info.get("tabelle") if isinstance(info, dict) else None):
        label = (crosscheck.label_of(row) or "").lower()
        value = presentation.parse_number(row.get("zahl")) if isinstance(row, dict) else None
        if label.startswith("wahlberechtigte"):
            out["eligible"] = value
        elif label.startswith("wähler"):
            out["voters"] = value
        elif label.startswith("ungültige"):
            out["invalid_ballots"] = value
        elif label.startswith("gültige"):
            out["valid_votes"] = value
    return out


def _row_candidate(row: Any, known: tuple[MayorCandidate, ...]) -> tuple[MayorCandidate | None, str | None]:
    kurz = crosscheck.label_of(row)
    if not kurz:
        return None, None
    nachname = kurz.split(",", 1)[0].strip()
    slug = slug_of(nachname)
    votes = presentation.parse_number(row.get("zahl")) if isinstance(row, dict) else None
    pct = _percent(row.get("prozent")) if isinstance(row, dict) else None
    bekannt = next((c for c in known if c.slug == slug), None)
    if bekannt is None:
        return (MayorCandidate(slug=slug, name=kurz, party="", votes=votes, share_pct=pct),
                f"„{kurz}“ aus der Ergebnisdarstellung passt zu keiner der neun OB-Kandidaturen "
                f"— zählt mit, aber ohne Zuordnung.")
    return MayorCandidate(slug=bekannt.slug, name=bekannt.name, party=bekannt.party,
                          votes=votes, share_pct=pct), None


def _candidate_rows(component: dict[str, Any], known: tuple[MayorCandidate, ...]) -> tuple[tuple[MayorCandidate, ...], tuple[str, ...]]:
    """Immer alle ``known`` in ihrer Reihenfolge (ohne Meldung: ``votes=None``),
    dazu Zeilen der Darstellung, die zu keiner bekannten Kandidatur passen."""
    gefunden: dict[str, MayorCandidate] = {}
    notes: list[str] = []
    for row in presentation._rows(component.get("tabelle")):
        cand, note = _row_candidate(row, known)
        if cand is not None:
            gefunden[cand.slug] = cand
        if note:
            notes.append(note)
    bekannte_slugs = {c.slug for c in known}
    out = [gefunden.get(c.slug, c) for c in known]
    out += [c for slug, c in gefunden.items() if slug not in bekannte_slugs]
    return tuple(out), tuple(notes)


def _runoff(component: dict[str, Any]) -> tuple[str, ...]:
    gk = component.get("gewaehlte_kandidaten")
    items = gk.get("items") if isinstance(gk, dict) else None
    if not isinstance(items, list):
        return ()
    out = []
    for it in items:
        label = it.get("label") if isinstance(it, dict) else None
        if isinstance(label, str) and label.strip():
            out.append(slug_of(label.split(",", 1)[0].strip()))
    return tuple(out)


def parse(payload: Any, known: tuple[MayorCandidate, ...] | None = None) -> MayorResult | None:
    """Ein Ergebnis-JSON der OB-Wahl — ``None`` ohne ``Komponente`` (vor der
    Auszählung liegt dort nur ein Zeitstempel, wie bei der Ratswahl)."""
    component = presentation._component(payload)
    if component is None:
        return None
    known = known if known is not None else candidates()
    expected, received = presentation._reports(component)
    totals = _totals(component)
    cands, notes = _candidate_rows(component, known)
    phase = "before" if received == 0 else ("complete" if received >= expected and expected > 0 else "counting")
    turnout = None
    if totals["voters"] is not None and totals["eligible"]:
        turnout = round(100 * totals["voters"] / totals["eligible"], 2)
    return MayorResult(
        phase=phase, reports_expected=expected, reports_received=received,
        turnout_pct=turnout, valid_votes=totals["valid_votes"], invalid_ballots=totals["invalid_ballots"],
        candidates=cands, runoff=_runoff(component),
        fetched_at=None, ok=True, error=None, notes=notes,
    )


# ------------------------------------------------------------------ Abruf

def base_url() -> str:
    return os.environ.get("WAHLABEND_VOTEMANAGER_URL",
                          "https://votemanager.kdo.de/20260913/03403000").rstrip("/")


def resolve_ids(session: requests.Session, base: str) -> str:
    """Die Gebiets-Id der Stadt für DIESE Wahl, aus ``termin.json`` gelesen
    (dort stehen Ratswahl und OB-Wahl nebeneinander, an ``wahl.id`` erkennbar).
    Ohne Antwort die Vorgabe."""
    try:
        resp = session.get(base + TERMIN_PATH, timeout=TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        _log.info("Wahlabend/OB: termin.json ohne Antwort (%s: %s) — Vorgabe-Id", type(exc).__name__, exc)
        return DEFAULT_CITY_ID
    for eintrag in payload.get("wahleintraege", []) if isinstance(payload, dict) else []:
        wahl = eintrag.get("wahl") if isinstance(eintrag, dict) else None
        gebiet = eintrag.get("gebiet_link") if isinstance(eintrag, dict) else None
        if isinstance(wahl, dict) and wahl.get("id") == WAHL_ID and isinstance(gebiet, dict) \
                and isinstance(gebiet.get("id"), str):
            return gebiet["id"]
    return DEFAULT_CITY_ID


_lock = threading.Lock()
_cache: tuple[float, MayorResult] | None = None
_good: MayorResult | None = None


def _bare(error: str) -> MayorResult:
    return MayorResult(phase="before", reports_expected=0, reports_received=0, turnout_pct=None,
                       valid_votes=None, invalid_ballots=None, candidates=candidates(), runoff=(),
                       fetched_at=None, ok=False, error=error, notes=())


def fetch(force: bool = False) -> MayorResult:
    """Wie ``votemanager.fetch``: höchstens einmal je Minute vom Server,
    der letzte gute Stand bleibt stehen, wenn der Abruf scheitert. Wirft nie."""
    global _cache, _good
    with _lock:
        now = time.monotonic()
        if _cache and not force and now - _cache[0] < ttl_seconds():
            return _cache[1]
        known = candidates()
        base = base_url()
        try:
            with requests.Session() as session:
                session.headers.update({"User-Agent": UA})
                city_id = resolve_ids(session, base)
                resp = session.get(f"{base}{API_PATH}/ergebnis_{city_id}_0.json", timeout=TIMEOUT)
                resp.raise_for_status()
                result = parse(resp.json(), known)
        except (requests.RequestException, ValueError) as exc:
            fehler = f"{type(exc).__name__}: {exc}"[:200]
            _log.warning("Wahlabend/OB: Abruf fehlgeschlagen — %s", fehler)
            result = None
        jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if result is None:
            out = _good if _good is not None else _bare("Der Abruf der OB-Wahl klemmt gerade "
                                                         "(keine Daten seit dem Start).")
            if _good is not None:
                out = MayorResult(**{**out.__dict__, "ok": False,
                                     "error": "Der Abruf klemmt — angezeigt wird der letzte gelungene Stand."})
        else:
            out = MayorResult(**{**result.__dict__, "fetched_at": jetzt})
            _good = out
        _cache = (now, out)
        return out


def probe(counted: int | None) -> MayorResult:
    """Generalprobe: die 2021er OB-Wahl (Fixture ``ob-2021.json``) auf die
    Namen von 2026 gelegt, Stimmen im Verhältnis ``counted``/133 skaliert —
    dasselbe Prinzip wie ``election.service.probe`` für die Ratswahl."""
    from pathlib import Path

    fixture = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "wahlabend" / "ob-2021.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    known = candidates()
    voll = parse(payload, known)
    if voll is None or counted is None or counted >= 133:
        return voll or _bare("Die Generalprobe der OB-Wahl trägt keine Zahlen.")
    anteil = max(0.0, min(1.0, counted / 133))
    skaliert = tuple(
        MayorCandidate(c.slug, c.name, c.party,
                       votes=round(c.votes * anteil) if c.votes is not None else None,
                       share_pct=c.share_pct)
        for c in voll.candidates
    )
    phase = "before" if counted == 0 else ("complete" if counted >= 133 else "counting")
    return MayorResult(
        phase=phase, reports_expected=voll.reports_expected,
        reports_received=round(voll.reports_expected * anteil),
        turnout_pct=voll.turnout_pct,
        valid_votes=round(voll.valid_votes * anteil) if voll.valid_votes is not None else None,
        invalid_ballots=round(voll.invalid_ballots * anteil) if voll.invalid_ballots is not None else None,
        candidates=skaliert, runoff=() if phase != "complete" else voll.runoff,
        fetched_at=None, ok=True, error=None, notes=(),
    )


def reset() -> None:
    """Cache und letzten guten Stand vergessen (für Tests)."""
    global _cache, _good
    with _lock:
        _cache = None
        _good = None
