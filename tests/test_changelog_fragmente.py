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
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.changelog_schnitt import (  # noqa: E402
    KATEGORIEN,
    FragmentFehler,
    lies_fragment,
    pr_nummer,
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
        assert fragment.kategorie in KATEGORIEN
        assert fragment.ueberschrift
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
    assert fragment.kategorie == "behoben"
    assert fragment.ueberschrift == "Behoben"
    # Umbruch-Zeilen werden zu einem Fließtext zusammengezogen.
    assert fragment.text == "**Kurz.** Und über zwei Zeilen."


def test_umlaut_schreibweise_wird_gelesen(tmp_path):
    pfad = _fragment(tmp_path, "---\nkategorie: Geändert\n---\n\nEin Eintrag.\n")
    assert lies_fragment(pfad).ueberschrift == "Geändert"


@pytest.mark.parametrize("inhalt,teil", [
    ("Kein Frontmatter, nur Text.\n", "Frontmatter"),
    ("---\nkategorie: repariert\n---\n\nText.\n", "unbekannt"),
    ("---\nkategorie: behoben\n---\n\n   \n", "kein Text"),
    ("---\nkategorie\n---\n\nText.\n", "schluessel"),
])
def test_kaputte_fragmente_werfen(tmp_path, inhalt, teil):
    pfad = _fragment(tmp_path, inhalt)
    with pytest.raises(FragmentFehler) as fehler:
        lies_fragment(pfad)
    assert teil in str(fehler.value)


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
    ergebnis = schnitt("1.13.0", datum="2026-08-17", wurzel=repo, nummern=lambda pfad: 777)
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")

    assert ergebnis.geschrieben and len(ergebnis.fragmente) == 2 and not ergebnis.ohne_nummer

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
    schnitt("1.13.0", datum="2026-08-17", wurzel=repo, nummern=lambda pfad: 777)
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "[Unreleased]: https://github.com/Schereo/Ratslotse/compare/v1.13.0...main" in text
    assert "[1.13.0]: https://github.com/Schereo/Ratslotse/compare/v1.12.0...v1.13.0" in text


def test_trocken_schreibt_nichts(repo):
    vorher = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    ergebnis = schnitt("1.13.0", datum="2026-08-17", wurzel=repo,
                       trocken=True, nummern=lambda pfad: 777)
    assert not ergebnis.geschrieben
    assert "## [1.13.0] – 2026-08-17" in ergebnis.text     # gerechnet …
    assert (repo / "CHANGELOG.md").read_text(encoding="utf-8") == vorher  # … aber nicht geschrieben
    assert len(list((repo / "changelog.d").glob("*.md"))) == 2


def test_fragment_ohne_auffindbare_nummer(repo, capsys):
    """Kein Commit gefunden → Eintrag ohne Nummer plus Warnung, kein Abbruch."""
    ergebnis = schnitt("1.13.0", datum="2026-08-17", wurzel=repo, nummern=lambda pfad: None)
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    neu = text.split("## [1.13.0]")[1].split("## [1.12.0]")[0]
    assert "**Eine neue Karte.**" in neu and "(#777)" not in neu
    assert len(ergebnis.ohne_nummer) == 2
    assert "keine PR-Nummer" in capsys.readouterr().err


def test_pr_nummer_nimmt_den_anlegenden_commit(tmp_path):
    """Der Squash-Merge trägt die Nummer im Titel — ältester Commit zuerst."""
    pfad = tmp_path / "x.md"
    assert pr_nummer(pfad, betreffe=["feat(haushalt): Konzernkarte (#578)",
                                     "fix: Tippfehler (#601)"]) == 578
    assert pr_nummer(pfad, betreffe=["wip: noch ohne PR"]) is None
    assert pr_nummer(pfad, betreffe=[]) is None
