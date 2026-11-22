"""Wann das Protokoll einer Sitzung voraussichtlich erscheint.

Ein Protokoll wird in der NÄCHSTEN Sitzung desselben Gremiums genehmigt und
erscheint im Ratsinfo meist wenige Tage danach. Gemessen am 12.11.2026 über
die 20 Protokolle mit echtem Eingangsdatum (``available_at`` seit 07/2026):
17 kamen 1–4 Tage nach der nächsten Sitzung, drei später (18, 22 und 67
Tage — dort wurde es offenbar erst eine Sitzung danach genehmigt).

Ferien muss man deshalb nicht gesondert rechnen: Steht die nächste Sitzung
im Kalender, liegt die Pause schon dazwischen. Steht sie noch nicht da,
schätzen wir ihren Abstand aus derselben Jahreszeit früherer Jahre — der
Abstand nach einer Juni-Sitzung enthält die Sommerferien von selbst.
"""
from __future__ import annotations

from datetime import date, timedelta
from statistics import median
from typing import Literal, TypedDict

#: Tage nach der genehmigenden Sitzung: frühestens, typisch, spätestens.
NACH_GENEHMIGUNG = (1, 3, 7)
#: Wie weit „dieselbe Jahreszeit" reicht (Tage des Jahres, in beide Richtungen).
SAISON_FENSTER = 21
#: Rückfall, wenn das Gremium keine Geschichte hat: ein Monat Sitzungsabstand.
ABSTAND_RUECKFALL = 30


class ProtocolEstimate(TypedDict):
    earliest: str
    expected: str
    latest: str
    #: ``next_session``: die genehmigende Sitzung steht im Kalender.
    #: ``history``: ihr Datum ist aus früheren Jahren geschätzt.
    basis: Literal["next_session", "history"]
    #: Die Sitzung, in der es genehmigt wird (geschätzt bei ``history``).
    approval_date: str


def _tag_im_jahr_abstand(a: date, b: date) -> int:
    d = abs(a.timetuple().tm_yday - b.timetuple().tm_yday)
    return min(d, 365 - d)


def typical_gap(session_date: date, history: list[date]) -> int:
    """Typischer Abstand zur nächsten Sitzung desselben Gremiums in derselben
    Jahreszeit früherer Jahre. ``history``: alle Sitzungstage des Gremiums."""
    tage = sorted(set(history))
    abstaende = [
        (nach - vor).days
        for vor, nach in zip(tage, tage[1:])
        if vor < session_date - timedelta(days=SAISON_FENSTER)
        and _tag_im_jahr_abstand(vor, session_date) <= SAISON_FENSTER
        and (nach - vor).days <= 180  # Wahlperiodenwechsel o. ä. nicht mitzählen
    ]
    if not abstaende:
        abstaende = [(n - v).days for v, n in zip(tage, tage[1:]) if (n - v).days <= 180]
    return round(median(abstaende)) if abstaende else ABSTAND_RUECKFALL


def protocol_estimate(session_date: date, next_session: date | None,
                      history: list[date]) -> ProtocolEstimate:
    if next_session:
        genehmigung, basis = next_session, "next_session"
    else:
        genehmigung = session_date + timedelta(days=typical_gap(session_date, history))
        basis = "history"
    frueh, typisch, spaet = NACH_GENEHMIGUNG
    return {
        "earliest": (genehmigung + timedelta(days=frueh)).isoformat(),
        "expected": (genehmigung + timedelta(days=typisch)).isoformat(),
        "latest": (genehmigung + timedelta(days=spaet)).isoformat(),
        "basis": basis,
        "approval_date": genehmigung.isoformat(),
    }
