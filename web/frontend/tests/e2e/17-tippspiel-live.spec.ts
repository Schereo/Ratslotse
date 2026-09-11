/**
 * Der Beamer (`/tipp/live`) — ohne Konto, hinter dem Schalter `tippspiel`.
 *
 * Wie bei `15-wahlabend.spec.ts` werden `/api/app-config`, `/api/tipp/setup`
 * und `/api/tipp/stand` gemockt: In der CI ist der Schalter aus und es gibt
 * keine Tipps, ein Test gegen die echten Endpunkte wäre also blind. Die drei
 * `tipp-stand-*.json`-Fixturen sind von Hand geformt (nicht wie bei
 * `wahlabend-probe.json` aus einer echten Serverfunktion gezogen) — anders
 * als die Wahlabend-Generalprobe braucht ein realistischer Tippspiel-Stand
 * echte Spieler*innen-Zeilen in der lokalen Datenbank; das für drei feste
 * Fixturen aufzusetzen wäre brüchiger als sie direkt gegen die
 * `PredictionStand`-Form in `antworten.py` zu schreiben.
 *
 * Fixtur-Geschichte: `open` (vor dem ersten Ergebnis) → `a` (Clara auf
 * Platz 3) → `b` (Clara auf Platz 1, Anna und Ben je einen Platz runter —
 * ihr Chip sagt „+2"/„−1", die Führung wechselt).
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

function fixture(name: string) {
  return JSON.parse(readFileSync(path.join(__dirname, "fixtures", `tipp-stand-${name}.json`), "utf8"));
}
const SETUP = JSON.parse(readFileSync(path.join(__dirname, "fixtures", "tipp-setup.json"), "utf8"));
const STAND_OPEN = fixture("open");
const STAND_A = fixture("a");
const STAND_B = fixture("b");

async function appConfig(page: Page, features: string[]) {
  await page.route("**/api/app-config", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ min_build: 0, note: null, features }),
    }),
  );
}

async function setupMock(page: Page) {
  await page.route("**/api/tipp/setup", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SETUP) }));
}

/** Liefert `zuerst` beim ersten Aufruf, danach immer `danach` (Default:
 *  derselbe Stand) — für den Übergang von einem Stand zum nächsten OHNE
 *  Reload, so wie die Seite ihn im Betrieb über `refetchInterval` erlebt. */
function standMock(page: Page, zuerst: unknown, danach: unknown = zuerst) {
  let rufe = 0;
  page.route("**/api/tipp/stand", (route) => {
    rufe += 1;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(rufe === 1 ? zuerst : danach),
    });
  });
}

test.describe("Schalter aus", () => {
  test("die Seite sagt Bescheid", async ({ page }) => {
    await appConfig(page, []);
    await page.goto("/tipp/live");
    await expect(page.getByRole("heading", { name: /noch nicht freigeschaltet/ })).toBeVisible();
  });
});

