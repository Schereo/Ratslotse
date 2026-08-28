// Rechnet die Skalen-Regeln des Grafik-Baukastens nach (`components/grafik/skala.ts`).
//
// WARUM ein eigener Lauf und kein `tsc`: Beide Fehler, die diese Probe fängt,
// waren typkorrekt. `[0, max]` compiliert einwandfrei — die Kurve wurde
// gezeichnet, nur eben außerhalb ihres eigenen Bildes, und die Achse zeigte
// fünfmal dieselbe Zahl. Das sieht man auf einem Bildschirm oder gar nicht.
//
// Die Probe importiert die ECHTEN Funktionen (Node liest `.ts` direkt), damit
// eine Änderung im Modul hier auffliegt und nicht an einer Kopie vorbeiläuft.

import { achsenStellen, ySpanne } from "../components/grafik/skala.ts";

let fehler = 0;
const pruefe = (name, bedingung, gesehen) => {
  if (bedingung) return;
  console.error(`  FEHLER  ${name}\n          gesehen: ${gesehen}`);
  fehler += 1;
};

// --------------------------------------------------------------------------
// (a) Die Spanne muss jeden Wert der Reihe enthalten — aus jeder Richtung.
// --------------------------------------------------------------------------
const REIHEN = [
  ["Schulden (alle positiv, groß)", [285.4, 301.2, 318.9, 330.1]],
  ["BBGO (alle negativ)", [-2.65, -5.41, -5.02, -5.55, -6.01, -10.13, -10.39]],
  ["AWB (positiv, unter 1 Mio.)", [0.35, 0.54, 0.62, 0.71]],
  ["gemischt", [-1.2, 0.8, 2.4]],
  ["eine einzige Zahl", [42.0]],
];

for (const [name, werte] of REIHEN) {
  const [von, bis] = ySpanne(werte, true);
  pruefe(`${name}: jeder Wert liegt in der Spanne`,
    werte.every((w) => w >= von && w <= bis), `[${von}, ${bis}]`);
  pruefe(`${name}: die Spanne läuft aufwärts`, von <= bis, `[${von}, ${bis}]`);
  pruefe(`${name}: die Null ist im Bild`, von <= 0 && bis >= 0, `[${von}, ${bis}]`);
}

// Ohne `nullbasis` ist die Null NICHT erzwungen — sonst verlöre jede
// Kennzahl-Kurve, die weit über null schwankt, ihre ganze Auflösung.
{
  const [von, bis] = ySpanne([98.2, 99.1, 98.7], false);
  pruefe("ohne nullbasis wird die Null nicht erzwungen", von > 90, `[${von}, ${bis}]`);
}

// --------------------------------------------------------------------------
// (b) Zwei Gitterlinien dürfen nie dieselbe Beschriftung tragen.
// --------------------------------------------------------------------------
const de = (v, n) => v.toFixed(n).replace(".", ",");
const RASTER = [
  ["Millionen-Raster bleibt ohne Nachkomma", [0, 100, 200, 300], 0],
  ["Zehner-Raster bleibt ohne Nachkomma", [0, 10, 20, 30], 0],
  ["Einer-Raster bleibt ohne Nachkomma", [-12, -10, -8, -6], 0],
  ["Fünftel-Raster bekommt eine Stelle", [0, 0.2, 0.4, 0.6, 0.8], 1],
  ["Hundertstel-Raster bekommt zwei", [0, 0.05, 0.1, 0.15], 2],
  ["Tausendstel wird bei zwei Stellen gekappt", [0, 0.002, 0.004], 2],
];

for (const [name, gitter, erwartet] of RASTER) {
  const stellen = achsenStellen(gitter);
  pruefe(name, stellen === erwartet, `${stellen} statt ${erwartet}`);
  const text = gitter.map((v) => de(v, stellen));
  // Beim gekappten Tausendstel-Raster ist die Dublette unvermeidbar — dort
  // ist die Beschriftung ehrlich zu grob, nicht falsch.
  if (erwartet < 2 || gitter[1] >= 0.01) {
    pruefe(`${name}: keine doppelte Beschriftung`,
      new Set(text).size === text.length, text.join(" "));
  }
}

pruefe("ein einzelner Gitterwert bricht nicht", achsenStellen([5]) === 0, "");

if (fehler) {
  console.error(`\n${fehler} Skalen-Probe(n) fehlgeschlagen.`);
  process.exit(1);
}
console.log(`Skalen-Proben in Ordnung (${REIHEN.length} Reihen, ${RASTER.length} Raster).`);
