/**
 * Der Wahlabend (`/wahlabend`) — ohne Konto und ohne Feature-Schalter im Server.
 *
 * Die Seite hängt an zwei Antworten: `/api/app-config` sagt, ob der Schalter
 * `wahlabend` an ist, und `/api/wahlabend` liefert alles Gerechnete. Beide
 * werden hier gemockt. Das ist kein Bequemlichkeits-Mock, sondern der einzige
 * Weg, der in der CI trägt: Dort ist `FEATURE_FLAGS` leer (der Schalter also
 * aus) UND die Ratsdatenbank leer — ein Test gegen den echten Endpunkt wäre
 * blind, und ein Test, der den Votemanager der Stadt abfragt, wäre es
 * abwechselnd.
 *
 * Die Zahlen in `fixtures/wahlabend-probe.json` sind die Generalprobe des
 * Backends (`app.election.service.probe(60)`): Stimmen von 2021, Listen und
 * Namen von 2026, 60 von 133 Wahlbezirken ausgezählt, Phase „counting".
 * Erzeugt mit:
 *
 *     cd web/backend && ../../.venv/bin/python -c "import json; \
 *       from app.election import service; print(json.dumps(service.probe(60), ensure_ascii=False))" \
 *       > ../frontend/tests/e2e/fixtures/wahlabend-probe.json
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const PROBE = JSON.parse(
  readFileSync(path.join(__dirname, "fixtures", "wahlabend-probe.json"), "utf8"),
);
/** Dieselbe Probe als Kandidaten-Rangliste (`candidates.ranking(service.probe(60))`). */
const KANDIDATEN = JSON.parse(
  readFileSync(path.join(__dirname, "fixtures", "wahlabend-kandidaten-probe.json"), "utf8"),
);
/** Und als EINE aufgefaltete Kandidatur (`/api/wahlabend/kandidat`). */
const KANDIDAT = JSON.parse(
  readFileSync(path.join(__dirname, "fixtures", "wahlabend-kandidat-probe.json"), "utf8"),
);
/** Und als Wahlbezirke (`service.districts(reg, probe_snapshot(…, 60), "probe")`). */
const BEZIRKE = JSON.parse(
  readFileSync(path.join(__dirname, "fixtures", "wahlbezirke-probe.json"), "utf8"),
);
/** Die Bezirks-Rangliste für Volt (`wahlabend_wahlbezirke_rangliste(party="volt", …, counted=60)`). */
const RANGLISTE = JSON.parse(
  readFileSync(path.join(__dirname, "fixtures", "wahlbezirke-rangliste-probe.json"), "utf8"),
);

/** `/api/app-config` mit genau den Schaltern, die dieser Test sehen will.
 *  `min_build` und `note` gehören dazu — es ist derselbe Endpunkt, den die
 *  native App vor allem anderen abfragt. */
async function appConfig(page: Page, features: string[]) {
  await page.route("**/api/app-config", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ min_build: 0, note: null, features }),
    }),
  );
}

/** `/api/wahlabend` samt Query (`?probe=`, `?counted=`, `?liste=` bleibt im
 *  Browser). Gibt einen Zähler zurück — für den Fall, in dem die Seite gar
 *  nicht fragen DARF. */
function wahlabendMock(page: Page) {
  const zaehler = { rufe: 0 };
  page.route("**/api/wahlabend*", (route) => {
    zaehler.rufe += 1;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(PROBE),
    });
  });
  // Später registriert = zuerst gefragt: Die Unterpfade bekommen ihre eigene
  // Antwort, alles andere unter /api/wahlabend die Tafel.
  page.route("**/api/wahlabend/wahlbezirke*", (route) => {
    zaehler.rufe += 1;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(BEZIRKE),
    });
  });
  page.route("**/api/wahlabend/kandidat?*", (route) => {
    zaehler.rufe += 1;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(KANDIDAT),
    });
  });
  page.route("**/api/wahlabend/kandidaten*", (route) => {
    zaehler.rufe += 1;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(KANDIDATEN),
    });
  });
  // Nach den Wahlbezirken registriert, damit der Unterpfad gewinnt.
  page.route("**/api/wahlabend/wahlbezirke/rangliste*", (route) => {
    zaehler.rufe += 1;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(RANGLISTE),
    });
  });
  return zaehler;
}

