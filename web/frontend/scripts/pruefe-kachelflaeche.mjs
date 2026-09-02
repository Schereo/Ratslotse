// Rechnet die Geometrie-Regeln der Kachelfläche nach
// (`components/grafik/kachelflaeche.ts`).
//
// WARUM ein eigener Lauf und kein `tsc`: Der Fehler, den diese Probe fängt,
// ist typkorrekt. Ein Posten von 1,8 Mio. € bekam auf 854 px Breite eine
// Kachel von 100 × 5 px — die Zahl stimmte, die Fläche stimmte, und trotzdem
// stand da ein Strich statt einer Kachel. Das sieht man auf einem Bildschirm
// oder gar nicht.
//
// Die Probe importiert die ECHTEN Funktionen (Node liest `.ts` direkt), damit
// eine Änderung am Modul hier auffliegt und nicht an einer Kopie vorbeiläuft.

import { readFileSync } from "node:fs";
import {
  beschriftet, buendelGrenze, kachelHoehe, kacheln, namenszeilen, namenszeilenStufe,
  rampenText, textstufe, traegtEinheit,
} from "../components/grafik/kachelflaeche.ts";

let fehler = 0;
const pruefe = (name, bedingung, gesehen) => {
  if (bedingung) return;
  console.error(`  FEHLER  ${name}\n          gesehen: ${gesehen}`);
  fehler += 1;
};

// Die beiden Datensätze, die die Komponente wirklich zeichnet. Erträge: die
// zehn Ertragsarten des Haushalts 2026 in Mio. € (Anlage 005) — 216 : 1
// zwischen größtem und kleinstem Posten, der harte Fall. Investitionen: die
// zwölf größten Vorhaben plus Rest-Kachel, Größenordnungen aus dem Programm.
const ERTRAEGE = [388.4, 146.8, 145.0, 26.6, 23.9, 17.0, 15.3, 14.4, 9.4, 1.8];
const INVESTITIONEN = [30, 22, 18, 14, 12, 10, 8, 7, 6, 5, 4, 3, 60];

/** Unter dieser Kürzestseite liest sich eine Kachel als Zeichenfehler. */
const SPLITTER = 10;

// --------------------------------------------------------------------------
// (a) Keine Splitter — über die ganze Breite, in der die Fläche überhaupt
//     gezeichnet wird (unter 520 px rendert die Komponente eine Rangliste).
// --------------------------------------------------------------------------
for (const [name, werte] of [["Erträge", ERTRAEGE], ["Investitionen", INVESTITIONEN]]) {
  const knoten = werte.map((value, i) => ({ value, i }));
  let schlimmste = { kurz: Infinity, breite: 0, masse: "" };
  for (let breite = 520; breite <= 1200; breite += 4) {
    for (const k of kacheln(knoten, breite, kachelHoehe(breite))) {
      const kurz = Math.min(k.breite, k.hoehe);
      if (kurz < schlimmste.kurz) {
        schlimmste = {
          kurz, breite,
          masse: `${Math.round(k.breite)} × ${Math.round(k.hoehe)} px`,
        };
      }
    }
  }
  pruefe(`${name}: keine Kachel unter ${SPLITTER} px Kürzestseite`,
    schlimmste.kurz >= SPLITTER,
    `${schlimmste.masse} bei ${schlimmste.breite} px Containerbreite`);
}

// --------------------------------------------------------------------------
// (b) Die Fläche ist restlos gefüllt und läuft nicht über: Eine Kachel
//     außerhalb ihres Rahmens wäre unsichtbar (`overflow-hidden`) — ihr
//     Anteil verschwände, ohne dass die Summe darunter es merkt.
// --------------------------------------------------------------------------
for (const [name, werte] of [["Erträge", ERTRAEGE], ["Investitionen", INVESTITIONEN]]) {
  const knoten = werte.map((value, i) => ({ value, i }));
  const breite = 854, hoehe = kachelHoehe(breite);
  const gelegt = kacheln(knoten, breite, hoehe);
  pruefe(`${name}: jede Kachel liegt im Rahmen`,
    gelegt.every((k) => k.x >= -0.5 && k.y >= -0.5
      && k.x + k.breite <= breite + 0.5 && k.y + k.hoehe <= hoehe + 0.5),
    `${breite} × ${hoehe} px`);
  pruefe(`${name}: jeder Posten bekommt genau eine Kachel`,
    gelegt.length === werte.length, `${gelegt.length} statt ${werte.length}`);

  // Fläche ∝ Wert: der Kern der Form. Die Fugen kosten jeder Kachel etwas,
  // deshalb wird das VERHÄLTNIS zweier Kacheln geprüft, nicht ihr Betrag —
  // und nur für die großen, bei denen die Fuge nicht ins Gewicht fällt.
  const summe = werte.reduce((s, w) => s + w, 0);
  const gross = gelegt.filter((k) => k.daten.value / summe > 0.05);
  for (const k of gross) {
    const soll = k.daten.value / summe;
    const ist = (k.breite * k.hoehe) / (breite * hoehe);
    pruefe(`${name}: Kachel ${k.daten.i} hält ihren Flächenanteil`,
      Math.abs(ist - soll) < 0.02,
      `${(ist * 100).toFixed(1)} % statt ${(soll * 100).toFixed(1)} %`);
  }
}

