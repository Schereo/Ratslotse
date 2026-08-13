"""Der Wächter gegen fremde E-Mail-Adressen im Repo.

Hintergrund: 12.08.2026 stand die Adresse einer echten Nutzerin im Docstring von
``scripts/qa_verlauf.py``. Das Herausbekommen kostete einen History-Rewrite und
eine Support-Anfrage bei GitHub. Diese Tests halten fest, dass der Check den
Fall erkennt — und dass er den echten Bestand nicht fälschlich anmeckert, denn
ein Check, der ständig grundlos rot ist, wird abgeschaltet.

Zwei Vorkehrungen in dieser Datei sind selbst Teil der Lehre:

1. Die Negativ-Beispiele stehen auf der TLD ``.invalid`` — RFC 2606 reserviert
   sie für garantiert nicht auflösbare Namen, sie können also niemandem gehören.
   Und sie stehen bewusst **nicht** auf der Erlaubtliste des Linters, sonst
   prüften diese Tests nichts mehr.
2. Sie werden über ``_fremd()`` zur Laufzeit zusammengesetzt statt als Literal
   hingeschrieben. Sonst müsste man diese Datei vom Linter ausnehmen — und
   ausgerechnet die Datei über Adress-Lecks wäre dann sein blinder Fleck.

(Die erste Fassung hatte beides nicht und benutzte die echte Adresse als
Testdatum. Der pre-commit-Hook hat den Commit geblockt.)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.lint_adressen import maskieren, pruefen  # noqa: E402


def _fremd(lokal: str, domain: str = "freemailer.invalid") -> str:
    """Eine Beispieladresse, die der Linter anmeckern soll — zusammengesetzt,
    damit in dieser Datei kein vollständiges Adress-Literal steht."""
    return f"{lokal}@{domain}"


def _schreiben(tmp_path: Path, inhalt: str, name: str = "beispiel.py") -> str:
    pfad = tmp_path / name
    pfad.write_text(inhalt, encoding="utf-8")
    return str(pfad)


def test_faengt_den_echten_fall(tmp_path):
    """Die Konstellation vom 12.08.: eine fremde Adresse als Beispielaufruf im
    Docstring — genau so ist sie damals ins Repo gekommen."""
    adresse = _fremd("nachname")
    pfad = _schreiben(
        tmp_path,
        f'"""Aufruf:\n\n    python scripts/qa_verlauf.py {adresse}\n"""\n',
    )
    treffer = pruefen([pfad])
    assert len(treffer) == 1
    _, zeile, fund = treffer[0]
    assert zeile == 3 and fund == adresse


@pytest.mark.parametrize("adresse", [
    "person@example.org",     # RFC 2606 — kann niemandem gehören
    "ratslotse@timsigl.de",   # eigene Kontaktadresse
    "noreply@ratslotse.de",   # eigener Absender
    "b@test.de",              # Fixture-Domain der Suite
    "f@x.de",                 # einzeln erlaubte Fixture
])
def test_erlaubte_adressen_schlagen_nicht_an(tmp_path, adresse):
    pfad = _schreiben(tmp_path, f"kontakt = '{adresse}'\n")
    assert pruefen([pfad]) == []


@pytest.mark.parametrize("lokal,domain", [
    ("max.mustermann", "freemailer.invalid"),      # Freemailer-Fall
    ("info", "irgendeine-behoerde.invalid"),       # Organisations-Postfach
    ("vorname", "firma.invalid"),
])
def test_fremde_adressen_schlagen_an(tmp_path, lokal, domain):
    pfad = _schreiben(tmp_path, f"# Beispiel: {_fremd(lokal, domain)}\n")
    assert len(pruefen([pfad])) == 1


def test_ausgabe_verraet_die_adresse_nicht():
    """CI-Logs eines öffentlichen Repos sind öffentlich — die Fundstelle darf
    dort nicht im Klartext landen, sonst wiederholt der Check das Leck."""
    maskiert = maskieren(_fremd("nachname"))
    assert "nachname" not in maskiert
    assert maskiert.startswith("n") and maskiert.endswith("@freemailer.invalid")


def test_binaerdateien_stuerzen_nicht_ab(tmp_path):
    pfad = tmp_path / "bild.bin"
    pfad.write_bytes(b"\xff\xd8\xff\x00 " + _fremd("nicht", "lesbar.invalid").encode() + b" \x00\xfe")
    assert pruefen([str(pfad)]) == []


def test_lockfiles_sind_ausgenommen(tmp_path):
    """Lockfiles tragen Adressen von Paket-Autoren aus Upstream-Meldungen —
    nicht von uns geschrieben, nicht von uns zu entfernen. Der Ausschluss muss
    auch bei absoluten Pfaden greifen (daran ist die erste Fassung gescheitert)."""
    unter = tmp_path / "web" / "frontend"
    unter.mkdir(parents=True)
    lock = unter / "package-lock.json"
    lock.write_text(f'{{"deprecated": "contact {_fremd("i", "upstream.invalid")}"}}\n',
                    encoding="utf-8")
    assert pruefen([str(lock)]) == []


def test_repo_ist_sauber():
    """Regressionsschutz für den echten Bestand — diese Datei eingeschlossen.

    Schlägt der Test an, ist gerade eine fremde Adresse hinzugekommen: nicht den
    Test anpassen, sondern die Adresse entfernen."""
    wurzel = Path(__file__).resolve().parents[1]
    dateien = subprocess.run(["git", "ls-files"], cwd=wurzel,
                             capture_output=True, text=True).stdout.splitlines()
    treffer = pruefen([str(wurzel / d) for d in dateien if d])
    assert treffer == [], f"{len(treffer)} fremde Adresse(n) im Repo"
