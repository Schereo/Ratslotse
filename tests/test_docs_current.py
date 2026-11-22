"""Wächter: Die Technik-Doku nennt nur, was es im Code noch gibt — und umgekehrt.

**Wogegen das steht.** Die Doku unter ``docs-site/`` ist Prosa über Code, und
Prosa bricht nicht, wenn der Code sich ändert. Gemessen am 22.11.2026, bevor
es diese Datei gab:

* 14 Pfade in der Doku zeigten auf Dateien, die umgezogen oder gelöscht waren
  (``council/steuerkraft.py``, ``lib/push.ts``, ``scripts/bot_poll.py`` …),
* 24 von 34 Feature-Schaltern kamen in der Doku nicht vor,
* 83 von 153 Umgebungsvariablen, die der Code liest, standen nirgends,
* ein Link führte auf ``/app-und-konten/`` statt ``/docs/app-und-konten/``.

Nichts davon meldete sich. Der KI-Review je PR (``docs-review.yml``) berät
nur, und er sieht den Diff, nicht den Bestand.

**Was hier geprüft wird** — alles, was sich ohne Urteil entscheiden lässt:
erzeugte Referenzseiten gegen ihre Register, genannte Pfade, Symbole, Modelle,
API-Routen und Umgebungsvariablen gegen den Code, Links gegen die Seiten, die
Seitenleiste gegen die Dateien. Ob ein Absatz noch *stimmt*, sieht kein Test;
dafür verlangt ``kern/features.py`` zu jedem Schalter eine Doku-Stelle, so
entsteht die Beschreibung mit dem Feature und nicht ein Quartal später.

**Beide Richtungen**, wie jeder Wächter hier: Jede Ausnahmeliste wird auch
darauf geprüft, ob ihre Einträge noch gebraucht werden.
"""
from __future__ import annotations

import ast
import json
import re
import unicodedata
from functools import cache
from pathlib import Path

import pytest

from kern import features
from scripts import docs_reference

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs-site" / "src" / "content" / "docs"
ASTRO_CONFIG = ROOT / "docs-site" / "astro.config.mjs"
OPS_PAGE = "betrieb.md"

FIX_REFERENCE = "python scripts/docs_reference.py"


# --------------------------------------------------------------------------
# Die Doku lesen
# --------------------------------------------------------------------------

@cache
def pages() -> dict[str, tuple[str, ...]]:
    """``{"betrieb.md": (zeile, …)}`` für jede Seite."""
    return {
        p.relative_to(DOCS).as_posix(): tuple(p.read_text(encoding="utf-8").splitlines())
        for p in sorted(DOCS.rglob("*.md*"))
    }


def hand_written() -> dict[str, tuple[str, ...]]:
    return {name: lines for name, lines in pages().items()
            if not name.startswith("referenz/")}


