#!/usr/bin/env python3
"""Erzeugt die Referenzseiten der Technik-Doku aus den Registern im Code.

Fünf Listen standen in der Doku von Hand und liefen dem Code hinterher:
gemessen am 22.11.2026 fehlten dort 2 von 22 Cron-Jobs, 24 von 34
Feature-Schaltern, 3 von 6 Rollen, 26 von 41 Eval-Läufen und 21 von 37
Workflows. Alle fünf haben im Repo längst EINE Quelle (``kern/jobs.py``,
``kern/features.py``, ``kern/roles.py``, die Docstrings unter ``eval/`` und
die Köpfe der Dateien unter ``.github/workflows/``) — also entstehen die
Seiten daraus, statt sie ein zweites Mal zu pflegen.

Die Seiten sind eingecheckt (die Doku baut mit Node, die Register sind
Python), deshalb gibt es die Prüfung: Wer ein Register ändert und die Seiten
nicht neu erzeugt, bekommt das vor dem Push gesagt.

    python scripts/docs_reference.py            # schreiben
    python scripts/docs_reference.py --check    # nur melden, ob es passt

``--check`` läuft in ``scripts/pruefe.py`` (Prüfung „doku") und in
``tests/test_docs_current.py``.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kern import features, jobs, roles  # noqa: E402

OUT_DIR = ROOT / "docs-site" / "src" / "content" / "docs" / "referenz"

#: Steht in jeder erzeugten Seite — der Wächter erkennt daran auch eine Seite,
#: die jemand von Hand in den Ordner gelegt hat.
MARKER = "<!-- Erzeugt von scripts/docs_reference.py — nicht von Hand ändern. -->"

_REGENERATE = (
    "Diese Seite entsteht aus `{source}` (`python scripts/docs_reference.py`). "
    "Wer sie von Hand ändert, verliert die Änderung beim nächsten Lauf; "
    "`tests/test_docs_current.py` hält sie gegen das Register."
)


def _cell(text: str) -> str:
    """Ein Text als Tabellenzelle: einzeilig, senkrechte Striche maskiert."""
    text = re.sub(r"``([^`]+)``", r"`\1`", str(text))  # Docstrings schreiben RST
    return (" ".join(text.split()).replace("|", "\\|").replace("*", "\\*")
            .replace("<", "&lt;"))


def _page(title: str, description: str, source: str, body: list[str]) -> str:
    head = [
        "---",
        f'title: "{title}"',
        f"description: {description}",
        # In der Seitenleiste steht die Gruppe schon über dem Eintrag.
        "sidebar:",
        f'  label: "{title.removeprefix("Referenz: ")}"',
        "---",
        "",
        MARKER,
        "",
        _REGENERATE.format(source=source),
        "",
    ]
    return "\n".join(head + body).rstrip() + "\n"


def render_jobs() -> str:
    body = [
        "Die Zeitpläne selbst stehen in der crontab des Servers, nicht im Repo. "
        "Das Register ist ihre lesbare Entsprechung: Es speist die "
        "Überfällig-Ampel im Admin-Panel (*Statistik → Cron-Jobs*) und den "
        "täglichen Herzschlag, der schweigende Jobs meldet. Wie die Jobs "
        "zusammenhängen, steht unter [Betrieb](/docs/betrieb/#geplante-jobs-cron).",
        "",
        "| Job | Was er tut | Takt | Überfällig nach |",
        "|---|---|---|---|",
    ]
    for job in jobs.JOBS:
        key = job["key"]
        script = f"scripts/{key}.py"
        name = f"`{script}`" if (ROOT / script).exists() else f"`{key}`"
        what = f"**{_cell(job['label'])}.** {_cell(job['description'])}"
        if job.get("pausiert"):
            what += f" **Pausiert:** {_cell(job['pausiert'])}"
        body.append(f"| {name} | {what} | {_cell(job['schedule'])} | {job['max_age_h']} h |")
    body += [
        "",
        f"{len(jobs.JOBS)} Jobs. „Überfällig nach“ ist bewusst großzügiger als der "
        "Abstand zweier Läufe, damit ein einzelner verspäteter Lauf keinen Alarm "
        "auslöst. Ein pausierter Job darf schweigen: keine Ampel, keine Mail.",
    ]
    return _page(
        "Referenz: Cron-Jobs",
        "Alle geplanten Jobs mit Takt und Überfällig-Schwelle, erzeugt aus kern/jobs.py.",
        "kern/jobs.py", body)


def render_features() -> str:
    body = [
        "Ein Schalter trennt Ausliefern von Freischalten: Der Code fährt fertig "
        "nach `main` und bleibt dunkel, bis `FEATURE_FLAGS` in der `.env` des "
        "Servers ihn nennt. **Auf dev sind alle Schalter an** (`FEATURE_FLAGS=*`); "
        "welche auf Prod an sind, steht nur dort. Die Oberflächen lesen die "
        "Liste über `GET /api/app-config`. Ein Schalter ist keine Rechteprüfung "
        "(dafür gibt es [Rollen und Rechte](/docs/referenz/rollen-rechte/)) und "
        "er ist eine Schuld: Die Spalte „Fertig, wenn“ nennt, woran man erkennt, "
        "dass er wieder wegkann.",
        "",
        "| Schalter | Was er freischaltet | Fertig, wenn |",
        "|---|---|---|",
    ]
    for feature in features.FEATURES.values():
        # Drei Spalten, nicht vier: Die Tabelle soll ohne Querrollen lesbar
        # sein, der Verweis steht deshalb am Ende der Beschreibung.
        link = f" [→ Erklärt in der Doku]({docs_url(feature.docs)})" if feature.docs else ""
        body.append(
            f"| `{feature.key}` | {_cell(feature.description)}{link} | "
            f"{_cell(feature.fertig_wenn)} |")
    body += ["", f"{len(features.FEATURES)} Schalter."]
    return _page(
        "Referenz: Feature-Schalter",
        "Alle Feature-Schalter mit Zweck und Abbaubedingung, erzeugt aus kern/features.py.",
        "kern/features.py", body)


def render_roles() -> str:
    body = [
        "Ein Konto trägt mehrere Rollen (Tabelle `web_user_roles`), jede Rolle "
        "bündelt Rechte. Geprüft wird immer gegen ein **Recht**, nie gegen einen "
        "Rollennamen: im Backend über `Depends(require_permission(\"…\"))`, im Web "
        "über `lib/rechte.ts`, in der App über `User.can(_:)`. Eine neue Rolle ist "
        "damit ein Eintrag im Register, ohne Frontend-Release und ohne App-Update.",
        "",
        "## Rollen",
        "",
        "| Rolle | Was sie darf | Rechte |",
        "|---|---|---|",
    ]
    for key in roles.ROLE_ORDER:
        role = roles.ROLES[key]
        rights = ", ".join(f"`{p}`" for p in roles.PERMISSIONS if p in role.permissions) or "–"
        note = "" if role.assignable else " Jedes Konto hat sie; im Admin-Panel wird sie nicht vergeben."
        body.append(
            f"| **{_cell(role.label)}** (`{role.key}`) | {_cell(role.description)}{note} | {rights} |")
    body += [
        "",
        "## Rechte",
        "",
        "| Recht | Rollen, die es tragen |",
        "|---|---|",
    ]
    for permission in roles.PERMISSIONS:
        holders = ", ".join(
            roles.ROLES[k].label for k in roles.ROLE_ORDER
            if permission in roles.ROLES[k].permissions)
        body.append(f"| `{permission}` | {_cell(holders)} |")
    body += [
        "",
        f"Die Rolle `{roles.DEFAULT_ROLE}` hat jedes Konto, auch ohne Zeile in "
        "`web_user_roles`; ihre Rechte gelten damit für alle. Admins erben jedes "
        "Recht, auch später hinzukommende. `web_users.role` ist nur noch ein "
        "abgeleitetes Schaufenster für ältere App-Builds und nie die Grundlage "
        "einer Rechteprüfung.",
    ]
    return _page(
        "Referenz: Rollen und Rechte",
        "Alle Rollen und die Rechte, die sie bündeln, erzeugt aus kern/roles.py.",
        "kern/roles.py", body)


#: Abkürzungen, hinter deren Punkt kein Satz endet.
_ABBREVIATIONS = ("inkl.", "bzw.", "z. B.", "z.B.", "ca.", "vgl.", "Nr.", "u. a.", "d. h.", "s.", "ggf.")


def _first_sentence(text: str, limit: int = 260) -> str:
    """Der erste Absatz eines Kommentars oder Docstrings, auf einen Satz gekürzt."""
    paragraph = " ".join(text.strip().split("\n\n")[0].split())
    sentence = paragraph
    for match in re.finditer(r"[.!?](?=\s+[A-ZÄÖÜ„\"(`]|$)", paragraph):
        candidate = paragraph[:match.end()]
        if len(candidate) > 40 and not candidate.endswith(_ABBREVIATIONS):
            sentence = candidate
            break
    return sentence if len(sentence) <= limit else sentence[:limit].rsplit(" ", 1)[0] + " …"


def eval_runs() -> list[tuple[str, str]]:
    """``[(pfad, erster Satz des Docstrings)]`` für jeden Messlauf."""
    files = sorted((ROOT / "eval").glob("run_*.py")) + sorted((ROOT / "scripts").glob("eval_*.py"))
    out = []
    for path in files:
        doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or ""
        out.append((path.relative_to(ROOT).as_posix(), _first_sentence(doc) or "–"))
    return out


def render_evals() -> str:
    runs = eval_runs()
    body = [
        "Jeder Lauf misst einen Schritt gegen feste Fälle, damit eine Änderung an "
        "Prompt oder Modell messbar besser oder schlechter wird. Wie die Läufe "
        "aufgebaut sind und wie man Fälle ergänzt, steht unter "
        "[Eval-Harness](/docs/eval/). Die Beschreibung je Zeile ist der erste Satz "
        "des Docstrings der Datei.",
        "",
        "| Lauf | Was er misst |",
        "|---|---|",
    ]
    body += [f"| `{path}` | {_cell(what)} |" for path, what in runs]
    body += ["", f"{len(runs)} Läufe."]
    return _page(
        "Referenz: Eval-Läufe",
        "Alle Messläufe für die Qualität der Modell-Schritte, erzeugt aus den Docstrings unter eval/.",
        "eval/run_*.py` und `scripts/eval_*.py", body)


_TRIGGER_WORDS = {
    "workflow_dispatch": "von Hand",
    "pull_request": "Pull Request",
    "pull_request_target": "Pull Request",
    "push": "Push",
    "schedule": "Zeitplan",
    "workflow_run": "nach einem anderen Workflow",
    "issue_comment": "Kommentar",
    "pull_request_review": "Review",
    "pull_request_review_comment": "Kommentar an einer Zeile",
    "workflow_call": "Aufruf aus einem Workflow",
}


def _workflow(path: Path) -> tuple[str, str, str]:
    """``(name, auslöser, wozu)`` aus dem Kopf einer Workflow-Datei — ohne
    YAML-Bibliothek, damit das Skript keine Abhängigkeit mehr braucht als die
    Register, die es liest."""
    lines = path.read_text(encoding="utf-8").splitlines()
    name = next((re.sub(r"^name:\s*", "", line).strip().strip("\"'")
                 for line in lines if line.startswith("name:")), path.stem)

    def comment_block(start: int) -> str:
        block = []
        for line in lines[start:]:
            if line.startswith("#"):
                block.append(line.lstrip("#").strip())
            elif block or line.strip():
                break
        return "\n".join(block)

    name_index = next((i for i, line in enumerate(lines) if line.startswith("name:")), 0)
    purpose = comment_block(0) or comment_block(name_index + 1)

    start = next((i for i, line in enumerate(lines) if re.match(r"^(on|\"on\"|'on'):", line)), None)
    triggers: list[str] = []
    if start is not None:
        inline = re.sub(r"^[^:]+:\s*", "", lines[start]).strip()
        block = []
        for line in lines[start + 1:]:
            if line and not line.startswith((" ", "#")):
                break
            block.append(line)
        keys = re.findall(r"[a-z_]+", inline) if inline else [
            m.group(1) for line in block if (m := re.match(r"^  ([a-z_]+):", line))]
        text = "\n".join(block)
        for key in keys:
            word = _TRIGGER_WORDS.get(key, key)
            if key == "schedule":
                crons = re.findall(r"cron:\s*[\"']([^\"']+)[\"']", text)
                word += " (" + ", ".join(f"`{c}`" for c in crons) + ")" if crons else ""
            elif key in ("push", "pull_request"):
                section = re.search(rf"^  {key}:\n((?:    .*\n?|\s*\n)*)", text, flags=re.M)
                branches = re.search(r"branches:\s*\[([^\]]+)\]", section.group(1)) if section else None
                if branches:
                    word += " auf " + ", ".join(
                        f"`{b.strip().strip(chr(34)).strip(chr(39))}`" for b in branches.group(1).split(","))
                if section and re.search(r"types:\s*\[[^\]]*closed", section.group(1)):
                    word += " (beim Schließen)"
            if word not in triggers:
                triggers.append(word)
    return name, ", ".join(triggers) or "–", _first_sentence(purpose) or "–"


def render_workflows() -> str:
    files = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    body = [
        "Alles, was GitHub Actions für dieses Repo tut: Prüfungen je Pull Request, "
        "die beiden Deploys und die Werkzeuge für den Betrieb, die sich von Hand "
        "starten lassen (`Ops: …`). Der Zusammenhang steht unter "
        "[Betrieb](/docs/betrieb/#ops-workflows-manuell-auslösbar). Die Spalte "
        "„Wozu“ ist der erste Satz des Kommentars am Kopf der Datei.",
        "",
        "| Workflow | Auslöser | Wozu |",
        "|---|---|---|",
    ]
    for path in files:
        name, triggers, purpose = _workflow(path)
        body.append(f"| **{_cell(name)}** (`{path.name}`) | {triggers} | {_cell(purpose)} |")
    body += ["", f"{len(files)} Workflows unter `.github/workflows/`."]
    return _page(
        "Referenz: Workflows",
        "Alle GitHub-Actions-Workflows mit Auslöser und Zweck, erzeugt aus .github/workflows/.",
        ".github/workflows/*.yml", body)


def docs_url(target: str) -> str:
    """``seite#anker`` → ``/docs/seite/#anker``."""
    page, _, anchor = target.partition("#")
    return f"/docs/{page.strip('/')}/" + (f"#{anchor}" if anchor else "")


PAGES = {
    "cron-jobs.md": render_jobs,
    "feature-schalter.md": render_features,
    "rollen-rechte.md": render_roles,
    "eval-laeufe.md": render_evals,
    "workflows.md": render_workflows,
}


def render_all() -> dict[str, str]:
    return {name: render() for name, render in PAGES.items()}


def stale() -> list[str]:
    """Namen der Seiten, die nicht (mehr) zum Register passen."""
    out = []
    for name, text in render_all().items():
        path = OUT_DIR / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            out.append(name)
    return out


def main(argv: list[str]) -> int:
    if "--check" in argv:
        behind = stale()
        if behind:
            print("Referenzseiten der Doku passen nicht zu den Registern: "
                  + ", ".join(behind))
            print("Beheben: python scripts/docs_reference.py")
            return 1
        print(f"{len(PAGES)} Referenzseiten passen zu den Registern.")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in render_all().items():
        (OUT_DIR / name).write_text(text, encoding="utf-8")
        print(f"geschrieben: {(OUT_DIR / name).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
