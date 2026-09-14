"""Ein Rückblick ohne Netz: der eingefrorene Stand einer gelaufenen Wahl.

Die Zahlen einer Wahl liegen seit 09/2026 im Repo
(``scripts/wahl_einfrieren.py`` → ``kommunalwahl/referenz-<jahr>/``). Damit
braucht ``/wahlen/ratswahl-2026`` den Votemanager nicht mehr — und das ist der
eigentliche Gewinn: Eine Rückblick-Seite, die für ein Ergebnis von 2021 eine
fremde Adresse anfragen muss, ist keine. Die Adressen der Stadt tragen den
Wahltag im Pfad und wandern irgendwann ins Archiv.

**Gerechnet wird nicht neu, sondern gleich.** ``night()`` baut aus den
eingefrorenen CSVs denselben ``Snapshot``, den auch der Live-Abruf liefert,
und schickt ihn durch dasselbe ``service.compose`` (NKWG §§ 36/37). Ein
Rückblick ist damit kein zweiter Rechenweg, sondern derselbe mit anderem
Eingang — der Unterschied steht in ``dataset: "archive"``.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from functools import lru_cache

from ..antworten import ElectionDistrictList, ElectionNight, ElectionTopEntry
from . import elections, reference, register
from .votemanager import Snapshot, parse

_log = logging.getLogger("ratslotse.web.wahlabend")


def verfuegbar(wahl: elections.Election) -> bool:
    """Lässt sich für diese Wahl eine ganze Seite zeigen?

    Dafür braucht es beides: die eingefrorenen Zahlen UND ihr eigenes
    Kandidatenregister. Von der Ratswahl 2021 gibt es nur die Zahlen — die
    Namen der Bewerber*innen hat nie jemand erfasst. Mit dem Register von
    heute gerechnet kämen 52 Sitze auf 16 Listen heraus statt 50 auf elf:
    Zahlen, die stimmen, unter Namen, die nicht dazugehören. Lieber keine
    Seite als diese.
    """
    return (wahl.archive_folder is not None and wahl.archive_folder.is_dir()
            and wahl.register_path is not None and wahl.register_path.is_file())


def _eingefroren(slug: str):
    """Register, Referenz und Snapshot einer eingefrorenen Wahl — oder
    ``None``. Beide Wege in den Rückblick (``night`` und ``districts``)
    brauchen dieselben drei Stücke."""
    wahl = elections.get(slug)
    if wahl is None or not verfuegbar(wahl) or wahl.archive_folder is None:
        return None
    ordner = wahl.archive_folder
    praefix = reference.meta_path(ordner).stem
    lies = lambda name: (ordner / f"{praefix}-{name}.csv").read_text(encoding="utf-8-sig")  # noqa: E731
    schnapp = Snapshot(
        city=parse(lies("stadt")), areas=parse(lies("wahlbereiche")),
        districts=parse(lies("wahlbezirke")),
        fetched_at=datetime.now(timezone.utc), last_modified=None, ok=True, error=None,
    )
    # Das Register DIESER Wahl — `verfuegbar` hat schon dafür gesorgt, dass es
    # eines gibt.
    assert wahl.register_path is not None
    reg = register.load(wahl.register_path)
    ref = reference.load(wahl.reference_folder) if wahl.reference_folder else None
    if ref is None:
        # Ohne Vorwahl kein Vergleich — `compose` braucht trotzdem eine
        # Referenz, also die eigene: Der Abstand zu sich selbst ist null,
        # und `previous_label` ist bei so einer Wahl ohnehin leer.
        ref = reference.load(ordner)
    return reg, ref, schnapp


@lru_cache(maxsize=8)
def districts(slug: str) -> ElectionDistrictList | None:
    """Die Wahlbezirke einer gelaufenen Wahl — aus dem Repo, ohne Netz."""
    try:
        from . import service

        teile = _eingefroren(slug)
        if teile is None:
            return None
        reg, _, schnapp = teile
        return service.districts(reg, schnapp, "archive")
    except Exception:
        _log.exception("Wahlabend: Wahlbezirke für „%s“ nicht lesbar", slug)
        return None


@lru_cache(maxsize=8)
def night(slug: str) -> ElectionNight | None:
    """Der Stand am Ende des Wahlabends — aus dem Repo, ohne Netz.

    ``None``, wenn der Ordner fehlt oder nicht lesbar ist; der Aufrufer
    antwortet dann 404 statt eines halben Bildes.
    """
    wahl = elections.get(slug)
    if wahl is None or not verfuegbar(wahl) or wahl.archive_folder is None:
        return None
    try:
        from . import service

        ordner = wahl.archive_folder
        praefix = reference.meta_path(ordner).stem
        lies = lambda name: (ordner / f"{praefix}-{name}.csv").read_text(encoding="utf-8-sig")  # noqa: E731
        schnapp = Snapshot(
            city=parse(lies("stadt")), areas=parse(lies("wahlbereiche")),
            districts=parse(lies("wahlbezirke")),
            fetched_at=datetime.now(timezone.utc), last_modified=None, ok=True, error=None,
        )
        # Das Register DIESER Wahl — `verfuegbar` hat schon dafür gesorgt,
        # dass es eines gibt.
        assert wahl.register_path is not None
        reg = register.load(wahl.register_path)
        ref = reference.load(wahl.reference_folder) if wahl.reference_folder else None
        if ref is None:
            # Ohne Vorwahl kein Vergleich — `compose` braucht trotzdem eine
            # Referenz, also die eigene: Der Abstand zu sich selbst ist null,
            # und `previous_label` ist bei so einer Wahl ohnehin leer.
            ref = reference.load(ordner)
        bild = service.compose(reg, ref, schnapp, "archive", margins=False, projection=False)
        return bild
    except Exception:
        _log.exception("Wahlabend: Rückblick für „%s“ nicht lesbar", slug)
        return None


def summary(wahl: elections.Election) -> str | None:
    """Das Ergebnis in einem Satz — für die Übersicht unter ``/wahlen``.

    Bewusst aus der **Meta-Datei** und nicht aus ``night()``: Für eine Liste
    aus vier Zeilen die ganze Sitzzuteilung dreimal nachzurechnen wäre
    Verschwendung, und die Meta-Datei trägt die Sitzverteilung ohnehin schon
    (``scripts/wahl_einfrieren.py`` prüft sie beim Einfrieren gegen den
    Votemanager).
    """
    # Für die EINE Zeile reicht der Ordner; ein Register braucht sie nicht.
    if wahl.archive_folder is None or not wahl.archive_folder.is_dir():
        return None
    try:
        if wahl.kind == "council":
            meta = json.loads(reference.meta_path(wahl.archive_folder).read_text(encoding="utf-8"))
            nach_label: dict[str, int] = {}
            for m in meta["sitzverteilung"]:
                nach_label[m["party"]] = nach_label.get(m["party"], 0) + 1
            spitze = sorted(nach_label.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
            teile = [f"{label} {n}" for label, n in spitze]
            return ", ".join(teile) + f" — {meta['sitze_gesamt']} Sitze"
        return _mayor_summary(wahl)
    except Exception:
        _log.exception("Wahlabend: Kurzfassung für „%s“ nicht lesbar", wahl.slug)
        return None


#: Neutraler Punkt für Listen ohne Farbe (Designsprache: „Gruppen: neutraler Dot").
NEUTRAL = ("#6b7a8c", "#a3b1c2")


def top(wahl: elections.Election, n: int = 5) -> list[ElectionTopEntry]:
    """Die vorderen Listen mit Sitzen und Farbe — die Punktzeile der Übersicht.

    Aus derselben Meta-Datei wie ``summary``; die Farbe kommt über den Slug aus
    dem Register (``parteien-meta.json``). Fehlt einer Liste der Slug (eine
    Liste von 2021, die es 2026 nicht mehr gibt), bleibt ihr Punkt neutral —
    das ist besser als eine geratene Farbe.
    """
    if wahl.archive_folder is None or not wahl.archive_folder.is_dir():
        return []
    try:
        if wahl.kind != "council":
            return _mayor_top(wahl, n)
        meta = json.loads(reference.meta_path(wahl.archive_folder).read_text(encoding="utf-8"))
        slug_by_label = {p["label"]: p.get("slug") for p in meta["parteien"]}
        sitze: dict[str, int] = {}
        for m in meta["sitzverteilung"]:
            sitze[m["party"]] = sitze.get(m["party"], 0) + 1
        farben = _farben(wahl)
        zeilen: list[ElectionTopEntry] = []
        for label, anzahl in sorted(sitze.items(), key=lambda kv: (-kv[1], kv[0]))[:n]:
            hell, dunkel = farben.get(slug_by_label.get(label) or "", NEUTRAL)
            zeilen.append(ElectionTopEntry(label=label, seats=anzahl, pct=None, color=hell, color_dark=dunkel))
        return zeilen
    except Exception:
        _log.exception("Wahlabend: Punktzeile für „%s“ nicht lesbar", wahl.slug)
        return []


def _farben(wahl: elections.Election) -> dict[str, tuple[str, str]]:
    """Slug -> (hell, dunkel) aus dem Register der Wahl — oder dem aktiven,
    wenn sie keines hat: Die Farbe einer Partei hängt nicht am Jahr."""
    try:
        reg = register.load(wahl.register_path) if wahl.register_path else register.load()
        return {p.slug: (p.color, p.color_dark) for p in reg.parties}
    except Exception:
        return {}


def _mayor_top(wahl: elections.Election, n: int) -> list[ElectionTopEntry]:
    from . import mayor

    datei = wahl.archive_folder / "praesentation-ob.json" if wahl.archive_folder else None
    if datei is None or not datei.is_file():
        return []
    stand = mayor.parse(json.loads(datei.read_text(encoding="utf-8")), mayor.candidates(wahl))
    if stand is None:
        return []
    beste = sorted(stand.candidates, key=lambda c: -(c.votes or 0))[:n]
    return [ElectionTopEntry(label=c.name, seats=None, pct=c.share_pct,
                             color=c.color or NEUTRAL[0], color_dark=c.color_dark or NEUTRAL[1]) for c in beste]


def _mayor_summary(wahl: elections.Election) -> str | None:
    """„Ulf Prange 33,2 % · Stichwahl" — aus der eingefrorenen Darstellung."""
    from . import mayor

    if wahl.archive_folder is None:
        return None
    datei = wahl.archive_folder / "praesentation-ob.json"
    if not datei.is_file():
        return None
    stand = mayor.parse(json.loads(datei.read_text(encoding="utf-8")), mayor.candidates(wahl))
    if stand is None or not stand.candidates:
        return None
    beste = max(stand.candidates, key=lambda c: c.votes or 0)
    text = f"{beste.name} {(beste.share_pct or 0):.1f} %".replace(".", ",")
    return f"{text} · Stichwahl" if stand.runoff else text


def reset() -> None:
    night.cache_clear()
    districts.cache_clear()