def prose_lines(name: str):
    """``(zeilennummer, zeile)`` außerhalb von Code-Blöcken."""
    fenced = False
    for number, line in enumerate(pages()[name], 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            yield number, line


_SPAN = re.compile(r"`([^`\n]+)`")


def code_spans(name: str):
    """``(zeilennummer, inhalt)`` jeder Code-Spanne im Fließtext."""
    for number, line in prose_lines(name):
        for match in _SPAN.finditer(line):
            yield number, match.group(1)


def slug_of(heading: str) -> str:
    """Der Anker, den Starlight einer Überschrift gibt (github-slugger)."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = text.replace("`", "").replace("*", "").strip().lower()
    kept = "".join(
        ch for ch in text
        if ch in "-_ " or unicodedata.category(ch)[0] in "LNM")
    return kept.replace(" ", "-")


@cache
def anchors(name: str) -> frozenset[str]:
    seen: dict[str, int] = {}
    out = set()
    for _, line in prose_lines(name):
        match = re.match(r"#{1,6}\s+(.*?)\s*#*\s*$", line)
        if not match:
            continue
        slug = slug_of(match.group(1))
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        out.add(slug if count == 0 else f"{slug}-{count}")
    return frozenset(out)


def page_file(slug: str) -> str | None:
    """``"betrieb"`` → ``"betrieb.md"``; ``None``, wenn es die Seite nicht gibt."""
    slug = slug.strip("/")
    for candidate in (f"{slug}.md", f"{slug}.mdx", f"{slug}/index.md", f"{slug}/index.mdx"):
        if candidate in pages():
            return candidate
    if slug == "" and "index.mdx" in pages():
        return "index.mdx"
    return None


def missing_target(target: str) -> str | None:
    """``None``, wenn ``seite#anker`` existiert — sonst der Grund."""
    slug, _, anchor = target.partition("#")
    name = page_file(slug)
    if name is None:
        return f"die Seite „{slug}“ gibt es nicht"
    if anchor and anchor not in anchors(name):
        return f"auf „{name}“ gibt es keine Überschrift mit dem Anker „#{anchor}“"
    return None


# --------------------------------------------------------------------------
# Den Code lesen
# --------------------------------------------------------------------------

_CODE_DIRS = ("kern", "council", "web/backend", "scripts", "eval", "kommunalwahl")
_SKIP_PARTS = {"node_modules", ".venv", "__pycache__", ".next", "dist", "build", ".astro"}


@cache
def python_files() -> tuple[Path, ...]:
    out = []
    for top in _CODE_DIRS:
        for path in (ROOT / top).rglob("*.py"):
            if not _SKIP_PARTS.intersection(path.parts):
                out.append(path)
    return tuple(sorted(out))


@cache
def frontend_files() -> tuple[Path, ...]:
    out = []
    base = ROOT / "web" / "frontend"
    for pattern in ("*.ts", "*.tsx", "*.mjs"):
        for path in base.rglob(pattern):
            if not _SKIP_PARTS.intersection(path.parts):
                out.append(path)
    return tuple(sorted(out))


def _env_name(node: ast.AST, constants: dict[str, str] | None = None) -> str | None:
    """Der Name der Variable, die ein Aufruf liest — wörtlich oder über eine
    Konstante des Moduls (``URL_ENV = "RATSLOTSE_PROXY_URL"``)."""
    if isinstance(node, ast.Name) and constants:
        value = constants.get(node.id)
    elif isinstance(node, ast.Constant) and isinstance(node.value, str):
        value = node.value
    else:
        return None
    if value and re.fullmatch(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+", value):
        return value
    return None


def _string_constants(tree: ast.Module) -> dict[str, str]:
    """``{NAME: "wert"}`` für die Zuweisungen auf oberster Ebene eines Moduls."""
    out = {}
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) and node.value else [])
        value = getattr(node, "value", None)
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            for target in targets:
                if isinstance(target, ast.Name):
                    out[target.id] = value.value
    return out


def _literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float)) \
            and not isinstance(node.value, bool):
        return str(node.value)
    return None


def _reads_env(call: ast.Call) -> bool:
    """Ein Aufruf, der eine Umgebungsvariable liest: ``os.environ.get``,
    ``os.getenv`` oder einer der kleinen Helfer (``_env_float`` …)."""
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    if name in {"getenv"}:
        return True
    if name == "get" and isinstance(func, ast.Attribute):
        return "environ" in ast.unparse(func.value)
    return "env" in name.lower()


@cache
def env_in_code() -> dict[str, dict]:
    """``{NAME: {"files": {…}, "defaults": {…}}}`` — jede Umgebungsvariable,
    die der Code liest, mit den wörtlichen Vorgabewerten, wo es welche gibt.

    Drei Formen: der Aufruf mit Vorgabe (``os.environ.get("X", "1")``), der
    Rückfall (``os.environ.get("X") or "1"``) und ein Feld der
    ``Settings``-Klasse des Backends, dessen Name die Variable ist.
    """
    found: dict[str, dict] = {}

    def note(name: str, path: Path, default: str | None = None):
        entry = found.setdefault(name, {"files": set(), "defaults": set()})
        entry["files"].add(path.relative_to(ROOT).as_posix())
        if default is not None:
            entry["defaults"].add(default)

    for path in python_files():
        if "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        constants = _string_constants(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and node.args and _reads_env(node):
                name = _env_name(node.args[0], constants)
                if name:
                    default = _literal(node.args[1]) if len(node.args) > 1 else None
                    note(name, path, default)
            elif isinstance(node, ast.Subscript) and "environ" in ast.unparse(node.value):
                name = _env_name(node.slice, constants)
                if name:
                    note(name, path)
            elif isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) \
                    and isinstance(node.values[0], ast.Call) and node.values[0].args \
                    and _reads_env(node.values[0]):
                name = _env_name(node.values[0].args[0], constants)
                default = _literal(node.values[-1])
                if name and default is not None:
                    note(name, path, default)
            elif isinstance(node, ast.ClassDef) and any(
                    "BaseSettings" in ast.unparse(base) for base in node.bases):
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        default = _literal(item.value) if item.value else None
                        note(item.target.id.upper(), path, default)

    pattern = re.compile(r"process\.env\.([A-Z][A-Z0-9_]+)")
    for path in frontend_files():
        if {"tests", "scripts"}.intersection(path.parts) or path.name.endswith(".test.ts") \
                or path.name == "playwright.config.ts":
            continue
        for name in pattern.findall(path.read_text(encoding="utf-8", errors="ignore")):
            note(name, path)
    return found


