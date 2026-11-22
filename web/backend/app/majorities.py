"""Der Mehrheitsrechner der Werkzeuge: Mit welchen Fraktionen reicht es?

Eingang ist die Besetzung aus ``council_committee_seats`` (abgerufen von
``council/committee_seats.py``), Ausgang die fertige Antwort für beide
Frontends: die Sitzblöcke je Fraktion oder Gruppe, die Mehrheitsschwelle, die
Auswahl der Nutzer*in („dabei“ / „ohne“) und jede Kombination, die mit dieser
Auswahl eine Mehrheit ergibt.

Die Rechnung steht hier und nicht im Browser, weil die iOS-App sie sonst ein
zweites Mal bräuchte — und zwei Fassungen derselben Mehrheitsregel liefen
auseinander, ohne dass es jemand merkt.

**Was als Mehrheit zählt.** Mehr als die Hälfte ALLER Stimmberechtigten des
Gremiums — im Rat 27 von 53. Das ist die Zahl, die auch bei voller Besetzung
trägt; fehlt jemand, reicht im Einzelfall weniger.

**Wie groß ein Gremium ist, sagt der Ratsbeschluss, nicht das Ratsinfo**
(``council/committee_rules.py``). Der Gegencheck vom 22.11.2026 fand fünf
Gremien, in denen das Ratsinfo nicht alle Stimmberechtigten führt oder einen
zu viel — mit der Folge einer falschen Schwelle (Betriebsausschuss
Gebäudewirtschaft: 7 von 13 statt 8 von 14). Wer für welche Fraktion sitzt,
kommt weiter aus dem Ratsinfo; die Zahl der Sitze der Ratsmitglieder und der
weiteren Stimmberechtigten aus dem Beschluss.

**Welche Kombinationen gezeigt werden.** Nur solche, aus denen kein frei
gewählter Partner wegfallen kann, ohne die Mehrheit zu verlieren („minimal“).
Wer mit „dabei“ gesetzt ist, bleibt immer drin, auch wenn er rechnerisch
entbehrlich wäre: Die Frage lautet dann „was fehlt MIR noch?“. Die Auswahl ist
neutral — „dabei“ und „ohne“ kann für jede Fraktion gleich gesetzt werden;
eine Wertung der Kombinationen gibt es nicht.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import combinations
from pathlib import Path
from typing import Literal

from council import committee_rules

from .antworten import (MajorityAdvisory, MajorityBlock, MajorityBody, MajorityBodyOption,
                        MajorityCalculator, MajorityCoalition, MajorityOverview,
                        MajorityPartner, MajoritySelection)

KOMMUNALWAHL = Path(__file__).resolve().parents[3] / "kommunalwahl"
RIS_GREMIUM = "https://ratsinfo.oldenburg.de/bi/kp0040.asp?__kgrnr={kgrnr}"
RIS_GREMIEN = "https://ratsinfo.oldenburg.de/bi/gr0040.asp"

BodyKind = Literal["council", "administrative", "committee"]
BlockKind = Literal["faction", "group", "single", "mayor", "external"]

RAT = "Rat"
VERWALTUNGSAUSSCHUSS = "Verwaltungsausschuss"

#: Die Block-Schlüssel, die keine Fraktion sind.
MAYOR = "ob"
EXTERNAL = "weitere"


@dataclass(frozen=True)
class Faction:
    key: str
    short: str
    label: str
    #: Schlüssel in ``kommunalwahl/parteien-meta.json`` für die Farben — oder
    #: ``None``, dann stehen sie hier.
    color_key: str | None = None
    color: str = "#7d8b99"
    color_dark: str = "#a3b1c2"
    #: Mitgliedsparteien einer Gruppe.
    parties: tuple[str, ...] = ()
    group: bool = False


#: Die Fraktionen und Gruppen des Rats, erkannt am Etikett des Ratsinfos
#: (von oben nach unten, die spezifischste zuerst). Eine unbekannte
#: Fraktion fällt nicht heraus: Sie bekommt ihr Etikett als Namen und einen
#: neutralen Punkt — der Rechner rechnet sie mit.
#:
#: „Zukunft Oldenburg“ ist eine Gruppe aus drei Einzelmandaten (NWZ,
#: 04.11.2026: Bürger Bündnis Oldenburg, Echt Oldenburg, Piratenpartei);
#: „OBM“ führt das Ratsinfo für Christoph Baak (Oldenburgs Bürgerliche Mitte),
#: der nach der Wahl aus der CDU-Fraktion ausgetreten ist.
_FACTIONS: tuple[tuple[tuple[str, ...], Faction], ...] = (
    (("grüne", "grünen"), Faction("gruene", "Grüne", "Bündnis 90/Die Grünen", "gruene")),
    (("bsw",), Faction("bsw", "BSW", "BSW", "bsw")),
    (("linke",), Faction("linke", "Linke", "Die Linke", "linke")),
    (("zukunft oldenburg",), Faction(
        "zukunft-oldenburg", "Zukunft OL", "Zukunft Oldenburg", None, "#0F7A6B", "#3FBFAA",
        ("Bürger Bündnis Oldenburg", "Echt Oldenburg", "Piratenpartei"), group=True)),
    (("obm", "bürgerliche mitte"), Faction(
        "obm", "OBM", "Oldenburgs Bürgerliche Mitte", None, "#5B6570", "#98A3AE")),
    (("spd",), Faction("spd", "SPD", "SPD", "spd")),
    (("cdu",), Faction("cdu", "CDU", "CDU", "cdu")),
    (("afd",), Faction("afd", "AfD", "AfD", "afd")),
    (("fdp",), Faction("fdp", "FDP", "FDP", "fdp")),
    (("volt",), Faction("volt", "Volt", "Volt", "volt")),
    (("piraten",), Faction("piraten", "Piraten", "Piratenpartei", "piraten")),
)

#: Die Oberbürgermeisterin / der Oberbürgermeister — in der Farbe, die die
#: Stichwahl-Karte für Jascha Rohr eingeführt hat (DESIGNSPRACHE § 2).
_MAYOR = Faction(MAYOR, "OB", "Oberbürgermeister", None, "#E8590C", "#FF8A3D")
#: Stimmberechtigte ohne Ratsmandat (Eltern, Lehrkräfte, Beschäftigte …).
_EXTERNAL = Faction(EXTERNAL, "Weitere", "Weitere Stimmberechtigte", None, "#8A9AAA", "#6B7B8C")


def slug(text: str) -> str:
    low = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        low = low.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", low).strip("-")


@lru_cache(maxsize=1)
def _meta_colors() -> dict[str, tuple[str, str]]:
    try:
        meta = json.loads((KOMMUNALWAHL / "parteien-meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: (v["farbe"], v["farbe_dunkel"]) for k, v in meta.items()
            if isinstance(v, dict) and "farbe" in v and "farbe_dunkel" in v}


def faction_for(label: str | None) -> Faction:
    """Das Etikett des Ratsinfos → die Fraktion (bekannt oder neutral)."""
    low = (label or "").lower()
    for needles, f in _FACTIONS:
        if any(n in low for n in needles):
            return f
    clean = label or "ohne Fraktion"
    return Faction(slug(clean) or "ohne", clean, clean)


def _colors(f: Faction) -> tuple[str, str]:
    if f.color_key and f.color_key in _meta_colors():
        return _meta_colors()[f.color_key]
    return f.color, f.color_dark


@dataclass
class _Block:
    faction: Faction
    seats: int = 0
    members: list[str] = field(default_factory=list)
    detail: dict[str, int] = field(default_factory=dict)


@dataclass
class _Body:
    name: str
    kgrnr: int | None
    rows: list[dict]

    @property
    def key(self) -> str:
        return slug(self.name)

    @property
    def listed(self) -> int:
        """Stimmberechtigte, wie das Ratsinfo sie führt — nur als Filter;
        gerechnet wird mit :func:`_resolve`."""
        return sum(1 for r in self.rows if r["voting"])

    @property
    def kind(self) -> BodyKind:
        if self.name == RAT:
            return "council"
        if self.name == VERWALTUNGSAUSSCHUSS:
            return "administrative"
        return "committee"


def _bodies(seats: list[dict]) -> list[_Body]:
    by_name: dict[str, _Body] = {}
    for r in seats:
        b = by_name.setdefault(r["committee"], _Body(r["committee"], r.get("kgrnr"), []))
        b.rows.append(r)
    order = {RAT: 0, VERWALTUNGSAUSSCHUSS: 1}
    return sorted((b for b in by_name.values() if b.listed),
                  key=lambda b: (order.get(b.name, 2), b.name.lower()))


def majority(votes: int) -> int:
    """Mehr als die Hälfte — bei 53 Stimmen 27, bei 11 sechs, bei 16 neun."""
    return votes // 2 + 1


def _short(name: str) -> str:
    """„Ausschuss für Stadtplanung und Bauen“ → „Stadtplanung und Bauen“."""
    return name.removeprefix("Ausschuss für ")


def _is_mayor(row: dict) -> bool:
    """Die Stimme des Oberbürgermeisters: im Rat mit eigener Rolle, im
    Verwaltungsausschuss als Vorsitz ohne Fraktion."""
    if (row.get("role") or "").lower().startswith("oberbürgermeister"):
        return True
    return row.get("faction") is None and row["name"].lower().startswith("oberbürgermeister")


def _blocks(body: _Body) -> list[_Block]:
    """Die Blöcke, wie das Ratsinfo sie führt — noch unsortiert und ungeprüft."""
    blocks: dict[str, _Block] = {}
    for r in body.rows:
        if not r["voting"]:
            continue
        if r["kpenr"] is None:
            f = _EXTERNAL
        elif _is_mayor(r):
            f = _MAYOR
        else:
            f = faction_for(r["faction"])
        b = blocks.setdefault(f.key, _Block(f))
        b.seats += 1
        if f.key == EXTERNAL:
            # Ohne Ratsmandat steht die Funktion im Namensfeld (s. committee_seats).
            b.detail[r["name"]] = b.detail.get(r["name"], 0) + 1
        else:
            b.members.append(r["name"])
    return list(blocks.values())


def _kind(f: Faction, council_seats: dict[str, int]) -> BlockKind:
    if f.key == MAYOR:
        return "mayor"
    if f.key == EXTERNAL:
        return "external"
    if f.group:
        return "group"
    return "faction" if council_seats.get(f.key, 0) >= 2 else "single"


def _order(blocks: list[_Block], council_seats: dict[str, int]) -> list[_Block]:
    tail = {MAYOR: 1, EXTERNAL: 2}
    return sorted(blocks, key=lambda b: (
        tail.get(b.faction.key, 0), -b.seats, -council_seats.get(b.faction.key, 0),
        b.faction.short.lower()))


@dataclass
class _Resolved:
    """Ein Gremium, wie gerechnet wird: Blöcke, Stimmenzahl, Hinweise."""
    blocks: list[_Block]
    votes: int
    notes: list[str]

    @property
    def selectable(self) -> int:
        """Stimmen aller Blöcke, die sich wählen lassen (ohne die Weiteren)."""
        return sum(b.seats for b in self.blocks if b.faction.key != EXTERNAL)


def _parts(items: list[tuple[str, int]]) -> str:
    return ", ".join(f"{n} {label}" if n > 1 else label for label, n in items)


def _resolve(body: _Body, council_seats: dict[str, int]) -> _Resolved:
    """Ratsinfo und Ratsbeschluss zusammenführen (s. Modul-Docstring).

    - Führt das Ratsinfo MEHR Ratsmitglieder als beschlossen, steht dort ein
      Eintrag zu viel (gemessen: ein Mitglied der alten Wahlperiode). Dann
      gilt je Fraktion höchstens, was ihr nach Sainte-Laguë/Schepers zusteht.
      Nur in diesem Fall wird korrigiert — bei gleicher oder kleinerer Zahl
      bleibt das Ratsinfo, denn Fraktionen können Sitze auch tauschen.
    - Die weiteren Stimmberechtigten kommen ganz aus dem Beschluss: Das
      Ratsinfo führt sie nur zum Teil.
    """
    blocks = _blocks(body)
    rule = committee_rules.composition_for(body.name)
    extra: list[str] = []
    corrected = False
    if rule is not None:
        council = [b for b in blocks if b.faction.key not in (EXTERNAL, MAYOR)]
        listed = sum(b.seats for b in council)
        if listed > rule.council_seats and body.kind != "council":
            strengths = {k: n for k, n in council_seats.items() if n >= 2}
            sure, tied, open_ = committee_rules.sainte_lague(strengths, rule.council_seats)
            for b in council:
                allowed = sure.get(b.faction.key, 0) + (1 if open_ and b.faction.key in tied else 0)
                if b.seats > allowed:
                    extra.append(
                        f"{b.faction.short}: Das Ratsinformationssystem führt {b.seats} Mitglieder, "
                        f"der Rat hat am {committee_rules.DECIDED} {allowed} "
                        f"{'Sitz' if allowed == 1 else 'Sitze'} festgestellt. Gerechnet wird mit "
                        f"{allowed}.")
                    b.seats = allowed
                    corrected = True
            if sum(b.seats for b in council) > rule.council_seats:
                extra.append(
                    f"Das Ratsinformationssystem führt hier {listed} stimmberechtigte Ratsmitglieder, "
                    f"beschlossen sind {rule.council_seats}.")
            blocks = [b for b in blocks if b.seats > 0]
        elif listed < rule.council_seats:
            extra.append(f"Von den {rule.council_seats} Sitzen der Ratsmitglieder führt das "
                         f"Ratsinformationssystem {listed} als besetzt.")
        blocks = [b for b in blocks if b.faction.key != EXTERNAL]
        if rule.others:
            blocks.append(_Block(_EXTERNAL, seats=sum(n for _, n in rule.others),
                                 detail=dict(rule.others)))
    blocks = _order(blocks, council_seats)
    votes = sum(b.seats for b in blocks)

    notes: list[str] = []
    has_mayor = any(b.faction.key == MAYOR for b in blocks)
    if body.kind == "council" and has_mayor:
        notes.append("Der Oberbürgermeister ist Mitglied des Rats und stimmt mit.")
    if body.kind == "administrative" and has_mayor:
        notes.append("Der Oberbürgermeister führt den Vorsitz im Verwaltungsausschuss und "
                     "stimmt mit.")
    ext = next((b for b in blocks if b.faction.key == EXTERNAL), None)
    need = majority(votes)
    if ext:
        teile = _parts(list(ext.detail.items()) if rule is not None
                       else sorted(ext.detail.items(), key=lambda x: (-x[1], x[0])))
        selectable = votes - ext.seats
        if len(ext.detail) == 1:
            satz = (f"{ext.seats} der {votes} Stimmen haben {next(iter(ext.detail))} "
                    f"(ohne Ratsmandat).")
        else:
            satz = f"{ext.seats} der {votes} Stimmen haben Mitglieder ohne Ratsmandat: {teile}."
        if selectable >= need:
            satz += (f" Sie zählen zur Mehrheitsschwelle; die Kombinationen kommen ohne sie "
                     f"auf {need} Stimmen.")
        else:
            satz += (f" Die Ratsmitglieder haben zusammen {selectable} Stimmen — für eine "
                     f"Mehrheit ({need}) reicht das allein nicht.")
        notes.append(satz)
    if rule is not None and rule.remark:
        notes.append(rule.remark)
    if rule is not None and rule.conditional:
        mehr = votes + sum(n for _, n in rule.conditional)
        notes.append(f"{rule.conditional_when} stimmen zusätzlich "
                     f"{' und '.join(label for label, _ in rule.conditional)} mit: dann "
                     f"{mehr} Stimmen, Mehrheit ab {majority(mehr)}.")
    notes.extend(extra)
    if rule is not None and rule.source and (rule.others or rule.conditional or corrected):
        notes.append(f"Zusammensetzung laut Ratsbeschluss vom {committee_rules.DECIDED} "
                     f"({rule.source}).")
    return _Resolved(blocks, votes, notes)


def _coalitions(blocks: list[_Block], need: int, include: set[str],
                exclude: set[str]) -> list[tuple[tuple[str, ...], int]]:
    # Stimmberechtigte ohne Ratsmandat sind kein Block, der sich verabredet —
    # sie zählen zur Schwelle, aber nie als Partner.
    seats = {b.faction.key: b.seats for b in blocks if b.faction.key != EXTERNAL}
    fixed = [k for k in seats if k in include]
    free = [k for k in seats if k not in include and k not in exclude]
    base = sum(seats[k] for k in fixed)
    if base >= need:
        return [(tuple(fixed), base)]
    out: list[tuple[tuple[str, ...], int]] = []
    for n in range(1, len(free) + 1):
        for extra in combinations(free, n):
            total = base + sum(seats[k] for k in extra)
            if total < need:
                continue
            # Minimal: Kein frei gewählter Partner darf entbehrlich sein.
            if any(total - seats[k] >= need for k in extra):
                continue
            out.append((tuple(fixed) + extra, total))
    order = {k: i for i, k in enumerate(seats)}
    out = [(tuple(sorted(c, key=order.__getitem__)), s) for c, s in out]
    return sorted(out, key=lambda c: (len(c[0]), -c[1], [order[k] for k in c[0]]))


def _overview(bodies: list[_Body], resolved: dict[str, _Resolved], include: list[str],
              exclude: list[str]) -> list[MajorityOverview]:
    """Dieselbe Auswahl in jedem Gremium: Wie viele Stimmen hat sie dort, und
    reicht es? Beantwortet die Frage, mit der der Rechner bestellt wurde —
    „wo haben wir eine Mehrheit?“ — ohne sechzehnmal umzuschalten."""
    out: list[MajorityOverview] = []
    for b in bodies:
        r = resolved[b.key]
        keys = {x.faction.key for x in r.blocks if x.faction.key != EXTERNAL}
        excl = {k for k in exclude if k in keys}
        incl = {k for k in include if k not in excl}
        need = majority(r.votes)
        picked = sum(x.seats for x in r.blocks if x.faction.key in incl)
        max_seats = sum(x.seats for x in r.blocks if x.faction.key in keys and x.faction.key not in excl)
        out.append({"key": b.key, "short": _short(b.name), "kind": b.kind, "votes": r.votes,
                    "majority": need, "seats": picked, "has_majority": picked >= need,
                    "missing": max(0, need - picked), "possible": max_seats >= need,
                    "reachable": r.selectable >= need})
    return out


def calculate(seats: list[dict], body_key: str | None, include: list[str],
              exclude: list[str]) -> MajorityCalculator:
    bodies = _bodies(seats)
    as_of = max((r["fetched_at"] for r in seats if r.get("fetched_at")), default=None)
    body = next((b for b in bodies if b.key == body_key), bodies[0] if bodies else None)
    if body is None:
        return {"bodies": [], "body": None, "blocks": [], "advisory": [],
                "selection": {"include": [], "exclude": [], "seats": 0, "missing": 0,
                              "has_majority": False, "max_seats": 0, "possible": False},
                "coalitions": [], "partners": [], "overview": [], "as_of": as_of}

    rat = next((b for b in bodies if b.name == RAT), None)
    council_seats: dict[str, int] = {}
    for r in (rat.rows if rat else []):
        if r["voting"] and r["kpenr"] is not None and not _is_mayor(r):
            k = faction_for(r["faction"]).key
            council_seats[k] = council_seats.get(k, 0) + 1

    resolved = {b.key: _resolve(b, council_seats) for b in bodies}
    options: list[MajorityBodyOption] = [
        {"key": b.key, "name": b.name, "short": _short(b.name), "kind": b.kind,
         "votes": resolved[b.key].votes}
        for b in bodies]
    now = resolved[body.key]
    blocks, votes = now.blocks, now.votes
    keys = {b.faction.key for b in blocks if b.faction.key != EXTERNAL}
    excl = {k for k in exclude if k in keys}
    incl = {k for k in include if k in keys and k not in excl}
    need = majority(votes)

    out_blocks: list[MajorityBlock] = []
    for b in blocks:
        color, color_dark = _colors(b.faction)
        out_blocks.append({
            "key": b.faction.key, "short": b.faction.short, "label": b.faction.label,
            "kind": _kind(b.faction, council_seats), "color": color, "color_dark": color_dark,
            "seats": b.seats, "selectable": b.faction.key != EXTERNAL,
            "members": b.members, "parties": list(b.faction.parties),
            "functions": [{"label": k, "seats": n} for k, n in b.detail.items()],
        })

    advisory: list[MajorityAdvisory] = []
    for r in body.rows:
        if r["voting"]:
            continue
        f = faction_for(r["faction"]) if r["faction"] else None
        color, color_dark = _colors(f) if f else (_EXTERNAL.color, _EXTERNAL.color_dark)
        advisory.append({"name": r["name"], "role": r["role"] or "",
                         "key": f.key if f else None, "short": f.short if f else None,
                         "color": color, "color_dark": color_dark})

    picked = sum(b.seats for b in blocks if b.faction.key in incl)
    max_seats = sum(b.seats for b in blocks if b.faction.key in keys and b.faction.key not in excl)
    selection: MajoritySelection = {
        "include": [b.faction.key for b in blocks if b.faction.key in incl],
        "exclude": [b.faction.key for b in blocks if b.faction.key in excl],
        "seats": picked, "missing": max(0, need - picked), "has_majority": picked >= need,
        "max_seats": max_seats, "possible": max_seats >= need,
    }
    coalitions: list[MajorityCoalition] = [
        {"blocks": list(c), "seats": s, "surplus": s - need,
         "added": [k for k in c if k not in incl]}
        for c, s in (_coalitions(blocks, need, incl, excl) if max_seats >= need else [])]

    # Wer kommt für die Mehrheit in Frage? Jeder Block, der in mindestens einer
    # der Kombinationen zur Auswahl hinzukommt — also nie einer, der nur als
    # entbehrlicher Mitläufer dabei wäre. Nur mit einer Auswahl, der noch
    # Stimmen fehlen; ohne Auswahl wäre es schlicht jeder.
    partners: list[MajorityPartner] = []
    if incl and picked < need:
        count: dict[str, int] = {}
        for c in coalitions:
            for k in c["added"]:
                count[k] = count.get(k, 0) + 1
        partners = [
            {"key": b.faction.key, "seats": b.seats, "total": picked + b.seats,
             "completes": picked + b.seats >= need, "coalitions": count[b.faction.key]}
            for b in blocks if b.faction.key in count]
        # Wer allein reicht, zuerst; sonst bleibt die Reihenfolge der Blöcke.
        partners.sort(key=lambda p: not p["completes"])

    out_body: MajorityBody = {
        "key": body.key, "name": body.name, "short": _short(body.name), "kind": body.kind,
        "votes": votes, "majority": need, "notes": now.notes,
        "reachable": now.selectable >= need,
        "source_url": RIS_GREMIUM.format(kgrnr=body.kgrnr) if body.kgrnr else RIS_GREMIEN,
    }
    return {"bodies": options, "body": out_body, "blocks": out_blocks, "advisory": advisory,
            "selection": selection, "coalitions": coalitions, "partners": partners,
            "overview": _overview(bodies, resolved, selection["include"], selection["exclude"]),
            "as_of": as_of}
