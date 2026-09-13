"""Sharepics je Liste, je Liste im Wahlbereich und je Person — das PNG hinter
``GET /api/wahlabend/karte.png``.

Das Bild in ``image.py`` zeigt den ganzen Rat. Hier geht es um EINE Liste
oder EINE Person: wie sie abgeschnitten hat, anschaulich genug, dass man es
in den Familienchat oder auf Instagram stellt — und mit Lotti, die den
Wählenden dankt. Drei Karten, dieselbe Bühne:

* **Liste stadtweit** — Anteil, Sitze, Stimmen mit dem Abstand zu 2021, der
  Rang unter den Listen und ein Halbkreis, in dem nur die eigenen Sitze
  Farbe tragen.
* **Liste im Wahlbereich** — Anteil und Sitze dort, dazu die Personenstimmen
  der Bewerber*innen als Balken; wer einzieht, in Hafenblau.
* **Person** — Personenstimmen, Platz nach Stimmen, Status (direkt, über die
  Liste, über einen anderen Wahlbereich, nicht gewählt) und dieselben Balken
  mit der eigenen Zeile hervorgehoben.

Was hier NICHT passiert: rechnen. Gezeichnet wird, was ``service.live()``
bzw. ``service.probe()`` liefern — die Sitze stammen aus derselben Zuteilung
wie die Seite, sonst zeigte die Karte etwas anderes als der Bildschirm.

Lotti kommt aus den Sprite-Sheets der iOS-App (``LottiSprite*.png``, 384 px
je Kachel, zeilenweise, Rest der letzten Zeile leer): Das Repo hat sie
ohnehin, und sie sind groß genug für 300 px im fertigen Bild. Fehlt eine
Datei, gibt es die Karte ohne Lotti — nie einen Fehler; dasselbe gilt für
die Schriften (``image._font``).

Parteifarben bleiben, was die Designsprache erlaubt: Punkte, kein Flächen-
anstrich. Die Balken tragen Hafenblau (drin) oder Grau (nicht drin).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from ..antworten import (
    ElectionArea,
    ElectionAreaParty,
    ElectionCandidate,
    ElectionNight,
    ElectionParty,
)
from .image import (
    BG,
    BORDER,
    BRICOLAGE,
    EMPTY,
    HEIGHT,
    INTER,
    MARGIN,
    MONO,
    MUTED,
    SCALE,
    TEXT,
    WIDTH,
    AnyFont,
    _clock,
    _color,
    _date,
    _number,
    _Sheet,
    semicircle,
)

_log = logging.getLogger("ratslotse.web.wahlabend")

#: Primär „Hafenblau" der Designsprache, hell: hsl(205 92% 34%).
PRIMARY = "#0768A7"
#: Orange als Text braucht die dunklere Stufe (Designsprache: orange-800).
SIGNAL_INK = "#9A3412"
CARD = "#FFFFFF"
#: Erfolg-Tint (gewählt) und neutraler Tint (nicht gewählt).
OK_BG, OK_INK = "#DCFCE7", "#15803D"
NEUTRAL_BG, NEUTRAL_INK = "#E8EFF6", "#58697A"

#: Die rechte Spalte gehört Lotti: ab hier steht kein Text mehr.
COLUMN = 760
LOTTI_BOX = 320

SPRITE_DIR = Path(__file__).resolve().parents[4] / "ios" / "Resources" / "Assets.xcassets"
TILE = 384

#: Regung -> (Sprite-Sheet, Bild darin). Die Nummern sind von Hand gewählt:
#: der Sprung auf dem höchsten Punkt, die Flügel beim Klatschen zusammen,
#: der Flügel beim Winken oben.
POSES: dict[str, tuple[str, int]] = {
    "jubelt": ("LottiSpriteCelebrate", 3),
    "klatscht": ("LottiSpriteClap", 4),
    "winkt": ("LottiSpriteWave", 11),
}

Kind = str  # "party" | "area" | "candidate"


# ------------------------------------------------------------------ Auswahl

@dataclass(frozen=True)
class Selection:
    """Was die Karte zeigt — aufgelöst gegen den Stand, oder ``None``."""
    party: ElectionParty
    area: ElectionArea | None = None
    area_party: ElectionAreaParty | None = None
    candidate: ElectionCandidate | None = None

    @property
    def kind(self) -> Kind:
        if self.candidate is not None:
            return "candidate"
        if self.area is not None:
            return "area"
        return "party"


def select(data: ElectionNight, slug: str, area: int | None, position: int | None) -> Selection | None:
    """Liste, Wahlbereich und Listenplatz gegen den Stand auflösen. ``None``,
    wenn es die Kombination nicht gibt (unbekannte Liste, Liste tritt im
    Wahlbereich nicht an, Listenplatz leer)."""
    party = next((p for p in data["parties"] if p["slug"] == slug), None)
    if party is None:
        return None
    if area is None:
        return Selection(party) if position is None else None
    area_row = next((a for a in data["areas"] if a["number"] == area), None)
    if area_row is None:
        return None
    area_party = next((p for p in area_row["parties"] if p["slug"] == slug), None)
    if area_party is None:
        return None
    if position is None:
        return Selection(party, area_row, area_party)
    candidate = next((c for c in area_party["candidates"] if c["position"] == position), None)
    if candidate is None:
        return None
    return Selection(party, area_row, area_party, candidate)


# ------------------------------------------------------------------ Texte

def _pct(value: float | None) -> str:
    if value is None:
        return "–"
    return f"{value:.1f}".replace(".", ",") + " %"


def _signed(value: float, digits: int = 1) -> str:
    text = f"{abs(value):.{digits}f}".replace(".", ",")
    return ("+" if value > 0 else "−") + text


def _share_delta(party: ElectionParty) -> str:
    now, before = party["share_pct"], party["share_2021_pct"]
    if now is None:
        return ""
    if before is None:
        return "neu angetreten"
    diff = round(now - before, 1)
    if abs(diff) < 0.05:
        return "wie 2021"
    return f"{_signed(diff)} Punkte zu 2021"


def _seat_delta(party: ElectionParty, seats: int) -> str:
    before = party["seats_2021"]
    if before is None:
        return "neu angetreten"
    diff = seats - before
    if diff == 0:
        return "wie 2021"
    word = "Sitz" if abs(diff) == 1 else "Sitze"
    return f"{_signed(diff, 0)} {word} zu 2021"


def _rank(data: ElectionNight, party: ElectionParty) -> str:
    ranked = sorted((p for p in data["parties"] if p["votes"] is not None),
                    key=lambda p: (-(p["votes"] or 0), p["index"]))
    if party["votes"] is None or party not in ranked:
        return ""
    rank = ranked.index(party) + 1
    words = {1: "Stärkste", 2: "Zweitstärkste", 3: "Drittstärkste"}
    if rank in words:
        return f"{words[rank]} Liste in Oldenburg"
    return f"Platz {rank} von {len(ranked)} Listen in Oldenburg"


def _person_name(name: str) -> str:
    """„Gerding, Anne Gesa" → „Anne Gesa Gerding"; ohne Komma bleibt es."""
    last, sep, first = name.partition(",")
    return f"{first.strip()} {last.strip()}" if sep else name.strip()


def _status(candidate: ElectionCandidate, phase: str, persons: bool) -> tuple[str, str, str]:
    """(Text, Hintergrund, Schrift) des Status-Chips."""
    if not persons or candidate["votes"] is None:
        return "Personenstimmen fehlen noch", NEUTRAL_BG, NEUTRAL_INK
    how = {"direct": "direkt", "list": "über die Liste", "transfer": "über einen anderen Wahlbereich"}
    prefix = "Zwischenstand: " if phase == "counting" else ""
    if candidate["elected"]:
        return f"{prefix}gewählt · {how.get(candidate['elected'], candidate['elected'])}", OK_BG, OK_INK
    return f"{prefix}nicht gewählt", NEUTRAL_BG, NEUTRAL_INK


def _kicker(data: ElectionNight, sel: Selection) -> str:
    parts = ["RATSWAHL OLDENBURG", _date(data["election"].get("date"))]
    if data["dataset"] == "probe":
        parts.append("GENERALPROBE MIT ZAHLEN VON 2021")
    elif data["phase"] == "complete":
        parts.append("VORLÄUFIGES ERGEBNIS")
    else:
        p = data["progress"]
        parts.append(f"ZWISCHENSTAND · {p['districts_counted']} VON {p['districts_total']} BEZIRKEN")
    if sel.area is not None:
        parts.append(f"WAHLBEREICH {sel.area['roman']}")
    return " · ".join(x for x in parts if x)


def _thanks(data: ElectionNight, sel: Selection) -> str:
    """Lottis Sprechblase: das Danke an die Wählenden — mit der Zahl, wenn
    der Stand sie schon hergibt."""
    if sel.area is not None:
        voters = sel.area["totals"]["voters"]
        where = sel.area["name"]
        if sel.candidate is not None:
            head = "Glückwunsch zum Sitz im Rat! " if sel.candidate["elected"] else "Danke fürs Antreten! "
            if voters:
                return f"{head}Und danke an die {_number(voters)} Menschen, die in {where} gewählt haben."
            return f"{head}Und danke an alle, die in {where} gewählt haben."
        if voters:
            return f"Danke an die {_number(voters)} Menschen, die in {where} gewählt haben!"
        return f"Danke an alle, die in {where} gewählt haben!"
    voters = data["totals"]["voters"]
    turnout = data["totals"]["turnout_pct"]
    if voters:
        text = f"Danke an die {_number(voters)} Oldenburger*innen, die gewählt haben!"
        if turnout:
            text += f" Wahlbeteiligung {_pct(turnout)}."
        return text
    return "Danke an alle Oldenburger*innen, die gewählt haben!"


def _pose(sel: Selection, data: ElectionNight) -> str:
    if sel.candidate is not None:
        return "jubelt" if sel.candidate["elected"] else "winkt"
    if sel.area is None and _rank(data, sel.party).startswith("Stärkste"):
        return "jubelt"
    return "klatscht"


# ------------------------------------------------------------------ Lotti

_sprite_cache: dict[tuple[str, int], Image.Image | None] = {}


def _frame(sheet: str, index: int) -> Image.Image | None:
    key = (sheet, index)
    if key in _sprite_cache:
        return _sprite_cache[key]
    frame: Image.Image | None = None
    try:
        path = SPRITE_DIR / f"{sheet}.imageset" / f"{sheet}.png"
        with Image.open(path) as im:
            cols = max(im.width // TILE, 1)
            x, y = (index % cols) * TILE, (index // cols) * TILE
            frame = im.convert("RGBA").crop((x, y, x + TILE, y + TILE))
    except Exception as exc:  # fehlende Datei, kaputtes PNG — Karte ohne Lotti
        _log.info("Wahlabend: Lotti-Sprite %s fehlt (%s)", sheet, exc)
    _sprite_cache[key] = frame
    return frame


def _lotti(sheet: _Sheet, pose: str, x: float, y: float, size: float) -> None:
    name, index = POSES.get(pose, POSES["klatscht"])
    frame = _frame(name, index)
    if frame is None:
        return
    px = int(round(size * sheet.scale))
    scaled = frame.resize((px, px), Image.Resampling.LANCZOS)
    sheet.image.paste(scaled, (int(round(x * sheet.scale)), int(round(y * sheet.scale))), scaled)


# ------------------------------------------------------------------ Zeichenhilfen

def _wrap(sheet: _Sheet, text: str, font: AnyFont, width: float) -> list[str]:
    lines: list[str] = []
    line = ""
    for word in text.split():
        probe = f"{line} {word}".strip()
        if line and sheet.width_of(probe, font) > width:
            lines.append(line)
            line = word
        else:
            line = probe
    if line:
        lines.append(line)
    return lines


def _fit(sheet: _Sheet, text: str, file: str, size: float, weight: int, width: float,
         floor: float = 26) -> AnyFont:
    """Die größte Schrift bis ``size``, in der ``text`` in ``width`` passt."""
    while size > floor:
        font = sheet.font(file, size, weight)
        if sheet.width_of(text, font) <= width:
            return font
        size -= 2
    return sheet.font(file, floor, weight)


def _ellipsis(sheet: _Sheet, text: str, font: AnyFont, width: float) -> str:
    if sheet.width_of(text, font) <= width:
        return text
    while text and sheet.width_of(text + "…", font) > width:
        text = text[:-1].rstrip()
    return text + "…"


def _rounded(sheet: _Sheet, x1: float, y1: float, x2: float, y2: float, radius: float,
             fill: str, outline: str | None = None) -> None:
    s = sheet._s
    sheet.draw.rounded_rectangle((s(x1), s(y1), s(x2), s(y2)), radius=s(radius), fill=fill,
                                 outline=outline, width=max(int(s(1)), 1) if outline else 0)


def _chip(sheet: _Sheet, x: float, y: float, text: str, bg: str, ink: str) -> float:
    font = sheet.font(INTER, 15, 600)
    width = sheet.width_of(text, font) + 24
    _rounded(sheet, x, y, x + width, y + 30, 15, bg)
    sheet.text(x + 12, y + 7, text, font, ink)
    return width


def _bubble(sheet: _Sheet, text: str, x1: float, y1: float, x2: float, tail_x: float) -> float:
    """Lottis Sprechblase, Schwanz nach unten. Gibt die untere Kante zurück."""
    font = sheet.font(INTER, 18, 500)
    pad, lead = 20.0, 26.0
    lines = _wrap(sheet, text, font, x2 - x1 - 2 * pad)
    y2 = y1 + 2 * pad + lead * len(lines) - 4
    _rounded(sheet, x1, y1, x2, y2, 18, CARD, BORDER)
    s = sheet._s
    tail = [(s(tail_x - 14), s(y2 - 1)), (s(tail_x + 14), s(y2 - 1)), (s(tail_x), s(y2 + 16))]
    sheet.draw.polygon(tail, fill=CARD, outline=BORDER)
    sheet.draw.line([tail[0], tail[1]], fill=CARD, width=max(int(s(2)), 1))
    for i, line in enumerate(lines):
        sheet.text(x1 + pad, y1 + pad + i * lead, line, font, TEXT)
    return y2


def _stat(sheet: _Sheet, x: float, y: float, label: str, value: str, note: str,
          note_ink: str = MUTED, value_size: float = 58) -> float:
    """Kicker, große Zahl, Zeile darunter. Gibt die gebrauchte Breite zurück."""
    kicker = sheet.font(MONO, 12)
    big = sheet.font(BRICOLAGE, value_size, 800)
    small = sheet.font(INTER, 15, 500)
    sheet.text(x, y, label, kicker, MUTED, tracking=1.2)
    sheet.text(x, y + 22, value, big, TEXT)
    if note:
        sheet.text(x, y + 22 + value_size + 10, note, small, note_ink)
    return max(sheet.width_of(label, kicker, 1.2), sheet.width_of(value, big),
               sheet.width_of(note, small) if note else 0)


def _bars(sheet: _Sheet, candidates: list[ElectionCandidate], x: float, y: float, width: float,
          highlight: int | None, row: float = 24.0, limit: int = 10) -> int:
    """Personenstimmen als Balken, Listenreihenfolge. Blau = zieht ein; die
    hervorgehobene Person fett und in Blau, auch wenn sie nicht drin ist.

    Mehr als ``limit`` Zeilen passen nicht; dann fallen die hinteren weg —
    nur die hervorgehobene Person nie: Sie rückt als letzte Zeile nach.
    Gibt zurück, wie viele Bewerber*innen nicht zu sehen sind."""
    rows = list(candidates[:limit])
    if highlight is not None and not any(c["position"] == highlight for c in rows):
        mine = next((c for c in candidates if c["position"] == highlight), None)
        if mine is not None:
            rows = rows[: max(limit - 1, 0)] + [mine]
    hidden = len(candidates) - len(rows)
    max_votes = max((c["votes"] or 0 for c in candidates), default=0)
    name_w, count_w, gap = 200.0, 64.0, 12.0
    bar_x, bar_w = x + name_w + gap, width - name_w - count_w - 2 * gap
    for i, c in enumerate(rows):
        yy = y + i * row
        mine = highlight is not None and c["position"] == highlight
        drin = c["elected"] is not None
        name_font = sheet.font(INTER, 13, 700 if (mine or drin) else 500)
        pos_font = sheet.font(MONO, 11)
        sheet.text(x, yy + 3, str(c["position"]), pos_font, MUTED)
        sheet.text(x + 22, yy + 2, _ellipsis(sheet, _person_name(c["name"]), name_font, name_w - 22),
                   name_font, TEXT if (mine or drin) else MUTED)
        votes = c["votes"]
        track_y1, track_y2 = yy + 6, yy + 14
        _rounded(sheet, bar_x, track_y1, bar_x + bar_w, track_y2, 4, "#E1E9F1")
        if votes is not None and max_votes > 0 and votes > 0:
            w = max(bar_w * votes / max_votes, 6)
            _rounded(sheet, bar_x, track_y1, bar_x + w, track_y2, 4,
                     PRIMARY if (drin or mine) else "#9AA9B8")
        count = _number(votes) if votes is not None else "–"
        count_font = sheet.font(INTER, 13, 700 if mine else 500)
        sheet.text(x + width - sheet.width_of(count, count_font), yy + 2, count, count_font,
                   TEXT if (mine or drin) else MUTED)
    if hidden > 0:
        note = f"… und {hidden} weitere auf der Liste" if hidden > 1 else "… und eine weitere Person auf der Liste"
        sheet.text(x, y + len(rows) * row + 2, note, sheet.font(INTER, 12, 400), MUTED)
    return hidden


# ------------------------------------------------------------------ Bild

def render(data: ElectionNight, sel: Selection) -> bytes:
    """Die Karte als PNG (1200×630)."""
    sheet = _Sheet(WIDTH, HEIGHT, SCALE, BG)
    _header(sheet, data, sel)
    if sel.kind == "party":
        _party(sheet, data, sel)
    elif sel.kind == "area":
        _area(sheet, data, sel)
    else:
        _candidate(sheet, data, sel)
    _lotti_column(sheet, data, sel)
    _footer(sheet, data)
    return sheet.png(WIDTH, HEIGHT)


def _header(sheet: _Sheet, data: ElectionNight, sel: Selection) -> None:
    sheet.text(MARGIN, 42, _kicker(data, sel), sheet.font(MONO, 13), MUTED, tracking=1.3)
    party = sel.party
    if sel.candidate is not None:
        c = sel.candidate
        title = _person_name(c["name"])
        font = _fit(sheet, title, BRICOLAGE, 54, 800, COLUMN - MARGIN)
        sheet.text(MARGIN, 66, title, font, TEXT)
        bits = [c["occupation"], f"Jahrgang {c['born']}" if c["born"] else None]
        sub = " · ".join(b for b in bits if b)
        area = sel.area
        where = f"Liste {party['short']} · Wahlbereich {area['roman']} ({area['name']})" if area else ""
        sub = f"{sub} · {where}" if sub and where else (sub or where)
    else:
        font = _fit(sheet, party["short"], BRICOLAGE, 54, 800, COLUMN - MARGIN - 30)
        sheet.circle(MARGIN + 11, 98, 11, _color(party["color"], MUTED))
        sheet.text(MARGIN + 34, 66, party["short"], font, TEXT)
        if sel.area is not None:
            a = sel.area
            counted = f"{a['districts_counted']} von {a['districts_total']} Bezirken ausgezählt"
            sub = f"Wahlbereich {a['roman']} · {a['name']} · {counted}"
        else:
            sub = party["name"]
    sub_font = sheet.font(INTER, 18, 400)
    sheet.text(MARGIN, 134, _ellipsis(sheet, sub, sub_font, COLUMN - MARGIN), sub_font, MUTED)
    sheet.line(MARGIN, 178, COLUMN, 178, BORDER, 1)


def _party(sheet: _Sheet, data: ElectionNight, sel: Selection) -> None:
    p = sel.party
    seats = p["seats"] or 0
    total = int(data["election"]["seats"])
    y = 200.0
    x = float(MARGIN)
    x += _stat(sheet, x, y, "STIMMENANTEIL", _pct(p["share_pct"]), _share_delta(p), SIGNAL_INK) + 44
    word = "SITZ IM RAT" if seats == 1 else "SITZE IM RAT"
    x += _stat(sheet, x, y, word, str(seats), _seat_delta(p, seats), SIGNAL_INK) + 44
    valid = data["totals"]["valid_votes"]
    note = f"von {_number(valid)} gültigen" if valid else ""
    _stat(sheet, x, y, "STIMMEN", _number(p["votes"] or 0), note)

    rank = _rank(data, p)
    if rank:
        sheet.text(MARGIN, 328, rank, sheet.font(INTER, 19, 600), TEXT)

    # Halbkreis: nur die eigenen Sitze tragen Farbe — links wie im Web, damit
    # die Position im Rat dieselbe ist wie auf der Seite.
    cx, cy, radius = MARGIN + 165.0, 556.0, 165.0
    parties = sorted(data["parties"], key=lambda q: q["index"])
    seated: list[str | None] = []
    for q in parties:
        seated += [q["slug"]] * (q["seats"] or 0)
    seated = (seated + [None] * total)[:total]
    for i, seat in enumerate(semicircle(total)):
        mine = seated[i] == p["slug"]
        fill = _color(p["color"], PRIMARY) if mine else EMPTY
        sheet.circle(cx + (seat.x - 1) * radius, cy - (1 - seat.y) * radius, seat.r * radius, fill)
    tx = cx + radius + 36
    sheet.text(tx, 462, f"{seats} von {total} Sitzen", sheet.font(BRICOLAGE, 28, 700), TEXT)
    majority = total // 2 + 1
    sheet.text(tx, 502, f"Mehrheit ab {majority}", sheet.font(MONO, 13), SIGNAL_INK, tracking=1.1)
    stand = "Hochrechnung" if data["phase"] == "counting" else "ausgezählter Stand"
    sheet.text(tx, 528, f"Sitze: {stand}, nach NKWG gerechnet", sheet.font(INTER, 14, 400), MUTED)


def _area(sheet: _Sheet, data: ElectionNight, sel: Selection) -> None:
    ap = sel.area_party
    assert ap is not None
    y = 200.0
    x = float(MARGIN)
    x += _stat(sheet, x, y, "STIMMENANTEIL HIER", _pct(ap["share_pct"]), "") + 44
    seats = ap["seats"] or 0
    word = "SITZ VON HIER" if seats == 1 else "SITZE VON HIER"
    x += _stat(sheet, x, y, word, str(seats), "") + 44
    lv, cv = ap["list_votes"], ap["candidate_votes"]
    note = f"Liste {_number(lv)} · Personen {_number(cv)}" if lv is not None and cv is not None else ""
    _stat(sheet, x, y, "STIMMEN", _number(ap["votes"] or 0), note)

    sheet.text(MARGIN, 318, "Die Bewerber*innen nach Personenstimmen", sheet.font(INTER, 15, 600), TEXT)
    sheet.text(MARGIN, 341, "Blau: zieht in den Rat ein", sheet.font(INTER, 13, 400), MUTED)
    _bars(sheet, ap["candidates"], MARGIN, 366, COLUMN - MARGIN, None, row=22.0, limit=9)


def _candidate(sheet: _Sheet, data: ElectionNight, sel: Selection) -> None:
    c, ap = sel.candidate, sel.area_party
    assert c is not None and ap is not None
    y = 200.0
    x = float(MARGIN)
    votes = c["votes"]
    x += _stat(sheet, x, y, "PERSONENSTIMMEN", _number(votes) if votes is not None else "–", "") + 44
    ranked = sorted((k for k in ap["candidates"] if k["votes"] is not None),
                    key=lambda k: (-(k["votes"] or 0), k["position"]))
    if votes is not None and c in ranked:
        rank_text = f"{ranked.index(c) + 1} von {len(ranked)}"
    else:
        rank_text = "–"
    _stat(sheet, x, y, "PLATZ NACH STIMMEN", rank_text, f"Listenplatz {c['position']}")

    text, bg, ink = _status(c, data["phase"], data["person_votes_available"])
    _chip(sheet, MARGIN, 312, text, bg, ink)

    sheet.text(MARGIN, 356, "Die Liste nach Personenstimmen", sheet.font(INTER, 15, 600), TEXT)
    _bars(sheet, ap["candidates"], MARGIN, 380, COLUMN - MARGIN, c["position"], row=20.0, limit=9)


def _lotti_column(sheet: _Sheet, data: ElectionNight, sel: Selection) -> None:
    x1, x2 = COLUMN + 40.0, WIDTH - MARGIN + 10.0
    lotti_x = x2 - LOTTI_BOX + 10
    lotti_y = HEIGHT - 40 - LOTTI_BOX
    tail_x = lotti_x + LOTTI_BOX * 0.5
    bottom = _bubble(sheet, _thanks(data, sel), x1, 196, x2, tail_x)
    # Lotti rückt hoch, wenn die Blase kurz ist — nie über sie hinweg.
    top = max(bottom + 14, lotti_y - 60)
    _lotti(sheet, _pose(sel, data), lotti_x, min(top, lotti_y), LOTTI_BOX)


def _footer(sheet: _Sheet, data: ElectionNight) -> None:
    font = sheet.font(INTER, 13, 400)
    clock = _clock(data["source"])
    stand = f" · Stand {clock} Uhr" if clock and data["dataset"] != "probe" else ""
    text = ("ratslotse.de/wahlabend · Quelle: Open Data des Votemanagers der Stadt Oldenburg"
            f"{stand} · Sitze von uns nach NKWG gerechnet — maßgeblich ist die amtliche Präsentation")
    sheet.text(MARGIN, 590, text, font, MUTED)
