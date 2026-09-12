"""Das Tippspiel als Antworten: Spiel-Setup, Tafel, „meins" (docs/plan-tippspiel-ratswahl.md).

**Woher der Vergleich kommt** (Plan §3 Zeile 9, §4 Regel 6). Grundlage ist
der **Wahlabend**: ``election.service.live()`` für die Sitze je Liste,
``election.mayor.fetch()`` für die OB-Prozente — in der Generalprobe die
beiden ``probe``-Fassungen. Der Beamer folgt damit dem Votemanager von
selbst, ohne dass am Abend jemand „Jetzt abfragen" und „Veröffentlichen"
klickt. **Darüber liegt je Liste die veröffentlichte Handeingabe** aus dem
Admin (1h): Eine Zeile mit ``published_source = "manuell"`` schlägt den
Wahlabend für genau diese Liste — sie ist die Zusage, der Abruf die
Bequemlichkeit. Eine veröffentlichte Zeile aus „Jetzt abfragen"
(``published_source = "votemanager"``) friert dagegen nichts ein: Sie ist
nur der Rückfall, wenn der Wahlabend für die Liste gerade keine Zahl nennt.

**Warum nicht „nur veröffentlicht"?** So stand es hier bis zum 11.09.2026,
und es hätte den Abend still ausgehebelt: Die Generalprobe
``?probe=2021&counted=N`` hätte nie einen Rang gezeigt (das Abnahmekriterium
von PR 4), und am Abend hätte JEDE Hochrechnung erst durch zwei Admin-Klicks
gemusst. Der Entwurf bleibt trotzdem die Sperre für die HANDEINGABE: Was ein
Mensch eintippt, erscheint erst nach „Veröffentlichen".

**Ein Stand ist ein Ist, nicht ein Abruf.** Die Ränge werden unter einem
Stand-Zeitstempel abgelegt, und ``rank_before`` ist der Rang im letzten
ANDEREN Stand. Der Zeitstempel wechselt deshalb nur, wenn sich die
verglichenen Zahlen ändern (Hash über Ist-Sitze und Ist-Prozente) — sonst
bekäme jeder Abruf nach Ablauf des Caches einen neuen Stand, und die
▲▼-Chips zeigten immer nur den vorigen Abruf. Die Generalprobe schreibt
NICHTS in die Datenbank (kein Auto-Lock, keine Ränge); ihr „vorheriger
Rang" lebt im Prozess, damit die Folge ``counted=0 → 40 → 90 → 133``
trotzdem Rangwechsel zeigt.

**Der Abend darf an nichts sterben** — dieselbe Regel wie in
``election/service.py``: Scheitert der Blick auf die Ratswahl oder die
OB-Wahl (Netzfehler, kaputte Antwort), rechnet die Tafel mit dem, was sie
hat — den veröffentlichten Zeilen — und antwortet immer.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

from kern.store import Store

from ..antworten import (
    ElectionNight,
    ElectionParty,
    PredictionCompareLine,
    PredictionGame,
    PredictionMayorCandidate,
    PredictionMayorCompareLine,
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

BERLIN = ZoneInfo("Europe/Berlin")


@dataclass(frozen=True)
class _Bundle:
    """Tafel plus die Ist-Werte, aus denen sie gerechnet wurde — ``mine()``
    braucht dieselben Zahlen je Zeile, und zwar GENAU dieselben, sonst
    zeigt „Mein Tipp" andere Punkte als die Rangliste."""
    stand: PredictionStand
    actual_seats: dict[str, int | None]
    actual_mayor: dict[str, float | None]


_lock = threading.Lock()
#: Je Runde (``game_id``) eine fertige Tafel: (monotonic, Bündel).
_cache: dict[int, tuple[float, _Bundle]] = {}
#: Stand-Zeitstempel je Pfad UND Runde (``"live:1"``, ``"probe:2"``): (Hash des Ist, stand_at).
_marker: dict[str, tuple[str, str]] = {}
#: Generalprobe je Runde: (Ränge des aktuellen Standes, Ränge des Standes davor).
_probe_ranks: dict[int, tuple[dict[int, int], dict[int, int]]] = {}


# ------------------------------------------------------------------ Bausteine

def _reg():
    return register.load()


def _uhrzeit(iso: str) -> str:
    """„18:07" in Europe/Berlin aus einem ISO-Zeitstempel. Naiv heißt UTC
    (so schreibt der Store), sonst zählt die mitgeführte Zone. Vorher stand
    hier ``iso[11:16]`` — die UTC-Stunde, am Wahlabend zwei Stunden daneben."""
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso[11:16]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BERLIN).strftime("%H:%M")


