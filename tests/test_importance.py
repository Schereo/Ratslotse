"""Wichtigkeits-Score: transparente, erklärbare Heuristik (0–100)."""
from datetime import date, timedelta

from council import importance
from council.store import CouncilStore


def _dec(**kw) -> dict:
    base = {"amount_eur": None, "gegenstimmen": None, "enthaltungen": None,
            "outcome": "angenommen", "title": "Sachbeschluss zu etwas",
            "committee": "Ausschuss für Stadtplanung und Bauen", "kind": "decision"}
    base.update(kw)
    return base


def test_score_bounds():
    for d in (_dec(), _dec(amount_eur=1e12, title="Satzung", committee="Rat der Stadt Oldenburg",
                          gegenstimmen=40, enthaltungen=5)):
        s = importance.importance_score(d, n_beratungen=8)
        assert 0 <= s <= 100


def test_big_binding_council_decision_scores_high():
    d = _dec(amount_eur=12_000_000, title="Bebauungsplan Nr. 851 als Satzung beschlossen",
             committee="Rat der Stadt Oldenburg", gegenstimmen=8, enthaltungen=3)
    assert importance.importance_score(d, n_beratungen=5) >= 70


def test_routine_note_scores_low():
    d = _dec(title="Kenntnisnahme der Niederschrift", outcome="zur_kenntnis",
             committee="Ausschuss für Soziales")
    # nur das Verbindlichkeits-Signal (Routine-Wort) ist da → niedrig
    assert importance.importance_score(d) <= 20


def test_contention_raises_score():
    quiet = _dec(amount_eur=500_000, vote="einstimmig", gegenstimmen=0, enthaltungen=0)
    loud = _dec(amount_eur=500_000, vote="mehrheitlich", gegenstimmen=12, enthaltungen=4)
    assert importance.importance_score(loud) > importance.importance_score(quiet)


def test_vote_field_used_when_counts_missing():
    # `gegenstimmen` oft NULL → auf das zuverlässigere `vote`-Feld stützen.
    contested = importance.importance_breakdown(_dec(vote="mehrheitlich"))
    unanimous = importance.importance_breakdown(_dec(vote="einstimmig"))
    assert contested["signals"]["umstritten"] > unanimous["signals"]["umstritten"]
    # Ganz ohne Abstimmungsinfo fehlt das Signal (zählt NICHT als 0):
    none_info = importance.importance_breakdown(_dec(vote=None, outcome="angenommen"))
    assert none_info["signals"]["umstritten"] is None
    # Kenntnisnahme = keine Abstimmung → kein Umstrittenheits-Signal:
    note = importance.importance_breakdown(_dec(vote="einstimmig", outcome="zur_kenntnis"))
    assert note["signals"]["umstritten"] is None


def test_money_is_monotonic():
    small = importance.importance_score(_dec(amount_eur=5_000))
    big = importance.importance_score(_dec(amount_eur=20_000_000))
    assert big > small


def test_effort_is_monotonic():
    d = _dec(amount_eur=100_000)
    assert importance.importance_score(d, n_beratungen=7) > importance.importance_score(d, n_beratungen=1)


def test_council_level_beats_committee():
    rat = _dec(title="Satzung über die Erhebung von Gebühren", committee="Rat der Stadt Oldenburg")
    aus = _dec(title="Satzung über die Erhebung von Gebühren", committee="Finanzausschuss")
    assert importance.importance_score(rat) > importance.importance_score(aus)


def test_missing_signals_renormalise():
    # Nur Titel-/Ebenen-Signal vorhanden (kein Geld, keine Abstimmung, keine
    # Beratungsfolge) → Score stützt sich allein darauf, kein Absturz auf 0.
    b = importance.importance_breakdown(_dec(title="Bebauungsplan als Satzung",
                                             committee="Rat der Stadt Oldenburg"))
    assert b["signals"]["geld"] is None and b["signals"]["aufwand"] is None
    assert b["signals"]["verbindlich"] is not None
    assert b["score"] > 50  # verbindlich + Ratsebene


def test_subvote_is_discounted():
    main = _dec(title="Satzung", committee="Rat der Stadt Oldenburg", kind="decision")
    sub = _dec(title="Satzung", committee="Rat der Stadt Oldenburg", kind="subvote")
    assert importance.importance_score(sub) < importance.importance_score(main)


def test_breakdown_shape():
    b = importance.importance_breakdown(_dec(amount_eur=1_000_000, gegenstimmen=5), n_beratungen=3)
    assert set(b["signals"]) == {"geld", "umstritten", "verbindlich", "aufwand"}
    assert set(b["contributions"]) == set(b["signals"])
    assert isinstance(b["score"], int)


def test_contributions_sum_to_score():
    """Die Beschluss-Seite addiert die Beiträge sichtbar — sie müssen den
    Heuristik-Score exakt ergeben, sonst geht die angezeigte Rechnung nicht auf."""
    cases = [
        (_dec(), None),
        (_dec(amount_eur=1_000_000, gegenstimmen=5), 3),
        (_dec(title="Kenntnisnahme der Niederschrift", outcome="zur_kenntnis"), None),
        (_dec(amount_eur=12_000_000, title="Satzung", committee="Rat der Stadt Oldenburg",
              gegenstimmen=8, enthaltungen=3), 6),
        (_dec(vote="einstimmig", amount_eur=4_321), 2),
        (_dec(amount_eur=999_999_999, vote="mehrheitlich"), 12),
    ]
    for d, n in cases:
        b = importance.importance_breakdown(d, n_beratungen=n)
        assert sum(v for v in b["contributions"].values() if v is not None) == b["score"], (d, n, b)
        # Fehlendes Signal → kein Beitrag (None, nicht 0).
        for k, sig in b["signals"].items():
            assert (b["contributions"][k] is None) == (sig is None)


