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
      data_status: { as_of: "2026-09-14", lagging: [
        { body_id: "potsdam", city: "Potsdam", latest_paper: "2026-06-25" }] },
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

function idee(i: number) {
  return {
    paper_id: `p-verkehr-${i}`, body_id: "muenster", body_name: "Münster",
    name: `Fahrradbügel aufstellen ${i}`, date: "2025-03-01", kind: "motion",
    web: "https://example.org/vo", outcome: "accepted", field: "verkehr",
    instrument: "Fahrradbügel aufstellen", summary: "Mehr Fahrradbügel aufstellen.",
    transfer: "adaptable", competence: "administration", originator: null,
    status: "missing", votes: "2/2", reason: "Kein Beleg.", confidence: "high",
    evidence: [], protocol: null, protocol_source: "withheld", window_since: "2023-01-01",
    effort: "budget", siblings: [], stance: "for", peer_stances: {}, addressee: null,
    feedback: "", peers: 0,
  };
}

test("ein Themenfeld unter „Einzelne Ideen“ holt den Abschnitt nach oben, statt die Ansicht springen zu lassen", async ({ page }) => {
  // Tims Befund 01.11.2026: Mit dem Feld verschwindet oben die Tafel, die
  // Bewegungen filtern mit (hier: von zwölf auf keine), und das Raster weicht
  // einer Liste, die erst noch lädt. Die Seite schrumpft, und wer unten
  // geklickt hatte, sah danach die Bewegungen statt der Ideen. Dazu sprang das
  // Scroll-Gedächtnis auf die Stelle vom letzten Besuch DIESES Feldes.
  await mocks(page);
  const viele = Array.from({ length: 12 }, (_, i) =>
    bewegung(100 + i, `Bewegung ${i}`, ["Münster", "Potsdam", "Osnabrück"], "missing"));
  await page.route((u) => u.pathname === "/api/council/cities/movements", (route) => {
    const url = new URL(route.request().url());
    const items = url.searchParams.get("field") === "verkehr" ? [] : viele;
    return route.fulfill({ json: {
      items, total: items.length, page: 1, per_page: 12, axis: ACHSE,
      counts: { missing: items.length, partial: 0, present: 0 },
    } });
  });
  await page.route((u) => u.pathname === "/api/council/cities/ideas", async (route) => {
    await new Promise((r) => setTimeout(r, 800));
    return route.fulfill({ json: {
      field: "verkehr", total: 20, page: 1, per_page: 30, counts: {},
      items: Array.from({ length: 20 }, (_, i) => idee(i)),
    } });
  });

  for (const grosse of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(grosse);
    await page.goto("/council/ideen");
    await page.evaluate(() =>
      sessionStorage.setItem("ratslotse:scroll:/council/ideen?feld=verkehr", "300"));
    const abschnitt = page.getByRole("region", { name: "Einzelne Ideen" });
    await abschnitt.getByRole("button", { name: /Verkehr/ }).click();
    await expect(abschnitt.getByText("Fahrradbügel aufstellen 0")).toBeVisible();
    // Oben, unter der Kopfleiste — nicht irgendwo darunter.
    const kopf = page.getByRole("heading", { name: "Einzelne Ideen" });
    await expect.poll(async () => (await kopf.boundingBox())?.y ?? -1).toBeGreaterThanOrEqual(0);
    await expect.poll(async () => (await kopf.boundingBox())?.y ?? 9999).toBeLessThan(200);
  }
});

test("ein Themenfeld blättert durch alle Ideen, nicht nur durch die ersten 30", async ({ page }) => {
  // Tims Befund 01.11.2026: Oben stand „1228 Ideen", die Liste hörte nach 30
  // auf. Die Seite steht in der Adresse (`ideenseite`), getrennt von der der
  // Bewegungen, und ein anderes Feld fängt wieder vorn an.
  await mocks(page);
  const seiten: string[] = [];
  await page.route((u) => u.pathname === "/api/council/cities/ideas", (route) => {
    const url = new URL(route.request().url());
    const seite = Number(url.searchParams.get("page") ?? "1");
    seiten.push(`${url.searchParams.get("field")}:${seite}`);
    const anfang = (seite - 1) * 30;
    const items = Array.from({ length: Math.max(0, Math.min(30, 70 - anfang)) },
      (_, i) => idee(anfang + i));
    return route.fulfill({ json: {
      field: url.searchParams.get("field"), total: 70, page: seite, per_page: 30, counts: {}, items,
    } });
  });

  await page.goto("/council/ideen");
  const abschnitt = page.getByRole("region", { name: "Einzelne Ideen" });
  await abschnitt.getByRole("button", { name: /Verkehr/ }).click();
  const blaettern = abschnitt.getByRole("navigation", { name: "Seiten der Ideen" });
  await expect(blaettern).toContainText("Seite 1 von 3");
  await expect(abschnitt.getByText("Fahrradbügel aufstellen 29", { exact: true })).toBeVisible();

  await blaettern.getByRole("button", { name: /Weiter/ }).click();
  await expect(page).toHaveURL(/feld=verkehr&ideenseite=2/, { timeout: 10_000 });
  await expect(abschnitt.getByText("Fahrradbügel aufstellen 30", { exact: true })).toBeVisible();
  await expect(blaettern).toContainText("Seite 2 von 3");
  expect(seiten).toContain("verkehr:2");
  // Geblättert wird hier, nicht in den Bewegungen darüber.
  await expect(page).not.toHaveURL(/[?&]seite=/);

  await abschnitt.getByRole("button", { name: "Alle Themenfelder" }).click();
  await abschnitt.getByRole("button", { name: /Klima/ }).click();
  await expect(page).toHaveURL(/feld=klima_umwelt$/, { timeout: 10_000 });
  await expect(blaettern).toContainText("Seite 1 von 3");
});

