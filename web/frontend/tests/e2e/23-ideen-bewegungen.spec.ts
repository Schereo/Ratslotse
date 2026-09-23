/**
 * Die Bewegungen auf „Ideen aus anderen Städten" (Plan PR 52/53).
 *
 * Gemockt, nicht gegen das Backend: In der CI ist die Städte-Datenbank leer
 * und der Schalter `ideen-anderswo` aus (`web/frontend/CLAUDE.md`) — ein Test
 * gegen den echten Endpunkt sähe nur den Leerzustand. Geprüft wird Mechanik,
 * keine Gestaltung: Tafel da, Filter gehen als Anfrage an den Server, die
 * Karte führt zur Ideen-Seite, „Zurück" findet den Filter wieder, und
 * Verwandtes steht nie unter den Belegen.
 */
import { expect, test, type Page } from "@playwright/test";

import { zustandsDatei } from "./konten";

test.use({ storageState: zustandsDatei("admin") });

const ACHSE = { start: "2022-01-01", end: "2027-01-01" };

function bewegung(id: number, label: string, staedte: string[], status: string | null) {
  const timeline = staedte.map((city, i) => ({
    paper_id: `p${id}-${i}`, body_id: city.toLowerCase(), city,
    date: `${2023 + (i % 3)}-0${1 + i}-15`, outcome: i % 2 ? "rejected" : "accepted", kind: "motion",
    title: `${label} (${city})`,
  }));
  return {
    cluster_id: id, label, field: "klima_umwelt",
    cities: staedte.map((city, i) => ({
      body_id: city.toLowerCase(), city, first_date: timeline[i].date, members: 1,
      outcomes: { [timeline[i].outcome]: 1 },
    })),
    members: staedte.length, oldenburg_members: 0,
    first_date: timeline[0].date, last_date: timeline[timeline.length - 1].date,
    outcomes: {}, timeline,
    oldenburg: status && {
      status, situation: "Oldenburg hat 2023 Hitze-Informationen veröffentlicht.",
      confidence: "medium",
      evidence: [{ decision_id: 9085, kvonr: 25977, title: "Hitze-Informationen - Bericht", date: "2023-06-08", outcome: "noted" }],
      related: [{ decision_id: null, kvonr: 27944, title: "Klimaanpassungskonzept - Zwischenstand", date: null, outcome: null }],
    },
  };
}

const GROSS = bewegung(14, "Hitzeaktionsplan aufstellen",
  ["Osnabrück", "Münster", "Potsdam", "Magdeburg", "Hannover", "Braunschweig"], "partial");
const KLEIN = bewegung(4, "Verpackungssteuer einführen", ["Münster", "Potsdam"], "missing");

async function mocks(page: Page) {
  const anfragen: string[] = [];
  await page.route("**/api/app-config", (route) =>
    route.fulfill({ json: { min_build: 0, note: null, features: ["ideen-anderswo"] } }));
  await page.route("**/api/council/cities/ideas/fields", (route) =>
    route.fulfill({ json: {
      fields: [
        { field: "klima_umwelt", total: 40, missing: 20, partial: 10, present: 8, not_applicable: 2, multi_city: 12, movements: 2 },
        { field: "verkehr", total: 30, missing: 15, partial: 5, present: 9, not_applicable: 1, multi_city: 9, movements: 1 },
      ],
      bodies: ["Münster", "Osnabrück", "Potsdam"],
    } }));
  await page.route((u) => u.pathname === "/api/council/cities/ideas", (route) =>
    route.fulfill({ json: { field: "klima_umwelt", total: 0, page: 1, per_page: 30, counts: {}, items: [] } }));
  await page.route((u) => u.pathname === "/api/council/cities/movements", (route) => {
    const url = new URL(route.request().url());
    anfragen.push(url.search);
    const tafel = url.searchParams.get("min_cities") === "5";
    const items = tafel ? [GROSS] : url.searchParams.get("field") === "verkehr" ? [] : [GROSS, KLEIN];
    return route.fulfill({ json: {
      items, total: items.length, page: 1, per_page: 12, axis: ACHSE,
      counts: { missing: 1, partial: 1, present: 3 },
    } });
  });
  await page.route((u) => u.pathname === "/api/council/cities/movements/detail", (route) =>
    route.fulfill({ json: {
      movement: GROSS, axis: ACHSE,
      documents: GROSS.timeline.map((p) => ({
        paper_id: p.paper_id, body_id: p.body_id, city: p.city, name: `Antrag ${p.city}`,
        date: p.date, kind: "motion", web: "https://example.org/vo", outcome: p.outcome,
        originator: "SPD-Fraktion", instrument: "Hitzeaktionsplan aufstellen",
        summary: "Die Stadt soll einen Hitzeaktionsplan aufstellen.",
        protocol: null, protocol_source: "none",
      })),
      oldenburg_documents: [],
      similar: [{ cluster_id: 3, label: "Kommunale Wärmeplanung erstellen", cities: 8, members: 27 }],
    } }));
  return anfragen;
}

