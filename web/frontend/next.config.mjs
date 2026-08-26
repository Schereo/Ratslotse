/** @type {import('next').NextConfig} */
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
// Next's dev server (HMR/React Refresh) needs 'unsafe-eval'; a production build
// does not — so only allow it in development to keep the prod CSP tight.
const isDev = process.env.NODE_ENV !== "production";
// The native-app build (`MOBILE=1 next build`) is a static export bundled into
// the Capacitor shell. Static export has no server, so it can't run rewrites()
// or headers(): the app talks to the backend at an absolute origin (see
// lib/platform.ts) and its CSP/security headers come from the app shell instead.
const MOBILE = process.env.MOBILE === "1";

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
    //
    // ACHTUNG, DAS GILT NUR IM WEB-BUILD. Der Capacitor-Export (`output:
    // "export"`) kennt `redirects` nicht — für die App zählt allein, dass
    // KEIN interner Link mehr auf die alten Pfade zeigt. Beim Umbau geprüft.
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
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
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
  ...(MOBILE
    ? {
        // Static HTML export for Capacitor: written to ./out, bundled as the app.
        output: "export",
        // Each route exports as <route>/index.html — friendliest for the
        // Capacitor local file server.
        trailingSlash: true,
        // The static export can't run the Next image optimizer.
        images: { unoptimized: true },
      }
    : { rewrites, redirects, headers }),
};

export default (phase) => ({
  ...nextConfig,
  ...(phase === DEV_PHASE ? { distDir: ".next-dev" } : {}),
});
