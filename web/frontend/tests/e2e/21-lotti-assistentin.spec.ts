/**
 * Lotti als Assistentin: der schwebende Knopf und sein Fenster.
 *
 * Der Erklär-Strom ist **gestubbt** — geprüft wird die Oberfläche, nicht das
 * Sprachmodell (dafür gibt es `eval/run_assistant.py`). Vier Zusagen, die man
 * einer Komponente nicht ansieht und die alle schon einmal anders waren:
 *
 * 1. Der Knopf ist **überall** da, am Schreibtisch wie auf dem Handy — genau
 *    das war im ersten Entwurf nicht so (er lag mobil in der Kopfleiste).
 * 2. Auf `/fragen` schneidet er den Composer **nicht** an.
 * 3. Der Verlauf **überlebt den Seitenwechsel**; das ist der Grund, warum das
 *    Fenster in der App-Hülle lebt und nicht in einer Seite.
 * 4. Ohne Schalter und auf den Konto-Seiten gibt es ihn **nicht**.
 *
 * Läuft gegen die LEERE Ratsdatenbank der CI: Keine Zusage hier hängt an
 * einem bestimmten Beschluss.
 */
import { expect, test, type Page } from "@playwright/test";

import { zustandsDatei } from "./konten";

const ANTWORT = "Die Treppe zeigt, wie viel die Stadt in jedem Jahr zurückzahlt.";

const STROM = (opts: { next?: string | null } = {}) => [
  `data: ${JSON.stringify({ type: "step", step: "context" })}\n\n`,
  `data: ${JSON.stringify({ type: "step", step: "answer" })}\n\n`,
  `data: ${JSON.stringify({ type: "token", text: ANTWORT })}\n\n`,
  `data: ${JSON.stringify({
    type: "done", mode: "explain", kind: "model",
    next: opts.next ?? null, glossary: ["Tilgung"], timings: { total_ms: 900 },
  })}\n\n`,
].join("");

/** Der Schalter kommt aus `/api/app-config`; ohne ihn gibt es keinen Knopf.
 *
 *  **Der try/catch ist nicht Vorsicht, sondern gemessen** (CI, 21.09.2026):
 *  Beendet ein `test.skip()` den Test, während dieser Handler noch auf die
 *  echte Antwort wartet, wirft Playwright „Response has been disposed" — und
 *  zwar in JEDEM danach laufenden Test derselben Datei, weil die Route
 *  weiterhin registriert ist. Ein Handler, der den Fehler schluckt und die
 *  Anfrage durchlässt, macht die ganze Datei gegen diesen Abbruch immun.
 */
async function schalterAn(page: Page, an = true) {
  await page.route("**/api/app-config", async (route) => {
    try {
      const antwort = await route.fetch();
      const body = await antwort.json();
      const features: string[] = (body.features ?? []).filter((f: string) => f !== "lotti-assistentin");
      if (an) features.push("lotti-assistentin");
      await route.fulfill({ json: { ...body, features } });
    } catch {
      await route.fallback().catch(() => { /* der Test ist schon zu Ende */ });
    }
  });
}

async function stromStubben(page: Page, opts: { next?: string | null } = {}) {
  await page.route("**/api/council/explain", (route) =>
    route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM(opts) })
      .catch(() => { /* der Test ist schon zu Ende */ }),
  );
}

const knopf = (page: Page) => page.locator("[data-lotti-knopf]");
const fenster = (page: Page) => page.locator("[data-lotti-fenster]");

