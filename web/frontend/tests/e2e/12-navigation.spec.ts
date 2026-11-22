/**
 * Die Navigation und die Wege durch die App.
 *
 * Zwei Eigenschaften, die keine einzelne Seite prüft: dass jeder Punkt der
 * Navigation irgendwo ankommt, und dass der aktive Punkt LEUCHTET. Der zweite
 * hing schon einmal am Schluss-Schrägstrich des App-Exports — der
 * Sitzungen-Tab leuchtete in der App nie, und im Browser fiel es niemandem
 * auf, weil es dort ging.
 */
import { expect, test } from "@playwright/test";
import { zustandsDatei } from "./konten";

/** Was ein gewöhnliches Konto in der Navigation erreichen können muss. */
const ZIELE = [
  { label: "Heute", pfad: /\/dashboard/ },
  { label: "Fragen", pfad: /\/fragen/ },
  { label: "Suche", pfad: /\/council/ },
  { label: "Meine Themen", pfad: /\/topics/ },
  { label: "Ausschuss-Abos", pfad: /\/abos/ },
  { label: "Merkliste", pfad: /\/bookmarks/ },
  { label: "Quiz", pfad: /\/quiz/ },
];

test.describe("Jeder Punkt der Navigation kommt an", () => {
  test.use({ storageState: zustandsDatei("nutzerin") });

  for (const { label, pfad } of ZIELE) {
    test(`„${label}“ führt zu ${pfad}`, async ({ page }) => {
      await page.goto("/dashboard");
      await page.getByRole("link", { name: label, exact: true }).first().click();
      await expect(page).toHaveURL(pfad, { timeout: 15_000 });
      await expect(page.locator("main")).not.toBeEmpty();
    });
  }
});

test.describe("Der aktive Punkt leuchtet", () => {
  test.use({ storageState: zustandsDatei("nutzerin") });

  test("auf dem Dashboard ist „Heute“ markiert", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("link", { name: "Heute", exact: true }).first())
      .toHaveAttribute("aria-current", "page");
  });

  test("auch mit Schluss-Schrägstrich in der Adresse", async ({ page }) => {
    // Ein exakter Vergleich (`pathname === "/topics"`) wäre bei „/topics/"
    // blind; der aktive Punkt geht deshalb über `pfad()`.
    await page.goto("/topics/");
    await expect(page.getByRole("link", { name: "Meine Themen", exact: true }).first())
      .toHaveAttribute("aria-current", "page");
  });

  test("die Reiter der Ratsseite markieren sich einzeln", async ({ page }) => {
    await page.goto("/council?tab=sessions");
    await expect(page.getByRole("link", { name: "Sitzungen", exact: true }).first())
      .toHaveAttribute("aria-current", "page");
    // Und „Suche" ist es dann NICHT — beide zeigen auf /council.
    await expect(page.getByRole("link", { name: "Suche", exact: true }).first())
      .not.toHaveAttribute("aria-current", "page");
  });
});

test.describe("Untermenüs der Seitenleiste", () => {
  // Seit 11/2026 klappt ein Bereich seine Unterseiten in der Seitenleiste auf,
  // solange man darin ist. Die Fläche wandert dabei auf die UNTERZEILE — und
  // genau das prüft sonst keine einzelne Seite: dass am Schreibtisch nicht
  // zwei Zeilen zugleich „hier bist du" sagen und nicht keine.
  test.use({ storageState: zustandsDatei("nutzerin") });

  test("die Analyse zeigt ihre Unterseiten, und die Unterzeile ist der Standort", async ({ page }) => {
    await page.goto("/council?tab=analysis&sub=parties");
    const leiste = page.locator("aside");
    const analyse = leiste.getByRole("group", { name: "Analyse" });
    await expect(analyse.getByRole("link", { name: "Parteien", exact: true }))
      .toHaveAttribute("aria-current", "page");
    // Der Hauptpunkt gibt die Markierung ab — sonst stünden zwei Standorte da.
    await expect(leiste.getByRole("link", { name: "Analyse", exact: true }))
      .not.toHaveAttribute("aria-current", "page");
    await expect(leiste.locator('[aria-current="page"]')).toHaveCount(1);

    await analyse.getByRole("link", { name: "Personen", exact: true }).click();
    await expect(page).toHaveURL(/sub=personen/, { timeout: 15_000 });
    await expect(analyse.getByRole("link", { name: "Personen", exact: true }))
      .toHaveAttribute("aria-current", "page");
  });

  test("„Analyse“ selbst führt auf Trends — die erste Unterzeile", async ({ page }) => {
    await page.goto("/dashboard");
    const leiste = page.locator("aside");
    await leiste.getByRole("link", { name: "Analyse", exact: true }).click();
    await expect(page).toHaveURL(/tab=analysis/, { timeout: 15_000 });
    await expect(leiste.getByRole("group", { name: "Analyse" }).getByRole("link", { name: "Trends", exact: true }))
      .toHaveAttribute("aria-current", "page");
  });

  test("außerhalb des Bereichs ist das Untermenü zu", async ({ page }) => {
    // Im Ruhezustand ist die Leiste so kurz wie vor dem Umbau.
    await page.goto("/dashboard");
    await expect(page.getByRole("link", { name: "Heute", exact: true }).first())
      .toHaveAttribute("aria-current", "page");
    await expect(page.locator("aside").getByRole("group", { name: "Analyse" })).toHaveCount(0);
  });

  test("am Schreibtisch keine Reiterleiste auf der Seite, auf dem Telefon schon", async ({ page }) => {
    // Beides zugleich wäre dieselbe Navigation doppelt. Unterhalb von `desk`
    // gibt es keine Seitenleiste, dort ist die Leiste der einzige Weg.
    await page.goto("/council?tab=analysis");
    const reiter = page.getByRole("button", { name: "Parteien", exact: true });
    await expect(page.locator("aside").getByRole("link", { name: "Parteien", exact: true })).toBeVisible();
    await expect(reiter).toBeHidden();

    await page.setViewportSize({ width: 390, height: 844 });
    await expect(reiter).toBeVisible();
    await reiter.click();
    await expect(page).toHaveURL(/sub=parties/, { timeout: 15_000 });
  });

  test("ohne Mandat gibt es keine Gruppe „Ratsarbeit“ — der Haushalt steht trotzdem da", async ({ page }) => {
    // Den Haushalt sieht jedes Konto; die Gruppe ist das Arbeitsmittel-Fach
    // für Ratsmitglieder und hängt am Recht `council_tools`. Für alle anderen
    // wäre „Ratsarbeit" eine Überschrift über einer einzigen Zeile.
    await page.goto("/dashboard");
    const leiste = page.locator("aside");
    await expect(leiste.getByText("Persönlich", { exact: true })).toBeVisible();
    await expect(leiste.getByRole("link", { name: "Haushalt", exact: true })).toBeVisible();
    await expect(leiste.getByText("Ratsarbeit", { exact: true })).toHaveCount(0);
    await expect(leiste.getByRole("link", { name: "Werkzeuge", exact: true })).toHaveCount(0);
  });
});

