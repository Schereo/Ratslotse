/**
 * „Meine Notiz“, auf dem Gerät verschlüsselt (Schalter `notizen`, Plan
 * `docs/plan-notizen-verschluesselt.md`).
 *
 * Echt sind hier Browser, WebCrypto und IndexedDB — genau das, was der
 * Vitest-Lauf nicht hat. `/api/notes` ist ein kleiner Schein-Server, der wie
 * der echte nur Blobs hält (Form und Version prüft `tests/test_notizen.py`).
 * So läuft der Test auch gegen das Backend der CI, das den Schalter nicht kennt.
 */
import { test, expect, type BrowserContext, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { zustandsDatei } from "./konten";
import { notizenSchein, passphraseWeg, type Ablage } from "./notizen-schein";

test.use({ storageState: zustandsDatei("nutzerin") });

const PUNKT = JSON.parse(readFileSync(join(__dirname, "fixtures", "punkt-4654-11-1.json"), "utf-8"));
const URL = "/council/punkt?ksinr=4654&top=%C3%96%2011.1";
const PASS = "Lotti liest mit 2026";

async function schein(page: Page, ablage: Ablage) {
  await page.route("**/api/app-config", (r) => r.fulfill({ json: { min_build: 0, features: ["punkt-seite", "notizen"] } }));
  await page.route("**/api/council/session/4654/item**", (r) => r.fulfill({ json: PUNKT }));
  await notizenSchein(page, ablage);
}

const karte = (page: Page) => page.locator("section", { has: page.locator("#meine-notiz") });
/** Die Notiz ist ein Reiter der Lesespalte — neben dem Chat, nicht unter ihm. */
const zurNotiz = (page: Page) => page.getByRole("tab", { name: "Meine Notiz" }).click();
/** Das Feld: ein Editor, der gleich formatiert zeigt, was man schreibt. */
const notiz = (k: Locator) => k.getByRole("textbox", { name: /Meine Notiz/ });

/** Ein virtueller Authenticator mit PRF — so, wie ein iPhone oder Mac ihn mitbringt. */
async function passkeyGeraet(page: Page, context: BrowserContext) {
  const cdp = await context.newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", { options: {
    protocol: "ctap2", ctap2Version: "ctap2_1", transport: "internal", hasResidentKey: true,
    hasUserVerification: true, isUserVerified: true, hasPrf: true, automaticPresenceSimulation: true,
  } });
}