test.describe("Schalter aus", () => {
  test("die Seite sagt Bescheid und fragt gar nicht erst nach Zahlen", async ({ page }) => {
    await appConfig(page, []);
    const zaehler = wahlabendMock(page);

    await page.goto("/wahlabend");
    await expect(
      page.getByRole("heading", { name: /noch nicht freigeschaltet/ }),
    ).toBeVisible();

    // Der Abruf hängt an `enabled: schalterAn` — steht der Schalter aus, geht
    // keine Anfrage raus. Sonst liefe am 13.09. jede versehentlich geöffnete
    // Seite gegen den Votemanager der Stadt.
    await page.waitForTimeout(1500);
    expect(zaehler.rufe, "/api/wahlabend wurde trotz ausgeschaltetem Schalter abgefragt").toBe(0);

    // Und nichts von der Tafel steht da.
    await expect(page.getByText(/Wahlbezirken ausgez/)).toHaveCount(0);
  });
});

test.describe("Schalter an: die Generalprobe", () => {
  test.beforeEach(async ({ page }) => {
    await appConfig(page, ["wahlabend"]);
    wahlabendMock(page);
  });

  test("die Anzeigetafel nennt den Auszählungsstand", async ({ page }) => {
    await page.goto("/wahlabend");
    await expect(page.getByText("60 von 133 Wahlbezirken ausgezählt")).toBeVisible();
    // Die Generalprobe sagt selbst, dass sie eine ist — sonst liest jemand die
    // Zahlen von 2021 als Ergebnis.
    await expect(page.getByText(/Generalprobe/).first()).toBeVisible();
  });

  test("die Listen-Tafel steht nach Stimmen sortiert", async ({ page }) => {
    await page.goto("/wahlabend");
    const tafel = page
      .locator("section")
      .filter({ has: page.getByRole("heading", { name: "Alle Listen stadtweit" }) });
    const zeilen = tafel.locator("ol > li");
    await expect(zeilen.nth(0)).toContainText("Grüne");
    await expect(zeilen.nth(1)).toContainText("SPD");
    await expect(zeilen.nth(2)).toContainText("CDU");
  });

  test("eine Liste antippen zeigt sechs Wahlbereiche mit Kandidat*innen", async ({ page }) => {
    await page.goto("/wahlabend");

    // Die Wahlbereiche liegen hinter dem zweiten Reiter; ohne Auswahl steht
    // dort nichts — die Karten kommen erst mit der Liste.
    await page.getByRole("tab", { name: "Wahlbereiche" }).click();
    await expect(page.getByRole("article")).toHaveCount(0);

    const wahl = page
      .locator("section")
      .filter({ has: page.getByRole("heading", { name: "Eine Liste, sechs Wahlbereiche" }) });
    await wahl.getByRole("button", { name: "Volt", exact: true }).click();

    // Sechs Wahlbereiche, egal ob die Liste überall antritt.
    await expect(page.getByRole("article")).toHaveCount(6);
    const wahlbereichI = page
      .getByRole("article")
      .filter({ has: page.getByRole("heading", { name: "Stadtmitte Nord" }) });
    await expect(wahlbereichI).toBeVisible();
    // Der Name steht in der Karte, nicht bloß irgendwo auf der Seite: Die
    // ausklappbare Sitzliste ganz unten führt ihn auch.
    await expect(wahlbereichI.getByText("Schilling, Daniel")).toBeVisible();

    // Die Auswahl gehört in die Adresse: Nur so lässt sich ein Wahlbereich
    // weiterreichen, und nur so überlebt sie ein Neuladen.
    await expect(page).toHaveURL(/[?&]liste=volt/);
    await expect(page).toHaveURL(/[?&]ansicht=bereiche/);
  });

  test("die Karte zeigt die sechs Wahlbereiche — und ein Wahlbereich öffnet seine Wahlbezirke", async ({ page }) => {
    await page.goto("/wahlabend?ansicht=bereiche&liste=volt");
    const karte = page.getByRole("img", { name: "Karte von Oldenburg" });
    await expect(karte).toBeVisible();
    // Sechs Flächen, sechs römische Ziffern (jede zweimal im SVG: Halo + Schrift).
    await expect(karte.locator("path")).toHaveCount(6);
    await expect(karte.getByText("IV", { exact: true }).first()).toBeVisible();

    // Einen Wahlbereich antippen: nur SEINE Wahlbezirke, groß — die
    // Geometrie und die zweite Antwort kommen erst jetzt. `force`, weil sich
    // die Rechtecke um zwei Polygone überschneiden, auch wenn die Flächen es
    // nicht tun.
    await karte.locator("path").first().click({ force: true });
    await expect(page.getByRole("heading", { name: /^Wahlbereich [IVX]+ · / })).toBeVisible();
    // Die Geometrie kommt nach dem Antippen — `count()` wartet nicht von
    // selbst, `expect.poll` tut es.
    await expect.poll(() => karte.locator("path").count()).toBeGreaterThan(6);
    expect(await karte.locator("path").count()).toBeLessThan(91);

    // „Ganze Stadt": alle 91 Urnenbezirke.
    await page.getByRole("button", { name: "Ganze Stadt" }).click();
    await expect(karte.locator("path")).toHaveCount(91);

    // Ein Wahlbezirk antippen zeigt sein Ergebnis.
    await karte.locator("path").first().click({ force: true });
    // Die Tafel des Wahllokals steht da — mit seinen gültigen Stimmen.
    await expect(page.getByText(/gültige Stimmen/)).toBeVisible();

    // Und zurück zu den sechs.
    await page.getByRole("button", { name: "Wahlbereiche" }).first().click();
    await expect(karte.locator("path")).toHaveCount(6);
  });

  test("die Rangliste unter der Karte nennt jeden Wahlbezirk der Liste mit Rang — die Briefwahl mit ihrem Wahlbereich", async ({ page }) => {
    await page.goto("/wahlabend?ansicht=bereiche&liste=volt");
    const liste = page.getByTestId("bezirks-rangliste");
    await expect(liste).toContainText("Volt in allen Wahlbezirken der Stadt");
    await expect(liste).toContainText("60 von 133 Bezirken gezählt");
    // 133 Zeilen, die erste trägt Rang 1 und den stärksten Anteil der Abschrift.
    await expect(liste.locator("ol > li")).toHaveCount(133);
    await expect(liste.locator("ol > li").first()).toContainText(RANGLISTE.rows[0].name);
    await expect(liste.locator("ol > li").first()).toContainText("1");
    // Die Briefwahl steht dazwischen und nennt ihren Wahlbereich ausdrücklich.
    await expect(liste.locator("ol > li").filter({ hasText: "Briefwahl" }).first().locator("[data-postal]")).toHaveText(/WB [IVX]+/);
    // Eine Zeile antippen holt die Karte in die Bezirke und wählt den Bezirk.
    await liste.locator("ol > li").first().getByRole("button").click();
    const karte = page.getByRole("img", { name: "Karte von Oldenburg" });
    await expect.poll(() => karte.locator("path").count()).toBe(91);
    await expect(page.getByText(/gültige Stimmen/)).toBeVisible();
  });

  test("der Wahlbezirk filtert die Rangliste auf ein Wahllokal", async ({ page }) => {
    await page.goto("/wahlabend?ansicht=kandidaten");
    const wahl = page.getByLabel("Wahlbezirk", { exact: true });
    await expect(wahl).toBeVisible();
    // Ohne Auswahl steht die ganze Stadt da, und jede Zeile nennt ihre
    // Hochburg — den Wahlbezirk, in dem diese Kandidatur am stärksten war.
    await expect(page.getByText(`${KANDIDATEN.total} Kandidaturen`)).toBeVisible();
    const hochburg = KANDIDATEN.rows.find((z: { top_district: number | null }) => z.top_district !== null);
    // In der TABELLE, nicht im Auswahlfeld: Dort steht derselbe Name als
    // `<option>` und ist unsichtbar.
    if (hochburg) await expect(page.locator("table").getByText(hochburg.top_district_name).first()).toBeVisible();

    // Ein Wahllokal wählen: weniger Kandidaturen, und die Adresse merkt es sich.
    const erster = KANDIDATEN.districts.find((b: { postal: boolean }) => !b.postal);
    await wahl.selectOption(String(erster.number));
    await expect(page).toHaveURL(new RegExp(`[?&]bezirk=${erster.number}`));
  });

  test("ein Name faltet alle Wahlbezirke dieser einen Kandidatur auf", async ({ page }) => {
    await page.goto("/wahlabend?ansicht=kandidaten");
    const name = KANDIDAT.name;
    const griff = page.locator("table").getByRole("button", { name: new RegExp(name) }).first();
    await expect(griff).toHaveAttribute("aria-expanded", "false");

    // Erst beim Aufklappen wird geholt — 383 Zeilen auf Vorrat wären 383 Abrufe.
    await expect(page.getByText(/Wo die Stimmen herkamen/i)).toHaveCount(0);
    await griff.click();
    await expect(griff).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByText(/Wo die Stimmen herkamen/i).first()).toBeVisible();

    // Jeder Wahlbezirk des Wahlbereichs steht da, stärkster zuerst.
    const tafel = page.locator("table li");
    await expect.poll(() => tafel.count()).toBe(KANDIDAT.districts.length);
    await expect(tafel.first()).toContainText(KANDIDAT.districts[0].name);

    // Und ein zweiter Klick klappt wieder zu.
    await griff.click();
    await expect(page.getByText(/Wo die Stimmen herkamen/i)).toHaveCount(0);
  });

  test("die Kandidaten-Rangliste kommt vom Server, mit stadtweitem Rang", async ({ page }) => {
    await page.goto("/wahlabend?ansicht=kandidaten");
    const reiter = page.getByRole("tab", { name: "Kandidat*innen" });
    await expect(reiter).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { name: "Alle Kandidat*innen nach Personenstimmen" })).toBeVisible();
    // Die Seite zeigt, was der Server schickt — Platz 1 der Probe steht oben,
    // mit seinem Rang. (Auf 1280 px ist es die Tabelle, darunter die Liste;
    // der Name steht in beiden genau einmal sichtbar.)
    const erster = KANDIDATEN.rows[0];
    await expect(page.getByText(erster.name).first()).toBeVisible();
    await expect(page.getByText(`${KANDIDATEN.total} Kandidaturen`)).toBeVisible();
    // Ein Filter wandert in die Adresse — die Rangliste selbst holt der Server.
    await page.getByRole("button", { name: "Volt", exact: true }).first().click();
    await expect(page).toHaveURL(/[?&]kliste=volt/);
  });
});

