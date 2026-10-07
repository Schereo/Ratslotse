import { test, expect, type Page } from "@playwright/test";
import { zustandsDatei } from "./konten";

/**
 * „Neu bei Ratslotse": Video-Kacheln und Story-Spieler (seit 3.0.0).
 *
 * Die Karte erscheint nur Konten, die ÄLTER sind als das Release
 * (`kern/releases.py::pending_for`) — die Konten der Suite sind frisch und
 * sähen sie nie. Die Antwort von `GET /news` ist deshalb gestellt; die Clips
 * selbst sind die echten Dateien aus `public/neuigkeiten/3.0.0/`.
 */

test.use({ storageState: zustandsDatei("nutzerin") });

const medium = (name: string, sekunden: number) => ({
  kind: "video", src: `/neuigkeiten/3.0.0/${name}.mp4`, alt: `Clip ${name}, ein paar Sätze lang beschrieben.`,
  aspect: "16/9", poster: `/neuigkeiten/3.0.0/${name}.webp`, cover: `/neuigkeiten/3.0.0/${name}.webp`, duration: sekunden,
});
const NEWS = {
  releases: [{
    version: "3.0.0", date: "2026-10-06", title: "Das Lotti-Update",
    teaser: "Drei neue Wege durch den Rat — je ein kurzes Video.",
    highlights: [
      { title: "Lotti erklärt dir, was du siehst", text: "Tipp auf Lotti unten rechts.", url: "/council",
        media: medium("lotti", 20), color: "signal", aside: false, tagline: "Tipp auf die Möwe.", action: "Lotti ausprobieren" },
      { title: "Mein Viertel", text: "Gib deine Straße ein.", url: "/karte",
        media: medium("viertel", 17.5), color: "green", aside: false, tagline: "Was sich vor deiner Haustür tut.", action: "Mein Viertel ausprobieren" },
      { title: "Ideen aus anderen Städten", text: "Was haben andere Räte beschlossen?", url: "/council/ideen",
        media: medium("ideen", 19.6), color: "primary", aside: false, tagline: "Was andere Räte schon beschlossen haben.", action: "Ideen entdecken" },
      { title: "Frag den Rat liest den ganzen Vorgang", text: "Zeitleiste und Eckdaten.", url: "/fragen",
        media: medium("akte", 20.7), color: "primary", aside: true, tagline: "Zeitleiste und Eckdaten unter jeder Antwort.", action: "Frag den Rat ausprobieren" },
    ],
  }],
  older_count: 0,
  seen_version: null,
};

/** Stellt `/news`, hält die Erste-Schritte-Leiste fern (sie stünde im
 *  Hinweis-Slot vor der Karte) und zählt, was an `/news/seen` geht. Wie der
 *  Server: Nach der Meldung ist die Ausgabe erledigt, `/news` liefert nichts
 *  mehr. */
async function stellen(page: Page): Promise<string[]> {
  const gemeldet: string[] = [];
  await page.route("**/api/news", (route) => route.fulfill({
    json: gemeldet.length ? { releases: [], older_count: 0, seen_version: "3.0.0" } : NEWS,
  }));
  await page.route("**/api/news/seen", (route) => {
    gemeldet.push((route.request().postDataJSON() as { version: string }).version);
    return route.fulfill({ json: { seen_version: "3.0.0" } });
  });
  await page.route("**/api/onboarding", (route) =>
    route.request().method() === "GET"
      ? route.fulfill({ json: { steps: ["frag", "beschluesse", "analyse", "karten"], celebrated: true } })
      : route.continue());
  // Sitzungspause und laufende Sitzung stehen im Hinweis-Slot VOR der Karte.
  // Kommt eine davon erst nach dem Aufklappen an, rutscht die Karte zurück in
  // die Pille (gemessen gegen die leere Ratsdatenbank: Pause aktiv).
  await page.route("**/api/council/session-break", (route) => route.fulfill({ json: { active: false } }));
  await page.route("**/api/council/sessions?scope=upcoming&limit=6", (route) => route.fulfill({ json: { sessions: [] } }));
  await page.addInitScript(() => {
    try { localStorage.removeItem("ratslotse.neuigkeiten.gesehen.3.0.0"); } catch { /* egal */ }
  });
  return gemeldet;
}

