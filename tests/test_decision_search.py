"""Beschluss-Suche: jedes Wort einzeln statt der ganzen Eingabe am Stück.

Anlass (21.10.2026): Ein Nutzer suchte „PAK Belastung“ und bekam nichts, obwohl
der Ratsbeschluss vom 31.08.2026 „Untersuchung einer festgestellten
PAK-Belastung …“ heißt — die Liste verlangte die Eingabe wörtlich.
"""
from council.decision_search import search_terms, spellings, text_filter
from council.store import CouncilStore


def _store(tmp_path, rows):
    store = CouncilStore(str(tmp_path / "council.sqlite"))
    store._conn.execute(
        "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
        "VALUES (1, 'Rat', '2026-08-31', '16:00', 'PFL', '2026-09-01')")
    for pos, (title, text, summary, template) in enumerate(rows):
        store._conn.execute(
            "INSERT INTO council_decisions (ksinr, position, kind, item_number, title, "
            "official_text, summary, template_number, outcome) "
            "VALUES (1, ?, 'decision', ?, ?, ?, ?, ?, 'accepted')",
            (pos, str(pos + 1), title, text, summary, template))
    store._conn.commit()
    return store


def _titles(store, query):
    rows = store.search_decisions(query)
    assert store.count_decisions(query) == len(rows), "Zählung und Liste laufen auseinander"
    return sorted(r["title"] for r in rows)


ROWS = [
    ("Untersuchung einer festgestellten PAK-Belastung in der Flugplatzbäke",
     "Die Verwaltung wird beauftragt, eine Kontrolluntersuchung zu veranlassen.", None, None),
    ("Bebauungsplan N-777 G (Fliegerhorst/Hallensichel Ost/Entlastungsstraße)",
     "Der Rat beschließt den Bebauungsplan.", None, "26/0101"),
    ("Faktenupdate zur geplanten Fliegerhorststraße", None, None, None),
    ("Änderung der Geschäftsordnung", "Die Änderung tritt in Kraft.", None, None),
    ("Radweg an der Ammerländer Heerstraße", None, "Ein Radweg wird gebaut.", None),
    ("Zuschuss von 100 Prozent", None, None, None),
]


def test_space_and_hyphen_find_the_same(tmp_path):
    store = _store(tmp_path, ROWS)
    pak = [ROWS[0][0]]
    assert _titles(store, "PAK-Belastung") == pak
    assert _titles(store, "PAK Belastung") == pak
    assert _titles(store, "Belastung, PAK") == pak


def test_words_may_sit_in_different_fields(tmp_path):
    store = _store(tmp_path, ROWS)
    # „PAK“ im Titel, „Kontrolluntersuchung“ nur im Beschlusstext.
    assert _titles(store, "PAK Kontrolluntersuchung") == [ROWS[0][0]]
    # Jedes Wort muss vorkommen — ein fremdes Wort leert die Liste.
    assert _titles(store, "PAK Radweg") == []


def test_sharp_s_and_capital_umlauts(tmp_path):
    store = _store(tmp_path, ROWS)
    assert ROWS[4][0] in _titles(store, "Ammerländer Heerstrasse")
    assert _titles(store, "heerstrasse") == [ROWS[4][0]]
    # LIKE faltet nur ASCII: „änderung“ fand „Änderung“ früher nicht.
    assert _titles(store, "änderung geschäftsordnung") == [ROWS[3][0]]


def test_colloquial_street_name_finds_the_official_one(tmp_path):
    store = _store(tmp_path, ROWS)
    both = sorted([ROWS[1][0], ROWS[2][0]])
    assert _titles(store, "Fliegerhorststraße") == both
    assert _titles(store, "Entlastungsstrasse") == both


def test_phrase_and_identifiers_stay_whole(tmp_path):
    store = _store(tmp_path, ROWS)
    assert _titles(store, '"Ammerländer Heerstraße"') == [ROWS[4][0]]
    assert _titles(store, '"Heerstraße Ammerländer"') == []
    # Die Vorlagennummer steht nur in template_number.
    assert _titles(store, "26/0101") == [ROWS[1][0]]
    assert _titles(store, "N-777 G") == [ROWS[1][0]]


