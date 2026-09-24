"""Die Quizfragen aus eigenen Daten (council.quiz_formats) — ohne Modell."""
from __future__ import annotations

import json

import pytest

from council import quiz_formats as qf
from council.store import CouncilStore


# ---- Anträge aus RIS-Titeln (echte Titel aus dem Abzug vom 23.09.2026) -----

def test_parse_motion_reads_proposer_year_and_core():
    m = qf.parse_motion("Senkung der Grundsteuer B (Fraktion WFO-LKR vom 28.12.2018)")
    assert m == {"proposer": "Fraktion WFO-LKR", "year": 2018, "core": "Senkung der Grundsteuer B"}


def test_parse_motion_prefix_form_and_slash_spacing():
    m = qf.parse_motion("Antrag der Fraktion BSW: Einführung eines Schulfachs „Glück und Wohlbefinden“")
    assert m and m["proposer"] == "Fraktion BSW" and m["core"].startswith("Einführung eines Schulfachs")
    m = qf.parse_motion("Regionales Umweltbildungszentrum Oldenburg (RUZ) (Fraktion Bündnis 90/ Die Grünen vom 17.08.2020)")
    assert m and m["proposer"] == "Fraktion Bündnis 90/Die Grünen" and m["core"] == "Regionales Umweltbildungszentrum Oldenburg (RUZ)"


def test_parse_motion_drops_the_referral_tail():
    m = qf.parse_motion('"Tag der Republik, Straßenumbenennung" (Gruppe Die Linke./Piratenpartei '
                        'vom 08.01.2018, Verweisung aus Rat am 22.01.2018)')
    assert m and m["proposer"] == "Gruppe Die Linke./Piratenpartei" and m["year"] == 2018
    assert m["core"] == "Tag der Republik, Straßenumbenennung"


def test_parse_motion_skips_reports_resolutions_and_non_motions():
    assert qf.parse_motion("Zweckentfremdungssatzung für Oldenburg (Gruppe Die Linke./Piratenpartei vom 15.04.2019) - Bericht") is None
    assert qf.parse_motion("Resolution zum Neubau der Huntebrücke (Antrag der Fraktionen SPD und CDU vom 17.1.2025)") is None
    # Eine Vorlage der Verwaltung — auch wenn ein Modell dort Fraktionen notiert hat.
    assert qf.parse_motion("Neubau Stadion Maastrichter Straße; Rechtsgutachten – Weiteres Vorgehen") is None


def _seed_motions(store: CouncilStore, n_accepted: int, n_rejected: int) -> None:
    c = store._conn
    with c:
        for ksinr, committee, day in ((1, "Rat", "2024-05-06"), (2, "Verkehrsausschuss", "2024-04-02")):
            c.execute("INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
                      "location, fetched_at) VALUES (?, ?, ?, '17:00', 'Rathaus', '2024-05-07')",
                      (ksinr, committee, day))
        k = 0
        for outcome, n in (("accepted", n_accepted), ("rejected", n_rejected)):
            for i in range(n):
                k += 1
                # Verschiedene Themen — gleich klingende Titel hielte die
                # Dubletten-Prüfung für denselben Antrag.
                thema = ["Bänke am Wasser", "Nachtbusse am Wochenende", "Trinkbrunnen in Parks",
                         "Radwege an Schulen", "Solardächer auf Turnhallen", "Hundewiesen im Norden",
                         "Kita-Plätze in Kreyenbrück", "Sanierung der Stadtbibliothek",
                         "Blühstreifen an Straßen", "Schwimmkurse für Kinder", "Taktung der Buslinie 310",
                         "Öffentliche Toiletten", "Bolzplatz in Eversten"][k - 1]
                title = f"Mehr {thema} jetzt (Fraktion Beispiel vom 01.02.2024)"
                for ksinr, oc in ((2, "accepted"), (1, outcome)):  # Ausschuss empfiehlt, Rat entscheidet
                    c.execute(
                        "INSERT INTO council_decisions (ksinr, position, title, outcome, vote, kind, "
                        "interest, template_number, simple_summary) VALUES (?,?,?,?,?,?,?,?,?)",
                        (ksinr, k, title, oc, "majority", "decision", 60, f"V-{k}",
                         f"Die Stadt stellt mehr Bänke auf ({k})."))


@pytest.fixture(autouse=True)
def _no_model(monkeypatch):
    """Kein Modell in den Tests: Die Beschreibung ist eine Attrappe."""
    monkeypatch.setattr(qf, "describe_motion",
                        lambda title, proposer, context: f"Der Antrag verlangt: {title}.")


