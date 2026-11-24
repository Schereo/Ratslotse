"""Was der Haushaltsentwurf zeigt (council/budget_findings.py): Zahlenprobe im
Code, Art je Säule, Prüfung der Deutung, Speichern je Vorbericht. Die Fälle
stammen aus dem Vorbericht zum Haushaltsentwurf 2027 (Anlage 316689)."""
from __future__ import annotations

import json
from datetime import date, timedelta
from types import SimpleNamespace

from council import budget_charts as bc, budget_findings as bf
from council.scraper import AgendaItem, CouncilSession
from council.store import CouncilStore

URL = "https://ratsinfo.oldenburg.de/bi/getfile.asp?id={}&type=do"

ERGEBNIS = bc.Chart(
    number="2.1.1-1", page=10, kind="diagram", title="Entwicklung der Jahresergebnisse",
    caption="2020 – 2025 Ist, 2026 Prognose, 2027 – 2030 Plan (Grafik 2.1.1-1)",
    header=["2024", "2025", "2026", "2027", "2028"],
    rows=[{"label": "Reihe 1", "values": [6.3, -24.8, -64.9, -170.1, -162.6]}])
STEUERN = bc.Chart(
    number="2.2-1", page=14, kind="table", title="Steuern",
    caption="(Grafik 2.2-1)", header=["Ist 2025", "Plan 2027"],
    rows=[{"label": "Gewerbesteuer", "values": [240_912_000.0, 153_400_000.0]},
          {"label": "Grundsteuer B", "values": [52_810_000.0, 54_650_000.0]}])
SEITEN = ["Vorbericht"] * 4 + [
    "Nach Abzug des prognostizierten Fehlbedarfs 2026 von 64,9 Millionen Euro verbleibt eine Rücklage. "
    "Die Stadt Oldenburg wird sich daher ab dem Jahr 2027 in die Haushaltssicherung begeben müssen und hat "
    "ein entsprechendes Haushaltskonsolidierungskonzept aufgestellt."] + ["Vorbericht"] * 4 + [
    "Der Ergebnishaushalt schließt 2027 mit einem Fehlbetrag ab, weil die "
    "Gewerbesteuer deutlich hinter den Erwartungen zurückbleibt."]


def _befund(**anders):
    f = {"title": "2027 sollen rund 170 Mio. € fehlen",
         "text": "Für 2027 plant die Verwaltung rund 170 Mio. € Fehlbetrag; 2025 waren es 24,8 Mio. € (Ist).",
         "key_figure": {"value": -170.1, "unit": "Mio. €", "label": "Fehlbetrag 2027, Plan"},
         "chart": "2.1.1-1", "page": 10, "quote": None,
         "visual": {"type": "columns", "unit": "Mio. €", "categories": ["2025", "2026", "2027"],
                    "series": [{"name": "Jahresergebnis", "values": [-24.8, -64.9, -170.1]}],
                    "stacked": False, "highlight": [2, 9]}}
    f.update(anders)
    return f


def _pruefe(f):
    return bf.check(f, {"2.1.1-1": ERGEBNIS, "2.2-1": STEUERN}, SEITEN, 2027)


def test_art_aus_bildunterschrift_und_kategorie():
    assert bf.kinds(["2025", "2026", "2027", "2028"], ERGEBNIS.caption, 2027) == \
        ["actual", "forecast", "plan", "financial_plan"]
    # Das Wort an der Kategorie schlägt die Unterschrift („2026 Plan/Prognose“).
    assert bf.kinds(["2026 Plan", "2026 Prognose", "Ist 2025"], "2026 Plan/Prognose", 2027) == \
        ["plan", "forecast", "actual"]
    assert bf.kinds(["Gewerbesteuer"], "", 2027) == [None]
    # Die Spalte der Grafik trägt die Art, das Modell schrieb nur das Jahr (Grafik 6-5).
    assert bf.kinds(["2025", "2026", "2027"], "", 2027, ["Ist 2025", "Prognose 2026", "Plan 2027"]) == \
        ["actual", "forecast", "plan"]
    # „bis 2025 Ist-Werte, ab 2026 Planzahlen“ (Grafik 2.4.2.11-1).
    assert bf.kinds(["2024", "2026", "2028"], "bis 2025 Ist-Werte, ab 2026 Planzahlen", 2027) == \
        ["actual", "plan", "financial_plan"]
    # Ohne jeden Hinweis (Grafik 3.1-1): nur was das Haushaltsjahr sicher sagt.
    assert bf.kinds(["2025", "2026", "2027", "2028"], "(Grafik 3.1-1)", 2027) == \
        ["actual", None, "plan", "financial_plan"]


