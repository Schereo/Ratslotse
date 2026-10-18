"""„Mein Viertel": Ist der Zeitraum eines Vorhabens schon vorbei?

Das Register hält den Stand eines Vorhabens so fest, wie ihn der jüngste
Beschluss nennt — „Im Bau, bis Januar 2026". Ein Jahr später steht dort
dasselbe, und die Stadt-Highlights zeigten am 03.10.2026 vier von sechs
Vorhaben, deren Bauzeit längst vorbei war (Skateanlage Eversten „bis Januar
2026", IGS-Sporthalle Kreyenbrück „4. Quartal 2025", Sandweg „2024–2025",
Mädchenhaus Ehnernstraße „Ende 2025"). Ob die Sache fertig ist, weiß der Rat
nicht — er beschließt keinen Bauabschluss. Was wir wissen: Der genannte
Zeitraum ist vorbei, oder seit über einem Jahr kam kein Beschluss dazu.

Dieses Modul rechnet daraus einen abgeleiteten Zustand, **deterministisch und
ohne Sprachmodell**: Den Zeitraum liest ein kleiner Parser, das Datum ist das
heutige. Ein Sprachmodell, das „bis Januar 2026" einordnen soll, kennt das
heutige Datum nicht; der Bündelungs-Prompt bekommt es inzwischen zwar mit,
aber das Urteil gehört hierher, wo es sich testen lässt.

Zustände (``schedule``):

- ``likely_done`` — im Bau, und der genannte Zeitraum ist vorbei: vermutlich
  abgeschlossen.
- ``overdue`` — Idee, Planung oder beschlossen, und der genannte Zeitraum ist
  vorbei: Zeitplan überschritten.
- ``quiet`` — kein (lesbares) Ende genannt, und der letzte Beschluss ist
  älter als ``QUIET_MONTHS``: Der Stand kann veraltet sein.

Fertige und abgelehnte Vorhaben bekommen nie einen Zustand.
"""
from __future__ import annotations

import calendar
import re
from datetime import date

#: Ohne genanntes Ende: Ab so vielen Monaten ohne neuen Beschluss gilt der
#: Stand als möglicherweise veraltet.
QUIET_MONTHS = 12

#: Stände, die noch etwas erwarten lassen.
OPEN_STAGES = ("idea", "planning", "decided", "building")

_MONATE = {
    "januar": 1, "jan": 1, "jänner": 1, "februar": 2, "feb": 2, "märz": 3, "maerz": 3, "mär": 3,
    "april": 4, "apr": 4, "mai": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7, "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9, "oktober": 10, "okt": 10, "november": 11, "nov": 11,
    "dezember": 12, "dez": 12,
}
_MONAT = r"(?P<monat>" + "|".join(sorted(_MONATE, key=len, reverse=True)) + r")\.?"
_JAHR = r"(?P<jahr>(?:19|20)\d{2})"

#: Ungefähre Zeitangaben → Ende des gemeinten Abschnitts (Monat, Tag). Im
#: Zweifel das SPÄTERE Ende: Ein Vorhaben fälschlich als überfällig zu
#: zeigen, wäre der schlimmere Fehler.
_UNGEFAEHR = {
    "anfang": (4, 30), "jahresbeginn": (4, 30), "frühjahr": (5, 31), "frühling": (5, 31),
    "mitte": (8, 31), "jahresmitte": (8, 31), "sommer": (9, 30), "herbst": (11, 30),
    "ende": (12, 31), "jahresende": (12, 31), "spätsommer": (9, 30), "spätherbst": (12, 31),
}


def _monatsende(jahr: int, monat: int) -> date:
    return date(jahr, monat, calendar.monthrange(jahr, monat)[1])


