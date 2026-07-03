import type { MetadataRoute } from "next";

const BASE = "https://ratslotse.de";

// Currently only the public marketing/legal pages are indexable. When the council
// pages (Beschlüsse/Themen) go public, list them here (incl. dynamic decision/entity
// URLs from the API) so they get crawled.
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: `${BASE}/`, changeFrequency: "monthly", priority: 1 },
    { url: `${BASE}/docs`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${BASE}/impressum`, changeFrequency: "yearly", priority: 0.3 },
    { url: `${BASE}/datenschutz`, changeFrequency: "yearly", priority: 0.3 },
  ];
}
