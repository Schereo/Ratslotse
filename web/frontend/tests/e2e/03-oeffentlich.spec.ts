/**
 * Was ohne Konto erreichbar sein muss — und was nicht.
 *
 * Teilen ist die Kernhandlung der App. Wer einen weitergereichten Link öffnet
 * und zuerst das Registrierungsformular sieht, ist weg, bevor er weiß, worum
 * es geht. Die andere Richtung ist genauso wichtig: Alles Persönliche
 * (Dashboard, eigene Themen, Merkliste) darf ohne Anmeldung NICHT aufgehen.
 *
 * Diese Datei prüft beide Richtungen — ohne jede Anmeldung.
 */
import { expect, test } from "@playwright/test";

/** Rechtliches und Hilfe. Ohne diese Seiten kommt die App nicht in den
 *  App Store (Richtlinie 1.5 verlangt eine erreichbare Support-Adresse). */
const RECHTLICHES = [
  { pfad: "/impressum", ueberschrift: /Impressum/ },
  { pfad: "/datenschutz", ueberschrift: /Datenschutzerkl/ },
  { pfad: "/barrierefreiheit", ueberschrift: /Barrierefreiheit/ },
  { pfad: "/hilfe", ueberschrift: /Hilfe/ },
  { pfad: "/changelog", ueberschrift: /Changelog/ },
];

test.describe("Ohne Konto lesbar", () => {
  test("die Startseite wirbt und führt zur Registrierung", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(/Rat/);
    await page.getByRole("link", { name: /Kostenlos registrieren/ }).first().click();
    await expect(page).toHaveURL(/\/register/);
  });

  for (const { pfad, ueberschrift } of RECHTLICHES) {
    test(`${pfad} steht ohne Anmeldung`, async ({ page }) => {
      const antwort = await page.goto(pfad);
      expect(antwort?.status(), `${pfad} antwortet nicht mit 200`).toBeLessThan(400);
      await expect(page.getByRole("heading", { name: ueberschrift }).first()).toBeVisible();
      // Kein Anmeldeformular davor — genau das war der Fehler, gegen den
      // `lib/public-routes.ts` gebaut wurde.
      await expect(page).not.toHaveURL(/\/login/);
    });
  }

  // Die Pfade aus `lib/OEFFENTLICHE_PFADE`. Ohne Daten zeigen sie einen
  // Leer- oder Nicht-gefunden-Zustand — das ist in Ordnung. NICHT in Ordnung
  // wäre die Anmeldewand: Dann ist jeder Teilen-Knopf wertlos.
  //
  // (Die Sitzungsseite MIT Inhalt prüft `04-council.spec.ts`; hier geht es um
  // die Grenze selbst, für alle vier auf einmal.)
  for (const pfad of [
    "/council/decision?id=1",
    "/council/sitzung?ksinr=1",
    "/council/thema?slug=radverkehr",
    "/council/person?slug=jemand",
  ]) {
    test(`${pfad} zeigt keine Anmeldewand`, async ({ page }) => {
      await page.goto(pfad);
      // Kurz warten: Eine Weiterleitung käme erst, nachdem /auth/me geantwortet hat.
      await page.waitForTimeout(1500);
      await expect(page).not.toHaveURL(/\/login/);
      await expect(page.locator("#password")).toHaveCount(0);
    });
  }

  test("die Anmeldeseiten stehen und tragen ihre Formulare", async ({ page }) => {
    for (const [pfad, feld] of [
      ["/login", "#password"],
      ["/register", "#password"],
      ["/forgot-password", "#email"],
    ] as const) {
      await page.goto(pfad);
      await expect(page.locator(feld)).toBeVisible();
    }
  });
});