def test_zahl_belegt_auch_umgerechnet_und_gerundet():
    kandidaten = {170_145_721.0, -24.8}
    assert bf.backed(170.1, kandidaten)                       # in Mio. €
    assert not bf.backed(170.0, kandidaten)                   # eine Grafik zeichnet genau
    assert bf.backed(170.0, kandidaten, exact=False)          # „rund 170 Mio. €“ im Satz
    assert bf.backed(24.8, kandidaten, exact=False)           # „24,8 Mio. € Fehlbetrag“
    assert not bf.backed(24.8, kandidaten)                    # aber nicht in der Darstellung
    assert not bf.backed(31.0, kandidaten, exact=False)
    assert bf.text_numbers("2027 rund 170 Mio. €, 2025 −24,8") == [170.0, -24.8]


def test_schranke_im_satz():
    """„über 160 Mio. €“ zu 162,6: eine Schranke, die stimmt. Zu 200 wäre sie
    zu weit weg, zu 158 falsch (Probelauf 23.11.2026: der wichtigste Befund
    fiel an genau dieser Formulierung)."""
    assert bf.text_claims("Ab 2027 fehlen jedes Jahr über 160 Mio. €, knapp 25 Mio. €") == [
        (160.0, "above"), (25.0, "below")]
    assert bf.bounded(160.0, "above", {-162.6})
    assert not bf.bounded(160.0, "above", {-200.3}) and not bf.bounded(160.0, "above", {-158.0})
    assert bf.bounded(25.0, "below", {-24.8})
    f, grund = _pruefe(_befund(title="Ab 2027 fehlen jedes Jahr über 160 Mio. €"))
    assert grund is None, grund
    assert _pruefe(_befund(title="Ab 2027 fehlen jedes Jahr über 120 Mio. €"))[1] == \
        "Zahl 120.0 in Titel oder Satz nicht belegt"


def test_gepruefter_befund_bekommt_die_art_vom_code():
    f, grund = _pruefe(_befund())
    assert grund is None
    assert f["visual"]["kinds"] == ["actual", "forecast", "plan"]
    assert f["visual"]["highlight"] == [2]                    # Index 9 gibt es nicht


def test_unbelegte_zahl_kippt_den_befund():
    assert _pruefe(_befund(text="Für 2027 plant die Verwaltung 180 Mio. € Fehlbetrag."))[1] == \
        "Zahl 180.0 in Titel oder Satz nicht belegt"
    v = _befund()["visual"] | {"series": [{"name": "x", "values": [-24.8, -64.9, -171.0]}]}
    assert "nicht belegt" in _pruefe(_befund(visual=v))[1]
    assert _pruefe(_befund(chart="9-9"))[1].startswith("Grafik 9-9 gibt es nicht")
    assert _pruefe(_befund(key_figure={"value": 99.0}))[1] == "Kennzahl nicht belegt"


def test_differenz_und_summe_derselben_grafik_sind_belegt():
    f, grund = bf.check(_befund(
        title="Die Gewerbesteuer soll um 87,5 Mio. € sinken",
        text="Für 2027 sind 153,4 Mio. € eingeplant, 2025 kamen 240,9 Mio. € herein.",
        key_figure={"value": -87.5, "unit": "Mio. €", "label": "Veränderung"}, chart="2.2-1", page=14,
        visual={"type": "bars", "unit": "Mio. €", "rows": [
            {"label": "Gewerbesteuer", "value": 153.4, "change": -87.5},
            {"label": "Gewerbe- und Grundsteuer B", "value": 208.05, "change": None}]}),
        {"2.2-1": STEUERN}, SEITEN, 2027)
    assert grund is None, grund