/**
 * Mobil (390 px): Die Seite scrollt nicht seitwärts.
 *
 * Dieselbe Zusage und dieselbe Messung wie in `14-layout.spec.ts` — dort für
 * die Seiten ohne Mock, hier für den Wahlabend MIT Zahlen: Erst mit den
 * Wahlbereich-Karten und dem Sitzband steht überhaupt etwas auf der Seite,
 * das zu breit werden könnte.
 */
test.describe("Handy (390px): der Wahlabend bleibt in der Breite", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  /** Um wie viel ist die Seite breiter als das Fenster? 0 = gar nicht. */
  async function ueberbreite(page: Page): Promise<number> {
    return page.evaluate(() => {
      const d = document.documentElement;
      return Math.max(0, d.scrollWidth - d.clientWidth);
    });
  }

  /** Die Elemente, die über den rechten Rand hinausragen — für die Meldung.
   *  Ein Element DARF überstehen, wenn es oder ein Vorfahr selbst scrollt. */
  async function ueberstehende(page: Page): Promise<string[]> {
    return page.evaluate(() => {
      const breite = document.documentElement.clientWidth;
      const aus: string[] = [];
      for (const el of Array.from(document.querySelectorAll("body *"))) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        let scrollt = false;
        for (let p: Element | null = el; p; p = p.parentElement) {
          const s = getComputedStyle(p);
          if (s.overflowX === "auto" || s.overflowX === "scroll" || s.overflowX === "hidden") {
            scrollt = true;
            break;
          }
        }
        if (scrollt) continue;
        if (r.right > breite + 1) {
          const kurz =
            el.tagName.toLowerCase() +
            (el.className && typeof el.className === "string"
              ? "." + el.className.split(/\s+/).slice(0, 3).join(".")
              : "");
          aus.push(`${kurz} (bis ${Math.round(r.right)}px, Fenster ${breite}px)`);
        }
      }
      return aus.slice(0, 5);
    });
  }

  test.beforeEach(async ({ page }) => {
    await appConfig(page, ["wahlabend"]);
    wahlabendMock(page);
  });

  for (const pfad of ["/wahlabend", "/wahlabend?liste=volt"]) {
    test(`${pfad} bleibt in der Breite`, async ({ page }) => {
      await page.goto(pfad, { waitUntil: "networkidle" });
      await expect(page.getByText("60 von 133 Wahlbezirken ausgezählt")).toBeVisible();
      const zuviel = await ueberbreite(page);
      expect(
        zuviel,
        `${pfad} ist ${zuviel}px zu breit. Schuldige:\n  ` +
          (await ueberstehende(page)).join("\n  "),
      ).toBeLessThanOrEqual(1);
    });
  }
});

