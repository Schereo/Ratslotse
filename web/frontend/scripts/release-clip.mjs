#!/usr/bin/env node
// Einen Highlight-Clip für „Neu bei Ratslotse“ aufnehmen — nach Drehbuch.
//
// Das Drehbuch liegt in release-clips/<version>.mjs (eine Datei je Ausgabe),
// der Schnitt danach in scripts/release_clips.py (Repo-Wurzel). Dieses Skript
// macht nur die Aufnahme: Chrome fahren, den Zeiger sichtbar machen, die
// Klicks des Drehbuchs ausführen und dabei festhalten, WANN und WO geklickt
// wurde — daraus macht highlight_clip.py den Zoom. Nichts wird geraten.
//
//   node scripts/release-clip.mjs 2.2.0 teilen --out DIR   → eine JSON-Zeile auf stdout
//   node scripts/release-clip.mjs 2.2.0 --list
//
// Aufgenommen wird über Chromes Screencast (CDP), Bild für Bild mit
// Zeitstempel, nicht über Playwrights recordVideo: Dessen Zeitachse ist die
// Bildzahl durch 25, und bei einem Seitenwechsel fehlten darin gemessen
// 0,5–0,9 s (08.09.2026) — der Zoom saß dann neben dem Klick. Die
// Screencast-Bilder tragen die Uhrzeit des Bildwechsels, die Klicks dieselbe
// Uhr; der Schnitt legt beides übereinander. Zwischen zwei Bildern hat sich
// nichts bewegt, das letzte Bild steht bis zum nächsten.
//
// Was ein Drehbuch bekommt (`stage`):
//   page            die Playwright-Seite, für Aufbau und Routen
//   goto(path)      Seite öffnen (Basis-URL davor), Störer wegklicken
//   begin()         ab hier zählt der Clip — alles davor wird weggeschnitten
//   click(target)   Zeiger fährt sichtbar hin, verweilt, klickt; wird ein Beat
//   hover(target)   nur hinfahren
//   look(target)    hinfahren und hinsehen: Zoom-Beat ohne Klick (für alles,
//                   was schon beim Überfahren aufgeht)
//   type(target, text)  hinfahren, fokussieren, Zeichen für Zeichen tippen
//   scrollTo(target) weich dorthin blättern (ein Sprung sähe nach Schnitt aus)
//   pause(seconds)  stehen lassen (die Pointe lesen lassen)
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
// Der Screencast liefert Bilder in CSS-Pixeln, egal welcher deviceScaleFactor
// eingestellt ist — 2× wäre nur ein hochskaliertes 1× (gemessen 08.09.2026).
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

/** Der Zeiger — Playwright zeichnet keinen. Läuft als Init-Skript in der
 *  Seite und hängt an den ECHTEN Mausereignissen: Er zeigt, was wirklich
 *  passiert. Falle: Init-Skripte laufen vor dem ersten DOM-Knoten,
 *  `document.documentElement` ist dort null — deshalb der Fallback. */
const CURSOR = () => {
  const attach = (el) => {
    if (document.documentElement) document.documentElement.appendChild(el);
    else addEventListener('DOMContentLoaded', () => document.documentElement.appendChild(el), { once: true });
  };
  const style = document.createElement('style');
  // Das Drücken schrumpft den Pfeil — als Teil von `transform`, NICHT als
  // eigenes `scale`: Die Einzel-Eigenschaft wirkt vor der Verschiebung und
  // multipliziert sie mit — der Zeiger sprang beim Klick 100 px Richtung
  // Ecke (gemessen 08.09.2026).
  style.textContent = `
    #rl-cursor { position: fixed; left: 0; top: 0; z-index: 2147483647;
      pointer-events: none; width: 26px; height: 26px; display: none; }
  `;
  attach(style);
  const cursor = document.createElement('div');
  cursor.id = 'rl-cursor';
  // Ein gewöhnlicher Pfeil, kräftig umrandet — auf hellem Grund und in
  // 980 px Breite noch lesbar.
  cursor.innerHTML = `<svg viewBox="0 0 24 24" width="26" height="26"
      style="filter: drop-shadow(0 2px 5px rgba(0,0,0,.45))">
    <path d="M5 2.5 L5 19.2 L9.3 15.2 L12.1 21.6 L15.2 20.2 L12.4 14 L18.3 13.6 Z"
          fill="#111827" stroke="#ffffff" stroke-width="1.7" stroke-linejoin="round"/>
  </svg>`;
  attach(cursor);
  let x = 0, y = 0, down = false;
  const render = () => {
    cursor.style.transform = `translate(${x - 2}px, ${y - 2}px) scale(${down ? 0.82 : 1})`;
  };
  addEventListener('mousemove', (e) => {
    cursor.style.display = 'block';
    x = e.clientX; y = e.clientY; render();
  }, true);
  addEventListener('mousedown', () => { down = true; render(); }, true);
  addEventListener('mouseup', () => { down = false; render(); }, true);
};

