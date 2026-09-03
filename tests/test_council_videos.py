"""council/videos.py — Video-Ergebnisse: Textwerkzeuge, Konsens, Store.

Kein Netz, kein LLM: `_ask` wird gemockt; geprüft werden die Sicherungen,
an denen die Messung vom 31.08.2026 hing (Ö-Präfix, Beleg-Prüfung,
Zwei-Pass-Konsens, vote-nur-wenn-belegt) und der Store-Roundtrip.
"""
from __future__ import annotations

from unittest import mock

import pytest

from council import videos
from council.store import CouncilStore


# ------------------------------------------------------------ Textwerkzeuge

def test_strip_prefix_handles_oe_and_n():
    # „Ö" ist kein ASCII-O — eine Zeichenklasse [OoNn] ließe es durch;
    # genau daran scheiterte der erste Prototyp (0 Treffer).
    assert videos.strip_prefix("Ö 10.3") == "10.3"
    assert videos.strip_prefix("N 4.2") == "4.2"
    assert videos.strip_prefix("8.1") == "8.1"
    assert videos.strip_prefix("") == ""


def test_strip_prefix_keeps_dringlichkeits_namespace():
    """„DZT 1" ist NICHT „Ö 1": Dringlichkeitsanträge zählen eigenständig.

    Ein `^[^\\d]+`-Schnitt verkürzte beide auf „1"; am 02.09.2026 hing
    dadurch die Sachabstimmung über den PAK-Dringlichkeitsantrag am TOP
    „Feststellung der Beschlussfähigkeit" — über den nie abgestimmt wird —
    und beim Antrag selbst stand nichts."""
    assert videos.strip_prefix("DZT 1") == "DZT 1"
    assert videos.strip_prefix("DZT 1") != videos.strip_prefix("Ö 1")


def test_fold_matches_asr_variance():
    # Modell zitiert mit Satzzeichen, Transkript ohne — gefaltet gleich.
    assert videos._fold("Dann ist der mehrheitlich angenommen.") == \
        videos._fold("dann ist der mehrheitlich angenommen")
    assert videos._fold("Bäder") == "baeder"


def test_flatten_anchors_are_folded_positions():
    segments = [(10.0, "Ähm, erster Teil."), (20.0, "Zweiter Teil!")]
    text, anchors = videos._flatten(segments)
    folded = videos._fold(text)
    # Der zweite Anker steht exakt am gefalteten Beginn des zweiten Segments.
    assert anchors[1][0] == len(videos._fold(segments[0][1]))
    assert folded[anchors[1][0]:].startswith("zweiterteil")
    assert videos._seconds_at(anchors, anchors[1][0]) == 20.0
    assert videos._seconds_at(anchors, 0) == 10.0


def test_resolve_vote_only_claims_what_wording_carries():
    # Gezählte Gegenstimme → mehrheitlich.
    assert videos.resolve_vote({"no_votes": 4, "beleg": "x"}) == "majority"
    # Wort „einstimmig" im Beleg → einstimmig.
    assert videos.resolve_vote({"no_votes": None,
                                "beleg": "dann ist das einstimmig angenommen"}) == "unanimous"
    # Bloßes „mehrheitlich" der Leitung ohne Zahl: offen — dieselbe Formel
    # stand im Prüfbestand einmal für Protokoll-„einstimmig" und einmal
    # für 18 ungezählte Gegenstimmen.
    assert videos.resolve_vote({"no_votes": None,
                                "beleg": "eine Enthaltung, mehrheitlich angenommen"}) is None


def test_find_video_tolerates_title_date_lag():
    """Das Titel-Datum läuft dem Sitzungsdatum bis zu einem Tag nach
    (Video „24.02.2026" war die Sitzung vom 23.02.) — rückwärts nie."""
    listing = ("aaa\tIrgendwas anderes\n"
               "bbb\tRatssitzung Oldenburg | 24.02.2026\n"
               "ccc\tRatssitzung Oldenburg | 09.02.2026\n")
    with mock.patch.object(videos, "_run_yt_dlp", return_value=listing):
        assert videos.find_video("2026-02-23")["video_id"] == "bbb"
        assert videos.find_video("2026-02-09")["video_id"] == "ccc"
        # Ein ÄLTERES Video zählt nie als Treffer für eine spätere Sitzung.
        assert videos.find_video("2026-02-25") is None
        assert videos.find_video("2026-03-16") is None


