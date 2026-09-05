"""council/livestream.py — Mitschnitt-Helfer: Zeitmarken, Loop-Wächter,
Schlussformel, Parallel-Transkription (ffmpeg und LLM gemockt)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from council import livestream
from scripts import record_council_livestream


# ------------------------------------------------------------- parse_segments

def test_parse_segments_with_marks():
    text = ("[00:00] Erster Absatz der Sitzung.\n"
            "[00:27] Weitere Wortmeldung sehe ich nicht. Herr Niederstein.\n"
            "[01:09] Selbst wenn der gesetzliche Druck nicht da wäre.")
    segs = livestream.parse_segments(text, chunk_offset=600)
    assert [s for s, _ in segs] == [600, 627, 669]
    assert segs[1][1].startswith("Weitere Wortmeldung")


def test_parse_segments_without_marks_falls_back_to_chunk_start():
    segs = livestream.parse_segments("Nur Text ohne jede Marke.", 1200)
    assert segs == [(1200.0, "Nur Text ohne jede Marke.")]


def test_parse_segments_empty():
    assert livestream.parse_segments("", 0) == []


# ------------------------------------------------------------- Loop-Wächter

def test_looks_looped_detects_gemini_collapse():
    # Der gemessene Kollaps vom 01.09.: eine kurze Phrase endlos.
    assert livestream._looks_looped("so ein " * 300)
    # Echte Rede wiederholt sich nicht so.
    assert not livestream._looks_looped(
        "Sehr geehrte Damen und Herren, wir kommen zur Abstimmung über den "
        "Beschlussvorschlag. " * 3)


def test_looks_fabricated_by_chars_per_second():
    # Die Live-Probe vom 01.09.: 58k Zeichen aus 80 s Musik = fabuliert.
    assert livestream._looks_fabricated("x" * 58_000, 80)
    # 600 s echte Rede liegen bei ~9k Zeichen — weit unter der Grenze.
    assert not livestream._looks_fabricated("x" * 9_000, 600)


def test_empty_provider_responses_drop_only_the_chunk(tmp_path, monkeypatch, caplog):
    """Drei leere Antworten verwerfen nur dieses Stück; der lokale Fallback
    bleibt trotz des zentralen Guards erreichbar."""
    chunk = tmp_path / "chunk_004.mp3"
    chunk.write_bytes(b"audio")
    calls = []

    def empty_response(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=None, usage=None)

    monkeypatch.setattr(livestream.llm, "chat_complete", empty_response)
    with caplog.at_level("WARNING"):
        assert livestream.transcribe_chunk(chunk) == ""
    assert len(calls) == 3
    assert all(call["_allow_empty_response"] is True for call in calls)
    assert "dreimal leere Antwort" in caplog.text


def test_parse_segments_caps_marks_beyond_chunk_end():
    """Zeitmarken hinter dem Stück-Ende sind Fortschreibung ohne Audio —
    ab dort wird gekappt (Live-Probe 01.09.: [2:49] in einem 80-s-Stück)."""
    text = ("[00:10] Echte Rede im Stück.\n"
            "[01:05] Noch knapp in der Toleranz.\n"
            "[02:49] Fabulierte Fortsetzung weit hinter dem Audio.\n"
            "[04:00] Noch mehr davon.")
    segs = livestream.parse_segments(text, chunk_offset=0, chunk_seconds=80)
    assert [t for _, t in segs] == ["Echte Rede im Stück.",
                                   "Noch knapp in der Toleranz."]


# ------------------------------------------------------------ Schlussformel

def test_closing_formula_variants():
    for satz in (
        "Damit schließe ich den öffentlichen Teil der Sitzung.",
        "Ich schließe die Sitzung und wünsche einen schönen Abend.",
        "Der öffentliche Teil der Ratssitzung ist damit dann geschlossen.",
        # Die ASR verschreibt „Ratssitzung" gern — das echte Sitzungsende
        # vom 01.06. kam als „Ratsetzung" durch und muss trotzdem greifen.
        "So, der öffentliche Teil der Ratsetzung ist damit dann geschlossen.",
    ):
        assert livestream.CLOSING_RE.search(satz), satz
    assert not livestream.CLOSING_RE.search(
        "Wir werden die Sitzung wie geplant fortsetzen.")


# ------------------------------------------- record_and_transcribe (gemockt)

class _FakeProc:
    """Tut so, als liefe ffmpeg: nach dem ersten poll() 'beendet'."""

    def __init__(self):
        self._polls = 0

    def poll(self):
        self._polls += 1
        return None if self._polls <= 1 else 0

    def terminate(self):
        self._polls = 99

    def wait(self, timeout=None):
        return 0


class _FailedProc:
    """ffmpeg ist vor dem ersten vollständigen Chunk fehlgeschlagen."""

    def poll(self):
        return 1

    def terminate(self):
        raise AssertionError("beendeten Prozess nicht terminieren")


class _TerminatedProc:
    """SIGTERM nach gefundener Schlussformel ist ein erwartetes Ende."""

    def __init__(self):
        self.terminated = False

    def poll(self):
        return -15 if self.terminated else None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return -15


def test_record_and_transcribe_transcribes_finished_chunks(tmp_path):
    (tmp_path / "chunk_000.mp3").write_bytes(b"a")
    (tmp_path / "chunk_001.mp3").write_bytes(b"b")
    texts = {"chunk_000.mp3": "[00:05] Anfang der Sitzung.",
             "chunk_001.mp3": "[00:10] Damit schließe ich die Sitzung."}
    with mock.patch.object(livestream, "start_recording",
                           return_value=_FakeProc()), \
         mock.patch.object(livestream, "transcribe_chunk",
                           side_effect=lambda p, attempt=0: texts[p.name]):
        segs = livestream.record_and_transcribe(tmp_path, poll_seconds=0)
    assert [s for s, _ in segs] == [5, livestream.CHUNK_SECONDS + 10]


def test_recording_continues_after_one_empty_transcript_chunk(tmp_path, monkeypatch):
    """Ein ausgefallener erster Chunk darf ffmpeg und die späteren Chunks der
    einmaligen Sitzung nicht mit abräumen."""
    (tmp_path / "chunk_000.mp3").write_bytes(b"a")
    (tmp_path / "chunk_001.mp3").write_bytes(b"b")
    calls = []

    def responses(**kwargs):
        calls.append(kwargs)
        content = (None if len(calls) <= 3 else
                   "[00:10] Damit schließe ich die Sitzung.")
        choices = None if content is None else [SimpleNamespace(
            message=SimpleNamespace(content=content))]
        return SimpleNamespace(choices=choices, usage=None)

    monkeypatch.setattr(livestream.llm, "chat_complete", responses)
    monkeypatch.setattr(livestream, "start_recording", lambda *_args: _FakeProc())
    segments = livestream.record_and_transcribe(tmp_path, poll_seconds=0)
    assert segments == [(livestream.CHUNK_SECONDS + 10, "Damit schließe ich die Sitzung.")]
    assert len(calls) == 4
    assert all(call["_allow_empty_response"] is True for call in calls)


def test_record_and_transcribe_without_ffmpeg(tmp_path):
    with mock.patch.object(livestream, "start_recording", return_value=None):
        assert livestream.record_and_transcribe(tmp_path) == []


def test_record_and_transcribe_raises_on_ffmpeg_failure(tmp_path):
    with mock.patch.object(livestream, "start_recording",
                           return_value=_FailedProc()):
        with pytest.raises(RuntimeError, match="ffmpeg-Aufnahme mit Exitcode 1"):
            livestream.record_and_transcribe(tmp_path, poll_seconds=0)


def test_record_and_transcribe_accepts_intentional_sigterm(tmp_path):
    (tmp_path / "chunk_000.mp3").write_bytes(b"a")
    (tmp_path / "chunk_001.mp3").write_bytes(b"b")
    texts = {
        "chunk_000.mp3": "[00:05] Damit schließe ich die Sitzung.",
        "chunk_001.mp3": "[00:01] Abspann.",
    }
    with mock.patch.object(livestream, "start_recording",
                           return_value=_TerminatedProc()), \
         mock.patch.object(livestream, "transcribe_chunk",
                           side_effect=lambda p, attempt=0: texts[p.name]):
        segments = livestream.record_and_transcribe(tmp_path, poll_seconds=0)
    assert [text for _, text in segments] == [
        "Damit schließe ich die Sitzung.", "Abspann."]


def test_livestream_retry_uses_fresh_directory(tmp_path, monkeypatch):
    """Chunks eines abgebrochenen Laufs dürfen nie im Retry auftauchen."""
    root = tmp_path / "recordings"
    root.mkdir()
    (root / "chunk_000.mp3").write_bytes(b"alter lauf")
    monkeypatch.setattr(record_council_livestream, "RECORDING_ROOT", root)

    seen: list[Path] = []

    def fake_record(run_dir: Path, on_chunk=None):
        seen.append(run_dir)
        assert not list(run_dir.glob("chunk_*.mp3"))
        (run_dir / "chunk_000.mp3").write_bytes(b"dieser lauf")
        return [(0.0, "Transkript")]

    with mock.patch.object(record_council_livestream.livestream,
                           "record_and_transcribe", side_effect=fake_record):
        assert record_council_livestream._record_fresh(4702)
        assert record_council_livestream._record_fresh(4702)

    assert len(seen) == 2
    assert seen[0] != seen[1]
    assert all(not path.exists() for path in seen)
    # Ein Rest aus dem alten, nicht isolierten Layout bleibt zwar liegen, ist
    # aber in keinem der beiden neuen Run-Verzeichnisse sichtbar.
    assert (root / "chunk_000.mp3").read_bytes() == b"alter lauf"


def test_recorder_does_not_repeat_existing_livestream_results():
    today = record_council_livestream.datetime.now(
        record_council_livestream.TZ
    ).date().isoformat()
    store = mock.Mock()
    store.sessions_needing_video_check.return_value = [{
        "ksinr": 4702,
        "session_date": today,
        "session_time": "17:00",
    }]
    store.get_video_results.return_value = [{"video_id": ""}]

    with mock.patch.object(record_council_livestream, "CouncilStore",
                           return_value=store), \
         mock.patch.object(record_council_livestream, "_record_fresh") as record:
        assert record_council_livestream.main() == {"sitzung_heute": 0}
    record.assert_not_called()


# ------------------------------------------------- Haken für die Live-Verfolgung

def test_on_chunk_receives_each_chunk_and_the_closing_flag(tmp_path):
    (tmp_path / "chunk_000.mp3").write_bytes(b"a")
    (tmp_path / "chunk_001.mp3").write_bytes(b"b")
    texts = {"chunk_000.mp3": "[00:05] Wir kommen zu Punkt 6.1.",
             "chunk_001.mp3": "[00:10] Damit schließe ich die Sitzung."}
    seen = []
    with mock.patch.object(livestream, "start_recording",
                           return_value=_FakeProc()), \
         mock.patch.object(livestream, "transcribe_chunk",
                           side_effect=lambda p, attempt=0: texts[p.name]):
        livestream.record_and_transcribe(
            tmp_path, poll_seconds=0,
            on_chunk=lambda idx, segs, closing: seen.append((idx, segs, closing)))
    assert [(i, c) for i, _, c in seen] == [(0, False), (1, True)]
    assert seen[0][1] == [(5, "Wir kommen zu Punkt 6.1.")]


def test_on_chunk_failure_does_not_stop_the_recording(tmp_path, caplog):
    """Der Live-Stand ist Zugabe: Ein Fehler darin verliert kein Stück."""
    (tmp_path / "chunk_000.mp3").write_bytes(b"a")
    (tmp_path / "chunk_001.mp3").write_bytes(b"b")
    texts = {"chunk_000.mp3": "[00:05] Anfang.",
             "chunk_001.mp3": "[00:10] Damit schließe ich die Sitzung."}

    def kaputt(idx, segs, closing):
        raise RuntimeError("Tracker tot")

    with mock.patch.object(livestream, "start_recording",
                           return_value=_FakeProc()), \
         mock.patch.object(livestream, "transcribe_chunk",
                           side_effect=lambda p, attempt=0: texts[p.name]), \
         caplog.at_level("ERROR"):
        segs = livestream.record_and_transcribe(tmp_path, poll_seconds=0, on_chunk=kaputt)
    assert len(segs) == 2
    assert "Live-Verfolgung für Stück 0 fehlgeschlagen" in caplog.text


def test_parse_segments_spreads_unmarked_paragraphs_over_the_chunk():
    """Ohne Marken (2 von 23 Stücken der Probe vom 31.08.) wird der Text
    nach Zeichenanteil über das Stück verteilt — die Live-Verfolgung braucht
    das WANN, nicht nur das WAS."""
    text = "Erster Absatz mit zwanzig Zeichen.\n\nZweiter Absatz, ebenso lang etwa.\n\nDritter."
    segs = livestream.parse_segments(text, chunk_offset=120, chunk_seconds=120)
    assert len(segs) == 3
    assert segs[0][0] == 120
    assert 120 < segs[1][0] < segs[2][0] < 240
    # Ohne Stücklänge bleibt es beim alten Verhalten: alles auf den Anfang.
    assert livestream.parse_segments(text, 120) == [(120.0, text.strip())]
