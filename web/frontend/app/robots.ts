import type { MetadataRoute } from "next";

// The marketing/legal pages are indexable; the logged-in app areas (and the API)
// are not. Council pages are gated for now — add/remove from `disallow` when they
// go public.
//
// dev.ratslotse.de and feature.ratslotse.de (both built with
// NEXT_PUBLIC_RATSLOTSE_ENV=dev) must never be indexed: since 10/2026 dev is
// reachable without Basic-Auth, and a crawled copy would compete with
// ratslotse.de. Caddy additionally sends `X-Robots-Tag: noindex` there.
export default function robots(): MetadataRoute.Robots {
  if (process.env.NEXT_PUBLIC_RATSLOTSE_ENV === "dev") {
    return { rules: { userAgent: "*", disallow: "/" } };
  }
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api/", "/admin", "/account", "/dashboard", "/topics", "/council"],
    },
    sitemap: "https://ratslotse.de/sitemap.xml",
    host: "https://ratslotse.de",
  };
}