# ------------------------------------------------------------------ Konsens

AGENDA = [
    {"item_number": "Ö 7.1", "title": "Umgestaltung des Bahnhofsvorplatzes"},
    {"item_number": "Ö 7.2", "title": "Umgestaltung des Uhlhornsweges Beschluss: geändert"},
]

QUOTE = ("Wenn Sie dem Beschlussvorschlag folgen, bitte ich um das Handzeichen. "
         "Gegenstimmen, Enthaltung, dann ist der einstimmig angenommen")
TRANSCRIPT = [(100.0, "Dann machen wir mit 7.1 weiter."),
              (200.0, QUOTE),
              (300.0, "Weiter mit 7.2.")]


def _finding(nr="7.1", outcome="accepted", beleg=QUOTE, **kw):
    return {"nr": nr, "art": "haupt", "outcome": outcome, "vote": None,
            "no_votes": None, "abstentions": None, "beleg": beleg, **kw}


def _extract_with(pass_a: list[dict], pass_b: list[dict]) -> list[dict]:
    # _one_pass liefert (Befunde, ausgefallene Abschnitte).
    with mock.patch.object(videos, "_one_pass",
                           side_effect=[(pass_a, set()), (pass_b, set())]):
        return videos.extract_results(TRANSCRIPT, AGENDA)


def test_consensus_keeps_agreeing_results_with_timestamp():
    out = _extract_with([_finding()], [_finding()])
    assert len(out) == 1
    r = out[0]
    assert r["item_number"] == "7.1"
    assert r["outcome"] == "accepted"
    assert r["vote"] == "unanimous"           # Wort steht im Beleg
    # Timestamp zeigt auf das Segment des Belegs (200 s).
    assert r["video_seconds"] == 200


def test_disagreeing_passes_are_withheld():
    out = _extract_with([_finding(outcome="accepted")],
                        [_finding(outcome="rejected")])
    assert out == []


def test_invented_quote_is_dropped():
    # Sicherung 2: das Zitat muss wörtlich im Transkript stehen — ein
    # umformuliertes fällt in BEIDEN Pässen raus (fing 7 Stück im Prüflauf).
    fake = _finding(beleg="Der Rat hat den Vorschlag ohne Gegenrede gebilligt "
                          "und einstimmig angenommen im Sinne der Vorlage")
    out = _extract_with([fake], [fake])
    assert out == []


def test_unknown_item_number_is_dropped():
    out = _extract_with([_finding(nr="99.9")], [_finding(nr="99.9")])
    assert out == []


def test_dringlichkeitsantrag_keeps_its_own_number():
    """Ein Ergebnis für „DZT 1" landet bei DZT 1 — nicht bei „Ö 1"."""
    agenda = AGENDA + [{"item_number": "Ö 1",
                        "title": "Feststellung der Beschlussfähigkeit"},
                       {"item_number": "DZT 1",
                        "title": "Dringlichkeitsantrag: festgestellte PAK-Belastung"}]
    fund = _finding(nr="DZT 1")
    with mock.patch.object(videos, "_one_pass",
                           side_effect=[([fund], set()), ([fund], set())]):
        out = videos.extract_results(TRANSCRIPT, agenda)
    assert [r["item_number"] for r in out] == ["DZT 1"]


def test_missing_in_one_pass_is_withheld():
    out = _extract_with([_finding()], [])
    assert out == []


def test_failed_chunk_is_reported_not_swallowed(caplog):
    """Ein ausgefallener Abschnitt nimmt seine Region mit — das MUSS ins Log.

    Am 02.09.2026 fiel B/0 dreimal leer aus; mit ihm verschwanden lautlos
    alle vier Absetzungen, die zu Sitzungsbeginn verkündet worden waren.
    Ohne diese Warnung sieht so ein Lauf aus wie eine stille Sitzung."""
    with mock.patch.object(videos, "_one_pass",
                           side_effect=[([_finding()], set()),
                                        ([_finding()], {0})]):
        with caplog.at_level("WARNING"):
            videos.extract_results(TRANSCRIPT, AGENDA)
    assert "Abschnitte ausgefallen" in caplog.text


