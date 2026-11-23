/**
 * Barrierefreiheit als Wächter: axe-core (WCAG 2.2 AA + Best Practices) auf
 * den Hauptseiten, hell und dunkel — und eine Prüfung, die axe nicht kann:
 * Verschwindet ein fokussiertes Element unter einer festen Leiste?
 *
 * Entstanden aus der Prüfung 11/2026: 80 Kontrastfehler, 17 Links nur per
 * Farbe, 62 zu kleine Tippflächen, fehlende Landmarken — alle behoben, und
 * ohne Wächter in drei Monaten wieder da. Der Test verlangt NULL Befunde.
 *
 * **Bewusste Ausnahmen stehen am Element**, nicht hier: `data-a11y-ausnahme=
 * "target-size"` an der Haushalts-Leiste, mit Begründung in
 * `a11y-ausnahmen.json`. Ein Befund zählt nicht, wenn sein Element oder ein
 * Vorfahr die Regel so ausnimmt. `tests/test_a11y_ausnahmen.py` hält beide
 * Richtungen (keine Markierung ohne Begründung, keine Begründung ohne
 * Markierung).
 *
 * **Leere Ratsdatenbank in der CI**: Detailseiten werden nur geprüft, wenn
 * `/council` einen Link darauf zeigt — lokal mit Abzug also mehr Seiten als in
 * der CI. Beides muss grün sein; vor dem Push einmal gegen leer laufen lassen
 * (s. web/frontend/CLAUDE.md).
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { zustandsDatei } from "./konten";

const AXE = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const AUSNAHMEN: Record<string, string> = JSON.parse(
  fs.readFileSync(path.join(__dirname, "a11y-ausnahmen.json"), "utf8"));
const REGELN = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"];

const OFFEN = ["/", "/login", "/register", "/hilfe", "/impressum", "/datenschutz",
  "/barrierefreiheit", "/changelog", "/forgot-password"];
const ANGEMELDET = ["/dashboard", "/council", "/council?tab=sessions", "/fragen",
  "/topics", "/abos", "/bookmarks", "/account", "/quiz", "/council/ideen",
  "/council/neuer-rat", "/council/decision?id=999999"];
const HAUSHALT = ["/haushalt", "/haushalt/schulden", "/haushalt/einnahmen"];

type Befund = { regel: string; hilfe: string; ziel: string; html: string };

async function axeBefunde(page: Page): Promise<Befund[]> {
  // Erscheinungen, die erst einblenden, würden mitten im Übergang gemessen.
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(400);
  await page.addScriptTag({ content: AXE });
  return page.evaluate(async ({ regeln, ausnahmen }) => {
    // @ts-expect-error — axe hängt sich ans Fenster.
    const r = await window.axe.run(document, { runOnly: { type: "tag", values: regeln } });
    const befunde: { regel: string; hilfe: string; ziel: string; html: string }[] = [];
    for (const v of r.violations) {
      for (const n of v.nodes) {
        const sel = n.target[0];
        const el = typeof sel === "string" ? document.querySelector(sel) : null;
        const ausgenommen = ausnahmen.includes(v.id) && el
          && el.closest(`[data-a11y-ausnahme~="${v.id}"]`);
        if (!ausgenommen) {
          befunde.push({ regel: v.id, hilfe: v.help, ziel: n.target.join(" "), html: n.html.slice(0, 160) });
        }
      }
    }
    return befunde;
  }, { regeln: REGELN, ausnahmen: Object.keys(AUSNAHMEN).filter((k) => !k.startsWith("_")) });
}

function meldung(seite: string, befunde: Befund[]): string {
  return `${befunde.length} Befund(e) auf ${seite}:\n` + befunde.slice(0, 8)
    .map((b) => `  [${b.regel}] ${b.hilfe}\n      ${b.ziel}\n      ${b.html}`).join("\n")
    + "\nBewusste Ausnahme? data-a11y-ausnahme am Element + Begründung in tests/e2e/a11y-ausnahmen.json.";
}

async function pruefeSeiten(page: Page, seiten: string[]) {
  for (const schema of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: schema });
    for (const seite of seiten) {
      await page.goto(seite);
      const befunde = await axeBefunde(page);
      expect.soft(befunde, meldung(`${seite} (${schema})`, befunde)).toEqual([]);
    }
  }
}

/** Detailseiten, auf die `/council` gerade zeigt — leer in der CI. */
async function detailSeiten(page: Page): Promise<string[]> {
  await page.goto("/council");
  await page.waitForLoadState("networkidle");
  const links = await page.locator("a[href^='/council/']").evaluateAll(
    (as) => as.map((a) => a.getAttribute("href") ?? ""));
  const nimm = (praefix: string) => links.find((h) => h.startsWith(praefix));
  return ["/council/decision?", "/council/sitzung?", "/council/person?", "/council/thema?"]
    .map(nimm).filter((h): h is string => !!h);
}

