/**
 * Lotti als Assistentin: Markieren statt Modus, die Vollbild-Abläufe und die
 * geführte Tour — bis 11/2026 der hintere Teil von
 * `21-lotti-assistentin.spec.ts` (warum geteilt, steht dort im Kopf).
 *
 * Der Erklär-Strom ist gestubbt (`lotti-helpers.ts`), und alles läuft gegen
 * die LEERE Ratsdatenbank der CI.
 */
import { expect, test, type Page } from "@playwright/test";

import { zustandsDatei } from "./konten";
import {
  ANTWORT, STROM, schalterAn, stromStubben, knopf, fenster,
} from "./lotti-helpers";

/**
 * „Markieren statt Modus" (Tim, 23.09.2026): Wer Text markiert, bekommt an
 * der Markierung einen Knopf „Lotti fragen"; ein Klick öffnet das Fenster und
 * stellt sofort „Was bedeutet das?" — mit der Markierung als Zitat.
 *
 * **Der Text ist ein eigener Absatz**, kein Seiteninhalt: Die CI-Ratsdatenbank
 * ist leer, und was dort auf einer Seite steht, hängt an Daten. Ein fester
 * Absatz prüft die Mechanik überall gleich; wie es mit echten Zahlen aussieht,
 * zeigen die Bilder im PR.
 */
const markierKnopf = (page: Page) => page.locator("[data-lotti-markierknopf]");
const PROBE = "Im Haushalt 2026 stehen 391,5 Mio. € an Aufwendungen.";

async function probeAbsatz(page: Page, opts: { anker?: boolean; text?: string } = {}) {
  await page.evaluate(({ anker, text }) => {
    document.getElementById("markier-probe")?.remove();
    const p = document.createElement("p");
    p.id = "markier-probe";
    p.textContent = text;
    if (anker) {
      p.setAttribute("data-erklaer", "test.probe");
      p.setAttribute("data-erklaer-titel", "Probe-Baustein");
    }
    // Fest oben links: Auf keiner Seite liegt der Knopf oder das Fenster
    // darüber, und kein Nachladen verschiebt ihn.
    Object.assign(p.style, {
      position: "fixed", top: "140px", left: "16px", maxWidth: "340px", zIndex: "30",
      background: "white", color: "black", padding: "8px", fontSize: "16px",
      lineHeight: "1.5", maxHeight: "200px", overflow: "hidden",
    });
    document.body.appendChild(p);
  }, { anker: opts.anker ?? false, text: opts.text ?? PROBE });
}

/** Markiert `teil` im Probe-Absatz (ohne Teil: alles). Programmatisch, also
 *  OHNE Zeiger — genau der Weg, den eine Langdruck-Auswahl am Handy nimmt:
 *  nur `selectionchange`, kein `pointerup`. */
async function markiere(page: Page, teil?: string) {
  await page.evaluate((teil) => {
    const t = document.getElementById("markier-probe")!.firstChild as Text;
    const i = teil ? t.data.indexOf(teil) : 0;
    const r = document.createRange();
    r.setStart(t, i);
    r.setEnd(t, teil ? i + teil.length : t.data.length);
    const sel = document.getSelection()!;
    sel.removeAllRanges();
    sel.addRange(r);
  }, teil ?? null);
}

async function auswahlBox(page: Page) {
  return page.evaluate(() => {
    const r = document.getSelection()!.getRangeAt(0).getBoundingClientRect();
    return { x: r.x, y: r.y, width: r.width, height: r.height };
  });
}

