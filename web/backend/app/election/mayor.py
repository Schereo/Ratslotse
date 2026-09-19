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
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

import requests

from . import crosscheck, elections, mayor_districts, presentation
from .register import KOMMUNALWAHL
from .votemanager import TIMEOUT, UA, ttl_seconds


def wahl() -> elections.Election:
    """Die OB-Wahl, die zur aktiven Ratswahl gehört.

    Wahl-Id (2026: 2552), Gebiets-Id und Basis-URL standen bis 09/2026 als
    Konstanten hier. Sie gehören zur Wahl, nicht zum Modul: Die Stichwahl am
    27.09.2026 trägt eine andere Id unter einem anderen Termin.
    """
    ob = elections.mayor_of()
    if ob is None:
        raise LookupError(f"Zu „{elections.active().slug}“ ist keine OB-Wahl eingetragen "
                          "(Feld „mayor“ in kommunalwahl/wahlen/).")
    return ob
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
    #: Die Farbe der vorschlagenden Liste aus dem Register — leer, wenn die
    #: Kandidatur zu keiner gehört (Einzelwahlvorschlag). Eine Stichwahl
    #: zwischen SPD und GRÜNEN in zweimal Grau wäre schlechter lesbar als
    #: nötig, und die Farben stehen ohnehin schon im Repo.
    color: str = ""
    color_dark: str = ""
    #: Der volle amtliche Name des Wahlvorschlags aus der Bekanntmachung.
    nominated_by: str = ""
    #: Parteilos, und von wem sie sonst noch unterstützt wird — beides steht
    #: NICHT in der Bekanntmachung, deshalb nur mit eigenen Quellen
    #: (`note_sources`). Ohne Beleg bleibt das Feld leer: In einem
    #: Wahlprodukt ist eine unbelegte Zuschreibung schlimmer als keine.
    independent: bool = False
    supported_by: tuple[str, ...] = ()
    #: MEHRERE Belege, seit eine zweite Unterstützung dazukam (Volt für Rohr,
    #: 15.09.2026): Eine Quelle deckt nicht, was eine andere Gruppe erklärt
    #: hat. Die Datei darf weiter einen einzelnen String tragen.
    note_sources: tuple[str, ...] = ()


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
    #: Die Wahlbezirke mit ihrem Stand — aus der Übersicht der Bezirks-Ebene,
    #: ein Abruf je Minute (``mayor_districts``). Leer, wenn die Ebene nicht
    #: erreichbar ist; die Stadtzeile trägt den Abend auch allein.
    districts: tuple[mayor_districts.MayorDistrict, ...] = ()
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


def _farben(vorgeschlagen_von: str) -> tuple[str, str]:
    """Die Farben der vorschlagenden Liste — über den amtlichen Namen, der in
    ``wahl-fakten.json`` und ``kandidaten.json`` derselbe ist."""
    from .register import load as load_register

    try:
        for partei in load_register().parties:
            if partei.official == vorgeschlagen_von:
                return partei.color, partei.color_dark
    except Exception:  # eine Farbe darf den Abend nicht umbringen
        _log.exception("Wahlabend/OB: Parteifarben nicht lesbar")
    return "", ""


def _quellen(k: dict) -> tuple[str, ...]:
    """Die Belege einer Kandidatur — ``hinweis_quelle`` als einzelner String
    ODER als Liste. Beides, weil die Datei bis 09/2026 nur eine Quelle je
    Kandidatur kannte und eine Migration hier nichts verbessern würde."""
    roh = k.get("hinweis_quelle")
    if isinstance(roh, str):
        return (roh,) if roh else ()
    return tuple(q for q in (roh or ()) if q)


