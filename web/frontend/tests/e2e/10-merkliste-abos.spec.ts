/**
 * Merkliste und Ausschuss-Abos — die beiden Stellen, an denen jemand der App
 * sagt, was ihn interessiert.
 *
 * Beide waren bisher nur als Screenshot abgedeckt („rendert ohne Fehler").
 * Was zählt, ist aber der Vorgang: Ein Abo, das die Oberfläche als gesetzt
 * zeigt und der Server nicht kennt, meldet nie etwas — und niemand merkt es,
 * weil nichts kaputt aussieht.
 */
import { expect, test } from "@playwright/test";
import { einrichtungUeberspringen } from "./helpers";

const PASSWORT = "password123";
const KONTO = "nutzerin@example.org";

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.locator("#email").fill(KONTO);
  await page.locator("#password").fill(PASSWORT);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await page.waitForURL(/\/(link|dashboard)/, { timeout: 15_000 });
  await einrichtungUeberspringen(page);
});

test.describe("Merkliste", () => {
  test("gruppiert nach Sitzung und zeigt die Anzahl", async ({ page }) => {
    const bauen = (id: number, titel: string) => ({
      id, kind: "decision", target_key: `decision:42:${id}`, title: titel,
      subtitle: "Bauausschuss · 2026-08-20", created_at: "2026-08-26T12:00:00",
      notify_result: false, result_notified_at: null, state: "decided",
      is_group: false, url: `/council/decision?id=${id}`, ksinr: 42,
      item_number: `Ö ${id}`, agenda_item: null,
      session: { ksinr: 42, committee: "Bauausschuss", session_date: "2026-08-20", session_time: "17:00", location: "Rathaus", n_items: 9 },
      decision: { id, outcome: "accepted", title: titel, simple_summary: "x" },
    });
    await page.route("**/api/bookmarks", (r) =>
      r.fulfill({ json: { bookmarks: [bauen(1, "Radwege am Hafen"), bauen(2, "Neue Turnhalle")] } }));
    await page.goto("/bookmarks");
    // Eine Karte je SITZUNG, nicht je Eintrag — sonst scrollt man sechs
    // Karten für eine Sitzung.
    const kopf = page.getByRole("button", { name: /Bauausschuss vom 20\.08\.2026, 2 Einträge anzeigen/ });
    await expect(kopf).toBeVisible();
    await expect(page.getByText("Radwege am Hafen")).toHaveCount(0);
    await kopf.click();
    await expect(page.getByText("Radwege am Hafen")).toBeVisible();
    await expect(page.getByText("Neue Turnhalle")).toBeVisible();
  });

  test("die leere Liste erklärt sich, statt nur leer zu sein", async ({ page }) => {
    await page.route("**/api/bookmarks", (r) => r.fulfill({ json: { bookmarks: [] } }));
    await page.goto("/bookmarks");
    await expect(page.getByText("Deine Merkliste ist noch leer")).toBeVisible();
  });

  test("ein Eintrag lässt sich entfernen — und der Server erfährt es", async ({ page }) => {
    let geloescht: string | null = null;
    const eintrag = {
      id: 1, kind: "decision", target_key: "decision:42:4",
      title: "Bebauungsplan am Hafen", subtitle: "Bauausschuss · 2026-08-20 · Ö 4",
      created_at: "2026-08-26T12:00:00", notify_result: false,
      result_notified_at: null, state: "decided", is_group: false,
      url: "/council/decision?id=91", ksinr: 42, item_number: "Ö 4",
      agenda_item: null,
      session: { ksinr: 42, committee: "Bauausschuss", session_date: "2026-08-20", session_time: "17:00", location: "Rathaus", n_items: 9 },
      decision: { id: 91, outcome: "accepted", title: "Bebauungsplan am Hafen", simple_summary: "Beschlossen." },
    };
    await page.route("**/api/bookmarks/*", (route) => {
      geloescht = route.request().method();
      return route.fulfill({ status: 204, body: "" });
    });
    await page.route("**/api/bookmarks", (route) =>
      route.fulfill({ json: { bookmarks: geloescht ? [] : [eintrag] } }));
    await page.goto("/bookmarks");
    // Die Liste gruppiert nach Sitzung und klappt die Gruppen zu. Das ist der
    // Sinn der Seite: Wer sechs Punkte einer Sitzung gemerkt hat, will nicht
    // sechs Karten scrollen. Der Eintrag steht also EINE Ebene tiefer.
    await page.getByRole("button", { name: /Bauausschuss.*anzeigen/ }).click();
    await expect(page.getByText("Bebauungsplan am Hafen").first()).toBeVisible();
    await page.getByRole("button", { name: "Aus der Merkliste entfernen" }).first().click();
    await expect.poll(() => geloescht).toBe("DELETE");
  });

  test("die Suche filtert die Liste", async ({ page }) => {
    const bauen = (id: number, titel: string) => ({
      id, kind: "decision", target_key: `decision:42:${id}`, title: titel,
      subtitle: "Bauausschuss · 2026-08-20", created_at: "2026-08-26T12:00:00",
      notify_result: false, result_notified_at: null, state: "decided",
      is_group: false, url: `/council/decision?id=${id}`, ksinr: 42,
      item_number: `Ö ${id}`, agenda_item: null,
      session: { ksinr: 42, committee: "Bauausschuss", session_date: "2026-08-20", session_time: "17:00", location: "Rathaus", n_items: 9 },
      decision: { id, outcome: "accepted", title: titel, simple_summary: "x" },
    });
    await page.route("**/api/bookmarks", (r) =>
      r.fulfill({ json: { bookmarks: [bauen(1, "Radwege am Hafen"), bauen(2, "Neue Turnhalle")] } }));
    await page.goto("/bookmarks");
    await page.getByRole("button", { name: /Bauausschuss.*anzeigen/ }).click();
    await expect(page.getByText("Neue Turnhalle")).toBeVisible();
    await page.getByPlaceholder(/Merkliste durchsuchen/).fill("Radwege");
    // Die Suche greift auf den EINTRÄGEN, die Gruppe bleibt aufgeklappt.
    await expect(page.getByText("Neue Turnhalle")).toHaveCount(0);
    await expect(page.getByText("Radwege am Hafen")).toBeVisible();
    // Und sie sucht auch im Gremium, nicht nur im Titel.
    await page.getByPlaceholder(/Merkliste durchsuchen/).fill("Bauausschuss");
    await expect(page.getByText("Neue Turnhalle")).toBeVisible();
    await expect(page.getByText("Radwege am Hafen")).toBeVisible();
  });
});

