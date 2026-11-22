/**
 * Lotti als Assistentin, Teil 2 — die zweite Hälfte von
 * `21-lotti-assistentin.spec.ts`; was dort im Kopf steht, gilt hier genauso
 * (gestubbter Strom, leere Ratsdatenbank).
 *
 * Der Schnitt folgt der Laufzeit, nicht dem Thema: Beide Hälften laufen in der
 * CI auf verschiedenen Läufern und brauchen deshalb jede ihr eigenes
 * `beforeEach`. Kein Test hier verlässt sich auf einen aus Teil 1.
 */
import { expect, test } from "@playwright/test";

import { zustandsDatei } from "./konten";
import {
  ANTWORT, GEPRUEFTE_ANTWORT, STROM, schalterAn, STROM_GEPRUEFT, ANTWORT_FACHWORT, STROM_FACHWORT,
  ANTWORT_SEITE, STROM_SEITE, ANTWORT_ZAHL, STROM_BELEGE, stromStubben, knopf, fenster,
  schuldenGeladen,
} from "./lotti-helpers";

test.describe("Lotti-Knopf und -Fenster (Teil 2)", () => {
  test.use({ storageState: zustandsDatei("ratsfrau") });

  test.beforeEach(async ({ page }) => {
    await schalterAn(page);
    await stromStubben(page);
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

  test("„Wo finde ich …?“ zeigt hin — ohne einen einzigen Netzaufruf", async ({ page }) => {
    // Die Zusage dieses PRs: Die Anker der Seite sind eine Landkarte, die der
    // Client schon hat. Trifft ein Titel, entsteht die Antwort im Browser —
    // kein `/explain`, keine Kosten, unter einer Millisekunde.
    let rufe = 0;
    await page.route("**/api/council/explain", async (route) => {
      rufe += 1;
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM() });
    });
    await page.goto("/haushalt/schulden");
    // Erst die Daten, dann messen — sonst entscheidet ein Rennen, ob es Anker
    // gibt (dieselbe Falle wie beim Erklär-Modus-Test oben).
    await schuldenGeladen(page);
    const anker = page.locator("[data-erklaer][data-erklaer-titel]");
    test.skip(await anker.count() === 0,
      "Diese Datenbank hat keine Haushaltsdaten — also auch keine Anker.");
    // **Der Titel kommt aus der Seite, nicht aus diesem Test.** Ein fest
    // eingetippter („Rate-Treppe“) misst, ob die Seite ihn heute noch so
    // nennt — nicht, ob die Lotsin funktioniert.
    const titel = (await anker.first().getAttribute("data-erklaer-titel"))!;
    const key = (await anker.first().getAttribute("data-erklaer"))!;

    await knopf(page).click();
    await fenster(page).getByRole("textbox", { name: "Frage an Lotti" })
      .fill(`Wo finde ich ${titel}?`);
    await page.keyboard.press("Enter");

    const chip = fenster(page).getByRole("button", { name: `Zeig mir: ${titel}` });
    await expect(chip).toBeVisible();
    expect(rufe, "die Lotsen-Runde darf das Backend nicht anfassen").toBe(0);
    // Kein Daumen: Es gibt hier nichts zu benoten und niemanden, der die Note
    // entgegennähme.
    await expect(fenster(page).getByRole("button", { name: /hilfreich/i })).toHaveCount(0);

    await chip.click();
    // Der Baustein steht danach im Bild — und trägt zwei Sekunden lang den
    // Ring, an dem man ihn findet.
    const ziel = page.locator(`[data-erklaer="${key}"]`);
    await expect(ziel).toHaveClass(/lotti-zeigt/);
    const box = (await ziel.boundingBox())!;
    const hoehe = page.viewportSize()!.height;
    expect(box.y).toBeLessThan(hoehe);
    expect(box.y + box.height).toBeGreaterThan(0);
    expect(rufe).toBe(0);
  });

  test("zum Fachwort gibt es KEINEN Chip — es steht im Text und klappt dort auf",
    async ({ page }) => {
      // Bis 22.09.2026 stand unter der Antwort „Was heißt Umschuldung?",
      // während „Umschuldung" zwei Zeilen darüber schon unterstrichen war
      // (PR 22). Zwei Wege zu derselben geprüften Erklärung, einer davon als
      // Bedienelement in der Fußzeile — der Weg AM WORT ist der bessere.
      await page.route("**/api/council/explain", (route) =>
        route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM_FACHWORT })
          .catch(() => { /* Test ist schon zu Ende */ }),
      );
      await page.goto("/dashboard");
      await knopf(page).click();
      await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
      await expect(fenster(page).getByText(ANTWORT_FACHWORT)).toBeVisible();

      await expect(fenster(page).getByRole("button", { name: /^Was heißt/ })).toHaveCount(0);
      // Der verbliebene Weg: das Wort selbst.
      await expect(fenster(page).getByRole("button", { name: "Was bedeutet Umschuldung?" }))
        .toBeVisible();
    });

  test("ein Fachwort klappt IM Fenster auf, statt am Rand abgeschnitten zu werden",
    async ({ page }) => {
      // Tims Befund 22.09.2026: Die Glossar-Erklärung war ein Popover am Wort
      // (`absolute left-0 top-full`, bis 17 rem breit). Lottis Fenster ist
      // 384 px breit und `overflow-hidden` — steht das Wort rechts, schnitt
      // der Fensterrand die Erklärung ab („Wirtschaftsplan" halb sichtbar).
      // Geprüft wird die Zusage, nicht die Bauform: Was aufklappt, liegt
      // GANZ im Fenster.
      await page.route("**/api/council/explain", (route) =>
        route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM_FACHWORT })
          .catch(() => { /* Test ist schon zu Ende */ }),
      );
      await page.goto("/dashboard");
      await knopf(page).click();
      await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();

      const wort = fenster(page).getByRole("button", { name: "Was bedeutet Umschuldung?" });
      await expect(wort).toBeVisible();
      await expect(wort).toHaveAttribute("aria-expanded", "false");
      const block = fenster(page).locator("[data-glossar-aufklapp]");
      await expect(block).toHaveCount(0);

      await wort.click();
      await expect(block).toBeVisible();
      await expect(wort).toHaveAttribute("aria-expanded", "true");
      await expect(block).toContainText("Umschuldung");

      const b = (await block.boundingBox())!;
      const f = (await fenster(page).boundingBox())!;
      expect(b.x, "linker Rand").toBeGreaterThanOrEqual(f.x - 1);
      expect(b.x + b.width, "rechter Rand").toBeLessThanOrEqual(f.x + f.width + 1);
      expect(b.y, "oberer Rand").toBeGreaterThanOrEqual(f.y - 1);
      expect(b.y + b.height, "unterer Rand").toBeLessThanOrEqual(f.y + f.height + 1);

      // Esc schließt die Erklärung — und NUR sie: Das Fenster bleibt stehen,
      // sonst verschwände mit dem ersten Esc gleich das ganze Gespräch.
      await page.keyboard.press("Escape");
      await expect(block).toHaveCount(0);
      await expect(fenster(page)).toBeVisible();
    });

  test("während der Strom läuft, steht da, woran Lotti gerade arbeitet",
    async ({ page }) => {
      // Tims zweiter Befund: drei 6-px-Punkte mit `animate-pulse` — „man sieht
      // fast nicht, dass da was lädt". Der Server meldet seine Schritte
      // längst als SSE-Rahmen `step`; das Fenster warf sie weg.
      //
      // **Warum `window.fetch` und nicht `page.route`.** `route.fulfill` kennt
      // nur einen fertigen Körper — einen LANGSAMEN Strom kann es nicht
      // liefern, und genau der ist hier der Prüfgegenstand: Die Schritt-Texte
      // stehen nur zwischen zwei Rahmen. Ein Prüfen nach dem `done` ginge am
      // Befund vorbei. Der Ersatz liegt deshalb eine Schicht tiefer, in der
      // Seite selbst, und baut den Strom Rahmen für Rahmen auf.
      await page.addInitScript(() => {
        const echt = window.fetch.bind(window);
        window.fetch = async (eingabe: RequestInfo | URL, init?: RequestInit) => {
          const url = typeof eingabe === "string" ? eingabe
            : eingabe instanceof URL ? eingabe.href : eingabe.url;
          if (!url.includes("/council/explain")) return echt(eingabe as RequestInfo, init);
          const rahmen = [
            { type: "step", step: "context" },
            { type: "step", step: "answer" },
            { type: "token", text: "Die Treppe zeigt die Tilgung." },
            { type: "done", mode: "explain", kind: "model", next: null, glossary: [] },
          ];
          const enc = new TextEncoder();
          const koerper = new ReadableStream<Uint8Array>({
            async start(c) {
              for (const r of rahmen) {
                await new Promise((fertig) => setTimeout(fertig, 800));
                c.enqueue(enc.encode(`data: ${JSON.stringify(r)}\n\n`));
              }
              c.close();
            },
          });
          return new Response(koerper, {
            status: 200, headers: { "Content-Type": "text/event-stream" },
          });
        };
      });
      await page.goto("/dashboard");
      await knopf(page).click();
      await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();

      // Vor dem ersten Rahmen: der Satz, der in jedem Fall wahr ist.
      await expect(fenster(page).getByText(/Lotti überlegt/)).toBeVisible();
      await expect(fenster(page).getByText(/Lotti liest die Seite/)).toBeVisible();
      await expect(fenster(page).getByText(/Lotti schreibt/)).toBeVisible();
      // Sobald Worte da sind, ist der Text selbst die Auskunft.
      await expect(fenster(page).getByText("Die Treppe zeigt die Tilgung.")).toBeVisible();
      await expect(fenster(page).getByText(/Lotti schreibt …/)).toHaveCount(0);
    });

  test("der Verweis auf eine andere Haushalts-Seite wird ein Chip, der hinführt",
    async ({ page }) => {
      // PR 21: Lotti kennt alle fünfzehn Haushalts-Seiten und sagt, wo etwas
      // ausführlich steht. Der Server prüft Route und Titel (in `PAGES`, im
      // Haushalt, für dieses Konto erreichbar) und schickt beides im
      // `done`-Rahmen; das Fenster macht daraus EIN Angebot — es navigiert
      // nichts von selbst (Plan 1, § 6).
      await page.route("**/api/council/explain", (route) =>
        route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM_SEITE })
          .catch(() => { /* Test ist schon zu Ende */ }),
      );
      await page.goto("/dashboard");
      await knopf(page).click();
      await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();

      const chip = fenster(page).getByRole("button", { name: /^Weiter zu: Schulden der Stadt/ });
      await expect(chip).toBeVisible();
      await chip.click();

      // Der Klick führt hin — und das Fenster bleibt offen: Der Verlauf
      // überlebt den Wechsel und bekommt die Zäsur „Jetzt auf: …" (PR 13).
      await expect(page).toHaveURL(/\/haushalt\/schulden/);
      await expect(fenster(page)).toBeVisible();
      await expect(fenster(page).getByText(ANTWORT_SEITE)).toBeVisible();
      await fenster(page).getByPlaceholder(/frag/i).fill("Und wie hoch sind die Zinsen?");
      await fenster(page).getByPlaceholder(/frag/i).press("Enter");
      await expect(page.locator("[data-lotti-zaesur]").first()).toBeVisible();
    });

  test("auf einer Seite mit Bausteinen führt ein Chip zum nächsten",
    async ({ page }) => {
      const gefragt: Record<string, unknown>[] = [];
      await page.route("**/api/council/explain", async (route) => {
        gefragt.push(route.request().postDataJSON());
        await route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM() })
          .catch(() => { /* Test ist schon zu Ende */ });
      });
      await page.goto("/haushalt/schulden");
      // Erst die Daten, dann messen (dieselbe Falle wie bei den Anker-Tests).
      await schuldenGeladen(page);
      const anker = page.locator("[data-erklaer][data-erklaer-titel]");
      const anzahl = await anker.count();
      test.skip(anzahl === 0,
        "Diese Datenbank hat keine Haushaltsdaten — also auch keine Anker.");
      // **Nicht einfach der ERSTE Anker** — die Bühne („Drei Zählweisen, eine
      // Stadt · Stand …") steht meist zuerst und ist seit dem Komma-Ausschluss
      // (`chipTauglich`) kein Chip mehr (PR 25, Nachbesserung 22.09.2026). Der
      // Test sucht deshalb denselben ersten CHIP-TAUGLICHEN Anker, den auch
      // `anschlussfragen` vorschlägt: kein Komma, kein Doppelpunkt, kein
      // Apostroph im Namen vor dem `·`.
      let titel = "";
      let key = "";
      for (let i = 0; i < anzahl; i++) {
        const t = (await anker.nth(i).getAttribute("data-erklaer-titel"))!;
        const kurzTitel = t.split(" · ")[0];
        if (/['’:,]/.test(kurzTitel)) continue;
        titel = t;
        key = (await anker.nth(i).getAttribute("data-erklaer"))!;
        break;
      }
      test.skip(!titel, "Keiner der Anker dieser Seite taugt als Chip.");
      // Der Chip nennt nur den NAMEN des Bausteins: Was hinter dem `·` steht,
      // ist ein Stand („… · Stand 31.12.2024") und machte aus dem Chip einen
      // zweizeiligen Klotz (`lib/assistentin.ts::chipTitel`). Geprüft wird
      // deshalb der Anfang, nicht der ganze Titel.
      const kurz = titel.split(" · ")[0].slice(0, 20);
      // **Der Chip ist eine Handlung** (PR 24): „Anzeigetafel erklären" statt
      // „Erklär mir: Die Anzeigetafel"; der führende Artikel fällt weg.
      const chipName = new RegExp(
        `^${kurz.replace(/^[Dd](er|ie|as|en|em|es)\s+/, "")
          .replace(/[.*+?^${}()|[\]\\-]/g, "\\$&")}`);

      await knopf(page).click();
      await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
      const chip = fenster(page).getByRole("button", { name: chipName });
      await expect(chip).toBeVisible();
      await chip.click();
      await expect.poll(() => gefragt.length).toBe(2);

      // Geerntet wird genau dieser Baustein, mit seinem Schlüssel — derselbe
      // Weg wie beim Abzeichen im Erklär-Modus.
      const el = (gefragt[1] as { element?: { key?: string; text?: string } }).element!;
      expect(el.key).toBe(key);
      expect(el.text!.length).toBeGreaterThan(0);
      // Und er wird nicht ein zweites Mal angeboten.
      await expect(fenster(page).getByRole("button", { name: chipName })).toHaveCount(0);
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
    // Seit 11/2026 steht sichtbar, wo die KI läuft; OpenRouter steht unter „Mehr dazu“.
    await expect(fenster(page).getByText(/Rechenzentren in der EU/)).toBeVisible();
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

    const TASTATUR = 320;
    await page.evaluate((h) => (window as unknown as
      { tastaturAuf: (h: number) => void }).tastaturAuf(h), TASTATUR);
    await expect(knopf(page)).toBeHidden();
    // Die Zusage, nicht eine Pixelzahl: Der untere Rand des Fensters liegt
    // über der Oberkante der Tastatur — und damit auch die Eingabezeile, in
    // die man gerade tippt. Bis 10/2026 standen hier „< 420" und „300 px
    // höher als vorher"; gemessen wurden 418,8 und 297,2 — je nach Schrift-
    // Rasterung grün oder rot, ohne dass sich am Verhalten etwas änderte.
    const tastaturOben = 844 - TASTATUR;
    // Die Messung braucht einen eigenen Takt: Wer im selben Aufruf umstellt
    // und misst, bekommt die alte Geometrie zurück und hält den Umbau
    // fälschlich für wirkungslos (eine Stunde am 21.09.2026).
    await expect.poll(async () => {
      const b = await fenster(page).boundingBox();
      return b ? b.y + b.height : Infinity;
    }).toBeLessThanOrEqual(tastaturOben);
    const nachher = (await fenster(page).boundingBox())!;
    // Und es ist wirklich hochgerückt, nicht nur zufällig schon oben: vorher
    // lag der Rand unter der Tastaturkante.
    expect(vorher.y + vorher.height).toBeGreaterThan(tastaturOben);
    expect(nachher.y).toBeGreaterThanOrEqual(0);
    await expect(fenster(page).getByLabel("Frage an Lotti")).toBeVisible();
  });

  test("unter dem Zeiger schaut Lotti auf", async ({ page }) => {
    // Tims Wunsch 22.09.2026: „dass ich außerhalb des Mauszeigers weiß, dass
    // ich den anklicken kann". Geprüft wird die ZUSAGE (es tut sich etwas
    // unter dem Zeiger, der Fokus bleibt sichtbar), nicht die Gestaltung —
    // kein Grad, kein Pixel, keine Klassennamen. Sonst meldet der Test jede
    // Politur als Fehler und wird beim dritten Mal weggeklickt.
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/dashboard");
    await expect(knopf(page)).toBeVisible();
    const kopf = knopf(page).locator("img");

    const ruhe = await kopf.evaluate((el) => getComputedStyle(el).transform);
    await knopf(page).hover();
    // Die Bewegung läuft `duration-fluss` (180 ms) — poll statt einer
    // einzelnen Messung, sonst misst man den ersten Frame.
    await expect.poll(async () => kopf.evaluate((el) => getComputedStyle(el).transform))
      .not.toBe(ruhe);

    // Der Schatten des Knopfs selbst wechselt mit — das ist der Teil, der
    // auch bei `prefers-reduced-motion` stehen bleibt.
    const gehoben = await knopf(page).evaluate((el) => getComputedStyle(el).boxShadow);
    await page.mouse.move(5, 5);
    await expect.poll(async () => knopf(page).evaluate((el) => getComputedStyle(el).boxShadow))
      .not.toBe(gehoben);

    // **Nicht hier geprüft: der Fokus-Ring.** `:focus-visible` hängt in
    // Chromium an der zuletzt benutzten Eingabeart; nach einem `hover()` im
    // selben Test ist ein `focus()` kein Tastatur-Fokus mehr, und der Test
    // würde mal so, mal so ausgehen. Dass der Ring bleibt, hängt ohnehin
    // nicht an dieser Änderung: Er sitzt in `--tw-ring-shadow`, der
    // Hover-Schatten in `--tw-shadow` — zwei Kanäle desselben `box-shadow`.
  });

  test("unter dem Composer steht keine Fußzeile mehr", async ({ page }) => {
    // 22.09.2026 gestrichen (Tim: „nimmt nur unnötig Platz weg"). Der Test
    // hält, dass sie nicht zurückkommt; wo der rechtliche Hinweis jetzt
    // steht, sagt der Kommentar in `panel.tsx`.
    await page.goto("/dashboard");
    await knopf(page).click();
    await expect(fenster(page)).toBeVisible();
    await expect(fenster(page).getByText(/Keine Rechtsberatung/)).toHaveCount(0);
  });

  test("unter einer Antwort mit Zahlen steht die Grundlage — und sie führt hin",
    async ({ page }) => {
      // PR 28: Lotti nennt Jahr und Quelle im Satz (Prompt-Regel 4), aber ein
      // Dokumentname im Fließtext ist kein Link. Die Papiere, die im Prompt
      // STANDEN, reisen im `done`-Rahmen als `evidence` mit; das Fenster macht
      // daraus die Zeile „Grundlage:".
      await page.route("**/api/council/explain", (route) =>
        route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM_BELEGE })
          .catch(() => { /* Test ist schon zu Ende */ }),
      );
      await page.goto("/dashboard");
      await knopf(page).click();
      await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();

      await expect(fenster(page).getByText(ANTWORT_ZAHL)).toBeVisible();
      const grundlage = fenster(page).locator("[data-lotti-grundlage]");
      await expect(grundlage).toBeVisible();
      await expect(grundlage).toContainText("Grundlage:");
      // **Ehrlich beschriftet**: Belege des KONTEXTS, nicht der einzelnen Zahl.
      await expect(grundlage).toHaveAttribute(
        "title", "Quellen, die Lotti für diese Antwort vorlagen");
      // Das Jahr steht nur dort, wo es nicht schon im Titel steht — sonst
      // hieße der zweite Chip „Jahresabschluss 2023 2023".
      const chip = fenster(page).getByRole("link", { name: /Statistisches Jahrbuch/ });
      await expect(chip).toHaveText(/Tabelle 1108 2024/);
      await expect(fenster(page).getByRole("link", { name: /Jahresabschluss/ }))
        .toHaveText(/^Jahresabschluss 2023$/);
      // Ohne Adresse bleibt der Name stehen, aber ohne Link: „Wir wissen, aus
      // welchem Papier das stammt, nur nicht, wo es liegt" ist eine Auskunft.
      await expect(fenster(page).getByText("Prüfbericht 2022")).toBeVisible();
      await expect(fenster(page).getByRole("link", { name: "Prüfbericht 2022" }))
        .toHaveCount(0);

      // Der Klick öffnet das Dokument in einem neuen Tab.
      const [neu] = await Promise.all([
        page.context().waitForEvent("page"),
        chip.click(),
      ]);
      expect(neu.url()).toBe("https://example.org/jahrbuch-1108.pdf");
      await neu.close();

      // **Vor den Daumen**: Erst lesen, worauf das beruht, dann urteilen.
      const grundlageBox = (await grundlage.boundingBox())!;
      const daumenBox = (await fenster(page)
        .getByRole("button", { name: /hilfreich|Daumen/i }).first().boundingBox())!;
      expect(grundlageBox.y).toBeLessThan(daumenBox.y);
    });

  test("ohne Zahlen steht keine Grundlage darunter", async ({ page }) => {
    // Die Wege ohne Modell (Glossar, Seitenwissen, „Lotti erklärt's einfach")
    // ruhen auf keiner Haushaltszahl — `evidence` ist leer, und eine leere
    // Zeile „Grundlage:" wäre ein Apparat ohne Gegenstand.
    await page.route("**/api/council/explain", (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM_GEPRUEFT })
        .catch(() => { /* Test ist schon zu Ende */ }),
    );
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
    await expect(fenster(page).getByText(GEPRUEFTE_ANTWORT)).toBeVisible();
    await expect(fenster(page).locator("[data-lotti-grundlage]")).toHaveCount(0);
  });

  test("ohne Schalter gibt es keinen Knopf", async ({ page }) => {
    await schalterAn(page, false);
    await page.goto("/dashboard");
    await expect(page.getByRole("heading").first()).toBeVisible();
    await expect(knopf(page)).toBeHidden();
  });
});
