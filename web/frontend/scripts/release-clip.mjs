#!/usr/bin/env node
// Einen Highlight-Clip für „Neu bei Ratslotse“ aufnehmen — nach Drehbuch.
//
// Das Drehbuch liegt in release-clips/<version>.mjs (eine Datei je Ausgabe),
// der Schnitt danach in scripts/release_clips.py (Repo-Wurzel). Dieses Skript
// macht nur die Aufnahme: Chrome fahren, die Klicks des Drehbuchs ausführen
// und dabei festhalten, WANN und WO geklickt wurde und wie der Zeiger fuhr —
// daraus macht der Schnitt Zoom, Spotlight und Zeiger. Nichts wird geraten.
//
//   node scripts/release-clip.mjs 2.2.0 teilen --out DIR   → eine JSON-Zeile auf stdout
//   node scripts/release-clip.mjs 2.2.0 --list
//
// Aufgenommen wird über Chromes Screencast (CDP), jedes Bild mit dem
// Zeitstempel, zu dem Chrome es gemalt hat — nicht über Playwrights
// recordVideo: Dessen Zeitachse ist die Bildzahl durch 25, und bei einem
// Seitenwechsel fehlten darin gemessen 0,5–0,9 s (08.09.2026) — der Zoom saß
// dann neben dem Klick. Die Bilder tragen dieselbe Uhr wie die Klicks; der
// Schnitt legt beides übereinander. Chrome schickt nur, wenn sich etwas
// bewegt: Das letzte Bild steht bis zum nächsten.
//
// Der Zeiger ist NICHT Teil der Seite. Bis 11/2026 zeichnete ihn ein
// Init-Skript in die Seite, und die Aufnahme erwischte nur einzelne
// Stellungen — Tims Befund zur 3.0.0: „hakelig“. Jetzt schreibt der Recorder
// die Bahn mit (Stützpunkte samt Zeit, dazu jeder Druck), und der
// Remotion-Schnitt zeichnet den Zeiger in jedes Bild neu, auf derselben Kurve.
// Die echte Maus fährt dieselbe Bahn mit, damit Hover-Zustände dort
// entstehen, wo der gezeichnete Zeiger steht.
//
// Was ein Drehbuch bekommt (`stage`):
//   page            die Playwright-Seite, für Aufbau und Routen
//   goto(path)      Seite öffnen (Basis-URL davor), Störer wegklicken
//   begin()         ab hier zählt der Clip — alles davor wird weggeschnitten
//   click(target)   Zeiger fährt sichtbar hin, verweilt, klickt; wird ein Beat
//   hover(target)   nur hinfahren
//   look(target)    hinfahren und hinsehen: Zoom-Beat ohne Klick (für alles,
//                   was schon beim Überfahren aufgeht)
//   markText(target, text)  ein Wort im Ziel mit gedrückter Maus markieren
//   type(target, text)  hinfahren, fokussieren, Zeichen für Zeichen tippen
//   scrollTo(target) weich dorthin blättern (ein Sprung sähe nach Schnitt aus)
//   pause(seconds)  stehen lassen (die Pointe lesen lassen)
//   say(text)       ab jetzt steht dieser Schritt als Untertitel im Clip
//   lupe(target, {dauer})  die Stelle vergrößert danebenstellen (Aha-Moment,
//                   im Remotion-Schnitt), so lange stehen lassen; `target`
//                   darf eine Liste sein (gemeinsamer Umriss)
//   ohne(fn)        was `fn` abwartet (Laden einer Seite), fällt aus dem Clip
// Im Drehbuch selbst (neben `run`): `vorwaermen: [pfade]` ruft diese Seiten vor
// der Aufnahme einmal auf (der Dev-Server übersetzt sonst mitten im Clip).
// `mobil: true` nimmt am Telefon auf (390×844, Touch, doppelte Auflösung) —
// für den Spieler am Telefon, in dem ein 16:9-Clip vom Schreibtisch winzig
// wird (gemessen 07.10.2026: Untertitel ~11 px). Statt des Zeigers zeigt der
// Schnitt dort nur die Tipp-Welle; `click` tippt, ohne hinzufahren.
//                   (nur im Remotion-Schnitt, `release_clips.py web --remotion`)
// `target` ist ein Selektor oder ein Locator.
import { chromium } from 'playwright';
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '..');
// 980 px breit: das schmale Fenster, in dem die Karte alles lesbar zeigt. Der
// Schnitt (release_clips.py) nimmt davon die oberen 16:9 — bei dieser Breite
// zeigt die App unten die Tab-Leiste, und die gehört nicht in den Clip.
// Dieselbe Bühne für alle Browser-Clips einer Ausgabe: Die Karte setzt ihr
// Seitenverhältnis aus dem Medium; springt es beim Blättern, wackelt sie.
const DEFAULT_VIEWPORT = { width: 980, height: 620 };
// Aufgenommen wird in doppelter Pixeldichte, am Telefon wie am Schreibtisch.
// Der Screencast liefert Bilder in CSS-Pixeln, solange die Pixeldichte nur
// EMULIERT ist (deviceScaleFactor, maxWidth, Geräte-Override — gemessen
// 08.09. und 11.10.2026; der Clip war „relativ unscharf"). Deshalb lief die
// Aufnahme bis 11/2026 über eine `page.screenshot`-Schleife in 2× — mit 12–17
// unregelmäßigen Bildern je Sekunde, Tims Befund zur 3.0.0: „zuckt“.
// Was beides löst (gemessen 08.11.2026): Playwrights Headless-Shell mit
// ECHTER Pixeldichte (`--force-device-scale-factor=2`) und einer
// Fenstergröße statt eines emulierten Viewports. Dann liefert der Screencast
// 2× bei rund 60 Bildern je Sekunde. Im installierten Chrome gilt die
// Fenstergröße samt Rahmen — die Seite wäre 87 px niedriger als bestellt.
const PIXELDICHTE = 2;
const MOBIL_VIEWPORT = { width: 390, height: 844 };
const DEFAULT_ACCOUNT = 'nutzerin@example.org';
const PASSWORD = 'password123';   // scripts/saat_konten.py

