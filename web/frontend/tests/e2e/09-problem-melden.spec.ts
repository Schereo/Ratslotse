import { expect, test, type Page } from "@playwright/test";
import type { User } from "@/lib/types";
import {
  oldenburgTodayISO,
  PROBLEM_REPORT_SESSION_KEY,
  PROBLEM_REPORT_SESSION_TTL_MS,
} from "@/lib/problem-report-session";
import type { ApiAntwort } from "@/lib/vertrag";

const emptyProblems = {
  problems: [],
  total: 0,
} satisfies ApiAntwort<"/probleme">;
const signedInUser = {
  id: 71,
  email: "melderin@example.org",
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
const unreadTopicHits = { total: 0 } satisfies ApiAntwort<"/topics/unread-count">;
const badgeState = {
  badges: [],
  earned_count: 0,
  newly_earned: [],
  next: null,
  total: 0,
} satisfies ApiAntwort<"/badges">;
type PrivateReport = ApiAntwort<"/meldungen/{report_id}">;

function todayISO(): string {
  return oldenburgTodayISO();
}

async function signedIn(page: Page, user: User = signedInUser) {
  const json = (body: unknown) => ({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
  await page.route("**/api/auth/me", (route) => route.fulfill(json(user)));
  await page.route("**/api/onboarding", (route) => route.fulfill(json(onboardingState)));
  await page.route("**/api/onboarding/setup", (route) => route.fulfill(json(setupState)));
  await page.route("**/api/topics/unread-count", (route) => route.fulfill(json(unreadTopicHits)));
  await page.route("**/api/badges", (route) => route.fulfill(json(badgeState)));
  await page.route("**/api/admin/feedback/unread-count", (route) => route.fulfill(json({ total: 0 })));
}

function privateReport(overrides: Partial<PrivateReport> = {}): PrivateReport {
  return {
    id: 42,
    draft_text: "Am fiktiven Testort fehlt an der Querung eine sichere Absenkung.",
    confirmed_text: null,
    category: "mobility",
    scope_kind: "point",
    observed_on: todayISO(),
    location_label: "Fiktiver Testort am Hafen",
    latitude: 53.1435,
    longitude: 8.2146,
    state: "draft",
    content_revision: 0,
    submitted_at: null,
    created_at: "2026-09-04T08:00:00Z",
    updated_at: "2026-09-04T08:00:00Z",
    ...overrides,
  };
}

async function seedServerDraft(
  page: Page,
  report: PrivateReport,
  localText = "Lokaler Zwischenstand",
  options: { ownerId?: number; savedAt?: number } = {},
) {
  await page.addInitScript(({ key, ownerId, savedAt, reportId, observedOn, text }) => {
    sessionStorage.setItem(key, JSON.stringify({
      version: 1,
      ownerId,
      savedAt,
      stage: "review",
      idempotencyKey: "iteration-6-resume-key",
      reportId,
      creationContent: null,
      content: {
        text,
        category: "mobility",
        scope_kind: "point",
        observed_on: observedOn,
        location_label: "Lokaler Testort",
        latitude: 53.14,
        longitude: 8.21,
      },
    }));
  }, {
    key: PROBLEM_REPORT_SESSION_KEY,
    ownerId: options.ownerId ?? signedInUser.id,
    savedAt: options.savedAt ?? Date.now(),
    reportId: report.id,
    observedOn: report.observed_on,
    text: localText,
  });
}

test.describe("Geführte private Problemmeldung", () => {
  test("verwendet den Kalendertag in Oldenburg auch bei abweichender Gerätezeitzone", () => {
    expect(oldenburgTodayISO(new Date("2026-03-28T23:30:00Z"))).toBe("2026-03-29");
    expect(oldenburgTodayISO(new Date("2026-10-24T22:30:00Z"))).toBe("2026-10-25");
  });

  test("führt prominent von der öffentlichen Übersicht über die Anmeldung zurück zum Meldeweg", async ({ page }) => {
    await page.route("**/api/probleme", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(emptyProblems),
    }));

    await page.goto("/probleme");

    const entry = page.getByRole("link", { name: "Problem melden" });
    await expect(entry).toBeVisible();
    await expect(entry).toHaveAttribute("href", "/probleme/melden");
    await entry.click();

    await expect(page).toHaveURL(/\/login\?weiter=%2Fprobleme%2Fmelden$/);
  });

  test("legt einen Ortsentwurf an, speichert die Korrektur revisionssicher und sendet den geprüften Text", async ({ page }) => {
    await signedIn(page);
    const calls: { method: string; path: string; body: Record<string, unknown> }[] = [];
    const forbiddenCalls: string[] = [];
    page.on("request", (request) => {
      if (/\/api\/(probleme|meldungen\/assistenz)(?:\?|$)/.test(request.url())) forbiddenCalls.push(request.url());
    });
    await page.route("**/api/meldungen/entwuerfe", async (route) => {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      calls.push({ method: route.request().method(), path: "/meldungen/entwuerfe", body });
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(privateReport({
          draft_text: String(body.text),
          location_label: String(body.location_label),
          latitude: Number(body.latitude),
          longitude: Number(body.longitude),
        })),
      });
    });
    await page.route("**/api/meldungen/42/entwurf", async (route) => {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      calls.push({ method: route.request().method(), path: "/meldungen/42/entwurf", body });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(privateReport({ draft_text: String(body.text), content_revision: 1 })),
      });
    });
    await page.route("**/api/meldungen/42/absenden", async (route) => {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      calls.push({ method: route.request().method(), path: "/meldungen/42/absenden", body });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(privateReport({
          draft_text: String(body.confirmed_text),
          confirmed_text: String(body.confirmed_text),
          content_revision: 1,
          state: "submitted",
          submitted_at: "2026-09-04T08:05:00Z",
          updated_at: "2026-09-04T08:05:00Z",
        })),
      });
    });

    await page.goto("/probleme/melden");

    await expect(page.getByRole("heading", { level: 1, name: "Problem melden" })).toBeVisible();
    await expect(page.getByText(/kein Notrufkanal.*112/i)).toBeVisible();
    await page.getByRole("button", { name: /Ein Ort/ }).click();
    await page.getByLabel("Ortsangabe").fill("Fiktiver Testort am Hafen");
    await page.getByRole("button", { name: "Kartenmitte markieren" }).click();
    await page.getByRole("button", { name: "Ort übernehmen" }).click();
    await page.getByRole("button", { name: "Datum übernehmen" }).click();
    await page.getByRole("button", { name: "Mobilität & Verkehr" }).click();
    await page.getByLabel("Eigene Beobachtung").fill(
      "Am fiktiven Testort fehlt an der Querung eine sichere Absenkung.",
    );
    await page.getByRole("button", { name: "Entwurf prüfen" }).click();

    await expect(page.getByRole("heading", { level: 2, name: "Meldung prüfen" })).toBeVisible();
    await expect(page.getByText(/Beschreibungstext kann nach dem Absenden automatisch.*OpenRouter/i)).toBeVisible();
    await expect(page.getByText(/Kontodaten.*separat gespeicherte Ortsangabe.*Koordinaten.*Beobachtungsdatum.*nicht gesendet/i)).toBeVisible();
    await expect(page.getByText(/keine persönlichen oder sensiblen Daten/i)).toBeVisible();
    await expect(page.getByRole("link", { name: "Mehr zum Datenschutz" }))
      .toHaveAttribute("href", "/datenschutz");
    const confirmation = page.getByRole("checkbox", { name: /Angaben selbst geprüft/i });
    await confirmation.check();
    const corrected = "Am fiktiven Testort fehlt an der Querung weiterhin eine sichere Absenkung.";
    await page.getByLabel("Beschreibung").fill(corrected);
    await expect(confirmation).not.toBeChecked();
    await confirmation.check();
    await page.getByRole("button", { name: "Meldung privat absenden" }).click();

    await expect(page.getByRole("heading", { name: "Meldung privat eingegangen" })).toBeFocused();
    await expect(page.getByText("Sie ist nicht automatisch öffentlich.", { exact: true })).toBeVisible();
    expect(calls).toHaveLength(3);
    expect(calls[0]).toEqual({
      method: "POST",
      path: "/meldungen/entwuerfe",
      body: {
        text: "Am fiktiven Testort fehlt an der Querung eine sichere Absenkung.",
        category: "mobility",
        scope_kind: "point",
        observed_on: todayISO(),
        location_label: "Fiktiver Testort am Hafen",
        latitude: expect.any(Number),
        longitude: expect.any(Number),
        idempotency_key: expect.stringMatching(/^[A-Za-z0-9._:-]{8,128}$/),
      },
    });
    expect(calls[1]).toEqual({
      method: "PUT",
      path: "/meldungen/42/entwurf",
      body: {
        text: corrected,
        category: "mobility",
        scope_kind: "point",
        observed_on: todayISO(),
        location_label: "Fiktiver Testort am Hafen",
        latitude: expect.any(Number),
        longitude: expect.any(Number),
        expected_revision: 0,
      },
    });
    expect(calls[2]).toEqual({
      method: "POST",
      path: "/meldungen/42/absenden",
      body: { expected_revision: 1, confirmed_text: corrected },
    });
    expect(await page.evaluate(() => Object.keys(sessionStorage).filter((key) => key.includes("problemmeldung"))))
      .toEqual([]);
    expect(forbiddenCalls).toEqual([]);
  });

  test("legt eine stadtweite Meldung ohne erfundenen Ort oder Kartenpunkt an", async ({ page }) => {
    await signedIn(page);
    const calls: { path: string; body: Record<string, unknown> }[] = [];
    let updateCalls = 0;
    await page.route("**/api/meldungen/entwuerfe", async (route) => {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      calls.push({ path: "create", body });
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(privateReport({
          draft_text: String(body.text),
          category: "environment",
          scope_kind: "citywide",
          location_label: "",
          latitude: null,
          longitude: null,
        })),
      });
    });
    await page.route("**/api/meldungen/42/entwurf", async (route) => {
      updateCalls += 1;
      await route.abort();
    });
    await page.route("**/api/meldungen/42/absenden", async (route) => {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      calls.push({ path: "submit", body });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(privateReport({
          draft_text: String(body.confirmed_text),
          confirmed_text: String(body.confirmed_text),
          category: "environment",
          scope_kind: "citywide",
          location_label: "",
          latitude: null,
          longitude: null,
          state: "submitted",
          submitted_at: "2026-09-04T08:05:00Z",
        })),
      });
    });

    await page.goto("/probleme/melden");
    await page.getByRole("button", { name: /Ganz Oldenburg/ }).click();
    await expect(page.getByRole("heading", { name: "Wann hast du das selbst beobachtet?" })).toBeFocused();
    await expect(page.getByLabel("Ortsangabe")).toHaveCount(0);
    await page.getByRole("button", { name: "Datum übernehmen" }).click();
    await page.getByRole("button", { name: "Umwelt & Grün" }).click();
    const description = "In mehreren fiktiven Stadtteilen fehlen schattige öffentliche Aufenthaltsorte.";
    await page.getByLabel("Eigene Beobachtung").fill(description);
    await page.getByRole("button", { name: "Entwurf prüfen" }).click();
    await page.getByRole("checkbox", { name: /Angaben selbst geprüft/i }).check();
    await page.getByRole("button", { name: "Meldung privat absenden" }).click();

    await expect(page.getByRole("heading", { name: "Meldung privat eingegangen" })).toBeVisible();
    expect(updateCalls).toBe(0);
    expect(calls[0]).toEqual({
      path: "create",
      body: {
        text: description,
        category: "environment",
        scope_kind: "citywide",
        observed_on: todayISO(),
        location_label: "",
        latitude: null,
        longitude: null,
        idempotency_key: expect.stringMatching(/^[A-Za-z0-9._:-]{8,128}$/),
      },
    });
    expect(calls[1]).toEqual({
      path: "submit",
      body: { expected_revision: 0, confirmed_text: description },
    });
  });

  test("verwendet beim erneuten Anlegen nach einem API-Fehler denselben Idempotenzschlüssel", async ({ page }) => {
    await signedIn(page);
    const bodies: Record<string, unknown>[] = [];
    await page.route("**/api/meldungen/entwuerfe", async (route) => {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      bodies.push(body);
      if (bodies.length === 1) {
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Vorübergehend nicht erreichbar." }),
        });
        return;
      }
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(privateReport({
          draft_text: String(body.text),
          category: "housing",
          scope_kind: "citywide",
          location_label: "",
          latitude: null,
          longitude: null,
        })),
      });
    });

    await page.goto("/probleme/melden");
    await page.getByRole("button", { name: /Ganz Oldenburg/ }).click();
    await page.getByRole("button", { name: "Datum übernehmen" }).click();
    await page.getByRole("button", { name: "Wohnen" }).click();
    const firstText = "Fiktive Beobachtung zu Wohnungen im gesamten Stadtgebiet.";
    const correctedText = "Korrigierte fiktive Beobachtung zu Wohnungen im gesamten Stadtgebiet.";
    await page.getByLabel("Eigene Beobachtung").fill(firstText);
    await page.getByRole("button", { name: "Entwurf prüfen" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Vorübergehend" })).toBeVisible();
    await page.getByLabel("Eigene Beobachtung").fill(correctedText);
    await page.getByRole("button", { name: "Entwurf prüfen" }).click();

    await expect(page.getByRole("heading", { name: "Meldung prüfen" })).toBeVisible();
    await expect(page.getByLabel("Beschreibung")).toHaveValue(correctedText);
    expect(bodies).toHaveLength(2);
    expect(bodies[1]).toEqual(bodies[0]);
  });

  test("weist ein zukünftiges Beobachtungsdatum vor einem API-Aufruf zurück", async ({ page }) => {
    await signedIn(page);
    let privateCalls = 0;
    page.on("request", (request) => {
      if (request.url().includes("/api/meldungen")) privateCalls += 1;
    });

    await page.goto("/probleme/melden");
    await page.getByRole("button", { name: /Ganz Oldenburg/ }).click();
    await page.getByLabel("Beobachtungsdatum").fill("2999-01-01");

    await expect(page.getByRole("alert").filter({ hasText: "nicht in der Zukunft" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Datum übernehmen" })).toBeDisabled();
    expect(privateCalls).toBe(0);
  });

  test("lädt einen sitzungsgebundenen Serverentwurf statt eines veralteten lokalen Texts", async ({ page }) => {
    await signedIn(page);
    const remote = privateReport({
      draft_text: "Der gespeicherte Serverentwurf beschreibt die fiktive Querung vollständig.",
      content_revision: 3,
    });
    await seedServerDraft(page, remote);
    let getCalls = 0;
    await page.route("**/api/meldungen/42", async (route) => {
      getCalls += 1;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(remote) });
    });

    await page.goto("/probleme/melden");

    await expect(page.getByRole("heading", { level: 2, name: "Meldung prüfen" })).toBeFocused();
    await expect(page.getByLabel("Beschreibung")).toHaveValue(remote.draft_text);
    await expect(page.getByLabel("Ortsangabe")).toHaveValue(remote.location_label);
    await page.getByLabel("Beobachtungsdatum").fill("2999-01-01");
    await expect(page.getByRole("alert").filter({ hasText: "nicht in der Zukunft" })).toBeVisible();
    expect(getCalls).toBe(1);
  });

  for (const invalidSession of [
    { label: "abgelaufenen", options: { savedAt: Date.now() - PROBLEM_REPORT_SESSION_TTL_MS - 1 } },
    { label: "kontofremden", options: { ownerId: signedInUser.id + 1 } },
  ]) {
    test(`verwirft einen ${invalidSession.label} lokalen Entwurf ohne Serverzugriff`, async ({ page }) => {
      await signedIn(page);
      await seedServerDraft(page, privateReport(), "Nicht wiederherstellen", invalidSession.options);
      let getCalls = 0;
      await page.route("**/api/meldungen/42", (route) => {
        getCalls += 1;
        return route.abort();
      });

      await page.goto("/probleme/melden");

      await expect(page.getByRole("button", { name: /Ganz Oldenburg/ })).toBeVisible();
      await expect(page.getByText("Nicht wiederherstellen")).toHaveCount(0);
      expect(getCalls).toBe(0);
    });
  }

  test("beginnt nach einem nicht mehr zugänglichen gespeicherten Entwurf sicher neu", async ({ page }) => {
    await signedIn(page);
    await seedServerDraft(page, privateReport());
    await page.route("**/api/meldungen/42", (route) => route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Meldung nicht gefunden." }),
    }));

    await page.goto("/probleme/melden");

    await expect(page.getByText("Der gespeicherte Entwurf ist nicht mehr verfügbar. Du kannst neu beginnen.")).toBeVisible();
    await expect(page.getByRole("button", { name: /Ganz Oldenburg/ })).toBeVisible();
    await expect(page.getByText("Lokaler Zwischenstand")).toHaveCount(0);
  });

  test("überschreibt bei einem Revisionskonflikt nichts und lädt den Serverstand nur auf Wunsch", async ({ page }) => {
    await signedIn(page);
    const initial = privateReport({ content_revision: 2 });
    const newer = privateReport({
      draft_text: "Ein neuerer Serverstand zur fiktiven Querung.",
      content_revision: 3,
    });
    await seedServerDraft(page, initial);
    let getCalls = 0;
    await page.route("**/api/meldungen/42", async (route) => {
      getCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(getCalls === 1 ? initial : newer),
      });
    });
    await page.route("**/api/meldungen/42/entwurf", (route) => route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Die Meldung wurde zwischenzeitlich geändert oder bereits abgesendet." }),
    }));

    await page.goto("/probleme/melden");
    const localCorrection = "Meine noch nicht gespeicherte Korrektur an der fiktiven Querung.";
    await page.getByLabel("Beschreibung").fill(localCorrection);
    await page.getByRole("checkbox", { name: /Angaben selbst geprüft/i }).check();
    await page.getByRole("button", { name: "Meldung privat absenden" }).click();

    await expect(page.getByRole("alert").filter({ hasText: "Auf dem Server liegt" }))
      .toContainText("Deine Eingabe wurde nicht überschrieben");
    await expect(page.getByLabel("Beschreibung")).toHaveValue(localCorrection);
    expect(getCalls).toBe(1);
    await page.getByRole("button", { name: "Neueren Entwurf laden" }).click();
    await expect(page.getByLabel("Beschreibung")).toHaveValue(newer.draft_text);
    expect(getCalls).toBe(2);
  });

  test("explains external AI pre-screening on the privacy page", async ({ page }) => {
    await page.goto("/datenschutz");

    await expect(page.getByRole("heading", { name: "KI-Vorprüfung privater Meldungen" })).toBeVisible();
    const section = page.getByRole("heading", { name: "KI-Vorprüfung privater Meldungen" })
      .locator("..")
      .locator("div");
    await expect(section).toContainText("OpenRouter");
    await expect(section).toContainText("Drittland");
    await expect(section).toContainText("Kontodaten");
    await expect(section).toContainText("Ortsangabe");
    await expect(section).toContainText("Koordinaten");
    await expect(section).toContainText("Beobachtungsdatum");
    await expect(section).toContainText("keine persönlichen oder sensiblen Daten");
    await expect(section).toContainText("Zero Data Retention");
    await expect(section).toContainText("Training");
    await expect(section).toContainText("keine automatische Entscheidung");
  });

  test("weist Admin-Konten ohne Aufruf der privaten API verständlich ab", async ({ page }) => {
    await signedIn(page, { ...signedInUser, id: 1, email: "admin@example.org", role: "admin" });
    let privateCalls = 0;
    page.on("request", (request) => {
      if (request.url().includes("/api/meldungen")) privateCalls += 1;
    });

    await page.goto("/probleme/melden");

    await expect(page.getByRole("heading", { name: "Persönliche Meldungen sind Bürgerkonten vorbehalten" })).toBeVisible();
    await expect(page.getByText(/Admin-Konten moderieren getrennt/i)).toBeVisible();
    expect(privateCalls).toBe(0);
  });
});

