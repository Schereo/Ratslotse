"""Das Tippspiel als Antworten: Spiel-Setup, Tafel, „meins" (docs/plan-tippspiel-ratswahl.md).

**Die Trennlinie, die den ganzen Abend hält.** Die Ratswahl (``election.service``)
und die OB-Wahl (``election.mayor``) werden hier NUR für Menschentext gelesen
— den Auszählungsstand im Kopf des Beamers, die Phase der OB-Wahl, und um zu
erkennen, dass die erste Hochrechnung da ist (Tipp-Schluss, automatisch).

**Was tatsächlich verglichen wird, kommt AUSSCHLIESSLICH aus
``prediction_result``** — Zeilen, die der Admin im Panel (1h) veröffentlicht
hat. Das ist Absicht: Ein Tippfehler beim Eintragen oder ein Aussetzer beim
automatischen Abruf soll nie unbeaufsichtigt auf dem Beamer landen. „Jetzt
abfragen" holt die Live-Zahlen NUR in den Entwurf; erst „Veröffentlichen"
macht sie hier sichtbar.

**Der Abend darf an nichts sterben** — dieselbe Regel wie in
``election/service.py``: Scheitert der Blick auf die Ratswahl oder die
OB-Wahl (Netzfehler, kaputte Antwort), bleiben die informativen Felder leer
oder auf ihrem letzten Stand; die Tafel selbst antwortet immer.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from statistics import mean

from kern.store import Store

from ..antworten import (
    ElectionNight,
    PredictionCompareLine,
    PredictionGame,
    PredictionMayorCandidate,
    PredictionMayorLine,
    PredictionMine,
    PredictionParty,
    PredictionRow,
    PredictionScore,
    PredictionSeatLine,
    PredictionStand,
)
from ..election import mayor, register
from ..election import service as election_service
from . import scoring

_log = logging.getLogger("ratslotse.web.tippspiel")

#: So lange gilt eine fertige Tafel — 30 Handys und ein Beamer sollen den
#: Abend nicht 30-mal neu rechnen (Muster: ``votemanager.TTL_SECONDS``).
STAND_TTL = 20.0

_lock = threading.Lock()
_cache: tuple[float, PredictionStand] | None = None


# ------------------------------------------------------------------ Bausteine

def _reg():
    return register.load()


def _has_any_result(night: ElectionNight) -> bool:
    """Zeigt die Ratswahl schon IRGENDEINE Zahl — Sitz oder Hochrechnung?"""
    return any((p["seats"] or p["projected_seats"]) for p in night["parties"])


def _check_auto_lock(store: Store) -> None:
    """Setzt den Tipp-Schluss, sobald die erste Hochrechnung der ECHTEN
    Ratswahl da ist — NIE aus der Generalprobe (der Aufrufer ruft das nur im
    Live-Pfad auf, s. ``stand``/``mine``)."""
    game = store.prediction_game()
    if game["phase"] != "open":
        return
    try:
        night = election_service.live()
    except Exception:
        _log.exception("Tippspiel: Blick auf die Ratswahl für den Auto-Lock fehlgeschlagen.")
        return
    if not _has_any_result(night):
        return
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    store.prediction_game_set(phase="locked", locked_at=now, locked_reason="projection")
    store.prediction_log_add(f"Erste Hochrechnung erkannt · Tipp-Schluss automatisch gesetzt ({now})")


def _deadline_hint(game: dict) -> str:
    if game["phase"] == "open":
        return "bis zur ersten Hochrechnung (ca. 20 Uhr)"
    if game["locked_at"]:
        uhrzeit = game["locked_at"][11:16] if len(game["locked_at"]) >= 16 else game["locked_at"]
        return f"Tipp-Schluss war um {uhrzeit} Uhr."
    return "Die Tippabgabe ist geschlossen."


def _parsed(rows: list[dict]) -> list[dict]:
    """Jede Store-Zeile (Spieler*in + LEFT JOIN Tipp) zu einem handlichen
    dict mit geparsten Tipps."""
    out = []
    for r in rows:
        seats = json.loads(r["seats_json"]) if r.get("seats_json") else None
        mayor_tip = json.loads(r["mayor_json"]) if r.get("mayor_json") else None
        out.append({
            "id": r["id"], "name": r["name"], "late_at": r["late_at"], "hidden_at": r.get("hidden_at"),
            "seats": seats, "mayor": mayor_tip,
            "updated_at": r.get("tip_updated_at") or r["created_at"],
        })
    return out


def _avg(tips: list[dict], key: str, slug: str) -> float | None:
    """Ø-Tipp einer Liste/Kandidatur — NUR aus rechtzeitig abgegebenen
    Tipps (``late_at is None``), wie im Plan festgelegt."""
    werte = [t[key][slug] for t in tips
            if t[key] and slug in t[key] and t[key][slug] is not None and t["late_at"] is None]
    return round(mean(werte), 2) if werte else None


def _actual_from_results(results: dict[str, dict]) -> tuple[dict[str, int | None], dict[str, float | None]]:
    seats: dict[str, int | None] = {}
    mayor_actual: dict[str, float | None] = {}
    for slug, r in results.items():
        if slug.startswith("ob:"):
            mayor_actual[slug[3:]] = r["published_pct"]
        else:
            seats[slug] = r["published_seats"]
    return seats, mayor_actual


def _source_label(results: dict[str, dict]) -> str:
    quellen = {r["published_source"] for r in results.values() if r.get("published_at")}
    if not quellen:
        return ""
    if len(quellen) > 1:
        return "gemischt"
    return next(iter(quellen)) or "manuell"


def _compare_sentence(compare: list[PredictionCompareLine]) -> str:
    # (short, Ø-Tipp, Ist) — als eigenes Tupel MIT definitiven float-Typen,
    # statt später wieder ins TypedDict zu greifen: Das behält seinen
    # deklarierten ``float | None``/``int | None``, auch nach einem Filter.
    kandidaten: list[tuple[str, float, float]] = [
        (c["short"], c["avg_tip"], float(c["actual"]))
        for c in compare if c["avg_tip"] is not None and c["actual"] is not None
    ]
    if not kandidaten:
        return "Sobald die ersten Sitze feststehen, zeigen wir hier, wie gut die Runde getippt hat."
    short, avg, actual = max(kandidaten, key=lambda k: abs(k[1] - k[2]))
    diff = round(avg - actual)
    if diff == 0:
        return f"Die Runde hat {short} im Schnitt genau richtig getippt."
    richtung = "zu stark" if diff > 0 else "zu schwach"
    einheit = "Sitz" if abs(diff) == 1 else "Sitze"
    return f"Die Runde hat {short} im Schnitt um {abs(diff)} {einheit} {richtung} getippt."


def _score_dict(s: scoring.Score) -> PredictionScore:
    return PredictionScore(total=s.total, seat_points=s.seat_points, mayor_points=s.mayor_points,
                           exact_lists=s.exact_lists, deviation=s.deviation)


def _mayor_status(counted: int | None) -> tuple[str, int, int]:
    try:
        m = mayor.probe(counted) if counted is not None else mayor.fetch()
    except Exception:
        _log.exception("Tippspiel: Blick auf die OB-Wahl fehlgeschlagen.")
        return "before", 0, 0
    return m.phase, m.reports_received, m.reports_expected


def _area_label(night: ElectionNight) -> str:
    gesamt = night["progress"]["districts_total"]
    gezaehlt = night["progress"]["districts_counted"]
    bereiche = night["areas"]
    voll = sum(1 for a in bereiche if a["districts_counted"] >= a["districts_total"] and a["districts_total"] > 0)
    if bereiche:
        return f"{voll}/{len(bereiche)} Wahlbereiche"
    return f"{gezaehlt}/{gesamt} Wahlbezirke"


# ------------------------------------------------------------------ Öffentliche Formen

def setup(store: Store) -> PredictionGame:
    game = store.prediction_game()
    reg = _reg()
    parties = [PredictionParty(slug=p.slug, short=p.short, name=p.official, color=p.color,
                               color_dark=p.color_dark, seats_2021=None) for p in reg.parties]
    try:
        ref_2021 = {p["slug"]: p.get("seats_2021") for p in election_service.live()["parties"]}
        for pp in parties:
            pp["seats_2021"] = ref_2021.get(pp["slug"])
    except Exception:
        _log.exception("Tippspiel: 2021er Sitze für die Startverteilung nicht zu lesen.")
    mayors = [PredictionMayorCandidate(slug=c.slug, name=c.name, party=c.party) for c in mayor.candidates()]
    return PredictionGame(
        title=game["title"], phase=game["phase"], seats_total=reg.seats,
        locked=game["phase"] != "open", locked_at=game["locked_at"],
        late_scored=bool(game["late_scored"]), player_count=len(store.prediction_players()),
        deadline_hint=_deadline_hint(game), parties=parties, mayor_candidates=mayors,
    )


def _build_stand(store: Store, *, probe: str | None, counted: int | None) -> PredictionStand:
    if probe is None:
        _check_auto_lock(store)
    game = store.prediction_game()
    reg = _reg()
    results = {r["slug"]: r for r in store.prediction_result()}
    published = any(r.get("published_at") for r in results.values())
    actual_seats, actual_mayor = _actual_from_results(results)

    tips = _parsed(store.prediction_players(include_hidden=False))
    sichtbare_mit_tipp = [t for t in tips if t["seats"] is not None]
    ohne_tipp = [t for t in tips if t["seats"] is None]

    compare: list[PredictionCompareLine] = []
    for p in reg.parties:
        avg = _avg(sichtbare_mit_tipp, "seats", p.slug)
        actual = actual_seats.get(p.slug)
        exakt = sum(1 for t in sichtbare_mit_tipp
                   if t["seats"].get(p.slug) is not None and actual is not None and t["seats"][p.slug] == actual)
        compare.append(PredictionCompareLine(slug=p.slug, short=p.short, color=p.color, color_dark=p.color_dark,
                                             actual=actual, avg_tip=avg, exact_count=exakt))

    mayor_lines: list[PredictionMayorLine] = []
    for c in mayor.candidates():
        avg = _avg(sichtbare_mit_tipp, "mayor", c.slug)
        mayor_lines.append(PredictionMayorLine(slug=c.slug, tip=avg or 0.0, actual_pct=actual_mayor.get(c.slug),
                                              avg_tip=avg, points=0))

    mayor_phase, mayor_received, mayor_expected = _mayor_status(counted if probe == "2021" else None)

    rows: list[PredictionRow] = []
    leader: int | None = None
    computed_at = max((r["published_at"] for r in results.values() if r.get("published_at")), default=None)

    if not published:
        alle = sorted(tips, key=lambda t: t["name"].casefold())
        rows = [PredictionRow(player_id=t["id"], name=t["name"], late_at=t["late_at"],
                              scored=t["late_at"] is None or bool(game["late_scored"]),
                              has_tip=t["seats"] is not None, score=None, rank=None, rank_before=None)
               for t in alle]
    else:
        standings = [
            scoring.Standing(id=t["id"], name=t["name"], updated_at=t["updated_at"],
                             scored=t["late_at"] is None or bool(game["late_scored"]),
                             score=scoring.score(t["seats"], t["mayor"], actual_seats, actual_mayor))
            for t in sichtbare_mit_tipp
        ]
        geordnet = scoring.order(standings)
        rang = {s.id: i for i, s in enumerate(geordnet, start=1)}
        vorher = store.prediction_standings_previous(computed_at) if computed_at else {}
        by_id = {t["id"]: t for t in sichtbare_mit_tipp}
        for s in geordnet:
            t = by_id[s.id]
            rows.append(PredictionRow(player_id=t["id"], name=t["name"], late_at=t["late_at"],
                                      scored=s.scored, has_tip=True, score=_score_dict(s.score),
                                      rank=rang[s.id], rank_before=vorher.get(s.id)))
        fuer_ohne = sorted(ohne_tipp, key=lambda t: t["name"].casefold())
        rows += [PredictionRow(player_id=t["id"], name=t["name"], late_at=t["late_at"], scored=False,
                              has_tip=False, score=None, rank=None, rank_before=None) for t in fuer_ohne]
        if geordnet:
            leader = geordnet[0].id
        if computed_at:
            store.prediction_standings_record(computed_at, [(pid, rang[pid], 0) for pid in rang])

    try:
        night = election_service.probe(counted) if probe == "2021" else election_service.live()
        area_label = _area_label(night)
        notes = list(night.get("notes", []))
    except Exception:
        _log.exception("Tippspiel: Auszählungsstand der Ratswahl nicht zu lesen.")
        area_label = ""
        notes = ["Der Auszählungsstand der Ratswahl ist gerade nicht abrufbar."]

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return PredictionStand(
        title=game["title"], phase=game["phase"], stand_label=(computed_at or "")[11:16],
        area_label=area_label, source_label=_source_label(results), seats_total=reg.seats,
        player_count=len(tips), tip_count=len(sichtbare_mit_tipp),
        compare=compare, mayor=mayor_lines, mayor_status=mayor_phase,
        rows=rows, leader_player_id=leader, compare_sentence=_compare_sentence(compare),
        computed_at=computed_at or now, notes=notes,
    )


def stand(store: Store, *, probe: str | None = None, counted: int | None = None) -> PredictionStand:
    """Die öffentliche Tafel (1g/1i) — gecacht, damit ein voller Raum den
    Abend nicht bei jedem Aufruf neu rechnet. Die Generalprobe (``probe``)
    wird NICHT gecacht: Sie ist selten und soll ``counted`` sofort zeigen."""
    if probe is not None:
        return _build_stand(store, probe=probe, counted=counted)
    global _cache
    with _lock:
        cached = _cache
        if cached and time.monotonic() - cached[0] < STAND_TTL:
            return cached[1]
    result = _build_stand(store, probe=None, counted=None)
    with _lock:
        _cache = (time.monotonic(), result)
    return result


def mine(store: Store, token_hash: str, *, probe: str | None = None, counted: int | None = None) -> PredictionMine | None:
    """„Mein Tipp" (1e/1f) — ``None``, wenn der Token zu niemandem gehört
    (der Router macht daraus 401: die Person ist einfach nicht angemeldet)."""
    player = store.prediction_player_by_token(token_hash)
    if player is None:
        return None
    game = store.prediction_game()
    reg = _reg()
    tafel = stand(store, probe=probe, counted=counted)
    results = {r["slug"]: r for r in store.prediction_result()}
    actual_seats, actual_mayor = _actual_from_results(results)

    seats_tip = json.loads(player["seats_json"]) if player.get("seats_json") else None
    mayor_tip = json.loads(player["mayor_json"]) if player.get("mayor_json") else None

    row = next((r for r in tafel["rows"] if r["player_id"] == player["id"]), None)

    avg_tips_seats = {c["slug"]: c["avg_tip"] for c in tafel["compare"]}
    avg_tips_mayor = {c["slug"]: c["avg_tip"] for c in tafel["mayor"]}

    seat_lines: list[PredictionSeatLine] = []
    if seats_tip is not None:
        for p in reg.parties:
            tip = seats_tip.get(p.slug, 0)
            actual = actual_seats.get(p.slug)
            seat_lines.append(PredictionSeatLine(
                slug=p.slug, tip=tip, actual=actual, avg_tip=avg_tips_seats.get(p.slug),
                points=scoring.seat_points(tip, actual), exact=actual is not None and tip == actual,
            ))
    mayor_lines: list[PredictionMayorLine] = []
    if mayor_tip is not None:
        for c in mayor.candidates():
            tip = mayor_tip.get(c.slug, 0.0)
            mayor_lines.append(PredictionMayorLine(
                slug=c.slug, tip=tip, actual_pct=actual_mayor.get(c.slug),
                avg_tip=avg_tips_mayor.get(c.slug), points=scoring.mayor_points(tip, actual_mayor.get(c.slug)),
            ))

    return PredictionMine(
        player_id=player["id"], name=player["name"], late_at=player["late_at"],
        scored=bool(row["scored"]) if row else (player["late_at"] is None or bool(game["late_scored"])),
        has_tip=seats_tip is not None, has_mayor_tip=mayor_tip is not None,
        locked=game["phase"] != "open",
        seats=seat_lines, mayor=mayor_lines,
        score=row["score"] if row else None, rank=row["rank"] if row else None,
        rank_before=row["rank_before"] if row else None,
        phase=game["phase"], stand_label=tafel["stand_label"], source_label=tafel["source_label"],
        notes=tafel["notes"],
    )


def reset() -> None:
    """Den Tafel-Cache verwerfen (für Tests)."""
    global _cache
    with _lock:
        _cache = None
