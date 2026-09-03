#!/usr/bin/env python3
"""Read-only preflight for production-only release dependencies.

The deploy first streams this file to the installed interpreter before
``rsync`` and runs it again at the cutover to drain older repo processes. It
does not edit ``.env``, install tools, or change crontab, and never prints
secret environment values.
"""
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path


DEFAULT_VIDEO_MODEL = "openai/gpt-5.6-luna"
DEFAULT_STT_MODEL = "google/gemini-2.5-flash"


class PreflightError(RuntimeError):
    """The deploy must stop before code transfer or service restart."""


def _env_file(path: Path) -> dict[str, str]:
    allowed = {
        "APP_MIN_BUILD",
        "OPENROUTER_API_KEY",
        "COUNCIL_VIDEO_MODEL",
        "COUNCIL_STT_MODEL",
    }
    if not path.is_file():
        raise PreflightError(".env fehlt")
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, raw_value = line.split("=", 1)
        name = name.strip()
        if name not in allowed:
            continue
        try:
            values[name] = " ".join(
                shlex.split(raw_value, comments=True, posix=True)
            ).strip()
        except ValueError as error:
            raise PreflightError(f"{name} ist in .env nicht lesbar") from error
    return values


def verify_configuration(
    values: dict[str, str], minimum_app_build: int
) -> tuple[int, str, str]:
    try:
        app_min_build = int(values.get("APP_MIN_BUILD", ""))
    except ValueError as error:
        raise PreflightError("APP_MIN_BUILD ist keine ganze Zahl") from error
    if app_min_build < minimum_app_build:
        raise PreflightError(
            f"APP_MIN_BUILD muss vor diesem Release mindestens {minimum_app_build} sein"
        )
    if not values.get("OPENROUTER_API_KEY", "").strip():
        raise PreflightError("OPENROUTER_API_KEY fehlt oder ist leer")

    video_model = values.get("COUNCIL_VIDEO_MODEL", DEFAULT_VIDEO_MODEL).strip()
    stt_model = values.get("COUNCIL_STT_MODEL", DEFAULT_STT_MODEL).strip()
    if not video_model:
        raise PreflightError("COUNCIL_VIDEO_MODEL ist leer")
    if not stt_model:
        raise PreflightError("COUNCIL_STT_MODEL ist leer")
    return app_min_build, video_model, stt_model


