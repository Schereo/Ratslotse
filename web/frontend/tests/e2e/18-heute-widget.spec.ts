import { expect, test, type Page } from "@playwright/test";
import { zustandsDatei } from "./konten";

test.use({ storageState: zustandsDatei("nutzerin") });

const hit = {
  id: 8699, topic_id: 1, topic_name: "Kitas und Kindertagespflege in Oldenburg",
  title: "Verwendung von Investitionsmitteln für die Kindertagesstätten und Kindertagespflege – Bericht",
  summary: "Der Bericht über die Verwendung von Investitionsmitteln für Kitas und Kindertagespflege wird zur Kenntnis genommen.",
  committee: "Jugendhilfeausschuss", session_date: "2026-06-17", outcome: "noted", is_new: true,
};
const full = { hits: [hit], topic_count: 3, total: 24, unread_total: 2, unread_decisions: 1 };
const widget = (page: Page) => page.getByRole("region", { name: "Neu zu deinen Themen" });

async function stub(page: Page, data: typeof full) {
  await page.route("**/api/topics/latest-hits?*", route => route.fulfill({ json: data }));
}

test("öffnet den richtigen Beschluss und markiert ihn themenübergreifend", async ({ page }) => {
  await stub(page, full);
  let marked = false;
  await page.route("**/api/topics/decisions/8699/seen", route => {
    marked = route.request().method() === "POST";
    return route.fulfill({ json: { marked: 2 } });
  });
  await page.goto("/dashboard");
  await expect(widget(page)).toContainText("1 ungelesen");
  await expect(widget(page)).toContainText(`Zu deinem Thema ${hit.topic_name}`);
  const link = widget(page).getByRole("link", { name: /Zu deinem Thema/ });
  await expect(link).toHaveAttribute("href", "/council/decision?id=8699");
  await link.click();
  await expect(page).toHaveURL(/\/council\/decision\?id=8699/);
  await expect.poll(() => marked).toBe(true);
});

test("gelesener Treffer verschwindet erst nach Bestätigung, Fokus bleibt im Widget", async ({ page }) => {
  let seen = false;
  await page.route("**/api/topics/latest-hits?*", route => route.fulfill({ json: seen
    ? { ...full, hits: [], unread_total: 0, unread_decisions: 0 } : full }));
  await page.route("**/api/topics/decisions/8699/seen", route => {
    seen = true;
    return route.fulfill({ json: { marked: 2 } });
  });
  await page.goto("/dashboard");
  await widget(page).getByRole("button", { name: /^Als gelesen markieren:/ }).click();
  await expect(widget(page)).toContainText("Alles gelesen");
  await expect(widget(page).getByRole("link", { name: /Zu deinem Thema/ })).toHaveCount(0);
  await expect(widget(page).getByRole("heading", { name: "Neu zu deinen Themen" })).toBeFocused();
  await expect(widget(page).getByRole("link", { name: "Meine Themen" })).toHaveAttribute("href", "/topics");
});

test("Fehler beim Markieren behält den Treffer und erlaubt einen neuen Versuch", async ({ page }) => {
  await stub(page, full);
  await page.route("**/api/topics/decisions/8699/seen", route => route.fulfill({ status: 503, json: { detail: "Offline" } }));
  await page.goto("/dashboard");
  await widget(page).getByRole("button", { name: /^Als gelesen markieren:/ }).click();
  await expect(widget(page).getByRole("alert")).toContainText("nicht gespeichert");
  await expect(widget(page)).toContainText("1 ungelesen");
  await expect(widget(page).getByRole("button", { name: /^Als gelesen markieren:/ })).toBeEnabled();
  await expect(widget(page)).not.toContainText("Alles gelesen");
});

test("Ladefehler wird nicht als leer ausgegeben und lässt sich im Widget beheben", async ({ page }) => {
  await page.route("**/api/topics/latest-hits?*", route => route.fulfill({ status: 503, json: { detail: "Offline" } }));
  await page.goto("/dashboard");
  await expect(widget(page).getByRole("alert")).toContainText("nicht geladen");
  await expect(widget(page)).not.toContainText("Alles gelesen");
  await expect(widget(page)).not.toContainText("Erstes Thema anlegen");
  await stub(page, full);
  await widget(page).getByRole("button", { name: "Erneut versuchen" }).click();
  await expect(widget(page)).toContainText("1 ungelesen");
  await expect(widget(page).getByRole("alert")).toHaveCount(0);
});

test("erfolgreich gelesen bleibt gelesen, wenn das Nachladen ausfällt", async ({ page }) => {
  let seen = false;
  await page.route("**/api/topics/latest-hits?*", route => route.fulfill(seen
    ? { status: 503, json: { detail: "Offline" } } : { json: full }));
  await page.route("**/api/topics/decisions/8699/seen", route => {
    seen = true;
    return route.fulfill({ json: { marked: 2 } });
  });
  await page.goto("/dashboard");
  await widget(page).getByRole("button", { name: /^Als gelesen markieren:/ }).click();
  await expect(widget(page)).toContainText("Alles gelesen");
  await expect(widget(page).getByRole("alert")).toContainText("nicht aktualisiert");
  await expect(widget(page).getByRole("link", { name: /Zu deinem Thema/ })).toHaveCount(0);
});

for (const [name, topic_count, total, text] of [
  ["ohne Themen", 0, 0, "Erstes Thema anlegen"],
  ["ohne Treffer", 3, 0, "Noch keine passenden Beschlüsse"],
  ["alles gelesen", 3, 24, "Alles gelesen"],
] as const) {
  test(`ehrlicher Zustand ${name}`, async ({ page }) => {
    await stub(page, { ...full, hits: [], topic_count, total, unread_total: 0, unread_decisions: 0 });
    await page.goto("/dashboard");
    await expect(widget(page)).toContainText(text);
    await expect(widget(page).getByRole("link", { name: /Zu deinem Thema/ })).toHaveCount(0);
  });
}

for (const width of [320, 390]) {
  test(`große Schrift bei ${width}px: lesbare Metadaten und erreichbare Aktionen`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await stub(page, full);
    await page.goto("/dashboard");
    await expect(widget(page)).toContainText("1 ungelesen");
    await page.addStyleTag({ content: "html { font-size: 200% !important; }" });
    const bounds = await widget(page).evaluate(el => {
      const r = el.getBoundingClientRect();
      return { right: r.right, width: window.innerWidth,
        overflow: Array.from(el.querySelectorAll("h2,p,button")).filter(child => child.scrollWidth > child.clientWidth + 1).map(child => child.textContent) };
    });
    expect(bounds.right).toBeLessThanOrEqual(bounds.width);
    expect(bounds.overflow).toEqual([]);
    const mark = widget(page).getByRole("button", { name: /^Als gelesen markieren:/ });
    await expect(mark).toBeVisible();
    expect((await mark.boundingBox())!.height).toBeGreaterThanOrEqual(44);
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