function fail(message) {
  console.error(message);
  process.exit(2);
}

const argv = process.argv.slice(2);
const flag = (name) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : undefined; };
const version = argv[0];
if (!version) fail('Aufruf: release-clip.mjs <version> <name> --out DIR  |  <version> --list');
const file = path.join(FRONTEND, 'release-clips', `${version}.mjs`);
const storyboards = (await import(pathToFileURL(file).href)).default;
if (argv.includes('--list')) {
  console.log(JSON.stringify(Object.keys(storyboards)));
  process.exit(0);
}
const name = argv[1];
const storyboard = storyboards[name];
if (!storyboard) fail(`Kein Drehbuch „${name}“ in ${file}. Vorhanden: ${Object.keys(storyboards).join(', ')}`);
const OUT = flag('--out') ?? mkdtempSync(path.join(tmpdir(), 'release-clip-'));
const BASE = flag('--base') ?? process.env.RELEASE_CLIP_BASE ?? 'http://localhost:3000';
const FRAMES = path.join(OUT, 'frames');
mkdirSync(FRAMES, { recursive: true });

const MOBIL = Boolean(storyboard.mobil);
const viewport = storyboard.viewport ?? (MOBIL ? MOBIL_VIEWPORT : DEFAULT_VIEWPORT);
// Die Headless-Shell (kein `channel`), echte Pixeldichte, die Fenstergröße
// IST der Viewport — s. PIXELDICHTE. Ohne emulierten Viewport kennt
// Playwright kein `isMobile`; am Telefon zählen Breite und Touch (die Seite
// fragt `pointer: coarse`, und die meldet die Shell mit `hasTouch`).
const browser = await chromium.launch({
  args: [`--force-device-scale-factor=${PIXELDICHTE}`, `--window-size=${viewport.width},${viewport.height}`],
});
const ctx = await browser.newContext({
  viewport: null, hasTouch: MOBIL, colorScheme: 'light',
  locale: 'de-DE', timezoneId: 'Europe/Berlin',
  permissions: ['clipboard-write', 'clipboard-read'],
});
// Ohne Web Share API nimmt ein Teilen-Knopf den Zwischenablage-Weg — und DER
// ist sichtbar („Link kopiert.“). Mit ihr öffnet Chrome das Blatt des
// Betriebssystems, das in der Aufnahme nicht vorkommt: Der Klick sähe aus wie nichts.
await ctx.addInitScript(() => { try { delete Navigator.prototype.share; } catch { /* egal */ } });
const page = await ctx.newPage();
const groesse = await page.evaluate(() => [innerWidth, innerHeight, devicePixelRatio]);
if (groesse[0] !== viewport.width || groesse[1] !== viewport.height || groesse[2] !== PIXELDICHTE) {
  fail(`Fenster ${groesse[0]}×${groesse[1]} @${groesse[2]}x statt ${viewport.width}×${viewport.height} @${PIXELDICHTE}x`);
}
// Die Karte „Neu bei Ratslotse“ selbst hat in ihren Clips nichts verloren.
await page.route('**/api/news', (route) => (
  route.request().method() === 'GET'
    ? route.fulfill({ contentType: 'application/json',
        body: JSON.stringify({ releases: [], older_count: 0, seen_version: null }) })
    : route.continue()
));
// Und die Abzeichen-Feier auch nicht: Die erste Frage des Probekontos
// verdient „Erste Frage“, und die Karte legte sich quer über die Antwort.
await page.route('**/api/badges', async (route) => {
  if (route.request().method() !== 'GET') return route.continue();
  const r = await route.fetch();
  await route.fulfill({ response: r, json: { ...(await r.json()), newly_earned: [] } });
});