def test_like_wildcards_are_literal(tmp_path):
    store = _store(tmp_path, ROWS)
    # Ohne Maskierung hiesse „0 %“ in LIKE „0 “ + beliebig — und träfe „100 Prozent“.
    assert _titles(store, '"0 %"') == []
    assert _titles(store, "100") == [ROWS[5][0]]


def test_search_terms():
    assert search_terms("PAK-Belastung") == [("pak",), ("belastung",)]
    assert search_terms("pak  PAK") == [("pak",)]
    # Ein Stück mit Ziffer bleibt ganz, Randzeichen fallen weg.
    assert search_terms("Vorlage 22/0257, Sitzung 31.08.") == [
        ("22/0257",), ("31.08",), ("vorlage",), ("sitzung",)]
    # Ein einzelner Buchstabe nur, wenn sonst nichts bleibt.
    assert search_terms("N-777 G") == [("n-777",)]
    assert search_terms("G") == [("g",)]
    assert search_terms('"Radweg Ammerländer"') == [("radweg ammerländer",)]
    assert search_terms("Fliegerhorststraße") == [
        ("fliegerhorststrasse", "entlastungsstrasse")]
    assert search_terms(" - ") == []
    assert text_filter(" - ") is None


def test_spellings():
    assert spellings("pak") == ["pak"]
    assert sorted(spellings("wasserstrasse")) == sorted(
        ["wasserstrasse", "waßerstrasse", "wasserstraße", "waßerstraße"])
    assert "Änderung" in spellings("änderung")
    # Viele „ss“: nur die beiden reinen Formen, die Abfrage wächst nicht mit 2^n.
    assert len(spellings("ss" * 6)) == 2


# Anlass des Rückfalls (21.10.2026): „Ich habe sogar den TOP direkt aus dem
# Protokoll kopiert und es kam null Ergebnis.“ Bei uns endete der Titel auf
# „… im Bereich“, im Protokoll ging er weiter — und dazu kamen „Ö 10.5“ und
# „- Beschlussantrag“, die in keinem unserer Felder stehen.
PASTED_TOP = ("Ö 10.5 Untersuchung einer festgestellten PAK-Belastung in der Flugplatzbäke "
              "im Bereich des ehemaligen Schießstandes am Fliegerhorst - Beschlussantrag")


def test_pasted_agenda_item_falls_back_to_most_words(tmp_path):
    rows = [("Untersuchung einer festgestellten PAK-Belastung in der Flugplatzbäke im Bereich",
             "Kontrolluntersuchung der Flugplatzbäke am ehemaligen Schießstand.", None, None),
            *ROWS[1:]]
    store = _store(tmp_path, rows)
    assert _titles(store, PASTED_TOP) == [rows[0][0]]
    assert _titles(store, "Dringlichkeitsantrag: festgestellte PAK-Belastung") == [rows[0][0]]


def test_fallback_only_when_strict_finds_nothing(tmp_path):
    store = _store(tmp_path, ROWS)
    # Streng: genau ein Treffer. Der Rückfall (3 von 4 Wörtern) brächte den
    # Radweg dazu — er darf nicht greifen, solange es einen echten Treffer gibt.
    assert _titles(store, "Radweg Ammerländer Heerstraße gebaut") == [ROWS[4][0]]
    # Hinter der letzten Seite bleibt die Liste leer, statt umzuschalten.
    assert store.search_decisions("PAK Belastung", offset=5) == []
    # Zwei Wörter: kein Rückfall — die Hälfte wäre ein einzelnes Wort.
    assert _titles(store, "PAK Haushalt") == []


def test_relaxed_terms():
    assert search_terms("im Bereich des ehemaligen Schießstandes", relaxed=True) == [
        ("bereich",), ("ehemalig",), ("schiessstand",)]
    assert search_terms("Ö 10.5 Bericht", relaxed=True) == [("bericht",)]
    assert search_terms("DZT 1 Dringlichkeitsantrag", relaxed=True) == [("dringlichkeitsantrag",)]
    # Streng bleibt die Nummer ein Begriff — wer sie tippt, meint sie.
    assert ("10.5",) in search_terms("Ö 10.5 Bericht")
    # Nur Füllwörter: dann doch die Füllwörter.
    assert search_terms("in der", relaxed=True) == [("in",), ("der",)]
    # Das Synonym hält auch am gekürzten Wort.
    assert search_terms("Fliegerhorststraße", relaxed=True)[0][1:] == (
        "entlastungsstrasse", "fliegerhorststrasse")
