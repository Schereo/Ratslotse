#!/usr/bin/env python3
"""Was die Pläne zu ihren Gebieten sagen — für die Karten aus ``plan_karten.py`` und ``plan_umrisse.py``.

Die Kartenbilder zeigen, WO ein Gebiet liegt; was es ist, steht daneben: in der Legende, in Steckbriefen,
Tabellen und Kenndaten. Dieses Modul liest das aus dem Text der PDFs (Textlayer, kein Sprachmodell) und
gibt es je Gebiet in einer Form zurück, die die Seite ohne weiteres Rechnen zeigt:

- ``summary``: eine kurze Zeile unter dem Namen („21 Betriebe · 2.000 m² Verkaufsfläche“),
- ``facts``: Kennzahlen als Paare (Bezeichnung, Wert) mit Seite,
- ``notes``: Listen und Absätze des Plans mit Überschrift und Seite (Defizite, Handlungskonzept,
  Stärken, Schwächen, die Sätze zum Stadtteil).

Was von Hand abgelesen ist (die Maßnahmen-Symbole des Masterplans, die Lage der geplanten Spielplätze),
steht hier als Konstante mit Seite. Jede Zahl steht so da, wie das Dokument sie schreibt.
"""
from __future__ import annotations

import re
import sys
from functools import cache
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(WURZEL / "scripts"))

RIS = "https://buergerinfo.oldenburg.de/getfile.php?id={id}&type=do"


def _norm(text: str) -> str:
    """Leerraum zusammenziehen, Trennungen am Zeilenende zurücknehmen — nicht aber „Dach- und Fassaden…“."""
    text = " ".join(text.split())
    return re.sub(r"(\w)- (?!und\b|oder\b|bis\b|bzw\b|sowie\b)(?=[a-zäöüß])", r"\1", text).strip()


@cache
def _doc(document_id: int):
    import pymupdf
    from plan_massnahmen import holen
    return pymupdf.open(holen(document_id))


@cache
def _texts(document_id: int) -> tuple[str, ...]:
    doc = _doc(document_id)
    return tuple(_norm(str(doc[i].get_text())) for i in range(len(doc)))


def fact(label: str, value: str, page: int | None = None) -> dict:
    return {"label": label, "value": value, "page": page}


def note(title: str, items: list[str], page: int | None, kind: str = "list") -> dict:
    """``kind``: ``list`` (Stichpunkte) oder ``text`` (Absätze des Plans, als Zitat gezeigt)."""
    return {"title": title, "kind": kind, "items": items, "page": page}


def _de(n: float, digits: int = 0) -> str:
    return f"{n:,.{digits}f}".replace(",", " ").replace(".", ",").replace(" ", ".")


# ── Was die Kategorien bedeuten (Legende und Gruppenkopf) ───────────────────

#: Je Plan und Art: was der Plan darunter versteht (in eigenen Worten nach der Seite) und die Seite.
GROUPS: dict[str, dict[str, tuple[str, int]]] = {
    "laermaktionsplan": {
        "Ruhiges Gebiet": ("Leise Grünflächen aus der Verschneidung von Lärmkarte und Grünflächen — „Ruhiger "
                           "Stadtraum“ oder landschaftlich geprägter Erholungsraum nach dem Leitfaden des "
                           "Umweltbundesamts.", 151),
        "Friedhof": ("Friedhöfe sollen unabhängig von der Lärmbelastung als Ruhiges Gebiet gelten.", 153),
        "Erholungsfläche": ("Öffentlich zugängliche, stadtweit bedeutende Erholungsgebiete mit einer Teilfläche "
                            "unter 60 dB(A).", 153),
    },
    "masterplan_stadtgruen": {
        "Maßnahmenbereich": ("Gebiete, in denen sich Defizite des Stadtgrüns überlagern — mit dringendem "
                             "Handlungsbedarf und eigenem Maßnahmenblatt.", 76),
    },
    "spielleitplanung": {
        "Suchraum für Spielplätze": ("Bebaute Gebiete ohne Spielplatz in erreichbarer Entfernung nach DIN "
                                     "18034-1 — dort fehlt ein Spielplatz.", 47),
        "Spielplatz in Planung": ("Spielplätze, die in den nächsten Jahren entstehen (Karte 8, gestrichelt).", 45),
    },
    "eek": {
        "Zentraler Versorgungsbereich Innenstadt": ("Der (ober-)zentrale Versorgungsbereich der Stadt.", 186),
        "Nahversorgungszentrum": ("Zentraler Versorgungsbereich eines Stadtteils — bis 2015 Stadtteilzentrum "
                                  "Typ B oder C.", 185),
        "Nahversorgungsstandort": ("Versorgt das Wohnumfeld, vor allem mit Lebensmitteln; kein zentraler "
                                   "Versorgungsbereich.", 157),
        "Fachmarktzentrum": ("Standort großflächiger Fachmärkte, kein zentraler Versorgungsbereich.", 186),
        "Fachmarktzentrum mit Nahversorgungsfunktion": ("Fachmarktzentrum, das zugleich die Wohngebiete ringsum "
                                                        "mit Lebensmitteln versorgt.", 185),
    },
    "waermeplan": {
        "Eignungsgebiet": ("Gebiet, in dem sich ein Wärmenetz wirtschaftlich betreiben lässt "
                           "(Wärmeliniendichte über 2,5 MWh je Meter und Jahr).", 79),
    },
}