/* ── Die Stichwahl (docs/plan-stichwahl-spannung.md S4) ─────────────────────
 * Zwei Stände nacheinander: erst 40 Bezirke (Rohr vorn), dann 60 (Prange
 * vorn, Führungswechsel beim 50.). `page.clock` dreht die Uhr eine Minute
 * vor, damit die Seite nachfragt — sie fragt alle 60 s. Der dritte Stand
 * (133) ist entschieden. Die Abschriften kommen aus der Probe des Backends
 * (`tests/test_browsertest_fixtures.py` hält sie am Vertrag). */

const STICHWAHL: Record<number, unknown> = Object.fromEntries(
  [40, 60, 133].map((n) => [n, JSON.parse(readFileSync(path.join(__dirname, "fixtures", `stichwahl-probe-${n}.json`), "utf8"))]),
);

function stichwahlMock(page: Page, staende: number[]) {
  let i = 0;
  page.route("**/api/wahlabend/stichwahl*", (route) => {
    const n = staende[Math.min(i, staende.length - 1)];
    i += 1;
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(STICHWAHL[n]) });
  });
}

test.describe("Stichwahl: Momente", () => {
  test.beforeEach(async ({ page }) => {
    await appConfig(page, ["wahlabend"]);
  });

  test("die Meldung nennt die neuen Bezirke, und der Titel trägt den Stand", async ({ page }) => {
    stichwahlMock(page, [60]);
    await page.goto("/wahlabend/stichwahl?probe=1");
    await expect(page.getByTestId("meldung")).toContainText("10 weitere Bezirke");
    await expect(page.getByTestId("meldung")).toContainText(/Prange \+[\d.]+, Rohr \+[\d.]+/);
    // Der 60er-Stand trägt den Wechsel beim 50. — nicht bei 60: keine Zeile.
    await expect(page.getByTestId("fuehrungswechsel-zeile")).toHaveCount(0);
    await expect.poll(() => page.title()).toMatch(/Prange 5\d,\d · Rohr 4\d,\d — 60\/133 · Stichwahl/);
    await expect(page.getByTestId("hochrechnung")).toContainText("Chance: Ulf Prange");
  });

  test("bei einem Führungswechsel tauschen die Karten den Platz", async ({ page }) => {
    await page.clock.install();
    stichwahlMock(page, [40, 60]);
    await page.goto("/wahlabend/stichwahl?probe=1");
    const karten = page.getByTestId("person");
    await expect(karten).toHaveCount(2);
    // 40 Bezirke: Rohr vorn — seine Karte steht zuerst (CSS `order`), trägt „Vorn".
    const erste = async () => {
      const lagen = await karten.evaluateAll((els) => els.map((e) => ({ slug: (e as HTMLElement).dataset.slug, x: e.getBoundingClientRect().left, y: e.getBoundingClientRect().top })));
      return lagen.sort((a, b) => a.y - b.y || a.x - b.x)[0]?.slug;
    };
    await expect.poll(erste).toBe("rohr");
    await expect(page.locator("[data-slug=rohr]")).toContainText("Vorn");

    // Eine Minute später fragt die Seite nach — und bekommt den 60er-Stand.
    await page.clock.runFor(61_000);
    await expect(page.getByText("60 von 133 Wahlbezirken ausgezählt")).toBeVisible();
    await expect.poll(erste).toBe("prange");
    await expect(page.locator("[data-slug=prange]")).toContainText("Vorn");
    await expect(page.locator("[data-slug=rohr]")).not.toContainText("Vorn");
  });

  test("rechnerisch entschieden: Lotti und „ist gewählt“", async ({ page }) => {
    stichwahlMock(page, [133]);
    await page.goto("/wahlabend/stichwahl?probe=1");
    await expect(page.getByTestId("entschieden")).toContainText("Ulf Prange ist gewählt");
    await expect(page.locator("[data-slug=prange]")).toContainText("Gewählt");
    await expect(page.getByTestId("hochrechnung")).toContainText("Endstand");
    await expect(page.getByTestId("verlauf")).toContainText("1 Führungswechsel");
  });
});

