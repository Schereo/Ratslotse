/**
 * Gemeinsame Notizen (Schalter `notizen-teilen`): anlegen, per Link oder per
 * Adresse einladen, beitreten, live zusammen schreiben.
 *
 * Gegen das ECHTE Backend samt WebSocket (über den Rewrite von Next, wie auf
 * den Servern), mit zwei frischen Konten in zwei Browsern und je einem
 * virtuellen Authenticator mit PRF. Nur der Punkt kommt aus der Fixture —
 * so läuft der Test auch gegen die leere Ratsdatenbank.
 */
import { test, expect, type Browser, type BrowserContext, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const PUNKT = JSON.parse(readFileSync(join(__dirname, "fixtures", "punkt-4654-11-1.json"), "utf-8"));
const URL = "/council/punkt?ksinr=4654&top=%C3%96%2011.1";

test.use({ storageState: { cookies: [], origins: [] } });

const neueAdresse = (wer: string) => `${wer}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.org`;

async function person(browser: Browser, name: string): Promise<{ ctx: BrowserContext; page: Page; email: string }> {
  const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", { options: {
    protocol: "ctap2", ctap2Version: "ctap2_1", transport: "internal", hasResidentKey: true,
    hasUserVerification: true, isUserVerified: true, hasPrf: true, automaticPresenceSimulation: true,
  } });
  await page.route("**/api/app-config", (r) => r.fulfill({ json: { min_build: 0,
    features: ["punkt-seite", "notizen", "notizen-teilen"] } }));
  await page.route("**/api/council/session/4654/item**", (r) => r.fulfill({ json: PUNKT }));
  const email = neueAdresse(name.toLowerCase());
  const r = await page.request.post("/api/auth/register",
    { data: { display_name: name, email, password: "password123" } });
  expect(r.ok(), await r.text()).toBeTruthy();
  const s = await page.request.post("/api/onboarding/setup", { data: { step: 3, done: true } });
  expect(s.ok(), await s.text()).toBeTruthy();
  return { ctx, page, email };
}

const karte = (page: Page) => page.locator("section", { has: page.locator("#meine-notiz") });

async function notizenEinrichten(scope: ReturnType<Page["locator"]>) {
  await scope.getByRole("button", { name: "Notizen einrichten" }).click();
  await scope.getByRole("button", { name: "Mit Passkey einrichten" }).click();
}

/** Der Text der Notiz OHNE die Namensschilder fremder Cursor — die stehen als
 *  Elemente im Editor, und `toHaveText` läse „…und RadwegBen“ (CI 24.11.2026). */
const ohneCursor = (feld: Locator) => feld.evaluate((el) => {
  const kopie = el.cloneNode(true) as HTMLElement;
  kopie.querySelectorAll(".collaboration-carets__caret").forEach((n) => n.remove());
  return kopie.textContent ?? "";
});