# --------------------------------------------------------------------------
# 1. Die erzeugten Referenzseiten
# --------------------------------------------------------------------------

def test_reference_pages_match_registries():
    """Cron-Jobs, Feature-Schalter und Rollen stehen im Code an einer Stelle;
    die Seiten dazu werden erzeugt und dürfen dem Register nicht nachlaufen."""
    behind = docs_reference.stale()
    assert not behind, (
        f"Diese Referenzseiten passen nicht mehr zu ihrem Register: {behind}. "
        f"Beheben: {FIX_REFERENCE}")


def test_reference_folder_holds_only_generated_pages():
    """Eine handgeschriebene Seite im Ordner ``referenz/`` sähe aus wie eine
    erzeugte — und niemand hielte sie aktuell."""
    stray = sorted(
        name for name in pages()
        if name.startswith("referenz/") and name.removeprefix("referenz/") not in docs_reference.PAGES)
    assert not stray, (
        f"Im Ordner referenz/ liegen Seiten, die scripts/docs_reference.py nicht erzeugt: {stray}. "
        "Entweder dort als Seite eintragen oder in einen anderen Ordner legen.")
    for name in docs_reference.PAGES:
        text = "\n".join(pages()[f"referenz/{name}"])
        assert docs_reference.MARKER in text, f"referenz/{name} trägt den Erzeugt-Vermerk nicht."


def _section(name: str, heading: str) -> str:
    """Der Text unter einer Überschrift bis zur nächsten gleicher oder höherer Ebene."""
    lines = pages()[name]
    start = next(i for i, line in enumerate(lines) if line.strip() == heading)
    level = len(heading) - len(heading.lstrip("#"))
    end = next((i for i in range(start + 1, len(lines))
                if re.match(rf"#{{1,{level}}}\s", lines[i])), len(lines))
    return "\n".join(lines[start:end])


def test_every_cron_job_has_a_row_on_the_ops_page():
    """Die Betriebsseite trägt zu jedem Job die Zeile der crontab und den
    Zusammenhang. Das Register kennt nur den Takt in Worten — fehlt die Zeile
    hier, weiß niemand, was auf dem Server einzutragen ist."""
    from kern import jobs

    table = _section(OPS_PAGE, "## Geplante Jobs (Cron)")
    missing = [job["key"] for job in jobs.JOBS if f"`{job['key']}.py`" not in table]
    assert not missing, (
        f"Diese Jobs aus kern/jobs.py haben keine Zeile in der Tabelle „Geplante Jobs (Cron)“ "
        f"von {OPS_PAGE}: {missing}")


def test_weekly_run_steps_match_the_ops_page():
    """Der Wochenlauf hatte 23 Schritte, als die Doku noch 14 nannte."""
    source = (ROOT / "scripts" / "weekly_enrich.py").read_text(encoding="utf-8")
    steps = next(
        ast.literal_eval(node.value) for node in ast.parse(source).body
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "STEPS")
    section = _section(OPS_PAGE, "### Schrittfolge des Wochenlaufs")
    missing = [command for _, command in steps if f"`{command}`" not in section]
    assert not missing, (
        f"Schritte aus scripts/weekly_enrich.py::STEPS fehlen unter „Schrittfolge des "
        f"Wochenlaufs“ in {OPS_PAGE}: {missing}")
    numbered = len(re.findall(r"^\d+\. \*\*", section, flags=re.M))
    assert numbered == len(steps), (
        f"{OPS_PAGE} zählt {numbered} Schritte des Wochenlaufs, STEPS hat {len(steps)}.")
    stated = re.search(r"Sie hat (\d+) Einträge", section)
    assert stated and int(stated.group(1)) == len(steps), (
        f"Die genannte Zahl der Schritte in {OPS_PAGE} passt nicht zu STEPS ({len(steps)}).")


# --------------------------------------------------------------------------
# 2. Jeder Feature-Schalter nennt, wo er erklärt wird
# --------------------------------------------------------------------------

