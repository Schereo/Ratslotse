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
export default defineConfig({
  test: {
    include: ["lib/**/*.test.ts"],
    environment: "node",
    // Deutsche Formatierung und Zeitzone sind Teil dessen, was geprüft wird —
    // ein Test, der auf dem Notebook in Europe/Berlin läuft und in der CI
    // unter UTC, prüft zweierlei. Node liest beides beim Start.
    env: { TZ: "Europe/Berlin", LANG: "de_DE.UTF-8" },
  },
  resolve: {
    alias: { "@": fileURLToPath(new URL(".", import.meta.url)) },
  },
});