/** Die Karte — notfalls aus der Pille des Hinweis-Slots geholt (eine
 *  laufende Sitzung oder die Sitzungspause stehen vor ihr). */
async function karte(page: Page) {
  await page.goto("/dashboard");
  const titel = page.locator("main").getByRole("heading", { name: "Das Lotti-Update" });
  const pille = page.locator("main").getByRole("button", { name: /^Neu bei Ratslotse/ });
  await expect(titel.or(pille).first()).toBeVisible();
  if (!(await titel.isVisible())) await pille.click();
  await expect(titel).toBeVisible();
  return titel.locator("xpath=ancestor::div[contains(@class,'@container')][1]");
}

const spieler = (page: Page) => page.getByRole("dialog");

test("Kacheln öffnen den Spieler; Pfeile blättern, Esc gibt den Fokus zurück", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await stellen(page);
  const k = await karte(page);
  await expect(k.getByRole("button", { name: /^Video ansehen:/ })).toHaveCount(3);
  await expect(k.getByRole("button", { name: /Mein Viertel, 18 Sekunden/ })).toBeVisible();
  await expect(k).toContainText("0 von 3 angesehen");

  const kachel = k.getByRole("button", { name: /Video ansehen: Mein Viertel/ });
  await kachel.click();
  await expect(spieler(page).getByRole("heading", { name: "2 von 3 · Mein Viertel" })).toBeVisible();
  await expect(spieler(page).getByRole("link", { name: /Mein Viertel ausprobieren/ })).toHaveAttribute("href", "/karte");

  await page.keyboard.press("ArrowRight");
  await expect(spieler(page).getByRole("heading", { name: "3 von 3 · Ideen aus anderen Städten" })).toBeVisible();
  // Auf dem letzten wird aus „Weiter" ein „Fertig".
  await expect(spieler(page).getByRole("button", { name: "Fertig" })).toBeVisible();
  await page.keyboard.press("ArrowLeft");
  await expect(spieler(page).getByRole("heading", { name: /^2 von 3/ })).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(spieler(page)).toHaveCount(0);
  await expect(kachel).toBeFocused();
  await expect(k).toContainText("2 von 3 angesehen");
  await expect(kachel).toHaveAccessibleName(/schon angesehen/);
});

test("mit reduzierter Bewegung: Standbild statt Autoplay, am Ende kein Weiter", async ({ page }) => {
  // Die Suite läuft zwar mit `reducedMotion: "reduce"` (playwright.config.ts),
  // aber ausdrücklich gesetzt hängt der Test nicht an der Konfiguration —
  // dieselbe Vorsicht wie in 18-heute-widget.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1280, height: 900 });
  await stellen(page);
  const k = await karte(page);
  expect(await page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches)).toBe(true);
  await k.getByRole("button", { name: /Video ansehen: Lotti/ }).click();
  const video = spieler(page).locator("video");
  await expect(spieler(page).getByRole("button", { name: "Abspielen" }).first()).toBeVisible();
  await page.waitForTimeout(800);
  expect(await video.evaluate((v: HTMLVideoElement) => v.paused)).toBe(true);

  // Selbst gestartet und bis ans Ende gespult: Es bleibt bei Lotti.
  await spieler(page).getByRole("button", { name: "Abspielen" }).first().click();
  await video.evaluate(async (v: HTMLVideoElement) => {
    await new Promise((r) => (v.readyState >= 1 ? r(null) : v.addEventListener("loadedmetadata", () => r(null), { once: true })));
    v.currentTime = Math.max(0, v.duration - 0.3);
  });
  await expect(spieler(page).getByRole("button", { name: "Noch einmal ansehen" })).toBeVisible({ timeout: 10_000 });
  await expect(spieler(page).getByRole("heading", { name: /^1 von 3/ })).toBeVisible();
});