test.describe("Meine Notiz", () => {
  test.setTimeout(90_000);

  test("einrichten, schreiben, gesperrt nach dem Neuladen, mit Passphrase wieder lesbar", async ({ page, browser }) => {
    const ablage: Ablage = { keys: null, notes: new Map() };
    await schein(page, ablage);
    await page.goto(URL);
    await zurNotiz(page);
    const k = karte(page);
    await k.getByRole("button", { name: "Notizen einrichten" }).click();
    await passphraseWeg(k);
    await k.locator("input[type=password]").nth(0).fill(PASS);
    await k.locator("input[type=password]").nth(1).fill(PASS);
    await k.getByRole("button", { name: "Weiter" }).click();
    const code = (await k.getByLabel("Wiederherstellungscode").textContent())!;
    expect(code).toMatch(/^([0-9A-HJKMNP-TV-Z]{4}-){7}[0-9A-HJKMNP-TV-Z]{4}$/);
    // Erst nach dem Abtippen lässt sich einrichten.
    await expect(k.getByRole("button", { name: "Notizen einrichten" })).toBeDisabled();
    await k.locator("input").first().fill(code.toLowerCase());
    await k.getByRole("button", { name: "Notizen einrichten" }).click();

    await notiz(k).fill("Verwaltung nach Unfallzahlen fragen.");
    await expect(k.getByText(/Gespeichert um/)).toBeVisible({ timeout: 10_000 });
    // Beim Server liegt nur Geheimtext.
    const gespeichert = [...ablage.notes.values()][0];
    expect(String(gespeichert.ciphertext)).not.toContain("Unfallzahlen");
    expect(Buffer.from(String(gespeichert.ciphertext), "base64").toString("latin1")).not.toContain("Unfallzahlen");

    await page.reload();
    // Der Notiz-Reiter bleibt gewählt — wer mitschreibt, schreibt weiter.
    await expect(page.getByRole("tab", { name: "Meine Notiz" })).toHaveAttribute("aria-selected", "true");
    await expect(k.getByText("Gesperrt", { exact: true })).toBeVisible();
    await expect(notiz(k)).toHaveCount(0);
    await k.locator("input[type=password]").fill(PASS);
    await k.getByRole("button", { name: /Entsperren/ }).click();
    await expect(notiz(k)).toHaveText("Verwaltung nach Unfallzahlen fragen.");

    // Ein zweites Gerät mit falscher Passphrase sieht nichts.
    const ctx2 = await browser.newContext({ storageState: zustandsDatei("nutzerin") });
    const p2 = await ctx2.newPage();
    await schein(p2, ablage);
    await p2.goto(URL);
    await zurNotiz(p2);
    const k2 = karte(p2);
    await k2.locator("input[type=password]").fill("eine ganz andere Passphrase");
    await k2.getByRole("button", { name: /Entsperren/ }).click();
    await expect(k2.getByText("Diese Passphrase passt nicht.")).toBeVisible();
    await expect(notiz(k2)).toHaveCount(0);
    // … mit dem Code aber schon, und danach gilt die neue Passphrase.
    await k2.getByRole("button", { name: "Passphrase vergessen?" }).click();
    await k2.locator("input").nth(0).fill(code);
    await k2.locator("input[type=password]").fill("neue Passphrase 2027");
    await k2.getByRole("button", { name: "Neue Passphrase setzen" }).click();
    await expect(notiz(k2)).toHaveText("Verwaltung nach Unfallzahlen fragen.");

    // Ein ECHT fremder Stand fragt weiterhin nach, statt still zu überschreiben.
    await notiz(k2).fill("Verwaltung nach Unfallzahlen fragen. Ortstermin?");
    await notiz(k2).blur();
    await expect.poll(() => [...ablage.notes.values()][0]?.version, { timeout: 10_000 }).toBe(2);
    await notiz(k).fill("Verwaltung nach Unfallzahlen fragen. Und die Kosten?");
    await notiz(k).blur();
    await expect(k.getByText("Auf einem anderen Gerät wurde diese Notiz inzwischen geändert.")).toBeVisible({ timeout: 10_000 });
    await expect(k.getByText("Verwaltung nach Unfallzahlen fragen. Ortstermin?").first()).toBeVisible();
    expect([...ablage.notes.values()][0]?.version).toBe(2);
    await ctx2.close();
  });

  test("mit Passkey einrichten, sperren und wieder entsperren — ohne Passphrase, ohne Code", async ({ page, context }) => {
    await passkeyGeraet(page, context);
    const ablage: Ablage = { keys: null, notes: new Map() };
    await schein(page, ablage);
    await page.goto(URL);
    await zurNotiz(page);
    const k = karte(page);
    await k.getByRole("button", { name: "Notizen einrichten" }).click();
    await k.getByRole("button", { name: "Mit Passkey einrichten" }).click();
    await notiz(k).fill("Kosten 2027 nachfragen.");
    await expect(k.getByText(/Gespeichert um/)).toBeVisible({ timeout: 10_000 });
    // Kein Code zum Abtippen, keine Passphrase — beim Server liegt nur die Verpackung des Passkeys.
    expect(ablage.keys?.wrapped_passphrase ?? null).toBeNull();
    expect(ablage.keys?.wrapped_recovery ?? null).toBeNull();
    expect(ablage.passkeys).toHaveLength(1);
    expect(String([...ablage.notes.values()][0].ciphertext)).not.toContain("Kosten");

    await k.getByRole("button", { name: "Sperren" }).click();
    await page.reload();
    await expect(k.getByText("Gesperrt", { exact: true })).toBeVisible();
    await expect(k.getByRole("button", { name: "Mit Passphrase" })).toHaveCount(0);
    await k.getByRole("button", { name: "Mit Passkey entsperren" }).click();
    await expect(notiz(k)).toHaveText("Kosten 2027 nachfragen.");
  });

  test("weiterschreiben, während gespeichert wird, ist kein Konflikt", async ({ page, context }) => {
    // Tims Befund 23.11.2026: Mitten im Tippen stand „Auf einem anderen Gerät
    // wurde diese Notiz inzwischen geändert“ — mit dem EIGENEN Text von eben.
    // Das zweite Speichern trug die Version von vor dem ersten.
    await passkeyGeraet(page, context);
    const ablage: Ablage = { keys: null, notes: new Map() };
    await schein(page, ablage);
    // Ein langsamer Server: So überholt das Tippen seine Antwort.
    await page.route("**/api/notes/agenda_item/**", async (r) => {
      if (r.request().method() === "PUT") await new Promise((weiter) => setTimeout(weiter, 1200));
      await r.fallback();
    });
    await page.goto(URL);
    await zurNotiz(page);
    const k = karte(page);
    await k.getByRole("button", { name: "Notizen einrichten" }).click();
    await k.getByRole("button", { name: "Mit Passkey einrichten" }).click();
    const feld = notiz(k);
    await feld.click();
    await feld.pressSequentially("Defizit 182 Millionen €");
    await expect(k.getByText("Speichert …")).toBeVisible({ timeout: 5_000 });
    await feld.pressSequentially(", kann Oldenburg nicht selber schließen");
    await feld.blur();
    await expect.poll(() => [...ablage.notes.values()][0]?.version, { timeout: 15_000 }).toBe(2);
    await expect(k.getByText(/Gespeichert um/)).toBeVisible({ timeout: 10_000 });
    await expect(k.getByText(/anderen Gerät/)).toHaveCount(0);
    await page.reload();
    await expect(notiz(k)).toHaveText("Defizit 182 Millionen €, kann Oldenburg nicht selber schließen");
  });

  test("formatiert gleich beim Schreiben: Liste, fett, Checkliste — und bleibt so", async ({ page, context }) => {
    await passkeyGeraet(page, context);
    const ablage: Ablage = { keys: null, notes: new Map() };
    await schein(page, ablage);
    await page.goto(URL);
    await zurNotiz(page);
    const k = karte(page);
    await k.getByRole("button", { name: "Notizen einrichten" }).click();
    await k.getByRole("button", { name: "Mit Passkey einrichten" }).click();
    const feld = notiz(k);
    const leiste = k.getByRole("toolbar", { name: "Formatierung" });
    const punkte = feld.locator("ul:not([data-type]) > li");

    await feld.click();
    // Wie in Markdown getippt: „1. “ am Zeilenanfang wird eine nummerierte Liste.
    await feld.pressSequentially("1. Ortstermin");
    await expect(feld.locator("ol > li")).toHaveText("Ortstermin");
    await feld.press("Enter");
    await feld.press("Enter");
    await feld.pressSequentially("Unfallzahlen");
    await leiste.getByRole("button", { name: "Aufzählung" }).click();
    await expect(punkte).toHaveCount(1);
    // Der Knopf zeigt, wo der Cursor steht — und nimmt dem Feld den Fokus nicht.
    await expect(leiste.getByRole("button", { name: "Aufzählung" })).toHaveAttribute("aria-pressed", "true");
    await expect(feld).toBeFocused();
    // ↩ setzt die Liste fort, ↩ auf dem leeren Punkt beendet sie.
    await feld.press("Enter");
    await feld.pressSequentially("Kosten");
    await feld.press("Enter");
    await feld.press("Enter");
    await feld.pressSequentially("Wichtig");
    await expect(punkte).toHaveCount(2);
    await expect(feld.locator(":scope > p").last()).toHaveText("Wichtig");
    await expect(leiste.getByRole("button", { name: "Aufzählung" })).toHaveAttribute("aria-pressed", "false");
    // Kein Markdown zu sehen: Fett ist fett.
    await feld.locator(":scope > p").last().dblclick();
    await leiste.getByRole("button", { name: "Fett" }).click();
    await expect(feld.locator("strong")).toHaveText("Wichtig");
    await expect(feld).not.toContainText("**");
    // Als Aufgabe — mit Kästchen zum Abhaken.
    await leiste.getByRole("button", { name: "Checkliste" }).click();
    const kasten = feld.getByRole("checkbox", { name: "Aufgabe: Wichtig" });
    await expect(kasten).not.toBeChecked();
    await kasten.check();
    await expect(kasten).toBeChecked();
    await feld.blur();
    await expect(k.getByText(/Gespeichert um/)).toBeVisible({ timeout: 10_000 });

    // Gespeichert ist Text, gezeigt wird er wieder formatiert.
    await k.getByRole("button", { name: "Sperren" }).click();
    await page.reload();
    await k.getByRole("button", { name: "Mit Passkey entsperren" }).click();
    await expect(punkte).toHaveCount(2);
    await expect(feld.locator("strong")).toHaveText("Wichtig");
    await expect(feld.getByRole("checkbox", { name: "Aufgabe: Wichtig" })).toBeChecked();
    await expect(feld.locator("ol > li")).toHaveText("Ortstermin");
  });

  test("ohne Schalter keine Karte", async ({ page }) => {
    await page.route("**/api/app-config", (r) => r.fulfill({ json: { min_build: 0, features: ["punkt-seite"] } }));
    await page.route("**/api/council/session/4654/item**", (r) => r.fulfill({ json: PUNKT }));
    await page.goto(URL);
    await expect(page.getByRole("heading", { name: "Weißenmoorstraße", level: 1 })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Meine Notiz" })).toHaveCount(0);
    await expect(page.locator("#meine-notiz")).toHaveCount(0);
  });
});
