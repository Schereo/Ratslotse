/**
 * Der Rats-Bereich: Sitzungen, Tagesordnungen, Ortsbezug der Beschlüsse.
 *
 * ÜBERARBEITET am 03.09.2026. Die Datei prüfte eine Oberfläche von vorher:
 * eine Überschrift „Ratsinformationssystem" (die Reiter heißen heute
 * „Suche", „Sitzungen", „Stadtkarte", „Analyse"), einen Zeitraum „Kommend"
 * (heute „Anstehend") — und vor allem einen DIALOG für die Tagesordnung. Die
 * klappt seit dem Umbau in der Karte selbst auf, und `/council` beginnt nicht
 * mehr bei den Sitzungen, sondern bei der Suche.
 */
import { test, expect } from "@playwright/test";
import { loginAdmin } from "./helpers";

const MOCK_SESSION = {
  ksinr: 42,
  committee: "Bauausschuss",
  session_date: "2026-07-15",
  session_time: "18:00",
  location: "Rathaus, Saal A",
  n_items: 3,
};

const MOCK_DETAIL = {
  ...MOCK_SESSION,
  agenda_items: [
    { item_number: "Ö 1", title: "Bebauungsplan Hafen", vorlage_nr: "2026/123", kvonr: null, is_public: 1 },
    { item_number: "Ö 2", title: "Radwegekonzept", vorlage_nr: null, kvonr: null, is_public: 1 },
    { item_number: "N 1", title: "Personalangelegenheit", vorlage_nr: null, kvonr: null, is_public: 0 },
  ],
  url: "https://ratsinfo.oldenburg.de/ksinr=42",
};

