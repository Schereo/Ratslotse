#!/usr/bin/env bash
# Schritt der Action .github/actions/ssh-config — Warum und Eingaben: action.yml.
#
# Schreibt Schlüssel, known_hosts und ~/.ssh/config. Anders als
# .github/actions/ssh räumt es nichts weg: Die folgenden Schritte des Jobs
# brauchen die Dateien, und der Runner wird nach dem Job verworfen.
#
# Muss mit bash 3.2 laufen: tests/test_ssh_action.py ruft es auf macOS auf.
set -euo pipefail

fail() {
  echo "::error::ssh-config-Action: $*" >&2
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

targets=${INPUT_TARGETS:-}
username=${INPUT_USERNAME:-}
port=${INPUT_PORT:-}
port=${port:-22}
key=${INPUT_KEY:-}
proxy_host=${INPUT_PROXY_HOST:-}
proxy_username=${INPUT_PROXY_USERNAME:-}
proxy_port=${INPUT_PROXY_PORT:-}
proxy_port=${proxy_port:-22}
known_hosts=${INPUT_KNOWN_HOSTS:-}

single_token username "$username"
port_number port "$port"
[ -n "$key" ] || fail "key ist leer."
single_token proxy_host "$proxy_host"
single_token proxy_username "$proxy_username"
port_number proxy_port "$proxy_port"

names=()
hosts=()
while IFS= read -r line || [ -n "$line" ]; do
  line=${line%$'\r'}
  # Nicht `read name host rest`: ein leerer `host` (Secret fehlt) fiele dabei
  # unbemerkt weg.
  [[ $line =~ ^[[:space:]]*$ ]] && continue
  [[ $line =~ ^[[:space:]]*([A-Za-z0-9_-]+)[[:space:]]+([^[:space:]]+)[[:space:]]*$ ]] ||
    fail "targets: Zeile „$line“ ist nicht „<name> <host>“ (fehlt ein Secret?)."
  name=${BASH_REMATCH[1]}
  [ "$name" != edge ] || fail "targets: „edge“ ist der Sprungrechner."
  for seen in ${names[@]+"${names[@]}"}; do
    [ "$seen" != "$name" ] || fail "targets: „$name“ steht doppelt."
  done
  names+=("$name")
  hosts+=("${BASH_REMATCH[2]}")
done <<<"$targets"
[ "${#names[@]}" -gt 0 ] || fail "targets nennt kein Ziel."
# Ohne geprüfte Host-Schlüssel wird nicht verbunden: Ein frischer Runner
# nähme sonst jeden Schlüssel an, auch den eines Rechners, der sich als
# Server ausgibt. Bis 11/2026 war das nur eine Warnung.
[ -n "$known_hosts" ] ||
  fail "known_hosts ist leer. Secret VPS_KNOWN_HOSTS setzen, Anleitung: ratslotse.de/docs/betrieb/ unter „Host-Schlüssel“."
entries=$(printf '%s\n' "$known_hosts" | tr -d '\r' | grep -Ecv '^[[:space:]]*(#|$)' || true)
[ "$entries" -gt 0 ] || fail "known_hosts enthält keinen Eintrag."

ssh_dir="$HOME/.ssh"
umask 077
mkdir -p "$ssh_dir"
chmod 700 "$ssh_dir"
printf '%s\n' "$key" | tr -d '\r' >"$ssh_dir/ratslotse_key"

printf '%s\n' "$known_hosts" | tr -d '\r' >"$ssh_dir/ratslotse_known_hosts"
echo "Host-Schlüssel werden geprüft ($entries Einträge)."

{
  echo "Host edge"
  echo "  HostName $proxy_host"
  echo "  Port $proxy_port"
  echo "  User $proxy_username"
  i=0
  while [ "$i" -lt "${#names[@]}" ]; do
    echo "Host ${names[$i]}"
    echo "  HostName ${hosts[$i]}"
    echo "  Port $port"
    echo "  User $username"
    echo "  ProxyJump edge"
    i=$((i + 1))
  done
  echo "Host *"
  echo "  IdentityFile \"$ssh_dir/ratslotse_key\""
  echo "  IdentitiesOnly yes"
  echo "  BatchMode yes"
  echo "  StrictHostKeyChecking yes"
  echo "  UserKnownHostsFile \"$ssh_dir/ratslotse_known_hosts\""
  echo "  GlobalKnownHostsFile /dev/null"
  echo "  ConnectTimeout 30"
  echo "  ServerAliveInterval 30"
  echo "  ServerAliveCountMax 6"
  echo "  LogLevel ERROR"
} >"$ssh_dir/config"

echo "SSH eingerichtet: ${names[*]} über edge."
