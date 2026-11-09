/**
 * Pläne der Stadt (Schalter `plaene`, docs/plan-ziele-plaene.md).
 *
 * Das Register steht als Code im Backend — Übersicht und Detailseite stehen
 * deshalb auch gegen die LEERE Ratsdatenbank der CI: dann ohne Berichte,
 * mit dem Satz „Kein Umsetzungsbericht …“. Geprüft wird, was in beiden
 * Fällen gilt: der Reiter heißt „Pläne“, eine Zeile führt zur Detailseite,
 * der Themenfeld-Filter und die Maßnahmen-Suche greifen (beide leben vom
 * Register, nicht vom Bestand), und keine der beiden Seiten scrollt auf dem
 * Handy seitwärts. Ohne Schalter bleibt es bei der alten Ziel-Seite und die
 * Detailseite gibt es nicht.
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

const CLIMATE_PLAN = 'a[href="/council/plan?key=klimaschutzplan_2035"]';

test("der Reiter heißt „Pläne“ und führt zum Plan", async ({ page }) => {
  await schalter(page, true);
  await page.goto("/council?tab=analysis&sub=ziele");
  await expect(page.getByRole("button", { name: "Pläne", pressed: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Laufend" })).toBeVisible();
  // Über die Adresse und in der Gruppe: Der Plan steht auch im Kopf unter
  // „Als Nächstes laut Plan“, und sein Name auf der Zeile des Vorgängers.
  await page.locator(`#plans-running ${CLIMATE_PLAN}`).click();
  await expect(page).toHaveURL(/\/council\/plan\?key=klimaschutzplan_2035/);
  await expect(page.getByRole("heading", { level: 1, name: "Klimaschutzplan Oldenburg 2035" })).toBeVisible();
  await expect(page.getByText("Laufzeit", { exact: true })).toBeVisible();
  await expect(page.getByText("Seit dem Beschluss", { exact: true })).toBeVisible();
});

test("der Filter zeigt nur die Pläne eines Themenfelds", async ({ page }) => {
  await schalter(page, true);
  await page.goto("/council?tab=analysis&sub=ziele");
  const filter = page.getByRole("group", { name: "Nach Themenfeld filtern" });
  await expect(page.locator(`#plans-running ${CLIMATE_PLAN}`)).toBeVisible();
  await filter.getByRole("button", { name: /^Verkehr/ }).click();
  await expect(page.locator('#plans-running a[href="/council/plan?key=mobilitaetsplan_2030"]')).toBeVisible();
  await expect(page.locator(`#plans-running ${CLIMATE_PLAN}`)).toHaveCount(0);
  await filter.getByRole("button", { name: /^Alle/ }).click();
  await expect(page.locator(`#plans-running ${CLIMATE_PLAN}`)).toBeVisible();
});

test("der Stand steht in den Worten der Stadt, mit Herkunft und ohne Quote", async ({ page }) => {
  await schalter(page, true);
  await page.goto("/council/plan?key=klimaschutzplan_2035");
  // Die Statusdatei ist eingecheckt — der Stand steht auch gegen die leere Ratsdatenbank der CI.
  const status = page.locator('section[aria-labelledby="plan-city-status"]');
  await expect(status.getByText("Klimaportal der Stadt · Stand 2026")).toBeVisible();
  await expect(status.getByText("Zählbasis: 90 → 97 Maßnahmen")).toBeVisible();
  await expect(status.getByRole("row", { name: /Realisiert 11 15 20 22 20/ })).toBeVisible();
  await expect(status).not.toContainText("%");
  // Die Kennzahl steht neben dem Plan: Soll, Ist, Quelle — und der Vorbehalt des Berichts.
  const indicator = page.locator('section[aria-labelledby="plan-indicators"]');
  await expect(indicator.getByRole("row", { name: /2023 969\.000 .* 935\.792 −17,9 % 25\/0866/ })).toBeVisible();
  await expect(indicator.getByText(/Strommix/)).toBeVisible();
});

test("der Stand je Empfehlung kommt aus den Zellfarben der Evaluation", async ({ page }) => {
  await schalter(page, true);
  await page.goto("/council/plan?key=aktionsplan_gewalt_2020");
  const status = page.locator('section[aria-labelledby="plan-city-status"]');
  await expect(status.getByText("Nach Angaben der Verwaltung · Stand 08/2026")).toBeVisible();
  await expect(status.getByText(/Der Text zählt 90 Empfehlungen, die Tabelle im Anhang hat 91 Zeilen/)).toBeVisible();
  const measures = page.locator('section[aria-labelledby="plan-measures"]');
  await measures.getByRole("button", { name: /Übergreifende Handlungsempfehlungen/ }).click();
  await expect(measures.getByText("nicht umgesetzt, wird weiterhin gebraucht").first()).toBeVisible();
});

test("der Rückblick zeigt, was die Verwaltung meldet — und sagt, wenn er nichts findet", async ({ page }) => {
  await schalter(page, true);
  await page.goto("/council/plan?key=aktionsplan_gewalt_2020");
  const review = page.locator('section[aria-labelledby="plan-review"]');
  await expect(review.getByText("Grenzen, die der Bericht selbst nennt")).toBeVisible();
  await expect(review.getByText(/scheiterte an fehlenden finanziellen Mitteln/)).toBeVisible();
  await expect(review.getByRole("link", { name: /Aktionsplan/ })).toBeVisible();
  await page.goto("/council/plan?key=smv2025");
  await expect(page.locator('section[aria-labelledby="plan-review"]')
    .getByText("Eine Auswertung hat Ratslotse im Ratsinformationssystem nicht gefunden.")).toBeVisible();
  // Ein laufender Plan hat keinen Rückblick.
  await page.goto("/council/plan?key=klimaschutzplan_2035");
  await expect(page.locator("#plan-city-status")).toBeVisible();
  await expect(page.locator('section[aria-labelledby="plan-review"]')).toHaveCount(0);
});

test("die Maßnahmen lassen sich durchsuchen", async ({ page }) => {
  await schalter(page, true);
  await page.goto("/council/plan?key=klimaschutzplan_2035");
  const search = page.getByLabel("In den Maßnahmen suchen");
  await search.fill("radverkehr");
  await expect(page.getByText(/^\d+ von 90$/)).toBeVisible();
  // Über die Kennung: Den Titel „Raumerweiterung Fuß- und Radverkehr“ tragen zwei Maßnahmen.
  await expect(page.getByText("FußRad_01", { exact: true })).toBeVisible();
  await search.fill("gibtesnichtxyz");
  await expect(page.getByText(/Keine Maßnahme passt/)).toBeVisible();
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
      "/council/plan?key=klimaanpassungskonzept", "/council/plan?key=klimaschutzplan_2035"]) {
      await page.goto(pfad, { waitUntil: "networkidle" });
      expect(await ueberbreite(page), `${pfad} bei ${breite} px`).toBeLessThanOrEqual(1);
    }
  });
}