def test_every_feature_points_to_its_documentation():
    """Ein Schalter ist der Moment, in dem ein Feature entsteht. Verlangt er
    eine Doku-Stelle, entsteht die Beschreibung mit ihm."""
    problems = []
    for key, feature in features.FEATURES.items():
        if not feature.docs:
            problems.append(f"{key}: kein `docs=…`")
            continue
        reason = missing_target(feature.docs)
        if reason:
            problems.append(f"{key}: docs=\"{feature.docs}\" — {reason}")
    assert not problems, (
        "Feature-Schalter ohne gültige Doku-Stelle (kern/features.py, Feld `docs`, "
        "Form „seite“ oder „seite#anker“ unter docs-site/src/content/docs/):\n  "
        + "\n  ".join(problems))


# --------------------------------------------------------------------------
# 3. Genannte Pfade und Symbole gibt es
# --------------------------------------------------------------------------

#: Wurzeln, unter denen die Doku Pfade abkürzt (``lib/api.ts`` meint
#: ``web/frontend/lib/api.ts``).
_PATH_ROOTS = ("", "web/frontend/", "web/backend/", "web/backend/app/", "docs-site/",
               "ios/", "scripts/", "kommunalwahl/")
_FILE_SUFFIX = re.compile(
    r"\.(py|tsx?|mjs|js|md|mdx|ya?ml|json|sql|swift|sh|toml|txt|css|svg|html|csv)$")
_PATH = re.compile(r"(?<![\w/.:@-])((?:[\w.@()\[\]-]+/)+[\w.@()\[\]*-]*)")
_BARE_FILE = re.compile(r"(?<![\w/.-])([\w-]+\.(?:py|tsx?|mjs|swift|ya?ml|sh))\b")

#: Pfade, die die Doku nennt und die es im Repo absichtlich nicht gibt.
#: Jeder mit Grund; der zweite Test meldet einen Eintrag, den niemand mehr braucht.
PATHS_NOT_IN_REPO: dict[str, str] = {
    "web/frontend/node_modules/": "entsteht beim Installieren, nicht eingecheckt",
    "web/frontend/.next/": "Build-Ausgabe von Next",
    "web/frontend/.next-build": "Build-Ausgabe von Next während des Deploys",
    "web/frontend/public/docs/": "Ziel der gebauten Doku auf dem Server",
    "docs-site/node_modules/": "entsteht beim Installieren, nicht eingecheckt",
    "docs-site/dist/": "Build-Ausgabe der Doku",
    "deploy/nginx-nwz-web.conf": "ADR 0004 nennt die Datei als entfernt",
    "scripts/bot_poll.py": "ADR 0007 beschreibt den abgelösten Telegram-Bot",
    "bot_poll.py": "ADR 0007 beschreibt den abgelösten Telegram-Bot",
}


@cache
def _top_level() -> frozenset[str]:
    return frozenset(p.name for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith("."))


def _exists(token: str) -> bool:
    token = token.rstrip("/")
    for root in _PATH_ROOTS:
        candidate = root + token
        if "*" in candidate:
            if any(ROOT.glob(candidate)):
                return True
        elif (ROOT / candidate).exists():
            return True
    return False


@cache
def _file_names() -> frozenset[str]:
    names = set()
    for top in (*_CODE_DIRS, "web/frontend", "ios", "tests", ".github", "docs-site/src", "deploy"):
        base = ROOT / top
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and not _SKIP_PARTS.intersection(path.parts):
                names.add(path.name)
    return frozenset(names)


def named_paths() -> dict[str, list[str]]:
    """``{pfad: ["seite:zeile", …]}`` — was im Fließtext wie ein Repo-Pfad aussieht."""
    found: dict[str, list[str]] = {}
    for name in hand_written():
        for number, span in code_spans(name):
            for match in _PATH.finditer(span):
                token = match.group(1).rstrip(".,;:)")
                first = token.split("/")[0]
                if not (first in _top_level() or first in {"app", "components", "lib", "routers"}
                        or _FILE_SUFFIX.search(token)):
                    continue
                if token.startswith(("http", "/", "~", "data/")) or any(c in token for c in "<{…") \
                        or token.endswith("(") \
                        or "..." in token or re.match(r"(?:[\w-]+\.)+[a-z]{2,}/", token):
                    continue  # Adresse, Platzhalter, Aufruf oder ein Pfad auf dem Server
                found.setdefault(token, []).append(f"{name}:{number}")
            for match in _BARE_FILE.finditer(span):
                token = match.group(1)
                if f"/{token}" not in span:
                    found.setdefault(token, []).append(f"{name}:{number}")
    return found