// --------------------------------------------------------------------------
// (c) Die Beschriftungs-Schwelle ist eine Regel, keine Zufallszahl: Was sie
//     durchlässt, muss zwei Zeilen à 11 px tragen können.
// --------------------------------------------------------------------------
pruefe("Beschriftung: 40 × 34 px trägt keine zwei Zeilen",
  !beschriftet(40, 34), "beschriftet(40, 34) = true");
pruefe("Beschriftung: 64 × 40 px trägt sie",
  beschriftet(64, 40), "beschriftet(64, 40) = false");
pruefe("Beschriftung: eine schmale, hohe Kachel trägt sie (vertikal)",
  beschriftet(44, 120), "beschriftet(44, 120) = false");

// --------------------------------------------------------------------------
// (e) Die Schrift folgt der Fläche: Die drei Stufen sind eine Treppe (nie
//     wird eine kleinere Kachel größer gesetzt als eine größere), die kleine
//     Stufe zählt ihre Zeilen wie zuvor, und auf der Erträge-Fläche steht
//     der größte Posten bei jeder Breite groß — sonst hieße die Stufe nichts.
// --------------------------------------------------------------------------
{
  const rang = { small: 0, medium: 1, large: 2 };
  let treppe = true;
  for (let b = 40; b <= 600 && treppe; b += 8) {
    for (let h = 34; h <= 440; h += 8) {
      if (rang[textstufe(b, h)] > rang[textstufe(b + 8, h + 8)]) { treppe = false; break; }
    }
  }
  pruefe("Textstufe: eine größere Kachel wird nie kleiner gesetzt", treppe, "Treppe verletzt");
  pruefe("Textstufe: die kleine Stufe zählt ihre Zeilen wie namenszeilen()",
    [[64, 40], [100, 60], [44, 120]].every(([b, h]) =>
      namenszeilenStufe("small", b, h) === namenszeilen(b, h)),
    "abweichend");
  pruefe("Textstufe: 200 × 130 px ist groß und trägt mindestens zwei Namenszeilen",
    textstufe(200, 130) === "large" && namenszeilenStufe("large", 200, 130) >= 2,
    `${textstufe(200, 130)}, ${namenszeilenStufe("large", 200, 130)} Zeilen`);
  pruefe("Einheit: 64 × 40 px trägt keine, 112 × 72 px trägt sie",
    !traegtEinheit(64, 40) && traegtEinheit(112, 72), "abweichend");
  const knoten = ERTRAEGE.map((value, i) => ({ value, i }));
  let grossUeberall = true;
  for (let b = 520; b <= 1200 && grossUeberall; b += 8) {
    const k = kacheln(knoten, b, kachelHoehe(b)).find((x) => x.daten.i === 0);
    if (!k || textstufe(k.breite, k.hoehe) !== "large") grossUeberall = false;
  }
  pruefe("Textstufe: der größte Ertragsposten steht bei jeder Breite groß",
    grossUeberall, "an mindestens einer Breite nicht");
}

// --------------------------------------------------------------------------
// (f) `buendelGrenze` hält ihren Vertrag: Beim gelieferten Schnitt trägt
//     JEDE Kachel (Rest eingeschlossen) über die ganze Breitenspanne ihre
//     Beschriftung — und der Schnitt ist maximal: eine Kachel mehr, und es
//     stünde wieder etwas Unbeschriftetes da. Die konkrete Zahl (2026: 7)
//     wird bewusst NICHT festgenagelt — ändert sich die Geometrie, darf sie
//     legitim wandern; der Vertrag darf es nicht.
// --------------------------------------------------------------------------
{
  const alleBeschriftet = (ab) => {
    const rest = ERTRAEGE.slice(ab).reduce((s, w) => s + w, 0);
    const knoten = [...ERTRAEGE.slice(0, ab), ...(rest > 0 ? [rest] : [])]
      .map((value) => ({ value }));
    for (let b = 520; b <= 1200; b += 8) {
      for (const k of kacheln(knoten, b, kachelHoehe(b))) {
        if (!beschriftet(k.breite, k.hoehe)) return false;
      }
    }
    return true;
  };
  const ab = buendelGrenze(ERTRAEGE);
  pruefe("buendelGrenze: liefert einen Rang in der Liste",
    ab >= 1 && ab <= ERTRAEGE.length, `${ab}`);
  pruefe("buendelGrenze: beim Schnitt trägt jede Kachel ihre Beschriftung",
    alleBeschriftet(ab), `Rang ${ab}`);
  pruefe("buendelGrenze: der Schnitt ist maximal",
    ab === ERTRAEGE.length || !alleBeschriftet(ab + 1),
    `Rang ${ab + 1} wäre auch beschriftet`);
}

