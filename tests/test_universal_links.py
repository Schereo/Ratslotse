"""Die Universal-Link-Datei und der Router der iOS-App sagen dasselbe.

Zwei Listen, eine Frage — „öffnet dieser Link die App?":

- ``web/frontend/public/.well-known/apple-app-site-association.json`` sagt
  iOS, welche Pfade überhaupt bei der App ankommen.
- ``AppRouter.route(for:)`` (``ios/…/AppRoute.swift``) entscheidet, was die
  App daraus macht.

Laufen sie auseinander, gibt es zwei Fehler, beide gemessen im Review
10/2026:

1. **Der Router kann es, die Datei lässt es nicht durch.** ``/karte``,
   ``/viertel``, ``/abos``, ``/quiz``, ``/login``, ``/register`` und ``/``
   bediente die App nativ, ein Link darauf öffnete trotzdem Safari.
2. **Die Datei lässt es durch, der Router kann es nicht.** Dann landet der
   Link in der App, fällt dort auf ``.web`` und geht gleich wieder hinaus —
   so ``/council/ideen`` (seither ``.ideas``) und ``/council/neuer-rat``
   (seither mit ``NOT`` ausgenommen).

Der Test liest beide Quellen als Text; Swift muss dafür nicht laufen.
"""
from __future__ import annotations

import json
import re
from fnmatch import fnmatchcase
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
AASA = WURZEL / "web" / "frontend" / "public" / ".well-known" / "apple-app-site-association.json"
ROUTER = WURZEL / "ios" / "Packages" / "RatslotseAPI" / "Sources" / "RatslotseAPI" / "AppRoute.swift"


def _muster() -> list[str]:
    daten = json.loads(AASA.read_text(encoding="utf-8"))
    (eintrag,) = daten["applinks"]["details"]
    return eintrag["paths"]


def _oeffnet_app(pfad: str) -> bool:
    """Wie iOS die alte ``paths``-Liste liest: der erste Treffer zählt, ein
    ``NOT`` davor schließt aus."""
    for m in _muster():
        nicht = m.startswith("NOT ")
        if fnmatchcase(pfad, m[4:] if nicht else m):
            return not nicht
    return False


def _router_faelle() -> dict[str, bool]:
    """Jeder Pfad aus dem ``switch path`` → ``True``, wenn die App ihn selbst
    zeigt; ``False``, wenn der Fall ausdrücklich nur ``.web(url)`` liefert."""
    quelle = ROUTER.read_text(encoding="utf-8")
    start = quelle.index("switch path {")
    ende = quelle.index("default: return .web(url)", start)
    block = quelle[start:ende]
    faelle: dict[str, bool] = {}
    teile = re.split(r"\n\s*case ", block)[1:]
    for teil in teile:
        kopf, _, rumpf = teil.partition(":")
        pfade = re.findall(r'"(/[^"]*)"', kopf)
        rueckgaben = re.findall(r"return\s+(\.\w+)", rumpf)
        nur_web = bool(rueckgaben) and set(rueckgaben) == {".web"}
        for p in pfade:
            faelle[p] = not nur_web
    return faelle


def test_der_router_wird_gelesen():
    faelle = _router_faelle()
    assert len(faelle) >= 20, faelle
    assert faelle["/council/decision"] is True
    assert faelle["/council/neuer-rat"] is False


def test_was_die_app_kann_oeffnet_die_app():
    fehlend = [p for p, nativ in _router_faelle().items() if nativ and not _oeffnet_app(p)]
    assert not fehlend, (
        f"Die App bedient {fehlend} selbst, die Universal-Link-Datei lässt sie "
        f"aber nicht durch — ein Link öffnet Safari. In {AASA.relative_to(WURZEL)} "
        "unter `paths` eintragen (mit und ohne Schrägstrich am Ende).")


def test_was_nur_das_web_kann_bleibt_draussen():
    rein_und_raus = [p for p, nativ in _router_faelle().items() if not nativ and _oeffnet_app(p)]
    assert not rein_und_raus, (
        f"{rein_und_raus} gehen erst in die App und von dort gleich wieder ins "
        "Web. In der Universal-Link-Datei mit `NOT …` VOR dem breiteren Muster "
        "ausnehmen.")


def test_jedes_genaue_muster_hat_einen_fall_im_router():
    """Die Gegenrichtung für die genauen Einträge: ein Pfad, den die Datei in
    die App schickt, den der Router aber nicht kennt, fällt dort auf `.web`."""
    faelle = _router_faelle()
    ohne = [m for m in _muster()
            if not m.startswith("NOT ") and "*" not in m and "?" not in m
            and (m.rstrip("/") or "/") not in faelle]
    assert not ohne, f"Kein Fall in AppRouter.route(for:) für {ohne}"
