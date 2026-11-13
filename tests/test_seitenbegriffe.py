"""Welche Texte einer Punkt-Seite Fachwörter tragen — und in welcher Reihenfolge."""
from council import seitenbegriffe


def _punkt(**mehr) -> dict:
    return {"item": {"summary": "Der Rat berät den Bebauungsplan 871.", "social_text": None},
            "course_item": {"important": False, "important_reason": "Der Bebauungsplan betrifft viele."},
            "template_fields": {"proposed_decision": "  Die Satzung wird beschlossen.  ", "cost": None, "climate": None},
            **mehr}


def test_reihenfolge_wie_auf_der_seite():
    p = _punkt(dossier={"sections": [{"statements": [{"text": "Der Hebesatz steigt."}]}]},
               amendments=[{"meaning": {"text": "Die Widmung entfällt."}, "reason": None}])
    assert seitenbegriffe.item_texts(p) == [
        "Der Rat berät den Bebauungsplan 871.", "Der Hebesatz steigt.", "Die Widmung entfällt.",
        "Die Satzung wird beschlossen."]


def test_ohne_dossier_steht_der_wortlaut_vor_den_antraegen():
    p = _punkt(amendments=[{"meaning": {"text": "Die Widmung entfällt."}}])
    assert seitenbegriffe.item_texts(p)[1:] == ["Die Satzung wird beschlossen.", "Die Widmung entfällt."]


def test_social_text_gewinnt_und_warum_wichtig_nur_wenn_gezeigt():
    p = _punkt()
    p["item"]["social_text"] = "Neuer Bebauungsplan für Etzhorn."
    p["course_item"]["important"] = True
    assert seitenbegriffe.item_texts(p)[:2] == ["Neuer Bebauungsplan für Etzhorn.", "Der Bebauungsplan betrifft viele."]


def test_jeder_begriff_einmal_ueber_die_ganze_seite():
    p = _punkt(dossier={"sections": [{"statements": [{"text": "Der Bebauungsplan liegt aus."}]}]})
    begriffe = seitenbegriffe.item_terms(p)
    assert [b["term"] for b in begriffe] == ["Bebauungsplan", "Satzung"]
    assert begriffe[0]["snippet"] in p["item"]["summary"]
    # getrimmt, damit die Fundstelle auch im getrimmten Zitat der Seite steht
    assert begriffe[1]["snippet"] == "Die Satzung wird beschlossen."


def test_leerer_punkt():
    assert seitenbegriffe.item_terms({"item": {}, "course_item": {}, "template_fields": None}) == []