test.describe("Markieren statt Modus", () => {
  test.use({ storageState: zustandsDatei("ratsfrau") });

  test.beforeEach(async ({ page }) => {
    await schalterAn(page);
  });

  test("markieren → Knopf unter der Markierung → Fenster fragt mit Zitat", async ({ page }) => {
    let geschickt: Record<string, unknown> | null = null;
    await page.route("**/api/council/explain", async (route) => {
      geschickt = route.request().postDataJSON();
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM() });
    });
    await page.goto("/dashboard");
    await expect(knopf(page)).toBeVisible();
    await probeAbsatz(page, { anker: true });
    await markiere(page, "391,5 Mio. €");

    await expect(markierKnopf(page)).toBeVisible();
    await expect(markierKnopf(page)).toContainText("Lotti fragen");
    // Unter dem Ende der Markierung, nicht über dem Text — und im Fenster.
    const auswahl = await auswahlBox(page);
    const box = (await markierKnopf(page).boundingBox())!;
    expect(box.y).toBeGreaterThanOrEqual(auswahl.y + auswahl.height);
    expect(box.y - (auswahl.y + auswahl.height)).toBeLessThan(40);
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(1280);

    await markierKnopf(page).click();
    await expect(fenster(page)).toBeVisible();
    await expect(markierKnopf(page)).toHaveCount(0);
    await expect(fenster(page).locator("[data-lotti-frage]").last())
      .toHaveText("„391,5 Mio. €“ — Was bedeutet das?");
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();

    const body = geschickt as unknown as {
      question: string; selection: string; heading: string;
      element: { key: string; title: string; text: string } | null;
    };
    expect(body.question).toBe("Was bedeutet das?");
    // Die Markierung geht IN IHRER ZEILE mit, der markierte Teil zwischen
    // »…« — das Zitat im Verlauf (oben) bleibt der markierte Text allein.
    expect(body.selection).toBe("Im Haushalt 2026 stehen »391,5 Mio. €« an Aufwendungen.");
    // Der Baustein, in dem die Markierung liegt, geht als Kontext mit.
    expect(body.element?.key).toBe("test.probe");
    expect(body.element?.text).toContain("Aufwendungen");
  });

  test("ohne Baustein drumherum geht nur die Markierung mit — nichts Geratenes", async ({ page }) => {
    let geschickt: Record<string, unknown> | null = null;
    await page.route("**/api/council/explain", async (route) => {
      geschickt = route.request().postDataJSON();
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM() });
    });
    await page.goto("/dashboard");
    await probeAbsatz(page);
    await markiere(page, "Aufwendungen");
    await markierKnopf(page).click();
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
    const body = geschickt as unknown as { selection: string; element: unknown };
    expect(body.selection).toBe("Im Haushalt 2026 stehen 391,5 Mio. € an »Aufwendungen«.");
    expect(body.element).toBeNull();
  });

  test("in einer Listenzeile geht die ZEILE mit — nicht nur die drei Wörter", async ({ page }) => {
    // Review zu #1517: Im Baustein „Kredite und Zinsen" stehen zwei Kredite
    // über 8,0 Mio. €. Markiert war der aus dem Mai; ohne die Zeile erklärte
    // Lotti den anderen. Die Zeile ist dort eine Flex-`li` mit zwei `span` —
    // OHNE Leerzeichen dazwischen im Quelltext; `Range.toString()` hätte
    // „8,0 Mio. €3,43 %" daraus gemacht.
    let geschickt: { selection: string } | null = null;
    await page.route("**/api/council/explain", async (route) => {
      geschickt = route.request().postDataJSON();
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM() });
    });
    await page.goto("/dashboard");
    await expect(knopf(page)).toBeVisible();
    await page.evaluate(() => {
      const ul = document.createElement("ul");
      ul.id = "markier-liste";
      Object.assign(ul.style, {
        position: "fixed", top: "140px", left: "16px", width: "520px", zIndex: "30",
        background: "white", color: "black", padding: "8px", fontSize: "14px",
      });
      for (const [a, b] of [["Mai 2026 · Bäderbetrieb Oldenburg · 8,0 Mio. €", "3,43 %"],
        ["Juni 2026 · Bäderbetrieb Oldenburg · 8,0 Mio. €", "3,46 %"]]) {
        const li = document.createElement("li");
        li.style.display = "flex";
        li.style.justifyContent = "space-between";
        const s1 = document.createElement("span");
        s1.textContent = a;
        const s2 = document.createElement("span");
        s2.textContent = b;
        li.append(s1, s2);
        ul.append(li);
      }
      document.body.appendChild(ul);
      const t = ul.firstElementChild!.firstElementChild!.firstChild as Text;
      const i = t.data.indexOf("8,0 Mio. €");
      const r = document.createRange();
      r.setStart(t, i);
      r.setEnd(t, i + "8,0 Mio. €".length);
      document.getSelection()!.removeAllRanges();
      document.getSelection()!.addRange(r);
    });
    await markierKnopf(page).click();
    await expect(fenster(page).locator("[data-lotti-frage]").last())
      .toHaveText("„8,0 Mio. €“ — Was bedeutet das?");
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
    expect(geschickt!.selection).toBe("Mai 2026 · Bäderbetrieb Oldenburg · »8,0 Mio. €« 3,43 %");
  });

  test("nach der Antwort fragt man direkt nach — das Zitat reist als Gedächtnis mit",
    async ({ page }) => {
      const bodies: Record<string, unknown>[] = [];
      await page.route("**/api/council/explain", async (route) => {
        bodies.push(route.request().postDataJSON());
        await route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM() });
      });
      await page.goto("/dashboard");
      await probeAbsatz(page);
      await markiere(page, "391,5 Mio. €");
      await markierKnopf(page).click();
      await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
      const eingabe = fenster(page).getByLabel("Frage an Lotti");
      await eingabe.fill("Und warum so viel?");
      await eingabe.press("Enter");
      await expect.poll(() => bodies.length).toBe(2);
      const history = (bodies[1] as { history: { question: string }[] }).history;
      expect(history.at(-1)?.question).toBe("„391,5 Mio. €“ — Was bedeutet das?");
    });

  test("mit der Maus: Doppelklick auf ein Wort zeigt den Knopf", async ({ page }) => {
    await stromStubben(page);
    await page.goto("/dashboard");
    await probeAbsatz(page);
    const punkt = await page.evaluate(() => {
      const t = document.getElementById("markier-probe")!.firstChild as Text;
      const i = t.data.indexOf("Aufwendungen");
      const r = document.createRange();
      r.setStart(t, i + 2);
      r.setEnd(t, i + 3);
      const b = r.getBoundingClientRect();
      return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
    });
    await page.mouse.dblclick(punkt.x, punkt.y);
    await expect(markierKnopf(page)).toBeVisible();
    // Klick daneben: weg.
    await page.mouse.click(700, 600);
    await expect(markierKnopf(page)).toHaveCount(0);
  });

  test("Esc und eine leere Auswahl nehmen den Knopf weg", async ({ page }) => {
    await page.goto("/dashboard");
    await probeAbsatz(page);
    await markiere(page, "Haushalt");
    await expect(markierKnopf(page)).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(markierKnopf(page)).toHaveCount(0);

    await markiere(page, "Aufwendungen");
    await expect(markierKnopf(page)).toBeVisible();
    await page.evaluate(() => document.getSelection()!.removeAllRanges());
    await expect(markierKnopf(page)).toHaveCount(0);
  });

  test("Esc schließt bei offenem Fenster nur den Knopf, nicht auch das Fenster", async ({ page }) => {
    await page.goto("/dashboard");
    await knopf(page).click();
    await expect(fenster(page)).toBeVisible();
    await probeAbsatz(page);
    // Das offene Fenster hat den Fokus in seiner Eingabezeile — und solange
    // ein Eingabefeld ihn hat, zählt keine Auswahl. Wer mit der Maus auf der
    // Seite markiert, nimmt ihn ihr mit dem ersten Klick; das hier stellt
    // genau das nach.
    await page.locator("#markier-probe").click();
    await markiere(page, "Haushalt");
    await expect(markierKnopf(page)).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(markierKnopf(page)).toHaveCount(0);
    await expect(fenster(page)).toBeVisible();
  });

  test("per Tab erreichbar, solange eine Auswahl steht", async ({ page }) => {
    await stromStubben(page);
    await page.goto("/dashboard");
    await probeAbsatz(page);
    await markiere(page, "391,5 Mio. €");
    await expect(markierKnopf(page)).toBeVisible();
    await page.keyboard.press("Tab");
    await expect(markierKnopf(page)).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(fenster(page).locator("[data-lotti-frage]").last())
      .toHaveText("„391,5 Mio. €“ — Was bedeutet das?");
  });

  test("ein einzelnes Zeichen ist ein Klick, keine Auswahl", async ({ page }) => {
    await page.goto("/dashboard");
    await probeAbsatz(page);
    await markiere(page, "€");
    // Die Ruhepause abwarten, sonst prüft man zu früh.
    await page.waitForTimeout(600);
    await expect(markierKnopf(page)).toHaveCount(0);
  });

  test("eine Markierung in einem Eingabefeld zeigt keinen Knopf", async ({ page }) => {
    await page.goto("/dashboard");
    await page.evaluate(() => {
      const i = document.createElement("input");
      i.id = "markier-eingabe";
      i.value = "mein eigener Text";
      Object.assign(i.style, { position: "fixed", top: "140px", left: "16px", zIndex: "30" });
      document.body.appendChild(i);
    });
    await page.locator("#markier-eingabe").selectText();
    await page.waitForTimeout(600);
    await expect(markierKnopf(page)).toHaveCount(0);
  });

  test("eine Markierung in Lottis Fenster zeigt keinen Knopf", async ({ page }) => {
    await stromStubben(page);
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
    const antwort = fenster(page).getByText(ANTWORT);
    await expect(antwort).toBeVisible();
    await antwort.selectText();
    await page.waitForTimeout(600);
    await expect(markierKnopf(page)).toHaveCount(0);
  });

  test("eine zu lange Markierung wird gekürzt — und das Fenster sagt es", async ({ page }) => {
    let geschickt: { selection: string } | null = null;
    await page.route("**/api/council/explain", async (route) => {
      geschickt = route.request().postDataJSON();
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM() });
    });
    await page.goto("/dashboard");
    await probeAbsatz(page, { text: "Aufwendungen und Erträge. ".repeat(80) });
    await markiere(page);
    await markierKnopf(page).click();
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
    // Die Grenze des Servers (`ExplainBody.selection`, 1.000) — darüber gäbe
    // es 422 statt einer Antwort.
    expect([...geschickt!.selection].length).toBeLessThanOrEqual(1000);
    await expect(fenster(page).getByText("Markierung gekürzt")).toBeVisible();
  });

  test("mit ausgeblendetem Lotti-Knopf gibt es auch keinen an der Markierung", async ({ page }) => {
    await page.addInitScript(() => {
      try { localStorage.setItem("ratslotse:lotti-knopf-aus", "1"); } catch { /* egal */ }
    });
    await page.goto("/dashboard");
    await expect(page.getByRole("heading").first()).toBeVisible();
    await probeAbsatz(page);
    await markiere(page, "Aufwendungen");
    await page.waitForTimeout(600);
    await expect(markierKnopf(page)).toHaveCount(0);
  });

  test("ohne Schalter gibt es keinen Knopf an der Markierung", async ({ page }) => {
    await schalterAn(page, false);
    await page.goto("/dashboard");
    await expect(page.getByRole("heading").first()).toBeVisible();
    await probeAbsatz(page);
    await markiere(page, "Aufwendungen");
    await page.waitForTimeout(600);
    await expect(markierKnopf(page)).toHaveCount(0);
  });

  test.describe("auf dem Handy", () => {
    test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

    test("der Knopf lässt dem Anfasser Platz, und ein Tipp fragt", async ({ page }) => {
      await stromStubben(page);
      await page.goto("/dashboard");
      await expect(knopf(page)).toBeVisible();
      await probeAbsatz(page);
      await markiere(page, "391,5 Mio. €");
      await expect(markierKnopf(page)).toBeVisible();
      const auswahl = await auswahlBox(page);
      const box = (await markierKnopf(page).boundingBox())!;
      // Unter der Auswahl — über ihr liegt das Menü des Systems — und mit
      // Abstand: Direkt unter dem Ende sitzt der Anfasser.
      expect(box.y - (auswahl.y + auswahl.height)).toBeGreaterThanOrEqual(30);
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(390);
      // Volle Bedienhöhe für den Finger.
      expect(box.height).toBeGreaterThanOrEqual(40);

      await markierKnopf(page).tap();
      await expect(fenster(page)).toBeVisible();
      await expect(fenster(page).locator("[data-lotti-frage]").last())
        .toHaveText("„391,5 Mio. €“ — Was bedeutet das?");
      await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
      // Die Auswahl ist aufgehoben — sonst hinge das Menü des Systems über
      // dem Fenster.
      expect(await page.evaluate(() => document.getSelection()!.isCollapsed)).toBe(true);
    });
  });
});

