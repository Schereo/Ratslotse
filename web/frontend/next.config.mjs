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
  return [
    {
      source: "/api/:path*",
      destination: `${BACKEND_URL}/api/:path*`,
    },
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
}

// Die alte /technik-Seite ist durch die Technik-Doku unter /docs ersetzt —
// alte Bookmarks/Suchtreffer landen per Permanent-Redirect am neuen Ort.
async function redirects() {
  return [{ source: "/technik", destination: "/docs", permanent: true }];
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
    `script-src 'self' 'unsafe-inline'${wasm ? " 'wasm-unsafe-eval'" : ""}${isDev ? " 'unsafe-eval'" : ""}`,
    "worker-src 'self' blob:",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https://*.basemaps.cartocdn.com https://*.openfreemap.org",
    "font-src 'self'",
    "connect-src 'self' https://*.openfreemap.org",
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

export default nextConfig;
