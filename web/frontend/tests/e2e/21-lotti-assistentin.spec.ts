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
const GEPRUEFTE_ANTWORT = "Tilgung ist die Rückzahlung eines Kredits.";

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

/** Der Weg OHNE Modell: Glossar, Seiten-Wissen, „Lotti erklärt's einfach".
 *  Ein Token, ein `done` mit `mode: "deterministic"` — genau so schickt es
 *  `POST /council/explain`, wenn `deterministic_answer` getroffen hat. */
const STROM_GEPRUEFT = [
  `data: ${JSON.stringify({ type: "token", text: GEPRUEFTE_ANTWORT })}\n\n`,
  `data: ${JSON.stringify({
    type: "done", mode: "deterministic", kind: "glossary",
    next: null, glossary: [], timings: { total_ms: 4 },
  })}\n\n`,
].join("");

/** Eine Modell-Antwort, in der ein Fachwort aus dem Glossar steht.
 *
 *  **„Tilgung" tut es nicht**, so naheliegend es auf der Schulden-Seite wäre:
 *  Das Glossar ist kuratiert (`kern/glossar.py`, 149 Begriffe) und kennt das
 *  Wort nicht. Ein Test auf ein Wort, das gar kein Begriff ist, prüfte die
 *  eigene Erwartung statt die Erkennung. */
const ANTWORT_FACHWORT = "Die Stadt zahlt jedes Jahr zurück; eine Umschuldung ändert daran nichts.";

const STROM_FACHWORT = [
  `data: ${JSON.stringify({ type: "token", text: ANTWORT_FACHWORT })}\n\n`,
  `data: ${JSON.stringify({
    type: "done", mode: "explain", kind: "model", next: null,
    glossary: ["Umschuldung"], timings: { total_ms: 900 },
  })}\n\n`,
].join("");

/** Eine Antwort, die auf eine andere Haushalts-Seite verweist (PR 21). Die
 *  Adresse steht NICHT im Text — sie reist im `done`-Rahmen als `next_page`,
 *  geprüft gegen `kern/knowledge.py` und die Rechte des Kontos. */
const ANTWORT_SEITE = "Der Schuldenstand lag Ende 2024 bei rund 295 Millionen Euro.";

const STROM_SEITE = [
  `data: ${JSON.stringify({ type: "token", text: ANTWORT_SEITE })}\n\n`,
  `data: ${JSON.stringify({
    type: "done", mode: "explain", kind: "model", next: null,
    next_page: { route: "/haushalt/schulden", title: "Wie viel Schulden hat Oldenburg?" },
    glossary: [], timings: { total_ms: 900 },
  })}\n\n`,
].join("");

/** Eine Antwort mit Haushaltszahlen (PR 28). Die Papiere reisen NICHT im
 *  Text, sondern im `done`-Rahmen als `evidence` — dieselbe Auswahl, die den
 *  Prompt gefüllt hat (`qa.geld_auswahl`).
 *
 *  Drei Belege, drei Fälle: einer, dessen Jahr noch fehlt (es kommt aus dem
 *  Baustein), einer, der es schon im Titel trägt, und einer ohne Adresse. */
const ANTWORT_ZAHL = "Der Schuldenstand lag Ende 2024 bei rund 295 Millionen Euro.";
const BELEGE = [
  { label: "Statistisches Jahrbuch, Tabelle 1108", year: 2024,
    url: "https://example.org/jahrbuch-1108.pdf" },
  { label: "Jahresabschluss 2023", year: 2023, url: "https://example.org/ja-2023.pdf" },
  { label: "Prüfbericht 2022", year: 2022, url: null },
];

const STROM_BELEGE = [
  `data: ${JSON.stringify({ type: "token", text: ANTWORT_ZAHL })}\n\n`,
  `data: ${JSON.stringify({
    type: "done", mode: "explain", kind: "model", next: null, next_page: null,
    glossary: [], evidence: BELEGE, timings: { total_ms: 900 },
  })}\n\n`,
].join("");

