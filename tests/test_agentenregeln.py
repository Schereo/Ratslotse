"""Die Regeln, die Agents lesen, müssen zum Repo passen.

**Warum das ein Test ist.** An diesem Repo arbeiten mehrere Coding-Agents
parallel, und sie lesen unterschiedliche Dateien: Claude Code liest
``CLAUDE.md`` (samt der verzeichnis-lokalen Fassungen), Codex liest
``AGENTS.md``. Bis 09/2026 trug ``AGENTS.md`` vier Zeilen Arbeitsablauf und
sonst nichts — ein Agent, der nur sie las, kannte weder das Branch-Modell noch
die Changelog-Pflicht noch die Designsprache.

Zwei Dateien mit denselben Regeln laufen auseinander; das ist keine Vermutung,
sondern die Erfahrung dieses Repos mit jeder doppelt geführten Wahrheit.
``AGENTS.md`` ist deshalb ein Symlink, und dieser Test hält ihn dort fest.

Dazu zwei Drift-Prüfungen: Die Tabelle der verzeichnis-lokalen Regeln muss
vollständig sein, und ``scripts/pruefe.py`` muss jeden Prüfschritt kennen, den
die CI fährt — sonst heißt „lokal grün" wieder etwas anderes als „CI grün".
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]


def test_agents_md_ist_ein_symlink_auf_claude_md():
    """Eine Quelle für beide Agenten — nicht zwei Dateien, die driften."""
    agents = WURZEL / "AGENTS.md"
    assert agents.is_symlink(), (
        "AGENTS.md ist kein Symlink mehr. Codex liest diese Datei und sonst "
        "keine; als eigene Kopie veraltet sie lautlos.\n"
        "  git rm AGENTS.md && ln -s CLAUDE.md AGENTS.md"
    )
    assert Path(agents.readlink()).name == "CLAUDE.md", (
        f"AGENTS.md zeigt auf {agents.readlink()}, erwartet wird CLAUDE.md."
    )
    assert agents.read_text() == (WURZEL / "CLAUDE.md").read_text()


def _verzeichnis_regeln() -> set[Path]:
    """Alle verzeichnis-lokalen CLAUDE.md, relativ zur Wurzel."""
    gefunden = set()
    for pfad in WURZEL.rglob("CLAUDE.md"):
        rel = pfad.relative_to(WURZEL)
        if rel == Path("CLAUDE.md"):
            continue  # die Wurzeldatei selbst
        teile = set(rel.parts)
        if teile & {"node_modules", ".git", ".venv", ".claude", "DerivedData", ".build"}:
            continue
        gefunden.add(rel)
    return gefunden


def test_die_wurzel_kennt_jede_verzeichnis_regel():
    """Eine Regeldatei, die in der Übersicht fehlt, findet niemand.

    Und umgekehrt: ein Eintrag ohne Datei ist ein toter Link im Repo, das
    öffentlich ist.
    """
    text = (WURZEL / "CLAUDE.md").read_text()
    genannt = {Path(m) for m in re.findall(r"\(([\w./-]*CLAUDE\.md)\)", text)}
    genannt = {p for p in genannt if p != Path("CLAUDE.md")}
    vorhanden = _verzeichnis_regeln()

    fehlen = sorted(str(p) for p in vorhanden - genannt)
    assert not fehlen, (
        "Diese Regeldateien stehen in keiner Übersicht in CLAUDE.md:\n  "
        + "\n  ".join(fehlen)
    )
    tot = sorted(str(p) for p in genannt - vorhanden)
    assert not tot, (
        "CLAUDE.md verweist auf Regeldateien, die es nicht gibt:\n  "
        + "\n  ".join(tot)
    )


def _ci_schritte(datei: Path) -> set[str]:
    """Die Werkzeuge, die ein Workflow in seinen ``run:``-Blöcken aufruft."""
    marken: set[str] = set()
    for zeile in datei.read_text().splitlines():
        nackt = zeile.strip()
        if nackt.startswith("#"):
            continue
        marken |= set(re.findall(r"scripts/[\w-]+\.(?:py|mjs)", nackt))
        for wort, muster in (("ruff", r"\bruff check\b"),
                             ("pytest", r"\bpytest\b"),
                             ("tsc", r"\btsc --noEmit\b"),
                             ("next lint", r"\bnext lint\b")):
            if re.search(muster, nackt):
                marken.add(wort)
    return marken


def test_pruefe_kennt_jeden_schritt_der_ci():
    """``scripts/pruefe.py`` ist der eine Befehl vor dem Push.

    Wenn die CI einen Schritt bekommt, den er nicht kennt, ist er wieder eine
    unvollständige Kopie — und genau das war der Zustand, den er ablösen
    sollte (vier Befehle in CONTRIBUTING.md, drei in test.yml, drei in
    frontend.yml).
    """
    quelle = (WURZEL / "scripts" / "pruefe.py").read_text()
    verlangt: set[str] = set()
    for name in ("test.yml", "frontend.yml"):
        verlangt |= _ci_schritte(WURZEL / ".github" / "workflows" / name)

    # Die Marken sind Dateinamen bzw. Werkzeugnamen; sie müssen im Skript
    # vorkommen. Pfade werden dort relativ zum jeweiligen Arbeitsverzeichnis
    # geschrieben, deshalb reicht der Dateiname — und ein mehrteiliger
    # Werkzeugname („next lint") steht dort als Liste einzelner Wörter.
    def kennt(marke: str) -> bool:
        return (marke in quelle or Path(marke).name in quelle
                or all(w in quelle for w in marke.split()))

    fehlen = sorted(m for m in verlangt if not kennt(m))
    assert not fehlen, (
        "Diese Prüfschritte fährt die CI, scripts/pruefe.py kennt sie nicht:\n  "
        + "\n  ".join(fehlen)
        + "\nTrag sie in PRUEFUNGEN ein, sonst heißt „lokal grün“ wieder "
          "etwas anderes als „CI grün“."
    )
    assert verlangt, "Aus den Workflows wurde kein einziger Schritt gelesen — Parser kaputt?"


def test_pruefe_laeuft_und_zaehlt_seine_pruefungen_auf():
    """``--liste`` ist die Selbstauskunft; sie darf nicht kaputtgehen."""
    r = subprocess.run([sys.executable, "scripts/pruefe.py", "--liste"],
                       cwd=WURZEL, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "schnell" in r.stdout
    assert len(r.stdout.strip().splitlines()) >= 5


def test_die_hooks_sind_ausfuehrbar():
    """Ein Hook ohne Ausführungsrecht wird von git wortlos übersprungen."""
    import os

    for name in ("pre-commit", "pre-push"):
        hook = WURZEL / ".githooks" / name
        assert hook.exists(), f".githooks/{name} fehlt."
        assert os.access(hook, os.X_OK), (
            f".githooks/{name} ist nicht ausführbar — git überspringt ihn "
            f"dann kommentarlos.\n  chmod +x .githooks/{name}"
        )
