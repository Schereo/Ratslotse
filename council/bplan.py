"""Bebauungsplan-Umringe der Stadt Oldenburg — für die Karte von „Mein Viertel".

**Warum die Stadt-Geodaten und nicht die PDF-Anlagen.** Was ein Bebauungsplan
umfasst, steht als Planzeichnung im Anhang der Vorlage — ein Bild, aus dem
sich keine Fläche für eine Karte gewinnen lässt (die Fallen stehen in der
Notiz zur Planzeichnungs-Idee: AES-verschlüsselte PDFs, kein Renderer auf dem
Server). Die Stadt führt die Umringe aller Bebauungspläne aber selbst in
ihrem Geoportal: je Plan die Nummer („777 G"), der Name, die Daten von
Aufstellungs- und Satzungsbeschluss, die Rechtskraft und die Fläche als
Polygon. Damit bekommt ein Vorhaben wie „Hallensichel-Ost/Entlastungsstraße"
seine Fläche auf die Karte, obwohl die Straße noch nicht gebaut ist und
OpenStreetMap sie deshalb nicht kennt (Tims Wunsch, 06.09.2026).

**Welche Quelle, und warum diese.** Auf openGEOdata liegt ein Abzug
„Umringe Bplan" (dl-de/zero) — zuletzt im Mai 2024 gepflegt, jüngster Plan
von Juli 2023; alles seither Rechtskräftige fehlte dort (gemessen
06.09.2026: 28 von 37 Vorhaben mit Plannummer ohne Fläche). Der
**Kartendienst des Geoportals** trägt dieselben Daten live, und dazu die
zweite Ebene, die der Abzug nie hatte: die **Pläne in Aufstellung** — genau
der Stand „in Planung", um den es auf der Tafel meist geht. Gemessen am
06.09.2026: 665 rechtsverbindliche Pläne (jüngster 24.07.2026) und 79 in
Aufstellung (jüngster Aufstellungsbeschluss 31.08.2026).

**Die Verknüpfung läuft über die Plannummer im Beschlusstitel.** Die
Verwaltung schreibt sie immer hinein: „Bebauungsplan N-777 G (…) -
Satzungsbeschluss", „Änderung 1 des Bebauungsplanes 777 D (…)",
„Vorhabenbezogener Bebauungsplan Nr. 64 (…)". Kein Sprachmodell, kein
Raten — ``plannummern_im_titel`` liest sie, ``schluessel`` macht beide
Schreibweisen vergleichbar (der Stadtbezirks-Buchstabe „N-" steht nur in den
Vorlagen, nicht im Datensatz; „Nr." und „Nummer" fehlen dort ebenso).

**Grenzen, die man kennen muss:**

- Der Umring ist der **Geltungsbereich**, nicht die Straße oder das Gebäude
  darin. Die Verkehrsflächen selbst stünden im XPlanGML — eine zweite Stufe.
- Eine **Änderung** eines Plans hat oft einen eigenen, kleineren Umring
  („513 Änd. 1"). Gibt es den, gilt er; sonst fällt die Zuordnung auf den
  Ursprungsplan zurück, weil eine Änderung innerhalb seines
  Geltungsbereichs liegt.
- Steht ein Plan in **beiden** Ebenen (Änderung in Aufstellung zum
  rechtskräftigen Ursprungsplan), sind das zwei Schlüssel — kein Konflikt.
  Denselben Schlüssel in beiden Ebenen gab es am 06.09.2026 nicht; käme er
  vor, gewänne der rechtsverbindliche.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import requests

#: Der Kartendienst des städtischen Geoportals (ArcGIS Server 10.7). Zwei
#: Ebenen desselben Dienstes, gleiche Felder: 18 = rechtsverbindlich,
#: 19 = in Aufstellung. Seitenweise (der Dienst deckelt bei 1.000), als
#: GeoJSON in WGS84.
MAPSERVER = "https://gisportal4ol.oldenburg.de/server/rest/services/GeoPortal/GeoPortal/MapServer"
EBENEN = {"effective": 18, "in_procedure": 19}
SEITE = 500
QUELLE_URL = "https://gis4ol.oldenburg.de/Stadtplan/?esearch=9&slayer=0&exprnum=0"
QUELLE_LABEL = "Stadt Oldenburg, Geoportal"

_session = requests.Session()
_session.headers["User-Agent"] = "Ratslotse (+https://ratslotse.de)"


def _datum(wert) -> str | None:
    """Der Dienst liefert Datumsfelder als Unix-Millisekunden, der Hub-Export
    als ISO-Text — beides auf ``YYYY-MM-DD``."""
    if wert in (None, ""):
        return None
    if isinstance(wert, (int, float)):
        return datetime.fromtimestamp(wert / 1000, tz=timezone.utc).date().isoformat()
    return str(wert)[:10]


def _ringe(geometrie: dict) -> list[list[list[float]]]:
    if geometrie.get("type") == "Polygon":
        return [r for r in geometrie["coordinates"] if r]
    if geometrie.get("type") == "MultiPolygon":
        return [r for poly in geometrie["coordinates"] for r in poly if r]
    return []


def _in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    innen = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1:
            innen = not innen
    return innen


def schwerpunkt(geometrie: dict | None) -> tuple[float, float] | None:
    """Ein Punkt IN der Fläche des größten Rings — der Pin eines Plans.

    Erst der Flächenschwerpunkt (Schnürsenkel-Formel). Der liegt bei einem
    L- oder U-förmigen Geltungsbereich aber außerhalb, genau wie der
    Bounding-Box-Mittelpunkt; dann wandert der Pin auf die Mitte des
    breitesten Stücks der Fläche in der Höhe des Schwerpunkts. Ergebnis
    ``(lat, lon)``.
    """
    if not geometrie:
        return None
    ringe = _ringe(geometrie)
    if not ringe:
        return None
    ring = max(ringe, key=len)
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        kreuz = x1 * y2 - x2 * y1
        a += kreuz
        cx += (x1 + x2) * kreuz
        cy += (y1 + y2) * kreuz
    if abs(a) < 1e-12:
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return (sum(ys) / len(ys), sum(xs) / len(xs))
    a *= 0.5
    x, y = cx / (6 * a), cy / (6 * a)
    if _in_ring(x, y, ring):
        return (y, x)
    # Schnittpunkte der Waagerechten durch y mit dem Ring → breitestes Stück.
    schnitte: list[float] = []
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y):
            schnitte.append((x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1)
    schnitte.sort()
    paare = list(zip(schnitte[0::2], schnitte[1::2]))
    if not paare:
        return (y, x)
    links, rechts = max(paare, key=lambda p: p[1] - p[0])
    return (y, (links + rechts) / 2)


def schluessel(nr: str | None) -> str:
    """Eine Plannummer in ihre Vergleichsform.

    Beide Seiten schreiben dieselbe Nummer verschieden: Der Datensatz sagt
    „777 G", „18c VhB", „513 Änd. 1", „117 I"; die Vorlagen „N-777 G",
    „Nr. 18 c", „Änderung Nummer 1 des Bebauungsplanes S-513". Weg mit dem
    Bezirksbuchstaben, „Nr."/„Nummer", Punkten und Leerraum zwischen Zahl und
    Buchstabe; Großschreibung; „ÄNDERUNG"/„ÄND" auf eine Form.
    """
    s = (nr or "").strip().upper()
    s = re.sub(r"^[NSWO]-\s*", "", s)
    s = re.sub(r"\b(NR\.?|NUMMER)\s*", "", s)
    s = s.replace(".", " ")
    s = re.sub(r"\bÄNDERUNG\b", "ÄND", s)
    s = re.sub(r"\s+", " ", s).strip()
    # „777 G" → „777G", „18 C VHB" → „18C VHB", „225 I" → „225I" — aber
    # „64 VHB" bleibt „64 VHB": Das Kürzel für „vorhabenbezogen" ist kein
    # Buchstabenzusatz der Nummer (gemessen 06.09.2026: alle 36 VhB-Pläne
    # fanden sich sonst nicht, weil der Datensatz „64 VhB" zu „64VHB" wurde).
    s = re.sub(r"^(\d+)\s+(?!VHB\b)([A-Z]{1,3})(?=$|\s)", r"\1\2", s)
    return s


_AENDERUNG_RE = re.compile(
    r"Änderung\s+(?:Nr\.?\s*|Nummer\s+)?(\d+)\s+(?:des|zum|der)\s+(?:vorhabenbezogenen\s+)?"
    r"Bebauungsplan(?:e?s)?\s+(?:Nr\.?\s*)?([NSWO]-)?(\d+\s?[a-zA-Z]?(?:\s[IVX]+)?)",
    re.IGNORECASE)
_VHB_RE = re.compile(
    r"Vorhabenbezogene[rn]?\s+Bebauungsplan(?:e?s)?\s+(?:Nr\.?\s*)?(\d+\s?[a-zA-Z]?)(?![\w-])",
    re.IGNORECASE)
_PLAN_RE = re.compile(
    r"Bebauungsplan(?:e?s)?\s+(?:Nr\.?\s*)?([NSWO]-)?(\d+\s?[A-Z]?(?:\s[IVX]+)?)(?![\w-])")


def plannummern_im_titel(titel: str | None) -> list[str]:
    """Die Plannummern eines Beschlusstitels als Vergleichsschlüssel, in der
    Reihenfolge, in der sie gelten: Eine Änderung zuerst („513 ÄND 1"), dann
    ihr Ursprungsplan („513") als Rückfall; ein vorhabenbezogener Plan als
    „64 VHB"; sonst der Plan selbst („777G")."""
    t = titel or ""
    out: list[str] = []

    def merke(k: str) -> None:
        if k and k not in out:
            out.append(k)

    for m in _AENDERUNG_RE.finditer(t):
        basis = schluessel(m.group(3))
        vhb = "vorhabenbezogen" in m.group(0).lower()
        merke(f"{basis}{' VHB' if vhb else ''} ÄND {m.group(1)}")
        merke(f"{basis} VHB" if vhb else basis)
    for m in _VHB_RE.finditer(t):
        merke(f"{schluessel(m.group(1))} VHB")
    if not out:
        for m in _PLAN_RE.finditer(t):
            merke(schluessel(m.group(2)))
    return out


def normiere(feature: dict, status: str = "effective") -> dict | None:
    """Ein Feature des Dienstes → eine Zeile für ``council_bplan_outlines``.
    ``status``: ``effective`` (rechtsverbindlich) oder ``in_procedure`` (in
    Aufstellung) — die Ebene, aus der das Feature kommt."""
    p = feature.get("properties") or {}
    nr = (p.get("Planverfahren") or "").strip()
    if not nr:
        return None
    geometrie = feature.get("geometry") or None
    mitte = schwerpunkt(geometrie)
    return {
        "key": schluessel(nr),
        "nr": nr,
        "status": status,
        "name": (p.get("Name") or "").strip(),
        "art": p.get("Art"),
        "verfahren": p.get("Verfahren"),
        "note": (p.get("Bemerkung") or "").strip() or None,
        "resolution_date": _datum(p.get("Aufstellungsbeschluss_Rat_VA")),
        "adoption_date": _datum(p.get("Satzungsbeschluss_Rat_VA")),
        "effective_date": _datum(p.get("rechtsverbindlich")),
        "drawing_code": (p.get("Planzeichnung") or "").strip() or None,
        "stol_id": p.get("Link_StOL"),
        "geojson": json.dumps(geometrie, separators=(",", ":")) if geometrie else None,
        "lat": mitte[0] if mitte else None,
        "lon": mitte[1] if mitte else None,
    }


def _ebene(layer: int, timeout: int) -> list[dict]:
    """Alle Features einer Ebene, seitenweise."""
    out: list[dict] = []
    offset = 0
    while True:
        r = _session.get(f"{MAPSERVER}/{layer}/query", params={
            "where": "1=1", "outFields": "*", "outSR": "4326", "f": "geojson",
            "orderByFields": "OBJECTID", "resultOffset": offset, "resultRecordCount": SEITE,
        }, timeout=timeout)
        r.raise_for_status()
        daten = r.json()
        if "error" in daten:
            raise RuntimeError(f"Geoportal, Ebene {layer}: {daten['error']}")
        features = daten.get("features", [])
        out.extend(features)
        if len(features) < SEITE:
            return out
        offset += SEITE
        if offset > 20 * SEITE:
            raise RuntimeError(f"Geoportal, Ebene {layer}: mehr als {20 * SEITE} Features — das ist kein Ende.")


def fetch_outlines(timeout: int = 120) -> list[dict]:
    """Alle Umringe aus beiden Ebenen des Geoportals holen, normiert. Wirft bei
    Netzfehlern und bei einem verdächtig kleinen Abzug — der Aufrufer
    (Wochenlauf) lässt dann den alten Bestand stehen
    (``replace_bplan_outlines`` läuft erst danach)."""
    zeilen: dict[str, dict] = {}
    # Rechtsverbindlich zuerst: Träfe derselbe Schlüssel in beiden Ebenen auf,
    # bleibt der rechtsverbindliche stehen.
    for status in ("effective", "in_procedure"):
        for f in _ebene(EBENEN[status], timeout):
            z = normiere(f, status)
            if z and z["key"] not in zeilen:
                zeilen[z["key"]] = z
    if sum(1 for z in zeilen.values() if z["status"] == "effective") < 100:
        raise RuntimeError(f"Nur {len(zeilen)} Bebauungspläne geliefert — das ist kein Vollabzug.")
    return list(zeilen.values())
