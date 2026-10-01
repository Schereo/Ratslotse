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
            AgendaItem(item_number="Ö 5", title="Einwohnerfragestunde"),
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
            '{"transitions": [{"at": "2:05", "kind": "vote", "top": "9.4", "evidence": "Punkt 9.4"},'
            ' {"at": "2:20", "kind": "vote", "top": "9.5", "evidence": "Punkt 9.5"},'
            ' {"at": "2:40", "kind": "vote", "top": "9.6", "evidence": "Punkt 9.6"}],'
            ' "top": "9.6", "phase": "abstimmung", "speaker": null, "party": null}',
        ])
        with mock.patch.object(livetracker.llm, "chat_complete", fake):
            tracker.on_chunk(1, [(125.0, "Punkt 9.4, wer ist dafür? Punkt 9.5, dafür? Punkt 9.6, dafür?")],
                             False)
        state = store.get_live_state(200)
        assert (state["item_number"], state["block_start"]) == ("9.6", "9.4")
        assert state["speaker"] is None and state["party"] is None
    finally:
        store.close()


def test_tracker_keeps_the_last_top_when_the_model_is_silent(tmp_path):
    store = _store(tmp_path)
    try:
        tracker, fake = _tracker(store, [
            '{"transitions": [], "top": "9.3", "phase": "aussprache", "speaker": null, "party": null,'
            ' "evidence": "Punkt 9.3"}',
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
            '{"transitions": [], "top": "9.6", "phase": "abstimmung", "speaker": null, "party": null,'
            ' "evidence": "Punkt 9.6"}',
        ])
        with mock.patch.object(livetracker.llm, "chat_complete", fake):
            tracker.on_chunk(0, [(5.0, "Punkt 9.6, einstimmig. Damit schließe ich die Sitzung.")], True)
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


def test_tracker_keeps_the_speaker_while_the_debate_continues(tmp_path):
    """15-s-Fenster tragen die Ankündigung nur jedes zweite Mal: Läuft die
    Aussprache zum selben Punkt weiter, redet noch, wer zuletzt dran war."""
    store = _store(tmp_path)
    try:
        tracker, fake = _tracker(store, [
            '{"transitions": [], "top": "9.3", "phase": "aussprache", "speaker": "Frau Drügemöller",'
            ' "party": null, "evidence": "Punkt 9.3, Frau Drügemöller"}',
            '{"transitions": [], "top": "9.3", "phase": "aussprache", "speaker": null, "party": null}',
            '{"transitions": [], "top": "9.3", "phase": "abstimmung", "speaker": null, "party": null}',
        ])
        with mock.patch.object(livetracker.llm, "chat_complete", fake):
            tracker.on_window(0, 15, [(2.0, "Punkt 9.3, Frau Drügemöller.")], False)
            tracker.on_window(15, 30, [(20.0, "… weiter im Text …")], False)
            assert store.get_live_state(200)["speaker"] == "Susanne Drügemöller"
            tracker.on_window(30, 45, [(35.0, "Wer ist dafür?")], False)
        assert store.get_live_state(200)["speaker"] is None
    finally:
        store.close()


# ------------------------------------------- nur eine Ratssitzung verfolgen

def test_names_item_reads_numbers_and_title_words():
    assert livetracker.names_item("Tagesordnungspunkt 9.3", "9.3", "Radweg")
    assert livetracker.names_item("wir kommen zu Punkt 93", "9.3", "Radweg")
    assert livetracker.names_item("Punkt 10,1, die Studie", "10.1", "Studie")
    assert not livetracker.names_item("seit 1993", "9.3", "Radweg")
    assert not livetracker.names_item("510 Millionen Quadratkilometer", "5", "Einwohnerfragestunde")
    assert livetracker.names_item("dann sind wir bei der Einwohnerfragestunde", "5",
                                  "Einwohnerfragestunde")
    # Ein Titelwort ohne Aufruf ist ein Thema (Probe am 29.06.: „Kennedystraße"
    # in der Einwohnerfragestunde, „Bahnhof" in einer Rede).
    assert not livetracker.names_item("Kennedystraße", "14.1", "Lärmschutz Kennedystraße")
    assert not livetracker.names_item("der Bahnhof ist die Visitenkarte", "7.1", "Bahnhofsumfeld")
    assert livetracker.names_item("wir kommen zum Bahnhofsumfeld", "7.1", "Bahnhofsumfeld")
    # Ein allgemeines Titelwort kennzeichnet keinen Punkt.
    assert not livetracker.names_item("ein Beschluss der Stadt", "10.1",
                                      "Studie Stadt Oldenburg - Beschluss")
    assert not livetracker.names_item(None, "5", "Einwohnerfragestunde")


