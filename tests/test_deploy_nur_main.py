"""Der Prod-Deploy startet von Hand nur von `main`.

`workflow_dispatch` ist der Notausgang für ausgefallene `closed`-Ereignisse.
Die Actions-UI bietet dabei JEDEN Zweig als Ref an; ohne Prüfung auf
`github.ref` brächte ein Klick auf den falschen einen Feature-Stand auf Prod.
"""
from __future__ import annotations

from pathlib import Path

import yaml

DEPLOY = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "deploy.yml"


def test_jeder_job_mit_handstart_verlangt_main():
    jobs = yaml.safe_load(DEPLOY.read_text())["jobs"]
    ohne = [name for name, job in jobs.items()
            if "workflow_dispatch" in str(job.get("if", ""))
            and "github.ref == 'refs/heads/main'" not in str(job.get("if", ""))]
    assert not ohne, (
        f"Diese Jobs lassen sich von jedem Zweig aus von Hand starten: {ohne}. "
        "Bedingung: (github.event_name == 'workflow_dispatch' && "
        "github.ref == 'refs/heads/main') || github.event.pull_request.merged == true")
    assert any("workflow_dispatch" in str(job.get("if", "")) for job in jobs.values())
