"""Die Hochrechnung der Stichwahl — je Wahlbezirk, mit ehrlicher Unsicherheit.

PR S2 aus ``docs/plan-stichwahl-spannung.md``. Reine Funktionen, kein Netz.

**Was das Modell annimmt.** Ein Wahlbezirk stimmt in der Stichwahl so ab wie
im ersten Wahlgang — verschoben um EINEN Schwung, den die schon gezählten
Bezirke verraten. Gemessen an der Stichwahl 2021 (Krogmann gegen Fuhrhop,
133 Bezirke): Zwischen den Bezirken streute der Anteil um 11 Punkte, nach
dem Schwung blieben 3. Das ist die Zusage, auf der die Hochrechnung steht.

**Warum zwei Schwünge.** 2021 drehte die Briefwahl in der Stichwahl um
6,5 Punkte, die Urne um 3,2. Wer beides zusammenwirft, liegt um gut drei
Punkte daneben — bei 52 : 48 der Unterschied zwischen richtig und falsch.
Urne und Brief bekommen deshalb je ihren eigenen Schwung; solange ein Topf
noch leer ist, leiht er sich den des anderen und trägt dafür einen
Unsicherheits-Aufschlag (``POT_SWING_SD``): In der Kalibrierung war das
Modell ohne ihn bei „Briefwahl zuerst" nach zehn Bezirken in 9 % der Fälle
sicher — und falsch.

**Was die Chance ist, und was nicht.** Φ(Vorsprung ÷ σ), mit σ aus den
Modellresten der gezählten Bezirke. Sie erscheint erst ab ``MIN_DISTRICTS``
gezählten Bezirken (mit fünf ist σ selbst Zufall), ist bei ``CHANCE_CAP``
gedeckelt und heißt auf der Seite „Modell", nie „Prognose". Sie ist an EINER
Stichwahl geprüft, die mit 54 : 46 nicht knapp war.

**Rechnerisch entschieden** ist keine Modellaussage: Der tatsächliche
Vorsprung übersteigt die Obergrenze dessen, was in den offenen Bezirken
noch kommen kann. Für Urnenbezirke sind das die Wahlberechtigten; für
Briefwahlbezirke, die keine führen (gemessen in S1), das
``POSTAL_GROWTH_CAP``-Fache ihrer gültigen Stimmen im ersten Wahlgang
(2021 wuchsen die Zwei-Kandidaten-Stimmen um 1,57).
"""
from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .mayor_districts import MayorDistrict

#: Unter so vielen gezählten Bezirken gibt es keine Chance-Zahl.
MIN_DISTRICTS = 15
#: Die Chance wird hier gedeckelt, bis die Arithmetik entschieden hat.
CHANCE_CAP = 99
#: Streuung (Anteil, 0…1) des Schwungs eines Topfes, dessen Bezirke noch
#: alle offen sind — 2021 lagen Urne und Brief 3,3 Punkte auseinander. Bis
#: 09/2026 stand hier 0,04; die Kalibrierung (s. ``SWING_SE_SCALE``) wollte
#: mehr Luft.
POT_SWING_SD = 0.06
#: Obergrenze der Stimmen eines offenen Briefwahlbezirks, relativ zu seinen
#: gültigen Stimmen im ersten Wahlgang.
POSTAL_GROWTH_CAP = 1.6
#: Untergrenze der Streuung (Anteil) um den Schwung, solange erst wenige
#: Bezirke eines Topfes gezählt sind — mit zweien wäre die gemessene
#: Streuung selbst Zufall. 2021 lag sie nach dem Schwung bei drei Punkten.
SWING_SD_FLOOR = 0.03
#: Aufschlag auf den Standardfehler des Schwungs: Bezirke melden nicht in
#: zufälliger Reihenfolge, sondern nach Ort und Größe gebündelt. 1,5 und
#: ``POT_SWING_SD`` 0,06 sind an 2021 gemessen, mit gleichmäßig verschobenen
#: Anteilen, damit das Rennen knapp wird (vier Reihenfolge-Arten, zehn
#: Endstände zwischen 48 und 51 %): „99 %" lag dann in 99,9 % der Fälle
#: richtig, „90–98 %" in 93 %. Mit 1,0 und 0,04 waren es 98,7 und 88.
#: Die Werte sind an EINER Stichwahl eingestellt — mehr gibt es nicht.
SWING_SE_SCALE = 1.5


@dataclass(frozen=True)
class RunoffProjection:
    #: Hochgerechneter Endstand je Slug in Prozent (Summe 100).
    shares: dict[str, float]
    #: Hochgerechnete Stimmen je Slug.
    projected_votes: dict[str, int]
    leader: str
    #: Hochgerechneter Vorsprung des Führenden in Stimmen.
    lead_votes: int
    #: Chance des Führenden in Prozent (ganze Zahl) — ``None`` unter
    #: ``MIN_DISTRICTS`` Bezirken oder wenn rechnerisch entschieden.
    chance_pct: int | None
    counted_ballot: int
    counted_postal: int
    open_ballot: int
    open_postal: int
    #: Der TATSÄCHLICHE Vorsprung übersteigt die Obergrenze der offenen Stimmen.
    decided: bool
    #: Wer nach den gezählten Stimmen tatsächlich vorn liegt.
    actual_leader: str
    actual_lead_votes: int
    open_votes_max: int
    #: Streuung des hochgerechneten Vorsprungs in Stimmen.
    sigma_votes: float
    caveats: tuple[str, ...]


