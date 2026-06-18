import * as fs from "fs";

export default async function globalTeardown() {
  const pid = process.env.PLAYWRIGHT_BACKEND_PID;
  if (pid) {
    try {
      process.kill(Number(pid), "SIGTERM");
    } catch {}
  }
  const tmpDir = process.env.PLAYWRIGHT_TMP_DIR;
  if (tmpDir && fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}