def groups(key: str, document_id: int) -> dict[str, dict]:
    url = RIS.format(id=document_id)
    return {name: {"description": text, "page": page, "source_url": f"{url}#page={page}"}
            for name, (text, page) in GROUPS.get(key, {}).items()}


# ── Masterplan Stadtgrün ───────────────────────────────────────────────────

MSG_DOC_ID = 251236
#: Die Maßnahmenarten aus der Legende der Übersicht (Baumstrategie Abb. 8), in deren Reihenfolge.
MSG_KINDS = ("Ausbau Grüne Wege", "Aufwertung Gewässerumfeld", "Baumerhalt", "Baumpflanzung",
             "Dach- und Fassadenbegrünung", "Entsiegelung", "Attraktive Freiraumgestaltung", "Anlage Pocket Park")
#: Die Symbole neben der Nummer jeder Einzelkarte — von Hand abgelesen (10.11.2026), Baumerhalt (Baumgruppe)
#: und Pocket Park (Baum mit Bank) an vergrößerten Ausschnitten unterschieden. Nummer: Indizes in MSG_KINDS.
MSG_SYMBOLS = {
    "1": (3, 4, 6, 7), "2": (0, 3, 4, 5, 6, 7), "3": (0, 3, 4, 5, 7), "4": (0, 1, 2, 3, 5, 7),
    "5": (0, 2, 3, 4, 6, 7), "6": (2, 3, 4, 5), "7": (3, 4, 5, 6), "8": (0, 2, 3, 4, 6), "9": (3, 4, 5),
    "10": (3, 4), "11": (0, 1, 2, 3), "12": (0, 3, 6, 7),
}


def masterplan() -> dict[str, dict]:
    """Je Maßnahmenbereich: Defizite, Handlungskonzept, Maßnahmen (Absätze) und die Symbole der Karte."""
    doc = _doc(MSG_DOC_ID)
    blocks: dict[int, list[str]] = {}
    for i in range(1, len(doc) + 1):
        kept = []
        for b in doc[i - 1].get_text("blocks"):
            t = _norm(b[4])
            if not t or re.fullmatch(r"(Stadt Oldenburg|Masterplan Stadtgrün|\d+|Quelle: .*)", t) \
                    or t.startswith("Stadt Oldenburg Masterplan"):
                continue
            kept.append(t)
        blocks[i] = kept
    starts = []
    for i in range(60, len(doc) + 1):
        m = re.search(r"Maßnahmenbereich (\d+) – (.+?) Bestand", " ".join(blocks[i]))
        if m:
            starts.append((m.group(1), i))
    out = {}
    for n, (code, p0) in enumerate(starts):
        p1 = starts[n + 1][1] if n + 1 < len(starts) else p0 + 2
        paras = [(p, t) for p in range(p0, p1) for t in blocks[p]]
        text = " ".join(t for _, t in paras)
        m = re.search(r"Defizitäre Funktionserfüllung (.+?) Handlungskonzept (.+?) Maßnahmen (.+)$", text)
        if not m:
            raise SystemExit(f"Masterplan, Bereich {code}: Maßnahmenblatt nicht erkannt (S. {p0})")
        deficits = [x.strip() for x in re.split(r",(?![^()]*\))", m.group(1))]
        concept = [x.strip() for x in m.group(2).split("•") if x.strip()]
        k = next(i for i, (_, t) in enumerate(paras) if t == "Maßnahmen" or t.startswith("Maßnahmen "))
        first = paras[k][1][len("Maßnahmen"):].strip()
        measures = [t for t in ([first] if first else []) + [t for _, t in paras[k + 1:]]
                    if not re.match(r"Maßnahmenbereich \d+ –", t)]
        deficit_page = next(p for p, t in paras if "Defizitäre" in t)
        kinds = [MSG_KINDS[i] for i in sorted(MSG_SYMBOLS[code])]
        out[code] = {
            "summary": f"{len(kinds)} Maßnahmenarten",
            "facts": [fact("Maßnahmen laut Karte", ", ".join(kinds), p0)],
            "notes": [note("Defizite", deficits, deficit_page), note("Handlungskonzept", concept, deficit_page),
                      note("Maßnahmen", measures, paras[k][0], "text")],
        }
    return out