def candidates(w: elections.Election | None = None) -> tuple[MayorCandidate, ...]:
    """Die Kandidaturen aus der Datei, die die Wahl nennt (2026:
    ``kommunalwahl/wahl-fakten.json``, Schlüssel ``ob_kandidaten``) — Stimmen
    und Anteil noch ``None``, die liefert erst ``fetch``/``probe``.

    ``only`` in der Registry grenzt ein — eine Stichwahl führt genau die zwei
    Kandidaturen, die in die zweite Runde gekommen sind. Ein Slug, den die
    Datei nicht kennt, ist ein Fehler und kein stilles Weglassen: Eine
    Stichwahl mit einer statt zwei Personen wäre keine."""
    datei, schluessel, nur = (w or wahl()).candidates or (KOMMUNALWAHL / "wahl-fakten.json", "ob_kandidaten", ())
    raw = json.loads(datei.read_text(encoding="utf-8"))
    out = []
    for k in raw[schluessel]:
        slug = slug_of(k["name"])
        if nur and slug not in nur:
            continue  # Stichwahl: nur die beiden, die noch antreten
        farbe, farbe_dunkel = _farben(k["vorgeschlagen_von"])
        out.append(MayorCandidate(
            slug=slug, name=k["name"],
            party=_party_kurz(k["vorgeschlagen_von"]), votes=None, share_pct=None,
            color=farbe, color_dark=farbe_dunkel,
            nominated_by=k["vorgeschlagen_von"],
            # Ohne Beleg keine Aussage: Parteilosigkeit und fremde
            # Unterstützung stehen nicht in der amtlichen Bekanntmachung, und
            # eine unbelegte Zuschreibung ist in einem Wahlprodukt das
            # Gegenteil von Präzision.
            independent=bool(k.get("parteilos")) and bool(_quellen(k)),
            supported_by=tuple(k.get("unterstuetzt_von") or ()) if _quellen(k) else (),
            note_sources=_quellen(k),
        ))
    if nur and len(out) != len(nur):
        fehlend = sorted(set(nur) - {c.slug for c in out})
        raise LookupError(f"{(w or wahl()).slug}: „only“ nennt Kandidaturen, die es in "
                          f"{datei.name} nicht gibt: {', '.join(fehlend)}")
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
    # Aus dem Register kommen Name, Partei UND Farbe; aus der Zeile nur die
    # Zahlen. `replace` statt eines neuen Objekts: So bleibt ein Feld, das
    # später zum Register dazukommt, von selbst erhalten.
    return replace(bekannt, votes=votes, share_pct=pct), None


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
            out.append(slug_of(_nachname(label)))
    return tuple(out)


def _nachname(label: str) -> str:
    """Der Nachname aus einem Label der Ergebnisdarstellung.

    Sie schreibt die Namen in ZWEI Formen, und das ist kein Detail:

        2021:  „Krogmann, Jürgen (SPD)"   → Nachname zuerst, Komma
        2026:  „Ulf Prange (SPD)"          → Vorname zuerst, kein Komma

    Bis 09/2026 wurde nur bis zum ersten Komma geschnitten. Bei der Form von
    2021 kam damit „Krogmann" heraus, bei der von 2026 der ganze String — und
    ``slug_of`` nimmt daraus das letzte Wort: „(SPD)". Auf Prod stand deshalb
    am 14.09.2026 ``runoff: ["spd", "gruene"]`` statt ``["prange", "rohr"]``:
    zwei Parteien als Kandidaturen ausgegeben, ohne Fehler und ohne Meldung.
    Deshalb zuerst die Klammer weg, dann erst die beiden Formen.
    """
    ohne_partei = re.sub(r"\s*\([^)]*\)\s*$", "", label).strip()
    return ohne_partei.split(",", 1)[0].strip() if "," in ohne_partei else ohne_partei


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

def base_url(w: elections.Election | None = None) -> str:
    return os.environ.get("WAHLABEND_VOTEMANAGER_URL", (w or wahl()).source.base).rstrip("/")


#: Wie lange eine gefundene Wahl-Id gilt. Vor der Stichwahl ist sie noch nicht
#: vergeben; jede Minute einmal nachsehen reicht, um sie am Wahltag zu haben.
ID_TTL = 300.0
_ids: dict[str, tuple[float, int | None, str]] = {}


