#!/usr/bin/env bash
# Schritt der Action .github/actions/ssh — Warum und Eingaben: action.yml.
#
# Ablauf: Schlüssel und eine ssh_config in ein eigenes 0700-Verzeichnis unter
# RUNNER_TEMP, optional Dateien als tar hinüber, dann das Skript über stdin an
# `bash -s` auf dem Ziel. Am Ende wird das Verzeichnis gelöscht, auch bei
# Fehlern.
#
# Das Skript geht über STDIN, nicht als Argument: Ein SSH-Befehl landet auf dem
# Ziel als `$SHELL -c '<befehl>'` in der Prozessliste, und die kann jeder
# Benutzer der Maschine lesen. appleboy/ssh-action hängte die `envs` als
# `export X='…'`-Zeilen vor das Skript und schickte alles als Befehl — der
# Abruf-Token des Dev-Deploys stand also für die Dauer des Deploys in `ps`.
#
# Muss mit bash 3.2 laufen: tests/test_ssh_action.py ruft es auf macOS auf.
set -euo pipefail

fail() {
  echo "::error::ssh-Action: $*" >&2
  exit 2
}

# Werte aus Secrets landen als Zeile in der ssh_config; ein Leerzeichen oder
# Zeilenumbruch darin machte daraus zwei Anweisungen.
single_token() {
  case "$2" in
    "") fail "$1 ist leer." ;;
    *[[:space:]]*) fail "$1 enthält ein Leerzeichen oder einen Zeilenumbruch." ;;
  esac
}

port_number() {
  [[ $2 =~ ^[0-9]+$ ]] || fail "$1 ist keine Portnummer."
}

host=${INPUT_HOST:-}
username=${INPUT_USERNAME:-}
port=${INPUT_PORT:-}
port=${port:-22}
key=${INPUT_KEY:-}
proxy_host=${INPUT_PROXY_HOST:-}
proxy_username=${INPUT_PROXY_USERNAME:-}
proxy_port=${INPUT_PROXY_PORT:-}
proxy_port=${proxy_port:-22}
proxy_key=${INPUT_PROXY_KEY:-}
known_hosts=${INPUT_KNOWN_HOSTS:-}
script=${INPUT_SCRIPT:-}
envs=${INPUT_ENVS:-}
command_timeout=${INPUT_COMMAND_TIMEOUT:-}
command_timeout=${command_timeout:-10m}
source_list=${INPUT_SOURCE:-}
target=${INPUT_TARGET:-}

single_token host "$host"
single_token username "$username"
port_number port "$port"
[ -n "$key" ] || fail "key ist leer."
if [ -n "$proxy_host" ]; then
  single_token proxy_host "$proxy_host"
  single_token proxy_username "$proxy_username"
  port_number proxy_port "$proxy_port"
fi
# Go-Dauern wie `1h30m` versteht `timeout` nicht; die Workflows nutzen nur
# eine Einheit, und so bleibt es.
[[ $command_timeout =~ ^[0-9]+[smhd]?$ ]] ||
  fail "command_timeout „$command_timeout“ ist keine Dauer wie 30m oder 2h."
[ -n "$script" ] || [ -n "$source_list" ] || fail "Weder script noch source gesetzt."
if [ -n "$source_list" ]; then
  single_token target "$target"
fi
# Ohne geprüfte Host-Schlüssel wird nicht verbunden: Ein frischer Runner
# nähme sonst jeden Schlüssel an, auch den eines Rechners, der sich als
# Server ausgibt. Bis 11/2026 war das nur eine Warnung.
[ -n "$known_hosts" ] ||
  fail "known_hosts ist leer. Secret VPS_KNOWN_HOSTS setzen, Anleitung: ratslotse.de/docs/betrieb/ unter „Host-Schlüssel“."
entries=$(printf '%s\n' "$known_hosts" | tr -d '\r' | grep -Ecv '^[[:space:]]*(#|$)' || true)
[ "$entries" -gt 0 ] || fail "known_hosts enthält keinen Eintrag."

umask 077
workdir=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/ssh-action.XXXXXX")
trap 'rm -rf "$workdir"' EXIT

printf '%s\n' "$key" | tr -d '\r' >"$workdir/key"
if [ -n "$proxy_host" ]; then
  printf '%s\n' "${proxy_key:-$key}" | tr -d '\r' >"$workdir/proxy_key"
fi

