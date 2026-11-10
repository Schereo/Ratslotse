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
  // Die Reihe aller Stände liegt unter einem Aufklapper — das Bild darüber zeigt den gewählten Stand.
  await status.getByRole("button", { name: "Alle Stände als Tabelle" }).click();
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

test("die Kernpunkte stehen nach Art, die Zahl als Kachel mit Zitat", async ({ page }) => {
  await schalter(page, true);
  await page.goto("/council/plan?key=thg_neutrale_verwaltung");
  const block = page.locator('section[aria-labelledby="plan-content"]');
  // Ziele oben, dann Zahlen, dann Regeln — die Überschriften kommen aus dem Backend.
  await expect(block.locator("h3")).toHaveText(["Ziel", "Zahlen", "Regeln", "Termin"]);
  // Die Kachel trägt die Zahl groß; ein Tipp zeigt darunter den ganzen Satz mit dem wörtlichen Zitat.
  const tile = block.getByRole("button", { name: /62,5 %/ });
  await expect(tile).toHaveAttribute("aria-expanded", "false");
  await tile.click();
  await expect(tile).toHaveAttribute("aria-expanded", "true");
  await expect(block.locator("blockquote")).toContainText("62,5 Prozent bis 2030");
  await expect(block.getByText("Bis 2030 sollen die Emissionen gegenüber 2023 um 62,5 Prozent sinken.")).toBeVisible();
});

test("ein Termin aus dem Plan steht im Zeitband und führt zu seinem Kernpunkt", async ({ page }) => {
  await schalter(page, true);
  await page.goto("/council/plan?key=thg_neutrale_verwaltung");
  await expect(page.getByText("Termin laut Plan", { exact: true })).toBeVisible();
  const due = page.getByRole("button", { name: /^Termin laut Plan, bis 2030/ });
  await expect(due).toBeVisible();
  // Der Tipp führt zur Kachel, die den Termin nennt. Der Wimpel ist klein — geklickt wird die Tippfläche.
  await due.click({ force: true });
  await expect(page.locator("#plan-point-1")).toBeInViewport();
});

test("die Sprungleiste nennt die Abschnitte des Plans und springt dorthin", async ({ page }) => {
  await schalter(page, true);
  await page.goto("/council/plan?key=klimaschutzplan_2035");
  const bar = page.getByRole("navigation", { name: "Abschnitte dieser Seite" });
  // Aus Dateien im Repo, also auch gegen die leere Datenbank; „Beschlüsse“ hängt am Bestand.
  for (const name of [/^Inhalt/, /^Berichte/, /^Stand/, /^Kennzahl/, /^Maßnahmen/]) {
    await expect(bar.getByRole("button", { name })).toBeVisible();
  }
  await expect(page.locator('section[aria-labelledby="plan-measures"]')).not.toBeInViewport();
  await bar.getByRole("button", { name: /^Maßnahmen/ }).click();
  await expect(page.locator("#plan-measures")).toBeInViewport();
  await expect(bar.getByRole("button", { name: /^Maßnahmen/ })).toHaveAttribute("aria-current", "true");
  // Die Leiste bleibt beim Rollen oben stehen.
  await expect(bar).toBeInViewport();
});

test("der Stand lässt sich je Jahr wählen, die Tabelle liegt unter einem Aufklapper", async ({ page }) => {
  await schalter(page, true);
  await page.goto("/council/plan?key=klimaschutzplan_2035");
  const block = page.locator('section[aria-labelledby="plan-city-status"]');
  await expect(block.getByText(/Stand 2026$/)).toBeVisible();
  await expect(block.getByRole("table")).toBeHidden();
  await block.getByRole("button", { name: "2022", exact: true }).click();
  await expect(block.getByText(/Stand 2022$/)).toBeVisible();
  await expect(block.getByText("Der erste Stand, den die Stadt meldet.")).toBeVisible();
  // Was die Bewegung zeigt — und was nicht (die Stadt meldet nur Summen).
  await expect(block.getByText(/nicht, welche Maßnahme die Stufe gewechselt hat/)).toBeVisible();
  await block.getByRole("button", { name: "Alle Stände als Tabelle" }).click();
  await expect(block.getByRole("table")).toBeVisible();
});