test.describe("Gemeinsame Notizen", () => {
  test.setTimeout(120_000);

  test("anlegen, per Link einladen, beitreten und live zusammen schreiben", async ({ browser }) => {
    const anna = await person(browser, "Anna");
    const ben = await person(browser, "Ben");
    try {
      // Anna legt die gemeinsame Notiz an — mit ihrer eigenen Notiz als Anfang.
      await anna.page.goto(URL);
      await anna.page.getByRole("tab", { name: "Meine Notiz" }).click();
      const ka = karte(anna.page);
      await notizenEinrichten(ka);
      await ka.getByRole("textbox", { name: /Meine Notiz/ }).fill("Tempo 30 vor der Schule");
      await ka.getByRole("button", { name: "+ Gemeinsam" }).click();
      await expect(ka.getByRole("checkbox", { name: "Mit meiner Notiz beginnen" })).toBeChecked();
      await ka.getByRole("button", { name: "Gemeinsame Notiz anlegen" }).click();
      const feldA = ka.getByRole("textbox", { name: "Gemeinsame Notiz" });
      await expect.poll(() => ohneCursor(feldA), { timeout: 15_000 }).toBe("Tempo 30 vor der Schule");
      await expect(ka.getByText("Live", { exact: true })).toBeVisible();

      // Einladen: der Link trägt das Geheimnis im Anker.
      // Kein Dialog: Der Bereich klappt in der Karte auf, die Notiz bleibt bedienbar.
      await ka.getByRole("button", { name: "Einladen" }).click();
      await expect(anna.page.getByRole("dialog")).toHaveCount(0);
      const bereich = ka.getByRole("region", { name: "Einladen" });
      await bereich.getByRole("button", { name: "Link erstellen" }).click();
      const link = await bereich.getByRole("textbox", { name: "Einladungslink" }).inputValue();
      expect(link).toMatch(/\/notiz-einladung\?i=[\w-]+#[\w-]{43}$/);
      await expect(feldA).toBeEditable();
      await bereich.getByRole("button", { name: "Schließen" }).click();
      await expect(bereich).toHaveCount(0);
      await expect(ka.getByRole("button", { name: "Einladen" })).toBeFocused();

      // Ben öffnet den Link, richtet seine Notizen ein und tritt bei.
      await ben.page.goto(link);
      // Der Titel kommt aus der Ratsdatenbank — in der CI ist sie leer, dann „einem Tagesordnungspunkt“.
      await expect(ben.page.getByText(/Anna lädt dich ein, gemeinsam eine Notiz zu .+ zu schreiben/))
        .toBeVisible({ timeout: 15_000 });
      await expect(ben.page).not.toHaveURL(/#/);   // der Anker steht nicht mehr im Verlauf
      await notizenEinrichten(ben.page.locator("section", { has: ben.page.locator("#einladung-notizen") }));
      await ben.page.getByRole("button", { name: "Beitreten" }).click();
      await ben.page.waitForURL(/\/council\/punkt/);
      const kb = karte(ben.page);
      const feldB = kb.getByRole("textbox", { name: "Gemeinsame Notiz" });
      await expect.poll(() => ohneCursor(feldB), { timeout: 15_000 }).toBe("Tempo 30 vor der Schule");
      await expect(kb.getByRole("button", { name: "Mit Anna" })).toHaveAttribute("aria-pressed", "true");

      // Beide schreiben — jeder sieht den Text des anderen.
      await feldB.click();
      await ben.page.keyboard.press("ControlOrMeta+End");
      await ben.page.keyboard.type(" und Radweg");
      await expect.poll(() => ohneCursor(feldA), { timeout: 10_000 }).toBe("Tempo 30 vor der Schule und Radweg");
      await feldA.click();
      await anna.page.keyboard.press("ControlOrMeta+End");
      await anna.page.keyboard.press("Enter");
      await anna.page.keyboard.type("Verwaltung fragen");
      await expect(feldB).toContainText("Verwaltung fragen", { timeout: 10_000 });
      await expect(ka.getByText("Live · 1 weitere Person gerade dabei")).toBeVisible();
      // Und Anna sieht, wo Ben gerade schreibt — mit seinem Namen.
      await feldB.click();
      await expect(ka.locator(".collaboration-carets__label", { hasText: "Ben" })).toBeVisible({ timeout: 10_000 });
      await expect(ka.getByRole("button", { name: "Mit Ben" })).toBeVisible();

      // Wer neu lädt, entsperrt und landet wieder in der gemeinsamen Notiz — mit demselben Stand.
      await ben.page.reload();
      const nachher = karte(ben.page);
      const entsperren = nachher.getByRole("button", { name: "Mit Passkey entsperren" });
      if (await entsperren.isVisible({ timeout: 5_000 }).catch(() => false)) await entsperren.click();
      await expect(nachher.getByRole("textbox", { name: "Gemeinsame Notiz" })).toContainText("und Radweg", { timeout: 15_000 });
    } finally {
      await anna.ctx.close();
      await ben.ctx.close();
    }
  });

  test("per Adresse einladen: annehmen, der Schlüssel kommt von selbst", async ({ browser }) => {
    const anna = await person(browser, "Anna");
    const ben = await person(browser, "Ben");
    try {
      // Ben hat seine Notizen schon — sein Schlüsselpaar entsteht beim Annehmen.
      await ben.page.goto(URL);
      await ben.page.getByRole("tab", { name: "Meine Notiz" }).click();
      await notizenEinrichten(karte(ben.page));

      await anna.page.goto(URL);
      await anna.page.getByRole("tab", { name: "Meine Notiz" }).click();
      const ka = karte(anna.page);
      await notizenEinrichten(ka);
      await ka.getByRole("button", { name: "+ Gemeinsam" }).click();
      await ka.getByRole("button", { name: "Gemeinsame Notiz anlegen" }).click();
      const feldA = ka.getByRole("textbox", { name: "Gemeinsame Notiz" });
      await expect(ka.getByText("Live", { exact: true })).toBeVisible({ timeout: 15_000 });
      await feldA.click();
      await anna.page.keyboard.type("Nur für uns zwei");

      await ka.getByRole("button", { name: "Einladen" }).click();
      const bereich = ka.getByRole("region", { name: "Einladen" });
      await bereich.getByRole("textbox", { name: "E-Mail-Adresse" }).fill(ben.email);
      await bereich.getByRole("button", { name: "Einladen", exact: true }).click();
      await expect(bereich.getByRole("status", { name: "Eingeladen" })).toContainText(ben.email);

      // Ben sieht die Einladung an der Notiz des Punkts (ohne Zustellweg kommt keine Mail).
      await ben.page.reload();
      const kb = karte(ben.page);
      const entsperren = kb.getByRole("button", { name: "Mit Passkey entsperren" });
      if (await entsperren.isVisible({ timeout: 5_000 }).catch(() => false)) await entsperren.click();
      await expect(kb.getByText("Anna lädt dich zu dieser Notiz ein.")).toBeVisible({ timeout: 15_000 });
      await kb.getByRole("button", { name: "Annehmen" }).click();

      // Anna hat die Notiz offen: Ihr Browser übergibt den Schlüssel, Ben ist drin.
      const feldB = kb.getByRole("textbox", { name: "Gemeinsame Notiz" });
      await expect.poll(() => ohneCursor(feldB), { timeout: 20_000 }).toBe("Nur für uns zwei");
      await expect(kb.getByRole("button", { name: "Mit Anna" })).toHaveAttribute("aria-pressed", "true");
      await feldB.click();
      await ben.page.keyboard.press("ControlOrMeta+End");
      await ben.page.keyboard.type(", sagt Ben");
      await expect.poll(() => ohneCursor(feldA), { timeout: 10_000 }).toBe("Nur für uns zwei, sagt Ben");

    } finally {
      await anna.ctx.close();
      await ben.ctx.close();
    }
  });

  test("per Adresse: der Weg über die Einladungsseite aus der Mail", async ({ browser }) => {
    const anna = await person(browser, "Anna");
    const ben = await person(browser, "Ben");
    try {
      await anna.page.goto(URL);
      await anna.page.getByRole("tab", { name: "Meine Notiz" }).click();
      const ka = karte(anna.page);
      await notizenEinrichten(ka);
      await ka.getByRole("button", { name: "+ Gemeinsam" }).click();
      await ka.getByRole("button", { name: "Gemeinsame Notiz anlegen" }).click();
      await expect(ka.getByText("Live", { exact: true })).toBeVisible({ timeout: 15_000 });
      // Über die Oberfläche: Nur sie legt die Kennung verschlüsselt in die Notiz.
      await ka.getByRole("button", { name: "Einladen" }).click();
      const bereich = ka.getByRole("region", { name: "Einladen" });
      await bereich.getByRole("textbox", { name: "E-Mail-Adresse" }).fill(ben.email);
      await bereich.getByRole("button", { name: "Einladen", exact: true }).click();
      await expect(bereich.getByRole("status", { name: "Eingeladen" })).toContainText(ben.email);

      // Die Kennung stünde im Link der Mail; hier holt Ben sie sich selbst.
      const inv = (await (await ben.page.request.get("/api/shared-notes")).json()).invitations[0];
      await ben.page.goto(`/notiz-einladung?a=${inv.id}`);
      await expect(ben.page.getByText(/Anna lädt dich ein, gemeinsam eine Notiz zu .+ zu schreiben/)).toBeVisible({ timeout: 15_000 });
      await notizenEinrichten(ben.page.locator("section", { has: ben.page.locator("#einladung-notizen") }));
      await ben.page.getByRole("button", { name: "Annehmen" }).click();
      // Anna ist in der Notiz: Die Seite springt von selbst dorthin.
      await ben.page.waitForURL(/\/council\/punkt/, { timeout: 20_000 });
      await expect(karte(ben.page).getByRole("textbox", { name: "Gemeinsame Notiz" })).toBeVisible({ timeout: 15_000 });
      await expect(karte(ben.page).getByRole("button", { name: "Mit Anna" })).toHaveAttribute("aria-pressed", "true");
    } finally {
      await anna.ctx.close();
      await ben.ctx.close();
    }
  });
});
