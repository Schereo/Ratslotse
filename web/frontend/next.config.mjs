import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/** @type {import('next').NextConfig} */
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
// Next's dev server (HMR/React Refresh) needs 'unsafe-eval'; a production build
// does not — so only allow it in development to keep the prod CSP tight.
const isDev = process.env.NODE_ENV !== "production";

// FINGERABDRUCK DER BÜNDEL IN public/lotti UND public/geo (lib/asset-paths.ts).
//
// Dateien aus public/ liefert Next mit `max-age=0` aus, jeder Besuch fragt sie
// also neu nach. Die Lotti-Dateien gehören aber zusammen (Verzeichnis und
// Blätter), eine Lebensdauer allein ließe ein neues lotti.json auf ein altes
// Blatt treffen. Deshalb steckt der Inhalt in der Adresse: Über alle Dateien
// des Ordners (Pfad + Inhalt) entsteht ein Abdruck, und nur unter
// /lotti/v/<abdruck>/… gibt es ein Jahr Lebensdauer. 29 MB, gemessen 40–80 ms
// je Start. Fehlt der Ordner, bleibt es bei den alten Adressen.
const PUBLIC_DIR = fileURLToPath(new URL("./public/", import.meta.url));

function contentFingerprint(folder) {
  const root = path.join(PUBLIC_DIR, folder);
  const hash = createHash("sha256");
  const walk = (dir) => {
    const entries = readdirSync(dir, { withFileTypes: true })
      .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.isFile()) {
        hash.update(path.relative(root, full));
        hash.update("\0");
        hash.update(readFileSync(full));
        hash.update("\0");
      }
    }
  };
  try {
    walk(root);
  } catch {
    return "";
  }
  return hash.digest("hex").slice(0, 12);
}

const LOTTI_VERSION = contentFingerprint("lotti");
const GEO_VERSION = contentFingerprint("geo");

// Nur der AKTUELLE Abdruck wird umgeleitet und darf lange liegen. Eine alte
// Adresse (ein Tab von vor dem Deploy) bekommt ein 404 statt der neuen Dateien
// unter altem Namen — und dieses 404 bekommt keine Lebensdauer, falls der alte
// Stand nach einem Revert mit demselben Abdruck zurückkommt.
const versionedBundles = [
  ["lotti", LOTTI_VERSION],
  ["geo", GEO_VERSION],
].filter(([, version]) => version);

// Proxy API calls to the FastAPI backend so the web frontend always talks to a
// same-origin /api (no CORS, cookies work). In production Caddy may handle /api
// directly; this rewrite is the fallback / dev convenience.
async function rewrites() {
  // Der API-Proxy steht in `fallback`, nicht in der Array-Kurzform. Die
  // Kurzform entspricht `afterFiles` — und afterFiles-Rewrites greifen VOR
  // dynamischen Routen. Ein Route-Handler mit Parameter, etwa
  // app/api/council/deep-research/[jobId]/events, käme damit nie zum Zug: Der
  // Proxy fängt die Anfrage vorher ab. Genau das ist passiert und hat den
  // Event-Stream der Gründlichen Recherche gepuffert (die Fortschrittskarte
  // blieb beim ersten Schritt stehen). `fallback` läuft nach den dynamischen
  // Routen: Wer einen eigenen Handler hat, bekommt ihn; alles andere geht wie
  // bisher direkt ans Backend.
  const api = [
    {
      source: "/api/:path*",
      destination: `${BACKEND_URL}/api/:path*`,
    },
    // OAuth-Metadaten für den MCP-Server (web/backend/app/routers/mcp_oauth.py).
    // Ihr Ort ist von RFC 9728/8414 vorgeschrieben, außerhalb von /api — der
    // Edge-Proxy reicht aber nur /api ans Backend, also leitet Next sie durch.
    {
      source: "/.well-known/oauth-protected-resource/:path*",
      destination: `${BACKEND_URL}/.well-known/oauth-protected-resource/:path*`,
    },
    {
      source: "/.well-known/oauth-authorization-server",
      destination: `${BACKEND_URL}/.well-known/oauth-authorization-server`,
    },
  ];
  const dateien = [
    // Apple fetches the AASA (Universal Links) at the extensionless URL but
    // requires Content-Type application/json. The file keeps a .json extension
    // on disk so Next's static serving sets the right type; this maps the
    // extensionless URL onto it — no webserver config needed.
    {
      source: "/.well-known/apple-app-site-association",
      destination: "/.well-known/apple-app-site-association.json",
    },
    // Die Technik-Doku (Astro-Starlight-Build) liegt als statische Site in
    // public/docs/ (kopiert der Deploy dorthin). Rewrites hier sind
    // "afterFiles": echte Dateien (/docs/_astro/…) gewinnen, nur
    // Verzeichnis-URLs werden auf ihre index.html gemappt — /docs braucht
    // damit keinen eigenen Webserver auf der Edge.
    { source: "/docs", destination: "/docs/index.html" },
    { source: "/docs/:path*", destination: "/docs/:path*/index.html" },
    // Versionierte Bündel-Adressen auf die echten Dateien (s. versionedBundles).
    ...versionedBundles.map(([folder, version]) => ({
      source: `/${folder}/v/${version}/:path*`,
      destination: `/${folder}/:path*`,
    })),
  ];
  return { afterFiles: dateien, fallback: api };
}

