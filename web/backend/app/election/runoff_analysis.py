"""Die Stichwahl im Rückblick — und im Vergleich zum ersten Wahlgang.

Tims Auftrag nach dem 27.09.2026: „genauso eine detaillierte Analyse wie für
die Stadtratswahl, auch mit Vergleich zur ersten OB-Wahl". Reine Funktionen
über die beiden EINGEFRORENEN Wahlgänge (``wahl_einfrieren.py --ob``) — kein
Netz, keine Schätzung, nur Arithmetik auf den Zahlen der Stadt.

**Was hier bewusst NICHT steht: eine Wählerwanderung.** „Wie viele
Boldt-Wählende gingen zu Rohr?" lässt sich aus 133 Bezirken nicht
belastbar rechnen. Gemessen an der Stichwahl 2026: Eine Regression der
Stichwahl-Stimmen auf die Stimmen aller Kandidaturen des ersten Wahlgangs
lieferte Übergangsraten von −0,52 (Butzin) bis +1,11 — negative Menschen,
bei R² 0,87. Die Anteile der Ausgeschiedenen hängen zu eng zusammen, und
ein Drittel der Wählenden blieb zu Hause, ohne dass man weiß, wer. Was
bleibt, sind Aussagen über ORTE, nicht über Personen: wo jemand zulegte,
und wie das mit dem ersten Wahlgang dort zusammenhängt.

**Urne und Brief getrennt.** In der Stichwahl kamen 39 % der Stimmen per
Brief, im ersten Wahlgang 32 %. Wer beides zusammenwirft, misst die
Verschiebung zwischen den Töpfen mit und hält sie für einen Meinungswandel.

**Wahlbeteiligung je Wahlbereich:** Wählende ALLER Bezirke des Bereichs
(Urne und Brief) durch die Wahlberechtigten seiner Urnenbezirke. Die
Briefwahlbezirke führen keine eigenen Wahlberechtigten — wer per Brief
wählt, steht im Verzeichnis seines Urnenbezirks. Stadtweit ergibt das genau
die Zahl der Stadt (63,46 % und 44,42 %).

**Alle Anteile sind die der beiden** (Anteil an den Stimmen für Gewinner
und Zweiten), auch im ersten Wahlgang — sonst wäre jeder Vergleich einer
zwischen 30 % von neun und 52 % von zwei. Der Schwung ist die Veränderung
des Gewinner-Anteils in Prozentpunkten.
"""
from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from . import elections, mayor, mayor_districts, runoff_model
from .mayor_districts import MayorDistrict

#: Wahlbereiche in der Schreibweise der Stadt.
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI"}
#: Sortierungen der Bezirks-Rangliste.
SORTS = ("share", "swing", "turnout", "number")
#: Töpfe für den Filter der Rangliste.
POTS = ("urn", "postal")


@dataclass(frozen=True)
class _Pair:
    """Ein Wahlbezirk in beiden Wahlgängen."""
    first: MayorDistrict
    runoff: MayorDistrict


def _pct(part: float, whole: float) -> float | None:
    return round(100 * part / whole, 2) if whole else None


def _share(d: MayorDistrict, slug: str, other: str) -> float | None:
    a, b = d.votes.get(slug), d.votes.get(other)
    if a is None or b is None or a + b == 0:
        return None
    return 100 * a / (a + b)


def _load(w: elections.Election, known: dict[str, str]) -> tuple[Any, tuple[MayorDistrict, ...]]:
    assert w.archive_folder is not None
    city = json.loads((w.archive_folder / "praesentation-ob.json").read_text(encoding="utf-8"))
    overview = json.loads((w.archive_folder / "praesentation-ob-wahlbezirke.json").read_text(encoding="utf-8"))
    return city, mayor_districts.parse_overview(overview, known)


def _total(pairs: list[_Pair], field: str, rnd: str) -> int:
    return sum(getattr(getattr(p, rnd), field) or 0 for p in pairs)


def _votes(pairs: list[_Pair], slug: str, rnd: str) -> int:
    return sum(getattr(p, rnd).votes.get(slug) or 0 for p in pairs)


