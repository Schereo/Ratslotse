"""Das Tippspiel als Antworten: Spiel-Setup, Tafel, „meins" (docs/plan-tippspiel-ratswahl.md).

**Woher der Vergleich kommt** (Plan §3 Zeile 9, §4 Regel 6). Grundlage ist
der **Wahlabend der Wahl, auf die die Runde tippt** (``basis()``): Bei einer
Ratswahl ``election.service.live()`` für die Sitze je Liste und
``election.mayor.fetch()`` für die OB-Prozente der zugehörigen OB-Wahl; bei
einer **Mehrheitswahl** (OB-Wahl, Stichwahl) nur ``mayor.fetch(w=…)`` für
genau diese Wahl — in der Generalprobe jeweils die ``probe``-Fassungen. Der
Beamer folgt damit dem Votemanager von selbst, ohne dass am Abend jemand
„Jetzt abfragen" und „Veröffentlichen" klickt. **Darüber liegt je Liste bzw.
Kandidatur die veröffentlichte Handeingabe** aus dem Admin (1h): Eine Zeile
mit ``published_source = "manuell"`` schlägt den Wahlabend für genau diese
Zeile — sie ist die Zusage, der Abruf die Bequemlichkeit. Eine
veröffentlichte Zeile aus „Jetzt abfragen" (``published_source =
"votemanager"``) friert dagegen nichts ein: Sie ist nur der Rückfall, wenn
der Wahlabend gerade keine Zahl nennt.

**Bis 19.09.2026 kannte dieser Baustein nur die Ratswahl.** Eine Runde auf
die Stichwahl ließ sich zwar anlegen (``setup`` sagte „pct"), aber die Tafel
las trotzdem ``mayor.fetch()`` — die OB-Wahl des ERSTEN Wahlgangs, längst
ausgezählt — und hielt einen Prozent-Tipp ohne Sitze für „keinen Tipp"
(``seats is None``). Gemessen vor dem Umbau: ``has_tip False``, neun
Kandidaturen des ersten Wahlgangs in „meins", ``tip_count 0``. Deshalb
entscheidet jetzt ``basis()`` je Runde, was gelesen und was verglichen wird.

**Warum nicht „nur veröffentlicht"?** So stand es hier bis zum 11.09.2026,
und es hätte den Abend still ausgehebelt: Die Generalprobe
``?probe=2021&counted=N`` hätte nie einen Rang gezeigt (das Abnahmekriterium
von PR 4), und am Abend hätte JEDE Hochrechnung erst durch zwei Admin-Klicks
gemusst. Der Entwurf bleibt trotzdem die Sperre für die HANDEINGABE: Was ein
Mensch eintippt, erscheint erst nach „Veröffentlichen".

**Ein Stand ist ein Ist, nicht ein Abruf.** Die Ränge werden unter einem
Stand-Zeitstempel abgelegt, und ``rank_before`` ist der Rang im letzten
ANDEREN Stand. Der Zeitstempel wechselt deshalb nur, wenn sich die
verglichenen Zahlen ändern (Hash über Ist-Sitze, Ist-Prozente und
Ist-Wahlbeteiligung) — sonst bekäme jeder Abruf nach Ablauf des Caches einen
neuen Stand, und die ▲▼-Chips zeigten immer nur den vorigen Abruf. Die
Generalprobe schreibt NICHTS in die Datenbank (kein Auto-Lock, keine Ränge);
ihr „vorheriger Rang" lebt im Prozess, damit die Folge ``counted=0 → 40 → 90
→ 133`` trotzdem Rangwechsel zeigt.

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
    PredictionPartyOption,
    PredictionRow,
    PredictionScore,
    PredictionSeatLine,
    PredictionStand,
    PredictionTurnoutCompare,
    PredictionTurnoutLine,
)
from ..election import elections, mayor, register
from ..election import service as election_service
from . import scoring

_log = logging.getLogger("ratslotse.web.tippspiel")

#: So lange gilt eine fertige Tafel — 30 Handys und ein Beamer sollen den
#: Abend nicht 30-mal neu rechnen (Muster: ``votemanager.TTL_SECONDS``).
STAND_TTL = 20.0

BERLIN = ZoneInfo("Europe/Berlin")

#: Wahllisten, die im Parteien-Menü beim Beitritt NICHT stehen — Tims
#: Entscheidung vom 19.09.2026. Das Menü ist ein Angebot der Seite, kein
#: Abbild des Stimmzettels; wer sich keiner der angebotenen zuordnen will,
#: lässt das Feld frei.
PARTY_MENU_EXCLUDED = frozenset({"afd"})

#: Slug der Wahlbeteiligung in ``prediction_result`` (neben Listen-Slugs und
#: ``ob:<slug>``) — eine Handeingabe des Admins schlägt auch hier den Abruf.
TURNOUT_SLUG = "turnout"


@dataclass(frozen=True)
class Basis:
    """Was eine Runde zum Vergleich braucht — aus IHRER Wahl, nicht aus „dem
    Wahlabend". ``reg`` gibt es nur bei einer Ratswahl (Sitze je Liste);
    ``ob_wahl`` ist die Wahl, gegen die Prozente zählen: bei einer Ratswahl
    die zugehörige OB-Wahl, bei einer Mehrheitswahl sie selbst."""
    wahl: elections.Election
    reg: register.Register | None
    ob_wahl: elections.Election | None

    @property
    def sitzwahl(self) -> bool:
        return self.reg is not None


@dataclass(frozen=True)
class _Bundle:
    """Tafel plus die Ist-Werte, aus denen sie gerechnet wurde — ``mine()``
    braucht dieselben Zahlen je Zeile, und zwar GENAU dieselben, sonst
    zeigt „Mein Tipp" andere Punkte als die Rangliste."""
    stand: PredictionStand
    basis: Basis
    actual_seats: dict[str, int | None]
    actual_mayor: dict[str, float | None]
    actual_turnout: float | None


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


