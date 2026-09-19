/**
 * Das Tippspiel (`/tipp`) — Beitritt, Tippen, „Mein Tipp" (1c–1e), ohne
 * Konto und ohne Backend: Alle drei Endpunkte werden gemockt, wie bei
 * `15-wahlabend.spec.ts` — dieselbe Begründung: In der CI ist der Schalter
 * aus UND die Datenbank leer, ein Test gegen den echten Endpunkt wäre blind.
 */
import { expect, test, type Page } from "@playwright/test";

async function appConfig(page: Page, features: string[]) {
  await page.route("**/api/app-config", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ min_build: 0, note: null, features }),
    }),
  );
}

const PARTEIEN = [
  { slug: "gruene", short: "Grüne", name: "BÜNDNIS 90/DIE GRÜNEN", color: "#46962B", color_dark: "#6FCB4C", seats_previous: 16 },
  { slug: "spd", short: "SPD", name: "SPD", color: "#E3000F", color_dark: "#FF4D57", seats_previous: 15 },
  { slug: "cdu", short: "CDU", name: "CDU", color: "#121212", color_dark: "#C9CDD3", seats_previous: 9 },
];
const OB_KANDIDATUREN = [
  { slug: "rohr", name: "Jascha Rohr", party: "GRÜNE" },
  { slug: "prange", name: "Ulf Prange", party: "SPD" },
];
// Das Parteien-Menü beim Beitritt (seit 19.09.2026) — ohne AfD, das
// entscheidet der Server; die Attrappe liefert nur, was er liefern würde.
const PARTEI_OPTIONEN = [
  { slug: "gruene", short: "Grüne", color: "#46962B", color_dark: "#6FCB4C" },
  { slug: "spd", short: "SPD", color: "#E3000F", color_dark: "#FF4D57" },
  { slug: "volt", short: "Volt", color: "#502379", color_dark: "#A87BD6" },
];

function setup(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    round: "ratswahl", listed: true, title: "Tippspiel zur Ratswahl", phase: "open", seats_total: 40,
    // Titel und Datum der Wahl kommen seit 09/2026 aus der Antwort, nicht aus
    // einem Literal in der Komponente — die Attrappe muss sie mitliefern.
    election_slug: "ratswahl-2026", election_title: "Ratswahl Oldenburg",
    election_date: "2026-09-13", tip_kind: "seats", previous_label: "2021",
    // Die Hauptrunde ist öffentlich: ohne Konto, Name selbst gewählt. Fehlt
    // das Feld, hält die Seite die Runde für eine Konto-Runde und blendet das
    // Namensfeld aus — genau das haben diese Tests gemerkt.
    public: true,
    locked: false, locked_at: null, late_scored: false, shared_device: false, player_count: 3,
    deadline_hint: "bis zur ersten Hochrechnung (ca. 20 Uhr)",
    parties: PARTEIEN, mayor_candidates: OB_KANDIDATUREN,
    party_options: PARTEI_OPTIONEN, turnout_previous: null, turnout_previous_label: "", successor_path: "",
    ...overrides,
  };
}

/** Die Stichwahl-Runde: keine Listen, zwei Kandidaturen, Prozente. */
function stichwahlSetup(overrides: Partial<Record<string, unknown>> = {}) {
  return setup({
    round: "stichwahl", title: "Tippspiel zur OB-Stichwahl", seats_total: 0, parties: [],
    election_slug: "ob-stichwahl-2026", election_title: "OB-Stichwahl Oldenburg", election_date: "2026-09-27",
    tip_kind: "pct", previous_label: "", deadline_hint: "bis zum ersten Auszählungsstand (kurz nach 18 Uhr)",
    turnout_previous: 63.46, turnout_previous_label: "1. Wahlgang",
    ...overrides,
  });
}

function meins(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    player_id: 1, name: "Anna", party: null, late_at: null, scored: true,
    has_tip: true, has_mayor_tip: false, locked: false,
    seats: [], mayor: [], turnout: null, score: null, rank: null, rank_before: null,
    phase: "open", stand_label: "", source_label: "", notes: [],
    ...overrides,
  };
}

