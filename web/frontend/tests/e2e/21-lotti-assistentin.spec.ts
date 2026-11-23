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
 *
 * **Auf drei Dateien verteilt (11/2026).** Alle 59 Lotti-Tests standen hier
 * in einer Datei; mit rund vier Minuten war sie die Untergrenze der ganzen CI
 * (eine Datei ist die kleinste Einheit, die sich auf die Läufer verteilen
 * lässt). Der Schnitt mitten durch diesen Block folgt der LAUFZEIT, nicht dem
 * Thema — Teil 2 steht in `21-lotti-assistentin-2.spec.ts`, das Markieren, die
 * Vollbild-Abläufe und die Tour in `21-lotti-markieren.spec.ts`. Das
 * gemeinsame Rüstzeug liegt in `lotti-helpers.ts`.
 */
import { expect, test } from "@playwright/test";

import { zustandsDatei } from "./konten";
import {
  ANTWORT, GEPRUEFTE_ANTWORT, STROM, schalterAn, STROM_GEPRUEFT, ANTWORT_FACHWORT, ANTWORT_SEITE,
  STROM_SEITE, STROM_HANDOFF, RATS_ANTWORT, FUNDSTUECKE, STROM_ARCHIV, stromStubben, knopf,
  fenster, schuldenGeladen,
} from "./lotti-helpers";

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

  test("am Schreibtisch sitzt er auf /fragen wie überall — der Composer steht dort in der Bühne", async ({ page }) => {
    // Tims Befund 08.11.2026: `--rl-composer` hob den Knopf auch am
    // Schreibtisch um die Composer-Höhe an, obwohl der Composer dort nicht
    // unten andockt — Lotti schwebte 118 px über ihrer Ecke.
    await page.setViewportSize({ width: 1280, height: 800 });
    const abstandUnten = async (pfad: string) => {
      await page.goto(pfad);
      await expect(knopf(page)).toBeVisible();
      const box = (await knopf(page).boundingBox())!;
      return 800 - (box.y + box.height);
    };
    const ueberall = await abstandUnten("/dashboard");
    await expect.poll(() => abstandUnten("/fragen")).toBeCloseTo(ueberall, 0);
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

  test("?lotti=1 öffnet das Fenster beim Ankommen und verschwindet aus der Adresse", async ({ page }) => {
    // Das Ziel von „Lotti-Chat ausprobieren“ auf der Karte „Neu bei Ratslotse“.
    // Bleibt der Parameter stehen, öffnet jedes Neuladen das Fenster wieder.
    await page.goto("/dashboard?lotti=1");
    await expect(fenster(page)).toBeVisible();
    await expect(page).toHaveURL(/\/dashboard\/?$/);
    await page.reload();
    await expect(knopf(page)).toBeVisible();
    await expect(fenster(page)).toBeHidden();
  });

  test("beim Laden bleibt der Fokus, wo er war — die erste Tabulatortaste trifft „Zum Inhalt springen“", async ({ page }) => {
    // Bis 10/2026 gab das Fenster den Fokus schon beim ERSTEN Rendern an den
    // Knopf zurück („Fenster zu" galt als „gerade geschlossen"). Wer per
    // Tastatur kam, landete hinter dem Sprunglink — mitten in der Seite.
    await page.goto("/dashboard");
    await expect(knopf(page)).toBeVisible();
    await expect(knopf(page)).not.toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Zum Inhalt springen" })).toBeFocused();
  });

  test("„Was sehe ich hier?“ zeigt die Antwort im Fenster", async ({ page }) => {
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
  });

  test("das leere Fenster zeigt zwei Startfragen plus „Was sehe ich hier?“ (PR 25)",
    async ({ page }) => {
      // Die Fragen stehen als Code in `kern/knowledge.py::PAGES["/dashboard"]`
      // — kein Modellaufruf. `GET /assistant/starters` selbst wird trotzdem
      // gestubbt: Der Schalter `lotti-assistentin` gilt hier nur CLIENTSEITIG
      // (`schalterAn` fälscht `/api/app-config`) — der echte Testserver läuft
      // ohne ihn, und ein Aufruf, der wirklich bei ihm ankommt, bekäme 404.
      // Genau dasselbe gilt für `/explain`, nur läuft der in jedem Test dieser
      // Datei ohnehin schon gestubbt.
      await page.route("**/api/council/assistant/starters*", (route) =>
        route.fulfill({
          status: 200, contentType: "application/json",
          body: JSON.stringify({
            starters: ["Werden auch meine eigenen Viertel berücksichtigt?",
                      "Woher stammen die Angaben auf dieser Seite?"],
          }),
        }).catch(() => { /* Test ist schon zu Ende */ }),
      );
      let geschickt: Record<string, unknown> | null = null;
      await page.route("**/api/council/explain", async (route) => {
        geschickt = route.request().postDataJSON();
        await route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM() })
          .catch(() => { /* Test ist schon zu Ende */ });
      });
      await page.goto("/dashboard");
      await knopf(page).click();
      const erste = fenster(page).getByRole("button", { name: "Werden auch meine eigenen Viertel berücksichtigt?" });
      const zweite = fenster(page).getByRole("button", { name: "Woher stammen die Angaben auf dieser Seite?" });
      await expect(erste).toBeVisible();
      await expect(zweite).toBeVisible();
      await expect(fenster(page).getByRole("button", { name: "Was sehe ich hier?" })).toBeVisible();

      await erste.click();
      await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
      expect(geschickt!.question).toBe("Werden auch meine eigenen Viertel berücksichtigt?");

      // Nach einer Antwort ist das Fenster nicht mehr leer — keine Startfragen
      // mehr, dieselbe Regel wie bei den Grund-Chips (PR 24).
      await expect(erste).toHaveCount(0);
      await expect(zweite).toHaveCount(0);
    });

  test("unter der Modell-Antwort stehen zwei Daumen, und sie melden die Quelle",
    async ({ page }) => {
      // B6 der zweiten Durchsicht: Der Endpunkt nimmt `source = "lotti"` seit
      // PR 7 an, im Fenster gab es keinen Daumen. Gezählt war die Annahme,
      // nie die Güte.
      let gemeldet: Record<string, unknown> | null = null;
      await page.route("**/api/council/qa-feedback", async (route) => {
        gemeldet = route.request().postDataJSON();
        await route.fulfill({ status: 201, json: { ok: true } })
          .catch(() => { /* Test ist schon zu Ende */ });
      });
      await page.goto("/dashboard");
      await knopf(page).click();
      await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
      await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
      const hoch = fenster(page).getByRole("button", { name: "Antwort war hilfreich" });
      await expect(hoch).toBeVisible();
      await expect(fenster(page).getByRole("button", { name: "Antwort war nicht hilfreich" }))
        .toBeVisible();
      await hoch.click();
      await expect.poll(() => gemeldet).not.toBeNull();
      expect(gemeldet!.source).toBe("lotti");
      expect(gemeldet!.rating).toBe("up");
      expect(gemeldet!.question).toBe("Was sehe ich hier?");
      expect(gemeldet!.answer_excerpt).toBe(ANTWORT);
    });

  test("unter einer geprüften Antwort steht KEIN Daumen", async ({ page }) => {
    // Glossar, Seiten-Wissen und Kurzfassung sind geprüfter Text, den das
    // Fenster nur durchreicht. Ein Daumen darunter bewertete das Glossar —
    // und stünde in derselben Quote wie Lottis eigene Erklärungen.
    await page.route("**/api/council/explain", (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM_GEPRUEFT })
        .catch(() => { /* Test ist schon zu Ende */ }),
    );
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
    await expect(fenster(page).getByText(GEPRUEFTE_ANTWORT)).toBeVisible();
    await expect(fenster(page).getByRole("button", { name: "Antwort war hilfreich" }))
      .toHaveCount(0);
  });

  test("eine Archivfrage beantwortet Lotti selbst — ein Weg, eine Runde", async ({ page }) => {
    // PR 23. Tim, 22.09.2026: „Den Rat fragen — da frage ich mich manchmal,
    // warum passiert das nicht automatisch, wenn das sinnvoll ist? Ich weiß
    // als User gar nicht, was heißt denn ‚den Rat fragen'?" Der Knopf ist weg;
    // die Entscheidung, welchen Weg eine Frage nimmt, ist unsere.
    let geschickt: Record<string, unknown> | null = null;
    await page.route("**/api/council/ask", async (route) => {
      geschickt = route.request().postDataJSON();
      await route.fulfill({ status: 200, contentType: "text/event-stream",
                            body: STROM_ARCHIV })
        .catch(() => { /* Test ist schon zu Ende */ });
    });
    await page.route("**/api/council/explain", (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM_HANDOFF })
        .catch(() => { /* Test ist schon zu Ende */ }),
    );
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByLabel("Frage an Lotti").fill("Wer hat dagegen gestimmt?");
    await fenster(page).getByRole("button", { name: "Fragen" }).click();

    // Kein Knopf dazwischen: die Antwort steht einfach da, mit Belegen.
    await expect(fenster(page).getByText(RATS_ANTWORT)).toBeVisible();
    await expect(fenster(page).getByText("Stadionneubau Maastrichter Straße")).toBeVisible();
    await expect(fenster(page).getByRole("button", { name: /Den Rat fragen/ }))
      .toHaveCount(0);
    // EINE Runde: die Frage steht genau einmal da, nicht zweimal.
    await expect(fenster(page).getByText("Wer hat dagegen gestimmt?")).toHaveCount(1);
    // Der Bildschirm reist mit — sonst sucht das Archiv nach nichts.
    const screen = (geschickt as { screen?: { route?: string } })?.screen;
    expect(screen?.route).toBe("/dashboard");
    // Und der Weg ins volle Ratsgespräch steht darunter.
    await expect(fenster(page).getByRole("button", { name: /Im Ratsgespräch weiterführen/ }))
      .toBeVisible();
    // Unter einer Antwort AUS dem Archiv steht kein Weg noch einmal dorthin.
    await expect(fenster(page).getByRole("button", { name: "Im Ratsarchiv nachsehen" }))
      .toHaveCount(0);
  });

  test("die erste Archivfrage eröffnet das Gespräch — die Erklärung danach landet darin",
    async ({ page }) => {
      // Bis 22.09.2026 nahm das Fenster die Kennung aus `/ask` nur an, wenn
      // schon ein Gespräch lief — ein Riegel gegen das `ask`-Gespräch, das
      // `/ask` ohne Bildschirm anlegt. Das Backend kennt Lottis Fenster
      // inzwischen am `screen` und legt ein `lotti`-Gespräch an; der Riegel
      // kostete nur noch den Faden (gemessen: Gespräch 51, kind=ask).
      await page.route("**/api/council/ask", (route) =>
        route.fulfill({ status: 200, contentType: "text/event-stream", body: [
          `data: ${JSON.stringify({ type: "sources", sources: FUNDSTUECKE })}\n\n`,
          `data: ${JSON.stringify({ type: "token", text: RATS_ANTWORT })}\n\n`,
          `data: ${JSON.stringify({ type: "done", cited: [8525], conversation_id: 4242 })}\n\n`,
        ].join("") }).catch(() => { /* Test ist schon zu Ende */ }),
      );
      const gefragt: Record<string, unknown>[] = [];
      await page.route("**/api/council/explain", async (route) => {
        gefragt.push(route.request().postDataJSON());
        await route.fulfill({
          status: 200, contentType: "text/event-stream",
          body: gefragt.length === 1 ? STROM_HANDOFF : STROM(),
        }).catch(() => { /* Test ist schon zu Ende */ });
      });
      await page.goto("/dashboard");
      await knopf(page).click();
      // Erste Frage im LEEREN Fenster, und sie geht ins Archiv.
      await fenster(page).getByLabel("Frage an Lotti").fill("Wer hat dagegen gestimmt?");
      await fenster(page).getByRole("button", { name: "Fragen" }).click();
      await expect(fenster(page).getByText(RATS_ANTWORT)).toBeVisible();
      expect(gefragt[0].conversation_id).toBeNull();

      // Die nächste Erklärung hängt sich an DASSELBE Gespräch.
      await fenster(page).getByLabel("Frage an Lotti").fill("Und was steht hier?");
      await fenster(page).getByRole("button", { name: "Fragen" }).click();
      await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
      expect(gefragt[1].conversation_id).toBe(4242);
    });

  test("unter einer Archiv-Antwort stehen nur die ZITIERTEN Quellen", async ({ page }) => {
    // Gemessen auf /council/decision?id=2982: „1 zitiert · 41 gefunden" und
    // darunter drei Zeilen, von denen zwei nichts mit der Frage zu tun
    // hatten. Eine Quelle, die falsch wirkt, beschädigt die richtige mit.
    await page.route("**/api/council/ask", (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM_ARCHIV })
        .catch(() => { /* Test ist schon zu Ende */ }),
    );
    await page.route("**/api/council/explain", (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM_HANDOFF })
        .catch(() => { /* Test ist schon zu Ende */ }),
    );
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByLabel("Frage an Lotti").fill("Wer hat dagegen gestimmt?");
    await fenster(page).getByRole("button", { name: "Fragen" }).click();
    await expect(fenster(page).getByText(RATS_ANTWORT)).toBeVisible();

    await expect(fenster(page).getByText("Stadionneubau Maastrichter Straße")).toBeVisible();
    await expect(fenster(page).getByText("Toleranz-Fonds 2026")).toHaveCount(0);
    await expect(fenster(page).getByText("Bebauungsplan Nr. 56")).toHaveCount(0);
    // Erreichbar bleiben sie — hinter einem Klick, wie bisher.
    await fenster(page).getByRole("button", { name: /Alle 3 Quellen/ }).click();
    await expect(fenster(page).getByText("Toleranz-Fonds 2026")).toBeVisible();
  });

  test("unter einer Archiv-Antwort steht kein Baustein-Chip dieser Seite",
    async ({ page }) => {
      // Gemessen auf /council/decision?id=2982: „Lotti erklärt's einfach
      // erklären" unter der Auskunft, wer dagegen gestimmt hat. Die Antwort
      // kommt aus 9.000 Beschlüssen; ein Kasten DIESER Seite daneben ist ein
      // Themenwechsel — und die Kurzfassung IST schon Lottis Erklärung.
      await page.route("**/api/council/ask", (route) =>
        route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM_ARCHIV })
          .catch(() => { /* Test ist schon zu Ende */ }),
      );
      await page.route("**/api/council/explain", (route) =>
        route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM_HANDOFF })
          .catch(() => { /* Test ist schon zu Ende */ }),
      );
      await page.goto("/haushalt/schulden");
      await schuldenGeladen(page);
      await knopf(page).click();
      await fenster(page).getByLabel("Frage an Lotti").fill("Wer hat dagegen gestimmt?");
      await fenster(page).getByRole("button", { name: "Fragen" }).click();
      await expect(fenster(page).getByText(RATS_ANTWORT)).toBeVisible();
      await expect(fenster(page).getByRole("button", { name: /erklären$/ })).toHaveCount(0);
    });

  test("reicht das Modell weiter, bleibt die Erklärung stehen und das Archiv kommt darunter",
    async ({ page }) => {
      // Der zweite Fall: Die Regex hat nicht gegriffen, das Modell setzt
      // `WEITER: ratsfrage`. Dann ist der Archivweg der ZWEITE Schritt
      // derselben Runde — die Frage-Blase steht schon oben.
      await page.route("**/api/council/ask", (route) =>
        route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM_ARCHIV })
          .catch(() => { /* Test ist schon zu Ende */ }),
      );
      await stromStubben(page, { next: "ratsfrage" });
      await page.goto("/dashboard");
      await knopf(page).click();
      await fenster(page).getByLabel("Frage an Lotti").fill("Und wie ging das aus?");
      await fenster(page).getByRole("button", { name: "Fragen" }).click();

      await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
      await expect(fenster(page).getByText(RATS_ANTWORT)).toBeVisible();
      await expect(fenster(page).getByText("Und wie ging das aus?")).toHaveCount(1);
      await expect(fenster(page).getByRole("button", { name: /Den Rat fragen/ }))
        .toHaveCount(0);
    });

  test("beim Weiterreichen geht die Frage NICHT zusätzlich als Verlauf mit", async ({ page }) => {
    // Release-Prüfung 03.10.2026: Die Frage stand samt Erklärung im Verlauf
    // UND als neue Frage — das Archiv antwortete „Eine neue Frage ist in Ihrer
    // Nachricht nicht enthalten“, mit 0 Quellen.
    let ask: { question: string; history: { question: string }[] } | null = null;
    await page.route("**/api/council/ask", (route) => {
      ask = route.request().postDataJSON();
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM_ARCHIV })
        .catch(() => { /* Test ist schon zu Ende */ });
    });
    await stromStubben(page, { next: "ratsfrage" });
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByLabel("Frage an Lotti").fill("Und wie ging das aus?");
    await fenster(page).getByRole("button", { name: "Fragen" }).click();
    await expect(fenster(page).getByText(RATS_ANTWORT)).toBeVisible();
    expect(ask).not.toBeNull();
    expect(ask!.question).toBe("Und wie ging das aus?");
    expect(ask!.history.map((r) => r.question)).not.toContain("Und wie ging das aus?");
  });

  test("eine zu lange Frage: das Feld hält bei 300, und ein 422 nimmt sie nicht weg",
    async ({ page }) => {
      await page.goto("/dashboard");
      await knopf(page).click();
      const feld = fenster(page).getByLabel("Frage an Lotti");
      await feld.fill("x".repeat(320));
      await expect(feld).toHaveValue("x".repeat(300));
      await expect(fenster(page).getByText("300/300")).toBeVisible();

      // Kommt doch ein 422 (ein alter Stand, ein anderer Weg), steht ein Satz
      // da — nicht Pydantics Liste — und die Frage wieder im Feld.
      await page.route("**/api/council/explain", (route) => route.fulfill({
        status: 422, contentType: "application/json",
        body: JSON.stringify({ detail: [{ msg: "String should have at most 300 characters" }] }),
      }).catch(() => { /* Test ist schon zu Ende */ }));
      await feld.fill("Wie hoch sind die Schulden?");
      await fenster(page).getByRole("button", { name: "Fragen" }).click();
      await expect(fenster(page).getByText(/zu lang/)).toBeVisible();
      await expect(fenster(page).getByText(/String should/)).toHaveCount(0);
      await expect(feld).toHaveValue("Wie hoch sind die Schulden?");
    });

  test("auf der Karte liegt nichts über dem Fenster (375 px)", async ({ page }) => {
    // Release-Prüfung 03.10.2026: Ebenen-Chips und Brotkrumen der Karte lagen
    // mit `z-[500]` über Lottis Fenster und verdeckten dessen Kopf.
    await page.setViewportSize({ width: 375, height: 812 });
    // Die Karte hängt am Schalter `mein-viertel` — dazu, nicht statt Lotti.
    await page.route("**/api/app-config", async (route) => {
      try {
        const body = await (await route.fetch()).json();
        const features = new Set<string>(body.features ?? []);
        features.add("lotti-assistentin");
        features.add("mein-viertel");
        await route.fulfill({ json: { ...body, features: [...features] } });
      } catch {
        await route.fallback().catch(() => { /* der Test ist schon zu Ende */ });
      }
    });
    await page.goto("/karte");
    await expect(page.getByRole("navigation", { name: "Stufe" })).toBeVisible();
    await knopf(page).click();
    const box = (await fenster(page).boundingBox())!;
    // Kopf, Kontextzeile und Mitte — dort lagen Chips und Brotkrumen.
    for (const anteil of [0.04, 0.12, 0.2, 0.5]) {
      const oben = await page.evaluate(([x, y]) => {
        const el = document.elementFromPoint(x, y);
        return !!el?.closest("[data-lotti-fenster]");
      }, [box.x + box.width / 3, box.y + box.height * anteil]);
      expect(oben, `bei ${Math.round(anteil * 100)} % der Fensterhöhe`).toBe(true);
    }
  });

  test("Knopf und Fenster liegen UNTER einem modalen Dialog", async ({ page }) => {
    // Release-Prüfung 03.10.2026: Der Knopf lag hell über der Abdunkelung
    // des Melde-Dialogs in „Mein Viertel“ — beide `z-50`, und die
    // Reihenfolge im DOM entschied. Nachgestellt mit derselben Ebene wie
    // `components/ui/dialog.tsx` (Overlay `fixed inset-0 z-50`), und zwar
    // VOR Lottis Knoten im DOM — der ungünstigste Fall.
    await page.goto("/dashboard");
    await knopf(page).click();
    await expect(fenster(page)).toBeVisible();
    await page.evaluate(() => {
      const schleier = document.createElement("div");
      schleier.className = "fixed inset-0 z-50 bg-black/50";
      schleier.setAttribute("data-test-schleier", "");
      document.body.prepend(schleier);
    });
    for (const ziel of [knopf(page), fenster(page)]) {
      const b = (await ziel.boundingBox())!;
      const oben = await page.evaluate(([x, y]) =>
        !!document.elementFromPoint(x, y)?.closest("[data-test-schleier]"),
      [b.x + b.width / 2, b.y + b.height / 2]);
      expect(oben).toBe(true);
    }
  });

  test("unter einer Erklärung steht ein stiller Textlink ins Archiv", async ({ page }) => {
    // Der Nachweg, wenn Lotti geantwortet hat und die Person trotzdem tiefer
    // will — ein Verb, das sagt, was passiert, statt „Den Rat fragen".
    await page.route("**/api/council/ask", (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM_ARCHIV })
        .catch(() => { /* Test ist schon zu Ende */ }),
    );
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();

    const link = fenster(page).getByRole("button", { name: "Im Ratsarchiv nachsehen" });
    await expect(link).toBeVisible();
    await link.click();
    await expect(fenster(page).getByText(RATS_ANTWORT)).toBeVisible();
  });

  test("nach der ersten Runde sind die Grund-Chips weg", async ({ page }) => {
    // PR 24: „Was sehe ich hier?" sagt, was man hier tun kann. Das braucht,
    // wer noch nichts gefragt hat; danach steht es nur im Weg (Tim: „viel zu
    // viele von diesen Pills").
    await page.goto("/dashboard");
    await knopf(page).click();
    const grund = fenster(page).getByRole("button", { name: "Was sehe ich hier?" });
    await expect(grund).toBeVisible();
    await grund.click();
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();

    await expect(fenster(page).getByRole("button", { name: "Was sehe ich hier?" }))
      .toHaveCount(0);
    // Die Aufforderung steht im Platzhalter, nicht auf einem Chip.
    await expect(fenster(page).getByPlaceholder(/Frag mich zu dieser Seite/))
      .toBeVisible();
  });

  test("den Erklär-Modus gibt es nicht mehr — weder als Chip noch als Icon", async ({ page }) => {
    // Tim, 23.09.2026: „Dieses ‚Frag mich zu dieser Seite‘ und dann kann man
    // irgendwas anklicken — das ist so mega komisch." Ersetzt durch „Lotti
    // fragen" an der Markierung (s. unten, „Markieren statt Modus").
    await page.goto("/dashboard");
    await knopf(page).click();
    await expect(fenster(page).getByRole("button", { name: "Was sehe ich hier?" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Etwas auf der Seite zeigen/ })).toHaveCount(0);
    await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
    await expect(page.getByRole("button", { name: /Etwas auf der Seite zeigen/ })).toHaveCount(0);
    await expect(page.getByText(/nichts einzeln erklären/)).toHaveCount(0);
  });

  test("unter einer Antwort steht höchstens EIN Chip", async ({ page }) => {
    // Tims Bild: drei Chips, zwei Daumen, zwei Grund-Chips — sieben
    // Bedienelemente für eine Antwort. Der Strom hier böte zwei an
    // (Zielseite UND Fachwort); stehen darf genau der Wegweiser.
    await page.route("**/api/council/explain", (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: [
        `data: ${JSON.stringify({ type: "token", text: ANTWORT_FACHWORT })}\n\n`,
        `data: ${JSON.stringify({
          type: "done", mode: "explain", kind: "model", next: null,
          next_page: { route: "/haushalt/schulden", title: "Schulden der Stadt" },
          glossary: ["Umschuldung"], timings: { total_ms: 900 },
        })}\n\n`,
      ].join("") }).catch(() => { /* Test ist schon zu Ende */ }),
    );
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
    await expect(fenster(page).getByText(ANTWORT_FACHWORT)).toBeVisible();

    await expect(fenster(page).getByRole("button", { name: /^Weiter zu:/ })).toHaveCount(1);
    await expect(fenster(page).getByRole("button", { name: /^Was heißt/ })).toHaveCount(0);
  });

  test("der Wegweiser zeigt nie auf die Seite, auf der man steht", async ({ page }) => {
    // Tims Bild vom 22.09.2026: „Weiter zu: Bereichs-Steckbrief" auf dem
    // Bereichs-Steckbrief. Der Server streicht die eigene Seite inzwischen
    // aus dem Wegweiser — das hier ist der Hosenträger zum Gürtel, für den
    // Fall, dass ein Rahmen sie trotzdem trägt.
    await page.route("**/api/council/explain", (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM_SEITE })
        .catch(() => { /* Test ist schon zu Ende */ }),
    );
    await page.goto("/haushalt/schulden");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
    await expect(fenster(page).getByText(ANTWORT_SEITE)).toBeVisible();
    await expect(fenster(page).getByRole("button", { name: /^Weiter zu: Schulden der Stadt/ }))
      .toHaveCount(0);
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
      // Der Netzmitschnitt der NÄCHSTEN Frage — vor dem Absenden registriert.
      // **Über den Composer**, nicht über den Grund-Chip: Der steht seit
      // PR 24 nur noch im leeren Fenster, und hier liegt schon eine Runde.
      const anfrage = page.waitForRequest("**/api/council/explain");
      await fenster(page).getByLabel("Frage an Lotti").fill("Was sehe ich hier?");
      await fenster(page).getByRole("button", { name: "Fragen" }).click();
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
});