def _mayor_has_result(ob: mayor.MayorResult) -> bool:
    """Nennt die OB-/Stichwahl schon einen Prozentwert? ``phase == "before"``
    trägt in der Generalprobe die Endprozente der Vorwahl mit — die zählen
    nicht, sonst wäre vor der ersten Stimme schon Tipp-Schluss."""
    return ob.phase != "before" and any(c.share_pct is not None for c in ob.candidates)


def wahl_der_runde(game: dict) -> elections.Election:
    """Auf welche Wahl diese Runde tippt.

    Die Spielzeile nennt sie (``election_slug``, seit 14.09.2026). Steht dort
    nichts — eine Runde von vor dem Umbau —, gilt die Wahl aus der
    Runden-Registry, und sonst die aktive Ratswahl. Nie einfach „der
    Wahlabend": Beim nächsten Mal ist das ein anderer, und eine alte Runde
    würde rückwirkend gegen fremde Zahlen gepunktet.
    """
    from . import rounds

    slug = game.get("election_slug")
    wahl = elections.get(slug) if slug else None
    if wahl is None:
        runde = rounds.get(game.get("slug"))
        wahl = elections.get(runde.election) if runde and runde.election else None
    return wahl or elections.active()


def basis(game: dict) -> Basis:
    """Wahl, Register und OB-Wahl einer Runde — an EINER Stelle entschieden.

    Router (Validierung, Admin, „Jetzt abfragen") und Tafel lesen dieselbe
    Grundlage; vorher hatte jede Stelle ihre eigene Vorstellung davon, was
    „die OB-Wahl" ist, und die Tafel lag bei der Stichwahl falsch."""
    wahl = wahl_der_runde(game)
    if wahl.kind == "council":
        return Basis(wahl=wahl, reg=register.load(wahl.register_path), ob_wahl=elections.mayor_of(wahl))
    return Basis(wahl=wahl, reg=None, ob_wahl=wahl)


