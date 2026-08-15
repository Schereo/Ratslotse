"""Teilvoten-Parser (council/votes.py): Fraktionen aus dem Abstimmungssatz.

Reine Regex-Logik — kein Netz, kein LLM, keine DB.
"""
from council.votes import parse_raw_result


def test_gegenstimmen_mehrerer_fraktionen():
    votes = parse_raw_result(
        "Der Rat beschließt mehrheitlich bei Gegenstimmen der Fraktionen SPD und Bündnis 90/Die Grünen.")
    assert ("SPD", "dagegen") in votes
    assert ("Grüne", "dagegen") in votes
    assert all(s == "dagegen" for _, s in votes)


def test_enthaltung_und_gegenstimmen_getrennt():
    votes = parse_raw_result(
        "Mehrheitlich angenommen bei Gegenstimmen der AfD-Fraktion und Enthaltung der FDP-Fraktion.")
    assert ("AfD", "dagegen") in votes
    assert ("FDP", "enthaltung") in votes
    # Die FDP darf NICHT als Gegenstimme zählen (Segment endet am nächsten Marker).
    assert ("FDP", "dagegen") not in votes


def test_gegen_die_stimmen_von():
    votes = parse_raw_result("Angenommen gegen die Stimmen von CDU und Volt.")
    assert set(votes) == {("CDU", "dagegen"), ("Volt", "dagegen")}


def test_zahlen_ohne_fraktion_liefern_nichts():
    assert parse_raw_result("Mehrheitlich bei 3 Gegenstimmen und 2 Enthaltungen angenommen.") == []


def test_einstimmig_ohne_marker_liefert_nichts():
    assert parse_raw_result("Einstimmig beschlossen.") == []
    assert parse_raw_result(None) == []
    assert parse_raw_result("   ") == []


def test_gruppe_bleibt_gruppe():
    # Gruppenvotum wird nicht auf Mitglieds-Parteien aufgelöst (Fraktion ≠ Partei):
    # „Für Oldenburg" = Finke (parteilos) + Sander (Piraten) — ein Gruppen-Nein
    # ist kein belegtes Piraten-Nein.
    votes = parse_raw_result("Mehrheitlich bei Gegenstimmen der Gruppe Für Oldenburg.")
    assert votes == [("Für Oldenburg", "dagegen")]


def test_gruppe_fdp_volt_nicht_doppelt():
    votes = parse_raw_result("Bei Enthaltung der Gruppe FDP/Volt angenommen.")
    assert votes == [("FDP/Volt", "enthaltung")]


def test_begruenung_ist_keine_partei():
    # Wortgrenzen: „Begrünung" enthält „grüne", zählt aber nicht als Fraktion.
    assert parse_raw_result("Gegenstimmen wegen der geplanten Begrünung des Platzes.") == []


def test_keine_zustimmung_ableiten():
    # „mehrheitlich angenommen" sagt nicht, WER zustimmte — es gibt keine dafür-Zeilen.
    votes = parse_raw_result(
        "Der Rat stimmt mehrheitlich zu, die SPD-Fraktion stimmte dagegen.")
    assert votes == [("SPD", "dagegen")]
