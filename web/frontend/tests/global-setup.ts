/**
 * Global setup: starts the FastAPI backend on port 8001 with throwaway SQLite
 * databases so the Playwright tests run against a real (but isolated) backend.
 * Port 8001 avoids conflicts with a locally-running dev backend on 8000.
 */
import { ChildProcess, spawn } from "child_process";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

let proc: ChildProcess | null = null;

export default async function globalSetup() {
  const repoRoot = path.resolve(__dirname, "../../../../");
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "stadtpuls-e2e-"));
  const nwzDb = path.join(tmpDir, "nwz.sqlite");
  const councilDb = path.join(tmpDir, "council.sqlite");

  process.env.PLAYWRIGHT_NWZ_DB = nwzDb;
  process.env.PLAYWRIGHT_COUNCIL_DB = councilDb;
  process.env.PLAYWRIGHT_TMP_DIR = tmpDir;

  // Write tmp paths so teardown can clean up
  fs.writeFileSync(path.join(tmpDir, ".tmpdir"), tmpDir);

  const env: Record<string, string> = {
    ...Object.fromEntries(Object.entries(process.env).filter(([, v]) => v !== undefined)) as Record<string, string>,
    NWZ_DB: nwzDb,
    COUNCIL_DB: councilDb,
    WEB_JWT_SECRET: "e2e-test-secret",
    WEB_ADMIN_EMAIL: "admin@test.de",
    COOKIE_SECURE: "false",
    DISABLE_RATE_LIMIT: "1",
    TELEGRAM_BOT_USERNAME: "testbot",
    PYTHONPATH: repoRoot,
  };

  const cmd = `/usr/bin/python3.11 /usr/local/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --log-level warning`;
  proc = spawn(cmd, [], {
    cwd: path.join(repoRoot, "web/backend"),
    env,
    stdio: "pipe",
    shell: true,
  });

  if (proc.stderr) {
    proc.stderr.on("data", (d: Buffer) => process.stderr.write("[backend] " + d));
  }

  // Store pid for teardown
  process.env.PLAYWRIGHT_BACKEND_PID = String(proc.pid);

  // Wait until the backend responds
  await waitForBackend("http://127.0.0.1:8001/api/health", 15_000);
}

async function waitForBackend(url: string, timeout: number) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(url);
      if (r.ok) return;
    } catch {}
    await new Promise((res) => setTimeout(res, 200));
  }
  throw new Error(`Backend at ${url} did not become ready within ${timeout}ms`);
}