def test_named_paths_exist():
    """Ein umgezogenes Modul hinterlässt in der Doku einen Pfad, der ins Leere
    zeigt — und wer ihm folgt, sucht an der falschen Stelle."""
    gone = {}
    for token, where in named_paths().items():
        if token in PATHS_NOT_IN_REPO:
            continue
        ok = token in _file_names() if "/" not in token else _exists(token)
        if not ok:
            gone[token] = where
    assert not gone, (
        "Die Doku nennt Dateien oder Ordner, die es nicht (mehr) gibt:\n  "
        + "\n  ".join(f"{t}  ({', '.join(w[:3])})" for t, w in sorted(gone.items()))
        + "\nDen Pfad in der Doku nachziehen. Ist er absichtlich nicht im Repo "
          "(Build-Ausgabe, Serverpfad), gehört er mit Grund in PATHS_NOT_IN_REPO.")


def test_path_exceptions_are_still_needed():
    named = named_paths()
    unused = sorted(t for t in PATHS_NOT_IN_REPO if t not in named)
    present = sorted(t for t in PATHS_NOT_IN_REPO if _exists(t) and (ROOT / t).exists()
                     and any((ROOT / t).iterdir() if (ROOT / t).is_dir() else [1])
                     and _tracked_dir(t))
    assert not unused, f"PATHS_NOT_IN_REPO nennt Pfade, die die Doku nicht mehr erwähnt: {unused}"
    assert not present, f"PATHS_NOT_IN_REPO nennt Pfade, die inzwischen eingecheckt sind: {present}"


def _tracked_dir(token: str) -> bool:
    """Liegt unter dem Pfad etwas Eingechecktes? (``.gitignore`` entscheidet,
    nicht das Dateisystem — lokal gibt es ``node_modules`` natürlich.)"""
    import subprocess

    result = subprocess.run(["git", "ls-files", "--", token], cwd=ROOT,
                            capture_output=True, text=True)
    return bool(result.stdout.strip())


_SYMBOL = re.compile(r"([\w./-]+\.(?:py|tsx?|swift|mjs))::([A-Za-z_][\w.]*)")


def test_named_symbols_exist():
    """``kern/llm.py::EU_ZUERST`` verspricht einen Namen in einer Datei."""
    gone = []
    for name in hand_written():
        for number, span in code_spans(name):
            for match in _SYMBOL.finditer(span):
                file_token, symbol = match.group(1), match.group(2).split(".")[-1]
                candidates = [ROOT / (root + file_token) for root in _PATH_ROOTS
                              if (ROOT / (root + file_token)).is_file()]
                if not candidates:
                    continue  # den fehlenden Pfad meldet test_named_paths_exist
                if not any(re.search(rf"\b{re.escape(symbol)}\b",
                                     c.read_text(encoding="utf-8", errors="ignore"))
                           for c in candidates):
                    gone.append(f"{file_token}::{match.group(2)}  ({name}:{number})")
    assert not gone, (
        "Die Doku nennt Namen, die in der genannten Datei nicht (mehr) stehen:\n  "
        + "\n  ".join(sorted(set(gone))))


# --------------------------------------------------------------------------
# 4. Umgebungsvariablen: die Tabellen der Betriebsseite gegen den Code
# --------------------------------------------------------------------------

_ENV_TOKEN = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")

#: Variablen, die der Code liest und die bewusst nicht in der Doku stehen.
ENV_NOT_DOCUMENTED: dict[str, str] = {
    "GITHUB_OUTPUT": "setzt GitHub Actions selbst",
    "XDG_CACHE_HOME": "Standard des Betriebssystems für den Cache-Ordner",
    "NODE_ENV": "setzt Next selbst",
    "TELEGRAM_CHAT_ID": "nur die Migration alter Datenbanken aus der Zeit des Telegram-Bots liest sie",
    "RATSLOTSE_LLM_TARIF": "Messschalter des Prüfstands, gesetzt im Unterprozess; gehört in keine .env",
    "RATSLOTSE_EU_ANBIETER": "Messschalter für den Rückfallweg; gehört in keine .env",
    "RATSLOTSE_WEB_DENKAUFWAND": "Messschalter der Fakten-Eval, gesetzt im Unterprozess",
    "RATSLOTSE_PROMPT_MITSCHNITT": "Option eines Eval-Laufs (Prompts mitschneiden)",
    "RATSLOTSE_STT_REFERENZ": "Option eines Eval-Laufs (welche Referenz gilt)",
    "PRUEFSTAND_STICHPROBE": "setzt der Prüfstand im Unterprozess eines Laufs",
}