def _read_night(probe: str | None, counted: int | None) -> ElectionNight | None:
    try:
        return election_service.probe(counted) if probe == "2021" else election_service.live()
    except Exception:
        _log.exception("Tippspiel: Auszählungsstand der Ratswahl nicht zu lesen.")
        return None


def _read_mayor(probe: str | None, counted: int | None, w: elections.Election) -> mayor.MayorResult | None:
    """Der Stand der OB- bzw. Stichwahl ``w`` — ausdrücklich DIESER Wahl.
    ``mayor.fetch()`` ohne ``w`` wäre immer der erste Wahlgang."""
    try:
        return mayor.probe(counted, w) if probe == "2021" else mayor.fetch(w=w)
    except Exception:
        _log.exception("Tippspiel: Blick auf die OB-Wahl %s fehlgeschlagen.", w.slug)
        return None


def _check_auto_lock(store: Store, game_id: int, night: ElectionNight | None = None,
                     ob: mayor.MayorResult | None = None) -> None:
    """Setzt den Tipp-Schluss, sobald die erste Zahl der ECHTEN Wahl dieser
    Runde da ist — NIE aus der Generalprobe (``_build`` ruft das nur im
    Live-Pfad auf; der Router bei jedem ``POST /api/tipp``, ohne ``night``
    und ``ob``, dann liest die Funktion selbst).

    Bei einer Ratswahl ist das die erste Hochrechnung, bei einer OB- oder
    Stichwahl der erste Auszählungsstand mit Prozenten. **Der Wahlabend
    gehört der RUNDE, nicht dem Dienst:** Eine Runde auf eine andere Wahl
    darf nicht zumachen, weil irgendwo anders ausgezählt wird.
    """
    game = store.prediction_game(game_id)
    if game["phase"] != "open":
        return
    b = basis(game)
    if b.sitzwahl:
        if b.wahl.slug != elections.active().slug:
            return
        if night is None:
            night = _read_night(None, None)
        if night is None or not _has_any_result(night):
            return
        anlass = "Erste Hochrechnung erkannt"
    else:
        assert b.ob_wahl is not None
        if ob is None:
            ob = _read_mayor(None, None, b.ob_wahl)
        if ob is None or not _mayor_has_result(ob):
            return
        anlass = "Erster Auszählungsstand erkannt"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    store.prediction_game_set(game_id, phase="locked", locked_at=now, locked_reason="projection")
    store.prediction_log_add(game_id, f"{anlass} · Tipp-Schluss automatisch gesetzt ({_uhrzeit(now)} Uhr)")


def _deadline_hint(game: dict, sitzwahl: bool) -> str:
    if game["phase"] == "open":
        return ("bis zur ersten Hochrechnung (ca. 20 Uhr)" if sitzwahl
                else "bis zum ersten Auszählungsstand (kurz nach 18 Uhr)")
    if game["locked_at"]:
        return f"Die Tippfrist endete um {_uhrzeit(game['locked_at'])} Uhr."
    return "Die Tippfrist ist vorbei."


def _parsed(rows: list[dict]) -> list[dict]:
    """Jede Store-Zeile (Spieler*in + LEFT JOIN Tipp) zu einem handlichen
    dict mit geparsten Tipps. ``tipped`` heißt: Es gibt einen Tipp — Sitze
    (Ratswahl) oder Prozente (Mehrheitswahl); ``seats_json`` allein sagt das
    seit der Stichwahl nicht mehr, dort steht ``null`` drin."""
    out = []
    for r in rows:
        seats = json.loads(r["seats_json"]) if r.get("seats_json") else None
        mayor_tip = json.loads(r["mayor_json"]) if r.get("mayor_json") else None
        out.append({
            "id": r["id"], "name": r["name"], "party": r.get("party"),
            "late_at": r["late_at"], "hidden_at": r.get("hidden_at"),
            "seats": seats, "mayor": mayor_tip, "turnout": r.get("turnout_pct"),
            "tipped": seats is not None or mayor_tip is not None,
            "updated_at": r.get("tip_updated_at") or r["created_at"],
        })
    return out


