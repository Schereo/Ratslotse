"""Die Clip-Pipeline für „Neu bei Ratslotse": Jeder Clip hat sein Drehbuch.

Der Wächter hält Registry (``kern/releases.py``) und Drehbücher
(``web/frontend/release-clips/<version>.mjs``) gegeneinander — in beide
Richtungen, wie ``test_api_vertrag.py``: Ein Video ohne Drehbuch lässt sich
beim nächsten Release nicht neu aufnehmen, ein Drehbuch ohne Video ist
Ballast. Dazu die reinen Rechenschritte des Schnitts, in Millisekunden statt
in Minuten Rendering.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kern import releases  # noqa: E402
from scripts import release_clips  # noqa: E402


def test_jeder_browser_clip_hat_ein_drehbuch():
    for release in releases.RELEASES:
        fehlend, _ = release_clips.missing_and_stale(release)
        assert not fehlend, (
            f"{release.version}: Clips ohne Drehbuch: {', '.join(fehlend)} — "
            f"Eintrag in web/frontend/release-clips/{release.version}.mjs anlegen "
            f"(`scripts/release_clips.py skeleton {release.version}` zeigt die Form)")


def test_kein_drehbuch_ohne_clip():
    for release in releases.RELEASES:
        _, verwaist = release_clips.missing_and_stale(release)
        assert not verwaist, (
            f"{release.version}: Drehbücher ohne Video in kern/releases.py: "
            f"{', '.join(verwaist)} — Medium auf kind=\"video\" stellen oder den Eintrag löschen")


def test_der_drehbuch_name_ist_der_dateistamm(tmp_path, monkeypatch):
    """Die Form, auf die der Wächter sich verlässt: ``  name: {`` mit zwei
    Leerzeichen — so schreibt sie auch das Gerüst."""
    monkeypatch.setattr(release_clips, "STORYBOARDS", tmp_path)
    (tmp_path / "9.9.0.mjs").write_text(
        "export default {\n  teilen: {\n  },\n  live: {\n  },\n"
        "    // nicht: {\n};\n", encoding="utf-8")
    assert release_clips.storyboard_names("9.9.0") == ["teilen", "live"]
    assert release_clips.storyboard_names("0.0.0") == []


def test_das_geruest_traegt_jedes_web_highlight():
    release = releases.RELEASES[0]
    text = release_clips.skeleton(release)
    erwartet = [h for h in release.highlights if h.only != releases.NUR_NATIVE]
    assert text.count("async run(") == len(erwartet)
    for h in erwartet:
        assert h.title in text and repr(h.url) in text
    assert "await begin();" in text


def test_der_clip_beginnt_mit_dem_bild_das_gerade_stand(tmp_path):
    """Der Screencast liefert nur Bildwechsel. Bei begin() um 11.0 war Bild b
    (seit 10.5) zu sehen — es eröffnet den Clip und steht bis zum nächsten
    Wechsel; das letzte Bild steht bis zum Ende."""
    a, b, c, d = (tmp_path / f"{n}.jpg" for n in "abcd")
    frames = [(10.0, a), (10.5, b), (12.0, c), (12.4, d)]
    plan = release_clips.frame_plan(frames, begin=11.0, end=13.0)
    assert [f for f, _ in plan] == [b, c, d]
    assert [d_ for _, d_ in plan] == pytest.approx([1.0, 0.4, 0.6])
    # Ohne begin(): ab dem ersten Bild, ganze Länge.
    erstes = release_clips.frame_plan(frames, None, 13.0)[0]
    assert erstes[0] == a and erstes[1] == pytest.approx(0.5)
    # Ein Bild, das nach dem Ende noch eintrudelt, kommt nicht mehr vor.
    spaet = release_clips.frame_plan([(10.0, a), (14.0, b)], None, 13.0)
    assert [f for f, _ in spaet] == [a] and spaet[0][1] == pytest.approx(3.0)


def test_beat_zeiten_relativ_zum_clipanfang():
    frames = [(10.0, Path("a.jpg")), (10.5, Path("b.jpg"))]
    assert release_clips.clip_start(frames, 11.0) == 11.0
    assert release_clips.clip_start(frames, None) == 10.0
    assert release_clips.beat_times(11.0, [11.5, 12.9]) == pytest.approx([0.5, 1.9])


def test_erster_bildwechsel_gegen_das_ausgangsbild():
    """Ein langsam aufblendendes Blatt ändert je Bild wenig — gegen das
    Ausgangsbild aber bald genug. Verglichen wird deshalb mit dem ersten
    Bild, nicht mit dem Vorgänger."""
    def bild(hell: int) -> Image.Image:
        return Image.new("L", (12, 12), hell)
    frames = [bild(10), bild(11), bild(13), bild(16), bild(30), bild(30)]
    assert release_clips.first_change(frames, threshold=6.0) == 4
    assert release_clips.first_change([bild(10), bild(10)], threshold=6.0) is None
    assert release_clips.first_change([], threshold=6.0) is None
