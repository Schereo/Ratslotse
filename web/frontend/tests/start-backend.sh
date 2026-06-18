#!/bin/sh
# Starts the FastAPI backend on port 8001 with throwaway SQLite databases.
# Called by the Playwright webServer config so it is launched by the shell
# (not from inside Playwright's sandboxed global-setup).
set -e

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
TMP_DIR="$(mktemp -d /tmp/stadtpuls-e2e-XXXXXX)"

export NWZ_DB="$TMP_DIR/nwz.sqlite"
export COUNCIL_DB="$TMP_DIR/council.sqlite"
export WEB_JWT_SECRET="e2e-test-secret"
export WEB_ADMIN_EMAIL="admin@test.de"
export COOKIE_SECURE="false"
export DISABLE_RATE_LIMIT="1"
export TELEGRAM_BOT_USERNAME="testbot"
export PYTHONPATH="$REPO_ROOT"

echo "E2E backend tmp dir: $TMP_DIR"
echo "NWZ_DB=$NWZ_DB"

# Trap cleans up temp dir when this process exits.
trap 'rm -rf "$TMP_DIR"' EXIT INT TERM

cd "$REPO_ROOT/web/backend"
exec /usr/bin/python3.11 /usr/local/bin/uvicorn \
  app.main:app \
  --host 127.0.0.1 \
  --port 8001 \
  --log-level warning
