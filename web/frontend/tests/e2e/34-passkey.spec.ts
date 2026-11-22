/**
 * „Mit Passkey anmelden“ (Schalter `passkey-anmeldung`, Backend
 * `web/backend/app/passkeys.py`).
 *
 * Echt sind Browser, WebAuthn und das Backend: Chrome bringt über CDP einen
 * virtuellen Authenticator mit PRF mit, wie ein iPhone oder Mac ihn hat, und
 * der Server prüft Signatur und Challenge wirklich (`tests/start-backend.sh`
 * schaltet den Schalter dafür an). Nur `/api/notes` ist der Schein-Server aus
 * `notizen-schein.ts` — das CI-Backend kennt den Schalter `notizen` nicht.
 *
 * Geprüft wird die Zusage „eine Abfrage für beides“: Wer sich per Passkey
 * registriert, hat danach Notiz-Schlüssel, verpackt mit genau diesem Passkey;
 * wer sich damit anmeldet, findet die Notizen offen.
 */
import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { notizenSchein, type Ablage } from "./notizen-schein";

const PUNKT = JSON.parse(readFileSync(join(__dirname, "fixtures", "punkt-4654-11-1.json"), "utf-8"));
const PUNKT_URL = "/council/punkt?ksinr=4654&top=%C3%96%2011.1";
const ANMELDE_SALZ_B64 = "5MnwhF9xlXWJRKjXOzZmPPe88kNNx+zhKCJHRsu15G4=";

test.use({ storageState: { cookies: [], origins: [] } });

async function authenticator(page: Page, context: BrowserContext) {
  const cdp = await context.newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", { options: {
    protocol: "ctap2", ctap2Version: "ctap2_1", transport: "internal", hasResidentKey: true,
    hasUserVerification: true, isUserVerified: true, hasPrf: true, automaticPresenceSimulation: true,
  } });
}

async function schalter(page: Page, ablage: Ablage) {
  await page.route("**/api/app-config", (r) => r.fulfill({ json: { min_build: 0, features: ["punkt-seite", "notizen", "passkey-anmeldung"] } }));
  await page.route("**/api/council/session/4654/item**", (r) => r.fulfill({ json: PUNKT }));
  await notizenSchein(page, ablage);
}

const neueAdresse = (wer: string) => `${wer}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.org`;

async function einrichtungFertig(page: Page) {
  const r = await page.request.post("/api/onboarding/setup", { data: { step: 3, done: true } });
  expect(r.ok(), await r.text()).toBeTruthy();
}

async function mitPasskeyRegistrieren(page: Page, email: string) {
  await page.goto("/register");
  await page.locator("#display-name").fill("Pia");
  await page.locator("#email").fill(email);
  await page.getByRole("button", { name: "Mit Passkey registrieren" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/register"), { timeout: 15_000 });
  await einrichtungFertig(page);
}

async function abmelden(page: Page) {
  await page.request.post("/api/auth/logout");
  // Ohne den Schritt über die Oberfläche bleibt der gemerkte Notiz-Schlüssel
  // liegen — hier ausdrücklich weg, sonst bewiese das Anmelden nichts.
  await page.evaluate(() => new Promise<void>((ok) => {
    const r = indexedDB.deleteDatabase("ratslotse-notizen");
    r.onsuccess = r.onerror = r.onblocked = () => ok();
  }));
}

async function mitPasskeyAnmelden(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Mit Passkey anmelden" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 15_000 });
}

test.describe("Mit Passkey anmelden", () => {
  test.setTimeout(90_000);

  test("registrieren und anmelden — dieselbe Abfrage schließt die Notizen auf", async ({ page, context }) => {
    await authenticator(page, context);
    const ablage: Ablage = { keys: null, notes: new Map() };
    await schalter(page, ablage);
    const email = neueAdresse("passkey");

    await mitPasskeyRegistrieren(page, email);
    const me = await (await page.request.get("/api/auth/me")).json();
    expect(me.email).toBe(email);
    expect(me.has_password).toBe(false);
    // Die Notiz-Schlüssel entstehen still, verpackt mit genau diesem Passkey.
    await expect.poll(() => ablage.passkeys?.length ?? 0).toBe(1);
    const konto = await (await page.request.get("/api/account/passkeys")).json();
    expect(konto.passkeys).toHaveLength(1);
    expect(ablage.passkeys![0].credential_id).toBe(konto.passkeys[0].credential_id);
    expect(ablage.passkeys![0].prf_salt).toBe(ANMELDE_SALZ_B64);
    expect(ablage.keys?.wrapped_passphrase ?? null).toBeNull();

    await abmelden(page);
    expect((await page.request.get("/api/auth/me")).status()).toBe(401);

    await mitPasskeyAnmelden(page);
    expect((await (await page.request.get("/api/auth/me")).json()).email).toBe(email);
    // Gleich offen, ohne zweite Abfrage und ohne neues Einrichten.
    await page.goto(PUNKT_URL);
    const karte = page.locator("section", { has: page.locator("#meine-notiz") });
    await expect(karte.locator("textarea")).toBeVisible({ timeout: 10_000 });
    await expect(karte.getByText("Gesperrt", { exact: true })).toHaveCount(0);
    expect(ablage.passkeys).toHaveLength(1);
  });

  test("Passwort-Konto legt im Konto einen Passkey an, meldet sich damit an und entfernt ihn", async ({ page, context }) => {
    await authenticator(page, context);
    await schalter(page, { keys: null, notes: new Map() });
    const email = neueAdresse("passwort");
    expect((await page.request.post("/api/auth/register", {
      data: { email, password: "password123", display_name: "Paul" } })).status()).toBe(201);
    await einrichtungFertig(page);

    await page.goto("/account");
    const karte = page.getByRole("region", { name: "Passkeys", exact: true });
    await karte.getByRole("button", { name: "Passkey hinzufügen" }).click();
    await expect(page.getByText("Passkey hinzugefügt.")).toBeVisible();
    await expect(karte.getByRole("button", { name: /entfernen/ })).toHaveCount(1);

    await abmelden(page);
    await mitPasskeyAnmelden(page);
    expect((await (await page.request.get("/api/auth/me")).json()).email).toBe(email);

    await page.goto("/account");
    await karte.getByRole("button", { name: /entfernen/ }).click();
    await page.getByRole("button", { name: "Entfernen", exact: true }).click();
    await expect(page.getByText("Passkey entfernt.")).toBeVisible();
    await expect(karte.getByRole("button", { name: /entfernen/ })).toHaveCount(0);
  });

  test("ein Konto nur mit Passkey: letzter Weg bleibt, Löschen bestätigt der Passkey", async ({ page, context }) => {
    await authenticator(page, context);
    await schalter(page, { keys: null, notes: new Map() });
    await mitPasskeyRegistrieren(page, neueAdresse("nurpasskey"));

    await page.goto("/account");
    const karte = page.getByRole("region", { name: "Passkeys", exact: true });
    await karte.getByRole("button", { name: /entfernen/ }).click();
    await page.getByRole("button", { name: "Entfernen", exact: true }).click();
    await expect(page.getByText(/einziger Weg ins Konto/)).toBeVisible();
    await expect(karte.getByRole("button", { name: /entfernen/ })).toHaveCount(1);

    await page.getByRole("button", { name: "Mit Passkey bestätigen & löschen" }).click();
    await page.getByRole("button", { name: "Endgültig löschen" }).click();
    await expect(page.getByText("Dein Konto wurde gelöscht.")).toBeVisible({ timeout: 15_000 });
    expect((await page.request.get("/api/auth/me")).status()).toBe(401);
  });
});