# ── Einzelhandelsentwicklungskonzept ────────────────────────────────────────

EEK_DOC_ID = 285989
#: Kapitel der Bestandsanalyse (Erhebung 2021) je Standort.
EEK_CHAPTERS = {
    "4.2": "innenstadt", "4.3": "nadorster-strasse-sued", "4.4": "hauptstrasse-eversten",
    "4.5": "nadorster-strasse-nord", "4.6": "osternburger-markt", "4.7": "scheideweg",
    "4.8": "cloppenburger-strasse", "4.9": "ofenerdiek", "4.10": "westkreuz", "4.11": "alexanderstrasse-nord",
    "4.12": "alexanderstrasse-sued", "4.13": "donnerschweer-strasse", "4.14": "bloherfelde-ost",
    "4.15": "edewechter-landstrasse", "5.2": "bloherfelde-west", "5.3": "hundsmuehler-strasse-nord",
    "5.4": "hundsmuehler-strasse-sued", "5.5": "kreyen-centrum", "6.1": "wechloy", "6.2": "stubbenweg",
    "6.3": "emsstrasse", "6.4": "kaufpark-kreyenbrueck",
}
_EEK_HEAD = re.compile(r"\b(\d\.\d+) (ZENTRALER VERSORGUNGSBEREICH|FACHMARKTZENTRUM|NAHVER|BLOHERFELDE WEST|"
                       r"HUNDSMÜHLER|KREYEN)")
_EEK_KEYS = re.compile(r"2012 2021 Betriebe (\d+) (\d+) Verkaufsfläche \(in m²\) ([\d.]+) ([\d.]+) Anzahl der "
                       r"Lebensmittelbetriebe (\d+) (\d+) Anzahl der Leerstände (\d+) (\d+)")


def einzelhandel(redrawn: set[str]) -> dict[str, dict]:
    """Je Standort die Kenndaten der Erhebung 2021 (mit 2012) und die Stärken und Schwächen aus der
    Bestandsanalyse. ``redrawn``: Standorte, deren Abgrenzung das Konzept 2023 neu zieht — dort gelten die
    Zahlen der alten Abgrenzung von 2015, und das steht dabei."""
    texts = _texts(EEK_DOC_ID)
    heads = sorted({(i, m.group(1)) for i, t in enumerate(texts, 1) if i > 20 for m in _EEK_HEAD.finditer(t)})
    out = {}
    for n, (p0, sec) in enumerate(heads):
        key = EEK_CHAPTERS.get(sec)
        if not key:
            continue
        p1 = heads[n + 1][0] + 1 if n + 1 < len(heads) else p0 + 6
        pages = range(p0, p1)
        text = " ".join(texts[p - 1] for p in pages)
        k = _EEK_KEYS.search(text)
        if not k:
            raise SystemExit(f"EEK {sec}: Kenndaten nicht gefunden (ab S. {p0})")
        shops0, shops1, area0, area1, food0, food1, empty0, empty1 = k.groups()
        kp = next(p for p in pages if "Verkaufsfläche (in m²)" in texts[p - 1])
        facts = [fact("Einzelhandelsbetriebe 2021", f"{shops1} (2012: {shops0})", kp),
                 fact("Verkaufsfläche 2021", f"{area1} m² (2012: {area0} m²)", kp),
                 fact("Lebensmittelbetriebe 2021", f"{food1} (2012: {food0})", kp),
                 fact("Leerstände 2021", f"{empty1} (2012: {empty0})", kp)]
        if key in redrawn:
            facts.append(fact("Bezug der Zahlen", "Abgrenzung von 2015 — 2023 neu gezogen", kp))
        notes = []
        s = re.search(r"Stärken (•.+?) Schwächen (•.+?)(?= Foto| Quelle| Karte \d| Abbildung| \d+ \d\.\d|"
                      r" \d\.\d+\.\d|$)", text)
        if s:
            sp = next(p for p in pages if "Stärken" in texts[p - 1])

            def bullets(chunk: str) -> list[str]:
                items = [re.split(r" Foto \d+:| Quelle:", y)[0] for y in chunk.split("•")]
                return [_norm(y).replace("Ł", "→").strip() for y in items if y.strip()]
            notes = [note("Stärken", bullets(s.group(1)), sp), note("Schwächen", bullets(s.group(2)), sp)]
        out[key] = {"summary": f"{shops1} Betriebe · {area1} m² Verkaufsfläche", "facts": facts, "notes": notes}
    missing = set(EEK_CHAPTERS.values()) - set(out)
    if missing:
        raise SystemExit(f"EEK: keine Kenndaten für {sorted(missing)}")
    return out