def _block(pairs: list[_Pair], slugs: tuple[str, str]) -> dict[str, Any]:
    """Stimmen, Anteile der beiden und Wachstum für eine Menge von Bezirken."""
    a, b = slugs
    out: dict[str, Any] = {"districts": len(pairs), "growth": {}}
    for rnd in ("first", "runoff"):
        va, vb = _votes(pairs, a, rnd), _votes(pairs, b, rnd)
        out[f"votes_{rnd}"] = {a: va, b: vb}
        out[f"share_{rnd}_pct"] = {a: _pct(va, va + vb), b: _pct(vb, va + vb)}
    for s in slugs:
        before = out["votes_first"][s]
        out["growth"][s] = round(out["votes_runoff"][s] / before, 3) if before else None
    first, runoff = out["share_first_pct"][a], out["share_runoff_pct"][a]
    out["swing_pts"] = round(runoff - first, 2) if first is not None and runoff is not None else None
    out["voters_first"] = _total(pairs, "voters", "first")
    out["voters_runoff"] = _total(pairs, "voters", "runoff")
    return out


def _turnout(pairs: list[_Pair], rnd: str) -> float | None:
    """Wählende aller Bezirke durch Wahlberechtigte der Urnenbezirke (s. o.)."""
    eligible = sum(getattr(p, rnd).eligible or 0 for p in pairs if not p.first.postal)
    return _pct(_total(pairs, "voters", rnd), eligible) if eligible else None


def _correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    try:
        return round(statistics.correlation(xs, ys), 2)
    except statistics.StatisticsError:
        return None


def _leader(share: float | None, a: str, b: str) -> str | None:
    """Wer im Bezirk vorn lag — ``None`` bei Gleichstand oder ohne Zahlen."""
    if share is None or share == 50:
        return None
    return a if share > 50 else b


