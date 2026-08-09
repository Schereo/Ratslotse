"""Regex-Ernte aus Bestandstexten (Schatzsuche 09.08.2026, Quick-Wins).

Pure Extraktoren über bereits gespeicherte Rohtexte — kein Netz, kein LLM.
Gegen die Prod-Kopie validiert: federführendes Amt in ~97 % der Vorlagen,
Sitzungsort in 838/841 Protokollen, Klima-Check (Oldenburger „Auswirkungen:
b) Klima"-Block, ab 2022 Standard), Beschlussvorschlag↔Beschluss-Vergleich.
"""
from __future__ import annotations

import difflib
import re

# Abschnitts-Überschriften, an denen ein Block sicher endet.
_ENDE = r"(?:[a-c]\)\s|Beschlussvorschlag|Sachverhalt|Begründung|Beratungsfolge|Finanzielle Auswirkungen|Anlagen?\b|Seite:\s*\d)"

_FLOSKELN = {"keine", "keine.", "-", "–", "./.", "entfällt", "entfällt.", "nein",
             "keine unmittelbaren"}


def _saeubern(text: str, max_len: int = 800) -> str | None:
    """Abschnitt bereinigen; Floskeln und Leeres → None."""
    zeilen = [z.strip() for z in (text or "").splitlines()]
    inhalt = " ".join(z for z in zeilen if z and not re.match(r"^(?:Seite:\s*\d+|Ausdruck vom:)", z))
    inhalt = re.sub(r"\s+", " ", inhalt).strip()
    if not inhalt or inhalt.lower() in _FLOSKELN:
        return None
    if len(inhalt) > max_len:
        # An der Satzgrenze schneiden statt mitten im Wort („Maastrichter Stra").
        geschnitten = inhalt[:max_len]
        punkt = geschnitten.rfind(". ")
        if punkt >= max_len // 2:
            inhalt = geschnitten[: punkt + 1]
        else:
            inhalt = geschnitten.rsplit(" ", 1)[0] + " …"
    return inhalt


# --- Vorlagen: Auswirkungen a) Finanzen / b) Klima ---------------------------

# Getrennt gesucht (nicht als ein Block): manche Vorlagen führen nur einen der
# beiden Punkte, die Reihenfolge ist aber stabil a) → b).
_FINANZ_RE = re.compile(r"\ba\)\s*Finanzen\s*\n(?P<t>.*?)(?=\n\s*b\)\s*Klima|\n\s*" + _ENDE + r"|\Z)",
                        re.DOTALL)
_KLIMA_RE = re.compile(r"\bb\)\s*Klima\s*\n(?P<t>.*?)(?=\n\s*" + _ENDE + r"|\Z)",
                       re.DOTALL)
# Der Klima-Block beginnt fast immer mit dem Prüfvermerk — der ist die Kerninfo.
_RELEVANT_RE = re.compile(r"(?:Prüfungsrelevant:\s*)?\b(Ja|Nein)\b", re.IGNORECASE)


def auswirkungen(vorlagen_text: str) -> dict:
    """{"finanzen": str|None, "klima": str|None} aus dem Auswirkungen-Block.

    „klima" enthält den Prüfvermerk mitsamt Begründung (z. B. „Prüfungsrelevant:
    Nein, … Sachstandsbericht"), „finanzen" die Kostenangabe der Verwaltung."""
    text = vorlagen_text or ""
    fin = _FINANZ_RE.search(text)
    kli = _KLIMA_RE.search(text)
    return {"finanzen": _saeubern(fin.group("t")) if fin else None,
            "klima": _saeubern(kli.group("t"), max_len=2500) if kli else None}


def klima_relevant(klima_text: str | None) -> bool | None:
    """Ja/Nein aus dem Prüfvermerk am Blockanfang; None wenn nicht erkennbar."""
    m = _RELEVANT_RE.match((klima_text or "").strip())
    if not m:
        return None
    return m.group(1).lower() == "ja"


# --- Vorlagen: federführendes Amt --------------------------------------------

# Kopfzeilen-Formate: „Stadtplanungsamt Vorlagen-Nr:" (alt), „<Amt> Datum:"
# (neu), sowie mehrzeilig umbrochene Ämter vor einer eigenen „Vorlagen-Nr:"-
# Zeile. Heuristik statt Whitelist: der Treffer muss nach Verwaltungseinheit
# klingen — sonst fängt man „Ausdruck vom:"-Zeilen.
_AMT_RE = re.compile(r"^\s*([A-ZÄÖÜ][\w äöüßÄÖÜ/,.-]{2,70}?)\s+(?:Vorlagen-?Nr|Datum)\s*:",
                     re.MULTILINE)
