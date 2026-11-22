#!/usr/bin/env node
/**
 * Die Browsertest-Dateien auf die Läufer der CI verteilen — nach DAUER.
 *
 *     node tests/shard-specs.mjs 3 8        # die Dateien von Teil 3 von 8
 *     node tests/shard-specs.mjs --plan 8   # die ganze Verteilung ansehen
 *
 * **Warum nicht `playwright test --shard=i/n`.** Das schneidet nach Test-
 * ANZAHL, in Dateireihenfolge. Die Tests sind aber sehr ungleich teuer
 * (gemessen 22.11.2026: 2,1 s je Test in `16-tippspiel`, 7,0 s in
 * `27-plaene`), und so liefen die vier Teile 6,3 / 7,5 / 8,5 / 9,8 Minuten.
 * Die Wartezeit eines Pull Requests ist der LANGSAMSTE Teil — die anderen
 * drei standen also minutenlang fertig herum.
 *
 * **Wie verteilt wird.** Die schwerste Datei zuerst, jeweils in den Teil, der
 * bisher am wenigsten trägt. Die Dauern stehen in `e2e-durations.json`
 * (Sekunden je Datei, aus einem grünen CI-Lauf; neu ziehen mit
 * `python scripts/e2e_durations.py --write`).
 *
 * **Die Dauern entscheiden nur über die BALANCE, nie über die Abdeckung.**
 * Verteilt wird, was auf der Platte liegt: Eine neue Spec-Datei ohne Eintrag
 * bekommt das mittlere Gewicht und läuft trotzdem — in genau einem Teil. Ein
 * Eintrag für eine gelöschte Datei wird ignoriert. Veraltete Zahlen machen
 * die Teile also ungleicher, lassen aber nie einen Test aus
 * (`tests/test_ci_shards.py` hält das fest).
 *
 * Eine DATEI bleibt die kleinste Einheit, wie bei `--shard` ohne
 * `fullyParallel`: Die Reihenfolge innerhalb einer Datei bleibt erhalten.
 */
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SPEC_DIR = join(HERE, "e2e");
const DURATIONS_FILE = join(HERE, "e2e-durations.json");

/** Verteilt `files` auf `total` Teile. Rein: dieselbe Eingabe, dieselbe Verteilung. */
export function planShards(files, durations, total) {
  const known = files.map((f) => durations[f]).filter((v) => typeof v === "number" && v > 0).sort((a, b) => a - b);
  const fallback = known.length ? known[Math.floor(known.length / 2)] : 1;
  const weighted = files
    .map((file) => ({ file, weight: durations[file] > 0 ? durations[file] : fallback }))
    // Bei gleichem Gewicht nach Name — sonst hinge die Verteilung an der
    // Reihenfolge, in der das Dateisystem die Dateien nennt.
    .sort((a, b) => b.weight - a.weight || a.file.localeCompare(b.file));
  const shards = Array.from({ length: total }, () => ({ files: [], weight: 0 }));
  for (const { file, weight } of weighted) {
    let lightest = shards[0];
    for (const shard of shards) if (shard.weight < lightest.weight) lightest = shard;
    lightest.files.push(file);
    lightest.weight += weight;
  }
  for (const shard of shards) shard.files.sort();
  return shards;
}

function specFiles() {
  return readdirSync(SPEC_DIR).filter((f) => f.endsWith(".spec.ts")).sort();
}

function readDurations() {
  try {
    return JSON.parse(readFileSync(DURATIONS_FILE, "utf8")).seconds ?? {};
  } catch {
    // Ohne Datei sind alle Dateien gleich schwer — schlechter verteilt, aber vollständig.
    return {};
  }
}

function fail(message) {
  console.error(message);
  process.exit(1);
}

function positiveInt(raw, what) {
  const n = Number(raw);
  if (!Number.isInteger(n) || n < 1) fail(`${what} muss eine ganze Zahl ab 1 sein, nicht „${raw}“.`);
  return n;
}

function main(args) {
if (args[0] === "--plan") {
  const total = positiveInt(args[1], "Die Zahl der Teile");
  const shards = planShards(specFiles(), readDurations(), total);
  if (args[2] === "--json") {
    console.log(JSON.stringify(shards.map((s) => s.files)));
  } else {
    shards.forEach((shard, i) => {
      console.log(`Teil ${i + 1}/${total}: ${(shard.weight / 60).toFixed(1)} min, ${shard.files.length} Dateien`);
      for (const file of shard.files) console.log(`    ${file}`);
    });
  }
} else {
  const total = positiveInt(args[1], "Die Zahl der Teile");
  const index = positiveInt(args[0], "Der Teil");
  if (index > total) fail(`Teil ${index} gibt es bei ${total} Teilen nicht.`);
  const { files } = planShards(specFiles(), readDurations(), total)[index - 1];
  // Ein leerer Teil darf nie still durchgehen: `playwright test` OHNE Dateien
  // führe die ganze Suite — auf jedem leeren Läufer noch einmal.
  if (files.length === 0) fail(`Teil ${index}/${total} ist leer — es gibt weniger Spec-Dateien als Teile.`);
  console.log(files.map((f) => `tests/e2e/${f}`).join(" "));
}
}

// Nur als Programm, nicht beim Import: `tests/test_ci_shards.py` holt sich
// `planShards` allein, um die Verteilung mit eigenen Eingaben zu prüfen.
if (process.argv[1] === fileURLToPath(import.meta.url)) main(process.argv.slice(2));
