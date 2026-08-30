// Build the static Next export for the remaining Capacitor Android app.
//
// Two things the plain `next build` can't do for a static export live here:
//  1. Route Handlers (app/api/**/route.ts) can't be statically exported — the
//     SSE proxy is web-only, so we move app/api aside for the build and restore
//     it afterwards. In the app, council-qa.tsx calls the backend directly.
//  2. A Content-Security-Policy must sit in <head> to take effect, and the app
//     talks cross-origin to the backend + tile hosts — so we inject an app CSP
//     into every exported .html once the build is done.
import { rename } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, statSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const API_DIR = "app/api";
const API_STASH = "app/_api.disabled";
// /g (geteilte Antworten, Task 31) rendert server-seitig (force-dynamic für
// die Link-Vorschau-Metadata) und kann nicht statisch exportiert werden. Die
// App braucht die Route nicht: geteilte Links öffnen immer im Browser.
const SHARE_DIR = "app/g";
const SHARE_STASH = "app/_g.disabled";

// Must match the backend origin the app talks to (lib/platform.ts apiBase()).
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "https://ratslotse.de";

const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  // API_BASE auch für Bilder: Die Planzeichnungen (P1) sind das erste <img>
  // mit Backend-URL — 'self' ist in der App https://localhost, ohne die
  // API-Origin blockt die WebView den Bild-Load.
  `img-src 'self' data: blob: ${API_BASE} https://*.basemaps.cartocdn.com https://*.openfreemap.org`,
  "font-src 'self'",
  `connect-src 'self' ${API_BASE} https://*.openfreemap.org https://*.basemaps.cartocdn.com`,
  "worker-src 'self' blob:",
].join("; ");

function injectCsp(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) { injectCsp(p); continue; }
    if (!name.endsWith(".html")) continue;
    let html = readFileSync(p, "utf8");
    if (html.includes('http-equiv="Content-Security-Policy"')) continue;
    const meta = `<meta http-equiv="Content-Security-Policy" content="${CSP}">`;
    html = html.replace(/<head(\s[^>]*)?>/, (m) => m + meta);
    writeFileSync(p, html);
  }
}

const hasApi = existsSync(API_DIR);
if (hasApi) await rename(API_DIR, API_STASH);
const hasShare = existsSync(SHARE_DIR);
if (hasShare) await rename(SHARE_DIR, SHARE_STASH);
let status = 1;
try {
  status = spawnSync("next", ["build"], {
    stdio: "inherit",
    env: { ...process.env, MOBILE: "1" },
  }).status ?? 1;
} finally {
  if (hasApi && existsSync(API_STASH)) await rename(API_STASH, API_DIR);
  if (hasShare && existsSync(SHARE_STASH)) await rename(SHARE_STASH, SHARE_DIR);
}

if (status === 0 && existsSync("out")) {
  injectCsp("out");
  console.log("✓ static export in ./out (CSP injected). Next: npm run cap:sync");
}
process.exit(status);
