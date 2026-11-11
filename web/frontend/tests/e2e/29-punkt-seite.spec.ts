/**
 * Die Seite eines Tagesordnungspunkts (Schalter `punkt-seite`, Plan
 * `docs/plan-sitzungsseite-kurs.md`, Schritt 4).
 *
 * Gestubbt mit einer echten Antwort von `/council/session/{ksinr}/item`
 * (`fixtures/punkt-4654-11-1.json`, Weißenmoorstraße im Verkehrsausschuss
 * am 21.09.2026) — der Test läuft so auch gegen die leere Ratsdatenbank.
 */
import { test, expect, type Page } from "@playwright/test";
import { zustandsDatei } from "./konten";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const PUNKT = JSON.parse(readFileSync(join(__dirname, "fixtures", "punkt-4654-11-1.json"), "utf-8"));
const SITZUNG = JSON.parse(readFileSync(join(__dirname, "fixtures", "sitzung-kurs-4654.json"), "utf-8"));

async function stubs(page: Page, features = ["sitzung-kurs", "punkt-seite"]) {
  await page.route("**/api/app-config", (route) => route.fulfill({ json: { min_build: 0, features } }));
  await page.route("**/api/council/session/4654/item**", (route) => route.fulfill({ json: PUNKT }));
  await page.route("**/api/council/session/4654", (route) => route.fulfill({ json: SITZUNG }));
}

test.describe("Punkt-Seite", () => {
  test("zeigt Kurzfassung, Vorgeschichte und Unterlagen ohne Konto", async ({ page }) => {
    await stubs(page);
    await page.goto("/council/punkt?ksinr=4654&top=%C3%96%2011.1");
    await expect(page.getByRole("heading", { name: "Weißenmoorstraße", level: 1 })).toBeVisible();
    await expect(page.getByText("Das Wichtigste in Kürze")).toBeVisible();
    await expect(page.getByRole("tab", { name: /Vorgeschichte/ })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText(/Verkehrsausschuss · diese Sitzung/)).toBeVisible();
    await page.getByRole("tab", { name: /Unterlagen/ }).click();
    await expect(page.getByRole("link", { name: /VCD-Antrag/ })).toHaveAttribute("target", "_blank");
    await expect(page.locator("#password")).toHaveCount(0);
  });

  test("Zurück und Weiter führen durch die Sitzung", async ({ page }) => {
    await stubs(page);
    await page.goto("/council/punkt?ksinr=4654&top=%C3%96%2011.1");
    await expect(page.getByRole("link", { name: /Weiter Ö 11\.2/ }))
      .toHaveAttribute("href", "/council/punkt?ksinr=4654&top=%C3%96%2011.2");
    await expect(page.getByRole("link", { name: /Zurück Ö 10/ }))
      .toHaveAttribute("href", "/council/punkt?ksinr=4654&top=%C3%96%2010");
  });

  test("„Frag den Rat“ reicht den Punkt als Bezug weiter", async ({ page }) => {
    await stubs(page);
    await page.goto("/council/punkt?ksinr=4654&top=%C3%96%2011.1");
    const vorschlag = page.getByRole("link", { name: /Was wurde dazu früher beschlossen\?/ });
    await expect(vorschlag).toHaveAttribute("href", /\/fragen\?q=.*&ksinr=4654&top=%C3%96%2011\.1/);
  });

  test.describe("angemeldet", () => {
    test.use({ storageState: zustandsDatei("admin") });

    test("„Frag den Rat“ antwortet direkt auf der Seite, mit dem Punkt als Gegenstand", async ({ page }) => {
      await stubs(page);
      let koerper: Record<string, unknown> = {};
      await page.route("**/api/council/ask", async (route) => {
        koerper = JSON.parse(route.request().postData() ?? "{}");
        await route.fulfill({ status: 200, contentType: "text/event-stream", body: [
          { type: "step", step: "answer" },
          { type: "sources", sources: [{ id: 4711, title: "Vorbehaltsnetz Weißenmoorstraße", summary: null,
            policy_field: null, outcome: "postponed", session_date: "2026-08-24", committee: "Verkehrsausschuss" }] },
          { type: "token", text: "Der Antrag wurde im August vertagt [4711]." },
          { type: "suggestions", questions: ["Wer hat den Antrag gestellt?"] },
          { type: "done", conversation_id: null },
        ].map((e) => `data: ${JSON.stringify(e)}\n\n`).join("") });
      });
      await page.goto("/council/punkt?ksinr=4654&top=%C3%96%2011.1");
      await page.getByRole("button", { name: /Was wurde dazu früher beschlossen\?/ }).click();
      // Die Antwort steht auf DIESER Seite — kein Sprung auf /fragen.
      await expect(page.getByText(/Der Antrag wurde im August vertagt/)).toBeVisible();
      await expect(page).toHaveURL(/\/council\/punkt/);
      await expect(page.getByRole("link", { name: /Vorbehaltsnetz Weißenmoorstraße/ }))
        .toHaveAttribute("href", "/council/decision?id=4711");
      await expect(page.getByRole("button", { name: "Wer hat den Antrag gestellt?" })).toBeVisible();
      // Der Punkt reist als Kennung mit, und das Gespräch gehört der Seite, nicht Lotti.
      expect(koerper.screen).toEqual({ route: "/council/punkt", surface: "page",
                                       refs: { ksinr: 4654, item_number: "Ö 11.1" } });
      expect(koerper.from_suggestion).toBe(true);
    });
  });

  test("die Karten der Sitzung führen auf die Seite des Punkts", async ({ page }) => {
    await stubs(page);
    await page.goto("/council/sitzung?ksinr=4654");
    await expect(page.getByRole("link", { name: "Weißenmoorstraße", exact: true }))
      .toHaveAttribute("href", "/council/punkt?ksinr=4654&top=%C3%96%2011.1");
  });

  test("ohne Schalter führt die Seite zur Sitzung", async ({ page }) => {
    await stubs(page, ["sitzung-kurs"]);
    await page.goto("/council/punkt?ksinr=4654&top=%C3%96%2011.1");
    await expect(page.getByRole("link", { name: "Zur Sitzung" })).toBeVisible();
  });

  for (const breite of [300, 320]) test(`kein seitliches Scrollen bei ${breite} px`, async ({ page }) => {
    await stubs(page);
    await page.setViewportSize({ width: breite, height: 844 });
    await page.goto("/council/punkt?ksinr=4654&top=%C3%96%2011.1");
    await expect(page.getByRole("heading", { name: "Weißenmoorstraße", level: 1 })).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth))
      .toBeLessThanOrEqual(0);
  });
});
