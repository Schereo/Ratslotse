"""Wahlabend zur Ratswahl 13.09.2026 — ``GET /api/wahlabend``.

Öffentlich (die Zahlen sind es auch: Open Data der Stadt), aber hinter dem
Feature-Schalter ``wahlabend``: Ohne ihn antwortet der Endpunkt 404, damit die
Seite bis zum Wahlabend dunkel bleiben kann und danach ohne Deploy wieder.

``?probe=1`` liefert die Generalprobe (Zahlen der Vorwahl im heutigen
Register), ``&counted=N`` davon nur die ersten N Wahlbezirke ausgezählt.

Dazu ``GET /api/wahlabend/bild.png``: derselbe Stand als teilbares Bild —
und ``GET /api/wahlabend/karte.png?list=…[&area=…[&position=…]]``: die
Karte einer Liste, einer Liste im Wahlbereich oder einer Person.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from kern import features
from kern.store import Store

from ..antworten import (
    WAHLABEND_KARTE_PNG,
    WAHLABEND_PNG,
    ElectionList,
    ElectionListItem,
    ElectionNight,
    MayorCandidate,
    MayorElectionInfo,
    MayorNight,
)
from ..deps import get_store, optional_user
from ..election import archive, elections, image, mayor, service, share
from ..prediction import rounds
from ..election import votemanager

router = APIRouter(tags=["wahlabend"])

#: So lange gilt ein gerendertes Bild. Kürzer lohnt nicht — die Zahlen des
#: Votemanagers ändern sich ohnehin nur im Minutentakt.
BILD_TTL = 60.0

_bild_lock = threading.Lock()
_bilder: dict[tuple[str, int | None, str, str], tuple[float, bytes]] = {}


def _frei() -> None:
    if not features.an("wahlabend"):
        raise HTTPException(status_code=404, detail="Der Wahlabend ist noch nicht freigeschaltet.")


def _stand(probe: str | None, counted: int | None) -> ElectionNight:
    """Generalprobe oder Abruf.

    Jeder nicht-leere Wert schaltet die Probe ein — bis 09/2026 musste dort
    genau ``2021`` stehen. Das war der Name der Vorwahl im Parameter, und bei
    der nächsten Kommunalwahl hätte ihn niemand mehr erraten. Alte Links mit
    ``?probe=2021`` funktionieren unverändert weiter.
    """
    return service.probe(counted) if probe else service.live()


@router.get("/api/wahlabend")
def wahlabend(
    probe: str | None = Query(default=None, description="gesetzt = Generalprobe mit den Zahlen der Vorwahl (jeder Wert)"),
    counted: int | None = Query(default=None, ge=0, le=500, description="Generalprobe: nur die ersten N Wahlbezirke ausgezählt"),
    wahl: str | None = Query(default=None, description="Slug einer gelaufenen Wahl — ihr eingefrorener Stand, ohne Abruf"),
) -> ElectionNight:
    """Der Wahlabend: live, als Generalprobe oder als Rückblick.

    ``?wahl=<slug>`` liefert den eingefrorenen Stand einer gelaufenen Wahl aus
    dem Repo (``kommunalwahl/referenz-…``). Das ist der Punkt, an dem eine
    Rückblick-Seite unabhängig vom Votemanager wird: Seine Adressen tragen den
    Wahltag im Pfad und wandern irgendwann ins Archiv.
    """
    _frei()
    if wahl:
        bild = archive.night(wahl)
        if bild is None:
            raise HTTPException(status_code=404,
                                detail="Von dieser Wahl liegt kein vollständiger Stand vor.")
        return bild
    return _stand(probe, counted)


@router.get("/api/wahlen")
def wahlen(user: dict | None = Depends(optional_user), store: Store = Depends(get_store)) -> ElectionList:
    """Alle Wahlen, die wir zeigen — die nächste zuerst, dann rückwärts.

    Öffentlich wie die Zahlen selbst. Entwürfe bleiben draußen; sie sind das
    Gegenstück zum Feature-Schalter für eine einzelne Wahl.
    """
    _frei()
    fokus = elections.focus()
    zeilen: list[ElectionListItem] = []
    for w in sorted(elections.all().values(), key=lambda w: (w.date, w.slug), reverse=True):
        if w.status == "entwurf":
            continue
        zeilen.append(ElectionListItem(
            slug=w.slug, short_title=w.short_title, title=w.title, date=w.date,
            polls_close=w.polls_close.isoformat(), kind=w.kind, status=w.status,
            path=_pfad_zu(w), summary=archive.summary(w), focus=w.slug == fokus.slug,
            tipp_path=_tipp_pfad(store, w, user),
        ))
    return ElectionList(elections=zeilen)


def _tipp_pfad(store: Store, w: elections.Election, user: dict | None) -> str:
    """Der Weg zum Tippspiel dieser Wahl — oder nichts.

    Nichts heißt: Es gibt keine Runde, oder sie steht nur Angemeldeten offen
    und hier fragt niemand Angemeldetes. **Die Runde wird hier NICHT angelegt**
    — eine Übersicht, die durch bloßes Ansehen vier Spielzeilen erzeugt, wäre
    eine Nebenwirkung, die niemand bestellt hat. Angelegt wird sie beim ersten
    Aufruf von ``/tipp``.
    """
    if not features.an("tippspiel"):
        return ""
    runde = rounds.get(w.slug)
    if runde is None:
        return ""
    zeile = store.prediction_spiel_zeile(runde.slug)
    if zeile is None and w.polls_close + elections.FOKUS_NACHHER < datetime.now(timezone.utc):
        # Auf eine gelaufene Wahl kann man nicht mehr tippen. Hat jemand es
        # damals getan, bleibt die Runde verlinkt (die Zeile ist da) — nur neu
        # angeboten wird sie nicht. Die Ratswahl 2021 bekäme sonst 2026 ein
        # Tippspiel, auf das niemand mehr etwas setzen kann.
        return ""
    sichtbarkeit = zeile["visibility"] if zeile else runde.visibility
    if sichtbarkeit == "konto" and user is None:
        return ""
    return rounds.public_path(runde)


def _pfad_zu(w: elections.Election) -> str:
    """Wo diese Wahl zu sehen ist — leer, wenn es keine Seite gibt.

    Die Ratswahl 2021 ist so ein Fall: Ihre Zahlen liegen im Repo, aber ihre
    Kandidatenlisten nicht. Sie steht deshalb in der Übersicht mit ihrem
    Ergebnis und ohne Link — ein Link auf eine Seite, die es nicht gibt, wäre
    schlechter als keiner.
    """
    if w.status != "rueckblick" and (w.slug == elections.active().slug or w.first_round):
        return elections.path_of(w)
    # Eine gelaufene Wahl braucht keine eigene Seite: Es IST der Wahlabend,
    # nur mit eingefrorenen Zahlen. `?wahl=` statt eines Pfadsegments, weil
    # der App-Export keine dynamischen Segmente kann (web/frontend/CLAUDE.md).
    return f"/wahlabend?wahl={w.slug}" if archive.verfuegbar(w) else ""


# ------------------------------------------------------------------ OB-Wahl und Stichwahl

def _mayor_night(w: elections.Election, probe: str | None, counted: int | None) -> MayorNight:
    """Ein Stand einer Mehrheitswahl als Antwort.

    ``probe`` nimmt echte Zahlen statt des Abrufs: für den ersten Wahlgang die
    OB-Wahl 2021, für eine Stichwahl den ersten Wahlgang selbst (eingefroren
    in ``kommunalwahl/referenz-2026/``). Der Parameter heißt aus Gewohnheit
    ``2021``; jeder Wert außer ``None`` schaltet die Probe ein.
    """
    stand = mayor.probe(counted, w) if probe else mayor.fetch(w=w)
    vorher: dict[str, float | None] = {}
    if w.first_round:
        erster = mayor.parse(mayor.probe_payload(w)[0], mayor.candidates(w))
        vorher = {c.slug: c.share_pct for c in erster.candidates} if erster else {}
    return MayorNight(
        dataset="probe" if probe else "live",
        phase=stand.phase,
        election=MayorElectionInfo(
            slug=w.slug, title=w.title, short_title=w.short_title, date=w.date,
            polls_close=w.polls_close.isoformat(), is_runoff=bool(w.first_round),
            presentation_url=mayor.base_url(w) + votemanager.PRESENTATION_PATH,
        ),
        reports_expected=stand.reports_expected, reports_received=stand.reports_received,
        turnout_pct=stand.turnout_pct, valid_votes=stand.valid_votes,
        invalid_ballots=stand.invalid_ballots,
        candidates=[MayorCandidate(slug=c.slug, name=c.name, party=c.party, votes=c.votes,
                                   share_pct=c.share_pct, first_round_pct=vorher.get(c.slug),
                                   color=c.color, color_dark=c.color_dark)
                    for c in stand.candidates],
        runoff=list(stand.runoff),
        elected=_gewaehlt(stand),
        fetched_at=stand.fetched_at, ok=stand.ok, error=stand.error, notes=list(stand.notes),
    )


def _gewaehlt(stand: mayor.MayorResult) -> str | None:
    """Wer gewählt ist — nur bei fertiger Auszählung und ohne Stichwahl.

    Bei einer Stichwahl nennt ``gewaehlte_kandidaten`` die beiden, die weiter
    sind (das steht in ``runoff``); daraus eine „gewählte Person" zu machen,
    wäre schlicht falsch.
    """
    if stand.phase != "complete" or stand.runoff:
        return None
    beste = max(stand.candidates, key=lambda c: c.votes or 0, default=None)
    return beste.slug if beste is not None and (beste.votes or 0) > 0 else None


@router.get("/api/wahlabend/ob")
def ob_wahl(probe: str | None = Query(default=None, description="gesetzt = Generalprobe mit den Zahlen der Vorwahl (jeder Wert)"),
            counted: int | None = Query(default=None, ge=0, le=133,
                                        description="Generalprobe: nur die ersten N Wahlbezirke ausgezählt")) -> MayorNight:
    """Die OB-Wahl für sich — hinter dem Schalter ``wahlabend`` (nicht
    ``tippspiel``): Sie ist Teil des Wahlabends, nicht nur des Tippspiels.

    Immer der ERSTE Wahlgang; die Stichwahl hat ihren eigenen Pfad. Daran
    hängt der Vergleich des Tippspiels, und der darf sich am 27.09. nicht
    unter der Hand verschieben.
    """
    _frei()
    return _mayor_night(mayor.wahl(), probe, counted)


@router.get("/api/wahlabend/stichwahl")
def stichwahl(probe: str | None = Query(default=None, description="gesetzt = Generalprobe mit den Zahlen des ersten Wahlgangs"),
              counted: int | None = Query(default=None, ge=0, le=133,
                                          description="Generalprobe: nur die ersten N Wahlbezirke ausgezählt")) -> MayorNight:
    """Die Stichwahl — 404, solange keine im Kalender steht.

    Am 13.09.2026 hat niemand die absolute Mehrheit erreicht; am 27.09. läuft
    deshalb die Stichwahl zwischen Ulf Prange (SPD) und Jascha Rohr (GRÜNE).
    Ihre Wahl-Id beim Votemanager gibt es heute noch nicht — sie wird zur
    Laufzeit in ``termin.json`` gesucht (``mayor.resolve_ids``). Bis dahin
    antwortet dieser Pfad mit ``phase: "before"`` und einem Vermerk, nicht mit
    einem Fehler: Eine Seite, die auf den Abend wartet, ist keine kaputte.
    """
    _frei()
    w = elections.runoff()
    if w is None:
        raise HTTPException(status_code=404, detail="Es steht keine Stichwahl an.")
    return _mayor_night(w, probe, counted)


@router.get("/api/wahlabend/bild.png", response_class=Response, responses=WAHLABEND_PNG)
def wahlabend_bild(
    feld: str | None = Query(default=None, pattern="^(seats|projected_seats)$",
                             description="„seats“ = ausgezählter Stand, „projected_seats“ = Hochrechnung; Vorgabe je Phase"),
    probe: str | None = Query(default=None, description="gesetzt = Generalprobe mit den Zahlen der Vorwahl (jeder Wert)"),
    counted: int | None = Query(default=None, ge=0, le=500, description="Generalprobe: nur die ersten N Wahlbezirke ausgezählt"),
) -> Response:
    """Der Stand als Bild zum Teilen (PNG, 1200×630) — öffentlich wie die
    Seite selbst; Messenger und soziale Netze holen es ohne Konto ab.

    Ohne ``feld`` zeigt das Bild während der Auszählung die Hochrechnung
    (interessanter als ein Zwischenstand aus 40 Bezirken) und sonst den
    ausgezählten Stand.
    """
    _frei()
    daten = _stand(probe, counted)
    gewaehlt: image.SeatField = "seats"
    if feld == "projected_seats" or (feld is None and daten["phase"] == "counting"):
        gewaehlt = "projected_seats"

    schluessel = (daten["dataset"], counted, gewaehlt, daten["computed_at"])
    jetzt = time.monotonic()
    with _bild_lock:
        treffer = _bilder.get(schluessel)
        if treffer and jetzt - treffer[0] < BILD_TTL:
            png = treffer[1]
        else:
            png = None
    if png is None:
        png = image.render(daten, gewaehlt)
        with _bild_lock:
            # Ein paar Schlüssel reichen (zwei Felder, Live und Generalprobe);
            # der älteste fliegt, sonst wächst der Speicher über den Abend.
            while len(_bilder) >= 8:
                del _bilder[min(_bilder, key=lambda k: _bilder[k][0])]
            _bilder[schluessel] = (jetzt, png)
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=60"})


#: Karten gibt es viele (16 Listen × 6 Wahlbereiche × bis zu 10 Plätze); der
#: Zwischenspeicher hält die zuletzt geteilten, nicht alle.
KARTEN_MAX = 64
_karten: dict[tuple[str, int | None, str, int | None, int | None, str, bool, str], tuple[float, bytes]] = {}


@router.get("/api/wahlabend/karte.png", response_class=Response, responses=WAHLABEND_KARTE_PNG)
def wahlabend_karte(
    list: str = Query(pattern="^[a-z0-9-]{1,40}$", description="Slug der Liste, z. B. „gruene“"),
    area: int | None = Query(default=None, ge=1, le=20, description="Wahlbereich (1–6): die Liste dort"),
    position: int | None = Query(default=None, ge=1, le=99, description="Listenplatz im Wahlbereich: die Person"),
    format: str = Query(default="beitrag", pattern="^(beitrag|story|quer)$",
                        description="„beitrag“ = 1080×1350 (4:5), „story“ = 1080×1920 (9:16), „quer“ = 1200×630"),
    compare: bool = Query(default=True, description="false = ohne den Abstand zur Vorwahl (Listenkarte)"),
    probe: str | None = Query(default=None, description="gesetzt = Generalprobe mit den Zahlen der Vorwahl (jeder Wert)"),
    counted: int | None = Query(default=None, ge=0, le=500, description="Generalprobe: nur die ersten N Wahlbezirke ausgezählt"),
) -> Response:
    """Die Karte zum Teilen (PNG): wie eine Liste, eine Liste im Wahlbereich
    oder eine Person abgeschnitten hat — mit Lotti, die den Wählenden dankt.
    ``format`` wählt Beitrag (4:5), Story (9:16) oder quer; ``position``
    braucht ``area``; eine Kombination, die es nicht gibt, antwortet 404.
    """
    _frei()
    daten = _stand(probe, counted)
    auswahl = share.select(daten, list, area, position)
    if auswahl is None:
        raise HTTPException(status_code=404, detail="Diese Liste, diesen Wahlbereich oder diesen Listenplatz gibt es nicht.")

    schluessel = (daten["dataset"], counted, list, area, position, format, compare, daten["computed_at"])
    jetzt = time.monotonic()
    with _bild_lock:
        treffer = _karten.get(schluessel)
        png = treffer[1] if treffer and jetzt - treffer[0] < BILD_TTL else None
    if png is None:
        png = share.render(daten, auswahl, format, compare)
        with _bild_lock:
            while len(_karten) >= KARTEN_MAX:
                del _karten[min(_karten, key=lambda k: _karten[k][0])]
            _karten[schluessel] = (jetzt, png)
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=60"})
