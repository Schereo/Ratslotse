"""„Was im Plan steht“: Zweck und Kernpunkte je Plan (`council/plan_key_points/*.json`).

Die Sätze entwirft ein Sprachmodell (``scripts/plan_kernpunkte.py``); in die
Datei kommt nur, was ``council/plan_judge.py`` ohne Modell belegen kann. Hier
steht fest, was diese Prüfung zusagt — und was jede eingecheckte Datei
einhalten muss, gleich wer sie zuletzt angefasst hat:

- das Zitat steht wörtlich in der Quelle (Zeilenumbrüche, Trennstriche und
  typografische Zeichen des PDF-Textes ausgenommen), bei Anlagen auf der
  genannten Seite;
- jede Zahl des Satzes steht im Zitat;
- jeder Plan hat eine Datei ODER einen Grund, warum er keine hat.

Gegen die Quellen selbst prüfen ``scripts/pruefe_plaene.py`` (Beschlusstexte
und Vorlagen aus dem Bestand) und ``scripts/plan_kernpunkte.py --pruefen``
(dazu die PDF-Dateien der Anlagen, mit Seitenzahl).
"""
from __future__ import annotations

import json

import pytest

from council import plan_judge, plan_pages, plan_state, plans
from council.store import CouncilStore
from scripts import plan_kernpunkte

FILES = sorted(plan_state.KEY_POINTS_DIR.glob("*.json"))

TEXT = {"id": "V1", "kind": "template", "template": "19/0943",
        "text": "Der DGE-Qualitätsstandard wird als verbind- liche Grundlage des Mittagessens eingeführt. "
                "Ausdruck vom: 11.11.2022 Seite: 2/4 Das Abonnement kostet 3,50 € im Primarbereich."}
PAGES = {"id": "A1", "kind": "attachment", "template": "19/0943", "document_id": 1, "label": "Konzept",
         "pages": ["Titel", "An Grundschulen wird an allen Tagen mit Ganztagsangebot ein warmes",
                   "Mittagessen angeboten. Maximal zwei Saftschorlen dürfen angeboten werden."]}
BY_ID = {"V1": TEXT, "A1": PAGES}


# ── Die Prüfung ohne Modell ────────────────────────────────────────────────

def test_zitat_muss_woertlich_in_der_quelle_stehen():
    good = {"text": "Der DGE-Qualitätsstandard ist die verbindliche Grundlage des Mittagessens.", "source": "V1",
            "quote": "Der DGE-Qualitätsstandard wird als verbindliche Grundlage des Mittagessens eingeführt."}
    kept, why = plan_judge.check_statement(good, BY_ID, 190)
    assert kept and why is None and kept["page"] is None  # „verbind- liche“ ist ein Zeilenumbruch, kein anderes Wort
    bent = {**good, "quote": "Der DGE-Qualitätsstandard wird als verbindliche Grundlage aller Mahlzeiten eingeführt."}
    assert plan_judge.check_statement(bent, BY_ID, 190) == (None, "Zitat steht nicht wörtlich in der Quelle")


def test_seitenfuss_des_ausdrucks_trennt_kein_zitat():
    """Die Fußzeile „Ausdruck vom … Seite 2/4“ steht mitten im Satz, wo die Vorlage die Seite wechselt."""
    over = {"text": "Das Abonnement kostet 3,50 € im Primarbereich.", "source": "V1",
            "quote": "des Mittagessens eingeführt. Das Abonnement kostet 3,50 € im Primarbereich."}
    assert plan_judge.check_statement(over, BY_ID, 190)[0]


def test_jede_zahl_des_satzes_steht_im_zitat():
    wrong = {"text": "Das Abonnement kostet 3,60 € im Primarbereich.", "source": "V1",
             "quote": "Das Abonnement kostet 3,50 € im Primarbereich."}
    assert plan_judge.check_statement(wrong, BY_ID, 190) == (None, "Zahl ohne Beleg im Zitat: 3,60")
    added = {**wrong, "text": "Seit 2019 kostet das Abonnement 3,50 € im Primarbereich."}
    assert plan_judge.check_statement(added, BY_ID, 190) == (None, "Zahl ohne Beleg im Zitat: 2019")
    # Dieselbe Zahl in anderer Schreibweise ist dieselbe Zahl.
    assert plan_judge.numbers("100,00 € und 2.000 Euro, 3,50") == plan_judge.numbers("100 € und 2000 Euro, 3,5")
    assert plan_judge.numbers("Tempo 30 bis Ende 2027.") == {"30", "2027"}


