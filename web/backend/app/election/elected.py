"""Der gewählte Rat: wer nach der Ratswahl ab dem 1. November im Rat sitzt.

Das Personenverzeichnis entsteht aus den Anwesenheitslisten der Protokolle
(``CouncilStore.list_members``). Wer neu gewählt ist, taucht dort erst nach
der ersten Sitzung auf, bei der Ratswahl 2026 also nach der konstituierenden
Sitzung am 02.11.2026, und auch das erst, wenn das Protokoll eingelesen ist.
Bis dahin hätte die Hälfte des neuen Rats keine Seite. Dieses Modul ist die
zweite Quelle: die Gewählten aus dem eingefrorenen Wahlergebnis.

**Gerechnet wird nicht neu.** Wer einen Sitz hat, steht in
``archive.night(...)["mandates"]`` — derselbe Weg (NKWG §§ 36/37), den der
Wahlabend und der Rückblick nehmen. Beruf und Jahrgang kommen aus dem
Kandidatenregister, Farben und Wahlbereiche aus demselben Bild.

**Vorläufig oder amtlich** steht in der Meta-Datei des Archivs
(``quelle.stand``); ``scripts/wahl_einfrieren.py --stand amtlich`` setzt es
nach der Sitzung des Wahlausschusses um.

**Was sich danach noch ändert**, steht in ``mandatswechsel.json`` im selben
Ordner, von Hand gepflegt: wer die Wahl ablehnt oder als Oberbürgermeister*in
ausscheidet, und wer für sie nachrückt. Das Nachrücken der Ersatzpersonen (NKWG) hängt
an der Art des Wahlvorschlags und an der Stimmenreihenfolge; das rechnen wir
nicht nach, sondern tragen ein, was die Stadt bekannt gibt. Der Name der
Nachfolge muss im Register derselben Liste stehen, sonst bricht das Laden ab.
Eine Seite mit einem Namen, der auf keinem Stimmzettel stand, wäre schlimmer
als ein fehlender Eintrag.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from ..antworten import ElectedCouncil, ElectedMember, ElectedVacancy
from . import archive, elections, reference, register

_log = logging.getLogger("ratslotse.web.wahlabend")

#: Datei der Mandatswechsel im Archivordner. Keine Jahreszahl im Namen, sonst
#: hielte ``reference.meta_path`` sie für eine zweite Meta-Datei.
CHANGES_FILE = "mandatswechsel.json"

#: Titel, die im Register vor dem Nachnamen stehen („Dr. Giesers, Benjamin").
_TITLE = re.compile(r"^((?:(?:Dr|Prof)\.(?:\s?[a-z]+\.)*\s+)+)")


def display_name(register_name: str) -> str:
    """„Dr. Giesers, Benjamin" → „Dr. Benjamin Giesers"."""
    last, _, first = register_name.partition(",")
    last, first = last.strip(), first.strip()
    m = _TITLE.match(last)
    title = m.group(1) if m else ""
    last = last[len(title):].strip()
    return " ".join(t for t in (title.strip(), first, last) if t)


def term_start(election_date: str) -> str:
    """Beginn der Wahlperiode: der 1. November des Wahljahres (§ 47 Abs. 2
    NKomVG)."""
    return f"{election_date[:4]}-11-01"


@dataclass(frozen=True)
class _Change:
    name: str
    list_slug: str
    reason: str
    successor: str | None


def _changes(folder: Path) -> list[_Change]:
    path = folder / CHANGES_FILE
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [_Change(c["name"], c["list"], c["reason"], c.get("successor"))
            for c in raw.get("changes", [])]


def _find(reg: register.Register, list_slug: str, name: str) -> tuple[int, register.Candidate] | None:
    party = reg.by_slug(list_slug)
    if party is None:
        return None
    for area, cands in party.areas.items():
        for c in cands:
            if c.name == name:
                return area, c
    return None


@lru_cache(maxsize=4)
def _load(slug: str) -> tuple[dict, list[dict], list[ElectedVacancy]] | None:
    """Kopf, Mitglieder (ohne Personen-Slug) und Wechsel einer Ratswahl."""
    wahl = elections.get(slug)
    if wahl is None or wahl.kind != "council" or wahl.archive_folder is None:
        return None
    night = archive.night(slug)
    if night is None or night["phase"] != "complete":
        return None
    assert wahl.register_path is not None  # `archive.night` hat es geprüft
    reg = register.load(wahl.register_path)
    meta = json.loads(reference.meta_path(wahl.archive_folder).read_text(encoding="utf-8"))
    parties = {p["slug"]: p for p in night["parties"]}
    areas = {a["number"]: a for a in night["areas"]}

    def entry(list_slug: str, area: int, cand: register.Candidate | None, name: str,
              votes: int | None, mandate: str) -> dict:
        p = parties[list_slug]
        a = areas[area]
        return {
            "name": display_name(name), "register_name": name,
            "list": list_slug, "list_short": p["short"], "color": p["color"], "color_dark": p["color_dark"],
            "area": area, "area_roman": a["roman"], "area_name": a["name"],
            "position": cand.position if cand else None, "votes": votes, "mandate": mandate,
            "occupation": cand.occupation if cand else None, "born": cand.born if cand else None,
        }

    members: list[dict] = []
    for m in night["mandates"]:
        name = m["name"]
        if name is None:
            # Ohne Personenstimmen gibt es keinen Namen — bei einem fertig
            # ausgezählten Ergebnis nicht zu erwarten, aber kein Grund, den
            # Rest wegzuwerfen.
            continue
        found = _find(reg, m["slug"], name)
        members.append(entry(m["slug"], m["area"], found[1] if found else None, name, m["votes"], m["kind"]))

    vacancies: list[ElectedVacancy] = []
    for ch in _changes(wahl.archive_folder):
        idx = next((i for i, e in enumerate(members)
                    if e["register_name"] == ch.name and e["list"] == ch.list_slug), None)
        if idx is None:
            raise ValueError(f"{CHANGES_FILE}: „{ch.name}“ ({ch.list_slug}) hat keinen Sitz")
        left = members.pop(idx)
        successor: str | None = None
        if ch.successor:
            found = _find(reg, ch.list_slug, ch.successor)
            if found is None:
                raise ValueError(f"{CHANGES_FILE}: „{ch.successor}“ steht nicht auf der Liste {ch.list_slug}")
            area, cand = found
            members.append(entry(ch.list_slug, area, cand, ch.successor, None, "successor"))
            successor = display_name(ch.successor)
        vacancies.append(ElectedVacancy(name=left["name"], list_short=left["list_short"],
                                        reason=ch.reason, successor=successor))

    # Stimmzettel-Reihenfolge der Listen, darin Wahlbereich und Listenplatz —
    # dieselbe Ordnung wie auf der Wahlabend-Seite.
    order = {p["slug"]: p["index"] for p in night["parties"]}
    members.sort(key=lambda e: (order[e["list"]], e["area"], e["position"] or 999))
    head = {
        "election": wahl.slug,
        "title": wahl.title,
        "date": wahl.date,
        "term_start": term_start(wahl.date),
        "seats": int(meta.get("sitze_gesamt") or reg.seats),
        "status": "amtlich" if meta.get("quelle", {}).get("stand") == "amtlich" else "vorlaeufig",
    }
    return head, members, vacancies


def split_name(register_name: str) -> tuple[str, str]:
    """„Dr. Giesers, Benjamin" → („Benjamin", „Giesers") — ohne Titel."""
    last, _, first = register_name.partition(",")
    last = last.strip()
    m = _TITLE.match(last)
    return first.strip(), last[len(m.group(1)):].strip() if m else last