/** `/api/tipp/me` antwortet 401, bis jemand beigetreten ist — simuliert den
 *  Cookie, den Playwright sonst nicht sieht. Für Tests, die direkt einen
 *  bereits angemeldeten Zustand prüfen wollen (z. B. „schon gesperrt"),
 *  startet `bereitsBeigetreten: true` gleich mit `meinsBody` als Antwort. */
function tippMocks(page: Page, meinsBody: object, opts: { setupOverrides?: object; bereitsBeigetreten?: boolean } = {}) {
  const zustand = {
    beigetreten: opts.bereitsBeigetreten ?? false,
    gespeicherterTipp: (opts.bereitsBeigetreten ? meinsBody : null) as object | null,
  };
  page.route("**/api/tipp/setup", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(setup(opts.setupOverrides)) }));
  page.route("**/api/tipp/me", (route) => {
    if (!zustand.beigetreten) return route.fulfill({ status: 401, contentType: "application/json", body: "{}" });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(zustand.gespeicherterTipp) });
  });
  page.route("**/api/tipp", (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    zustand.beigetreten = true;
    const body = route.request().postDataJSON() as { seats?: Record<string, number> };
    if (body.seats) {
      zustand.gespeicherterTipp = meins({ has_tip: true, seats: PARTEIEN.map((p) => ({
        slug: p.slug, tip: body.seats![p.slug] ?? 0, actual: null, avg_tip: null, points: 0, exact: false,
      })) });
    } else if (!zustand.gespeicherterTipp) {
      // Beitritt ohne Tipp (1c): „meins" existiert, aber noch ohne Sitze —
      // das Formular startet dann bei der 2021er Startverteilung.
      zustand.gespeicherterTipp = meins({ has_tip: false, seats: [], mayor: [] });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(zustand.gespeicherterTipp) });
  });
  return zustand;
}

test.describe("Schalter aus", () => {
  test("die Seite sagt Bescheid und fragt gar nicht erst nach Zahlen", async ({ page }) => {
    await appConfig(page, []);
    let rufe = 0;
    await page.route("**/api/tipp/**", (route) => { rufe += 1; return route.fulfill({ status: 404, body: "{}" }); });

    await page.goto("/tipp");
    await expect(page.getByRole("heading", { name: /noch nicht freigeschaltet/ })).toBeVisible();
    await page.waitForTimeout(1000);
    expect(rufe, "/api/tipp/… wurde trotz ausgeschaltetem Schalter abgefragt").toBe(0);
  });
});