def _jahr4(s: str, bezug: int) -> int:
    """„26" in „2025/26" → 2026."""
    if len(s) == 4:
        return int(s)
    return (bezug // 100) * 100 + int(s)


#: Die Muster, längste und genaueste zuerst. Jeder Treffer belegt seinen
#: Abschnitt; spätere Muster sehen ihn nicht mehr („4. Quartal 2025" ist kein
#: Jahr 2025 plus ein Datum). Je Muster eine Funktion Treffer → Enddatum.
_MUSTER: list[tuple[re.Pattern[str], object]] = []


def _muster(regex: str):
    def deko(fn):
        _MUSTER.append((re.compile(regex, re.IGNORECASE), fn))
        return fn
    return deko


@_muster(r"(?P<tag>\d{1,2})\.\s?(?P<mon>\d{1,2})\.\s?" + _JAHR)
def _datum(m: re.Match) -> date | None:
    try:
        return date(int(m["jahr"]), int(m["mon"]), int(m["tag"]))
    except ValueError:
        return None


@_muster(r"(?P<tag>\d{1,2})\.\s*" + _MONAT + r"\s+" + _JAHR)
def _datum_wort(m: re.Match) -> date | None:
    try:
        return date(int(m["jahr"]), _MONATE[m["monat"].lower()], int(m["tag"]))
    except ValueError:
        return None


@_muster(r"(?:schul|kita-?|kindergarten|kindertagesstätten|ausbildungs|betreuungs)jahr(?:es)?\s+"
         r"(?P<a>(?:19|20)\d{2})\s*/\s*(?P<b>\d{2,4})")
def _schuljahr(m: re.Match) -> date:
    # Ein Schul- oder Kita-Jahr endet am 31. Juli seines zweiten Jahres.
    return date(_jahr4(m["b"], int(m["a"])), 7, 31)


_QUARTAL_WORT = {"erste": 1, "zweite": 2, "dritte": 3, "vierte": 4, "letzte": 4}


@_muster(r"(?P<q>[1-4]\.|erste[nmrs]?|zweite[nmrs]?|dritte[nmrs]?|vierte[nmrs]?|letzte[nmrs]?)"
         r"\s*quartal(?:s)?\s+(?:des\s+jahres\s+)?" + _JAHR)
def _quartal(m: re.Match) -> date:
    q = m["q"].lower()
    nummer = int(q[0]) if q[0].isdigit() else _QUARTAL_WORT[re.sub(r"[nmrs]$", "", q)]
    return _monatsende(int(m["jahr"]), nummer * 3)


@_muster(r"\bQ(?P<q>[1-4])\s*/?\s*" + _JAHR)
def _quartal_kurz(m: re.Match) -> date:
    return _monatsende(int(m["jahr"]), int(m["q"]) * 3)


@_muster(r"(?P<h>1|2|erste[nmrs]?|zweite[nmrs]?)\.?\s*(?:halbjahr|jahreshälfte|hälfte)\s+(?:des\s+jahres\s+)?" + _JAHR)
def _halbjahr(m: re.Match) -> date:
    zweite = m["h"].lower().startswith(("2", "zweit"))
    return _monatsende(int(m["jahr"]), 12 if zweite else 6)


@_muster(r"winter\s+(?P<a>(?:19|20)\d{2})\s*/\s*(?P<b>\d{2,4})")
def _winter_doppel(m: re.Match) -> date:
    return date(_jahr4(m["b"], int(m["a"])), 3, 31)


@_muster(_MONAT + r"\s+" + _JAHR)
def _monat(m: re.Match) -> date:
    return _monatsende(int(m["jahr"]), _MONATE[m["monat"].lower()])


@_muster(r"winter\s+" + _JAHR)
def _winter(m: re.Match) -> date:
    return date(int(m["jahr"]) + 1, 3, 31)


@_muster(r"(?<![A-Za-zÄÖÜäöüß])(?P<wort>" + "|".join(sorted(_UNGEFAEHR, key=len, reverse=True)) + r")\s+(?:des\s+jahres\s+)?" + _JAHR)
def _ungefaehr(m: re.Match) -> date:
    monat, tag = _UNGEFAEHR[m["wort"].lower()]
    return date(int(m["jahr"]), monat, tag)


@_muster(r"(?P<a>(?:19|20)\d{2})\s*(?:[–—-]|bis)\s*(?P<b>(?:19|20)?\d{2})(?![\d./])")
def _jahresspanne(m: re.Match) -> date | None:
    b = _jahr4(m["b"], int(m["a"]))
    if b < int(m["a"]):
        return None
    return date(b, 12, 31)


@_muster(r"(?P<a>(?:19|20)\d{2})\s*/\s*(?P<b>\d{2}|(?:19|20)\d{2})(?![\d.])")
def _doppeljahr(m: re.Match) -> date:
    # „2025/2026" ohne Zusatz: Schul-, Haushalts- oder Kalenderjahr — das
    # spätere Ende ist das Ende des zweiten Jahres.
    return date(_jahr4(m["b"], int(m["a"])), 12, 31)


@_muster(r"(?<![\d.])" + _JAHR + r"(?![\d])")
def _jahr(m: re.Match) -> date:
    return date(int(m["jahr"]), 12, 31)


#: Steht davor, ist die Angabe ein BEGINN, kein Ende: „ab September 2025",
#: „ab Schuljahr 2027", „seit 2020". Ein Beginn in der Vergangenheit sagt
#: nichts darüber, ob etwas vorbei ist.
_BEGINN_RE = re.compile(
    r"\b(?:ab|seit|beginnend(?:\s+(?:im|mit|ab))?|von|vom|starten?d?|start|baubeginn|beginn)\s+"
    r"(?:dem\s+|der\s+|des\s+|im\s+|voraussichtlich\s+)?(?:[A-ZÄÖÜa-zäöüß][\w-]*\s+)?$",
    re.IGNORECASE)


def zeitraum_ende(text: str | None) -> date | None:
    """Das späteste ENDE, das ein Menschentext wie „Schuljahr 2025/2026",
    „4. Quartal 2025" oder „Mitte Juni 2025 bis Januar 2026" nennt.

    ``None``, wenn der Text kein Ende hergibt: gar keine Zeitangabe („zwei
    Jahre", „in den nächsten Kita-Jahren") oder nur einen Beginn („ab März
    2026"). Mehrere Angaben („ab Mai 2025; Vermarktung 2026") → die späteste,
    die kein Beginn ist.
    """
    if not text:
        return None
    belegt = [False] * len(text)
    enden: list[date] = []
    for regex, fn in _MUSTER:
        for m in regex.finditer(text):
            if any(belegt[m.start():m.end()]):
                continue
            for i in range(m.start(), m.end()):
                belegt[i] = True
            ende = fn(m)  # type: ignore[operator]
            if ende is None:
                continue
            davor = text[max(0, m.start() - 40):m.start()]
            # Ein freistehendes „ab X" ist Beginn. Nicht aber „von 2025 bis
            # 2027": Dort IST der Treffer schon die Spanne (das „bis" gehört
            # zum Muster), oder hinter ihm folgt das Ende.
            spanne = re.search(r"\bbis\b|[–—]|\d\s*-\s*\d", m.group(0), re.IGNORECASE)
            if (_BEGINN_RE.search(davor) and not spanne
                    and not re.match(r"\s*(?:bis\b|[–—-])", text[m.end():], re.IGNORECASE)):
                continue
            enden.append(ende)
    return max(enden) if enden else None


def _monate_zwischen(frueher: date, spaeter: date) -> int:
    return (spaeter.year - frueher.year) * 12 + (spaeter.month - frueher.month) - (spaeter.day < frueher.day)


_MONATSNAMEN = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
                "Oktober", "November", "Dezember")


