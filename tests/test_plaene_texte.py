"""Pläne der Stadt, Paket 2: ein Satz je Bericht, „Neu im jüngsten Bericht“, einfache Sprache,
Fragen, verwandte Pläne.

Überall dasselbe Prinzip: Ein Modell (oder eine Einbettung) schlägt vor, auf die Seite kommt nur,
was ohne Modell geprüft ist. Hier steht fest, was diese Prüfung zusagt — und was jede eingecheckte
Datei einhalten muss, gleich wer sie zuletzt angefasst hat:

- Berichtssatz: Das Zitat steht wörtlich in der Vorlage, jede Zahl des Satzes im Zitat; je Plan
  zitiert jede Stelle nur ein Bericht.
- Neu: zusätzlich steht das Zitat im vorigen Bericht NICHT, und es wiederholt nicht den Satz des
  jüngsten Berichts. Die Seite zeigt den Block nur, solange der Bericht der jüngste ist und nicht
  älter als zwei Jahre.
- Einfache Sprache: nur aus den Kernpunkten — keine Zahl, die dort nicht steht; passt die Fassung
  nicht mehr zu den Kernpunkten, zeigt die Seite sie nicht.
- Verwandte Pläne: nie Vorgänger oder Nachfolger (die stehen im Kopf), nie ein verworfenes Paar.

Gegen die Vorlagen selbst prüft ``scripts/pruefe_plaene.py`` (am Bestand).
"""
from __future__ import annotations

import json

import pytest

from council import plan_judge, plan_pages, plan_state, plans
from scripts import plan_berichte, plan_einfach, plan_verwandt

TODAY = "2026-11-10"
OLD = "Derzeit gibt es 20 realisierte Maßnahmen. Die Verwaltung bereitet die Fortschreibung vor."
NEW = ("Derzeit gibt es 22 realisierte Maßnahmen. Die Verwaltung bereitet die Fortschreibung vor. "
       "Im September wurde die Neuberechnung des Szenarios bis 2035 beauftragt.")

REPORT_FILES = sorted(plan_state.REPORTS_DIR.glob("*.json"))
PLAIN_FILES = sorted(plan_state.PLAIN_DIR.glob("*.json"))


# ── Die Prüfung ohne Modell ────────────────────────────────────────────────

def test_berichtssatz_braucht_woertliches_zitat_und_jede_zahl():
    ok = {"text": "22 Maßnahmen sind realisiert.", "quote": "Derzeit gibt es 22 realisierte Maßnahmen."}
    kept, dropped = plan_judge.checked_statements([ok], NEW, plan_judge.REPORT_TEXT_MAX)
    assert kept == [ok] and dropped == []
    for wrong in ({"text": "24 Maßnahmen sind realisiert.", "quote": "Derzeit gibt es 22 realisierte Maßnahmen."},
                  {"text": "22 Maßnahmen sind realisiert.", "quote": "Derzeit gibt es 22 umgesetzte Maßnahmen."},
                  {"text": "x" * (plan_judge.REPORT_TEXT_MAX + 1), "quote": "Derzeit gibt es 22 realisierte Maßnahmen."},
                  "kein Objekt"):
        kept, dropped = plan_judge.checked_statements([wrong], NEW, plan_judge.REPORT_TEXT_MAX)
        assert kept == [] and len(dropped) == 1


def test_ein_zitat_traegt_nur_einen_satz():
    a = {"text": "22 Maßnahmen sind realisiert.", "quote": "Derzeit gibt es 22 realisierte Maßnahmen."}
    b = {"text": "Es gibt 22 fertige Maßnahmen.", "quote": "Derzeit gibt es 22 realisierte  Maßnahmen."}
    kept, dropped = plan_judge.checked_statements([a, b], NEW, plan_judge.REPORT_TEXT_MAX)
    assert kept == [a] and "schon einen anderen Satz" in dropped[0]


def test_neu_ist_nur_was_im_vorigen_bericht_nicht_stand():
    repeated = {"text": "Die Fortschreibung wird vorbereitet.", "quote": "Die Verwaltung bereitet die Fortschreibung vor."}
    fresh = {"text": "Die Neuberechnung bis 2035 ist beauftragt.",
             "quote": "Im September wurde die Neuberechnung des Szenarios bis 2035 beauftragt."}
    changed = {"text": "22 Maßnahmen sind realisiert.", "quote": "Derzeit gibt es 22 realisierte Maßnahmen."}
    kept, dropped = plan_judge.checked_statements([repeated, fresh, changed], NEW, plan_judge.REPORT_TEXT_MAX, absent_from=OLD)
    # Dieselbe Aussage mit neuer Zahl zählt als neu; der wörtlich wiederholte Satz nicht.
    assert kept == [fresh, changed] and "im vorigen Bericht" in dropped[0]


