"""council/stt_retain.py — welche Stücke aufgehoben werden und wie."""
from __future__ import annotations

import subprocess

import pytest

from council import livestream, stt_retain


# --------------------------------------------------------------- select_indices

def test_select_indices_always_keeps_the_first_two():
    """Die ersten zwei Stücke sind Stille/Vorprogramm vor Sitzungsbeginn —
    die will die Stichprobe absichtlich sehen."""
    assert stt_retain.select_indices(5, keep=20) == [0, 1, 2, 3, 4]
    idx = stt_retain.select_indices(100, keep=10)
    assert idx[:2] == [0, 1]
    assert len(idx) == 10
    assert idx == sorted(idx) and len(set(idx)) == len(idx)


def test_select_indices_spreads_evenly_over_the_session():
    """Nicht die letzten/ersten ``keep`` Stücke — verteilt über die ganze
    Sitzung, sonst fehlt die Stichprobe am Sitzungsende."""
    idx = stt_retain.select_indices(600, keep=20)
    assert len(idx) == 20
    assert idx[-1] > 400          # reicht bis nahe ans Ende


def test_select_indices_disabled_or_empty():
    assert stt_retain.select_indices(50, keep=0) == []
    assert stt_retain.select_indices(0, keep=20) == []


def test_select_indices_keep_larger_than_n_returns_everything():
    assert stt_retain.select_indices(3, keep=20) == [0, 1, 2]


# --------------------------------------------------------------------- enabled

def test_enabled_reads_the_env_switch(monkeypatch):
    monkeypatch.setenv("COUNCIL_STT_BEHALTEN", "0")
    assert stt_retain.enabled() is False
    monkeypatch.setenv("COUNCIL_STT_BEHALTEN", "5")
    assert stt_retain.enabled() is True
    monkeypatch.delenv("COUNCIL_STT_BEHALTEN", raising=False)
    assert stt_retain.enabled() is True   # Vorgabe: an


def test_behalten_falls_back_on_garbage(monkeypatch, caplog):
    monkeypatch.setenv("COUNCIL_STT_BEHALTEN", "viel")
    with caplog.at_level("WARNING"):
        assert stt_retain._behalten() == 20
    assert "keine Zahl" in caplog.text


# ----------------------------------------------------------------------- retain

def test_retain_copies_selected_pieces_and_writes_comparison_text(tmp_path, monkeypatch):
    monkeypatch.setenv("RATSLOTSE_STT_AUDIO", str(tmp_path / "stt"))
    monkeypatch.setenv("COUNCIL_STT_BEHALTEN", "2")
    quelle = tmp_path / "lauf"
    quelle.mkdir()
    stuecke = []
    for i in range(5):
        p = quelle / f"chunk_{i:03d}.mp3"
        p.write_bytes(f"audio-{i}".encode())
        stuecke.append((p, f"Text {i}"))

    stt_retain.retain(4711, "chunks", stuecke)

    ziel = stt_retain.session_dir(4711)
    kopiert = sorted(p.name for p in ziel.glob("*.mp3"))
    assert kopiert == ["chunk_000.mp3", "chunk_001.mp3"]     # keep=2 → nur die Lead-Stücke
    assert (ziel / "chunk_000.chunks.txt").read_text(encoding="utf-8") == "Text 0"
    assert (ziel / "chunk_000.mp3").read_bytes() == b"audio-0"


def test_retain_disabled_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("RATSLOTSE_STT_AUDIO", str(tmp_path / "stt"))
    monkeypatch.setenv("COUNCIL_STT_BEHALTEN", "0")
    p = tmp_path / "chunk_000.mp3"
    p.write_bytes(b"a")
    stt_retain.retain(1, "chunks", [(p, "Text")])
    assert not stt_retain.session_dir(1).exists()


def test_retain_survives_a_missing_source_file(tmp_path, monkeypatch, caplog):
    """Ein Stück, das der Aufräumer schon gelöscht hat (Wettlauf), darf die
    Aufbewahrung nicht abbrechen lassen."""
    monkeypatch.setenv("RATSLOTSE_STT_AUDIO", str(tmp_path / "stt"))
    monkeypatch.setenv("COUNCIL_STT_BEHALTEN", "5")
    fehlt = tmp_path / "chunk_000.mp3"     # existiert nie
    da = tmp_path / "chunk_001.mp3"
    da.write_bytes(b"b")
    stt_retain.retain(2, "chunks", [(fehlt, "x"), (da, "y")])
    ziel = stt_retain.session_dir(2)
    assert [p.name for p in ziel.glob("*.mp3")] == ["chunk_001.mp3"]


