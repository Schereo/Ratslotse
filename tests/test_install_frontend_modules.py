"""node_modules neben dem laufenden Server (``scripts/install_frontend_modules.py``).

Am 12.11.2026 leerte ``npm ci`` im Deploy den Baum, aus dem der laufende
``next start`` noch nachlud — die Seite antwortete mit 500. Geprüft wird hier
mit einem nachgebauten ``npm``/``node`` auf dem PATH (kein Netz): dass ein
unveränderter Stand gar nicht installiert, ein geänderter daneben entsteht,
ein gescheitertes ``npm ci`` den alten Baum stehen lässt — und dass kein
Deploy-Workflow ``npm ci`` wieder direkt auf dem Server ausführt.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_frontend_modules.py"
WORKFLOWS = ROOT / ".github" / "workflows"
DEPLOYS = ("deploy.yml", "deploy-dev.yml", "deploy-feature.yml")

# An npm that logs its calls: `ci` creates a tree with one package (fails with
# NPM_FAIL=1), `ls` succeeds while that package is present.
FAKE_NPM = """#!/bin/sh
echo "$*" >> "$NPM_LOG"
case "$1" in
  --version) echo 10.9.9 ;;
  ci)
    [ "$NPM_FAIL" = 1 ] && exit 7
    mkdir -p node_modules/pkg
    cp package-lock.json node_modules/pkg/lock-copy ;;
  ls) [ -f node_modules/pkg/lock-copy ] ;;
esac
"""
FAKE_NODE = "#!/bin/sh\necho v22.23.3\n"


def _bin_dir(tmp: Path) -> Path:
    bindir = tmp / "bin"
    if not bindir.is_dir():
        bindir.mkdir()
        for name, body in (("npm", FAKE_NPM), ("node", FAKE_NODE)):
            f = bindir / name
            f.write_text(body)
            f.chmod(f.stat().st_mode | stat.S_IXUSR)
    return bindir


def _frontend(tmp: Path, lock: str = '{"v": 1}') -> Path:
    frontend = tmp / "web" / "frontend"
    frontend.mkdir(parents=True)
    (frontend / "package.json").write_text('{"name": "f"}')
    (frontend / "package-lock.json").write_text(lock)
    return frontend


def _run(tmp: Path, frontend: Path, **extra: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PATH": f"{_bin_dir(tmp)}{os.pathsep}{os.environ['PATH']}",
           "NPM_LOG": str(tmp / "npm.log"), **extra}
    return subprocess.run([sys.executable, str(SCRIPT), str(frontend)], env=env,
                          capture_output=True, text=True)


def _ci_calls(tmp: Path) -> int:
    log = tmp / "npm.log"
    return sum(1 for line in log.read_text().splitlines() if line.startswith("ci")) if log.exists() else 0


def _installed_lock(frontend: Path) -> Path:
    return frontend / "node_modules" / "pkg" / "lock-copy"


def test_installs_once_then_leaves_tree_alone(tmp_path):
    frontend = _frontend(tmp_path)
    first = _run(tmp_path, frontend)
    assert first.returncode == 0, first.stderr
    assert _installed_lock(frontend).is_file()
    assert (frontend / "node_modules" / ".ratslotse-stamp").is_file()
    assert not (tmp_path / "web" / "frontend-modules-staging").exists()
    assert not list(frontend.glob("node_modules-old-*"))

    second = _run(tmp_path, frontend)
    assert second.returncode == 0 and "unverändert" in second.stdout
    assert _ci_calls(tmp_path) == 1, "ein unveränderter Stand darf npm ci nicht aufrufen"


def test_new_lockfile_builds_aside_and_swaps(tmp_path):
    frontend = _frontend(tmp_path)
    assert _run(tmp_path, frontend).returncode == 0
    (frontend / "package-lock.json").write_text('{"v": 2}')
    result = _run(tmp_path, frontend)
    assert result.returncode == 0, result.stderr
    assert _installed_lock(frontend).read_text() == '{"v": 2}'
    assert _ci_calls(tmp_path) == 2
    assert not list(frontend.glob("node_modules-old-*"))


def test_half_emptied_tree_with_stamp_is_reinstalled(tmp_path):
    """06.09.2026 auf Prod: rsync hatte node_modules halb geleert — der
    Stempel allein darf dann nicht reichen."""
    frontend = _frontend(tmp_path)
    assert _run(tmp_path, frontend).returncode == 0
    _installed_lock(frontend).unlink()
    assert _run(tmp_path, frontend).returncode == 0
    assert _installed_lock(frontend).is_file()
    assert _ci_calls(tmp_path) == 2


def test_failed_npm_ci_keeps_old_tree(tmp_path):
    frontend = _frontend(tmp_path)
    assert _run(tmp_path, frontend).returncode == 0
    (frontend / "package-lock.json").write_text('{"v": 2}')
    result = _run(tmp_path, frontend, NPM_FAIL="1")
    assert result.returncode != 0 and "alten Stand" in result.stderr
    assert _installed_lock(frontend).read_text() == '{"v": 1}'


def _server_scripts(workflow: dict) -> list[str]:
    """What runs on the server: scripts of SSH steps and `run` blocks that go
    there via `ssh target`. The docs build on the GitHub runner may keep its
    `npm ci`."""
    scripts = []
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            if step.get("uses") == "./.github/actions/ssh":
                scripts.append(step.get("with", {}).get("script", ""))
            elif "ssh target" in step.get("run", ""):
                scripts.append(step["run"])
    return scripts


def test_no_deploy_runs_npm_ci_on_the_server():
    for name in DEPLOYS:
        scripts = _server_scripts(yaml.safe_load((WORKFLOWS / name).read_text()))
        commands = [line.strip() for script in scripts for line in script.splitlines()
                    if line.strip() and not line.strip().startswith("#")]
        direct = [c for c in commands if "npm ci" in c]
        assert not direct, (
            f"{name} führt `npm ci` auf dem Server aus: {direct}. Das leert node_modules unter "
            "dem laufenden `next start` — stattdessen "
            "`.venv/bin/python scripts/install_frontend_modules.py web/frontend`.")
        assert any("scripts/install_frontend_modules.py web/frontend" in c for c in commands), (
            f"{name} erneuert die Frontend-Module nicht über scripts/install_frontend_modules.py.")
