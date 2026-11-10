/**
 * „Meine Notiz“, auf dem Gerät verschlüsselt (Schalter `notizen`, Plan
 * `docs/plan-notizen-verschluesselt.md`).
 *
 * Echt sind hier Browser, WebCrypto und IndexedDB — genau das, was der
 * Vitest-Lauf nicht hat. `/api/notes` ist ein kleiner Schein-Server, der wie
 * der echte nur Blobs hält (Form und Version prüft `tests/test_notizen.py`).
 * So läuft der Test auch gegen das Backend der CI, das den Schalter nicht kennt.
 */
import { test, expect, type Page, type Route } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { zustandsDatei } from "./konten";

test.use({ storageState: zustandsDatei("nutzerin") });

const PUNKT = JSON.parse(readFileSync(join(__dirname, "fixtures", "punkt-4654-11-1.json"), "utf-8"));
const URL = "/council/punkt?ksinr=4654&top=%C3%96%2011.1";
const PASS = "Lotti liest mit 2026";

type Ablage = { keys: Record<string, unknown> | null; notes: Map<string, Record<string, unknown>> };

async function schein(page: Page, ablage: Ablage) {
  await page.route("**/api/app-config", (r) => r.fulfill({ json: { min_build: 0, features: ["punkt-seite", "notizen"] } }));
  await page.route("**/api/council/session/4654/item**", (r) => r.fulfill({ json: PUNKT }));
  await page.route("**/api/notes**", async (route: Route) => {
    const req = route.request();
    const pfad = new globalThis.URL(req.url()).pathname.replace(/^\/api\/notes/, "");
    const body = req.postData() ? JSON.parse(req.postData()!) : null;
    const jetzt = new Date().toISOString().slice(0, 19);
    if (pfad === "/keys") {
      if (req.method() === "GET") return route.fulfill({ json: { configured: !!ablage.keys, keys: ablage.keys } });
      if (req.method() === "DELETE") { ablage.keys = null; ablage.notes.clear(); return route.fulfill({ json: { deleted: 0 } }); }
      if (body.wrapped_recovery) {
        if (ablage.keys) return route.fulfill({ status: 409, json: { detail: "Notizen sind schon eingerichtet." } });
        ablage.keys = { ...body, updated_at: jetzt };
      } else {
        ablage.keys = { ...ablage.keys, ...body, updated_at: jetzt };
      }
      return route.fulfill({ json: { configured: true, keys: ablage.keys } });
    }
    if (pfad === "" || pfad === "/") {
      return route.fulfill({ json: { notes: [...ablage.notes.values()] } });
    }
    const [, kind, key, art] = pfad.split("/").map(decodeURIComponent);
    const id = `${kind}|${key}|${art}`;
    const alt = ablage.notes.get(id);
    if (req.method() === "DELETE") { ablage.notes.delete(id); return route.fulfill({ status: 204, body: "" }); }
    if ((alt?.version ?? 0) !== body.version) {
      return route.fulfill({ status: 409, json: { detail: { message: "geändert", current: alt ?? null } } });
    }
    const neu = { target_kind: kind, target_key: key, kind: art, iv: body.iv, ciphertext: body.ciphertext,
                  key_version: body.key_version, version: (alt?.version as number ?? 0) + 1, updated_at: jetzt };
    ablage.notes.set(id, neu);
    return route.fulfill({ json: neu });
  });
}

const karte = (page: Page) => page.locator("section", { has: page.locator("#meine-notiz") });

test.describe("Meine Notiz", () => {
  test.setTimeout(90_000);

  test("einrichten, schreiben, gesperrt nach dem Neuladen, mit Passphrase wieder lesbar", async ({ page, browser }) => {
    const ablage: Ablage = { keys: null, notes: new Map() };
    await schein(page, ablage);
    await page.goto(URL);
    const k = karte(page);
    await k.getByRole("button", { name: "Notizen einrichten" }).click();
    await k.locator("input[type=password]").nth(0).fill(PASS);
    await k.locator("input[type=password]").nth(1).fill(PASS);
    await k.getByRole("button", { name: "Weiter" }).click();
    const code = (await k.getByLabel("Wiederherstellungscode").textContent())!;
    expect(code).toMatch(/^([0-9A-HJKMNP-TV-Z]{4}-){7}[0-9A-HJKMNP-TV-Z]{4}$/);
    // Erst nach dem Abtippen lässt sich einrichten.
    await expect(k.getByRole("button", { name: "Notizen einrichten" })).toBeDisabled();
    await k.locator("input").first().fill(code.toLowerCase());
    await k.getByRole("button", { name: "Notizen einrichten" }).click();

    await k.locator("textarea").fill("Verwaltung nach Unfallzahlen fragen.");
    await expect(k.getByText(/Gespeichert um/)).toBeVisible({ timeout: 10_000 });
    // Beim Server liegt nur Geheimtext.
    const gespeichert = [...ablage.notes.values()][0];
    expect(String(gespeichert.ciphertext)).not.toContain("Unfallzahlen");
    expect(Buffer.from(String(gespeichert.ciphertext), "base64").toString("latin1")).not.toContain("Unfallzahlen");

    await page.reload();
    await expect(k.getByText("Gesperrt", { exact: true })).toBeVisible();
    await expect(k.locator("textarea")).toHaveCount(0);
    await k.locator("input[type=password]").fill(PASS);
    await k.getByRole("button", { name: /Entsperren/ }).click();
    await expect(k.locator("textarea")).toHaveValue("Verwaltung nach Unfallzahlen fragen.");

    // Ein zweites Gerät mit falscher Passphrase sieht nichts.
    const ctx2 = await browser.newContext({ storageState: zustandsDatei("nutzerin") });
    const p2 = await ctx2.newPage();
    await schein(p2, ablage);
    await p2.goto(URL);
    const k2 = karte(p2);
    await k2.locator("input[type=password]").fill("eine ganz andere Passphrase");
    await k2.getByRole("button", { name: /Entsperren/ }).click();
    await expect(k2.getByText("Diese Passphrase passt nicht.")).toBeVisible();
    await expect(k2.locator("textarea")).toHaveCount(0);
    // … mit dem Code aber schon, und danach gilt die neue Passphrase.
    await k2.getByRole("button", { name: "Passphrase vergessen?" }).click();
    await k2.locator("input").nth(0).fill(code);
    await k2.locator("input[type=password]").fill("neue Passphrase 2027");
    await k2.getByRole("button", { name: "Neue Passphrase setzen" }).click();
    await expect(k2.locator("textarea")).toHaveValue("Verwaltung nach Unfallzahlen fragen.");
    await ctx2.close();
  });

  test("ohne Schalter keine Karte", async ({ page }) => {
    await page.route("**/api/app-config", (r) => r.fulfill({ json: { min_build: 0, features: ["punkt-seite"] } }));
    await page.route("**/api/council/session/4654/item**", (r) => r.fulfill({ json: PUNKT }));
    await page.goto(URL);
    await expect(page.getByRole("heading", { name: "Weißenmoorstraße", level: 1 })).toBeVisible();
    await expect(page.locator("#meine-notiz")).toHaveCount(0);
  });
});
