"""council/stream_stt.py — Streaming-Transkription: Wortliste, Nachrichten,
Fenster, Ablauf mit gefälschtem Websocket (kein Netz, kein ffmpeg)."""
from __future__ import annotations

import io
import json
import threading
from types import SimpleNamespace
from unittest import mock

import pytest

from council import livestream, stream_stt
from scripts import record_council_livestream


@pytest.fixture(autouse=True)
def _schlussformel_sofort(monkeypatch):
    monkeypatch.setattr(livestream, "CLOSING_MIN_SECONDS", 0)


def test_vocabulary_takes_surnames_and_parties_once():
    people = [{"name": "Christoph Baak"}, {"name": "Susanne Drügemöller"}, {"name": "Christoph Baak"}, {"name": ""}]
    vocab = stream_stt.vocabulary(people)
    assert vocab[:2] == ["Baak", "Drügemöller"]
    assert "BSW" in vocab and vocab.count("Baak") == 1


def test_session_config_is_german_pcm_with_vocabulary():
    cfg = stream_stt.session_config(["Baak"])
    assert cfg["language_config"]["languages"] == ["de"]
    assert (cfg["encoding"], cfg["sample_rate"], cfg["channels"]) == ("wav/pcm", 16000, 1)
    assert cfg["realtime_processing"]["custom_vocabulary"] is True
    assert cfg["realtime_processing"]["custom_vocabulary_config"]["vocabulary"] == ["Baak"]
    assert cfg["messages_config"]["receive_partial_transcripts"] is False
    assert stream_stt.session_config([])["realtime_processing"]["custom_vocabulary"] is False


def test_parse_transcript_only_takes_final_utterances():
    final = json.dumps({"type": "transcript", "data": {"is_final": True, "utterance": {
        "text": " Herr Paul, dann Herr Bark. ", "start": 132.0, "end": 133.1}}})
    assert stream_stt.parse_transcript(final) == (132.0, 133.1, "Herr Paul, dann Herr Bark.")
    partial = json.dumps({"type": "transcript", "data": {"is_final": False, "utterance": {"text": "Herr", "start": 132.0}}})
    assert stream_stt.parse_transcript(partial) is None
    assert stream_stt.parse_transcript(json.dumps({"type": "end_session"})) is None
    assert stream_stt.parse_transcript("kein json") is None
    leer = json.dumps({"type": "transcript", "data": {"is_final": True, "utterance": {"text": "  ", "start": 1}}})
    assert stream_stt.parse_transcript(leer) is None


def test_windower_dispatches_after_settle_and_flushes_on_close():
    seen = []
    w = stream_stt.Windower(lambda a, b, segs, closing: seen.append((a, b, segs, closing)),
                            window_seconds=15, settle=6, trigger=None)
    w.add((3.0, "eins"))
    w.advance(15.0)
    assert seen == []            # Fenster 0–15 wartet 6 s auf Nachzügler
    w.advance(21.0)
    assert seen == [(0.0, 15.0, [(3.0, "eins")], False)]
    w.add((16.0, "zwei")); w.add((14.5, "nachzügler"))
    w.advance(50.0)              # 15–30 fällig ab 36 s, 30–45 erst ab 51 s
    assert [(a, b) for a, b, _, _ in seen] == [(0.0, 15.0), (15.0, 30.0)]
    assert seen[1][2] == [(16.0, "zwei"), (14.5, "nachzügler")]
    w.add((52.0, "schluss"))
    w.close()
    assert seen[-1] == (30.0, 50.0, [(52.0, "schluss")], True)


def test_windower_fires_at_once_when_the_chair_calls_an_item():
    """„Wir kommen zu Punkt 9.3" soll nicht auf die Fenstergrenze warten —
    dafür gibt es das Streaming überhaupt."""
    seen = []
    w = stream_stt.Windower(lambda a, b, segs, closing: seen.append((a, b, [t for _, t in segs])),
                            window_seconds=15, settle=6)
    w.advance(7.0)
    w.add((6.5, "Wir kommen zu Tagesordnungspunkt 9.3."))
    assert seen == [(0.0, 7.0, ["Wir kommen zu Tagesordnungspunkt 9.3."])]
    # Innerhalb der Sperrfrist löst eine zweite Anrede nichts aus …
    w.advance(9.0)
    w.add((8.5, "Frau Drügemöller, bitte."))
    assert len(seen) == 1
    # … danach schon; die reguläre Grenze verschiebt sich hinter das Fenster.
    w.advance(13.0)
    w.add((12.5, "Herr Paul hat das Wort."))
    assert seen[-1] == (7.0, 13.0, ["Frau Drügemöller, bitte.", "Herr Paul hat das Wort."])
    w.advance(21.5)              # nächste reguläre Grenze ist 15 s (+6 Settle)
    assert seen[-1][:2] == (13.0, 15.0)
    assert w.triggered == 2


def test_windower_survives_a_failing_tracker(caplog):
    def kaputt(a, b, segs, closing):
        raise RuntimeError("Tracker tot")
    w = stream_stt.Windower(kaputt, window_seconds=15, settle=0, trigger=None)
    with caplog.at_level("ERROR"):
        w.advance(15.0)
    assert w.dispatched == 1 and "fehlgeschlagen" in caplog.text