test.describe("Ratsarbeit: Haushalt und Werkzeuge", () => {
  test.use({ storageState: zustandsDatei("ratsfrau") });

  test("beide stehen in ihrer eigenen Gruppe", async ({ page }) => {
    await page.goto("/dashboard");
    const leiste = page.locator("aside");
    await expect(leiste.getByText("Ratsarbeit", { exact: true })).toBeVisible();
    await expect(leiste.getByRole("link", { name: "Haushalt", exact: true })).toBeVisible();
    await expect(leiste.getByRole("link", { name: "Werkzeuge", exact: true })).toBeVisible();
  });

  test("der Haushalt zeigt seine vier Etappen, ein Schritt markiert die seine", async ({ page }) => {
    // Schritt 6 und 7 liegen in derselben Etappe; ihre Zeile führt auf den
    // ersten der beiden. Geprüft wird die Adresse, nicht der Name der Etappe —
    // der ist Text und darf sich ändern.
    await page.goto("/haushalt/pruefung");
    const leiste = page.locator("aside");
    const etappen = leiste.getByRole("group", { name: "Haushalt" });
    await expect(etappen.getByRole("link")).toHaveCount(4, { timeout: 15_000 });
    await expect(etappen.locator('[aria-current="page"]')).toHaveAttribute("href", "/haushalt/plan-ist");
    await expect(leiste.locator('[aria-current="page"]')).toHaveCount(1);
  });

  test("auf der Übersicht trägt der Hauptpunkt die Markierung", async ({ page }) => {
    // Die Übersicht gehört zu keiner Etappe — dann darf die Navigation nicht
    // ohne Standort dastehen.
    await page.goto("/haushalt");
    const leiste = page.locator("aside");
    await expect(leiste.getByRole("group", { name: "Haushalt" }).getByRole("link")).toHaveCount(4, { timeout: 15_000 });
    await expect(leiste.getByRole("link", { name: "Haushalt", exact: true }))
      .toHaveAttribute("aria-current", "page");
    await expect(leiste.locator('[aria-current="page"]')).toHaveCount(1);
  });

  test("die Werkzeuge haben noch kein Untermenü", async ({ page }) => {
    // Es erscheint erst ab dem zweiten Werkzeug: Eine einzelne Unterzeile
    // wiederholte nur die Übersicht.
    await page.goto("/werkzeuge/mehrheiten");
    const leiste = page.locator("aside");
    await expect(leiste.getByRole("link", { name: "Werkzeuge", exact: true }))
      .toHaveAttribute("aria-current", "page");
    await expect(leiste.getByRole("group", { name: "Werkzeuge" })).toHaveCount(0);
  });
});

test.describe("Deep-Links kommen an", () => {
  test.use({ storageState: zustandsDatei("nutzerin") });

  test("ein Reiter aus der Adresse wird übernommen", async ({ page }) => {
    for (const tab of ["sessions", "decisions"]) {
      await page.goto(`/council?tab=${tab}`);
      await expect(page).toHaveURL(new RegExp(`tab=${tab}`));
      await expect(page.locator("main")).not.toBeEmpty();
    }
  });

  test("eine unbekannte Kennung endet im App-eigenen 404, nicht im Nichts", async ({ page }) => {
    await page.goto("/council/decision?id=99999999");
    // Die App-eigene 404 erbt die Hülle: Navigation und Suche bleiben da.
    await expect(page.getByText(/finde ich nicht/i).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("link", { name: "Heute", exact: true }).first()).toBeVisible();
  });
});

test.describe("Mobil", () => {
  test.use({ storageState: zustandsDatei("nutzerin") });

  test("die untere Leiste trägt die Hauptpunkte", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/dashboard");
    // In der Leiste selbst suchen: „Heute" heißt seit 10/2026 überall so,
    // also auch in der (mobil versteckten) Seitenleiste davor im DOM.
    const leiste = page.getByRole("navigation", { name: "Hauptnavigation" });
    for (const label of ["Heute", "Fragen"]) {
      await expect(leiste.getByRole("link", { name: label, exact: true })).toBeVisible();
    }
  });
});
