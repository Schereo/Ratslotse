"""Das Bild zum Teilen der Stichwahl — das PNG hinter
``GET /api/wahlabend/stichwahl/bild.png`` (Tims Wunsch 23.09.2026).

Am Stichwahl-Abend teilen Leute den Stand: im Familienchat, in der Story,
als Link-Vorschau. Dieses Bild zeigt genau, was die Seite zeigt — die beiden
Namen, ihre Anteile und Stimmen, wie viele Bezirke gezählt sind, die
Hochrechnung und Lotti. Drei Formate wie bei den Karten der Ratswahl
(``share.py``): **beitrag** (1080×1350), **story** (1080×1920) und **quer**
(1200×630, auch als Link-Vorschau der Seite).

Die Balken tragen die Farbe der Person, wie auf der Seite und der
Stichwahl-Karte — die Ausnahme von „keine Parteifarben-Flächen", die die
Designsprache für zwei Namen auf einem Stimmzettel macht (§ 2).

Gerechnet wird hier nichts: gezeichnet wird ``MayorNight``, derselbe Stand
wie auf der Seite. Lotti bleibt neutral — sie jubelt über ein Ergebnis,
nicht über eine Person, und klatscht, solange gezählt wird.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..antworten import MayorCandidate, MayorNight
from .image import (
    BG,
    BORDER,
    BRICOLAGE,
    INTER,
    MONO,
    MUTED,
    SCALE,
    TEXT,
    _color,
    _date,
    _local,
    _number,
    _Sheet,
)
from .share import CARD, TRACK, _ellipsis, _fit, _lines, _lotti, _rounded, _wrap

FORMATS: tuple[str, ...] = ("beitrag", "story", "quer")


@dataclass(frozen=True)
class Layout:
    """Die Maße eines Formats. Stehen die beiden untereinander (hoch), ist
    ``block_dx`` 0 und der zweite Block beginnt unter dem ersten (aus seiner
    Höhe gerechnet, ``_hoehe``); nebeneinander (quer) stehen sie auf einer
    Linie. Die Hochrechnung folgt darunter."""
    name: str
    width: int
    height: int
    margin: float
    kicker_y: float
    kicker_size: float
    title_y: float
    title_size: float
    sub_y: float
    sub_size: float
    rule_y: float
    blocks_y: float
    block_w: float
    block_dx: float
    #: Abstand zwischen den Blöcken und bis zur Hochrechnung.
    gap: float
    name_size: float
    party_size: float
    pct_size: float
    bar_h: float
    votes_size: float
    proj_size: float
    lotti_x: float
    lotti_y: float
    lotti_size: float
    bubble_x1: float
    bubble_y1: float
    bubble_x2: float
    #: Der Schwanz der Blase zeigt nach unten (quer) oder nach rechts (hoch).
    bubble_down: bool
    bubble_size: float
    footer_y: float
    footer_size: float


#: Hochformate werden auf dem Handy auf ~390 px gestaucht — Beschriftungen
#: deshalb ≥ 26 px, Titel ≥ 80 px (Lehre aus den Ratswahl-Karten, 13.09.).
BEITRAG = Layout(
    name="beitrag", width=1080, height=1350, margin=72,
    kicker_y=60, kicker_size=22, title_y=112, title_size=84, sub_y=214, sub_size=30, rule_y=276,
    blocks_y=304, block_w=936, block_dx=0, gap=30,
    name_size=40, party_size=22, pct_size=92, bar_h=22, votes_size=28,
    proj_size=28,
    lotti_x=736, lotti_y=968, lotti_size=290,
    bubble_x1=72, bubble_y1=1000, bubble_x2=708, bubble_down=False, bubble_size=32,
    footer_y=1290, footer_size=20,
)

#: Story: oben und unten legen die Apps je ~250 px Bedienung über das Bild.
STORY = Layout(
    name="story", width=1080, height=1920, margin=72,
    kicker_y=250, kicker_size=24, title_y=306, title_size=96, sub_y=424, sub_size=34, rule_y=496,
    blocks_y=536, block_w=936, block_dx=0, gap=44,
    name_size=50, party_size=26, pct_size=118, bar_h=26, votes_size=32,
    proj_size=32,
    lotti_x=716, lotti_y=1380, lotti_size=300,
    bubble_x1=72, bubble_y1=1410, bubble_x2=690, bubble_down=False, bubble_size=34,
    footer_y=1640, footer_size=22,
)

QUER = Layout(
    name="quer", width=1200, height=630, margin=56,
    kicker_y=38, kicker_size=14, title_y=62, title_size=50, sub_y=124, sub_size=18, rule_y=162,
    blocks_y=184, block_w=320, block_dx=352, gap=48,
    name_size=26, party_size=14, pct_size=66, bar_h=14, votes_size=17,
    proj_size=18,
    lotti_x=860, lotti_y=250, lotti_size=300,
    bubble_x1=800, bubble_y1=56, bubble_x2=1150, bubble_down=True, bubble_size=18,
    footer_y=586, footer_size=13,
)

LAYOUTS: dict[str, Layout] = {"beitrag": BEITRAG, "story": STORY, "quer": QUER}


# ------------------------------------------------------------------ Texte

def _pct(value: float | None) -> str:
    return "–" if value is None else f"{value:.1f} %".replace(".", ",")


def _nachname(name: str) -> str:
    return name.split()[-1] if name.split() else name


def _nach_stimmen(night: MayorNight) -> list[MayorCandidate]:
    """Die meisten Stimmen zuerst; vor der Auszählung die Reihenfolge des
    ersten Wahlgangs (wie auf der Seite, ``nachStimmen``)."""
    kandidaten = list(night["candidates"])
    if any(c["votes"] for c in kandidaten):
        return sorted(kandidaten, key=lambda c: -(c["votes"] or 0))
    return sorted(kandidaten, key=lambda c: -(c["first_round_pct"] or 0))


def _clock(night: MayorNight) -> str | None:
    raw = night["fetched_at"]
    if not raw:
        return None
    try:
        return _local(datetime.fromisoformat(raw)).strftime("%H:%M")
    except ValueError:
        return None


def _entschieden(night: MayorNight) -> MayorCandidate | None:
    """Wer gewählt ist — rechnerisch entschieden oder alles gezählt."""
    p = night.get("projection")
    fertig = night["phase"] == "complete"
    if not (fertig or (p is not None and p["decided"])):
        return None
    reihe = _nach_stimmen(night)
    if len(reihe) > 1 and reihe[0]["votes"] == reihe[1]["votes"]:
        return None
    return reihe[0] if reihe and reihe[0]["votes"] else None


def _kicker(night: MayorNight) -> str:
    teile = ["OLDENBURG", "OB-STICHWAHL", _date(night["election"]["date"])]
    if night["dataset"] == "probe":
        teile.append("GENERALPROBE")
    elif night["phase"] == "complete":
        teile.append("ENDSTAND")
    elif (uhr := _clock(night)) is not None:
        teile.append(f"STAND {uhr} UHR")
    return " · ".join(teile)


def _titel(night: MayorNight) -> str:
    gewaehlt = _entschieden(night)
    if gewaehlt is not None:
        return f"{gewaehlt['name']} ist gewählt"
    if night["phase"] == "before":
        return "Stichwahl — ab 18 Uhr live"
    reihe = _nach_stimmen(night)
    if len(reihe) > 1 and reihe[0]["votes"] == reihe[1]["votes"]:
        return "Stichwahl: gleichauf"
    return f"Stichwahl: {_nachname(reihe[0]['name'])} vorn"


def _unterzeile(night: MayorNight) -> str:
    if night["phase"] == "complete":
        return f"Alle {night['reports_expected']} Wahlbezirke ausgezählt"
    if night["phase"] == "before":
        return "Noch kein Wahlbezirk ausgezählt"
    return f"{night['reports_received']} von {night['reports_expected']} Wahlbezirken ausgezählt"


def _blasentext(night: MayorNight) -> str:
    gewaehlt = _entschieden(night)
    if gewaehlt is not None:
        return f"Glückwunsch, {gewaehlt['name']} — und danke an alle, die gewählt haben!"
    if night["phase"] == "before":
        return f"Am {_date(night['election']['date']).title()} ab 18 Uhr zählt Oldenburg aus. Live auf ratslotse.de!"
    offen = night["reports_expected"] - night["reports_received"]
    return f"Noch {offen} {'Bezirk' if offen == 1 else 'Bezirke'} offen — es bleibt spannend. Live auf ratslotse.de!"


def _hochrechnung(night: MayorNight) -> str | None:
    p = night.get("projection")
    if p is None or night["phase"] == "complete" or p["decided"]:
        return None
    reihe = sorted(night["candidates"], key=lambda c: -(p["shares"].get(c["slug"]) or 0))
    zahlen = " · ".join(f"{_nachname(c['name'])} {_pct(p['shares'].get(c['slug']))}" for c in reihe)
    gezaehlt = p["counted_ballot"] + p["counted_postal"]
    return f"Hochrechnung: {zahlen} (Modell nach {gezaehlt} Bezirken)"


# ------------------------------------------------------------------ Zeichnen

def render(night: MayorNight, fmt: str = "beitrag") -> bytes:
    """Der Stand als PNG — beitrag (1080×1350), story (1080×1920) oder quer (1200×630)."""
    L = LAYOUTS.get(fmt, BEITRAG)
    sheet = _Sheet(L.width, L.height, SCALE, BG)
    breite = L.width - 2 * L.margin
    text_rechts = L.bubble_x1 - 40 if L.bubble_down else L.width - L.margin

    kicker = sheet.font(MONO, L.kicker_size)
    sheet.text(L.margin, L.kicker_y, _ellipsis(sheet, _kicker(night), kicker, text_rechts - L.margin),
               kicker, MUTED, tracking=1.3)
    titel = _titel(night)
    sheet.text(L.margin, L.title_y, titel, _fit(sheet, titel, BRICOLAGE, L.title_size, 800, text_rechts - L.margin), TEXT)
    sheet.text(L.margin, L.sub_y, _unterzeile(night), sheet.font(INTER, L.sub_size, 500), MUTED)
    sheet.line(L.margin, L.rule_y, text_rechts, L.rule_y, BORDER, 1)

    hoehe = _hoehe(L)
    schritt = 0.0 if L.block_dx else hoehe + L.gap
    for i, c in enumerate(_nach_stimmen(night)[:2]):
        _block(sheet, L, c, L.margin + i * L.block_dx, L.blocks_y + i * schritt)

    zeile = _hochrechnung(night)
    if zeile:
        font = sheet.font(INTER, L.proj_size, 500)
        y = L.blocks_y + (hoehe if L.block_dx else 2 * hoehe + L.gap) + L.gap
        _lines(sheet, L.margin, y, zeile, font, MUTED, text_rechts - L.margin, L.proj_size * 1.35, 2)

    _blase(sheet, L, _blasentext(night))
    _lotti(sheet, "jubelt" if _entschieden(night) is not None else ("winkt" if night["phase"] == "before" else "klatscht"),
           L.lotti_x, L.lotti_y, L.lotti_size)

    fuss = sheet.font(INTER, L.footer_size, 400)
    uhr = _clock(night)
    stand = f" · Stand {uhr} Uhr" if uhr and night["dataset"] != "probe" else ""
    text = f"ratslotse.de/wahlabend/stichwahl · Quelle: Votemanager der Stadt Oldenburg{stand} · kein amtliches Ergebnis"
    _lines(sheet, L.margin, L.footer_y, text, fuss, MUTED, breite, L.footer_size * 1.3, 2)
    return sheet.png(L.width, L.height)


def _hoehe(L: Layout) -> float:
    """Wie hoch ein Block ist — dieselben Abstände wie in ``_block``."""
    return L.name_size * 1.3 + L.party_size * 1.7 + L.pct_size * 1.12 + L.bar_h + L.votes_size * 1.8


def _block(sheet: _Sheet, L: Layout, c: MayorCandidate, x: float, y: float) -> None:
    """Eine Person: Punkt und Name, wer sie vorgeschlagen hat, der Anteil
    groß, der Balken in ihrer Farbe, die Stimmen."""
    farbe = _color(c["color"], MUTED)
    punkt = L.name_size * 0.2
    sheet.circle(x + punkt, y + L.name_size * 0.62, punkt, farbe)
    name = sheet.font(BRICOLAGE, L.name_size, 800)
    sheet.text(x + 3 * punkt, y, _ellipsis(sheet, c["name"], name, L.block_w - 3 * punkt), name, TEXT)
    partei = f"vorgeschlagen von {c['party']}" if c["party"] else "Einzelwahlvorschlag"
    sheet.text(x, y + L.name_size * 1.3, partei.upper(), sheet.font(MONO, L.party_size), MUTED, tracking=1.0)
    py = y + L.name_size * 1.3 + L.party_size * 1.7
    sheet.text(x, py, _pct(c["share_pct"]), sheet.font(BRICOLAGE, L.pct_size, 800), TEXT)
    by = py + L.pct_size * 1.12
    _rounded(sheet, x, by, x + L.block_w, by + L.bar_h, L.bar_h / 2, TRACK)
    anteil = max(0.0, min(100.0, c["share_pct"] or 0.0)) / 100
    if anteil > 0:
        _rounded(sheet, x, by, x + max(L.bar_h, L.block_w * anteil), by + L.bar_h, L.bar_h / 2, farbe)
    stimmen = f"{_number(c['votes'])} Stimmen" if c["votes"] else "noch keine Stimmen"
    sheet.text(x, by + L.bar_h + L.votes_size * 0.6, stimmen, sheet.font(INTER, L.votes_size, 600), TEXT)


def _blase(sheet: _Sheet, L: Layout, text: str) -> None:
    """Lottis Sprechblase — der Schwanz zeigt auf Lotti."""
    font = sheet.font(INTER, L.bubble_size, 500)
    pad, lead = L.bubble_size * 1.1, L.bubble_size * 1.35
    x1, y1, x2 = L.bubble_x1, L.bubble_y1, L.bubble_x2
    lines = _wrap(sheet, text, font, x2 - x1 - 2 * pad)
    y2 = y1 + 2 * pad + lead * len(lines) - lead * 0.15
    _rounded(sheet, x1, y1, x2, y2, 18, CARD, BORDER)
    s = sheet._s
    if L.bubble_down:
        tx = L.lotti_x + L.lotti_size * 0.5
        tail = [(s(tx - 14), s(y2 - 1)), (s(tx + 14), s(y2 - 1)), (s(tx), s(y2 + 16))]
    else:
        ty = min(max(L.lotti_y + L.lotti_size * 0.3, y1 + 30), y2 - 30)
        tail = [(s(x2 - 1), s(ty - 14)), (s(x2 - 1), s(ty + 14)), (s(x2 + 18), s(ty))]
    sheet.draw.polygon(tail, fill=CARD, outline=BORDER)
    sheet.draw.line([tail[0], tail[1]], fill=CARD, width=max(int(s(2)), 1))
    for i, line in enumerate(lines):
        sheet.text(x1 + pad, y1 + pad + i * lead, line, font, TEXT)