# ── Spielleitplanung ───────────────────────────────────────────────────────

SPL_DOC_ID = 306888
#: Spielplatztypen (Kap. 7.2.3, S. 36): Name, Einzugsradius, Zahl laut Text — gegen sie hält sich die
#: Erkennung der Kreise auf Karte 7.
SPL_TYPES = {
    "Stadtteilspielplatz": (1000, 6), "Stadtviertelspielplatz": (750, 5), "Quartiersspielplatz": (350, 37),
    "Nachbarschaftsspielplatz": (175, 92), "Ballspielfläche": (175, 5),
}
SPL_STEM = {"Stadtteilspielplatz": "Stadtteil", "Stadtviertelspielplatz": "Stadtviertel",
            "Quartiersspielplatz": "Quartiers", "Nachbarschaftsspielplatz": "Nachbarschafts"}
#: Geplante Spielplätze (Karte 8, S. 46, gestrichelt; Text S. 45): Kennung, Name, Typ, Wort, an dem der Satz
#: im Text zu erkennen ist. Die Lage sucht ``plan_karten`` um den Anker (Straße + Versatz in Pixeln, von
#: Hand an den Ausschnitten gesetzt).
SPL_PLANNED = [
    ("D15", "Fliegerhorst", "Stadtteilspielplatz", "Spielplatz des Typs a", "Anna-Schwarz-Straße", (0, 0), 40),
    ("D16", "Grundschule Fliegerhorst", "Quartiersspielplatz", "Schulspielplatz", "Anna-Schwarz-Straße",
     (-33, -13), 12),
    ("E27", "Schramperweg", "Nachbarschaftsspielplatz", "Typs d am Schramperweg", "Schramperweg", (25, -42), 12),
    ("A27", "Hohenmoorstraße", "Nachbarschaftsspielplatz", "Hohenmoorstraße", "Hohenmoorstraße", (7, -5), 12),
    ("F18", "Gerhard-Stalling-Straße", "Quartiersspielplatz", "Gerhard-Stalling-Straße", "Gerhard-Stalling-Straße",
     (-43, 30), 12),
    ("D07", "Bolzplatz am Eßkamp", "Ballspielfläche", "Bolzplatz", "Eßkamp", (-27, -23), 12),
]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])", text) if s.strip()]


def _expand(sentence: str) -> str:
    """„Dobben- und Gerichtsviertel“ → „Dobbenviertel und Gerichtsviertel“ (zum Suchen, nicht zum Zeigen)."""
    return re.sub(r"(\w+)- und (\w+?)(viertel|straße|feld)\b", r"\1\3 und \2\3", sentence)


def spielleitplanung_quotes(place_names: dict[str, str]) -> dict[str, list[dict]]:
    """Die Sätze aus der Auswertung (Kap. 7.2.3, S. 37) und den Suchräumen (Kap. 9.2, S. 47), die einen
    Stadtteil beim Namen nennen — je Ortsbereich, mit Seite."""
    texts = _texts(SPL_DOC_ID)
    out: dict[str, list[dict]] = {}
    for page in (37, 47):
        for s in _sentences(texts[page - 1]):
            wide = _expand(s)
            for pid, name in place_names.items():
                if re.search(rf"\b{re.escape(name)}\b", wide):
                    out.setdefault(pid, []).append({"text": s, "page": page})
    return out