def test_reihe_heisst_gleicher_titel_bis_auf_nummer_und_jahr():
    assert plan_judge.same_series("Klimaschutz-Aktivitäten 2/2026 - Bericht", "Klimaschutz-Aktivitäten 3/2026 - Bericht")
    assert not plan_judge.same_series("Vorstellung Integrationskonzept 2026 - Bericht", "Sachstand Umsetzung Integrationskonzept - Bericht")
    assert not plan_judge.same_series("", "")
    reports = [{"title": "Sachstand A 1/2025", "date": "2025-01-01", "template": "25/1"},
               {"title": "Sachstand A 2/2025", "date": "2025-06-01", "template": "25/2"}]
    assert plan_berichte.series_pair(reports) == (reports[0], reports[1])
    assert plan_berichte.series_pair(reports[:1]) is None


def test_jede_stelle_zitiert_nur_ein_bericht_der_frueheste():
    """Wiederholt ein späterer Bericht einen Satz wörtlich, zählt dort der zweite Vorschlag — oder keiner."""
    first = {"template": "25/1", "date": "2025-01-01", "text": "A.", "quote": "Ein vierter Sensor wurde in Betrieb genommen."}
    again = {"template": "26/1", "date": "2026-01-01", "text": "A noch einmal.", "quote": "Ein vierter Sensor wurde in Betrieb genommen.",
             "alternatives": [{"text": "B.", "quote": "Die Leerstandsquote liegt bei 8,2 %."}]}
    longer = {"template": "26/2", "date": "2026-06-01", "text": "C.",
              "quote": "Ein vierter Sensor wurde in Betrieb genommen. Weitere Standorte sind in Planung."}
    out = plan_berichte.distinct([longer, again, first])
    assert [(r["template"], r["text"]) for r in out] == [("25/1", "A."), ("26/1", "B.")]
    assert all("alternatives" not in r for r in out)


def test_neu_wiederholt_nicht_den_satz_des_juengsten_berichts():
    reports = [{"template": "26/2", "quote": "Im September wurde die Neuberechnung beauftragt. Ein Vorschlag folgt."}]
    block = {"to": "26/2", "items": [{"text": "x", "quote": "Im September wurde die Neuberechnung beauftragt."},
                                      {"text": "y", "quote": "Ab Oktober gibt es ein neues Beratungsangebot."}]}
    assert [i["text"] for i in plan_berichte.fresh_only(block, reports)["items"]] == ["y"]
    assert plan_berichte.fresh_only({"to": "26/2", "items": block["items"][:1]}, reports) is None
    assert plan_berichte.fresh_only(None, reports) is None


def test_einfache_fassung_nennt_keine_fremde_zahl():
    lines = ["Der Plan enthält 90 Maßnahmen.", "Bis 2030 sollen die Emissionen sinken."]
    plain = ["Der Plan hat 90 Maßnahmen.", "Bis 2030 sollen die Emissionen sinken.", "Es geht um Klimaschutz."]
    questions = ["Was wurde zuletzt zum Plan berichtet?", "Was soll bis 2030 sinken?", "Welche Maßnahmen gibt es?"]
    assert plan_judge.check_plain(plain, questions, "Plan 2035", lines) == []
    assert plan_judge.check_plain(["Der Plan hat 95 Maßnahmen.", *plain[1:]], questions, "Plan 2035", lines)
    assert plan_judge.check_plain(plain[:2], questions, "Plan 2035", lines)
    assert plan_judge.check_plain([plain[0], plain[1], "x" * (plan_judge.PLAIN_CHARS + 1)], questions, "Plan 2035", lines)
    assert plan_judge.check_plain(plain, [questions[0], questions[0], questions[2]], "Plan 2035", lines)
    assert plan_judge.check_plain(plain, [questions[0], "Keine Frage.", questions[2]], "Plan 2035", lines)
    assert plan_judge.check_plain(plain, [questions[0], "Was kosten die 400 Maßnahmen?", questions[2]], "Plan 2035", lines)


