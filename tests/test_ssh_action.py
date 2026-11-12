"""Die eigenen SSH-Actions (``.github/actions/ssh``, ``…/ssh-config``) und ihre Verwendung.

Bis 11/2026 bekam ``appleboy/ssh-action`` den Deploy-Schlüssel und lud das
Programm, das ihn benutzt, zur Laufzeit ohne Prüfsumme nach. Die eigene Action
nutzt nur das OpenSSH des Runners. ``ssh-config`` ersetzt die fünf
handgeschriebenen ``~/.ssh/config``-Blöcke, die alle ``StrictHostKeyChecking
no`` trugen. Hier wird geprüft:

1. ``ssh/run.sh`` — gegen ein nachgebautes ``ssh``, das den Befehl lokal
   ausführt, statt einen Server zu fragen. So läuft der ganze Weg einmal durch:
   Umgebung exportieren, Skript über stdin an ``bash -s``, Exit-Code zurück.
2. ``ssh-config/run.sh`` — und ob das echte ``ssh -G`` beide Konfigurationen
   so liest, wie sie gemeint sind.
3. die Workflows — dass jeder Schritt mit einer der Actions einen Checkout
   davor hat (sonst findet GitHub die Action nicht, und ein Ops-Workflow fällt
   erst beim nächsten Handstart um), nur Eingaben nutzt, die es gibt, jede
   Variable aus ``envs`` auch setzt und ``VPS_KNOWN_HOSTS`` mitgibt. Und dass
   der Schlüssel an nichts anderes geht als an diese beiden Actions.
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
CONFIG_ACTION = ROOT / ".github" / "actions" / "ssh-config"
CONFIG_RUN = CONFIG_ACTION / "run.sh"
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))
LOCAL_SSH = "./.github/actions/ssh"
LOCAL_SSH_CONFIG = "./.github/actions/ssh-config"
LOCAL_ACTIONS = {LOCAL_SSH: ACTION, LOCAL_SSH_CONFIG: CONFIG_ACTION}
KNOWN_HOSTS_INPUT = "${{ secrets.VPS_KNOWN_HOSTS }}"
#: Das echte ssh, für `ssh -G` (liest eine Konfiguration, ohne zu verbinden).
REAL_SSH = shutil.which("ssh")

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
    assert r.returncode == 0, r.stderr
    assert "StrictHostKeyChecking yes" in (r.log / "config").read_text()
    assert "::warning" not in r.stdout


def test_without_known_hosts_every_run_carries_a_warning(remote):
    r = remote(script="true")
    assert r.returncode == 0, r.stderr
    assert "::warning title=Host-Schlüssel ungeprüft::" in r.stdout
    assert "VPS_KNOWN_HOSTS" in r.stdout


def test_known_hosts_without_an_entry_is_refused(remote):
    r = remote(script="true", known_hosts="# nur ein Kommentar\n\n")
    assert r.returncode == 2
    assert "keinen Eintrag" in r.stderr
    assert not (r.log / "argv").exists()


def test_a_failed_connection_points_to_the_secret_when_checking(remote):
    """Exit 255 heißt bei strenger Prüfung meist: Schlüssel fehlt oder ist neu."""
    r = remote(script="exit 255", known_hosts="[ziel.example.org]:2222 ssh-ed25519 AAAA")
    assert r.returncode == 255
    assert "VPS_KNOWN_HOSTS" in r.stderr


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


@pytest.mark.skipif(REAL_SSH is None, reason="kein ssh installiert")
def test_real_ssh_reads_the_config_as_meant(remote):
    r = remote(script="true", known_hosts="[ziel.example.org]:2222 ssh-ed25519 AAAA")
    assert r.returncode == 0, r.stderr
    target = _ssh_g(r.log / "config", "ratslotse-target")
    assert target["hostname"] == "ziel.example.org" and target["port"] == "2222"
    assert target["user"] == "deploy" and target["proxyjump"] == "ratslotse-jump"
    assert target["stricthostkeychecking"] == "true"
    jump = _ssh_g(r.log / "config", "ratslotse-jump")
    assert jump["hostname"] == "sprung.example.org" and jump["port"] == "2223"
    assert jump["user"] == "springer" and jump["stricthostkeychecking"] == "true"


# ── ssh-config ─────────────────────────────────────────────────────────────


def _ssh_g(config: Path, host: str) -> dict[str, str]:
    """Was ssh für `host` aus `config` liest — erste Belegung je Schlüssel."""
    assert REAL_SSH
    out = subprocess.run([REAL_SSH, "-G", "-F", str(config), host],
                         capture_output=True, text=True, timeout=30, check=True).stdout
    seen: dict[str, str] = {}
    for line in out.splitlines():
        key, _, value = line.partition(" ")
        seen.setdefault(key, value)
    return seen


@pytest.fixture
def configure(tmp_path):
    """Führt ssh-config/run.sh mit eigenem HOME aus."""
    home = tmp_path / "runner-home"
    home.mkdir()

    def call(**inputs: str):
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(home),
            "INPUT_TARGETS": "prod prod.example.org\ndev  dev.example.org \n",
            "INPUT_PORT": "2222",
            "INPUT_USERNAME": "deploy",
            "INPUT_KEY": KEY,
            "INPUT_PROXY_HOST": "sprung.example.org",
            "INPUT_PROXY_PORT": "2223",
            "INPUT_PROXY_USERNAME": "springer",
            **{f"INPUT_{k.upper()}": v for k, v in inputs.items()},
        }
        result = subprocess.run(["bash", str(CONFIG_RUN)], env=env, cwd=tmp_path,
                                capture_output=True, text=True, timeout=60)
        result.ssh_dir = home / ".ssh"  # type: ignore[attr-defined]
        return result

    return call


def test_config_names_every_target_behind_the_jump_host(configure):
    r = configure(known_hosts="[prod.example.org]:2222 ssh-ed25519 AAAA\r\n")
    assert r.returncode == 0, r.stderr
    assert "prod dev über edge" in r.stdout and "1 Einträge" in r.stdout
    config = (r.ssh_dir / "config").read_text()
    assert config.count("ProxyJump edge") == 2
    assert "StrictHostKeyChecking yes" in config and "StrictHostKeyChecking no" not in config
    assert (r.ssh_dir / "ratslotse_key").read_text() == KEY + "\n"
    assert "\r" not in (r.ssh_dir / "ratslotse_known_hosts").read_text()
    assert oct(r.ssh_dir.stat().st_mode & 0o777) == "0o700"
    for name in ("ratslotse_key", "ratslotse_known_hosts", "config"):
        assert oct((r.ssh_dir / name).stat().st_mode & 0o777) == "0o600", name


@pytest.mark.skipif(REAL_SSH is None, reason="kein ssh installiert")
def test_real_ssh_reads_the_generated_config_as_meant(configure):
    r = configure(known_hosts="[prod.example.org]:2222 ssh-ed25519 AAAA")
    assert r.returncode == 0, r.stderr
    config = r.ssh_dir / "config"
    for name, host in (("prod", "prod.example.org"), ("dev", "dev.example.org")):
        seen = _ssh_g(config, name)
        assert seen["hostname"] == host and seen["port"] == "2222" and seen["user"] == "deploy"
        assert seen["proxyjump"] == "edge"
        assert seen["stricthostkeychecking"] == "true"
        assert seen["identityfile"] == str(r.ssh_dir / "ratslotse_key")
        assert seen["userknownhostsfile"] == str(r.ssh_dir / "ratslotse_known_hosts")
    edge = _ssh_g(config, "edge")
    assert edge["hostname"] == "sprung.example.org" and edge["port"] == "2223"
    assert edge["user"] == "springer" and edge["stricthostkeychecking"] == "true"


def test_config_without_known_hosts_accepts_the_first_key_and_warns(configure):
    r = configure()
    assert r.returncode == 0, r.stderr
    assert "StrictHostKeyChecking accept-new" in (r.ssh_dir / "config").read_text()
    assert "::warning title=Host-Schlüssel ungeprüft::" in r.stdout


@pytest.mark.parametrize("inputs, message", [
    ({"targets": "target "}, "fehlt ein Secret"),
    ({"targets": "target ein host"}, "fehlt ein Secret"),
    ({"targets": "edge sprung.example.org"}, "Sprungrechner"),
    ({"targets": "a x.example.org\na y.example.org"}, "doppelt"),
    ({"targets": "\n  \n"}, "kein Ziel"),
    ({"proxy_host": ""}, "proxy_host"),
    ({"port": "zweiundzwanzig"}, "port"),
    ({"key": ""}, "key"),
    ({"known_hosts": "# leer"}, "keinen Eintrag"),
])
def test_bad_config_inputs_write_nothing(configure, inputs, message):
    r = configure(**inputs)
    assert r.returncode == 2, r.stderr
    assert message in r.stderr
    assert not (r.ssh_dir / "config").exists()


# ── Verwendung in den Workflows ────────────────────────────────────────────


def _declared_inputs(action: Path) -> set[str]:
    return set(yaml.safe_load((action / "action.yml").read_text(encoding="utf-8"))["inputs"])


def _ssh_steps(actions=(LOCAL_SSH,)):
    """(Datei, Workflow, Job-Name, Job, Index, Schritt) je Schritt mit einer der Actions."""
    for path in WORKFLOWS:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in (workflow.get("jobs") or {}).items():
            for index, step in enumerate(job.get("steps") or []):
                if step.get("uses") in actions:
                    yield path.name, workflow, job_name, job, index, step


def test_the_actions_are_actually_used():
    files = {f for f, *_ in _ssh_steps()}
    assert {"deploy.yml", "deploy-dev.yml", "deploy-feature.yml"} <= files
    files = {f for f, *_ in _ssh_steps((LOCAL_SSH_CONFIG,))}
    assert {"deploy.yml", "ops-erreichbarkeit.yml", "ops-haushalt-vergleich.yml"} <= files


def test_every_ssh_step_has_a_checkout_before_it():
    missing = []
    for file, _, job_name, job, index, _ in _ssh_steps(tuple(LOCAL_ACTIONS)):
        checkouts = [s for s in job["steps"][:index] if str(s.get("uses", "")).startswith("actions/checkout@")]
        sparse = [str((s.get("with") or {}).get("sparse-checkout", "")) for s in checkouts]
        if not checkouts or not any(not sp or ".github/actions" in sp for sp in sparse):
            missing.append(f"{file}:{job_name}")
    assert not missing, (
        f"Ohne Checkout findet GitHub die lokale Action nicht: {missing}. Davor einfügen:\n"
        "      - uses: actions/checkout@v7\n        with:\n"
        "          sparse-checkout: .github/actions\n          persist-credentials: false")


@pytest.mark.parametrize("uses", sorted(LOCAL_ACTIONS))
def test_only_declared_inputs_are_passed(uses):
    declared = _declared_inputs(LOCAL_ACTIONS[uses])
    unknown = sorted(f"{file}:{job_name} {key}"
                     for file, _, job_name, _, _, step in _ssh_steps((uses,))
                     for key in (step.get("with") or {}) if key not in declared)
    assert not unknown, (
        f"Diese Eingaben kennt {uses[2:]}/action.yml nicht: {unknown}. "
        "GitHub warnt dabei nur — ein `comand_timeout` liefe still mit dem Vorgabewert.")


def test_every_ssh_step_checks_host_keys_against_the_secret():
    """Ohne die Zeile nähme der Schritt jeden Host-Schlüssel an, still."""
    missing = sorted(f"{file}:{job_name}"
                     for file, _, job_name, _, _, step in _ssh_steps(tuple(LOCAL_ACTIONS))
                     if (step.get("with") or {}).get("known_hosts") != KNOWN_HOSTS_INPUT)
    assert not missing, (
        f"Diese Schritte geben die Host-Schlüssel nicht mit: {missing}. "
        f"Unter with: ergänzen:  known_hosts: {KNOWN_HOSTS_INPUT}")


def test_no_workflow_switches_host_key_checking_off():
    """Eigene ssh-Konfigurationen gehören in .github/actions/ssh-config."""
    found = sorted(path.name for path in WORKFLOWS
                   if "StrictHostKeyChecking" in path.read_text(encoding="utf-8")
                   or "~/.ssh/config" in path.read_text(encoding="utf-8"))
    assert not found, (
        f"Eigene SSH-Konfiguration in {found}. Stattdessen `uses: {LOCAL_SSH_CONFIG}` "
        "(s. ops-wartungsbarriere.yml) — dort gilt VPS_KNOWN_HOSTS.")


def test_every_name_in_envs_is_set_by_the_step():
    missing = []
    for file, workflow, job_name, job, _, step in _ssh_steps():
        names = [n.strip() for n in str((step.get("with") or {}).get("envs", "")).split(",") if n.strip()]
        available = set(workflow.get("env") or {}) | set(job.get("env") or {}) | set(step.get("env") or {})
        missing += [f"{file}:{job_name} {n}" for n in names if n not in available]
    assert not missing, (
        f"In envs genannt, aber nirgends unter env: gesetzt: {missing}. "
        "run.sh bricht dann ab — erst beim nächsten Lauf des Workflows.")


def test_the_deploy_key_goes_only_to_the_two_actions():
    """Weder an eine fremde Action noch in ein eigenes `run:`-Skript.

    Ein `run:`-Schritt mit dem Schlüssel schriebe ihn selbst irgendwohin — und
    seine Verbindung prüfte die Host-Schlüssel nur, wenn er auch daran denkt.
    """
    leaks = []
    for path in WORKFLOWS:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "SSH_PRIVATE_KEY" in str(workflow.get("env") or ""):
            leaks.append(f"{path.name} (env: des Workflows)")
        for job_name, job in (workflow.get("jobs") or {}).items():
            if "SSH_PRIVATE_KEY" in str(job.get("env") or ""):
                leaks.append(f"{path.name}:{job_name} (env: des Jobs)")
            for step in job.get("steps") or []:
                uses = str(step.get("uses", ""))
                if uses in LOCAL_ACTIONS:
                    if "SSH_PRIVATE_KEY" in str(step.get("env") or ""):
                        leaks.append(f"{path.name}:{job_name} → env: von {uses}")
                    continue
                passed = str(step.get("with") or "") + str(step.get("env") or "") + str(step.get("run") or "")
                if "SSH_PRIVATE_KEY" in passed:
                    leaks.append(f"{path.name}:{job_name} → {uses or 'run:'}")
    assert not leaks, (
        f"secrets.SSH_PRIVATE_KEY geht woandershin: {leaks}. Stattdessen "
        f"`uses: {LOCAL_SSH}` (Skript auf dem Server) oder `uses: {LOCAL_SSH_CONFIG}` "
        "(ssh/scp/rsync im Workflow).")
