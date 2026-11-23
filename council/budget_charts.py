"""Die Grafiken eines Vorberichts zum Haushalt als Daten — ohne Modell.

Tim, 23.11.2026, zum Haushaltsentwurf 2027: „die grafiken aus dem
haushaltsentwurf analysieren und spannende effekte erläutern und anzeigen“.
Der Vorbericht 2027 (79 Seiten) trägt 56 nummerierte „Grafik n-m“. Gezählt:

* 32 sind **Tabellen**, deren Zahlen als Text im PDF stehen — PyMuPDF findet
  sie (``find_tables``), jede Zelle ist exakt.
* Die meisten **Diagramme** beschriften ihre Säulen mit dem Wert. Die Werte
  stehen in der Textebene aber NICHT in Jahresfolge: In Grafik 2.1.1-1 steht
  24,3 (2023) vor 14,6 (2022). Zugeordnet wird deshalb über die x-Position:
  Jeder Wert gehört zur Kategorie, über deren Beschriftung er steht.
  (``council/vorbericht_zahlen.py`` liest bis heute in Textfolge.)
* Rund neun sind **Bilder** ohne Textebene — die bleiben als Lücke stehen.

Was hier herauskommt, ist das einzige Zahlenmaterial, gegen das die Befunde
(``council/budget_findings.py``) geprüft werden: Eine Zahl, die nicht in
einer Grafik oder im Text der Seite steht, erscheint nicht.

Die Logik arbeitet auf Wörtern mit Koordinaten und Tabellenzellen; nur
``from_pdf`` braucht PyMuPDF (optional, s. ``council/anlagentext.py``).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

#: „(Grafik 2.1.1-1)", „Grafik 7-1: Entwicklung …", „Grafik -2)" (Kapitel ohne Nummer).
_CAPTION_RE = re.compile(r"\(?\bGrafik\s*((?:\d+(?:\.\d+)*)?\s*-\s*\d+)\)?")
_YEAR_RE = re.compile(r"^(?:19|20)\d\d$")
#: Eine Zahl, wie der Vorbericht sie schreibt: 1.234.567,89 · -24,8 · ‐21.356.491 · 6,2% · 0,00 €
_NUMBER_RE = re.compile(r"^[-‐−–]?\d{1,3}(?:\.\d{3})*(?:,\d+)?%?$|^[-‐−–]?\d+(?:,\d+)?%?$")
_MINUS = "-‐−–"


def parse_number(text: str | None) -> float | None:
    """„-24,8" → -24.8, „‐21.356.491" → -21356491.0, „6,2%" → 6.2; sonst None."""
    t = (text or "").strip().replace(" ", "").replace(" ", "").rstrip("€").strip()
    if not t or not _NUMBER_RE.match(t):
        return None
    negative = t[0] in _MINUS
    t = t.lstrip(_MINUS).rstrip("%").replace(".", "").replace(",", ".")
    try:
        value = float(t)
    except ValueError:
        return None
    return -value if negative else value


@dataclass
class Chart:
    number: str
    page: int
    caption: str
    kind: str                       # "table" | "diagram" | "image"
    title: str = ""
    header: list[str] = field(default_factory=list)
    #: je Zeile bzw. Reihe: Bezeichnung und Werte in der Reihenfolge von ``header``.
    rows: list[dict] = field(default_factory=list)
    #: Text, der zur Grafik gehört, aber nicht in die Zeilen passt (Legende, Achse).
    extras: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)

    def numbers(self) -> list[float]:
        return [v for r in self.rows for v in r["values"] if v is not None]


def is_table(cells: list[list[str | None]]) -> bool:
    """Ist das eine Tabelle — oder das Gitter eines Diagramms, das
    ``find_tables`` für eine hält? Eine Tabelle ist dicht gefüllt; im Gitter
    stehen ein paar Wertbeschriftungen verstreut in sonst leeren Zellen
    (Grafik 2.1.1-1: 21 Spalten, je Zeile ein Wert)."""
    cells = [r for r in cells if r]
    total = sum(len(r) for r in cells)
    filled = sum(1 for r in cells for c in r if (c or "").strip())
    return total > 0 and filled / total >= 0.45 and len(cells) >= 2


def chart_number(text: str) -> str | None:
    m = _CAPTION_RE.search(text or "")
    return re.sub(r"\s+", "", m.group(1)) if m else None


# ---- Tabellen ------------------------------------------------------------------

def from_table(cells: list[list[str | None]]) -> tuple[list[str], list[dict]]:
    """Kopf und Zeilen einer Tabelle: Kopf sind die Zeilen oben ohne Zahl (Jahre
    zählen als Kopf, „Ist 2025"), Bezeichnung die erste Spalte mit Text."""
    rows = [[(c or "").replace("\n", " ").strip() for c in r] for r in cells if any((c or "").strip() for c in r)]
    if not rows:
        return [], []
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]

    def has_values(r: list[str]) -> bool:
        return sum(1 for c in r[1:] if parse_number(c) is not None and not _YEAR_RE.match(c)) >= 1

    header_rows = []
    while rows and not has_values(rows[0]):
        header_rows.append(rows.pop(0))
    header = [" ".join(h[i] for h in header_rows if h[i]).strip() for i in range(width)]
    out = []
    for r in rows:
        values = [parse_number(c) for c in r[1:]]
        if any(v is not None for v in values):
            out.append({"label": r[0], "values": values})
    return header[1:], out