#: Variablen in den Tabellen, die NICHT der eigene Code liest.
ENV_READ_ELSEWHERE: dict[str, str] = {
    "FASTEMBED_CACHE_PATH": "liest die Bibliothek fastembed",
}


def env_rows() -> dict[str, tuple[int, list[str]]]:
    """``{NAME: (zeile, [zellen…])}`` — die Tabellenzeilen der Betriebsseite,
    deren erste Zelle eine Variable nennt."""
    rows = {}
    for number, line in prose_lines(OPS_PAGE):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        match = re.fullmatch(r"`([A-Z][A-Z0-9_]+)`", cells[0]) if cells else None
        if match and _ENV_TOKEN.fullmatch(match.group(1)):
            rows.setdefault(match.group(1), (number, cells))
    return rows


def env_in_docs() -> set[str]:
    """Jede Variable, die irgendwo in der Doku steht — auch in einem
    Code-Block: Ein ``.env``-Beispiel ist Dokumentation."""
    out = set()
    for lines in pages().values():
        for line in lines:
            out.update(_ENV_TOKEN.findall(line))
    return out


def test_env_variables_read_by_code_are_documented():
    """Eine Variable, die nur im Code steht, findet auf dem Server niemand —
    bis der Dienst mit dem Vorgabewert läuft und sich anders verhält als gedacht."""
    documented = env_in_docs()
    missing = {name: sorted(entry["files"])[0] for name, entry in env_in_code().items()
               if name not in documented and name not in ENV_NOT_DOCUMENTED}
    assert not missing, (
        "Der Code liest Umgebungsvariablen, die in der Doku nirgends stehen:\n  "
        + "\n  ".join(f"{n}  ({f})" for n, f in sorted(missing.items()))
        + f"\nIn die passende Tabelle unter „Umgebungsvariablen“ in {OPS_PAGE} eintragen "
          "(Variable, wofür, Vorgabe). Nur wenn sie niemand setzen soll: mit Grund in "
          "ENV_NOT_DOCUMENTED.")


def test_documented_env_variables_are_read():
    """Die Gegenrichtung: Eine Tabellenzeile zu einer Variable, die niemand
    mehr liest, lässt jemanden an einem Regler drehen, der nichts bewegt."""
    read = env_in_code()
    dead = {name: number for name, (number, _) in env_rows().items()
            if name not in read and name not in ENV_READ_ELSEWHERE
            and not _named_outside_python(name)}
    assert not dead, (
        f"{OPS_PAGE} dokumentiert Umgebungsvariablen, die der Code nicht (mehr) liest:\n  "
        + "\n  ".join(f"{n}  (Zeile {z})" for n, z in sorted(dead.items()))
        + "\nZeile streichen oder umbenennen. Liest sie etwas außerhalb des eigenen Codes: "
          "mit Grund in ENV_READ_ELSEWHERE.")


@cache
def _other_sources() -> str:
    """Workflows, Deploy-Skripte und Swift — dort werden Variablen gesetzt
    oder gelesen, die der Python-Syntaxbaum nicht sieht."""
    chunks = []
    for base, patterns in ((".github", ("*.yml",)), ("deploy", ("*",)), ("ios", ("*.swift", "*.yml")),
                           ("web/frontend", ("*.ts", "*.tsx", "*.mjs", ".env.example")),
                           ("scripts", ("*.sh", "*.py")), ("kern", ("*.py",)), ("council", ("*.py",)),
                           ("web/backend", ("*.py",))):
        root = ROOT / base
        if not root.exists():
            continue
        for pattern in patterns:
            for path in root.rglob(pattern):
                if path.is_file() and not _SKIP_PARTS.intersection(path.parts):
                    chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks)


def _named_outside_python(name: str) -> bool:
    return re.search(rf"\b{re.escape(name)}\b", _other_sources()) is not None