test("die Ideen-Seite: je Stadt eine Zeile, alle Vorlagen, Beleg und Verwandtes getrennt", async ({ page }) => {
  await mocks(page);
  // „Stand: …" kommt mit der Bewegung — die ganze Themenfeld-Übersicht holt
  // die Seite dafür nicht mehr (bis 11/2026 ihre langsamste Anfrage).
  const fieldRequests: string[] = [];
  page.on("request", (r) => { if (r.url().includes("/api/council/cities/ideas/fields")) fieldRequests.push(r.url()); });
  await page.goto("/council/ideen/bewegung?id=14");

  await expect(page.getByRole("heading", { level: 1, name: "Hitzeaktionsplan aufstellen" })).toBeVisible();
  await expect(page.getByText("Stand: 14.09.2026")).toBeVisible();
  await expect(page.getByText("Aus Potsdam liegen Vorlagen nur bis 25.06.2026 vor.")).toBeVisible();
  expect(fieldRequests).toEqual([]);
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
  const reiter = page.getByRole("button", { name: "Ideen aus anderen Städten", exact: true });
  await expect(reiter).toHaveAttribute("aria-pressed", "true");
  // Zurück in die Analyse über dieselbe Leiste.
  await page.getByRole("button", { name: /^Trends$/ }).click();
  await expect(page).toHaveURL(/\/council\?tab=analysis$/, { timeout: 20_000 });
  // Und von dort wieder hin.
  await page.getByRole("button", { name: "Ideen aus anderen Städten", exact: true }).click();
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

test("ein gescheiterter Abruf ist ein Fehler mit „Nochmal versuchen“, keine Leere", async ({ page }) => {
  await mocks(page);
  let fehlschlagen = true;
  await page.route((u) => u.pathname === "/api/council/cities/movements", (route) =>
    fehlschlagen
      ? route.fulfill({ status: 500, json: { detail: "kaputt" } })
      : route.fulfill({ json: { items: [KLEIN], total: 1, page: 1, per_page: 12, axis: ACHSE, counts: {} } }));
  await page.goto("/council/ideen");
  const liste = page.getByRole("region", { name: "Ideen, die mehrere Räte hatten" });
  // Bis 10/2026 stand hier „Noch keine Bewegungen" — als gäbe es keine.
  await expect(liste.getByRole("alert")).toBeVisible({ timeout: 20_000 });
  await expect(liste).not.toContainText("Noch keine");
  fehlschlagen = false;
  await liste.getByRole("button", { name: "Nochmal versuchen" }).click();
  await expect(liste).toContainText("Verpackungssteuer einführen");
});

test("ein Netzfehler auf der Ideen-Seite sagt nicht „gibt es nicht“", async ({ page }) => {
  await mocks(page);
  await page.route((u) => u.pathname === "/api/council/cities/movements/detail", (route) =>
    route.fulfill({ status: 503, json: { detail: "Wartung" } }));
  await page.goto("/council/ideen/bewegung?id=14");
  // Nicht `getByRole("alert")` allein: Next legt mit `#__next-route-announcer__`
  // eine zweite, leere Alert-Region an, und der strikte Locator bricht ab.
  await expect(page.getByRole("alert").filter({ hasText: "konnte nicht geladen werden" }))
    .toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Diese Idee gibt es nicht (mehr).")).toHaveCount(0);
});

test("der Datenstand steht unter der Überschrift", async ({ page }) => {
  await mocks(page);
  await page.route("**/api/council/cities/ideas/fields", (route) =>
    route.fulfill({ json: {
      fields: [{ field: "klima_umwelt", total: 4, missing: 2, partial: 1, present: 1, not_applicable: 0, multi_city: 1, movements: 2 }],
      bodies: ["Münster", "Wolfsburg"],
      data_status: { as_of: "2026-09-10", lagging: [{ body_id: "wolfsburg", city: "Wolfsburg", latest_paper: "2026-06-25" }] },
    } }));
  await page.goto("/council/ideen");
  await expect(page.getByText("Stand: 10.09.2026")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/Aus Wolfsburg liegen Vorlagen nur bis 25\.06\.2026 vor/)).toBeVisible();
});

test("ohne den Schalter ist die Seite ein 404, keine leere Seite", async ({ page }) => {
  await page.route("**/api/app-config", (route) =>
    route.fulfill({ json: { min_build: 0, note: null, features: [] } }));
  for (const pfad of ["/council/ideen", "/council/ideen/bewegung?id=14"]) {
    await page.goto(pfad);
    await expect(page.getByText("Diesen Inhalt finde ich nicht").first(), pfad)
      .toBeVisible({ timeout: 20_000 });
  }
});
