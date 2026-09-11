"""Tippspiel zur Ratswahl 13.09.2026 — öffentlich unter ``/api/tipp/…``,
Verwaltung unter ``/api/tipp/admin/…`` (docs/plan-tippspiel-ratswahl.md).

**Ohne Konto.** Wer mitspielt, gibt einen Namen ein und bekommt einen Cookie
(``tipp_token``, 30 Tage, HttpOnly) — die Identität IST der Token, es gibt
keine ``web_users``-Zeile dazu. ``POST /api/tipp`` ist damit ZUGLEICH Beitritt
(ohne gültigen Cookie, ``name`` Pflicht) und Tipp-Update (mit gültigem Cookie).

**Hinter dem Feature-Schalter ``tippspiel`` stehen nur die ÖFFENTLICHEN
Routen** — wie beim Wahlabend antworten sie ohne ihn mit 404. Die
Admin-Routen bleiben davon unberührt: Tim soll das Spiel vorbereiten können,
bevor der Schalter fällt.

**Der Entwurf ist die Sperre.** ``PUT …/admin/ergebnis`` und
``POST …/admin/abfragen`` schreiben nur den ENTWURF (``prediction_result``,
Spalten ohne ``published_``); erst ``POST …/admin/veroeffentlichen`` macht
eine Zeile für ``GET /api/tipp/stand`` sichtbar. Ein Tippfehler beim
Eintragen landet damit nie unbeaufsichtigt auf dem Beamer.
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
    PredictionAdminStand,
    PredictionGame,
    PredictionMine,
    PredictionResultRow,
    PredictionStand,
)
from ..config import get_settings
from ..deps import get_store, require_admin
from ..election import mayor, register
from ..prediction import service
from ..ratelimit import prediction_join_limiter, prediction_tip_limiter
from ..schemas import PredictionJoinIn, PredictionPhaseIn, PredictionPlayerIn, PredictionResultLineIn

router = APIRouter(tags=["tippspiel"])

COOKIE_NAME = "tipp_token"
COOKIE_MAX_AGE = 30 * 24 * 3600


def _frei() -> None:
    if not features.an("tippspiel"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Das Tippspiel ist noch nicht freigeschaltet.")


# ------------------------------------------------------------------ Identität

def _hash(klartext: str) -> str:
    return hashlib.sha256(klartext.encode("utf-8")).hexdigest()


def _token_hash(request: Request) -> str | None:
    klartext = request.cookies.get(COOKIE_NAME)
    return _hash(klartext) if klartext else None


def _set_cookie(response: Response, klartext: str) -> None:
    settings = get_settings()
    response.set_cookie(key=COOKIE_NAME, value=klartext, httponly=True, secure=settings.cookie_secure,
                        samesite="lax", max_age=COOKIE_MAX_AGE, path="/")


def _clear_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax")


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
                            f"Der Tipp muss genau die {len(erwartet)} Listen tragen ({'; '.join(teile)}).")
    for slug, wert in seats.items():
        if not isinstance(wert, int) or not (0 <= wert <= reg.seats):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                f"Die Sitzzahl für {slug} muss zwischen 0 und {reg.seats} liegen.")
    summe = sum(seats.values())
    if summe != reg.seats:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"Die Sitze müssen sich auf {reg.seats} summieren — dein Tipp ergibt {summe}.")


def _validate_mayor(tip: dict[str, float] | None) -> None:
    if not tip:
        return
    bekannt = {c.slug for c in mayor.candidates()}
    unbekannt = sorted(set(tip) - bekannt)
    if unbekannt:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"Unbekannte OB-Kandidatur im Tipp: {', '.join(unbekannt)}.")
    for slug, wert in tip.items():
        if not (0 <= wert <= 100):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                f"Der Prozentwert für {slug} muss zwischen 0 und 100 liegen.")
    summe = sum(tip.values())
    if summe > 100.5:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"Die OB-Prozente dürfen zusammen nicht mehr als 100 % ergeben "
                            f"(dein Tipp ergibt {summe:.1f} %).")


# ------------------------------------------------------------------ Öffentlich

@router.get("/api/tipp/setup")
def setup(store: Store = Depends(get_store)) -> PredictionGame:
    _frei()
    return service.setup(store)


@router.post("/api/tipp", status_code=status.HTTP_200_OK)
def beitreten_oder_tippen(payload: PredictionJoinIn, request: Request, response: Response,
                          store: Store = Depends(get_store)) -> PredictionMine:
    """Ohne gültigen Cookie: Beitritt (``name`` Pflicht). Mit gültigem
    Cookie: nur der Tipp wird aktualisiert, ``name`` bleibt unbeachtet —
    umbenennen kann nur der Admin (``PUT …/admin/spieler/{id}``)."""
    _frei()
    prediction_join_limiter.check(request)
    service._check_auto_lock(store)  # noqa: SLF001 — bewusste Wiederverwendung, s. Moduldoc
    reg = register.load()
    token_hash = _token_hash(request)
    player = store.prediction_player_by_token(token_hash) if token_hash else None

    if player is None:
        if not payload.name:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Bitte gib deinen Namen ein.")
        name = _clean_name(payload.name)
        game = store.prediction_game()
        jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
        late_at = jetzt if game["phase"] != "open" else None
        klartext = secrets.token_hex(16)
        try:
            player = store.prediction_player_add(name, _hash(klartext), late_at)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"„{name}“ ist schon vergeben — versuch es z. B. mit „{name} 2“.") from exc
        _set_cookie(response, klartext)
        if late_at:
            store.prediction_log_add(f"{player['name']} ist nach Tipp-Schluss beigetreten (nachgetippt).")

    if payload.seats is not None:
        game = store.prediction_game()
        if player["late_at"] is None and game["phase"] != "open":
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "Die Tippabgabe ist seit dem Tipp-Schluss geschlossen.")
        _validate_seats(payload.seats, reg)
        _validate_mayor(payload.mayor)
        prediction_tip_limiter.check(request)
        store.prediction_tip_set(player["id"], json.dumps(payload.seats, ensure_ascii=False),
                                 json.dumps(payload.mayor, ensure_ascii=False) if payload.mayor else None)
        service.reset()

    # Bei einem NEUEN Beitritt trägt das eingehende Request-Objekt den gerade
    # gesetzten Cookie noch nicht (der wirkt erst beim nächsten Aufruf des
    # Browsers) — deshalb ``player["token_hash"]`` statt ``_token_hash(request)``.
    ergebnis = service.mine(store, player["token_hash"])
    assert ergebnis is not None  # der Spieler wurde in dieser Funktion selbst angelegt oder gefunden
    return ergebnis


@router.get("/api/tipp/me")
def meins(request: Request, probe: str | None = Query(default=None),
         counted: int | None = Query(default=None, ge=0, le=133),
         store: Store = Depends(get_store)) -> PredictionMine:
    _frei()
    token_hash = _token_hash(request)
    if token_hash is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Du bist noch nicht dabei — erst beitreten.")
    ergebnis = service.mine(store, token_hash, probe=probe, counted=counted)
    if ergebnis is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Dieser Tipp gehört zu niemandem mehr — bitte neu beitreten.")
    return ergebnis


@router.delete("/api/tipp/me")
def austreten(request: Request, response: Response, store: Store = Depends(get_store)) -> Ok:
    _frei()
    token_hash = _token_hash(request)
    if token_hash:
        player = store.prediction_player_by_token(token_hash)
        if player:
            store.prediction_player_delete_own(player["id"])
            service.reset()
    _clear_cookie(response)
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
         store: Store = Depends(get_store)) -> PredictionStand:
    _frei()
    ergebnis = service.stand(store, probe=probe, counted=counted)
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
def qr_code(store: Store = Depends(get_store)) -> Response:
    _frei()
    import segno

    link = f"{get_settings().app_base_url}/tipp"
    qr = segno.make(link, error="m")
    puffer = __import__("io").BytesIO()
    qr.save(puffer, kind="png", scale=12, border=2)
    return Response(content=puffer.getvalue(), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


# ------------------------------------------------------------------ Admin (1h) — kein Schalter, s. Moduldoc

def _admin_stand(store: Store) -> PredictionAdminStand:
    reg = register.load()
    results = {r["slug"]: r for r in store.prediction_result()}
    tips = service._parsed(store.prediction_players(include_hidden=True))  # noqa: SLF001

    rows: list[PredictionResultRow] = []
    for p in reg.parties:
        r = results.get(p.slug, {})
        avg = service._avg(tips, "seats", p.slug)  # noqa: SLF001
        veroeffentlicht = r.get("published_seats")
        exakt = sum(1 for t in tips if t["seats"] and t["seats"].get(p.slug) is not None
                   and veroeffentlicht is not None and t["seats"][p.slug] == veroeffentlicht)
        rows.append(PredictionResultRow(
            slug=p.slug, seats=r.get("seats"), pct=None, source=r.get("source") or "manuell",
            avg_tip=avg, exact_count=exakt, published_seats=veroeffentlicht, published_pct=None,
            published_source=r.get("published_source"), published_at=r.get("published_at"),
        ))
    for c in mayor.candidates():
        slug = f"ob:{c.slug}"
        r = results.get(slug, {})
        avg = service._avg(tips, "mayor", c.slug)  # noqa: SLF001
        rows.append(PredictionResultRow(
            slug=slug, seats=None, pct=r.get("pct"), source=r.get("source") or "manuell",
            avg_tip=avg, exact_count=0, published_seats=None, published_pct=r.get("published_pct"),
            published_source=r.get("published_source"), published_at=r.get("published_at"),
        ))
    log = [f"{eintrag['at']} · {eintrag['text']}" for eintrag in store.prediction_log(limit=30)]
    return PredictionAdminStand(game=service.setup(store), results=rows, log=log)


@router.get("/api/tipp/admin/stand")
def admin_stand(_admin: dict = Depends(require_admin), store: Store = Depends(get_store)) -> PredictionAdminStand:
    return _admin_stand(store)


@router.put("/api/tipp/admin/ergebnis")
def ergebnis_eintragen(zeilen: list[PredictionResultLineIn], _admin: dict = Depends(require_admin),
                       store: Store = Depends(get_store)) -> PredictionAdminStand:
    store.prediction_result_set([{"slug": z.slug, "seats": z.seats, "pct": z.pct} for z in zeilen], source="manuell")
    service.reset()
    return _admin_stand(store)


@router.post("/api/tipp/admin/abfragen")
def jetzt_abfragen(_admin: dict = Depends(require_admin), store: Store = Depends(get_store)) -> PredictionAdminStand:
    """„Jetzt abfragen": die Live-Zahlen der Ratswahl UND der OB-Wahl in den
    Entwurf übernehmen — NICHT veröffentlicht, das bleibt ein eigener Schritt."""
    from ..election import service as election_service

    night = election_service.live()
    zeilen: list[dict] = []
    for p in night["parties"]:
        wert = p["seats"] if p["seats"] is not None else p["projected_seats"]
        if wert is not None:
            zeilen.append({"slug": p["slug"], "seats": wert})
    ob = mayor.fetch()
    for c in ob.candidates:
        if c.share_pct is not None:
            zeilen.append({"slug": f"ob:{c.slug}", "pct": c.share_pct})
    if zeilen:
        store.prediction_result_set(zeilen, source="votemanager")
        listen = sum(1 for z in zeilen if "seats" in z)
        store.prediction_log_add(f"Votemanager abgefragt · {listen} Listen, {len(zeilen) - listen} "
                                 f"OB-Kandidaturen in den Entwurf übernommen.")
        service.reset()
    return _admin_stand(store)


@router.post("/api/tipp/admin/veroeffentlichen")
def veroeffentlichen(_admin: dict = Depends(require_admin), store: Store = Depends(get_store)) -> PredictionAdminStand:
    n = store.prediction_result_publish()
    store.prediction_log_add(f"Entwurf veröffentlicht · {n} Zeilen live.")
    service.reset()
    return _admin_stand(store)


@router.post("/api/tipp/admin/verwerfen")
def verwerfen(_admin: dict = Depends(require_admin), store: Store = Depends(get_store)) -> PredictionAdminStand:
    store.prediction_result_discard()
    store.prediction_log_add("Entwurf verworfen · der Stand vor der letzten Eingabe ist wiederhergestellt.")
    service.reset()
    return _admin_stand(store)


@router.put("/api/tipp/admin/phase")
def phase_setzen(payload: PredictionPhaseIn, _admin: dict = Depends(require_admin),
                 store: Store = Depends(get_store)) -> PredictionAdminStand:
    felder: dict[str, object] = {"phase": payload.phase}
    if payload.phase == "locked":
        game = store.prediction_game()
        if game["phase"] == "open":
            felder["locked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            felder["locked_reason"] = "admin"
    if payload.late_scored is not None:
        felder["late_scored"] = 1 if payload.late_scored else 0
    store.prediction_game_set(**felder)
    text = {"open": "Spiel wieder geöffnet", "locked": "Tippen manuell geschlossen", "final": "Endstand gesetzt"}[payload.phase]
    store.prediction_log_add(text)
    service.reset()
    return _admin_stand(store)


@router.put("/api/tipp/admin/spieler/{player_id}")
def spieler_bearbeiten(player_id: int, payload: PredictionPlayerIn, _admin: dict = Depends(require_admin),
                       store: Store = Depends(get_store)) -> Ok:
    name = _clean_name(payload.name) if payload.name is not None else None
    store.prediction_player_update(player_id, name=name, hidden=payload.hidden)
    service.reset()
    return Ok(ok=True)