def test_env_exception_lists_are_still_needed():
    read = env_in_code()
    documented = env_in_docs()
    stale = sorted(n for n in ENV_NOT_DOCUMENTED if n not in read or n in documented)
    assert not stale, (
        "ENV_NOT_DOCUMENTED nennt Variablen, die der Code nicht mehr liest "
        f"oder die inzwischen dokumentiert sind: {stale}")
    stale = sorted(n for n in ENV_READ_ELSEWHERE if n in read or n not in env_rows())
    assert not stale, (
        "ENV_READ_ELSEWHERE nennt Variablen, die der eigene Code inzwischen liest "
        f"oder die nicht mehr in den Tabellen stehen: {stale}")


def test_documented_env_defaults_match_code():
    """Steht in der Tabelle eine andere Vorgabe als im Code, glaubt man der
    Tabelle — beim Modell je Aufgabe heißt das: Man rechnet mit dem falschen."""
    wrong = []
    for name, (number, cells) in env_rows().items():
        defaults = env_in_code().get(name, {}).get("defaults", set())
        if len(defaults) != 1 or len(cells) < 3:
            continue  # keine oder mehrere Vorgaben im Code: nichts Eindeutiges zu vergleichen
        default = next(iter(defaults))
        if default == "":
            continue
        cell = cells[-1]
        named = set(_SPAN.findall(cell))
        if not named:
            continue  # die Zelle beschreibt die Vorgabe in Worten
        if not any(_same_value(default, value) for value in named):
            wrong.append(f"{name}  (Zeile {number}): Doku {sorted(named)}, Code „{default}“")
    assert not wrong, (
        f"Vorgabewerte in {OPS_PAGE} weichen vom Code ab:\n  " + "\n  ".join(wrong))


def _same_value(code: str, doc: str) -> bool:
    if code == doc:
        return True
    try:
        return float(code) == float(doc.replace(",", "."))
    except ValueError:
        return code.lower() == doc.lower()


# --------------------------------------------------------------------------
# 5. Modelle und API-Routen
# --------------------------------------------------------------------------

_MODEL = re.compile(
    r"\b((?:openai|anthropic|google|deepseek|mistralai|meta-llama|x-ai|qwen|jinaai|"
    r"sentence-transformers)/[A-Za-z0-9][\w.:-]*[A-Za-z0-9])")


@cache
def _model_sources() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in python_files() if "tests" not in p.parts)


def test_named_models_exist_in_code():
    """Ein Modellname in der Doku, den der Code nicht mehr kennt, ist ein
    Modell, das längst gewechselt wurde."""
    sources = _model_sources()
    gone = {}
    for name in hand_written():
        for number, line in prose_lines(name):
            for model in _MODEL.findall(line):
                if model not in sources:
                    gone.setdefault(model, []).append(f"{name}:{number}")
    assert not gone, (
        "Die Doku nennt Modelle, die im Code nicht (mehr) vorkommen:\n  "
        + "\n  ".join(f"{m}  ({', '.join(w[:3])})" for m, w in sorted(gone.items())))


#: ``/api/…``-Adressen fremder Dienste, die die Doku zitiert.
FOREIGN_API_PATHS: dict[str, str] = {
    "/api/v1/batches": "OpenRouter",
    "/api/v1/models/{}/endpoints": "OpenRouter",
}


def _normal(path: str) -> str:
    return re.sub(r"\{[^}]*\}|<[^>]*>|\$\{[^}]*\}|\[[^\]]*\]", "{}", path).rstrip("/")


def test_named_api_paths_exist_in_contract():
    """Eine Route in der Doku, die der Vertrag nicht kennt, wurde umbenannt
    oder entfernt."""
    spec = json.loads((ROOT / "api" / "openapi.json").read_text(encoding="utf-8"))
    known = {_normal(p) for p in spec["paths"]}
    gone = {}
    seen_foreign = set()
    for name in hand_written():
        for number, line in prose_lines(name):
            for raw in re.findall(r"(?<![\w.])(/api/[\w{}<>/:.\-\[\]$]*)", line):
                path = _normal(raw.rstrip(".,:"))
                if path in FOREIGN_API_PATHS:
                    seen_foreign.add(path)
                    continue
                if path in known or any(k.startswith(path + "/") for k in known):
                    continue
                gone.setdefault(path, []).append(f"{name}:{number}")
    assert not gone, (
        "Die Doku nennt API-Routen, die api/openapi.json nicht kennt:\n  "
        + "\n  ".join(f"{p}  ({', '.join(w[:3])})" for p, w in sorted(gone.items())))
    unused = sorted(set(FOREIGN_API_PATHS) - seen_foreign)
    assert not unused, f"FOREIGN_API_PATHS nennt Adressen, die die Doku nicht mehr zitiert: {unused}"