test.describe("Schalter an: Beitritt und Tippen", () => {
  test.beforeEach(async ({ page }) => {
    await appConfig(page, ["tippspiel"]);
  });

  test("Einstieg zeigt Name-Feld, Regeln und einen deaktivierten Knopf", async ({ page }) => {
    tippMocks(page, meins());
    await page.goto("/tipp");
    await expect(page.getByRole("heading", { name: /Wie geht die Ratswahl Oldenburg aus/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Jetzt mitmachen/ })).toBeDisabled();
    await expect(page.getByText("5 · 3 · 1")).toBeVisible();
    // Tims Wunsch 19.09.2026: Der Hinweis, den richtigen Namen zu nehmen,
    // und das Parteien-Menü — freiwillig, mit „Keine Angabe" vorn.
    await expect(page.getByText(/richtigen Namen/)).toBeVisible();
    const partei = page.getByLabel(/Parteizugehörigkeit/);
    await expect(partei).toHaveValue("");
    await expect(partei.locator("option")).toHaveText(["Keine Angabe", "Grüne", "SPD", "Volt"]);
  });

  test("die Partei geht mit dem Beitritt an den Server", async ({ page }) => {
    tippMocks(page, meins());
    const beitritte: unknown[] = [];
    await page.route("**/api/tipp", (route) => {
      if (route.request().method() === "POST") beitritte.push(route.request().postDataJSON());
      return route.fallback();
    });
    await page.goto("/tipp");
    await page.getByLabel(/Dein Name/).fill("Testperson");
    await page.getByLabel(/Parteizugehörigkeit/).selectOption("volt");
    await page.getByRole("button", { name: /Jetzt mitmachen/ }).click();
    await expect(page.getByText("Sitze im Rat")).toBeVisible();
    expect(beitritte[0]).toMatchObject({ name: "Testperson", party: "volt" });
  });

  test("die Wahlbeteiligung reist mit dem Tipp — leer heißt nicht getippt", async ({ page }) => {
    tippMocks(page, meins());
    const tipps: Record<string, unknown>[] = [];
    await page.route("**/api/tipp", (route) => {
      const body = route.request().postDataJSON() as Record<string, unknown> | null;
      if (route.request().method() === "POST" && body?.seats) tipps.push(body);
      return route.fallback();
    });
    await page.goto("/tipp");
    await page.getByLabel(/Dein Name/).fill("Testperson");
    await page.getByRole("button", { name: /Jetzt mitmachen/ }).click();
    await page.getByLabel("Sitze für Grüne").fill("40");
    await expect(page.getByText("Wahlbeteiligung tippen")).toBeVisible();
    // `fill` kann in ein Zahlenfeld kein Komma schreiben (Chromium verwirft
    // den Wert) — echte Tastaturen liefern den Punkt selbst, `beteiligungAus`
    // nimmt beides (s. lib/tipp.test.ts).
    await page.getByLabel("Wahlbeteiligung in Prozent").fill("57.5");
    await page.getByRole("button", { name: "Tipp abgeben" }).click();
    await expect(page.getByRole("button", { name: "Gespeichert" })).toBeVisible();
    expect(tipps[0]).toMatchObject({ turnout: 57.5 });
  });

  test("nach dem Beitritt steht das Formular auf null — alle Sitze selbst verteilen", async ({ page }) => {
    tippMocks(page, meins());
    await page.goto("/tipp");
    await page.getByLabel(/Dein Name/).fill("Testperson");
    await page.getByRole("button", { name: /Jetzt mitmachen/ }).click();

    await expect(page.getByText("Sitze im Rat")).toBeVisible();
    // Bis 13.09.2026 stand hier die Verteilung von 2021 als Vorschlag, und
    // der Knopf war sofort aktiv: Ein Klick tippte unbemerkt das letzte
    // Ergebnis nach. Jetzt fängt jede Liste bei 0 an — abgeben kann nur,
    // wer wirklich verteilt hat.
    await expect(page.getByLabel("Sitze für Grüne")).toHaveValue("0");
    // Der Knopf sagt selbst, was fehlt — ein gesperrter Knopf ohne Grund
    // lässt Leute drücken und nichts passieren (Tims Befund 13.09.).
    await expect(page.getByRole("button", { name: "Noch 40 Sitze verteilen" })).toBeDisabled();

    // Alle 40 auf eine Liste — dann passt es, und der Knopf geht auf.
    await page.getByLabel("Sitze für Grüne").fill("40");
    await expect(page.getByText(/40 von 40 — passt/)).toBeVisible();
    await expect(page.getByRole("button", { name: /Tipp abgeben/ })).toBeEnabled();
  });

  test("ein Sitz zu viel sperrt den Abgabe-Knopf und zeigt den Rest", async ({ page }) => {
    tippMocks(page, meins());
    await page.goto("/tipp");
    await page.getByLabel(/Dein Name/).fill("Testperson");
    await page.getByRole("button", { name: /Jetzt mitmachen/ }).click();
    await expect(page.getByText("Sitze im Rat")).toBeVisible();

    // Erst die 40 voll verteilen, dann einen Sitz zu viel setzen — über eine
    // ZWEITE Liste, denn eine einzelne Liste ist auf die Sitzzahl geklemmt
    // (`setzeSitz`): Auf Grüne stehen schon alle 40, „+" bewirkt dort nichts.
    await page.getByLabel("Sitze für Grüne").fill("40");
    await expect(page.getByText(/40 von 40 — passt/)).toBeVisible();
    await page.getByRole("button", { name: "SPD: einen Sitz mehr" }).click();
    await expect(page.getByRole("button", { name: "1 Sitz zu viel" })).toBeDisabled();
  });

  test("die OB-Wahl bleibt zu, bis sie eingeschaltet wird", async ({ page }) => {
    tippMocks(page, meins());
    await page.goto("/tipp");
    await page.getByLabel(/Dein Name/).fill("Testperson");
    await page.getByRole("button", { name: /Jetzt mitmachen/ }).click();
    await expect(page.getByText("Sitze im Rat")).toBeVisible();

    await expect(page.getByText("Jascha Rohr")).not.toBeVisible();
    await page.getByRole("switch", { name: "OB-Wahl mittippen" }).click();
    await expect(page.getByText("Jascha Rohr")).toBeVisible();
    await expect(page.getByText(/Noch 100,0 %/)).toBeVisible();
  });
});