def test_bruecke_muss_aufgehen():
    brücke = {"type": "bridge", "unit": "Mio. €", "start": {"label": "2026", "value": -64.9},
              "steps": [{"label": "Gewerbesteuer", "value": -87.5}, {"label": "übrige", "value": -17.7}],
              "end": {"label": "2027", "value": -170.1}}
    zahlen = {"2.1.1-1": bc.Chart(**{**ERGEBNIS.as_dict(), "rows": ERGEBNIS.rows + [
        {"label": "Gewerbesteuer", "values": [None, None, None, -87.5, None]}]})}
    assert bf.check(_befund(visual=brücke), zahlen, SEITEN, 2027)[1] is None
    kaputt = brücke | {"steps": [{"label": "Gewerbesteuer", "value": -87.5}]}
    assert bf.check(_befund(visual=kaputt), zahlen, SEITEN, 2027)[1] == "Brücke geht nicht auf"


def test_zitat_muss_woertlich_auf_einer_seite_stehen():
    zitat = "weil die Gewerbesteuer deutlich hinter den Erwartungen zurückbleibt"
    f, grund = _pruefe(_befund(quote=zitat, page=3))
    assert grund is None and f["page"] == 10 and f["quote_page"] == 10   # Seite der Grafik, Seite des Zitats
    assert _pruefe(_befund(quote="weil die Personalkosten stark gestiegen sind"))[1] == "Zitat steht nicht im Text"


def _antwort(inhalt: dict):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(inhalt)))],
                           usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=100))


def test_erzeugen_prueft_zahlen_dann_deutung(monkeypatch):
    zweiter = _befund(title="Noch einmal das Ergebnis")
    erfunden = _befund(title="Erfunden", text="Es fehlen 999 Mio. €.")
    deutung_falsch = _befund(title="Die Gewerbesteuer bricht ein", chart="2.2-1", page=14,
                             text="2027 sind 153,4 Mio. € eingeplant.",
                             key_figure={"value": 153.4, "unit": "Mio. €", "label": "Plan 2027"},
                             visual={"type": "bars", "unit": "Mio. €",
                                     "rows": [{"label": "Gewerbesteuer", "value": 153.4}]})
    aufrufe = []

    def antwort(**kw):
        aufrufe.append(kw["_feature"])
        if kw["_feature"] == "budget_findings":
            assert "HAUSHALTSJAHR: 2027" in kw["messages"][1]["content"]
            return _antwort({"findings": [_befund(), zweiter, erfunden, deutung_falsch], "overview": {}})
        ok = "bricht ein" not in kw["messages"][1]["content"].split("MATERIAL")[0]
        return _antwort({"correct": ok, "reason": "" if ok else "Wertung „bricht ein“"})

    monkeypatch.setattr(bf.llm, "chat_complete", antwort)
    payload, kosten = bf.generate([ERGEBNIS, STEUERN], SEITEN, "Haushalt 2027", 2027)
    assert [f["title"] for f in payload["findings"]] == [_befund()["title"]]
    assert [(r["stage"], r["reason"]) for r in payload["rejected"]] == [
        ("numbers", "zweiter Befund zur selben Grafik"),
        ("numbers", "Zahl 999.0 in Titel oder Satz nicht belegt"),
        ("reading", "Wertung „bricht ein“")]
    assert aufrufe.count("budget_findings_verify") == 2 and kosten > 0


def test_gesamtbild_satz_braucht_woertliches_zitat_und_seine_zahlen():
    """Tim, 24.11.2026: „dass die Stadt in die Haushaltskonsolidierung rutscht“
    gehört an den Anfang — steht im Vorbericht 2027 auf S. 5."""
    zitat = "Die Stadt Oldenburg wird sich daher ab dem Jahr 2027 in die Haushaltssicherung begeben müssen"
    s, grund = bf.check_statement({"text": "Ab 2027 muss die Stadt in die Haushaltssicherung.", "quote": zitat,
                                   "page": 2}, SEITEN)
    assert grund is None and s["page"] == 5                    # die Seite berichtigt
    assert bf.check_statement({"text": "Ab 2027 Haushaltssicherung.", "quote": None}, SEITEN)[1] == "Satz ohne Zitat"
    assert bf.check_statement({"text": "Die Rücklage ist weg.", "quote": "Die Rücklage ist vollständig aufgebraucht worden"},
                              SEITEN)[1] == "Zitat steht nicht im Text"
    # Eine Zahl im Satz, die nicht im Zitat steht — auch wenn sie anderswo stimmen mag.
    assert bf.check_statement({"text": "2026 fehlen 70 Mio. €, danach folgt die Haushaltssicherung.",
                               "quote": "Nach Abzug des prognostizierten Fehlbedarfs 2026 von 64,9 Millionen Euro"},
                              SEITEN)[1] == "Zahl 70.0 im Satz steht nicht im Zitat"