// Die alte /technik-Seite ist durch die Technik-Doku unter /docs ersetzt —
// alte Bookmarks/Suchtreffer landen per Permanent-Redirect am neuen Ort.
async function redirects() {
  return [
    { source: "/technik", destination: "/docs", permanent: true },
    // Die Etappe „Mitreden" war bis 21.08.2026 auf drei Seiten verteilt; sie
    // beantworten eine Frage und stehen jetzt als Abschnitte auf einer.
    { source: "/haushalt/jahr", destination: "/haushalt/mitreden#termine", permanent: true },
    { source: "/haushalt/streit", destination: "/haushalt/mitreden#streit", permanent: true },
    // `/haushalt/labor → mitreden#labor` stand hier vom 21. bis 24.08.2026 —
    // seit #707 ist das Labor wieder eine eigene Seite, und dieser Redirect
    // hätte jeden Aufruf zurückgeworfen (aufgefallen erst im Labor-2.0-Bau:
    // #707 hat ihn übersehen). Er war `permanent`, Browser dürfen ein 308
    // cachen — wer die Seite in den drei Tagen besucht hat, landet ggf.
    // weiter auf Mitreden, bis der Browser-Cache fällt. Auf dev verschmerzbar;
    // ein Gegen-Redirect ließe sich nicht sauber formulieren.
    // „Die Prüfung" und „Die dreizehn Zahlen" (21.08.2026): geprüft und
    // zusammengefasst stehen als Abschnitte auf einer Seite.
    { source: "/haushalt/kennzahlen", destination: "/haushalt/pruefung#kennzahlen", permanent: true },
    // Plan und Ist der Investitionen (21.08.2026).
    { source: "/haushalt/gebaut", destination: "/haushalt/investitionen#gebaut", permanent: true },
    // Teilhaushalte und Produkte sind derselbe Baum (21.08.2026).
    { source: "/haushalt/bereiche", destination: "/haushalt/produkte#bereiche", permanent: true },
    // Die ganze Stadt: Summe, Gesellschaften, Pläne, Gebühren (21.08.2026).
    { source: "/haushalt/beteiligungen", destination: "/haushalt/konzern#gesellschaften", permanent: true },
    { source: "/haushalt/betriebe", destination: "/haushalt/konzern#betriebe", permanent: true },
    { source: "/haushalt/gebuehren", destination: "/haushalt/konzern#gebuehren", permanent: true },
  ];
}

// Basis-Security-Header für alle Antworten.
const BASE_HEADERS = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // `geolocation=(self)`: Die Stadtkarte fragt den Standort („Meinen Standort
  // nehmen"), und zwar nur die eigene Seite. Bis 09/2026 stand hier `()` —
  // der Browser fragte gar nicht erst, der Knopf meldete nur „nicht
  // verfügbar" (Tims Befund 07.09.2026, auf dev gemessen). Kamera und
  // Mikrofon bleiben zu.
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(self)" },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
];