test.describe("Mein Tipp nach Tipp-Schluss", () => {
  test("zeigt Rang und Punkte, wenn schon ein Ergebnis feststeht", async ({ page }) => {
    await appConfig(page, ["tippspiel"]);
    tippMocks(page, meins({
      locked: true, phase: "locked", stand_label: "20:41", has_tip: true,
      score: { total: 42, seat_points: 35, mayor_points: 0, turnout_points: 7, exact_lists: 7, deviation: 3, pct_deviation: null },
      rank: 3, rank_before: 5,
      seats: PARTEIEN.map((p, i) => ({ slug: p.slug, tip: 15 - i, actual: 15 - i, avg_tip: 14, points: 5, exact: true })),
    }), { setupOverrides: { locked: true, phase: "locked" }, bereitsBeigetreten: true });
    await page.goto("/tipp");
    await expect(page.getByText("Dein Rang")).toBeVisible();
    await expect(page.getByText("3", { exact: true })).toBeVisible();
    await expect(page.getByText("2 Plätze vorgerückt")).toBeVisible();
    await expect(page.getByText("42")).toBeVisible();
  });
});

test.describe("Spätstarter", () => {
  test("wer nach Tipp-Schluss beitritt, kommt trotzdem zum Tippformular", async ({ page }) => {
    // Der Server lässt genau das zu (Tipp als „nachgetippt"); die
    // Zustandsmaschine schickte solche Personen vorher direkt zu „Mein
    // Tipp" — ohne Tipp, ohne Formular.
    await appConfig(page, ["tippspiel"]);
    tippMocks(page, meins({
      locked: true, phase: "locked", has_tip: false, late_at: "2026-09-13T18:41:00+00:00", scored: false,
    }), { setupOverrides: { locked: true, phase: "locked", locked_at: "2026-09-13T18:41:00+00:00" }, bereitsBeigetreten: true });
    await page.goto("/tipp");
    await expect(page.getByRole("button", { name: "Noch 40 Sitze verteilen" })).toBeVisible();
    await expect(page.getByText("später abgegeben")).toBeVisible();
  });

  test("Mein Tipp trägt das Nachgetippt-Etikett mit Uhrzeit", async ({ page }) => {
    await appConfig(page, ["tippspiel"]);
    tippMocks(page, meins({
      locked: true, phase: "locked", has_tip: true, late_at: "2026-09-13T18:41:00+00:00", scored: false,
      seats: PARTEIEN.map((p, i) => ({ slug: p.slug, tip: 15 - i, actual: null, avg_tip: null, points: 0, exact: false })),
    }), { setupOverrides: { locked: true, phase: "locked" }, bereitsBeigetreten: true });
    await page.goto("/tipp");
    await expect(page.getByText("Später Tipp 20:41")).toBeVisible();
    await expect(page.getByText(/Du bekommst Punkte, aber keinen Platz in der Rangliste/)).toBeVisible();
  });
});

