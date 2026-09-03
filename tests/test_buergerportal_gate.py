"""Wächter für Sichtbarkeit und Feature-only-Beispieldaten des Bürgerportals."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "web" / "frontend"
GATE = "PROBLEME_FREI"
SEED_COMMAND = "scripts/saat_buergerportal_feature.py"


def test_problem_route_and_entry_points_share_the_environment_gate():
    gate = (FRONTEND / "lib" / "probleme-frei.ts").read_text()
    page = (FRONTEND / "app" / "(app)" / "probleme" / "page.tsx").read_text()
    nav = (FRONTEND / "components" / "nav.tsx").read_text()
    sitemap = (FRONTEND / "app" / "sitemap.ts").read_text()

    assert 'process.env.NEXT_PUBLIC_RATSLOTSE_ENV === "dev"' in gate
    assert f"export const {GATE}" in gate
    assert GATE in page and "notFound()" in page
    assert GATE in nav and 'href: "/probleme"' in nav
    assert GATE in sitemap and "`${BASE}/probleme`" in sitemap


def test_only_feature_deployment_can_invoke_the_example_seeder():
    workflows = ROOT / ".github" / "workflows"
    callers = []
    for workflow in workflows.glob("*.yml"):
        if SEED_COMMAND in workflow.read_text():
            callers.append(workflow.name)

    assert callers == ["deploy-feature.yml"]
    feature = (workflows / "deploy-feature.yml").read_text()
    assert "cd ~/app-feature" in feature
    assert f"RATSLOTSE_FEATURE_SEED=1 .venv/bin/python {SEED_COMMAND}" in feature
