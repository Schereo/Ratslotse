/**
 * Meldet jede Identität EINMAL je Lauf an und legt ihre Sitzung ab.
 *
 * Läuft als eigenes Playwright-Projekt vor allen anderen (`dependencies` in
 * `playwright.config.ts`). Warum das die Suite halbiert, steht in `konten.ts`.
 *
 * OHNE BROWSER. Die Anmeldung geht über die API, nicht über das Formular: Das
 * Cookie ist dasselbe (`access_token`, gesetzt von `app/session.py`), nur ohne
 * Seitenaufbau, Hydration und Navigation. Der Weg durch das FORMULAR wird
 * weiterhin geprüft — in `01-auth.spec.ts`, und dort gehört er auch hin.
 *
 * ALLES IN EINEM TEST, und das ist Absicht: In der CI läuft die Suite
 * aufgeteilt (`--shard=i/4`, s. `.github/workflows/e2e.yml`). Vier einzelne
 * Setup-Tests dürfte Playwright auf die Teile verteilen — dann fehlte einem
 * Teil die Sitzung, die er braucht, und der Fehler käme als „Datei nicht
 * gefunden" mitten aus einem ganz anderen Test. Ein Test kann nicht zerfallen.
 */
import { expect, test as setup } from "@playwright/test";

import { KONTEN, PASSWORT, zustandsDatei } from "./konten";

setup("Sitzungen für alle Identitäten anlegen", async ({ playwright, baseURL }) => {
  for (const konto of KONTEN) {
    const ctx = await playwright.request.newContext({ baseURL });

    if (konto.anlegen) {
      // 409 heißt „gibt es schon" und ist in Ordnung: Ein zweiter Lauf gegen
      // dieselbe Datenbank soll nicht daran scheitern. Die Anmeldung darunter
      // ist ohnehin der Schritt, der zählt.
      await ctx.post("/api/auth/register", {
        data: { email: konto.email, password: PASSWORT },
      });
    }

    const anmeldung = await ctx.post("/api/auth/login", {
      data: { email: konto.email, password: PASSWORT },
    });
    expect(
      anmeldung.ok(),
      `Anmeldung für ${konto.email} fehlgeschlagen: ${await anmeldung.text()}`,
    ).toBeTruthy();

    // Der Einrichtungs-Assistent liegt als Fläche über der ganzen Seite
    // (`fixed inset-0`) und fängt JEDEN Klick ab — ein Test, der etwas ganz
    // anderes prüft, wartet sonst 30 Sekunden auf einen Klick, der nie
    // ankommt. `step: 3, done: true` ist genau das, was das „Überspringen" im
    // Assistenten sendet; die 4 aus dem Router-Kommentar weist das Schema mit
    // 422 ab. Wer den Assistenten SELBST prüfen will, nimmt keine dieser
    // Sitzungen — `13-einrichtung.spec.ts` legt sich frische Konten an.
    const assistent = await ctx.post("/api/onboarding/setup", {
      data: { step: 3, done: true },
    });
    expect(assistent.ok(), await assistent.text()).toBeTruthy();

    // „Gespräche merken?" steht sonst als Karte VOR dem Eingabefeld der
    // Frage-Seite, solange sie niemand beantwortet hat. `false` ist die
    // zurückhaltendere Antwort und für Tests die richtige: Sie legt nichts am
    // Konto ab.
    const gespraeche = await ctx.post("/api/council/conversations/setting", {
      data: { an: false },
    });
    expect(gespraeche.ok(), await gespraeche.text()).toBeTruthy();

    await ctx.storageState({ path: zustandsDatei(konto.name) });
    await ctx.dispose();
  }
});
