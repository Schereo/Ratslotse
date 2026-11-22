"""Die Wahlprogramme zur Ratswahl 2026 als Lesestoff: je Liste Abschnitte mit
Seitenzahl, dazu Sitze und Quelle.

Die Texte liegen im Repo (``kommunalwahl/programme/<slug>.txt``, ausgewertet
für den Wahlprogramm-Vergleich, Belegkette in ``quellen/manifest.json``). Hier
wird nur gelesen und geschnitten — für „Was die Wahlprogramme dazu sagen" auf
der Punkt-Seite (``council/programm_bezug.py``).

Gezeigt werden nur Listen, die im Rat sitzen UND ein Programm haben: Wer nicht
abstimmt, dessen Programm ordnet keinen Tagesordnungspunkt ein.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent / "kommunalwahl"
#: Ziel-Länge eines Abschnitts: lang genug für eine Forderung samt Begründung,
#: kurz genug, dass fünf je Liste in einen Prompt passen.
ABSCHNITT_ZEICHEN = 800
_SEITE = re.compile(r"=+ \[Seite (\d+)\] =+")
_SATZENDE = re.compile(r"(?<=[.!?:;])\s+")


@lru_cache(maxsize=1)
def lists() -> tuple[dict, ...]:
    """Die Listen im Rat mit Programm, nach Sitzen: ``slug``, ``label``,
    ``seats``, ``title`` und ``url`` des Programms, ``paged`` (hat Seitenzahlen)."""
    wahl = json.loads((WURZEL / "referenz-2026" / "ratswahl-2026.json").read_text())
    quellen = {p["slug"]: p for p in json.loads((WURZEL / "quellen" / "manifest.json").read_text())["programme"]}
    sitze: dict[str, int] = {}
    for s in wahl["sitzverteilung"]:
        sitze[s["party"]] = sitze.get(s["party"], 0) + 1
    aus = []
    for p in wahl["parteien"]:
        q = quellen.get(p["slug"])
        if not sitze.get(p["label"]) or not q or not (WURZEL / "programme" / f"{p['slug']}.txt").exists():
            continue
        aus.append({"slug": p["slug"], "label": p["label"], "seats": sitze[p["label"]],
                    "title": q.get("titel") or f"Wahlprogramm {p['label']}", "url": q.get("url"),
                    "paged": q.get("format") == "pdf"})
    aus.sort(key=lambda x: (-x["seats"], x["label"]))
    return tuple(aus)


def _absaetze(text: str) -> list[str]:
    """Absätze eines Seitentexts — ohne Navigationsreste einer Webseite
    („Facebook", „Seite auswählen") und ohne Zeilen eines Inhaltsverzeichnisses."""
    aus = []
    for roh in re.split(r"\n\s*\n", text):
        a = re.sub(r"\s+", " ", roh).strip()
        if not a or re.search(r"\.{6,}", a):
            continue
        if len(a) < 30 and not re.search(r"[.!?:]$", a):
            continue
        aus.append(a)
    return aus


def _schneiden(absaetze: list[str]) -> list[str]:
    """Absätze zu Abschnitten von etwa ``ABSCHNITT_ZEICHEN`` fügen; ein
    überlanger Absatz wird an Satzenden geteilt. Es geht kein Text verloren —
    ein Zitat muss sich später wörtlich wiederfinden lassen."""
    stuecke: list[str] = []
    for a in absaetze:
        if len(a) <= ABSCHNITT_ZEICHEN * 1.5:
            stuecke.append(a)
            continue
        puffer = ""
        for satz in _SATZENDE.split(a):
            if puffer and len(puffer) + len(satz) > ABSCHNITT_ZEICHEN:
                stuecke.append(puffer)
                puffer = satz
            else:
                puffer = f"{puffer} {satz}".strip()
        if puffer:
            stuecke.append(puffer)
    aus: list[str] = []
    puffer = ""
    for s in stuecke:
        if puffer and len(puffer) + len(s) > ABSCHNITT_ZEICHEN:
            aus.append(puffer)
            puffer = s
        else:
            puffer = f"{puffer} {s}".strip()
    if puffer:
        aus.append(puffer)
    return [a for a in aus if len(a) >= 80]


@lru_cache(maxsize=32)
def passages(slug: str) -> tuple[dict, ...]:
    """Die Abschnitte eines Programms: ``idx``, ``page`` (``None`` bei einer
    Webseite), ``text``."""
    text = (WURZEL / "programme" / f"{slug}.txt").read_text()
    teile = _SEITE.split(text)
    seiten: list[tuple[int | None, str]] = []
    if len(teile) > 1:
        seiten = [(int(teile[i]), teile[i + 1]) for i in range(1, len(teile), 2)]
    else:
        seiten = [(None, text)]
    aus = []
    for seite, inhalt in seiten:
        for stueck in _schneiden(_absaetze(inhalt)):
            aus.append({"idx": len(aus), "page": seite, "text": stueck})
    return tuple(aus)


def text_hash(slug: str) -> str:
    return hashlib.sha256((WURZEL / "programme" / f"{slug}.txt").read_bytes()).hexdigest()[:16]


def norm(text: str | None) -> str:
    """Für den Zitat-Vergleich: Leerraum egal, Groß- und Kleinschreibung egal."""
    return re.sub(r"\s+", " ", text or "").strip().lower()


def find_quote(slug: str, quote: str) -> dict | None:
    """Der Abschnitt, in dem ``quote`` wörtlich steht — oder ``None``."""
    q = norm(quote)
    if len(q) < 20:
        return None
    return next((p for p in passages(slug) if q in norm(p["text"])), None)