# ------------------------------------------------ Ablauf mit falschem Websocket

class _FakeWS:
    """Nimmt PCM-Rahmen an und meldet je 10 s Audio eine fertige Äußerung;
    auf stop_recording folgt end_session."""

    def __init__(self, script):
        self.script = script          # {audio_sekunde: text}
        self.sent_seconds = 0.0
        self._out = []
        self._cv = threading.Condition()
        self.closed = False

    def send(self, frame):
        if isinstance(frame, bytes):
            self.sent_seconds += stream_stt.FRAME_SECONDS
            for at, text in list(self.script.items()):
                if self.sent_seconds >= at:
                    self.script.pop(at)
                    self._push(json.dumps({"type": "transcript", "data": {"is_final": True, "utterance": {
                        "text": text, "start": at - 2, "end": at}}}))
        elif json.loads(frame).get("type") == "stop_recording":
            self._push(json.dumps({"type": "end_session"}))

    def _push(self, msg):
        with self._cv:
            self._out.append(msg)
            self._cv.notify_all()

    def __iter__(self):
        while True:
            with self._cv:
                while not self._out:
                    if self.closed:
                        return
                    self._cv.wait(0.05)
                msg = self._out.pop(0)
            yield msg
            if json.loads(msg).get("type") == "end_session":
                return

    def close(self):
        self.closed = True
        with self._cv:
            self._cv.notify_all()


def _pcm(seconds: float) -> SimpleNamespace:
    """ffmpeg-Ersatz: so viele Bytes Stille, wie Sekunden Audio."""
    return SimpleNamespace(stdout=io.BytesIO(b"\0" * int(seconds * stream_stt.SAMPLE_RATE * 2)),
                           poll=lambda: 0, terminate=lambda: None, wait=lambda timeout=None: 0, kill=lambda: None)


def test_record_and_transcribe_streams_windows_and_stops_at_closing(monkeypatch):
    script = {5.0: "Wir kommen zu Punkt 6.1.", 30.0: "Frau Drügemöller, bitte.",
              52.0: "Damit schließe ich die Sitzung.", 70.0: "Abspann, nie gesehen."}
    fake = _FakeWS(script)
    monkeypatch.setattr(stream_stt, "open_session", lambda vocab: "wss://fake")
    monkeypatch.setattr(stream_stt.ws_client, "connect", lambda url, **kw: fake)
    monkeypatch.setattr(stream_stt, "ffmpeg_pcm", lambda source: _pcm(120))
    windows = []
    # pace=20: 5 ms je Rahmen, damit der Leser-Thread die Schlussformel
    # sieht, bevor die Datei zu Ende gesendet ist (wie im Echtzeitbetrieb).
    segs = stream_stt.record_and_transcribe(
        on_window=lambda a, b, s, closing: windows.append(([t for _, t in s], closing)),
        source="datei.m4a", people=[{"name": "Susanne Drügemöller"}], window_seconds=15, pace=20)
    assert [t for _, t in segs] == ["Wir kommen zu Punkt 6.1.", "Frau Drügemöller, bitte.",
                                    "Damit schließe ich die Sitzung."]
    assert segs[0][0] == 3.0                     # start der Äußerung, nicht ihr Ende
    # Aufruf und Worterteilung lösen sofort aus, der Schluss kommt als
    # letztes Fenster mit closing.
    assert windows[0] == (["Wir kommen zu Punkt 6.1."], False)
    assert (["Frau Drügemöller, bitte."], False) in windows
    assert windows[-1][1] is True and "Damit schließe ich die Sitzung." in windows[-1][0]
    assert fake.sent_seconds < 70                # nach der Schlussformel wird nicht weitergesendet


def test_open_session_without_key_is_unavailable(monkeypatch):
    monkeypatch.setattr(stream_stt, "API_KEY", "")
    with pytest.raises(stream_stt.StreamUnavailable):
        stream_stt.open_session([])


def test_recorder_falls_back_to_chunks_when_streaming_is_unavailable(monkeypatch):
    monkeypatch.setattr(stream_stt, "API_KEY", "geheim")
    monkeypatch.setattr(stream_stt, "record_and_transcribe",
                        mock.Mock(side_effect=stream_stt.StreamUnavailable("Sitzung nicht eröffnet")))
    tracker = SimpleNamespace(on_chunk=lambda *a: None, on_window=lambda *a: None, people=[], chunk_seconds=15)
    with mock.patch.object(record_council_livestream, "_record_fresh", return_value=[(0.0, "x")]) as fresh:
        segs, weg = record_council_livestream._record(4702, tracker)
    assert (segs, weg) == ([(0.0, "x")], "chunks")
    assert tracker.chunk_seconds == livestream.CHUNK_SECONDS
    fresh.assert_called_once()


def test_recorder_prefers_streaming_when_configured(monkeypatch):
    monkeypatch.setattr(stream_stt, "API_KEY", "geheim")
    monkeypatch.setattr(stream_stt, "record_and_transcribe", mock.Mock(return_value=[(1.0, "y")]))
    with mock.patch.object(record_council_livestream, "_record_fresh") as fresh:
        segs, weg = record_council_livestream._record(4702, None)
    assert (segs, weg) == ([(1.0, "y")], "gladia")
    fresh.assert_not_called()
