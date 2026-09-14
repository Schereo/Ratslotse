"""Sharepics je Liste, je Liste im Wahlbereich und je Person — das PNG hinter
``GET /api/wahlabend/karte.png?list=…[&area=…[&position=…]]``.

Das Bild in ``image.py`` zeigt den ganzen Rat. Hier geht es um EINE Liste
oder EINE Person: wie sie abgeschnitten hat, anschaulich genug, dass man es
in den Familienchat oder auf Instagram stellt — und mit Lotti, die den
Wählenden dankt. Drei Karten, dieselbe Bühne:

* **Liste stadtweit** — Anteil, Sitze, Stimmen mit dem Abstand zur Vorwahl, der
  Rang unter den Listen und ein Halbkreis, in dem nur die eigenen Sitze
  Farbe tragen.
* **Liste im Wahlbereich** — Anteil und Sitze dort, dazu die Personenstimmen
  der Bewerber*innen als Balken; wer einzieht, in Hafenblau.
* **Person** — Personenstimmen, Platz nach Stimmen, Status (direkt, über die
  Liste, über einen anderen Wahlbereich, nicht gewählt) und dieselben Balken
  mit der eigenen Zeile hervorgehoben.

Drei Formate: **beitrag** (1080×1350, 4:5 — der Instagram-Beitrag), **story**
(1080×1920, 9:16 — Story und Status; oben und unten bleibt Platz für die
Bedienelemente der Apps) und **quer** (1200×630 — Messenger und
Link-Vorschauen). Alle zeichnen dieselben Bausteine; nur die Maße stehen in
einem ``Layout`` — ein weiteres Format ist ein weiterer Satz Maße, kein
kopierter Zeichencode.

Was hier NICHT passiert: rechnen. Gezeichnet wird, was ``service.live()``
bzw. ``service.probe()`` liefern — die Sitze stammen aus derselben Zuteilung
wie die Seite, sonst zeigte die Karte etwas anderes als der Bildschirm.

Lotti kommt aus den Sprite-Sheets der iOS-App (``LottiSprite*.png``, 384 px
je Kachel, zeilenweise, Rest der letzten Zeile leer): Das Repo hat sie
ohnehin, und sie sind groß genug für 300–450 px im fertigen Bild. Fehlt eine
Datei, gibt es die Karte ohne Lotti — nie einen Fehler; dasselbe gilt für
die Schriften (``image._font``).

Parteifarben bleiben, was die Designsprache erlaubt: Punkte, kein Flächen-
anstrich. Die Balken tragen Hafenblau (drin) oder Grau (nicht drin).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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
    INTER,
    MONO,
    MUTED,
    SCALE,
    TEXT,
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
TRACK, BAR_OFF = "#E1E9F1", "#9AA9B8"

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
Format = Literal["quer", "beitrag", "story"]
FORMATS: tuple[str, ...] = ("beitrag", "story", "quer")


# ------------------------------------------------------------------ Maße

@dataclass(frozen=True)
class Layout:
    """Alle Maße eines Formats, in Endpunkten. Die Zeichenfunktionen kennen
    nur diese Werte — kein Format hat eigenen Zeichencode."""
    name: str
    width: int
    height: int
    margin: float
    #: Rechte Kante der Textspalte (quer: links von Lotti; hoch: Bildbreite).
    column: float
    kicker_y: float
    kicker_size: float
    kicker_lines: int
    title_y: float
    title_size: float
    sub_y: float
    sub_size: float
    sub_lines: int
    rule_y: float
    stats_y: float
    stat_value: float
    stat_label: float
    stat_note: float
    stat_gap: float
    rank_y: float
    rank_size: float
    chip_y: float
    chip_size: float
    #: Halbkreis der Listenkarte: Mittelpunkt, Radius, Beschriftung rechts davon.
    arc_cx: float
    arc_cy: float
    arc_r: float
    arc_text_x: float
    arc_text_y: float
    #: Beschriftung unter dem Halbkreis statt rechts daneben (Story).
    arc_text_below: bool
    #: Balken der Wahlbereichs- und Personenkarte.
    list_head_y: float
    list_head_size: float
    area_bars_y: float
    cand_bars_y: float
    bar_row: float
    bar_limit: int
    bar_name_w: float
    bar_count_w: float
    bar_size: float
    #: Lotti: linke obere Ecke und Kantenlänge.
    lotti_x: float
    lotti_y: float
    lotti_size: float
    #: Sprechblase: Kasten, Schwanz zeigt nach unten (quer) oder rechts (hoch).
    bubble_x1: float
    bubble_y1: float
    bubble_x2: float
    bubble_tail: str
    bubble_size: float
    bubble_lead: float
    footer_y: float
    footer_size: float
    footer_lead: float

    @property
    def text_w(self) -> float:
        return self.column - self.margin


QUER = Layout(
    name="quer", width=1200, height=630, margin=64, column=760,
    kicker_y=42, kicker_size=13, kicker_lines=1, title_y=66, title_size=54, sub_y=134, sub_size=18, sub_lines=1,
    rule_y=178, stats_y=200, stat_value=58, stat_label=12, stat_note=15, stat_gap=44,
    rank_y=328, rank_size=19, chip_y=312, chip_size=15,
    arc_cx=229, arc_cy=556, arc_r=165, arc_text_x=430, arc_text_y=462, arc_text_below=False,
    list_head_y=318, list_head_size=15, area_bars_y=366, cand_bars_y=376,
    bar_row=20, bar_limit=9, bar_name_w=200, bar_count_w=64, bar_size=13,
    lotti_x=836, lotti_y=270, lotti_size=320,
    bubble_x1=800, bubble_y1=196, bubble_x2=1146, bubble_tail="down", bubble_size=18, bubble_lead=26,
    footer_y=590, footer_size=13, footer_lead=18,
)

#: Beitrag und Story werden auf dem Handy auf rund 390 px Breite gestaucht —
#: was hier 30 px hat, ist dort 11 px. Deshalb ist alles gut doppelt so groß
#: wie im Querformat, und die Balken zeigen sechs statt neun Zeilen.
BEITRAG = Layout(
    name="beitrag", width=1080, height=1350, margin=72, column=1008,
    kicker_y=56, kicker_size=20, kicker_lines=2, title_y=128, title_size=92, sub_y=232, sub_size=30, sub_lines=2,
    rule_y=338, stats_y=360, stat_value=92, stat_label=24, stat_note=28, stat_gap=48,
    rank_y=572, rank_size=34, chip_y=566, chip_size=28,
    arc_cx=282, arc_cy=990, arc_r=210, arc_text_x=530, arc_text_y=850, arc_text_below=False,
    list_head_y=650, list_head_size=30, area_bars_y=732, cand_bars_y=700,
    bar_row=50, bar_limit=6, bar_name_w=370, bar_count_w=120, bar_size=30,
    lotti_x=728, lotti_y=1046, lotti_size=300,
    bubble_x1=72, bubble_y1=1082, bubble_x2=700, bubble_tail="right", bubble_size=32, bubble_lead=42,
    footer_y=1304, footer_size=19, footer_lead=23,
)

#: Story: Instagram legt oben (Name, Fortschritt) und unten (Antwortfeld)
#: je rund 250 px Bedienung über das Bild — dort steht nichts Wichtiges.
STORY = Layout(
    name="story", width=1080, height=1920, margin=72, column=1008,
    kicker_y=230, kicker_size=24, kicker_lines=2, title_y=316, title_size=104, sub_y=432, sub_size=34, sub_lines=2,
    rule_y=552, stats_y=578, stat_value=96, stat_label=26, stat_note=30, stat_gap=48,
    rank_y=826, rank_size=38, chip_y=820, chip_size=32,
    arc_cx=322, arc_cy=1200, arc_r=250, arc_text_x=72, arc_text_y=1240, arc_text_below=True,
    list_head_y=900, list_head_size=34, area_bars_y=1000, cand_bars_y=960,
    bar_row=58, bar_limit=6, bar_name_w=400, bar_count_w=130, bar_size=34,
    lotti_x=700, lotti_y=1400, lotti_size=320,
    bubble_x1=72, bubble_y1=1400, bubble_x2=680, bubble_tail="right", bubble_size=32, bubble_lead=44,
    footer_y=1712, footer_size=22, footer_lead=28,
)

LAYOUTS: dict[str, Layout] = {"quer": QUER, "beitrag": BEITRAG, "story": STORY}


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


def _share_delta(party: ElectionParty, vorwahl: str) -> str:
    now, before = party["share_pct"], party["share_previous_pct"]
    if now is None:
        return ""
    if before is None:
        return "neu angetreten"
    diff = round(now - before, 1)
    if abs(diff) < 0.05:
        return f"wie {vorwahl}"
    return f"{_signed(diff)} Punkte zu {vorwahl}"


def _seat_delta(party: ElectionParty, seats: int, vorwahl: str) -> str:
    before = party["seats_previous"]
    if before is None:
        return "neu angetreten"
    diff = seats - before
    if diff == 0:
        return f"wie {vorwahl}"
    word = "Sitz" if abs(diff) == 1 else "Sitze"
    return f"{_signed(diff, 0)} {word} zu {vorwahl}"


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
        vorwahl = data["election"].get("previous_label") or "der Vorwahl"
        parts.append(f"GENERALPROBE MIT ZAHLEN VON {vorwahl.upper()}")
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


def _lines(sheet: _Sheet, x: float, y: float, text: str, font: AnyFont, fill: str,
           width: float, lead: float, max_lines: int) -> float:
    """Umbrochener Text; was über die letzte erlaubte Zeile hinausgeht, wird
    dort gekürzt. Gibt die Unterkante zurück."""
    lines = _wrap(sheet, text, font, width)
    if len(lines) > max_lines:
        rest = " ".join(lines[max_lines - 1:])
        lines = lines[: max_lines - 1] + [_ellipsis(sheet, rest, font, width)]
    for i, line in enumerate(lines):
        sheet.text(x, y + i * lead, line, font, fill)
    return y + len(lines) * lead


def _rounded(sheet: _Sheet, x1: float, y1: float, x2: float, y2: float, radius: float,
             fill: str, outline: str | None = None) -> None:
    s = sheet._s
    sheet.draw.rounded_rectangle((s(x1), s(y1), s(x2), s(y2)), radius=s(radius), fill=fill,
                                 outline=outline, width=max(int(s(1)), 1) if outline else 0)


def _chip(sheet: _Sheet, x: float, y: float, text: str, bg: str, ink: str, size: float) -> float:
    font = sheet.font(INTER, size, 600)
    pad, height = size * 0.8, size * 2
    width = sheet.width_of(text, font) + 2 * pad
    _rounded(sheet, x, y, x + width, y + height, height / 2, bg)
    sheet.text(x + pad, y + (height - size) / 2 - size * 0.05, text, font, ink)
    return width


def _bubble(sheet: _Sheet, L: Layout, text: str, tail_at: float) -> float:
    """Lottis Sprechblase. ``tail_at``: x des Schwanzes (nach unten) bzw. y
    (nach rechts). Gibt die untere Kante zurück."""
    font = sheet.font(INTER, L.bubble_size, 500)
    pad, lead = L.bubble_size * 1.1, L.bubble_lead
    x1, y1, x2 = L.bubble_x1, L.bubble_y1, L.bubble_x2
    lines = _wrap(sheet, text, font, x2 - x1 - 2 * pad)
    y2 = y1 + 2 * pad + lead * len(lines) - lead * 0.15
    _rounded(sheet, x1, y1, x2, y2, 18, CARD, BORDER)
    s = sheet._s
    if L.bubble_tail == "down":
        tail = [(s(tail_at - 14), s(y2 - 1)), (s(tail_at + 14), s(y2 - 1)), (s(tail_at), s(y2 + 16))]
    else:
        ty = min(max(tail_at, y1 + 30), y2 - 30)
        tail = [(s(x2 - 1), s(ty - 14)), (s(x2 - 1), s(ty + 14)), (s(x2 + 18), s(ty))]
    sheet.draw.polygon(tail, fill=CARD, outline=BORDER)
    sheet.draw.line([tail[0], tail[1]], fill=CARD, width=max(int(s(2)), 1))
    for i, line in enumerate(lines):
        sheet.text(x1 + pad, y1 + pad + i * lead, line, font, TEXT)
    return y2


def _stat(sheet: _Sheet, L: Layout, x: float, label: str, value: str, note: str,
          note_ink: str = MUTED) -> float:
    """Kicker, große Zahl, Zeile darunter. Gibt die gebrauchte Breite zurück."""
    y = L.stats_y
    kicker = sheet.font(MONO, L.stat_label)
    big = sheet.font(BRICOLAGE, L.stat_value, 800)
    small = sheet.font(INTER, L.stat_note, 500)
    sheet.text(x, y, label, kicker, MUTED, tracking=1.2)
    sheet.text(x, y + L.stat_label * 1.8, value, big, TEXT)
    note_w = 0.0
    if note:
        note_y = y + L.stat_label * 1.8 + L.stat_value + L.stat_note * 0.6
        room = L.column - x
        if sheet.width_of(note, small) > room and " · " in note:
            # „Liste 3.466 · Personen 5.730" passt in den Hochformaten nicht
            # in die letzte Spalte — dann zwei Zeilen statt über den Rand.
            for i, part in enumerate(note.split(" · ")):
                sheet.text(x, note_y + i * L.stat_note * 1.35, part, small, note_ink)
                note_w = max(note_w, sheet.width_of(part, small))
        else:
            sheet.text(x, note_y, note, small, note_ink)
            note_w = sheet.width_of(note, small)
    return max(sheet.width_of(label, kicker, 1.2), sheet.width_of(value, big), note_w)


def _bars(sheet: _Sheet, L: Layout, candidates: list[ElectionCandidate], y: float,
          highlight: int | None) -> int:
    """Personenstimmen als Balken, Listenreihenfolge. Blau = zieht ein; die
    hervorgehobene Person fett und in Blau, auch wenn sie nicht drin ist.

    Mehr als ``bar_limit`` Zeilen passen nicht; dann fallen die hinteren weg —
    nur die hervorgehobene Person nie: Sie rückt als letzte Zeile nach.
    Gibt zurück, wie viele Bewerber*innen nicht zu sehen sind."""
    limit = L.bar_limit
    rows = list(candidates[:limit])
    if highlight is not None and not any(c["position"] == highlight for c in rows):
        mine = next((c for c in candidates if c["position"] == highlight), None)
        if mine is not None:
            rows = rows[: max(limit - 1, 0)] + [mine]
    hidden = len(candidates) - len(rows)
    max_votes = max((c["votes"] or 0 for c in candidates), default=0)
    x, width, row = L.margin, L.text_w, L.bar_row
    name_w, count_w, gap = L.bar_name_w, L.bar_count_w, 12.0
    bar_x, bar_w = x + name_w + gap, width - name_w - count_w - 2 * gap
    pos_font = sheet.font(MONO, L.bar_size - 2)
    pos_w = L.bar_size * 1.7
    thick = L.bar_size * 0.62
    for i, c in enumerate(rows):
        yy = y + i * row
        mine = highlight is not None and c["position"] == highlight
        drin = c["elected"] is not None
        strong = mine or drin
        name_font = sheet.font(INTER, L.bar_size, 700 if strong else 500)
        sheet.text(x, yy + 3, str(c["position"]), pos_font, MUTED)
        sheet.text(x + pos_w, yy + 2, _ellipsis(sheet, _person_name(c["name"]), name_font, name_w - pos_w),
                   name_font, TEXT if strong else MUTED)
        votes = c["votes"]
        y1, y2 = yy + 6, yy + 6 + thick
        _rounded(sheet, bar_x, y1, bar_x + bar_w, y2, thick / 2, TRACK)
        if votes is not None and max_votes > 0 and votes > 0:
            w = max(bar_w * votes / max_votes, thick)
            _rounded(sheet, bar_x, y1, bar_x + w, y2, thick / 2, PRIMARY if strong else BAR_OFF)
        count = _number(votes) if votes is not None else "–"
        count_font = sheet.font(INTER, L.bar_size, 700 if mine else 500)
        sheet.text(x + width - sheet.width_of(count, count_font), yy + 2, count, count_font,
                   TEXT if strong else MUTED)
    if hidden > 0:
        note = f"… und {hidden} weitere auf der Liste" if hidden > 1 else "… und eine weitere Person auf der Liste"
        sheet.text(x, y + len(rows) * row + 2, note, sheet.font(INTER, L.bar_size - 1, 400), MUTED)
    return hidden


# ------------------------------------------------------------------ Bild

def render(data: ElectionNight, sel: Selection, fmt: str = "beitrag", compare: bool = True) -> bytes:
    """Die Karte als PNG — beitrag (1080×1350), story (1080×1920) oder quer (1200×630).

    ``compare=False`` lässt den Abstand zur Vorwahl weg (Listenkarte): Wer die
    Karte teilt, muss den Verlust nicht mitteilen — die Zahlen stehen ohnehin
    auf der Seite."""
    L = LAYOUTS.get(fmt, BEITRAG)
    sheet = _Sheet(L.width, L.height, SCALE, BG)
    _header(sheet, L, data, sel)
    if sel.kind == "party":
        _party(sheet, L, data, sel, compare)
    elif sel.kind == "area":
        _area(sheet, L, data, sel)
    else:
        _candidate(sheet, L, data, sel)
    _lotti_and_bubble(sheet, L, data, sel)
    _footer(sheet, L, data)
    return sheet.png(L.width, L.height)


def _header(sheet: _Sheet, L: Layout, data: ElectionNight, sel: Selection) -> None:
    kicker_font = sheet.font(MONO, L.kicker_size)
    kicker = _kicker(data, sel)
    width = L.width - 2 * L.margin
    lines: list[str] = []
    for part in kicker.split(" · "):
        probe = f"{lines[-1]} · {part}" if lines else part
        if lines and len(lines) < L.kicker_lines and sheet.width_of(probe, kicker_font, 1.3) > width:
            lines.append(part)
        elif lines:
            lines[-1] = probe
        else:
            lines.append(part)
    for i, line in enumerate(lines[: L.kicker_lines]):
        sheet.text(L.margin, L.kicker_y + i * L.kicker_size * 1.5,
                   _ellipsis(sheet, line, kicker_font, width), kicker_font, MUTED, tracking=1.3)
    party = sel.party
    if sel.candidate is not None:
        c = sel.candidate
        title = _person_name(c["name"])
        font = _fit(sheet, title, BRICOLAGE, L.title_size, 800, L.text_w)
        sheet.text(L.margin, L.title_y, title, font, TEXT)
        bits = [c["occupation"], f"Jahrgang {c['born']}" if c["born"] else None]
        sub = " · ".join(b for b in bits if b)
        area = sel.area
        where = f"Liste {party['short']} · Wahlbereich {area['roman']} ({area['name']})" if area else ""
        sub = f"{sub} · {where}" if sub and where else (sub or where)
    else:
        dot = L.title_size * 0.2
        font = _fit(sheet, party["short"], BRICOLAGE, L.title_size, 800, L.text_w - 3 * dot)
        sheet.circle(L.margin + dot, L.title_y + L.title_size * 0.6, dot, _color(party["color"], MUTED))
        sheet.text(L.margin + 3 * dot + 2, L.title_y, party["short"], font, TEXT)
        if sel.area is not None:
            a = sel.area
            counted = f"{a['districts_counted']} von {a['districts_total']} Bezirken ausgezählt"
            sub = f"Wahlbereich {a['roman']} · {a['name']} · {counted}"
        else:
            sub = party["name"]
    sub_font = sheet.font(INTER, L.sub_size, 400)
    _lines(sheet, L.margin, L.sub_y, sub, sub_font, MUTED, L.text_w, L.sub_size * 1.4, L.sub_lines)
    sheet.line(L.margin, L.rule_y, L.column, L.rule_y, BORDER, 1)


def _party(sheet: _Sheet, L: Layout, data: ElectionNight, sel: Selection, compare: bool = True) -> None:
    p = sel.party
    seats = p["seats"] or 0
    total = int(data["election"]["seats"])
    x = L.margin
    # Wie die Vorwahl heißt, sagt die Antwort — bis 09/2026 stand „2021" hier
    # in vier Zeichenketten. Ohne Vorwahl bleibt der Vergleich weg.
    vorwahl = data["election"].get("previous_label") or ""
    share_note = _share_delta(p, vorwahl) if compare and vorwahl else ""
    seat_note = _seat_delta(p, seats, vorwahl) if compare and vorwahl else ""
    x += _stat(sheet, L, x, "STIMMENANTEIL", _pct(p["share_pct"]), share_note, SIGNAL_INK) + L.stat_gap
    word = "SITZ IM RAT" if seats == 1 else "SITZE IM RAT"
    x += _stat(sheet, L, x, word, str(seats), seat_note, SIGNAL_INK) + L.stat_gap
    valid = data["totals"]["valid_votes"]
    note = f"von {_number(valid)} gültigen" if valid else ""
    _stat(sheet, L, x, "STIMMEN", _number(p["votes"] or 0), note)

    rank = _rank(data, p)
    if rank:
        sheet.text(L.margin, L.rank_y, rank, sheet.font(INTER, L.rank_size, 600), TEXT)

    # Halbkreis: nur die eigenen Sitze tragen Farbe — links wie im Web, damit
    # die Position im Rat dieselbe ist wie auf der Seite.
    cx, cy, radius = L.arc_cx, L.arc_cy, L.arc_r
    parties = sorted(data["parties"], key=lambda q: q["index"])
    seated: list[str | None] = []
    for q in parties:
        seated += [q["slug"]] * (q["seats"] or 0)
    seated = (seated + [None] * total)[:total]
    for i, seat in enumerate(semicircle(total)):
        mine = seated[i] == p["slug"]
        fill = _color(p["color"], PRIMARY) if mine else EMPTY
        sheet.circle(cx + (seat.x - 1) * radius, cy - (1 - seat.y) * radius, seat.r * radius, fill)
    tx, ty = L.arc_text_x, L.arc_text_y
    big = L.rank_size * 1.5
    stand = "Hochrechnung" if data["phase"] == "counting" else "ausgezählter Stand"
    majority = total // 2 + 1
    if L.arc_text_below:
        # Story: die Zeile unter dem Halbkreis, alles hintereinander.
        sheet.text(tx, ty, f"{seats} von {total} Sitzen", sheet.font(BRICOLAGE, big, 700), TEXT)
        mono = sheet.font(MONO, L.stat_label)
        sheet.text(tx, ty + big * 1.35, f"Mehrheit ab {majority}", mono, SIGNAL_INK, tracking=1.1)
        rest = f"  ·  Sitze: {stand}, nach NKWG gerechnet"
        sheet.text(tx + sheet.width_of(f"Mehrheit ab {majority}", mono, 1.1), ty + big * 1.35 - 1, rest,
                   sheet.font(INTER, L.stat_note - 2, 400), MUTED)
        return
    sheet.text(tx, ty, f"{seats} von {total} Sitzen", sheet.font(BRICOLAGE, big, 700), TEXT)
    sheet.text(tx, ty + big * 1.45, f"Mehrheit ab {majority}", sheet.font(MONO, L.stat_label + 1), SIGNAL_INK,
               tracking=1.1)
    note_font = sheet.font(INTER, L.stat_note - 1, 400)
    _lines(sheet, tx, ty + big * 2.35, f"Sitze: {stand}, nach NKWG gerechnet", note_font, MUTED,
           L.column - tx, (L.stat_note - 1) * 1.4, 2)


def _area(sheet: _Sheet, L: Layout, data: ElectionNight, sel: Selection) -> None:
    ap = sel.area_party
    assert ap is not None
    x = L.margin
    x += _stat(sheet, L, x, "STIMMENANTEIL HIER", _pct(ap["share_pct"]), "") + L.stat_gap
    seats = ap["seats"] or 0
    word = "SITZ VON HIER" if seats == 1 else "SITZE VON HIER"
    x += _stat(sheet, L, x, word, str(seats), "") + L.stat_gap
    lv, cv = ap["list_votes"], ap["candidate_votes"]
    note = f"Liste {_number(lv)} · Personen {_number(cv)}" if lv is not None and cv is not None else ""
    _stat(sheet, L, x, "STIMMEN", _number(ap["votes"] or 0), note)

    sheet.text(L.margin, L.list_head_y, "Die Bewerber*innen nach Personenstimmen",
               sheet.font(INTER, L.list_head_size, 600), TEXT)
    sheet.text(L.margin, L.list_head_y + L.list_head_size * 1.55, "Blau: zieht in den Rat ein",
               sheet.font(INTER, L.list_head_size - 2, 400), MUTED)
    _bars(sheet, L, ap["candidates"], L.area_bars_y, None)


def _candidate(sheet: _Sheet, L: Layout, data: ElectionNight, sel: Selection) -> None:
    c, ap = sel.candidate, sel.area_party
    assert c is not None and ap is not None
    x = L.margin
    votes = c["votes"]
    x += _stat(sheet, L, x, "PERSONENSTIMMEN", _number(votes) if votes is not None else "–", "") + L.stat_gap
    ranked = sorted((k for k in ap["candidates"] if k["votes"] is not None),
                    key=lambda k: (-(k["votes"] or 0), k["position"]))
    if votes is not None and c in ranked:
        rank_text = f"{ranked.index(c) + 1} von {len(ranked)}"
    else:
        rank_text = "–"
    _stat(sheet, L, x, "PLATZ NACH STIMMEN", rank_text, f"Listenplatz {c['position']}")

    text, bg, ink = _status(c, data["phase"], data["person_votes_available"])
    _chip(sheet, L.margin, L.chip_y, text, bg, ink, L.chip_size)

    # Die Überschrift der Balken steht unter dem Chip: quer dicht darunter,
    # in den Hochformaten trägt der Kasten schon Luft.
    head_y = L.cand_bars_y - L.list_head_size * 1.6
    sheet.text(L.margin, head_y, "Die Liste nach Personenstimmen", sheet.font(INTER, L.list_head_size, 600), TEXT)
    _bars(sheet, L, ap["candidates"], L.cand_bars_y, c["position"])


def _lotti_and_bubble(sheet: _Sheet, L: Layout, data: ElectionNight, sel: Selection) -> None:
    text = _thanks(data, sel)
    if L.bubble_tail == "down":
        bottom = _bubble(sheet, L, text, L.lotti_x + L.lotti_size * 0.5)
        # Lotti rückt hoch, wenn die Blase kurz ist — nie über sie hinweg.
        top = max(bottom + 14, L.lotti_y - 60)
        _lotti(sheet, _pose(sel, data), L.lotti_x, min(top, L.lotti_y), L.lotti_size)
    else:
        _bubble(sheet, L, text, L.lotti_y + L.lotti_size * 0.3)
        _lotti(sheet, _pose(sel, data), L.lotti_x, L.lotti_y, L.lotti_size)


def _footer(sheet: _Sheet, L: Layout, data: ElectionNight) -> None:
    font = sheet.font(INTER, L.footer_size, 400)
    clock = _clock(data["source"])
    stand = f" · Stand {clock} Uhr" if clock and data["dataset"] != "probe" else ""
    first = f"ratslotse.de/wahlabend · Quelle: Open Data des Votemanagers Oldenburg{stand}"
    second = "Sitze von uns nach NKWG gerechnet — maßgeblich ist die amtliche Präsentation"
    width = L.width - 2 * L.margin
    if sheet.width_of(f"{first} · {second}", font) <= width:
        sheet.text(L.margin, L.footer_y, f"{first} · {second}", font, MUTED)
    else:
        sheet.text(L.margin, L.footer_y, _ellipsis(sheet, first, font, width), font, MUTED)
        sheet.text(L.margin, L.footer_y + L.footer_lead, _ellipsis(sheet, second, font, width), font, MUTED)
