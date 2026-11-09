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
- **Aktionsplan Gewalt 2020:** die Evaluation (Anlage 314635 zu 26/0681/1). Die
  Verteilung zählt ihr Text, den Stand je Empfehlung trägt die Zellfarbe im
  Anhang 4.1; das Skript prüft beides gegeneinander.
- **Ernährungsstrategie:** der Bericht 26/0431 mit der Stufe je Handlungsansatz
  (alle 68; die Tabellen sind Text, nur die Kreisdiagramme sind Bilder).
- **Strategieplan Mobilität und Verkehr (smv2025):** Anhang 1 zur Fortschreibung des
  Lärmaktionsplans (Anlage 280377 zu 24/0293/1) — jede Einzelmaßnahme mit ihrem
  Umsetzungsstand, Stand Oktober 2023. Eine eigene Vorlage zur Auswertung gibt
  es im Ratsinformationssystem nicht; gefunden hat den Anhang die Durchsicht der
  Anlagen am 10.11.2026.
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
from collections import Counter
from collections.abc import Callable
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council import plan_state, plans  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from scripts.plan_massnahmen import (  # noqa: E402
    CACHE, RIS_DATEI, SMV_DOCUMENT, SMV_LEGEND, USER_AGENT, _seiten, holen, smv_rows, violence_rows,
)

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
_NUMBER_WORDS = {"eine": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8,
                 "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12}


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


# ── Aktionsplan Gewalt 2020 ────────────────────────────────────────────────

#: Farbe in Anhang 4.1 → das Wort der Legende dort, und die Gruppe für den Farbton.
_VIOLENCE_LEGEND = {
    "dark_green": ("umgesetzt", "done"),
    "light_green": ("erste Umsetzung, wiederholungsbedürftig", "done"),
    "pastel_green": ("angegangen, liegt nicht mehr beim Gleichstellungsbüro", "started"),
    "yellow": ("begonnen", "in_progress"),
    "red": ("nicht umgesetzt, wird weiterhin gebraucht", "open"),
    "grey": ("nicht umgesetzt, wird nicht weiterverfolgt", "paused"),
}
#: Was der Text der Evaluation (Kapitel 2) selbst zählt: Satzmuster → (Wort, Gruppe, Farben im Anhang).
_VIOLENCE_COUNTS = (
    (r"konnten (\w+) Handlungsempfehlungen, also mehr als die Hälfte umgesetzt werden", "umgesetzt", "done",
     ("dark_green", "light_green")),
    (r"(\w+) Handlungsempfehlungen sind aktuell in der Umsetzung", "aktuell in der Umsetzung", "in_progress",
     ("yellow",)),
    (r"(\w+) Handlungsempfehlungen wurden im Aktionszeitraum nicht umgesetzt, werden aber weiterhin gebraucht",
     "nicht umgesetzt, wird weiterhin gebraucht", "open", ("red",)),
    (r"(\w+) Handlungsempfehlungen konnten im Aktionszeitraum nicht umgesetzt werden und werden aus verschiedenen "
     r"Gründen nicht weiterverfolgt", "nicht umgesetzt, wird nicht weiterverfolgt", "paused", ("grey",)),
)


def _number(word: str) -> int:
    return int(word) if word.isdigit() else _NUMBER_WORDS[word.lower()]


def aktionsplan_gewalt_2020(store: CouncilStore) -> dict:
    """Die Verteilung zählt der Text der Evaluation selbst (Kapitel 2); den Stand je
    Empfehlung trägt die Zellfarbe im Anhang. Beides muss zusammenpassen — die eine
    Abweichung, die es gibt (Text 90 Empfehlungen, Tabelle 91 Zeilen), steht als Hinweis da."""
    rows = violence_rows()
    text = " ".join(" ".join(page.split()) for page in _seiten(314635)[15:30])
    total = re.search(r"alle (\d+) Handlungsempfehlungen des Aktionsplans betrachtet", text)
    if not total:
        raise SystemExit("Aktionsplan Gewalt: Gesamtzahl im Text der Evaluation nicht gefunden")
    by_color = Counter(row["color"] for row in rows)
    counts, off = [], []
    for pattern, raw, norm, colors in _VIOLENCE_COUNTS:
        m = re.search(pattern, text)
        if not m:
            raise SystemExit(f"Aktionsplan Gewalt: Satz zu „{raw}“ nicht gefunden")
        said, seen = _number(m.group(1)), sum(by_color[c] for c in colors)
        if abs(said - seen) > 1:
            raise SystemExit(f"Aktionsplan Gewalt: „{raw}“ — Text {said}, Tabelle {seen}")
        if said != seen:
            off.append(f"„{raw}“: Text {said}, Tabelle {seen}")
        counts.append({"status_raw": raw, "status_norm": norm, "count": said})
    # Die sechste Gruppe zählt der Text nicht aus. Sie steht in der Tabelle — und muss
    # zugleich der Rest zur Gesamtzahl des Textes sein, sonst stimmt etwas nicht.
    rest = int(total.group(1)) - sum(c["count"] for c in counts)
    if rest != by_color["pastel_green"]:
        raise SystemExit(f"Aktionsplan Gewalt: Rest zur Gesamtzahl {rest}, pastellgrüne Zeilen {by_color['pastel_green']}")
    raw, norm = _VIOLENCE_LEGEND["pastel_green"]
    counts.insert(2, {"status_raw": raw, "status_norm": norm, "count": rest})
    stated = sum(c["count"] for c in counts)
    notes = [{"text": f"Vier der fünf Zahlen nennt der Text der Evaluation. Die {rest} Empfehlungen „{raw}“ zählt er "
                      "nicht aus; sie stehen so in der Tabelle im Anhang und sind zugleich der Rest zur Gesamtzahl.",
              "url": None},
             {"text": "Den Stand je Empfehlung zeigt die Evaluation als Zellfarbe in Anhang 4.1; die Wörter "
                      "dazu stammen aus der Legende dort.", "url": None}]
    if len(rows) != int(total.group(1)) or off:
        notes.append({"text": f"Der Text zählt {total.group(1)} Empfehlungen, die Tabelle im Anhang hat {len(rows)} "
                              "Zeilen" + (f" ({'; '.join(off)})." if off else "."), "url": None})
    return {
        "plan": "aktionsplan_gewalt_2020",
        "snapshots": [{
            "as_of": "2026-08",
            "source": {"kind": "attachment", "label": "Evaluation und Fortschreibung, Kapitel 2 und Anhang 4.1",
                       "template": "26/0681/1", "url": RIS_DATEI.format(id=314635), "fetched": None},
            "total": int(total.group(1)),
            "complete": stated == int(total.group(1)),
            "counts": counts,
            "measures": [{"code": str(n), "status_raw": _VIOLENCE_LEGEND[row["color"]][0],
                          "status_norm": _VIOLENCE_LEGEND[row["color"]][1]} for n, row in enumerate(rows, start=1)],
        }],
        "notes": notes,
    }


# ── Ernährungsstrategie ────────────────────────────────────────────────────

#: Die fünf Stufen des Berichts 26/0431 in seinen Worten. Laut Stadt eine „qualitative
#: Einschätzung“ — wir zeigen sie als Stufen und mitteln sie nie (§ 3.4 Nr. 1).
_NUTRITION_STAGES = {
    100: ("wird vollständig umgesetzt (Stufe 100 %)", "done"),
    75: ("Umsetzung steht kurz bevor, erste Schritte erfolgt (Stufe 75 %)", "in_progress"),
    50: ("Grundlagen für die Umsetzung geschaffen (Stufe 50 %)", "in_progress"),
    25: ("Umsetzung aufgegriffen (Stufe 25 %)", "started"),
    0: ("keine Umsetzungsaktivitäten (Stufe 0 %)", "open"),
}
#: Der Bericht „Ernährungsstrategie: Umsetzungsstand“ (26/0431) als PDF.
_NUTRITION_DOCUMENT = 309762


def nutrition_rows() -> list[dict]:
    """Die fünf Tabellen „Nr. · Handlungsfeld · Priorität · Stand Umsetzung“ des Berichts.

    Die Tabellen sind Text (Bilder sind nur die Kreisdiagramme darunter). Die
    Stufe steht in der letzten Zelle über einem gezeichneten Balken;
    ``find_tables`` verliert sie dort, darum wird sie je Zeile nachgelesen.
    """
    import pymupdf

    rows: list[dict] = []
    with pymupdf.open(holen(_NUTRITION_DOCUMENT)) as doc:
        for pno in range(doc.page_count):
            page = doc[pno]
            for table in page.find_tables().tables:  # type: ignore[attr-defined]  # pymupdf ohne Typen
                cells = table.extract()
                if (cells[0][0] or "").strip() != "Nr.":
                    continue
                for values, row in zip(cells[1:], table.rows[1:], strict=True):
                    x0, y0, x1, y1 = row.bbox
                    last = row.cells[-1] or (x1 - 110, y0, x1, y1)
                    text = str(page.get_text("text", clip=pymupdf.Rect(last[0] - 2, y0 + 1, x1 + 2, y1 - 1)))
                    stage = re.search(r"(\d{1,3})\s*%", text)
                    if not stage or int(stage.group(1)) not in _NUTRITION_STAGES:
                        raise SystemExit(f"Ernährungsstrategie, Seite {pno + 1}: Zeile {values[0]!r} ohne Stufe")
                    rows.append({"code": (values[0] or "").strip(), "stage": int(stage.group(1)), "page": pno + 1})
    return rows


def ernaehrungsstrategie(store: CouncilStore) -> dict:
    rows = nutrition_rows()
    codes = [m["code"] for m in (plans.measures("ernaehrungsstrategie") or {"measures": []})["measures"]]
    if sorted(r["code"] for r in rows) != sorted(codes):
        raise SystemExit(f"Ernährungsstrategie: Bericht nennt {len(rows)} Ansätze, die Liste {len(codes)} — "
                         "oder die Kennungen weichen ab")
    said = re.search(r"Umsetzungsstand aller (\d+) Ansätze", " ".join(template_text(store, "26/0431").split()))
    if not said or int(said.group(1)) != len(rows):
        raise SystemExit(f"Ernährungsstrategie: {len(rows)} Zeilen gelesen, der Bericht sagt "
                         f"{said.group(1) if said else '—'}")
    tally = Counter(r["stage"] for r in rows)
    return {
        "plan": "ernaehrungsstrategie",
        "snapshots": [{
            "as_of": "2026-05",
            "source": {"kind": "template", "label": "Bericht „Ernährungsstrategie: Umsetzungsstand“",
                       "template": "26/0431", "url": RIS_DATEI.format(id=_NUTRITION_DOCUMENT), "fetched": None},
            "total": len(rows),
            "complete": True,
            "counts": [{"status_raw": raw, "status_norm": norm, "count": tally[stage]}
                       for stage, (raw, norm) in _NUTRITION_STAGES.items()],
            "measures": [{"code": r["code"], "status_raw": _NUTRITION_STAGES[r["stage"]][0],
                          "status_norm": _NUTRITION_STAGES[r["stage"]][1]} for r in rows],
        }],
        "notes": [
            {"text": "Die Stufen sind laut Bericht eine qualitative Einschätzung der Verwaltung, kein Messwert.",
             "url": None},
            {"text": "Zur Umsetzung beschlossen hat der Rat fünf der 68 Ansätze (24/0811); der Bericht ordnet "
                     "trotzdem alle ein.", "url": None},
        ],
    }


# ── Strategieplan Mobilität und Verkehr (smv2025) ──────────────────────────

def smv2025(store: CouncilStore) -> dict:
    """Der Stand jeder Einzelmaßnahme aus dem Anhang zum Lärmaktionsplan.

    Maßgeblich ist das Kürzel der letzten Spalte — laut Anhang „stellt [sie] den
    Umsetzungsstand dar“. Das Wort in der Spalte „Status“ weicht bei einzelnen
    Zeilen ab; wie oft, steht als Hinweis da, statt dass wir eine der beiden
    Spalten still bevorzugen.
    """
    rows = smv_rows()
    codes = [m["code"] for m in (plans.measures("smv2025") or {"measures": []})["measures"]]
    if [r["code"] for r in rows] != codes:
        raise SystemExit("smv2025: Anhang und Maßnahmenliste nennen nicht dieselben Nummern — "
                         "python scripts/plan_massnahmen.py --nur smv2025")
    tally = Counter(r["status_code"] for r in rows)
    def agrees(row: dict) -> bool:
        # „Nicht umgesetzt“ in Spalte 5 heißt in der Legende „nicht umgesetzt / aufgegeben“.
        word = row["status_word"].lower()
        return bool(word) and SMV_LEGEND[row["status_code"]][0].lower().startswith(word)

    differs = [r["code"] for r in rows if not agrees(r)]
    notes = [
        {"text": "Grundlage ist laut Anhang der Evaluationsbericht des Fachdienstes Mobilität von 2021, "
                 "aktualisiert im Oktober 2023. Dem Rat lag er als Anhang zur Fortschreibung des "
                 "Lärmaktionsplans vor; eine eigene Vorlage dazu hat Ratslotse nicht gefunden.", "url": None},
    ]
    if differs:
        notes.append({"text": f"Bei {len(differs)} Maßnahmen weicht das Wort in der Spalte „Status“ vom Kürzel "
                              "der letzten Spalte ab oder fehlt. Gezeigt ist das Kürzel, das laut Anhang den "
                              "Umsetzungsstand darstellt.", "url": None})
    return {
        "plan": "smv2025",
        "snapshots": [{
            "as_of": "2023-10",
            "source": {"kind": "attachment",
                       "label": "Anhang 1 zur Fortschreibung des Lärmaktionsplans",
                       "template": "24/0293/1", "url": RIS_DATEI.format(id=SMV_DOCUMENT), "fetched": None},
            "total": len(rows),
            "complete": True,
            "counts": [{"status_raw": raw, "status_norm": norm, "count": tally[code]}
                       for code, (raw, norm) in SMV_LEGEND.items()],
            "measures": [{"code": r["code"], "status_raw": SMV_LEGEND[r["status_code"]][0],
                          "status_norm": SMV_LEGEND[r["status_code"]][1]} for r in rows],
        }],
        "notes": notes,
    }


#: plan → Leser. Jeder prüft seine Zahlen selbst gegen die Quelle und bricht ab, wenn sie nicht aufgehen.
SOURCES: dict[str, Callable[[CouncilStore], dict]] = {
    "klimaschutzplan_2035": klimaschutzplan,
    "waermeplan": waermeplan,
    "aktionsplan_gewalt_2020": aktionsplan_gewalt_2020,
    "ernaehrungsstrategie": ernaehrungsstrategie,
    "smv2025": smv2025,
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
