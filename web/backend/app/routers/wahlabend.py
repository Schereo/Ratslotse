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

import logging
import threading
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status

from pydantic import BaseModel

from kern import features
from kern.store import Store

from ..antworten import (
    WAHLABEND_KARTE_PNG,
    WAHLABEND_PNG,
    ElectionCandidateRanking,
    ElectionDistrictList,
    ElectionList,
    ElectionListItem,
    ElectionNight,
    ElectionWatchEntry,
    ElectionWatchList,
    MayorCandidate,
    MayorDistrictEntry,
    MayorDistrictList,
    MayorElectionInfo,
    MayorHistoryPoint,
    MayorNight,
    RunoffProjection,
)
from ..deps import get_store, optional_user, require_active
from ..election import archive, candidates, elections, history, image, mayor, runoff_model, service, share
from ..prediction import rounds

_log = logging.getLogger("ratslotse.web.wahlabend")
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
    return _night(probe, counted, wahl)


def _night(probe: str | None, counted: int | None, wahl: str | None) -> ElectionNight:
    """Rückblick aus dem Repo, sonst Generalprobe oder Abruf."""
    if wahl:
        bild = archive.night(wahl)
        if bild is None:
            raise HTTPException(status_code=404,
                                detail="Von dieser Wahl liegt kein vollständiger Stand vor.")
        return bild
    return _stand(probe, counted)


@router.get("/api/wahlabend/wahlbezirke")
def wahlabend_wahlbezirke(
    probe: str | None = Query(default=None, description="gesetzt = Generalprobe mit den Zahlen der Vorwahl (jeder Wert)"),
    counted: int | None = Query(default=None, ge=0, le=500, description="Generalprobe: nur die ersten N Wahlbezirke ausgezählt"),
    wahl: str | None = Query(default=None, description="Slug einer gelaufenen Wahl — ihr eingefrorener Stand, ohne Abruf"),
) -> ElectionDistrictList:
    """Derselbe Stand je Wahlbezirk — die Ebene unter den Wahlbereichen.

    Öffentlich wie der Wahlabend selbst, hinter demselben Schalter. Eigener
    Endpunkt, weil die Seite die 133 Bezirke erst braucht, wenn jemand die
    Karte aufmacht (s. ``ElectionDistrictList``).
    """
    _frei()
    if wahl:
        bild = archive.districts(wahl)
        if bild is None:
            raise HTTPException(status_code=404,
                                detail="Von dieser Wahl liegt kein vollständiger Stand vor.")
        return bild
    reg = service.load_register()
    if probe:
        return service.districts(reg, service.probe_snapshot(reg, service.load_reference(), counted), "probe")
    return service.districts(reg, votemanager.fetch(), "live")


@router.get("/api/wahlabend/kandidaten")
def wahlabend_kandidaten(
    probe: str | None = Query(default=None, description="gesetzt = Generalprobe mit den Zahlen der Vorwahl (jeder Wert)"),
    counted: int | None = Query(default=None, ge=0, le=500, description="Generalprobe: nur die ersten N Wahlbezirke ausgezählt"),
    wahl: str | None = Query(default=None, description="Slug einer gelaufenen Wahl — ihr eingefrorener Stand, ohne Abruf"),
    sort: str = Query(default="votes", pattern="^(votes|party|area|name)$",
                      description="votes = nach Personenstimmen, party = in Stimmzettel-Reihenfolge, area = je Wahlbereich, name"),
    party: str | None = Query(default=None, description="nur diese Liste (Slug)"),
    area: int | None = Query(default=None, ge=1, le=20, description="nur dieser Wahlbereich (Nummer)"),
) -> ElectionCandidateRanking:
    """Alle Kandidaturen als eine Rangliste — sortiert und gefiltert vom Server.

    Öffentlich wie der Wahlabend selbst, hinter demselben Schalter. Der Rang
    ist stadtweit und bleibt es auch gefiltert; was die beiden Anteile
    bedeuten, steht in ``election/candidates.py``.
    """
    _frei()
    night = _night(probe, counted, wahl)
    if party is not None and party not in {p["slug"] for p in night["parties"]}:
        raise HTTPException(status_code=404, detail="Diese Liste tritt bei dieser Wahl nicht an.")
    if area is not None and area not in {a["number"] for a in night["areas"]}:
        raise HTTPException(status_code=404, detail="Diesen Wahlbereich gibt es bei dieser Wahl nicht.")
    return candidates.ranking(night, sort=sort, party=party, area=area)


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
        tipp, gesperrt = _tipp_pfad(store, w, user)
        zeilen.append(ElectionListItem(
            slug=w.slug, short_title=w.short_title, title=w.title, date=w.date,
            polls_close=w.polls_close.isoformat(), kind=w.kind, status=w.status,
            path=_pfad_zu(w), summary=archive.summary(w), focus=w.slug == fokus.slug,
            tipp_path=tipp, tipp_locked=gesperrt, top=archive.top(w),
        ))
    return ElectionList(elections=zeilen)