// --------------------------------------------------------------------------
// (d) Die Textfarbe der Kacheln, gegen die ECHTEN Token gerechnet.
//
//     `--hh-seg-text` ist für die Anzeigetafel gemacht; auf einer Karte läuft
//     die Rampe weiter, und weißer Text landet dort auf fast Weiß. Die Probe
//     liest `app/globals.css`, rechnet beide Möglichkeiten aus und verlangt,
//     dass `rampenText()` die BESSERE nimmt. Sie verlangt NICHT 4,5 : 1: In
//     der Mitte jeder Rampe erreicht keine der beiden Farben das (ein Stufe 1
//     hell: 4,41, aus Stufe 3 dunkel: 4,30) — das steht am Modul und ist eine
//     Eigenschaft der Rampe, kein Fehler dieser Wahl.
// --------------------------------------------------------------------------
const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

/** Der Block, der die Rampen WIRKLICH setzt — `:root` kommt mehrfach vor. */
function rampenBlock(sel) {
  for (let ab = 0; ; ) {
    const i = css.indexOf(`${sel} {`, ab);
    if (i < 0) return null;
    const j = css.indexOf("\n}", i);
    const block = css.slice(i, j);
    if (block.includes("--hh-ein-0")) return block;
    ab = i + 1;
  }
}

function hslZuRgb(h, s, l) {
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  const [r, g, b] = [[c, x, 0], [x, c, 0], [0, c, x], [0, x, c], [x, 0, c], [c, 0, x]][
    Math.floor(((h % 360) + 360) % 360 / 60)];
  return [r + m, g + m, b + m];
}

function farbe(text) {
  const t = text.trim();
  if (t === "#fff") return [1, 1, 1];
  const m = t.match(/(?:hsl\(\s*)?([\d.]+)\s+([\d.]+)%\s+([\d.]+)%/);
  if (!m) throw new Error(`unbekannte Farbe: ${t}`);
  return hslZuRgb(Number(m[1]), Number(m[2]) / 100, Number(m[3]) / 100);
}

function kontrast(a, b) {
  const leucht = (rgb) => {
    const [r, g, bl] = rgb.map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [la, lb] = [leucht(a), leucht(b)];
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

// `--foreground` steht im Theme-Block, nicht im Rampen-Block: erst hell, dann dunkel.
const VORDERGRUND = [...css.matchAll(/--foreground:\s*([^;]+);/g)].map((m) => m[1]);

for (const [nr, [sel, thema]] of [[":root", "hell"], [".dark", "dunkel"]].entries()) {
  const block = rampenBlock(sel);
  pruefe(`Rampen-Block ${sel} gefunden`, !!block, "nicht gefunden");
  if (!block) continue;
  const seg = farbe(block.match(/--hh-seg-text:\s*([^;]+);/)[1]);
  const vorne = farbe(VORDERGRUND[nr]);
  for (const [rampe, stufen] of [["ein", 7], ["aus", 10]]) {
    for (let stufe = 0; stufe < stufen; stufe += 1) {
      const m = block.match(new RegExp(`--hh-${rampe}-${stufe}:\\s*([^;]+);`));
      if (!m) continue;
      const grund = farbe(m[1]);
      const gewaehlt = rampenText(rampe, stufe);
      const [gut, schlecht] = gewaehlt.includes("seg-text")
        ? [kontrast(grund, seg), kontrast(grund, vorne)]
        : [kontrast(grund, vorne), kontrast(grund, seg)];
      pruefe(`${thema}, Rampe ${rampe}, Stufe ${stufe}: die bessere Textfarbe`,
        gut >= schlecht,
        `${gewaehlt} hält ${gut.toFixed(2)} : 1, die andere ${schlecht.toFixed(2)} : 1`);
    }
  }
}

// --------------------------------------------------------------------------
// (e) Namenszeilen: mindestens eine, nie mehr als die Kachel trägt.
// --------------------------------------------------------------------------
pruefe("Namenszeilen: eine winzige Kachel bekommt mindestens eine Zeile",
  namenszeilen(40, 34) >= 1, `${namenszeilen(40, 34)}`);
pruefe("Namenszeilen: eine hohe Kachel bekommt mehrere",
  namenszeilen(200, 200) >= 8, `${namenszeilen(200, 200)}`);
pruefe("Namenszeilen: der Wert bekommt seine Zeile zurück",
  namenszeilen(200, 200) * 14 <= 200 - 12, `${namenszeilen(200, 200)} Zeilen auf 200 px`);

if (fehler) {
  console.error(`\n${fehler} Regel(n) der Kachelfläche verletzt.`);
  process.exit(1);
}
console.log("Kachelfläche: alle Regeln halten.");