// ---- Aufnahme: Screencast mit Zeitstempeln ----------------------------------
// `metadata.timestamp` ist Wanduhr-Zeit in Sekunden wie `clock()` — gemessen
// 08.11.2026: Ein Bild kommt 2–10 ms nach seinem Zeitstempel an.
const clock = () => Date.now() / 1000;
const frames = [];
const cdp = await ctx.newCDPSession(page);
cdp.on('Page.screencastFrame', ({ data, metadata, sessionId }) => {
  // Erst quittieren, dann schreiben: Chrome schickt das nächste Bild erst
  // nach der Quittung.
  cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {});
  const f = path.join(FRAMES, `f${String(frames.length).padStart(5, '0')}.jpg`);
  writeFileSync(f, Buffer.from(data, 'base64'));
  frames.push({ t: metadata.timestamp ?? clock(), file: f });
});
await cdp.send('Page.startScreencast', {
  format: 'jpeg', quality: 90, everyNthFrame: 1,
  maxWidth: viewport.width * PIXELDICHTE, maxHeight: viewport.height * PIXELDICHTE,
});

const marks = { begin: null, beats: [], navigations: [], steps: [], cuts: [], pointer: [], presses: [] };
// Jede Navigation mit Zeitstempel — im JSON sichtbar, damit sich ein Clip,
// in dem „die Seite zu früh wechselt“, ohne Raten erklären lässt.
page.on('framenavigated', (frame) => {
  if (frame === page.mainFrame()) marks.navigations.push({ t: clock(), url: frame.url() });
});
let cursor = null;   // wo der Zeiger gerade steht (CSS-Pixel), null = noch nicht gezeigt

const locate = (target) => (typeof target === 'string' ? page.locator(target).first() : target);
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

// ---- Der Zeiger: Bahn mitschreiben, echte Maus mitführen ---------------------
// `marks.pointer` sind Stützpunkte `{t, x, y}`; zwischen zweien fährt der
// Zeiger auf der Kurve `ruck` (web/clips/src/Zeiger.tsx rechnet dieselbe).
// Steht er, stehen zwei Punkte am selben Ort. Der erste Punkt ist sein
// Auftritt. `marks.presses` sind die Spannen mit gedrückter Taste.

/** Minimaler Ruck (Flash & Hogan 1985): So beschleunigt und bremst eine
 *  Hand, die zu einem Ziel greift — kein Schlingern am Anfang, kein Einrasten
 *  am Ende. */
const ruck = (p) => p * p * p * (10 - 15 * p + 6 * p * p);