@lru_cache(maxsize=4)
def analyse(slug: str) -> dict[str, Any] | None:
    """Die ganze Auswertung einer eingefrorenen Stichwahl — ``None``, wenn es
    sie (noch) nicht gibt. Die Bezirke kommen ungefiltert und nach Nummer;
    Sortieren und Filtern macht ``districts``."""
    w = elections.get(slug)
    if w is None or not w.first_round or w.archive_folder is None:
        return None
    first_election = elections.get(w.first_round)
    if first_election is None or first_election.archive_folder is None:
        return None
    for folder in (w.archive_folder, first_election.archive_folder):
        if not (folder / "praesentation-ob-wahlbezirke.json").is_file():
            return None

    runoff_candidates = mayor.candidates(w)
    known = {c.slug: c.name for c in runoff_candidates}
    city_runoff_raw, runoff_districts = _load(w, known)
    city_first_raw, first_districts = _load(first_election, known)
    city_runoff = mayor.parse(city_runoff_raw, runoff_candidates)
    city_first = mayor.parse(city_first_raw, mayor.candidates(first_election))
    if city_runoff is None or city_first is None or city_runoff.phase != "complete":
        return None

    # Der Gewinner zuerst: Alle Anteile und Schwünge sind aus seiner Sicht.
    by_votes = sorted(city_runoff.candidates, key=lambda c: -(c.votes or 0))
    if len(by_votes) != 2:
        return None
    slugs = (by_votes[0].slug, by_votes[1].slug)
    a, b = slugs

    first_by_number = {d.number: d for d in first_districts}
    pairs = [_Pair(first_by_number[d.number], d) for d in runoff_districts
             if d.number in first_by_number and d.counted]
    if len(pairs) != len(runoff_districts):
        # Ein Bezirk ohne Gegenstück im ersten Wahlgang — dann stimmt kein
        # Vergleich mehr in sich. Lieber keine Analyse als eine schiefe.
        return None

    first_by_slug = {c.slug: c for c in city_first.candidates}
    candidates = []
    for c in by_votes:
        f = first_by_slug.get(c.slug)
        candidates.append({
            "slug": c.slug, "name": c.name, "party": c.party, "color": c.color, "color_dark": c.color_dark,
            "votes_first": f.votes if f else None, "share_first_pct": f.share_pct if f else None,
            "votes_runoff": c.votes, "share_runoff_pct": c.share_pct,
        })
    eliminated = [{"slug": c.slug, "name": c.name, "party": c.party, "votes": c.votes or 0,
                   "share_pct": c.share_pct}
                  for c in sorted(city_first.candidates, key=lambda c: -(c.votes or 0)) if c.slug not in slugs]

    urn_pairs = [p for p in pairs if not p.first.postal]
    city = {
        **_block(pairs, slugs),
        "turnout_first_pct": _turnout(pairs, "first"), "turnout_runoff_pct": _turnout(pairs, "runoff"),
        "valid_first": city_first.valid_votes, "valid_runoff": city_runoff.valid_votes,
        "eligible_first": _total(urn_pairs, "eligible", "first"),
        "eligible_runoff": _total(urn_pairs, "eligible", "runoff"),
    }

    pots = []
    for key, label, postal in (("urn", "Urne", False), ("postal", "Briefwahl", True)):
        pots.append({"key": key, "label": label, **_block([p for p in pairs if p.first.postal == postal], slugs)})

    areas = []
    for number in sorted({p.first.area for p in pairs}):
        part = [p for p in pairs if p.first.area == number]
        areas.append({"number": number, "label": f"Wahlbereich {ROMAN.get(number, str(number))}",
                      **_block(part, slugs),
                      "turnout_first_pct": _turnout(part, "first"), "turnout_runoff_pct": _turnout(part, "runoff")})

    rows = []
    for p in pairs:
        s1, s2 = _share(p.first, a, b), _share(p.runoff, a, b)
        t1 = None if p.first.postal else _pct(p.first.voters or 0, p.first.eligible or 0)
        t2 = None if p.first.postal else _pct(p.runoff.voters or 0, p.runoff.eligible or 0)
        leader_first, leader_runoff = _leader(s1, a, b), _leader(s2, a, b)
        rows.append({
            "number": p.runoff.number, "name": p.runoff.name, "area": p.runoff.area, "postal": p.runoff.postal,
            "votes_first": {s: p.first.votes.get(s) for s in slugs},
            "votes_runoff": {s: p.runoff.votes.get(s) for s in slugs},
            "share_first_pct": round(s1, 2) if s1 is not None else None,
            "share_runoff_pct": round(s2, 2) if s2 is not None else None,
            "swing_pts": round(s2 - s1, 2) if s1 is not None and s2 is not None else None,
            "voters_first": p.first.voters, "voters_runoff": p.runoff.voters,
            "turnout_first_pct": t1, "turnout_runoff_pct": t2,
            "turnout_change_pts": round(t2 - t1, 2) if t1 is not None and t2 is not None else None,
            "leader_first": leader_first, "leader_runoff": leader_runoff,
            "flipped": leader_first is not None and leader_runoff is not None and leader_first != leader_runoff,
        })

    # Aufholen nach Fünfteln: die URNENbezirke nach dem Anteil des Gewinners
    # im ersten Wahlgang, schwächstes Fünftel zuerst. Nur Urne — die
    # Briefwahlbezirke haben keinen Ort, und ihr Schwung ist ein anderer.
    urn_rows = sorted((r for r in rows if not r["postal"] and r["share_first_pct"] is not None),
                      key=lambda r: r["share_first_pct"])
    quintiles = []
    for i in range(5):
        part_rows = urn_rows[math.floor(i * len(urn_rows) / 5): math.floor((i + 1) * len(urn_rows) / 5)]
        numbers = {r["number"] for r in part_rows}
        block = _block([p for p in pairs if p.runoff.number in numbers], slugs)
        quintiles.append({"rank": i + 1, "districts": len(part_rows),
                          "share_first_pct": block["share_first_pct"][a],
                          "share_runoff_pct": block["share_runoff_pct"][a],
                          "swing_pts": block["swing_pts"], "growth": block["growth"]})

    flipped = [r for r in rows if r["flipped"]]
    city_runoff_by_slug = {c.slug: c.share_pct for c in city_runoff.candidates}
    return {
        "election": {"slug": w.slug, "short_title": w.short_title, "date": w.date,
                     "first_round_slug": first_election.slug, "first_round_date": first_election.date},
        "result_status": _result_status(w),
        "winner": a,
        "candidates": candidates,
        "eliminated": eliminated,
        "city": city,
        "pots": pots,
        "areas": areas,
        "quintiles": quintiles,
        "catch_up_r": _correlation([r["share_first_pct"] for r in urn_rows], [r["swing_pts"] for r in urn_rows]),
        "lead_districts": {
            "first": {s: sum(1 for r in rows if r["leader_first"] == s) for s in slugs},
            "runoff": {s: sum(1 for r in rows if r["leader_runoff"] == s) for s in slugs},
        },
        "flipped": {s: sum(1 for r in flipped if r["leader_runoff"] == s) for s in slugs},
        "projection_review": _projection_review(w, a, city_runoff_by_slug.get(a)),
        "districts": sorted(rows, key=lambda r: r["number"]),
    }


