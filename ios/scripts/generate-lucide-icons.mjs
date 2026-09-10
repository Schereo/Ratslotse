/**
 * Die Lucide-Assets der App aus `lucide-react` erzeugen — und prüfen.
 *
 * Web und App sollen dieselbe Bildsprache tragen; deshalb liegen die Vektoren
 * nicht abgetippt, sondern gerendert im Asset-Katalog. Welche gebraucht
 * werden, sagt das Register `RatsIconography.swift` — eine zweite Liste hier
 * wäre eine, die man vergisst.
 *
 *   node ios/scripts/generate-lucide-icons.mjs            # fehlende schreiben
 *   node ios/scripts/generate-lucide-icons.mjs --pruefen  # nur melden
 *
 * Warum es die Prüfung gibt: `LucideBellDot` stand bis 09/2026 ohne seinen
 * Glockenkörper im Katalog — abgetippt und dabei ein Pfad verloren. Die Datei
 * war da, der Test „Asset vorhanden" grün, und auf dem Knopf „Vorgang folgen"
 * schwebte ein Punkt über einem Strich. Verglichen werden deshalb die
 * gezeichneten FORMEN, nicht der Dateitext: Attributreihenfolge und
 * Zeilenenden unterscheiden sich zwischen den von Hand angelegten Dateien und
 * dem Renderer, ohne dass ein Pixel anders aussieht.
 */
import { createRequire } from "node:module";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = join(scriptDirectory, "..", "..");
const requireFromWeb = createRequire(join(repositoryRoot, "web", "frontend", "package.json"));
const React = requireFromWeb("react");
const { renderToStaticMarkup } = requireFromWeb("react-dom/server");
const Lucide = requireFromWeb("lucide-react");

const pruefen = process.argv.includes("--pruefen");
const assetCatalog = join(repositoryRoot, "ios", "Resources", "Assets.xcassets");
const register = join(
  repositoryRoot, "ios", "Packages", "RatslotseDesign", "Sources", "RatslotseDesign",
  "RatsIconography.swift",
);

/** Alle `"LucideXyz"` aus dem Register — die Liste, die die App wirklich zieht. */
const assetNames = [...new Set(
  [...(await readFile(register, "utf8")).matchAll(/"(Lucide\w+)"/g)].map((m) => m[1]),
)].sort();

/** Nur die gezeichneten Formen, unabhängig von Attributreihenfolge und Schreibweise. */
function shapes(svg) {
  return [...svg.matchAll(/<(path|circle|rect|line|polyline|polygon|ellipse)\b([^>]*?)\/?>/g)]
    .map(([, tag, attrs]) => {
      const pairs = [...attrs.matchAll(/([\w-]+)="([^"]*)"/g)]
        .map(([, key, value]) => `${key}=${value.replace(/\s+/g, " ").trim()}`)
        .sort();
      return `${tag} ${pairs.join(" ")}`;
    })
    .join(" ; ");
}

const render = (icon) => renderToStaticMarkup(React.createElement(icon, {
  color: "#000000", fill: "none", size: 24, strokeWidth: 2, "aria-hidden": undefined,
}));

const contents = (assetName) => `${JSON.stringify({
  images: [{ filename: `${assetName}.svg`, idiom: "universal" }],
  info: { author: "xcode", version: 1 },
  properties: {
    "preserves-vector-representation": true,
    "template-rendering-intent": "template",
  },
}, null, 2)}\n`;

const befunde = [];
let geschrieben = 0;

for (const assetName of assetNames) {
  const componentName = assetName.slice("Lucide".length);
  const icon = Lucide[componentName];
  if (!icon) {
    befunde.push(`${assetName}: Lucide 0.451.0 kennt kein ${componentName}`);
    continue;
  }

  const imageSet = join(assetCatalog, `${assetName}.imageset`);
  const svgPath = join(imageSet, `${assetName}.svg`);
  const soll = render(icon);
  let ist = null;
  try { ist = await readFile(svgPath, "utf8"); } catch { /* fehlt */ }

  if (ist !== null && shapes(ist) === shapes(soll)) continue;

  if (pruefen) {
    befunde.push(ist === null
      ? `${assetName}: Asset fehlt`
      : `${assetName}: gezeichnete Formen weichen ab\n    ist:  ${shapes(ist)}\n    soll: ${shapes(soll)}`);
    continue;
  }

  await mkdir(imageSet, { recursive: true });
  await writeFile(svgPath, `${soll}\n`);
  await writeFile(join(imageSet, "Contents.json"), contents(assetName));
  geschrieben += 1;
}

if (befunde.length) {
  console.error(`${befunde.length} von ${assetNames.length} Assets stimmen nicht mit Lucide überein:`);
  for (const b of befunde) console.error(`  ${b}`);
  console.error("\n  node ios/scripts/generate-lucide-icons.mjs   # schreibt sie neu");
  process.exit(1);
}

console.log(pruefen
  ? `${assetNames.length} Lucide-Assets stimmen mit lucide-react überein.`
  : `${assetNames.length} Lucide-Assets geprüft, ${geschrieben} geschrieben.`);