def _avg(tips: list[dict], key: str, slug: str) -> float | None:
    """Ø-Tipp einer Liste/Kandidatur — NUR aus rechtzeitig abgegebenen
    Tipps (``late_at is None``), wie im Plan festgelegt."""
    werte = [t[key][slug] for t in tips
            if t[key] and slug in t[key] and t[key][slug] is not None and t["late_at"] is None]
    return round(mean(werte), 2) if werte else None


def _turnout_tips(tips: list[dict]) -> list[float]:
    return [t["turnout"] for t in tips if t["turnout"] is not None and t["late_at"] is None]


def _avg_turnout(tips: list[dict]) -> float | None:
    werte = _turnout_tips(tips)
    return round(mean(werte), 2) if werte else None


def party_options() -> list[PredictionPartyOption]:
    """Das Parteien-Menü: die Parteien und Wählergruppen der Ratswahl, ohne
    ``PARTY_MENU_EXCLUDED`` und ohne Einzelwahlvorschläge (eine Person ist
    keine Partei). Die Reihenfolge ist die des Stimmzettels."""
    try:
        reg = _reg()
    except Exception:
        _log.exception("Tippspiel: Parteien-Menü nicht lesbar.")
        return []
    return [PredictionPartyOption(slug=p.slug, short=p.short, color=p.color, color_dark=p.color_dark)
            for p in reg.parties if p.slug not in PARTY_MENU_EXCLUDED and p.kind != "einzelbewerber"]


def party_of(slug: str | None, options: list[PredictionPartyOption] | None = None) -> PredictionPartyOption | None:
    """Das Etikett zu einer gespeicherten Parteiangabe. Ein Slug, den das
    Register nicht mehr kennt, wird nicht verschluckt, sondern roh gezeigt —
    die Person hat ihn gewählt."""
    if not slug:
        return None
    for option in (options if options is not None else party_options()):
        if option["slug"] == slug:
            return option
    return PredictionPartyOption(slug=slug, short=slug, color="", color_dark="")


def _actuals(results: dict[str, dict], night: ElectionNight | None,
             ob: mayor.MayorResult | None) -> tuple[dict[str, int | None], dict[str, float | None], float | None, str]:
    """Das Ist je Liste, je OB-Kandidatur und für die Wahlbeteiligung, plus
    das ``source_label``.

    Reihenfolge je Schlüssel: veröffentlichte HANDEINGABE > Wahlabend >
    veröffentlichter Votemanager-Schnappschuss (Rückfall). Die OB-Prozente
    zählen erst, wenn dort etwas ausgezählt ist — ``probe(0)`` trägt die
    Endprozente der Vorwahl bei ``phase == "before"``, und die wären sonst vor
    der ersten Stimme schon Punkte wert. Die Wahlbeteiligung kommt bei einer
    Ratswahl aus deren Summenzeile, sonst aus der OB-/Stichwahl — mit
    derselben Sperre."""
    seats: dict[str, int | None] = {}
    pct: dict[str, float | None] = {}
    turnout: float | None = None
    quellen: set[str] = set()
    if night is not None:
        for p in night["parties"]:
            wert = night_seats(p)
            if wert is not None:
                seats[p["slug"]] = wert
        if night["phase"] != "before":
            turnout = night["totals"]["turnout_pct"]
    if ob is not None and ob.phase != "before":
        for c in ob.candidates:
            if c.share_pct is not None:
                pct[c.slug] = c.share_pct
        if night is None:
            turnout = ob.turnout_pct
    if seats or pct or turnout is not None:
        quellen.add("votemanager")
    for slug, r in results.items():
        if not r.get("published_at"):
            continue
        manuell = (r.get("published_source") or "manuell") == "manuell"
        if slug == TURNOUT_SLUG:
            wert = r["published_pct"]
            if wert is None:
                continue
            if manuell or turnout is None:
                turnout = wert
                quellen.add("manuell" if manuell else "votemanager")
            continue
        if slug.startswith("ob:"):
            ziel, key, wert = pct, slug[3:], r["published_pct"]
        else:
            ziel, key, wert = seats, slug, r["published_seats"]
        if wert is None:
            continue
        if manuell or key not in ziel:
            ziel[key] = wert
            quellen.add("manuell" if manuell else "votemanager")
    if not quellen:
        label = ""
    elif len(quellen) > 1:
        label = "gemischt"
    else:
        label = next(iter(quellen))
    return seats, pct, turnout, label


