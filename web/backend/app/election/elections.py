"""Welche Wahlen es gibt: Identität, Termin, Quelle — je eine Datei.

Bis 09/2026 stand „Ratswahl Oldenburg, 13.09.2026" nicht an einer Stelle,
sondern an acht: die Basis-URL in ``votemanager.py``, die Wahl-Id der OB-Wahl
in ``mayor.py``, eine zweite in ``presentation.py``, der Referenzordner in
``reference.py``, der Zeitpunkt des Wahlschlusses als
``ELECTION_NIGHT_START``, das Kandidatenregister als Pfadkonstante, und in
``service._bare`` noch einmal Titel und Sitzzahl von Hand. Eine zweite Wahl —
die OB-Stichwahl am 27.09.2026 — hätte jede dieser Stellen angefasst.

Jetzt ist eine Wahl **eine Datei** in ``kommunalwahl/wahlen/``:

    ratswahl-2026.json    die Ratswahl: Register, Referenz, drei CSVs
    ob-2026.json          die OB-Wahl: keine CSV, nur eine Wahl-Id

**Warum JSON und nicht — wie bei Tipprunden und Feature-Schaltern — Code.**
Die Registry dort beschreibt *Verhalten* (was ist freigeschaltet, wie heißt
eine Runde). Eine Wahl beschreibt die *Welt*: Adressen beim Votemanager,
Gebiets-Ids, ein Datum, Dateinamen. Das ist dieselbe Gattung wie
``kandidaten.json`` und ``wahl-fakten.json``, es liegt neben ihnen, und
``scripts/wahl_einfrieren.py`` liest es mit.

**Welche Wahl die Seite zeigt**, sagt ``active()``: die jüngste Ratswahl, die
nicht mehr Entwurf ist — oder, wenn ``WAHLABEND_ELECTION`` in der ``.env``
steht, die dort genannte. Der Notausgang ist derselbe Gedanke wie bei
``WAHLABEND_COLUMNS``: Am Wahlabend soll eine Umstellung eine Zeile in der
``.env`` und ein Dienst-Neustart sein, kein Merge und kein Deploy.

**Was die Registry NICHT tut:** Sie rechnet nicht. Wie aus Stimmen Sitze
werden, steht weiter in ``seats.py`` (NKWG §§ 36/37, gegen das amtliche
Ergebnis 2021 verifiziert) — die Registry sagt nur, *welche* Zahlen gemeint
sind und *woher* sie kommen.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

#: Repo-Wurzel: web/backend/app/election/ -> vier Ebenen hoch.
ROOT = Path(__file__).resolve().parents[4]
WAHLEN = ROOT / "kommunalwahl" / "wahlen"

_log = logging.getLogger("ratslotse.web.wahlabend")

#: Was eine Wahl sein kann. ``council`` rechnet nach NKWG in Sitze um,
#: ``mayor`` kennt nur Prozente (und eine Stichwahl ist davon ein Fall).
KINDS = ("council", "mayor")
STATUS = ("entwurf", "live", "rueckblick")


@dataclass(frozen=True)
class Source:
    """Woher die Zahlen kommen. Heute gibt es genau einen Adapter."""

    adapter: str
    base: str
    #: Nur bei Wahlen mit Open Data: Schlüssel -> Pfad unterhalb von ``base``.
    files: dict[str, str]
    #: Wahl-Id der Ergebnisdarstellung (``/daten/api/wahl_<id>/``) — ``None``,
    #: solange es sie noch nicht gibt; dann greift ``discover``.
    presentation_id: int | None
    #: Wie die Wahl-Id zur Laufzeit zu finden ist, wenn sie heute noch nicht
    #: vergeben ist: ``{"title_contains": "Stichwahl"}`` sucht den Eintrag in
    #: ``termin.json``. Gemessen an 2006 und 2021 (``api/termine.json`` der
    #: Stadt): Eine Stichwahl bekommt KEINEN eigenen Termin, sie erscheint
    #: unter dem der Hauptwahl — die Basis-URL steht also fest, die Id nicht.
    discover: dict[str, str] | None
    #: Gebiets-Id der Stadt für diese Wahl — Vorgabe, falls ``wahl.json`` bzw.
    #: ``termin.json`` gerade nicht zu haben ist.
    city_id: str | None
    #: Ebene der Wahlbereiche (nur Ratswahl).
    areas_level: str | None

    def api_path(self, presentation_id: int | None = None) -> str:
        """Der API-Pfad — mit der gefundenen Id, sonst mit der eingetragenen."""
        gewaehlt = presentation_id if presentation_id is not None else self.presentation_id
        if gewaehlt is None:
            raise LookupError("Diese Wahl hat noch keine Wahl-Id; sie muss erst gefunden werden.")
        return f"/daten/api/wahl_{gewaehlt}"


@dataclass(frozen=True)
class Election:
    slug: str
    kind: str
    title: str
    short_title: str
    date: str
    #: Wahlschluss mit Zeitzone — ab hier wird im Minutentakt abgerufen.
    polls_close: datetime
    #: Zu vergebende Sitze (nur ``council``). Steht auch im Register; die
    #: Registry trägt sie, damit ``service._bare`` sie kennt, wenn genau das
    #: Register nicht lesbar ist. ``tests/test_wahlregistry.py`` hält beide
    #: Zahlen gegeneinander — eine doppelte Angabe ohne Wächter wäre eine Falle.
    seats: int
    status: str
    source: Source
    #: Nur ``council``: Kandidatenregister und Referenzordner der Vorwahl.
    register_path: Path | None
    reference_folder: Path | None
    #: Wie die Vorwahl in der Anzeige heißt — „2021". Stand bis 09/2026 als
    #: Literal an rund dreißig Stellen im Frontend und in den Teilen-Bildern;
    #: bei der nächsten Kommunalwahl wären das dreißig stille Lügen.
    previous_label: str
    #: Nur ``council``: die OB-Wahl, die auf derselben Seite erscheint.
    mayor: str | None
    #: Nur ``mayor``: (Datei, Schlüssel, Slugs) der Kandidaturen. Die Slugs
    #: sind leer = alle; eine Stichwahl nennt genau die beiden, die antreten.
    candidates: tuple[Path, str, tuple[str, ...]] | None
    #: Nur Stichwahl: der erste Wahlgang — Vergleichswert und Generalprobe.
    first_round: str | None

    @property
    def year(self) -> str:
        return self.date[:4]


def _pfad(roh: object) -> Path | None:
    return ROOT / str(roh) if isinstance(roh, str) and roh else None


def _aus(datei: Path) -> Election:
    roh = json.loads(datei.read_text(encoding="utf-8"))
    quelle = roh.get("source") or {}
    kandidaten = roh.get("candidates") or None
    return Election(
        slug=roh["slug"], kind=roh["kind"], title=roh["title"],
        short_title=roh.get("short_title") or roh["title"],
        date=roh["date"], polls_close=datetime.fromisoformat(roh["polls_close"]),
        seats=int(roh.get("seats", 0)), status=roh.get("status", "entwurf"),
        source=Source(
            adapter=quelle.get("adapter", "votemanager"), base=str(quelle.get("base", "")).rstrip("/"),
            files=dict(quelle.get("files") or {}), presentation_id=quelle.get("presentation_id"),
            city_id=quelle.get("city_id"), areas_level=quelle.get("areas_level"),
            discover=dict(quelle["discover"]) if quelle.get("discover") else None,
        ),
        register_path=_pfad(roh.get("register")),
        reference_folder=_pfad(roh.get("reference")),
        previous_label=str(roh.get("previous_label") or ""),
        mayor=roh.get("mayor"),
        candidates=(ROOT / kandidaten["file"], kandidaten["key"],
                    tuple(kandidaten.get("only") or ())) if kandidaten else None,
        first_round=roh.get("first_round"),
    )


@lru_cache(maxsize=1)
def all() -> dict[str, Election]:  # noqa: A001 — „alle Wahlen“; der Name ist hier der treffende
    """Jede Datei in ``kommunalwahl/wahlen/``, nach Slug."""
    wahlen = {}
    for datei in sorted(WAHLEN.glob("*.json")):
        wahl = _aus(datei)
        if wahl.slug != datei.stem:
            raise ValueError(f"{datei.name}: „slug“ ist „{wahl.slug}“ — Datei und Slug müssen gleich heißen.")
        wahlen[wahl.slug] = wahl
    if not wahlen:
        raise FileNotFoundError(f"{WAHLEN} enthält keine Wahl.")
    return wahlen


def get(slug: str | None) -> Election | None:
    return all().get(slug) if slug else None


def _vorgabe() -> Election:
    """Die jüngste Ratswahl, die kein Entwurf mehr ist.

    Bewusst nach Datum und nicht nach ``status: live``: Eine Wahl ist schon
    vor ihrem Abend die richtige Antwort (die Seite zeigt dann den Countdown
    und die Generalprobe), und nach ihr bleibt sie es, bis eine spätere
    dazukommt.
    """
    ratswahlen = [w for w in all().values() if w.kind == "council" and w.status != "entwurf"]
    if not ratswahlen:
        raise FileNotFoundError("Keine Ratswahl in kommunalwahl/wahlen/ (alle sind Entwurf).")
    return max(ratswahlen, key=lambda w: (w.date, w.slug))


def active() -> Election:
    """Die Wahl, die ``/api/wahlabend`` zeigt — mit Notausgang aus der ``.env``."""
    gewuenscht = os.environ.get("WAHLABEND_ELECTION", "").strip()
    if gewuenscht:
        wahl = all().get(gewuenscht)
        if wahl is not None and wahl.kind == "council":
            return wahl
        _log.warning("WAHLABEND_ELECTION nennt „%s“ — das ist keine bekannte Ratswahl; "
                     "es bleibt bei der Vorgabe.", gewuenscht)
    return _vorgabe()


def runoff() -> Election | None:
    """Die Stichwahl, wenn es eine gibt — die jüngste Mehrheitswahl mit einem
    ersten Wahlgang, die kein Entwurf mehr ist.

    Sie ist bewusst NICHT ``active()``: Die Ratswahl bleibt die Wahl, die
    ``/api/wahlabend`` zeigt, und der Tippspiel-Vergleich bleibt am ERSTEN
    Wahlgang. Die Stichwahl hat ihre eigene Seite.
    """
    kandidaten = [w for w in all().values()
                  if w.kind == "mayor" and w.first_round and w.status != "entwurf"]
    return max(kandidaten, key=lambda w: (w.date, w.slug)) if kandidaten else None


#: Ab wann eine Wahl „im Fokus" ist und wie lange sie es bleibt
#: (docs/plan-wahlen-generalisieren.md, PR 7). Zwei Tage vorher ist früh
#: genug, dass ein geteilter Link am Wahlwochenende schon richtig führt, und
#: spät genug, dass keine Seite wochenlang einen Countdown zeigt. Drei Tage
#: danach sind für alle, die am Montag nachlesen.
FOKUS_VORHER = timedelta(days=2)
FOKUS_NACHHER = timedelta(days=3)


def focus(jetzt: datetime | None = None) -> Election:
    """Die Wahl, auf die eine Seite gerade zeigen würde.

    Die Regel, in dieser Reihenfolge:

    1. Läuft gerade ein Wahlwochenende, **die** Wahl — und liegen zwei am
       selben Tag (13.09.2026: Ratswahl und OB-Wahl), die Ratswahl. Sie ist
       die, nach der Leute suchen.
    2. Sonst die nächste anstehende.
    3. Sonst die zuletzt gelaufene (``active()``).

    Sie steht hier und nicht in einer Seite, weil mehrere Stellen sie
    brauchen: ``/api/app-config`` für den Countdown auf Startseite und
    Heute-Karte, und später die Übersicht unter ``/wahlen``.
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    # Steht in der ``.env`` eine Wahl, ist SIE gemeint — sonst zeigte der
    # Notausgang nur die halbe Seite um: /api/wahlabend die gewählte, der
    # Countauf der Startseite weiter die aus dem Kalender.
    gewuenscht = os.environ.get("WAHLABEND_ELECTION", "").strip()
    if gewuenscht and gewuenscht in all():
        return all()[gewuenscht]
    kandidaten = [w for w in all().values() if w.status != "entwurf"]
    if not kandidaten:
        return active()

    def rang(w: Election) -> tuple:
        # Ratswahl vor OB-Wahl, sonst nach Datum — bei Gleichstand entscheidet
        # der Slug, damit die Antwort nicht am Dateisystem hängt.
        return (0 if w.kind == "council" else 1, w.polls_close, w.slug)

    im_fenster = [w for w in kandidaten
                  if w.polls_close - FOKUS_VORHER <= jetzt <= w.polls_close + FOKUS_NACHHER]
    if im_fenster:
        return min(im_fenster, key=rang)
    kommend = [w for w in kandidaten if w.polls_close > jetzt]
    if kommend:
        return min(kommend, key=lambda w: (w.polls_close, rang(w)))
    return active()


def path_of(wahl: Election) -> str:
    """Wo diese Wahl zu sehen ist."""
    return "/wahlabend/stichwahl" if wahl.first_round else "/wahlabend"


def mayor_of(wahl: Election | None = None) -> Election | None:
    """Die OB-Wahl, die zu einer Ratswahl gehört — oder ``None``."""
    wahl = wahl or active()
    kandidat = all().get(wahl.mayor) if wahl.mayor else None
    return kandidat if kandidat is not None and kandidat.kind == "mayor" else None


def reset() -> None:
    """Registry neu einlesen — für Tests, die eine Datei erzeugen."""
    all.cache_clear()
