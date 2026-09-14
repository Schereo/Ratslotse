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
from datetime import datetime
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
    #: Wahl-Id der Ergebnisdarstellung (``/daten/api/wahl_<id>/``).
    presentation_id: int | None
    #: Gebiets-Id der Stadt für diese Wahl — Vorgabe, falls ``wahl.json`` bzw.
    #: ``termin.json`` gerade nicht zu haben ist.
    city_id: str | None
    #: Ebene der Wahlbereiche (nur Ratswahl).
    areas_level: str | None

    @property
    def api_path(self) -> str:
        return f"/daten/api/wahl_{self.presentation_id}"


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
    #: Nur ``council``: die OB-Wahl, die auf derselben Seite erscheint.
    mayor: str | None
    #: Nur ``mayor``: (Datei, Schlüssel) der Kandidaturen.
    candidates: tuple[Path, str] | None

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
        ),
        register_path=_pfad(roh.get("register")),
        reference_folder=_pfad(roh.get("reference")),
        mayor=roh.get("mayor"),
        candidates=(ROOT / kandidaten["file"], kandidaten["key"]) if kandidaten else None,
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


def mayor_of(wahl: Election | None = None) -> Election | None:
    """Die OB-Wahl, die zu einer Ratswahl gehört — oder ``None``."""
    wahl = wahl or active()
    kandidat = all().get(wahl.mayor) if wahl.mayor else None
    return kandidat if kandidat is not None and kandidat.kind == "mayor" else None


def reset() -> None:
    """Registry neu einlesen — für Tests, die eine Datei erzeugen."""
    all.cache_clear()
