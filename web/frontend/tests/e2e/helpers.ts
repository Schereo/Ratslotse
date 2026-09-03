import { Page, expect } from "@playwright/test";

const ADMIN_EMAIL = "admin@test.de";
const ADMIN_PASSWORD = "password123";

/** Register + login the admin account (first user). Returns when on /dashboard or /link. */
export async function registerAdmin(page: Page) {
  await page.goto("/register");
  await page.locator("#email").fill(ADMIN_EMAIL);
  await page.locator("#password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Konto erstellen" }).click();
  await page.waitForURL(/\/(link|dashboard)/, { timeout: 15_000 });
}

/** Den Einrichtungs-Assistenten als erledigt melden.
 *
 *  Ein frisches Konto bekommt ihn beim ersten Öffnen — als Fläche über der
 *  ganzen Seite (`fixed inset-0`). Sie fängt jeden Klick ab: Der Abmelde-Knopf
 *  in der Seitenleiste war sichtbar UND unerreichbar, und Playwright wartete
 *  30 Sekunden auf einen Klick, der nie ankam.
 *
 *  Erledigt wird er über den Server, nicht durch Klicken: `done: true` ist
 *  dasselbe, was das „Überspringen" im Assistenten sendet. So hängt kein Test,
 *  der etwas ganz anderes prüft, an den Schritten eines Assistenten. Wer den
 *  Assistenten SELBST prüfen will, ruft das hier nicht auf. */
export async function einrichtungUeberspringen(page: Page) {
  // `step: 3, done: true` ist genau das, was der Assistent am Ende selbst
  // sendet. Die 4 aus dem Router-Kommentar weist das Schema mit 422 ab — der
  // Client verschluckt den Fehler (`.catch(() => {})`), die Fläche bliebe
  // stehen, und der Test wartete 30 Sekunden auf einen Klick, der nicht ankommt.
  const antwort = await page.request.post("/api/onboarding/setup", {
    data: { step: 3, done: true },
  });
  expect(antwort.ok(), await antwort.text()).toBeTruthy();
  // Die Seite steht schon — sie hat ihren Stand vor dem POST geholt. Ohne das
  // Neuladen bleibt die Fläche stehen, obwohl der Server sie längst für
  // erledigt hält.
  await page.reload();
  await expect(page.getByRole("button", { name: /Los geht/ })).toHaveCount(0);
}

/** Die Einwilligung „Gespräche merken?" beantworten.
 *
 *  Sie steht als Karte VOR dem Eingabefeld der Frage-Seite, solange sie
 *  niemand beantwortet hat (`saves_conversations` ist dann `null`). Ein Test,
 *  der eine Frage stellen will, kommt sonst gar nicht ans Feld — und sieht nur
 *  „Deine Frage" nicht.
 *
 *  `an: false` ist die zurückhaltendere Antwort und für Tests die richtige:
 *  Sie legt nichts am Konto ab. */
export async function gespraecheNichtMerken(page: Page) {
  const antwort = await page.request.post("/api/council/conversations/setting", {
    data: { an: false },
  });
  expect(antwort.ok(), await antwort.text()).toBeTruthy();
}

/** Login an already-existing admin account. */
export async function loginAdmin(page: Page) {
  // Make the helper independent from test-file order. The register endpoint
  // may answer 409 when the account already exists; either way the following
  // login is the authoritative step.
  await page.request.post("/api/auth/register", {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  });
  await page.goto("/login");
  await page.locator("#email").fill(ADMIN_EMAIL);
  await page.locator("#password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await page.waitForURL(/\/(link|dashboard)/, { timeout: 15_000 });
  await einrichtungUeberspringen(page);
}

/** Wait for toast message to appear. */
export async function expectToast(page: Page, text: string | RegExp) {
  await expect(page.locator("[data-sonner-toast]")).toContainText(text);
}

export { ADMIN_EMAIL, ADMIN_PASSWORD };
