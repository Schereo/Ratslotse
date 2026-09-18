/**
 * Quiz und Admin-Panel — die beiden Bereiche, die bisher gar nicht angefahren
 * wurden.
 *
 * Beim Admin-Panel zählt vor allem die Grenze: Es hängt am Recht `admin`, und
 * ein gewöhnliches Konto darf dort nicht landen. Beim Quiz zählt, dass es
 * seinen Leerzustand erklärt statt weiß zu bleiben — in der CI ist die
 * Ratsdatenbank leer, und genau so sieht auch eine frische Umgebung aus.
 */
import { expect, test } from "@playwright/test";
import { zustandsDatei } from "./konten";
import type { ApiAntwort } from "../../lib/vertrag";

test.describe("Quiz", () => {
  test.use({ storageState: zustandsDatei("nutzerin") });

  test("die Seite geht auf und erklärt sich, auch ohne Fragen", async ({ page }) => {
    const fehler: string[] = [];
    page.on("pageerror", (e) => fehler.push(e.message));
    await page.goto("/quiz");
    // Entweder es gibt Fragen, oder die Seite sagt, dass gerade keine da sind.
    // Ein weißer Bildschirm ist in beiden Fällen falsch.
    await expect(page.locator("main")).not.toBeEmpty({ timeout: 15_000 });
    expect(fehler).toEqual([]);
  });

  test("die eigene Statistik ist erreichbar", async ({ page }) => {
    await page.goto("/quiz/stats");
    await expect(page.getByText(/Quiz-Statistik/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("bietet entweder ein Spiel an — oder sagt, dass gerade keins da ist", async ({ page }) => {
    // Der Bestand entscheidet, WAS dort steht: Mit Fragen die Kacheln
    // (darunter das Karten-Quiz), ohne Fragen der Vorbereitungs-Hinweis. Beide
    // sind richtig. Falsch wäre eine Seite, die weder das eine noch das andere
    // zeigt — und genau das fiel beim Lauf gegen eine LEERE Ratsdatenbank auf,
    // dem Zustand der CI.
    await page.goto("/quiz");
    const angebot = page.getByText(/Karten-Quiz|Neues Spiel|Meine Fragen üben/);
    const hinweis = page.getByText(/wird gerade vorbereitet/);
    await expect
      .poll(async () => (await angebot.count()) + (await hinweis.count()), { timeout: 15_000 })
      .toBeGreaterThan(0);
  });
});

test.describe("Admin-Panel — die Grenze", () => {
  // Je Identität ein eigener Block: `test.use` gilt für einen ganzen Block,
  // nicht für einen einzelnen Test. Vorher meldete sich jeder Test hier selbst
  // an — genau die Runde, die `konten.ts` einspart.

  test.describe("ein gewöhnliches Konto", () => {
    test.use({ storageState: zustandsDatei("nutzerin") });

    test("kommt nicht hinein", async ({ page }) => {
      await page.goto("/admin");
      // Kein Admin-Inhalt. Was genau kommt (404 oder Weiterleitung), ist der
      // Oberfläche überlassen — NICHT überlassen ist, dass Verwaltungsdaten
      // sichtbar werden.
      await expect(page.getByRole("heading", { name: "Admin" })).toHaveCount(0);
      await expect(page.getByText("Nutzer*innen", { exact: true })).toHaveCount(0);
    });

    test("sieht den Admin-Zugang auch nicht in der Navigation", async ({ page }) => {
      await page.goto("/dashboard");
      await expect(page.getByRole("link", { name: /^Admin$/ })).toHaveCount(0);
    });
  });

  test.describe("ein Ratsmitglied ohne Adminrecht", () => {
    // Wichtig, weil `budget` und `admin` zwei verschiedene Rechte sind: Wer
    // den Haushalt sehen darf, darf noch lange keine Konten verwalten.
    test.use({ storageState: zustandsDatei("ratsfrau") });

    test("kommt ebenfalls nicht hinein", async ({ page }) => {
      await page.goto("/admin");
      await expect(page.getByRole("heading", { name: "Admin" })).toHaveCount(0);
    });
  });

  test.describe("das Adminkonto", () => {
    test.use({ storageState: zustandsDatei("chef") });

    test("kommt hinein", async ({ page }) => {
      const fehler: string[] = [];
      page.on("pageerror", (e) => fehler.push(e.message));
      await page.goto("/admin");
      await expect(page.getByRole("heading", { name: "Admin" }).first()).toBeVisible({ timeout: 15_000 });
      expect(fehler).toEqual([]);
    });

    test("Bereiche bleiben über Direktlinks, Neuladen und Zurück erreichbar", async ({ page }) => {
      await page.goto("/admin#konten");
      await expect(page.getByRole("heading", { name: "Wer kommt wieder?" })).toBeVisible();
      await expect(page.getByRole("navigation", { name: "Admin-Bereiche" }).getByRole("link")).toHaveCount(5);
      await page.getByRole("link", { name: "Menschen", exact: true }).click();
      await expect(page.getByRole("link", { name: "Nutzer*innen", exact: true })).toHaveAttribute("aria-current", "page");
      await page.reload();
      await expect(page.getByRole("link", { name: "Nutzer*innen", exact: true })).toHaveAttribute("aria-current", "page");
      await page.goBack();
      await expect(page.getByRole("heading", { name: "Wer kommt wieder?" })).toBeVisible();
      await page.getByRole("link", { name: "Betrieb", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Cron-Jobs", exact: true })).toBeVisible();
      await page.getByRole("link", { name: "Inhalte", exact: true }).click();
      await expect(page.getByRole("link", { name: "Themen-Dubletten", exact: true })).toBeVisible();
    });

    test("Nutzer*innen nach letzter Nutzung und aktiven Tagen sortieren und inaktive Konten filtern", async ({ page }) => {
      const basis = await (await page.request.get("/api/admin/users")).json() as ApiAntwort<"/admin/users">;
      expect(basis.length).toBeGreaterThanOrEqual(4);
      const day = (ago: number) => new Date(Date.now() - ago * 86_400_000).toISOString().slice(0, 10);
      const users: ApiAntwort<"/admin/users"> = [
        { ...basis[0], display_name: "Test Anna", last_seen: day(0), active_days_30: 7, active_days_total: 8, status: "active", created_at: "2026-09-04T12:00:00Z" },
        { ...basis[1], display_name: "Test Bea", last_seen: day(7), active_days_30: 2, active_days_total: 20, status: "active", created_at: "2026-09-03T12:00:00Z" },
        { ...basis[2], display_name: "Test Cem", last_seen: day(40), active_days_30: 0, active_days_total: 4, status: "disabled", created_at: "2026-09-02T12:00:00Z" },
        { ...basis[3], display_name: "Test Dana", last_seen: null, active_days_30: 0, active_days_total: 0, status: "pending", created_at: "2026-09-01T12:00:00Z" },
      ];
      await page.route("**/api/admin/users", (route) => route.fulfill({ json: users }));
      await page.goto("/admin#users");
      const list = page.getByRole("region", { name: "Nutzer*innenliste" });
      const links = list.getByRole("link");
      await expect(links).toHaveCount(4);
      await page.getByLabel("Nutzer*innen sortieren").selectOption("recent");
      await expect(links.first()).toContainText("Test Anna");
      await page.getByLabel("Nutzer*innen sortieren").selectOption("inactive");
      await expect(links.first()).toContainText("Test Dana");
      await page.getByLabel("Nutzer*innen sortieren").selectOption("active_30");
      await expect(links.first()).toContainText("Test Anna");
      await page.getByLabel("Nutzer*innen sortieren").selectOption("active_total");
      await expect(links.first()).toContainText("Test Bea");
      await expect(links.first()).toContainText("20 Tage insgesamt");
      await page.getByLabel("Aktivität filtern").selectOption("inactive_30");
      await expect(links).toHaveCount(2);
      await expect(list).toContainText("Test Cem");
      await expect(list).toContainText("Test Dana");
      await page.getByLabel("Gesperrte ausblenden").check();
      await expect(links).toHaveCount(1);
      await expect(links.first()).toContainText("Test Dana");
      await expect(page.getByRole("status")).toHaveText("1 von 4 Nutzer*innen");
      await page.getByLabel("Aktivität filtern").selectOption("never");
      await expect(links).toHaveCount(1);
      await page.getByLabel("Aktivität filtern").selectOption("all");
      await page.getByRole("textbox", { name: "Konten durchsuchen" }).fill("Anna");
      await expect(links).toHaveCount(1);
      await expect(links.first()).toContainText("Test Anna");
      await page.setViewportSize({ width: 320, height: 850 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
      await page.setViewportSize({ width: 390, height: 850 });
      await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
    });

    test("junge Konten bleiben offen; unabhängige Merkmale sind kein Verlust-Trichter", async ({ page }) => {
      // Deliberately more questions than finished setups, and no account old
      // enough for 30 days. These are real possibilities, not a funnel.
      const stages = [
        ["registriert", 4, 4, null], ["bestaetigt", 4, 4, null],
        ["setup_begonnen", 3, 4, null], ["setup_fertig", 2, 4, null],
        ["haken", 3, 3, 1], ["frage", 4, 4, null],
        ["tag2", 1, 3, 2], ["tag7", 1, 2, 7], ["tag30", 0, 0, 30],
      ].map(([key, n, eligible, window_days]) => ({ key, label: key, n, eligible, window_days }));
      await page.route("**/api/admin/stats/cohorts?*", (route) => route.fulfill({ json: {
        weeks: 8, excluded: 1, total: stages,
        cohorts: [{ week: "2026-09-14", n: 4, stages }],
        kennzahlen: { haken_quote: 1, tag2: 1 / 3, tag7: 0.5, tag30: null, sackgassen_quote: null, fragen_median: 2 },
        previous: { haken_quote: null, tag2: null, tag7: null, tag30: null, sackgassen_quote: null, fragen_median: 1 },
        basis: { haken: [3, 3], tag2: [1, 3], tag7: [1, 2], tag30: [0, 0], sackgassen: [0, 0], vorher_n: 0 },
      } }));
      await page.goto("/admin#konten");
      const section = page.getByRole("region", { name: "Entwicklung neuer Konten" });
      await expect(section.getByText("1 von 2", { exact: true })).toBeVisible();
      await expect(section.getByText("50 %", { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "30 Tage", exact: true }).click();
      await expect(section.getByText("0 von 0", { exact: true })).toBeVisible();
      await expect(section.getByText("0 %", { exact: true })).toHaveCount(0);
      await expect(section.getByText(/Daraus lässt sich noch keine Rückkehrquote berechnen/)).toBeVisible();
      await page.getByLabel("Anmeldegruppe").selectOption("2026-09-14");
      await expect(section.getByText("Registriert in der Woche ab 14.09.2026", { exact: true })).toBeVisible();
      await section.getByText("Alle Anmeldewochen vergleichen", { exact: true }).click();
      await expect(section.getByRole("columnheader", { name: "Eine erste Frage gestellt" })).toBeVisible();
      await expect(section.getByRole("cell", { name: "Noch offen", exact: true })).toBeVisible();
      await page.setViewportSize({ width: 320, height: 850 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
      await page.setViewportSize({ width: 390, height: 850 });
      await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
    });

    test("tolerierte Cron-Fehler bleiben im Überblick und im Auffällig-Filter sichtbar", async ({ page }) => {
      const basis = { description: "Testlauf", schedule: "wöchentlich", state: "ok" as const, age_h: 1,
        last: { started_at: "2026-09-17T12:00:00Z", duration_s: 10, stats: {} }, history: [] };
      const jobs: ApiAntwort<"/admin/jobs"> = [
        { ...basis, key: "weekly_enrich", label: "Bestandsanreicherung", steps: [
          { name: "Ratsdaten lesen", script: "read", status: "ok", duration_s: 5 },
          { name: "Fremden Dienst abrufen", script: "fetch", status: "warn", duration_s: 5 },
        ] },
        { ...basis, key: "backup", label: "Sicherung", steps: [] },
      ];
      await page.route("**/api/admin/jobs", (route) => route.fulfill({ json: jobs }));
      await page.goto("/admin");
      await expect(page.getByRole("link", { name: /^1 Cron-Jobs mit Auffälligkeiten/ })).toBeVisible();
      await page.getByRole("link", { name: /^1 Cron-Jobs mit Auffälligkeiten/ }).click();
      await page.getByRole("button", { name: "Auffällig (1)", exact: true }).click();
      await expect(page.getByText("Bestandsanreicherung", { exact: true })).toBeVisible();
      await expect(page.getByText("Sicherung", { exact: true })).toHaveCount(0);
      await expect(page.getByText("Mit Warnungen · wöchentlich", { exact: true })).toBeVisible();
      await page.getByText("2 Schritte", { exact: false }).click();
      await expect(page.getByText("Fehlgeschlagen, vorerst toleriert", { exact: true })).toBeVisible();
      await expect(page.getByText("alle durchgelaufen", { exact: false })).toHaveCount(0);
    });

    test("Mailübersicht führt zur vollständigen Historie und erhält Fehler sowie ältere Aufrufe", async ({ page }) => {
      const users = await (await page.request.get("/api/admin/users")).json() as ApiAntwort<"/admin/users">;
      const user = users[0];
      const stats: ApiAntwort<"/admin/stats/emails"> = {
        tage: 30, verschickt: 1, gescheitert: 2, rueckkehr: 8,
        je_anlass: [{ anlass: "probe", mails: 0, gescheitert: 2, konten: 1 }, { anlass: "n2_thema", mails: 1, gescheitert: 0, konten: 1 }],
        je_tag: [], rueckkehr_je_anlass: [{ anlass: "n6_woche", rueckkehr: 8 }],
        vielempfaenger: [{ owner_id: user.id, email: user.email, display_name: user.display_name,
          delivery_channel: "push", mails: 1, je_woche: 0.2, letzte: "2026-09-17T10:00:00Z", haeufigster_anlass: "n2_thema" }],
      };
      await page.route("**/api/admin/stats/emails?*", (route) => route.fulfill({ json: stats }));
      let failNextPage = true;
      await page.route(`**/api/admin/users/${user.id}/emails?*`, (route) => {
        const params = new URL(route.request().url()).searchParams;
        const offset = Number(params.get("offset"));
        // Retry is covered without relying on the query library's automatic retry.
        if (offset === 20 && failNextPage) return route.fulfill({ status: 503, json: { detail: "Testfehler" } });
        const response: ApiAntwort<"/admin/users/{user_id}/emails"> = {
          summary: { gesamt: 44, zeitraum: 44, tage: 30, je_woche: 10.3, je_anlass: { n2_thema: 44 }, gescheitert: 1 },
          rows: Array.from({ length: 45 }, (_, i) => ({ id: 45 - i, anlass: "n2_thema",
            subject: `Mail ${45 - i}: Neue Vorlagen zum Radverkehr und zur Schulwegsicherheit in Eversten`,
            sent_at: "2026-09-17T10:00:00Z", ok: i !== 44, besuch_am_tag: i % 2 === 0,
          })).slice(offset, offset + Number(params.get("limit"))),
        };
        return route.fulfill({ json: response });
      });
      await page.goto("/admin#emails");
      const table = page.getByRole("table", { name: "Versand und Link-Aufrufe nach Anlass" });
      await expect(table.getByRole("row", { name: /Testmail/ }).getByRole("cell", { name: "2", exact: true })).toBeVisible();
      await expect(table.getByRole("row", { name: /Wochenvorschau/ }).getByRole("cell", { name: "8", exact: true })).toBeVisible();
      await expect(table.getByRole("row", { name: /Wochenvorschau/ }).getByRole("cell", { name: "–", exact: true })).toBeVisible();
      await expect(page.getByText("Keine Öffnungs- oder Klickquote:", { exact: false })).toBeVisible();
      await page.getByRole("link", { name: new RegExp(user.email.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) }).click();
      await expect(page).toHaveURL(new RegExp(`#users\\?user=${user.id}&detail=emails$`));
      const mails = page.getByRole("list", { name: "Einzelne Mailversuche" });
      await expect(mails.getByRole("listitem")).toHaveCount(20);
      await expect(page.getByRole("region", { name: "Mailhistorie", exact: true }).getByText("10,3", { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Ältere Mails laden" }).click();
      await expect(page.getByText("Ältere Mails konnten nicht geladen werden.", { exact: false })).toBeVisible({ timeout: 15_000 });
      await expect(mails.getByRole("listitem")).toHaveCount(20);
      failNextPage = false;
      await page.getByRole("button", { name: "Erneut versuchen", exact: true }).click();
      await expect(mails.getByRole("listitem")).toHaveCount(40);
      await page.getByRole("button", { name: "Ältere Mails laden" }).click();
      await expect(mails.getByRole("listitem")).toHaveCount(45);
      await expect(mails.getByText(/^Mail 1:/)).toBeVisible();
      await expect(mails.getByText("Fehlgeschlagen", { exact: true })).toHaveCount(1);
      await expect(page.getByRole("button", { name: "Ältere Mails laden" })).toHaveCount(0);
      await page.getByRole("navigation", { name: "Kontodetails" }).getByRole("link", { name: "Aktivität" }).click();
      await page.goBack();
      await expect(page.getByRole("heading", { name: "Versandverlauf", exact: true })).toBeVisible();
      await page.reload();
      await expect(page.getByRole("navigation", { name: "Kontodetails" }).getByRole("link", { name: "E-Mails", exact: true })).toHaveAttribute("aria-current", "page");
      for (const width of [320, 390]) {
        await page.setViewportSize({ width, height: 850 });
        if (width === 390) await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
      }
      await page.getByRole("link", { name: "Zur Kontenliste", exact: true }).click();
      await expect(page.getByRole("textbox", { name: "Konten durchsuchen" })).toBeVisible();
    });

    test("Verläufe sind per Tastatur ablesbar und behalten Nullwerte", async ({ page }) => {
      await page.route("**/api/admin/stats/growth?*", async (route) => {
        const response = await route.fetch();
        const data = await response.json();
        await route.fulfill({ json: { ...data, wau: [0, 7, 2], wau_days: ["2026-09-03", "2026-09-10", "2026-09-17"] } });
      });
      await page.goto("/admin");
      const chart = page.getByRole("group", { name: "aktive Konten im Zeitverlauf", exact: true });
      await chart.locator('[tabindex="0"]').focus();
      await page.keyboard.press("Home");
      await expect(page.locator(":focus")).toHaveAttribute("aria-label", /0 aktive Konten/);
      await page.keyboard.press("ArrowRight");
      await expect(page.locator(":focus")).toHaveAttribute("aria-label", /7 aktive Konten/);
      await page.getByText("Alle 3 Werte als Tabelle", { exact: true }).click();
      const table = page.getByRole("table", { name: "aktive Konten – vollständiger Verlauf" });
      await expect(table.getByRole("row")).toHaveCount(4);
      await expect(table.getByRole("cell", { name: "0", exact: true })).toBeVisible();
    });
  });
});
