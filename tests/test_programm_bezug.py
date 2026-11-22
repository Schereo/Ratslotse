"""Was die Wahlprogramme zu einem Punkt sagen (``council/programm_bezug.py``).
Ein Zitat einer Partei ist ein Urteil über sie — die Tests halten fest, dass
nichts auf die Seite kommt, was nicht wörtlich im Programm DIESER Liste steht
und vom Prüfer bestätigt wurde."""
import json
from types import SimpleNamespace

import pytest

from council import programm_bezug as pb
from council import wahlprogramme as wp

LISTEN = ({"slug": "fdp", "label": "FDP", "seats": 2, "title": "Programm der FDP", "url": "https://example.org/fdp.pdf", "paged": True},
          {"slug": "linke", "label": "Linke", "seats": 7, "title": "Programm der Linken", "url": None, "paged": True},
          {"slug": "cdu", "label": "CDU", "seats": 7, "title": "Programm der CDU", "url": "https://example.org/cdu", "paged": False})
ABSCHNITTE = {
    "fdp": ({"idx": 0, "page": 8, "text": "Wir setzen uns für die Rechte von Eigentümern ein und lehnen jede Form von Enteignung durch eine "
                                          "Zweckentfremdungssatzung ab. Stattdessen setzen wir auf private Investoren."},),
    "linke": ({"idx": 0, "page": 6, "text": "Kommunales Leerstandsregister und Zweckentfremdungssatzung einführen. Wohnen ist ein Grundrecht."},),
    "cdu": ({"idx": 0, "page": None, "text": "Steuererhöhungen lehnen wir grundsätzlich ab. Wir wollen solide Finanzen für Oldenburg."},),
}


@pytest.fixture(autouse=True)
def programme(monkeypatch):
    monkeypatch.setattr(wp, "lists", lambda: LISTEN)
    monkeypatch.setattr(wp, "passages", lambda slug: ABSCHNITTE.get(slug, ()))
    monkeypatch.setattr(wp, "text_hash", lambda slug: f"h-{slug}")


def _v(party, stance, quote, reason="Das Programm lehnt die Satzung ausdrücklich ab.", basis="measure"):
    return {"party": party, "stance": stance, "quote": quote, "reason": reason, "basis": basis}


def test_nur_woertliche_zitate_aus_dem_programm_dieser_liste():
    aus = pb.pre_check([
        _v("fdp", "against", "lehnen jede Form von Enteignung durch eine Zweckentfremdungssatzung ab"),
        _v("linke", "for", "lehnen jede Form von Enteignung durch eine Zweckentfremdungssatzung ab"),   # steht bei der FDP, nicht bei der Linken
        _v("cdu", "for", "Wir fordern eine Zweckentfremdungssatzung für Oldenburg"),                    # frei erfunden
        _v("spd", "for", "Kommunales Leerstandsregister und Zweckentfremdungssatzung einführen"),        # keine Liste im Rat mit Programm
        _v("fdp", "none", None)])
    assert [(e["party"], e["stance"], e["page"]) for e in aus] == [("fdp", "against", 8)]


def test_seite_kommt_aus_der_fundstelle_und_leerraum_ist_egal():
    aus = pb.pre_check([{"party": "linke", "stance": "for", "page": 99, "basis": "measure",
                         "quote": "Kommunales  Leerstandsregister und\nZweckentfremdungssatzung einführen", "reason": "Die Linke fordert die Satzung."}])
    assert aus[0]["page"] == 6 and aus[0]["quote"] == "Kommunales Leerstandsregister und Zweckentfremdungssatzung einführen"


def test_verdaechtige_begruendung_und_zu_kurzes_zitat_fallen_weg():
    assert pb.pre_check([_v("fdp", "against", "lehnen jede Form von Enteignung durch eine Zweckentfremdungssatzung ab",
                            reason="Mehr unter https://example.org, bitte dort lesen.")]) == []
    assert pb.pre_check([_v("cdu", "against", "lehnen wir ab")]) == []


def _antwort(inhalt):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(inhalt)))], usage=None)


