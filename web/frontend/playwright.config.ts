import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 }, // auth API call can take a few seconds on first render
  // In der CI EIN Versuch mehr. Browsertests hängen an Zeitverhalten, das auf
  // einem geteilten Läufer schwankt — ein einzelner Aussetzer soll keinen Merge
  // blockieren. Lokal bleibt es bei null: Wer hier grün sieht, soll es auch
  // beim ersten Anlauf gewesen sein.
  retries: process.env.CI ? 1 : 0,
  workers: 1, // serial so the shared backend DB stays consistent

  use: {
    baseURL: "http://localhost:3000",
    // Disable CSS animations/transitions so screenshots aren't captured mid-fade
    // (dialogs use a 200ms fade-in/zoom-in that otherwise renders semi-transparent).
    reducedMotion: "reduce",
    // Full-page screenshot after every test so you can see the UI without a headed browser.
    screenshot: "on",
    // Keep video + trace only on failures — useful for debugging.
    video: "retain-on-failure",
    trace: "retain-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  // Playwright starts these webServers in order before running tests.
  // The backend shell script handles its own temp-db cleanup on exit.
  webServer: [
    {
      // FastAPI backend with isolated SQLite databases
      command: "/bin/sh tests/start-backend.sh",
      url: "http://127.0.0.1:8001/api/health",
      reuseExistingServer: false,
      timeout: 30_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      // Next.js dev server — proxies /api/* → :8001
      command: "BACKEND_URL=http://127.0.0.1:8001 npm run dev -- --port 3000",
      url: "http://localhost:3000",
      reuseExistingServer: false,
      timeout: 60_000,
      stdout: "pipe",
      stderr: "pipe",
      env: { BACKEND_URL: "http://127.0.0.1:8001" },
    },
  ],

  reporter: [
    // Interactive HTML report: run `npx playwright show-report` to open it.
    ["html", { outputFolder: "playwright-report", open: "never" }],
    ["list"],
  ],

  outputDir: "test-results",
});
