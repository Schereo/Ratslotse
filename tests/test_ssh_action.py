"""Die eigene SSH-Action (``.github/actions/ssh``) und ihre Verwendung.

Bis 11/2026 bekam ``appleboy/ssh-action`` den Deploy-Schlüssel und lud das
Programm, das ihn benutzt, zur Laufzeit ohne Prüfsumme nach. Die eigene Action
nutzt nur das OpenSSH des Runners. Hier wird geprüft:

1. ``run.sh`` selbst — gegen ein nachgebautes ``ssh``, das den Befehl lokal
   ausführt, statt einen Server zu fragen. So läuft der ganze Weg einmal durch:
   Umgebung exportieren, Skript über stdin an ``bash -s``, Exit-Code zurück.
2. die Workflows — dass jeder Schritt mit der Action einen Checkout davor hat
   (sonst findet GitHub die Action nicht, und ein Ops-Workflow fällt erst beim
   nächsten Handstart um), nur Eingaben nutzt, die es gibt, und jede Variable
   aus ``envs`` auch setzt. Und dass der Schlüssel an keine fremde Action geht.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / ".github" / "actions" / "ssh"
RUN = ACTION / "run.sh"
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))
LOCAL_SSH = "./.github/actions/ssh"

#: Nachgebautes ssh: hält Aufruf und Konfiguration fest und führt den
#: entfernten Befehl so aus, wie es sshd täte — als `$SHELL -c` im Home.
FAKE_SSH = r"""#!/bin/sh
cfg=""
while [ $# -gt 0 ]; do
  case "$1" in
    -F) cfg="$2"; shift 2 ;;
    -T) shift ;;
    *) break ;;
  esac
done
host="$1"; shift
printf '%s\n' "$host" "$@" >> "$FAKE_LOG/argv"
cp "$cfg" "$FAKE_LOG/config"
keydir=$(dirname "$cfg")
ls -l "$keydir" > "$FAKE_LOG/files"
cp "$keydir/key" "$FAKE_LOG/key"
[ -f "$keydir/proxy_key" ] && cp "$keydir/proxy_key" "$FAKE_LOG/proxy_key"
cd "$FAKE_HOME" && exec sh -c "$*"
"""

#: `timeout` gibt es auf macOS nicht; der Ersatz kann, was run.sh braucht.
FAKE_TIMEOUT = r"""#!/usr/bin/env python3
import subprocess, sys
args = sys.argv[1:]
if args[0] == "-k":
    args = args[2:]
dur, cmd = args[0], args[1:]
unit = {"s": 1, "m": 60, "h": 3600, "d": 86400}
secs = float(dur[:-1]) * unit[dur[-1]] if dur[-1] in unit else float(dur)
try:
    sys.exit(subprocess.run(cmd, timeout=secs).returncode)
except subprocess.TimeoutExpired:
    sys.exit(124)
