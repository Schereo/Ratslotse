"""Changelog-Fragmente: Form der Einträge und der Versionsschnitt.

Zwei Dinge hält diese Datei fest:

1. **Jedes Fragment im Bestand ist lesbar.** Ein Tippfehler im Frontmatter
   („kategorie: geändert " mit Leerzeichen, „fix" statt „behoben") fiele sonst
   erst beim Versionsschnitt auf — also Wochen später, wenn niemand mehr weiß,
   was gemeint war. Die Seite /changelog überspringt kaputte Fragmente still,
   damit ein Build nie daran scheitert; das Meckern ist genau deshalb Aufgabe
   dieses Tests.
2. **Der Schnitt funktioniert** — Fragment rein, Eintrag samt PR-Nummer an der
   richtigen Stelle raus, Datei weg. Die PR-Nummer kommt aus der Git-Historie;
   hier wird sie als Attrappe hereingereicht, damit der Test nicht von echten
   Commits abhängt.
3. **Aus dem Tag wird ein GitHub-Release.** Der Schritt fiel dreimal aus
   (v1.14.0, v1.15.0, v2.0.0 hingen als Tags ohne Release), deshalb steht er
   jetzt im Skript — und deshalb wird hier festgehalten, dass er den richtigen
   Abschnitt nimmt, zu lange Jahrgänge kürzt statt zu scheitern, und einem
   nachgereichten alten Release nicht „Latest" verpasst.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.changelog_schnitt import (  # noqa: E402
    GITHUB_TEXTGRENZE,
    KATEGORIEN,
    FragmentFehler,
    ReleaseFehler,
    _ist_neueste,
    abschnitt,
    kernsaetze,
    lies_fragment,
    pr_nummer,
    release,
    release_text,
    sammle_fragmente,
    schnitt,
)

WURZEL = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# (a) Form der Fragmente
# --------------------------------------------------------------------------

def test_bestand_ist_wohlgeformt():
    """Regressionsschutz für die echten Fragmente unter changelog.d/."""
    fragmente = sammle_fragmente(WURZEL / "changelog.d")
    for fragment in fragmente:
        assert fragment.category in KATEGORIEN
        assert fragment.heading
        assert len(fragment.text) > 30, f"{fragment.pfad.name}: Eintrag zu dünn"
        assert "(#" not in fragment.text, (
            f"{fragment.pfad.name}: Die PR-Nummer gehört nicht ins Fragment — "
            "der Schnitt holt sie aus der Git-Historie."
        )


def _fragment(tmp_path: Path, inhalt: str, name: str = "beispiel.md") -> Path:
    pfad = tmp_path / name
    pfad.write_text(inhalt, encoding="utf-8")
    return pfad


def test_liest_frontmatter_und_text(tmp_path):
    pfad = _fragment(tmp_path, "---\nkategorie: behoben\n---\n\n**Kurz.** Und\nüber zwei Zeilen.\n")
    fragment = lies_fragment(pfad)
    assert fragment.category == "behoben"
    assert fragment.heading == "Behoben"
    # Umbruch-Zeilen werden zu einem Fließtext zusammengezogen.
    assert fragment.text == "**Kurz.** Und über zwei Zeilen."


def test_umlaut_schreibweise_wird_gelesen(tmp_path):
    pfad = _fragment(tmp_path, "---\nkategorie: Geändert\n---\n\nEin Eintrag.\n")
    assert lies_fragment(pfad).heading == "Geändert"


@pytest.mark.parametrize("inhalt,part", [
    ("Kein Frontmatter, nur Text.\n", "Frontmatter"),
    ("---\nkategorie: repariert\n---\n\nText.\n", "unbekannt"),
    ("---\nkategorie: behoben\n---\n\n   \n", "kein Text"),
    ("---\nkategorie\n---\n\nText.\n", "key"),
])
def test_kaputte_fragmente_werfen(tmp_path, inhalt, part):
    pfad = _fragment(tmp_path, inhalt)
    with pytest.raises(FragmentFehler) as fehler:
        lies_fragment(pfad)
    assert part in str(fehler.value)


def test_ueberschrift_im_fragment_wird_abgewiesen(tmp_path):
    """Der Schnitt zieht ein Fragment zu EINEM Listenpunkt zusammen. Eine
    Überschrift darin landet deshalb mitten im Satz — genau so steckte #816
    im Changelog: „- ### Kurzfassungen: … Die Tragweite-Gründe …". Der Prüfer
    ließ das durch, weil er nur Frontmatter und Nicht-Leere ansah."""
    pfad = _fragment(
        tmp_path,
        "---\nkategorie: geaendert\n---\n\n"
        "### Kurzfassungen: genauer, aktuelleres Modell\n\n"
        "Die Tragweite-Gründe laufen jetzt auf einem anderen Modell.\n",
    )
    with pytest.raises(FragmentFehler, match="Überschrift"):
        lies_fragment(pfad)


def test_mehrere_absaetze_bleiben_erlaubt(tmp_path):
    """Nur die Überschrift ist das Problem, nicht der Aufbau: Absätze werden
    zu einem Fließtext verbunden, das ist gewollt."""
    pfad = _fragment(
        tmp_path,
        "---\nkategorie: geaendert\n---\n\n"
        "**Kernsatz.** Erster Absatz.\n\nZweiter Absatz.\n",
    )
    assert lies_fragment(pfad).text == "**Kernsatz.** Erster Absatz. Zweiter Absatz."


def test_readme_und_unterstrich_sind_keine_fragmente(tmp_path):
    _fragment(tmp_path, "# Wie das hier geht\n", name="README.md")
    _fragment(tmp_path, "Notiz\n", name="_entwurf.md")
    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    _fragment(tmp_path, "---\nkategorie: behoben\n---\n\nEcht.\n", name="echt.md")
    assert [f.pfad.name for f in sammle_fragmente(tmp_path)] == ["echt.md"]


# --------------------------------------------------------------------------
# (b) Der Schnitt
# --------------------------------------------------------------------------

CHANGELOG = """# Changelog