def resolve_ids(session: requests.Session, base: str,
                w: elections.Election | None = None) -> tuple[int | None, str]:
    """Wahl-Id und Gebiets-Id der Stadt für DIESE Wahl, aus ``termin.json``.

    Dort stehen alle Wahlen eines Termins nebeneinander. Bis 09/2026 war die
    Wahl-Id eine Konstante und nur die Gebiets-Id wurde gelesen — das trägt
    für die **Stichwahl** nicht: Ihre Id existiert erst, wenn die Stadt sie
    anlegt (gemessen 14.09.2026: ``termin.json`` kennt nur 913 und 2552).
    Steht in der Registry ``discover``, wird der Eintrag deshalb am **Titel**
    gesucht, nicht an einer Id, die niemand raten kann.

    Zwei Dinge, die aus den Terminlisten der Stadt gemessen sind
    (``03403000/api/termine.json``, Stichwahlen 2006 und 2021): Eine Stichwahl
    bekommt **keinen eigenen Termin**, sie erscheint unter dem der Hauptwahl —
    die Basis-URL steht also fest. Und ihr Titel trägt das Wort „Stichwahl".

    Ohne Antwort die Vorgabe aus der Registry; wirft nie.
    """
    w = w or wahl()
    quelle = w.source
    jetzt = time.monotonic()
    merker = _ids.get(w.slug)
    if merker and jetzt - merker[0] < ID_TTL:
        return merker[1], merker[2]

    gefunden: tuple[int | None, str] = (quelle.presentation_id, quelle.city_id or "")
    try:
        resp = session.get(base + TERMIN_PATH, timeout=TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        _log.info("Wahlabend/OB: termin.json ohne Antwort (%s: %s) — Vorgabe-Ids", type(exc).__name__, exc)
        return gefunden

    treffer = _eintrag(payload, quelle)
    if treffer is not None:
        gefunden = treffer
        if quelle.presentation_id is None:
            _log.info("Wahlabend/OB: Wahl-Id für „%s“ gefunden: %s", w.slug, treffer[0])
    elif quelle.presentation_id is None:
        _log.info("Wahlabend/OB: „%s“ steht noch nicht in termin.json — die Seite wartet.", w.slug)
    _ids[w.slug] = (jetzt, gefunden[0], gefunden[1])
    return gefunden


def _eintrag(payload: object, quelle: elections.Source) -> tuple[int | None, str] | None:
    """Der passende Wahleintrag: nach Id, sonst nach Titel (``discover``)."""
    suche = (quelle.discover or {}).get("title_contains", "").casefold()
    for eintrag in payload.get("wahleintraege", []) if isinstance(payload, dict) else []:
        if not isinstance(eintrag, dict):
            continue
        eintrag_wahl = eintrag.get("wahl")
        gebiet = eintrag.get("gebiet_link")
        if not isinstance(eintrag_wahl, dict) or not isinstance(gebiet, dict) \
                or not isinstance(gebiet.get("id"), str):
            continue
        if quelle.presentation_id is not None:
            if eintrag_wahl.get("id") == quelle.presentation_id:
                return quelle.presentation_id, gebiet["id"]
            continue
        titel = eintrag_wahl.get("titel")
        if suche and isinstance(titel, str) and suche in titel.casefold() \
                and isinstance(eintrag_wahl.get("id"), int):
            return eintrag_wahl["id"], gebiet["id"]
    return None


_lock = threading.Lock()
#: Je Wahl ein Zwischenspeicher und ein letzter guter Stand — die Stichwahl
#: darf den ersten Wahlgang nicht aus dem Gedächtnis drängen (das Tippspiel
#: vergleicht weiter gegen ihn).
_cache: dict[str, tuple[float, MayorResult]] = {}
_good: dict[str, MayorResult] = {}


def _bare(error: str, w: elections.Election | None = None) -> MayorResult:
    return MayorResult(phase="before", reports_expected=0, reports_received=0, turnout_pct=None,
                       valid_votes=None, invalid_ballots=None, candidates=candidates(w), runoff=(),
                       fetched_at=None, ok=False, error=error, notes=())


NOCH_NICHT = ("Die Zahlen dieser Wahl stehen beim Votemanager noch nicht bereit — "
              "die Seite versucht es weiter.")


def _fetch_districts(session: requests.Session, base: str, api: str,
                     known: tuple[MayorCandidate, ...]) -> tuple[mayor_districts.MayorDistrict, ...]:
    """Die Bezirks-Übersicht — ein zweiter Abruf im selben Lauf. Scheitert er,
    bleibt es bei der Stadtzeile; ein fehlender Bezirks-Stand darf den Abend
    nicht umbringen, er nimmt nur der Hochrechnung den Boden."""
    try:
        wahl_json = session.get(f"{base}{api}/wahl.json", timeout=TIMEOUT)
        wahl_json.raise_for_status()
        ebene = mayor_districts.level_id(wahl_json.json())
        if ebene is None:
            _log.info("Wahlabend/OB: wahl.json nennt keine Wahlbezirks-Ebene")
            return ()
        resp = session.get(f"{base}{mayor_districts.overview_path(api, ebene)}", timeout=TIMEOUT)
        resp.raise_for_status()
        return mayor_districts.parse_overview(resp.json(), {c.slug: c.name for c in known})
    except (requests.RequestException, ValueError) as exc:
        _log.info("Wahlabend/OB: Bezirks-Übersicht ohne Antwort (%s: %s)", type(exc).__name__, exc)
        return ()


def fetch(force: bool = False, w: elections.Election | None = None) -> MayorResult:
    """Wie ``votemanager.fetch``: höchstens einmal je Minute vom Server,
    der letzte gute Stand bleibt stehen, wenn der Abruf scheitert. Wirft nie.

    Ohne ``w`` die OB-Wahl der aktiven Ratswahl — das ist der ERSTE Wahlgang,
    und daran hängt der Vergleich des Tippspiels. Die Stichwahl wird
    ausdrücklich angefragt."""
    w = w or wahl()
    with _lock:
        now = time.monotonic()
        gemerkt = _cache.get(w.slug)
        if gemerkt and not force and now - gemerkt[0] < ttl_seconds():
            return gemerkt[1]
        known = candidates(w)
        base = base_url(w)
        fehlt = False
        try:
            with requests.Session() as session:
                session.headers.update({"User-Agent": UA})
                wahl_id, city_id = resolve_ids(session, base, w)
                if wahl_id is None:
                    fehlt = True
                    raise ValueError("Wahl-Id noch nicht vergeben")
                api = w.source.api_path(wahl_id)
                resp = session.get(f"{base}{api}/ergebnis_{city_id}_0.json", timeout=TIMEOUT)
                resp.raise_for_status()
                result = parse(resp.json(), known)
                if result is not None:
                    result = replace(result, districts=_fetch_districts(session, base, api, known))
        except (requests.RequestException, ValueError) as exc:
            fehler = f"{type(exc).__name__}: {exc}"[:200]
            _log.log(logging.INFO if fehlt else logging.WARNING,
                     "Wahlabend/OB (%s): Abruf fehlgeschlagen — %s", w.slug, fehler)
            result = None
        jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
        vorher = _good.get(w.slug)
        if result is None:
            out = vorher if vorher is not None else _bare(
                NOCH_NICHT if fehlt else "Der Abruf der OB-Wahl klemmt gerade "
                                         "(keine Daten seit dem Start).", w)
            if vorher is not None:
                out = MayorResult(**{**out.__dict__, "ok": False,
                                     "error": "Der Abruf klemmt — angezeigt wird der letzte gelungene Stand."})
        else:
            out = MayorResult(**{**result.__dict__, "fetched_at": jetzt})
            _good[w.slug] = out
        _cache[w.slug] = (now, out)
        return out


def probe_payload(w: elections.Election | None = None) -> tuple[object, str]:
    """Die Zahlen der Generalprobe und woher sie stammen.

    Für den ersten Wahlgang die OB-Wahl 2021 (Fixture ``ob-2021.json``). Für
    eine **Stichwahl** der erste Wahlgang selbst — eingefroren am 14.09.2026
    in ``kommunalwahl/referenz-2026/praesentation-ob.json`` (PR „Ratswahl 2026
    einfrieren"). Das ist die ehrlichere Probe: dieselbe Stadt, dieselben zwei
    Namen, dieselben 133 Wahlbezirke.
    """
    from pathlib import Path

    wurzel = Path(__file__).resolve().parents[4]
    w = w or wahl()
    if w.first_round:
        datei = wurzel / "kommunalwahl" / "referenz-2026" / "praesentation-ob.json"
        if datei.is_file():
            return json.loads(datei.read_text(encoding="utf-8")), "erster Wahlgang"
    datei = wurzel / "tests" / "fixtures" / "wahlabend" / "ob-2021.json"
    return json.loads(datei.read_text(encoding="utf-8")), "OB-Wahl 2021"


def _nur_die_beiden(voll: MayorResult, known: tuple[MayorCandidate, ...]) -> MayorResult:
    """Die Probe einer Stichwahl aus den Zahlen des ersten Wahlgangs.

    ``parse`` hängt bewusst jede Zeile an, die zu keiner bekannten Kandidatur
    passt — live ist das der Alarm „da steht jemand, den wir nicht kennen".
    Bei DIESER Probe sind es die sieben, die ausgeschieden sind: kein Alarm,
    sondern Vorgeschichte. Die Anteile werden auf die beiden verbliebenen
    umgerechnet, damit die Probe aussieht wie eine Stichwahl und nicht wie ein
    erster Wahlgang mit sieben leeren Zeilen.

    Es ist eine Probe, keine Vorhersage: Dass die Ausgeschiedenen ihre Stimmen
    im selben Verhältnis weiterreichen, behauptet niemand.
    """
    erlaubt = {c.slug for c in known}
    behalten = [c for c in voll.candidates if c.slug in erlaubt]
    summe = sum(c.votes or 0 for c in behalten)
    neu = tuple(
        replace(c, share_pct=round(100 * (c.votes or 0) / summe, 2) if summe else None)
        for c in behalten
    )
    # Auch die Hinweise gehören weg: ``parse`` meldet jede Zeile, die zu keiner
    # bekannten Kandidatur passt („Boldt, Die Linke … zählt mit, aber ohne
    # Zuordnung"). Live ist das der Alarm; hier wären es sieben Zeilen über
    # Menschen, die gar nicht mehr antreten — genau das Rauschen, das eine
    # Probe unlesbar macht.
    return MayorResult(**{**voll.__dict__, "candidates": neu, "valid_votes": summe or None,
                          "runoff": (), "notes": ()})


def probe_districts(counted: int | None, known: tuple[MayorCandidate, ...],
                    w: elections.Election | None = None) -> tuple[mayor_districts.MayorDistrict, ...]:
    """Die Bezirke der Generalprobe: der erste Wahlgang je Bezirk, eingefroren
    in ``referenz-2026/praesentation-ob-wahlbezirke.json`` — die ersten
    ``counted`` in Dateireihenfolge gelten als gemeldet, der Rest wartet.
    Nur für eine Stichwahl; der erste Wahlgang probt gegen 2021 ohne Bezirke."""
    from pathlib import Path

    w = w or wahl()
    if not w.first_round:
        return ()
    datei = Path(__file__).resolve().parents[4] / "kommunalwahl" / "referenz-2026" / "praesentation-ob-wahlbezirke.json"
    if not datei.is_file():
        return ()
    alle = mayor_districts.parse_overview(json.loads(datei.read_text(encoding="utf-8")),
                                          {c.slug: c.name for c in known})
    n = len(alle) if counted is None else max(0, min(len(alle), counted))
    out = []
    for i, d in enumerate(alle):
        if i < n:
            out.append(d)
        else:
            out.append(replace(d, counted=False, valid_votes=None, voters=None,
                               votes={slug: None for slug in d.votes}))
    return tuple(out)


def probe(counted: int | None, w: elections.Election | None = None) -> MayorResult:
    """Generalprobe: echte Zahlen im Register DIESER Wahl, im Verhältnis
    ``counted``/133 ausgezählt — dasselbe Prinzip wie
    ``election.service.probe`` für die Ratswahl."""
    w = w or wahl()
    payload, _herkunft = probe_payload(w)
    known = candidates(w)
    voll = parse(payload, known)
    if voll is not None and w.first_round:
        voll = _nur_die_beiden(voll, known)
    if voll is None or counted is None or counted >= 133:
        if voll is None:
            return _bare("Die Generalprobe der OB-Wahl trägt keine Zahlen.", w)
        return replace(voll, districts=probe_districts(None, known, w))
    anteil = max(0.0, min(1.0, counted / 133))
    bezirke = probe_districts(counted, known, w)
    phase = "before" if counted == 0 else ("complete" if counted >= 133 else "counting")
    if bezirke:
        # Die Stichwahl-Probe zählt Bezirk für Bezirk: Die Stadtzeile ist die
        # Summe der gemeldeten Bezirke, wie live — nicht ein Anteil der
        # Gesamtzahl. Erst so bewegt sich der Anteil über den Abend (die
        # Urne meldet zuerst, die Briefwahl liegt anders), und erst so passt
        # die Zeile zu den Bezirken, aus denen die Hochrechnung rechnet.
        gemeldet = [d for d in bezirke if d.counted]
        stimmen = {c.slug: sum(d.votes.get(c.slug) or 0 for d in gemeldet) for c in voll.candidates}
        summe = sum(stimmen.values())
        skaliert = tuple(
            replace(c, votes=stimmen[c.slug], share_pct=round(100 * stimmen[c.slug] / summe, 2) if summe else None)
            for c in voll.candidates
        )
        return MayorResult(
            phase=phase, reports_expected=len(bezirke), reports_received=len(gemeldet),
            # Vor dem ersten gemeldeten Bezirk gibt es KEINE Beteiligung. Bis
            # 19.09.2026 trug die Probe hier die des Vorwahlgangs, und die
            # Seite schrieb „Noch nichts ausgezählt · 63,5 %" — ein Wert, den
            # es am echten Abend um 18:00 Uhr nicht gibt.
            turnout_pct=voll.turnout_pct if phase != "before" else None,
            valid_votes=summe or None,
            invalid_ballots=round(voll.invalid_ballots * anteil) if voll.invalid_ballots is not None else None,
            candidates=skaliert, runoff=() if phase != "complete" else voll.runoff,
            fetched_at=None, ok=True, error=None, notes=(), districts=bezirke,
        )
    skaliert = tuple(
        replace(c, votes=round(c.votes * anteil) if c.votes is not None else None)
        for c in voll.candidates
    )
    return MayorResult(
        phase=phase, reports_expected=voll.reports_expected,
        reports_received=round(voll.reports_expected * anteil),
        turnout_pct=voll.turnout_pct if phase != "before" else None,
        valid_votes=round(voll.valid_votes * anteil) if voll.valid_votes is not None else None,
        invalid_ballots=round(voll.invalid_ballots * anteil) if voll.invalid_ballots is not None else None,
        candidates=skaliert, runoff=() if phase != "complete" else voll.runoff,
        fetched_at=None, ok=True, error=None, notes=(),
        districts=bezirke,
    )


def reset() -> None:
    """Cache, gefundene Ids und letzten guten Stand vergessen (für Tests)."""
    with _lock:
        _cache.clear()
        _good.clear()
        _ids.clear()