// CSP als Funktion: die Doku-Suche (Pagefind) braucht WebAssembly, der Rest
// der Site nicht. Zwei matchende CSP-Header würden sich zur strengsten
// Schnittmenge kombinieren — deshalb unten zwei sich ausschließende Muster.
function csp({ wasm = false } = {}) {
  return [
    "default-src 'self'",
    // appleid.cdn-apple.com: „Sign in with Apple JS" für den Web-Login-Popup.
    `script-src 'self' 'unsafe-inline' https://appleid.cdn-apple.com${wasm ? " 'wasm-unsafe-eval'" : ""}${isDev ? " 'unsafe-eval'" : ""}`,
    "worker-src 'self' blob:",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https://*.basemaps.cartocdn.com https://*.openfreemap.org https://upload.wikimedia.org",
    "font-src 'self'",
    "connect-src 'self' https://*.openfreemap.org https://appleid.apple.com",
    "frame-ancestors 'none'",
  ].join("; ");
}

async function headers() {
  return [
    {
      // Alle Seiten AUSSER /docs …
      source: "/((?!docs).*)",
      headers: [...BASE_HEADERS, { key: "Content-Security-Policy", value: csp() }],
    },
    {
      // … die Doku separat, mit WASM-Erlaubnis für die Pagefind-Suche.
      source: "/docs/:path*",
      headers: [...BASE_HEADERS, { key: "Content-Security-Policy", value: csp({ wasm: true }) }],
    },
    {
      source: "/docs",
      headers: [...BASE_HEADERS, { key: "Content-Security-Policy", value: csp({ wasm: true }) }],
    },
    // Versionierte Bündel: Der Inhalt steckt in der Adresse, also darf der
    // Browser sie behalten, ohne nachzufragen. Nicht im Dev-Server — dort
    // ändert `lotti_uebernehmen.py` Dateien, ohne dass sich der Abdruck des
    // laufenden Servers mitändert.
    ...(isDev
      ? []
      : versionedBundles.map(([folder, version]) => ({
          source: `/${folder}/v/${version}/:path*`,
          headers: [{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }],
        }))),
  ];
}

// DER DEV-SERVER BAUT IN EIN EIGENES VERZEICHNIS.
//
// `next dev` und `next build` teilten sich bis 08/2026 `.next`. Ein Build
// neben einem laufenden Dev-Server überschreibt dessen Chunks: Die Seite
// liefert danach für JEDE Chunk-URL eine 404-HTML-Seite, die Konsole meldet
// „Refused to execute script … MIME type ('text/html')", und die App bleibt
// bei „wird geladen …" stehen. Das sieht aus wie ein Fehler im Code und ist
// keiner — ein Reload hilft nicht, nur ein Neustart des Dev-Servers.
//
// Passiert ist es an einem Tag zweimal, und zwar aus dem naheliegendsten
// Grund: Vor einem Merge prüft man mit `npm run build`, während nebenan noch
// der Server läuft, an dem man gerade gearbeitet hat.
//
// Die Konfiguration als FUNKTION zu exportieren, löst das ohne Disziplin:
// Next reicht die Phase herein, und der Dev-Server bekommt `.next-dev`.
// `next build` und `next start` bleiben bei `.next` — Deploy, Dockerfile und
// der rsync-Ausschluss in deploy.yml sind unberührt.
const DEV_PHASE = "phase-development-server";

const nextConfig = {
  reactStrictMode: true,
  // Don't advertise the framework in the X-Powered-By header.
  poweredByHeader: false,
  // No image optimizer: `/_next/image` answers 404. Next 14 runs it through
  // `sharp`, and the copy it found (0.32.6, pulled in only by
  // `@capacitor/assets`) carried the libvips/libheif flaws behind two
  // unauthenticated RCE advisories (GHSA-2464-fhr4-w9xw, GHSA-2xp9-vwfh-vxw4;
  // fixed only from sharp 0.35.5 / Next 15.5.28). `@capacitor/assets` is gone
  // since 11/2026, but the optimizer stays off: we use `next/image` for a
  // handful of our own small PNG icons, which lose nothing by being served
  // as they are.
  images: { unoptimized: true },
  // Die Abdrücke der Bündel für lib/asset-paths.ts (zur Bauzeit einkompiliert,
  // passend zu den Dateien, die derselbe Build ausliefert).
  env: { LOTTI_BUNDLE_VERSION: LOTTI_VERSION, GEO_BUNDLE_VERSION: GEO_VERSION },
  rewrites,
  redirects,
  headers,
};

export default (phase) => ({
  ...nextConfig,
  ...(phase === DEV_PHASE ? { distDir: ".next-dev" } : {}),
});