"""

KEY = "-----BEGIN OPENSSH PRIVATE KEY-----\nAAAAzielschluessel\n-----END OPENSSH PRIVATE KEY-----"
PROXY_KEY = "-----BEGIN OPENSSH PRIVATE KEY-----\nAAAAsprungschluessel\n-----END OPENSSH PRIVATE KEY-----"


@pytest.fixture
def remote(tmp_path):
    """Führt run.sh mit nachgebautem ssh aus; gibt eine Aufruf-Funktion zurück."""
    bin_dir, log, home, runner_temp = (tmp_path / n for n in ("bin", "log", "home", "runner"))
    for d in (bin_dir, log, home, runner_temp):
        d.mkdir()
    (bin_dir / "ssh").write_text(FAKE_SSH)
    (bin_dir / "ssh").chmod(0o755)
    if not shutil.which("timeout"):
        (bin_dir / "timeout").write_text(FAKE_TIMEOUT)
        (bin_dir / "timeout").chmod(0o755)

    def call(cwd: Path | None = None, extra_env: dict[str, str] | None = None, **inputs: str):
        env = {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(tmp_path),
            "RUNNER_TEMP": str(runner_temp),
            "FAKE_LOG": str(log),
            "FAKE_HOME": str(home),
            "INPUT_HOST": "ziel.example.org",
            "INPUT_PORT": "2222",
            "INPUT_USERNAME": "deploy",
            "INPUT_KEY": KEY,
            "INPUT_PROXY_HOST": "sprung.example.org",
            "INPUT_PROXY_PORT": "2223",
            "INPUT_PROXY_USERNAME": "springer",
            "INPUT_PROXY_KEY": PROXY_KEY,
            **{f"INPUT_{k.upper()}": v for k, v in inputs.items()},
            **(extra_env or {}),
        }
        result = subprocess.run(["bash", str(RUN)], env=env, cwd=cwd or tmp_path,
                                capture_output=True, text=True, timeout=60)
        result.log = log  # type: ignore[attr-defined]
        result.home = home  # type: ignore[attr-defined]
        result.runner_temp = runner_temp  # type: ignore[attr-defined]
        return result

    return call


def test_script_runs_remotely_and_returns_its_output(remote):
    r = remote(script="echo hallo vom ziel\npwd")
    assert r.returncode == 0, r.stderr
    assert "hallo vom ziel" in r.stdout
    assert str(r.home) in r.stdout


def test_env_values_arrive_unchanged_and_never_as_an_argument(remote):
    tricky = "a b 'c' \"d\" $HOME `id` \\e\nzweite zeile; rm -rf /"
    r = remote(script='printf "%s" "$WERT" > wert.txt', envs="WERT, LEER",
               extra_env={"WERT": tricky, "LEER": ""})
    assert r.returncode == 0, r.stderr
    assert (r.home / "wert.txt").read_text() == tricky
    argv = (r.log / "argv").read_text()
    assert "zweite zeile" not in argv and "rm -rf" not in argv, (
        "Ein Wert aus envs stand im SSH-Befehl — damit stünde er auf dem Ziel in `ps`.")
    assert argv.splitlines() == ["ratslotse-target", "bash -s"]
    assert "Umgebung: WERT LEER" in r.stdout


def test_a_variable_named_in_envs_must_be_set(remote):
    r = remote(script="echo nie", envs="FEHLT_GANZ")
    assert r.returncode == 2
    assert "FEHLT_GANZ" in r.stderr and "nie" not in r.stdout


def test_commands_reading_stdin_do_not_swallow_the_rest_of_the_script(remote):
    r = remote(script="cat\nread zeile || true\necho nach-dem-lesen")
    assert r.returncode == 0, r.stderr
    assert "nach-dem-lesen" in r.stdout


def test_remote_exit_code_is_passed_on(remote):
    r = remote(script="echo vorher\nexit 3")
    assert r.returncode == 3
    assert "vorher" in r.stdout and "Exit 3" in r.stderr


def test_command_timeout_stops_the_script(remote):
    r = remote(script="sleep 3\necho zu-spaet", command_timeout="1s")
    assert r.returncode in (124, 137)
    assert "zu-spaet" not in r.stdout and "command_timeout" in r.stderr


def test_config_goes_through_the_jump_host_with_both_keys(remote):
    r = remote(script="true")
    assert r.returncode == 0, r.stderr
    config = (r.log / "config").read_text()
    for line in ("HostName ziel.example.org", "Port 2222", "User deploy", "ProxyJump ratslotse-jump",
                 "HostName sprung.example.org", "Port 2223", "User springer",
                 "IdentitiesOnly yes", "BatchMode yes", "StrictHostKeyChecking accept-new"):
        assert line in config, line
    assert (r.log / "key").read_text() == KEY + "\n"
    assert (r.log / "proxy_key").read_text() == PROXY_KEY + "\n"
    modes = [ln.split()[0] for ln in (r.log / "files").read_text().splitlines() if ln.startswith("-")]
    assert modes and all(m.startswith("-rw-------") for m in modes), modes


def test_keys_are_gone_afterwards_even_after_a_failure(remote):
    r = remote(script="exit 1")
    assert r.returncode == 1
    assert list(r.runner_temp.iterdir()) == []


def test_proxy_key_defaults_to_the_target_key_and_proxy_is_optional(remote):
    r = remote(script="true", proxy_key="")
    assert (r.log / "proxy_key").read_text() == KEY + "\n"
    r = remote(script="true", proxy_host="")
    assert r.returncode == 0, r.stderr
    assert "ProxyJump" not in (r.log / "config").read_text()


def test_known_hosts_switches_on_strict_checking(remote):
    r = remote(script="true", known_hosts="[ziel.example.org]:2222 ssh-ed25519 AAAA")
    assert "StrictHostKeyChecking yes" in (r.log / "config").read_text()


def test_upload_copies_into_the_target_folder(remote, tmp_path):
    work = tmp_path / "workspace"
    work.mkdir()
    (work / "schnappschuss.json").write_text('{"ok": true}')
    r = remote(cwd=work, source="schnappschuss.json", target="app/data/")
    assert r.returncode == 0, r.stderr
    assert (r.home / "app" / "data" / "schnappschuss.json").read_text() == '{"ok": true}'


@pytest.mark.parametrize("inputs, message", [
    ({"host": "zwei woerter", "script": "true"}, "host"),
    ({"port": "zweiundzwanzig", "script": "true"}, "port"),
    ({"key": "", "script": "true"}, "key"),
    ({"command_timeout": "1h30m", "script": "true"}, "command_timeout"),
    ({"envs": "kein-name", "script": "true"}, "envs"),
    ({"source": "gibt-es-nicht.txt", "target": "app/"}, "gibt-es-nicht"),
    ({}, "Weder script noch source"),
])
def test_bad_inputs_stop_before_connecting(remote, inputs, message):
    r = remote(**inputs)
    assert r.returncode == 2, r.stderr
    assert message in r.stderr
    assert not (r.log / "argv").exists()


# ── Verwendung in den Workflows ────────────────────────────────────────────


def _declared_inputs() -> set[str]:
    return set(yaml.safe_load((ACTION / "action.yml").read_text(encoding="utf-8"))["inputs"])


def _ssh_steps():
    """(Datei, Job-Name, Job, Index, Schritt) für jeden Schritt mit der eigenen Action."""
    for path in WORKFLOWS:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in (workflow.get("jobs") or {}).items():
            for index, step in enumerate(job.get("steps") or []):
                if step.get("uses") == LOCAL_SSH:
                    yield path.name, workflow, job_name, job, index, step


def test_the_action_is_actually_used():
    files = {f for f, *_ in _ssh_steps()}
    assert {"deploy.yml", "deploy-dev.yml", "deploy-feature.yml"} <= files


def test_every_ssh_step_has_a_checkout_before_it():
    missing = []
    for file, _, job_name, job, index, _ in _ssh_steps():
        checkouts = [s for s in job["steps"][:index] if str(s.get("uses", "")).startswith("actions/checkout@")]
        sparse = [str((s.get("with") or {}).get("sparse-checkout", "")) for s in checkouts]
        if not checkouts or not any(not sp or ".github/actions" in sp for sp in sparse):
            missing.append(f"{file}:{job_name}")
    assert not missing, (
        f"Ohne Checkout findet GitHub die lokale Action nicht: {missing}. Davor einfügen:\n"
        "      - uses: actions/checkout@v7\n        with:\n"
        "          sparse-checkout: .github/actions\n          persist-credentials: false")


def test_only_declared_inputs_are_passed():
    declared = _declared_inputs()
    unknown = sorted(f"{file}:{job_name} {key}"
                     for file, _, job_name, _, _, step in _ssh_steps()
                     for key in (step.get("with") or {}) if key not in declared)
    assert not unknown, (
        f"Diese Eingaben kennt .github/actions/ssh/action.yml nicht: {unknown}. "
        "GitHub warnt dabei nur — ein `comand_timeout` liefe still mit dem Vorgabewert.")


def test_every_name_in_envs_is_set_by_the_step():
    missing = []
    for file, workflow, job_name, job, _, step in _ssh_steps():
        names = [n.strip() for n in str((step.get("with") or {}).get("envs", "")).split(",") if n.strip()]
        available = set(workflow.get("env") or {}) | set(job.get("env") or {}) | set(step.get("env") or {})
        missing += [f"{file}:{job_name} {n}" for n in names if n not in available]
    assert not missing, (
        f"In envs genannt, aber nirgends unter env: gesetzt: {missing}. "
        "run.sh bricht dann ab — erst beim nächsten Lauf des Workflows.")


def test_the_deploy_key_goes_to_no_foreign_action():
    """Der Schlüssel darf nur an `run:`-Schritte und lokale Actions gehen."""
    leaks = []
    for path in WORKFLOWS:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in (workflow.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                uses = str(step.get("uses", ""))
                if uses and not uses.startswith("./"):
                    passed = str(step.get("with") or "") + str(step.get("env") or "")
                    if "SSH_PRIVATE_KEY" in passed:
                        leaks.append(f"{path.name}:{job_name} → {uses}")
    assert not leaks, (
        f"secrets.SSH_PRIVATE_KEY geht an eine fremde Action: {leaks}. "
        f"Stattdessen `uses: {LOCAL_SSH}` (gleiche Eingaben wie appleboy/ssh-action).")
