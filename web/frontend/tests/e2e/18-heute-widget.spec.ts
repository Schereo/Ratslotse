import { test, expect, type Page } from "@playwright/test";
import { zustandsDatei } from "./konten";

test.use({ storageState: zustandsDatei("admin") });
const first = { since: "2026-05-11T10:00:00Z", until: "2026-09-11T10:00:00Z", first_visit: false };
const item = { id: "protocol:4675", kind: "protocol" as const, ksinr: 4675,
  arrived: "2026-09-05T07:16:38", committee: "Ausschuss für Wirtschaftsförderung, Digitalisierung und internationale Zusammenarbeit",
  session_date: "2026-06-01", decision_count: 12 };
const groups = Array.from({ length: 17 }, (_, i) => ({ kind: "protocol" as const,
  committee: i === 0 ? item.committee : `Gremium ${i}`, count: i === 16 ? 49 : 50,
  first_session_date: "2026-01-01", last_session_date: item.session_date,
  latest: { ...item, committee: i === 0 ? item.committee : `Gremium ${i}` },
}));
const full = { ...first, total: 849, counts: { protocol: 849 }, groups, items: [item] };
const widget = (page: Page) => page.locator('[data-heute-widget="seit-besuch"]');
async function stub(page: Page, data = full) {
  await page.route("**/api/today/visit", route => route.fulfill({ json: first }));
  await page.route("**/api/today/updates**", route => {
    const params = new URL(route.request().url()).searchParams;
    if (params.has("committee")) {
      const offset = Number(params.get("offset") || 0);
      expect(params.get("since")).toBe(first.since);
      expect(params.get("until")).toBe(first.until);
      expect(params.get("kind")).toBe("protocol");
      expect(params.get("committee")).toBe(item.committee);
      return route.fulfill({ json: { ...data, total: 6, groups: [groups[0]],
        items: Array.from({ length: 3 }, (_, i) => ({ ...item, id: `protocol:${4675 + offset + i}`, ksinr: 4675 + offset + i })),
      } });
    }
    return route.fulfill({ json: data });
  });
}
async function openGroup(page: Page) {
  await widget(page).getByRole("button", { name: /849 Protokolle/ }).click();
  await widget(page).getByRole("button", { name: /Wirtschaft.*50 Protokolle/ }).click();
  await expect(widget(page).getByRole("link")).toHaveCount(3);
}

test("vier Monate bleiben gebündelt; Gremien und Sitzungen öffnen sich schrittweise", async ({ page }) => {
  await stub(page);
  await page.goto("/dashboard");
  await expect(widget(page)).toContainText("17 Gremien");
  await expect(widget(page).getByRole("link")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Neu zu deinen Themen" })).toHaveCount(0);
  await widget(page).getByRole("button", { name: /849 Protokolle/ }).click();
  await expect(widget(page).getByRole("button", { name: /50 Protokolle/ })).toHaveCount(4);
  await widget(page).getByRole("button", { name: "Weitere Gremien (13)" }).click();
  await expect(widget(page).getByRole("button", { name: /50 Protokolle/ })).toHaveCount(8);
  await widget(page).getByRole("button", { name: /Wirtschaft.*50 Protokolle/ }).click();
  const link = widget(page).getByRole("link").first();
  await expect(link).toHaveAttribute("href", "/council/sitzung?ksinr=4675");
  await link.click();
  await expect(page).toHaveURL(/sitzung\?ksinr=4675/);
});

test("Nachladen bleibt im Gremium und Besuchszeitraum; Fokus folgt erster neuer Sitzung", async ({ page }) => {
  await stub(page);
  await page.goto("/dashboard");
  await openGroup(page);
  await widget(page).getByRole("button", { name: "Weitere Sitzungen (3)" }).click();
  await expect(widget(page).getByRole("link")).toHaveCount(6);
  await expect(widget(page).getByRole("link").nth(3)).toBeFocused();
  await expect(widget(page).getByRole("button", { name: /Weitere Sitzungen/ })).toHaveCount(0);
});

test("Ladefehler erhält Sitzungen und erlaubt Wiederholen", async ({ page }) => {
  await stub(page);
  await page.goto("/dashboard");
  await openGroup(page);
  await page.route("**/api/today/updates**", route => route.fulfill({ status: 503, json: { detail: "Offline" } }));
  await widget(page).getByRole("button", { name: /Weitere Sitzungen/ }).click();
  await expect(widget(page).getByRole("alert")).toContainText("nicht aktualisiert");
  await expect(widget(page).getByRole("link")).toHaveCount(3);
  await stub(page);
  await widget(page).getByRole("button", { name: "Erneut versuchen" }).click();
  await expect(widget(page).getByRole("link")).toHaveCount(6);
});

test("einzelne Sitzung braucht keine zusätzliche Gremium-Ebene", async ({ page }) => {
  await stub(page, { ...full, total: 1, counts: { protocol: 1 }, groups: [{ ...groups[0], count: 1 }] });
  await page.goto("/dashboard");
  await widget(page).getByRole("button", { name: /1 Protokolle/ }).click();
  await expect(widget(page).getByRole("link")).toHaveCount(1);
  await expect(widget(page).getByRole("link")).toHaveAttribute("href", "/council/sitzung?ksinr=4675");
});

test("erster Besuch und leerer Zeitraum werden ehrlich benannt", async ({ page }) => {
  await stub(page, { ...full, first_visit: true, total: 0, counts: { protocol: 0 }, groups: [], items: [] });
  await page.goto("/dashboard");
  await expect(widget(page).getByRole("heading")).toHaveText("Neu bei Ratslotse");
  await expect(widget(page)).toContainText("die letzten sieben Tage");
  await expect(widget(page)).toContainText("Keine neuen relevanten Ratsunterlagen");
  await expect(widget(page).getByRole("button")).toHaveCount(0);
});

for (const width of [320, 390]) {
  test(`große Schrift bei ${width}px und reduzierte Bewegung`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await stub(page);
    await page.goto("/dashboard");
    await openGroup(page);
    await page.addStyleTag({ content: "html { font-size: 200% !important; }" });
    const result = await widget(page).evaluate(el => ({
      overflow: Array.from(el.querySelectorAll("p,button,h2")).filter(c => c.scrollWidth > c.clientWidth + 1).map(c => c.textContent),
      transitions: Array.from(el.querySelectorAll("button[aria-expanded] svg")).map(c => getComputedStyle(c).transitionDuration),
    }));
    expect(result.overflow).toEqual([]);
    expect(result.transitions.every(t => parseFloat(t) <= 0.00001)).toBe(true);
    expect((await widget(page).getByRole("button", { name: /Weitere Sitzungen/ }).boundingBox())!.height).toBeGreaterThanOrEqual(44);
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