def _projection_review(w: elections.Election, winner: str, final_share: float | None) -> dict[str, Any] | None:
    """Wie gut lag die Hochrechnung des Abends? Aus dem eingefrorenen Verlauf
    (``verlauf.json``, ein Stand je Meldung) gegen das Endergebnis.

    Am Abend wurde mehrfach gefragt, wie die Vorhersage funktioniert und ob
    man ihr trauen kann (Tim, 27.09.2026). Die Antwort ist eine Messung,
    keine Behauptung: je Stand die hochgerechnete Zahl des Gewinners neben
    der gezählten und der endgültigen. Das ist EIN Abend — eine Aussage über
    die Güte des Modells im Allgemeinen ist das nicht, und die Seite sagt es.
    """
    if w.archive_folder is None or final_share is None:
        return None
    try:
        history = json.loads((w.archive_folder / "verlauf.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(history, list) or not history:
        return None

    points = []
    for h in history:
        projected = h.get("projected_shares") or {}
        counted = h.get("shares") or {}
        projected_share = projected.get(winner)
        projected_leader = max(projected, key=lambda slug: projected[slug]) if projected else None
        points.append({
            "at": h.get("at"),
            "reports_received": int(h.get("reports_received") or 0),
            "counted_share_pct": counted.get(winner),
            "projected_share_pct": projected_share,
            "error_pts": round(projected_share - final_share, 2) if projected_share is not None else None,
            "chance_pct": h.get("chance_pct"),
            "projected_leader": projected_leader,
            "counted_leader": h.get("leader"),
        })

    def right_from(field: str) -> int | None:
        """Ab welcher Bezirkszahl lag dieses Feld bis zum Schluss auf dem Gewinner?"""
        since = None
        for pt in points:
            if pt[field] == winner:
                since = pt["reports_received"] if since is None else since
            else:
                since = None
        return since

    counted_leaders = [pt["counted_leader"] for pt in points if pt["counted_leader"]]
    after_min = [abs(pt["error_pts"]) for pt in points
                 if pt["error_pts"] is not None and pt["reports_received"] >= runoff_model.MIN_DISTRICTS]
    chances = [pt for pt in points if pt["chance_pct"] is not None]
    return {
        "final_share_pct": final_share,
        "min_districts": runoff_model.MIN_DISTRICTS,
        "chance_cap": runoff_model.CHANCE_CAP,
        "projection_right_from": right_from("projected_leader"),
        "counted_right_from": right_from("counted_leader"),
        "counted_lead_changes": sum(1 for x, y in zip(counted_leaders, counted_leaders[1:]) if x != y),
        "max_error_after_min_pts": round(max(after_min), 2) if after_min else None,
        "first_chance": chances[0] if chances else None,
        "chance_always_winner": all(pt["projected_leader"] == winner for pt in chances) if chances else None,
        "points": points,
    }


def _result_status(w: elections.Election) -> str:
    """„vorlaeufig" | „amtlich" — aus der ``quelle.json`` des Archivs."""
    if w.archive_folder is None:
        return "vorlaeufig"
    try:
        source = json.loads((w.archive_folder / "quelle.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "vorlaeufig"
    return "amtlich" if source.get("stand") == "amtlich" else "vorlaeufig"


def districts(rows: list[dict[str, Any]], sort: str = "share", area: int | None = None,
              pot: str | None = None) -> list[dict[str, Any]]:
    """Die Rangliste: gefiltert und sortiert, mit Rang.

    ``share`` und ``swing`` absteigend (der Gewinner zuerst dort, wo er am
    stärksten ist bzw. am meisten zulegte); ``turnout`` nach dem RÜCKGANG
    der Beteiligung, der stärkste zuerst — Briefwahlbezirke haben keine
    Beteiligung und stehen am Ende; ``number`` aufsteigend."""
    selected = [r for r in rows
                if (area is None or r["area"] == area)
                and (pot is None or r["postal"] == (pot == "postal"))]
    missing = float("inf")

    def descending(field: str):
        return lambda r: (-r[field] if r[field] is not None else missing, r["number"])

    if sort == "swing":
        selected.sort(key=descending("swing_pts"))
    elif sort == "turnout":
        selected.sort(key=lambda r: (r["turnout_change_pts"] if r["turnout_change_pts"] is not None else missing,
                                     r["number"]))
    elif sort == "number":
        selected.sort(key=lambda r: r["number"])
    else:
        selected.sort(key=descending("share_runoff_pct"))
    return [{**r, "rank": i} for i, r in enumerate(selected, start=1)]


def reset() -> None:
    analyse.cache_clear()