def test_verdict_uses_the_final_decision_and_balances(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _seed_motions(store, n_accepted=10, n_rejected=2)
    qs = qf.verdict_questions(store)
    store.close()
    rejected = [q for q in qs if q["correct_index"] == 1]
    accepted = [q for q in qs if q["correct_index"] == 0]
    # Je Vorlage EINE Frage, mit dem Ausgang im Rat (nicht der Empfehlung).
    assert len(rejected) == 2
    assert len(accepted) == round(2 * qf.VERDICT_ACCEPTED_PER_REJECTED)
    q = rejected[0]
    assert q["options"] == ["Angenommen", "Abgelehnt"] and q["format"] == "verdict"
    assert q["question"].startswith("Die Fraktion Beispiel beantragte 2024:")
    assert q["question"].endswith("Wie hat der Rat entschieden?")
    assert "abgelehnt" in q["explanation"]
    # Beim abgelehnten Antrag keine Kurzfassung — sie könnte den Vorschlag
    # beschreiben, als gälte er.
    assert q["detail"] is None and accepted[0]["detail"]
    assert q["source_ref"].startswith("/council/decision?id=")


def test_verdict_keys_are_stable_and_refreshable(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _seed_motions(store, n_accepted=3, n_rejected=2)
    first = qf.verdict_questions(store)
    assert store.save_quiz_questions(first) == len(first)
    again = qf.verdict_questions(store)
    assert store.save_quiz_questions(again) == 0            # nichts doppelt
    assert store.refresh_quiz_payloads(again) == len(again)
    picked = store.pick_quiz_questions([qf.VERDICT_AREA], None, [], 10)
    store.close()
    assert picked and all(p["format"] == "verdict" for p in picked)
    assert "correct_index" not in picked[0]                 # Lösung erst beim Auswerten


# ---- Haushaltsvergleiche ----------------------------------------------------

def _seed_products(store: CouncilStore, year: int, values: dict[str, tuple[float, float]]) -> None:
    with store._conn:
        for no, (exp, rev) in values.items():
            store._conn.execute(
                "INSERT INTO council_products (year, product_no, product_name, expenses, revenues, "
                "result, source_url, fetched_at) VALUES (?,?,?,?,?,?,?,'2026-09-23')",
                (year, no, no, exp, rev, rev - exp, "https://example.org/haushalt.pdf"))


def test_compare_pairs_only_within_the_ratio_band(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _seed_products(store, 2026, {
        "P10.126001": (19_500_000, 1_200_000),   # Feuerwehr
        "P10.272001": (3_600_000, 200_000),      # Stadtbibliothek  (5,4×)
        "P10.127000": (19_900_000, 19_400_000),  # Rettungsdienst   (1,02× zur Feuerwehr: Münzwurf)
        "P10.523000": (100_000, 0),              # Denkmalschutz    (195× zur Feuerwehr: geschenkt)
        "P99.999999": (5_000_000, 0),            # nicht kuratiert
    })
    qs = qf.compare_questions(store)
    store.close()
    pairs = {frozenset(q["options"]) for q in qs}
    assert frozenset({"Feuerwehr", "Stadtbibliothek"}) in pairs
    assert frozenset({"Feuerwehr", "Rettungsdienst"}) not in pairs
    assert frozenset({"Feuerwehr", "Denkmalschutz"}) not in pairs
    assert all("P99" not in o for q in qs for o in q["options"])
    q = next(q for q in qs if set(q["options"]) == {"Feuerwehr", "Stadtbibliothek"})
    assert q["options"][q["correct_index"]] == "Feuerwehr"
    assert q["format"] == "compare" and q["question"] == "Wofür plant Oldenburg 2026 mehr Geld ein?"
    chart = json.loads(q["chart"])
    assert {i["label"] for i in chart["items"]} == set(q["options"])   # die Kacheln lesen hieraus


def test_compare_notes_self_financing(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _seed_products(store, 2026, {"P10.127000": (19_900_000, 19_400_000),
                                 "P10.561100": (3_700_000, 300_000)})
    (q,) = qf.compare_questions(store)
    store.close()
    assert "Beim Rettungsdienst kommen davon 19,4 Mio. €" in q["explanation"]


def test_compare_refreshes_to_the_new_year(tmp_path):
    """Ein neues Planjahr frischt dieselbe Frage auf — samt Lösung, falls sich
    die Reihenfolge dreht."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _seed_products(store, 2025, {"P10.126001": (10_000_000, 0), "P10.420000": (20_000_000, 0)})
    store.save_quiz_questions(qf.compare_questions(store))
    _seed_products(store, 2026, {"P10.126001": (30_000_000, 0), "P10.420000": (15_000_000, 0)})
    new = qf.compare_questions(store)
    assert store.save_quiz_questions(new) == 0
    assert store.refresh_quiz_payloads(new) == 1
    (row,) = store.quiz_active_rows()
    store.close()
    assert "2026" in row["question"]
    assert row["options"][row["correct_index"]] == "Feuerwehr"


# ---- Reihenfolge (Plan Q8) --------------------------------------------------

def test_order_needs_clear_steps_and_carries_the_solution(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _seed_products(store, 2026, {
        "P10.540002": (46_000_000, 0),   # Straßen
        "P10.126001": (19_500_000, 0),   # Feuerwehr
        "P10.281002": (12_100_000, 0),   # Kultur
        "P10.561100": (3_700_000, 0),    # Klimaschutz
        "P10.420000": (13_200_000, 0),   # Sport: zu nah an Kultur (1,09×)
    })
    qs = qf.order_questions(store)
    store.close()
    # Zwei Vierer tragen — keiner stellt Sport und Kultur (1,09×) nebeneinander.
    assert len(qs) == 2
    assert not any({"Sportförderung", "Kulturförderung"} <= set(q["options"]) for q in qs)
    q = next(q for q in qs if "Kulturförderung" in q["options"])
    assert q["qtype"] == "order" and len(q["options"]) == 4
    right = qf.correct_order(q["options"], json.loads(q["chart"]))
    assert [q["options"][i] for i in right] == ["Straßen, Wege und Plätze", "Feuerwehr", "Kulturförderung", "Klimaschutz"]


def test_order_distance_counts_swapped_pairs():
    right = [2, 0, 3, 1]
    assert qf.order_distance([2, 0, 3, 1], right) == 0
    assert qf.order_distance([0, 2, 3, 1], right) == 1
    assert qf.order_distance([1, 3, 0, 2], right) == 6


# ---- Worum ging es? (Tims Hinweis 24.09.2026) --------------------------------

def test_verdict_carries_a_description_as_hint(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _seed_motions(store, n_accepted=2, n_rejected=2)
    qs = qf.verdict_questions(store)
    store.close()
    assert qs and all(q["hint"].startswith("Der Antrag verlangt") for q in qs)


def test_verdict_without_description_is_dropped(tmp_path, monkeypatch):
    """Ohne Beschreibung wäre die Antwort geraten — die Frage fällt weg."""
    monkeypatch.setattr(qf, "describe_motion", lambda *a: None)
    store = CouncilStore(tmp_path / "c.sqlite")
    _seed_motions(store, n_accepted=2, n_rejected=2)
    assert qf.verdict_questions(store) == []
    store.close()


def test_verdict_reuses_stored_descriptions(tmp_path, monkeypatch):
    store = CouncilStore(tmp_path / "c.sqlite")
    _seed_motions(store, n_accepted=2, n_rejected=2)
    store.save_quiz_questions(qf.verdict_questions(store))
    monkeypatch.setattr(qf, "describe_motion", lambda *a: (_ for _ in ()).throw(AssertionError("kein Modell")))
    again = qf.verdict_questions(store)
    store.close()
    assert again and all(q["hint"] for q in again)


def test_rebuild_retires_what_is_no_longer_built(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _seed_motions(store, n_accepted=2, n_rejected=2)
    qs = qf.verdict_questions(store)
    store.save_quiz_questions(qs)
    keep = [q["content_hash"] for q in qs[:2]]
    assert store.retire_quiz_area_except(*qf.VERDICT_AREA, keep) == len(qs) - 2
    assert {r["content_hash"] for r in store.quiz_active_rows()} == set(keep)
    store.close()


def test_describe_motion_rejects_give_aways(monkeypatch):
    from types import SimpleNamespace
    from kern import llm
    def answer(text):
        return lambda **kw: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
    monkeypatch.undo()      # die Attrappe aus _no_model weg, die echte Funktion prüfen
    ctx = "Ratsfrau X (Beispiel): Sie fordert, der Firma die städtischen Aufträge zu entziehen."
    monkeypatch.setattr(llm, "chat_complete", answer("Der Antrag verlangt, einer Firma die Aufträge zu entziehen."))
    assert qf.describe_motion("Verdachtskündigung", "Gruppe X", ctx).startswith("Der Antrag verlangt")
    monkeypatch.setattr(llm, "chat_complete", answer("Der Antrag wurde mehrheitlich abgelehnt."))
    assert qf.describe_motion("Verdachtskündigung", "Gruppe X", ctx) is None
    monkeypatch.setattr(llm, "chat_complete", answer("NICHTS"))
    assert qf.describe_motion("Verdachtskündigung", "Gruppe X", ctx) is None
    assert qf.describe_motion("Verdachtskündigung", "Gruppe X", "zu kurz") is None


def test_parse_motion_two_digit_year():
    m = qf.parse_motion("Sachgrundlose Befristung von Arbeitsverträgen (Gruppe Linke./Piraten vom 18.10.18)")
    assert m == {"proposer": "Gruppe Linke./Piraten", "year": 2018, "core": "Sachgrundlose Befristung von Arbeitsverträgen"}


def test_motion_context_puts_the_proposer_first(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _seed_motions(store, n_accepted=0, n_rejected=1)
    did = store._conn.execute("SELECT id, item_number FROM council_decisions WHERE ksinr = 1").fetchone()[0]
    with store._conn:
        store._conn.execute("UPDATE council_decisions SET item_number = 'Ö 7' WHERE id = ?", (did,))
        for pos, (who, party, text) in enumerate([
                ("Herr A", "Andere", "Wir halten das für falsch."),
                ("Frau B", "Beispiel", "Wir wollen mehr Bänke am Wasser, damit man ausruhen kann.")]):
            store._conn.execute(
                "INSERT INTO council_speeches (ksinr, position, kind, top, speaker, party, text, extracted_at) "
                "VALUES (1, ?, 'speech', '7 Mehr Bänke', ?, ?, ?, '2024-05-07')", (pos, who, party, text))
    ctx = qf.motion_context(store, did, "Fraktion Beispiel")
    store.close()
    assert ctx.index("Frau B") < ctx.index("Herr A")