def verify_crontab(crontab: str) -> None:
    active = [
        line.strip()
        for line in crontab.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    requirements = (
        ("30 10 * * *", "scripts/check_council_videos.py"),
        # Der Produktionsserver läuft auf UTC. 13 Uhr UTC entspricht in
        # Oldenburg 14 Uhr (CET) bzw. 15 Uhr (CEST) und liegt damit sicher vor
        # dem üblichen Sitzungsbeginn. 16 Uhr UTC wäre im Sommer erst 18 Uhr.
        ("0 13 * * *", "scripts/record_council_livestream.py"),
    )
    for schedule, script in requirements:
        matches: list[str] = []
        for line in active:
            fields = line.split(maxsplit=5)
            if (
                len(fields) == 6
                and " ".join(fields[:5]) == schedule
                and script in fields[5]
            ):
                matches.append(fields[5])
        if not matches:
            raise PreflightError(f"Aktiver Cron-Eintrag fehlt: {schedule} … {script}")
        if len(matches) != 1:
            raise PreflightError(
                f"Cron-Eintrag für {script} ist {len(matches)}-mal aktiv; "
                "er muss genau einmal laufen"
            )
        if ".venv/bin/python" not in matches[0]:
            raise PreflightError(
                f"Cron-Eintrag für {script} verwendet nicht .venv/bin/python"
            )


def _read_crontab() -> str:
    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PreflightError("crontab konnte nicht gelesen werden") from error
    if result.returncode != 0:
        raise PreflightError("crontab -l war nicht erfolgreich")
    return result.stdout


def verify_systemd_permissions() -> None:
    """Require the effective matching policy to disable authentication.

    ``sudo -n -l COMMAND`` alone is insufficient: with sudoers' default
    ``listpw=any``, any unrelated NOPASSWD entry can make the list operation
    non-interactive even when COMMAND itself still requires a password. Since
    sudo 1.9.15, ``-ll COMMAND`` includes the effective matching rule and its
    ``!authenticate`` option. Older/abridged output is rejected fail-closed.
    """
    commands = (
        ("stop", "nwz-web-api"),
        ("start", "nwz-web-api"),
        ("restart", "nwz-web-frontend"),
    )
    for action, unit in commands:
        try:
            result = subprocess.run(
                ["sudo", "-n", "-ll", "/bin/systemctl", action, unit],
                capture_output=True,
                text=True,
                timeout=10,
                env={**os.environ, "LC_ALL": "C"},
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise PreflightError("sudoers-Rechte konnten nicht geprüft werden") from error
        if result.returncode != 0:
            raise PreflightError(
                f"Passwordless sudo fehlt: /bin/systemctl {action} {unit}"
            )
        option_lines = [
            line.split(":", 1)[1]
            for line in result.stdout.splitlines()
            if line.strip().startswith("Options:") and ":" in line
        ]
        options = {
            option.strip()
            for line in option_lines
            for option in line.split(",")
        }
        if "!authenticate" not in options:
            raise PreflightError(
                "Explizites NOPASSWD ist in der effektiven sudo-Regel nicht "
                f"nachweisbar: /bin/systemctl {action} {unit} "
                "(sudo >= 1.9.15 mit verbose policy listing erforderlich)"
            )


def _tool_version(executable: Path, argument: str, label: str) -> str:
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise PreflightError(f"{label} fehlt oder ist nicht ausführbar")
    try:
        result = subprocess.run(
            [str(executable), argument], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PreflightError(f"{label} lässt sich nicht starten") from error
    if result.returncode != 0:
        raise PreflightError(f"{label} meldet beim Versionscheck einen Fehler")
    lines = (result.stdout or result.stderr).splitlines()
    if not lines:
        raise PreflightError(f"{label} liefert keine Versionsinformation")
    return lines[0].strip()


def _yt_dlp(root: Path) -> Path:
    local = root / ".venv" / "bin" / "yt-dlp"
    if local.is_file():
        return local
    discovered = shutil.which("yt-dlp")
    if not discovered:
        raise PreflightError("yt-dlp fehlt (.venv/bin/yt-dlp oder PATH)")
    return Path(discovered)


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
    except (OSError, ValueError):
        return False
    return True


def running_repo_python_processes(
    root: Path,
    proc_root: Path = Path("/proc"),
    own_pid: int | None = None,
) -> list[tuple[int, str]]:
    """Find older API/cron/ops Python processes belonging to this checkout.

    Linux exposes both argv and cwd through ``/proc``.  Looking at the whole
    repo process is stricter than checking open SQLite file descriptors: a
    cron may still be fetching remote data and open the store only after the
    backup.  Processes started after the maintenance marker see the Store
    guard; this scan catches processes that loaded the previous code before
    that marker existed.
    """
    root = root.resolve()
    own_pid = os.getpid() if own_pid is None else own_pid
    if not proc_root.is_dir():
        raise PreflightError("/proc fehlt; laufende Repo-Prozesse sind nicht prüfbar")

    found: list[tuple[int, str]] = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit() or int(entry.name) == own_pid:
            continue
        pid = int(entry.name)
        try:
            raw_args = (entry / "cmdline").read_bytes().split(b"\0")
            args = [arg.decode(errors="replace") for arg in raw_args if arg]
            cwd = Path(os.readlink(entry / "cwd"))
        except (OSError, PermissionError):
            # Other users' processes are irrelevant and commonly unreadable.
            continue
        if not args:
            continue
        executable = Path(args[0]).name.lower()
        if "python" not in executable and "uvicorn" not in executable:
            continue
        belongs_to_repo = _under(cwd, root)
        if not belongs_to_repo:
            for argument in args:
                candidate = Path(argument)
                if candidate.is_absolute() and _under(candidate, root):
                    belongs_to_repo = True
                    break
        if not belongs_to_repo:
            continue
        label = next(
            (Path(argument).name for argument in args[1:] if argument.endswith(".py")),
            Path(args[0]).name,
        )
        found.append((pid, label))
    return sorted(found)


def verify_quiescent(
    root: Path,
    proc_root: Path = Path("/proc"),
    timeout_seconds: int = 0,
) -> None:
    deadline = time.monotonic() + max(0, timeout_seconds)
    while True:
        running = running_repo_python_processes(root, proc_root=proc_root)
        if not running:
            return
        if time.monotonic() >= deadline:
            detail = ", ".join(f"PID {pid} ({label})" for pid, label in running)
            raise PreflightError(
                "Repo-Pythonprozesse laufen noch nach dem API-Stopp: " + detail
            )
        time.sleep(min(2, max(0, deadline - time.monotonic())))


def verify(
    root: Path,
    minimum_app_build: int,
    require_quiescent: bool = False,
    quiescent_timeout: int = 0,
) -> None:
    root = root.resolve()
    build, video_model, stt_model = verify_configuration(
        _env_file(root / ".env"), minimum_app_build
    )
    verify_crontab(_read_crontab())
    verify_systemd_permissions()
    yt_dlp = _tool_version(_yt_dlp(root), "--version", "yt-dlp")

    # The generic static build has crashed on this production VM's MPEG-TS
    # demuxer. Require the known deployment location preferred by the code.
    ffmpeg = _tool_version(
        Path.home() / "bin" / "ffmpeg", "-version", "FFmpeg unter ~/bin/ffmpeg"
    )
    if require_quiescent:
        verify_quiescent(root, timeout_seconds=quiescent_timeout)
    print(
        "Release-Runtime geprüft: "
        f"APP_MIN_BUILD={build}; Video-Modell={video_model}; STT-Modell={stt_model}; "
        f"yt-dlp={yt_dlp}; FFmpeg={ffmpeg}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--minimum-app-build", type=int, required=True)
    parser.add_argument(
        "--require-quiescent",
        action="store_true",
        help="zusätzlich laufende Python-Prozesse dieses Checkouts ausschließen",
    )
    parser.add_argument(
        "--quiescent-timeout",
        type=int,
        default=0,
        help="Sekunden auf bereits laufende Repo-Prozesse warten",
    )
    args = parser.parse_args()
    try:
        verify(
            args.root,
            args.minimum_app_build,
            args.require_quiescent,
            args.quiescent_timeout,
        )
    except PreflightError as error:
        parser.exit(1, f"PRE-DEPLOY BLOCKIERT: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