def spielleitplanung_planned_quote(word: str) -> dict | None:
    texts = _texts(SPL_DOC_ID)
    hit = next((s for s in _sentences(texts[44]) if word in s), None)
    return {"text": hit, "page": 45} if hit else None


def playground_counts(counts: dict[str, int]) -> str:
    """{Typ: Zahl} → „2 Quartiers- und 5 Nachbarschaftsspielplätze; kein Stadtteil- oder Stadtviertelspielplatz“."""
    order = list(SPL_STEM)
    have = [t for t in order if counts.get(t)]
    big_missing = [t for t in order[:2] if not counts.get(t)]
    if not have:
        return "keiner"
    last = have[-1]
    words = [f"{counts[t]} {SPL_STEM[t]}-" for t in have[:-1]]
    words.append(f"{counts[last]} {SPL_STEM[last]}spielpl" + ("atz" if counts[last] == 1 else "ätze"))
    text = ", ".join(words[:-1]) + (" und " if len(words) > 1 else "") + words[-1]
    if big_missing:
        stems = [SPL_STEM[t] for t in big_missing]
        text += "; kein " + (f"{stems[0]}- oder {stems[1]}spielplatz" if len(stems) == 2 else f"{stems[0]}spielplatz")
    return text


# ── Lärmaktionsplan ────────────────────────────────────────────────────────

LAP_DOC_ID = 280381


def laerm_shares() -> dict[str, str]:
    """Tabelle 28/29 (S. 155): Nummer → Anteil der Fläche mit L_DEN unter 60 dB(A), wie er dort steht."""
    import plan_listen
    cemeteries, recreation = plan_listen.green_areas(_texts(LAP_DOC_ID)[154])
    return {r[0]: r[3].replace("%", " %") for r in cemeteries + recreation}


# ── Wärmeplan ──────────────────────────────────────────────────────────────

WNG_DOC_ID = 306748


def waermeplan(table: dict[str, list[str]]) -> dict[str, dict]:
    """Je Eignungsgebiet die Gebietsbeschreibung (ab S. 80): Versorgung laut Plan, Gebäude, Wärmebedarf
    heute (aus Tabelle 4, ``table``: Kennung → Zeile) und 2035, Treibhausgase, Heizungsanlagen.
    Nur, was dort in der erwarteten Einheit steht: Bei WNG 10 schreibt der Plan „33,71 MWh“, wo Tabelle 4
    33,7 GWh nennt — dort fällt der Wert für 2035 weg statt falsch dazustehen."""
    texts = _texts(WNG_DOC_ID)
    out = {}
    for i in range(79, 110):
        t = texts[i - 1] + " " + texts[i]
        for m in re.finditer(r"(WNG \d+) (.{2,40}?) (Eignungsgebiet zur [^.]+?) Gebietsbeschreibung: ", t):
            code = m.group(1)
            if code in out or m.start() > len(texts[i - 1]):
                continue
            body = t[m.end():m.end() + 3000]
            supply = re.search(r"mittels (.+)$", m.group(3))
            facts = []
            if supply:
                facts.append(fact("Versorgung laut Plan", supply.group(1).strip(), i))
            b = re.search(r"(?:etwa|rund|insgesamt) ([\d.]+) Gebäude", body)
            if b:
                facts.append(fact("Gebäude", b.group(1), i))
            row = table.get(code)
            if row:
                facts.append(fact("Wärmebedarf heute", row[3], 79))
            f = re.search(r"Zieljahr 2035 wird ein Wärmebedarf von etwa ([\d,]+) GWh/a prognostiziert\. Dies "
                          r"entspricht einer Reduktion um rund ([\d,]+) ?%", body)
            if f:
                facts.append(fact("Wärmebedarf 2035", f"{f.group(1)} GWh/a (−{f.group(2)} %)", i))
            c = re.search(r"Treibhausgasemissionen belaufen sich.{0,80}?auf (?:etwa|rund|ca\.) ([\d,]+) kt CO", body)
            if c:
                facts.append(fact("Treibhausgase heute", f"{c.group(1)} kt CO₂ im Jahr", i))
            h = re.search(r"Gesamtleistung von ca\. ([\d,]+) MW, bei einem durchschnittlichen Anlagenalter von (\d+) "
                          r"Jahren", body)
            if h:
                facts.append(fact("Heizungsanlagen", f"{h.group(1)} MW, im Schnitt {h.group(2)} Jahre alt", i))
            out[code] = {"summary": supply.group(1).strip() if supply else None, "facts": facts, "notes": []}
    return out
