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


# --- Beschluss-Seite ---------------------------------------------------------

def _beschluss(**mehr) -> dict:
    return {"decision": {"simple_summary": "Die Stadt verlängert die Veränderungssperre.",
                         "official_text": "  Die Satzung wird beschlossen.  "},
            **mehr}


def test_beschluss_reihenfolge_und_auszug_zeilenweise():
    d = _beschluss(template_dossier={"sections": [{"statements": [{"text": "Der Hebesatz steigt."}]}]},
                   template={"excerpt": "Anlass:\nDer Bebauungsplan 858 ist in Arbeit.\n\n \nDie Bürgschaft bleibt."})
    assert seitenbegriffe.decision_texts(d) == [
        "Die Stadt verlängert die Veränderungssperre.", "Die Satzung wird beschlossen.", "Der Hebesatz steigt.",
        "Anlass:", "Der Bebauungsplan 858 ist in Arbeit.", "Die Bürgschaft bleibt."]
    begriffe = seitenbegriffe.decision_terms(d)
    assert [b["term"] for b in begriffe] == ["Veränderungssperre", "Satzung", "Hebesatz", "Bebauungsplan", "Bürgschaft"]
    # Keine Fundstelle reicht über einen Zeilenwechsel — die Seite zeigt den Auszug zeilenweise.
    assert all("\n" not in b["snippet"] for b in begriffe)


def test_beschluss_begriffe_aus_der_vorlage_nur_wo_sie_stehen():
    d = _beschluss(template={"excerpt": "Die Stadt muss ihr Einvernehmen erteilen."})
    aus_vorlage = [{"term": "Einvernehmen", "explanation": "Die Zustimmung der Stadt."},
                   {"term": "Patronatserklärung", "explanation": "…"}]
    begriffe = seitenbegriffe.decision_terms(d, aus_vorlage)
    assert [(b["term"], b["kind"]) for b in begriffe] == [
        ("Veränderungssperre", "glossary"), ("Satzung", "glossary"), ("Einvernehmen", "document")]


def test_beschluss_ohne_texte():
    assert seitenbegriffe.decision_terms({"decision": {}}) == []


# --- Sitzungsseite -----------------------------------------------------------

def _sitzung(**mehr) -> dict:
    return {
        "has_protocol": False,
        "agenda_items": [
            {"item_number": "Ö 1", "summary": "Die Satzung über die Tagesordnung."},          # Formalie
            {"item_number": "Ö 2", "summary": "Der Rat berät den Bebauungsplan 871.", "template_number": "26/0001"},
            {"item_number": "Ö 3", "summary": "Bericht zum Bebauungsplan 5.", "template_number": "26/0002"},
            {"item_number": "Ö 4", "summary": "Die Bürgschaft und die Satzung und der Hebesatz."},
            {"item_number": "Ö 5", "summary": "Anfragen zur Grundsteuer C."},                   # Anfragen
            {"item_number": "Ö 6", "summary": "Die Umschuldung als Überschrift."},              # nicht im Kurs
        ],
        "decisions": [],
        "course": {"items": {
            "Ö 1": {"type": "formality", "formality": True},
            "Ö 2": {"type": "decision", "important": True, "important_reason": "Der Hebesatz hängt daran."},
            "Ö 3": {"type": "report"},
            "Ö 4": {"type": "decision"},
            "Ö 5": {"type": "inquiries"},
        }},
        **mehr}


def test_sitzung_nur_karten_die_die_seite_zeigt():
    karten = seitenbegriffe.session_cards(_sitzung())
    assert [k[0] for k in karten] == ["Ö 2", "Ö 3", "Ö 4"]
    assert karten[0] == ("Ö 2", "26/0001", ["Der Rat berät den Bebauungsplan 871.", "Der Hebesatz hängt daran."])


def test_sitzung_erste_karte_je_begriff_und_hoechstens_zwei_je_karte():
    begriffe = seitenbegriffe.session_terms(_sitzung())
    # „Bebauungsplan“ nur an Ö 2 (nicht noch einmal an Ö 3); an Ö 4 stehen drei
    # Fachwörter, „Hebesatz“ ist schon an Ö 2 erklärt, bleiben zwei.
    assert [(b["item"], b["term"]) for b in begriffe] == [
        ("Ö 2", "Bebauungsplan"), ("Ö 2", "Hebesatz"), ("Ö 4", "Bürgschaft"), ("Ö 4", "Satzung")]


def test_sitzung_nach_dem_protokoll_zaehlt_der_beschlusstext():
    s = _sitzung(has_protocol=True, decisions=[
        {"kind": "decision", "item_number": "2", "simple_summary": "Die Veränderungssperre gilt weiter.", "summary": "x"},
        {"kind": "subvote", "item_number": "2", "simple_summary": "Die Umschuldung."}])
    karten = dict((k[0], k[2]) for k in seitenbegriffe.session_cards(s))
    # Beschlusstext statt Ankündigung, und „Warum wichtig“ steht nach dem Protokoll nicht mehr da.
    assert karten["Ö 2"] == ["Die Veränderungssperre gilt weiter."]
    assert [b["term"] for b in seitenbegriffe.session_terms(s) if b["item"] == "Ö 2"] == ["Veränderungssperre"]


def test_sitzung_begriffe_aus_der_vorlage_nur_an_ihrer_karte():
    aus = {"26/0002": [{"term": "Bericht", "explanation": "…"}], "26/0001": [{"term": "Rat", "explanation": "…"}]}
    begriffe = seitenbegriffe.session_terms(_sitzung(), aus)
    # Ö 2 ist mit zwei Glossar-Begriffen voll; „Bericht“ gilt nur an Ö 3.
    assert [(b["item"], b["term"], b["kind"]) for b in begriffe if b["kind"] == "document"] == [("Ö 3", "Bericht", "document")]


def test_sitzung_deckel():
    punkte = [{"item_number": f"Ö {i}", "summary": f"{w} steht an."} for i, w in enumerate(
        ["Die Satzung", "Der Hebesatz", "Die Bürgschaft", "Der Bebauungsplan", "Die Umschuldung", "Die Veränderungssperre",
         "Der Jahresabschluss", "Der Wirtschaftsplan", "Der Eigenbetrieb", "Die Zuwendung", "Der Teilhaushalt",
         "Der Flächennutzungsplan", "Der Verwaltungsausschuss", "Die Kommunalaufsicht"], 1)]
    s = {"agenda_items": punkte, "decisions": [], "course": {"items": {p["item_number"]: {"type": "decision"} for p in punkte}}}
    assert len(seitenbegriffe.session_terms(s)) == seitenbegriffe.MAX_SITZUNG


def test_sitzung_ohne_kurs():
    assert seitenbegriffe.session_terms({"agenda_items": [{"item_number": "Ö 1", "summary": "Die Satzung."}]}) == []
