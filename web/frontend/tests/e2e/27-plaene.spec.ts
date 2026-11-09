/**
 * Pläne der Stadt (Schalter `plaene`, docs/plan-ziele-plaene.md).
 *
 * Das Register steht als Code im Backend — Übersicht und Detailseite stehen
 * deshalb auch gegen die LEERE Ratsdatenbank der CI: dann ohne Berichte,
 * mit dem Satz „Kein Umsetzungsbericht …“. Geprüft wird, was in beiden
 * Fällen gilt: der Reiter heißt „Pläne“, eine Karte führt zur Detailseite,
 * und keine der beiden scrollt auf dem Handy seitwärts. Ohne Schalter bleibt
 * es bei der alten Ziel-Seite und die Detailseite gibt es nicht.
 */
import { expect, test, type Page } from "@playwright/test";
import { zustandsDatei } from "./konten";

test.use({ storageState: zustandsDatei("nutzerin") });

async function schalter(page: Page, an: boolean) {
  await page.route("**/api/app-config", async (route) => {
    const echt = await (await route.fetch()).json();
    const ohne = (echt.features ?? []).filter((f: string) => f !== "plaene");
    await route.fulfill({ json: { ...echt, features: an ? [...ohne, "plaene"] : ohne } });
  });
}

async function ueberbreite(page: Page): Promise<number> {
  return page.evaluate(() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth));
}

test("der Reiter heißt „Pläne“ und führt zum Plan", async ({ page }) => {
  await schalter(page, true);
  await page.goto("/council?tab=analysis&sub=ziele");
  await expect(page.getByRole("button", { name: "Pläne", pressed: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Laufend" })).toBeVisible();
  // Über die Adresse, nicht den Namen: „abgelöst durch Klimaschutzplan …“
  // steht auch auf der Karte des Vorgängers.
  await page.locator('a[href="/council/plan?key=klimaschutzplan_2035"]').click();
  await expect(page).toHaveURL(/\/council\/plan\?key=klimaschutzplan_2035/);
  await expect(page.getByRole("heading", { level: 1, name: "Klimaschutzplan Oldenburg 2035" })).toBeVisible();
  await expect(page.getByText("Laufzeit", { exact: true })).toBeVisible();
});

test("ohne Schalter bleibt es bei den Zielen", async ({ page }) => {
  await schalter(page, false);
  await page.goto("/council?tab=analysis&sub=ziele");
  await expect(page.getByRole("button", { name: "Ziele", pressed: true })).toBeVisible();
  await page.goto("/council/plan?key=klimaschutzplan_2035");
  await expect(page.getByRole("heading", { level: 1, name: "Klimaschutzplan Oldenburg 2035" })).toHaveCount(0);
});

for (const breite of [390, 320]) {
  test(`keine Seite scrollt seitwärts (${breite} px)`, async ({ page }) => {
    await page.setViewportSize({ width: breite, height: 800 });
    await schalter(page, true);
    for (const pfad of ["/council?tab=analysis&sub=ziele", "/council/plan?key=aktionsplan_gewalt_2020",
      "/council/plan?key=klimaanpassungskonzept"]) {
      await page.goto(pfad, { waitUntil: "networkidle" });
      expect(await ueberbreite(page), `${pfad} bei ${breite} px`).toBeLessThanOrEqual(1);
    }
  });
}