test.describe("Ohne Konto NICHT lesbar", () => {
  // Die Frontend-Hälfte einer Grenze, die das Backend eigenständig durchsetzt
  // (`optional_user` in deps.py). Fiele sie, sähe man kurz eine leere Seite
  // statt der Anmeldung — und niemand merkt, dass etwas offen steht.
  // „Mein Viertel" (/karte, und /viertel als alter Einstieg) war bis 09/2026
  // öffentlich; seit dem Umzug auf die vereinte Stadtkarte liegt es hinter
  // der Anmeldung (STADTKARTE-PLAN.md, Schritt 5).
  for (const pfad of ["/dashboard", "/topics", "/bookmarks", "/account", "/abos", "/karte", "/viertel?id=kreyenbrueck"]) {
    test(`${pfad} schickt zur Anmeldung`, async ({ page }) => {
      await page.goto(pfad);
      await page.waitForURL(/\/login/, { timeout: 15_000 });
      await expect(page.locator("#password")).toBeVisible();
    });
  }
});

test.describe("Rücksprungziel nach der Anmeldung", () => {
  test("ein fremdes Ziel wird verworfen, nicht befolgt", async ({ page }) => {
    // `?weiter=` kommt aus der Adresszeile und ist damit fremde Eingabe.
    // `//fremde.example` ist für den Browser eine Weiterleitung nach außen.
    await page.goto("/login?weiter=//example.org/");
    await expect(page.locator("#password")).toBeVisible();
    await expect(page).toHaveURL(/localhost/);
  });
});

test.describe("Unbekannte Adressen", () => {
  test("eine Seite, die es nicht gibt, zeigt 404 statt eines leeren Rahmens", async ({ page }) => {
    const antwort = await page.goto("/gibt-es-nicht");
    expect(antwort?.status()).toBe(404);
  });
});

test.describe("Unbestätigtes Konto", () => {
  // Bis 10/2026 prüfte die App-Hülle „unbestätigt" VOR der Ausnahme für
  // öffentliche Seiten: Wer sich registriert, aber den Link noch nicht
  // geklickt hatte, sah auf einem geteilten Beschluss nur die Wand —
  // weniger als ein anonymer Besuch. Und die Wand hatte keinen Ausgang.
  test.beforeEach(async ({ page }) => {
    // Frisches Konto je Test — das Abmelden unten soll keiner geteilten
    // Sitzung schaden. `register` setzt das Sitzungs-Cookie selbst.
    const email = `unbestaetigt-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.org`;
    const antwort = await page.request.post("/api/auth/register", {
      data: { email, password: "password123", display_name: "Noch Unbestätigt" },
    });
    expect(antwort.ok(), await antwort.text()).toBeTruthy();
    // Ohne Mailversand ist eine Registrierung in der Testumgebung sofort
    // bestätigt (`auth.py::register`). Den unbestätigten Zustand stellt
    // deshalb `/auth/me` her — genau das Feld, an dem die Hülle entscheidet.
    await page.route("**/api/auth/me", async (route) => {
      try {
        const echt = await route.fetch();
        if (!echt.ok()) return route.fulfill({ response: echt });
        const ich = await echt.json();
        await route.fulfill({ json: { ...ich, email_verified: false, status: "pending" } });
      } catch {
        await route.fallback().catch(() => { /* Test ist schon zu Ende */ });
      }
    });
  });

  test("liest eine öffentliche Seite wie ohne Konto — mit Hinweis und Abmelden", async ({ page }) => {
    await page.goto("/council/decision?id=1");
    await expect(page.getByText(/Bestätige noch deine E-Mail-Adresse/)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Bitte bestätige deine E-Mail" })).toHaveCount(0);
    // Keine Einladung zum Registrieren — das Konto gibt es ja schon.
    await expect(page.getByRole("link", { name: "Registrieren" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Abmelden" })).toBeVisible();
  });

  test("die Wand vor den Konto-Seiten hat einen Ausgang", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Bitte bestätige deine E-Mail" })).toBeVisible();
    await page.getByRole("button", { name: "Abmelden" }).click();
    await page.waitForURL(/\/login/);
    await expect(page.locator("#password")).toBeVisible();
  });
});
