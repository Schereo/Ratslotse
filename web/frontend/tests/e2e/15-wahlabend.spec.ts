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

    // Ohne Auswahl steht unten nichts — die Karten kommen erst mit der Liste.
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