/** Den Zeiger an einer Stelle auftauchen lassen (ohne Fahrt). */
async function zeige(x, y) {
  cursor = { x, y };
  marks.pointer.push({ t: clock(), x, y });
  await page.mouse.move(x, y);
}

/** Vom aktuellen Ort nach (x, y) fahren. Die Dauer wächst mit dem Weg, wie
 *  bei einer Hand: kurze Wege knapp eine halbe Sekunde, lange bis 0,9 s. */
async function fahre(x, y, { dauer } = {}) {
  const { x: x0, y: y0 } = cursor;
  const d = dauer ?? clamp(0.32 + Math.hypot(x - x0, y - y0) / 1500, 0.42, 0.9);
  const a = clock();
  marks.pointer.push({ t: a, x: x0, y: y0 });
  marks.pointer.push({ t: a + d, x, y });
  for (;;) {
    const p = Math.min(1, (clock() - a) / d);
    const e = ruck(p);
    await page.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e);
    if (p >= 1) break;
    await page.waitForTimeout(12);
  }
  cursor = { x, y };
}

async function druecke() {
  marks.presses.push({ a: clock(), b: null });
  await page.mouse.down();
}

async function loslassen() {
  await page.mouse.up();
  const offen = marks.presses[marks.presses.length - 1];
  if (offen && offen.b === null) offen.b = clock();
}
async function center(target) {
  const l = locate(target);
  await l.scrollIntoViewIfNeeded();
  const b = await l.boundingBox();
  if (!b) throw new Error(`Ziel nicht sichtbar: ${typeof target === 'string' ? target : '(Locator)'}`);
  // Der Umriss reist mit: Der Remotion-Schnitt legt das Spotlight darum,
  // statt nah heranzuzoomen (Tims Befund 07.10.2026: zu nah, kein Kontext).
  return { x: b.x + b.width / 2, y: b.y + b.height / 2, box: { x: b.x, y: b.y, w: b.width, h: b.height } };
}

/** Störer wegklicken — nur in Dialogen, damit kein „Weiter“ einer
 *  Blätter-Leiste erwischt wird (das hat am 07.09.2026 eine aufgeklappte
 *  Tagesordnung weggeräumt). */
async function dismiss() {
  for (let i = 0; i < 6; i++) {
    const b = page.locator('[role="dialog"] button', { hasText: /^(Später|Alles klar|Verstanden|Weiter|Schließen)$/ }).first();
    if (!(await b.count())) return;
    await b.click().catch(() => {});
    await page.waitForTimeout(300);
  }
}

