"""Drittanbieter-Actions hängen an einem Commit-SHA, nicht an einem Tag.

Ein Tag ist ein beweglicher Zeiger im fremden Repo. Wer ihn umhängt, lässt
seinen Code in unseren Workflows laufen — und `appleboy/ssh-action` bekommt
dort den Deploy-Schlüssel (`secrets.SSH_PRIVATE_KEY`, auch als `proxy_key`).
Gemeldet hat das die Sicherheitsprüfung im 11/2026; die Zeile stand damals in
24 Workflows. Inzwischen geht der Schlüssel an die eigene Action
``.github/actions/ssh`` (``tests/test_ssh_action.py``); der Pin bleibt für
alle übrigen Drittanbieter-Actions.

Erlaubt sind:

- ``uses: owner/repo@<40 Hex-Zeichen> # vX.Y.Z`` für alles außerhalb von
  ``actions/*`` und ``github/*``. Der Kommentar sagt Menschen, welche Version
  das ist, und Dependabot (``.github/dependabot.yml``) zieht ihn beim
  Nachziehen des SHA mit.
- lokale Actions (``./…``) und Docker-Abbilder mit ``@sha256:…``.

Den SHA nachsehen statt raten — ist das Tag annotiert, zeigt es auf ein
Tag-Objekt, nicht auf den Commit::

    git ls-remote https://github.com/OWNER/REPO 'refs/tags/vX.Y.Z' 'refs/tags/vX.Y.Z^{}'

Die Zeile mit ``^{}`` ist der Commit; fehlt sie, ist das Tag leichtgewichtig
und die erste Zeile ist der Commit.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GITHUB = ROOT / ".github"

#: Diese Organisationen gehören GitHub selbst; ihre Tags gelten als vertrauenswürdig.
FIRST_PARTY = {"actions", "github"}

#: Ausnahmen mit Grund, als (Datei, Action-Referenz). Jede ist eine Schuld:
#: Der zweite Test meldet, wenn sie nicht mehr gebraucht wird.
EXCEPTIONS: set[tuple[str, str]] = set()

_USES = re.compile(
    r"""^\s*(?:-\s*)?uses:\s*["']?(?P<ref>[^\s"'#]+)["']?\s*(?:#\s*(?P<comment>.*\S))?\s*$""")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_VERSION = re.compile(r"^v?\d+(?:\.\d+)*\S*$")


def _workflow_files() -> list[Path]:
    files = sorted((GITHUB / "workflows").glob("*.y*ml"))
    files += sorted((GITHUB / "actions").rglob("action.y*ml")) if (GITHUB / "actions").is_dir() else []
    return files


def _uses_lines() -> list[tuple[str, int, str, str | None]]:
    """Alle `uses:`-Zeilen als (Datei, Zeile, Referenz, Kommentar)."""
    found = []
    for path in _workflow_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = _USES.match(line)
            if match:
                found.append((str(path.relative_to(ROOT)), number, match["ref"], match["comment"]))
    return found


def _is_third_party(ref: str) -> bool:
    if ref.startswith(("./", "docker://")):
        return False
    return ref.split("/", 1)[0].lower() not in FIRST_PARTY


def _violations() -> dict[tuple[str, str], str]:
    """(Datei, Referenz) → was fehlt."""
    out: dict[tuple[str, str], str] = {}
    for file, number, ref, comment in _uses_lines():
        if ref.startswith("docker://"):
            if "@sha256:" not in ref:
                out[(file, ref)] = f"Zeile {number}: Docker-Abbild ohne @sha256:-Digest"
            continue
        if not _is_third_party(ref):
            continue
        _, _, version = ref.partition("@")
        if not _SHA.match(version):
            out[(file, ref)] = f"Zeile {number}: kein 40-stelliger Commit-SHA"
        elif not comment or not _VERSION.match(comment):
            out[(file, ref)] = f"Zeile {number}: Versionskommentar fehlt (`# vX.Y.Z`)"
    return out


def test_the_scanner_sees_the_workflows():
    """Ohne Treffer prüfte der Wächter nichts — etwa nach einem Umzug der Dateien."""
    refs = {ref.split("@")[0] for _, _, ref, _ in _uses_lines()}
    assert "actions/checkout" in refs
    assert "./.github/actions/ssh" in refs


def test_third_party_actions_are_pinned_to_a_commit_sha():
    new = {key: why for key, why in _violations().items() if key not in EXCEPTIONS}
    assert not new, (
        "Drittanbieter-Actions müssen an einem vollen Commit-SHA hängen, mit der "
        "Version als Kommentar — `uses: owner/repo@<sha> # vX.Y.Z`:\n"
        + "\n".join(f"  {file}: {ref} — {why}" for (file, ref), why in sorted(new.items()))
        + "\nSHA nachsehen: git ls-remote https://github.com/OWNER/REPO "
        "'refs/tags/vX.Y.Z' 'refs/tags/vX.Y.Z^{}' (die ^{}-Zeile ist der Commit).")


def test_exceptions_are_still_needed():
    stale = EXCEPTIONS - set(_violations())
    assert not stale, (
        f"{sorted(stale)} braucht keine Ausnahme mehr — "
        "aus EXCEPTIONS in tests/test_actions_pinned.py streichen.")


def test_dependabot_keeps_the_actions_current():
    """Ein gepinnter SHA wird nie von selbst neuer; ohne Dependabot veraltet er still."""
    config = yaml.safe_load((GITHUB / "dependabot.yml").read_text(encoding="utf-8"))
    ecosystems = {u.get("package-ecosystem") for u in config.get("updates", [])}
    assert "github-actions" in ecosystems, (
        "In .github/dependabot.yml fehlt der Eintrag `package-ecosystem: github-actions` — "
        "ohne ihn zieht niemand die gepinnten SHAs nach.")


def test_scanner_rules():
    """Die Regeln des Wächters an Beispielen, damit eine Regex-Änderung nicht still lockert."""
    sha = "029f5b4aeeeb58fdfe1410a5d17f967dacf36262"

    def parse(line: str) -> tuple[str, str | None]:
        match = _USES.match(line)
        assert match, line
        return match["ref"], match["comment"]

    assert parse(f"      - uses: appleboy/ssh-action@{sha} # v1.0.3") == (
        f"appleboy/ssh-action@{sha}", "v1.0.3")
    assert parse("        uses: 'appleboy/ssh-action@v1.0.3'") == ("appleboy/ssh-action@v1.0.3", None)
    assert _is_third_party("appleboy/ssh-action@v1")
    assert _is_third_party("owner/repo/.github/workflows/x.yml@main")
    assert not _is_third_party("actions/checkout@v4")
    assert not _is_third_party("github/codeql-action/init@v3")
    assert not _is_third_party("./.github/actions/lokal")
    assert _SHA.match(sha)
    assert not _SHA.match(sha[:7])
    assert not _SHA.match("v1.0.3")