def _tipp_pfad(store: Store, w: elections.Election, user: dict | None) -> tuple[str, bool]:
    """Der Weg zum Tippspiel dieser Wahl — oder nichts; dazu, ob es eines gäbe.

    Das zweite Feld ist das ehrliche Signal für den Registrier-Anreiz: „Es
    gibt ein Tippspiel, aber nicht für dich." Ohne diese Angabe müsste die
    Seite raten, ob sich ein Konto hier lohnt.

    Nichts heißt: Es gibt keine Runde, oder sie steht nur Angemeldeten offen
    und hier fragt niemand Angemeldetes. **Die Runde wird hier NICHT angelegt**
    — eine Übersicht, die durch bloßes Ansehen vier Spielzeilen erzeugt, wäre
    eine Nebenwirkung, die niemand bestellt hat. Angelegt wird sie beim ersten
    Aufruf von ``/tipp``.
    """
    if not features.an("tippspiel"):
        return "", False
    runde = rounds.get(w.slug)
    if runde is None:
        return "", False
    zeile = store.prediction_spiel_zeile(runde.slug)
    vorbei = (w.polls_close + elections.FOKUS_NACHHER < datetime.now(timezone.utc)
              or archive.summary(w) is not None)
    if zeile is None and vorbei:
        # Auf eine gelaufene Wahl kann man nicht mehr tippen. Hat jemand es
        # damals getan, bleibt die Runde verlinkt (die Zeile ist da) — nur neu
        # angeboten wird sie nicht. Die Ratswahl 2021 bekäme sonst 2026 ein
        # Tippspiel, auf das niemand mehr etwas setzen kann — und die OB-Wahl
        # vom 13.09. stand zwei Tage danach noch als „Tippspiel mit Konto" da,
        # obwohl ihr Ergebnis längst feststand: Ein Ergebnis im Repo heißt
        # vorbei, egal wie frisch.
        return "", False
    sichtbarkeit = zeile["visibility"] if zeile else runde.visibility
    if sichtbarkeit == "konto" and user is None:
        return "", True
    return rounds.public_path(runde), False


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
    hochrechnung: RunoffProjection | None = None
    if w.first_round:
        known = mayor.candidates(w)
        erster = mayor.parse(mayor.probe_payload(w)[0], known)
        vorher = {c.slug: c.share_pct for c in erster.candidates} if erster else {}
        hochrechnung = _runoff_projection(stand, known, w)
    antwort = MayorNight(
        history=[], lead_changes=[],
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
    if hochrechnung is not None:
        antwort["projection"] = hochrechnung
    if w.first_round:
        try:
            antwort["history"] = _probe_mayor_history(w, counted) if probe else history.record_mayor(w.slug, antwort)
            antwort["lead_changes"] = history.lead_changes(antwort["history"])
        except Exception:
            # Der Verlauf ist Zugabe; er darf den Abend nicht mitnehmen.
            _log.exception("Stichwahl: der Verlauf ließ sich nicht fortschreiben.")
            antwort["history"], antwort["lead_changes"] = [], []
    return antwort


def _probe_mayor_history(w: elections.Election, counted: int | None) -> list[MayorHistoryPoint]:
    """Der Verlauf der Generalprobe: Stände in Zehnerschritten bis
    ``counted``, ab 18:00 Uhr alle 15 Minuten — wie bei der Ratswahl."""
    known = mayor.candidates(w)
    ziel = 133 if counted is None else max(0, min(133, counted))
    stops = list(range(10, ziel + 1, 10))
    if ziel > 0 and (not stops or stops[-1] != ziel):
        stops.append(ziel)
    out: list[MayorHistoryPoint] = []
    for i, n in enumerate(stops):
        stand = mayor.probe(n, w)
        proj = _runoff_projection(stand, known, w)
        at = (service.PROBE_START + i * service.PROBE_STEP).astimezone(timezone.utc).isoformat(timespec="seconds")
        shares = {c.slug: c.share_pct for c in stand.candidates if c.votes and c.share_pct is not None}
        out.append(MayorHistoryPoint(
            at=at, reports_received=stand.reports_received, shares=shares,
            projected_shares=dict(proj["shares"]) if proj else {},
            chance_pct=proj["chance_pct"] if proj else None,
            leader=history.mayor_leader(shares, {c.slug: c.votes for c in stand.candidates}),
        ))
    return out


def _runoff_projection(stand: mayor.MayorResult, known: tuple[mayor.MayorCandidate, ...],
                       w: elections.Election) -> RunoffProjection | None:
    """Die Hochrechnung zum Stand — nur mit genau zwei Kandidaturen und
    sobald ein Bezirk gemeldet hat (``runoff_model.project``)."""
    if len(known) != 2 or not stand.districts:
        return None
    vorher = mayor.probe_districts(None, known, w)
    p = runoff_model.project(stand.districts, vorher, (known[0].slug, known[1].slug))
    if p is None:
        return None
    return RunoffProjection(
        shares=p.shares, projected_votes=p.projected_votes, leader=p.leader, lead_votes=p.lead_votes,
        chance_pct=p.chance_pct, counted_ballot=p.counted_ballot, counted_postal=p.counted_postal,
        open_ballot=p.open_ballot, open_postal=p.open_postal, decided=p.decided,
        actual_leader=p.actual_leader, actual_lead_votes=p.actual_lead_votes,
        open_votes_max=p.open_votes_max, caveats=list(p.caveats),
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


# ------------------------------------------------------------------ Beobachtungsliste

#: So heißt eine gemerkte Kandidatur in der Merkliste-Tabelle. Die Tabelle
#: gehört sonst den Ratsinhalten (Sitzung, TOP, Beschluss); eine Kandidatur
#: hat weder Sitzung noch Vorlage, deshalb bleibt sie aus der Ratsliste
#: heraus (``routers/bookmarks.py`` überspringt diese Art) und wird nur hier
#: bedient. Der Schlüssel ist das Tripel, das eine Kandidatur eindeutig macht.
WATCH_KIND = "candidate"


def _watch_key(election: str, party: str, area: int, position: int) -> str:
    return f"candidate:{election}:{party}:{area}:{position}"


def _watch_parse(key: str) -> tuple[str, str, int, int] | None:
    teile = key.split(":")
    if len(teile) != 5 or teile[0] != "candidate" or not teile[3].isdigit() or not teile[4].isdigit():
        return None
    return teile[1], teile[2], int(teile[3]), int(teile[4])


class WatchIn(BaseModel):
    election: str
    party: str
    area: int
    position: int


@router.get("/api/wahlabend/beobachtet")
def wahlabend_beobachtet(
    wahl: str | None = Query(default=None, description="Slug der Wahl; ohne ihn die Wahl im Fokus"),
    probe: str | None = Query(default=None, description="gesetzt = Generalprobe"),
    counted: int | None = Query(default=None, ge=0, le=500),
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> ElectionWatchList:
    """Die gemerkten Kandidaturen dieses Kontos, mit dem Stand von jetzt.

    Angemeldet, weil es die eigene Liste ist. Eine Antwort statt 383 Zeilen
    für fünf Namen — die App soll nicht die ganze Rangliste holen müssen.
    """
    _frei()
    slug = wahl or elections.focus().slug
    night = _night(probe, counted, wahl)
    zeilen = {(z["party"], z["area"], z["position"]): z
              for z in candidates.ranking(night)["rows"]}
    eintraege: list[ElectionWatchEntry] = []
    for row in store.get_bookmarks(user["id"]):
        if row.get("kind") != WATCH_KIND:
            continue
        teile = _watch_parse(row.get("target_key") or "")
        if teile is None or teile[0] != slug:
            continue
        _, partei, bereich, platz = teile
        eintraege.append(ElectionWatchEntry(
            id=row["id"], election=slug, party=partei, area=bereich, position=platz,
            name=row.get("title") or "", subtitle=row.get("subtitle") or "",
            row=zeilen.get((partei, bereich, platz)),
        ))
    # Wer vorn liegt, steht oben; wer gar keine Zeile hat, ans Ende.
    eintraege.sort(key=lambda e: (e["row"] is None, e["row"]["rank"] if e["row"] and e["row"]["rank"] else 10 ** 6))
    return ElectionWatchList(election=night["election"], entries=eintraege)


@router.post("/api/wahlabend/beobachtet", status_code=status.HTTP_201_CREATED)
def wahlabend_beobachten(
    payload: WatchIn = Body(...),
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> ElectionWatchEntry:
    """Eine Kandidatur merken — quer über alle Listen, das ist der Punkt."""
    _frei()
    night = _night(None, None, payload.election if payload.election != elections.focus().slug else None)
    zeile = next((z for z in candidates.ranking(night)["rows"]
                  if z["party"] == payload.party and z["area"] == payload.area
                  and z["position"] == payload.position), None)
    if zeile is None:
        raise HTTPException(status_code=404, detail="Diese Kandidatur gibt es bei dieser Wahl nicht.")
    row = store.add_bookmark(
        user["id"], kind=WATCH_KIND,
        target_key=_watch_key(payload.election, payload.party, payload.area, payload.position),
        title=zeile["name"],
        subtitle=f"{zeile['party_short']} · Wahlbereich {zeile['area_roman']} · Platz {zeile['position']}",
    )
    return ElectionWatchEntry(
        id=row["id"], election=payload.election, party=payload.party,
        area=payload.area, position=payload.position,
        name=zeile["name"], subtitle=row.get("subtitle") or "", row=zeile,
    )


@router.delete("/api/wahlabend/beobachtet/{merker_id}", status_code=status.HTTP_204_NO_CONTENT)
def wahlabend_nicht_mehr_beobachten(
    merker_id: int,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> Response:
    """Einen Merker entfernen. 404, wenn er einem anderen Konto gehört —
    dieselbe Antwort wie „gibt es nicht", damit die Kennung nichts verrät."""
    _frei()
    vorhanden = store.get_bookmark_for_owner(user["id"], merker_id)
    if vorhanden is None or vorhanden.get("kind") != WATCH_KIND:
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    store.delete_bookmark(user["id"], merker_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/wahlabend/stichwahl/bezirke")
def stichwahl_bezirke(probe: str | None = Query(default=None, description="gesetzt = Generalprobe mit den Zahlen des ersten Wahlgangs"),
                      counted: int | None = Query(default=None, ge=0, le=133,
                                                  description="Generalprobe: nur die ersten N Wahlbezirke gemeldet")) -> MayorDistrictList:
    """Die 133 Wahlbezirke der Stichwahl mit ihrem Stand — und je Bezirk
    dieselben zwei Kandidaturen im ersten Wahlgang als Vergleich.

    Öffentlich wie die Stichwahl, hinter demselben Schalter. Das ist der
    Eingang für Karte und Hochrechnung (docs/plan-stichwahl-spannung.md).
    """
    _frei()
    w = elections.runoff()
    if w is None:
        raise HTTPException(status_code=404, detail="Es steht keine Stichwahl an.")
    stand = mayor.probe(counted, w) if probe else mayor.fetch(w=w)
    known = mayor.candidates(w)
    vorher = {d.number: d.votes for d in mayor.probe_districts(None, known, w)}
    zeilen = [MayorDistrictEntry(
        number=d.number, name=d.name, area=d.area, postal=d.postal, counted=d.counted,
        eligible=d.eligible, voters=d.voters, valid_votes=d.valid_votes,
        votes=dict(d.votes), first_round=dict(vorher.get(d.number, {})),
    ) for d in stand.districts]
    return MayorDistrictList(
        dataset="probe" if probe else "live", phase=stand.phase,
        election=MayorElectionInfo(
            slug=w.slug, title=w.title, short_title=w.short_title, date=w.date,
            polls_close=w.polls_close.isoformat(), is_runoff=bool(w.first_round),
            presentation_url=mayor.base_url(w) + votemanager.PRESENTATION_PATH,
        ),
        total=len(zeilen), counted=sum(1 for z in zeilen if z["counted"]), districts=zeilen,
    )


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
