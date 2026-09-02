#!/bin/sh
# Starts the FastAPI backend on port 8001 with throwaway SQLite databases.
# Called by the Playwright webServer config so it is launched by the shell
# (not from inside Playwright's sandboxed global-setup).
set -e

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
TMP_DIR="$(mktemp -d /tmp/ratslotse-e2e-XXXXXX)"

# Der Schalter heißt RATSLOTSE_DB, seit die Konten-Datenbank umbenannt wurde
# (08/2026). Hier stand danach noch NWZ_DB — den liest niemand mehr, und die
# Vorgabe greift: Die Browsertests liefen damit gegen die ECHTE lokale
# data/ratslotse.sqlite und legten dort ihre Testkonten an.
export RATSLOTSE_DB="$TMP_DIR/ratslotse.sqlite"
export COUNCIL_DB="$TMP_DIR/council.sqlite"
export WEB_JWT_SECRET="e2e-test-secret"
export WEB_ADMIN_EMAIL="admin@test.de"
export COOKIE_SECURE="false"
export DISABLE_RATE_LIMIT="1"
export TELEGRAM_BOT_USERNAME="testbot"
# Never inherit a developer's real mail configuration into throwaway browser
# tests. Without delivery configured, test accounts are active immediately.
export RESEND_API_KEY=""
export PYTHONPATH="$REPO_ROOT"

echo "E2E backend tmp dir: $TMP_DIR"
echo "RATSLOTSE_DB=$RATSLOTSE_DB"

# Trap cleans up temp dir when this process exits.
trap 'rm -rf "$TMP_DIR"' EXIT INT TERM

PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/.venv/bin/python}"

# Konten säen, bevor der Server startet. Ohne sie steht jeder Browsertest vor
# einem leeren Konto: kein Thema, keine Merkliste, kein Fortschritt — und
# prüft damit einen Zustand, den nach dem ersten Tag niemand mehr hat.
# `admin@test.de` ist dieselbe Adresse, die `tests/e2e/helpers.ts` benutzt.
"$PYTHON_BIN" "$REPO_ROOT/scripts/saat_konten.py" --db "$RATSLOTSE_DB" \
  --council-db "$COUNCIL_DB" >/dev/null || echo "Saat übersprungen"

cd "$REPO_ROOT/web/backend"
exec "$PYTHON_BIN" -m uvicorn \
  app.main:app \
  --host 127.0.0.1 \
  --port 8001 \
  --log-level warning