/* ── Die Karte der Stichwahl (S5) ──────────────────────────────────────── */

const STICHWAHL_BEZIRKE = JSON.parse(readFileSync(path.join(__dirname, "fixtures", "stichwahl-bezirke-probe-60.json"), "utf8"));

test.describe("Stichwahl: Karte", () => {
  test("91 Flächen, offene gestrichelt, ein Tipp zeigt beide Wahlgänge", async ({ page }) => {
    await appConfig(page, ["wahlabend"]);
    stichwahlMock(page, [60]);
    // Später registriert = zuerst gefragt (s. wahlabendMock).
    await page.route("**/api/wahlabend/stichwahl/bezirke*", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(STICHWAHL_BEZIRKE) }),
    );
    await page.goto("/wahlabend/stichwahl?probe=1");
    const karte = page.getByTestId("stichwahl-karte");
    await expect.poll(() => karte.locator("svg path").count()).toBe(91);
    // 60 gezählt, davon alle Urne (die Briefwahl kommt zuletzt): 31 offen.
    await expect.poll(() => karte.locator("svg path[data-offen]").count()).toBe(31);
    await expect(karte).toContainText("60 von 91 Urnenbezirken gezählt");
    await karte.locator("svg path").first().click({ force: true });
    await expect(page.getByTestId("bezirkstafel")).toContainText("1. Wahlgang");
    await expect(page.getByTestId("bezirkstafel")).toContainText("Stichwahl");
    // Ein Wahlbereich heranholen: weniger Flächen, mit Nummer beschriftet.
    await karte.getByRole("button", { name: "I", exact: true }).click();
    await expect.poll(() => karte.locator("svg path").count()).toBeLessThan(91);
    await expect(karte.getByText("Wahlbereich I", { exact: true })).toBeVisible();
  });
});

