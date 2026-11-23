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

/** Ein 1×1-JPEG — genug, damit der Browser es als Bild zeigt. */
const JPEG = "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA=";

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
    // Überschrift aus der Leiste — im Dokument ein h3, die Karte ist schon ein h2.
    await leiste.getByRole("button", { name: "Überschrift", exact: true }).click();
    await feld.pressSequentially("Haushalt 2027");
    await expect(feld.getByRole("heading", { level: 3, name: "Haushalt 2027" })).toBeVisible();
    await expect(leiste.getByRole("button", { name: "Überschrift", exact: true })).toHaveAttribute("aria-pressed", "true");
    await feld.press("Enter");
    // „## “ wie in Markdown: die kleinere.
    await feld.pressSequentially("## Fragen");
    await expect(feld.getByRole("heading", { level: 4, name: "Fragen" })).toBeVisible();
    await feld.press("Enter");
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
    await expect(feld.getByRole("heading", { level: 3, name: "Haushalt 2027" })).toBeVisible();
    await expect(feld.getByRole("heading", { level: 4, name: "Fragen" })).toBeVisible();
  });

  test("Verweis auf eine Seite der Anlage: Chip in der Notiz, und der Chat fragt zu genau dieser Stelle", async ({ page, context }) => {
    await passkeyGeraet(page, context);
    const ablage: Ablage = { keys: null, notes: new Map() };
    await schein(page, ablage);
    let koerper: Record<string, unknown> = {};
    await page.route("**/api/council/ask", async (route) => {
      koerper = JSON.parse(route.request().postData() ?? "{}");
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: [
        { type: "step", step: "answer" },
        { type: "token", text: "Auf Seite 2 fordert der VCD Tempo 30." },
        { type: "done", conversation_id: null },
      ].map((e) => `data: ${JSON.stringify(e)}\n\n`).join("") });
    });
    // Die Seitenbilder: ein winziges JPEG je Seite, die Seitenzahl vom Server.
    const seitenbilder: string[] = [];
    await page.route("**/api/council/documents/314015/pages", (r) =>
      r.fulfill({ json: { document_id: 314015, n_pages: 3 } }));
    await page.route("**/api/council/documents/314015/page/**", (r) => {
      seitenbilder.push(r.request().url().split("/documents/")[1]);
      return r.fulfill({ contentType: "image/jpeg", body: Buffer.from(JPEG, "base64") });
    });
    await page.goto(URL);
    await zurNotiz(page);
    const k = karte(page);
    await k.getByRole("button", { name: "Notizen einrichten" }).click();
    await k.getByRole("button", { name: "Mit Passkey einrichten" }).click();
    const feld = notiz(k);
    await feld.click();
    await feld.pressSequentially("Prüfen: ");

    // Unterlage wählen (die einzige ist vorausgewählt), Seite in der Vorschau
    // blättern, einfügen.
    await k.getByRole("toolbar", { name: "Formatierung" }).getByRole("button", { name: "Unterlage verweisen" }).click();
    const auswahl = k.getByRole("group", { name: "Unterlage verweisen" });
    await expect(auswahl.getByRole("radio", { name: /VCD-Antrag/ })).toBeChecked();
    await expect(auswahl.getByRole("img", { name: /^Seite 1 von „VCD-Antrag/ })).toBeVisible();
    await expect(auswahl.getByText("Seite 1 von 3")).toBeVisible();
    await auswahl.getByRole("button", { name: "Nächste Seite" }).click();
    await expect(auswahl.getByLabel(/Seite \(leer/)).toHaveValue("2");
    await expect(auswahl.getByRole("img", { name: /^Seite 2 von „VCD-Antrag/ })).toBeVisible();
    expect(seitenbilder).toEqual(["314015/page/1?w=640", "314015/page/2?w=640"]);
    // Vergrößern: groß ansehen, blättern, Esc schließt nur die Vergrößerung.
    await auswahl.getByRole("button", { name: "Seite 2 größer anzeigen" }).click();
    const gross = page.getByRole("dialog", { name: /^Seite 2 von 3/ });
    await expect(gross.getByRole("img", { name: /^Seite 2 von „VCD-Antrag/ })).toBeVisible();
    expect(seitenbilder).toContain("314015/page/2?w=1280");
    await gross.getByRole("button", { name: "Vergrößern" }).click();
    await expect(gross.getByRole("button", { name: "Ganze Seite zeigen" })).toHaveAttribute("aria-pressed", "true");
    await gross.getByRole("button", { name: "Ganze Seite zeigen" }).click();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("dialog", { name: /^Seite 3 von 3/ })).toBeVisible();
    await page.keyboard.press("ArrowLeft");
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(auswahl).toBeVisible();
    await expect(auswahl.getByLabel(/Seite \(leer/)).toHaveValue("2");
    await auswahl.getByRole("button", { name: "Einfügen" }).click();
    const chip = feld.locator("[data-doc-ref]");
    await expect(chip).toContainText("VCD-Antrag");
    await expect(chip).toContainText("S. 2");
    await expect(chip.getByRole("link")).toHaveAttribute("href", /getfile\.asp\?id=314015&type=do#page=2$/);
    // Beim Überfahren: die Seite als Bild — aus dem Zwischenspeicher, kein neuer Abruf.
    await chip.getByRole("link").hover();
    await expect(page.getByRole("tooltip").getByRole("img", { name: /^Seite 2 von „VCD-Antrag/ })).toBeVisible();
    await page.mouse.move(0, 0);
    await expect(page.getByRole("tooltip")).toHaveCount(0);
    expect(seitenbilder.filter((u) => u.endsWith("w=640"))).toHaveLength(3);

    // Im Chat fragen: Der Bezug steht über dem Feld, die Frage trägt Kennung und Seite.
    await chip.getByRole("button", { name: /^Im Chat fragen/ }).click();
    const frage = page.getByRole("textbox", { name: /Deine Frage zu Seite 2/ });
    await expect(frage).toBeFocused();
    await frage.fill("Was steht dort zu Tempo 30?");
    await frage.press("Enter");
    await expect(page.getByText("Auf Seite 2 fordert der VCD Tempo 30.")).toBeVisible();
    const refs = (koerper.screen as { refs: Record<string, unknown> }).refs;
    expect(refs).toMatchObject({ ksinr: 4654, item_number: "Ö 11.1", document_id: 314015, page: 2 });
    // Der Notiztext reist nicht mit.
    expect(JSON.stringify(koerper)).not.toContain("Prüfen");

    // Gespeichert als Text, nach dem Neuladen wieder ein Chip.
    await feld.blur();
    await expect(k.getByText(/Gespeichert um/)).toBeVisible({ timeout: 10_000 });
    await k.getByRole("button", { name: "Sperren" }).click();
    await page.reload();
    await k.getByRole("button", { name: "Mit Passkey entsperren" }).click();
    await expect(notiz(k).locator("[data-doc-ref]")).toContainText("S. 2");
  });

  test("die Auswahl der Unterlagen schiebt das Telefon nicht seitwärts", async ({ page, context }) => {
    await passkeyGeraet(page, context);
    await page.setViewportSize({ width: 320, height: 760 });
    const ablage: Ablage = { keys: null, notes: new Map() };
    await schein(page, ablage);
    await page.route("**/api/council/documents/**", (r) => r.fulfill({ status: 404, json: { detail: "—" } }));
    await page.goto(URL);
    await zurNotiz(page);
    const k = karte(page);
    await k.getByRole("button", { name: "Notizen einrichten" }).click();
    await k.getByRole("button", { name: "Mit Passkey einrichten" }).click();
    await k.getByRole("button", { name: "Unterlage verweisen" }).click();
    await expect(k.getByText("Keine Vorschau für diese Seite.")).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth))
      .toBeLessThanOrEqual(0);
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
