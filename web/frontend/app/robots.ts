import type { MetadataRoute } from "next";

// The marketing/legal pages are indexable; the logged-in app areas (and the API)
// are not. Council pages are gated for now — add/remove from `disallow` when they
// go public.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api/", "/admin", "/account", "/dashboard", "/topics", "/nwz", "/link", "/council"],
    },
    sitemap: "https://ratslotse.de/sitemap.xml",
    host: "https://ratslotse.de",
  };
}
