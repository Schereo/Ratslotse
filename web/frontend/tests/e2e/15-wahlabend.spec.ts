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
/** Und als Wahlbezirke (`service.districts(reg, probe_snapshot(…, 60), "probe")`). */
const BEZIRKE = JSON.parse(
  readFileSync(path.join(__dirname, "fixtures", "wahlbezirke-probe.json"), "utf8"),
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
  page.route("**/api/wahlabend/kandidaten*", (route) => {
    zaehler.rufe += 1;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(KANDIDATEN),
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