test("die Übersicht: Tafel, Filter als Anfrage, Weg zur Ideen-Seite und zurück", async ({ page }) => {
  const anfragen = await mocks(page);
  await page.goto("/council/ideen");

  const tafel = page.getByRole("region", { name: "Gerade in Bewegung" });
  await expect(tafel).toBeVisible();
  await expect(tafel).toContainText("Hitzeaktionsplan aufstellen");
  // Die Zeitleiste liest sich als Satz.
  await expect(tafel.getByRole("img").first()).toHaveAttribute("aria-label", /6 Städte, 2023 bis 2025/);

  const liste = page.getByRole("region", { name: "Ideen, die mehrere Räte hatten" });
  await expect(liste).toContainText("Verpackungssteuer einführen");
  await expect(liste.getByRole("button", { name: /Noch offen/ })).toHaveAttribute("aria-pressed", "true");

  // Ein Filter ist eine Anfrage an den Server, kein Filtern im Browser.
  await liste.getByRole("button", { name: /Hat Oldenburg/ }).click();
  await expect.poll(() => anfragen.some((q) => q.includes("oldenburg=present"))).toBe(true);
  await expect(page).toHaveURL(/stand=vorhanden/, { timeout: 10_000 });
  await liste.getByRole("button", { name: /Noch offen/ }).click();

  await liste.getByRole("button", { name: /Verkehr/ }).click();
  await expect.poll(() => anfragen.some((q) => q.includes("field=verkehr"))).toBe(true);
  await expect(liste).toContainText("Filter zurücksetzen");
  await liste.getByRole("button", { name: "Filter zurücksetzen" }).click();
  await expect(page).toHaveURL(/\/council\/ideen$/, { timeout: 10_000 });

  await liste.getByRole("button", { name: /Klima/ }).click();
  await liste.getByRole("link", { name: /Verpackungssteuer einführen/ }).click();
  // Großzügig: Die Zielseite übersetzt der Dev-Server beim ersten Aufruf,
  // und neben anderen Specs dauert das länger als die üblichen fünf Sekunden.
  await expect(page).toHaveURL(/\/council\/ideen\/bewegung\?id=4/, { timeout: 20_000 });
  await page.getByRole("link", { name: "Alle Ideen" }).click();
  await expect(page).toHaveURL(/feld=klima_umwelt/, { timeout: 20_000 });
});

