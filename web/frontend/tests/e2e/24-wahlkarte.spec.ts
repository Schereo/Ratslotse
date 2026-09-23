import fs from "node:fs";
import path from "node:path";
import { test, expect, type Page } from "@playwright/test";
import { zustandsDatei } from "./konten";

// Die Ebene „Wahlergebnis" der Stadtkarte (docs/plan-viertel-wahlkarte.md):
// Stadt → Ortsbereich → Wahlbezirk. Alles gemockt — in der CI ist die
// Ratsdatenbank leer, und die Wahl-Antwort ist eine Abschrift.
//
// Abschrift neu erzeugen (cd web/backend):
//   FEATURE_FLAGS=wahlabend ../../.venv/bin/python -c "import json; from datetime import datetime, timezone; \
//     from app.election import district_map; \
//     k = district_map.build('ratswahl-2026', now=datetime(2026, 9, 23, 12, tzinfo=timezone.utc)); \
//     k['districts'] = [d for d in k['districts'] if any(p['name'] == 'Krusenbusch' for p in d['places'])]; \
//     print(json.dumps(k, ensure_ascii=False))" > ../frontend/tests/e2e/fixtures/wahlkarte-krusenbusch.json

test.use({ storageState: zustandsDatei("admin") });

const KARTE = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "wahlkarte-krusenbusch.json"), "utf8"));
const districts = [
  { place_id: "krusenbusch", name: "Krusenbusch", count: 4, last_date: "2026-05-21", stages: { planning: 4 } },
  { place_id: "fliegerhorst", name: "Fliegerhorst", count: 14, last_date: "2026-04-13", stages: { decided: 14 } },
];

async function stub(page: Page) {
  const wahlAbrufe: string[] = [];
  await page.route("**/api/app-config", (r) => r.fulfill({ json: { min_build: 0, features: ["mein-viertel", "wahlabend"] } }));
  await page.route("**/api/districts/projects", (r) => r.fulfill({ json: { districts, highlights: [], total: 18, stages: {}, updated_at: "2026-09-12" } }));
  await page.route("**/api/districts/*/projects", (r) => r.fulfill({ json: {
    place: { id: "krusenbusch", name: "Krusenbusch" }, projects: [], upcoming: [], investments: [], participations: [], closures: [], press: [], neighbours: [], updated_at: "2026-09-12",
  } }));
  await page.route("**/api/wahlabend/karte*", (r) => {
    const url = new URL(r.request().url());
    wahlAbrufe.push(url.search);
    const wahl = url.searchParams.get("wahl");
    const election = KARTE.elections.find((e: { slug: string }) => e.slug === wahl) ?? KARTE.election;
    return r.fulfill({ json: { ...KARTE, election } });
  });
  return wahlAbrufe;
}

test("Stadt: Bezirke in Siegerfarbe, Legende in der Tafel", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await stub(page);
  await page.goto("/karte?ebenen=wahlergebnis");
  const legende = page.locator("section[aria-labelledby=wahlkarte-stadt]");
  await expect(legende).toContainText("SPD");
  await expect(legende).toContainText("vorn in 48");
  await expect(legende).toContainText("Gleichstand");
  await expect(legende).toContainText("32 % der Stimmen kamen per Brief");
  // Die Bezirke, zu denen die Antwort Zahlen hat, liegen gefärbt in ihrer Ebene.
  await expect.poll(() => page.locator(".leaflet-wahlbezirke-pane path.leaflet-interactive").count()).toBeGreaterThan(80);
  await expect(page.getByRole("group", { name: "Welche Wahl" }).getByRole("button", { name: "Ratswahl" })).toHaveAttribute("aria-pressed", "true");
});

test("Ortsbereich → Bezirk: volle Aufteilung, teilbar über die Adresse", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const abrufe = await stub(page);
  await page.goto("/karte?ort=krusenbusch&ebenen=wahlergebnis");
  const liste = page.locator("section[aria-labelledby=wahlkarte-viertel]");
  await expect(liste).toContainText("3 Wahlbezirke in Krusenbusch");
  await expect(liste.locator("[data-bezirk]")).toHaveCount(3);
  await liste.locator('[data-bezirk="515"]').click();
  const tafel = page.getByTestId("wahl-bezirk-tafel");
  await expect(tafel).toContainText("Grundschule Krusenbusch");
  await expect(tafel.locator("tbody tr").first()).toContainText("AfD");
  await expect(page).toHaveURL(/bezirk=515/);
  // Umschalten auf die OB-Wahl fragt die andere Wahl ab und merkt sie sich.
  await page.getByRole("group", { name: "Welche Wahl" }).getByRole("button", { name: "OB-Wahl" }).click();
  await expect(page).toHaveURL(/wahl=ob-2026/);
  await expect.poll(() => abrufe.some((q) => q.includes("wahl=ob-2026"))).toBe(true);
  await expect(page).not.toHaveURL(/bezirk=/);
});

test("mobil: keine Seitwärts-Verschiebung mit Bezirks-Tafel", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await stub(page);
  await page.goto("/karte?ort=krusenbusch&ebenen=wahlergebnis&bezirk=515");
  await expect(page.getByTestId("wahl-bezirk-tafel")).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
});
