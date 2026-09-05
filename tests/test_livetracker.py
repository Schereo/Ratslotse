"""council/livetracker.py — die Live-Verfolgung: Sprecher-Abgleich, Antwort-
Parser, Block-Erkennung, Stand in der Datenbank (Modell gemockt)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from council import livetracker
from council.scraper import AgendaItem, CouncilSession
from council.store import CouncilStore

ROSTER = [
    {"name": "Christoph Baak", "party": "CDU", "role": "member"},
    {"name": "Susanne Drügemöller", "party": "Bündnis 90/Die Grünen", "role": "member"},
    {"name": "Kristina Onken", "party": "SPD", "role": "member"},
    {"name": "Jürgen Krogmann", "party": "", "role": "administration"},
]


# ------------------------------------------------------------- norm_top

def test_norm_top_strips_prefixes_but_keeps_urgent_motions():
    assert livetracker.norm_top("Ö 9.3") == "9.3"
    assert livetracker.norm_top("TOP 10.2") == "10.2"
    assert livetracker.norm_top(" 6.1 ") == "6.1"
    assert livetracker.norm_top("DZT 1") == "DZT 1"
    assert livetracker.norm_top(None) is None
    assert livetracker.norm_top("") is None


# -------------------------------------------------------- match_speaker

def test_match_speaker_tolerates_misheard_surnames():
    """Die Erkennung verschreibt Namen (Probe 31.08.): Bark → Baak (Ähnlichkeit
    0,75), Onke → Onken; ein fremder Name bleibt unter der Schwelle."""
    assert livetracker.match_speaker("Herr Bark", ROSTER)["name"] == "Christoph Baak"
    assert livetracker.match_speaker("Frau Dr. Onke", ROSTER)["name"] == "Kristina Onken"
    assert livetracker.match_speaker("Frau Drügemöller", ROSTER)["name"] == "Susanne Drügemöller"
    assert livetracker.match_speaker("Susanne Drügemöller", ROSTER)["name"] == "Susanne Drügemöller"
    assert livetracker.match_speaker("Herr Müller", ROSTER) is None
    assert livetracker.match_speaker(None, ROSTER) is None
    assert livetracker.match_speaker("Herr", ROSTER) is None


def test_party_of_falls_back_to_verwaltung_for_administration():
    assert livetracker.party_of(ROSTER[0]) == "CDU"
    assert livetracker.party_of(ROSTER[3]) == "Verwaltung"
    assert livetracker.party_of({"name": "X", "party": "", "role": "guest"}) is None


# ------------------------------------------------------- parse_response

def test_parse_response_reads_fenced_and_broken_json():
    prev = {"top": "6.1", "speaker": None, "party": None}
    got = livetracker.parse_response('```json\n{"top": "6.2", "phase": "aufruf"}\n```', prev)
    assert got["top"] == "6.2" and got["transitions"] == []
    got = livetracker.parse_response('Hier: {"top": "6.3", "transitions": "kaputt"}', prev)
    assert got["top"] == "6.3" and got["transitions"] == []
    # Abgeschnitten: der alte Stand bleibt, die Phase wird unklar.
    got = livetracker.parse_response('{"top": "6.4", "transitions": [{"at": "0', prev)
    assert got["top"] == "6.1" and got["phase"] == "unklar"


# ---------------------------------------------------------- LiveTracker

def _attendance(store: CouncilStore, ksinr: int, people: list[dict]) -> None:
    """Anwesenheit schreibt sonst nur der Protokoll-Import (save_protocol)."""
    with store.transaktion():
        for p in people:
            store._conn.execute(
                "INSERT INTO council_attendance (ksinr, name, party, role) VALUES (?, ?, ?, ?)",
                (ksinr, p["name"], p["party"] or None, p["role"]))


def _store(tmp_path) -> CouncilStore:
    store = CouncilStore(tmp_path / "council.sqlite")
    store.save_session(CouncilSession(
        ksinr=100, committee="Rat", session_date="2026-06-29", session_time="18:00",
        location="PFL", agenda_items=[AgendaItem(item_number="Ö 1", title="Alt")],
    ))
    _attendance(store, 100, ROSTER)
    # Dazwischen eine Ausschuss-Sitzung MIT Liste — die zählt nicht als Rat.
    store.save_session(CouncilSession(
        ksinr=105, committee="Bauausschuss", session_date="2026-08-20", session_time="17:00",
        location="PFL", agenda_items=[AgendaItem(item_number="Ö 1", title="Bau")],
    ))
    _attendance(store, 105, [{"name": "Nur Ausschuss", "party": "FDP", "role": "member"}])
    store.save_session(CouncilSession(
        ksinr=200, committee="Rat", session_date="2026-08-31", session_time="18:00",
        location="PFL", agenda_items=[
            AgendaItem(item_number="Ö 1", title="Feststellung der Beschlussfähigkeit"),
            AgendaItem(item_number="Ö 9.3", title="Radweg Alexanderstraße"),
            AgendaItem(item_number="Ö 9.4", title="Veränderungssperre Nord"),
            AgendaItem(item_number="Ö 9.5", title="Veränderungssperre Süd"),
            AgendaItem(item_number="Ö 9.6", title="Veränderungssperre West"),
        ],
    ))
    return store


def test_council_roster_before_takes_the_last_council_session_with_a_list(tmp_path):
    store = _store(tmp_path)
    try:
        namen = [p["name"] for p in store.council_roster_before(200)]
        assert "Christoph Baak" in namen and "Jürgen Krogmann" in namen
        assert "Nur Ausschuss" not in namen
        # Für die erste Ratssitzung gibt es keine Vorgängerin.
        assert store.council_roster_before(100) == []
    finally:
        store.close()


def _tracker(store, responses):
    start = datetime(2026, 8, 31, 18, 0, tzinfo=timezone.utc)
    tracker = livetracker.LiveTracker(store, 200, chunk_seconds=120, started_at=start)
    calls = iter(responses)

    def fake(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=next(calls)))], usage=None)

    return tracker, fake


def test_tracker_writes_state_and_events_per_chunk(tmp_path):
    store = _store(tmp_path)
    try:
        tracker, fake = _tracker(store, [
            '{"transitions": [{"at": "0:20", "kind": "top", "top": "Ö 9.3", "evidence": "Punkt 9.3"},'
            ' {"at": "0:50", "kind": "speaker", "speaker": "Frau Drügemöller"}],'
            ' "top": "9.3", "phase": "aussprache", "speaker": "Frau Drügemöller",'
            ' "party": "Grüne", "evidence": "Frau Drügemöller für die Grünen"}',
        ])
        with mock.patch.object(livetracker.llm, "chat_complete", fake):
            tracker.on_chunk(0, [(5.0, "Wir kommen zu Punkt 9.3."),
                                 (50.0, "Frau Drügemöller, bitte.")], False)
        state = store.get_live_state(200)
        assert state["item_number"] == "9.3"
        assert state["item_title"] == "Radweg Alexanderstraße"
        assert state["phase"] == "aussprache"
        # Sprecher UND Fraktion kommen aus dem Verzeichnis, nicht vom Modell.
        assert state["speaker"] == "Susanne Drügemöller"
        assert state["party"] == "Bündnis 90/Die Grünen"
        assert state["block_start"] is None
        assert state["finished"] is False
        # since = Aufnahmestart + Sekunde des Aufrufs; as_of = Ende des Stücks.
        assert state["since"] == "2026-08-31T18:00:20+00:00"
        assert state["as_of"] == "2026-08-31T18:02:00+00:00"
        events = store.live_events(200)
        assert [(e["kind"], e["at_seconds"]) for e in events] == [("top", 20), ("speaker", 50)]
        assert events[0]["item_number"] == "9.3"
        assert events[1]["speaker"] == "Susanne Drügemöller"
        assert tracker.updates == 1
    finally:
        store.close()


def test_tracker_marks_a_block_of_quick_items(tmp_path):
    """Vier Veränderungssperren in 50 Sekunden (Probe 31.08.): Der Stand
    nennt den letzten Punkt und den ersten des Blocks."""
    store = _store(tmp_path)
    try:
        tracker, fake = _tracker(store, [
            '{"transitions": [{"at": "2:05", "kind": "vote", "top": "9.4"},'
            ' {"at": "2:20", "kind": "vote", "top": "9.5"},'
            ' {"at": "2:40", "kind": "vote", "top": "9.6"}],'
            ' "top": "9.6", "phase": "abstimmung", "speaker": null, "party": null}',
        ])
        with mock.patch.object(livetracker.llm, "chat_complete", fake):
            tracker.on_chunk(1, [(125.0, "Punkt 9.4, wer ist dafür? Punkt 9.5 … 9.6")], False)
        state = store.get_live_state(200)
        assert (state["item_number"], state["block_start"]) == ("9.6", "9.4")
        assert state["speaker"] is None and state["party"] is None
    finally:
        store.close()


def test_tracker_keeps_the_last_top_when_the_model_is_silent(tmp_path):
    store = _store(tmp_path)
    try:
        tracker, fake = _tracker(store, [
            '{"transitions": [], "top": "9.3", "phase": "aussprache", "speaker": null, "party": null}',
            # Leere Antwort des Anbieters → kein Wechsel, Phase unklar.
        ])
        with mock.patch.object(livetracker.llm, "chat_complete", fake):
            tracker.on_chunk(0, [(5.0, "Punkt 9.3.")], False)
        with mock.patch.object(livetracker.llm, "chat_complete",
                               lambda **kw: SimpleNamespace(choices=None, usage=None)):
            tracker.on_chunk(1, [(130.0, "…")], False)
        state = store.get_live_state(200)
        assert state["item_number"] == "9.3"
        assert state["phase"] == "unklar"
        assert state["since"] == "2026-08-31T18:00:00+00:00"
        assert state["as_of"] == "2026-08-31T18:04:00+00:00"
    finally:
        store.close()


def test_tracker_finishes_on_closing_formula_and_on_finish(tmp_path):
    store = _store(tmp_path)
    try:
        tracker, fake = _tracker(store, [
            '{"transitions": [], "top": "9.6", "phase": "abstimmung", "speaker": null, "party": null}',
        ])
        with mock.patch.object(livetracker.llm, "chat_complete", fake):
            tracker.on_chunk(0, [(5.0, "Damit schließe ich die Sitzung.")], True)
        state = store.get_live_state(200)
        assert state["finished"] is True and state["phase"] == "ende"
        assert state["item_number"] == "9.6"
        # finish() nach dem Ende ändert nichts mehr.
        tracker.finish()
        assert store.get_live_state(200)["as_of"] == state["as_of"]
    finally:
        store.close()


def test_tracker_finish_without_any_state_writes_an_ended_row(tmp_path):
    """Aufnahme abgebrochen, bevor ein Fenster durch war: Die Karte darf
    trotzdem nicht „gerade" sagen — eine Ende-Zeile ohne TOP."""
    store = _store(tmp_path)
    try:
        tracker, _ = _tracker(store, [])
        tracker.finish(t_to=240)
        state = store.get_live_state(200)
        assert state["finished"] is True and state["item_number"] is None
        assert state["as_of"] == "2026-08-31T18:04:00+00:00"
    finally:
        store.close()


def test_new_tracker_clears_the_previous_run(tmp_path):
    store = _store(tmp_path)
    try:
        store.save_live_state(200, {"item_number": "1", "phase": "aufruf"}, "alt")
        store.add_live_events(200, [{"at_seconds": 1, "kind": "top", "item_number": "1"}])
        livetracker.LiveTracker(store, 200, chunk_seconds=120)
        assert store.get_live_state(200) is None
        assert store.live_events(200) == []
    finally:
        store.close()
