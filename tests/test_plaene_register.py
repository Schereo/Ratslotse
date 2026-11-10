"""Wächter für das Plan-Register (`council/plans.py`), ohne Datenbank.

Das Register ist Handarbeit. Was hier geprüft wird, ist die Form: Ein
Tippfehler in einer Vorlagennummer, ein Nachfolger, der auf einen
Schlüssel zeigt, den es nicht gibt, oder ein Themenfeld, das die
Klassifikation nicht kennt, fiele sonst erst auf der Seite auf — als
leerer Block, nicht als Fehler.

Ob die Nummern im Bestand existieren und jede Berichtsreihe etwas findet,
prüft ``scripts/pruefe_plaene.py`` gegen den lokalen Abzug; der Messtest
am Ende dieser Datei ruft genau das, wenn ein Abzug da ist.
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

import pytest

from council import plans
from council.goals import GOALS
from council.topics import POLICY_FIELDS

PLANS = list(plans.PLANS.values())
IDS = [p.key for p in PLANS]


def test_schluessel_passt_zum_eintrag():
    for key, plan in plans.PLANS.items():
        assert plan.key == key, f"{key!r} trägt intern den Schlüssel {plan.key!r}"
        assert re.fullmatch(r"[a-z0-9_]+", key), f"{key!r}: nur a-z, 0-9 und _"


@pytest.mark.parametrize("plan", PLANS, ids=IDS)
def test_art_und_themenfeld(plan):
    assert plan.kind in plans.KIND_LABELS, f"{plan.key}: unbekannte Art {plan.kind!r}"
    assert plan.policy_field in POLICY_FIELDS, (
        f"{plan.key}: Themenfeld {plan.policy_field!r} fehlt in council.topics.POLICY_FIELDS")
    assert plan.owner is None or plan.kind == "reference", (
        f"{plan.key}: ein Plan eines Dritten läuft nur als Verweis (kind='reference')")
    assert plan.goal is None or plan.goal in GOALS, f"{plan.key}: Ziel {plan.goal!r} unbekannt"


@pytest.mark.parametrize("plan", PLANS, ids=IDS)
def test_vorlagennummern_und_daten_haben_die_richtige_form(plan):
    for number in plans.all_templates(plan):
        assert plans.TEMPLATE_RE.match(number), (
            f"{plan.key}: {number!r} ist keine Vorlagennummer (JJ/NNNN oder JJ/NNNN/F)")
    decisions = ((plan.adopted,) if plan.adopted else ()) + plan.decisions
    for d in decisions:
        assert plans.DATE_RE.match(d.date), f"{plan.key}: Datum {d.date!r} nicht ISO"
        assert d.mode in ("adopted", "noted"), f"{plan.key}: Beschlussart {d.mode!r}"
        if d.template is None:
            # Vor dem Bestand: Sitzungen ab 01/2018 hat das RIS alle.
            assert d.date < "2018", (
                f"{plan.key}: Beschluss {d.date} ohne Vorlagennummer, obwohl er im Bestand liegt")
    for feld in ("start", "end", "review_due"):
        wert = getattr(plan, feld)
        assert wert is None or plans.DATE_RE.match(wert), f"{plan.key}.{feld}: {wert!r} nicht ISO"
    if plan.start and plan.end:
        assert plan.start[:4] <= plan.end[:4], f"{plan.key}: endet vor seinem Beginn"


@pytest.mark.parametrize("plan", PLANS, ids=IDS)
def test_plan_in_arbeit_nennt_seinen_auftrag(plan):
    if plan.adopted is None:
        assert plan.commissioned, (
            f"{plan.key}: ohne Beschluss braucht der Plan die Vorlage, mit der die Arbeit "
            "begann (commissioned) — sonst hat die Seite nichts zu zeigen")


@pytest.mark.parametrize("plan", PLANS, ids=IDS)
def test_berichtsmuster_sind_gueltig(plan):
    assert plan.report_patterns, f"{plan.key}: ohne Titelmuster findet Phase 1 keinen Bericht"
    for muster in plan.report_patterns + plan.exclude_patterns + plan.implementation_patterns:
        re.compile(muster, re.IGNORECASE)
        # council/CLAUDE.md: \b vorn trifft deutsche Komposita nicht.
        assert not muster.startswith(r"\b"), f"{plan.key}: {muster!r} — keine Wortgrenze vorn"


def test_vorgaenger_und_nachfolger_zeigen_aufeinander():
    for plan in PLANS:
        if plan.successor:
            assert plan.successor in plans.PLANS, f"{plan.key}: Nachfolger {plan.successor!r} fehlt"
            nach = plans.PLANS[plan.successor]
            assert nach.predecessor == plan.key, (
                f"{plan.key} → {nach.key}, aber {nach.key}.predecessor = {nach.predecessor!r}")
        if plan.predecessor:
            assert plan.predecessor in plans.PLANS, (
                f"{plan.key}: Vorgänger {plan.predecessor!r} fehlt")
            vor = plans.PLANS[plan.predecessor]
            assert vor.successor == plan.key, (
                f"{vor.key} ← {plan.key}, aber {vor.key}.successor = {vor.successor!r}")


def test_ketten_haben_keinen_kreis():
    for plan in PLANS:
        gesehen = {plan.key}
        weiter = plan.successor
        while weiter:
            assert weiter not in gesehen, f"Kreis in der Kette ab {plan.key}"
            gesehen.add(weiter)
            weiter = plans.PLANS[weiter].successor


def test_titel_abgleich():
    gewalt = plans.PLANS["aktionsplan_gewalt_2020"]
    assert plans.matches_title(gewalt, "Zwischenbericht zur Umsetzung des Kommunalen "
                                       "Aktionsplans gegen Gewalt an Frauen*")
    assert not plans.matches_title(gewalt, "Gleichstellungsplan - Bericht")
    laerm = plans.PLANS["laermaktionsplan"]
    assert plans.matches_title(laerm, "Fortschreibung des Lärmaktionsplans - Beschluss")
    assert not plans.matches_title(laerm, "Lärmaktionsplanung des Eisenbahn-Bundesamtes - Bericht")
    assert plans.template_stem("23/0211/2") == "23/0211"


# ---------------------------------------------------------------------------
# Gegen den Bestand — nur mit lokalem Abzug (scripts/lokale_daten.py hol && setz)
# ---------------------------------------------------------------------------

#: EIGENE Variable, nicht COUNCIL_DB (tests/CLAUDE.md).
ECHTE_DB = Path(os.environ.get("RATSLOTSE_MESS_DB")
                or Path(__file__).resolve().parents[1] / "data" / "council.sqlite")


@pytest.mark.skipif(not ECHTE_DB.exists(), reason="kein lokaler Abzug")
def test_register_gegen_den_bestand():
    from scripts.pruefe_plaene import pruefe

    conn = sqlite3.connect(f"file:{ECHTE_DB}?mode=ro", uri=True)
    try:
        if not conn.execute("select count(*) from council_templates").fetchone()[0]:
            pytest.skip("Abzug ist leer")
        befunde = pruefe(conn)
    finally:
        conn.close()
    fehler = [b for b in befunde if b.schwere == "fehler"]
    assert not fehler, "\n".join(str(b) for b in fehler) + (
        "\n→ python scripts/pruefe_plaene.py zeigt alle Befunde")


def test_seiten_der_stadt():
    """Phase 5b: Der Verweis auf die Seite der Stadt zeigt auf einen Plan im Register und auf
    eine der beiden Seiten der Stadt — nirgendwohin sonst."""
    assert len(plans.PLAN_WEBSITES) >= 20
    for key, url in plans.PLAN_WEBSITES.items():
        assert key in plans.PLANS, f"{key} steht nicht im Register"
        assert url.startswith(("https://www.oldenburg.de/startseite/", "https://klimaportal.oldenburg.de/")), url
        assert "?" not in url and " " not in url
    assert plans.website("klimaschutzplan_2035") == "https://klimaportal.oldenburg.de/massnahmen"
    assert plans.website("luftreinhalteplan") is None