def test_contributions_show_renormalised_weight():
    """Realfall (Fahrradstraßen Haareneschstr., Prod-id 7070): Geld und Aufwand
    fehlen, also tragen die übrigen zwei das volle Gewicht — ein voll
    ausgeschlagenes Signal liefert dann mehr als sein Rohgewicht von 24."""
    b = importance.importance_breakdown(
        _dec(title="Zukunft der Fahrradstraßen Haareneschstraße", committee="Rat",
             vote="mehrheitlich", gegenstimmen=20))
    assert b["signals"]["geld"] is None and b["signals"]["aufwand"] is None
    assert b["score"] == 81
    assert b["contributions"] == {"geld": None, "umstritten": 52, "verbindlich": 29, "aufwand": None}


# ---- Store-Integration: Backfill + Sortierung -------------------------------

def test_backfill_importance_store(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    c = store._conn
    with c:
        c.execute("INSERT INTO council_sessions(ksinr,committee,session_date,session_time,location,fetched_at) "
                  "VALUES (1,'Rat','2025-03-01','18:00','Rathaus','x')")
        c.execute("INSERT INTO council_sessions(ksinr,committee,session_date,session_time,location,fetched_at) "
                  "VALUES (2,'Ausschuss für Soziales','2025-03-02','17:00','Rathaus','x')")
        # wichtig: Satzung im Rat, große Summe, umstritten, mit Beratungsfolge
        c.execute("INSERT INTO council_decisions(ksinr,position,kind,title,outcome,vote,gegenstimmen,amount_eur,kvonr) "
                  "VALUES (1,0,'decision','Bebauungsplan Nr. 851 als Satzung','angenommen','mehrheitlich',9,8000000,555)")
        # unwichtig: bloße Kenntnisnahme im Fachausschuss, kein Geld
        c.execute("INSERT INTO council_decisions(ksinr,position,kind,title,outcome) "
                  "VALUES (2,0,'decision','Kenntnisnahme der Niederschrift','zur_kenntnis')")
        for datum in ("2025-01-01", "2025-02-01"):
            c.execute("INSERT INTO council_beratungen(kvonr,datum,gremium,fetched_at) VALUES (555,?,'Rat','x')", (datum,))

    assert store.backfill_importance() == 2
    by_title = {d["title"]: d for d in store.search_decisions(sort="importance", limit=10)}
    big = by_title["Bebauungsplan Nr. 851 als Satzung"]
    small = by_title["Kenntnisnahme der Niederschrift"]
    assert big["importance"] > small["importance"] and big["importance"] >= 60
    # „Wichtigste zuerst" sortiert korrekt
    assert [d["title"] for d in store.search_decisions(sort="importance", limit=10)][0] == big["title"]
    # only_missing überspringt bereits bewertete Zeilen
    assert store.backfill_importance(only_missing=True) == 0
    store.close()


def test_importance_sort_damps_old_decisions(tmp_path):
    """„Wichtigste zuerst" gewichtet mit Aktualität.

    Ohne Dämpfung stünden dort fast nur Haushaltsbeschlüsse: Sie tragen
    strukturell die höchste Tragweite und verdrängen alles Aktuelle. Ein alter
    100er darf einen frischen 70er deshalb nicht überholen.
    """
    store = CouncilStore(tmp_path / "c.sqlite")
    c = store._conn
    alt = (date.today() - timedelta(days=5 * 365)).isoformat()
    neu = (date.today() - timedelta(days=20)).isoformat()
    with c:
        for ksinr, datum in ((1, alt), (2, neu)):
            c.execute("INSERT INTO council_sessions(ksinr,committee,session_date,session_time,location,fetched_at)"
                      " VALUES (?,'Rat',?,'18:00','Rathaus','x')", (ksinr, datum))
        c.execute("INSERT INTO council_decisions(ksinr,position,kind,title,outcome)"
                  " VALUES (1,0,'decision','Haushaltssatzung 2021','angenommen')")
        c.execute("INSERT INTO council_decisions(ksinr,position,kind,title,outcome)"
                  " VALUES (2,0,'decision','Radweg Musterstraße','angenommen')")
        # Scores direkt setzen — hier zählt die Sortierung, nicht die Heuristik.
        c.execute("UPDATE council_decisions SET importance = 100 WHERE ksinr = 1")
        c.execute("UPDATE council_decisions SET importance = 70 WHERE ksinr = 2")

    titles = [d["title"] for d in store.search_decisions(sort="importance", limit=10)]
    assert titles[0] == "Radweg Musterstraße", titles
    # Gegenprobe: Die Dämpfung darf die Sortierung nicht zu „Neueste zuerst"
    # entarten lassen. Bei 5 Jahren bleibt vom 100er noch 100/(1+5/2) ≈ 29 —
    # ein frischer 20er (≈ 20) muss dahinter bleiben.
    with c:
        c.execute("UPDATE council_decisions SET importance = 20 WHERE ksinr = 2")
    titles = [d["title"] for d in store.search_decisions(sort="importance", limit=10)]
    assert titles[0] == "Haushaltssatzung 2021", titles
    store.close()