def test_seite_wird_berichtigt_und_ein_seitenwechsel_ueberbrueckt():
    wrong_page = {"text": "Höchstens zwei Saftschorlen sind erlaubt.", "source": "A1", "page": 1,
                  "quote": "Maximal zwei Saftschorlen dürfen angeboten werden."}
    assert plan_judge.check_statement(wrong_page, BY_ID, 190)[0]["page"] == 3
    across = {"text": "An Grundschulen gibt es an Ganztagstagen ein warmes Mittagessen.", "source": "[A1], S. 2",
              "quote": "An Grundschulen wird an allen Tagen mit Ganztagsangebot ein warmes Mittagessen angeboten."}
    assert plan_judge.check_statement(across, BY_ID, 190)[0]["page"] == 2


def test_was_sonst_faellt():
    base = {"text": "Höchstens zwei Saftschorlen sind erlaubt.", "source": "A1",
            "quote": "Maximal zwei Saftschorlen dürfen angeboten werden."}
    assert plan_judge.check_statement({**base, "source": "A9"}, BY_ID, 190)[1] == "unbekannte Quelle"
    assert plan_judge.check_statement({**base, "quote": "zwei Saftschorlen"}, BY_ID, 190)[1].startswith("Zitat steht nicht")
    assert plan_judge.check_statement({**base, "text": "x" * 191}, BY_ID, 190)[1].startswith("Satz fehlt")
    assert plan_judge.check_statement("kein Objekt", BY_ID, 190)[0] is None


def test_ein_zitat_belegt_einen_satz():
    """Zwei Sätze auf demselben Zitat sagen dasselbe zweimal — und der Zweck zählt mit."""
    quote = "Maximal zwei Saftschorlen dürfen angeboten werden."
    answer = {"purposes": [{"text": "Das Konzept begrenzt Süßes.", "source": "A1", "quote": quote}],
              "points": [{"text": "Höchstens zwei Saftschorlen sind erlaubt.", "kind": "standard", "source": "A1", "quote": quote},
                         {"text": "Das Abonnement kostet 3,50 € im Primarbereich.", "kind": "unbekannt", "source": "V1",
                          "quote": "Das Abonnement kostet 3,50 € im Primarbereich."}]}
    found = plan_judge.verified_key_points(answer, [TEXT, PAGES])
    assert [p["text"] for p in found["purposes"]] == ["Das Konzept begrenzt Süßes."]
    assert [(p["source"], p["kind"]) for p in found["points"]] == [("V1", "goal")]


def test_prompt_nennt_ergebnis_und_reihenfolge(monkeypatch):
    """Ein Text über einen Plan kennt dessen Beschlussart: „zur Kenntnis genommen“ ist nicht „beschlossen“."""
    from types import SimpleNamespace
    seen = {}

    def fake(**kw):
        seen["prompt"] = kw["messages"][0]["content"]
        seen["feature"] = kw["_feature"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
                               usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1))

    monkeypatch.setattr(plan_judge.llm, "chat_complete", fake)
    found, _ = plan_judge.key_points("Demografiestrategie", "noted", [{**TEXT, "heading": "Vorlage 19/0943"},
                                                                     {**PAGES, "heading": "Anlage: Konzept"}])
    assert found == {"purposes": [], "points": [], "dropped": []} and seen["feature"] == "plan_key_points"
    assert "nur zur Kenntnis genommen" in seen["prompt"] and "— Seite 2 —" in seen["prompt"]
    assert "Ausdruck vom" not in seen["prompt"] and seen["prompt"].index("[V1]") < seen["prompt"].index("[A1]")


# ── Die eingecheckten Dateien ──────────────────────────────────────────────

def test_jeder_plan_hat_datei_oder_grund():
    files = {p.stem for p in FILES}
    without = set(plan_kernpunkte.WITHOUT_BLOCK)
    assert not files & without, f"Datei UND Grund: {sorted(files & without)}"
    missing = set(plans.PLANS) - files - without
    assert not missing, (f"Ohne Datei und ohne Grund: {sorted(missing)} — python scripts/plan_kernpunkte.py "
                         "oder ein Eintrag in WITHOUT_BLOCK")
    assert files | without <= set(plans.PLANS)
    assert all(reason.strip() for reason in plan_kernpunkte.WITHOUT_BLOCK.values())


