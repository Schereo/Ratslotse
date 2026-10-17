"""Nachrecherche der KI-Frage: einmal gezielt nachsuchen, wenn etwas fehlt.

Anlass (Auswertung 16.10.2026): Die Suche lief genau einmal. „Wie viel
kostet der kostenlose Bus Samstag?“ — die Vorlagen sagen „Samstagsfahrten“;
der Stadion-Vergabe-Beschluss vom 01.06.2026 war gar nicht unter den
Treffern. Im Gold-Set fehlte bei 28 % der verfehlten Fakten das Material.
Diese Tests halten die Regeln fest, ohne Modell und ohne Embeddings.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from council import qa


def _modell(monkeypatch, antwort):
    gesehen: list[str] = []

    def chat(**kw):
        gesehen.append(kw["messages"][0]["content"])
        inhalt = antwort if isinstance(antwort, str) else json.dumps(antwort)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=inhalt))],
                               usage=None)
    monkeypatch.setattr(qa.llm, "chat_complete", chat)
    return gesehen


_TREFFER = [{"id": 1, "title": "Kostenloser ÖPNV an Samstagen – Bericht", "committee": "Verkehrsausschuss",
             "session_date": "2025-09-10"}]


def test_das_modell_sieht_frage_und_titel_und_nennt_anfragen(monkeypatch):
    gesehen = _modell(monkeypatch, {"suchen": ["Samstagsfahrten ÖPNV Ausgleich", "SEB Endbericht"]})
    anfragen = qa.nachrecherche_anfragen("Wie viel kostet der kostenlose Bus Samstag pro Jahr?", _TREFFER)
    assert anfragen == ["Samstagsfahrten ÖPNV Ausgleich", "SEB Endbericht"]
    assert "Kostenloser ÖPNV an Samstagen" in gesehen[0] and "Verkehrsausschuss" in gesehen[0]


def test_hoechstens_drei_ohne_dubletten_und_ohne_die_frage_selbst(monkeypatch):
    frage = "Was kostet das Stadion?"
    _modell(monkeypatch, {"suchen": ["A", "A", frage, "B", "C", "D"]})
    assert qa.nachrecherche_anfragen(frage, _TREFFER) == ["A", "B", "C"]


def test_jeder_fehler_heisst_keine_nachrecherche(monkeypatch):
    _modell(monkeypatch, "kein json")
    assert qa.nachrecherche_anfragen("Frage?", _TREFFER) == []
    _modell(monkeypatch, {"suchen": "kein array"})
    assert qa.nachrecherche_anfragen("Frage?", _TREFFER) == []

    def kaputt(**kw):
        raise TimeoutError
    monkeypatch.setattr(qa.llm, "chat_complete", kaputt)
    assert qa.nachrecherche_anfragen("Frage?", _TREFFER) == []


def test_neue_funde_rutschen_nach_score_ein_die_erste_liste_bleibt_geordnet():
    erste = [{"id": 1, "score": 0.9}, {"id": 2, "score": 0.4}, {"id": 3, "score": 0.6}]
    neue = [{"id": 9, "score": 0.5}, {"id": 8, "score": 0.95}]
    ids = [c["id"] for c in qa.nachrecherche_einfuegen(erste, neue)]
    # 8 schlägt alle; 9 schlägt 2 (0,4) — die erste Liste behält ihre Folge 1, 2, 3.
    assert ids == [8, 1, 9, 2, 3]


# ---- Kontext-Diät: weniger Wortbeiträge, die zur Sache zuerst --------------

def test_debatten_diaet_nimmt_die_aussprache_zur_sache_zuerst():
    ctx = [{"id": 10}, {"id": 20}]
    debatten = (
        [{"id": i, "zu_beschluss": None, "session_date": "2026-01-01", "top": f"T{i}"} for i in range(1, 31)]
        + [{"id": 100, "zu_beschluss": 20, "session_date": "2026-06-01", "top": "Ö 5"},
           {"id": 101, "zu_beschluss": 10, "session_date": "2026-06-01", "top": "Ö 4"},
           {"id": 200, "zu_beschluss": None, "session_date": "2026-02-01", "top": "Akte"}])
    aus = qa.debatten_diaet(debatten, ctx, behalten={200}, max_n=5)
    ids = [d["id"] for d in aus]
    assert ids[0] == 200                    # die Akte bleibt, zählt nicht mit
    assert ids[1:3] == [101, 100]           # Aussprache in Rangfolge der Beschlüsse
    assert len(ids) == 1 + 5


def test_debatten_diaet_deckelt_je_tagesordnungspunkt():
    debatten = [{"id": i, "zu_beschluss": 1, "session_date": "2026-06-01", "top": "Ö 5"} for i in range(10)]
    debatten.append({"id": 99, "zu_beschluss": None, "session_date": "2026-05-01", "top": "Ö 2"})
    aus = qa.debatten_diaet(debatten, [{"id": 1}], max_n=10, je_top=4)
    assert [d["id"] for d in aus] == [0, 1, 2, 3, 99]


# ---- Belegnotizen: erst lesen, dann antworten ------------------------------

def test_belegnotizen_lesen_parallel_und_behalten_nur_gueltige(monkeypatch):
    aufrufe: list[str] = []

    def chat(**kw):
        inhalt = kw["messages"][0]["content"]
        aufrufe.append(inhalt)
        notizen = [{"key": "B1", "relevant": True, "notiz": "Satzung am 13.04.2026 beschlossen."},
                   {"key": "B2", "relevant": False, "notiz": "nichts"},
                   {"key": "X9", "relevant": True, "notiz": "erfunden"}]
        if "W7" in inhalt:
            notizen = [{"key": "W7", "relevant": True, "notiz": "Grüne: OVG kippte 2020er Satzung."}]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps({"notizen": notizen})))], usage=None)
    monkeypatch.setattr(qa.llm, "chat_complete", chat)
    monkeypatch.setattr(qa, "NOTIZ_PAKET", 2)
    ctx = [{"id": 1, "title": "B-Plan N-777 G", "committee": "Rat", "session_date": "2026-04-13",
            "outcome": "accepted"}, {"id": 2, "title": "Anderes", "outcome": "noted"}]
    debatten = [{"id": 7, "speaker": "X", "party": "Grüne", "text": "OVG", "session_date": "2026-04-13"}]
    notizen = qa.belegnotizen("Wann wurde der B-Plan beschlossen?", ctx, debatten)
    assert len(aufrufe) == 2                                   # zwei Pakete
    assert [n["key"] for n in notizen] == ["B1", "W7"]        # irrelevant und erfunden fallen raus
    block = qa.belegnotizen_block(notizen)
    assert block.startswith("BELEGNOTIZEN") and "Beschluss [1]" in block and "angenommen" in block


def test_belegnotizen_kommen_an_den_anfang_des_kontexts():
    messages, _ = qa._answer_messages(
        "Wann?", [{"id": 1, "title": "T", "official_text": "B"}], typ="topic",
        notiz_block=qa.belegnotizen_block([{"key": "B1", "kopf": "Beschluss [1] T", "notiz": "N"}]))
    prompt = messages[0]["content"]
    assert prompt.index("BELEGNOTIZEN (vorab") < prompt.index("[1] T")
    assert "Schreibe NIE, etwas gehe aus den Unterlagen nicht" in prompt
    # Ohne Notizen weder Block noch Regel.
    ohne, _ = qa._answer_messages("Wann?", [{"id": 1, "title": "T", "official_text": "B"}], typ="topic")
    assert "BELEGNOTIZEN" not in ohne[0]["content"]


def test_belegnotizen_fehler_heisst_ohne_notiz(monkeypatch):
    def kaputt(**kw):
        raise TimeoutError
    monkeypatch.setattr(qa.llm, "chat_complete", kaputt)
    assert qa.belegnotizen("Frage?", [{"id": 1, "title": "T"}], []) == []
