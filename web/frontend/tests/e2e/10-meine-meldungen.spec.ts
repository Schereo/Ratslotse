import { expect, test, type Page } from "@playwright/test";
import { PROBLEM_REPORT_SESSION_KEY } from "@/lib/problem-report-session";
import type { User } from "@/lib/types";
import type { ApiAntwort } from "@/lib/vertrag";

const signedInUser = {
  id: 81,
  email: "berichte@example.org",
  role: "user",
  status: "active",
  email_verified: true,
  delivery_channel: "email",
  apple_linked: false,
  has_password: true,
} satisfies User;
const onboardingState = { steps: [], celebrated: true } satisfies ApiAntwort<"/onboarding">;
const setupState = {
  step: 3,
  started_at: null,
  done_at: "2026-09-04T00:00:00Z",
  pending: false,
} satisfies ApiAntwort<"/onboarding/setup">;
const badgeState = {
  badges: [],
  earned_count: 0,
  newly_earned: [],
  next: null,
  total: 0,
} satisfies ApiAntwort<"/badges">;
type PrivateReport = ApiAntwort<"/meldungen/{report_id}">;
type PrivateReportList = ApiAntwort<"/meldungen">;
type PrivateReportSummary = PrivateReportList["reports"][number];

function json(body: unknown, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  };
}

async function signedIn(page: Page, user: User = signedInUser) {
  await page.route("**/api/auth/me", (route) => route.fulfill(json(user)));
  await page.route("**/api/onboarding", (route) => route.fulfill(json(onboardingState)));
  await page.route("**/api/onboarding/setup", (route) => route.fulfill(json(setupState)));
  await page.route("**/api/topics/unread-count", (route) => route.fulfill(json({ total: 0 })));
  await page.route("**/api/badges", (route) => route.fulfill(json(badgeState)));
  await page.route("**/api/admin/feedback/unread-count", (route) => route.fulfill(json({ total: 0 })));
}

function summary(overrides: Partial<PrivateReportSummary> = {}): PrivateReportSummary {
  return {
    id: 42,
    text_preview: "Am fiktiven Kanal fehlt an der Querung eine sichere Absenkung.",
    category: "mobility",
    scope_kind: "point",
    observed_on: "2026-09-01",
    state: "draft",
    content_revision: 3,
    submitted_at: null,
    updated_at: "2026-09-04T08:05:00Z",
    ...overrides,
  };
}

function privateReport(overrides: Partial<PrivateReport> = {}): PrivateReport {
  return {
    id: 42,
    draft_text: "Am fiktiven Kanal fehlt an der Querung eine sichere Absenkung.",
    confirmed_text: null,
    category: "mobility",
    scope_kind: "point",
    observed_on: "2026-09-01",
    location_label: "Fiktiver Kanalweg am Hafen",
    latitude: 53.1435,
    longitude: 8.2146,
    state: "draft",
    content_revision: 3,
    submitted_at: null,
    created_at: "2026-09-01T08:00:00Z",
    updated_at: "2026-09-04T08:05:00Z",
    ...overrides,
  };
}

