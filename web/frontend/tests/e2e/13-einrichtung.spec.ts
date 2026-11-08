/**
 * Der Einrichtungs-Assistent — den bisher JEDER Test übersprungen hat.
 *
 * `auth.setup.ts` hakt ihn für die Identitäten der Suite über den Server
 * ab, damit ein Test, der etwas anderes prüft, nicht an vier Schritten hängt.
 * Genau deshalb hat ihn nie einer angesehen: Er ist das Erste, was ein neues
 * Konto sieht, und die einzige Stelle, an der jemand seine Gremien und
 * Stadtteile in einem Zug wählt.
 *
 * Hier wird er ABSICHTLICH nicht übersprungen.
 */
import { expect, test } from "@playwright/test";

/** Jeder Test braucht ein FRISCHES Konto: Ein eingerichtetes bekommt den
 *  Assistenten nie wieder zu sehen. Die Adresse trägt deshalb den Zeitstempel. */
function neuesKonto() {
  return `neu-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.org`;
}

async function registrieren(page: import("@playwright/test").Page) {
  const email = neuesKonto();
  await page.goto("/register");
  // Der Anzeigename ist Pflicht — ohne ihn weist der Server die
  // Registrierung ab (422).
  await page.locator("#display-name").fill("Testkonto");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill("password123");
  await page.getByRole("button", { name: "Konto erstellen" }).click();
  await page.waitForURL(/\/(link|dashboard)/, { timeout: 15_000 });
  return email;
}

/** Der Assistent beginnt mit einem Auftakt-Schirm („Willkommen bei
 *  Ratslotse"). Erst dahinter kommen die vier Schritte. */
async function bisZuDenGremien(page: import("@playwright/test").Page) {
  await expect(page.getByRole("button", { name: /Los geht/ })).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: /Los geht/ }).click();
  await expect(page.getByText("Welche Ausschüsse interessieren dich?")).toBeVisible({ timeout: 15_000 });
}