/* ── Simulator und Tippspiel-Einladung (19.09.2026) ──────────────────────── */

/** `/api/wahlen` entscheidet, ob und wohin verlinkt wird — die Seite rät das
 *  nicht nach. Drei Fälle, drei Antworten. */
function wahlenMock(page: Page, zeile: { tipp_path: string; tipp_locked: boolean }) {
  return page.route("**/api/wahlen", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        elections: [{
          slug: "ob-stichwahl-2026", short_title: "OB-Stichwahl Oldenburg", title: "Stichwahl",
          date: "2026-09-27", polls_close: "2026-09-27T18:00:00+02:00", kind: "mayor", status: "live",
          path: "/wahlabend/stichwahl", summary: null, focus: true, top: [], ...zeile,
        }],
      }),
    }));
}

test.describe("Simulator und Tippspiel-Einladung", () => {
  test.beforeEach(async ({ page }) => {
    await appConfig(page, ["wahlabend", "tippspiel"]);
  });

  test("der Auszählungs-Simulator taucht im Prod-Build nirgends auf", async ({ page }) => {
    // Die Browsertests laufen OHNE `NEXT_PUBLIC_RATSLOTSE_ENV=dev` — also so,
    // wie Prod gebaut wird. Ein Werkzeug, mit dem jede*r die Zahlen der Seite
    // verstellen kann, darf dort nicht auftauchen.
    stichwahlMock(page, [60]);
    await wahlenMock(page, { tipp_path: "/tipp?runde=stichwahl", tipp_locked: false });
    await page.goto("/wahlabend/stichwahl?probe=1");
    await expect(page.getByTestId("meldung")).toBeVisible();
    await expect(page.getByTestId("auszaehlungs-simulator")).toHaveCount(0);
  });

  test("offene Runde: die Einladung führt ins Tippspiel", async ({ page }) => {
    stichwahlMock(page, [60]);
    await wahlenMock(page, { tipp_path: "/tipp?runde=stichwahl", tipp_locked: false });
    await page.goto("/wahlabend/stichwahl?probe=1");
    const einladung = page.getByTestId("tippspiel-einladung");
    await expect(einladung).toBeVisible();
    await expect(einladung.getByRole("link")).toHaveAttribute("href", "/tipp?runde=stichwahl");
  });

  test("Konto-Runde: die Einladung führt zur Anmeldung, nicht gegen die Wand", async ({ page }) => {
    stichwahlMock(page, [60]);
    await wahlenMock(page, { tipp_path: "", tipp_locked: true });
    await page.goto("/wahlabend/stichwahl?probe=1");
    await expect(page.getByTestId("tippspiel-einladung").getByRole("link")).toHaveAttribute("href", "/login");
  });

  test("ohne Runde bleibt die Seite still", async ({ page }) => {
    stichwahlMock(page, [60]);
    await wahlenMock(page, { tipp_path: "", tipp_locked: false });
    await page.goto("/wahlabend/stichwahl?probe=1");
    await expect(page.getByTestId("meldung")).toBeVisible();
    await expect(page.getByTestId("tippspiel-einladung")).toHaveCount(0);
  });

  test("und wenn `/api/wahlen` ausfällt, bleibt der Wahlabend stehen", async ({ page }) => {
    // Der Schalter `wahlabend` ist im Test-Backend aus, `/api/wahlen`
    // antwortet dann mit 404. Genau daran ist die Seite am 19.09.2026 in die
    // Fehlerfläche gelaufen, bevor die Einladung ihren Fehler selbst schluckte.
    stichwahlMock(page, [60]);
    await page.route("**/api/wahlen", (route) =>
      route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "aus" }) }));
    await page.goto("/wahlabend/stichwahl?probe=1");
    await expect(page.getByTestId("meldung")).toBeVisible();
    await expect(page.getByTestId("tippspiel-einladung")).toHaveCount(0);
  });
});