test.describe("Lotti-Knopf und -Fenster", () => {
  test.use({ storageState: zustandsDatei("ratsfrau") });

  test.beforeEach(async ({ page }) => {
    await schalterAn(page);
    await stromStubben(page);
  });

  test("der Knopf schwebt unten rechts — am Schreibtisch wie auf dem Handy", async ({ page }) => {
    for (const grosse of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(grosse);
      await page.goto("/dashboard");
      await expect(knopf(page)).toBeVisible();
      const box = (await knopf(page).boundingBox())!;
      // Rechte Hälfte, untere Hälfte — mehr soll hier nicht festgenagelt sein
      // (Pixelvergleiche meldet jede beabsichtigte Änderung als Fehler).
      expect(box.x + box.width / 2).toBeGreaterThan(grosse.width / 2);
      expect(box.y + box.height / 2).toBeGreaterThan(grosse.height / 2);
    }
  });

  test("er öffnet das Fenster, wird zum Kreuz, und Esc schließt wieder", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(fenster(page)).toBeHidden();
    await knopf(page).click();
    await expect(fenster(page)).toBeVisible();
    await expect(knopf(page)).toHaveAttribute("aria-expanded", "true");
    await page.keyboard.press("Escape");
    await expect(fenster(page)).toBeHidden();
    // Der Fokus kehrt auf den Knopf zurück — sonst beginnt die nächste
    // Tabulatortaste wieder ganz oben auf der Seite (BITV).
    await expect(knopf(page)).toBeFocused();
  });

  test("„Was sehe ich hier?“ zeigt die Antwort im Fenster", async ({ page }) => {
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
  });

  test("eine Archivfrage wird IM Fenster beantwortet — mit Belegen", async ({ page }) => {
    // Bis PR 4 führte der Knopf weg auf `/fragen`, und der Zusammenhang war
    // hin: Wer auf der Schulden-Seite „wer hat das beantragt?" fragt, landete
    // auf einer leeren Fragen-Seite, und das „das" war weg.
    let geschickt: Record<string, unknown> | null = null;
    await page.route("**/api/council/ask", async (route) => {
      geschickt = route.request().postDataJSON();
      await route.fulfill({
        status: 200, contentType: "text/event-stream",
        body: [
          `data: ${JSON.stringify({ type: "sources", sources: [
            { id: 8525, title: "Stadionneubau Maastrichter Straße", committee: "Rat",
              session_date: "2026-06-01" },
          ] })}\n\n`,
          `data: ${JSON.stringify({ type: "token", text: "Der Rat hat 2026 zugestimmt." })}\n\n`,
          `data: ${JSON.stringify({ type: "done", cited: [8525] })}\n\n`,
        ].join(""),
      }).catch(() => { /* Test ist schon zu Ende */ });
    });
    await stromStubben(page, { next: "ratsfrage" });
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByLabel("Frage an Lotti").fill("Wer hat dagegen gestimmt?");
    await fenster(page).getByRole("button", { name: "Fragen" }).click();
    await fenster(page).getByRole("button", { name: /Den Rat fragen/ }).click();
    await expect(fenster(page).getByText("Der Rat hat 2026 zugestimmt.")).toBeVisible();
    await expect(fenster(page).getByText("Stadionneubau Maastrichter Straße")).toBeVisible();
    // Der Bildschirm reist mit — sonst sucht das Archiv nach nichts.
    const screen = (geschickt as { screen?: { route?: string } })?.screen;
    expect(screen?.route).toBe("/dashboard");
    // Und der Weg ins volle Ratsgespräch steht darunter.
    await expect(fenster(page).getByRole("button", { name: /Im Ratsgespräch weiterführen/ }))
      .toBeVisible();
  });

  test("die Kontext-Pille zeigt die Seite, nicht den Anzeigenamen", async ({ page }) => {
    // Auf `/dashboard` ist die `h1` „Moin, <Anzeigename>!" — sie ging bis
    // 21.09.2026 als Überschrift in die Pille, in den Prompt und in den Titel
    // des gespeicherten Gesprächs. Regel 9 des Assistentin-Plans
    // („Anzeigename nie") war damit auf der meistbesuchten Seite verletzt.
    let geschickt: Record<string, unknown> | null = null;
    await page.route("**/api/council/explain", (route) => {
      geschickt = route.request().postDataJSON();
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM() })
        .catch(() => { /* der Test ist schon zu Ende */ });
    });
    await page.goto("/dashboard");
    // Der Anzeigename kommt aus der Saat und heißt nicht überall gleich —
    // deshalb aus der Überschrift gelesen statt hier festgenagelt.
    const h1 = (await page.getByRole("heading", { level: 1 }).innerText()).trim();
    const name = h1.replace(/^Moin,?\s*/i, "").replace(/!$/, "").trim();
    expect(name.length, `Die h1 von /dashboard grüßt nicht: „${h1}“`).toBeGreaterThan(2);
    await knopf(page).click();
    const pille = fenster(page).locator("[data-lotti-kontext]");
    await expect(pille).toBeVisible();
    await expect(pille).not.toContainText(name);
    await expect(pille).toContainText("Heute");
    // Und der Name geht auch nicht als `heading` ans Backend.
    await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
    const körper = geschickt as { heading?: string; page_title?: string } | null;
    expect(körper?.heading).toBe("");
    expect(körper?.page_title ?? "").not.toContain(name);
  });

  test("der Verlauf überlebt den Seitenwechsel", async ({ page }) => {
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
    // Wegnavigieren und wieder öffnen: Das Fenster lebt in der App-Hülle.
    await page.goto("/bookmarks");
    await knopf(page).click();
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
  });

  test("nach dem Seitenwechsel: Zäsur im Verlauf, und das Gedächtnis bleibt hier",
    async ({ page }) => {
      // B5 der zweiten Durchsicht: Auf der neuen Seite stand die Erklärung der
      // alten als erste Runde — ohne Trennlinie — und ihre Runden gingen als
      // `history` in den Prompt, obwohl sie zu einer anderen Seite gehörten.
      await page.goto("/dashboard");
      await knopf(page).click();
      await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
      await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
      await expect(fenster(page).locator("[data-lotti-zaesur]")).toHaveCount(0);

      await page.goto("/bookmarks");
      await knopf(page).click();
      // Der Netzmitschnitt der NÄCHSTEN Frage — vor dem Klick registriert.
      const anfrage = page.waitForRequest("**/api/council/explain");
      await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
      const koerper = (await anfrage).postDataJSON() as {
        route?: string; history?: { question: string }[] };
      expect(koerper.route).toBe("/bookmarks");
      // Die Runde von `/dashboard` bleibt sichtbar, reist aber nicht mit.
      expect(koerper.history ?? []).toEqual([]);

      const zaesur = fenster(page).locator("[data-lotti-zaesur]");
      await expect(zaesur).toHaveCount(1);
      await expect(zaesur).toContainText("Jetzt auf:");
      // Sie steht VOR der neuen Runde, nicht am Ende des Verlaufs.
      await expect(fenster(page).getByText(ANTWORT)).toHaveCount(2);
    });

  test("auf der Fragen-Seite schneidet der Knopf den Composer nicht an", async ({ page }) => {
    for (const grosse of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(grosse);
      await page.goto("/fragen");
      const eingabe = page.getByPlaceholder(/Deine Frage/).first();
      await expect(eingabe).toBeVisible();
      const a = (await knopf(page).boundingBox())!;
      const b = (await eingabe.boundingBox())!;
      const ueberlappt = a.x < b.x + b.width && a.x + a.width > b.x
        && a.y < b.y + b.height && a.y + a.height > b.y;
      expect(ueberlappt, `Knopf überdeckt den Composer bei ${grosse.width} px`).toBe(false);
    }
  });

  test("der Erklär-Modus sagt in jedem Fall, woran man ist", async ({ page }) => {
    // **Die CI-Ratsdatenbank ist LEER**, und der Haushalt zeigt ohne Daten
    // keine Bühne (Designsprache: „Ohne Datengrundlage entfällt die Bühne")
    // — also auch keine Anker. Geprüft wird deshalb eine Zusage, die in
    // beiden Welten gilt: Entweder es gibt Abzeichen, oder der Modus sagt
    // ehrlich, dass er hier nichts einzeln erklären kann. Der zweite Zweig
    // ist kein Notbehelf, sondern der Fall, den jemand mit leerer Seite
    // wirklich sieht.
    await page.goto("/haushalt/schulden");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Etwas auf der Seite zeigen" }).click();
    // Der Modus schließt das Fenster: Die Abzeichen stehen auf der SEITE,
    // und auf dem Handy deckt das Fenster genau sie ab.
    await expect(fenster(page)).toBeHidden();
    const marken = page.locator("[data-erklaer-marke]");
    const hinweis = page.getByText(/nichts einzeln erklären/);
    await expect(marken.first().or(hinweis)).toBeVisible();
  });

  test("ein angetipptes Abzeichen schickt NUR diesen Baustein", async ({ page }) => {
    let geschickt: Record<string, unknown> | null = null;
    await page.route("**/api/council/explain", async (route) => {
      geschickt = route.request().postDataJSON();
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM() });
    });
    await page.goto("/haushalt/schulden");
    // ERST die Daten abwarten, dann den Modus starten: Sonst entscheidet ein
    // Rennen zwischen Nachladen und Messen, ob es Anker gibt — und der Test
    // übersprang sich auch dort, wo Daten da waren.
    await page.waitForLoadState("networkidle");
    const anker = page.locator("[data-erklaer]");
    // Ohne Ratsdaten (so läuft die CI) gibt es keinen Baustein zum Antippen —
    // sichtbar überspringen statt etwas anderes messen.
    test.skip(await anker.count() === 0,
      "Diese Datenbank hat keine Haushaltsdaten — also auch keine Anker.");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Etwas auf der Seite zeigen" }).click();
    const marken = page.locator("[data-erklaer-marke]");
    await expect(marken.first()).toBeVisible();
    await marken.first().click();
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
    expect(geschickt).toBeTruthy();
    const el = (geschickt as { element?: { key?: string; text?: string } }).element!;
    expect(el.key).toMatch(/^haushalt-schulden\./);
    expect(el.text!.length).toBeGreaterThan(0);
    expect(el.text!.length).toBeLessThanOrEqual(1202);
  });

  test("Esc beendet den Erklär-Modus", async ({ page }) => {
    await page.goto("/haushalt/schulden");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Etwas auf der Seite zeigen" }).click();
    const marken = page.locator("[data-erklaer-marke]");
    // Egal ob Anker oder Hinweis — eines von beiden steht da, bevor Esc kommt.
    await page.getByText(/nichts einzeln erklären/).or(marken.first()).first().waitFor();
    await page.keyboard.press("Escape");
    await expect(marken).toHaveCount(0);
    await expect(page.getByText(/nichts einzeln erklären/)).toBeHidden();
  });

  test("ohne beantwortete Einwilligung fragt Lotti nichts", async ({ page }) => {
    // Die Saat-Konten haben die Frage längst beantwortet — für diesen Fall
    // muss sie zurückgesetzt werden. Geprüft wird die Zusage, die dahinter
    // steht: Der Satz über die externe Verarbeitung steht VOR der ersten
    // Frage, nicht danach.
    await page.route("**/api/auth/me", async (route) => {
      try {
        const antwort = await route.fetch();
        const body = await antwort.json();
        await route.fulfill({ json: { ...body, saves_conversations: null } });
      } catch {
        await route.fallback().catch(() => { /* Test ist schon zu Ende */ });
      }
    });
    await page.goto("/dashboard");
    await knopf(page).click();
    await expect(fenster(page).getByText(/Soll ich mir deine Gespräche merken/)).toBeVisible();
    await expect(fenster(page).getByText(/OpenRouter/)).toBeVisible();
    await expect(fenster(page).getByRole("button", { name: "Fragen" })).toBeDisabled();
    await expect(fenster(page).getByRole("button", { name: "Was sehe ich hier?" })).toBeDisabled();
  });

  test("auf der Konto-Seite gibt es Lotti nicht", async ({ page }) => {
    // Dort stehen die eigene Adresse und die Kontodaten — sie dürfen nicht
    // als Seitentext in einen Prompt wandern (kern/knowledge.py).
    await page.goto("/account");
    await expect(knopf(page)).toBeHidden();
  });

  test("der Knopf lässt sich ausblenden — und Lotti bleibt erreichbar", async ({ page }) => {
    // Die Einstellung wohnt im Gerät, nicht im Konto: Wem Lotti auf dem
    // Telefon im Weg ist, dem ist sie am Monitor vielleicht recht.
    await page.goto("/account");
    await page.getByRole("switch", { name: "Lotti-Knopf ausblenden" }).click();
    await page.goto("/dashboard");
    await expect(page.getByRole("heading").first()).toBeVisible();
    await expect(knopf(page)).toBeHidden();

    // „Ausblenden" heißt wegräumen, nicht abschalten — über die Palette
    // öffnet sie sich weiterhin.
    await page.keyboard.press("ControlOrMeta+k");
    await page.getByRole("option", { name: "Lotti fragen" }).click();
    await expect(fenster(page)).toBeVisible();
  });

  test("eine anderswo getroffene Einwilligung gilt auch hier", async ({ page }) => {
    // Die Karte erschien ein zweites Mal, wenn man die Frage auf `/fragen`
    // beantwortet hatte und danach Lotti öffnete: Das Fenster las den Stand
    // des Kontos nur EINMAL, beim Einhängen.
    let gefragt = false;
    await page.route("**/api/auth/me", async (route) => {
      try {
        const antwort = await route.fetch();
        const body = await antwort.json();
        await route.fulfill({
          json: { ...body, saves_conversations: gefragt ? 1 : null },
        });
      } catch {
        await route.fallback().catch(() => { /* Test ist schon zu Ende */ });
      }
    });
    await page.goto("/dashboard");
    await knopf(page).click();
    await expect(fenster(page).getByText(/Soll ich mir deine Gespräche merken/)).toBeVisible();

    // Die Wahl fällt woanders — hier kommt sie nur als neuer Kontostand an.
    gefragt = true;
    await page.getByRole("button", { name: "Lotti schließen" }).click().catch(() => {});
    await page.goto("/bookmarks");
    await knopf(page).click();
    await expect(fenster(page).getByText(/Soll ich mir deine Gespräche merken/)).toBeHidden();
    await expect(fenster(page).getByRole("button", { name: "Was sehe ich hier?" }))
      .toBeEnabled();
  });

  test("ein Lotti-Gespräch öffnet sich in ihrem Fenster, nicht im Ratsgespräch",
    async ({ page }) => {
      await page.route("**/api/council/conversations?**", async (route) => {
        await route.fulfill({ json: {
          saves_conversations: 1, total: 1, matches: 1, has_more: false,
          conversations: [{ id: 77, title: "Schulden › Rate-Treppe",
                            updated: new Date().toISOString(), n_turns: 1,
                            kind: "lotti" }],
        } });
      });
      await page.route("**/api/council/conversations/77", async (route) => {
        await route.fulfill({ json: {
          id: 77, title: "Schulden › Rate-Treppe", kind: "lotti",
          updated: new Date().toISOString(),
          turns: [{ question: "Was ist die Rate-Treppe?", answer: ANTWORT,
                    sources: { route: "/haushalt/schulden", mode: "explain",
                               glossary: ["Tilgung"], next: null } }],
        } });
      });
      await page.goto("/fragen");
      await page.getByRole("button", { name: /Gespräche/ }).first().click();
      await expect(page.getByRole("dialog", { name: "Gespräche" })
        .getByText("Mit Lotti ·").first()).toBeVisible();
      // Der Titel selbst, nicht die Zeile drumherum: Über ihr liegt die
      // Gruppen-Überschrift des Sheets und fängt den Klick ab.
      await page.getByRole("dialog", { name: "Gespräche" })
        .getByText("Schulden › Rate-Treppe", { exact: true }).click();
      // Die Runde steht in LOTTIS Fenster …
      await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
      // … und nicht im Ratsgespräch darunter.
      await expect(page.locator("main").getByText(ANTWORT)).toBeHidden();
    });

  test("die Tastatur verdeckt das Fenster nicht", async ({ page }) => {
    // **Eine echte Tastatur lässt sich hier nicht öffnen** — Chromium im Test
    // kennt keine. Nachgestellt wird deshalb genau das, was sie auslöst: ein
    // geschrumpfter `visualViewport`. Die Rechnung dahinter prüft
    // `lib/tastatur.test.ts`; hier geht es um die Verdrahtung, also darum,
    // dass das Fenster wirklich hochrückt und der Knopf verschwindet.
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => {
      const hoerer: Record<string, (() => void)[]> = { resize: [], scroll: [] };
      const falsch = {
        height: window.innerHeight, offsetTop: 0,
        addEventListener: (n: string, f: () => void) => { hoerer[n]?.push(f); },
        removeEventListener: () => { /* im Test nie nötig */ },
      };
      Object.defineProperty(window, "visualViewport", { value: falsch, configurable: true });
      (window as unknown as { tastaturAuf: (h: number) => void }).tastaturAuf = (h) => {
        falsch.height = window.innerHeight - h;
        hoerer.resize.forEach((f) => f());
      };
    });
    await page.goto("/dashboard");
    await knopf(page).click();
    const vorher = (await fenster(page).boundingBox())!;

    await page.evaluate(() => (window as unknown as
      { tastaturAuf: (h: number) => void }).tastaturAuf(320));
    await expect(knopf(page)).toBeHidden();
    // Die Messung braucht einen eigenen Takt: Wer im selben Aufruf umstellt
    // und misst, bekommt die alte Geometrie zurück und hält den Umbau
    // fälschlich für wirkungslos (eine Stunde am 21.09.2026).
    await expect.poll(async () => {
      const b = await fenster(page).boundingBox();
      return b ? Math.round(b.y + b.height) : 0;
    }).toBeLessThan(420);
    const nachher = (await fenster(page).boundingBox())!;
    // Der untere Rand des Fensters liegt jetzt über der Tastatur — und damit
    // auch die Eingabezeile, in die man gerade tippt.
    expect(nachher.y + nachher.height).toBeLessThan(vorher.y + vorher.height - 300);
    await expect(fenster(page).getByLabel("Frage an Lotti")).toBeVisible();
  });

  test("ohne Schalter gibt es keinen Knopf", async ({ page }) => {
    await schalterAn(page, false);
    await page.goto("/dashboard");
    await expect(page.getByRole("heading").first()).toBeVisible();
    await expect(knopf(page)).toBeHidden();
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