def night_seats(party: ElectionParty) -> int | None:
    """Die Sitzzahl, die der Wahlabend für eine Liste gerade nennt: die
    Hochrechnung, sobald es eine gibt, sonst der ausgezählte Stand — am Ende
    sind beide gleich. Auch „Jetzt abfragen" im Admin nimmt diese Zeile,
    damit Entwurf und Tafel dieselbe Zahl meinen."""
    if party["projected_seats"] is not None:
        return party["projected_seats"]
    return party["seats"]


def _has_any_result(night: ElectionNight) -> bool:
    """Zeigt die Ratswahl schon IRGENDEINE Zahl — Sitz oder Hochrechnung?"""
    return any((p["seats"] or p["projected_seats"]) for p in night["parties"])


def _read_night(probe: str | None, counted: int | None) -> ElectionNight | None:
    try:
        return election_service.probe(counted) if probe == "2021" else election_service.live()
    except Exception:
        _log.exception("Tippspiel: Auszählungsstand der Ratswahl nicht zu lesen.")
        return None


def _read_mayor(probe: str | None, counted: int | None) -> mayor.MayorResult | None:
    try:
        return mayor.probe(counted) if probe == "2021" else mayor.fetch()
    except Exception:
        _log.exception("Tippspiel: Blick auf die OB-Wahl fehlgeschlagen.")
        return None


def _check_auto_lock(store: Store, game_id: int, night: ElectionNight | None = None) -> None:
    """Setzt den Tipp-Schluss, sobald die erste Hochrechnung der ECHTEN
    Ratswahl da ist — NIE aus der Generalprobe (``_build`` ruft das nur im
    Live-Pfad auf; der Router bei jedem ``POST /api/tipp``, ohne ``night``,
    dann liest die Funktion selbst)."""
    game = store.prediction_game(game_id)
    if game["phase"] != "open":
        return
    if night is None:
        night = _read_night(None, None)
    if night is None or not _has_any_result(night):
        return
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    store.prediction_game_set(game_id, phase="locked", locked_at=now, locked_reason="projection")
    store.prediction_log_add(game_id, f"Erste Hochrechnung erkannt · Tipp-Schluss automatisch gesetzt ({_uhrzeit(now)} Uhr)")


def _deadline_hint(game: dict) -> str:
    if game["phase"] == "open":
        return "bis zur ersten Hochrechnung (ca. 20 Uhr)"
    if game["locked_at"]:
        return f"Die Tippfrist endete um {_uhrzeit(game['locked_at'])} Uhr."
    return "Die Tippfrist ist vorbei."


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


def _actuals(results: dict[str, dict], night: ElectionNight | None,
             ob: mayor.MayorResult | None) -> tuple[dict[str, int | None], dict[str, float | None], str]:
    """Das Ist je Liste und je OB-Kandidatur, plus das ``source_label``.

    Reihenfolge je Schlüssel: veröffentlichte HANDEINGABE > Wahlabend >
    veröffentlichter Votemanager-Schnappschuss (Rückfall). Die OB-Prozente
    zählen erst, wenn dort etwas ausgezählt ist — ``probe(0)`` trägt die
    Endprozente von 2021 bei ``phase == "before"``, und die wären sonst vor
    der ersten Stimme schon Punkte wert."""
    seats: dict[str, int | None] = {}
    pct: dict[str, float | None] = {}
    quellen: set[str] = set()
    if night is not None:
        for p in night["parties"]:
            wert = night_seats(p)
            if wert is not None:
                seats[p["slug"]] = wert
    if ob is not None and ob.phase != "before":
        for c in ob.candidates:
            if c.share_pct is not None:
                pct[c.slug] = c.share_pct
    if seats or pct:
        quellen.add("votemanager")
    for slug, r in results.items():
        if not r.get("published_at"):
            continue
        if slug.startswith("ob:"):
            ziel, key, wert = pct, slug[3:], r["published_pct"]
        else:
            ziel, key, wert = seats, slug, r["published_seats"]
        if wert is None:
            continue
        manuell = (r.get("published_source") or "manuell") == "manuell"
        if manuell or key not in ziel:
            ziel[key] = wert
            quellen.add("manuell" if manuell else "votemanager")
    if not quellen:
        label = ""
    elif len(quellen) > 1:
        label = "gemischt"
    else:
        label = next(iter(quellen))
    return seats, pct, label


def _digest(actual_seats: dict, actual_mayor: dict, late_scored: bool) -> str:
    """Was einen Stand vom nächsten unterscheidet: die verglichenen Zahlen
    (und ob Spätstarter zählen — das ordnet die Liste um)."""
    roh = json.dumps([sorted(actual_seats.items()), sorted(actual_mayor.items()), late_scored])
    return hashlib.sha1(roh.encode()).hexdigest()  # noqa: S324 — kein Sicherheitszweck


