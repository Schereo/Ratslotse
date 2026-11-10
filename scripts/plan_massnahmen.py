#!/usr/bin/env python3
"""Maßnahmenlisten der Pilotpläne aus den Dokumenten der Stadt lesen (Plan „Pläne“, Phase 2).

Schreibt ``council/plan_measures/<plan>.json``. Die Dateien sind eingecheckt
und geprüft (Zählabgleich gegen die Zahl der Stadt, Stichprobe gegen die
Quelle, Befunde im PR); dieses Skript macht sie **nachvollziehbar**, nicht
täglich neu. Ohne Modell — jede Liste steht in den Dokumenten als Text.

Quellen (öffentliches Ratsinformationssystem, ``getfile.php``), höflich
geholt — eigener User-Agent, mindestens 1 s Abstand — und unter
``~/.cache/ratslotse/plan-quellen/`` aufgehoben:

- Klimaschutzplan: Kurzübersicht Maßnahmen, Anlage 255735 zu 22/0910 (90)
- Wärmeplan: Abschlussbericht, Anlage 306748 zu 26/0236, Tabelle 7 (18)
- Ernährungsstrategie: Strategie-Entwurf, Anlage 286179 zu 24/0810 (68)
- Aktionsplan Gewalt 2026: Evaluation und Fortschreibung, Anlage 314635 zu 26/0681/1 (30)
- Aktionsplan Gewalt 2020: dieselbe Anlage, Anhang 4.1 — die Tabelle hat 91 Zeilen, der
  Text zählt 90 Empfehlungen. Der Stand steht dort als Zellfarbe (``violence_rows``).
- Mobilitätsplan: Ergebnis der Priorisierung, Anlage 275932 zu 24/0216 — die
  Anlage zählt nicht durch; aufgenommen ist, was sie namentlich nennt.

    python scripts/plan_massnahmen.py               # alle schreiben
    python scripts/plan_massnahmen.py --nur waermeplan
    python scripts/plan_massnahmen.py --pruefen     # nur vergleichen, nichts schreiben
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council import plans  # noqa: E402

CACHE = Path.home() / ".cache" / "ratslotse" / "plan-quellen"
RIS_DATEI = "https://buergerinfo.oldenburg.de/getfile.php?id={id}&type=do"
USER_AGENT = "Ratslotse/1.0 (+https://ratslotse.de; Pläne der Stadt)"
_letzter_abruf = 0.0


def holen(document_id: int) -> Path:
    """Die PDF-Datei einer Anlage — aus dem Zwischenspeicher oder höflich vom RIS."""
    global _letzter_abruf
    ziel = CACHE / f"{document_id}.pdf"
    if ziel.exists() and ziel.stat().st_size > 0:
        return ziel
    CACHE.mkdir(parents=True, exist_ok=True)
    warten = 1.5 - (time.monotonic() - _letzter_abruf)
    if warten > 0:
        time.sleep(warten)
    req = urllib.request.Request(RIS_DATEI.format(id=document_id), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        daten = r.read()
    _letzter_abruf = time.monotonic()
    if not daten.startswith(b"%PDF"):
        raise RuntimeError(f"Anlage {document_id}: keine PDF-Datei erhalten")
    ziel.write_bytes(daten)
    return ziel


def _seiten(document_id: int) -> list[str]:
    import pymupdf
    with pymupdf.open(holen(document_id)) as doc:
        return [str(doc[i].get_text()) for i in range(doc.page_count)]


_LIGATUREN = {"ﬂ ": "fl", "ﬀ ": "ff", "ﬁ ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬁ": "fi"}


def sauber(text: str) -> str:
    """Ligaturen, Silbentrennung am Zeilenende, Schrägstriche und Leerzeichen glätten."""
    for alt, neu in _LIGATUREN.items():
        text = text.replace(alt, neu)
    # Dieselbe Ligatur, schon aufgelöst, aber mit Lücke: „Verpfl egung“, „fi nden“.
    text = re.sub(r"(?<=\w)(fl|fi|ff) (?=[a-zäöüß])", r"\1", text)
    # „Koordinierungs-\nund Beratungsstelle“ ist ein Ergänzungsstrich, keine Silbentrennung.
    text = re.sub(r"(\w)-\s*\n\s*(?=(?:und|oder|bzw\.|sowie|bis)\b)", r"\1- ", text)
    text = re.sub(r"(\w)-\s*\n\s*(?=[a-zäöüß])", r"\1", text)
    text = re.sub(r"(\w)-\s*\n\s*(?=[A-ZÄÖÜ])", r"\1-", text)  # „Bio-\nZertifizierung“
    text = re.sub(r"\s*/\s*(?=[A-ZÄÖÜ])", " / ", text)  # „Gebäude/ Strom/ Wärme“
    return re.sub(r"\s+", " ", text).strip()


# ── Klimaschutzplan ────────────────────────────────────────────────────────

def klimaschutzplan() -> list[dict]:
    """Die Tabelle Themenfeld · Maßnahmenpaket · Nr. · Titel, über ``find_tables``.

    Themenfeld und Paket sind verbundene Zellen: Sie stehen in der ersten
    Zeile ihres Bereichs, darunter ``None``. Eine Zeile ohne Nummer setzt den
    Titel der vorigen fort („… in Bebauungs- und / Flächennutzungspläne“).
    """
    import pymupdf
    out: list[dict] = []
    feld = paket = ""
    with pymupdf.open(holen(255735)) as doc:
        for i in range(doc.page_count):
            pno, page = i + 1, doc[i]
            for tabelle in page.find_tables().tables:  # type: ignore[attr-defined]  # pymupdf ohne Typen
                for zeile in tabelle.extract()[1:]:  # ohne Kopfzeile
                    zellen = [(z or "").strip() for z in zeile]
                    if zellen[0]:
                        feld = sauber(zellen[0])
                    if zellen[1]:
                        paket = sauber(zellen[1])
                    nummer = next((m for z in zellen[2:5] if (m := re.fullmatch(r"(\S+)\s+(\d\d)\s*_", z))), None)
                    titel = sauber(" ".join(z for z in zellen[5:] if z))
                    if nummer:
                        out.append({"code": f"{nummer.group(1)}_{nummer.group(2)}", "title": titel,
                                    "field": feld, "package": paket, "page": pno})
                    elif titel and out:
                        out[-1]["title"] = sauber(out[-1]["title"] + " " + titel)
    return out


# ── Aktionsplan Gewalt 2020 ────────────────────────────────────────────────

#: Füllfarbe der Zelle „Evaluation“ in Anhang 4.1 → Name der Farbe in der Legende dort.
VIOLENCE_COLORS: dict[tuple[float, float, float], str] = {
    (0.33, 0.86, 0.24): "dark_green", (0.71, 0.88, 0.52): "light_green", (0.84, 0.91, 0.79): "pastel_green",
    (1.0, 0.75, 0.0): "yellow", (1.0, 0.67, 0.67): "red", (0.75, 0.75, 0.75): "grey",
}
_HEADER_GREY = (0.85, 0.85, 0.85)
#: Anhang 4.1 steht auf den PDF-Seiten 69–94 (gedruckt 64–89), quer gesetzt.
_VIOLENCE_PAGES = range(68, 94)
#: Spalten der Tabelle als y-Bereiche der gedrehten Seite.
_COL_EVALUATION, _COL_RECOMMENDATION, _COL_THEME = (63, 346), (437, 567), (678, 780)


def violence_rows() -> list[dict]:
    """Jede Zeile der Tabelle „Umsetzungsstand aller Handlungsempfehlungen“ mit ihrer Farbe.

    Der Stand steht dort **nur als Zellfarbe** — der Text allein verliert ihn.
    Eine Zeile ist, was zwischen zwei Linien liegt, die Empfehlung UND
    Evaluation queren (Themenfeld und Zuständigkeit sind über mehrere Zeilen
    verbunden). Läuft eine Zeile über den Seitenumbruch, setzt die erste Zeile
    der Folgeseite sie fort: gleiche Farbe, und der Text der Empfehlung fehlt
    oder schließt an einen offenen Satz an.
    """
    import pymupdf

    def fill(drawing) -> tuple[float, float, float] | None:
        f = drawing.get("fill")
        return (round(f[0], 2), round(f[1], 2), round(f[2], 2)) if f else None

    rows: list[dict] = []
    part = "Übergreifende Handlungsempfehlungen"
    with pymupdf.open(holen(314635)) as doc:
        for pno in _VIOLENCE_PAGES:
            page = doc[pno]
            drawings = page.get_drawings()
            evaluation: dict[int, float] = {}
            recommendation: dict[int, float] = {}
            for d in drawings:
                r = d["rect"]
                if fill(d) != (0.0, 0.0, 0.0) or r.width > 2.5 or r.height <= 20:
                    continue
                if r.y1 <= 350:
                    evaluation[round(r.x0)] = evaluation.get(round(r.x0), 0) + r.height
                elif r.y0 >= 430 and r.y1 <= 570:
                    recommendation[round(r.x0)] = recommendation.get(round(r.x0), 0) + r.height
            lines = sorted(x for x, h in evaluation.items()
                           if h >= 260 and sum(recommendation.get(x + k, 0) for k in (-1, 0, 1)) >= 110)
            lines = [x for i, x in enumerate(lines) if i == 0 or x - lines[i - 1] > 2]
            marks = []
            for m in re.finditer(r"Themenschwerpunkt „([^“]+)“", str(page.get_text())):
                hits = page.search_for("Themenschwerpunkt")
                if hits:
                    marks.append((min(h.x0 for h in hits), m.group(1)))
            first_on_page = True
            for a, b in zip(lines, lines[1:], strict=False):
                if b - a < 8:
                    continue
                for x, name in marks:
                    if a >= x - 3:
                        part = name
                inside = [d for d in drawings if d["rect"].x0 >= a - 1 and d["rect"].x1 <= b + 1]
                if any(fill(d) == _HEADER_GREY for d in inside):
                    continue  # Kopfzeile oder Zwischentitel

                def cell(column: tuple[int, int], a=a, b=b, page=page) -> str:
                    return sauber(str(page.get_text("text", clip=pymupdf.Rect(a + 1, column[0] + 1, b - 1, column[1] - 1))))

                colors: set[str] = set()
                for d in inside:
                    key = fill(d)
                    if key is not None and key in VIOLENCE_COLORS and d["rect"].y1 <= 350 and d["rect"].width >= 3:
                        colors.add(VIOLENCE_COLORS[key])
                title = cell(_COL_RECOMMENDATION)
                if not title and not colors:
                    continue
                if len(colors) > 1:
                    raise RuntimeError(f"Aktionsplan Gewalt, Seite {pno + 1}: Zeile mit zwei Farben {sorted(colors)}")
                last = rows[-1] if rows else None
                continues = bool(first_on_page and last and colors == {last["color"]} and (
                    not title or title[:1].islower() or not last["title"].rstrip().endswith((".", ")", "“"))))
                first_on_page = False
                if continues and last:
                    last["title"] = sauber(f"{last['title']} {title}")
                elif title and colors:
                    rows.append({"title": title, "field": part, "page": pno + 1, "color": colors.pop()})
                else:
                    raise RuntimeError(f"Aktionsplan Gewalt, Seite {pno + 1}: Zeile ohne Text oder ohne Farbe ({title[:40]!r})")
    return rows


def aktionsplan_gewalt_2020() -> list[dict]:
    """Die Stadt nummeriert die Empfehlungen nicht; die Kennung ist die Reihenfolge in ihrer Tabelle."""
    return [{"code": str(n), "title": row["title"], "field": row["field"], "page": row["page"]}
            for n, row in enumerate(violence_rows(), start=1)]


# ── Wärmeplan ──────────────────────────────────────────────────────────────

_WAERME_FELDER = {"K": "Kommunikation", "O": "Organisation", "F": "Förderung", "T": "Technik"}


def waermeplan() -> list[dict]:
    """Tabelle 7 im Abschlussbericht: „K1 - Kommunikation und Aktivierung …“."""
    out: list[dict] = []
    for pno, text in enumerate(_seiten(306748), start=1):
        if "Tabelle 7" not in text and not out:
            continue
        for m in re.finditer(r"(?m)^([KOFT]\d) - (.+?)\s*$", text):
            if m.group(1) not in {e["code"] for e in out}:
                out.append({"code": m.group(1), "title": sauber(m.group(2)),
                            "field": _WAERME_FELDER[m.group(1)[0]], "page": pno})
        if len(out) >= 18:
            break
    return out


# ── Ernährungsstrategie ────────────────────────────────────────────────────

def ernaehrungsstrategie() -> list[dict]:
    """„A11 Faire Produkte … stärken“ bis zur Zeile „Neuer Ansatz | Priorität: …“."""
    seiten = _seiten(286179)
    out: dict[str, dict] = {}
    feld = ""
    for pno, text in enumerate(seiten, start=1):
        # Die Handlungsfelder sind die Abschnitte 5.1 bis 5.5 („5.3 Mehrweg“).
        abschnitt = re.search(r"(?m)^5\.\d (\S.+?)\s*$", text)
        if abschnitt:
            feld = sauber(abschnitt.group(1))
        # Der Titel ist höchstens fünf Zeilen lang; darunter steht, ob der
        # Ansatz neu ist („Neuer Ansatz | Priorität: hoch“) oder schon läuft.
        for m in re.finditer(r"(?m)^(A\d{1,2}) ([^\n]+(?:\n[^\n]+){0,4}?)\n"
                             r"(?=Neuer Ansatz|Ansatz wird|Laufendes Vorhaben|[^\n]*\| Priorität)", text):
            code = m.group(1)
            if code not in out:
                out[code] = {"code": code, "title": sauber(m.group(2)), "field": feld, "page": pno}
    return sorted(out.values(), key=lambda e: int(e["code"][1:]))


# ── Aktionsplan Gewalt 2026 ────────────────────────────────────────────────

#: Die sechs Schwerpunktthemen (Kapitel 3.3.1–3.3.6 der Fortschreibung).
_GEWALT_2026_FELDER = {
    "1": "Informations- und Öffentlichkeitsarbeit",
    "2": "Prävention",
    "3": "Männer* im Kontext Häusliche Gewalt",
    "4": "Vernetzung",
    "5": "Schutz und Unterstützung",
    "6": "Digitale Gewalt",
}


def aktionsplan_gewalt_2026() -> list[dict]:
    """„Handlungsempfehlung 6.1 – Schaffung einer …“ in den Listen je Fokusthema."""
    out: dict[str, dict] = {}
    for pno, text in enumerate(_seiten(314635), start=1):
        flach = text.replace("\n", " ")
        for m in re.finditer(r"Handlungsempfehlung (\d\.\d) – (.+?)(?= Handlungsempfehlung \d\.\d –| Nummer |$)",
                             flach):
            code = m.group(1)
            if code not in out:
                # Eine Bildunterschrift („Quelle: …“) rutscht mitunter ans Listenende.
                titel = re.sub(r"\s*Quelle: .*$", "", sauber(m.group(2)))
                out[code] = {"code": code, "title": titel, "field": _GEWALT_2026_FELDER[code[0]],
                             "page": pno}
    return sorted(out.values(), key=lambda e: tuple(int(x) for x in e["code"].split(".")))


# ── Mobilitätsplan ─────────────────────────────────────────────────────────

def mobilitaetsplan() -> list[dict]:
    """Was Anlage 1 zu 24/0216 namentlich nennt (Seiten 8, 10–17).

    Die Anlage ist ein Foliensatz und zählt die „ca. 70“ priorisierten
    Maßnahmen nicht einzeln auf. Hier steht deshalb von Hand, was sie
    benennt — je Eintrag mit Seite; geprüft wird, dass jeder Name dort steht.
    """
    seiten = _seiten(275932)
    eintraege = [
        *[("Radverkehr – Premiumrouten", f"Premiumroute {n}", 8) for n in (
            "FAST FLIN (Fliegerhorst)", "Hatten-Sandkrug", "Wahnbek", "Bad Zwischenahn",
            "Tungeln-Wardenburg", "Ofen", "Petersfehn-Friedrichsfehn-Edewecht")],
        *[("Radverkehr – Fahrradstraßen", f"Fahrradstraße {n} nach neuen Standards", 8) for n in (
            "Haareneschstraße", "Katharinenstraße", "Haarenufer", "Huntestraße")],
        *[("Radverkehr – Fahrradstraßen", f"Neue Fahrradstraße {n}", 8) for n in (
            "Quellenweg", "Lindenallee", "Herbartstraße", "Bismarckstraße", "Roggemannstraße",
            "Am Schloßgarten", "Schleusenstraße", "Kanalstraße", "Herrenweg")],
        ("ÖPNV", "Wallring – durchgehende ÖPNV-Spur", 10),
        ("Mobilitätsstationen", "Teilkonzept Mobilitätsstationen (Carsharing, Stationen, Bikesharing)", 11),
        ("Ladeinfrastruktur", "Teilkonzept Ladeinfrastruktur (öffentliche Ladepunkte quartalsweise)", 14),
        ("Konzepterstellung", "Neuaufteilung von Verkehrsflächen am Beispiel Damm", 16),
        ("Parkraummanagement", "Bewohnerparkzone Haarenesch", 17),
        ("Parkraummanagement", "Quartiersparklösungen (z. B. Fliegerhorst)", 17),
        ("Parkraummanagement", "Erneuerung dynamisches Parkleitsystem", 17),
        ("P+R und B+R", "B+R: sieben neue Stationen", 17),
        ("P+R und B+R", "P+R: Stadt-Umland-Kooperation", 17),
        ("P+R und B+R", "P+R: Pflege und Aufwertung des Bestands", 17),
        ("SPNV", "Haltepunkt Ofenerdiek prüfen", 17),
        ("Fußverkehr", "Fußverkehr bei allen Planungen berücksichtigen und stärken", 17),
        ("Grundlagenarbeit", "Modal-Split-Untersuchung", 17),
    ]
    stichwort = {  # das Wort, das auf der genannten Seite stehen muss
        "Wallring – durchgehende ÖPNV-Spur": "ÖPNV-Spur", "Teilkonzept Mobilitätsstationen": "Mobilitätsstationen",
        "Teilkonzept Ladeinfrastruktur": "Ladepunkte", "Neuaufteilung": "Damm",
        "Erneuerung dynamisches Parkleitsystem": "Parkleitsystem", "B+R: sieben neue Stationen": "Sieben neue",
        "P+R: Stadt-Umland-Kooperation": "Stadt-Umland", "P+R: Pflege": "Aufwertung Bestand",
        "Haltepunkt Ofenerdiek": "Ofenerdiek", "Fußverkehr bei": "Fußverkehr", "Modal-Split": "Modal Split",
        "Quartiersparklösungen": "Quartiersparklösungen", "Bewohnerparkzone": "Haarenesch",
    }
    out = []
    for i, (feld, titel, seite) in enumerate(eintraege, start=1):
        wort = next((w for k, w in stichwort.items() if titel.startswith(k)), None)
        if wort is None:
            wort = re.sub(r"^(Premiumroute|Neue Fahrradstraße|Fahrradstraße) ", "", titel)
            wort = wort.removesuffix(" nach neuen Standards").split(" (")[0]
        if wort not in seiten[seite - 1]:
            raise RuntimeError(f"Mobilitätsplan: „{wort}“ steht nicht auf Seite {seite}")
        out.append({"code": f"M{i:02d}", "title": titel, "field": feld, "page": seite})
    return out


# ── Digitalisierungsstrategie und Agenda 2025: Titel aus dem Satzbild ──────

def _lines(page) -> list[tuple[float, float, float, bool, str]]:
    """(x, y, Schriftgröße, fett, Text) je Textzeile. Hochgestellte Fußnotenziffern
    („IoT⁴“) fallen weg — sie gehören nicht zum Titel."""
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip() and not s["flags"] & 1]
            if not spans:
                continue
            first = spans[0]
            out.append((first["origin"][0], first["origin"][1], round(first["size"], 1),
                        "Bold" in first["font"], " ".join("".join(s["text"] for s in spans).split())))
    return out


#: Der Umsetzungsplan (24/0574) gliedert seine Maßnahmen nach Wirkungskreis und Status
#: (Abschnitte 2.2.1 bis 2.2.5); 2.2.6 sind Indikatoren, keine Maßnahmen.
_DIGITAL_GROUPS = {
    "2.2.1": "Mit Außenwirkung, bereits laufend",
    "2.2.2": "Mit Außenwirkung, neu",
    "2.2.3": "Verwaltungsintern, laufend",
    "2.2.4": "Verwaltungsintern, neu",
    "2.2.5": "Aufrechterhaltung des Verwaltungsbetriebes, laufend",
}


def digitalisierungsstrategie() -> list[dict]:
    """Jede Maßnahme ist eine fette Zeile (11,2 pt) unter ihrer Abschnittsüberschrift (12 pt).

    Die Stadt nummeriert nicht; die Nummer ist die Reihenfolge im Umsetzungsplan. Eine zweite
    fette Zeile direkt darunter setzt den Titel fort.
    """
    import pymupdf
    out: list[dict] = []
    parts: list[list[str]] = []
    field: str | None = None
    last_y: float | None = None
    with pymupdf.open(holen(284226)) as doc:
        for pno in range(doc.page_count):
            for _x, y, size, bold, text in _lines(doc[pno]):
                section = re.match(r"(2\.2\.\d) ", text)
                if not bold or size not in (11.2, 12.0):
                    last_y = None
                    continue
                if size == 12.0:
                    field = _DIGITAL_GROUPS.get(section.group(1)) if section else None
                    last_y = None
                    continue
                if field is None:
                    continue
                if last_y is not None and 0 < y - last_y < 16:
                    parts[-1].append(text)
                else:
                    parts.append([text])
                    out.append({"code": str(len(out) + 1), "title": "", "field": field, "page": pno + 1})
                last_y = y
    for row, lines in zip(out, parts, strict=True):
        row["title"] = sauber("\n".join(lines))
    if {r["field"] for r in out} != set(_DIGITAL_GROUPS.values()):
        raise RuntimeError("Digitalisierungsstrategie: nicht alle fünf Abschnitte 2.2.1–2.2.5 gefunden")
    return out


#: Die vier „zentralen Bausteine“ der Agenda 2025; die Nummer eines Maßnahmenpakets beginnt mit ihrer Ziffer.
_AGENDA_BLOCKS = {
    "1": "Information und Beratung, gesellschaftliche Teilhabe und Partizipation",
    "2": "Gesundheitliche und pflegerische Versorgung",
    "3": "Wohnen und Mobilität",
    "4": "Steuerung und Vernetzung",
}


def agenda_2025_alter() -> list[dict]:
    """Die Tabellen „Nr. · Maßnahmenpakete · Beschreibung · Status · Federführung“ je Baustein.

    Gelesen wird über die Lage der Wörter: Die Nummer steht am linken Rand, der Titel in der
    Spalte daneben bis zur nächsten Nummer; wo die Spalte endet, sagt der Kopf „BESCHREIBUNG“.
    """
    import pymupdf
    out: list[dict] = []
    with pymupdf.open(holen(293527)) as doc:
        text = " ".join(" ".join(str(doc[i].get_text()).split()) for i in range(doc.page_count))
        for name in _AGENDA_BLOCKS.values():
            if name not in text:
                raise RuntimeError(f"Agenda 2025: Baustein „{name}“ steht nicht im Dokument")
        right: float | None = None
        for pno in range(doc.page_count):
            page = doc[pno]
            # (x, y, Wort) — pymupdf liefert die Wortliste ohne Typen.
            words = [(float(w[0]), float(w[1]), str(w[4])) for w in page.get_text("words")]
            head = [x for x, _y, word in words if word == "BESCHREIBUNG"]
            if head:
                right = head[0] - 4
            numbers = sorted((y, word) for x, y, word in words if re.fullmatch(r"[1-4]\.\d{1,2}", word) and x < 90)
            if not numbers or right is None:
                continue
            column = [ln for ln in _lines(page) if 95 < ln[0] < right and ln[2] > 9]
            for i, (y, code) in enumerate(numbers):
                until = numbers[i + 1][0] if i + 1 < len(numbers) else float("inf")
                title = sauber("\n".join(t for _x, ty, _size, _bold, t in column if y - 4 <= ty < until - 4))
                out.append({"code": code, "title": title, "field": _AGENDA_BLOCKS[code[0]], "page": pno + 1})
    # Je Baustein lückenlos durchnummeriert: 1.1, 1.2, … — sonst fehlt eine Zeile.
    for digit in _AGENDA_BLOCKS:
        codes = [r["code"] for r in out if r["code"].startswith(digit + ".")]
        if codes != [f"{digit}.{n}" for n in range(1, len(codes) + 1)] or not codes:
            raise RuntimeError(f"Agenda 2025: Baustein {digit} ist nicht lückenlos nummeriert: {codes}")
    return out


# ── Strategieplan Mobilität und Verkehr (smv2025) ──────────────────────────

#: Anhang 1 zur Fortschreibung des Lärmaktionsplans (24/0293/1): alle Einzelmaßnahmen des
#: smv2025 mit ihrem Umsetzungsstand, Stand Oktober 2023.
SMV_DOCUMENT = 280377
#: Kürzel der letzten Spalte → Wortlaut der Legende auf Seite 1 und unsere Einordnung.
#: Die Tabelle schreibt die Kürzel uneinheitlich („u“ und „U“); die Legende ist maßgeblich.
SMV_LEGEND = {
    "u": ("Umgesetzt", "done"),
    "iu": ("in Umsetzung", "in_progress"),
    "ip": ("in Planung", "started"),
    "v": ("Vorüberlegungen", "started"),
    "nb": ("noch nicht begonnen", "open"),
    "-": ("nicht umgesetzt / aufgegeben", "paused"),
}
#: Spalte 4 des Anhangs, in seinen Worten.
_SMV_HORIZON = {"k": "Kurzfristig", "m": "Mittelfristig", "l": "Langfristig"}


def smv_rows() -> list[dict]:
    """Die neun Spalten des Anhangs: Nr. · Maßnahme · Ziel · k/m/l · Status (Wort) · Erläuterung ·
    Weitere Umsetzung · Haushaltsmittel · Kürzel.

    Das Kürzel der letzten Spalte ist laut Anhang der Umsetzungsstand; das Wort in Spalte 5
    weicht bei einzelnen Zeilen davon ab und kommt als ``status_word`` mit.
    """
    import pymupdf
    rows: list[dict] = []
    with pymupdf.open(holen(SMV_DOCUMENT)) as doc:
        first = " ".join(str(doc[0].get_text()).split())
        for code, (label, _norm) in SMV_LEGEND.items():
            if not re.search(re.escape(label) + r"\s*\(" + re.escape(code) + r"\)", first, re.I):
                raise RuntimeError(f"smv2025: Legende „{label} ({code})“ steht nicht auf Seite 1")
        for pno in range(doc.page_count):
            for table in doc[pno].find_tables().tables:  # type: ignore[attr-defined]  # pymupdf ohne Typen
                for raw in table.extract():
                    if not (raw[0] or "").strip().isdigit():
                        continue  # Kopfzeile, Legende
                    if len(raw) != 9:
                        raise RuntimeError(f"smv2025, Seite {pno + 1}: Zeile {raw[0]!r} hat {len(raw)} Spalten")
                    code = " ".join((raw[8] or "").split()).lower()
                    horizon = (raw[3] or "").strip().lower()
                    if code not in SMV_LEGEND or horizon not in _SMV_HORIZON:
                        raise RuntimeError(f"smv2025, Seite {pno + 1}: Zeile {raw[0]!r} — Kürzel {raw[8]!r}, Frist {raw[3]!r}")
                    rows.append({"code": (raw[0] or "").strip(), "title": sauber(raw[1] or ""),
                                 "horizon": horizon, "status_code": code,
                                 "status_word": sauber(raw[4] or ""), "page": pno + 1})
    return rows


def smv2025() -> list[dict]:
    return [{"code": r["code"], "title": r["title"], "field": _SMV_HORIZON[r["horizon"]], "page": r["page"]}
            for r in smv_rows()]


#: plan → (Extraktor, Quelle, Zahl der Stadt, Hinweis zur Zählung)
QUELLEN: dict[str, tuple[Callable[[], list[dict]], dict, int | None, str | None]] = {
    "klimaschutzplan_2035": (klimaschutzplan, {
        "label": "Kurzübersicht der Maßnahmen", "document_id": 255735, "template": "22/0910",
        "as_of": "2022-11-25"}, 90,
        "So beschlossen am 19.12.2022. Laut Bericht 3/2026 (26/0750) sind es inzwischen 97 Maßnahmen."),
    "waermeplan": (waermeplan, {
        "label": "Abschlussbericht Kommunale Wärmeplanung, Tabelle 7", "document_id": 306748,
        "template": "26/0236", "as_of": "2026-03-23"}, 18, None),
    "ernaehrungsstrategie": (ernaehrungsstrategie, {
        "label": "Ernährungsstrategie", "document_id": 286179, "template": "24/0810",
        "as_of": "2024-12-12"}, 68,
        "68 Handlungsansätze; fünf davon hat der Rat zur Umsetzung beschlossen (24/0811)."),
    "aktionsplan_gewalt_2020": (aktionsplan_gewalt_2020, {
        "label": "Evaluation und Fortschreibung, Anhang 4.1", "document_id": 314635,
        "template": "26/0681/1", "as_of": "2026-08"}, None,
        "Die Evaluation zählt 90 Handlungsempfehlungen; ihre Tabelle im Anhang hat 91 Zeilen. "
        "Die Stadt nummeriert sie nicht — die Nummer ist die Reihenfolge in ihrer Tabelle."),
    "aktionsplan_gewalt_2026": (aktionsplan_gewalt_2026, {
        "label": "Evaluation und Fortschreibung, Kapitel 3", "document_id": 314635,
        "template": "26/0681/1", "as_of": "2026-08"}, 30,
        "Sechs Fokusthemen mit je fünf Handlungsempfehlungen."),
    "mobilitaetsplan_2030": (mobilitaetsplan, {
        "label": "Ergebnis der Maßnahmenpriorisierung, Anlage 1", "document_id": 275932,
        "template": "24/0216", "as_of": "2024-04"}, None,
        "Die Anlage nennt diese Maßnahmen namentlich. Insgesamt wurden laut Anlage „ca. 70“ "
        "von über 250 Einzelmaßnahmen priorisiert; eine vollständige Liste liegt dem Rat nicht vor."),
    "digitalisierungsstrategie": (digitalisierungsstrategie, {
        "label": "Umsetzungsplan zur Digitalisierungsstrategie, Abschnitte 2.2.1 bis 2.2.5", "document_id": 284226,
        "template": "24/0574", "as_of": "2024-10-24"}, None,
        "Erste Phase des Umsetzungsplans (2025 bis 2027). Die Stadt zählt und nummeriert die Maßnahmen "
        "nicht — die Nummer ist die Reihenfolge im Umsetzungsplan."),
    "agenda_2025_alter": (agenda_2025_alter, {
        "label": "Agenda 2025, Maßnahmenpakete der vier zentralen Bausteine", "document_id": 293527,
        "template": "25/0403", "as_of": "2025-06"}, None,
        "Die Agenda nummeriert ihre Maßnahmenpakete je Baustein, nennt aber keine Gesamtzahl. "
        "Ein Paket kann mehrere Teilmaßnahmen (A, B, …) enthalten."),
    "smv2025": (smv2025, {
        "label": "Anhang 1 zur Fortschreibung des Lärmaktionsplans: Einzelmaßnahmen des smv2025",
        "document_id": SMV_DOCUMENT, "template": "24/0293/1", "as_of": "2023-10"}, None,
        "Der Anhang nummeriert bis 126, enthält aber 112 Zeilen: Die Nummern 86, 87 und 89 bis 100 "
        "kommen darin nicht vor. Die Gruppen sind die Fristen des Plans (kurz-, mittel-, langfristig)."),
}


def bauen(key: str) -> dict:
    extraktor, quelle, zahl, hinweis = QUELLEN[key]
    massnahmen = extraktor()
    codes = [m["code"] for m in massnahmen]
    if len(codes) != len(set(codes)):
        raise RuntimeError(f"{key}: doppelte Kennungen")
    if zahl is not None and len(massnahmen) != zahl:
        raise RuntimeError(f"{key}: {len(massnahmen)} Maßnahmen gelesen, die Stadt zählt {zahl}")
    return {"plan": key, "source": {**quelle, "url": RIS_DATEI.format(id=quelle["document_id"])},
            "count_city": zahl, "count_note": hinweis, "measures": massnahmen}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--nur", help="ein Plan-Schlüssel")
    ap.add_argument("--pruefen", action="store_true", help="nur vergleichen, nichts schreiben")
    args = ap.parse_args(argv)
    abweichung = False
    for key in [args.nur] if args.nur else list(QUELLEN):
        neu = bauen(key)
        pfad = plans.MEASURES_DIR / f"{key}.json"
        text = json.dumps(neu, ensure_ascii=False, indent=1) + "\n"
        alt = pfad.read_text(encoding="utf-8") if pfad.exists() else None
        if args.pruefen:
            gleich = alt == text
            abweichung |= not gleich
            print(f"{'✓' if gleich else '✗'} {key}: {len(neu['measures'])} Maßnahmen")
            continue
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(text, encoding="utf-8")
        print(f"✓ {key}: {len(neu['measures'])} Maßnahmen → {pfad.relative_to(WURZEL)}")
    return 1 if abweichung else 0


if __name__ == "__main__":
    raise SystemExit(main())
