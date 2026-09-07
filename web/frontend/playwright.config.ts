import { defineConfig, devices } from "@playwright/test";

// Die Ports sind einstellbar, und das ist kein Luxus: Dieses Repo wird in
// mehreren `git worktree`s gleichzeitig bearbeitet, und dort läuft fast immer
// schon ein `next dev` auf 3000. Playwright bricht dann ab mit „is already
// used" — und der naheliegende Ausweg, den fremden Prozess abzuschießen,
// trifft die Arbeit einer anderen Sitzung.
//
//     E2E_PORT=3010 E2E_API_PORT=8011 npx playwright test
//
// `tests/start-backend.sh` liest dieselbe Variable für den API-Port.
const PORT = Number(process.env.E2E_PORT || 3000);
const API_PORT = Number(process.env.E2E_API_PORT || 8001);

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 }, // auth API call can take a few seconds on first render
  // In der CI EIN Versuch mehr. Browsertests hängen an Zeitverhalten, das auf
  // einem geteilten Läufer schwankt — ein einzelner Aussetzer soll keinen Merge
  // blockieren. Lokal bleibt es bei null: Wer hier grün sieht, soll es auch
  // beim ersten Anlauf gewesen sein.
  retries: process.env.CI ? 1 : 0,
  // Seriell, damit die geteilte Backend-Datenbank konsistent bleibt: Alle
  // Tests eines Laufs reden mit EINEM uvicorn auf EINER SQLite-Datei.
  //
  // Parallel wird trotzdem gearbeitet, nur eine Ebene höher: Die CI fährt
  // vier Läufer mit `--shard=i/4` (`e2e.yml`), und jeder startet über
  // `tests/start-backend.sh` sein eigenes Backend auf einer eigenen
  // Wegwerf-Datenbank. Die Aufteilung ist deshalb sicher, ohne dass ein
  // einziger Test isoliert werden müsste.
  //
  // Dass sie ganze DATEIEN verteilt und keine einzelnen Tests, hängt an
  // `fullyParallel` — das steht hier bewusst nicht auf `true`. Damit ist eine
  // Datei EINE Gruppe, und die Reihenfolge innerhalb einer Datei bleibt, wie
  // sie ist. Wer `fullyParallel: true` setzt, zerreißt genau das.
  workers: 1,

  use: {
    baseURL: `http://localhost:${PORT}`,
    // Disable CSS animations/transitions so screenshots aren't captured mid-fade
    // (dialogs use a 200ms fade-in/zoom-in that otherwise renders semi-transparent).
    reducedMotion: "reduce",
    // Full-page screenshot after every test so you can see the UI without a headed browser.
    //
    // NUR LOKAL. In der CI wird der Bericht ausschließlich bei Rot gesichert
    // (`if: failure()` in `e2e.yml`) — die Aufnahmen eines grünen Laufs sieht
    // dort also niemand, sie kosten aber je Test eine Vollseiten-Aufnahme.
    // Gemessen über 140 Tests: gut eine Minute für Bilder, die weggeworfen
    // werden. Bei Rot nimmt `only-on-failure` weiterhin auf, der Bericht
    // verliert also nichts, was der Fehlersuche dient.
    screenshot: process.env.CI ? "only-on-failure" : "on",
    // Keep video + trace only on failures — useful for debugging.
    video: "retain-on-failure",
    trace: "retain-on-failure",
  },

  projects: [
    // Meldet jede Identität einmal an und legt ihre Sitzung unter
    // `tests/e2e/.auth/` ab. Warum das die Suite etwa halbiert, steht in
    // `tests/e2e/konten.ts`; wie es gemacht wird, in `tests/e2e/auth.setup.ts`.
    {
      name: "setup",
      testMatch: /.*\.setup\.ts/,
    },
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      // `dependencies` heißt: läuft erst, wenn „setup" grün ist. Scheitert das
      // Anmelden, fallen die Tests nicht einzeln mit „Datei nicht gefunden"
      // aus, sondern der Lauf sagt an EINER Stelle, dass die Sitzung fehlt.
      dependencies: ["setup"],
    },
  ],

  // Playwright starts these webServers in order before running tests.
  // The backend shell script handles its own temp-db cleanup on exit.
  webServer: [
    {
      // FastAPI backend with isolated SQLite databases
      command: "/bin/sh tests/start-backend.sh",
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 30_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      // Next.js dev server — proxies /api/* → :8001
      command: `npm run dev -- --port ${PORT}`,
      url: `http://localhost:${PORT}`,
      reuseExistingServer: false,
      timeout: 60_000,
      stdout: "pipe",
      stderr: "pipe",
      env: { BACKEND_URL: `http://127.0.0.1:${API_PORT}` },
    },
  ],

  reporter: [
    // Interactive HTML report: run `npx playwright show-report` to open it.
    ["html", { outputFolder: "playwright-report", open: "never" }],
    ["list"],
  ],

  outputDir: "test-results",
});