def test_haushaltssicherung_steht_woertlich_oben():
    """Ohne Modell: der erste ganze Satz der Überblicksseiten, der sie nennt."""
    assert bf.notice(SEITEN) == {"page": 5, "text": (
        "Die Stadt Oldenburg wird sich daher ab dem Jahr 2027 in die Haushaltssicherung begeben müssen und hat "
        "ein entsprechendes Haushaltskonsolidierungskonzept aufgestellt.")}
    # „31.12.“ beendet keinen Satz.
    assert bf.notice(["Bis zum 31. 12. 2026 reicht die Rücklage. Danach folgt die Haushaltssicherung für die Stadt."]) \
        == {"page": 1, "text": "Danach folgt die Haushaltssicherung für die Stadt."}
    assert bf.notice(["Kein Wort davon."]) is None
    assert bf.notice(["Die Stadt muss ab 2027 in die Haushaltssicherung und hat ein Konzept aufgestellt. 7"])["text"] \
        .endswith("aufgestellt.")


def test_eckzahl_aus_grafik_oder_zitat():
    f, grund = bf.check_fact({"label": "Jahresergebnis 2027, Plan", "value": -170.1, "unit": "Mio. €",
                              "chart": "2.1.1-1"}, {"2.1.1-1": ERGEBNIS}, SEITEN)
    assert grund is None and f["page"] == 10
    f, grund = bf.check_fact({"label": "Fehlbedarf 2026, Prognose", "value": 64.9, "unit": "Mio. €", "chart": None,
                              "quote": "Nach Abzug des prognostizierten Fehlbedarfs 2026 von 64,9 Millionen Euro"},
                             {}, SEITEN)
    assert grund is None and f["page"] == 5
    assert bf.check_fact({"label": "Investitionen 2027", "value": 154.0, "unit": "Mio. €", "chart": "2.1.1-1"},
                         {"2.1.1-1": ERGEBNIS}, SEITEN)[1] == "Wert 154.0 nicht belegt"


def test_gesamtbild_ein_pruefaufruf_fuer_alles(monkeypatch):
    aufrufe = []

    def antwort(**kw):
        aufrufe.append(kw["_feature"])
        return _antwort({"verdicts": [{"id": "s0", "correct": True}, {"id": "s1", "correct": False, "reason": "Ursache erfunden"},
                                      {"id": "f0", "correct": True}]})

    monkeypatch.setattr(bf.llm, "chat_complete", antwort)
    zitat = "Die Stadt Oldenburg wird sich daher ab dem Jahr 2027 in die Haushaltssicherung begeben müssen"
    roh = {"statements": [{"text": "Ab 2027 muss die Stadt in die Haushaltssicherung.", "quote": zitat, "page": 5},
                          {"text": "Schuld ist die Gewerbesteuer.", "quote": zitat, "page": 5}],
           "facts": [{"label": "Jahresergebnis 2027, Plan", "value": -170.1, "unit": "Mio. €", "chart": "2.1.1-1"}]}
    gesamt, weg, kosten = bf.overview(roh, {"2.1.1-1": ERGEBNIS}, SEITEN)
    assert aufrufe == ["budget_findings_verify"]
    assert [s["text"] for s in gesamt["statements"]] == ["Ab 2027 muss die Stadt in die Haushaltssicherung."]
    assert [f["label"] for f in gesamt["facts"]] == ["Jahresergebnis 2027, Plan"]
    assert [w["stage"] for w in weg] == ["reading"]
    # Hält kein Satz, gibt es kein Gesamtbild — Eckzahlen allein stehen nicht da.
    monkeypatch.setattr(bf.llm, "chat_complete", lambda **kw: _antwort({"verdicts": [{"id": "f0", "correct": True}]}))
    assert bf.overview(roh, {"2.1.1-1": ERGEBNIS}, SEITEN)[0] is None