def _digest(actual_seats: dict, actual_mayor: dict, actual_turnout: float | None, late_scored: bool) -> str:
    """Was einen Stand vom nächsten unterscheidet: die verglichenen Zahlen
    (und ob Spätstarter zählen — das ordnet die Liste um)."""
    roh = json.dumps([sorted(actual_seats.items()), sorted(actual_mayor.items()), actual_turnout, late_scored])
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


def _pp(wert: float) -> str:
    """„2,3" — Prozentpunkte mit einer Nachkommastelle, deutsch."""
    return f"{wert:.1f}".replace(".", ",")


def _compare_sentence(compare: list[PredictionCompareLine], ob: list[PredictionMayorCompareLine],
                      sitzwahl: bool) -> str:
    """Der Satz neben Lotti auf dem Vergleichs-Beamer — bei einer Ratswahl
    über die Liste mit dem größten Abstand in Sitzen, bei einer OB- oder
    Stichwahl über die Kandidatur mit dem größten Abstand in Prozentpunkten."""
    if sitzwahl:
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
    personen: list[tuple[str, float, float]] = [
        (m["name"], m["avg_tip"], m["actual_pct"])
        for m in ob if m["avg_tip"] is not None and m["actual_pct"] is not None
    ]
    if not personen:
        return "Sobald der erste Auszählungsstand da ist, siehst du hier, wie gut die Tipps zum Stand passen."
    name, avg, actual = max(personen, key=lambda k: abs(k[1] - k[2]))
    diff = round(avg - actual, 1)
    if abs(diff) < 0.5:
        return f"Bei {name} liegen die Tipps im Durchschnitt nah am aktuellen Stand."
    richtung = "mehr" if diff > 0 else "weniger"
    return (f"Für {name} wurden im Durchschnitt rund {_pp(abs(diff))} Prozentpunkte {richtung} getippt, "
            f"als der aktuelle Stand zeigt.")


def _score_dict(s: scoring.Score) -> PredictionScore:
    return PredictionScore(total=s.total, seat_points=s.seat_points, mayor_points=s.mayor_points,
                           turnout_points=s.turnout_points, exact_lists=s.exact_lists,
                           deviation=s.deviation, pct_deviation=s.pct_deviation)


def _area_label(night: ElectionNight | None, ob: mayor.MayorResult | None) -> str:
    if night is not None:
        gesamt = night["progress"]["districts_total"]
        gezaehlt = night["progress"]["districts_counted"]
        bereiche = night["areas"]
        voll = sum(1 for a in bereiche if a["districts_counted"] >= a["districts_total"] and a["districts_total"] > 0)
        if bereiche:
            return f"{voll}/{len(bereiche)} Wahlbereiche"
        return f"{gezaehlt}/{gesamt} Wahlbezirke"
    if ob is not None and ob.reports_expected:
        return f"{ob.reports_received}/{ob.reports_expected} Wahlbezirke"
    return ""


def _mayor_candidates(b: Basis) -> tuple[mayor.MayorCandidate, ...]:
    if b.ob_wahl is None:
        return ()
    try:
        return mayor.candidates(b.ob_wahl)
    except Exception:
        _log.exception("Tippspiel: Kandidaturen der OB-Wahl %s nicht lesbar.", b.ob_wahl.slug)
        return ()