def _stand_at(key: str, digest: str) -> tuple[str, bool]:
    """Der Stand-Zeitstempel zu diesem Ist — derselbe, solange sich das Ist
    nicht ändert. Gibt mit, ob es ein NEUER Stand ist. Streng steigend, auch
    wenn zwei Stände in dieselbe Millisekunde fallen (Tests)."""
    alt = _marker.get(key)
    if alt and alt[0] == digest:
        return alt[1], False
    jetzt = datetime.now(timezone.utc)
    if alt:
        vorher = datetime.fromisoformat(alt[1])
        if jetzt <= vorher:
            jetzt = vorher + timedelta(milliseconds=1)
    stamp = jetzt.isoformat(timespec="milliseconds")
    _marker[key] = (digest, stamp)
    return stamp, True


def _compare_sentence(compare: list[PredictionCompareLine]) -> str:
    # (short, Ø-Tipp, Ist) — als eigenes Tupel MIT definitiven float-Typen,
    # statt später wieder ins TypedDict zu greifen: Das behält seinen
    # deklarierten ``float | None``/``int | None``, auch nach einem Filter.
    kandidaten: list[tuple[str, float, float]] = [
        (c["short"], c["avg_tip"], float(c["actual"]))
        for c in compare if c["avg_tip"] is not None and c["actual"] is not None
    ]
    if not kandidaten:
        return "Sobald die erste Hochrechnung da ist, siehst du hier, wie gut die Tipps zum aktuellen Stand passen."
    short, avg, actual = max(kandidaten, key=lambda k: abs(k[1] - k[2]))
    diff = round(avg - actual)
    if diff == 0:
        return f"Bei {short} liegen die Tipps im Durchschnitt nah am aktuellen Stand."
    richtung = "mehr" if diff > 0 else "weniger"
    einheit = "Sitz" if abs(diff) == 1 else "Sitze"
    return f"Für {short} wurden im Durchschnitt rund {abs(diff)} {einheit} {richtung} getippt, als der aktuelle Stand zeigt."


def _score_dict(s: scoring.Score) -> PredictionScore:
    return PredictionScore(total=s.total, seat_points=s.seat_points, mayor_points=s.mayor_points,
                           exact_lists=s.exact_lists, deviation=s.deviation)


def _area_label(night: ElectionNight) -> str:
    gesamt = night["progress"]["districts_total"]
    gezaehlt = night["progress"]["districts_counted"]
    bereiche = night["areas"]
    voll = sum(1 for a in bereiche if a["districts_counted"] >= a["districts_total"] and a["districts_total"] > 0)
    if bereiche:
        return f"{voll}/{len(bereiche)} Wahlbereiche"
    return f"{gezaehlt}/{gesamt} Wahlbezirke"


# ------------------------------------------------------------------ Öffentliche Formen

def setup(store: Store, game_id: int) -> PredictionGame:
    from . import rounds  # hier statt oben: rounds ist rein, service nicht — kein Kreis, nur Ordnung

    game = store.prediction_game(game_id)
    runde = rounds.get(game["slug"])
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
        round=game["slug"], listed=runde.listed if runde else False,
        title=game["title"], phase=game["phase"], seats_total=reg.seats,
        locked=game["phase"] != "open", locked_at=game["locked_at"],
        late_scored=bool(game["late_scored"]), player_count=store.prediction_player_count(game_id),
        deadline_hint=_deadline_hint(game), parties=parties, mayor_candidates=mayors,
    )


def _build(store: Store, game_id: int, *, probe: str | None, counted: int | None) -> _Bundle:
    night = _read_night(probe, counted)
    ob = _read_mayor(probe, counted)
    if probe is None:
        _check_auto_lock(store, game_id, night)
    game = store.prediction_game(game_id)
    reg = _reg()
    results = {r["slug"]: r for r in store.prediction_result(game_id)}
    actual_seats, actual_mayor, source_label = _actuals(results, night, ob)
    vergleichbar = bool(actual_seats or actual_mayor)

    tips = _parsed(store.prediction_players(game_id, include_hidden=False))
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

    mayor_compare: list[PredictionMayorCompareLine] = []
    for c in mayor.candidates():
        mayor_compare.append(PredictionMayorCompareLine(
            slug=c.slug, name=c.name, party=c.party,
            actual_pct=actual_mayor.get(c.slug), avg_tip=_avg(sichtbare_mit_tipp, "mayor", c.slug),
        ))

    rows: list[PredictionRow] = []
    leader: int | None = None
    computed_at: str | None = None

    if not vergleichbar:
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
        pfad = f"{'probe' if probe is not None else 'live'}:{game_id}"
        computed_at, neu = _stand_at(pfad, _digest(actual_seats, actual_mayor, bool(game["late_scored"])))
        if probe is not None:
            # Kein Datenbank-Schreiben in der Generalprobe — der vorige Rang
            # lebt im Prozess und wechselt mit jedem neuen Ist.
            bisher = _probe_ranks.get(game_id, ({}, {}))
            if neu:
                bisher = (rang, bisher[0])
                _probe_ranks[game_id] = bisher
            vorher = bisher[1]
        else:
            vorher = store.prediction_standings_previous(game_id, computed_at)
            store.prediction_standings_record(
                game_id, computed_at, [(s.id, rang[s.id], s.score.total) for s in geordnet])
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

    if night is not None:
        area_label = _area_label(night)
        notes = list(night.get("notes", []))
    else:
        area_label = ""
        notes = ["Der Auszählungsstand der Ratswahl ist gerade nicht abrufbar."]

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    tafel = PredictionStand(
        title=game["title"], phase=game["phase"], stand_label=_uhrzeit(computed_at) if computed_at else "",
        area_label=area_label, source_label=source_label, seats_total=reg.seats,
        player_count=len(tips), tip_count=len(sichtbare_mit_tipp),
        compare=compare, mayor=mayor_compare, mayor_status=ob.phase if ob is not None else "before",
        rows=rows, leader_player_id=leader, compare_sentence=_compare_sentence(compare),
        computed_at=computed_at or now, notes=notes,
    )
    return _Bundle(stand=tafel, actual_seats=actual_seats, actual_mayor=actual_mayor)