def test_quoted_accepts_small_slips_but_not_inventions():
    window = "[2:05] Wir kommen zu Tagesordnungspunkt 9,3, Radweg Alexanderstraße."
    assert livetracker.quoted("Tagesordnungspunkt 9.3, Radweg", window)
    assert livetracker.quoted("wir kommen zu Tagesordnungspunkt 9,3 Radweg Alexanderstrasse", window)
    assert not livetracker.quoted("Ich rufe Punkt 9.3 auf", window)
    # Über zwei Segmente hinweg (Probe am 29.06.: „mit 7.1 [25:53] weiter").
    split = "[25:51] angenommen. Dann machen wir mit 7.1\n[25:53] weiter. Umgestaltung"
    assert livetracker.quoted("Dann machen wir mit 7.1 weiter.", split)
    assert not livetracker.quoted("", window)


def test_replacement_programme_never_reaches_the_card(tmp_path):
    """28.09.2026: O1 sendete Ersatzprogramm, der Tracker machte aus den
    Publikumsfragen der Kinder-Uni die Einwohnerfragestunde. Weder das
    Urteil „anderes" noch ein Zitat ohne Aufruf darf einen Stand zeigen."""
    store = _store(tmp_path)
    try:
        tracker, fake = _tracker(store, [
            # Das Modell erkennt Ersatzprogramm — und nennt trotzdem einen TOP.
            '{"broadcast": "anderes", "transitions": [{"at": "0:05", "kind": "top", "top": "5",'
            ' "evidence": "eine Frage auf der linken Seite"}], "top": "5", "phase": "aussprache",'
            ' "speaker": "Frau Drügemöller", "evidence": "eine Frage auf der linken Seite"}',
            # Das Modell hält es für den Rat, aber niemand ruft einen Punkt auf.
            '{"broadcast": "rat", "transitions": [{"at": "0:20", "kind": "top", "top": "5",'
            ' "evidence": "eine Frage auf der rechten Seite"}], "top": "5", "phase": "aussprache",'
            ' "evidence": "eine Frage auf der rechten Seite"}',
            # Ein erfundenes Zitat: steht so nicht im Transkript.
            '{"broadcast": "rat", "transitions": [{"at": "0:35", "kind": "top", "top": "5",'
            ' "evidence": "Wir kommen zur Einwohnerfragestunde"}], "top": "5", "phase": "aufruf"}',
        ])
        with mock.patch.object(livetracker.llm, "chat_complete", fake):
            tracker.on_window(0, 15, [(5.0, "Die letzte Frage, eine Frage auf der linken Seite.")], False)
            tracker.on_window(15, 30, [(20.0, "Und eine Frage auf der rechten Seite.")], False)
            tracker.on_window(30, 45, [(35.0, "Wie viele Liter Wasser gibt es?")], False)
        assert store.get_live_state(200) is None
        assert store.live_events(200) == []
        assert tracker.on_air is False and tracker.off_air_windows == 1
        tracker.finish(t_to=45)
        state = store.get_live_state(200)
        assert state["finished"] is True and state["item_number"] is None
    finally:
        store.close()


def test_off_air_withdraws_the_state_and_the_session_brings_it_back(tmp_path):
    """Fällt die Übertragung mitten in der Sitzung aus, verschwindet der
    Stand nach OFF_AIR_SECONDS; setzt sie wieder ein, kommt er nach
    RESUME_SECONDS zurück — ohne dass erst ein neuer Punkt aufgerufen wird."""
    store = _store(tmp_path)
    call = ('{"broadcast": "rat", "transitions": [{"at": "0:02", "kind": "top", "top": "9.3",'
            ' "evidence": "Punkt 9.3"}], "top": "9.3", "phase": "aufruf"}')
    other = '{"broadcast": "anderes", "transitions": [], "top": null, "phase": "unklar"}'
    council = '{"broadcast": "rat", "transitions": [], "top": "9.3", "phase": "aussprache"}'
    off = livetracker.OFF_AIR_SECONDS // 15
    back = livetracker.RESUME_SECONDS // 15
    try:
        tracker, fake = _tracker(store, [call] + [other] * off + [council] * back)
        with mock.patch.object(livetracker.llm, "chat_complete", fake):
            tracker.on_window(0, 15, [(2.0, "Wir kommen zu Punkt 9.3.")], False)
            assert store.get_live_state(200)["item_number"] == "9.3"
            t = 15
            for i in range(off):
                tracker.on_window(t, t + 15, [(t + 1.0, "Es folgt ein Vortrag.")], False)
                t += 15
                if i < off - 1:
                    assert store.get_live_state(200) is not None
            assert store.get_live_state(200) is None
            # Der Aufruf bleibt als Ereignis stehen.
            assert [e["item_number"] for e in store.live_events(200)] == ["9.3"]
            for i in range(back):
                tracker.on_window(t, t + 15, [(t + 1.0, "Herr Baak, bitte.")], False)
                t += 15
                if i < back - 1:
                    assert store.get_live_state(200) is None
        state = store.get_live_state(200)
        assert state["item_number"] == "9.3" and state["finished"] is False
        assert state["since"] == "2026-08-31T18:00:02+00:00"
    finally:
        store.close()
