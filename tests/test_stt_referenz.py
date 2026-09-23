"""eval/stt_referenz.py — Referenztext aus einer Untertitel-Attrappe schneiden,
ohne echte YouTube-Untertitel oder echtes Sitzungs-Audio."""
from __future__ import annotations

from eval import stt_referenz


# ------------------------------------------------------------------- top_aufrufe

def test_top_aufrufe_finds_the_number_in_different_phrasings():
    segmente = [(10.0, "Wir kommen zu Tagesordnungspunkt 6.1."),
               (40.0, "Ich rufe TOP 7 auf."),
               (70.0, "Punkt 8 bitte."),
               (90.0, "Keine Nummer hier.")]
    assert stt_referenz.top_aufrufe(segmente) == [
        (10.0, "6.1"), (40.0, "7"), (70.0, "8")]


def test_top_aufrufe_empty_input():
    assert stt_referenz.top_aufrufe([]) == []


# ---------------------------------------------------------------- schaetze_versatz

def test_schaetze_versatz_uses_the_median_of_shared_calls():
    stream = [(0.0, "6.1"), (100.0, "7")]
    video = [(305.0, "6.1"), (403.0, "7")]      # Versatz ~ +303..+305
    versatz = stt_referenz.schaetze_versatz(stream, video)
    assert 300 < versatz < 310


def test_schaetze_versatz_none_without_common_call():
    assert stt_referenz.schaetze_versatz([(0.0, "1")], [(0.0, "9")]) is None
    assert stt_referenz.schaetze_versatz([], []) is None


# ------------------------------------------------------------------- fenster_text

def test_fenster_text_joins_segments_in_the_window():
    segmente = [(0.0, "Erster Satz."), (15.0, "Zweiter Satz."), (35.0, "Fällt raus.")]
    assert stt_referenz.fenster_text(segmente, 0, 30) == "Erster Satz. Zweiter Satz."
    assert stt_referenz.fenster_text(segmente, 30, 60) == "Fällt raus."


def test_fenster_text_empty_window_is_empty_string():
    assert stt_referenz.fenster_text([(100.0, "spät")], 0, 30) == ""


# ---------------------------------------------------------------- gewaehlte_stuecke

def test_gewaehlte_stuecke_reads_either_production_path(tmp_path):
    (tmp_path / "chunk_000.mp3").write_bytes(b"a")
    (tmp_path / "chunk_000.chunks.txt").write_text("Gemini-Text", encoding="utf-8")
    (tmp_path / "chunk_001.mp3").write_bytes(b"b")
    (tmp_path / "chunk_001.gladia.txt").write_text("Gladia-Text", encoding="utf-8")
    (tmp_path / "chunk_002.mp3").write_bytes(b"c")   # kein Vergleichstext

    stuecke = stt_referenz.gewaehlte_stuecke(tmp_path)

    assert [(idx, text) for idx, _, text in stuecke] == [
        (0, "Gemini-Text"), (1, "Gladia-Text"), (2, "")]


# --------------------------------------------------------------------- erzeugen

def test_erzeugen_writes_a_txt_file_per_piece_shifted_by_the_offset(tmp_path):
    (tmp_path / "chunk_000.mp3").write_bytes(b"a")
    (tmp_path / "chunk_001.mp3").write_bytes(b"b")
    stuecke = [(0, tmp_path / "chunk_000.mp3", ""), (1, tmp_path / "chunk_001.mp3", "")]
    video_segmente = [(10.0, "Anfang der Sitzung."), (45.0, "Mitte der Sitzung.")]

    n = stt_referenz.erzeugen(stuecke, video_segmente, versatz=10.0, chunk_sekunden=30)

    assert n == 2
    assert (tmp_path / "chunk_000.txt").read_text(encoding="utf-8") == "Anfang der Sitzung."
    assert (tmp_path / "chunk_001.txt").read_text(encoding="utf-8") == "Mitte der Sitzung."


def test_main_end_to_end_with_a_fake_video_and_stream_transcript(tmp_path, monkeypatch, capsys):
    """Das ganze Werkzeug über die Kommandozeile, ohne echtes Netz: eigene
    Sitzungsordner-Struktur, eigene Untertitel-Attrappe, Versatz automatisch
    über den gemeinsamen TOP-Aufruf geschätzt."""
    monkeypatch.setenv("RATSLOTSE_STT_AUDIO", str(tmp_path / "stt"))
    from council import stt_retain
    ordner = stt_retain.session_dir(4711)
    ordner.mkdir(parents=True)
    (ordner / "chunk_000.mp3").write_bytes(b"a")
    (ordner / "chunk_000.chunks.txt").write_text(
        "Wir kommen zu Tagesordnungspunkt 6.1.", encoding="utf-8")
    (ordner / "chunk_001.mp3").write_bytes(b"b")
    (ordner / "chunk_001.chunks.txt").write_text("Aussprache ohne Aufruf.", encoding="utf-8")

    # Videotranskript: derselbe Aufruf 300 s später (Versatz), plus Folgetext.
    video_segmente = [(300.0, "Wir kommen zu Tagesordnungspunkt 6.1."),
                      (330.0, "Aussprache ohne Aufruf, mit mehr Worten.")]
    monkeypatch.setattr("eval.transkripte.SITZUNGEN", {4711: "fake-id"})
    monkeypatch.setattr("eval.transkripte.laden", lambda video_id: video_segmente)
    monkeypatch.setattr("sys.argv", ["stt_referenz.py", "4711"])

    rc = stt_referenz.main()

    assert rc == 0
    ausgabe = capsys.readouterr().out
    assert "+300.0 s" in ausgabe
    assert (ordner / "chunk_000.txt").read_text(encoding="utf-8") == "Wir kommen zu Tagesordnungspunkt 6.1."
    assert "Aussprache" in (ordner / "chunk_001.txt").read_text(encoding="utf-8")


def test_main_without_a_common_top_call_requires_manual_offset(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RATSLOTSE_STT_AUDIO", str(tmp_path / "stt"))
    from council import stt_retain
    ordner = stt_retain.session_dir(4712)
    ordner.mkdir(parents=True)
    (ordner / "chunk_000.mp3").write_bytes(b"a")
    monkeypatch.setattr("eval.transkripte.SITZUNGEN", {4712: "fake-id"})
    monkeypatch.setattr("eval.transkripte.laden", lambda video_id: [(0.0, "Nichts Gemeinsames.")])
    monkeypatch.setattr("sys.argv", ["stt_referenz.py", "4712"])

    assert stt_referenz.main() == 1
    assert "von Hand angeben" in capsys.readouterr().err
