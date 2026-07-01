// Build the static Next export for the Capacitor apps.
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

const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://*.basemaps.cartocdn.com https://*.openfreemap.org",
  "font-src 'self'",
  "connect-src 'self' https://ratslotse.de https://*.openfreemap.org https://*.basemaps.cartocdn.com",
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
let status = 1;
try {
  status = spawnSync("next", ["build"], {
    stdio: "inherit",
    env: { ...process.env, MOBILE: "1" },
  }).status ?? 1;
} finally {
  if (hasApi && existsSync(API_STASH)) await rename(API_STASH, API_DIR);
}

if (status === 0 && existsSync("out")) {
  injectCsp("out");
  console.log("✓ static export in ./out (CSP injected). Next: npm run cap:sync");
}
process.exit(status);
