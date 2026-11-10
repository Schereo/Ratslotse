/**
 * „Mein Mitschrieb“ beim Mitlesen (Schalter `mitschrieb`, Plan
 * `docs/plan-sitzungsseite-kurs.md` 3.17, verschlüsselt wie die Notizen).
 *
 * Gestubbt mit der echten Sitzung vom 21.09.2026; `/api/notes` ist der
 * Schein-Server aus `notizen-schein.ts`.
 */
import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { zustandsDatei } from "./konten";
import { notizenSchein, type Ablage } from "./notizen-schein";

test.use({ storageState: zustandsDatei("nutzerin") });

const SITZUNG = JSON.parse(readFileSync(join(__dirname, "fixtures", "sitzung-kurs-4654.json"), "utf-8"));
const PUNKT = JSON.parse(readFileSync(join(__dirname, "fixtures", "punkt-4654-11-1.json"), "utf-8"));
const PASS = "Lotti liest mit 2026";

async function stubs(page: Page, ablage: Ablage, features = ["sitzung-kurs", "punkt-seite", "mitlesen", "notizen", "mitschrieb"]) {
  await page.route("**/api/app-config", (r) => r.fulfill({ json: { min_build: 0, features } }));
  await page.route("**/api/council/session/4654/item**", (r) => r.fulfill({ json: PUNKT }));
  await page.route("**/api/council/session/4654", (r) => r.fulfill({ json: SITZUNG }));
  await notizenSchein(page, ablage);
}

const karte = (page: Page) => page.locator("section", { has: page.locator("#mein-mitschrieb") });

test.describe("Mein Mitschrieb", () => {
  test.setTimeout(90_000);

  test("Ergebnis und Text festhalten — die eigene Boje färbt sich, verschlüsselt gespeichert", async ({ page }) => {
    const ablage: Ablage = { keys: null, notes: new Map() };
    await stubs(page, ablage);
    await page.goto("/council/sitzung/mitlesen?ksinr=4654");
    await page.getByRole("button", { name: /^Ö 9 · Soziales D-Ticket/ }).click();
    const k = karte(page);
    await expect(k.getByRole("heading", { name: "Mein Mitschrieb zu Ö 9" })).toBeVisible();
    await k.getByRole("button", { name: "Notizen einrichten" }).click();
    await k.locator("input[type=password]").nth(0).fill(PASS);
    await k.locator("input[type=password]").nth(1).fill(PASS);
    await k.getByRole("button", { name: "Weiter" }).click();
    const code = (await k.getByLabel("Wiederherstellungscode").textContent())!;
    await k.locator("input").first().fill(code);
    await k.getByRole("button", { name: "Notizen einrichten" }).click();

    await k.getByRole("button", { name: "Angenommen" }).click();
    await expect(k.getByRole("button", { name: "Angenommen" })).toHaveAttribute("aria-pressed", "true");
    await k.locator("textarea").fill("Verwaltung will im Dezember berichten.");
    await expect(k.getByText(/Gespeichert um/)).toBeVisible({ timeout: 10_000 });
    // Die Boje im eigenen Kurs trägt das eigene Ergebnis, ausdrücklich als Mitschrieb.
    await expect(page.getByRole("button", { name: /^Ö 9 · Soziales D-Ticket.*Angenommen \(mein Mitschrieb\)/ })).toBeVisible();
    const blob = [...ablage.notes.values()].find((n) => n.kind === "transcript")!;
    expect(blob.target_key).toBe("4654|Ö 9");
    expect(Buffer.from(String(blob.ciphertext), "base64").toString("latin1")).not.toContain("Dezember");

    // Neu laden: gesperrt; nach dem Entsperren sind Text und Färbung wieder da.
    await page.reload();
    await expect(k.getByText("Gesperrt", { exact: true })).toBeVisible();
    await k.locator("input[type=password]").fill(PASS);
    await k.getByRole("button", { name: /Entsperren/ }).click();
    await expect(k.locator("textarea")).toHaveValue("Verwaltung will im Dezember berichten.");
    await expect(page.getByRole("button", { name: /^Ö 9 · Soziales D-Ticket.*\(mein Mitschrieb\)/ })).toBeVisible();
  });

  test("ohne Schalter kein Mitschrieb", async ({ page }) => {
    await stubs(page, { keys: null, notes: new Map() }, ["sitzung-kurs", "punkt-seite", "mitlesen", "notizen"]);
    await page.goto("/council/sitzung/mitlesen?ksinr=4654");
    await expect(page.locator("#jetzt-titel")).toBeVisible();
    await expect(page.locator("#mein-mitschrieb")).toHaveCount(0);
  });
});