def test_fingerabdruck_haengt_an_den_kernpunkten():
    lines = ["Zweck.", "Erster Punkt.", "Zweiter Punkt."]
    assert plan_judge.plain_basis(lines) == plan_judge.plain_basis(["Zweck.", "Erster  Punkt.", "Zweiter Punkt."])
    assert plan_judge.plain_basis(lines) != plan_judge.plain_basis(["Zweck.", "Erster Punkt.", "Dritter Punkt."])


def test_auftrag_ans_modell_nennt_bericht_und_regeln(monkeypatch):
    seen = {}

    class Reply:
        usage = None
        choices = [type("C", (), {"message": type("M", (), {"content": json.dumps({"candidates": [
            {"text": "22 Maßnahmen sind realisiert.", "quote": "Derzeit gibt es 22 realisierte Maßnahmen."},
            {"text": "Erfunden: 99 Maßnahmen.", "quote": "Das steht nirgends im Bericht, wirklich nicht."}]})})})]

    def fake(**kwargs):
        seen.update(kwargs)
        return Reply()

    monkeypatch.setattr(plan_judge.llm, "chat_complete", fake)
    monkeypatch.setattr(plan_judge, "cost_usd", lambda response, model: 0.0)
    kept, dropped, _cost = plan_judge.report_sentence("Klimaschutzplan", "Aktivitäten 3/2026", "08.10.2026", NEW)
    assert [k["text"] for k in kept] == ["22 Maßnahmen sind realisiert."] and len(dropped) == 1
    prompt = seen["messages"][0]["content"]
    assert seen["_feature"] == "plan_reports" and NEW in prompt and "Aktivitäten 3/2026" in prompt
    assert "keine Wertung" in prompt and "ALLEIN" in prompt


# ── Die eingecheckten Dateien ──────────────────────────────────────────────