test.describe("Mein Tipp: OB-Tipp", () => {
  test("der eigene OB-Tipp klappt an Ort und Stelle auf", async ({ page }) => {
    await appConfig(page, ["tippspiel"]);
    tippMocks(page, meins({
      locked: true, phase: "locked", has_tip: true, has_mayor_tip: true,
      seats: PARTEIEN.map((p, i) => ({ slug: p.slug, tip: 15 - i, actual: null, avg_tip: null, points: 0, exact: false })),
      mayor: OB_KANDIDATUREN.map((k, i) => ({ slug: k.slug, tip: 40 - i * 10, actual_pct: null, avg_tip: null, points: 0 })),
    }), { setupOverrides: { locked: true, phase: "locked" }, bereitsBeigetreten: true });
    await page.goto("/tipp");
    await expect(page.getByText("Jascha Rohr")).toBeHidden();
    await page.getByRole("button", { name: "OB-Tipp ansehen" }).click();
    await expect(page.getByText("Jascha Rohr")).toBeVisible();
    // Eine Nachkommastelle wie im Formular (Schrittweite 0,5) — seit 19.09.2026.
    await expect(page.getByText("40,0 %")).toBeVisible();
  });
});

test.describe("Abgeben ist ein Moment", () => {
  test("der Knopf bestätigt, danach steht die Bestätigung — und zurück geht es auch", async ({ page }) => {
    // Vorher sprang der Knopf beim Klick sofort auf „Tipp aktualisieren":
    // Man wusste nicht, ob der Tipp angekommen war (Tims Befund 11.09.).
    await appConfig(page, ["tippspiel"]);
    tippMocks(page, meins());
    await page.goto("/tipp");
    await page.getByLabel(/Dein Name/).fill("Testperson");
    await page.getByRole("button", { name: /Jetzt mitmachen/ }).click();
    await expect(page.getByText("Sitze im Rat")).toBeVisible();
    await page.getByLabel("Sitze für Grüne").fill("40");  // Formular startet bei 0

    await page.getByRole("button", { name: "Tipp abgeben" }).click();
    await expect(page.getByRole("button", { name: "Gespeichert" })).toBeVisible();

    // … und danach die Bestätigung (1e) statt des Formulars.
    await expect(page.getByText("Dein Tipp ist gespeichert.")).toBeVisible();
    await page.getByRole("button", { name: "Tipp ändern" }).click();
    await expect(page.getByText("Sitze im Rat")).toBeVisible();
    await expect(page.getByRole("button", { name: "Zurück" })).toBeVisible();
  });
});