test("die Ideen-Seite: je Stadt eine Zeile, alle Vorlagen, Beleg und Verwandtes getrennt", async ({ page }) => {
  await mocks(page);
  await page.goto("/council/ideen/bewegung?id=14");

  await expect(page.getByRole("heading", { level: 1, name: "Hitzeaktionsplan aufstellen" })).toBeVisible();
  const buehne = page.getByRole("region", { name: "Wie die Idee durch die Räte lief" });
  await expect(buehne.getByRole("img")).toHaveCount(6);
  await expect(buehne.getByRole("img").first()).toHaveAttribute("aria-label", /^Osnabrück: 1 Stadt/);

  const chronik = page.getByRole("region", { name: "Alle Vorlagen, nach Datum" });
  await expect(chronik.getByRole("listitem")).toHaveCount(6);
  await expect(chronik).toContainText("Zu dieser Sitzung liegt keine Niederschrift vor.");

  const ol = page.getByRole("region", { name: "Und in Oldenburg?" });
  await expect(ol).toContainText("Teilweise vorhanden");
  // Verwandtes erscheint NUR unter seiner eigenen Überschrift.
  const belege = ol.getByText("Worauf sich das stützt").locator("..");
  await expect(belege).toContainText("Hitze-Informationen");
  await expect(belege).not.toContainText("Klimaanpassungskonzept");
  await expect(ol.getByText("Verwandtes aus Oldenburg").locator("..")).toContainText("Klimaanpassungskonzept");

  await expect(page.getByRole("link", { name: "Kommunale Wärmeplanung erstellen" })).toBeVisible();
});

test("eine unbekannte Idee zeigt einen Leerzustand statt eines Fehlers", async ({ page }) => {
  await mocks(page);
  await page.route((u) => u.pathname === "/api/council/cities/movements/detail", (route) =>
    route.fulfill({ status: 404, json: { detail: "unbekannte Bewegung" } }));
  await page.goto("/council/ideen/bewegung?id=999");
  await expect(page.getByText("Diese Idee gibt es nicht (mehr).")).toBeVisible();
});

test("die Ideen sind ein Reiter der Analyse, kein eigener Punkt in der Navigation", async ({ page }) => {
  await mocks(page);
  await page.goto("/council/ideen");
  const reiter = page.getByRole("button", { name: /Andere Städte/ });
  await expect(reiter).toHaveAttribute("aria-pressed", "true");
  // Zurück in die Analyse über dieselbe Leiste.
  await page.getByRole("button", { name: /^Trends$/ }).click();
  await expect(page).toHaveURL(/\/council\?tab=analysis$/, { timeout: 20_000 });
  // Und von dort wieder hin.
  await page.getByRole("button", { name: /Andere Städte/ }).click();
  await expect(page).toHaveURL(/\/council\/ideen$/, { timeout: 20_000 });
});

test("die Zeitleiste liest ab: Überfahren, Tasten und der Sprung in die Chronik", async ({ page }) => {
  await mocks(page);
  await page.goto("/council/ideen");

  // Auf der Karte: Über einem Punkt steht sofort, was er ist — ohne `title`,
  // den der Browser erst nach einer Sekunde zeigte.
  const karte = page.getByRole("region", { name: "Ideen, die mehrere Räte hatten" })
    .getByRole("link", { name: /Verpackungssteuer einführen/ });
  const punkt = karte.locator("[data-punkt]").first();
  await expect(punkt).not.toHaveAttribute("title", /.+/);
  await expect(karte).toContainText("2 Vorlagen");
  await punkt.hover();
  await expect(karte).toContainText("Münster · 15.01.2023 · beschlossen");
  await expect(karte).toContainText("Verpackungssteuer einführen (Münster)");
  await page.mouse.move(0, 0);
  await expect(karte).not.toContainText("15.01.2023");

  // Auf der Ideen-Seite zeigt die Ablesung im Ruhezustand die jüngste Vorlage.
  await page.goto("/council/ideen/bewegung?id=14");
  const buehne = page.getByRole("region", { name: "Wie die Idee durch die Räte lief" });
  await expect(buehne).toContainText("Antrag Braunschweig");

  // Tastatur: ein Tabstopp, dann Pos1 und Pfeile — nach Datum.
  const flaeche = buehne.getByRole("group", { name: /Vorlagen auf der Zeitleiste/ });
  await flaeche.focus();
  await page.keyboard.press("Home");
  await expect(buehne).toContainText("Antrag Osnabrück");
  await page.keyboard.press("ArrowRight");
  await expect(buehne).toContainText("Antrag Magdeburg");

  // Der Sprung in die Chronik landet beim Eintrag.
  await buehne.getByRole("button", { name: "In der Chronik zeigen" }).click();
  await expect(page.locator("#vorlage-p14-3")).toBeInViewport();
});
