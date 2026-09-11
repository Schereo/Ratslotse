import { test, expect, type Page } from "@playwright/test";
import { zustandsDatei } from "./konten";

test.use({ storageState: zustandsDatei("admin") });
const first = { since: "2026-09-01T10:00:00+00:00", until: "2026-09-11T10:00:00+00:00", first_visit: false };
const item = { id: "protocol:4675", kind: "protocol" as const, ksinr: 4675,
  arrived: "2026-09-05T07:16:38", committee: "Ausschuss für Wirtschaftsförderung, Digitalisierung und internationale Zusammenarbeit",
  session_date: "2026-06-01", decision_count: 12 };
const full = { ...first, total: 4, counts: { protocol: 2, agenda: 1, agenda_change: 1 }, items: [item] };
const widget = (page: Page) => page.locator('[data-heute-widget="seit-besuch"]');
async function stub(page: Page, data = full) {
  await page.route("**/api/today/visit", route => route.fulfill({ json: first }));
  await page.route("**/api/today/updates?*", route => route.fulfill({ json: data }));
}

test("zeigt allgemeine Ergänzungen und öffnet die richtige Sitzung", async ({ page }) => {
  await stub(page);
  await page.goto("/dashboard");
  await expect(widget(page)).toContainText("4");
  await expect(widget(page)).toContainText("Protokolle ergänzt");
  await expect(widget(page)).toContainText("Tagesordnung geändert");
  await expect(page.getByRole("heading", { name: "Neu zu deinen Themen" })).toHaveCount(0);
  const link = widget(page).getByRole("link");
  await expect(link).toHaveAttribute("href", "/council/sitzung?ksinr=4675");
  await link.click();
  await expect(page).toHaveURL(/sitzung\?ksinr=4675/);
});

test("weitere Einträge behalten ihren Zeitraum und erhalten den Fokus", async ({ page }) => {
  await stub(page);
  await page.route("**/api/today/updates?*", route => {
    const p = new URL(route.request().url()).searchParams;
    if (p.get("offset") === "1") {
      expect(p.get("since")).toBe(first.since);
      expect(p.get("until")).toBe(first.until);
      return route.fulfill({ json: { ...full, items: [{ ...item, id: "agenda:4633", ksinr: 4633, kind: "agenda", committee: "Sozialausschuss" }] } });
    }
    return route.fulfill({ json: full });
  });
  await page.goto("/dashboard");
  await widget(page).getByRole("button", { name: "Weitere Neuigkeiten (3)" }).click();
  await expect(widget(page).getByRole("link", { name: /Sozialausschuss/ })).toBeFocused();
  await expect(widget(page).getByRole("link")).toHaveCount(2);
});

test("Fehler erhält den bisherigen Rückblick und Wiederholen funktioniert", async ({ page }) => {
  await stub(page);
  await page.goto("/dashboard");
  await expect(widget(page).getByRole("link")).toHaveCount(1);
  await page.route("**/api/today/updates?*", route => route.fulfill({ status: 503, json: { detail: "Offline" } }));
  await widget(page).getByRole("button", { name: /Weitere Neuigkeiten/ }).click();
  await expect(widget(page).getByRole("alert")).toContainText("nicht aktualisiert");
  await expect(widget(page).getByRole("link")).toHaveCount(1);
  await stub(page, { ...full, items: [{ ...item, id: "protocol:2", committee: "Jugendhilfeausschuss" }] });
  await widget(page).getByRole("button", { name: "Erneut versuchen" }).click();
  await expect(widget(page)).toContainText("Jugendhilfe");
});

test("erster Besuch und leerer Zeitraum werden ehrlich benannt", async ({ page }) => {
  await stub(page, { ...full, first_visit: true, total: 0, counts: { protocol: 0, agenda: 0, agenda_change: 0 }, items: [] });
  await page.goto("/dashboard");
  await expect(widget(page).getByRole("heading")).toHaveText("Neu bei Ratslotse");
  await expect(widget(page)).toContainText("die letzten sieben Tage");
  await expect(widget(page)).toContainText("Keine neuen Ratsunterlagen");
  await expect(widget(page).getByRole("button", { name: /Weitere/ })).toHaveCount(0);
});

for (const width of [320, 390]) {
  test(`große Schrift bei ${width}px und reduzierte Bewegung`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await stub(page);
    await page.goto("/dashboard");
    await expect(widget(page).getByRole("link")).toHaveCount(1);
    await page.addStyleTag({ content: "html { font-size: 200% !important; }" });
    const result = await widget(page).evaluate(el => ({
      overflow: Array.from(el.querySelectorAll("p,button,h2")).filter(c => c.scrollWidth > c.clientWidth + 1).map(c => c.textContent),
      animation: getComputedStyle(el.querySelector("li")!).animationName,
    }));
    expect(result.overflow).toEqual([]);
    expect(result.animation).toBe("none");
    expect((await widget(page).getByRole("button", { name: /Weitere/ }).boundingBox())!.height).toBeGreaterThanOrEqual(44);
  });
}

for (const width of [1280, 1600]) {
  test(`Wochenkarte passt mit langen Titeln in die Widget-Spalte bei ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await stub(page, full);
    await page.route("**/api/council/week-preview", route => route.fulfill({ json: {
      found: true, from_date: "2026-09-11", to_date: "2026-09-18",
      sessions: [{ ksinr: 4618, committee: "Wirtschaft & Digitales", session_date: "2026-09-14", session_time: "17:00", n_items: 6 }],
      items: [{ ksinr: 4618, item_number: "Ö 6", committee: "Wirtschaft & Digitales", session_date: "2026-09-14",
        title: "Vermarktung eines städtischen Investorengrundstücks zur Bebauung mit einer Quartiersgarage im Bereich des Bebauungsplanes S-835 (MediTech Oldenburg (MTO))",
        summary: null, template_number: null, kvonr: null }],
    } }));
    await page.goto("/dashboard");
    const week = page.locator('[data-tour="woche-im-rat"]');
    await expect(week).toBeVisible();
    await expect.poll(() => week.evaluate(el => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(1);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  });
}