const stage = {
  page,
  base: BASE,
  async goto(p) {
    await page.goto(BASE + p);
    // Bis die Seite ihre Daten hat — sonst beginnt ein Clip auf dem
    // Lade-Skelett. Läuft die Seite dauerhaft nach (Karte, Strom), reicht der
    // Ablauf der Frist.
    await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
    await dismiss();
  },
  async login(email = DEFAULT_ACCOUNT) {
    await page.goto(BASE + '/');
    await page.evaluate(async ({ email, password }) => {
      const r = await fetch('/api/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        credentials: 'include', body: JSON.stringify({ email, password }),
      });
      if (!r.ok) throw new Error(`Anmeldung fehlgeschlagen: ${r.status}`);
    }, { email, password: PASSWORD });
  },
  begin() {
    marks.begin = clock();
    // Was der Aufbau mit `click`/`markText` erledigt hat, ist kein Beat des
    // Clips — es läge vor dessen Anfang, und der Zoom käme aus dem Nichts.
    marks.beats.length = 0;
    marks.steps.length = 0;
    marks.cuts.length = 0;
    marks.pointer.length = 0;
    marks.presses.length = 0;
    // Der Zeiger erscheint erst mit der ersten Fahrt — ein Aufbau-Klick
    // davor (Playwright) darf keinen Sprung hinterlassen.
    cursor = null;
  },
  pause: (seconds) => page.waitForTimeout(seconds * 1000),
  /** Der Schritt, der ab jetzt als Untertitel steht. */
  say(text) { marks.steps.push({ t: clock(), text }); },
  /** Weich zum Ziel blättern — `scrollIntoViewIfNeeded` springt, und ein
   *  Sprung im Clip sieht aus wie ein Schnitt. */
  async scrollTo(target, { settle = 1.2 } = {}) {
    await locate(target).evaluate((el) => el.scrollIntoView({ behavior: 'smooth', block: 'center' }));
    await page.waitForTimeout(settle * 1000);
  },
  /** Zeiger fährt sichtbar zum Ziel. Die erste Fahrt beginnt schräg
   *  links unterhalb (`from`), spätere dort, wo er gerade steht. */
  async hover(target, { from = [-380, 160] } = {}) {
    const z = await center(target);
    if (MOBIL) return z;   // am Telefon gibt es keinen Zeiger, der hinfährt
    if (!cursor) {
      await zeige(clamp(z.x + from[0], 8, viewport.width - 8), clamp(z.y + from[1], 8, viewport.height - 8));
      await page.waitForTimeout(500);
    }
    await fahre(z.x, z.y);
    return z;
  },
  /** Hinfahren, kurz verweilen (Hover-Zustand zeigen), klicken — ein Beat. */
  async click(target, { from, hover = 0.85 } = {}) {
    const z = await stage.hover(target, { from });
    await page.waitForTimeout((MOBIL ? Math.min(hover, 0.5) : hover) * 1000);
    marks.beats.push({ t: clock(), x: z.x, y: z.y, tap: true, box: z.box });
    if (MOBIL) {
      await page.touchscreen.tap(z.x, z.y);
      return;
    }
    await druecke();
    await page.waitForTimeout(140);
    await loslassen();
  },
  /** Hinfahren und hinsehen — der Zoom kommt, die Tipp-Markierung nicht. */
  async look(target, { from, hover = 0.4 } = {}) {
    const z = await stage.hover(target, { from });
    await page.waitForTimeout(hover * 1000);
    marks.beats.push({ t: clock(), x: z.x, y: z.y, tap: false, box: z.box });
  },
  /** Die Pointe lesbar machen: Der Remotion-Schnitt stellt das Ziel
   *  vergrößert als Karte daneben, das Original bekommt das Spotlight. Ein
   *  stärkerer Zoom hätte den Zusammenhang gekostet (Tim, 07.10.2026) — die
   *  Antwort im 384-px-Fenster von Lotti war in der Karte sonst unlesbar.
   *  Der Zeiger bleibt, wo er ist. */
  async lupe(target, { dauer = 3.2 } = {}) {
    const ziele = Array.isArray(target) ? target : [target];
    await locate(ziele[0]).scrollIntoViewIfNeeded();
    const boxen = [];
    for (const z of ziele) {
      const bb = await locate(z).boundingBox();
      if (!bb) throw new Error('Lupe: Ziel nicht sichtbar');
      boxen.push(bb);
    }
    const x0 = Math.min(...boxen.map((q) => q.x)), y0 = Math.min(...boxen.map((q) => q.y));
    const x1 = Math.max(...boxen.map((q) => q.x + q.width)), y1 = Math.max(...boxen.map((q) => q.y + q.height));
    const b = { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
    marks.beats.push({ t: clock(), x: b.x + b.width / 2, y: b.y + b.height / 2, tap: false,
      lupe: dauer, box: { x: b.x, y: b.y, w: b.width, h: b.height } });
    await page.waitForTimeout(dauer * 1000);
  },
  /** Warten, ohne dass es im Clip steht: Was `fn` abwartet (eine Seite
   *  lädt, Daten kommen), schneidet der Schnitt heraus — die ersten 0,3 s
   *  bleiben, damit man die Reaktion auf den Klick sieht. Gemessen
   *  07.10.2026: bis zu drei Sekunden leere Ladeseite je Seitenwechsel. */
  async ohne(fn) {
    const a = clock();
    await fn();
    const b = clock();
    if (b - a > 0.6) marks.cuts.push({ a: a + 0.3, b });
  },
  /** Ein Wort (oder eine Wortfolge) im Ziel mit der Maus markieren: Zeiger
   *  an den Anfang, drücken, sichtbar bis zum Ende ziehen, loslassen. Ein
   *  Beat ohne Tipp am Ende der Markierung — dort erscheint, was auf eine
   *  Markierung antwortet (3.0.0: „Lotti fragen“). */
  async markText(target, text, { from } = {}) {
    const l = locate(target);
    await l.scrollIntoViewIfNeeded();
    const box = await l.evaluate((el, gesucht) => {
      const lauf = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      for (let n = lauf.nextNode(); n; n = lauf.nextNode()) {
        const i = n.textContent.indexOf(gesucht);
        if (i < 0) continue;
        const r = document.createRange();
        r.setStart(n, i);
        r.setEnd(n, i + gesucht.length);
        const rects = [...r.getClientRects()];
        const a = rects[0], z = rects[rects.length - 1];
        return { x0: a.left + 1, y0: a.top + a.height / 2, x1: z.right - 1, y1: z.top + z.height / 2 };
      }
      return null;
    }, text);
    if (!box) throw new Error(`Text nicht gefunden: ${text}`);
    if (!cursor) {
      const [dx, dy] = from ?? [-380, 160];
      await zeige(clamp(box.x0 + dx, 8, viewport.width - 8), clamp(box.y0 + dy, 8, viewport.height - 8));
      await page.waitForTimeout(500);
    }
    await fahre(box.x0, box.y0);
    await page.waitForTimeout(350);
    await druecke();
    // Beim Markieren zieht die Hand gleichmäßiger als beim Greifen.
    await fahre(box.x1, box.y1, { dauer: clamp((box.x1 - box.x0) / 260, 0.45, 1.1) });
    await loslassen();
    marks.beats.push({ t: clock(), x: (box.x0 + box.x1) / 2, y: box.y1, tap: false,
      box: { x: box.x0 - 4, y: box.y0 - 12, w: box.x1 - box.x0 + 8, h: 24 } });
  },
  async type(target, text, { delay = 35 } = {}) {
    await stage.hover(target);
    await locate(target).focus();
    await page.keyboard.type(text, { delay });
  },
};