test.describe("axe: öffentliche Seiten", () => {
  test("ohne Befund, hell und dunkel", async ({ page }) => {
    test.setTimeout(120_000);
    await pruefeSeiten(page, OFFEN);
  });
});

test.describe("axe: angemeldet", () => {
  test.use({ storageState: zustandsDatei("nutzerin") });

  test("Hauptseiten ohne Befund, hell und dunkel", async ({ page }) => {
    test.setTimeout(180_000);
    await pruefeSeiten(page, ANGEMELDET);
  });

  test("Detailseiten ohne Befund (nur mit Daten)", async ({ page }) => {
    test.setTimeout(120_000);
    const seiten = await detailSeiten(page);
    test.skip(seiten.length === 0, "Leere Ratsdatenbank — keine Detailseite erreichbar.");
    await pruefeSeiten(page, seiten);
  });
});

test.describe("axe: Haushalt", () => {
  test.use({ storageState: zustandsDatei("ratsfrau") });

  test("ohne Befund, hell und dunkel", async ({ page }) => {
    test.setTimeout(120_000);
    await pruefeSeiten(page, HAUSHALT);
  });
});

/**
 * WCAG 2.4.11 „Fokus nicht verdeckt": Mit Tab scrollt der Browser das nächste
 * Element nur so weit herein, dass es an der Fensterkante steht — auf dem
 * Telefon liegt dort die feste Tab-Leiste. Gemessen 11/2026: auf sechs von
 * neun Seiten verschwand das fokussierte Element ganz darunter. Abhilfe:
 * `scroll-padding-bottom` und `:focus-visible { scroll-margin-top }` in
 * app/globals.css.
 *
 * Geprüft wird an fünf Punkten des Elements, ob dort etwas ANDERES liegt.
 * SVG-Elemente (Diagramm-Balken) zählen nicht: Über ihnen liegt absichtlich
 * eine durchsichtige Fangfläche für Zeiger.
 */
test.describe("Fokus nicht verdeckt (390 px)", () => {
  test.use({ storageState: zustandsDatei("nutzerin"), viewport: { width: 390, height: 844 }, hasTouch: true });

  for (const seite of ["/dashboard", "/council", "/fragen", "/account", "/topics"]) {
    test(`${seite}: kein fokussiertes Element liegt ganz unter einer Leiste`, async ({ page }) => {
      await page.goto(seite);
      await page.waitForLoadState("networkidle");
      const verdeckt: string[] = [];
      for (let i = 0; i < 60; i++) {
        await page.keyboard.press("Tab");
        const v = await page.evaluate(() => {
          const e = document.activeElement;
          if (!e || e === document.body || e instanceof SVGElement) return null;
          const b = e.getBoundingClientRect();
          if (b.width < 4 || b.height < 4) return null;
          const punkte = [[0.5, 0.5], [0.15, 0.2], [0.85, 0.2], [0.15, 0.8], [0.85, 0.8]];
          let zu = 0;
          let wer = "";
          for (const [fx, fy] of punkte) {
            const x = b.left + b.width * fx;
            const y = b.top + b.height * fy;
            if (x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) { zu++; wer ||= "außerhalb des Fensters"; continue; }
            const h = document.elementFromPoint(x, y);
            if (h && !e.contains(h) && !h.contains(e)) {
              zu++;
              wer ||= `${h.tagName.toLowerCase()}.${String(h.className).split(/\s+/).slice(0, 3).join(".")}`;
            }
          }
          if (zu < punkte.length) return null;
          const name = (e.getAttribute("aria-label") || (e as HTMLElement).innerText || "").trim().slice(0, 40);
          return `${e.tagName.toLowerCase()} „${name}" unter ${wer}`;
        });
        if (v) verdeckt.push(v);
      }
      expect(verdeckt, `Fokussiert, aber verdeckt:\n  ${verdeckt.slice(0, 6).join("\n  ")}`).toEqual([]);
    });
  }
});
