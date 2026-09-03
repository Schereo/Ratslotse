"""Punktfragen bekommen knappe Antworten (Befund 12.08. an einer echten
Nutzer-Frage: Auf „Wann wurde B-Plan 831 beschlossen?" folgten dem Datum noch
fünf Redebeiträge, nach denen niemand gefragt hatte)."""
import json

from council import qa


def test_eng_regel_ersetzt_die_typ_regeln_und_die_debatten_pflicht():
    """Bei eng=True steht die Kürze-Regel im Prompt — und der Debatten-Block
    verlangt KEIN Meinungsbild mehr. Ohne das gewann die „IMMER ergänzen"-
    Anweisung des Blocks gegen die Kürze (im Test genau so gemessen)."""
    debatten = [{"speaker": "Meier", "party": "SPD", "date": "2026-01-01",
                 "text": "Ein Beitrag zur Sache.", "art": "rede"}]
    block_eng = qa._debatten_block(debatten, eng=True)
    block_normal = qa._debatten_block(debatten, eng=False)
    assert "KEIN Absatz zum Meinungsbild" in block_eng
    assert "IMMER" not in block_eng
    assert "IMMER" in block_normal          # normales Verhalten bleibt
    assert "Ein Beitrag zur Sache." in block_eng   # Daten bleiben im Kontext


def test_eng_kappt_das_token_budget():
    """Zweite Bremse neben der Prompt-Regel — ein Ausreißer bleibt kurz."""
    assert qa._answer_tokens("topic", gross=False, eng=True) == 320
    assert qa._answer_tokens("topic", gross=True, eng=True) == 320   # gross verliert
    assert qa._answer_tokens("topic", gross=False, eng=False) >= 1000


def test_analyse_liest_eng_aus_der_antwort(monkeypatch):
    """Das Merkmal reist im ohnehin laufenden Analyse-Call mit — kein
    zusätzlicher Aufruf, keine zusätzliche Latenz."""
    class _Antwort:
        def __init__(self, text):
            self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]

    payload = json.dumps({"question": "Wann wurde X beschlossen?", "begriffe": "X Beschluss",
                          "typ": "topic", "eng": True, "varianten": []})
    monkeypatch.setattr(qa.llm, "chat_complete", lambda **kw: _Antwort(payload))
    qa._ANALYSE_CACHE.clear()
    assert qa.analyse_query("Wann wurde X beschlossen?")["eng"] is True

    payload2 = json.dumps({"question": "Was wurde zu X entschieden?", "begriffe": "X",
                           "typ": "topic", "eng": False, "varianten": []})
    monkeypatch.setattr(qa.llm, "chat_complete", lambda **kw: _Antwort(payload2))
    qa._ANALYSE_CACHE.clear()
    assert qa.analyse_query("Was wurde zu X entschieden?")["eng"] is False


def test_analyse_fallback_ist_nicht_eng(monkeypatch):
    """Fällt die Analyse aus, bleibt es bei der ausführlichen Antwort —
    lieber zu lang als eine abgeschnittene Antwort auf eine breite Frage."""
    def _kaputt(**kw):
        raise RuntimeError("Provider weg")

    monkeypatch.setattr(qa.llm, "chat_complete", _kaputt)
    qa._ANALYSE_CACHE.clear()
    assert qa.analyse_query("Was wurde zum Fliegerhorst entschieden?")["eng"] is False
