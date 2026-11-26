"""Die Zahl der Woche (council/week_number.py): ein Lauf für alle Quellen.

Tim, 25.11.2026: Vorlagentitel und Befund-Sätze sind „keine Alltagssprache“,
und statt zweier Lösungen soll es ein System geben, das täglich läuft. Was
hier festgehalten wird:

* Kandidaten kommen aus Beschluss-Beträgen (nur angenommene), dem
  Haushaltsentwurf (nur mit Schalter) und der Zahl der Beschlüsse.
* Den Satz schreibt das Modell; Zahl, Einheit, Jahr und Fachwörter hält der Code.
* Neu gewählt wird nur, wenn sich die Kandidaten ändern — sonst kein Aufruf.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from council import week_number as wn
from council.scraper import AgendaItem, CouncilSession
from council.store import CouncilStore

HEUTE = date(2026, 11, 25)
@pytest.fixture
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    yield s
    s.close()


def _beschluss(store, i: int, betrag: float, outcome: str = "accepted", tag: date = HEUTE - timedelta(days=2)):
    store.save_session(CouncilSession(100 + i, "Ausschuss für Finanzen und Beteiligungen", tag.isoformat(),
                                      "17:00", "Rathaus"))
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_decisions (id,ksinr,position,item_number,title,outcome,kind,amount_eur,"
            "simple_summary) VALUES (?,?,1,'4',?,?,'decision',?,?)",
            (i, 100 + i, f"Überplanmäßige Bewilligung {i}", outcome, betrag,
             "Die Stadt gibt für StartJob mehr aus als geplant."))


def test_kandidaten_aus_allen_quellen(store, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "")
    _beschluss(store, 1, 59000)
    _beschluss(store, 2, 9e6, outcome="rejected")       # abgelehnt: kein Geld, das fließt
    ids = [c["id"] for c in wn.candidates(store, HEUTE)]
    assert ids == ["d1", "c7"]


@pytest.mark.parametrize("raw, grund", [
    ({"id": "d1", "value": 59000, "unit": "Euro", "sentence": "So viel gibt die Stadt zusätzlich für StartJob aus."},
     None),
    ({"id": "c7", "value": 1, "unit": "Beschlüsse", "sentence": "So viele Beschlüsse gab es diese Woche."}, None),
    ({"id": "d1", "value": 59000, "unit": "€", "sentence": "So viel wurde überplanmäßig bewilligt."}, "Fachwort"),
    ({"id": "d1", "value": 59000, "unit": "€", "sentence": "So viel, also 59.000 €, für StartJob."}, "wiederholt"),
    ({"id": "d1", "value": 60000, "unit": "€", "sentence": "So viel gibt die Stadt für StartJob aus."}, "steht nicht"),
    ({"id": "d1", "value": 59000, "unit": "%", "sentence": "So viel gibt die Stadt für StartJob aus."}, "Einheit"),
    ({"id": "d1", "value": 59000, "unit": "€", "sentence": "So viel gibt die Stadt 2026 für StartJob aus."}, None),
    ({"id": "d1", "value": 59000, "unit": "€", "sentence": "So viel gibt die Stadt 2025 für StartJob aus."},
     "Jahr steht nicht"),
    ({"id": "d1", "value": 59000, "unit": "€", "sentence": "Die Stadt gibt mehr für StartJob aus."}, "So viel"),
    ({"id": "c7", "value": 1, "unit": "Beschlüsse",
      "sentence": "So viele Beschlüsse fassten Rat und Ausschüsse in den letzten 7 Tagen."}, None),
    ({"id": "c7", "value": 1, "unit": "Beschlüsse",
      "sentence": "So viele Beschlüsse fassten Rat und Ausschüsse in den letzten 14 Tagen."}, "steht nicht"),
    ({"id": "x9", "value": 1, "unit": "€", "sentence": "So viel."}, "unbekannt"),
])
def test_satz_wird_im_code_geprueft(store, monkeypatch, raw, grund):
    _beschluss(store, 1, 59000)
    karte, warum = wn.check(raw, wn.candidates(store, HEUTE))
    if grund is None:
        assert warum is None and karte["sentence"] == raw["sentence"]
    else:
        assert karte is None and grund in warum


def test_karten_behalten_die_arten_der_app(store, monkeypatch):
    """Beschluss und Anzahl kommen in den Arten, die die ausgelieferte App kennt."""
    _beschluss(store, 1, 59000)
    cands = wn.candidates(store, HEUTE)
    karte, _ = wn.check({"id": "d1", "value": 59000, "unit": "€",
                         "sentence": "So viel gibt die Stadt zusätzlich für StartJob aus."}, cands)
    assert karte == {"kind": "amount", "amount_eur": 59000.0, "decision_id": 1, "title": "Überplanmäßige Bewilligung 1",
                     "sentence": "So viel gibt die Stadt zusätzlich für StartJob aus.",
                     "session_date": (HEUTE - timedelta(days=2)).isoformat(), "window_days": 7}


def _antworten(monkeypatch, *antworten):
    folge = iter(antworten)
    aufrufe = []

    def chat(**kw):
        aufrufe.append(kw)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(next(folge))))])
    monkeypatch.setattr(wn.llm, "chat_complete", chat)
    monkeypatch.setattr(wn, "cost_usd", lambda resp, model: 0.007)
    return aufrufe


def test_lauf_waehlt_nur_bei_neuem_kandidaten(store, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "")
    _beschluss(store, 1, 59000)
    gut = {"id": "d1", "value": 59000, "unit": "€", "sentence": "So viel gibt die Stadt zusätzlich für StartJob aus."}
    aufrufe = _antworten(monkeypatch, {"id": "d1", "value": 1, "unit": "€", "sentence": "So viel."}, gut)
    assert wn.run(store, HEUTE)["neu"] == 1 and len(aufrufe) == 2      # erster Vorschlag fiel durch
    assert store.latest_week_number(HEUTE.isoformat())["payload"]["sentence"] == gut["sentence"]

    assert wn.run(store, HEUTE + timedelta(days=1)) == {"kandidaten": 2, "neu": 0}   # nichts Neues: kein Aufruf
    assert len(aufrufe) == 2

    _beschluss(store, 3, 120000, tag=HEUTE)
    aufrufe = _antworten(monkeypatch, {"id": "d3", "value": 120000, "unit": "€",
                                       "sentence": "So viel kostet der neue Spielplatz."})
    assert wn.run(store, HEUTE + timedelta(days=1))["neu"] == 1 and len(aufrufe) == 1
    assert store.latest_week_number(HEUTE.isoformat())["payload"]["decision_id"] == 3


def test_lauf_ohne_gueltigen_vorschlag_speichert_nichts(store, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "")
    _beschluss(store, 1, 59000)
    _antworten(monkeypatch, *[{"id": "d1", "value": 59000, "unit": "€", "sentence": "Überplanmäßige Bewilligung."}] * 2)
    assert wn.run(store, HEUTE)["verworfen"] == 1
    assert store.latest_week_number("2000-01-01") is None


# ---- Haushaltsentwurf (Schalter haushaltsentwurf-befunde) ------------------------

VORBERICHT = {"findings": [{"key_figure": {"value": -200.3, "unit": "Mio. €", "label": "Fehlbedarf 2030, Plan"},
                            "title": "Laut Plan bleibt das Jahresergebnis bis 2030 negativ", "text": "…"}],
              "overview": {"facts": [{"value": 939.1, "unit": "Mio. €",
                                      "label": "Ordentliche Aufwendungen 2027, Plan"}],
                           "statements": [{"text": "Für 2027 plant die Stadt ein negatives Jahresergebnis von "
                                                   "rund 170,1 Mio. €.", "quote": "…"}]},
              "budget_year": 2027}


def _vorbericht(store, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "haushaltsentwurf-befunde")
    punkt = AgendaItem(item_number="Ö 7", title="Haushalt 2027 - Verwaltungsentwurf - Bericht",
                       template_number="26/0835", kvonr=None, is_public=True,
                       anlagen=[{"label": "2027 001 Vw Vorbericht Haushalt 2027",
                                 "url": "https://ratsinfo.oldenburg.de/bi/getfile.asp?id=316689&type=do"}])
    store.save_session(CouncilSession(ksinr=4642, committee="Ausschuss für Finanzen und Beteiligungen",
                                      session_date=(HEUTE - timedelta(days=2)).isoformat(), session_time="17:00",
                                      location="PFL", agenda_items=[punkt]))
    store.save_budget_draft_findings(316689, "h", status="ok", payload=VORBERICHT, model="m", verify_model="v",
                                     cost_usd=0.05, prompt_version=2)


def test_haushaltsentwurf_nur_mit_schalter(store, monkeypatch):
    _beschluss(store, 1, 59000)
    _vorbericht(store, monkeypatch)
    ids = [c["id"] for c in wn.candidates(store, HEUTE)]
    assert ids[:3] == ["h316689b0", "h316689e0", "h316689s0"] and "d1" in ids
    monkeypatch.setenv("FEATURE_FLAGS", "")
    assert not any(c["kind"] == "budget" for c in wn.candidates(store, HEUTE))


@pytest.mark.parametrize("raw, grund", [
    ({"id": "h316689s0", "value": 170.1, "unit": "Mio. €",
      "sentence": "So viel mehr will die Stadt 2027 ausgeben, als sie einnimmt."}, None),
    ({"id": "h316689e0", "value": 939.1, "unit": "Mio. €", "sentence": "So viel Geld will die Stadt 2027 ausgeben."},
     None),
    ({"id": "h316689b0", "value": 200.3, "unit": "Mio. €", "sentence": "So viel soll der Fehlbedarf 2030 betragen."},
     "Fachwort"),
    ({"id": "h316689s0", "value": 171, "unit": "Mio. €", "sentence": "So viel soll der Stadt 2027 fehlen."},
     "steht nicht"),
    ({"id": "h316689s0", "value": 170.1, "unit": "Mio. €", "sentence": "So viel soll der Stadt 2028 fehlen."},
     "Jahr steht nicht"),
    ({"id": "h316689s0", "value": 170.1, "unit": "Mio. €", "sentence": "So viel soll der Stadt fehlen."}, "Jahr fehlt"),
    ({"id": "h316689e0", "value": 939.1, "unit": "%", "sentence": "So viel Geld will die Stadt 2027 ausgeben."},
     "Einheit"),
])
def test_haushaltssatz_wird_geprueft(store, monkeypatch, raw, grund):
    _vorbericht(store, monkeypatch)
    karte, warum = wn.check(raw, wn.candidates(store, HEUTE))
    if grund is None:
        assert warum is None and karte["kind"] == "budget_draft" and karte["sentence"] == raw["sentence"]
        assert (karte["ksinr"], karte["item_number"], karte["budget_year"]) == (4642, "Ö 7", 2027)
    else:
        assert karte is None and grund in warum