printf '%s\n' "$known_hosts" | tr -d '\r' >"$workdir/known_hosts"

{
  echo "Host ratslotse-target"
  echo "  HostName $host"
  echo "  Port $port"
  echo "  User $username"
  echo "  IdentityFile \"$workdir/key\""
  if [ -n "$proxy_host" ]; then
    echo "  ProxyJump ratslotse-jump"
    echo "Host ratslotse-jump"
    echo "  HostName $proxy_host"
    echo "  Port $proxy_port"
    echo "  User $proxy_username"
    echo "  IdentityFile \"$workdir/proxy_key\""
  fi
  echo "Host *"
  echo "  IdentitiesOnly yes"
  echo "  BatchMode yes"
  echo "  StrictHostKeyChecking yes"
  echo "  UserKnownHostsFile \"$workdir/known_hosts\""
  echo "  GlobalKnownHostsFile /dev/null"
  echo "  ConnectTimeout 30"
  # Lange stille Läufe (OCR: drei Stunden) halten die Verbindung offen; reißt
  # sie ab, endet ssh nach drei Minuten statt erst am command_timeout.
  echo "  ServerAliveInterval 30"
  echo "  ServerAliveCountMax 6"
  echo "  LogLevel ERROR"
} >"$workdir/config"

# Ruft ssh mit Zeitlimit auf und übersetzt den Exit-Code in eine Meldung.
run_remote() {
  local what=$1 rc
  shift
  set +e
  timeout -k 30 "$command_timeout" ssh -F "$workdir/config" -T ratslotse-target "$@"
  rc=$?
  set -e
  case $rc in
    0) return 0 ;;
    124 | 137) echo "::error::$what nach $command_timeout abgebrochen (command_timeout)." >&2 ;;
    255) echo "::error::$what: SSH-Verbindung zu Ziel oder Sprungrechner gescheitert (Exit 255). Steht „Host key verification failed“ darüber, fehlt der Schlüssel in VPS_KNOWN_HOSTS oder hat sich geändert." >&2 ;;
    *) echo "::error::$what endete auf dem Ziel mit Exit $rc." >&2 ;;
  esac
  exit "$rc"
}

if [ -n "$source_list" ]; then
  sources=()
  IFS=',' read -r -a parts <<<"$source_list"
  for part in ${parts[@]+"${parts[@]}"}; do
    part=${part#"${part%%[![:space:]]*}"}
    part=${part%"${part##*[![:space:]]}"}
    [ -n "$part" ] || continue
    [ -e "$part" ] || fail "source „$part“ gibt es nicht."
    sources+=("$part")
  done
  [ "${#sources[@]}" -gt 0 ] || fail "source nennt keine Datei."
  tar -cf "$workdir/upload.tar" -- "${sources[@]}"
  quoted_target=$(printf '%q' "$target")
  echo "Kopiere ${sources[*]} nach $target"
  run_remote "Kopieren" "mkdir -p -- $quoted_target && tar -xf - -C $quoted_target" <"$workdir/upload.tar"
fi

if [ -n "$script" ]; then
  exported=()
  # Das ganze Skript steht in einem `{ … } </dev/null`: bash liest den Block
  # vollständig, bevor es ihn ausführt, und nichts darin kann den Rest des
  # Skripts von stdin wegessen (ein `cat`, `read` oder `ssh` ohne Eingabe).
  {
    echo "{"
    if [ -n "$envs" ]; then
      IFS=',' read -r -a names <<<"$envs"
      for name in ${names[@]+"${names[@]}"}; do
        name=${name//[[:space:]]/}
        [ -n "$name" ] || continue
        [[ $name =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || fail "envs: „$name“ ist kein Variablenname."
        # Leer ist erlaubt (ein leerer Workflow-Schalter), fehlend nicht: Dann
        # fehlt der Eintrag unter `env:` des Schritts, und das Skript liefe
        # still ohne die Variable.
        [ -n "${!name+set}" ] || fail "envs nennt $name, aber der Schritt setzt die Variable nicht (env:)."
        printf 'export %s=%q\n' "$name" "${!name}"
        exported+=("$name")
      done
    fi
    printf '%s\n' "$script"
    echo "} </dev/null"
  } >"$workdir/script.sh"
  echo "Skript auf dem Ziel, Zeitlimit $command_timeout${exported[0]+, Umgebung: ${exported[*]}}"
  run_remote "Das Skript" "bash -s" <"$workdir/script.sh"
fi