test.describe("Ein frisches Konto", () => {
  test("bekommt den Auftakt und dahinter die Gremien-Frage", async ({ page }) => {
    await registrieren(page);
    await expect(page.getByText(/Willkommen bei/)).toBeVisible({ timeout: 15_000 });
    await bisZuDenGremien(page);
  });

  test("die Fläche fängt Klicks ab — das ist Absicht, kein Fehler", async ({ page }) => {
    // Sie liegt als `fixed inset-0` über der Seite. Der Abmelde-Knopf in der
    // Seitenleiste ist dahinter SICHTBAR und trotzdem unerreichbar; genau
    // daran hingen Tests 30 Sekunden, bevor `helpers.ts` den Assistenten über
    // den Server abschaltete. Der Test hält fest, dass das so bleibt.
    await registrieren(page);
    await expect(page.getByRole("button", { name: /Los geht/ })).toBeVisible({ timeout: 15_000 });
    // Der Abmelde-Knopf der Seitenleiste liegt DAHINTER: sichtbar für das
    // Auge, unerreichbar für den Klick. Playwright meldet das als „intercepts
    // pointer events" — genau der Zustand, den `helpers.ts` umgeht.
    const abmelden = page.getByRole("button", { name: "Abmelden" });
    if (await abmelden.count()) {
      await expect(abmelden.first().click({ timeout: 2_000 })).rejects.toThrow();
    }
  });

  test("jeder Schritt ist überspringbar — niemand wird zu einer Eingabe gezwungen", async ({ page }) => {
    await registrieren(page);
    await bisZuDenGremien(page);
    // Bis zu fünf Mal überspringen; danach muss der Assistent weg sein.
    for (let i = 0; i < 5; i++) {
      const weg = await page.getByText("Welche Ausschüsse interessieren dich?").count() === 0
        && await page.getByRole("button", { name: "Überspringen" }).count() === 0;
      if (weg) break;
      const knopf = page.getByRole("button", { name: "Überspringen" });
      if (await knopf.count() === 0) break;
      await knopf.first().click();
      await page.waitForTimeout(400);
    }
    await expect(page.getByRole("button", { name: "Überspringen" })).toHaveCount(0, { timeout: 15_000 });
  });

  test("bleibt erledigt, wenn man die App kurz verlässt und zurückkommt", async ({ page }) => {
    // Der Assistent hängt seit 11/2026 im App-Layout (components/onboarding-
    // gate.tsx) statt im Wurzel-Layout. Verlässt man die App-Hülle per
    // Client-Navigation, wird er abgebaut — und beim Zurückkehren schob ihn
    // die noch gecachte Server-Antwort (`pending: true`) wieder hoch, beim
    // Auftakt, obwohl der Server ihn längst für erledigt hielt.
    await page.setViewportSize({ width: 390, height: 844 });
    await registrieren(page);
    await bisZuDenGremien(page);
    // Alles überspringen, auch den Auffang-Schritt „noch kein Thema, kein
    // Gremium" am Ende („Später, ohne Thema").
    const weiter = page.getByRole("button", { name: /^Überspringen$|^Später, ohne Thema$/ });
    for (let i = 0; i < 8; i++) {
      if (await weiter.count() === 0) break;
      await weiter.first().click();
      await page.waitForTimeout(400);
    }
    await expect(weiter).toHaveCount(0, { timeout: 15_000 });
    const einladung = page.getByRole("button", { name: "Erst mal selbst umschauen" });
    await einladung.waitFor({ timeout: 5_000 }).catch(() => {});
    if (await einladung.count()) await einladung.click();

    // Hinaus (Mehr → Hilfe liegt außerhalb von app/(app)) und zurück, beides
    // ohne Neuladen.
    await page.getByRole("button", { name: "Mehr" }).first().click();
    await page.getByRole("dialog", { name: "Mehr" }).getByRole("link", { name: "Hilfe" }).click();
    await page.waitForURL(/\/hilfe/);
    await page.goBack();
    await page.waitForURL(/\/dashboard/);
    await expect(page.getByRole("navigation").first()).toBeVisible();
    await page.waitForTimeout(1_500);
    await expect(page.getByText(/Willkommen bei/)).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Los geht/ })).toHaveCount(0);
  });

  test("die Gremien-Auswahl merkt sich, was angetippt wurde", async ({ page }) => {
    // Die Liste kommt aus der API. In der CI ist die Ratsdatenbank leer, also
    // gesetzt statt gehofft — sonst prüfte der Test dort nichts.
    await page.route("**/api/council/committees**", (r) =>
      r.fulfill({ json: { committees: ["Verkehrsausschuss", "Kulturausschuss"] } }));
    await registrieren(page);
    await bisZuDenGremien(page);
    // Die Kacheln sind Umschalter: gewählt = gefüllt (`aria-pressed`).
    const kachel = page.getByRole("button", { name: /Verkehr/ }).first();
    await expect(kachel).toHaveAttribute("aria-pressed", "false");
    await kachel.click();
    await expect(kachel).toHaveAttribute("aria-pressed", "true");
    // Und der zweite bleibt unberührt — es ist eine Mehrfachauswahl, kein Radio.
    await expect(page.getByRole("button", { name: /Kultur/ }).first())
      .toHaveAttribute("aria-pressed", "false");
  });

  test("ein Stadtthema steht nur an seiner Kachel — anwählen, anpassen, abwählen", async ({ page }) => {
    // Bis 11/2026 stand ein gewähltes Stadtthema zusätzlich oben in „Deine
    // Themen" und wiederholte, was die Kachel schon zeigte. Die Kachel ist
    // jetzt der Umschalter und trägt „anpassen" selbst.
    //
    // In der CI ist die Ratsdatenbank leer — dort gäbe es keine Kachel (zu
    // wenig Beschlüsse). Vorschläge und Themenliste sind deshalb gesetzt.
    let themen: { id: number; name: string; description: string; image_key: string; matched: boolean; hits_12m: number }[] = [];
    await page.route("**/api/topics", (r) => {
      if (r.request().method() === "GET") return r.fulfill({ json: themen });
      if (r.request().method() === "POST") {
        const t = { id: themen.length + 1, ...r.request().postDataJSON(), image_key: "cycling", matched: true, hits_12m: 7 };
        themen.push(t);
        return r.fulfill({ json: t });
      }
      return r.continue();
    });
    await page.route("**/api/topics/*", (r) => {
      if (r.request().method() !== "DELETE") return r.continue();
      const id = Number(new URL(r.request().url()).pathname.split("/").pop());
      themen = themen.filter((t) => t.id !== id);
      return r.fulfill({ status: 204 });
    });
    // Nach der allgemeinen Regel angelegt: Die zuletzt angelegte gewinnt.
    // Vierzehn Kacheln, damit die Liste wirklich scrollen muss.
    const weitere = Array.from({ length: 13 }, (_, i) => ({ name: `Thema ${i + 1}`, description: "", n: 5, key: `thema-${i}` }));
    await page.route("**/api/topics/suggestions**", (r) => r.fulfill({ json: {
      city: [{ name: "Radverkehr", description: "Radwege, Fahrradstraßen und Abstellanlagen.", n: 7, key: "cycling" }, ...weitere],
      suggestions: [], districts: [],
    } }));
    await registrieren(page);
    await bisZuDenGremien(page);
    await page.getByRole("button", { name: /Weiter/ }).last().click();
    await expect(page.getByText("Worüber willst du Bescheid wissen?")).toBeVisible({ timeout: 15_000 });

    const kachel = page.locator("button[aria-pressed]", { hasText: "Radverkehr" });
    const anpassen = page.getByRole("button", { name: "Radverkehr anpassen" });
    await expect(kachel).toHaveAttribute("aria-pressed", "false");
    await expect(anpassen).toHaveCount(0);
    // Bis 11/2026 hing „anpassen" als Zeile unter der Kachel, und jeder Klick
    // machte die ganze Reihe höher. Jetzt liegt es in der Spalte rechts.
    const hoehe = () => kachel.locator("xpath=..").evaluate((li) => li.getBoundingClientRect().height);
    const ungewaehlt = await hoehe();

    await kachel.click();
    await expect(kachel).toHaveAttribute("aria-pressed", "true");
    await expect(anpassen).toBeEnabled();
    expect(await hoehe()).toBe(ungewaehlt);
    await expect(page.getByText(/Deine Themen/)).toHaveCount(0);
    expect(themen.map((t) => t.name)).toEqual(["Radverkehr"]);

    // Ein zweiter Klick nimmt es wieder heraus.
    await kachel.click();
    await expect(kachel).toHaveAttribute("aria-pressed", "false");
    await expect(anpassen).toHaveCount(0);
    // Die Anzeige springt sofort um; gelöscht ist erst, wenn der Server es war.
    await expect.poll(() => themen.length).toBe(0);

    // Die Liste scrollt in sich: Wer bis zur letzten Kachel geht, hat das
    // Feld für ein eigenes Thema weiter vor Augen.
    await page.locator("button[aria-pressed]", { hasText: "Thema 13" }).scrollIntoViewIfNeeded();
    await expect(page.getByRole("textbox", { name: "Thema" })).toBeInViewport();
  });

  test("ein eigenes Thema sagt, dass es sucht — und der Hinweis folgt der gespeicherten Zahl", async ({ page }) => {
    // „Entlastungsstraße" (Tims Befund 08.11.2026): Erst stand „hat der Rat
    // bisher nichts entschieden" da, darunter die Zeile mit „6 Beschlüsse in
    // 12 Monaten". Der Hinweis hängt jetzt an der Antwort des Anlegens — an
    // derselben Zahl wie die Zeile —, nicht am Urteil davor.
    let antwortAnlegen = { decision_count: 6, matched: true };
    let freigeben: () => void = () => {};
    const beschreibungDa = new Promise<void>((r) => { freigeben = r; });
    let themen: object[] = [];
    await page.route("**/api/topics/describe", async (r) => {
      await beschreibungDa;
      return r.fulfill({ json: {
        name: "Entlastungsstraße", description: "Planungen zu einer Entlastungsstraße.", verdict: "plausibel",
        matches: 0, matches_capped: false, examples: [], is_council_topic: true, reason: "",
        vague: false, hint: "", suggestion: "", parts: [],
      } });
    });
    await page.route("**/api/topics", (r) => {
      if (r.request().method() === "GET") return r.fulfill({ json: themen });
      const t = { id: themen.length + 1, ...r.request().postDataJSON(), image_key: null,
                  hits_12m: antwortAnlegen.decision_count, ...antwortAnlegen };
      themen = [...themen, t];
      return r.fulfill({ json: t });
    });
    await page.route("**/api/topics/suggestions**", (r) => r.fulfill({ json: { city: [], suggestions: [], districts: [] } }));
    await registrieren(page);
    await bisZuDenGremien(page);
    await page.getByRole("button", { name: /Weiter/ }).last().click();
    await expect(page.getByText("Worüber willst du Bescheid wissen?")).toBeVisible({ timeout: 15_000 });

    const feld = page.getByRole("textbox", { name: "Thema" });
    await feld.fill("Entlastungsstraße");
    await feld.press("Enter");
    // Solange die Beschreibung entsteht, steht da, was passiert.
    await expect(page.getByText(/Lotti sucht passende Beschlüsse/)).toBeVisible();
    freigeben();
    await expect(page.getByText(/Lotti sucht passende Beschlüsse/)).toHaveCount(0, { timeout: 15_000 });
    // Sechs gespeicherte Treffer: kein „nichts entschieden", obwohl das
    // Urteil davor „plausibel" lautete.
    await expect(page.getByText(/6\s*Beschlüsse in 12 Monaten/)).toBeVisible();
    await expect(page.getByText(/hat der Rat bisher nichts entschieden/)).toHaveCount(0);

    // Und umgekehrt: Findet das Anlegen nichts, steht der Hinweis da.
    antwortAnlegen = { decision_count: 0, matched: true };
    await feld.fill("Grundschule Krusenbusch");
    await feld.press("Enter");
    await expect(page.getByText(/Über „Grundschule Krusenbusch" hat der Rat bisher nichts entschieden/)).toBeVisible({ timeout: 15_000 });
  });

  test("die Stadtteile nennen keine Grenze, bis man an sie stößt", async ({ page }) => {
    // Tims Befund 08.11.2026: „2 von 3 Stadtteilen · Weiter" las sich wie die
    // Aufgabe, drei zu wählen. Die Grenze steht erst da, wenn jemand einen
    // vierten antippt. Die Liste ist gesetzt — in der CI fehlen Beschlüsse,
    // und ohne sie ist kein Stadtteil wählbar.
    await page.route("**/api/council/districts**", (r) => r.fulfill({ json: { districts: [
      { place_id: "donnerschwee", name: "Donnerschwee", kind: "local_area", count: 12 },
      { place_id: "eversten", name: "Eversten", kind: "local_area", count: 9 },
      { place_id: "haarentor", name: "Haarentor", kind: "local_area", count: 7 },
      { place_id: "nadorst", name: "Nadorst", kind: "local_area", count: 5 },
    ] } }));
    await registrieren(page);
    await bisZuDenGremien(page);
    await page.getByRole("button", { name: "Überspringen" }).first().click();   // Gremien
    await expect(page.getByText(/Worüber willst du/)).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: "Überspringen" }).first().click();   // Themen
    await expect(page.getByText("Welche Stadtteile interessieren dich?")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Bis zu drei/)).toHaveCount(0);

    const pille = (name: string) => page.getByRole("button", { name, exact: true });
    await pille("Donnerschwee").click();
    await pille("Eversten").click();
    await expect(page.getByRole("button", { name: "2 Stadtteile · Weiter" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/von 3/)).toHaveCount(0);

    await pille("Haarentor").click();
    await expect(page.getByRole("button", { name: "3 Stadtteile · Weiter" })).toBeVisible({ timeout: 15_000 });
    await pille("Nadorst").click();
    await expect(page.getByText(/Für den Anfang reichen drei Stadtteile/)).toBeVisible();
    await expect(pille("Nadorst")).toHaveAttribute("aria-pressed", "false");
  });

  test("der Server kennt den Stand — nicht nur der Browser", async ({ page }) => {
    // Wer die App mittendrin schließt, macht dort weiter. Das kann nur
    // funktionieren, wenn der Schritt auf dem Server steht.
    await registrieren(page);
    const stand = await page.request.get("/api/onboarding/setup");
    expect(stand.ok()).toBeTruthy();
    const daten = await stand.json();
    // Die Form, an der die Oberfläche entscheidet: `pending` heißt „zeig ihn",
    // `step` ist die Stelle, an der jemand aufgehört hat.
    expect(daten).toMatchObject({ pending: true, step: 0, done_at: null });
  });
});

test.describe("Ein eingerichtetes Konto", () => {
  test("sieht den Assistenten nicht wieder", async ({ page }) => {
    await registrieren(page);
    const antwort = await page.request.post("/api/onboarding/setup", { data: { step: 3, done: true } });
    expect(antwort.ok()).toBeTruthy();
    // Der Server führt ihn jetzt als erledigt — nicht nur der Browser.
    const stand = await (await page.request.get("/api/onboarding/setup")).json();
    expect(stand.pending).toBeFalsy();
    await page.reload();
    await expect(page.getByRole("button", { name: /Los geht/ })).toHaveCount(0);
    await expect(page.getByText("Welche Ausschüsse interessieren dich?")).toHaveCount(0);
    // Und die Seite darunter ist wieder bedienbar.
    await page.goto("/topics");
    await expect(page.locator("main")).not.toBeEmpty();
  });
});
