import type { MetadataRoute } from "next";
import { themaKeys, vergleichsSlugs } from "@/lib/kommunalwahl";

const BASE = "https://ratslotse.de";

// Currently only the public marketing/legal pages are indexable. When the council
// pages (Beschlüsse/Themen) go public, list them here (incl. dynamic decision/entity
// URLs from the API) so they get crawled.
export default function sitemap(): MetadataRoute.Sitemap {
  // Der Wahlprogramm-Vergleich ist statisch — alle Routen sind zur Bauzeit
  // aufzählbar (12 Themenfelder + 9 Listen + 3 feste Seiten). Er steht aber
  // hinterm Umgebungs-Gate (nur dev.ratslotse.de): Im Prod-Build sind die
  // Seiten 404 und gehören nicht in die Sitemap.
  const kommunalwahlFrei = process.env.NEXT_PUBLIC_RATSLOTSE_ENV === "dev";
  const kommunalwahl: MetadataRoute.Sitemap = !kommunalwahlFrei ? [] : [
    { url: `${BASE}/kommunalwahl`, changeFrequency: "weekly", priority: 0.9 },
    { url: `${BASE}/kommunalwahl/naehe`, changeFrequency: "weekly", priority: 0.7 },
    { url: `${BASE}/kommunalwahl/check`, changeFrequency: "weekly", priority: 0.7 },
    { url: `${BASE}/kommunalwahl/methodik`, changeFrequency: "monthly", priority: 0.5 },
    ...themaKeys().map((t) => ({
      url: `${BASE}/kommunalwahl/thema/${t}`,
      changeFrequency: "weekly" as const,
      priority: 0.7,
    })),
    ...vergleichsSlugs().map((s) => ({
      url: `${BASE}/kommunalwahl/liste/${s}`,
      changeFrequency: "weekly" as const,
      priority: 0.7,
    })),
  ];

  return [
    { url: `${BASE}/`, changeFrequency: "monthly", priority: 1 },
    { url: `${BASE}/docs`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${BASE}/hilfe`, changeFrequency: "monthly", priority: 0.5 },
    { url: `${BASE}/impressum`, changeFrequency: "yearly", priority: 0.3 },
    { url: `${BASE}/datenschutz`, changeFrequency: "yearly", priority: 0.3 },
    ...kommunalwahl,
  ];
}