def test_retain_never_raises_on_write_failure(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("RATSLOTSE_STT_AUDIO", str(tmp_path / "stt"))
    monkeypatch.setenv("COUNCIL_STT_BEHALTEN", "5")
    p = tmp_path / "chunk_000.mp3"
    p.write_bytes(b"a")
    monkeypatch.setattr(stt_retain.shutil, "copyfile",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("Platte voll")))
    with caplog.at_level("ERROR"):
        stt_retain.retain(3, "chunks", [(p, "x")])
    assert "fehlgeschlagen" in caplog.text


def test_cleanup_keeps_only_the_three_newest_sessions(tmp_path, monkeypatch):
    import time
    monkeypatch.setenv("RATSLOTSE_STT_AUDIO", str(tmp_path / "stt"))
    monkeypatch.setenv("COUNCIL_STT_BEHALTEN", "20")
    base = stt_retain.base_dir()
    for ksinr in (1, 2, 3, 4):
        d = base / str(ksinr)
        d.mkdir(parents=True)
        (d / "chunk_000.mp3").write_bytes(b"a")
        time.sleep(0.01)
    stt_retain._cleanup_old(base, keep_sessions=3)
    uebrig = sorted(p.name for p in base.iterdir())
    assert uebrig == ["2", "3", "4"]


# ----------------------------------------------------------------- retain_from_raw

def _ffmpeg_verfuegbar() -> bool:
    return livestream.ffmpeg_bin() is not None


@pytest.mark.skipif(not _ffmpeg_verfuegbar(), reason="kein ffmpeg installiert")
def test_retain_from_raw_cuts_generated_silence_into_chunks(tmp_path, monkeypatch):
    """Ohne echten Mitschnitt: ein 75-s-Stille-PCM (``anullsrc``) steht für
    den mitgeschriebenen Rohton des Streaming-Wegs — muss in 30-s-Stücke
    geschnitten, ausgewählt und mit dem passenden Gladia-Text abgelegt
    werden."""
    monkeypatch.setenv("RATSLOTSE_STT_AUDIO", str(tmp_path / "stt"))
    monkeypatch.setenv("COUNCIL_STT_BEHALTEN", "20")
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw = raw_dir / "raw.pcm"
    exe = livestream.ffmpeg_bin()
    subprocess.run([exe, "-nostdin", "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
                    "-t", "75", "-f", "s16le", str(raw)], check=True)
    segmente = [(5.0, "Wir kommen zu Punkt 1."), (35.0, "Frau Drügemöller."),
               (65.0, "Damit schließe ich die Sitzung.")]

    stt_retain.retain_from_raw(4242, raw, segmente, weg="gladia", chunk_seconds=30)

    ziel = stt_retain.session_dir(4242)
    stuecke = sorted(p.name for p in ziel.glob("*.mp3"))
    assert stuecke == ["chunk_000.mp3", "chunk_001.mp3", "chunk_002.mp3"]
    assert (ziel / "chunk_000.gladia.txt").read_text(encoding="utf-8") == "Wir kommen zu Punkt 1."
    assert (ziel / "chunk_002.gladia.txt").read_text(encoding="utf-8") == "Damit schließe ich die Sitzung."


def test_retain_from_raw_disabled_does_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("COUNCIL_STT_BEHALTEN", "0")
    stt_retain.retain_from_raw(1, tmp_path / "nichtda.pcm", [])
    # Kein Fehler, kein Verzeichnis — nur eine Aussage möglich: nichts passiert.


def test_retain_from_raw_missing_ffmpeg_logs_and_returns(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("RATSLOTSE_STT_AUDIO", str(tmp_path / "stt"))
    monkeypatch.setenv("COUNCIL_STT_BEHALTEN", "20")
    monkeypatch.setattr(livestream, "ffmpeg_bin", lambda: None)
    raw = tmp_path / "raw.pcm"
    raw.write_bytes(b"\0" * 100)
    with caplog.at_level("WARNING"):
        stt_retain.retain_from_raw(1, raw, [])
    assert "ffmpeg fehlt" in caplog.text
    assert not stt_retain.session_dir(1).exists()
