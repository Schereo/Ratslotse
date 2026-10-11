"""Was als „Antwort ohne Quelle" zählt — und wann die Beleglage dünn ist.

Alle vier Antworten zu den Parkgebühren vom 10.10.2026 standen im Zähler
``ai_answer_empty`` (Sackgassen-Quote im Admin-Panel), weil er nur zitierte
Beschlüsse kannte; sie zitierten eine Haushaltsanlage ([A4]) bzw. kamen aus
der Kontenebene. Und unter ihnen stand „nur wenige passende Beschlüsse — die
Antwort kann unsicher sein" (Auswertung 11.10.2026).
"""
from council import qa


def test_beschluss_anlage_haushalt_und_bausteine_sind_belege():
    assert qa.antwort_belegt("…", [18022])
    assert qa.antwort_belegt("rund 3,7 Mio. € [A4].", [])
    assert qa.antwort_belegt("4,5 Mio. €", [], geld={"facets": ["accounts"],
                                                    "accounts": {"accounts": [{"label": "Parkgebühren"}]}})
    assert qa.antwort_belegt("Nach § 15 …", [], weitere=True)


def test_ohne_jeden_beleg_bleibt_es_eine_sackgasse():
    assert not qa.antwort_belegt("Dazu geben die Unterlagen nichts her.", [])
    # Summen des Gesamthaushalts kommen zu jeder Geldfrage mit — sie belegen nichts.
    assert not qa.antwort_belegt("…", [], geld={"facets": ["plan", "ansatz"],
                                               "haushalt": [{"area": "Summe"}],
                                               "ansatz": {"posten": []}})
    assert not qa.antwort_belegt("…", [], geld={"facets": ["accounts"], "accounts": None})


def test_geld_belegt():
    assert qa.geld_belegt({"facets": ["schulden"], "schulden": {"year": 2025}})
    assert not qa.geld_belegt({})
    assert not qa.geld_belegt(None)
