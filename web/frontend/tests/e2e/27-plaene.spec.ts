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
  await page.goto("/council/plan?key=kai_2015");
  await expect(page.locator('section[aria-labelledby="plan-review"]')
    .getByText("Eine Auswertung hat Ratslotse im Ratsinformationssystem nicht gefunden.")).toBeVisible();
  // Ein Stand je Maßnahme ohne eigene Vorlage ist ein Stand, keine Auswertung — die Seite sagt beides.
  await page.goto("/council/plan?key=smv2025");
  await expect(page.locator('section[aria-labelledby="plan-review"]')
    .getByText(/Eine eigene Vorlage zur Auswertung .* nicht gefunden/)).toBeVisible();
  await expect(page.locator("#plan-city-status")).toBeVisible();
  // Ein laufender Plan hat keinen Rückblick.
  await page.goto("/council/plan?key=klimaschutzplan_2035");
  await expect(page.locator("#plan-city-status")).toBeVisible();
  await expect(page.locator('section[aria-labelledby="plan-review"]')).toHaveCount(0);
});

test("die Übersicht sagt, wo man nachfragen kann — als Tatsache, nicht als Vorwurf", async ({ page }) => {
  await schalter(page, true);
  await page.goto("/council?tab=analysis&sub=ziele");
  const list = page.locator('section[aria-labelledby="plans-follow-ups"]');
  await expect(list.getByText("Das sagt etwas über die Berichte, nicht über die Arbeit.")).toBeVisible();
  await expect(list.getByText(/„Nicht gefunden“ heißt nicht „gibt es nicht“/)).toBeVisible();
  // Gegen die leere Ratsdatenbank der CI hat kein Plan einen Bericht — die Liste ist dort lang, hier kürzer.
  const ask = list.getByRole("link", { name: "Den Rat fragen" }).first();
  await expect(ask).toHaveAttribute("href", /^\/fragen\?q=Was(\+|%20)ist/);
});

test("wo ein Modell den Stand herausgesucht hat, steht das wörtliche Zitat dabei", async ({ page }) => {
  await schalter(page, true);
  await page.goto("/council/plan?key=mobilitaetsplan_2030");
  const measures = page.locator('section[aria-labelledby="plan-measures"]');
  await expect(measures.getByText(/Ein Sprachmodell hat die Stellen im Bericht herausgesucht/)).toBeVisible();
  await measures.getByRole("button", { name: "Alle aufklappen" }).click();
  await expect(measures.getByText("„Die Bewohnerparkzone Haarenesch wurde zum 1. Januar 2026 umgesetzt.“")).toBeVisible();
  // Die Stadt zählt hier nichts aus — also auch keine Verteilung.
  await expect(page.locator('section[aria-labelledby="plan-city-status"]')).toHaveCount(0);
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

test("was der Plan festlegt, steht unter dem Kopf — jeder Satz mit Zitat und Dokument", async ({ page }) => {
  // Die Kernpunkte stehen als Dateien im Repo (council/plan_key_points/), also auch gegen die leere Datenbank.
  await schalter(page, true);
  await page.goto("/council/plan?key=schulverpflegung");
  const block = page.locator('section[aria-labelledby="plan-content"]');
  await expect(block.getByText("Was der Plan festlegt", { exact: true })).toBeVisible();
  const points = block.locator("li");
  expect(await points.count()).toBeGreaterThanOrEqual(3);
  // Der Bio-Anteil wurde nach 2019 mehrfach geändert: Der Punkt trägt das Datum des jüngsten Beschlusses.
  await expect(block.getByText("Stand 01.12.2025", { exact: true })).toBeVisible();
  // Ein Tipp klappt das wörtliche Zitat auf; der Link führt ins Dokument, bei einer Anlage auf die Seite.
  // Ein Punkt aus der Anlage („…, S. 5“): Sein Link hängt nicht am Bestand — gegen die leere Datenbank
  // der CI kennt das Backend weder die Vorlage noch den Beschluss, die Dokument-Nummer steht in der Datei.
  const fromPlan = points.filter({ hasText: /, S\. \d+/ }).first();
  await expect(fromPlan.locator("blockquote")).toBeHidden();
  await fromPlan.getByRole("button").click();
  await expect(fromPlan.locator("blockquote")).toBeVisible();
  await expect(fromPlan.locator('a[href^="https://buergerinfo.oldenburg.de/getfile.php"][href*="#page="]')).toBeVisible();
  // Der Block steht VOR den Berichten.
  const order = await page.evaluate(() => {
    const content = document.getElementById("plan-content"), log = document.getElementById("plan-reports");
    return content && log ? Boolean(content.compareDocumentPosition(log) & Node.DOCUMENT_POSITION_FOLLOWING) : null;
  });
  expect(order).not.toBe(false);
  // Ohne Plantext kein Block und kein Platzhalter (2015 beschlossen, vor dem Bestand).
  await page.goto("/council/plan?key=kai_2015");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator('section[aria-labelledby="plan-content"]')).toHaveCount(0);
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
      "/council/plan?key=klimaanpassungskonzept", "/council/plan?key=klimaschutzplan_2035",
      "/council/plan?key=schulverpflegung"]) {
      await page.goto(pfad, { waitUntil: "networkidle" });
      expect(await ueberbreite(page), `${pfad} bei ${breite} px`).toBeLessThanOrEqual(1);
    }
  });
}
