// Drehbücher für die Clips von Ratslotse 3.0.0 — eines je Highlight aus
// kern/releases.py. Aufnahme: python scripts/release_clips.py web 3.0.0
//
// Ein Drehbuch bekommt die Bühne (`stage`) und spielt darauf eine kurze
// Szene: erst Aufbau (Seite öffnen, Zustand herstellen), dann `begin()`,
// dann die Klicks. Alles vor `begin()` wird weggeschnitten; jeder `click()`
// wird zum Zoom-Beat. Was `stage` kann, steht in scripts/release-clip.mjs.
//
// **Wie die Clips erklären** (Tims Wünsche 07.10.2026, Remotion-Schnitt in
// web/clips/): Jeder Clip zeigt zuerst den WEG dorthin — er startet auf einer
// bekannten Seite (meist „Heute“) im Schreibtisch-Layout mit Seitenleiste —,
// dann höchstens fünf Schritte, jeder mit einem kurzen Satz in Du-Form
// (`say()`), ohne Werkstattwörter. Je Feature EIN Nutzen und EIN Aha:
//   lotti   — Nutzen „Du verstehst etwas nicht? Frag Lotti, auf jeder Seite.“
//             Aha: eigene Frage → Antwort mit den echten Zahlen; Wort markieren → Erklärung.
//   viertel — Nutzen „Was sich vor deiner Haustür tut.“
//             Aha: der eigene Stadtteil öffnet sich direkt, Vorhaben mit Stand + Beschlüssen.
//   ideen   — Nutzen „Gute Ideen anderer Räte — und ob Oldenburg sie schon hat.“
//             Aha: welche Stadt wann was beschlossen hat + der Stand in Oldenburg mit Belegen.
//   akte    — Nutzen „Antworten mit dem ganzen Vorgang.“
//             Aha: unter der Antwort Eckdaten und Verlauf bis zum aktuellen Stand.
// `titel`, `untertitel`, `weg` (Browser), `app` (App), `farbe`, `lotti` stehen
// im Drehbuch und gehen ins Intro und Outro.
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
    // Lotti erklärt dir jede Seite. Beschluss: Bebauungsplan 837, Rat
    // 31.08.2026 — „mehrheitlich bei 16 Gegenstimmen und einer Enthaltung“.
    vorwaermen: ['/council/decision?id=21966'],
    viewport: { width: 1280, height: 800 },
    titel: 'Lotti erklärt dir jede Seite',
    untertitel: 'Frag einfach, was du nicht verstehst',
    weg: ['Jede Seite', 'Lotti unten rechts'],
    app: ['Jede Seite', 'Lotti unten rechts'],
    farbe: 'signal',
    lotti: 'standbild-erklaert.png',
    titelbild_lotti: 'standbild-hebt-hand.png',
    async run({ page, goto, begin, click, type, markText, pause, say, lupe, ohne }) {
      const ziel = '/council/decision?id=21966';
      const frage = 'Wie viele haben dagegen gestimmt?';
      const wort = 'Öffentlichkeitsbeteiligung';
      const band = await echteAntworten(page, '**/api/council/explain**');

      // Aufbau: beide Fragen einmal wirklich stellen.
      await goto(ziel);
      await page.locator('button[aria-label="Lotti fragen"]:visible').first().click();
      const einwilligen = page.locator('button:has-text("KI nutzen, nicht merken")');
      if (await einwilligen.count()) await einwilligen.click();
      await page.locator('[aria-label="Frage an Lotti"]').fill(frage);
      await lottiAntwort(page, () => page.locator('button[aria-label="Fragen"]').last().click());
      await page.locator('button[aria-label="Lotti schließen"]:visible').first().click();
      await pause(0.5);
      await markText('text=' + wort, wort);
      await lottiAntwort(page, () => page.locator('button[aria-label^="Lotti fragen: Was bedeutet"]').click());
      if (band.anzahl < 2) throw new Error(`Nur ${band.anzahl} Antwort(en) aufgehoben`);
      band.wiedergeben();

      // Die Szene — mit leerem Fenster (Lotti hebt den Verlauf je Tab auf).
      await page.evaluate(() => {
        sessionStorage.removeItem('ratslotse:lotti-verlauf');
        sessionStorage.removeItem('ratslotse:lotti-gespraech');
      });
      await goto(ziel);
      await page.waitForSelector('button[aria-label="Lotti fragen"]');
      await page.mouse.click(5, 300);   // eine verbliebene Markierung aufheben
      await pause(1.0);
      await begin();
      say('Auf jeder Seite unten rechts: Lotti');
      await pause(1.2);
      await click(page.locator('button[aria-label="Lotti fragen"]:visible').first());
      await page.waitForSelector('[aria-label="Frage an Lotti"]');
      await pause(0.5);
      say('Frag in eigenen Worten, was du wissen willst');
      await type('[aria-label="Frage an Lotti"]', frage);
      await pause(0.3);
      await lottiAntwort(page, () => click(page.locator('button[aria-label="Fragen"]').last()));
      say('Lotti liest die Seite mit und antwortet mit den Zahlen aus dem Protokoll');
      await lupe(page.locator('#lotti-fenster div.space-y-2').last(), { dauer: 3.6 });
      await click(page.locator('button[aria-label="Lotti schließen"]:visible').first());
      await pause(0.6);
      say('Ein Wort unklar? Markieren und „Lotti fragen“');
      await markText('text=' + wort, wort);
      await page.waitForSelector('button[aria-label^="Lotti fragen: Was bedeutet"]');
      await pause(0.6);
      await lottiAntwort(page, () => click('button[aria-label^="Lotti fragen: Was bedeutet"]'));
      say('… und Lotti erklärt es in einfachen Worten');
      await pause(0.8);   // das Fenster geht erst wieder auf
      await lupe(page.locator('#lotti-fenster div.space-y-2').last(), { dauer: 4.0 });
    },
  },

  viertel: {
    // Mein Viertel — mit dem WEG dorthin (Tims Befund 07.10.2026: Die Clips
    // fingen mittendrin an, man sah nicht, wie man hinkommt). Start auf
    // „Heute“ im Schreibtisch-Layout, die Seitenleiste ist im Bild.
    // Kita Eßkamp: im Bau, fertig zum Kindergartenjahr 2026/2027.
    vorwaermen: ['/dashboard', '/karte', '/karte?ort=fliegerhorst'],
    viewport: { width: 1280, height: 800 },
    titel: 'Mein Viertel',
    untertitel: 'Was sich vor deiner Haustür tut',
    weg: ['Seitenleiste', 'Mein Viertel'],
    app: ['Mehr', 'Mein Viertel'],
    farbe: 'gruen',
    titelbild_lotti: 'standbild-zeigt-links.png',
    async run({ page, goto, begin, click, look, scrollTo, pause, say, lupe, ohne }) {
      // Das Probekonto hat Fliegerhorst gewählt (Themen) — „Mein Viertel“
      // öffnet deshalb gleich den eigenen Stadtteil.
      await goto('/dashboard');
      await page.waitForSelector('nav a:has-text("Mein Viertel")');
      await pause(1.2);
      await begin();
      say('Mein Viertel findest du in der Seitenleiste');
      await pause(1.0);
      await click(page.locator('nav a', { hasText: 'Mein Viertel' }).first());
      await ohne(async () => {
        await page.waitForSelector('text=Vorhaben aus den Beschlüssen');
        await page.waitForSelector('.leaflet-interactive');
        await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
      });
      say('Dein Stadtteil öffnet sich direkt — alle Vorhaben auf Karte und Liste');
      await pause(1.6);
      await look(page.locator('h1, h2', { hasText: 'Fliegerhorst' }).first());
      await pause(1.4);
      const vorhaben = page.locator('a, button', { hasText: 'Neue Grundschule und Dreifeldhalle' }).first();
      say('Ein Vorhaben öffnen: Stand, Zeitplan und die Beschlüsse dazu');
      await click(vorhaben);
      await ohne(async () => {
        await page.waitForURL(/v=\d+/);
        await page.waitForSelector('ol[aria-label="Stand des Vorhabens"]:visible');
      });
      await pause(0.8);
      // Titel, Beschreibung und Stufenleiste — nicht die Beschlussliste
      // darunter, sonst wird die Lupe kleiner als das Original.
      await lupe([
        page.locator(':is(h1,h2,h3):visible', { hasText: 'Neue Grundschule und Dreifeldhalle' }).first(),
        page.locator('ol[aria-label="Stand des Vorhabens"]:visible').first(),
      ], { dauer: 3.6 });
      const beschluesse = page.locator('text=/\\d Beschlüsse?/').first();
      await beschluesse.waitFor();
      await scrollTo(beschluesse, { settle: 1.4 });
      await pause(1.6);
      say('Über „Stadt zeigen“ kommst du in jedes andere Viertel');
      await click(page.locator('button, a', { hasText: 'Stadt zeigen' }).first());
      await ohne(() => page.waitForSelector('input[aria-label="Straße oder Stadtteil"]'));
      await pause(2.4);
    },
  },

  ideen: {
    // Ideen aus anderen Städten: Analyse → Reiter → „Gerade in Bewegung“ →
    // Hitzeaktionsplan → Stand in Oldenburg → Zeitleiste durch die Räte.
    vorwaermen: ['/dashboard', '/council?tab=analysis', '/council/ideen', '/council/ideen/bewegung?id=1'],
    viewport: { width: 1280, height: 800 },
    titel: 'Ideen aus anderen Städten',
    untertitel: 'Was andere Räte schon beschlossen haben',
    weg: ['Seitenleiste', 'Analyse', 'Ideen aus anderen Städten'],
    app: ['Mehr', 'Ideen aus anderen Städten'],
    farbe: 'primary',
    lotti: 'standbild-hat-idee.png',
    titelbild_lotti: 'standbild-zeigt-links.png',
    async run({ page, goto, begin, click, look, scrollTo, pause, say, lupe, ohne }) {
      await goto('/dashboard');
      await page.waitForSelector('nav a:has-text("Analyse")');
      await pause(1.2);
      await begin();
      say('Ideen aus anderen Städten findest du in der Analyse');
      await pause(1.0);
      await click(page.locator('nav a', { hasText: 'Analyse' }).first());
      const reiter = page.locator('button', { hasText: 'Ideen aus anderen Städten' }).first();
      await ohne(() => reiter.waitFor());
      await pause(0.9);
      await click(reiter);
      await ohne(async () => {
        await page.waitForSelector('text=Gerade in Bewegung');
        await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
      });
      await pause(1.0);
      say('Ideen, die gerade in mehreren Räten laufen');
      await look(page.locator(':text("Gerade in Bewegung"):visible').first());
      await pause(1.6);
      say('Eine Idee öffnen: Gibt es das in Oldenburg schon?');
      await click(page.locator('a', { hasText: 'Hitzeaktionsplan aufstellen' }).first());
      await ohne(async () => {
        await page.waitForSelector(':text("Und in Oldenburg?"):visible');
        await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
      });
      await pause(1.2);
      // Überschrift, Urteil und der erste Satz — der ganze Abschnitt wäre zu
      // hoch für eine Lupe, die wirklich vergrößert.
      const urteil = page.locator(':text("Teilweise vorhanden"):visible').first();
      await lupe([
        page.locator(':text("Und in Oldenburg?"):visible').first(),
        urteil,
        urteil.locator('xpath=following::p[1]'),
      ], { dauer: 3.8 });
      say('Die Zeitleiste: welche Stadt wann was beschlossen hat');
      await scrollTo(page.locator('#buehne-titel:visible').first(), { settle: 1.4 });
      await look(page.locator('[aria-label^="Potsdam:"]:visible').first());
      await pause(1.4);
      await look(page.locator('[aria-label^="Magdeburg:"]:visible').first());
      await pause(2.4);
    },
  },

  akte: {
    // Frag den Rat liest den ganzen Vorgang: Frage zum Stadion, darunter
    // Eckdaten (Abstimmung, Betrag) und der Verlauf bis zum aktuellen Stand.
    vorwaermen: ['/dashboard', '/fragen'],
    viewport: { width: 1280, height: 800 },
    titel: 'Frag den Rat',
    untertitel: 'Antworten mit dem ganzen Vorgang',
    weg: ['Seitenleiste', 'Fragen'],
    app: ['Fragen'],
    farbe: 'primary',
    lotti: 'standbild-liest.png',
    titelbild_lotti: 'standbild-zeigt-links.png',
    async run({ page, goto, begin, click, type, look, scrollTo, pause, say, lupe, ohne }) {
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

      // Die Szene — vom Start aus über die Seitenleiste.
      await goto('/dashboard');
      await page.waitForSelector('nav a:has-text("Fragen")');
      await pause(1.2);
      await begin();
      say('Unter „Fragen“ stellst du deine Frage an den Rat');
      await pause(1.0);
      await click(page.locator('nav a', { hasText: 'Fragen' }).first());
      await ohne(() => page.waitForSelector('[data-search]'));
      await einwilligen();
      await pause(0.6);
      say('Frag nach einem Vorgang — zum Beispiel dem neuen Stadion');
      await type('[data-search]', frage);
      await page.waitForSelector('button[aria-label="Fragen"]:not([disabled])');
      await pause(0.4);
      await click('button[aria-label="Fragen"]');
      await ohne(() => page.waitForSelector('section[aria-label="Eckdaten"]', { timeout: 30_000 }));
      say('Die Antwort fasst den ganzen Vorgang zusammen');
      await pause(0.6);
      // Der innerste Block mit „Kurz gesagt“ — nicht die ganze Antwort.
      await lupe(page.locator(':is(p,div,li):visible', { hasText: 'Kurz gesagt' }).last(), { dauer: 3.4 });
      const eck = page.locator('section[aria-label="Eckdaten"]');
      await eck.evaluate((el) => {
        el.style.scrollMarginTop = '76px';
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      say('Darunter die Eckdaten: Abstimmung, Betrag, Stand');
      await pause(1.3);
      await lupe(eck, { dauer: 3.4 });
      const stand = page.locator('section[aria-label="Verlauf des Vorgangs"] >> text=Aktueller Stand');
      say('… und der Verlauf bis zum aktuellen Stand');
      await scrollTo(stand, { settle: 1.4 });
      await lupe(stand.locator('xpath=..'), { dauer: 3.6 });
    },
  },
};
