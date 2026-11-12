"""Was die Vorlage eines Punkts trägt, ohne Modell (Plan Vorlagen, Stufe 0)."""
from council import vorlage_felder as vf


def test_kostenstatus():
    assert vf.cost_status("Es entstehen Kosten von rund 20.000 Euro jährlich.") == "amount"
    assert vf.cost_status("1,2 Mio. € im Haushaltsjahr 2027") == "amount"
    assert vf.cost_status("Keine.") == "none"
    assert vf.cost_status("Es entstehen keine Kosten.") == "none"
    assert vf.cost_status("Die Mittel stehen im Budget des Amtes zur Verfügung.") == "text"
    assert vf.cost_status("") is None


def test_antraege_aus_vorlage_und_punkt_ohne_dubletten():
    vorlage = {"template_number": "26/0795", "document_url": "u", "office": "Büro des OB",
               "proposed_decision": "Der Rat bildet …", "financial_impact": "35,00 Euro pro Sitzung",
               "climate_impact": "Prüfungsrelevant: Nein"}
    an_vorlage = [{"label": "Änderungsantrag CDU", "url": "a1", "is_motion": 1, "applicants": ["CDU"]},
                  {"label": "Lageplan", "url": "a2", "is_motion": 0, "applicants": []}]
    am_punkt = [{"label": "Änderungsantrag CDU", "url": "a1", "raw_text": ""},
                {"label": "2026-10-31 Reduzierung", "url": "a3",
                 "raw_text": "Fraktion Bündnis 90/Die Grünen\nÄnderungsantrag zu TOP 13.2"},
                {"label": "Übersicht", "url": "a4", "raw_text": "Tabelle"}]
    f = vf.build(vorlage, an_vorlage, am_punkt)
    assert [m["url"] for m in f["motions"]] == ["a1", "a3"]
    assert f["cost"] == {"text": "35,00 Euro pro Sitzung", "status": "amount"}
    assert f["climate"]["relevant"] is False


def test_ohne_vorlage_und_antrag_nichts():
    assert vf.build(None, [], [{"label": "Übersicht", "url": "x", "raw_text": ""}]) is None