def _turnout_previous(wahl: elections.Election) -> tuple[float | None, str]:
    """Der Anhaltspunkt fürs Wahlbeteiligungs-Feld: Bei einer Stichwahl die
    Beteiligung des ersten Wahlgangs — aus dem eingefrorenen Stand im Repo
    (``mayor.probe_payload``), nicht aus dem Netz. Sonst nichts: Für eine
    Ratswahl gäbe es die Vorwahl, aber die liegt fünf Jahre zurück."""
    if not wahl.first_round:
        return None, ""
    try:
        erster = elections.get(wahl.first_round)
        payload, herkunft = mayor.probe_payload(wahl)
        if erster is None or herkunft != "erster Wahlgang":
            return None, ""
        ergebnis = mayor.parse(payload, mayor.candidates(erster))
    except Exception:
        _log.exception("Tippspiel: Wahlbeteiligung des ersten Wahlgangs nicht lesbar.")
        return None, ""
    if ergebnis is None or ergebnis.turnout_pct is None:
        return None, ""
    return ergebnis.turnout_pct, "1. Wahlgang"


def _successor_path(store: Store, game: dict, runde) -> str:
    """Wohin Neue sollen, wenn diese Runde zu ist: zur gelisteten Runde der
    Wahl im Fokus, falls das eine ANDERE ist und dort noch getippt werden
    darf. Sonst leer. Nur für gelistete Runden — ein privater Kreis hat
    keinen Nachfolger."""
    from . import rounds

    if game["phase"] == "open" or runde is None or not runde.listed:
        return ""
    try:
        naechste = rounds.fuer_wahl(elections.focus().slug)
    except Exception:
        _log.exception("Tippspiel: Nachfolge-Runde nicht bestimmbar.")
        return ""
    if naechste is None or naechste.slug == runde.slug:
        return ""
    zeile = store.prediction_spiel_zeile(naechste.slug)
    if zeile is not None and zeile["phase"] != "open":
        return ""
    return rounds.public_path(naechste)


# ------------------------------------------------------------------ Öffentliche Formen

def setup(store: Store, game_id: int) -> PredictionGame:
    from . import rounds  # hier statt oben: rounds ist rein, service nicht — kein Kreis, nur Ordnung

    game = store.prediction_game(game_id)
    runde = rounds.get(game["slug"])
    b = basis(game)
    # Eine Mehrheitswahl hat keine Listen und keine Sitze — dort wird auf
    # Prozente getippt, und `parties` bleibt leer. Der Client entscheidet
    # daran, welches Formular er zeigt; er muss die Wahlart nicht auswerten.
    parties: list[PredictionParty] = []
    if b.reg is not None:
        parties = [PredictionParty(slug=p.slug, short=p.short, name=p.official, color=p.color,
                                   color_dark=p.color_dark, seats_previous=None) for p in b.reg.parties]
        try:
            vorwahl = {p["slug"]: p.get("seats_previous") for p in election_service.live()["parties"]}
            for pp in parties:
                pp["seats_previous"] = vorwahl.get(pp["slug"])
        except Exception:
            _log.exception("Tippspiel: Sitze der Vorwahl für die Startverteilung nicht zu lesen.")
    mayors = [PredictionMayorCandidate(slug=c.slug, name=c.name, party=c.party) for c in _mayor_candidates(b)]
    turnout_previous, turnout_label = _turnout_previous(b.wahl)
    return PredictionGame(
        round=game["slug"], listed=runde.listed if runde else False,
        title=game["title"], phase=game["phase"], seats_total=b.reg.seats if b.reg else 0,
        election_slug=b.wahl.slug, election_title=b.wahl.short_title, election_date=b.wahl.date,
        tip_kind="seats" if b.sitzwahl else "pct",
        public=game.get("visibility", "oeffentlich") != "konto",
        previous_label=b.wahl.previous_label,
        locked=game["phase"] != "open", locked_at=game["locked_at"],
        late_scored=bool(game["late_scored"]), shared_device=bool(game["shared_device"]),
        player_count=store.prediction_player_count(game_id),
        deadline_hint=_deadline_hint(game, b.sitzwahl), parties=parties, mayor_candidates=mayors,
        party_options=party_options(),
        turnout_previous=turnout_previous, turnout_previous_label=turnout_label,
        successor_path=_successor_path(store, game, runde),
    )