def test_pruefer_muss_bestaetigen_und_sagt_worauf_es_fusst(monkeypatch):
    einordnungen = pb.pre_check([
        _v("fdp", "against", "lehnen jede Form von Enteignung durch eine Zweckentfremdungssatzung ab"),
        _v("linke", "for", "Kommunales Leerstandsregister und Zweckentfremdungssatzung einführen", reason="Die Linke fordert die Satzung."),
        _v("cdu", "against", "Steuererhöhungen lehnen wir grundsätzlich ab", reason="Die CDU lehnt Steuererhöhungen ab.")])
    gesehen = {}

    def chat(**kw):
        gesehen.update(kw)
        return _antwort({"verdicts": [{"nr": 1, "supported": "yes", "specific": "measure"},
                                      {"nr": 2, "supported": "no", "specific": "measure"},       # Zitat trägt es nicht
                                      {"nr": 3, "supported": "yes", "specific": "no"}]})          # nur dasselbe Themenfeld
    monkeypatch.setattr(pb.llm, "chat_complete", chat)
    monkeypatch.setattr("council.plan_judge.cost_usd", lambda resp, model: 0.004)
    durch, kosten = pb.verify("Zweckentfremdungssatzung", ["Die Satzung soll beschlossen werden."],
                              "Eine Zweckentfremdungssatzung beschließen.", einordnungen, batch=False)
    assert [(e["party"], e["basis"]) for e in durch] == [("fdp", "measure")] and kosten == 0.004
    assert all(not k.startswith("_") for k in durch[0])            # die Umgebung bleibt intern
    assert gesehen["model"] == pb.VERIFY_MODEL and "_ersatz" not in gesehen
    assert "ANLIEGEN DES PUNKTS: Eine Zweckentfremdungssatzung beschließen." in gesehen["messages"][1]["content"]


def test_ohne_urteil_keine_aussage_ueber_eine_partei(monkeypatch):
    einordnungen = pb.pre_check([_v("fdp", "against", "lehnen jede Form von Enteignung durch eine Zweckentfremdungssatzung ab")])
    monkeypatch.setattr(pb.llm, "chat_complete", lambda **kw: _antwort({"verdicts": []}))
    assert pb.verify("x", [], "y", einordnungen, batch=False)[0] == []


def test_ohne_anliegen_schlaegt_das_modell_nichts_vor(monkeypatch):
    """Ein reiner Bericht will nichts — „dafür" hätte keine Richtung."""
    monkeypatch.setattr(pb.llm, "chat_complete", lambda **kw: _antwort(
        {"concern": None, "parties": [_v("fdp", "against", "lehnen jede Form von Enteignung durch eine Zweckentfremdungssatzung ab")]}))
    anliegen, parteien, _ = pb.propose("Drogenhilfestrategie - Bericht", ["Der Bericht stellt die Strategie vor."], {"fdp": list(ABSCHNITTE["fdp"])}, batch=False)
    assert anliegen == "" and parteien == []


def test_stichwoerter_sind_markant():
    assert pb.stichwoerter("Satzung über das Verbot der Zweckentfremdung von Wohnraum in der Stadt Oldenburg (Zweckentfremdungssatzung) - Beschluss") \
        == ["Zweckentfremdung"]
    assert pb.stichwoerter("Änderung 31 des Flächennutzungsplanes (BAB-Kreuz/Sandweg) - Bericht") == []


def test_sicht_der_seite_nach_sitzen_mit_quelle_und_schweigenden():
    payload = {"concern": "Eine Zweckentfremdungssatzung beschließen.", "stances": [
        {"party": "fdp", "stance": "against", "basis": "measure", "quote": "lehnen … ab", "page": 8, "reason": "Die FDP lehnt die Satzung ab."}]}
    sicht = pb.item_view(payload)
    assert sicht["concern"].startswith("Eine Zweck") and sicht["silent"] == ["Linke", "CDU"]
    assert sicht["parties"] == [{"slug": "fdp", "label": "FDP", "seats": 2, "stance": "against", "basis": "measure", "quote": "lehnen … ab",
                                 "page": 8, "reason": "Die FDP lehnt die Satzung ab.", "program_title": "Programm der FDP",
                                 "program_url": "https://example.org/fdp.pdf"}]
    assert pb.item_view({"stances": []}) is None and pb.item_view(None) is None


class _Store:
    def __init__(self):
        self.zeile = None

    def terms_material(self, tn):
        return {"title": "Zweckentfremdungssatzung - Beschluss", "texts": ["Die Satzung soll beschlossen werden."], "template_text": "…"} if tn == "26/1" else None

    def program_stances(self, tn):
        return self.zeile

    def save_program_stances(self, tn, h, **kw):
        self.zeile = {"template_number": tn, "sources_hash": h, **kw}