Alle nennenswerten Änderungen …

## [Unreleased]

### Behoben
- **Ein von Hand eingetragener Punkt.** Er stammt aus der Zeit vor den
  Fragmenten und muss den Schnitt unverändert überleben. (#100)

### Behoben
- **Ein zweiter Abschnitt gleichen Namens.** So sieht der echte Block aus:
  Jeder PR hängt seine eigene Überschrift an. (#101)

## [1.12.0] – 2026-08-16

### Behoben
- Irgendwas Älteres. (#99)

[Unreleased]: https://github.com/Schereo/Ratslotse/compare/v1.12.0...main
[1.12.0]: https://github.com/Schereo/Ratslotse/compare/v1.11.0...v1.12.0
"""


@pytest.fixture()
def repo(tmp_path):
    """Ein Mini-Repo: CHANGELOG.md mit Alt-Eintrag plus zwei Fragmente."""
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    ordner = tmp_path / "changelog.d"
    ordner.mkdir()
    (ordner / "neue-karte.md").write_text(
        "---\nkategorie: hinzugefuegt\n---\n\n**Eine neue Karte.** Sie zeigt etwas,\n"
        "das vorher niemand sehen konnte.\n", encoding="utf-8")
    (ordner / "andere-farbe.md").write_text(
        "---\nkategorie: behoben\n---\n\n**Ein Fehler weniger.** Der Knopf tut wieder,\n"
        "was draufsteht.\n", encoding="utf-8")
    return tmp_path


def test_schnitt_sortiert_ein_und_raeumt_auf(repo):
    result = schnitt("1.13.0", tag_iso="2026-08-17", wurzel=repo, nummern=lambda pfad: 777)
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")

    assert result.geschrieben and len(result.fragmente) == 2 and not result.ohne_nummer

    # Leeres [Unreleased] bleibt oben stehen, darunter die neue Version.
    assert "## [Unreleased]\n\n## [1.13.0] – 2026-08-17\n" in text

    neu = text.split("## [1.13.0]")[1].split("## [1.12.0]")[0]
    # Fragment mit Nummer, je Kategorie einsortiert …
    assert "### Hinzugefügt\n- **Eine neue Karte.**" in neu
    assert "(#777)" in neu
    # … die Alt-Einträge stehen unverändert im selben Block …
    assert "**Ein von Hand eingetragener Punkt.**" in neu and "(#100)" in neu
    assert "**Ein zweiter Abschnitt gleichen Namens.**" in neu and "(#101)" in neu
    # … und das behobene Fragment landet **einmal**, am Ende des ersten
    # gleichnamigen Abschnitts. Ohne Entdoppelung der Überschriften stünde es
    # so oft da, wie „### Behoben" im Block vorkommt.
    assert neu.count("### Behoben") == 2 and neu.count("### Hinzugefügt") == 1
    assert neu.count("**Ein Fehler weniger.**") == 1
    assert neu.count("**Eine neue Karte.**") == 1
    assert (neu.index("**Ein von Hand eingetragener Punkt.**")
            < neu.index("**Ein Fehler weniger.**")
            < neu.index("**Ein zweiter Abschnitt gleichen Namens.**"))

    # Die Zeilen bleiben auf Dateibreite umbrochen.
    assert max(len(z) for z in neu.split("\n")) <= 80

    # Fragmente sind weg, das Verzeichnis bleibt.
    assert list((repo / "changelog.d").glob("*.md")) == []
    assert (repo / "changelog.d").is_dir()


def test_schnitt_zieht_die_vergleichslinks_nach(repo):
    schnitt("1.13.0", tag_iso="2026-08-17", wurzel=repo, nummern=lambda pfad: 777)
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "[Unreleased]: https://github.com/Schereo/Ratslotse/compare/v1.13.0...main" in text
    assert "[1.13.0]: https://github.com/Schereo/Ratslotse/compare/v1.12.0...v1.13.0" in text


def test_trocken_schreibt_nichts(repo):
    vorher = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    result = schnitt("1.13.0", tag_iso="2026-08-17", wurzel=repo,
                       trocken=True, nummern=lambda pfad: 777)
    assert not result.geschrieben
    assert "## [1.13.0] – 2026-08-17" in result.text     # gerechnet …
    assert (repo / "CHANGELOG.md").read_text(encoding="utf-8") == vorher  # … aber nicht geschrieben
    assert len(list((repo / "changelog.d").glob("*.md"))) == 2


def test_fragment_ohne_auffindbare_nummer(repo, capsys):
    """Kein Commit gefunden → Eintrag ohne Nummer plus Warnung, kein Abbruch."""
    result = schnitt("1.13.0", tag_iso="2026-08-17", wurzel=repo, nummern=lambda pfad: None)
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    neu = text.split("## [1.13.0]")[1].split("## [1.12.0]")[0]
    assert "**Eine neue Karte.**" in neu and "(#777)" not in neu
    assert len(result.ohne_nummer) == 2
    assert "keine PR-Nummer" in capsys.readouterr().err


def test_pr_nummer_nimmt_den_anlegenden_commit(tmp_path):
    """Der Squash-Merge trägt die Nummer im Titel — ältester Commit zuerst."""
    pfad = tmp_path / "x.md"
    assert pr_nummer(pfad, betreffe=["feat(haushalt): Konzernkarte (#578)",
                                     "fix: Tippfehler (#601)"]) == 578
    assert pr_nummer(pfad, betreffe=["wip: noch ohne PR"]) is None
    assert pr_nummer(pfad, betreffe=[]) is None


# --------------------------------------------------------------------------
# (c) GitHub-Release
# --------------------------------------------------------------------------

def test_abschnitt_nimmt_genau_eine_version(repo):
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    block = abschnitt(text, "1.12.0")
    assert "Irgendwas Älteres. (#99)" in block
    # Weder die eigene Überschrift noch der Nachbarblock noch die Link-Liste:
    assert "## [1.12.0]" not in block
    assert "Ein von Hand eingetragener Punkt" not in block
    assert "compare/" not in block


def test_abschnitt_ohne_version_wirft(repo):
    with pytest.raises(ReleaseFehler, match=r"9\.9\.9"):
        abschnitt((repo / "CHANGELOG.md").read_text(encoding="utf-8"), "9.9.9")


def test_kernsaetze_behalten_ueberschrift_und_nummer():
    block = (
        "### Hinzugefügt\n"
        "- **Eine neue Karte.** Sie zeigt etwas, das vorher niemand sehen\n"
        "  konnte, und der Absatz geht noch lange weiter. (#123)\n"
        "\n"
        "### Behoben\n"
        "- **Ein Fehler weniger.** Ohne Nummer, das kommt vor.\n"
    )
    kurz = kernsaetze(block)
    assert kurz.splitlines() == [
        "### Hinzugefügt",
        "- **Eine neue Karte.** (#123)",
        "",
        "### Behoben",
        "- **Ein Fehler weniger.**",
    ]


def test_kernsatz_faellt_auf_den_ersten_satz_zurueck():
    """Nicht jeder Eintrag beginnt fett — die Jahrgänge v1.0–v1.4 stammen aus der
    Zeit vor den Fragmenten und schreiben schlichte Sätze."""
    kurz = kernsaetze("- ### Kurzfassungen: genauer. Und dann viel mehr Text. (#816)")
    assert kurz == "- **Kurzfassungen: genauer.** (#816)"


def test_release_text_laesst_kurze_abschnitte_in_ruhe():
    block = "### Behoben\n- **Klein.** Passt. (#1)"
    assert release_text(block, "1.0.0") == block


def test_release_text_kuerzt_zu_lange_abschnitte():
    eintrag = "- **Kernsatz Nummer {n}.** " + ("Fließtext. " * 60) + "(#{n})\n"
    block = "### Hinzugefügt\n" + "".join(eintrag.format(n=i) for i in range(400))
    assert len(block) > GITHUB_TEXTGRENZE

    text = release_text(block, "1.14.0")
    assert len(text) < GITHUB_TEXTGRENZE
    assert "**Kernsatz Nummer 399.** (#399)" in text      # kein Abschneiden am Limit
    assert "blob/v1.14.0/CHANGELOG.md" in text            # Verweis auf den vollen Text
    assert "Fließtext." not in text


def test_nur_die_oberste_version_wird_latest(repo):
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    # Im Fixture steht [Unreleased] oben, darunter 1.12.0 als einzige Version.
    assert _ist_neueste(text, "1.12.0")
    assert not _ist_neueste(text, "1.11.0")


def test_release_trocken_ruft_kein_gh(repo, monkeypatch, capsys):
    """Der Probelauf fasst weder gh noch das Fernarchiv an — sonst wäre er auf
    einem Rechner ohne gh nicht zu gebrauchen."""
    import scripts.changelog_schnitt as modul

    def verboten(*args, **kwargs):  # pragma: no cover — soll nie laufen
        raise AssertionError("der Probelauf darf nichts nach außen tun")

    monkeypatch.setattr(modul, "_gh", verboten)
    monkeypatch.setattr(modul, "_tag_auf_remote", verboten)

    text = release("1.12.0", titel="v1.12.0 — Test", wurzel=repo, trocken=True)
    assert "Irgendwas Älteres. (#99)" in text
    assert "--latest" in capsys.readouterr().err


def test_release_ohne_gepushten_tag_wirft(repo, monkeypatch):
    """Lokal getaggt reicht nicht: Das Release zeigt auf den Stand bei GitHub."""
    import scripts.changelog_schnitt as modul
    monkeypatch.setattr(modul, "_tag_auf_remote", lambda version, wurzel=None: False)
    with pytest.raises(ReleaseFehler, match="nicht bei origin"):
        release("1.12.0", wurzel=repo)


def test_release_legt_nichts_doppelt_an(repo, monkeypatch):
    import scripts.changelog_schnitt as modul
    monkeypatch.setattr(modul, "_tag_auf_remote", lambda version, wurzel=None: True)
    monkeypatch.setattr(
        modul, "_gh",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, "", ""))
    with pytest.raises(ReleaseFehler, match="gibt es schon"):
        release("1.12.0", wurzel=repo)
