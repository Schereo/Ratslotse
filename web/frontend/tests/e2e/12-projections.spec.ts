import { expect, test, type Page } from "@playwright/test";
import type { User } from "@/lib/types";
import type { ApiAntwort } from "@/lib/vertrag";

const moderator = {
  id: 92,
  email: "projektion@example.org",
  role: "moderator",
  status: "active",
  email_verified: true,
  delivery_channel: "email",
  apple_linked: false,
  has_password: true,
} satisfies User;
const regularUser = { ...moderator, id: 93, role: "user" } satisfies User;
const onboarding = { steps: [], celebrated: true } satisfies ApiAntwort<"/onboarding">;
const setup = { step: 3, started_at: null, done_at: "2026-09-05T00:00:00Z", pending: false } satisfies ApiAntwort<"/onboarding/setup">;
const badges = { badges: [], earned_count: 0, newly_earned: [], next: null, total: 0 } satisfies ApiAntwort<"/badges">;

type Queue = ApiAntwort<"/moderation/projektionen">;
type Detail = ApiAntwort<"/moderation/projektionen/{report_id}">;
type Confirmation = ApiAntwort<"/moderation/projektionen/{report_id}/neue-stadtweite-projektion", "post">;

function json(body: unknown, status = 200) {
  return { status, contentType: "application/json", body: JSON.stringify(body) };
}

async function signedIn(page: Page, user: User = moderator) {
  await page.route("**/api/auth/me", (route) => route.fulfill(json(user)));
  await page.route("**/api/onboarding", (route) => route.fulfill(json(onboarding)));
  await page.route("**/api/onboarding/setup", (route) => route.fulfill(json(setup)));
  await page.route("**/api/topics/unread-count", (route) => route.fulfill(json({ total: 0 })));
  await page.route("**/api/badges", (route) => route.fulfill(json(badges)));
}

const queue: Queue = {
  reports: [{
    id: 81,
    content_revision: 2,
    text_preview: "Fiktive stadtweite Beobachtung für eine bewusste Projektion.",
    category: "public_space",
    scope_kind: "citywide",
    observed_on: "2026-09-02",
  }],
  total: 1,
  limit: 20,
  offset: 0,
};
const detail: Detail = {
  id: 81,
  content_revision: 2,
  category: "public_space",
  scope_kind: "citywide",
  observations: [{
    text: "Fiktive stadtweite Beobachtung für eine bewusste Projektion.",
    observed_on: "2026-09-02",
  }],
};