test.describe("mit Bewegung", () => {
  test.use({ reducedMotion: "no-preference" });

  test("am Ende eines Clips kommt der nächste", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await stellen(page);
    const k = await karte(page);
    await k.getByRole("button", { name: /Video ansehen: Lotti/ }).click();
    const video = spieler(page).locator("video");
    await video.evaluate(async (v: HTMLVideoElement) => {
      await new Promise((r) => (v.readyState >= 1 ? r(null) : v.addEventListener("loadedmetadata", () => r(null), { once: true })));
      v.currentTime = Math.max(0, v.duration - 0.3);
      await v.play().catch(() => {});
    });
    await expect(spieler(page).getByRole("heading", { name: "2 von 3 · Mein Viertel" })).toBeVisible({ timeout: 10_000 });
  });
});

test("alle angesehen setzt die Marke; die Karte bleibt für diesen Besuch, × blendet aus", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const gemeldet = await stellen(page);
  const k = await karte(page);
  await k.getByRole("button", { name: /Video ansehen: Lotti/ }).click();
  await page.keyboard.press("ArrowRight");
  expect(gemeldet).toEqual([]);
  await page.keyboard.press("ArrowRight");
  await expect.poll(() => gemeldet).toEqual(["3.0.0"]);
  await page.keyboard.press("Escape");
  // Nicht unter dem schließenden Spieler weggesprungen:
  await expect(k).toContainText("3 von 3 angesehen");

  await k.getByRole("button", { name: "Neuigkeiten ausblenden" }).click();
  await expect(page.locator("main").getByRole("heading", { name: "Das Lotti-Update" })).toHaveCount(0);
  expect(gemeldet).toEqual(["3.0.0", "3.0.0"]);
});

test("„Außerdem“ öffnet seinen Clip allein und zählt nicht zum Fortschritt", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await stellen(page);
  const k = await karte(page);
  await k.getByRole("button", { name: /Außerdem: Frag den Rat liest den ganzen Vorgang/ }).click();
  await expect(spieler(page).getByRole("heading", { name: "Außerdem · Frag den Rat liest den ganzen Vorgang" })).toBeVisible();
  await expect(spieler(page).getByRole("button", { name: "Zurück" })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(k).toContainText("0 von 3 angesehen");
});

test.describe("am Telefon", () => {
  test.use({ hasTouch: true, viewport: { width: 375, height: 812 } });

  test("Karussell ohne Seitwärts-Scroll; Tipp rechts blättert weiter", async ({ page }) => {
    await stellen(page);
    const k = await karte(page);
    // Die Kacheln laufen im Karussell, die SEITE bleibt in der Breite.
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    const leiste = k.getByRole("list", { name: "Neuerungen dieser Ausgabe" });
    expect(await leiste.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(true);

    await k.getByRole("button", { name: /Video ansehen: Lotti/ }).tap();
    await expect(spieler(page).getByRole("heading", { name: /^1 von 3/ })).toBeVisible();
    const buehne = await spieler(page).locator("video").locator("xpath=ancestor::div[contains(@class,'touch-none')][1]").boundingBox();
    if (!buehne) throw new Error("Bühne ohne Maße");
    await page.touchscreen.tap(buehne.x + buehne.width - 20, buehne.y + buehne.height / 2);
    await expect(spieler(page).getByRole("heading", { name: /^2 von 3/ })).toBeVisible();
    await page.touchscreen.tap(buehne.x + 20, buehne.y + buehne.height / 2);
    await expect(spieler(page).getByRole("heading", { name: /^1 von 3/ })).toBeVisible();
  });
});
