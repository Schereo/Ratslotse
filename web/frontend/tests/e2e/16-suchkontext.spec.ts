import { test, expect, type Page } from "@playwright/test";
import { zustandsDatei } from "./konten";

// Die Navigation braucht mehr als eine Seite, auch mit leerer CI-Datenbank.
// Geprüft wird der Frontend-Weg; die Filterlogik des Stores hat eigene Tests.
const beschluss = (id: number) => ({
  id, ksinr: null, title: `Radwege – Abschnitt ${id}`, kind: "decision",
  committee: "Bauausschuss", session_date: "2026-07-15", item_number: String(id),
  outcome: "accepted", official_text: "Der Ausbau des Radwegs wird beschlossen.",
  factions: [], parties: [], policy_tags: [], amount_eur: null,
});

async function ratsdaten(page: Page) {
  const anfragen: URLSearchParams[] = [];
  await page.route("**/api/council/committees", (r) => r.fulfill({ json: { committees: ["Bauausschuss"] } }));
  await page.route("**/api/council/decisions?**", (r) => {
    const p = new URL(r.request().url()).searchParams;
    anfragen.push(p);
    const offset = Number(p.get("offset"));
    return r.fulfill({ json: {
      total: 60,
      decisions: Array.from({ length: Math.min(50, 60 - offset) }, (_, i) => beschluss(offset + i + 1)),
    } });
  });
  await page.route("**/api/council/decision/*", (r) => r.fulfill({ json: {
    decision: beschluss(Number(new URL(r.request().url()).pathname.split("/").pop())),
    attendance: [], present_parties: [], sub_votes: [], template_journey: [],
    similar: [], entities: [], ratsinfo_url: "https://example.org/quelle",
  } }));
  return anfragen;
}

test.use({ storageState: zustandsDatei("nutzerin") });

for (const mobil of [false, true]) {
  test(`Suche → Beschluss → Zurück hält Seite, Filter, Treffer und Position (${mobil ? "mobil" : "Desktop"})`, async ({ page }) => {
    test.setTimeout(60_000);
    if (mobil) await page.setViewportSize({ width: 390, height: 844 });
    const anfragen = await ratsdaten(page);
    await page.goto("/council?tab=decisions&q=Rad&committee=Bauausschuss&outcome=accepted&sort=date_asc&page=2");
    await expect(page.getByRole("status")).toContainText("Seite 2 von 2");
    const treffer = page.locator("#beschluss-54");
    await treffer.scrollIntoViewIfNeeded();
    const oben = (await treffer.boundingBox())!.y;
    await treffer.click();
    await expect(page).toHaveURL(/\/council\/decision\?id=54&/);
    await expect(page.getByRole("heading", { name: "Radwege – Abschnitt 54", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Zurück zur Suche", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("Seite 2 von 2");
    await expect(treffer).toBeFocused();
    await expect.poll(async () => Math.abs((await treffer.boundingBox())!.y - oben)).toBeLessThan(12);
    for (const [key, value] of Object.entries({ q: "Rad", committee: "Bauausschuss", outcome: "accepted", sort: "date_asc", page: "2" })) {
      expect(new URL(page.url()).searchParams.get(key)).toBe(value);
    }
    expect(anfragen.at(-1)?.get("offset")).toBe("50");
    expect(anfragen.at(-1)?.get("committee")).toBe("Bauausschuss");

    // Beim zweiten Treffer existiert ein Vorwärts-Eintrag: history.length
    // wächst dann nicht. Auch dieser normale Rechercheweg muss zurückführen.
    await page.locator("#beschluss-55").click();
    await expect(page).toHaveURL(/\/council\/decision\?id=55&/);
    await expect(page.getByRole("heading", { name: "Radwege – Abschnitt 55", exact: true })).toBeVisible();
    await page.goBack();
    await expect(page.locator("#beschluss-55")).toBeFocused();
    await page.goForward();
    await expect(page).toHaveURL(/\/council\/decision\?id=55&/);
    await page.getByRole("button", { name: "Zurück zur Suche", exact: true }).click();
    await expect(page.locator("#beschluss-55")).toBeFocused();
    await expect(page.getByRole("status")).toContainText("Seite 2 von 2");
  });
}

test("Eingabe, Neuladen, neuer Tab und Rückkehr über die Navigation verwenden dieselbe Suchadresse", async ({ page, context }) => {
  test.setTimeout(60_000);
  const anfragen = await ratsdaten(page);
  await page.goto("/council?page=1");
  await page.getByPlaceholder("Suchen (z. B. Haushalt, Radwege)…").fill("Rad & Schule");
  await expect(page.getByRole("status")).toContainText("zu Rad & Schule");
  await page.getByRole("button", { name: "2", exact: true }).first().click();
  await expect(page.getByRole("status")).toContainText("Seite 2 von 2");
  const adresse = page.url();
  expect(new URL(adresse).searchParams.get("q")).toBe("Rad & Schule");
  await page.reload();
  await expect(page.getByPlaceholder("Suchen (z. B. Haushalt, Radwege)…")).toHaveValue("Rad & Schule");
  await expect(page.getByRole("status")).toContainText("Seite 2 von 2");
  expect(anfragen.at(-1)?.get("q")).toBe("Rad & Schule");

  const geteilt = await context.newPage();
  await ratsdaten(geteilt);
  await geteilt.goto(adresse);
  await expect(geteilt.getByRole("status")).toContainText("Seite 2 von 2");
  await expect(geteilt.getByPlaceholder("Suchen (z. B. Haushalt, Radwege)…")).toHaveValue("Rad & Schule");
  await geteilt.close();

  await page.getByRole("link", { name: "Fragen", exact: true }).first().click();
  await expect(page).toHaveURL(/\/fragen/);
  await page.getByRole("link", { name: "Suche", exact: true }).first().click();
  await expect(page.getByRole("status")).toContainText("Seite 2 von 2");
  await expect(page.getByPlaceholder("Suchen (z. B. Haushalt, Radwege)…")).toHaveValue("Rad & Schule");

  // Ein expliziter Deep-Link darf keine versteckten Filter der alten Suche erben.
  await page.goto("/council?field=bildung");
  await expect(page.getByRole("status")).toContainText("Seite 1 von 2");
  await expect(page.getByPlaceholder("Suchen (z. B. Haushalt, Radwege)…")).toHaveValue("");
  expect(anfragen.at(-1)?.get("q")).toBeNull();
  expect(anfragen.at(-1)?.get("field")).toBe("bildung");
});

test("ein direkt geöffneter Beschluss findet ohne gespeicherte History seine Suche", async ({ page }) => {
  await ratsdaten(page);
  const suche = "/council?tab=decisions&q=Rad&page=2#beschluss-54";
  await page.goto(`/council/decision?id=54&suche=${encodeURIComponent(suche)}`);
  await page.getByRole("button", { name: "Zurück zur Suche", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Seite 2 von 2");
  await expect(page.locator("#beschluss-54")).toBeFocused();
});
