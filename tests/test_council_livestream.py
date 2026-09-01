"""council/livestream.py — Mitschnitt-Helfer: Zeitmarken, Loop-Wächter,
Schlussformel, Parallel-Transkription (ffmpeg und LLM gemockt)."""
from __future__ import annotations

from unittest import mock

from council import livestream


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
    assert [s for s, _ in segs] == [5, 610]


def test_record_and_transcribe_without_ffmpeg(tmp_path):
    with mock.patch.object(livestream, "start_recording", return_value=None):
        assert livestream.record_and_transcribe(tmp_path) == []