test.describe("Ausschuss-Abos", () => {
  // Zwei Endpunkte, und das ist der Kern: `/council/committees` liefert die
  // NAMEN (Zeichenketten), `/subscriptions` das eigene Abo. Zeigt die
  // Oberfläche ein Abo, das der Server nicht kennt, meldet sie nie etwas —
  // und es sieht nicht kaputt aus.
  const NAMEN = ["Rat der Stadt Oldenburg", "Verkehrsausschuss", "Kulturausschuss"];

  async function gremien(page: import("@playwright/test").Page, abos: string[]) {
    await page.route("**/api/council/committees**", (r) =>
      r.fulfill({ json: { committees: NAMEN } }));
    await page.route("**/api/subscriptions**", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({ json: { subscriptions: abos } });
      }
      return route.fulfill({ json: { ok: true } });
    });
  }

  test("zeigt die Gremien mit ihrem Kurznamen", async ({ page }) => {
    await gremien(page, []);
    await page.goto("/abos");
    await expect(page.getByRole("heading", { name: "Ausschuss-Abos" })).toBeVisible();
    // Der Kurzname, nicht der amtliche — „Rat der Stadt Oldenburg" sprengt
    // sonst die Kachel.
    await expect(page.getByText("Verkehr", { exact: true }).first()).toBeVisible();
  });

  test("ein Klick abonniert wirklich — und schickt den AMTLICHEN Namen", async ({ page }) => {
    let gesendet: Record<string, unknown> | null = null;
    await page.route("**/api/council/committees**", (r) =>
      r.fulfill({ json: { committees: NAMEN } }));
    await page.route("**/api/subscriptions**", (route) => {
      if (route.request().method() === "GET") return route.fulfill({ json: { subscriptions: [] } });
      gesendet = route.request().postDataJSON();
      return route.fulfill({ json: { ok: true } });
    });
    await page.goto("/abos");
    await page.getByRole("button", { name: /abonnieren/i }).first().click();
    await expect.poll(() => gesendet).not.toBeNull();
    // Der Kurzname ist nur für die Anzeige. Ginge er an den Server, fände der
    // kein Gremium dieses Namens und das Abo bliebe wirkungslos.
    expect(NAMEN).toContain((gesendet as unknown as { committee_name: string }).committee_name);
  });

  test("ein bestehendes Abo steht als abonniert da", async ({ page }) => {
    await gremien(page, ["Verkehrsausschuss"]);
    await page.goto("/abos");
    await expect(page.getByRole("button", { name: /abbestellen/i }).first()).toBeVisible();
  });

  test("ein Fehler des Servers bleibt nicht stumm", async ({ page }) => {
    await page.route("**/api/council/committees**", (r) =>
      r.fulfill({ status: 500, json: { detail: "kaputt" } }));
    await page.goto("/abos");
    await expect(page.getByText("Die Gremien kamen nicht durch")).toBeVisible();
  });
});
