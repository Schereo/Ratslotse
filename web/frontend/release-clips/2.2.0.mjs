// Drehbücher für die Clips von Ratslotse 2.2.0 — eines je Highlight aus
// kern/releases.py. Aufnahme: python scripts/release_clips.py web 2.2.0
//
// Ein Drehbuch bekommt die Bühne (`stage`) und spielt darauf eine kurze
// Szene: erst Aufbau (Seite öffnen, Zustand herstellen), dann `begin()`,
// dann die Klicks. Alles vor `begin()` wird weggeschnitten; jeder `click()`
// wird zum Zoom-Beat. Was `stage` kann, steht in scripts/release-clip.mjs.
//
// Die Szenen laufen gegen die lokale App mit ECHTEN Ratsdaten
// (scripts/lokale_daten.py). Wo etwas nachgestellt ist — eine laufende
// Sitzung, eine KI-Antwort —, steht es dabei; die Tagesordnungen, Begriffe und
// Erklärungen darin sind echt.

/** Ein SSE-Strom, wie ihn POST /api/council/ask liefert (data: {json}\n\n). */
const sse = (events) => events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('');

/** Lokales Datum als ISO — toISOString wäre UTC und nachts einen Tag daneben. */
const localISO = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const hhmm = (h) => `${String(Math.max(0, Math.min(23, h))).padStart(2, '0')}:00`;

