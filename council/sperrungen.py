"""Aktuelle Straßensperrungen der Stadt Oldenburg — für „Mein Viertel".

Die Stadt führt ihre Sperrungen und Baustellen im selben Geoportal wie die
Bebauungspläne (``council/bplan.py``): Ebene 11 „Verkehrsinformationen –
Aktuelle Sperrungen", je Eintrag Straße, Grund, von/bis, eine Beschreibung
in Prosa, die Art (Vollsperrung, Umleitung, …) und die Linie auf der Karte.
Das ist die strukturierte Fassung der Baustellen-Seite auf oldenburg.de —
dort stehen dieselben Maßnahmen als Fließtext ohne Geometrie.

**Was der Lauf tut.** Täglich (``scripts/check_presse.py``, der Stadt-
Quellen-Lauf) alle Einträge holen, je Linie die Ortsbereiche bestimmen
(``geo.ortsbereiche_der_geometrie``) und in ``council_road_closures``
fortschreiben: Bekanntes aktualisieren, Neues anlegen, Verschwundenes als
beendet markieren — wie bei den Beteiligungen. Die Stadt löscht eine
Sperrung, sobald sie vorbei ist; wir behalten sie als Historie.

**Grenzen.** Die Ebene trägt nur, was die Verkehrsbehörde einträgt
(gemessen 06.09.2026: 20 Einträge, größere Maßnahmen wie Alexanderstraße
oder Donnerschweer Straße dabei, kleine Tagesbaustellen nicht). ``bis`` fehlt
bei Dauer-Sperrungen (Cäcilienbrücke seit 2020).
"""
from __future__ import annotations

import html
import json
import re

from council import geo, places
from council.bplan import MAPSERVER, _datum, _session

EBENE = 11
QUELLE_LABEL = "Stadt Oldenburg, Geoportal"
QUELLE_URL = "https://www.oldenburg.de/startseite/stadtraum/verkehr-mobilitaet/baustellen.html"

#: Die Art-Codes der Ebene (Domäne des Feldes ``Art``).
ART = {1: "einseitige Sperrung", 2: "Umleitung", 3: "Vollsperrung",
       4: "zeitweilige Behinderungen", 5: "Einbahnstraßenregelung", 6: "Kranarbeiten"}

#: Ab diesem Anteil der Linie gehört eine Sperrung auf die Tafel eines
#: Ortsbereichs. Niedriger als bei Vorhaben: Eine Sperrung an der Grenze
#: betrifft beide Seiten.
MIN_SHARE = 0.2


def _text(beschreibung: str | None) -> str:
    """HTML der Verkehrsbehörde (``<br/>``, Entities) → Fließtext mit Absätzen."""
    s = beschreibung or ""
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def _orte(geometrie: dict | None) -> list[dict]:
    """Ortsbereiche, die die Linie berührt → ``[{place_id, share}]``, größter zuerst."""
    stimmen = geo.ortsbereiche_der_geometrie(geometrie)
    gesamt = sum(stimmen.values()) or 1
    out = []
    for name, n in sorted(stimmen.items(), key=lambda kv: -kv[1]):
        place = places.resolve(name)
        if place:
            out.append({"place_id": place.id, "share": round(n / gesamt, 3)})
    return out


def normiere(feature: dict) -> dict | None:
    p = feature.get("properties") or {}
    objectid = p.get("OBJECTID")
    street = (p.get("Strasse") or "").strip()
    if objectid is None or not street:
        return None
    geometrie = feature.get("geometry") or None
    mitte = geo.linien_mittelpunkt(geometrie) if geometrie else None
    if not mitte and geometrie and geometrie.get("type") == "Point":
        lon, lat = geometrie["coordinates"][:2]
        mitte = (lat, lon)
    art = p.get("Art")
    return {
        "objectid": int(objectid),
        "street": street,
        "reason": (p.get("Grund") or "").strip() or None,
        "kind": art,
        "kind_label": ART.get(art) if isinstance(art, int) else None,
        "valid_from": _datum(p.get("von")),
        "valid_until": _datum(p.get("bis")),
        "description": _text(p.get("Beschreibung")) or None,
        "geojson": json.dumps(geometrie, separators=(",", ":")) if geometrie else None,
        "lat": mitte[0] if mitte else None,
        "lon": mitte[1] if mitte else None,
        "places": _orte(geometrie),
    }


def fetch_closures(timeout: int = 60) -> list[dict]:
    """Alle aktuellen Sperrungen der Stadt, normiert. Wirft bei Netzfehlern —
    der Aufrufer lässt dann den Bestand stehen."""
    r = _session.get(f"{MAPSERVER}/{EBENE}/query", params={
        "where": "1=1", "outFields": "*", "outSR": "4326", "f": "geojson", "resultRecordCount": 1000,
    }, timeout=timeout)
    r.raise_for_status()
    daten = r.json()
    if "error" in daten:
        raise RuntimeError(f"Geoportal, Ebene {EBENE}: {daten['error']}")
    if daten.get("exceededTransferLimit") or (daten.get("properties") or {}).get("exceededTransferLimit"):
        raise RuntimeError("Sperrungen: Der Dienst hat abgeschnitten.")
    return [z for z in (normiere(f) for f in daten.get("features", [])) if z]
