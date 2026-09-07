"""Der Wahlabend als teilbares Bild — das PNG hinter ``GET /api/wahlabend/bild.png``.

Ein Stand, den man in WhatsApp oder Instagram schickt: 1200×630 (die Größe,
die Messenger und soziale Netze als Vorschau erwarten), Halbkreis der Sitze,
Legende, Quelle. Gerechnet wird hier nichts — das Bild zeichnet nur, was
``service.live()`` bzw. ``service.probe()`` schon fertig geliefert haben.

Zwei Dinge sind Absicht:

* **Die Geometrie ist dieselbe wie im Web.** ``semicircle()`` ist die
  Übersetzung von ``halbkreis()`` aus ``web/frontend/lib/wahlabend.ts``, Zeile
  für Zeile. Zwei Halbkreise, die sich um einen Platz unterscheiden, sähen aus
  wie zwei verschiedene Ergebnisse.
* **Das Bild darf nie an einer Schrift scheitern.** Fehlt eine Datei oder
  kennt die Fassung von FreeType die Variationsachsen nicht, fällt ``_font``
  auf ``ImageFont.load_default`` zurück; das Bild wird hässlicher, aber es
  kommt.

Gezeichnet wird in **Endpunkten** (1200×630) auf einer doppelt so großen
Leinwand; ganz zum Schluss verkleinert LANCZOS auf die Zielgröße — das ist das
Antialiasing, das Pillow beim Zeichnen selbst nicht mitbringt.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageDraw, ImageFont

from ..antworten import ElectionNight, ElectionParty, ElectionSource

#: Welches Sitzfeld gezeigt wird: der ausgezählte Stand oder die Hochrechnung.
SeatField = Literal["seats", "projected_seats"]

WIDTH, HEIGHT = 1200, 630
#: Faktor, um den größer gezeichnet wird, bevor LANCZOS verkleinert.
SCALE = 2
MARGIN = 64

# Hellmodus der Designsprache (web/frontend/DESIGNSPRACHE.md).
BG = "#F3F7FB"
TEXT = "#0E1E33"
MUTED = "#5B6B7B"
SIGNAL = "#F26A1B"
BORDER = "#DDE5EE"
#: Ein Sitz, den noch niemand hat.
EMPTY = "#D5DEE7"

FONT_DIR = Path(__file__).resolve().parents[4] / "ios" / "Resources" / "Fonts"
INTER = "Inter-Variable.ttf"
BRICOLAGE = "BricolageGrotesque-Variable.ttf"
MONO = "IBMPlexMono-Medium.ttf"

MONTHS = ("JANUAR", "FEBRUAR", "MÄRZ", "APRIL", "MAI", "JUNI",
          "JULI", "AUGUST", "SEPTEMBER", "OKTOBER", "NOVEMBER", "DEZEMBER")

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

AnyFont = ImageFont.FreeTypeFont | ImageFont.ImageFont


# ------------------------------------------------------------------ Geometrie

@dataclass(frozen=True)
class Seat:
    """Ein Platz im Halbkreis, in einem Kasten von 2 × 1 (Mittelpunkt 1|1)."""
    x: float
    y: float
    r: float
    row: int


def semicircle(n: int, rows: int = 3, inner: float = 0.48) -> list[Seat]:
    """Die Plätze eines Halbkreis-Parlaments, links nach rechts.

    Wortgleich mit ``halbkreis()`` in ``web/frontend/lib/wahlabend.ts``: Die
    Reihen bekommen Plätze im Verhältnis ihres Umfangs, der Rest wandert von
    außen nach innen, sortiert wird nach Winkel (π links, 0 rechts).
    """
    if n <= 0:
        return []
    radii = [1.0 if rows == 1 else inner + i * (1 - inner) / (rows - 1) for i in range(rows)]
    total = sum(radii)
    per_row = [int(n * r / total) for r in radii]
    rest = n - sum(per_row)
    i = rows - 1
    while rest > 0:
        per_row[i] += 1
        i = (i - 1 + rows) % rows
        rest -= 1
    row_gap = (1 - inner) / (rows - 1) if rows > 1 else 0.3
    points: list[tuple[float, Seat]] = []
    for i, r in enumerate(radii):
        m = per_row[i]
        arc = math.pi * r / max(m, 1)
        dot = min(row_gap, arc) * 0.34
        for j in range(m):
            angle = math.pi * (1 - (j + 0.5) / m)
            points.append((angle, Seat(1 + r * math.cos(angle), 1 - r * math.sin(angle), dot, i)))
    points.sort(key=lambda t: (-t[0], t[1].row))
    return [s for _, s in points]


# ------------------------------------------------------------------ Schriften

_font_cache: dict[tuple[str, int, int | None], AnyFont] = {}


def _axis_name(axis: Any) -> str:
    name = axis.get("name", "") if isinstance(axis, dict) else ""
    if isinstance(name, bytes):
        name = name.decode("utf-8", "replace")
    return str(name).lower()


def _font(file: str, size: int, weight: int | None = None) -> AnyFont:
    """Die Schrift in Zeichengröße — Variable Fonts auf das gewünschte Gewicht
    gestellt. Jeder Fehlschlag endet in der eingebauten Schrift, nie in einer
    Ausnahme: Ein Bild ohne Inter ist besser als kein Bild."""
    key = (file, size, weight)
    cached = _font_cache.get(key)
    if cached is not None:
        return cached
    font: AnyFont
    try:
        font = ImageFont.truetype(str(FONT_DIR / file), size)
        if weight is not None:
            try:
                axes: Any = font.get_variation_axes()
                values: list[float] = []
                for axis in axes:
                    low, high = float(axis["minimum"]), float(axis["maximum"])
                    name = _axis_name(axis)
                    if "weight" in name:
                        values.append(min(max(float(weight), low), high))
                    elif "optical" in name:
                        values.append(min(max(float(size), low), high))
                    else:
                        values.append(float(axis["default"]))
                font.set_variation_by_axes(values)
            except Exception:
                pass  # statische Schrift oder FreeType ohne Variationen
    except Exception:
        font = ImageFont.load_default(size)
    _font_cache[key] = font
    return font


def _color(value: str | None, fallback: str = MUTED) -> str:
    return value if value and _HEX.match(value) else fallback


# ------------------------------------------------------------------ Leinwand

class _Sheet:
    """Zeichnet in Endpunkten (1200×630) auf eine ``scale``-fach größere Leinwand."""

    def __init__(self, width: int, height: int, scale: int, background: str) -> None:
        self.scale = scale
        self.image = Image.new("RGB", (width * scale, height * scale), background)
        self.draw = ImageDraw.Draw(self.image)

    def _s(self, value: float) -> float:
        return value * self.scale

    def font(self, file: str, size: float, weight: int | None = None) -> AnyFont:
        return _font(file, int(round(size * self.scale)), weight)

    def width_of(self, text: str, font: AnyFont, tracking: float = 0.0) -> float:
        raw = self.draw.textlength(text, font=font) / self.scale
        return raw + tracking * max(len(text) - 1, 0)

    def text(self, x: float, y: float, text: str, font: AnyFont, fill: str,
             tracking: float = 0.0) -> None:
        """Text mit der Oberlänge auf ``y`` — bei ``tracking`` Zeichen für Zeichen."""
        if tracking <= 0:
            self._text_at(self._s(x), self._s(y), text, font, fill)
            return
        cursor = self._s(x)
        for char in text:
            self._text_at(cursor, self._s(y), char, font, fill)
            cursor += self.draw.textlength(char, font=font) + self._s(tracking)

    def _text_at(self, x: float, y: float, text: str, font: AnyFont, fill: str) -> None:
        try:
            self.draw.text((x, y), text, font=font, fill=fill, anchor="la")
        except (ValueError, AttributeError):
            self.draw.text((x, y), text, font=font, fill=fill)

    def circle(self, x: float, y: float, r: float, fill: str) -> None:
        box = (self._s(x - r), self._s(y - r), self._s(x + r), self._s(y + r))
        self.draw.ellipse(box, fill=fill)

    def line(self, x1: float, y1: float, x2: float, y2: float, fill: str, width: float = 1) -> None:
        self.draw.line((self._s(x1), self._s(y1), self._s(x2), self._s(y2)),
                       fill=fill, width=max(int(round(self._s(width))), 1))

    def dashed_v(self, x: float, y1: float, y2: float, fill: str, width: float,
                 dash: float, gap: float) -> None:
        """Senkrecht gestrichelt — Pillow kennt kein ``strokeDasharray``."""
        y = y1
        while y < y2:
            self.line(x, y, x, min(y + dash, y2), fill, width)
            y += dash + gap

    def png(self, width: int, height: int) -> bytes:
        out = self.image.resize((width, height), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        out.save(buffer, format="PNG")
        return buffer.getvalue()


# ------------------------------------------------------------------ Texte

def _number(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _date(iso: str | None) -> str:
    """„2026-09-13" → „13. SEPTEMBER 2026"; unlesbares bleibt, wie es ist."""
    if not iso:
        return ""
    try:
        d = datetime.strptime(iso[:10], "%Y-%m-%d")
    except ValueError:
        return iso.upper()
    return f"{d.day}. {MONTHS[d.month - 1]} {d.year}"


def _local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        from zoneinfo import ZoneInfo

        return dt.astimezone(ZoneInfo("Europe/Berlin"))
    except Exception:
        # Ohne tzdata: Der Wahlabend liegt in der Sommerzeit.
        return dt.astimezone(timezone(timedelta(hours=2)))


def _clock(source: ElectionSource) -> str | None:
    """Die Uhrzeit des Standes, deutsche Zeit — der Stand der CSV geht vor
    unserem Abruf."""
    raw = source.get("last_modified")
    if raw:
        try:
            return _local(parsedate_to_datetime(raw)).strftime("%H:%M")
        except (TypeError, ValueError):
            pass
    raw = source.get("fetched_at")
    if raw:
        try:
            return _local(datetime.fromisoformat(raw)).strftime("%H:%M")
        except ValueError:
            pass
    return None


def _seats_of(party: ElectionParty, field: SeatField) -> int:
    value = party["projected_seats"] if field == "projected_seats" else party["seats"]
    return value or 0


# ------------------------------------------------------------------ Bild

def render(data: ElectionNight, field: SeatField = "seats") -> bytes:
    """Der Stand als PNG (1200×630), fertig zum Teilen."""
    sheet = _Sheet(WIDTH, HEIGHT, SCALE, BG)
    total_seats = int(data["election"]["seats"])
    majority = total_seats // 2 + 1

    _header(sheet, data, field)
    if data["phase"] == "before":
        font = sheet.font(INTER, 25, 500)
        text = "Noch nichts ausgezählt — die Wahllokale schließen um 18 Uhr"
        sheet.text((WIDTH - sheet.width_of(text, font)) / 2, 350, text, font, TEXT)
    else:
        _arc(sheet, data, field, total_seats, majority)
        _legend(sheet, data, field)
    _footer(sheet)
    return sheet.png(WIDTH, HEIGHT)


def _header(sheet: _Sheet, data: ElectionNight, field: SeatField) -> None:
    stand = "HOCHRECHNUNG" if field == "projected_seats" else "STAND"
    kicker = f"RATSWAHL OLDENBURG · {_date(data['election'].get('date'))} · {stand}"
    sheet.text(MARGIN, 42, kicker, sheet.font(MONO, 13), MUTED, tracking=1.3)
    sheet.text(MARGIN, 66, "Wahlabend", sheet.font(BRICOLAGE, 54, 800), TEXT)

    progress = data["progress"]
    counted, all_districts = progress["districts_counted"], progress["districts_total"]
    line = f"{_number(counted)} von {_number(all_districts)} Wahlbezirken ausgezählt"
    if data["dataset"] == "probe":
        line += " · Generalprobe mit Zahlen von 2021"
    else:
        clock = _clock(data["source"])
        if clock:
            line += f" · Stand {clock} Uhr"
    sheet.text(MARGIN, 132, line, sheet.font(INTER, 19, 400), MUTED)
    sheet.line(MARGIN, 178, WIDTH - MARGIN, 178, BORDER, 1)


def _arc(sheet: _Sheet, data: ElectionNight, field: SeatField, total_seats: int, majority: int) -> None:
    cx, cy, radius = WIDTH / 2, 498.0, 252.0

    label = f"Mehrheit ab {majority}"
    font = sheet.font(MONO, 13)
    sheet.text(cx - sheet.width_of(label, font, 1.1) / 2, 200, label, font, SIGNAL, tracking=1.1)
    # Wie im Web: senkrecht durch die Mitte, von 0,42 bis 1,02 des Kastens.
    sheet.dashed_v(cx, cy - 0.58 * radius, cy + 0.02 * radius, SIGNAL, 3, 8, 5)

    parties = sorted(data["parties"], key=lambda p: p["index"])
    seated: list[ElectionParty | None] = []
    for party in parties:
        seated += [party] * _seats_of(party, field)
    seated = seated[:total_seats]
    seated += [None] * (total_seats - len(seated))

    for i, seat in enumerate(semicircle(total_seats)):
        party = seated[i]
        fill = _color(party["color"], MUTED) if party else EMPTY
        sheet.circle(cx + (seat.x - 1) * radius, cy - (1 - seat.y) * radius, seat.r * radius, fill)


def _legend(sheet: _Sheet, data: ElectionNight, field: SeatField) -> None:
    name_font = sheet.font(INTER, 16, 500)
    count_font = sheet.font(INTER, 16, 700)
    dot, gap_dot, gap_word, gap_item = 5.0, 8.0, 6.0, 26.0

    items: list[tuple[str, str, str, float]] = []
    for party in sorted(data["parties"], key=lambda p: p["index"]):
        seats = _seats_of(party, field)
        if seats <= 0:
            continue
        short, count = party["short"], str(seats)
        width = (2 * dot + gap_dot + sheet.width_of(short, name_font)
                 + gap_word + sheet.width_of(count, count_font))
        items.append((short, count, _color(party["color"]), width))
    if not items:
        return

    # Zeilen umbrechen, damit auch sechzehn Listen noch passen.
    rows: list[list[tuple[str, str, str, float]]] = [[]]
    available = WIDTH - 2 * MARGIN
    used = 0.0
    for item in items:
        extra = item[3] + (gap_item if rows[-1] else 0)
        if rows[-1] and used + extra > available:
            rows.append([])
            used = item[3]
        else:
            used += extra
        rows[-1].append(item)

    y = 518.0
    for row in rows:
        width = sum(i[3] for i in row) + gap_item * (len(row) - 1)
        x = (WIDTH - width) / 2
        for short, count, color, item_width in row:
            sheet.circle(x + dot, y + 9, dot, color)
            sheet.text(x + 2 * dot + gap_dot, y, short, name_font, MUTED)
            sheet.text(x + item_width - sheet.width_of(count, count_font), y, count, count_font, TEXT)
            x += item_width + gap_item
        y += 26


def _footer(sheet: _Sheet) -> None:
    font = sheet.font(INTER, 13, 400)
    text = ("ratslotse.de/wahlabend · Quelle: Open Data des Votemanagers der Stadt Oldenburg"
            " · Sitze von uns nach NKWG gerechnet, Fehler möglich — maßgeblich ist die amtliche Präsentation")
    sheet.text(MARGIN, 590, text, font, MUTED)
