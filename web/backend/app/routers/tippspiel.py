"""Tippspiel zur Ratswahl 13.09.2026 — öffentlich unter ``/api/tipp/…``,
Verwaltung unter ``/api/tipp/admin/…`` (docs/plan-tippspiel-ratswahl.md).

**Ohne Konto.** Wer mitspielt, gibt einen Namen ein und bekommt einen Cookie
(``tipp_token``, 30 Tage, HttpOnly) — die Identität IST der Token, es gibt
keine ``web_users``-Zeile dazu. ``POST /api/tipp`` ist damit ZUGLEICH Beitritt
(ohne gültigen Cookie, ``name`` Pflicht) und Tipp-Update (mit gültigem Cookie).

**Seit 12.09.2026 mehrere Runden** (``prediction/rounds.py``): ``?round=``
wählt sie, ohne Parameter ist es die Hauptrunde. Jede Runde hat ihren
eigenen Cookie (``tipp_token`` bzw. ``tipp_token_<slug>``), damit eine
Person in zwei Runden zwei Personen sein kann — und ein Cookie der einen
Runde in der anderen nie eine Person ergibt.

**Hinter dem Feature-Schalter ``tippspiel`` stehen nur die ÖFFENTLICHEN
Routen** — wie beim Wahlabend antworten sie ohne ihn mit 404. Die
Admin-Routen bleiben davon unberührt: Tim soll das Spiel vorbereiten können,
bevor der Schalter fällt.

**Der Entwurf ist die Sperre für die Handeingabe.** ``PUT …/admin/ergebnis``
und ``POST …/admin/abfragen`` schreiben nur den ENTWURF (``prediction_result``,
Spalten ohne ``published_``); erst ``POST …/admin/veroeffentlichen`` macht
eine Zeile für ``GET /api/tipp/stand`` wirksam. Ein Tippfehler beim
Eintragen landet damit nie unbeaufsichtigt auf dem Beamer. Die Tafel selbst
folgt dem Wahlabend auch ohne Admin — eine veröffentlichte Handeingabe
überschreibt ihn je Liste (s. ``prediction/service.py``).
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from kern import features
from kern.store import Store

from ..antworten import (
    MayorNight,
    Ok,
    PredictionAdminPlayer,
    PredictionAdminStand,
    PredictionGame,
    PredictionMine,
    PredictionResultRow,
    PredictionRoundInfo,
    PredictionStand,
)
from ..config import get_settings
from ..deps import get_store, require_admin
from ..election import mayor, register
from ..prediction import rounds, service
from ..prediction.rounds import Round
from ..ratelimit import prediction_join_limiter, prediction_tip_limiter
from ..schemas import PredictionJoinIn, PredictionPhaseIn, PredictionPlayerIn, PredictionResultLineIn

router = APIRouter(tags=["tippspiel"])

COOKIE_NAME = "tipp_token"
COOKIE_MAX_AGE = 30 * 24 * 3600


def _frei() -> None:
    if not features.an("tippspiel"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Das Tippspiel ist noch nicht freigeschaltet.")


def _runde(slug: str | None) -> Round:
    runde = rounds.get(slug)
    if runde is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diese Tipprunde gibt es nicht.")
    return runde


def _game_id(store: Store, runde: Round) -> int:
    """Die Spielzeile der Runde — legt sie beim ersten Zugriff an."""
    return store.prediction_game_by_slug(runde.slug, runde.title)["id"]


def _cookie_name(runde: Round) -> str:
    return COOKIE_NAME if runde.is_default else f"{COOKIE_NAME}_{runde.slug}"


# ------------------------------------------------------------------ Identität

def _hash(klartext: str) -> str:
    return hashlib.sha256(klartext.encode("utf-8")).hexdigest()


def _token_hash(request: Request, runde: Round) -> str | None:
    klartext = request.cookies.get(_cookie_name(runde))
    return _hash(klartext) if klartext else None


def _set_cookie(response: Response, runde: Round, klartext: str) -> None:
    settings = get_settings()
    response.set_cookie(key=_cookie_name(runde), value=klartext, httponly=True, secure=settings.cookie_secure,
                        samesite="lax", max_age=COOKIE_MAX_AGE, path="/")


def _clear_cookie(response: Response, runde: Round) -> None:
    settings = get_settings()
    response.delete_cookie(_cookie_name(runde), path="/", httponly=True, secure=settings.cookie_secure, samesite="lax")


# ------------------------------------------------------------------ Validierung — deutsche Sätze statt Pydantic-Meldungen

def _clean_name(name: str) -> str:
    bereinigt = " ".join(name.split())
    if not (2 <= len(bereinigt) <= 30):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "Der Name muss zwischen 2 und 30 Zeichen lang sein.")
    return bereinigt


def _validate_seats(seats: dict[str, int], reg: register.Register) -> None:
    erwartet = {p.slug for p in reg.parties}
    if set(seats) != erwartet:
        fehlend = sorted(erwartet - set(seats))
        unbekannt = sorted(set(seats) - erwartet)
        teile = []
        if fehlend:
            teile.append(f"es fehlen: {', '.join(fehlend)}")
        if unbekannt:
            teile.append(f"unbekannt: {', '.join(unbekannt)}")
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"Bitte gib für alle {len(erwartet)} Wahllisten eine Sitzzahl an ({'; '.join(teile)}).")
    for slug, wert in seats.items():
        if not isinstance(wert, int) or not (0 <= wert <= reg.seats):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                f"Die Sitzzahl für {slug} muss zwischen 0 und {reg.seats} liegen.")
    summe = sum(seats.values())
    if summe != reg.seats:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"Verteile insgesamt {reg.seats} Sitze. Du hast bisher {summe} Sitze vergeben.")


def _validate_mayor(tip: dict[str, float] | None) -> None:
    if not tip:
        return
    bekannt = {c.slug for c in mayor.candidates()}
    unbekannt = sorted(set(tip) - bekannt)
    if unbekannt:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"Diese Person steht nicht zur OB-Wahl: {', '.join(unbekannt)}.")
    for slug, wert in tip.items():
        if not (0 <= wert <= 100):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                f"Der Prozentwert für {slug} muss zwischen 0 und 100 liegen.")
    summe = sum(tip.values())
    if summe > 100.5:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"Die Stimmenanteile bei der OB-Wahl dürfen zusammen nicht mehr als 100 % ergeben "
                            f"(dein Tipp ergibt {summe:.1f} %).")


# ------------------------------------------------------------------ Öffentlich

@router.get("/api/tipp/setup")
def setup(runde: str | None = Query(default=None, alias="round"), store: Store = Depends(get_store)) -> PredictionGame:
    _frei()
    r = _runde(runde)
    return service.setup(store, _game_id(store, r))


@router.post("/api/tipp", status_code=status.HTTP_200_OK)
def beitreten_oder_tippen(payload: PredictionJoinIn, request: Request, response: Response,
                          runde: str | None = Query(default=None, alias="round"),
                          store: Store = Depends(get_store)) -> PredictionMine:
    """Ohne gültigen Cookie: Beitritt (``name`` Pflicht). Mit gültigem
    Cookie: nur der Tipp wird aktualisiert, ``name`` bleibt unbeachtet —
    umbenennen kann nur der Admin (``PUT …/admin/spieler/{id}``)."""
    _frei()
    r = _runde(runde)
    game_id = _game_id(store, r)
    prediction_join_limiter.check(request)
    service._check_auto_lock(store, game_id)  # noqa: SLF001 — bewusste Wiederverwendung, s. Moduldoc
    reg = register.load()
    token_hash = _token_hash(request, r)
    player = store.prediction_player_by_token(token_hash, game_id) if token_hash else None

    if player is None:
        if not payload.name:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Bitte gib deinen Namen ein.")
        name = _clean_name(payload.name)
        game = store.prediction_game(game_id)
        jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
        late_at = jetzt if game["phase"] != "open" else None
        klartext = secrets.token_hex(16)
        try:
            player = store.prediction_player_add(game_id, name, _hash(klartext), late_at)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"„{name}“ ist schon vergeben — versuch es z. B. mit „{name} 2“.") from exc
        _set_cookie(response, r, klartext)
        if late_at:
            store.prediction_log_add(game_id, f"{player['name']} ist nach Tipp-Schluss beigetreten (nachgetippt).")

    if payload.seats is not None:
        game = store.prediction_game(game_id)
        if player["late_at"] is None and game["phase"] != "open":
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "Die Tippfrist ist vorbei. Du kannst deinen Tipp nicht mehr ändern.")
        _validate_seats(payload.seats, reg)
        _validate_mayor(payload.mayor)
        prediction_tip_limiter.check(request)
        store.prediction_tip_set(player["id"], json.dumps(payload.seats, ensure_ascii=False),
                                 json.dumps(payload.mayor, ensure_ascii=False) if payload.mayor else None)
        service.reset()

    # Bei einem NEUEN Beitritt trägt das eingehende Request-Objekt den gerade
    # gesetzten Cookie noch nicht (der wirkt erst beim nächsten Aufruf des
    # Browsers) — deshalb ``player["token_hash"]`` statt ``_token_hash(request)``.
    ergebnis = service.mine(store, game_id, player["token_hash"])
    assert ergebnis is not None  # der Spieler wurde in dieser Funktion selbst angelegt oder gefunden
    return ergebnis


@router.get("/api/tipp/me")
def meins(request: Request, probe: str | None = Query(default=None),
         counted: int | None = Query(default=None, ge=0, le=133),
         runde: str | None = Query(default=None, alias="round"),
         store: Store = Depends(get_store)) -> PredictionMine:
    _frei()
    r = _runde(runde)
    token_hash = _token_hash(request, r)
    if token_hash is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Gib zuerst deinen Namen ein, um mitzumachen.")
    ergebnis = service.mine(store, _game_id(store, r), token_hash, probe=probe, counted=counted)
    if ergebnis is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Deine Teilnahme wurde nicht gefunden. Gib deinen Namen bitte noch einmal ein.")
    return ergebnis


@router.delete("/api/tipp/me")
def austreten(request: Request, response: Response, runde: str | None = Query(default=None, alias="round"),
              store: Store = Depends(get_store)) -> Ok:
    _frei()
    r = _runde(runde)
    token_hash = _token_hash(request, r)
    if token_hash:
        player = store.prediction_player_by_token(token_hash, _game_id(store, r))
        if player:
            store.prediction_player_delete_own(player["id"])
            service.reset()
    _clear_cookie(response, r)
    return Ok(ok=True)


# Der 304-Zweig unten gibt eine `Response` zurück, nicht die deklarierte
# Form: FastAPI lässt eine `Response` bewusst unverändert durch (dieselbe
# Eigenheit wie bei `GET /api/health` in `main.py`), die Annotation bleibt
# trotzdem `PredictionStand` — sie ist es, aus der `/openapi.json` den
# Vertrag baut. Ein Typprüfer kann das nicht wissen; darum eine benannte
# Ausnahme statt einer aufgeweichten Annotation (die FastAPI beim Start mit
# einem harten Fehler quittiert, s. Commit-Historie dieser Zeile).
@router.get("/api/tipp/stand")
def stand(request: Request, response: Response, probe: str | None = Query(default=None),
         counted: int | None = Query(default=None, ge=0, le=133),
         runde: str | None = Query(default=None, alias="round"),
         store: Store = Depends(get_store)) -> PredictionStand:
    _frei()
    r = _runde(runde)
    ergebnis = service.stand(store, _game_id(store, r), probe=probe, counted=counted)
    etag = f'"{hashlib.sha1(ergebnis["computed_at"].encode()).hexdigest()[:16]}"'  # noqa: S324 — kein Sicherheitszweck, nur Cache-Schlüssel
    if request.headers.get("if-none-match") == etag:
        return Response(  # pyright: ignore[reportReturnType] — siehe oben
            status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-cache"
    return ergebnis


@router.get("/api/wahlabend/ob")
def ob_wahl(probe: str | None = Query(default=None), counted: int | None = Query(default=None, ge=0, le=133)) -> MayorNight:
    """Die OB-Wahl für sich — hinter dem Schalter ``wahlabend`` (nicht
    ``tippspiel``): Sie ist Teil des Wahlabends, nicht nur des Tippspiels."""
    if not features.an("wahlabend"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Der Wahlabend ist noch nicht freigeschaltet.")
    ergebnis = mayor.probe(counted) if probe == "2021" else mayor.fetch()
    return MayorNight(
        phase=ergebnis.phase, reports_expected=ergebnis.reports_expected, reports_received=ergebnis.reports_received,
        turnout_pct=ergebnis.turnout_pct, valid_votes=ergebnis.valid_votes, invalid_ballots=ergebnis.invalid_ballots,
        candidates=[{"slug": c.slug, "name": c.name, "party": c.party, "votes": c.votes, "share_pct": c.share_pct}
                   for c in ergebnis.candidates],
        runoff=list(ergebnis.runoff), fetched_at=ergebnis.fetched_at, ok=ergebnis.ok, error=ergebnis.error,
        notes=list(ergebnis.notes),
    )


# ------------------------------------------------------------------ QR-Code

@router.get("/api/tipp/qr.png", response_class=Response, responses={200: {"content": {"image/png": {}}}})
def qr_code(runde: str | None = Query(default=None, alias="round"), store: Store = Depends(get_store)) -> Response:
    _frei()
    import segno

    link = f"{get_settings().app_base_url}{rounds.public_path(_runde(runde))}"
    qr = segno.make(link, error="m")
    puffer = __import__("io").BytesIO()
    qr.save(puffer, kind="png", scale=12, border=2)
    return Response(content=puffer.getvalue(), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


# ------------------------------------------------------------------ Admin (1h) — kein Schalter, s. Moduldoc

def _admin_stand(store: Store, runde: Round) -> PredictionAdminStand:
    reg = register.load()
    game_id = _game_id(store, runde)
    results = {r["slug"]: r for r in store.prediction_result(game_id)}
    tips = service._parsed(store.prediction_players(game_id, include_hidden=True))  # noqa: SLF001
    # Ø-Tipp und „exakt" zählen wie auf der öffentlichen Tafel: ohne
    # ausgeblendete Personen. Die Teilnehmerliste unten zeigt sie dagegen
    # ausdrücklich — der Admin will sie wiederfinden.
    sichtbare = [t for t in tips if t["hidden_at"] is None]

    rows: list[PredictionResultRow] = []
    for p in reg.parties:
        r = results.get(p.slug, {})
        avg = service._avg(sichtbare, "seats", p.slug)  # noqa: SLF001
        veroeffentlicht = r.get("published_seats")
        exakt = sum(1 for t in sichtbare if t["seats"] and t["seats"].get(p.slug) is not None
                   and veroeffentlicht is not None and t["seats"][p.slug] == veroeffentlicht)
        rows.append(PredictionResultRow(
            slug=p.slug, seats=r.get("seats"), pct=None, source=r.get("source") or "manuell",
            avg_tip=avg, exact_count=exakt, published_seats=veroeffentlicht, published_pct=None,
            published_source=r.get("published_source"), published_at=r.get("published_at"),
        ))
    for c in mayor.candidates():
        slug = f"ob:{c.slug}"
        r = results.get(slug, {})
        avg = service._avg(sichtbare, "mayor", c.slug)  # noqa: SLF001
        rows.append(PredictionResultRow(
            slug=slug, seats=None, pct=r.get("pct"), source=r.get("source") or "manuell",
            avg_tip=avg, exact_count=0, published_seats=None, published_pct=r.get("published_pct"),
            published_source=r.get("published_source"), published_at=r.get("published_at"),
        ))
    spieler = [PredictionAdminPlayer(
        id=t["id"], name=t["name"], late_at=t["late_at"], hidden=t["hidden_at"] is not None,
        has_tip=t["seats"] is not None, has_mayor_tip=t["mayor"] is not None,
    ) for t in sorted(tips, key=lambda t: t["name"].casefold())]
    # Uhrzeit in Berliner Zeit statt des rohen UTC-Zeitstempels aus dem Store
    # („2026-09-11T12:06:18" las sich am Nachmittag wie ein Fehler).
    log = [f"{service._uhrzeit(eintrag['at'])} · {eintrag['text']}"  # noqa: SLF001
           for eintrag in store.prediction_log(game_id, limit=30)]
    # Alle Runden für den Umschalter — jede wird beim ersten Blick angelegt,
    # damit auch eine noch leere Runde schon verwaltet werden kann.
    alle: list[PredictionRoundInfo] = []
    for rd in rounds.ROUNDS.values():
        zeile = store.prediction_game_by_slug(rd.slug, rd.title)
        alle.append(PredictionRoundInfo(slug=rd.slug, title=zeile["title"], listed=rd.listed, phase=zeile["phase"],
                                        player_count=store.prediction_player_count(zeile["id"])))
    return PredictionAdminStand(rounds=alle, game=service.setup(store, game_id), results=rows, players=spieler, log=log)


#: Der Runden-Parameter der Admin-Endpunkte — dieselbe Schreibweise wie öffentlich.
def _admin_runde(runde: str | None = Query(default=None, alias="round")) -> Round:
    return _runde(runde)


@router.get("/api/tipp/admin/stand")
def admin_stand(_admin: dict = Depends(require_admin), runde: Round = Depends(_admin_runde),
                store: Store = Depends(get_store)) -> PredictionAdminStand:
    return _admin_stand(store, runde)


@router.put("/api/tipp/admin/ergebnis")
def ergebnis_eintragen(zeilen: list[PredictionResultLineIn], _admin: dict = Depends(require_admin),
                       runde: Round = Depends(_admin_runde), store: Store = Depends(get_store)) -> PredictionAdminStand:
    store.prediction_result_set(_game_id(store, runde),
                                [{"slug": z.slug, "seats": z.seats, "pct": z.pct} for z in zeilen], source="manuell")
    service.reset()
    return _admin_stand(store, runde)


@router.post("/api/tipp/admin/abfragen")
def jetzt_abfragen(_admin: dict = Depends(require_admin), runde: Round = Depends(_admin_runde),
                   store: Store = Depends(get_store)) -> PredictionAdminStand:
    """„Jetzt abfragen": die Live-Zahlen der Ratswahl UND der OB-Wahl in den
    Entwurf übernehmen — NICHT veröffentlicht, das bleibt ein eigener Schritt."""
    from ..election import service as election_service

    night = election_service.live()
    zeilen: list[dict] = []
    for p in night["parties"]:
        wert = service.night_seats(p)
        if wert is not None:
            zeilen.append({"slug": p["slug"], "seats": wert})
    ob = mayor.fetch()
    for c in ob.candidates:
        if c.share_pct is not None:
            zeilen.append({"slug": f"ob:{c.slug}", "pct": c.share_pct})
    game_id = _game_id(store, runde)
    if zeilen:
        store.prediction_result_set(game_id, zeilen, source="votemanager")
        listen = sum(1 for z in zeilen if "seats" in z)
        store.prediction_log_add(game_id, f"Votemanager abgefragt · {listen} Listen, {len(zeilen) - listen} "
                                 f"Personen bei der OB-Wahl in den Entwurf übernommen.")
        service.reset()
    return _admin_stand(store, runde)


@router.post("/api/tipp/admin/veroeffentlichen")
def veroeffentlichen(_admin: dict = Depends(require_admin), runde: Round = Depends(_admin_runde),
                     store: Store = Depends(get_store)) -> PredictionAdminStand:
    game_id = _game_id(store, runde)
    n = store.prediction_result_publish(game_id)
    store.prediction_log_add(game_id, f"Entwurf veröffentlicht · {n} Ergebnisse sind jetzt sichtbar.")
    service.reset()
    return _admin_stand(store, runde)


@router.post("/api/tipp/admin/verwerfen")
def verwerfen(_admin: dict = Depends(require_admin), runde: Round = Depends(_admin_runde),
              store: Store = Depends(get_store)) -> PredictionAdminStand:
    game_id = _game_id(store, runde)
    store.prediction_result_discard(game_id)
    store.prediction_log_add(game_id, "Entwurf verworfen · der Stand vor der letzten Eingabe ist wiederhergestellt.")
    service.reset()
    return _admin_stand(store, runde)


@router.put("/api/tipp/admin/phase")
def phase_setzen(payload: PredictionPhaseIn, _admin: dict = Depends(require_admin),
                 runde: Round = Depends(_admin_runde), store: Store = Depends(get_store)) -> PredictionAdminStand:
    game_id = _game_id(store, runde)
    felder: dict[str, object] = {"phase": payload.phase}
    if payload.phase == "locked":
        game = store.prediction_game(game_id)
        if game["phase"] == "open":
            felder["locked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            felder["locked_reason"] = "admin"
    if payload.late_scored is not None:
        felder["late_scored"] = 1 if payload.late_scored else 0
    store.prediction_game_set(game_id, **felder)
    text = {"open": "Spiel wieder geöffnet", "locked": "Tippfrist manuell beendet", "final": "Endstand gesetzt"}[payload.phase]
    store.prediction_log_add(game_id, text)
    service.reset()
    return _admin_stand(store, runde)


@router.put("/api/tipp/admin/spieler/{player_id}")
def spieler_bearbeiten(player_id: int, payload: PredictionPlayerIn, _admin: dict = Depends(require_admin),
                       runde: Round = Depends(_admin_runde), store: Store = Depends(get_store)) -> PredictionAdminStand:
    name = _clean_name(payload.name) if payload.name is not None else None
    store.prediction_player_update(player_id, name=name, hidden=payload.hidden)
    service.reset()
    return _admin_stand(store, runde)