@pytest.mark.parametrize("path", REPORT_FILES, ids=[p.stem for p in REPORT_FILES])
def test_form_einer_berichtsdatei(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["plan"] == path.stem and data["plan"] in plans.PLANS and data["read_by"] == "model"
    assert isinstance(data["reviewed"], bool) and data["reports"]
    assert [r["date"] for r in data["reports"]] == sorted(r["date"] for r in data["reports"])
    assert len({r["template"] for r in data["reports"]}) == len(data["reports"])
    entries = [*data["reports"], *(data.get("news") or {}).get("items", [])]
    for entry in entries:
        text, quote = entry["text"], entry["quote"]
        assert text == " ".join(text.split()) and text.endswith(".") and len(text) <= plan_judge.REPORT_TEXT_MAX, text
        assert plan_judge.QUOTE_MIN_TIGHT <= len(plan_judge.tight(quote)) and len(quote) <= plan_judge.QUOTE_MAX, quote
        assert not plan_judge.numbers(text) - plan_judge.numbers(quote), f"Zahl ohne Beleg: {text}"
    for n, report in enumerate(data["reports"]):
        assert not plan_berichte.overlaps(report["quote"], [r["quote"] for r in data["reports"][:n]]), report["template"]
    if news := data.get("news"):
        assert 1 <= len(news["items"]) <= plan_judge.NEWS_MAX and news["from_date"] < news["to_date"]
        assert news["to"] == data["reports"][-1]["template"] or news["to"] not in {r["template"] for r in data["reports"]}
        assert plan_berichte.fresh_only(news, data["reports"]) == news


@pytest.mark.parametrize("path", PLAIN_FILES, ids=[p.stem for p in PLAIN_FILES])
def test_einfache_fassung_passt_zu_den_kernpunkten(path):
    problems = plan_einfach.check(path.stem)
    assert problems == [], f"{problems} — python scripts/plan_einfach.py --nur {path.stem} (oder die Datei löschen)"


def test_jeder_plan_mit_kernpunkten_hat_eine_einfache_fassung():
    missing = set(plan_state.key_point_keys()) - set(plan_state.plain_keys())
    assert not missing, f"ohne einfache Fassung: {sorted(missing)} — python scripts/plan_einfach.py"
    assert set(plan_state.plain_keys()) <= set(plan_state.key_point_keys())


def test_verwandte_plaene_passen_zum_register():
    assert plan_verwandt.check() == []
    related = plan_state.related()
    for key, others in related.items():
        assert key not in others and len(others) == len(set(others))
        assert all(key in related[o] for o in others), "verwandt gilt in beide Richtungen"
        assert not any(plan_verwandt.chained(key, o) for o in others)
    # Was das Register selbst nennt, steht vorn.
    assert related["schulverpflegung"][0] == "ernaehrungsstrategie"


# ── Auf der Seite ──────────────────────────────────────────────────────────

def item(template: str, date: str, title: str, n: int) -> dict:
    return {"plan_key": "klimaschutzplan_2035", "agenda_item_id": n, "ksinr": n, "item_number": "1", "date": date,
            "committee": "Ausschuss für Stadtgrün, Umwelt und Klima", "title": title, "template_number": template,
            "kvonr": None, "role": "report", "oral": 0, "decision_id": None, "outcome": None}


def test_bericht_traegt_seinen_satz_im_zeitstrahl():
    plan = plans.PLANS["klimaschutzplan_2035"]
    data = plan_state.reports(plan.key)
    known = data["reports"][-1]
    stations = plan_pages.timeline([item(known["template"], known["date"], "Bericht", 1),
                                    item("99/9999", "2026-11-01", "Ohne Satz", 2),
                                    {**item(known["template"], "2026-10-09", "Mündlich", 3), "oral": 1, "template_number": None}],
                                   plan)["stations"]
    by_template = {s["template_number"]: s for s in stations}
    assert by_template[known["template"]]["summary"] == {"text": known["text"], "quote": known["quote"]}
    assert by_template["99/9999"]["summary"] is None and by_template[None]["summary"] is None
    # Ohne Plan (Übersicht) fragt niemand nach Sätzen.
    assert all(s["summary"] is None for s in plan_pages.timeline([item(known["template"], known["date"], "Bericht", 1)])["stations"])


def test_neu_block_nur_solange_der_bericht_der_juengste_und_frisch_ist():
    plan = plans.PLANS["klimaschutzplan_2035"]
    news = plan_state.reports(plan.key)["news"]
    latest = plan_pages.timeline([item(news["from"], news["from_date"], "Aktivitäten 2", 1),
                                  item(news["to"], news["to_date"], "Aktivitäten 3", 2)], plan)["stations"]
    block = plan_pages.news_block(plan, latest, TODAY)
    assert block["to_template"] == news["to"] and len(block["items"]) == len(news["items"])
    assert "Nach Angaben der Verwaltung" in block["note"]
    # Zwei Jahre später ist „neu“ nicht mehr neu …
    assert plan_pages.news_block(plan, latest, "2028-11-10") is None
    # … und sobald ein jüngerer Bericht da ist, gehört der Vergleich zu einem alten.
    newer = plan_pages.timeline([item(news["to"], news["to_date"], "Aktivitäten 3", 2),
                                 item("26/9999", "2026-11-05", "Aktivitäten 4", 3)], plan)["stations"]
    assert plan_pages.news_block(plan, newer, TODAY) is None
    assert plan_pages.news_block(plan, [], TODAY) is None
    assert plan_pages.news_block(plans.PLANS["kai_2015"], latest, TODAY) is None


def test_einfache_fassung_verschwindet_wenn_die_kernpunkte_sich_aendern(monkeypatch):
    plan = plans.PLANS["schulverpflegung"]
    block = plan_pages.plain_block(plan)
    assert len(block["sentences"]) == plan_judge.PLAIN_SENTENCES and len(block["questions"]) == plan_judge.QUESTION_COUNT
    assert all(q.endswith("?") for q in block["questions"])
    points = plan_state.key_points(plan.key)
    changed = {**points, "points": [{**points["points"][0], "text": "Ein anderer Kernpunkt."}, *points["points"][1:]]}
    monkeypatch.setattr(plan_state, "key_points", lambda key: changed)
    assert plan_pages.plain_block(plan) is None
    assert plan_pages.plain_block(plans.PLANS["kai_2015"]) is None


def test_verwandte_plaene_auf_der_seite():
    related = plan_pages.related_block(plans.PLANS["klimaschutzplan_2035"], TODAY)
    assert 1 <= len(related) <= plan_pages.RELATED_MAX
    assert "thg_neutrale_verwaltung" in [r["key"] for r in related]
    # Der Vorgänger steht im Kopf der Seite, nicht hier.
    assert plans.PLANS["klimaschutzplan_2035"].predecessor not in [r["key"] for r in related]
    assert all(r["title"] and r["field_label"] and r["status_label"] for r in related)
    assert plan_pages.related_block(plans.PLANS["kai_2015"], TODAY) == []
