"""Die geprüften Maßnahmenlisten (`council/plan_measures/*.json`, Plan „Pläne“, Phase 2).

Die Dateien sind von Hand geprüft und eingecheckt; gebaut hat sie
``scripts/plan_massnahmen.py`` aus den Dokumenten der Stadt. Was hier fest
steht, ist die Zusage der Liste: Sie gehört zu einem Plan im Register, jede
Kennung kommt einmal vor, jede Maßnahme nennt ihre Seite — und wo die Stadt
eine Zahl nennt, stimmt die Liste mit ihr überein (Plan § 5, Messziel Phase 2).

Ob die Dateien noch zu den Quellen passen: ``python scripts/plan_massnahmen.py
--pruefen`` (holt die PDF-Dateien, darum nicht in der Suite).
"""
from __future__ import annotations

import json

import pytest

from council import plan_pages, plans

DATEIEN = sorted(plans.MEASURES_DIR.glob("*.json"))


def test_es_gibt_listen():
    assert len(DATEIEN) >= 5, "Die fünf Pilotpläne aus Phase 2 fehlen"


@pytest.mark.parametrize("pfad", DATEIEN, ids=[p.stem for p in DATEIEN])
def test_form_einer_liste(pfad):
    d = json.loads(pfad.read_text(encoding="utf-8"))
    assert d["plan"] == pfad.stem, f"{pfad.name}: Dateiname und Plan passen nicht zusammen"
    assert d["plan"] in plans.PLANS, f"{pfad.name}: Plan {d['plan']!r} steht nicht im Register"
    src = d["source"]
    assert isinstance(src["document_id"], int) and src["url"].startswith("https://buergerinfo.oldenburg.de/")
    assert src.get("template") is None or plans.TEMPLATE_RE.match(src["template"])
    codes = [m["code"] for m in d["measures"]]
    assert len(codes) == len(set(codes)), f"{pfad.name}: doppelte Kennung"
    for m in d["measures"]:
        assert m["title"].strip() and m["title"] == " ".join(m["title"].split()), m
        assert isinstance(m["page"], int) and m["page"] > 0, m
        assert not any(z in m["title"] for z in "ﬂﬀﬁ"), f"Ligatur im Titel: {m}"
    if d["count_city"] is not None:
        assert len(codes) == d["count_city"], (
            f"{pfad.name}: {len(codes)} Maßnahmen, die Stadt zählt {d['count_city']} — "
            "python scripts/plan_massnahmen.py --nur " + pfad.stem)
    else:
        assert d["count_note"], f"{pfad.name}: ohne Zahl der Stadt muss die Liste sagen, warum"


def test_zahlen_der_pilotplaene():
    erwartet = {"klimaschutzplan_2035": 90, "waermeplan": 18, "ernaehrungsstrategie": 68,
                "aktionsplan_gewalt_2026": 30}
    for key, zahl in erwartet.items():
        assert len(plans.measures(key)["measures"]) == zahl, key


def test_block_auf_der_planseite():
    block = plan_pages.measures_block("klimaschutzplan_2035")
    assert block["count"] == 90 and block["count_city"] == 90
    felder = [g["field"] for g in block["groups"]]
    assert felder[0] == "Gebäude / Strom / Wärme" and "Mobilität" in felder
    assert sum(len(g["measures"]) for g in block["groups"]) == 90
    assert block["source"]["as_of_label"] == "25.11.2022"
    assert plan_pages.measures_block("masterplan_stadtgruen") is None


def test_zahlen_der_weiteren_listen():
    """Drei Listen ohne Zahl der Stadt (10.11.2026, ohne Modell gelesen). Die Zahl hier ist unsere
    eigene Zählung am Dokument — sie hält fest, dass der Leser nichts verliert."""
    erwartet = {"digitalisierungsstrategie": 40, "agenda_2025_alter": 26, "smv2025": 112}
    for key, zahl in erwartet.items():
        liste = plans.measures(key)
        assert len(liste["measures"]) == zahl and liste["count_city"] is None, key
    # Die Agenda nummeriert je Baustein; der Anhang zum smv2025 überspringt Nummern.
    assert [m["code"] for m in plans.measures("agenda_2025_alter")["measures"]][:3] == ["1.1", "1.2", "1.3"]
    nummern = {int(m["code"]) for m in plans.measures("smv2025")["measures"]}
    assert max(nummern) == 126 and not nummern & {86, 87, *range(89, 101)}


def test_neue_listen_werden_nicht_ueber_kennungen_zugeordnet():
    """„1.1“ oder „12“ sind keine Kennungen, die man in fremden Vorlagen suchen darf — die
    Zuordnung über Kennungen bleibt den Plänen mit eigenen Kürzeln vorbehalten."""
    from council import plan_tracking
    assert not {"digitalisierungsstrategie", "agenda_2025_alter", "smv2025"} & set(plan_tracking.measure_matchers())
