#!/usr/bin/env python3
"""Die Dauern der Browsertest-Dateien aus einem grünen CI-Lauf ziehen.

    python scripts/e2e_durations.py            # zeigen, was der jüngste grüne Lauf sagt
    python scripts/e2e_durations.py --write    # … und in die Datei schreiben
    python scripts/e2e_durations.py --run 45036345622

**Wozu.** `web/frontend/tests/shard-specs.mjs` verteilt die Spec-Dateien nach
Dauer auf die Läufer der CI. Die Zahlen dafür stehen in
`web/frontend/tests/e2e-durations.json` und kommen von hier — aus den Logs der
CI selbst, weil nur dort gemessen wird, was dort zählt (lokal ist dieselbe
Suite auf einem Notebook zwei- bis dreimal so schnell und anders verteilt).

**Wann.** Wenn die Teile sichtbar auseinanderlaufen — die Laufzeit je Teil
steht an jedem Pull Request neben der Prüfung. Die Abdeckung hängt NICHT an
dieser Datei: Eine Spec-Datei ohne Eintrag läuft mit mittlerem Gewicht mit.

Braucht die `gh`-Kommandozeile mit Lesezugriff auf das Repo.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "web" / "frontend" / "tests" / "e2e-durations.json"
WORKFLOW = "e2e.yml"

#: Eine Ergebniszeile des `list`-Reporters:
#: `✓  12 [chromium] › tests/e2e/27-plaene.spec.ts:38:5 › der Reiter … (7.0s)`
#: Das Anmelde-Projekt (`[setup]`) zählt nicht — es läuft in jedem Teil.
RESULT_LINE = re.compile(
    r"[✓✘×-]\s+\d+ \[chromium\] › tests/e2e/(?P<file>[\w.\-]+\.spec\.ts):\d+:\d+ › "
    r".*? \((?P<value>\d+(?:\.\d+)?)(?P<unit>ms|s|m)\)")
UNIT_SECONDS = {"ms": 0.001, "s": 1.0, "m": 60.0}


def parse_log(text: str) -> dict[str, float]:
    """Sekunden je Spec-Datei aus dem Log EINES Läufers."""
    seconds: dict[str, float] = collections.defaultdict(float)
    for match in RESULT_LINE.finditer(text):
        seconds[match["file"]] += float(match["value"]) * UNIT_SECONDS[match["unit"]]
    return dict(seconds)


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def latest_green_run() -> str:
    run_id = gh("run", "list", "--workflow", WORKFLOW, "--status", "success",
                "--limit", "1", "--json", "databaseId", "--jq", ".[0].databaseId").strip()
    if not run_id:
        sys.exit(f"Kein grüner Lauf von {WORKFLOW} gefunden.")
    return run_id


def run_durations(run_id: str) -> dict[str, float]:
    """Alle Läufer eines Laufs zusammen — jede Datei läuft in genau einem."""
    seconds: dict[str, float] = collections.defaultdict(float)
    job_ids = gh("run", "view", run_id, "--json", "jobs", "--jq", ".jobs[].databaseId").split()
    for job_id in job_ids:
        for file, value in parse_log(gh("run", "view", run_id, "--job", job_id, "--log")).items():
            seconds[file] += value
    return dict(seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--run", help="Kennung des CI-Laufs (Vorgabe: der jüngste grüne)")
    parser.add_argument("--write", action="store_true", help=f"nach {TARGET.relative_to(ROOT)} schreiben")
    args = parser.parse_args()

    run_id = args.run or latest_green_run()
    seconds = run_durations(run_id)
    if not seconds:
        sys.exit(f"Lauf {run_id}: keine Ergebniszeilen gefunden — hat sich der Reporter geändert?")

    for file, value in sorted(seconds.items(), key=lambda item: -item[1]):
        print(f"  {value:6.1f} s  {file}")
    print(f"  {sum(seconds.values()) / 60:.1f} min über {len(seconds)} Dateien (Lauf {run_id})")

    if args.write:
        TARGET.write_text(json.dumps({
            "measured": date.today().isoformat(),
            "run": int(run_id),
            "seconds": {file: round(value, 1) for file, value in sorted(seconds.items())},
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"geschrieben: {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