test.describe("Ratsinformationssystem", () => {
  test.beforeEach(async ({ page }) => {
    await loginAdmin(page);

    await page.route("**/api/council/committees", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ committees: ["Bauausschuss", "Stadtentwicklungsausschuss"] }),
      }),
    );
    await page.route("**/api/council/sessions**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        // `total` gehört dazu: Ohne es steht „undefined Sitzungen gefunden"
        // über der Liste und „NaN" in der Blätterleiste.
        body: JSON.stringify({ sessions: [MOCK_SESSION], count: 1, total: 1 }),
      }),
    );
  });

  test("der Sitzungs-Reiter zeigt Überschrift und Zeitraum", async ({ page }) => {
    await page.goto("/council?tab=sessions");
    await expect(page.getByRole("heading", { name: "Sitzungen" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Anstehend" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Vergangen" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Alle", exact: true })).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/04-council-page.png", fullPage: true });
  });

  test("ohne Reiter beginnt die Seite bei der Suche", async ({ page }) => {
    await page.goto("/council");
    await expect(page.getByRole("heading", { name: "Suche" }).first()).toBeVisible();
  });

  test("die Sitzungskarten kommen aus dem Backend", async ({ page }) => {
    await page.goto("/council?tab=sessions");
    const karte = page.locator("main button").filter({ hasText: "Bauausschuss" }).first();
    await expect(karte).toBeVisible();
    // Das Datum steht als Kalenderblatt (Monat + Tag), nicht mehr als
    // „15.07.2026"; die Uhrzeit daneben im Klartext.
    // „Jul" im DOM — die Großschreibung macht CSS, und `toContainText` liest
    // den Text, nicht das Aussehen.
    await expect(karte).toContainText("Jul");
    await expect(karte).toContainText("15");
    await expect(karte).toContainText("18:00 Uhr");
    await expect(karte).toContainText("3 TOPs");
    await page.screenshot({ path: "test-results/screenshots/04-council-sessions.png", fullPage: true });
  });

  test("ein Klick klappt die Tagesordnung in der Karte auf", async ({ page }) => {
    await page.route("**/api/council/session/42", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_DETAIL) }),
    );

    await page.goto("/council?tab=sessions");
    await page.locator("main button", { hasText: "Bauausschuss" }).first().click();
    // Kein Dialog mehr: Die Tagesordnung erscheint IN der Karte, und der
    // Knopf wird zum Zuklappen.
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByText("Bebauungsplan Hafen")).toBeVisible();
    await expect(page.getByText("nichtöffentlich")).toBeVisible();
    await expect(page.getByRole("button", { name: "Weniger anzeigen" })).toBeVisible();
    // animations: "disabled" fast-forwards the dialog fade/zoom so the capture
    // isn't taken mid-animation (which renders the content semi-transparent).
    await page.screenshot({ path: "test-results/screenshots/04-council-detail.png", fullPage: true, animations: "disabled" });
  });

  test("nur konkrete Unterpunkte bieten „Merken“ an", async ({ page }) => {
    await page.route("**/api/council/session/42", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...MOCK_DETAIL,
          agenda_items: [
            { item_number: "Ö 4", title: "Anträge der Fraktionen, Gruppen, Rats- und Ausschussmitglieder", vorlage_nr: null, kvonr: null, is_public: 1 },
            { item_number: "Ö 4.1", title: "Antrag: Mehr sichere Schulwege", vorlage_nr: "2026/401", kvonr: 401, is_public: 1 },
          ],
        }),
      }),
    );

    await page.goto("/council?tab=sessions");
    await page.locator("main button", { hasText: "Bauausschuss" }).first().click();
    const parent = page.locator("li", { hasText: "Anträge der Fraktionen" });
    const child = page.locator("li", { hasText: "Mehr sichere Schulwege" });
    await expect(parent.getByRole("button", { name: "Zur Merkliste hinzufügen" })).toHaveCount(0);
    await expect(child.getByRole("button", { name: "Zur Merkliste hinzufügen" })).toBeVisible();
  });

  test("ein Wechsel des Zeitraums lädt neu", async ({ page }) => {
    let callCount = 0;
    await page.route("**/api/council/sessions**", (route) => {
      callCount++;
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ sessions: [], count: 0, total: 0 }) });
    });

    await page.goto("/council?tab=sessions");
    await page.getByRole("button", { name: "Vergangen" }).click();
    await page.waitForTimeout(500);
    expect(callCount).toBeGreaterThanOrEqual(2);
    await page.screenshot({ path: "test-results/screenshots/04-council-scope-switch.png", fullPage: true });
  });

  test("Beschlüsse lassen sich nach Ortsbezug filtern", async ({ page }) => {
    await page.route("**/api/council/fields", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ fields: [] }) }),
    );
    await page.route("**/api/council/districts", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        // `place_id` ist der Wert, mit dem gefiltert wird — der Name ist nur
        // die Beschriftung. Ohne ihn wählt der Klick nichts aus, und die
        // Abfrage geht unverändert wieder heraus.
        body: JSON.stringify({
          districts: [{
            place_id: "kreyenbrueck", name: "Kreyenbrück", kind: "district",
            kind_label: "Stadtteil", parent_ids: [],
            count: 2, vote_count: 1, report_count: 1,
          }],
        }),
      }),
    );
    let requestedDistrict = "";
    await page.route("**/api/council/decisions**", (route) => {
      requestedDistrict = new URL(route.request().url()).searchParams.get("district") ?? "";
      const decision = {
        id: 11, ksinr: 42, kind: "decision", parent_item: null, item_number: "5",
        title: "Widmung Klingenbergplatz", beschluss: "Die Erweiterungsfläche wird gewidmet.",
        outcome: "accepted", vote: null, gegenstimmen: null, enthaltungen: null,
        factions: [], parties: [], vorlage_nr: null, raw_result: null,
        committee: "Bauausschuss", session_date: "2026-07-15", protocol_url: null,
        policy_field: null, policy_tags: [], summary: null, amount_eur: null,
        location_matches: requestedDistrict ? [{
          name: "Klingenbergplatz", stadtteil: "Kreyenbrück", source: "title",
          evidence: "Widmung Klingenbergplatz", method: "regex", confidence: 0.98,
        }] : [],
      };
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ total: 1, decisions: [decision] }),
      });
    });

    await page.goto("/council?tab=decisions");
    await page.getByRole("button", { name: "Ortsbezug" }).click();
    await page.getByRole("button", { name: "Kreyenbrück (1)" }).click();

    await expect.poll(() => requestedDistrict).toBe("kreyenbrueck");
    await expect(page).toHaveURL(/district=kreyenbrueck/);
    await expect(page.getByText("Ortsbezug:", { exact: true })).toBeVisible();
    await expect(page.getByText("Fundstelle: „Widmung Klingenbergplatz“")).toBeVisible();
  });
});