def test_bau_speichert_meldet_kosten_und_laeuft_nicht_doppelt(monkeypatch):
    aufrufe = []
    monkeypatch.setattr(pb, "candidates", lambda store, title, texts: {s: list(a) for s, a in ABSCHNITTE.items()})

    def chat(**kw):
        aufrufe.append(kw["_feature"])
        if kw["_feature"] == "program_stance":
            return _antwort({"concern": "Eine Zweckentfremdungssatzung beschließen.", "parties": [
                _v("fdp", "against", "lehnen jede Form von Enteignung durch eine Zweckentfremdungssatzung ab"), _v("cdu", "none", None)]})
        return _antwort({"verdicts": [{"nr": 1, "supported": "yes", "specific": "measure"}]})
    monkeypatch.setattr(pb.llm, "chat_complete", chat)
    monkeypatch.setattr("council.plan_judge.cost_usd", lambda resp, model: 0.003)
    kosten = []
    s = _Store()
    d = pb.build_for_template(s, "26/1", stopp=SimpleNamespace(ausgeben=kosten.append))
    assert d["status"] == "ok" and [e["party"] for e in d["payload"]["stances"]] == ["fdp"]
    assert d["payload"]["proposed"] == 1 and d["payload"]["checked"] == 1 and kosten == [pytest.approx(0.009)]
    pb.build_for_template(s, "26/1")
    assert aufrufe == ["program_stance", "program_stance", "program_stance_verify"]    # gleiche Quellenlage: kein neuer Aufruf
    assert pb.build_for_template(s, "26/9") is None


def test_zwei_durchgaenge_werden_vereinigt_widerspruch_faellt_weg():
    a = [_v("fdp", "against", "x"), _v("cdu", "for", "y"), _v("linke", "none", None)]
    b = [_v("fdp", "against", "x2"), _v("fdp", "against", "X"), _v("cdu", "against", "z"), _v("linke", "for", "w")]
    v = pb.vereinige(a, b)
    # FDP mit zwei verschiedenen Zitaten als Alternativen, CDU widerspricht sich, Linke aus dem zweiten Durchgang
    assert [(x["party"], x["stance"], x["quote"]) for x in v] == [("fdp", "against", "x"), ("fdp", "against", "x2"), ("linke", "for", "w")]


def test_je_liste_gilt_das_erste_zitat_das_der_pruefer_laesst(monkeypatch):
    """Die FDP zur Zweckentfremdungssatzung: Das erste Zitat ließ der Prüfer
    nicht gelten („Enteignung durch"), das zweite schon."""
    zwei = dict(ABSCHNITTE)
    zwei["fdp"] = (*ABSCHNITTE["fdp"], {"idx": 1, "page": 9, "text": "In Kürze: Ablehnung von Enteignungen und einer Zweckentfremdungssatzung. Verschlankung der Bauanträge."})
    monkeypatch.setattr(wp, "passages", lambda slug: zwei.get(slug, ()))
    einordnungen = pb.pre_check([
        _v("fdp", "against", "lehnen jede Form von Enteignung durch eine Zweckentfremdungssatzung ab"),
        _v("fdp", "against", "Ablehnung von Enteignungen und einer Zweckentfremdungssatzung"),
        _v("fdp", "against", "Ablehnung von  Enteignungen und einer Zweckentfremdungssatzung")])      # dasselbe Zitat noch einmal
    assert [e["page"] for e in einordnungen] == [8, 9]
    monkeypatch.setattr(pb.llm, "chat_complete", lambda **kw: _antwort({"verdicts": [
        {"nr": 1, "supported": "no", "specific": "measure"}, {"nr": 2, "supported": "yes", "specific": "measure"}]}))
    durch, _ = pb.verify("Zweckentfremdungssatzung", [], "Die Satzung beschließen.", einordnungen, batch=False)
    assert [(e["party"], e["page"]) for e in durch] == [("fdp", 9)]


def test_wahlprogramme_schneiden_ohne_text_zu_verlieren():
    """Die echten Dateien: Jede Liste im Rat mit Programm hat Abschnitte, und ein
    Satz aus dem Programm findet sich wörtlich wieder."""
    import importlib
    echt = importlib.reload(wp)
    listen = echt.lists()
    assert {"spd", "gruene", "cdu", "fdp"} <= {liste["slug"] for liste in listen}
    assert sum(liste["seats"] for liste in listen) >= 45
    assert all(len(echt.passages(liste["slug"])) >= 10 for liste in listen)
    fund = echt.find_quote("fdp", "lehnen jede Form von Enteignung durch eine Zweckentfremdungssatzung ab")
    assert fund and fund["page"] == 8
