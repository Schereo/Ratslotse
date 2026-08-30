import { createRequire } from "node:module";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = join(scriptDirectory, "..", "..");
const requireFromWeb = createRequire(join(repositoryRoot, "web", "frontend", "package.json"));
const React = requireFromWeb("react");
const { renderToStaticMarkup } = requireFromWeb("react-dom/server");
const Lucide = requireFromWeb("lucide-react");

const icons = {
  ArrowLeft: "ArrowLeft",
  BarChart3: "BarChart3",
  Bell: "Bell",
  Bookmark: "Bookmark",
  CalendarDays: "CalendarDays",
  CircleHelp: "CircleHelp",
  FileSearch2: "FileSearch2",
  History: "History",
  House: "House",
  LogOut: "LogOut",
  Map: "Map",
  MessageSquarePlus: "MessageSquarePlus",
  MoreHorizontal: "MoreHorizontal",
  Scale: "Scale",
  Search: "Search",
  SlidersHorizontal: "SlidersHorizontal",
  Sparkles: "Sparkles",
  Tags: "Tags",
  Trophy: "Trophy",
  UserCircle: "UserCircle",
};

const assetCatalog = join(repositoryRoot, "ios", "Resources", "Assets.xcassets");

for (const [assetSuffix, componentName] of Object.entries(icons)) {
  const assetName = `Lucide${assetSuffix}`;
  const imageSet = join(assetCatalog, `${assetName}.imageset`);
  const icon = Lucide[componentName];
  if (!icon) throw new Error(`Lucide 0.451.0 does not export ${componentName}`);

  await rm(imageSet, { recursive: true, force: true });
  await mkdir(imageSet, { recursive: true });

  const svg = renderToStaticMarkup(
    React.createElement(icon, {
      color: "#000000",
      fill: "none",
      size: 24,
      strokeWidth: 2,
      "aria-hidden": undefined,
    }),
  );

  await writeFile(join(imageSet, `${assetName}.svg`), `${svg}\n`);
  await writeFile(
    join(imageSet, "Contents.json"),
    `${JSON.stringify({
      images: [{ filename: `${assetName}.svg`, idiom: "universal" }],
      info: { author: "xcode", version: 1 },
      properties: {
        "preserves-vector-representation": true,
        "template-rendering-intent": "template",
      },
    }, null, 2)}\n`,
  );
}
