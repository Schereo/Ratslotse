/**
 * Erzeugt `lib/api-schema.ts` aus dem API-Vertrag `api/openapi.json`.
 *
 *   npm run api:typen            # generieren
 *   npm run api:typen -- --pruefen   # nur vergleichen (Exit 1 bei Abweichung)
 *
 * **Warum eine Prüf-Zeile am Dateiende.** Die generierten Typen veralten, wenn
 * sich das BACKEND ändert — nicht das Frontend. Der Frontend-Workflow läuft
 * aber nur bei Frontend-Änderungen, würde die Drift also gar nicht sehen.
 * Deshalb schreibt dieses Skript den SHA-256 des Vertrags als letzte Zeile in
 * die generierte Datei: Ein Python-Test (`tests/test_api_vertrag.py`) kann
 * damit prüfen, ob die Typen zum Schema passen, ganz ohne Node.
 */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const hier = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(hier, "..");
const VERTRAG = resolve(FRONTEND, "../../api/openapi.json");
const ZIEL = resolve(FRONTEND, "lib/api-schema.ts");
const MARKE = "// vertrag-sha256: ";

const pruefen = process.argv.includes("--pruefen");
const summe = createHash("sha256").update(readFileSync(VERTRAG)).digest("hex");

if (pruefen) {
  let inhalt;
  try {
    inhalt = readFileSync(ZIEL, "utf8");
  } catch {
    console.error(`FEHLT: lib/api-schema.ts — einmal \`npm run api:typen\` laufen lassen.`);
    process.exit(1);
  }
  const row = inhalt.trimEnd().split("\n").at(-1) ?? "";
  if (row !== MARKE + summe) {
    console.error(
      "VERALTET: lib/api-schema.ts passt nicht zu api/openapi.json.\n" +
      "  cd web/frontend && npm run api:typen   # neu erzeugen und mitcommitten",
    );
    process.exit(1);
  }
  console.log("lib/api-schema.ts ist aktuell.");
  process.exit(0);
}

execFileSync("npx", ["openapi-typescript", VERTRAG, "-o", ZIEL], {
  cwd: FRONTEND,
  stdio: "inherit",
});
const erzeugt = readFileSync(ZIEL, "utf8").trimEnd();
writeFileSync(ZIEL, `${erzeugt}\n\n${MARKE}${summe}\n`);
console.log(`lib/api-schema.ts geschrieben (Vertrag ${summe.slice(0, 12)}…).`);
