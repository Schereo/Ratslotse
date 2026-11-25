"""Der Themen-Satz (`summary`) sieht den ganzen Beschluss, nicht nur den Anfang.

Bis 11/2026 bekam ``topics.classify_batch`` nur die ersten 400 Zeichen von
``official_text``. 19134 (Rat, 15.04.2024) beauftragt zuerst eine
Wirtschaftlichkeitsanalyse und danach — per Änderungsantrag angefügt — die
Erweiterung des EGH um eine Wohnungsgesellschaft. Der Satz hieß nur
„Beauftragung einer Wirtschaftlichkeitsanalyse …“, und Frag den Rat (liest
``summary`` vor ``official_text``) antwortete, die Gesellschaft sei nur geprüft
worden. Den Bestand zieht ``scripts/fix_long_summaries.py`` nach.
"""
from __future__ import annotations

from council import topics

# Der echte Beschlusstext von 19134.
TEXT_19134 = (
    "Die Verwaltung wird mit der Vergabe und Durchführung einer Wirtschaftlichkeitsanalyse für "
    "die Modelle „Erweiterung des Eigenbetriebs Gebäudewirtschaft und Hochbau (EGH)“ bzw. spätere "
    "„Umwandlung des EGH in eine städtische GmbH“ sowie „Städtische GmbH & Co. KG“ zur Gründung "
    "einer kommunalen Wohnungsgesellschaft beauftragt. Hierdurch soll insbesondere ein "
    "angemessenes Verhältnis zur Leistungsfähigkeit der Stadt sichergestellt werden. Die "
    "Verwaltung wird mit der „Erweiterung des Eigenbetriebs Gebäudewirtschaft und Hochbau (EGH)“ "
    "um den Betreibsteil Wohnungsgesellschaft beauftragt. Die Verwaltung legt zur Sitzung des AFB "
    "am im Juni 2024 eine entsprechende Änderung der Betriebssatzung vor. Die "
    "Organisationsuntersuchung EGH berücksichtigt die Erweiterung um den Betriebsteil "
    "Wohnungsgesellschaft."
)


def _render(text: str) -> str:
    return topics._render_items([{"id": 19134, "title": "Gründung einer Wohnungsgesellschaft",
                                  "committee": "Rat", "official_text": text,
                                  "outcome": "accepted"}])


def test_angehaengter_auftrag_kommt_im_prompt_an():
    prompt = _render(TEXT_19134)
    assert "um den Betreibsteil Wohnungsgesellschaft beauftragt" in prompt
    assert "Änderung der Betriebssatzung" in prompt


def test_sehr_langer_text_behaelt_anfang_und_ende():
    text = "Anfang des Beschlusses. " + "Füllsatz ohne Belang. " * 400 + "Der Auftrag am Ende."
    out = topics._beschlusstext(text)
    assert out.startswith("Anfang des Beschlusses.")
    assert out.endswith("Der Auftrag am Ende.")
    assert len(out) <= topics.TEXT_KOPF + topics.TEXT_ENDE + 5


def test_kurzer_text_bleibt_unveraendert():
    assert topics._beschlusstext("  Ein   kurzer\nBeschluss. ") == "Ein kurzer Beschluss."


def test_prompt_verlangt_den_folgenreichsten_teil():
    assert "GANZEN Beschluss" in topics._PROMPT