def test_mcp_tools_match_the_mcp_page():
    """Die Werkzeuge des MCP-Servers sind eine öffentliche Schnittstelle: Wer
    einen Agenten anschließt, liest sie auf der Doku-Seite nach."""
    from council import mcp_tools

    page = "\n".join(pages()["mcp.md"])
    listed = set(re.findall(r"^\| `([a-z_]+)` \|", page, flags=re.M))
    missing = sorted(set(mcp_tools.TOOLS) - listed)
    gone = sorted(listed - set(mcp_tools.TOOLS))
    assert not missing, f"mcp.md nennt diese Werkzeuge aus council/mcp_tools.py nicht: {missing}"
    assert not gone, f"mcp.md nennt Werkzeuge, die es nicht mehr gibt: {gone}"


# --------------------------------------------------------------------------
# 6. Links und Seitenleiste
# --------------------------------------------------------------------------

_LINK = re.compile(r"\]\(([^)\s]+)\)")
_FRONTMATTER_LINK = re.compile(r"^\s*link:\s*(\S+)\s*$")


def test_internal_links_resolve():
    """Die Doku liegt unter ``/docs``. Ein Link ohne diesen Vorsatz landet in
    der Webanwendung, ein Link auf eine umbenannte Überschrift am Seitenanfang."""
    broken = []
    for name in pages():
        targets = [(n, m) for n, line in prose_lines(name) for m in _LINK.findall(line)]
        targets += [(n, m.group(1)) for n, line in enumerate(pages()[name], 1)
                    if (m := _FRONTMATTER_LINK.match(line))]
        for number, target in targets:
            if re.match(r"[a-z][a-z0-9+.-]*:", target):
                continue  # https:, mailto: …
            where = f"{name}:{number}"
            if target.startswith("#"):
                if target[1:] not in anchors(name):
                    broken.append(f"{where}: {target} — diese Überschrift gibt es hier nicht")
            elif target.startswith("/docs"):
                reason = missing_target(target.removeprefix("/docs").strip("/").replace("/#", "#"))
                if reason:
                    broken.append(f"{where}: {target} — {reason}")
            elif target.startswith("/"):
                broken.append(
                    f"{where}: {target} — führt aus der Doku heraus in die Webanwendung; "
                    f"gemeint ist vermutlich /docs{target}")
            elif not target.startswith(("../../assets/", "../assets/", "./", "../")):
                broken.append(f"{where}: {target} — weder Adresse noch /docs/-Pfad")
    assert not broken, "Links in der Doku, die nicht ankommen:\n  " + "\n  ".join(broken)


def test_every_page_is_reachable_from_the_sidebar():
    """Eine Seite, die nicht in ``astro.config.mjs`` steht, wird gebaut und
    ist trotzdem unsichtbar — erreichbar nur für den, der die Adresse kennt."""
    config = ASTRO_CONFIG.read_text(encoding="utf-8")
    slugs = set(re.findall(r"slug:\s*'([^']+)'", config))
    directories = set(re.findall(r"directory:\s*'([^']+)'", config))
    orphans = []
    for name in pages():
        slug = re.sub(r"(/index)?\.mdx?$", "", name)
        if name == "index.mdx" or slug in slugs or name.split("/")[0] in directories:
            continue
        orphans.append(name)
    assert not orphans, (
        f"Diese Seiten stehen nicht in der Seitenleiste (docs-site/astro.config.mjs): {orphans}")
    missing = sorted(s for s in slugs if page_file(s) is None)
    assert not missing, f"Die Seitenleiste nennt Seiten, die es nicht gibt: {missing}"


@pytest.mark.parametrize("heading,slug", [
    ("Geplante Jobs (Cron)", "geplante-jobs-cron"),
    ("Host-Schlüssel (`VPS_KNOWN_HOSTS`)", "host-schlüssel-vps_known_hosts"),
    ("„Lotti erklärt's einfach\"", "lotti-erklärts-einfach"),
    ("Was der Protokoll-Lauf inline nachzieht", "was-der-protokoll-lauf-inline-nachzieht"),
])
def test_slug_matches_what_starlight_builds(heading, slug):
    """Die Anker rechnet dieser Test selbst nach, ohne die Doku zu bauen. Die
    Beispiele sind am gebauten HTML abgelesen (22.11.2026)."""
    assert slug_of(heading) == slug