def test_unklares_urteil_verwirft(monkeypatch):
    def antwort(**kw):
        if kw["_feature"] == "budget_findings":
            return _antwort({"findings": [_befund()]})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="kein JSON"))], usage=None)

    monkeypatch.setattr(bf.llm, "chat_complete", antwort)
    payload, _ = bf.generate([ERGEBNIS], SEITEN, "Haushalt 2027", 2027)
    assert payload["findings"] == [] and payload["rejected"][0]["stage"] == "reading"


def _sitzung():
    tag = (date.today() + timedelta(days=5)).isoformat()
    punkt = AgendaItem(item_number="Ö 7", title="Haushalt 2027 - Verwaltungsentwurf - Bericht",
                       template_number="26/0835", kvonr=None, is_public=True,
                       anlagen=[{"label": "2027 001 Vw Vorbericht Haushalt 2027 Verwaltungsentwurf",
                                 "url": URL.format(316689)},
                                {"label": "2027 002 Vw Ergebnishaushalt", "url": URL.format(316690)}])
    return CouncilSession(ksinr=4642, committee="Rat", session_date=tag, session_time="17:00",
                          location="PFL", agenda_items=[punkt])


def test_vorbericht_finden_erzeugen_speichern_anzeigen(tmp_path, monkeypatch):
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        store.save_session(_sitzung())
        berichte = store.budget_reports((date.today() - timedelta(days=3)).isoformat())
        assert [(b["document_id"], b["title"]) for b in berichte] == [
            (316689, "Haushalt 2027 - Verwaltungsentwurf - Bericht")]
        assert bf.budget_year_of(berichte[0]["label"], berichte[0]["title"]) == 2027

        monkeypatch.setattr(bf.bc, "from_pdf", lambda data: [ERGEBNIS])
        from council import anlagentext
        monkeypatch.setattr(anlagentext, "pdf_seiten", lambda data, extraktor=None: SEITEN)
        erzeugt = []
        monkeypatch.setattr(bf, "generate", lambda *a, **kw: (erzeugt.append(a) or {"findings": [_befund()]}, 0.02))
        laden = []
        bf.build_for_report(store, berichte[0], download=lambda url: laden.append(url) or b"%PDF")
        assert laden == [URL.format(316689)] and len(erzeugt) == 1
        bf.build_for_report(store, berichte[0], download=lambda url: laden.append(url) or b"%PDF")
        assert len(laden) == 1                                # gespeichert, kein zweiter Abruf

        sicht = store.item_budget_findings(4642, "Ö 7")
        assert sicht["document_id"] == 316689 and sicht["budget_year"] == 2027
        assert sicht["about"] == bf.ABOUT and "overview" not in sicht
        assert sicht["findings"][0]["title"] == _befund()["title"]
    finally:
        store.close()


def test_vorbericht_ohne_lesbare_grafik_wird_vermerkt(tmp_path, monkeypatch):
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        store.save_session(_sitzung())
        bericht = store.budget_reports()[0]
        monkeypatch.setattr(bf.bc, "from_pdf", lambda data: [bc.Chart(number="1-1", page=3, caption="", kind="image")])
        from council import anlagentext
        monkeypatch.setattr(anlagentext, "pdf_seiten", lambda data, extraktor=None: SEITEN)
        assert bf.build_for_report(store, bericht, download=lambda url: b"%PDF") is None
        assert store.budget_draft_findings(316689)["status"] == "no_charts"
        assert store.item_budget_findings(4642, "Ö 7") is None
    finally:
        store.close()


def test_nur_vorberichte_mit_genug_seiten():
    assert bf.is_budget_report("2027 001 Vw Vorbericht Haushalt 2027", None)
    assert bf.is_budget_report("Anlage 2 Vorbericht", 92)
    assert not bf.is_budget_report("Vorbericht zur Sitzung", 3)
    assert not bf.is_budget_report("Ergebnishaushalt", 300)