def council(slug_of, history, known: dict[str, str], election: str | None = None) -> ElectedCouncil | None:
    """Der gewählte Rat der aktiven (oder genannten) Ratswahl.

    ``history`` ist ``CouncilStore.council_history``: Es findet die Person
    auch dann, wenn Protokolle und Ratsinformationssystem sie mit zweitem
    Vornamen führen („Ruth Regina Drügemöller"), und nennt ihre
    Wahlperioden im Rat. Wo es niemanden findet, bildet ``slug_of``
    (``CouncilStore.person_slug``) den Slug aus dem Namen auf dem
    Stimmzettel. ``known`` bildet die Slugs des Personenverzeichnisses auf
    ihre Art ab (``council`` | ``advisory``).
    """
    try:
        teile = _load(election or elections.active().slug)
    except Exception:
        _log.exception("Gewählter Rat: nicht lesbar")
        return None
    if teile is None:
        return None
    head, raw, vacancies = teile
    # Die Wahlperiode, die mit dieser Wahl endet: fünf Jahre vor der neuen.
    letzte = int(head["term_start"][:4]) - 5
    verlauf = history([split_name(e["register_name"]) for e in raw], head["term_start"])
    members: list[ElectedMember] = []
    for e, h in zip(raw, verlauf):
        slug = h["slug"] or slug_of(e["name"])
        terms = [int(t) for t in h["terms"]]
        status: Literal["new", "current", "former"] = (
            "current" if letzte in terms else "former" if terms else "new")
        members.append(ElectedMember(
            slug=slug, name=e["name"], list=e["list"], list_short=e["list_short"],
            color=e["color"], color_dark=e["color_dark"], area=e["area"],
            area_roman=e["area_roman"], area_name=e["area_name"], position=e["position"],
            votes=e["votes"], mandate=e["mandate"], occupation=e["occupation"], born=e["born"],
            has_profile=slug in known, council_status=status, council_terms=terms,
        ))
    return ElectedCouncil(
        election=head["election"], title=head["title"], date=head["date"],
        term_start=head["term_start"], seats=head["seats"], status=head["status"],
        members=members, vacancies=vacancies,
    )
