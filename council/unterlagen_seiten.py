"""Seitenanfänge im gespeicherten Text eines Dokuments.

Ein Beleg zeigt auf eine Seite im PDF (`…getfile.php?id=…#page=2`). Dafür muss
man wissen, wo im GESPEICHERTEN Text jede Seite beginnt
(docs/plan-vorlagen-aufbereiten.md, § 3.3):

- **Vorlagen** tragen auf jeder Seite ab der zweiten den Druckkopf
  „Seite: n/m" (5.239 von 5.253). Daraus lassen sich die Seiten ohne Download
  rechnen — „Ausdruck vom:" fehlt dagegen in rund 250 Vorlagen.
- **Anlagen** haben keinen Druckkopf. Ihr Text wurde beim Speichern bereinigt
  (Trennstriche, Platzhalter, Leerraum), Rechnen über Längen ginge daneben.
  Deshalb Anker: Der Anfang jeder Seite aus ``pdf_seiten`` wird im
  gespeicherten Text gesucht, monoton von vorn.
"""
from __future__ import annotations

import bisect
import hashlib
import re

_SEITE_RE = re.compile(r"^[^\S\n]*Seite:[^\S\n]*(\d+)[^\S\n]*/[^\S\n]*(\d+)[^\S\n]*$", re.MULTILINE)
_AUSDRUCK_RE = re.compile(r"^[^\S\n]*Ausdruck[^\S\n]+vom:.*$", re.MULTILINE)
ANKER_ZEICHEN = 60


def text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def template_page_offsets(text: str) -> list[int] | None:
    """Seitenanfänge einer Vorlage aus dem Druckkopf, oder ``None``, wenn er
    fehlt oder lückenhaft ist (dann lieber kein Seitensprung als ein falscher)."""
    t = text or ""
    treffer = list(_SEITE_RE.finditer(t))
    if not treffer:
        return None
    gesamt = int(treffer[0].group(2))
    anfang: dict[int, int] = {1: 0}
    for m in treffer:
        n = int(m.group(1))
        if int(m.group(2)) != gesamt or n in anfang:
            continue
        # Die Seite beginnt mit dem Druckkopf: „Ausdruck vom:" steht, wenn es
        # da ist, direkt vor „Seite:".
        start = m.start()
        davor = t.rfind("\n", 0, max(0, m.start() - 1))
        zeile = t[davor + 1:m.start()]
        if _AUSDRUCK_RE.match(zeile):
            start = davor + 1
        anfang[n] = start
    if sorted(anfang) != list(range(1, gesamt + 1)):
        return None
    return [anfang[n] for n in range(1, gesamt + 1)]


def _verdichtet(text: str) -> tuple[str, list[int]]:
    """Text ohne Leerraum und Bindestriche, dazu je Zeichen sein Ort im Original."""
    zeichen, orte = [], []
    for i, ch in enumerate(text):
        if ch.isspace() or ch in "-­":
            continue
        zeichen.append(ch.lower())
        orte.append(i)
    return "".join(zeichen), orte


def anchor_offsets(pages: list[str], stored: str) -> list[int] | None:
    """Seitenanfänge im gespeicherten Text über den Anfang jeder Seite.

    ``None``, wenn weniger als die Hälfte der Seiten gefunden wird — dann
    stimmt der Text nicht zu den Seiten (neu gelesen, anderes Werkzeug).
    Nicht gefundene Seiten (leer, Bild) erben den Anfang der nächsten.
    """
    if not pages:
        return None
    voll, orte = _verdichtet(stored or "")
    if not voll:
        return None
    gefunden: list[int | None] = []
    pos = 0
    for seite in pages:
        anker, _ = _verdichtet(seite)
        anker = anker[:ANKER_ZEICHEN]
        if len(anker) < 12:
            gefunden.append(None)
            continue
        i = voll.find(anker, pos)
        if i < 0:
            gefunden.append(None)
            continue
        gefunden.append(orte[i])
        pos = i + len(anker)
    if sum(g is not None for g in gefunden) < max(1, len(pages) // 2):
        return None
    gefunden[0] = 0 if gefunden[0] is None else gefunden[0]
    # Lücken: eine Seite ohne Anker beginnt, wo die nächste gefundene beginnt.
    naechste = len(stored)
    for k in range(len(gefunden) - 1, -1, -1):
        if gefunden[k] is None:
            gefunden[k] = naechste
        else:
            naechste = gefunden[k]  # type: ignore[assignment]
    return [int(g) for g in gefunden]  # type: ignore[arg-type]


def page_of(offsets: list[int] | None, pos: int) -> int | None:
    """Die Seite (ab 1), auf der eine Stelle im gespeicherten Text steht."""
    if not offsets:
        return None
    return max(1, bisect.bisect_right(offsets, pos))