const viewport = storyboard.viewport ?? DEFAULT_VIEWPORT;
const browser = await chromium.launch({ channel: 'chrome' });
const ctx = await browser.newContext({
  viewport, deviceScaleFactor: 1, colorScheme: 'light',
  locale: 'de-DE', timezoneId: 'Europe/Berlin',
  permissions: ['clipboard-write', 'clipboard-read'],
});
// Ohne Web Share API nimmt ein Teilen-Knopf den Zwischenablage-Weg — und DER
// ist sichtbar („Link kopiert.“). Mit ihr öffnet Chrome das Blatt des
// Betriebssystems, das in der Aufnahme nicht vorkommt: Der Klick sähe aus wie nichts.
await ctx.addInitScript(() => { try { delete Navigator.prototype.share; } catch { /* egal */ } });
await ctx.addInitScript(CURSOR);
const page = await ctx.newPage();
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

// ---- Aufnahme: Screencast mit Zeitstempeln ---------------------------------
const clock = () => Date.now() / 1000;   // dieselbe Uhr wie metadata.timestamp
const frames = [];
const cdp = await ctx.newCDPSession(page);
cdp.on('Page.screencastFrame', ({ data, metadata, sessionId }) => {
  const f = path.join(FRAMES, `f${String(frames.length).padStart(5, '0')}.jpg`);
  writeFileSync(f, Buffer.from(data, 'base64'));
  frames.push({ t: metadata.timestamp, file: f });
  cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {});
});
await cdp.send('Page.startScreencast', {
  format: 'jpeg', quality: 92, maxWidth: viewport.width, maxHeight: viewport.height, everyNthFrame: 1,
});

const marks = { begin: null, beats: [], navigations: [] };
// Jede Navigation mit Zeitstempel — im JSON sichtbar, damit sich ein Clip,
// in dem „die Seite zu früh wechselt“, ohne Raten erklären lässt.
page.on('framenavigated', (frame) => {
  if (frame === page.mainFrame()) marks.navigations.push({ t: clock(), url: frame.url() });
});
let cursor = null;   // wo der Zeiger gerade steht (CSS-Pixel), null = noch nicht gezeigt

const locate = (target) => (typeof target === 'string' ? page.locator(target).first() : target);
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
async function center(target) {
  const l = locate(target);
  await l.scrollIntoViewIfNeeded();
  const b = await l.boundingBox();
  if (!b) throw new Error(`Ziel nicht sichtbar: ${typeof target === 'string' ? target : '(Locator)'}`);
  return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
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
    // Der Zeiger erscheint erst mit der ersten Fahrt — ein Aufbau-Klick
    // davor (Playwright) darf keinen Sprung hinterlassen.
    cursor = null;
    return page.evaluate(() => { const c = document.getElementById('rl-cursor'); if (c) c.style.display = 'none'; });
  },
  pause: (seconds) => page.waitForTimeout(seconds * 1000),
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
    if (!cursor) {
      cursor = { x: clamp(z.x + from[0], 8, viewport.width - 8), y: clamp(z.y + from[1], 8, viewport.height - 8) };
      await page.mouse.move(cursor.x, cursor.y);
      await page.waitForTimeout(500);
    }
    const distance = Math.hypot(z.x - cursor.x, z.y - cursor.y);
    await page.mouse.move(z.x, z.y, { steps: clamp(Math.round(distance / 9), 18, 60) });
    cursor = z;
    return z;
  },
  /** Hinfahren, kurz verweilen (Hover-Zustand zeigen), klicken — ein Beat. */
  async click(target, { from, hover = 0.85 } = {}) {
    const z = await stage.hover(target, { from });
    await page.waitForTimeout(hover * 1000);
    marks.beats.push({ t: clock(), x: z.x, y: z.y, tap: true });
    await page.mouse.down();
    await page.waitForTimeout(140);
    await page.mouse.up();
  },
  /** Hinfahren und hinsehen — der Zoom kommt, die Tipp-Markierung nicht. */
  async look(target, { from, hover = 0.4 } = {}) {
    const z = await stage.hover(target, { from });
    await page.waitForTimeout(hover * 1000);
    marks.beats.push({ t: clock(), x: z.x, y: z.y, tap: false });
  },
  async type(target, text, { delay = 35 } = {}) {
    await stage.hover(target);
    await locate(target).focus();
    await page.keyboard.type(text, { delay });
  },
};

try {
  await stage.login(storyboard.account);
  await storyboard.run(stage);
} catch (e) {
  // Das letzte Bild hilft beim Suchen: Wo stand die Seite, als es hakte?
  await page.screenshot({ path: path.join(OUT, 'fehler.png') }).catch(() => {});
  await ctx.close().catch(() => {});
  await browser.close().catch(() => {});
  fail(`Drehbuch „${name}“ gescheitert: ${e?.stack ?? e}`);
}
const end = clock();
await page.waitForTimeout(300);   // späte Bilder noch einsammeln
await cdp.send('Page.stopScreencast').catch(() => {});
await ctx.close();
await browser.close();

const result = {
  width: viewport.width,
  height: viewport.height,
  begin: marks.begin,
  end,
  beats: marks.beats.map((b) => ({ t: b.t, x: Math.round(b.x), y: Math.round(b.y), tap: b.tap })),
  navigations: marks.navigations,
  frames,
};
const manifest = path.join(OUT, 'aufnahme.json');
writeFileSync(manifest, JSON.stringify(result));
console.log(JSON.stringify({ manifest, frames: frames.length, beats: result.beats.length }));
