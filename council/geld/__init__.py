"""Steckplätze für Haushalts-Facetten der KI-Frage.

Die zwanzig Facetten bis 09/2026 (Plan, Ist, Produkte, Schulden, …) leben
verteilt über vier Stellen in ``council/qa.py`` und je eine Methode in
``council/store.py``. Das war tragbar, solange eine Facette nach der anderen
entstand. Tims Ziel vom 02.09.2026 ist ein anderes: **fast jede Zahl der
Haushalts-Tabellen soll über die KI-Frage erreichbar sein** — rund fünfzehn
Tabellen kannte die Frage bis dahin gar nicht (Haushaltsvollzug, Satzung,
Beteiligungsbericht, Wirtschaftspläne, Spenden, Hebesätze, Vorhaben, …).

Deshalb dieses Paket: **Eine Facette = ein Modul.** Es bringt drei Dinge mit
und wird beim Import entdeckt — niemand trägt es irgendwo ein:

* ``erkennen(text, typ, facetten)`` — feuert die Facette bei diesem
  Fragewortlaut? ``text`` ist gefaltet (klein, ``ae/oe/ue/ss``, nur
  ``a-z0-9`` und Leerzeichen — s. :func:`falte`), ``typ`` der LLM-Fragetyp,
  ``facetten`` die bis dahin erkannten Facetten (damit eine Facette an eine
  andere andocken kann: „vorhaben“ an „investitionen“).
* eine **Store-Mixin-Klasse** mit genau einer Methode
  ``<methode>(woerter, year=None) -> dict | None`` — ``CouncilStore`` erbt
  alle Mixins; die Methode arbeitet mit ``self._conn``, ``self._trifft`` und
  ``self._beleg`` wie die zwanzig älteren. ``None`` heißt: nichts
  Einschlägiges — dann wächst der Prompt nicht.
* ``block(daten) -> str`` — der Prompt-Baustein; ``""`` für ``None``.

Zusammengehalten von einer :class:`Facette`; ``FACETTE`` heißt das Objekt im
Modul. ``rang`` ordnet die Facette in die Kontext-Reihenfolge ein (der Deckel
``GELD_MAX_CHARS`` schneidet hinten ab): unter 500 steht sie VOR den alten
Facetten (eng auslösende Quellen, deren Antwort die Frage ist), ab 500
dahinter (breite Quellen, die sich anhängen).

Die Regeln aus dem Abschnittskopf „Geld-Facetten“ in ``qa.py`` gelten
unverändert: erkannt wird am ROHEN Fragewortlaut, nie an den expandierten
Begriffen und nie am LLM-Fragetyp allein; die Begriffe entscheiden nur, WAS
die Quelle liefert. Und jede Facette misst sich in ihrer eigenen Testdatei
(``tests/test_geld_<name>.py``): welche Fragen sie ziehen, welche nicht, wie
groß ihr Baustein an echten Zahlen wird.
"""
from __future__ import annotations

import importlib
import pkgutil
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Facette:
    #: Schlüssel in ``geld["facets"]`` und ``GELD_FACETTEN`` — kurz, klein,
    #: deutsch wie die alten („vollzug“, „satzung“).
    name: str
    #: Name der Store-Methode im Mixin: ``(woerter, year=None) -> dict | None``.
    methode: str
    erkennen: Callable[[str, str, set[str]], bool]
    block: Callable[[Any], str]
    #: Die Mixin-Klasse mit der Methode. Kein ``__init__``, kein Zustand.
    mixin: type
    #: Kontext-Rang: < 500 vor den alten Facetten, >= 500 dahinter.
    rang: int
    #: Gemessene Obergrenze des Bausteins in Zeichen — der Wächter dagegen
    #: steht in der Testdatei der Facette.
    grenze: int
    #: Eine Frage, die diese Facette sicher zieht (Register-Test).
    probefrage: str

    @property
    def key(self) -> str:
        """Schlüssel im ``geld``-dict — derselbe wie der Name."""
        return self.name


def falte(text: str) -> str:
    """Dieselbe Faltung wie ``qa._falte`` — hier noch einmal, weil ``qa``
    dieses Paket importiert und nicht umgekehrt."""
    text = (text or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def jahrgang(conn: sqlite3.Connection, tabelle: str, spalte: str,
             year: int | None, wo: str = "") -> tuple[int | None, bool]:
    """Welcher Jahrgang wird geliefert — und ist es der gefragte?

    Fragt jemand nach 2020 und der Bestand hat 2020, kommt 2020. Fehlt der
    Jahrgang (oder nennt die Frage keinen), kommt der jüngste — und das
    zweite Feld sagt ``True``, wenn das vom Gefragten ABWEICHT. Der Baustein
    schreibt dann dazu, dass er das jüngste Jahr zeigt, statt still ein
    anderes Jahr für das gefragte auszugeben.

    ``wo`` ist eine optionale zusätzliche WHERE-Bedingung (ohne ``WHERE``)."""
    bed = f" WHERE {wo}" if wo else ""
    try:
        if year is not None:
            da = conn.execute(
                f"SELECT 1 FROM {tabelle}{bed}{' AND' if wo else ' WHERE'} "
                f"{spalte} = ? LIMIT 1", (year,)).fetchone()
            if da:
                return year, False
        juengst = conn.execute(f"SELECT MAX({spalte}) FROM {tabelle}{bed}").fetchone()[0]
    except sqlite3.OperationalError:
        return None, False
    return juengst, year is not None and juengst is not None


def de_mio(euro: float | None) -> str:
    """„12,3 Mio. €“ — deutsche Schreibweise, eine Nachkommastelle."""
    if euro is None:
        return "–"
    v = euro / 1e6
    s = f"{abs(v):,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if v < 0 else ''}{s} Mio. €"


def _lade() -> tuple[Facette, ...]:
    aus: list[Facette] = []
    for m in pkgutil.iter_modules(__path__):
        if m.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{m.name}")
        fac = getattr(mod, "FACETTE", None)
        if fac is None:
            continue
        if not isinstance(fac, Facette):
            raise TypeError(f"{mod.__name__}.FACETTE ist keine Facette")
        if not hasattr(fac.mixin, fac.methode):
            raise TypeError(f"{mod.__name__}: Mixin hat keine Methode {fac.methode}")
        aus.append(fac)
    aus.sort(key=lambda f: (f.rang, f.name))
    namen = [f.name for f in aus]
    if len(namen) != len(set(namen)):
        raise ValueError(f"Facetten-Namen doppelt: {namen}")
    return tuple(aus)


FACETTEN: tuple[Facette, ...] = _lade()
#: Vor den alten Facetten (rang < 500) / dahinter (rang >= 500).
NAMEN_VORN: tuple[str, ...] = tuple(f.name for f in FACETTEN if f.rang < 500)
NAMEN_HINTEN: tuple[str, ...] = tuple(f.name for f in FACETTEN if f.rang >= 500)
MIXINS: tuple[type, ...] = tuple(f.mixin for f in FACETTEN)
BAUSTEINE: dict[str, tuple[str, Callable[[Any], str]]] = {
    f.name: (f.key, f.block) for f in FACETTEN}
METHODEN: dict[str, str] = {f.name: f.methode for f in FACETTEN}