/** Der Strom, mit dem `/explain` eine Archivfrage beantwortet: **gar nicht.**
 *  Seit PR 23 entscheidet der Server am Wortlaut und schickt ohne einen
 *  einzigen Modellaufruf den Schritt plus `mode: "handoff"` — das Fenster
 *  stellt dann von selbst die Ratsfrage, als zweiten Schritt derselben Runde. */
const STROM_HANDOFF = [
  `data: ${JSON.stringify({ type: "step", step: "archiv" })}\n\n`,
  `data: ${JSON.stringify({
    type: "done", mode: "handoff", kind: "archiv",
    next: "ratsfrage", next_page: null, glossary: [], timings: { total_ms: 3 },
  })}\n\n`,
].join("");

/** Die Ratsantwort aus dem Archiv — Quellen, Text, zitierte Nummern.
 *
 *  **Drei Fundstücke, eines zitiert**: genau die Lage, die Tim am
 *  22.09.2026 auf `/council/decision?id=2982` gesehen hat („1 zitiert · 41
 *  gefunden", darunter drei Zeilen, zwei davon zur Sache fremd). */
const RATS_ANTWORT = "Der Rat hat 2026 zugestimmt.";
const FUNDSTUECKE = [
  { id: 8525, title: "Stadionneubau Maastrichter Straße", committee: "Rat",
    session_date: "2026-06-01" },
  { id: 11, title: "Toleranz-Fonds 2026", committee: "Rat", session_date: "2026-03-01" },
  { id: 12, title: "Bebauungsplan Nr. 56", committee: "Rat", session_date: "2026-02-01" },
];
const STROM_ARCHIV = [
  `data: ${JSON.stringify({ type: "sources", sources: FUNDSTUECKE })}\n\n`,
  `data: ${JSON.stringify({ type: "token", text: RATS_ANTWORT })}\n\n`,
  `data: ${JSON.stringify({ type: "done", cited: [8525] })}\n\n`,
].join("");

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
      await page.waitForLoadState("networkidle");
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

  test("nach der ersten Runde sind die Grund-Chips weg — der Zeiger bleibt",
    async ({ page }) => {
      // PR 24: „Was sehe ich hier?" und „Etwas auf der Seite zeigen" sagen,
      // was man hier tun kann. Das braucht, wer noch nichts gefragt hat;
      // danach stehen sie nur im Weg (Tim: „viel zu viele von diesen Pills").
      await page.goto("/dashboard");
      await knopf(page).click();
      const grund = fenster(page).getByRole("button", { name: "Was sehe ich hier?" });
      await expect(grund).toBeVisible();
      await grund.click();
      await expect(fenster(page).getByText(ANTWORT)).toBeVisible();

      await expect(fenster(page).getByRole("button", { name: "Was sehe ich hier?" }))
        .toHaveCount(0);
      // Der Erklär-Modus bleibt erreichbar — als stilles Icon am Composer.
      const zeiger = fenster(page).getByRole("button", { name: "Etwas auf der Seite zeigen" });
      await expect(zeiger).toHaveCount(1);
      await expect(zeiger).toBeVisible();
      // Und die Aufforderung steht im Platzhalter, nicht auf einem Chip.
      await expect(fenster(page).getByPlaceholder(/Frag mich zu dieser Seite/))
        .toBeVisible();
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
          next_page: { route: "/haushalt/schulden", title: "Wie viel Schulden hat Oldenburg?" },
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
    await expect(fenster(page).getByRole("button", { name: /^Weiter zu: Wie viel Schulden/ }))
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
    await page.waitForLoadState("networkidle");
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

      const chip = fenster(page).getByRole("button", { name: /^Weiter zu: Wie viel Schulden/ });
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
      await page.waitForLoadState("networkidle");
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