# ---- Diagramme -----------------------------------------------------------------

_CATEGORY_SUFFIX = frozenset({"Plan", "Prognose", "Ist", "HR", "Soll", "Ansatz"})


def is_regular(rows: list[dict]) -> bool:
    """Trägt jede Kategorie gleich viele Werte? Sonst hat sich ein fremder Wert
    eingeschlichen (eine Zahl aus der Legende, ein Achsenwert) oder einer fehlt —
    und die Zuordnung ist nicht mehr sicher."""
    if not rows:
        return False
    width = len(rows[0]["values"])
    counts = [sum(1 for r in rows if r["values"][i] is not None) for i in range(width)]
    if len(set(counts)) != 1:
        return False
    # Eine Reihe trägt Werte EINER Größenordnung. 6,2 neben 221.124.932 heißt:
    # Hier wurde eine Tabelle für ein Diagramm gehalten (Grafik 2.4.1.3-1).
    for r in rows:
        magnitudes = [abs(v) for v in r["values"] if v]
        if magnitudes and max(magnitudes) / min(magnitudes) > 500:
            return False
    return True


#: Ein Wort mit Lage: (x0, y0, x1, y1, Text).
Word = tuple[float, float, float, float, str]


def _axis_ticks(numbers: list[Word]) -> set[int]:
    """Die Achsenteilung: Zahlen in einer senkrechten Spalte (gleiche x-Mitte),
    mindestens drei, in gleichen Abständen — „0 / 20 / 40 / 60"."""
    columns: dict[int, list[Word]] = {}
    for w in numbers:
        columns.setdefault(round((w[0] + w[2]) / 2 / 6), []).append(w)
    out: set[int] = set()
    for ws in columns.values():
        if len(ws) < 3:
            continue
        vs = sorted(parse_number(w[4]) or 0.0 for w in ws)
        steps = {round(b - a, 3) for a, b in zip(vs, vs[1:])}
        if len(steps) == 1:
            out |= {id(w) for w in ws}
    return out


def from_diagram(words: list[Word]) -> tuple[list[str], list[dict], list[str]]:
    """Kategorien, Reihen und Beiwerk eines beschrifteten Säulendiagramms.

    Kategorien sind die Jahre auf einer gemeinsamen Zeile (±6 pt — „2030“ sitzt
    gern etwas tiefer), dazu „Plan“/„Prognose“ direkt darunter. Die
    Achsenteilung (gleichmäßige Zahlenspalte) zählt nicht. Jeder übrige Wert
    gehört zur Kategorie, über bzw. unter deren Mitte er steht — negative Werte
    stehen unter der Achse. Mehrere Werte einer Kategorie werden nach x
    getrennt (Gruppen) oder, wo sie übereinander stehen, von unten nach oben
    (Stapel)."""
    years = [w for w in words if _YEAR_RE.match(w[4])]
    if len(years) < 2:
        return [], [], [w[4] for w in words]
    lines: dict[int, int] = {}
    for w in years:
        lines[round(w[1] / 3)] = lines.get(round(w[1] / 3), 0) + 1
    y_mode = max(lines, key=lambda k: (lines[k], k)) * 3
    axis_years = sorted((w for w in years if abs(w[1] - y_mode) <= 6), key=lambda w: w[0])
    if len(axis_years) < 2:
        return [], [], [w[4] for w in words]
    centers = [(w[0] + w[2]) / 2 for w in axis_years]
    band = min((b - a for a, b in zip(centers, centers[1:])), default=40.0)
    header = []
    for w, c in zip(axis_years, centers):
        suffix = [v[4] for v in words if w[1] + 2 < v[1] < w[1] + 16 and abs((v[0] + v[2]) / 2 - c) < band / 2
                  and v[4] in _CATEGORY_SUFFIX]
        header.append(" ".join([w[4], *suffix]))
    numbers = [w for w in words if parse_number(w[4]) is not None and not _YEAR_RE.match(w[4])]
    axis = _axis_ticks(numbers)
    left, right = centers[0] - band * 0.6, centers[-1] + band * 0.6
    labels = [w for w in numbers if id(w) not in axis and left <= (w[0] + w[2]) / 2 <= right]
    per_category: list[list[Word]] = [[] for _ in centers]
    for w in labels:
        mx = (w[0] + w[2]) / 2
        i = min(range(len(centers)), key=lambda k: abs(centers[k] - mx))
        per_category[i].append(w)
    n = max((len(x) for x in per_category), default=0)
    series: list[list[float | None]] = [[None] * len(centers) for _ in range(n)]
    for i, ws in enumerate(per_category):
        if not ws:
            continue
        spread = max(w[0] for w in ws) - min(w[0] for w in ws)
        ordered = sorted(ws, key=(lambda w: w[0]) if spread > band * 0.25 else (lambda w: -w[1]))
        for k, w in enumerate(ordered):
            series[k][i] = parse_number(w[4])
    used = {id(w) for ws in per_category for w in ws} | {id(w) for w in axis_years} | axis
    extras = [w[4] for w in words if id(w) not in used and parse_number(w[4]) is None and not _YEAR_RE.match(w[4])]
    return header, [{"label": f"Reihe {k + 1}", "values": s} for k, s in enumerate(series)], extras


