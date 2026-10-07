// Drehbücher für die Clips von Ratslotse 3.0.0 — eines je Highlight aus
// kern/releases.py. Aufnahme: python scripts/release_clips.py web 3.0.0
//
// Ein Drehbuch bekommt die Bühne (`stage`) und spielt darauf eine kurze
// Szene: erst Aufbau (Seite öffnen, Zustand herstellen), dann `begin()`,
// dann die Klicks. Alles vor `begin()` wird weggeschnitten; jeder `click()`
// wird zum Zoom-Beat. Was `stage` kann, steht in scripts/release-clip.mjs.
//
// Die Szenen laufen gegen die lokale App mit ECHTEN Ratsdaten
// (scripts/lokale_daten.py) und — für die Ideen — einem Abzug von
// cities.sqlite. **Nichts ist gestellt**, auch die KI-Antworten nicht: Jede
// Frage wird im Aufbau einmal wirklich gestellt (Sprachmodell, wenige
// Zehntel Cent), die Antwort aufgehoben und im Clip WIEDERGEGEBEN. So
// wartet der Clip nicht zwanzig Sekunden auf das Modell, und was man sieht,
// ist trotzdem genau das, was Ratslotse geantwortet hat (2.2.0 stellte die
// Antwort noch von Hand nach).

/**
 * Echte Antworten aufheben und wiedergeben.
 *
 * Solange `aufnehmen` gilt, geht jede Anfrage an `muster` wirklich durch
 * (das Modell antwortet), und ihr Körper wird der Reihe nach aufgehoben.
 * Nach `wiedergeben()` bekommt die n-te Anfrage die n-te Antwort — sofort
 * und vollständig. Die Reihenfolge der Fragen im Clip muss also die des
 * Aufbaus sein.
 */
async function echteAntworten(page, muster) {
  const band = [];
  let abspielen = false;
  let naechste = 0;
  await page.route(muster, async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    if (!abspielen) {
      const r = await route.fetch({ timeout: 180_000 });
      const body = await r.body();
      band.push({ status: r.status(), headers: r.headers(), body });
      return route.fulfill({ status: r.status(), headers: r.headers(), body });
    }
    const aufnahme = band[naechste++];
    if (!aufnahme) return route.continue();
    return route.fulfill(aufnahme);
  });
  return {
    wiedergeben() { abspielen = true; naechste = 0; },
    verwerfen() { band.length = 0; },
    get anzahl() { return band.length; },
  };
}

/** Klickt (über `tun`) und wartet, bis Lotti fertig geantwortet hat: die
 *  Antwort ist da und ihre Figur ruht wieder (`regung="ruht"`). */
async function lottiAntwort(page, tun) {
  const antwort = page.waitForResponse((r) => r.url().includes('/council/explain'), { timeout: 180_000 });
  await tun();
  await antwort;
  await page.waitForFunction(() => {
    const f = document.querySelector('#lotti-fenster');
    return f && f.querySelector('[regung="ruht"]');
  }, null, { timeout: 60_000 });
}

