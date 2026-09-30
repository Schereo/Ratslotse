"""„gilt als behandelt" ist ein eigenes Ergebnis (``settled``), kein Beschluss.

Anlass (30.09.2026): Datensatz 19018 — Schlossplatz-Spielplatz, Jugendhilfe-
ausschuss 18.09.2024 — stand auf ``accepted``, amtlich aber „gilt als
behandelt". Das „einstimmig" gehörte zum Antrag zur Geschäftsordnung; „Frag den
Rat" zitierte den Punkt als Auftrag, Mittel in den Haushalt einzustellen. Im
Bestand stand die Formel auf vier verschiedenen Werten (59 no_decision, 43
accepted, 20 postponed, 3 noted).
"""
import pytest

from council import outcome_note
from council.store import CouncilStore
from council.votes import normalize_outcome


@pytest.mark.parametrize("alt,raw,neu", [
    # Der Anlass: Modell nahm das „einstimmig" des Verfahrensantrags für den Inhalt.
    ("accepted", "- einstimmig – - gilt als behandelt -", "settled"),
    ("no_decision", "- gilt als behandelt -", "settled"),
    ("postponed", "Der Tagesordnungspunkt wird als behandelt gelten gelassen. -einstimmig", "settled"),
    ("noted", "- einstimmig - - gilt als behandelt -", "settled"),
    ("accepted", "Der Antrag gilt als behandelt. - einstimmig.", "settled"),
    # Steht die Formel am Ende, gewinnt sie: erst wurde ein Verfahrensantrag
    # angenommen, dann galt der Punkt als behandelt (Datensatz 7028).
    ("no_decision", "mehrheitlich bei drei Gegenstimmen angenommen - gilt als behandelt -", "settled"),
    # Verwiesen ist nicht behandelt: postponed.
    ("accepted", "- gilt als behandelt - - verwiesen in den Schulausschuss am 06.02.2024 -", "postponed"),
    # Angenommen wurde die Verweisung, nicht der Inhalt.
    ("accepted", "- mehrheitlich bei 6 Enthaltungen - in die zuständigen Fachausschüsse verwiesen.", "postponed"),
    # Unverändert: gewöhnliche Ergebnisse, und Mischsätze, in denen unklar ist, was entschieden wurde.
    ("accepted", "- einstimmig -", "accepted"),
    ("rejected", "- mehrheitlich abgelehnt bei neun Gegenstimmen -", "rejected"),
    ("accepted", "Der Vorschlag des Oberbürgermeisters wird einstimmig angenommen. Beide Anträge "
                 "gelten als behandelt. Der Bericht wird zur Kenntnis genommen.", "accepted"),
    ("rejected", "Die Verweisung in den Ausschuss wird abgelehnt.", "rejected"),
    # Abgelehnte Verweisung — auch als „lehnt … ab" (14874 auf Prod).
    ("accepted", "Der Ausschuss lehnt anschließend den Verweisungsantrag der CDU in den "
                 "Sozialausschuss mehrheitlich ab: - bei 3 Gegenstimmen -", "accepted"),
    ("accepted", "Dem Verweisungsantrag der SPD-Fraktion wird - einstimmig - zugestimmt.", "postponed"),
    ("noted", "Der Bericht wird zur Kenntnis genommen.", "noted"),
    ("accepted", None, "accepted"),
])
def test_normalize_outcome(alt, raw, neu):
    assert normalize_outcome(alt, raw, "decision") == neu


def test_ein_verfahrensantrag_bleibt_was_er_ist():
    """Der Antrag, den Punkt als behandelt gelten zu lassen, wird tatsächlich
    angenommen oder abgelehnt — nur der Hauptpunkt ist „behandelt"."""
    raw = "Der Antrag, den Tagesordnungspunkt als behandelt gelten zu lassen, wird einstimmig abgelehnt."
    assert normalize_outcome("rejected", raw, "subvote") == "rejected"
    assert normalize_outcome("accepted", "- gilt als behandelt -", "subvote") == "accepted"


def test_beim_einlesen_gilt_die_regel(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    store._insert_decision(
        4254, 0, "decision", None, "8.1", "Schaffung eines Spielplatzes in der Innenstadt",
        "Mittel in den Haushalt einstellen", "accepted", "unanimous", None, None, [], None, None,
        "- einstimmig – - gilt als behandelt -")
    store._insert_decision(
        4254, 1, "subvote", "8.1", "8.1", "Geschäftsordnungsantrag: als behandelt gelten lassen",
        None, "accepted", "unanimous", None, None, [], None, None,
        "- einstimmig – - gilt als behandelt -")
    ergebnis = dict(store._conn.execute("SELECT kind, outcome FROM council_decisions").fetchall())
    assert ergebnis == {"decision": "settled", "subvote": "accepted"}
    store.close()


def test_settled_ist_ein_nicht_gefasster_beschluss_fuer_alle_texte():
    """Die Kurzfassung darf den Vorschlag nicht als beschlossen nachschreiben
    (dieselbe Regel wie bei abgelehnt/vertagt, ``outcome_note``)."""
    assert "settled" in outcome_note.NOT_ADOPTED
    hinweis = outcome_note.note("settled", "- einstimmig – - gilt als behandelt -")
    assert "GILT ALS BEHANDELT" in hinweis and "NICHT abgestimmt" in hinweis
    assert "einstimmig" in hinweis  # der Abstimmungssatz steht im Prompt
    # Die Probe: Ein Text ohne das Ergebnis besteht nicht …
    assert not outcome_note.states_outcome(
        "settled", "Die Verwaltung soll Mittel in den Haushalt 2025 einstellen.")
    # … einer, der es nennt, besteht.
    assert outcome_note.states_outcome(
        "settled", "Der Punkt galt als behandelt; über den Vorschlag wurde nicht abgestimmt.")
    assert outcome_note.as_proposal("settled", "Mittel einstellen.").startswith("Als behandelt erklärt")


def test_bestandsskript_meldet_und_schreibt(tmp_path, capsys):
    from scripts import fix_settled_outcomes as fix

    db = tmp_path / "council.sqlite"
    store = CouncilStore(db)
    with store._conn:
        for i, (out, raw) in enumerate([("accepted", "- gilt als behandelt -"),
                                        ("accepted", "- einstimmig -")]):
            store._conn.execute(
                "INSERT INTO council_decisions (ksinr, position, kind, title, outcome, raw_result) "
                "VALUES (1, ?, 'decision', 'T', ?, ?)", (i, out, raw))
    store.close()
    import sys
    sys.argv = ["fix", "--db", str(db)]
    assert fix.main() == {"umgestellt": 0, "faellig": 1}      # Bericht
    sys.argv = ["fix", "--db", str(db), "--schreiben"]
    assert fix.main() == {"umgestellt": 1, "faellig": 1}
    sys.argv = ["fix", "--db", str(db), "--schreiben"]
    assert fix.main() == {"umgestellt": 0, "faellig": 0}      # zweiter Lauf: nichts mehr
    store = CouncilStore(db)
    assert [r[0] for r in store._conn.execute(
        "SELECT outcome FROM council_decisions ORDER BY position")] == ["settled", "accepted"]
    store.close()
