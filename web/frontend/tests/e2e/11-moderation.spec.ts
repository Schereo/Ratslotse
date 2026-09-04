import { expect, test, type Page } from "@playwright/test";
import type { User } from "@/lib/types";
import type { ApiAntwort } from "@/lib/vertrag";

const moderator = {
  id: 91,
  email: "moderation@example.org",
  role: "moderator",
  status: "active",
  email_verified: true,
  delivery_channel: "email",
  apple_linked: false,
  has_password: true,
} satisfies User;
const onboarding = { steps: [], celebrated: true } satisfies ApiAntwort<"/onboarding">;
const setup = {
  step: 3,
  started_at: null,
  done_at: "2026-09-05T00:00:00Z",
  pending: false,
} satisfies ApiAntwort<"/onboarding/setup">;
const badges = {
  badges: [],
  earned_count: 0,
  newly_earned: [],
  next: null,
  total: 0,
} satisfies ApiAntwort<"/badges">;

type Queue = ApiAntwort<"/moderation/meldungen">;
type Detail = ApiAntwort<"/moderation/meldungen/{report_id}">;

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
    id: 73,
    text_preview: "An der fiktiven Querung fehlt eine sichere Absenkung.",
    category: "mobility",
    scope_kind: "point",
    observed_on: "2026-09-01",
    local_outcome: "external_review_candidate",
    local_reason_codes: [],
    ai_verdict: "suitable",
    ai_reason_code: "municipal_problem",
  }],
  total: 1,
  limit: 20,
  offset: 0,
};

const detail: Detail = {
  id: 73,
  category: "mobility",
  scope_kind: "point",
  content_revision: 1,
  observations: [{
    text: "An der fiktiven Querung fehlt eine sichere Absenkung.",
    observed_on: "2026-09-01",
  }],
  local_outcome: "external_review_candidate",
  local_reason_codes: [],
  ai_verdict: "suitable",
  ai_reason_code: "municipal_problem",
};