def _build(store: Store, game_id: int, *, probe: str | None, counted: int | None) -> _Bundle:
    game = store.prediction_game(game_id)
    b = basis(game)
    night = _read_night(probe, counted) if b.sitzwahl else None
    ob = _read_mayor(probe, counted, b.ob_wahl) if b.ob_wahl is not None else None
    if probe is None:
        _check_auto_lock(store, game_id, night, ob)
    game = store.prediction_game(game_id)
    results = {r["slug"]: r for r in store.prediction_result(game_id)}
    actual_seats, actual_mayor, actual_turnout, source_label = _actuals(results, night, ob)
    vergleichbar = bool(actual_seats or actual_mayor or actual_turnout is not None)
    optionen = party_options()

    tips = _parsed(store.prediction_players(game_id, include_hidden=False))
    sichtbare_mit_tipp = [t for t in tips if t["tipped"]]
    ohne_tipp = [t for t in tips if not t["tipped"]]

    compare: list[PredictionCompareLine] = []
    for p in (b.reg.parties if b.reg is not None else ()):
        avg = _avg(sichtbare_mit_tipp, "seats", p.slug)
        actual = actual_seats.get(p.slug)
        exakt = sum(1 for t in sichtbare_mit_tipp
                   if t["seats"] and t["seats"].get(p.slug) is not None and actual is not None
                   and t["seats"][p.slug] == actual)
        compare.append(PredictionCompareLine(slug=p.slug, short=p.short, color=p.color, color_dark=p.color_dark,
                                             actual=actual, avg_tip=avg, exact_count=exakt))

    mayor_compare: list[PredictionMayorCompareLine] = []
    for c in _mayor_candidates(b):
        mayor_compare.append(PredictionMayorCompareLine(
            slug=c.slug, name=c.name, party=c.party,
            actual_pct=actual_mayor.get(c.slug), avg_tip=_avg(sichtbare_mit_tipp, "mayor", c.slug),
        ))
    turnout_compare = PredictionTurnoutCompare(actual_pct=actual_turnout, avg_tip=_avg_turnout(sichtbare_mit_tipp),
                                               tip_count=len(_turnout_tips(sichtbare_mit_tipp)))

    def zeile(t: dict, *, scored: bool, score: PredictionScore | None, rank: int | None,
              rank_before: int | None) -> PredictionRow:
        return PredictionRow(player_id=t["id"], name=t["name"], party=party_of(t["party"], optionen),
                             late_at=t["late_at"], scored=scored, has_tip=t["tipped"], score=score,
                             rank=rank, rank_before=rank_before)

    rows: list[PredictionRow] = []
    leader: int | None = None
    computed_at: str | None = None

    if not vergleichbar:
        alle = sorted(tips, key=lambda t: t["name"].casefold())
        rows = [zeile(t, scored=t["late_at"] is None or bool(game["late_scored"]), score=None, rank=None, rank_before=None)
                for t in alle]
    else:
        standings = [
            scoring.Standing(id=t["id"], name=t["name"], updated_at=t["updated_at"],
                             scored=t["late_at"] is None or bool(game["late_scored"]),
                             score=scoring.score(t["seats"], t["mayor"], actual_seats, actual_mayor,
                                                 t["turnout"], actual_turnout))
            for t in sichtbare_mit_tipp
        ]
        geordnet = scoring.order(standings)
        rang = {s.id: i for i, s in enumerate(geordnet, start=1)}
        pfad = f"{'probe' if probe is not None else 'live'}:{game_id}"
        computed_at, neu = _stand_at(pfad, _digest(actual_seats, actual_mayor, actual_turnout, bool(game["late_scored"])))
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
            rows.append(zeile(by_id[s.id], scored=s.scored, score=_score_dict(s.score),
                              rank=rang[s.id], rank_before=vorher.get(s.id)))
        fuer_ohne = sorted(ohne_tipp, key=lambda t: t["name"].casefold())
        rows += [zeile(t, scored=False, score=None, rank=None, rank_before=None) for t in fuer_ohne]
        if geordnet:
            leader = geordnet[0].id

    if b.sitzwahl:
        notes = list(night.get("notes", [])) if night is not None else [
            "Der Auszählungsstand der Ratswahl ist gerade nicht abrufbar."]
    else:
        notes = list(ob.notes) if ob is not None else ["Der Auszählungsstand ist gerade nicht abrufbar."]
        if ob is not None and not ob.ok and ob.error:
            notes.append(ob.error)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    tafel = PredictionStand(
        title=game["title"], phase=game["phase"], tip_kind="seats" if b.sitzwahl else "pct",
        stand_label=_uhrzeit(computed_at) if computed_at else "",
        area_label=_area_label(night, ob), source_label=source_label,
        seats_total=b.reg.seats if b.reg else 0,
        player_count=len(tips), tip_count=len(sichtbare_mit_tipp),
        compare=compare, mayor=mayor_compare, turnout=turnout_compare,
        mayor_status=ob.phase if ob is not None else "before",
        rows=rows, leader_player_id=leader,
        compare_sentence=_compare_sentence(compare, mayor_compare, b.sitzwahl),
        computed_at=computed_at or now, notes=notes,
    )
    return _Bundle(stand=tafel, basis=b, actual_seats=actual_seats, actual_mayor=actual_mayor,
                   actual_turnout=actual_turnout)


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
    bnd = _bundle(store, game_id, probe=probe, counted=counted)
    b = bnd.basis
    tafel = bnd.stand

    seats_tip = json.loads(player["seats_json"]) if player.get("seats_json") else None
    mayor_tip = json.loads(player["mayor_json"]) if player.get("mayor_json") else None
    turnout_tip = player.get("turnout_pct")

    row = next((r for r in tafel["rows"] if r["player_id"] == player["id"]), None)

    avg_tips_seats = {c["slug"]: c["avg_tip"] for c in tafel["compare"]}
    avg_tips_mayor = {c["slug"]: c["avg_tip"] for c in tafel["mayor"]}

    seat_lines: list[PredictionSeatLine] = []
    if seats_tip is not None and b.reg is not None:
        for p in b.reg.parties:
            tip = seats_tip.get(p.slug, 0)
            actual = bnd.actual_seats.get(p.slug)
            seat_lines.append(PredictionSeatLine(
                slug=p.slug, tip=tip, actual=actual, avg_tip=avg_tips_seats.get(p.slug),
                points=scoring.seat_points(tip, actual), exact=actual is not None and tip == actual,
            ))
    mayor_lines: list[PredictionMayorLine] = []
    if mayor_tip is not None:
        for c in _mayor_candidates(b):
            tip = mayor_tip.get(c.slug, 0.0)
            actual_pct = bnd.actual_mayor.get(c.slug)
            mayor_lines.append(PredictionMayorLine(
                slug=c.slug, tip=tip, actual_pct=actual_pct,
                avg_tip=avg_tips_mayor.get(c.slug), points=scoring.mayor_points(tip, actual_pct),
            ))
    turnout_line: PredictionTurnoutLine | None = None
    if turnout_tip is not None:
        turnout_line = PredictionTurnoutLine(
            tip=turnout_tip, actual_pct=bnd.actual_turnout, avg_tip=tafel["turnout"]["avg_tip"],
            points=scoring.turnout_points(turnout_tip, bnd.actual_turnout),
        )

    return PredictionMine(
        player_id=player["id"], name=player["name"], party=party_of(player.get("party")),
        late_at=player["late_at"],
        scored=bool(row["scored"]) if row else (player["late_at"] is None or bool(game["late_scored"])),
        has_tip=seats_tip is not None or mayor_tip is not None, has_mayor_tip=mayor_tip is not None,
        locked=game["phase"] != "open",
        seats=seat_lines, mayor=mayor_lines, turnout=turnout_line,
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
