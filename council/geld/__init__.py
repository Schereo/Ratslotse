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
  ``<methode>(terms, year=None) -> dict | None`` — ``CouncilStore`` erbt
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
from kern.dbfehler import tabelle_fehlt


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
    except sqlite3.OperationalError as fehler:
        if not tabelle_fehlt(fehler):
            raise
        return None, False
    return juengst, year is not None and juengst is not None


def de_mio(euro: float | None) -> str:
    """„12,3 Mio. €“ — deutsche Schreibweise, eine Nachkommastelle."""
    if euro is None:
        return "–"
    v = euro / 1e6
    s = f"{abs(v):,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if v < 0 else ''}{s} Mio. €"


def de_euro(euro: float | None) -> str:
    """„788.669 €“ — für Beträge, die in Mio. zu „0,8“ verkämen (Spenden,
    Gebühren, Pro-Kopf-Werte)."""
    if euro is None:
        return "–"
    return f"{euro:,.0f} €".replace(",", ".")


def de_zahl(v: float | None, stellen: int = 0) -> str:
    """„1.702,25“ — Tausenderpunkt und Dezimalkomma, ohne Einheit."""
    if v is None:
        return "–"
    return (f"{v:,.{stellen}f}".replace(",", "\x00").replace(".", ",")
            .replace("\x00", "."))


def de_prozent(v: float | None, stellen: int = 1) -> str:
    """„42,8 %“ — das Dezimalkomma ist die Falle, in die jeder Baustein beim
    ersten Anlauf läuft („+42.8 %“)."""
    if v is None:
        return "–"
    return f"{v:.{stellen}f} %".replace(".", ",")


def beleg_text(b: dict | None, stand: bool = False) -> str:
    """„ — Beleg: Jahresabschluss 2024, Abschnitt 6.2, S. 41“.

    Dieselbe Zeile wie ``qa._beleg_text`` — hier, weil ``qa`` dieses Paket
    importiert und nicht umgekehrt. ``stand`` hängt „Stand …“ an; die
    Facetten lassen es meist weg, weil ``as_of`` bei den Haushalts-
    Herkünften oft ein ganzer Abgrenzungssatz ist (200–300 Zeichen), den
    der Baustein-Kopf schon als Anweisung führt."""
    if not b:
        return ""
    teile = [str(t) for t in (b.get("label"), b.get("citation")) if t]
    if b.get("page"):
        teile.append(f"S. {b['page']}")
    if not teile:
        return ""
    as_of = f", Stand {b['as_of']}" if stand and b.get("as_of") else ""
    return f" — Beleg: {', '.join(teile)}{as_of}"


_JAHR = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")
_ZEITRAUM = ("seit", "ab", "nach", "zwischen", "bis")


def jahr_aus_text(text: str) -> int | None:
    """Das eine gefragte Jahr aus einem (gefalteten oder rohen) Wortlaut.

    Zwei Jahre („von 2019 bis 2024“) sind ein Zeitraum, keins; „seit 2020“,
    „ab 2020“, „nach 2020“ ist der Anfang einer Reihe, nicht der Jahrgang.
    Dieselbe Regel wie ``qa.haushaltsjahr`` — für ``erkennen``, das nur den
    Text sieht und ``qa`` nicht importieren kann."""
    t = falte(text or "")
    jahre = sorted({int(j) for j in _JAHR.findall(t)})
    if len(jahre) != 1:
        return None
    if re.search(r"\b(" + "|".join(_ZEITRAUM) + r")\s+" + str(jahre[0]) + r"\b", t):
        return None
    return jahre[0]


def lesestore(pfad: str):
    """Ein Store NUR ZUM LESEN — für Größenmessungen an einer echten Datenbank.

    ``CouncilStore`` migriert beim Öffnen und schreibt dabei; wer die
    dev-Kopie nur befragen will, darf sie nicht anfassen. Das hier öffnet
    ``mode=ro`` und bringt mit, was die Facetten-Methoden brauchen:
    ``_conn``, ``_trifft``, ``_beleg`` und alle Mixins."""
    from council.store import CouncilStore   # spät: store importiert dieses Paket

    conn = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    class _LeseStore(*MIXINS):
        _trifft = CouncilStore._trifft
        _falte_wort = CouncilStore._falte_wort
        _stamm = CouncilStore._stamm
        _beleg = CouncilStore._beleg

        def close(self) -> None:
            conn.close()

    st = _LeseStore()
    st._conn = conn
    return st


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