test.describe("Geführte Problemmeldung auf schmalem Touch-Gerät", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, colorScheme: "dark" });

  test("shows the AI disclosure on mobile without horizontal overflow", async ({ page }, testInfo) => {
    await signedIn(page);
    await page.addInitScript(() => localStorage.setItem("theme", "dark"));
    const remote = privateReport();
    await seedServerDraft(page, remote);
    await page.route("**/api/meldungen/42", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(remote),
    }));

    await page.goto("/probleme/melden");

    await expect(page.getByLabel("Externe KI-Vorprüfung")).toBeVisible();
    const geometry = await page.evaluate(() => ({
      viewport: window.innerWidth,
      page: document.documentElement.scrollWidth,
    }));
    expect(geometry.page).toBeLessThanOrEqual(geometry.viewport);
    await page.screenshot({ path: testInfo.outputPath("ai-disclosure-review-mobile-dark.png"), fullPage: true });
  });

  test("bleibt ohne horizontalen Seitenüberlauf bedienbar", async ({ page }, testInfo) => {
    await signedIn(page);
    await page.addInitScript(() => localStorage.setItem("theme", "dark"));
    await page.goto("/probleme/melden");

    await expect(page.getByRole("button", { name: /Ganz Oldenburg/ })).toBeVisible();
    const geometry = await page.evaluate(() => ({
      viewport: window.innerWidth,
      page: document.documentElement.scrollWidth,
    }));
    expect(geometry.page).toBeLessThanOrEqual(geometry.viewport);
    await page.screenshot({ path: testInfo.outputPath("problem-melden-mobile-dark.png"), fullPage: true });
  });
});
