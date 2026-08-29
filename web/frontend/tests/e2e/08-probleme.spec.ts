import { expect, test } from "@playwright/test";
import { VORSCHAU_PROBLEME } from "../../lib/probleme";

const summaries = VORSCHAU_PROBLEME.map((problem) => ({
  id: problem.id,
  title: problem.title,
  category: problem.category,
  scope_kind: problem.scope_kind,
  location_label: problem.location_label,
  latitude: problem.latitude,
  longitude: problem.longitude,
  geometry: problem.geometry,
  status: problem.status,
  frequency: problem.frequency,
}));
const response = { problems: summaries, total: summaries.length };

test.describe("Öffentliche Problemkarte", () => {
  test.beforeEach(async ({ page }) => {
    await page.route(/\/api\/probleme\/\d+$/, (route) => {
      const id = Number(new URL(route.request().url()).pathname.split("/").pop());
      const problem = VORSCHAU_PROBLEME.find((entry) => entry.id === id);
      return route.fulfill({
        status: problem ? 200 : 404,
        contentType: "application/json",
        body: JSON.stringify(problem ?? { detail: "Problem nicht gefunden." }),
      });
    });
    await page.route("**/api/probleme", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(response),
    }));
  });

  test("startet minimal mit der Karte und wechselt ins Status-Board", async ({ page }) => {
    await page.goto("/probleme");

    await expect(page.getByRole("heading", { name: "Probleme in Oldenburg" })).toBeVisible();
    await expect(page.locator(".problem-map-pin")).toHaveCount(3);
    await expect(page.getByRole("button", { name: "Karte" })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText("Du willst später selbst etwas melden?")).toBeVisible();

    await page.getByRole("button", { name: "Status" }).click();
    await expect(page).toHaveURL(/view=status/);
    await expect(page.getByRole("heading", { name: "Neu" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Geprüft" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Beispiel:/ })).toHaveCount(4);
    await expect(page.getByLabel("Nach Thema filtern")).toHaveCount(0);
    await expect(page.locator(".problem-frequency-dot.frequency-very_many")).toBeVisible();
  });

  test("Auswahl im Status-Board ist verlinkbar", async ({ page }) => {
    await page.goto("/probleme?view=status");
    await expect(page.getByText(/unabhängige Meldung/)).toHaveCount(0);
    await page.getByRole("button", { name: /Beispiel: Barrierefreier Zugang/ }).click();
    await expect(page).toHaveURL(/problem=9003/);
    await expect(page.getByRole("heading", { level: 2, name: "Beispiel: Barrierefreier Zugang zur Haltestelle fehlt" })).toBeVisible();
    await expect(page.getByText("4 unabhängige Meldungen")).toBeVisible();
    await page.getByRole("link", { name: "Problemseite öffnen" }).click();
    await expect(page).toHaveURL(/\/probleme\/9003$/);
  });

  test("zeigt alle freigegebenen Details und die öffentliche Zeitleiste", async ({ page }) => {
    await page.goto("/probleme/9001");

    await expect(page.getByRole("heading", { level: 1, name: "Beispiel: Dunkler Fußweg am Kanal" })).toBeVisible();
    await expect(page.getByText("6 unabhängige Meldungen")).toBeVisible();
    await expect(page.getByText("Reporter*innen")).toHaveCount(0);
    await expect(page.getByText("Aktuelle Beobachtungen")).toHaveCount(0);
    await expect(page.getByText("Beobachtungen insgesamt")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Öffentliche Zeitleiste" })).toBeVisible();
    await expect(page.getByText("Beispielhafte öffentliche Rückmeldung")).toBeVisible();
    await expect(page.getByText("Problem veröffentlicht")).toBeVisible();
    await expect(page.getByText("Stadtverwaltung")).toBeVisible();
    await expect(page.getByText("Ratslotse-Prüfung")).toBeVisible();
    await expect(page.getByRole("link", { name: "Quelle öffnen" })).toHaveAttribute("href", "https://example.invalid/fiktive-quelle");
    await expect(page.getByRole("link", { name: "Zur Problemkarte" })).toBeVisible();
    await expect(page.getByText(/kein amtlicher Bearbeitungsstand/i)).toBeVisible();
    await expect(page.getByText("Du willst später selbst etwas melden?")).toBeVisible();
  });

  test("erklärt ein nicht gefundenes Problem ohne Anmeldeschranke", async ({ page }) => {
    await page.goto("/probleme/9999");

    await expect(page.getByRole("heading", { name: "Problem nicht gefunden" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Zur Problemkarte" })).toBeVisible();
    await expect(page).toHaveURL(/\/probleme\/9999$/);

    await page.goto("/probleme/ungueltig");
    await expect(page.getByRole("heading", { name: "Problem nicht gefunden" })).toBeVisible();
    await expect(page).toHaveURL(/\/probleme\/ungueltig$/);
  });
});