test.describe("Owner-bound private report history", () => {
  test("returns to the private overview after authentication", async ({ page }) => {
    await page.route("**/api/auth/me", (route) => route.fulfill(json({ detail: "Nicht angemeldet." }, 401)));

    await page.goto("/meine-meldungen");

    await expect(page).toHaveURL(/\/login\?weiter=%2Fmeine-meldungen$/);
  });

  test("shows honest summaries and loads precise facts only for the selected detail", async ({ page }) => {
    await signedIn(page);
    const list: PrivateReportList = {
      reports: [
        summary(),
        summary({
          id: 41,
          text_preview: "Bestätigte fiktive Beobachtung im Stadtgebiet.",
          state: "submitted",
          scope_kind: "citywide",
          submitted_at: "2026-09-03T10:00:00Z",
          updated_at: "2026-09-03T10:00:00Z",
        }),
      ],
      total: 2,
      limit: 10,
      offset: 0,
    };
    await page.route("**/api/meldungen?*", (route) => route.fulfill(json(list)));
    await page.route("**/api/meldungen/42", (route) => route.fulfill(json(privateReport())));
    await page.route("**/api/meldungen/41", (route) => route.fulfill(json(privateReport({
      id: 41,
      draft_text: "Bestätigte fiktive Beobachtung im Stadtgebiet.",
      confirmed_text: "Bestätigte fiktive Beobachtung im Stadtgebiet.",
      state: "submitted",
      scope_kind: "citywide",
      location_label: "",
      latitude: null,
      longitude: null,
      content_revision: 1,
      submitted_at: "2026-09-03T10:00:00Z",
      updated_at: "2026-09-03T10:00:00Z",
    }))));

    await page.goto("/meine-meldungen");

    await expect(page.getByRole("heading", { level: 1, name: "Meine Meldungen" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Meine Meldungen" })).toBeVisible();
    await expect(page.getByText("Entwurf", { exact: true })).toBeVisible();
    await expect(page.getByText("Privat eingegangen", { exact: true })).toBeVisible();
    await expect(page.getByText("Fiktiver Kanalweg am Hafen")).toHaveCount(0);
    await expect(page.getByText("53.1435")).toHaveCount(0);

    const draftButton = page.getByRole("button", { name: /Am fiktiven Kanal.*öffnen/i });
    await draftButton.click();

    await expect(page.getByRole("heading", { level: 2, name: "Meldung im Detail" })).toBeFocused();
    await expect(page.getByText("Fiktiver Kanalweg am Hafen")).toBeVisible();
    await expect(page.getByText("Revision 3")).toBeVisible();
    await expect(page.getByRole("button", { name: "Entwurf fortsetzen" })).toBeVisible();
    await page.getByRole("button", { name: "Schließen" }).click();
    await expect(draftButton).toBeFocused();

    await page.getByRole("button", { name: /Bestätigte fiktive Beobachtung.*öffnen/i }).click();
    await expect(page.getByText("Diese Meldung ist privat eingegangen und hier schreibgeschützt.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Entwurf fortsetzen" })).toHaveCount(0);
  });

  test("shows loading and empty states explicitly", async ({ page }) => {
    await signedIn(page);
    let releaseResponse: (() => void) | undefined;
    const responseReady = new Promise<void>((resolve) => {
      releaseResponse = resolve;
    });
    await page.route("**/api/meldungen?*", async (route) => {
      await responseReady;
      await route.fulfill(json({ reports: [], total: 0, limit: 10, offset: 0 } satisfies PrivateReportList));
    });

    await page.goto("/meine-meldungen");

    await expect(page.getByRole("status")).toContainText("Meine Meldungen werden geladen");
    releaseResponse?.();
    await expect(page.getByText("Noch keine eigenen Meldungen")).toBeVisible();
    await expect(page.getByRole("link", { name: "Problem melden" })).toBeVisible();
  });

  test("offers an explicit retry after a list error", async ({ page }) => {
    await signedIn(page);
    let attempts = 0;
    await page.route("**/api/meldungen?*", (route) => {
      attempts += 1;
      if (attempts === 1) return route.fulfill(json({ detail: "Vorübergehend nicht erreichbar." }, 503));
      return route.fulfill(json({
        reports: [summary()],
        total: 1,
        limit: 10,
        offset: 0,
      } satisfies PrivateReportList));
    });

    await page.goto("/meine-meldungen");

    await expect(page.getByRole("alert").filter({ hasText: "Meine Meldungen konnten nicht geladen werden" }))
      .toBeVisible();
    await page.getByRole("button", { name: "Nochmal versuchen" }).click();
    await expect(page.getByText(summary().text_preview)).toBeVisible();
    expect(attempts).toBe(2);
  });

  test("shows detail loading and offers retry after a private detail error", async ({ page }) => {
    await signedIn(page);
    await page.route("**/api/meldungen?*", (route) => route.fulfill(json({
      reports: [summary()],
      total: 1,
      limit: 10,
      offset: 0,
    } satisfies PrivateReportList)));
    let releaseDetail: (() => void) | undefined;
    const detailReady = new Promise<void>((resolve) => {
      releaseDetail = resolve;
    });
    let attempts = 0;
    await page.route("**/api/meldungen/42", async (route) => {
      attempts += 1;
      if (attempts === 1) {
        await detailReady;
        return route.fulfill(json({ detail: "Vorübergehend nicht erreichbar." }, 503));
      }
      return route.fulfill(json(privateReport()));
    });

    await page.goto("/meine-meldungen");
    await page.getByRole("button", { name: /Am fiktiven Kanal.*öffnen/i }).click();

    await expect(page.getByRole("status")).toContainText("Meldungsdetails werden geladen");
    releaseDetail?.();
    await expect(page.getByRole("alert").filter({ hasText: "Die Meldung konnte nicht geöffnet werden" }))
      .toBeVisible();
    await page.getByRole("button", { name: "Nochmal versuchen" }).click();
    await expect(page.getByRole("heading", { level: 2, name: "Meldung im Detail" })).toBeFocused();
    expect(attempts).toBe(2);
  });

  test("loads older reports with the next bounded offset", async ({ page }) => {
    await signedIn(page);
    const offsets: number[] = [];
    const firstReports = Array.from({ length: 10 }, (_, index) => summary({
      id: 100 - index,
      text_preview: `Fiktiver Entwurf ${100 - index}.`,
    }));
    await page.route("**/api/meldungen?*", (route) => {
      const url = new URL(route.request().url());
      const offset = Number(url.searchParams.get("offset"));
      offsets.push(offset);
      const reports = offset === 0
        ? firstReports
        : [summary({ id: 1, text_preview: "Ältester fiktiver Entwurf." })];
      return route.fulfill(json({ reports, total: 11, limit: 10, offset } satisfies PrivateReportList));
    });

    await page.goto("/meine-meldungen");
    await page.getByRole("button", { name: "Ältere Meldungen laden" }).click();

    await expect(page.getByText("Ältester fiktiver Entwurf.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Ältere Meldungen laden" })).toHaveCount(0);
    expect(offsets).toEqual([0, 10]);
  });

  test("continues the selected server draft without creating another report", async ({ page }) => {
    await signedIn(page);
    await page.route("**/api/meldungen?*", (route) => route.fulfill(json({
      reports: [summary()],
      total: 1,
      limit: 10,
      offset: 0,
    } satisfies PrivateReportList)));
    let detailReads = 0;
    let createCalls = 0;
    await page.route("**/api/meldungen/42", (route) => {
      detailReads += 1;
      return route.fulfill(json(privateReport(detailReads === 1 ? {} : {
        draft_text: "Neuerer autoritativer Serverstand der fiktiven Meldung.",
        content_revision: 4,
      })));
    });
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().endsWith("/api/meldungen/entwuerfe")) {
        createCalls += 1;
      }
    });

    await page.goto("/meine-meldungen");
    await page.getByRole("button", { name: /Am fiktiven Kanal.*öffnen/i }).click();
    await page.getByRole("button", { name: "Entwurf fortsetzen" }).click();

    await expect(page).toHaveURL(/\/probleme\/melden$/);
    await expect(page.getByRole("heading", { level: 2, name: "Meldung prüfen" })).toBeFocused();
    await expect(page.getByLabel("Beschreibung")).toHaveValue(
      "Neuerer autoritativer Serverstand der fiktiven Meldung.",
    );
    expect(detailReads).toBe(2);
    expect(createCalls).toBe(0);
    const saved = await page.evaluate((key) => JSON.parse(sessionStorage.getItem(key) ?? "null"), PROBLEM_REPORT_SESSION_KEY);
    expect(saved).toMatchObject({
      ownerId: signedInUser.id,
      reportId: 42,
      creationContent: null,
    });
  });

  test("does not enter a fresh reporting flow when continuation cannot be stored safely", async ({ page }) => {
    await signedIn(page);
    await page.addInitScript((key) => {
      const original = Storage.prototype.setItem;
      Storage.prototype.setItem = function setItem(storageKey: string, value: string) {
        if (storageKey === key) throw new DOMException("Storage unavailable", "QuotaExceededError");
        return original.call(this, storageKey, value);
      };
    }, PROBLEM_REPORT_SESSION_KEY);
    await page.route("**/api/meldungen?*", (route) => route.fulfill(json({
      reports: [summary()],
      total: 1,
      limit: 10,
      offset: 0,
    } satisfies PrivateReportList)));
    await page.route("**/api/meldungen/42", (route) => route.fulfill(json(privateReport())));
    let createCalls = 0;
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().endsWith("/api/meldungen/entwuerfe")) {
        createCalls += 1;
      }
    });

    await page.goto("/meine-meldungen");
    await page.getByRole("button", { name: /Am fiktiven Kanal.*öffnen/i }).click();
    await page.getByRole("button", { name: "Entwurf fortsetzen" }).click();

    await expect(page).toHaveURL(/\/meine-meldungen$/);
    await expect(page.getByRole("alert").filter({ hasText: "Entwurf konnte nicht sicher geöffnet werden" }))
      .toBeVisible();
    expect(createCalls).toBe(0);
  });

  test("excludes admin accounts without calling the private report API", async ({ page }) => {
    await signedIn(page, { ...signedInUser, id: 1, email: "admin@example.org", role: "admin" });
    let privateCalls = 0;
    page.on("request", (request) => {
      if (request.url().includes("/api/meldungen")) privateCalls += 1;
    });

    await page.goto("/meine-meldungen");

    await expect(page.getByRole("heading", { name: "Persönliche Meldungen sind Bürgerkonten vorbehalten" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Meine Meldungen" })).toHaveCount(0);
    expect(privateCalls).toBe(0);
  });
});

test.describe("Private report history on a narrow touch screen", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, colorScheme: "dark" });

  test("keeps the overview, private detail, and navigation free of horizontal overflow", async ({ page }) => {
    await signedIn(page);
    await page.route("**/api/meldungen?*", (route) => route.fulfill(json({
      reports: [summary({ text_preview: "N".repeat(160) })],
      total: 1,
      limit: 10,
      offset: 0,
    } satisfies PrivateReportList)));
    await page.route("**/api/meldungen/42", (route) => route.fulfill(json(privateReport({
      draft_text: `Eine fiktive Beobachtung mit langem Inhalt ${"N".repeat(180)}`,
      location_label: `Fiktiver privater Ort ${"L".repeat(120)}`,
    }))));

    await page.goto("/meine-meldungen");
    await page.getByRole("button", { name: "Mehr" }).click();
    const navigationLink = page.getByRole("link", { name: "Meine Meldungen" });
    await expect(navigationLink).toBeVisible();
    await navigationLink.click();
    await page.getByRole("button", { name: /N{20}.*öffnen/i }).click();
    await expect(page.getByRole("heading", { level: 2, name: "Meldung im Detail" })).toBeFocused();

    const geometry = await page.evaluate(() => ({
      viewport: window.innerWidth,
      page: document.documentElement.scrollWidth,
    }));
    expect(geometry.page).toBeLessThanOrEqual(geometry.viewport);
  });
});
