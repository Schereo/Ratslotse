#!/usr/bin/env python3
"""Stand der Pläne aus den Quellen der Stadt lesen (Plan „Pläne“, Phase 3).

Schreibt ``council/plan_status/<plan>.json``: je Plan eine Liste von
Momentaufnahmen, jede mit Stichtag, Quelle und der Verteilung **im Wortlaut
der Stadt**. Die Dateien sind eingecheckt und geprüft wie die
Maßnahmenlisten (``scripts/plan_massnahmen.py``); dieses Skript macht sie
nachvollziehbar, nicht täglich neu. Ohne Modell.

Warum Dateien und kein Cron (docs/plan-ziele-plaene.md § 4): Auf dev laufen
keine Crons, ``build_plans.py`` läuft dort bei jedem Deploy, und ein Abruf
bei einer fremden Seite gehört nicht in einen Deploy.

Quellen:

- **Klimaschutzplan:** das Klimaportal der Stadt (klimaportal.oldenburg.de).
  ``robots.txt`` erlaubt den Abruf; eine Lizenz nennt die Seite nicht, also
  übernehmen wir **Tatsachen** (Statuswerte, Zahlen, Stichtage) mit Quelle und
  nie Texte oder Grafiken. Höflich geholt: eigener User-Agent, mindestens zwei
  Sekunden Abstand, alles unter ``~/.cache/ratslotse/plan-quellen/klimaportal/``.
  Gegenprobe sind die Zählblöcke der Ratsvorlagen 26/0074 und 26/0750.
  **Übernommen wird nur die Reihe.** Den Stand je Maßnahme zeigen die
  Paketseiten zwar, aber nicht verlässlich: Dieselbe Maßnahme steht auf
  mehreren Seiten mit verschiedenen Ständen, Kennungen sind vertauscht, und
  die Summe geht nicht in der Reihe auf (gemessen 09.11.2026: 57 von 90
  eindeutig, 6 widersprüchlich). ``--portal-massnahmen`` zeigt den Abgleich.
- **Wärmeplan:** die Beschlussvorlage 26/0236. Sie ordnet sechs der 18
  Maßnahmen als „in Umsetzung“ ein; für die übrigen nennt sie ein Vorhaben
  und keinen Stand.

    python scripts/plan_status.py                 # alle schreiben
    python scripts/plan_status.py --nur waermeplan
    python scripts/plan_status.py --pruefen       # nur vergleichen, nichts schreiben
    python scripts/plan_status.py --neu-holen     # Zwischenspeicher des Portals verwerfen
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import html
import json
import re
import sys
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council import plan_state, plans  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from scripts.plan_massnahmen import CACHE, USER_AGENT  # noqa: E402

PORTAL = "https://klimaportal.oldenburg.de"
PORTAL_CACHE = CACHE / "klimaportal"
#: Abstand zwischen zwei Abrufen beim Portal, in Sekunden.
PORTAL_GAP = 2.0
_last_fetch = 0.0
_refresh = False


# ── Klimaportal ────────────────────────────────────────────────────────────


def _cache_file(path: str) -> Path:
    return PORTAL_CACHE / (path.strip("/").replace("/", "__") or "index")


def portal_page(path: str) -> str:
    """Eine Seite des Klimaportals — aus dem Zwischenspeicher oder höflich geholt."""
    global _last_fetch
    target = _cache_file(path)
    if target.exists() and target.stat().st_size > 0 and not _refresh:
        return target.read_text(encoding="utf-8")
    PORTAL_CACHE.mkdir(parents=True, exist_ok=True)
    wait = PORTAL_GAP - (time.monotonic() - _last_fetch)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(f"{PORTAL}/{path.strip('/')}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    _last_fetch = time.monotonic()
    text = data.decode("utf-8")
    target.write_text(text, encoding="utf-8")
    return text


def portal_fetched(path: str) -> str:
    """Abrufdatum der Seite im Zwischenspeicher (ISO)."""
    return dt.date.fromtimestamp(_cache_file(path).stat().st_mtime).isoformat()


def _decode(value):
    """Astros Serialisierung der Insel-Props: ``[typ, wert]`` mit 0 = Wert/Objekt, 1 = Liste."""
    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], int):
        kind, inner = value
        if kind == 0:
            return {k: _decode(v) for k, v in inner.items()} if isinstance(inner, dict) else inner
        if kind == 1:
            return [_decode(v) for v in inner]
        return inner
    return value


_ISLAND = re.compile(r'<astro-island[^>]*component-url="([^"]+)"[^>]*?props="([^"]*)"')


def islands(page: str) -> list[dict]:
    """Die Daten aller Inseln einer Seite. Das Portal ist statisch gebaut; die
    Zahlen stehen als JSON im Attribut ``props``, nicht in einer Schnittstelle."""
    out = []
    for m in _ISLAND.finditer(page):
        try:
            raw = json.loads(html.unescape(m.group(2)))
        except json.JSONDecodeError:
            continue
        out.append({k: _decode(v) for k, v in raw.items()})
    return out


def _walk(value):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)


SERIES_TITLE = "Umsetzungsstatus der Klimaschutzmaßnahmen"
_LEVEL = re.compile(r"^\s*(\d)\s*[–-]\s*(.+?)\s*$")


def portal_series() -> dict:
    """Die Reihe „Umsetzungsstatus“ von der Monitoring-Seite: Jahre, Stufen, Quelle."""
    for node in (n for isl in islands(portal_page("monitoring")) for n in _walk(isl)):
        chart = node.get("chartData")
        if not isinstance(chart, dict) or (chart.get("title") or {}).get("value") != SERIES_TITLE:
            continue
        years = [str(x) for x in chart["xAxis"]["data"]]
        levels = []
        for s in chart["seriesList"]:
            m = _LEVEL.match(s["name"])
            if not m:
                raise SystemExit(f"Klimaportal: Stufe ohne Nummer: {s['name']!r}")
            levels.append((int(m.group(1)), m.group(2), [int(v) for v in s["data"]]))
        levels.sort()
        return {"years": years, "levels": levels, "source": (chart.get("source") or {}).get("value") or ""}
    raise SystemExit("Klimaportal: Diagramm „Umsetzungsstatus der Klimaschutzmaßnahmen“ nicht gefunden")


_CODE = re.compile(r"^[A-Za-zÄÖÜäöüß]+_\d{2}$")
_H3 = re.compile(r"<h3[^>]*>(.*?)</h3>", re.S)
_TAG = re.compile(r"<[^>]+>")


def portal_package_paths() -> list[str]:
    """Die Paketseiten unter ``/massnahmen/<handlungsfeld>/<paket>`` laut Sitemap."""
    paths = []
    for url in re.findall(r"<loc>([^<]+)</loc>", portal_page("sitemap-0.xml")):
        path = url.removeprefix(PORTAL).strip("/")
        if path.startswith("massnahmen/") and path.count("/") >= 2:
            paths.append(path)
    return sorted(paths)


def portal_measure_rows() -> list[dict]:
    """Alle Maßnahmen-Kästen der Paketseiten: Seite, Titel, Kennung, Status — ungefiltert."""
    rows = []
    for path in portal_package_paths():
        for isl in islands(portal_page(path)):
            boxes = ((isl.get("bentoData") or {}).get("box") or {}).get("boxes") or []
            titles: dict[str, str] = {}
            for box in boxes:
                for content in box.get("content") or []:
                    text = (content.get("data") or {}).get("html")
                    m = _H3.search(text) if isinstance(text, str) else None
                    if m:
                        titles.setdefault(box.get("pageId"), html.unescape(_TAG.sub("", m.group(1))).strip())
            for box in boxes:
                for content in box.get("content") or []:
                    items = [(i.get("data") or {}) for i in (content.get("data") or {}).get("items") or []]
                    status = next((i.get("valueLabel") for i in items if i.get("type") == "status"), None)
                    if not status:
                        continue
                    code = next((i["valueLabel"].strip() for i in items
                                 if isinstance(i.get("valueLabel"), str) and _CODE.match(i["valueLabel"].strip())), None)
                    rows.append({"path": path, "title": titles.get(box.get("pageId")), "code": code,
                                 "status_raw": status.strip()})
    return rows


def portal_measure_check() -> dict:
    """Wie verlässlich der Stand je Maßnahme im Portal ist — der Grund, warum er fehlt.

    Eine Zeile zählt nur, wenn Kennung **und** Titel zu unserer Liste aus der
    Ratsvorlage passen; eindeutig ist eine Maßnahme, wenn alle ihre Zeilen
    denselben Stand nennen.
    """
    ours = {m["code"].lower(): m for m in (plans.measures("klimaschutzplan_2035") or {"measures": []})["measures"]}

    def squash(text: str) -> str:
        return re.sub(r"[^a-zäöüß0-9]+", "", text.lower())

    states: dict[str, set[str]] = {}
    for row in portal_measure_rows():
        mine = ours.get((row["code"] or "").lower())
        if not mine or not row["title"]:
            continue
        if difflib.SequenceMatcher(None, squash(row["title"]), squash(mine["title"])).ratio() < 0.6:
            continue
        states.setdefault(mine["code"], set()).add(row["status_raw"].lower())
    return {"measures": len(ours), "unique": sum(1 for s in states.values() if len(s) == 1),
            "contradictory": sorted(c for c, s in states.items() if len(s) > 1)}


# ── Vorlagentexte ──────────────────────────────────────────────────────────


def template_text(store: CouncilStore, number: str) -> str:
    row = store.get_vorlage_by_nr(number)
    if not row or not row.get("raw_text"):
        raise SystemExit(f"Vorlage {number}: kein Text im Bestand")
    return row["raw_text"]


#: Stufe des Klimaschutzplans → Stichwort, an dem ein Zählblock sie erkennt.
_KSP_KEYWORDS = ((0, "neu"), (1, "zuordnung"), (3, "umsetzungsreif"), (2, "planung"),
                 (4, "in umsetzung"), (5, "realisiert"), (6, "zurückgestellt"))
_BLOCK_LINE = re.compile(r"^-?\s*(\d+)\s+(?:Maßnahmen?:\s*)?(\S.*)$")


def template_count_block(text: str) -> dict[int, int]:
    """Der Zählblock eines Berichts „Klimaschutz-Aktivitäten“ als Stufe → Zahl.

    Zwei Schreibweisen im Bestand: „- 6 Maßnahmen: Zuordnung Amt“ (26/0074)
    und „10 Zuordnung Amt“ (26/0750). Gelesen wird ab dem Einleitungssatz,
    solange Zeilen mit einer Zahl beginnen.
    """
    m = re.search(r"Klimaschutzmaßnahmen\s+(?:folgenden Stand erreicht|wie folgt umgesetzt):", text)
    if not m:
        return {}
    out: dict[int, int] = {}
    unclosed = False  # „Realisiert (und teilweise / weiterhin Daueraufgabe)“ läuft über zwei Zeilen
    for line in text[m.end():].splitlines():
        line = line.strip()
        if not line or line.startswith("Anzahl der Maßnahmen"):
            continue
        hit = _BLOCK_LINE.match(line)
        if not hit:
            if unclosed:
                unclosed = ")" not in line
                continue
            break
        label = hit.group(2).lower()
        level = next((n for n, word in _KSP_KEYWORDS if word in label), None)
        if level is None:
            break
        out[level] = int(hit.group(1))
        unclosed = label.count("(") > label.count(")")
    return out


# ── Klimaschutzplan ────────────────────────────────────────────────────────

#: Stufe des Portals → Gruppe. Nur zum Gruppieren; angezeigt wird das Wort der Stadt.
_KSP_NORM = {0: "open", 1: "started", 2: "started", 3: "started", 4: "in_progress", 5: "done", 6: "paused"}
#: Jahr der Reihe → Bericht im Rat mit demselben Zählblock (Gegenprobe).
_KSP_CONFIRMED = {"2025": "26/0074", "2026": "26/0750"}


def klimaschutzplan(store: CouncilStore) -> dict:
    series = portal_series()
    source = {"kind": "klimaportal", "label": f"Klimaportal der Stadt, „{SERIES_TITLE}“",
              "url": f"{PORTAL}/monitoring", "fetched": portal_fetched("monitoring"),
              "attribution": series["source"]}
    snapshots = []
    for idx, year in enumerate(series["years"]):
        counts = [{"status_raw": name, "status_norm": _KSP_NORM[n], "count": values[idx]}
                  for n, name, values in series["levels"]]
        snap: dict = {"as_of": year, "source": source, "total": sum(c["count"] for c in counts),
                      "complete": True, "counts": counts}
        number = _KSP_CONFIRMED.get(year)
        if number:
            block = template_count_block(template_text(store, number))
            portal = {n: values[idx] for n, _, values in series["levels"]}
            if not block or any(block.get(n, 0) != portal[n] for n in portal):
                raise SystemExit(f"Klimaschutzplan {year}: Portal {portal} und Vorlage {number} {block} "
                                 "nennen verschiedene Zahlen")
            snap["confirmed_by"] = {"template": number}
        snapshots.append(snap)
    for year in _KSP_CONFIRMED:
        if year not in series["years"]:
            raise SystemExit(f"Klimaschutzplan: Jahr {year} fehlt in der Reihe des Portals")
    return {
        "plan": "klimaschutzplan_2035",
        "snapshots": snapshots,
        "notes": [
            {"text": "Das Statussystem des Portals soll nach eigener Aussage nur einen zusammenfassenden "
                     "Überblick geben; über die tatsächliche Umsetzung der einzelnen Maßnahme sagt es nichts.",
             "url": f"{PORTAL}/monitoring"},
            {"text": "Laut Portal laufen viele realisierte Maßnahmen als Daueraufgaben weiter.",
             "url": f"{PORTAL}/monitoring"},
            {"text": "Bis 2025 zählt die Stadt 90 Maßnahmen, 2026 sind es 97.", "url": None},
        ],
    }


# ── Wärmeplan ──────────────────────────────────────────────────────────────

_WAERME_HEAD = re.compile(r"^([KFTO]\d)\s*[-–]\s+\S.*$", re.M)
_NUMBER_WORDS = {"zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9,
                 "zehn": 10, "elf": 11, "zwölf": 12}


def waermeplan(store: CouncilStore) -> dict:
    """Die Beschlussvorlage führt einen Teil der Maßnahmen unter „Maßnahmen in
    Umsetzung“, die übrigen unter „Weitere Maßnahmen“ ohne Stand. Gezählt wird
    nur, was die Stadt selbst so nennt — und gegen ihr Zahlwort geprüft."""
    number = "26/0236"
    text = template_text(store, number)
    heads = list(_WAERME_HEAD.finditer(text))
    begin = re.search(r"^Maßnahmen in Umsetzung\s*$", text, re.M)
    rest = re.search(r"^Weitere Maßnahmen\s*$", text, re.M)
    if not begin or not rest or rest.start() < begin.start():
        raise SystemExit("Wärmeplan: Abschnitte „Maßnahmen in Umsetzung“ / „Weitere Maßnahmen“ nicht gefunden")
    running = [h.group(1) for h in heads if begin.end() < h.start() < rest.start()]
    codes = [m["code"] for m in (plans.measures("waermeplan") or {"measures": []})["measures"]]
    found = [h.group(1) for h in heads]
    if sorted(set(found)) != sorted(codes):
        raise SystemExit(f"Wärmeplan: Vorlage nennt {sorted(set(found))}, die Liste {sorted(codes)}")
    said = re.search(r"(\w+) Maßnahmen können bereits als „in Umsetzung“ kategorisiert werden", text)
    if not said or _NUMBER_WORDS.get(said.group(1).lower()) != len(running):
        raise SystemExit(f"Wärmeplan: {len(running)} Maßnahmen mit Stand gelesen, die Vorlage sagt "
                         f"{said.group(1) if said else '—'}")
    return {
        "plan": "waermeplan",
        "snapshots": [{
            "as_of": "2026-03",
            "source": {"kind": "template", "label": "Beschlussvorlage Oldenburger Wärmeplan", "template": number,
                       "url": None, "fetched": None},
            "total": len(codes),
            "complete": False,
            "counts": [{"status_raw": "in Umsetzung", "status_norm": "in_progress", "count": len(running)}],
            "measures": [{"code": c, "status_raw": "in Umsetzung", "status_norm": "in_progress"} for c in running],
        }],
        "notes": [{"text": f"Für die übrigen {len(codes) - len(running)} Maßnahmen beschreibt die Vorlage ein "
                           "Vorhaben und nennt keinen Stand.", "url": None}],
    }


#: plan → Leser. Jeder prüft seine Zahlen selbst gegen die Quelle und bricht ab, wenn sie nicht aufgehen.
SOURCES: dict[str, Callable[[CouncilStore], dict]] = {
    "klimaschutzplan_2035": klimaschutzplan,
    "waermeplan": waermeplan,
}


def main(argv: list[str] | None = None) -> int:
    global _refresh
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--nur", help="ein Plan-Schlüssel")
    ap.add_argument("--pruefen", action="store_true", help="nur vergleichen, nichts schreiben")
    ap.add_argument("--neu-holen", action="store_true", help="Zwischenspeicher des Portals verwerfen")
    ap.add_argument("--portal-massnahmen", action="store_true",
                    help="zeigen, wie verlässlich der Stand je Maßnahme im Klimaportal ist")
    ap.add_argument("--db", type=Path, default=WURZEL / "data" / "council.sqlite")
    args = ap.parse_args(argv)
    _refresh = args.neu_holen
    if args.portal_massnahmen:
        print(json.dumps(portal_measure_check(), ensure_ascii=False))
        return 0
    store = CouncilStore(args.db)
    differs = False
    try:
        for key in [args.nur] if args.nur else list(SOURCES):
            text = json.dumps(SOURCES[key](store), ensure_ascii=False, indent=1) + "\n"
            path = plan_state.STATUS_DIR / f"{key}.json"
            old = path.read_text(encoding="utf-8") if path.exists() else None
            n = len(json.loads(text)["snapshots"])
            if args.pruefen:
                differs |= old != text
                print(f"{'✓' if old == text else '✗'} {key}: {n} Momentaufnahmen")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"✓ {key}: {n} Momentaufnahmen → {path.relative_to(WURZEL)}")
    finally:
        store.close()
    return 1 if differs else 0


if __name__ == "__main__":
    raise SystemExit(main())
