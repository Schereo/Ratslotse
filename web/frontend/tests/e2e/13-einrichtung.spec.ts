/**
 * Der Einrichtungs-Assistent — den bisher JEDER Test übersprungen hat.
 *
 * `einrichtungUeberspringen()` in `helpers.ts` schaltet ihn über den Server
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
  await expect(page.getByText("Welche Gremien interessieren dich?")).toBeVisible({ timeout: 15_000 });
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
      const weg = await page.getByText("Welche Gremien interessieren dich?").count() === 0
        && await page.getByRole("button", { name: "Überspringen" }).count() === 0;
      if (weg) break;
      const knopf = page.getByRole("button", { name: "Überspringen" });
      if (await knopf.count() === 0) break;
      await knopf.first().click();
      await page.waitForTimeout(400);
    }
    await expect(page.getByRole("button", { name: "Überspringen" })).toHaveCount(0, { timeout: 15_000 });
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
    await expect(page.getByText("Welche Gremien interessieren dich?")).toHaveCount(0);
    // Und die Seite darunter ist wieder bedienbar.
    await page.goto("/topics");
    await expect(page.locator("main")).not.toBeEmpty();
  });
});
