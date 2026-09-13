"""Wahlabend zur Ratswahl 13.09.2026 — ``GET /api/wahlabend``.

Öffentlich (die Zahlen sind es auch: Open Data der Stadt), aber hinter dem
Feature-Schalter ``wahlabend``: Ohne ihn antwortet der Endpunkt 404, damit die
Seite bis zum Wahlabend dunkel bleiben kann und danach ohne Deploy wieder.

``?probe=2021`` liefert die Generalprobe (Zahlen von 2021 im Register von
2026), ``&counted=N`` davon nur die ersten N Wahlbezirke ausgezählt.

Dazu ``GET /api/wahlabend/bild.png``: derselbe Stand als teilbares Bild —
und ``GET /api/wahlabend/karte.png?list=…[&area=…[&position=…]]``: die
Karte einer Liste, einer Liste im Wahlbereich oder einer Person.
"""
from __future__ import annotations

import threading
import time

from fastapi import APIRouter, HTTPException, Query, Response

from kern import features

from ..antworten import WAHLABEND_KARTE_PNG, WAHLABEND_PNG, ElectionNight
from ..election import image, service, share

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
    return service.probe(counted) if probe == "2021" else service.live()


@router.get("/api/wahlabend")
def wahlabend(
    probe: str | None = Query(default=None, description="„2021“ = Generalprobe mit den Zahlen von 2021"),
    counted: int | None = Query(default=None, ge=0, le=500, description="Generalprobe: nur die ersten N Wahlbezirke ausgezählt"),
) -> ElectionNight:
    _frei()
    return _stand(probe, counted)


@router.get("/api/wahlabend/bild.png", response_class=Response, responses=WAHLABEND_PNG)
def wahlabend_bild(
    feld: str | None = Query(default=None, pattern="^(seats|projected_seats)$",
                             description="„seats“ = ausgezählter Stand, „projected_seats“ = Hochrechnung; Vorgabe je Phase"),
    probe: str | None = Query(default=None, description="„2021“ = Generalprobe mit den Zahlen von 2021"),
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
    compare: bool = Query(default=True, description="false = ohne den Abstand zu 2021 (Listenkarte)"),
    probe: str | None = Query(default=None, description="„2021“ = Generalprobe mit den Zahlen von 2021"),
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
