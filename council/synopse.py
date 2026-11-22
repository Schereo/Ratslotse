"""Spaltenleser für Synopsen: alt | neu | Begründung, Zeile für Zeile
(docs/plan-vorlagen-aufbereiten.md, PR 17).

Eine Synopse stellt die geltende Fassung neben die neue. Im Textlayer des
PDFs sind die Spalten aber verschachtelt — gelesen wie Fließtext kommt
„335 … 400 … Empfehlung der Kommission" als ein Brei heraus, und ein Modell
kann daraus kein verlässliches alt/neu machen. Dieser Leser nimmt die Wörter
mit ihren Koordinaten (PyMuPDF), bestimmt die Spaltengrenzen aus den
Kopfzeilen („Ursprungsfassung", „Änderungen", „Begründung") und schneidet die
Seite in Blöcke, wo die Zeilen eine Lücke lassen. Ohne Modell.

Beispiel 26/0743 (Entschädigungssatzung): die Aufwandsentschädigung steigt
von 335 auf 400 € — vorher nur im Brei zu finden.
"""
from __future__ import annotations

import re
from typing import TypedDict

_KOPF_ALT = re.compile(r"^(?:ursprungsfassung|bisherige|geltende|alte|bisher|alt)", re.I)
_KOPF_NEU = re.compile(r"^(?:änderungen?|neue|neufassung|künftige|neu)", re.I)
_KOPF_GRUND = re.compile(r"^(?:begründung|erläuterung|bemerkung)", re.I)
_PARAGRAF = re.compile(r"§\s*\d+[a-z]?(?:\s*(?:Abs(?:atz|\.)\s*)?\(?\d+\)?)?")


class RuleChange(TypedDict):
    ref: str | None
    before: str
    after: str
    reason: str | None
    page: int


def _linien(seite) -> list[float]:
    """Senkrechte Tabellenlinien einer Seite (x), von links nach rechts."""
    xs = sorted({round(d["rect"].x0) for d in seite.get_drawings()
                 if d["rect"].width < 2 and d["rect"].height > 50})
    out: list[float] = []
    for x in xs:
        if not out or x - out[-1] > 8:
            out.append(x)
    return out


def _spalten_aus_linien(seite, woerter: list[tuple]) -> tuple[float, float] | None:
    """Grenzen aus den Tabellenlinien: Die Spalte unter „Ursprungsfassung"
    endet an der Linie vor „Änderungen"."""
    linien = _linien(seite)
    neu = next((w for w in woerter if _KOPF_NEU.match(w[4])), None)
    if len(linien) < 3 or neu is None:
        return None
    vor_neu = [x for x in linien if x <= neu[0] + 2]
    nach_neu = [x for x in linien if x > neu[2]]
    if not vor_neu:
        return None
    return float(vor_neu[-1]), float(nach_neu[0]) if nach_neu else float("inf")


def _spalten(woerter: list[tuple]) -> tuple[float, float] | None:
    """Grenzen alt|neu und neu|Begründung aus den Kopfzeilen der ersten Seite
    (Rückfall ohne Tabellenlinien)."""
    alt = neu = grund = None
    for w in woerter:
        t = w[4]
        if alt is None and _KOPF_ALT.match(t):
            alt = w[0]
        elif neu is None and _KOPF_NEU.match(t):
            neu = w[0]
        elif grund is None and _KOPF_GRUND.match(t):
            grund = w[0]
    if alt is None or neu is None or neu <= alt:
        return None
    b1 = neu - 40
    b2 = (grund - 30) if grund and grund > neu else float("inf")
    return b1, b2


def _bloecke(woerter: list[tuple], luecke: float) -> list[list[tuple]]:
    """Wörter nach Zeilen, Zeilen nach Blöcken (getrennt durch eine Lücke)."""
    zeilen: dict[int, list[tuple]] = {}
    for w in woerter:
        zeilen.setdefault(round(w[1] / 3), []).append(w)
    bloecke, aktuell, letzte = [], [], None
    for y in sorted(zeilen):
        oben = min(w[1] for w in zeilen[y])
        if letzte is not None and oben - letzte > luecke and aktuell:
            bloecke.append(aktuell)
            aktuell = []
        aktuell.extend(zeilen[y])
        letzte = max(w[3] for w in zeilen[y])
    if aktuell:
        bloecke.append(aktuell)
    return bloecke


def _text(woerter: list[tuple]) -> str:
    woerter = sorted(woerter, key=lambda w: (round(w[1] / 3), w[0]))
    t = " ".join(w[4] for w in woerter)
    return re.sub(r"(\w)- (\w)", r"\1\2", re.sub(r"\s+", " ", t)).strip()


def read(pdf_bytes: bytes) -> list[RuleChange]:
    """Die Änderungen einer Synopse: je Block alt, neu, Begründung, Paragraf, Seite.
    Leer, wenn die Spalten nicht zu erkennen sind (dann bleibt es beim Fließtext)."""
    import pymupdf  # noqa: PLC0415 — nur hier gebraucht

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    grenzen = None
    out: list[RuleChange] = []
    ref = None
    for n, seite in enumerate(doc, 1):
        woerter = seite.get_text("words")
        if grenzen is None:
            grenzen = _spalten_aus_linien(seite, woerter) or _spalten(woerter)
            if grenzen is None:
                return []
            kopf_unten = max((w[3] for w in woerter if _KOPF_NEU.match(w[4]) or _KOPF_ALT.match(w[4])), default=0)
            woerter = [w for w in woerter if w[1] > kopf_unten]
        b1, b2 = grenzen
        hoehe = sorted(w[3] - w[1] for w in woerter)[len(woerter) // 2] if woerter else 10
        for block in _bloecke(woerter, luecke=hoehe * 0.9):
            mitte = lambda w: (w[0] + w[2]) / 2  # noqa: E731
            alt = _text([w for w in block if mitte(w) < b1])
            neu = _text([w for w in block if b1 <= mitte(w) < b2])
            grund = _text([w for w in block if mitte(w) >= b2]) or None
            if m := _PARAGRAF.search(" ".join([alt, neu])):
                ref = re.sub(r"\s+", " ", m.group(0))
            if not neu or neu == alt or len(neu) < 3:
                continue
            out.append({"ref": ref, "before": alt, "after": neu, "reason": grund, "page": n})
    return out


def changes(regeln: list[RuleChange], kontext: int = 5) -> list[dict]:
    """Die geänderten Stellen je Block, mit ein paar Wörtern Umfeld:
    ``{"ref": "§ 2", "page": 1, "before": "… monatlich 335 Euro.", "after": "… monatlich 400 Euro."}``."""
    from council.motions import word_diff  # noqa: PLC0415

    out = []
    for r in regeln:
        d = word_diff(r["before"], r["after"])
        for i, (op, _) in enumerate(d):
            if op != "-":
                continue
            neu = d[i + 1][1] if i + 1 < len(d) and d[i + 1][0] == "+" else ""
            vor = d[i - 1][1].split()[-kontext:] if i > 0 and d[i - 1][0] == "=" else []
            ende = i + 2 if neu else i + 1
            nach = d[ende][1].split()[:kontext] if ende < len(d) and d[ende][0] == "=" else []
            alt_t = " ".join(vor + d[i][1].split() + nach)
            neu_t = " ".join(vor + neu.split() + nach)
            if neu and len(d[i][1]) <= 200 and len(neu) <= 200:
                out.append({"ref": r["ref"], "page": r["page"], "before": alt_t, "after": neu_t})
    return out