_AMT_ANKER_RE = re.compile(r"Vorlagen-?Nr\s*:", re.MULTILINE)
_AMT_WORTE = ("amt", "dezernat", "betrieb", "büro", "feuerwehr", "referat", "stab",
              "gleichstellung", "rechnungsprüfung", "verbraucherschutz", "veterinär")
_KEIN_AMT_RE = re.compile(r"^(?:\d|öffentlich|nichtöffentlich|Ausdruck|Seite)", re.IGNORECASE)


def _klingt_nach_amt(kandidat: str) -> bool:
    return any(w in kandidat.lower() for w in _AMT_WORTE)


def federfuehrendes_amt(vorlagen_text: str) -> str | None:
    kopf = (vorlagen_text or "")[:2500]
    for m in _AMT_RE.finditer(kopf):
        kandidat = re.sub(r"\s+", " ", m.group(1)).strip(" ,.-")
        if _klingt_nach_amt(kandidat):
            return kandidat[:80]
    # Mehrzeilig umbrochene Ämter („Eigenbetrieb Gebäudewirtschaft und\nHochbau\n
    # Vorlagen-Nr:"): die 1–2 nichtleeren Zeilen vor dem Anker zusammensetzen.
    anker = _AMT_ANKER_RE.search(kopf)
    if anker:
        davor = [z.strip() for z in kopf[:anker.start()].splitlines() if z.strip()]
        davor = [z for z in davor if not _KEIN_AMT_RE.match(z)]
        for fenster in (2, 1):
            kandidat = re.sub(r"\s+", " ", " ".join(davor[-fenster:])).strip(" ,.-")
            if 3 <= len(kandidat) <= 80 and _klingt_nach_amt(kandidat):
                return kandidat
    return None


# --- Protokolle: Sitzungsort -------------------------------------------------

_ORT_RE = re.compile(r"Sitzungsort:\s*(.+)")


def sitzungsort(protokoll_text: str) -> str | None:
    m = _ORT_RE.search((protokoll_text or "")[:3000])
    if not m:
        return None
    ort = re.sub(r"\s+", " ", m.group(1)).strip(" ,.-")
    return ort[:120] or None


# --- Vorlagen: Beschlussvorschlag + Abweichung zum Beschluss -----------------

_VORSCHLAG_RE = re.compile(
    r"Beschluss(?:vorschlag|entwurf)[^\n]{0,60}?:?\s*\n(?P<v>.*?)"
    r"(?=\n\s*(?:Sachverhalt|Begründung|Finanzielle|Auswirkungen|Anlagen?\b|Beratungsfolge)|\Z)",
    re.DOTALL)


def beschlussvorschlag(vorlagen_text: str) -> str | None:
    m = _VORSCHLAG_RE.search(vorlagen_text or "")
    if not m:
        return None
    return _saeubern(m.group("v"), max_len=1500)


def _norm(s: str) -> str:
    return re.sub(r"[^a-zäöüß0-9 ]", "", re.sub(r"\s+", " ", (s or "").lower())).strip()


def abweichung(vorschlag: str | None, beschluss: str | None) -> str | None:
    """Wie stark weicht der gefasste Beschluss vom Verwaltungsvorschlag ab?

    → "unveraendert" | "leicht" | "stark" | None (eine Seite fehlt oder ist zu
    kurz). Maß ist Containment, nicht die symmetrische difflib-Ratio: der aus
    dem Protokoll extrahierte Beschluss ist oft eine Kurzfassung des Vorschlags
    — Kürzung allein ist keine inhaltliche Änderung. Gezählt wird, welcher
    Anteil des kürzeren Texts als gemeinsame Blöcke (ab 12 Zeichen, gegen
    Zufallstreffer) im längeren wiederkehrt."""
    v, b = _norm(vorschlag or "")[:2000], _norm(beschluss or "")[:2000]
    if len(v) < 25 or len(b) < 25:
        return None
    kurz, lang = (v, b) if len(v) <= len(b) else (b, v)
    sm = difflib.SequenceMatcher(None, kurz, lang, autojunk=False)
    getroffen = sum(bl.size for bl in sm.get_matching_blocks() if bl.size >= 12)
    anteil = getroffen / len(kurz)
    if anteil >= 0.9:
        return "unveraendert"
    if anteil >= 0.55:
        return "leicht"
    return "stark"