def _share(a: int | None, b: int | None) -> float | None:
    if a is None or b is None or a + b <= 0:
        return None
    return a / (a + b)


def _swing(rows: list[tuple[float, float, int]]) -> float | None:
    """Gewichteter Schwung (Ist − Erwartung) über gezählte Bezirke:
    ``rows`` = (p_erster_wahlgang, q_stichwahl, n_stichwahl)."""
    gewicht = sum(n for _, _, n in rows)
    if gewicht <= 0:
        return None
    return sum((q - p) * n for p, q, n in rows) / gewicht


def project(current: Sequence[MayorDistrict], first_round: Sequence[MayorDistrict],
            slugs: tuple[str, str]) -> RunoffProjection | None:
    """Die Hochrechnung zu einem Stand. ``None``, solange kein Bezirk gemeldet
    hat oder der erste Wahlgang die Bezirke nicht kennt."""
    a, b = slugs
    vorher: Mapping[int, MayorDistrict] = {d.number: d for d in first_round}
    if not vorher:
        return None

    gezaehlt: list[tuple[MayorDistrict, MayorDistrict]] = []
    offen: list[tuple[MayorDistrict, MayorDistrict]] = []
    for d in current:
        v = vorher.get(d.number)
        if v is None:
            continue
        (gezaehlt if d.counted and d.votes.get(a) is not None and d.votes.get(b) is not None else offen).append((d, v))
    if not gezaehlt:
        return None

    # Je Topf: Schwung aus den gezählten Bezirken, Faktor für die Stimmenzahl.
    def rows(postal: bool) -> list[tuple[float, float, int]]:
        out = []
        for d, v in gezaehlt:
            if d.postal != postal:
                continue
            p = _share(v.votes.get(a), v.votes.get(b))
            q = _share(d.votes.get(a), d.votes.get(b))
            if p is None or q is None:
                continue
            out.append((p, q, (d.votes.get(a) or 0) + (d.votes.get(b) or 0)))
        return out

    urne, brief = rows(False), rows(True)
    s_urne, s_brief = _swing(urne), _swing(brief)
    caveats: list[str] = []
    if s_urne is None and s_brief is None:
        return None
    if s_urne is None:
        s_urne = s_brief
        caveats.append("Noch kein Urnenbezirk gezählt — der Schwung der Briefwahl gilt vorläufig auch für die Urne.")
    if s_brief is None:
        s_brief = s_urne
        caveats.append("Noch kein Briefwahlbezirk gezählt — der Schwung der Urne gilt vorläufig auch für die Briefwahl.")
    assert s_urne is not None and s_brief is not None

    # Wie stark die Stimmen gegenüber dem ersten Wahlgang wachsen — je Topf:
    # 2021 wuchsen die Zwei-Kandidaten-Stimmen an der Urne um 1,72, im Brief
    # um 1,31. Ein gemeinsamer Faktor gewichtete die Urne falsch, sobald die
    # Briefwahl zuerst kommt; und die Urne ist der Topf, in dem der eine
    # Name stärker ist als der andere.
    def faktor_von(paare: list[tuple[MayorDistrict, MayorDistrict]]) -> float | None:
        n2 = sum((d.votes.get(a) or 0) + (d.votes.get(b) or 0) for d, _ in paare)
        n1 = sum((v.votes.get(a) or 0) + (v.votes.get(b) or 0) for _, v in paare)
        return n2 / n1 if n1 > 0 else None

    faktor_alle = faktor_von(gezaehlt) or 1.0
    faktor = {postal: faktor_von([(d, v) for d, v in gezaehlt if d.postal == postal]) or faktor_alle
              for postal in (False, True)}
    n2 = sum((d.votes.get(a) or 0) + (d.votes.get(b) or 0) for d, _ in gezaehlt)

    # Reste der gezählten Bezirke — in Stimmen, damit große Bezirke mehr wiegen.
    reste: list[float] = []
    # Und als Anteil je Topf, (Rest, Gewicht): daraus die Unsicherheit des
    # SCHWUNGS selbst.
    reste_topf: dict[bool, list[tuple[float, int]]] = {False: [], True: []}
    for d, v in gezaehlt:
        p = _share(v.votes.get(a), v.votes.get(b))
        q = _share(d.votes.get(a), d.votes.get(b))
        if p is None or q is None:
            continue
        n = (d.votes.get(a) or 0) + (d.votes.get(b) or 0)
        rest = q - (p + (s_brief if d.postal else s_urne))
        reste.append(rest * n)
        reste_topf[d.postal].append((rest, n))
    sig_r = statistics.pstdev(reste) if len(reste) > 1 else 0.0
    n_bar = n2 / len(gezaehlt)

    ist_a = sum(d.votes.get(a) or 0 for d, _ in gezaehlt)
    ist_b = sum(d.votes.get(b) or 0 for d, _ in gezaehlt)
    erw_a = erw_b = 0.0
    varianz = 0.0
    offen_topf_stimmen = {False: 0.0, True: 0.0}
    open_max = 0
    for d, v in offen:
        p = _share(v.votes.get(a), v.votes.get(b))
        n = ((v.votes.get(a) or 0) + (v.votes.get(b) or 0)) * faktor[d.postal]
        if p is None or n <= 0:
            continue
        s = s_brief if d.postal else s_urne
        anteil = min(1.0, max(0.0, p + s))
        erw_a += anteil * n
        erw_b += (1 - anteil) * n
        varianz += (2 * sig_r * n / n_bar) ** 2 if n_bar > 0 else 0.0
        offen_topf_stimmen[d.postal] += n
        # Obergrenze dessen, was hier noch kommen kann.
        if d.postal or not (d.eligible or v.eligible):
            open_max += int(round(POSTAL_GROWTH_CAP * (v.valid_votes or 0)))
        else:
            open_max += int(d.eligible or v.eligible or 0)
    # Der Schwung ist selbst nur geschätzt — und ein Fehler darin trifft ALLE
    # offenen Bezirke eines Topfes in dieselbe Richtung. Er wächst deshalb mit
    # den offenen Stimmen, nicht mit ihrer Wurzel. Bis 09/2026 fehlte dieser
    # Term, und die Chance war in knappen Rennen viel zu sicher: An 2021 mit
    # verschobenen Anteilen gemessen, lag „99 %" in 12 von 100 Fällen daneben
    # (tests/test_runoff_model.py, Kalibrierung).
    for postal, zeilen in reste_topf.items():
        if not zeilen or offen_topf_stimmen[postal] <= 0:
            continue
        gewicht = sum(n for _, n in zeilen)
        streuung = math.sqrt(sum(n * r * r for r, n in zeilen) / gewicht) if gewicht else 0.0
        streuung = max(streuung, SWING_SD_FLOOR)
        k_eff = gewicht ** 2 / sum(n * n for _, n in zeilen)
        varianz += (2 * SWING_SE_SCALE * streuung / math.sqrt(k_eff) * offen_topf_stimmen[postal]) ** 2
    # Der Topf ohne gezählten Bezirk: sein Schwung ist geliehen.
    if not urne and offen_topf_stimmen[False] > 0:
        varianz += (2 * POT_SWING_SD * offen_topf_stimmen[False]) ** 2
    if not brief and offen_topf_stimmen[True] > 0:
        varianz += (2 * POT_SWING_SD * offen_topf_stimmen[True]) ** 2

    proj_a, proj_b = ist_a + erw_a, ist_b + erw_b
    gesamt = proj_a + proj_b
    leader = a if proj_a >= proj_b else b
    lead = abs(proj_a - proj_b)
    sigma = math.sqrt(varianz)
    actual_leader = a if ist_a >= ist_b else b
    actual_lead = abs(ist_a - ist_b)
    decided = not offen or actual_lead > open_max
    n_gezaehlt = len(gezaehlt)

    chance: int | None = None
    if decided:
        chance = None
    elif n_gezaehlt < MIN_DISTRICTS:
        caveats.append(f"Erst {n_gezaehlt} von {n_gezaehlt + len(offen)} Bezirken gezählt — zu früh für eine Wahrscheinlichkeit.")
    elif sigma > 0:
        chance = min(CHANCE_CAP, int(round(100 * 0.5 * (1 + math.erf(lead / sigma / math.sqrt(2))))))
    else:
        chance = CHANCE_CAP
    caveats.append("Modell: Jeder offene Bezirk stimmt wie im ersten Wahlgang, verschoben um den Trend der "
                   "schon gezählten Bezirke — Urne und Briefwahl getrennt. Über die Wähler*innen der "
                   "ausgeschiedenen Kandidaturen weiß es nichts.")

    return RunoffProjection(
        shares={a: round(100 * proj_a / gesamt, 1) if gesamt else 0.0,
                b: round(100 * proj_b / gesamt, 1) if gesamt else 0.0},
        projected_votes={a: int(round(proj_a)), b: int(round(proj_b))},
        leader=leader, lead_votes=int(round(lead)), chance_pct=chance,
        counted_ballot=sum(1 for d, _ in gezaehlt if not d.postal),
        counted_postal=sum(1 for d, _ in gezaehlt if d.postal),
        open_ballot=sum(1 for d, _ in offen if not d.postal),
        open_postal=sum(1 for d, _ in offen if d.postal),
        decided=decided, actual_leader=actual_leader, actual_lead_votes=actual_lead,
        open_votes_max=open_max, sigma_votes=sigma, caveats=tuple(caveats),
    )