test.describe("Stichwahl (?runde=stichwahl): Prozente statt Sitze", () => {
  test("Einstieg nennt die beiden Kandidaturen, das Formular hat keine Sitze", async ({ page }) => {
    await appConfig(page, ["tippspiel"]);
    let beigetreten = false;
    await page.route(/\/api\/tipp\/setup\?round=stichwahl$/, (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(stichwahlSetup()) }));
    await page.route(/\/api\/tipp\/me\?round=stichwahl$/, (route) =>
      beigetreten
        ? route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(meins({ has_tip: false })) })
        : route.fulfill({ status: 401, contentType: "application/json", body: "{}" }));
    const koerper: Record<string, unknown>[] = [];
    await page.route(/\/api\/tipp\?round=stichwahl$/, (route) => {
      beigetreten = true;
      koerper.push(route.request().postDataJSON() as Record<string, unknown>);
      return route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify(meins({ has_tip: koerper.length > 1, has_mayor_tip: koerper.length > 1 })) });
    });

    await page.goto("/tipp?runde=stichwahl");
    await expect(page.getByRole("heading", { name: /Wie geht die OB-Stichwahl Oldenburg aus/ })).toBeVisible();
    await expect(page.getByText(/Jascha Rohr und Ulf Prange bekommen/)).toBeVisible();
    await expect(page.getByText("6 · 3 · 1")).toBeVisible();
    await page.getByLabel(/Dein Name/).fill("Nele");
    await page.getByRole("button", { name: /Jetzt mitmachen/ }).click();

    // Kein Sitze-Kopf, dafür die beiden Prozentfelder und die Wahlbeteiligung
    // mit dem Anhaltspunkt aus dem ersten Wahlgang.
    await expect(page.getByText("Wer wird OB?")).toBeVisible();
    await expect(page.getByText("Sitze im Rat")).toHaveCount(0);
    await expect(page.getByLabel("Prozent für Ulf Prange")).toBeVisible();
    await expect(page.getByText(/1\. Wahlgang: 63,5 %/)).toBeVisible();
    await page.getByLabel("Prozent für Ulf Prange").fill("52");
    await page.getByLabel("Prozent für Jascha Rohr").fill("48");
    await page.getByLabel("Wahlbeteiligung in Prozent").fill("45");
    await page.getByRole("button", { name: "Tipp abgeben" }).click();
    await expect(page.getByRole("button", { name: "Gespeichert" })).toBeVisible();
    expect(koerper.at(-1)).toMatchObject({ seats: null, mayor: { prange: 52, rohr: 48 }, turnout: 45 });
  });

  test("Mein Tipp zeigt die Prozente offen, mit Partei-Etikett und Wahlbeteiligung", async ({ page }) => {
    await appConfig(page, ["tippspiel"]);
    await page.route(/\/api\/tipp\/setup\?round=stichwahl$/, (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(stichwahlSetup({ locked: true, phase: "locked" })) }));
    await page.route(/\/api\/tipp\/me\?round=stichwahl$/, (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(meins({
        locked: true, phase: "locked", stand_label: "18:41", has_tip: true, has_mayor_tip: true,
        party: PARTEI_OPTIONEN[2],
        mayor: [
          { slug: "rohr", tip: 48, actual_pct: 47.9, avg_tip: 49.1, points: 6 },
          { slug: "prange", tip: 52, actual_pct: 52.1, avg_tip: 50.9, points: 6 },
        ],
        turnout: { tip: 45, actual_pct: 43.2, avg_tip: 46.0, points: 3 },
        score: { total: 15, seat_points: 0, mayor_points: 12, turnout_points: 3, exact_lists: 0, deviation: null, pct_deviation: 2.0 },
        rank: 2, rank_before: 4,
      })) }));
    await page.goto("/tipp?runde=stichwahl");
    await expect(page.getByText("Dein Rang")).toBeVisible();
    await expect(page.getByText("Kandidaturen 12 · Wahlbeteiligung 3")).toBeVisible();
    await expect(page.getByText("Ulf Prange")).toBeVisible();          // offen, ohne Knopf
    await expect(page.getByRole("button", { name: /OB-Tipp ansehen/ })).toHaveCount(0);
    await expect(page.getByText("Wahlbeteiligung", { exact: true })).toBeVisible();
    await expect(page.getByTitle("Parteizugehörigkeit: Volt").first()).toBeVisible();
  });
});

test.describe("Von der Ratswahl zur Stichwahl", () => {
  test("/tipp schickt Neue zur laufenden Runde, wenn die Ratswahl-Runde zu ist", async ({ page }) => {
    await appConfig(page, ["tippspiel"]);
    tippMocks(page, meins(), { setupOverrides: { locked: true, phase: "locked", successor_path: "/tipp?runde=stichwahl" } });
    await page.route(/\/api\/tipp\/setup\?round=stichwahl$/, (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(stichwahlSetup()) }));
    await page.route(/\/api\/tipp\/me\?round=stichwahl$/, (route) =>
      route.fulfill({ status: 401, contentType: "application/json", body: "{}" }));
    await page.goto("/tipp");
    await expect(page).toHaveURL(/\/tipp\/?\?runde=stichwahl/);
    await expect(page.getByRole("heading", { name: /Wie geht die OB-Stichwahl Oldenburg aus/ })).toBeVisible();
  });

  test("wer in der Ratswahl-Runde schon mitgespielt hat, bleibt bei seinem Ergebnis", async ({ page }) => {
    await appConfig(page, ["tippspiel"]);
    tippMocks(page, meins({
      locked: true, phase: "locked", stand_label: "20:41", has_tip: true,
      score: { total: 42, seat_points: 35, mayor_points: 0, turnout_points: 7, exact_lists: 7, deviation: 3, pct_deviation: null },
      rank: 3, rank_before: 5,
      seats: PARTEIEN.map((p, i) => ({ slug: p.slug, tip: 15 - i, actual: 15 - i, avg_tip: 14, points: 5, exact: true })),
    }), { setupOverrides: { locked: true, phase: "locked", successor_path: "/tipp?runde=stichwahl" }, bereitsBeigetreten: true });
    await page.goto("/tipp");
    await expect(page.getByText("Dein Rang")).toBeVisible();
    await expect(page).toHaveURL(/\/tipp\/?$/);
  });
});

