"""Die Punkte-Formel des Tippspiels — reine Funktionen, EIN Rechenweg für
Handy und Beamer (docs/plan-tippspiel-ratswahl.md, Anhang A).

Aus dem Design-Artboard (Claude-Design ``2e1e6508…``, Turn 1a) übernommen,
nicht aus der ersten Fassung des Plans: 5/3/1/0 je Liste, 6/3/1/0 je
OB-Kandidatur — flacher als „10/7/4/1/0", damit die sechs kleinen Listen
(Piraten, PGM, Die PARTEI, Echt Oldenburg, DAVA, M. Stille) nicht nur
Trostpunkte abwerfen.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Höchstwerte — 16 Listen × 5, 9 OB-Kandidaturen × 6.
MAX_SEAT_POINTS = 16 * 5
MAX_MAYOR_POINTS = 9 * 6
MAX_TOTAL_POINTS = MAX_SEAT_POINTS + MAX_MAYOR_POINTS


def seat_points(tip: int, actual: int | None) -> int:
    """5 Punkte exakt, 3 bei ±1 Sitz, 1 bei ±2 Sitzen, sonst 0.

    ``actual is None`` (noch keine Zahl für diese Liste) ergibt 0 — ein Tipp
    kann nicht „richtig" sein, solange es nichts zu vergleichen gibt.

    **0 getippt und 0 erhalten IST exakt.** Ohne diese Regel wären die sechs
    kleinen Listen (Piraten, PGM, Die PARTEI, Echt Oldenburg, DAVA, M. Stille)
    wertlos, obwohl ihr Tipp eine genauso echte Entscheidung ist wie jeder
    andere — „diese Liste zieht nicht ein" kann falsch liegen.
    """
    if actual is None:
        return 0
    diff = abs(tip - actual)
    if diff == 0:
        return 5
    if diff == 1:
        return 3
    if diff == 2:
        return 1
    return 0


def mayor_points(tip_pct: float, actual_pct: float | None) -> int:
    """6 Punkte bei höchstens 0,5, 3 bei höchstens 1,5, 1 bei höchstens 3,0
    Prozentpunkten Abstand, sonst 0. Die Grenze selbst zählt zur besseren
    Stufe: genau 1,5 Punkte Abstand gibt noch 3, nicht 1."""
    if actual_pct is None:
        return 0
    diff = abs(tip_pct - actual_pct)
    if diff <= 0.5:
        return 6
    if diff <= 1.5:
        return 3
    if diff <= 3.0:
        return 1
    return 0


@dataclass(frozen=True)
class Score:
    total: int
    seat_points: int
    mayor_points: int
    exact_lists: int
    #: Summe der absoluten Sitz-Abweichungen — ``None``, solange KEINE der
    #: getippten Listen schon einen amtlichen (oder eingetragenen) Wert hat.
    deviation: int | None


def score(tip_seats: dict[str, int], tip_mayor: dict[str, float] | None,
         actual_seats: dict[str, int | None], actual_mayor: dict[str, float | None]) -> Score:
    """Der volle Punktestand einer Person gegen den aktuellen Stand.

    ``actual_seats``/``actual_mayor`` dürfen Slugs enthalten, die im Tipp
    fehlen (und umgekehrt) — es zählt nur, was IM TIPP steht; eine Liste, die
    der Tipp nie erwähnt hätte (kann bei 16 Pflichtfeldern nicht vorkommen,
    ist aber defensiv trotzdem sicher). Ohne OB-Tipp (``tip_mayor`` leer oder
    ``None``) sind die Bonuspunkte 0 — kein Abzug, die OB-Wahl bleibt optional.
    """
    seat_pts = 0
    exact = 0
    deviations: list[int] = []
    for slug, tip in tip_seats.items():
        actual = actual_seats.get(slug)
        seat_pts += seat_points(tip, actual)
        if actual is not None:
            if tip == actual:
                exact += 1
            deviations.append(abs(tip - actual))
    mayor_pts = sum(mayor_points(tip, actual_mayor.get(slug)) for slug, tip in (tip_mayor or {}).items())
    return Score(
        total=seat_pts + mayor_pts, seat_points=seat_pts, mayor_points=mayor_pts,
        exact_lists=exact, deviation=sum(deviations) if deviations else None,
    )


@dataclass(frozen=True)
class Standing:
    """Eine sortierbare Zeile für ``order`` — ``id`` ist beliebig (z. B.
    ``player_id``), der Rest reicht für die Turnierregel."""
    id: int
    name: str
    updated_at: str
    #: Zählt der Tipp zur Rangliste, oder ist die Person außer Konkurrenz
    #: (Spätstarter, solange ``prediction_game.late_scored`` aus ist)?
    scored: bool
    score: Score


def order(rows: list[Standing]) -> list[Standing]:
    """Turnierregel: höhere Punktzahl vor niedrigerer; bei Gleichstand die
    kleinere Abweichungssumme, dann die frühere Abgabe (``updated_at``),
    dann der Name. Spätstarter (``scored is False``) stehen GESCHLOSSEN
    hinter allen gewerteten Zeilen, untereinander nach derselben Regel."""
    def schluessel(r: Standing) -> tuple:
        abweichung = r.score.deviation if r.score.deviation is not None else 10 ** 9
        return (0 if r.scored else 1, -r.score.total, abweichung, r.updated_at, r.name.casefold())

    return sorted(rows, key=schluessel)


def ranks(rows: list[Standing]) -> dict[int, int]:
    """``{id: rang}`` nach ``order`` — dicht (1, 2, 3, …), Spätstarter zählen
    in derselben fortlaufenden Nummerierung mit, stehen aber immer danach."""
    return {r.id: i for i, r in enumerate(order(rows), start=1)}