/**
 * B4 der zweiten Durchsicht (21.09.2026): Der Knopf stand auch dann im DOM,
 * wenn der Einrichtungs-Assistent als Vollfläche (`fixed inset-0`) davor lag —
 * mit Tab erreichbar, vom Auge nicht zu sehen. Wer ihn traf, öffnete ein
 * Fenster HINTER der Fläche und bekam Seitenwissen zu einer Seite, die gerade
 * gar nicht zu sehen war.
 */
test.describe("Vollbild-Abläufe lassen keinen Lotti-Knopf daneben", () => {
  // Ohne gespeicherte Anmeldung: Der Assistent zeigt sich nur einem FRISCHEN
  // Konto — die Identitäten der Suite sind in `auth.setup.ts` längst
  // abgehakt (s. helpers.ts).
  test.use({ storageState: { cookies: [], origins: [] } });

  test("der Einrichtungs-Assistent: kein Knopf, nach dem Überspringen wieder da", async ({ page }) => {
    await schalterAn(page);
    await stromStubben(page);
    await page.goto("/register");
    await page.locator("#display-name").fill("Testkonto");
    await page.locator("#email").fill(`lotti-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.org`);
    await page.locator("#password").fill("password123");
    await page.getByRole("button", { name: "Konto erstellen" }).click();
    await page.waitForURL(/\/(link|dashboard)/, { timeout: 15_000 });

    // Der Auftakt des Assistenten steht — und Lotti nicht daneben. Geprüft
    // wird `toHaveCount(0)`, nicht `toBeHidden()`: Der Befund war gerade,
    // dass der Knopf UNSICHTBAR, aber vorhanden und tab-bar war.
    await expect(page.getByRole("button", { name: /Los geht/ })).toBeVisible({ timeout: 15_000 });
    await expect(knopf(page)).toHaveCount(0);

    // Durch den Assistenten hindurch: Auftakt, dann jeden Schritt überspringen.
    await page.getByRole("button", { name: /Los geht/ }).click();
    for (let i = 0; i < 6; i++) {
      const weiter = page.getByRole("button", { name: /^(Überspringen|Später|Fertig)$/ });
      if (!(await weiter.count())) break;
      await weiter.first().click();
      await page.waitForTimeout(400);
      if (await knopf(page).count()) break;
    }
    // Die Tour-Einladung kann als letzter Takt folgen — auch sie ist eine
    // Vollfläche, also wird sie weggeklickt.
    const spaeter = page.getByRole("button", { name: /Erst mal selbst|Später/ });
    if (await spaeter.count()) await spaeter.first().click().catch(() => { /* schon zu */ });

    await expect(knopf(page)).toBeVisible({ timeout: 15_000 });
  });
});

test.describe("Die geführte Tour", () => {
  test.use({ storageState: zustandsDatei("ratsfrau") });

  test("räumt den Lotti-Knopf weg und gibt ihn danach zurück", async ({ page }) => {
    await schalterAn(page);
    await stromStubben(page);
    await page.goto("/dashboard");
    await expect(knopf(page)).toBeVisible();
    // Ein offenes Fenster muss sich dabei schließen — die Tour lässt sich aus
    // der ⌘K-Palette starten, also auch bei offenem Lotti.
    await knopf(page).click();
    await expect(fenster(page)).toBeVisible();

    // Dasselbe Signal, das die Palette („Lotti-Tour starten") sendet.
    await page.evaluate(() => window.dispatchEvent(new Event("ratslotse:start-tour")));
    await expect(page.getByRole("dialog", { name: /^Tour:/ })).toBeVisible({ timeout: 15_000 });
    await expect(knopf(page)).toHaveCount(0);
    await expect(fenster(page)).toHaveCount(0);

    await page.keyboard.press("Escape");
    await expect(knopf(page)).toBeVisible({ timeout: 15_000 });
  });
});