test.describe("Eigene Runde (?runde=vally)", () => {
  test("Einstieg nennt die Runde, und jeder Abruf trägt sie", async ({ page }) => {
    // Eine zweite Runde (prediction/rounds.py) ist ein eigener Kreis mit
    // eigenem Link. Die Hauptrunde hat KEINEN Parameter — deshalb greifen
    // die Mocks oben für `?round=vally` nicht, und genau das ist der Punkt:
    // Ohne Parameter hätte diese Runde die Hauptrunde getroffen.
    await appConfig(page, ["tippspiel"]);
    const abrufe: string[] = [];
    await page.route(/\/api\/tipp\/setup\?round=vally$/, (route) => {
      abrufe.push(route.request().url());
      return route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify(setup({ round: "vally", listed: false, title: "Vallys Tippspiel" })) });
    });
    await page.route(/\/api\/tipp\/me\?round=vally$/, (route) => {
      abrufe.push(route.request().url());
      return route.fulfill({ status: 401, contentType: "application/json", body: "{}" });
    });
    await page.route(/\/api\/tipp\?round=vally$/, (route) => {
      abrufe.push(`${route.request().method()} ${route.request().url()}`);
      return route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify(meins({ name: "Nele", has_tip: false })) });
    });

    await page.goto("/tipp?runde=vally");
    await expect(page.getByText(/Vallys Tippspiel/)).toBeVisible();
    await page.getByLabel(/Dein Name/).fill("Nele");
    await page.getByRole("button", { name: /Jetzt mitmachen/ }).click();
    await expect.poll(() => abrufe.some((u) => u.startsWith("POST") && u.endsWith("/api/tipp?round=vally"))).toBe(true);
    expect(abrufe.every((u) => u.includes("round=vally"))).toBe(true);
  });
});

test.describe("Geteiltes Gerät (Schalter je Runde)", () => {
  test("nach dem Speichern gibt „Fertig — nächste Person“ das Gerät weiter, der Tipp bleibt", async ({ page }) => {
    // Vallys Kreis (13.09.2026) tippt von EINEM Handy. Der Knopf löscht nur
    // den Cookie (POST /api/tipp/abmelden) — danach steht der Einstieg
    // wieder da, und die Seite sagt, dass hier mehrere Personen tippen.
    await appConfig(page, ["tippspiel"]);
    const zustand = tippMocks(page, meins(), { setupOverrides: { shared_device: true } });
    let abgemeldet = 0;
    await page.route("**/api/tipp/abmelden", (route) => {
      abgemeldet += 1;
      zustand.beigetreten = false;
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
    });
    await page.goto("/tipp");
    await expect(page.getByText(/mehrere Personen an einem Gerät/)).toBeVisible();
    await page.getByLabel(/Dein Name/).fill("Erste Person");
    await page.getByRole("button", { name: /Jetzt mitmachen/ }).click();
    await page.getByLabel("Sitze für Grüne").fill("40");
    await page.getByRole("button", { name: "Tipp abgeben" }).click();

    await expect(page.getByText("Dein Tipp ist gespeichert.")).toBeVisible();
    await expect(page.getByText(/Gib das Gerät jetzt weiter/)).toBeVisible();
    // Solange das Gerät nicht weitergegeben ist, geht „Tipp ändern" weiter.
    await expect(page.getByRole("button", { name: "Tipp ändern" })).toBeVisible();
    await page.getByRole("button", { name: /Fertig — nächste Person/ }).click();

    await expect(page.getByLabel(/Dein Name/)).toBeVisible();
    expect(abgemeldet).toBe(1);
    await expect(page.getByLabel(/Dein Name/)).toHaveValue("");
  });

  test("in der Hauptrunde gibt es den Knopf nicht", async ({ page }) => {
    await appConfig(page, ["tippspiel"]);
    tippMocks(page, meins(), { bereitsBeigetreten: true });
    await page.goto("/tipp");
    await expect(page.getByText("Dein Tipp ist gespeichert.")).toBeVisible();
    await expect(page.getByRole("button", { name: /nächste Person/ })).toHaveCount(0);
  });
});