# ---- PDF -----------------------------------------------------------------------

def from_pdf(data: bytes) -> list[Chart]:
    """Alle „Grafik n-m" eines Vorberichts. Braucht PyMuPDF."""
    import pymupdf  # noqa: PLC0415 — optional, s. council/anlagentext.py

    out: list[Chart] = []
    seen: set[str] = set()
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            blocks = page.get_text("blocks")
            captions = []
            for b in blocks:
                for m in _CAPTION_RE.finditer(b[4]):
                    # Nur die Unterschrift selbst, nicht der Verweis im Fließtext
                    # („wie Grafik 6-3 zeigt"): Sie steht in Klammern oder am Blockende.
                    if m.group(0).startswith("(") or b[4].strip().endswith(m.group(0).strip()) or ":" in b[4][m.end():m.end() + 2]:
                        captions.append((re.sub(r"\s+", "", m.group(1)), b))
            if not captions:
                continue
            tables = list(page.find_tables().tables)
            words = [tuple(w[:5]) for w in page.get_text("words")]
            images = page.get_images()
            previous_bottom = 0.0
            for number, b in sorted(captions, key=lambda x: x[1][1]):
                if number in seen:
                    continue
                seen.add(number)
                cap_y = b[1]
                chart = Chart(number=number, page=page.number + 1, caption=" ".join(b[4].split())[:300], kind="image")
                # Die Unterschrift steht unter der Tabelle oder in ihrer letzten Zeile.
                candidates = [t for t in tables if previous_bottom - 2 <= t.bbox[1] < cap_y and t.bbox[3] <= cap_y + 15
                              and is_table(t.extract())]
                if candidates:
                    t = max(candidates, key=lambda t: t.bbox[3])
                    chart.kind = "table"
                    chart.header, chart.rows = from_table(t.extract())
                    top = t.bbox[1]
                else:
                    # Der Bereich ist die Zeichnung selbst, nicht „430 pt darüber":
                    # Sonst griffe eine Zahl aus dem Absatz über dem Diagramm mit.
                    strokes = [d["rect"] for d in page.get_drawings()
                               if d["rect"].y1 <= cap_y + 6 and d["rect"].y0 >= max(previous_bottom, cap_y - 430)
                               and d["rect"].width < page.rect.width * 0.95]
                    top = (min(r.y0 for r in strokes) - 18) if strokes else max(previous_bottom, cap_y - 430)
                    inside = [w for w in words if top <= w[1] < cap_y]
                    header, series, extras = from_diagram(inside)  # type: ignore[arg-type]
                    # Ohne Wertbeschriftung (nur Achse) bleibt ein Diagramm eine Lücke:
                    # Säulenhöhen nachzumessen hieße, Zahlen zu erfinden, die nirgends stehen.
                    if series and is_regular(series) and sum(1 for s in series for v in s["values"] if v is not None) >= 2:
                        chart.kind, chart.header, chart.rows, chart.extras = "diagram", header, series, extras[:20]
                    elif not images:
                        continue
                # Titel: die kurze Zeile direkt über Tabelle bzw. Diagramm
                title = [x for x in blocks if top - 40 <= x[3] <= top + 30 and len(x[4]) < 140 and not _CAPTION_RE.search(x[4])]
                if title:
                    chart.title = " ".join(title[0][4].split())
                previous_bottom = b[3]
                out.append(chart)
    return out


def compact(charts: list[Chart], limit: int = 40_000) -> str:
    """Die Grafiken als knapper Text für ein Modell — jede Zahl, wie sie im
    Material steht (deutsche Schreibweise), mit Seite und Nummer."""
    parts = []
    for c in charts:
        if not c.rows:
            continue
        header = " | ".join(c.header)
        rows = "\n".join(f"  {r['label'] or '–'}: " + " | ".join("–" if v is None else _german(v) for v in r["values"])
                         for r in c.rows[:30])
        extra = f"\n  Beiwerk: {' · '.join(c.extras[:12])}" if c.extras else ""
        parts.append(f"[Grafik {c.number}] PDF-S. {c.page} · {_KIND_LABEL.get(c.kind, c.kind)} · {c.title}\n"
                     f"  Unterschrift: {c.caption}\n  Spalten: {header}\n{rows}{extra}")
    return "\n\n".join(parts)[:limit]


_KIND_LABEL = {"table": "Tabelle", "diagram": "Diagramm", "image": "Bild"}


def _german(v: float) -> str:
    if float(v).is_integer() and abs(v) >= 1000:
        return f"{v:,.0f}".replace(",", ".")
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")