test.describe("Schalter an", () => {
  test.beforeEach(async ({ page }) => {
    await appConfig(page, ["tippspiel"]);
    await setupMock(page);
  });

  test("vor dem ersten Ergebnis zeigt die Seite den QR-Code", async ({ page }) => {
    standMock(page, STAND_OPEN);
    await page.goto("/tipp/live");
    await expect(page.getByText("ratslotse.de/tipp")).toBeVisible();
    await expect(page.getByRole("img", { name: /QR-Code/ })).toBeVisible();
    // Kein Podium, solange nichts ausgezählt ist.
    await expect(page.getByText("Anna")).toHaveCount(0);
  });

  test("ab dem ersten Stand erscheint das Podium mit allen drei Namen", async ({ page }) => {
    standMock(page, STAND_A);
    await page.goto("/tipp/live?ansicht=rangliste");
    const podium = page.locator(".grid.grid-cols-3 > div");
    await expect(podium).toHaveCount(3);
    await expect(podium.nth(1)).toContainText("Anna"); // Mitte = Platz 1
    await expect(podium.nth(0)).toContainText("Ben"); // links = Platz 2
    await expect(podium.nth(2)).toContainText("Clara"); // rechts = Platz 3
  });

  test("die Vergleichs-Ansicht zeigt die Liste und den Server-Satz", async ({ page }) => {
    standMock(page, STAND_A);
    await page.goto("/tipp/live?ansicht=vergleich");
    await expect(page.getByText(/Die Runde hat die CDU/)).toBeVisible();
    // exact:true — sonst matcht auch die SVG-<title> "… Mehrheit ab 27 von 52
    // Sitzen." (Playwright-Textsuche ist standardmäßig ein Teilstring-Test).
    await expect(page.getByText("52 Sitze", { exact: true })).toBeVisible();
  });

  // Das Projekt fährt Playwright global mit `reducedMotion: "reduce"`
  // (Determinismus für alle anderen Tests) — `ConfettiBurst` verweigert sich
  // dem BEWUSST (components/confetti.tsx). Für den einen Test, der genau
  // dieses Feature prüft, wird die Bewegung hier gezielt wieder erlaubt.
  test.describe("Führungswechsel (mit Bewegung)", () => {
    test.use({ reducedMotion: "no-preference" });

    test("rückt die neue Nummer eins ins Podium-Zentrum, ihr Chip sagt +2 und Konfetti läuft", async ({ page }) => {
      test.setTimeout(60_000);
      standMock(page, STAND_A, STAND_B);
      await page.goto("/tipp/live?ansicht=rangliste");
      await expect(page.locator(".grid.grid-cols-3 > div").nth(1)).toContainText("Anna");

      // Eine echte Hochrechnung wechselt den Stand NIE per Reload — die Seite
      // bleibt offen und pollt weiter. Ein Reload würde Podiums eigene „nicht
      // beim ersten Rendern"-Sperre zurücksetzen und nie feiern — genau die
      // Sperre, die verhindert, dass jeder Seitenaufruf Konfetti zeigt. Deshalb
      // hier auf die zweite Antwort von `/api/tipp/stand` warten (den echten
      // Poll-Takt, 30 s bei vorliegendem Ergebnis) statt neu zu laden.
      await page.waitForResponse((r) => r.url().includes("/api/tipp/stand") && r.status() === 200, { timeout: 40_000 });

      // Ab hier läuft `ConfettiBurst` nur 3,2 s (components/confetti.tsx) — eng
      // pollen (50 ms), nicht über `expect()`s eigenen, gröberen Rhythmus,
      // sonst ist das Fenster beim Prüfen manchmal schon vorbei.
      const konfettiGesehen = await page
        .waitForFunction(() => document.querySelector(".animate-confetti-fall") !== null, null, { timeout: 3500, polling: 50 })
        .then(() => true)
        .catch(() => false);
      expect(konfettiGesehen, "Konfetti wurde nach dem Führungswechsel nie im DOM gefunden").toBe(true);

      await expect(page.locator(".grid.grid-cols-3 > div").nth(1)).toContainText("Clara");
      await expect(page.locator(".grid.grid-cols-3 > div").nth(1)).toContainText("+2");
    });
  });

  test("kein seitliches Scrollen mit echten Daten (Handy)", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    standMock(page, STAND_A);
    for (const ansicht of ["qr", "vergleich", "rangliste"]) {
      await page.goto(`/tipp/live?ansicht=${ansicht}`, { waitUntil: "networkidle" });
      const zuviel = await page.evaluate(() => {
        const d = document.documentElement;
        return Math.max(0, d.scrollWidth - d.clientWidth);
      });
      const schuldige = await page.evaluate(() => {
        const breite = document.documentElement.clientWidth;
        const aus: string[] = [];
        for (const el of Array.from(document.querySelectorAll("body *"))) {
          const r = (el as HTMLElement).getBoundingClientRect();
          if (r.width === 0 || r.height === 0) continue;
          if (r.right > breite + 1) {
            aus.push(`${el.tagName.toLowerCase()}.${(el.className as string || "").toString().split(/\s+/).slice(0, 4).join(".")} (bis ${Math.round(r.right)}px, Fenster ${breite}px)`);
          }
        }
        return aus.slice(0, 8);
      });
      expect(zuviel, `?ansicht=${ansicht} ist ${zuviel}px zu breit. Schuldige:\n  ` + schuldige.join("\n  ")).toBeLessThanOrEqual(1);
    }
  });

  test("Regel 3: Erstbesuch ist dunkel, Hellmodus zeigt keine dunkle Kachel", async ({ page }) => {
    standMock(page, STAND_A);
    // Kein `localStorage`-Zugriff VOR der ersten Navigation — die Seite steht
    // noch auf `about:blank`, das hat keinen Origin, den `localStorage`
    // ansprechen könnte. Ein frischer Playwright-Kontext hat ohnehin noch
    // keinen gespeicherten Wert, das Entfernen war also nur zur Sicherheit.
    await page.goto("/tipp/live?ansicht=vergleich");
    await expect.poll(() => page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(true);

    // Auf Hell umstellen (wie ein Klick auf den Schalter) und neu ansehen.
    await page.evaluate(() => localStorage.setItem("theme", "light"));
    await page.reload({ waitUntil: "networkidle" });
    expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(false);

    // Die `.hh-tafel`-Fläche (Server-Satz-Kachel) darf im Hellen nicht dunkel
    // sein — Tims stehende Regel „Anzeigetafel-Tönung, nie Tiefsee im Hellen".
    const helligkeit = await page.evaluate(() => {
      const el = document.querySelector(".hh-tafel");
      if (!el) return null;
      const bg = getComputedStyle(el).backgroundColor;
      const [r, g, b] = bg.match(/[\d.]+/g)!.map(Number);
      return (r * 299 + g * 587 + b * 114) / 1000; // Wahrgenommene Helligkeit, 0–255.
    });
    expect(helligkeit, "die Anzeigetafel ist im Hellmodus dunkel").toBeGreaterThan(128);
  });
});

test.describe("Generalprobe", () => {
  test("reicht probe/counted an den Abruf weiter und schildert sich aus", async ({ page }) => {
    // Ohne das Weiterreichen trüge nur die Browser-Adresse die Probe, der
    // Abruf dahinter zeigte den Live-Stand — auf einem Beamer der denkbar
    // schlechteste Irrtum.
    await appConfig(page, ["tippspiel"]);
    await setupMock(page);
    const gesehen: string[] = [];
    await page.route("**/api/tipp/stand**", (route) => {
      gesehen.push(new URL(route.request().url()).search);
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(STAND_A) });
    });

    await page.goto("/tipp/live?probe=2021&counted=40");
    await expect(page.getByText("Generalprobe · Zahlen von 2021")).toBeVisible();
    expect(gesehen[0]).toBe("?probe=2021&counted=40");
  });

  test("ohne Parameter fragt der Beamer den Live-Stand ab", async ({ page }) => {
    await appConfig(page, ["tippspiel"]);
    await setupMock(page);
    const gesehen: string[] = [];
    await page.route("**/api/tipp/stand**", (route) => {
      gesehen.push(new URL(route.request().url()).search);
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(STAND_A) });
    });

    await page.goto("/tipp/live");
    await expect(page.getByText("Generalprobe · Zahlen von 2021")).toBeHidden();
    expect(gesehen[0]).toBe("");
  });
});