def _bundle(store: Store, game_id: int, *, probe: str | None, counted: int | None) -> _Bundle:
    """Tafel samt Ist — je Runde gecacht, damit ein voller Raum den Abend
    nicht bei jedem Aufruf neu rechnet. Die Generalprobe (``probe``) wird
    NICHT gecacht: Sie ist selten und soll ``counted`` sofort zeigen."""
    if probe is not None:
        return _build(store, game_id, probe=probe, counted=counted)
    with _lock:
        cached = _cache.get(game_id)
        if cached and time.monotonic() - cached[0] < STAND_TTL:
            return cached[1]
    result = _build(store, game_id, probe=None, counted=None)
    with _lock:
        _cache[game_id] = (time.monotonic(), result)
    return result


def stand(store: Store, game_id: int, *, probe: str | None = None, counted: int | None = None) -> PredictionStand:
    """Die öffentliche Tafel (1g/1i) einer Runde."""
    return _bundle(store, game_id, probe=probe, counted=counted).stand


def mine(store: Store, game_id: int, token_hash: str, *, probe: str | None = None,
         counted: int | None = None) -> PredictionMine | None:
    """„Mein Tipp" (1e/1f) — ``None``, wenn der Token in dieser Runde zu
    niemandem gehört (der Router macht daraus 401: nicht angemeldet)."""
    player = store.prediction_player_by_token(token_hash, game_id)
    if player is None:
        return None
    game = store.prediction_game(game_id)
    reg = _reg()
    b = _bundle(store, game_id, probe=probe, counted=counted)
    tafel = b.stand

    seats_tip = json.loads(player["seats_json"]) if player.get("seats_json") else None
    mayor_tip = json.loads(player["mayor_json"]) if player.get("mayor_json") else None

    row = next((r for r in tafel["rows"] if r["player_id"] == player["id"]), None)

    avg_tips_seats = {c["slug"]: c["avg_tip"] for c in tafel["compare"]}
    avg_tips_mayor = {c["slug"]: c["avg_tip"] for c in tafel["mayor"]}

    seat_lines: list[PredictionSeatLine] = []
    if seats_tip is not None:
        for p in reg.parties:
            tip = seats_tip.get(p.slug, 0)
            actual = b.actual_seats.get(p.slug)
            seat_lines.append(PredictionSeatLine(
                slug=p.slug, tip=tip, actual=actual, avg_tip=avg_tips_seats.get(p.slug),
                points=scoring.seat_points(tip, actual), exact=actual is not None and tip == actual,
            ))
    mayor_lines: list[PredictionMayorLine] = []
    if mayor_tip is not None:
        for c in mayor.candidates():
            tip = mayor_tip.get(c.slug, 0.0)
            actual_pct = b.actual_mayor.get(c.slug)
            mayor_lines.append(PredictionMayorLine(
                slug=c.slug, tip=tip, actual_pct=actual_pct,
                avg_tip=avg_tips_mayor.get(c.slug), points=scoring.mayor_points(tip, actual_pct),
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
    """Den Tafel-Cache verwerfen (nach jedem Admin-Schreiben und für Tests).
    Die Stand-Marker bleiben: Ein neues Ist bekommt seinen Zeitstempel beim
    nächsten Aufbau von selbst, ein unverändertes behält seinen."""
    with _lock:
        _cache.clear()


def reset_all() -> None:
    """Auch Stand-Marker und Generalproben-Ränge vergessen (für Tests)."""
    with _lock:
        _cache.clear()
        _marker.clear()
        _probe_ranks.clear()
