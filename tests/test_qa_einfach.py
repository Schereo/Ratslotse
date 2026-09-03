"""„Einfacher erklären" ist ein eigener Modus, keine beiläufige Bitte.

Befund aus Build 11 (Tim, 15.08.): Der Knopf schickte nur den Satz „Erkläre das
bitte einfacher, ohne Fachbegriffe." als normale Frage in dieselbe Pipeline. Im
Antwort-Prompt stand der Wunsch damit als EINE Zeile neben zwei Dutzend Zeilen
Präzisions-, Zitier- und Gliederungsregeln — und verlor: Die „einfache" Antwort
enthielt weiter „Ausfallbürgschaften", „Teilfortschreibung des Nahverkehrsplans"
und „VBN-Tarifgebiet 3".
"""
from council import qa
from kern import prompts


def test_knopftext_und_getippte_varianten_werden_erkannt():
    """Der Knopf schickt immer denselben Satz — wer ihn selbst tippt, meint
    dasselbe und bekommt denselben Modus."""
    assert qa.will_vereinfachung("Erkläre das bitte einfacher, ohne Fachbegriffe.")
    assert qa.will_vereinfachung("erklär mir das mal einfacher")
    assert qa.will_vereinfachung("Bitte einfacher")
    assert qa.will_vereinfachung("Kannst du das in einfacher Sprache sagen?")
    assert qa.will_vereinfachung("Ohne Fachbegriffe bitte!")
    assert qa.will_vereinfachung("laienverständlich bitte")


def test_echte_fragen_bleiben_echte_fragen():
    """Das andere Register („Ausführlicher") und inhaltliche Fragen dürfen den
    Modus nie auslösen — sonst antwortet die Suche auf etwas anderes."""
    assert not qa.will_vereinfachung("Bitte ausführlicher — was gehört noch zum Bild?")
    assert not qa.will_vereinfachung("Wie ist der Stand beim Stadionneubau?")
    assert not qa.will_vereinfachung("Wurde der Antrag einfach durchgewinkt?")
    assert not qa.will_vereinfachung("Gibt es einfache Sprache auf der Website der Stadt?")
    # Eine lange, inhaltliche Frage bleibt eine Frage, auch mit „einfacher" darin.
    assert not qa.will_vereinfachung(
        "Wie will die Stadt erreichen, dass Bürgerinnen und Bürger einfacher an "
        "Informationen über Bauvorhaben in ihrem Stadtteil kommen und welche "
        "Beschlüsse gab es dazu zuletzt im Rat?")


def test_prompt_enthaelt_die_zu_vereinfachende_antwort():
    bisher = "Der Rat übernahm Ausfallbürgschaften über 44.699.000 Euro [8679]."
    msgs, _extra = qa.vereinfachen_messages(
        "Was wurde beschlossen?", bisher,
        [{"id": 8679, "title": "Ausfallbürgschaft", "session_date": "2026-06-01"}])
    prompt = msgs[0]["content"]
    assert bisher in prompt
    assert "VEREINFACHEN" in prompt
    # Kein Debatten-/Presse-Block: deren „ergänze IMMER einen Absatz zum
    # Meinungsbild" arbeitet gegen die Kürze — genau daran ist die beiläufige
    # Bitte im normalen Antwort-Prompt gescheitert.
    assert "Meinungsbild" not in prompt
    assert "UMFANGREICHES Thema" not in prompt


def test_ohne_vorherige_antwort_wird_direkt_einfach_geantwortet():
    """Alte App-Versionen schicken das Feld nicht mit. Dann gibt es keinen
    leeren Zitat-Block, sondern eine einfache Antwort aus den Beschlüssen."""
    msgs, _extra = qa.vereinfachen_messages("Was wurde beschlossen?", "", [])
    assert "keine frühere Antwort" in msgs[0]["content"]


def test_lange_vorlage_wird_gedeckelt():
    """Kostendeckel je Klick: Der Prompt trägt die Ausgangsantwort nur bis zur
    Obergrenze."""
    block = qa._bisher_block("x" * (qa.VEREINFACHEN_MAX_CHARS + 500))
    assert block.count("x") == qa.VEREINFACHEN_MAX_CHARS


def test_zitierte_ids_liest_auch_unbekannte_nummern():
    """Beim Vereinfachen sind die ids der vorigen Antwort der Anlass, die
    Beschlüsse überhaupt nachzuladen — resolve_citations kann das nicht, es
    braucht das Kandidatenset schon vorher."""
    text = "Erstens [8679]. Zweitens [5690, 5797]. Drittens [8525, 2026-04-20]."
    assert qa.zitierte_ids(text) == [8679, 5690, 5797, 8525]
    assert qa.zitierte_ids("ohne Belege") == []


def test_budget_ist_kleiner_als_das_der_normalen_antwort():
    """Zweite Bremse neben der Prompt-Regel: kurz ist das Ziel."""
    assert qa.VEREINFACHEN_TOKENS < qa._answer_tokens("topic")


def test_prompt_verbietet_nachkomma_millionen():
    """Die „44,699 Millionen Euro"-Falle aus Build 11: rechnerisch richtig
    (44.699.000 €), als Satz aber unlesbar. Beide Antwort-Prompts sagen jetzt,
    wie ein Betrag im Fließtext auszusehen hat."""
    for key in ("qa_answer", "qa_simple"):
        assert "44,699" in prompts.DEFAULTS[key]["template"]
        assert "Millionen Euro" in prompts.DEFAULTS[key]["template"]


def test_qa_einfach_rendert_mit_seinen_platzhaltern():
    prompts.render("qa_simple", question="F", bisher="B", context="C")