def test_empty_provider_responses_keep_local_retry_and_fail_only_chunk(monkeypatch, caplog):
    """Fünf leere Antworten enden als ausgefallener Abschnitt, nicht als
    Abbruch des ganzen Video-Laufs."""
    calls = []

    def empty_response(**kwargs):
        calls.append(kwargs)
        return type("Response", (), {"choices": None, "usage": None})()

    monkeypatch.setattr(videos.llm, "chat_complete", empty_response)
    monkeypatch.setattr(videos.time, "sleep", lambda _seconds: None)
    with caplog.at_level("ERROR"):
        found, failed = videos._one_pass("Ö 1\tTest", "Transkript", 0, "A")
    assert found == []
    assert failed == {0}
    assert len(calls) == videos.EMPTY_RETRIES + 1 == 5
    assert all(call["_allow_empty_response"] is True for call in calls)
    assert "Video-Lesen A/0 fehlgeschlagen" in caplog.text


def test_anchor_prefers_full_quote_over_ambiguous_head():
    """Die Abstimmungs-Formeln beginnen wortgleich — der 60-Zeichen-Kopf
    allein verankerte TOP 14.4 bei Minute 25 statt 1:50 (gemessen 31.08.).
    Das volle Zitat trägt den Übergang zum nächsten TOP und ist eindeutig."""
    formel = "Gibt es Gegenstimmen? Enthaltung einstimmig angenommen. Tagesordnungspunkt "
    segs = [(100.0, formel + "sechs zwei Stadion GmbH und KKG Jahresabschluss."),
            (500.0, "Aussprache dazwischen, viele Worte, ganz andere Dinge."),
            (900.0, formel + "sieben eins Umgestaltung des Bahnhofsvorplatzes.")]
    text, anchors = videos._flatten(segs)
    folded = videos._fold(text)
    quote = formel + "sieben eins Umgestaltung des Bahnhofsvorplatzes."
    pos = videos._anchor_position(folded, "7.1", quote, quote)
    assert videos._seconds_at(anchors, pos) == 900.0


# -------------------------------------------------------------------- Store

@pytest.fixture()
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    s._conn.execute(
        "INSERT INTO council_sessions (ksinr, committee, session_date, session_time,"
        " location, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
        (4702, "Rat", "2026-08-31", "17:00", "Rathaus", ""),
    )
    s._conn.commit()
    return s


def test_video_results_roundtrip_and_replace(store):
    rows = [{"item_number": "7.1", "outcome": "accepted", "vote": "unanimous",
             "no_votes": None, "abstentions": 1, "quote": "…",
             "video_seconds": 200}]
    assert store.save_video_results(4702, "vid123", "test-model", rows) == 1
    got = store.get_video_results(4702)
    assert len(got) == 1
    assert got[0]["item_number"] == "7.1"
    assert got[0]["video_id"] == "vid123"
    assert got[0]["video_seconds"] == 200
    # Zweiter Lauf ersetzt den Bestand komplett (Untertitel nachgereicht).
    store.save_video_results(4702, "vid123", "test-model",
                             [dict(rows[0], item_number="7.2")])
    got = store.get_video_results(4702)
    assert [r["item_number"] for r in got] == ["7.2"]


def test_sessions_needing_video_check(store):
    # Ohne decisions und ohne video_results → Kandidat.
    need = store.sessions_needing_video_check("2026-08-01")
    assert [s["ksinr"] for s in need] == [4702]

    # Der Livestream liefert schon Ergebnisse, aber noch keine Sprung-Links:
    # Der YouTube-Nachlauf muss die Sitzung weiter finden.
    store.save_video_results(4702, "", "livestream-model", [
        {"item_number": "7.1", "outcome": "accepted", "quote": "live"}])
    assert [s["ksinr"] for s in
            store.sessions_needing_video_check("2026-08-01")] == [4702]

    # Der YouTube-Lauf ersetzt den Livestream-Bestand vollständig und erst
    # dessen echte Video-ID schließt die Sitzung aus weiteren Läufen aus.
    store.save_video_results(4702, "vid123", "m", [
        {"item_number": "7.1", "outcome": "accepted", "quote": "x"}])
    assert store.sessions_needing_video_check("2026-08-01") == []
    assert [r["video_id"] for r in store.get_video_results(4702)] == ["vid123"]


def test_sessions_with_protocol_are_not_candidates(store):
    store._conn.execute(
        """INSERT INTO council_decisions (ksinr, position, item_number, outcome)
           VALUES (4702, 1, '7.1', 'angenommen')""")
    store._conn.commit()
    assert store.sessions_needing_video_check("2026-08-01") == []
