import { test, expect, type Page } from "@playwright/test";
import { zustandsDatei } from "./konten";

test.use({ storageState: zustandsDatei("admin") });
const districts = [
  { place_id: "buemmerstede", name: "Bümmerstede", count: 1, last_date: "2025-09-15", stages: { planning: 1 } },
  { place_id: "fliegerhorst", name: "Fliegerhorst", count: 14, last_date: "2026-04-13", stages: { decided: 14 } },
  { place_id: "krusenbusch", name: "Krusenbusch", count: 4, last_date: "2026-05-21", stages: { planning: 4 } },
];
const titles = ["Fußgängerbrücke zwischen Krusenbusch und Bümmerstede", "Bebauungsplan Fliegerhorst/Hallensichel-Ost", "Wohnquartier am Krusenbusch"];
const widget = (page: Page) => page.locator('[data-heute-widget="mein-viertel"]');
async function stub(page: Page, options: { upcoming?: boolean; failed?: boolean; selected?: boolean } = {}) {
  const requests: string[] = [];
  await page.route("**/api/app-config", route => route.fulfill({ json: { min_build: 0, features: ["mein-viertel"] } }));
  await page.route("**/api/topics", route => route.fulfill({ json: options.selected === false ? [] : districts.map((d, id) => ({ id, name: d.name, description: "Mein Viertel" })) }));
  await page.route("**/api/districts/projects", route => route.fulfill({ json: { districts, highlights: [], total: 19, stages: {}, updated_at: "2026-09-12" } }));
  await page.route("**/api/districts/*/projects", route => {
    const id = new URL(route.request().url()).pathname.split("/").at(-2)!;
    requests.push(id);
    if (id === "fliegerhorst" && options.failed) return route.fulfill({ status: 503, json: { detail: "Offline" } });
    const i = districts.findIndex(d => d.place_id === id);
    const date = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
    return route.fulfill({ json: { place: {}, projects: [{ id: 140 + i, place_id: id, name: titles[i], what: "Hier wird ein Vorhaben vorbereitet. Der letzte belegte Stand stammt aus den Ratsunterlagen.", stage: "planning", last_date: districts[i].last_date, first_date: "2025-01-01", hidden: false }],
      upcoming: options.upcoming && id === "krusenbusch" ? [{ id: 1, ksinr: 42, session_date: date, item_number: "Ö 5", session_time: "17:00", title: "Neue Kita am Quartier", committee: "Jugendhilfeausschuss" }] : [],
      investments: [], participations: [], closures: [], press: [], neighbours: [], updated_at: "2026-09-12" } });
  });
  return requests;
}

test("zeigt konkrete Vorhaben mit Einheiten, Ratsdatum und direktem Projektziel", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await stub(page);
  await page.goto("/dashboard");
  await expect(widget(page).getByRole("article")).toHaveCount(3);
  await expect(widget(page)).toContainText("14 Vorhaben");
  await expect(widget(page)).toContainText("Zuletzt im Rat: 15.09.2025");
  await expect(widget(page).getByRole("link", { name: /Wohnquartier am Krusenbusch/ })).toHaveAttribute("href", "/karte?ort=krusenbusch&v=142");
  await expect(widget(page)).not.toContainText("Neu seit");
  // Client-Navigation behält den Query-Cache. Der Rückweg darf auch vor dem
  // ersten useHeute-Effekt nicht mit einem ungültigen Datum abbrechen.
  await page.getByRole("link", { name: "Sitzungen", exact: true }).click();
  await expect(page).toHaveURL(/\/council\?tab=sessions/);
  await page.getByRole("link", { name: "Heute", exact: true }).click();
  await expect(widget(page).getByText(titles[2], { exact: true })).toBeVisible();
});

test("mobil lädt erst sichtbare Viertel; weitere bleiben mit großer Schrift erreichbar", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  const requests = await stub(page);
  await page.goto("/dashboard");
  await expect(widget(page).getByText("Wohnquartier am Krusenbusch", { exact: true })).toBeVisible();
  expect(requests).not.toContain("buemmerstede");
  await widget(page).getByRole("button", { name: "1 weiteres Viertel anzeigen" }).click();
  await expect(widget(page).getByText(titles[0], { exact: true })).toBeVisible();
  await page.addStyleTag({ content: "html { font-size: 200% !important; }" });
  await expect.poll(() => widget(page).evaluate(el => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(1);
  await widget(page).getByRole("button", { name: "Weniger Viertel" }).click();
  await expect(widget(page).getByRole("button", { name: "1 weiteres Viertel anzeigen" })).toBeFocused();
});

test("eine nächste Beratung führt zur richtigen Tagesordnung", async ({ page }) => {
  await stub(page, { upcoming: true });
  await page.goto("/dashboard");
  const link = widget(page).getByRole("link", { name: /Neue Kita am Quartier/ });
  await expect(link).toContainText("im Rat");
  await expect(link).toHaveAttribute("href", "/council?tab=sessions&ksinr=42&top=%C3%96%205");
});

test("Ladefehler in einem Viertel lässt die anderen sichtbar und kann wiederholt werden", async ({ page }) => {
  const options = { failed: true };
  await stub(page, options);
  await page.goto("/dashboard");
  await expect(widget(page).getByRole("alert")).toContainText("nicht geladen");
  await expect(widget(page).getByText("Wohnquartier am Krusenbusch", { exact: true })).toBeVisible();
  options.failed = false;
  await widget(page).getByRole("button", { name: "Erneut versuchen" }).click();
  await expect(widget(page).getByText(titles[1], { exact: true })).toBeVisible();
});

test("ohne gewähltes Viertel lädt die Karte keine fremden Viertel", async ({ page }) => {
  const requests = await stub(page, { selected: false });
  await page.goto("/dashboard");
  await expect(widget(page).getByRole("link", { name: "Viertel auswählen" })).toHaveAttribute("href", "/karte");
  expect(requests).toEqual([]);
});