test.describe("Human-confirmed public projection", () => {
  test("authors public copy and publishes only after explicit confirmation", async ({ page }) => {
    await signedIn(page);
    let confirmationBody: unknown;
    let confirmed = false;
    await page.route("**/api/moderation/projektionen?*", (route) => route.fulfill(json(
      confirmed ? { ...queue, reports: [], total: 0 } : queue,
    )));
    await page.route("**/api/moderation/projektionen/81", (route) => route.fulfill(json(detail)));
    await page.route("**/api/moderation/projektionen/81/neue-stadtweite-projektion", async (route) => {
      confirmationBody = route.request().postDataJSON();
      confirmed = true;
      await route.fulfill(json({
        report_id: 81,
        content_revision: 2,
        problem_id: 501,
        problem_title: "Fiktive öffentliche Sitzmöglichkeiten",
      } satisfies Confirmation, 201));
    });

    await page.goto("/moderation/projektionen");
    await page.getByRole("button", { name: /Fiktive stadtweite Beobachtung.*öffentlich zuordnen/i }).click();
    await expect(page.getByRole("heading", { name: "Öffentliche Zuordnung vorbereiten" })).toBeFocused();
    await expect(page.getByText("Privater Ort")).toHaveCount(0);
    await expect(page.getByText(/Koordinaten/)).toHaveCount(0);
    await page.getByRole("button", { name: "Neue stadtweite Projektion" }).click();
    await page.getByLabel("Öffentlicher Titel").fill("Fiktive öffentliche Sitzmöglichkeiten");
    await page.getByLabel("Öffentliche Zusammenfassung").fill("Eine bewusst öffentliche, fiktive Zusammenfassung ohne private Rohdaten.");
    await page.getByRole("button", { name: "Veröffentlichung abschließend prüfen" }).click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Private Texte, Identität und genauer Ort bleiben ausgeschlossen");
    expect(confirmed).toBe(false);
    await dialog.getByRole("button", { name: "Öffentlich zuordnen" }).click();

    await expect(page.getByRole("heading", { name: "Öffentliche Projektion bestätigt" })).toBeFocused();
    await expect(page.getByRole("link", { name: "Öffentliche Ansicht öffnen" })).toHaveAttribute("href", "/probleme/501");
    expect(confirmationBody).toEqual({
      expected_revision: 2,
      title: "Fiktive öffentliche Sitzmöglichkeiten",
      summary: "Eine bewusst öffentliche, fiktive Zusammenfassung ohne private Rohdaten.",
    });
  });

  test("assigns to an existing public target without exposing hidden location", async ({ page }) => {
    await signedIn(page);
    await page.route("**/api/moderation/projektionen?*", (route) => route.fulfill(json(queue)));
    await page.route("**/api/moderation/projektionen/81", (route) => route.fulfill(json(detail)));
    await page.route("**/api/moderation/projektionen/81/ziele?*", (route) => route.fulfill(json([{
      problem_id: 77,
      title: "Bestehende fiktive Projektion",
      summary: "Bereits öffentliche fiktive Zusammenfassung.",
      category: "public_space",
      scope_kind: "citywide",
      status: "new",
      independent_reports: 2,
    }])));
    let body: unknown;
    await page.route("**/api/moderation/projektionen/81/bestehendes-problem", async (route) => {
      body = route.request().postDataJSON();
      await route.fulfill(json({ report_id: 81, content_revision: 2, problem_id: 77, problem_title: "Bestehende fiktive Projektion" }, 201));
    });

    await page.goto("/moderation/projektionen");
    await page.getByRole("button", { name: /öffentlich zuordnen/i }).click();
    await page.getByRole("button", { name: "Bestehendem Problem zuordnen" }).click();
    await page.getByLabel("Nach öffentlichem Titel suchen").fill("Bestehende");
    await page.getByRole("button", { name: /Bestehende fiktive Projektion/ }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Öffentlich zuordnen" }).click();

    await expect(page.getByText("Öffentliche Projektion bestätigt")).toBeVisible();
    expect(body).toEqual({ expected_revision: 2, problem_id: 77 });
  });

  test("keeps authored public text after a conflict and permits an explicit retry", async ({ page }) => {
    await signedIn(page);
    let attempts = 0;
    await page.route("**/api/moderation/projektionen?*", (route) => route.fulfill(json(queue)));
    await page.route("**/api/moderation/projektionen/81", (route) => route.fulfill(json(detail)));
    await page.route("**/api/moderation/projektionen/81/neue-stadtweite-projektion", async (route) => {
      attempts += 1;
      if (attempts === 1) {
        await route.fulfill(json({ detail: "Vorübergehend nicht erreichbar." }, 503));
        return;
      }
      await route.fulfill(json({
        report_id: 81,
        content_revision: 2,
        problem_id: 503,
        problem_title: "Fiktiver Retry-Titel",
      } satisfies Confirmation, 201));
    });

    await page.goto("/moderation/projektionen");
    await page.getByRole("button", { name: /öffentlich zuordnen/i }).click();
    await page.getByRole("button", { name: "Neue stadtweite Projektion" }).click();
    await page.getByLabel("Öffentlicher Titel").fill("Fiktiver Retry-Titel");
    await page.getByLabel("Öffentliche Zusammenfassung").fill("Diese fiktive Formulierung bleibt nach einem Konflikt erhalten.");
    await page.getByRole("button", { name: "Veröffentlichung abschließend prüfen" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Öffentlich zuordnen" }).click();

    await expect(page.getByText("Vorübergehend nicht erreichbar.")).toBeVisible();
    await expect(page.getByLabel("Öffentlicher Titel")).toHaveValue("Fiktiver Retry-Titel");
    await expect(page.getByLabel("Öffentliche Zusammenfassung")).toHaveValue("Diese fiktive Formulierung bleibt nach einem Konflikt erhalten.");
    await page.getByRole("button", { name: "Veröffentlichung abschließend prüfen" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Öffentlich zuordnen" }).click();
    await expect(page.getByText("Öffentliche Projektion bestätigt")).toBeVisible();
    expect(attempts).toBe(2);
  });

  test("provides an explicit safe exit when a candidate disappears", async ({ page }) => {
    await signedIn(page);
    await page.route("**/api/moderation/projektionen?*", (route) => route.fulfill(json(queue)));
    await page.route("**/api/moderation/projektionen/81", (route) => route.fulfill(json({ detail: "Meldung nicht gefunden." }, 404)));

    await page.goto("/moderation/projektionen");
    const trigger = page.getByRole("button", { name: /öffentlich zuordnen/i });
    await trigger.click();
    await expect(page.getByText("Die Freigabe ist nicht mehr verfügbar")).toBeVisible();
    await page.getByRole("button", { name: "Zur Projektionsliste" }).click();
    await expect(trigger).toBeFocused();
  });

  test("keeps regular users out without loading projection data", async ({ page }) => {
    await signedIn(page, regularUser);
    let privateCalls = 0;
    await page.route("**/api/moderation/projektionen**", (route) => {
      privateCalls += 1;
      return route.fulfill(json({ detail: "Nicht erlaubt." }, 403));
    });

    await page.goto("/moderation/projektionen");

    await expect(page.getByText("Moderationsrechte erforderlich")).toBeVisible();
    expect(privateCalls).toBe(0);
  });

  test("stays usable on a narrow screen", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 760 });
    await signedIn(page);
    await page.route("**/api/moderation/projektionen?*", (route) => route.fulfill(json(queue)));
    await page.route("**/api/moderation/projektionen/81", (route) => route.fulfill(json(detail)));

    await page.goto("/moderation/projektionen");
    await page.getByRole("button", { name: /öffentlich zuordnen/i }).click();

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