test.describe("Private human moderation", () => {
  test("routes moderation-only accounts away from the general app", async ({ page }) => {
    await page.route("**/api/**", (route) => route.fulfill(json({ detail: "Nicht erlaubt." }, 403)));
    await signedIn(page);
    await page.route("**/api/moderation/meldungen?*", (route) => route.fulfill(json({
      reports: [],
      total: 0,
      limit: 20,
      offset: 0,
    } satisfies Queue)));

    await page.goto("/dashboard");

    await expect(page).toHaveURL(/\/moderation\/meldungen$/);
    await expect(page.getByRole("heading", { level: 1, name: "Meldungen prüfen" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Abmelden" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Befehle|Feedback/ })).toHaveCount(0);
  });

  test("keeps the moderator in a minimized, human-controlled rejection flow", async ({ page }) => {
    await signedIn(page);
    let decisions = 0;
    let decided = false;
    let releaseDraft!: () => void;
    const draftGate = new Promise<void>((resolve) => { releaseDraft = resolve; });
    let submittedBody: Record<string, unknown> | undefined;
    await page.route("**/api/moderation/meldungen?*", (route) => route.fulfill(json(
      decided ? { reports: [], total: 0, limit: 20, offset: 0 } satisfies Queue : queue,
    )));
    await page.route("**/api/moderation/meldungen/73", (route) => route.fulfill(json(detail)));
    await page.route("**/api/moderation/meldungen/73/ablehnungsentwurf", async (route) => {
      await draftGate;
      await route.fulfill(json({
        content_revision: 1,
        suggestion: "Bitte beschreiben Sie den kommunalen Bezug noch genauer.",
        available: true,
      }));
    });
    await page.route("**/api/moderation/meldungen/73/entscheidung", async (route) => {
      decisions += 1;
      decided = true;
      submittedBody = route.request().postDataJSON();
      await route.fulfill(json({
        report_id: 73,
        content_revision: 1,
        outcome: "rejected",
        rejection_explanation: String(submittedBody?.rejection_explanation ?? ""),
        decided_at: "2026-09-05T09:00:00Z",
      }));
    });

    await page.goto("/moderation/meldungen");

    await expect(page.getByRole("heading", { level: 1, name: "Meldungen prüfen" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Moderation", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Meine Meldungen" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Befehle|Feedback/ })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Abmelden" })).toBeVisible();
    const queueTrigger = page.getByRole("button", { name: /An der fiktiven Querung.*prüfen/i });
    await queueTrigger.click();
    const detailHeading = page.getByRole("heading", { level: 2, name: "Menschliche Prüfung" });
    await expect(detailHeading).toBeFocused();
    await page.getByRole("button", { name: "Schließen" }).click();
    await expect(queueTrigger).toBeFocused();
    await queueTrigger.click();
    await expect(page.getByText("Automatischer Hinweis: wahrscheinlich geeignet")).toBeVisible();
    await expect(page.getByText(/Als kommunales Problem eingeschätzt/)).toBeVisible();
    await expect(page.getByText(/keine automatische Entscheidung/i)).toBeVisible();
    await expect(page.getByText("Vertraulicher Fantasieort")).toHaveCount(0);
    await expect(page.getByText("53.143")).toHaveCount(0);

    await page.getByRole("button", { name: "Ablehnung vorbereiten" }).click();
    const explanation = page.getByLabel("Erklärung für die meldende Person");
    await expect(page.getByText("Entwurf wird erstellt…")).toBeVisible();
    expect(decisions).toBe(0);
    await explanation.fill("Diese Meldung betrifft kein kommunales Anliegen.");
    releaseDraft();
    await expect(page.getByText("Entwurf wird erstellt…")).toHaveCount(0);
    await expect(explanation).toHaveValue("Diese Meldung betrifft kein kommunales Anliegen.");
    await page.getByRole("button", { name: "Ablehnung abschließend prüfen" }).click();
    await expect(page.getByRole("heading", { name: "Meldung endgültig ablehnen?" })).toBeVisible();
    expect(decisions).toBe(0);
    await page.getByRole("dialog").getByRole("button", { name: "Ablehnung verbindlich speichern" }).click();

    expect(decisions).toBe(1);
    expect(submittedBody).toEqual({
      expected_revision: 1,
      outcome: "rejected",
      rejection_explanation: "Diese Meldung betrifft kein kommunales Anliegen.",
    });
    await expect(page.getByText("Die Ablehnung wurde gespeichert.")).toBeVisible();
  });

  test("preserves manual text when drafting is unavailable", async ({ page }) => {
    await signedIn(page);
    let releaseDraft!: () => void;
    const draftGate = new Promise<void>((resolve) => { releaseDraft = resolve; });
    await page.route("**/api/moderation/meldungen?*", (route) => route.fulfill(json(queue)));
    await page.route("**/api/moderation/meldungen/73", (route) => route.fulfill(json(detail)));
    await page.route("**/api/moderation/meldungen/73/ablehnungsentwurf", async (route) => {
      await draftGate;
      await route.fulfill(json({ content_revision: 1, suggestion: null, available: false }));
    });

    await page.goto("/moderation/meldungen");
    await page.getByRole("button", { name: /An der fiktiven Querung.*prüfen/i }).click();
    await page.getByRole("button", { name: "Ablehnung vorbereiten" }).click();
    const explanation = page.getByLabel("Erklärung für die meldende Person");
    await expect(page.getByText("Entwurf wird erstellt…")).toBeVisible();
    await explanation.fill("Meine fiktive manuelle Erklärung bleibt erhalten.");
    releaseDraft();

    await expect(page.getByText(/Kein Entwurf verfügbar/)).toBeVisible();
    await expect(page.getByText("Entwurf wird erstellt…")).toHaveCount(0);
    await expect(explanation).toHaveValue("Meine fiktive manuelle Erklärung bleibt erhalten.");
  });

  test("returns from a no-longer-reviewable detail to the refreshed queue", async ({ page }) => {
    await signedIn(page);
    await page.route("**/api/moderation/meldungen?*", (route) => route.fulfill(json(queue)));
    await page.route("**/api/moderation/meldungen/73", (route) => route.fulfill(json({ detail: "Meldung nicht gefunden." }, 404)));

    await page.goto("/moderation/meldungen");
    await page.getByRole("button", { name: /An der fiktiven Querung.*prüfen/i }).click();
    await expect(page.getByText("Die Meldung ist nicht mehr prüfbar")).toBeVisible();
    await page.getByRole("button", { name: "Zur Prüfliste" }).click();
    await expect(page.getByText("Die Meldung ist nicht mehr prüfbar")).toHaveCount(0);
  });

  test("loads reports beyond the first queue page", async ({ page }) => {
    await signedIn(page);
    const firstPage = Array.from({ length: 20 }, (_, index) => ({
      ...queue.reports[0],
      id: 100 + index,
      text_preview: `Fiktive Meldung ${index + 1}`,
    }));
    await page.route("**/api/moderation/meldungen?*", (route) => {
      const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
      route.fulfill(json({
        reports: offset === 0
          ? firstPage
          : [{ ...queue.reports[0], id: 120, text_preview: "Fiktive Meldung 21" }],
        total: 21,
        limit: 20,
        offset,
      } satisfies Queue));
    });

    await page.goto("/moderation/meldungen");
    await expect(page.getByText("Fiktive Meldung 21")).toHaveCount(0);
    await page.getByRole("button", { name: "Weitere Meldungen laden" }).click();
    await expect(page.getByText("Fiktive Meldung 21")).toBeVisible();
    await expect(page.getByRole("button", { name: "Weitere Meldungen laden" })).toHaveCount(0);
  });

  test("allows approval despite unsuitable AI advice and has no mobile overflow", async ({ page }) => {
    await signedIn(page, { ...moderator, role: "admin" });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/admin/feedback/unread-count", (route) => route.fulfill(json({ total: 0 })));
    let decided = false;
    await page.route("**/api/moderation/meldungen?*", (route) => route.fulfill(json(
      decided
        ? { reports: [], total: 0, limit: 20, offset: 0 } satisfies Queue
        : {
          ...queue,
          reports: [{ ...queue.reports[0], ai_verdict: "unsuitable", ai_reason_code: "non_municipal_matter" }],
        } satisfies Queue,
    )));
    await page.route("**/api/moderation/meldungen/73", (route) => route.fulfill(json({
      ...detail,
      ai_verdict: "unsuitable",
      ai_reason_code: "non_municipal_matter",
    } satisfies Detail)));
    let outcome = "";
    let attempts = 0;
    await page.route("**/api/moderation/meldungen/73/entscheidung", async (route) => {
      attempts += 1;
      outcome = route.request().postDataJSON().outcome;
      if (attempts === 1) {
        await route.fulfill(json({ detail: "Die Freigabe konnte nicht gespeichert werden." }, 409));
        return;
      }
      decided = true;
      await route.fulfill(json({
        report_id: 73,
        content_revision: 1,
        outcome: "approved",
        rejection_explanation: null,
        decided_at: "2026-09-05T09:00:00Z",
      }));
    });

    await page.goto("/moderation/meldungen");
    await page.getByRole("button", { name: /An der fiktiven Querung.*prüfen/i }).click();
    await expect(page.getByText("Automatischer Hinweis: wahrscheinlich ungeeignet")).toBeVisible();
    await expect(page.getByText(/Möglicherweise kein kommunales Anliegen/)).toBeVisible();
    const detailOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(detailOverflow).toBeLessThanOrEqual(1);
    await page.getByRole("button", { name: "Als geprüft freigeben" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Als geprüft freigeben" }).click();
    await expect(page.getByText("Die Freigabe konnte nicht gespeichert werden.", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Als geprüft freigeben" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Als geprüft freigeben" }).click();
    expect(outcome).toBe("approved");
    expect(attempts).toBe(2);
    await expect(page.getByText("Die Freigabe wurde gespeichert.")).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