export default {
  lotti: {
    // Lotti erklärt dir jede Seite: Knopf antippen, Frage zur Abstimmung,
    // danach ein Wort markieren und „Lotti fragen“.
    //
    // Beschluss: Bebauungsplan 837, Rat 31.08.2026 — „mehrheitlich bei 16
    // Gegenstimmen und einer Enthaltung“ (echter Wortlaut).
    async run({ page, goto, begin, click, type, markText, pause }) {
      const ziel = '/council/decision?id=21966';
      const frage = 'Wie viele haben dagegen gestimmt?';
      const wort = 'Öffentlichkeitsbeteiligung';
      const band = await echteAntworten(page, '**/api/council/explain**');

      // Aufbau: beide Fragen einmal wirklich stellen.
      await goto(ziel);
      await page.locator('button[aria-label="Lotti fragen"]').first().click();
      await page.locator('[aria-label="Frage an Lotti"]').fill(frage);
      await lottiAntwort(page, () => page.locator('button[aria-label="Fragen"]').last().click());
      await page.locator('button[aria-label="Lotti schließen"]').first().click();
      await pause(0.5);
      await markText('text=' + wort, wort);
      await lottiAntwort(page, () => page.locator('button[aria-label^="Lotti fragen: Was bedeutet"]').click());
      if (band.anzahl < 2) throw new Error(`Nur ${band.anzahl} Antwort(en) aufgehoben`);
      band.wiedergeben();

      // Die Szene — mit leerem Fenster: Lotti hebt den Verlauf je Tab auf
      // (components/assistentin/panel.tsx, SPEICHER/SPEICHER_ID).
      await page.evaluate(() => {
        sessionStorage.removeItem('ratslotse:lotti-verlauf');
        sessionStorage.removeItem('ratslotse:lotti-gespraech');
      });
      await goto(ziel);
      await page.waitForSelector('button[aria-label="Lotti fragen"]');
      await page.mouse.click(5, 300);   // eine verbliebene Markierung aufheben
      await pause(1.0);
      await begin();
      await pause(0.6);
      await click('button[aria-label="Lotti fragen"]');
      await page.waitForSelector('[aria-label="Frage an Lotti"]');
      await pause(0.4);
      await type('[aria-label="Frage an Lotti"]', frage);
      await pause(0.3);
      await lottiAntwort(page, () => click(page.locator('button[aria-label="Fragen"]').last()));
      await pause(2.6);   // die Antwort lesen lassen
      await click(page.locator('button[aria-label="Lotti schließen"]').first());
      await pause(0.8);
      await markText('text=' + wort, wort);
      await page.waitForSelector('button[aria-label^="Lotti fragen: Was bedeutet"]');
      await pause(0.5);
      await lottiAntwort(page, () => click('button[aria-label^="Lotti fragen: Was bedeutet"]'));
      await pause(3.4);
    },
  },

  viertel: {
    // Mein Viertel — mit dem WEG dorthin (Tims Befund 07.10.2026: Die Clips
    // fingen mittendrin an, man sah nicht, wie man hinkommt). Start auf
    // „Heute“ im Schreibtisch-Layout, die Seitenleiste ist im Bild.
    // Kita Eßkamp: im Bau, fertig zum Kindergartenjahr 2026/2027.
    viewport: { width: 1280, height: 800 },
    titel: 'Mein Viertel',
    untertitel: 'Was sich vor deiner Haustür tut',
    weg: ['Seitenleiste', 'Mein Viertel'],
    app: ['Mehr', 'Mein Viertel'],
    async run({ page, goto, begin, click, look, scrollTo, pause, say }) {
      // Das Probekonto hat Fliegerhorst gewählt (Themen) — „Mein Viertel“
      // öffnet deshalb gleich den eigenen Stadtteil.
      await goto('/dashboard');
      await page.waitForSelector('nav a:has-text("Mein Viertel")');
      await pause(1.2);
      await begin();
      say('Mein Viertel findest du in der Seitenleiste');
      await pause(1.0);
      await click(page.locator('nav a', { hasText: 'Mein Viertel' }).first());
      await page.waitForSelector('text=Vorhaben aus den Beschlüssen');
      await page.waitForSelector('.leaflet-interactive');
      say('Dein Stadtteil öffnet sich direkt — alle Vorhaben auf Karte und Liste');
      await pause(1.6);
      await look(page.locator('h1, h2', { hasText: 'Fliegerhorst' }).first());
      await pause(1.4);
      const vorhaben = page.locator('a, button', { hasText: 'Neue Grundschule und Dreifeldhalle' }).first();
      say('Ein Vorhaben öffnen: Stand, Zeitplan und die Beschlüsse dazu');
      await click(vorhaben);
      await page.waitForURL(/v=\d+/);
      await pause(1.4);
      const beschluesse = page.locator('text=/\\d Beschlüsse?/').first();
      await beschluesse.waitFor();
      await scrollTo(beschluesse, { settle: 1.4 });
      await pause(1.6);
      say('Über „Stadt zeigen“ kommst du in jedes andere Viertel');
      await click(page.locator('button, a', { hasText: 'Stadt zeigen' }).first());
      await page.waitForSelector('input[aria-label="Straße oder Stadtteil"]');
      await pause(2.4);
    },
  },

  ideen: {
    // Ideen aus anderen Städten: „Gerade in Bewegung“ → Hitzeaktionsplan →
    // Stand in Oldenburg mit Belegen → die Zeitleiste durch die Räte.
    async run({ page, goto, begin, click, look, scrollTo, pause }) {
      await goto('/council/ideen');
      await page.waitForSelector('text=Gerade in Bewegung');
      await pause(1.2);
      await begin();
      await pause(1.0);
      await click(page.locator('a', { hasText: 'Hitzeaktionsplan aufstellen' }).first());
      await page.waitForSelector('text=Und in Oldenburg?');
      await pause(1.4);
      await look(page.locator('text=Teilweise vorhanden').first());
      await pause(2.2);
      const buehne = page.locator('#buehne-titel');
      await scrollTo(buehne, { settle: 1.4 });
      await look(page.locator('[aria-label^="Potsdam:"]').first());
      await pause(1.6);
      await look(page.locator('[aria-label^="Magdeburg:"]').first());
      await pause(2.6);
    },
  },

  akte: {
    // Frag den Rat liest den ganzen Vorgang: Frage zum Stadion, darunter
    // Eckdaten (Abstimmung, Betrag) und der Verlauf bis zum aktuellen Stand.
    async run({ page, goto, begin, click, type, look, scrollTo, pause }) {
      const frage = 'Was hat der Rat zum neuen Fußballstadion beschlossen?';
      const band = await echteAntworten(page, '**/api/council/ask');
      const einwilligen = async () => {
        const knopf = page.locator('button:has-text("KI nutzen, nicht merken")');
        if (await knopf.count()) { await knopf.click(); await pause(0.8); }
      };

      // Aufbau: die Frage einmal wirklich stellen. Spricht die Antwort von
      // „der Akte“ — ein Wort aus unserer Werkstatt, nicht aus dem Rat —,
      // noch einmal fragen (höchstens dreimal); gezeigt wird nur, was
      // Ratslotse wirklich geantwortet hat.
      for (let versuch = 1; ; versuch++) {
        await goto('/fragen');
        await page.waitForSelector('[data-search]');
        await einwilligen();
        await page.locator('[data-search]').fill(frage);
        await page.locator('button[aria-label="Fragen"]:not([disabled])').first().click();
        await page.waitForSelector('section[aria-label="Verlauf des Vorgangs"]', { timeout: 180_000 });
        const text = await page.locator('body').innerText();
        if (!/\bAkte\b/.test(text) || versuch >= 3) break;
        band.verwerfen();
      }
      band.wiedergeben();

      // Die Szene.
      await goto('/fragen');
      await page.waitForSelector('[data-search]');
      await einwilligen();
      await pause(1.0);
      await begin();
      await type('[data-search]', frage);
      await page.waitForSelector('button[aria-label="Fragen"]:not([disabled])');
      await pause(0.4);
      await click('button[aria-label="Fragen"]');
      await page.waitForSelector('section[aria-label="Eckdaten"]', { timeout: 30_000 });
      await pause(2.2);   // „Kurz gesagt“ lesen lassen
      const eck = page.locator('section[aria-label="Eckdaten"]');
      // Oben bündig unter die Kopfzeile, nicht mittig: Die Eckdaten sollen
      // ganz zu sehen sein.
      await eck.evaluate((el) => {
        el.style.scrollMarginTop = '76px';
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      await pause(1.3);
      await look(eck.locator('text=Mio. €').first());
      await pause(1.8);
      const stand = page.locator('section[aria-label="Verlauf des Vorgangs"] >> text=Aktueller Stand');
      await scrollTo(stand, { settle: 1.4 });
      await look(stand);
      await pause(3.0);
    },
  },
};