def schedule_state(stage: str | None, when: str | None, last_date: str | None,
                   today: date | None = None) -> dict:
    """``{"schedule": …, "schedule_note": …, "when_end": …}`` für ein Vorhaben.

    ``schedule`` ist ``likely_done``, ``overdue``, ``quiet`` oder ``None``;
    ``schedule_note`` der Satz, den Web und App unverändert zeigen (die Logik
    gehört ins Backend, nicht in zwei Frontends); ``when_end`` das gelesene
    Ende als ISO-Datum oder ``None``.
    """
    heute = today or date.today()
    ende = zeitraum_ende(when)
    out: dict = {"schedule": None, "schedule_note": None, "when_end": ende.isoformat() if ende else None}
    if stage not in OPEN_STAGES:
        return out
    if ende is not None:
        if ende >= heute:
            return out
        if stage == "building":
            out["schedule"] = "likely_done"
            out["schedule_note"] = (f"Laut Beschluss „{when}“ – der Zeitraum ist vorbei. "
                                    "Vermutlich abgeschlossen; einen neueren Beschluss gibt es nicht.")
        else:
            out["schedule"] = "overdue"
            out["schedule_note"] = (f"Zeitplan überschritten: genannt war „{when}“, "
                                    "ein neuerer Beschluss liegt nicht vor.")
        return out
    try:
        letzt = date.fromisoformat((last_date or "")[:10])
    except ValueError:
        return out
    if _monate_zwischen(letzt, heute) >= QUIET_MONTHS:
        out["schedule"] = "quiet"
        out["schedule_note"] = (f"Seit {_MONATSNAMEN[letzt.month - 1]} {letzt.year} kein neuer Beschluss – "
                                "der Stand kann veraltet sein.")
    return out


__all__ = ["zeitraum_ende", "schedule_state", "QUIET_MONTHS", "OPEN_STAGES"]