export default {
  teilen: {
    // Sitzungen teilen — auch einzelne Punkte: der Teilen-Knopf an einer Zeile.
    async run({ page, goto, begin, click, pause }) {
      await goto('/council?tab=sessions');
      await page.locator('button:has-text("TOPs")').first().click();
      await page.waitForSelector('[aria-label*="teilen"]', { timeout: 20000 });
      // Der Zeilen-Knopf heißt „Tagesordnungspunkt Ö 5 teilen", nicht „Teilen".
      const knopf = page.locator('[aria-label*="teilen"]').nth(4);
      await knopf.scrollIntoViewIfNeeded();
      await pause(1.0);
      await begin();
      await pause(0.6);
      await click(knopf);
      await pause(3.0);   // „Link kopiert." lesen lassen
    },
  },

  kalender: {
    // Deine Sitzungen im Kalender: die Karte aufklappen, den Link kopieren.
    async run({ page, goto, begin, click, pause }) {
      await goto('/abos');
      await page.waitForSelector('[aria-label="Kalender-Abo anzeigen"]');
      await pause(0.8);
      await begin();
      await pause(0.5);
      await click('[aria-label="Kalender-Abo anzeigen"]');
      await page.waitForSelector('button:has-text("Link kopieren")');
      await pause(1.4);
      await click('button:has-text("Link kopieren")');
      await pause(2.8);
    },
  },

  glossar: {
    // Der Rat erklärt seine Fachwörter: Frage stellen, ein Begriff in der
    // Antwort ist gepunktet unterstrichen, ein Klick zeigt die Erklärung.
    //
    // Die ANTWORT ist nachgestellt (kein Sprachmodell im Schnitt, keine
    // Kosten, jedes Mal gleich). Ihr Inhalt stützt sich auf die echte
    // Tagesordnung des Rates vom 31.08.2026 (Ö 9.4–9.6); die Erklärung, die
    // aufgeht, kommt aus dem echten Glossar (lib/glossary.ts).
    async run({ page, goto, begin, click, look, type, pause }) {
      const antwort =
        'Eine Veränderungssperre friert ein Gebiet ein, solange die Stadt dort einen neuen ' +
        'Bebauungsplan aufstellt: Bauvorhaben, die dem künftigen Plan zuwiderlaufen könnten, ' +
        'werden bis dahin nicht genehmigt. Der Rat beschließt sie als Satzung, nachdem ein ' +
        'Aufstellungsbeschluss gefasst ist; sie gilt zwei Jahre und lässt sich um ein Jahr ' +
        'verlängern.\n\nIn Oldenburg standen am 31. August 2026 die Verlängerungen der ' +
        'Veränderungssperren 94, 95 und 96 auf der Tagesordnung des Rates — sie sichern ' +
        'Bebauungspläne, mit denen die Stadt Vergnügungsstätten an der Bremer Heerstraße, der ' +
        'Bürgerstraße und der Nadorster Straße steuern will.';
      const stuecke = antwort.match(/[^ ]+(?: [^ ]+){0,6} ?/g) ?? [antwort];
      await page.route('**/api/council/ask', (route) => route.fulfill({
        status: 200, contentType: 'text/event-stream',
        body: sse([
          { type: 'sources', sources: [], mode: 'wissen', qtype: 'begriff' },
          ...stuecke.map((text) => ({ type: 'token', text })),
          { type: 'done', cited: [] },
        ]),
      }));
      await goto('/fragen');
      await page.waitForSelector('[data-search]');
      // Beim ersten Besuch fragt die Seite, ob Gespräche gemerkt werden
      // sollen — ohne Antwort bleibt der Frage-Knopf aus. Das gehört zum
      // Aufbau, nicht in den Clip.
      const einwilligung = page.locator('button:has-text("KI nutzen, nicht merken")');
      if (await einwilligung.count()) { await einwilligung.click(); await pause(0.8); }
      await pause(0.6);
      await begin();
      await type('[data-search]', 'Was ist eine Veränderungssperre?');
      await page.waitForSelector('button[aria-label="Fragen"]:not([disabled])');
      await pause(0.4);
      await click('button[aria-label="Fragen"]');
      await page.waitForSelector('button[aria-label^="Was bedeutet"]', { timeout: 15000 });
      await pause(1.6);
      // Am Schreibtisch geht die Erklärung beim Überfahren auf — ein Klick
      // schlösse sie wieder. Also hinsehen statt tippen.
      const begriff = page.locator('button[aria-label^="Was bedeutet"]').first();
      await look(begriff);
      await pause(3.4);
    },
  },

  live: {
    // Live: welcher Punkt gerade dran ist — die Karte auf „Heute", ein Klick
    // führt in die Tagesordnung, dort ist der laufende Punkt markiert.
    //
    // NACHGESTELLT ist nur, DASS die Sitzung gerade läuft: Die Ratssitzung
    // vom 31.08.2026 (ksinr 4702, echte Tagesordnung) bekommt das heutige
    // Datum und einen Übertragungsstand auf TOP 9.3. Wer spricht, bleibt
    // offen — eine echte Person würden wir nicht in eine gestellte Szene setzen.
    async run({ page, goto, begin, click, look, scrollTo, pause }) {
      const KSINR = 4702;
      const jetzt = new Date();
      const heute = localISO(jetzt);
      const stand = {
        item_number: '9.3', item_title: 'Bebauungsplan 837 (nördlich Eßkamp/östlich Südbäke)',
        block_start: null, phase: 'Aussprache', speaker: null, party: null,
        since: new Date(jetzt.getTime() - 6 * 60000).toISOString(),
        as_of: new Date(jetzt.getTime() - 40000).toISOString(),
        updated_at: new Date(jetzt.getTime() - 40000).toISOString(),
        finished: false,
      };
      const live = (s) => ({
        ...s, session_date: heute, session_time: hhmm(jetzt.getHours() - 1),
        live_until: hhmm(jetzt.getHours() + 3), live_state: stand,
      });
      await page.route(/\/api\/council\/sessions\?/, async (route) => {
        const r = await route.fetch();
        const j = await r.json();
        const drin = (j.sessions ?? []).some((s) => s.ksinr === KSINR);
        j.sessions = (j.sessions ?? []).map((s) => (s.ksinr === KSINR ? live(s) : s));
        if (!drin && route.request().url().includes('scope=upcoming')) {
          j.sessions.unshift(live({
            ksinr: KSINR, committee: 'Rat', location: 'Altes Rathaus, Ratssaal',
            n_items: 37, my_topic_items: [], matched_items: [],
          }));
        }
        await route.fulfill({ response: r, json: j });
      });
      await page.route(`**/api/council/session/${KSINR}`, async (route) => {
        const r = await route.fetch();
        await route.fulfill({ response: r, json: live(await r.json()) });
      });
      await goto('/dashboard');
      await page.waitForSelector('[data-testid="live-stand"]', { timeout: 15000 });
      await pause(0.8);
      await begin();
      await pause(1.4);   // die Karte lesen lassen
      await click('a:has-text("Tagesordnung")');
      await page.waitForSelector(`#session-${KSINR}`, { timeout: 15000 });
      // Die Sitzung klappt auf; der laufende Punkt trägt „Läuft gerade" —
      // dorthin blättern und hinsehen.
      const zeile = page.locator('span:has-text("Läuft gerade")').first();
      await zeile.waitFor({ timeout: 15000 });
      await pause(1.0);
      await scrollTo(zeile);
      await look(zeile);
      await pause(3.0);
    },
  },
};
