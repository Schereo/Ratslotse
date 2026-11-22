import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Unit-Tests für die LOGIK in `lib/` — nicht für Komponenten.
//
// WARUM DIESE GRENZE. Die Browsertests (`playwright.config.ts`) prüfen die
// Flüsse: anmelden, suchen, eine Seite öffnen. Sie brauchen zwei Server und
// zwei Minuten, und sie sagen bei einem Fehler nur, dass die Seite anders
// aussieht als erwartet. Für eine Funktion, die aus einer Uhrzeit ein
// Live-Fenster rechnet, ist das das falsche Werkzeug: Der Fall „16:29 gegen
// 16:30" ist dort nicht herstellbar, hier ist er eine Zeile.
//
// Komponenten bleiben bewusst außen vor. Ein Test, der JSX rendert, prüft am
// Ende meist die eigene Fixture (s. `tests/CLAUDE.md`) und braucht eine
// DOM-Nachbildung, die mit jeder React-Fassung nachgezogen werden will.
//
// WARUM `.mts`. Das Paket hat kein `"type": "module"`, eine `.ts`-Datei gilt
// für Node also als CommonJS — und diese hier benutzt `import`. Vite 8 lädt sie
// noch über einen Bündelschritt, meldet das aber bei jedem Lauf und kündigt
// an, die Datei künftig von Node selbst laden zu lassen. `.mts` ist in jedem
// Fall ein ES-Modul.
export default defineConfig({
  test: {
    include: ["lib/**/*.test.ts"],
    environment: "node",
    // Deutsche Formatierung und Zeitzone sind Teil dessen, was geprüft wird —
    // ein Test, der auf dem Notebook in Europe/Berlin läuft und in der CI
    // unter UTC, prüft zweierlei. Node liest beides beim Start.
    env: { TZ: "Europe/Berlin", LANG: "de_DE.UTF-8" },
    // „Beim Start" heißt: Jede Testdatei braucht einen eigenen PROZESS. `forks`
    // ist die Vorgabe und steht hier trotzdem, weil die Zeile darüber daran
    // hängt. Gemessen beim Sprung auf vitest 5 (22.11.2026), Elternprozess
    // unter `TZ=UTC LANG=C.UTF-8` wie in der CI: mit `forks` stimmen Zeitzone
    // und Sprache in allen 85 Dateien, mit `threads` in keiner — Threads
    // teilen sich den Prozess, und der ist dann schon unter UTC gestartet.
    pool: "forks",
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)),
      // `server-only` ist eine Next-MARKIERUNG, kein echtes Paket: Ein Modul,
      // das sie importiert, darf nicht ins Browser-Bündel. Außerhalb von Next
      // ließe sich so ein Modul gar nicht laden. Für die Tests ist die
      // Markierung bedeutungslos — sie laufen ohnehin in Node.
      "server-only": fileURLToPath(new URL("./lib/__testhilfen/server-only.ts", import.meta.url)),
    },
  },
});
