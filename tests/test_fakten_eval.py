"""Die Fakten-Eval ohne Modell: Fallformat, Mitschnitt-Leser, Bericht.

Die Abgleich-Regeln selbst prüft ``tests/test_fakten_abgleich.py``; hier geht
es um das, was drumherum schiefgehen kann — ein Fall ohne Quelle, eine Route,
die es nicht gibt, ein Mitschnitt, der dem falschen Fall zugeordnet wird.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from eval import fakten_abgleich as fa  # noqa: E402
from eval import run_fakten as rf  # noqa: E402
from kern import knowledge  # noqa: E402

HAUSHALT = WURZEL / "eval" / "cases_fakten_haushalt.json"


@pytest.fixture(scope="module")
def faelle() -> list[dict]:
    return json.loads(HAUSHALT.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Das Fallformat (Spezifikation vom 23.09.2026)
# --------------------------------------------------------------------------- #

def test_pflichtfelder_und_eindeutige_ids(faelle):
    ids = [f["id"] for f in faelle]
    assert len(ids) == len(set(ids))
    for f in faelle:
        assert f["kanal"] in ("lotti", "rat"), f["id"]
        assert f["frage"].strip() and f["kategorie"].startswith("haushalt/"), f["id"]
        assert isinstance(f["antwort_in_daten"], bool), f["id"]
        assert f.get("baustein"), f"{f['id']}: ohne Baustein fällt der Kontextfehler aus der Liste"


def test_jeder_goldfakt_hat_quelle_und_zahl(faelle):
    for f in faelle:
        for g in f["gold"]:
            assert g["art"] in ("zahl", "text", "id"), f["id"]
            assert g.get("quelle"), f"{f['id']}: Goldfakt ohne Quelle"
            if g["art"] == "zahl":
                assert isinstance(g["wert"], (int, float)), f["id"]
                for alt in g.get("oder") or []:
                    assert isinstance(alt["wert"], (int, float)) and alt.get("quelle"), f["id"]
            if g["art"] == "text":
                assert g["muss"], f["id"]
        for v in f["verboten"]:
            assert isinstance(v["wert"], (int, float)) and v.get("grund"), f["id"]


def test_fall_mit_antwort_hat_pflichtgold(faelle):
    """Ein beantwortbarer Fall ohne Pflicht-Goldfakt wäre immer „ok“."""
    for f in faelle:
        if f["antwort_in_daten"]:
            assert any(g.get("pflicht", True) for g in f["gold"]), f["id"]


def test_lotti_routen_gibt_es(faelle):
    for f in faelle:
        if f["kanal"] == "lotti":
            assert knowledge.fuer_route(f["route"]) is not None, f"{f['id']}: {f['route']}"
            assert f["route"] not in knowledge.OHNE_ERKLAERUNG, f["id"]


def test_verteilung_wie_beauftragt(faelle):
    """~60 % Lotti, ~15 Fälle ohne Antwort in den Daten, alle Haushaltsseiten."""
    lotti = sum(1 for f in faelle if f["kanal"] == "lotti")
    assert 0.5 <= lotti / len(faelle) <= 0.7
    assert sum(1 for f in faelle if not f["antwort_in_daten"]) >= 12
    seiten = {r for r in knowledge.PAGES if knowledge.im_haushalt(r)}
    fehlend = seiten - {f.get("route") for f in faelle} - {"/haushalt/labor", "/haushalt/bereich"}
    assert not fehlend, f"Haushaltsseiten ohne Lotti-Fall: {sorted(fehlend)}"


def test_goldwerte_sind_keine_modellantworten():
    """Die Goldwerte kommen aus SQL (build_fakten_haushalt.py), nie aus dem
    Kontext, den die Eval prüft — sonst prüfte sie ihn gegen sich selbst."""
    quelltext = (WURZEL / "eval" / "build_fakten_haushalt.py").read_text(encoding="utf-8")
    assert "from council" not in quelltext and "import qa" not in quelltext


# --------------------------------------------------------------------------- #
# Mitschnitt und Zuordnung
# --------------------------------------------------------------------------- #

def test_mitschnitt_liest_nur_neue_zeilen(tmp_path):
    (tmp_path / "qa_answer.jsonl").write_text(json.dumps({"ts": 1, "feature": "qa_answer"}) + "\n")
    m = rf.Mitschnitt(tmp_path)
    assert len(m.neu()) == 1
    assert m.neu() == []
    with (tmp_path / "qa_answer.jsonl").open("a") as f:
        f.write(json.dumps({"ts": 2, "feature": "qa_answer"}) + "\n")
    (tmp_path / "qa_analysis.jsonl").write_text(json.dumps({"ts": 1.5, "feature": "qa_analysis"}) + "\n")
    assert [z["ts"] for z in m.neu()] == [1.5, 2]


def test_der_antwortende_aufruf_ist_der_letzte_vollstaendige():
    aufrufe = [{"feature": "qa_analysis"}, {"feature": "qa_answer", "aborted": True, "n": 1},
               {"feature": "qa_answer", "n": 2}]
    assert rf._antwort_aufruf(aufrufe)["n"] == 2
    assert rf._antwort_aufruf([{"feature": "qa_analysis"}]) is None


def test_prompt_text_nimmt_alle_nachrichten():
    text = rf.prompt_text({"messages": [{"role": "system", "content": "A"},
                                        {"role": "user", "content": [{"text": "B"}]}]})
    assert "A" in text and "B" in text


def test_kopfzeilen_finden_die_bausteine():
    kontext = ("SCHULDENSTAND (Statistisches Jahrbuch). Das ist ein Bestand\n- x: 1 €\n"
               "INVESTITIONEN — TATSÄCHLICH ABGEFLOSSEN (Tabelle 1107-1)\n")
    assert rf._kopfzeilen(kontext)[:2] == ["SCHULDENSTAND", "INVESTITIONEN"]


# --------------------------------------------------------------------------- #
# Bericht
# --------------------------------------------------------------------------- #

def _lauf(modell: str, zeilen: list[dict]) -> dict:
    return {"modell": modell, "zeitstempel": "x", "faelle": zeilen,
            "kennzahlen": rf.kennzahlen(zeilen)}


def test_kontextfehler_werden_nach_baustein_gruppiert():
    fall = {"id": "a", "kanal": "rat", "frage": "Wie hoch?", "kategorie": "haushalt/schulden",
            "baustein": "store.schulden_kontext", "bekannt": "Fix unterwegs",
            "gold": [{"art": "zahl", "wert": 40_804_000, "jahr": 2025, "quelle": "q"}]}
    kontext = "Kopf 2025:\n- Ein Jahr davor (2024): 1 €\n  - davon Kredit: 40.804.000 €"
    zeile = {"id": "a", "kanal": "rat", "kategorie": "haushalt/schulden", "frage": "Wie hoch?",
             "antwort": "", "weg": "ask", "ms": 1, **fa.bewerten(fall, kontext, "")}
    assert zeile["fehlerart"] == "kontext_falsch_zugeordnet"
    gruppen = rf.kontextfehler([_lauf("m", [zeile])], [fall])
    (eintrag,) = gruppen["store.schulden_kontext"]
    assert eintrag["jahre"] == [[2024]] and eintrag["bekannt"]
    text = rf.bericht_teil([_lauf("m", [zeile])], [fall])
    assert "store.schulden_kontext" in text and "bekannt, Fix unterwegs" in text


def test_arbeitsliste_nimmt_je_fall_den_neuesten_stand():
    """Ein Teillauf nach einem Kontext-Nachzug (nur die Haushaltsfälle)
    überstimmt den älteren Gesamtlauf für SEINE Fälle — die übrigen Fälle
    behalten ihren Befund aus dem Gesamtlauf. Zwei Läufe desselben Stands
    („nach K1, Lauf 1" und „…, Lauf 2") zählen beide."""
    faelle = [{"id": i, "kanal": "rat", "frage": "?", "kategorie": "k", "baustein": "b",
               "gold": [{"art": "zahl", "wert": 5, "quelle": "q"}]} for i in ("hh", "rat")]
    fehlt = {"fehlerart": "kontext_fehlt", "kanal": "rat", "frage": "?", "weg": "ask",
             "kontext_ok": False, "antwort_ok": False, "ms": 1, "erfunden": [],
             "gold": [{"fakt": "x", "kontext": {"status": "fehlt", "fundstellen": [],
                                                "jahre": []}}]}
    ok = {**fehlt, "fehlerart": "ok", "kontext_ok": True, "antwort_ok": True}

    def lauf(stempel, etikett, zeilen):
        return {**_lauf("m", zeilen), "zeitstempel": stempel, "etikett": etikett}
    alt = lauf("20260923-08", "nach #1493", [{**fehlt, "id": "hh"}, {**fehlt, "id": "rat"}])
    neu1 = lauf("20260923-12", "nach K1, Lauf 1", [{**ok, "id": "hh"}])
    neu2 = lauf("20260923-13", "nach K1, Lauf 2", [{**ok, "id": "hh"}])
    ids = [e["id"] for es in rf.kontextfehler([alt, neu1, neu2], faelle).values() for e in es]
    assert ids == ["rat"]
    # Fehlt der Fakt in EINEM der beiden neuen Läufe, steht der Fall drauf.
    neu2 = lauf("20260923-13", "nach K1, Lauf 2", [{**fehlt, "id": "hh"}])
    ids = [e["id"] for es in rf.kontextfehler([alt, neu1, neu2], faelle).values() for e in es]
    assert sorted(ids) == ["hh", "rat"]


def test_bericht_ersetzt_nur_den_erzeugten_teil(tmp_path):
    ziel = tmp_path / "b.md"
    ziel.write_text(f"# Kopf\nvon Hand\n\n{rf.MARKE_AN}\nalt\n{rf.MARKE_AUS}\n\nFuß von Hand\n")
    rf.bericht_schreiben([], [], ziel)
    text = ziel.read_text()
    assert "von Hand" in text and "Fuß von Hand" in text and "\nalt\n" not in text