@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
def test_form_einer_datei(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    plan = plans.PLANS[data["plan"]]
    assert data["plan"] == path.stem and data["read_by"] == "model" and isinstance(data["reviewed"], bool)
    assert plan_judge.POINTS_MIN <= len(data["points"]) <= plan_judge.POINTS_MAX
    documents = {(d, t) for d, t, _ in plan_kernpunkte.DOCUMENTS.get(plan.key, ())}
    decided = {(d.template, d.date, d.committee) for d in ((plan.adopted,) if plan.adopted else ()) + plan.decisions}
    quotes = [plan_judge.tight(e["quote"]) for e in [data["purpose"], *data["points"]]]
    assert len(quotes) == len(set(quotes)), "ein Zitat belegt zwei Sätze"
    for entry, limit in [(data["purpose"], 200), *[(p, 190) for p in data["points"]]]:
        text, quote, ref = entry["text"], entry["quote"], entry["source"]
        assert text == " ".join(text.split()) and text.endswith(".") and len(text) <= limit, text
        assert len(plan_judge.tight(quote)) >= plan_judge.QUOTE_MIN_TIGHT and len(quote) <= plan_judge.QUOTE_MAX, quote
        assert not plan_judge.numbers(text) - plan_judge.numbers(quote), f"Zahl ohne Beleg: {text}"
        assert ref["template"] in plans.all_templates(plan), ref
        if ref["kind"] == "decision":
            assert (ref["template"], ref["date"], ref["committee"]) in decided, ref
        elif ref["kind"] == "attachment":
            assert (ref["document_id"], ref["template"]) in documents and ref["label"].strip(), ref
            assert isinstance(ref["page"], int) and ref["page"] > 0, ref
        else:
            assert ref["kind"] == "template", ref
    for point in data["points"]:
        assert point["kind"] in plan_judge.POINT_KINDS


def test_schulverpflegung_nennt_den_heutigen_bio_stand():
    """Der Anlass (Tim, 10.11.2026): Der Bio-Anteil wurde 2022 bis 2025 viermal geändert. Auf der Seite
    steht der heute geltende Stand mit dem Beschluss, der ihn gesetzt hat — nicht der von 2019."""
    data = plan_state.key_points("schulverpflegung")
    bio = [p for p in data["points"] if "Bio" in p["text"]]
    assert bio and all(p["source"]["template"] != "19/0943" for p in bio)
    assert any(p["source"]["template"] == "25/0634" and "Käse" in p["quote"] for p in bio)


# ── Der Block auf der Seite ────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    yield s
    s.close()


def test_block_auf_der_planseite(store):
    page = plan_pages.detail(store, "schulverpflegung", today="2026-11-10")
    block = page["content"]
    assert block["heading"] == "Was der Plan festlegt" and block["note"] == plan_pages.CONTENT_NOTE
    assert plan_judge.POINTS_MIN <= len(block["points"]) <= plan_judge.POINTS_MAX
    amended = [p for p in block["points"] if p["amended"]]
    assert amended and all(p["source"]["date"] > "2019-12-16" for p in amended)
    original = next(p for p in block["points"] if p["source"]["kind"] == "attachment")
    assert original["source"]["url"].endswith(f"#page={original['source']['page']}") and not original["amended"]
    assert original["source"]["date_label"] == "16.12.2019" and original["source"]["decision_id"] is None


def test_ueberschrift_sagt_wie_verbindlich_der_plan_ist(store):
    """„Festlegt“ nur bei einem Beschluss (§ 3.4 Regel 7)."""
    noted = next(k for k in plan_state.key_point_keys() if plans.PLANS[k].adopted and plans.PLANS[k].adopted.mode == "noted")
    assert plan_pages.content_block(store, plans.PLANS[noted])["heading"] == "Was im Plan steht"
    assert plan_pages.CONTENT_HEADINGS["draft"] == "Was der Entwurf vorsieht"


def test_ohne_plantext_kein_block_und_kein_platzhalter(store):
    page = plan_pages.detail(store, "kai_2015", today="2026-11-10")
    assert page["content"] is None