try {
  await stage.login(storyboard.account);
  // Vorwärmen: Der Dev-Server übersetzt eine Seite erst beim ersten Aufruf —
  // mitten in der Aufnahme stand „Heute“ dann 30 s still, bis /karte fertig
  // war (07.10.2026). Jede Seite des Drehbuchs einmal vorher aufrufen.
  for (const p of storyboard.vorwaermen ?? []) {
    await page.goto(BASE + p, { timeout: 180_000 });
    await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => {});
  }
  await storyboard.run(stage);
} catch (e) {
  // Das letzte Bild hilft beim Suchen: Wo stand die Seite, als es hakte?
  await cdp.send('Page.stopScreencast').catch(() => {});
  await page.screenshot({ path: path.join(OUT, 'fehler.png') }).catch(() => {});
  await ctx.close().catch(() => {});
  await browser.close().catch(() => {});
  fail(`Drehbuch „${name}“ gescheitert: ${e?.stack ?? e}`);
}
const end = clock();
await page.waitForTimeout(300);   // späte Bilder noch einsammeln
await cdp.send('Page.stopScreencast');
await ctx.close();
await browser.close();

const result = {
  width: viewport.width,
  height: viewport.height,
  begin: marks.begin,
  end,
  beats: marks.beats.map((b) => ({ t: b.t, x: Math.round(b.x), y: Math.round(b.y), tap: b.tap, box: b.box ?? null,
    ...(b.lupe ? { lupe: b.lupe } : {}) })),
  steps: marks.steps,
  cuts: marks.cuts,
  pointer: marks.pointer,
  presses: marks.presses.map((p) => ({ a: p.a, b: p.b ?? end })),
  // Was der Remotion-Schnitt fürs Intro und Outro braucht (Titel, Weg …).
  meta: Object.fromEntries(Object.entries(storyboard)
    .filter(([k, v]) => k !== 'run' && typeof v !== 'function')),
  navigations: marks.navigations,
  frames,
};
const manifest = path.join(OUT, 'aufnahme.json');
writeFileSync(manifest, JSON.stringify(result));
console.log(JSON.stringify({ manifest, frames: frames.length, beats: result.beats.length }));