test("die Übersicht klappt eine Zeile auf und kennt drei Reihenfolgen", async ({ page }) => {
  await schalter(page, true);
  await page.goto("/council?tab=analysis&sub=ziele");
  const row = page.locator("#plans-running li", { has: page.locator(CLIMATE_PLAN) }).first();
  // Ein Tipp auf die Zeile zeigt, worum es geht; der Titel bleibt der Weg zum Plan.
  await row.getByRole("button", { name: /Kurzfassung zeigen$/ }).click({ position: { x: 8, y: 8 } });
  await expect(row.getByText("Was der Plan festlegt", { exact: true })).toBeVisible();
  await expect(row.getByRole("link", { name: /^Zum Plan/ })).toBeVisible();
  await expect(page).toHaveURL(/tab=analysis/);
  // „Endet bald“: eine Liste statt der Gruppen, das nächste Ende zuerst — aus dem Register, ohne Bestand.
  const views = page.getByRole("group", { name: "Reihenfolge der Pläne" });
  await views.getByRole("button", { name: "Endet bald" }).click();
  await expect(page.getByRole("heading", { name: "Endet bald" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Laufend" })).toHaveCount(0);
  const first = page.locator("#plans-ending li").first();
  await expect(first).toContainText(/noch \d+ (Monat|Jahr)/i);
  // Mit dem Themenfeld zusammen: nur dessen Pläne, in derselben Reihenfolge.
  await page.getByRole("group", { name: "Nach Themenfeld filtern" }).getByRole("button", { name: /^Verkehr/ }).click();
  await expect(page.locator('#plans-ending a[href="/council/plan?key=mobilitaetsplan_2030"]')).toBeVisible();
  await expect(page.locator(`#plans-ending ${CLIMATE_PLAN}`)).toHaveCount(0);
  await views.getByRole("button", { name: "Nach Status" }).click();
  await expect(page.getByRole("heading", { name: "Laufend" })).toBeVisible();
});

test("Lotti erklärt den Plan einfach, drei Fragen führen ins Ratsarchiv, verwandte Pläne stehen daneben", async ({ page }) => {
  // Alles drei kommt aus Dateien im Repo — auch gegen die leere Ratsdatenbank.
  await schalter(page, true);
  await page.goto("/council/plan?key=schulverpflegung");
  const block = page.locator('section[aria-labelledby="plan-content"]');
  const lotti = block.getByRole("button", { name: /Lotti erklärt/ });
  await expect(lotti).toHaveAttribute("aria-expanded", "false");
  await lotti.click();
  await expect(block.getByText(/Automatisch aus den belegten Kernpunkten/)).toBeVisible();
  await expect(block.getByText(/zu 100 Prozent bio/)).toBeVisible();
  // Die Fragen sind Links auf die KI-Frage, mit der Frage vorbelegt.
  const chips = block.getByRole("group", { name: "Fragen an Lotti" }).getByRole("link");
  await expect(chips).toHaveCount(3);
  expect(await chips.first().getAttribute("href")).toMatch(/^\/fragen\?q=.+&chip=1$/);
  // Verwandt: was das Register selbst nennt. Vorgänger und Nachfolger stehen im Kopf, nicht hier.
  const related = page.locator('section[aria-labelledby="plan-related"]');
  await related.getByRole("link", { name: /Ernährungsstrategie/ }).click();
  await expect(page).toHaveURL(/\/council\/plan\?key=ernaehrungsstrategie/);
  await expect(page.locator('section[aria-labelledby="plan-related"]').getByRole("link", { name: /Schulverpflegung/ })).toBeVisible();
  // Ohne Kernpunkte gibt es weder die einfache Fassung noch Fragen.
  await page.goto("/council/plan?key=kai_2015");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("button", { name: /Lotti erklärt/ })).toHaveCount(0);
});

test("ein Bericht sagt in einem Satz, was drinsteht — mit Zitat; Neues steht darüber", async ({ page }) => {
  await schalter(page, true);
  await page.goto("/council/plan?key=klimaschutzplan_2035");
  const log = page.locator('section[aria-labelledby="plan-reports"]');
  await expect(log.getByText("Berichte im Rat", { exact: true })).toBeVisible();
  // Die Berichte selbst liegen im Bestand: Gegen die leere Datenbank der CI gibt es keinen Zeitstrahl —
  // und dann weder Satz noch „Neu“. Mit Bestand trägt der jüngste Bericht seinen Satz.
  if (await log.getByText("Aktueller Stand", { exact: true }).count() === 0) {
    await expect(log.getByText("Laut Bericht")).toHaveCount(0);
    await expect(log.getByText(/^Neu im jüngsten Bericht/)).toHaveCount(0);
    return;
  }
  const sentence = log.getByRole("button", { name: /^Laut Bericht/ }).first();
  await expect(sentence).toBeVisible();
  await expect(log.locator("blockquote")).toHaveCount(0);
  await sentence.click();
  await expect(log.locator("blockquote").first()).toBeVisible();
  // „Neu“ steht nur da, solange der verglichene Bericht der jüngste ist — dann als Selbstauskunft benannt.
  const news = log.getByText(/^Neu im jüngsten Bericht/);
  if (await news.count()) await expect(log.getByText(/Nach Angaben der Verwaltung/)).toBeVisible();
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
      "/council/plan?key=schulverpflegung", "/council/plan?key=kita_ausbau"]) {
      await page.goto(pfad, { waitUntil: "networkidle" });
      expect(await ueberbreite(page), `${pfad} bei ${breite} px`).toBeLessThanOrEqual(1);
    }
  });
}
