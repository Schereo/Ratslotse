"use client";

// <Zeitreihe> — die allgemeine Linien-Zeitreihe des Grafik-Baukastens (GB-01),
// dazu <ZeitreiheMini> als Karten-Sparkline (H3-02: Beteiligungs-Karten).
//
// MATHE: d3-scale (Skalen, nice ticks) + d3-shape (`line`/`area` mit
// `defined`). Das `defined`-Prädikat (`definiert`, der Type Guard über der
// normalisierten Reihe — dasselbe Muster wie `vorhanden` im Daten-Vertrag)
// lässt die Linie an jeder Lücke ABREISSEN, weil d3-shape dort schlicht kein
// Segment zeichnet. Interpolation ist damit im Code unmöglich, nicht nur
// verboten: Es gibt keine Stelle, an der ein Zwischenwert entstünde.
//
// LÜCKEN SIND DATEN (GB-00): `{jahr, fehlt}` steht IN der Reihe. Im Bild
// rendert die Lücke als schraffierter Kasten mit gestrichelter Signal-Kante
// (die Konvention des Bereichs), darunter beschriftet sie ein <LueckenFeld> —
// von der Komponente, nie von der Seite. Ein Jahr, das in der Reihe einfach
// FEHLT (weder Wert noch Lücke), bricht die Linie ebenfalls und bekommt einen
// „?"-Kasten: lieber sichtbar unerklärt als still durchgezogen.
//
// DIREKTBESCHRIFTUNG SPARSAM (GB-01): Endwerte immer, dazu — auf Wunsch der
// Seite — die GRÖSSTE DIFFERENZ, also der größte Anstieg und der größte
// Rückgang der Reihe (`spruenge`). Beides ist im Vertrag des Baukastens
// ausdrücklich erlaubt („Endwerte, größte Differenz"); alles andere liest die
// <Ableseleiste> (GB-00): Desktop Hover, mobil sticky Tap-Zeile, immer
// Pfeiltasten. Kein Tooltip; was nur beim Hovern existiert, fehlt im
// Ausdruck und in der Vorlesehilfe.
//
// SPRÜNGE RECHNET DIE KOMPONENTE, nicht die Seite. Das ist Absicht: Eine
// Seite, die „2001 fiel die Schuld am stärksten" als Text trägt, wird mit dem
// nächsten Jahrgang still falsch. Verglichen werden nur BENACHBARTE Jahre —
// über eine Lücke hinweg gibt es keinen Sprung, sondern Unwissen.
//
// BREAKPOINTS EINGEBAUT, KEIN PROP (H4-A „Zeitreihe + Ableseleiste"):
// unter 520 px Containerbreite wird die Zeichenfläche 180 px hoch, die
// Achse zeigt nur Dekaden, die Schrift wächst auf Fingermaß. Gemessen wird
// der Container (`lib/use-breite.ts`), damit die viewBox auf Faktor 1,0
// bleibt und nichts mitgestaucht wird.
//
// KEINE BEWERTUNGSFARBEN: Die Reihe trägt den neutralen Schieferton
// `--hh-aus-0` (theme-geprüft gegen die Karte), die Zweitreihe eine eigene
// Rampenstufe — nie Signal-Orange, denn eine zweite Größe ist keine
// Abweichung. Orange bleibt den Lücken-Markierungen vorbehalten.

import { useId, useState, type ReactNode } from "react";
import { scaleLinear } from "d3-scale";
import { area, curveStepAfter, line } from "d3-shape";
import { useBreite } from "@/lib/use-breite";
import { cn } from "@/lib/utils";
import { istLuecke, type JahrLuecke, type JahrPunkt, type JahrWert } from "./daten";
import { deZahl } from "./format";
import { LueckenFeld } from "./luecken-feld";
import {
  AbleseBeschreibung, AbleseFlaeche, Ableseleiste, useAblesen,
  type AbleseStelle, type AbleseWert,
} from "./ablesen";

/** Farbe der Hauptreihe: der neutrale Schieferton des Bereichs. */
const TON = "var(--hh-aus-0)";
/** Farbe der Zweitreihe: eigene Rampenstufe, KEIN Orange (eine zweite
 *  Größe ist keine Abweichung — H4-13: „Zins ist keine Abweichung"). */
const TON_ZWEIT = "var(--hh-ein-1)";

// Beschriftungen im Bild bekommen einen Kontur-Halo in Kartenfarbe, sonst
// schneidet die Kurve mitten durch die Ziffern (Muster aus `schulden-kurve`).
const halo = { paintOrder: "stroke", strokeWidth: 3, strokeLinejoin: "round" } as const;

export type ZeitreiheAnnotation = {
  jahr: number;
  /** Der ganze Satz — steht IMMER unter der Grafik und in der Vorlesehilfe. */
  text: string;
  /** Kurzform für den Chip über der Grafik („108,9 Mio. umgebucht").
   *  Praktisch immer angeben: Ohne sie trägt der Chip nur „ⓘ Jahr", und der
   *  sagt nur, DASS etwas war — nicht was (Tims Befund 18.08.2026). Die
   *  Chips stehen in einem eigenen Container statt im Bild: HTML bricht um,
   *  wo im SVG platzierte Texte bei engen Breiten ineinanderliefen. Chip
   *  und ⓘ wählen beide das Jahr; der ganze Satz steht dann in der
   *  Ableseleiste. */
  kurz?: string;
};

export type ZeitreiheUmschalter = {
  /** Beschriftungen der Ansichten, z. B. ["absolut", "pro Kopf"]. */
  optionen: readonly string[];
  aktiv: number;
  onWahl: (i: number) => void;
};

/** Ein Jahr der normalisierten Reihe: Wert, erklärte Lücke — oder ein Jahr,
 *  das in der Reihe schlicht fehlt (`unerklaert`). */
type Stelle =
  | { jahr: number; art: "wert"; punkt: JahrWert }
  | { jahr: number; art: "luecke"; punkt: JahrLuecke }
  | { jahr: number; art: "unerklaert" };

type WertStelle = Extract<Stelle, { art: "wert" }>;

/** Das `defined`-Prädikat für d3-shape — UND der Type Guard fürs Lesen:
 *  Wer an den Wert will, kommt am Lücken-Zweig nicht vorbei. */
const definiert = (s: Stelle): s is WertStelle => s.art === "wert";

/** Die Reihe auf den vollen Jahresbereich normalisieren — so kann kein
 *  fehlendes Jahr aus der x-Achse herausfallen und still interpoliert wirken.
 *
 *  **Außer bei einer Treppe.** Dort ist ein Jahr ohne eigenen Punkt kein
 *  fehlendes Jahr: Der Wert von vorhin gilt weiter, bis der nächste Punkt
 *  kommt — das ist die Aussage der Quelle, nicht ihre Lücke. Die
 *  Hebesatz-Tabelle führt neun Änderungsjahre in 45 Jahren; würde sie hier
 *  aufgefüllt, stünden 37 Fragezeichen im Bild und die Linie risse an jedem
 *  davon ab. Genau das tat sie, bis der Modus auch hier greift.
 *
 *  Die Unterscheidung, die dahinter steht: „wir wissen es nicht" (Lücke,
 *  Schraffur, Linienbruch) gegen „es hat sich nichts geändert" (Stufe). Beide
 *  verbieten dieselbe Interpolation, aber aus verschiedenen Gründen. */
function normalisiere(reihe: JahrPunkt[], treppe = false): Stelle[] {
  const sortiert = [...reihe].sort((a, b) => a.jahr - b.jahr);
  if (!sortiert.length) return [];
  if (treppe) {
    return sortiert.map((p) => istLuecke(p)
      ? { jahr: p.jahr, art: "luecke" as const, punkt: p }
      : { jahr: p.jahr, art: "wert" as const, punkt: p });
  }
  const nach = new Map(sortiert.map((p) => [p.jahr, p]));
  const aus: Stelle[] = [];
  for (let jahr = sortiert[0].jahr; jahr <= sortiert[sortiert.length - 1].jahr; jahr++) {
    const p = nach.get(jahr);
    if (!p) aus.push({ jahr, art: "unerklaert" });
    else if (istLuecke(p)) aus.push({ jahr, art: "luecke", punkt: p });
    else aus.push({ jahr, art: "wert", punkt: p });
  }
  return aus;
}

export function Zeitreihe({
  reihe, einheit, ariaTitel, titel, nachkomma = 1, format, zweitreihe,
  annotationen, spruenge = false, vorjahresdifferenz = false, tabelle = false,
  umschalter, beleg, nullbasis = true, hinweis, treppe = false, className,
}: {
  /** Punkte UND Lücken in einer Liste (Daten-Vertrag GB-00). */
  reihe: JahrPunkt[];
  /** Steht in der Ableseleiste und der Kopf-Zeile, z. B. „Mio. €". */
  einheit: string;
  /** Der Satz für die Vorlesehilfe — Pflicht, eine Grafik ohne Namen ist
   *  für den Screenreader ein leeres Rechteck. */
  ariaTitel: string;
  /** Sichtbare Kopfzeile über dem Bild („Schulden insgesamt"). Rechts daneben
   *  setzt die Komponente die gemessene Menge: Spanne, Zahl der Werte,
   *  Einheit — nie „viele Jahre", immer die Zahl. Ohne `titel` keine
   *  Kopfzeile: Eine leere Überschriftenzeile wäre ein Versprechen. */
  titel?: string;
  nachkomma?: number;
  /** Eigenes Zahlenformat (Vorgabe: `deZahl` mit `nachkomma`). Für Reihen,
   *  deren Werte nicht als Mio. kommen — gebaut aus `format.ts`, nie aus
   *  `toLocaleString`. */
  format?: (wert: number) => string;
  /** Dünn und gestrichelt IN derselben Zeichenfläche (GB-01),
   *  z. B. die Zinslast zur Schuldenreihe. */
  zweitreihe?: { label: string; reihe: JahrPunkt[]; format?: (wert: number) => string };
  /** Beschriftete Stellen („2010: 108,9 Mio. an Eigenbetriebe umgebucht").
   *  Im Bild ein ⓘ-Marker (breit mit `kurz` daneben); der ganze Satz steht in
   *  der **Ableseleiste**, sobald das Jahr gewählt ist — ein Tipp aufs ⓘ
   *  genügt, weil die Fangfläche darüberliegt. Bis 08/2026 stand der Text
   *  zusätzlich dauerhaft unter der Grafik; das doppelte Anzeigen ist auf
   *  Tims Entscheid (18.08.2026) der Leisten-Zeile gewichen. KEIN Tooltip im
   *  Sinn der GB-00-Regel: Die Zeile ist Text im Layout, bleibt bis zur
   *  nächsten Wahl stehen, ist per Pfeiltasten und Finger gleich erreichbar,
   *  und die Vorlesehilfe trägt alle Sätze weiterhin vollständig
   *  (`aria-describedby` + `vorlesen` je Stelle). */
  annotationen?: ZeitreiheAnnotation[];
  /** Den größten Anstieg und den größten Rückgang direkt beschriften.
   *
   *  Gerechnet aus den Daten und ausdrücklich NICHT über eine Lücke hinweg.
   *  Die Marke trägt Signal-Orange, weil sie eine **Differenz** markiert —
   *  keine Bewertung: Ein Rückgang kann eine abgegebene Aufgabe sein und ein
   *  Anstieg eine sanierte Schule. Die Marke sagt „hier ist die größte
   *  Bewegung", nicht „das ist gut". Was dahintersteckt, gehört als belegter
   *  Satz auf die Seite (oder als `annotationen`), nicht in eine Farbe. */
  spruenge?: boolean;
  /** Zusätzliche Zeile in der Ableseleiste: die Veränderung zum Vorjahr.
   *  Nur zwischen benachbarten Jahren — hinter einer Lücke bleibt sie weg,
   *  sonst wäre die Differenz über zwei Jahre als „ggü. Vorjahr"
   *  ausgewiesen. Ohne Signal-Marke: Jede Richtung ist gleich markiert. */
  vorjahresdifferenz?: boolean;
  /** Alle Werte zusätzlich als aufklappbare Tabelle unter der Grafik —
   *  für Leser*innen, die eine Zahl abschreiben wollen, statt sie an der
   *  Leiste abzufahren. Lücken stehen darin als „—"; ihr Grund steht wie
   *  immer im <LueckenFeld> darunter, das nie einklappbar ist. */
  tabelle?: boolean;
  /** Ansichts-Umschalter („absolut" / „pro Kopf") — gerendert von der
   *  Komponente (mobil full-width, H4-13), Daten wechselt die Seite. */
  umschalter?: ZeitreiheUmschalter;
  /** Beleg-Chip-Slot (GB-00): die Seite wählt die Quelle. */
  beleg?: ReactNode;
  /** Bestandsgrößen starten bei null (Vorgabe); reine Abstands-Reihen
   *  dürfen abschneiden. */
  nullbasis?: boolean;
  /** Eigener Bedien-Hinweis unter der Ableseleiste. */
  hinweis?: string;
  /** Treppe statt Linie: Der Wert gilt bis zum nächsten Punkt und springt
   *  dort — für Größen, die zwischen zwei Beschlüssen **stillstehen**.
   *
   *  Gebaut für die Hebesatz-Reihe (Tabelle 1105 führt nur die neun
   *  Änderungsjahre seit 1980). Eine gerade Verbindung wäre dort keine
   *  Vereinfachung, sondern eine falsche Aussage: Sie zeigte einen langsamen
   *  Anstieg über zehn Jahre, wo der Rat einmal entschieden hat. Dieselbe
   *  Regel wie beim Lückenbruch — was die Quelle nicht sagt, zeichnen wir
   *  nicht (`curveStepAfter` aus d3-shape, GB-01).
   *
   *  Die Ableseleiste bleibt punktweise: Sie zeigt die Stufe und, über
   *  `format`, seit wann sie gilt. */
  treppe?: boolean;
  className?: string;
}) {
  const { box, breite } = useBreite();
  const [tabelleOffen, setTabelleOffen] = useState(false);
  const stellenListe = normalisiere(reihe, treppe);
  const beschreibungId = useId();
  const ablesen = useAblesen(
    stellenListe.length,
    Math.max(stellenListe.length - 1, 0),
  );

  const fmt = format ?? ((v: number) => deZahl(v, nachkomma));
  const fmtZweit = zweitreihe?.format ?? fmt;
  const schmal = breite < 520;
  const fs = schmal
    ? { achse: 13, jahr: 13, wert: 14, legende: 12.5, marke: 12.5 }
    : { achse: 11, jahr: 11, wert: 13, legende: 12, marke: 11 };

  const werte = stellenListe.filter(definiert);
  if (werte.length < 2) return null;

  const spanneVon = stellenListe[0].jahr;
  const spanneBis = stellenListe[stellenListe.length - 1].jahr;
  // Die Zweitreihe wird auf die x-Achse der Hauptreihe geklemmt: Ein Jahr
  // außerhalb hätte keine Stelle im Bild und würde von der Skala nach
  // draußen gerechnet — die Linie liefe aus der Zeichenfläche.
  const zweitStellen = zweitreihe
    ? normalisiere(zweitreihe.reihe.filter(
        (p) => p.jahr >= spanneVon && p.jahr <= spanneBis), treppe)
    : [];
  const zweitNach = new Map(zweitStellen.map((s) => [s.jahr, s]));

  // --- Skalen (d3-scale) ---------------------------------------------------
  const plotH = schmal ? 180 : 210;
  const YTOP = 18;
  const Y0 = YTOP + plotH;
  const yJahr = Y0 + (schmal ? 21 : 18);
  const H = yJahr + 8;

  const alleWerte = [
    ...werte.map((s) => (s.punkt as JahrWert).wert),
    ...zweitStellen.filter(definiert).map((s) => s.punkt.wert),
  ];
  const ySkala = scaleLinear()
    .domain([nullbasis ? 0 : Math.min(...alleWerte), Math.max(...alleWerte)])
    .nice(schmal ? 3 : 4)
    .range([Y0, YTOP + 12]);
  const gitter = ySkala.ticks(schmal ? 3 : 4);
  const achsenText = gitter.map((v) => deZahl(v, 0));

  // Linker Rand nach der BREITESTEN Achsenzahl (Mono ≈ 0,62 em je Zeichen) —
  // ein fester Wert ragte im schmalen Container aus der Fläche (schulden-kurve).
  const W = breite;
  const X0 = Math.ceil(Math.max(...achsenText.map((t) => t.length)) * fs.achse * 0.62) + 9;
  const X1 = W - 16;

  const von = spanneVon;
  const bis = spanneBis;
  const x = (jahr: number) => X0 + ((jahr - von) / Math.max(bis - von, 1)) * (X1 - X0);
  const y = (v: number) => ySkala(v);

  // --- Pfade (d3-shape, defined = vorhanden) -------------------------------
  // `defined` läuft über die NORMALISIERTE Reihe: Lücken UND unerklärte Jahre
  // sind nicht defined — d3-shape beendet dort das Segment und beginnt hinter
  // der Lücke ein neues. Genau das ist der Lückenbruch des Vertrags.
  // `treppe` tauscht nur die Kurvenform — die Geometrie bleibt dieselbe.
  // `curveStepAfter` hält den Wert bis zum nächsten Punkt und springt dort:
  // genau das, was ein Hebesatz tut. Eine gerade Verbindung behauptete, der
  // Satz sei zwischen 2015 und 2025 langsam gestiegen; er stand zehn Jahre
  // still und sprang dann.
  const kurve = treppe ? curveStepAfter : undefined;
  const linie = line<Stelle>()
    .defined(definiert)
    .x((s) => x(s.jahr))
    .y((s) => y((s as { punkt: JahrWert }).punkt.wert));
  const flaeche = area<Stelle>()
    .defined(definiert)
    .x((s) => x(s.jahr))
    .y0(Y0)
    .y1((s) => y((s as { punkt: JahrWert }).punkt.wert));
  const zweitLinie = line<Stelle>()
    .defined(definiert)
    .x((s) => x(s.jahr))
    .y((s) => y((s as { punkt: JahrWert }).punkt.wert));
  if (kurve) {
    linie.curve(kurve);
    flaeche.curve(kurve);
    zweitLinie.curve(kurve);
  }

  const luecken = stellenListe.filter((s) => s.art !== "wert");
  const abstand = stellenListe.length > 1 ? x(stellenListe[1].jahr) - x(von) : 60;
  const halbeLuecke = Math.max(9, Math.min(30, abstand * 0.45));

  const erster = werte[0].punkt;
  const letzter = werte[werte.length - 1].punkt;

  // --- Jahresachse: mobil nur Dekaden (H4-A), sonst ausgedünnt -------------
  const jahresmarken: number[] = [];
  if (schmal) {
    for (let j = Math.ceil(von / 10) * 10; j <= bis; j += 10) jahresmarken.push(j);
  } else {
    const schritt = Math.max(Math.ceil((bis - von) / 6), 1);
    for (let j = von; j <= bis; j += schritt) jahresmarken.push(j);
  }
  if (jahresmarken[jahresmarken.length - 1] !== bis) {
    if (jahresmarken.length && bis - jahresmarken[jahresmarken.length - 1] < (bis - von) / 10) {
      jahresmarken.pop();
    }
    jahresmarken.push(bis);
  }

  // --- Beschriftungen im Bild entzerren ------------------------------------
  // SVG-Text weicht nicht von selbst aus. Wo mehrere Marken zusammenfallen
  // (der Endwert und der größte Anstieg liegen regelmäßig am selben Punkt),
  // hilft nur: Kästen grob schätzen, Belegtes sammeln, die beweglichen Marken
  // zeilenweise ausweichen lassen. Genau messen ginge nur mit einem zweiten
  // Render-Durchgang; die Schätzung (~0,55 der Schriftgröße je Zeichen) ist
  // bewusst großzügig.
  type Kasten = { x1: number; x2: number; y1: number; y2: number };
  const textBreite = (t: string, size: number) => t.length * size * 0.55;
  const stoert = (a: Kasten, b: Kasten) =>
    a.x1 < b.x2 + 4 && b.x1 < a.x2 + 4 && a.y1 < b.y2 + 2 && b.y1 < a.y2 + 2;
  /** Die erste freie Zeile über dem Punkt, sonst darunter. */
  const ausweichen = (py: number, kasten: (ty: number) => Kasten,
                      belegt: Kasten[]): number => {
    const zeile = fs.marke + 4;
    const kandidaten: number[] = [];
    for (let n = 0; n < 6 && py - 10 - n * zeile - fs.marke > YTOP; n++) {
      kandidaten.push(py - 10 - n * zeile);
    }
    kandidaten.push(Math.min(py + 9 + fs.marke, Y0 - 4));
    return kandidaten.find((k) => !belegt.some((b) => stoert(kasten(k), b)))
      ?? kandidaten[kandidaten.length - 1];
  };

  const endText = fmt(letzter.wert);
  const endY = y(letzter.wert) - 10;
  const belegt: Kasten[] = [{
    x1: x(letzter.jahr) - 7 - textBreite(endText, fs.wert + 1),
    x2: x(letzter.jahr) - 7,
    y1: endY - fs.wert - 1, y2: endY + 3,
  }];

  // Die Zweitreihe beschriftet sich am eigenen Endpunkt — breit mit Name und
  // Spanne, schmal gar nicht: Dort trägt die Legende unter dem Bild den
  // Namen, und zwei Beschriftungen in einem 180-px-Bild überlagern sich.
  const zweitWerte = zweitStellen.filter(definiert);
  const zweitLetzter = zweitWerte.length
    ? zweitWerte[zweitWerte.length - 1].punkt : null;
  const zweitBeschriftung = !schmal && zweitreihe && zweitLetzter
    ? (() => {
        const text = `${zweitreihe.label} `
          + `(${zweitWerte[0].punkt.jahr}–${zweitLetzter.jahr})`;
        const w = textBreite(text, fs.marke);
        const tx = Math.min(Math.max(x(zweitLetzter.jahr), X0 + w), X1);
        const ty = y(zweitLetzter.wert) - 8;
        belegt.push({ x1: tx - w, x2: tx, y1: ty - fs.marke, y2: ty + 3 });
        return { text, tx, ty };
      })()
    : null;

  // Annotations-Marken: ⓘ am oberen Rand, mit Strich zum Punkt. Der TEXT
  // dazu steht nicht mehr im Bild, sondern in einer Chip-Zeile darüber
  // (Tims Entscheid 18.08.2026): Im Bild platzierte Kurztexte liefen bei
  // engen Breiten ineinander oder in die Marke des Nachbarn — eine
  // Ausweich-Geometrie dafür war die Sorte Komplexität, die HTML mit
  // flex-wrap schlicht nicht hat. Der Chip wählt beim Antippen sein Jahr,
  // dieselbe Mechanik wie das ⓘ selbst.
  const annoMarken = (annotationen ?? []).flatMap((a) => {
    const idx = stellenListe.findIndex((s) => s.jahr === a.jahr);
    if (idx < 0) return [];
    const stelle = stellenListe[idx];
    const py = stelle.art === "wert" ? y(stelle.punkt.wert) : (Y0 + YTOP) / 2;
    return [{ ...a, py, idx }];
  });

  // Die größte Bewegung nach oben und nach unten — gerechnet, neutral
  // beschriftet, und NUR zwischen benachbarten Jahren: Über eine Lücke hinweg
  // wäre der „Sprung" die Summe zweier unbekannter Bewegungen.
  const spruengeMarken = (() => {
    if (!spruenge) return [];
    const deltas: { jahr: number; delta: number; wert: number }[] = [];
    for (let i = 1; i < stellenListe.length; i++) {
      const a = stellenListe[i - 1], b = stellenListe[i];
      if (!definiert(a) || !definiert(b)) continue;
      deltas.push({ jahr: b.jahr, delta: b.punkt.wert - a.punkt.wert,
                    wert: b.punkt.wert });
    }
    if (!deltas.length) return [];
    const runter = [...deltas].sort((p, q) => p.delta - q.delta)[0];
    const rauf = [...deltas].sort((p, q) => q.delta - p.delta)[0];
    return [runter, rauf]
      // Steigt eine Reihe nur, sind größter Anstieg und größter „Rückgang"
      // dieselbe Stelle — dann steht die Marke einmal.
      .filter((m, i, alle) => alle.findIndex((n) => n.jahr === m.jahr) === i)
      .map((m) => {
        const text = `${m.jahr}: ${m.delta > 0 ? "+" : "−"}${fmt(Math.abs(m.delta))}`;
        const w = textBreite(text, fs.marke);
        return {
          ...m, text, w,
          mitte: Math.min(Math.max(x(m.jahr), X0 + w / 2), X1 - w / 2),
          py: y(m.wert),
        };
      })
      .sort((a, b) => a.mitte - b.mitte)
      .map((m) => {
        const kasten = (ty: number): Kasten => ({
          x1: m.mitte - m.w / 2, x2: m.mitte + m.w / 2,
          y1: ty - fs.marke, y2: ty + 3,
        });
        const ty = ausweichen(m.py, kasten, belegt);
        belegt.push(kasten(ty));
        return { ...m, ty };
      });
  })();

  // --- Ableseleiste: eine Stelle je Jahr, auch für Lücken ------------------
  const annotationNach = new Map((annotationen ?? []).map((a) => [a.jahr, a]));
  const ableseStellen: AbleseStelle[] = stellenListe.map((s, i) => {
    const zweit = zweitNach.get(s.jahr);
    const werteZeile: AbleseWert[] =
      s.art === "wert"
        ? [{ label: einheit, wert: fmt(s.punkt.wert), farbe: TON }]
        : [{ label: einheit, wert: "—", signal: true }];
    // Die Veränderung zum Vorjahr — nur wenn beide Jahre einen Wert haben
    // und wirklich benachbart sind.
    const vorher = i > 0 ? stellenListe[i - 1] : null;
    const delta = vorjahresdifferenz && s.art === "wert" && vorher && definiert(vorher)
      ? s.punkt.wert - vorher.punkt.wert : null;
    if (delta != null) {
      werteZeile.push({
        label: "ggü. Vorjahr",
        wert: `${delta > 0 ? "+" : delta < 0 ? "−" : ""}${fmt(Math.abs(delta))}`,
        // Keine Signal-Marke: Sie markierte die Bewegung als Abweichung, und
        // „Anstieg" ist hier keine. Jede Richtung sieht gleich aus.
        signal: false,
      });
    }
    if (zweitreihe) {
      werteZeile.push({
        label: zweitreihe.label,
        wert: zweit?.art === "wert" ? fmtZweit((zweit.punkt as JahrWert).wert) : "—",
        farbe: TON_ZWEIT,
      });
    }
    const grund = s.art === "luecke" ? s.punkt.fehlt : s.art === "unerklaert" ? "keine Angabe" : null;
    const anno = annotationNach.get(s.jahr);
    return {
      titel: String(s.jahr) + (anno ? " ⓘ" : ""),
      werte: werteZeile,
      anmerkung: anno?.text,
      vorlesen: [
        `${s.jahr}:`,
        s.art === "wert" ? `${fmt(s.punkt.wert)} ${einheit}.` : `keine Zahl — ${grund}.`,
        zweitreihe && zweit?.art === "wert"
          ? `${zweitreihe.label} ${fmtZweit((zweit.punkt as JahrWert).wert)}.`
          : "",
        anno ? `Anmerkung: ${anno.text}` : "",
      ].filter(Boolean).join(" "),
    };
  });

  const beschreibung = [
    `${ariaTitel}, ${von} bis ${bis}.`,
    werte.map((s) => `${s.jahr}: ${fmt((s.punkt as JahrWert).wert)}`).join(", "),
    `${einheit}.`,
    luecken.length
      ? `Ohne Zahl: ${luecken.map((s) =>
          `${s.jahr} (${s.art === "luecke" ? s.punkt.fehlt : "keine Angabe"})`).join(", ")}.`
      : "",
    // Was im Bild als zweite Linie und als Marke steht, gehört auch in die
    // Vorlesehilfe — sonst ist die Grafik für sie eine andere.
    zweitreihe && zweitWerte.length
      ? `Dünne zweite Reihe: ${zweitreihe.label}, `
        + `${zweitWerte[0].jahr} bis ${zweitWerte[zweitWerte.length - 1].jahr}.`
      : "",
    ...(annotationen ?? []).map((a) => a.text),
  ].filter(Boolean).join(" ");

  return (
    <div ref={box} className={cn("min-w-0", className)}>
      {umschalter && (
        <div
          role="group" aria-label="Ansicht wählen"
          className="mb-2.5 grid gap-1 rounded-full border border-border bg-card p-1 ab-tablet:inline-grid"
          style={{ gridTemplateColumns: `repeat(${umschalter.optionen.length}, minmax(0, 1fr))` }}
        >
          {umschalter.optionen.map((o, i) => (
            <button
              key={o} type="button" aria-pressed={i === umschalter.aktiv}
              onClick={() => umschalter.onWahl(i)}
              className={cn(
                "min-h-[36px] rounded-full px-3.5 text-[12.5px] transition-colors",
                i === umschalter.aktiv
                  ? "bg-primary font-semibold text-primary-foreground"
                  : "text-foreground/75 hover:bg-accent",
              )}
            >
              {o}
            </button>
          ))}
        </div>
      )}

      {/* Kopfzeile: links, was gezeigt wird — rechts, wie viel davon
          gemessen ist. Ehrliche Mengen sind Vertrag des Baukastens. */}
      {titel && (
        <div className="mb-2 flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            {titel}
          </p>
          <span className="font-mono text-[10px] uppercase text-muted-foreground">
            {von}–{bis} · {werte.length} Werte · {einheit}
          </span>
        </div>
      )}

      {/* Die Chip-Zeile: je Annotation ein Chip mit Jahr und Kurzform, in
          einem eigenen Container statt im Bild — HTML bricht um, wo das SVG
          ausweichen müsste. Der Chip WÄHLT sein Jahr (dieselbe Mechanik wie
          das ⓘ), der ganze Satz erscheint in der Ableseleiste; der gewählte
          Chip füllt sich synchron zum ⓘ im Bild. */}
      {annoMarken.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {annoMarken.map((a) => {
            const aktivesJahr = stellenListe[ablesen.aktiv]?.jahr === a.jahr;
            return (
              <button
                key={a.jahr} type="button"
                aria-pressed={aktivesJahr}
                onClick={() => { ablesen.waehle(a.idx); ablesen.setTastatur(false); }}
                className={cn(
                  "inline-flex min-h-[26px] items-center gap-1.5 rounded-full border px-2.5",
                  "text-[11px] leading-none transition-colors",
                  aktivesJahr
                    ? "border-foreground/70 bg-foreground/75 text-card"
                    : "border-border bg-card text-foreground/80 hover:border-foreground/40",
                )}
              >
                <span aria-hidden="true" className="font-mono text-[10px] italic">ⓘ</span>
                <span className="font-mono text-[10px] font-semibold tabular-nums">{a.jahr}</span>
                {a.kurz && <span className="font-medium">{a.kurz}</span>}
              </button>
            );
          })}
        </div>
      )}

      <AbleseBeschreibung id={beschreibungId}>{beschreibung}</AbleseBeschreibung>
      {/* `role="group"`, nicht `img`: Die Jahres-Ziele der Ablese-Fläche
          wären in einem `img` für die Vorlesehilfe unsichtbar. */}
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="group"
        aria-label={ariaTitel} aria-describedby={beschreibungId}>
        {gitter.map((v, i) => (
          <g key={v}>
            <line x1={X0} y1={y(v)} x2={X1} y2={y(v)} className="stroke-border/60" />
            <text x={X0 - 6} y={y(v) + 4} textAnchor="end" fontSize={fs.achse}
              className="fill-muted-foreground font-mono">{achsenText[i]}</text>
          </g>
        ))}
        <line x1={X0} y1={Y0} x2={X1} y2={Y0} className="stroke-border" />

        {/* Lücken-Kästen: Schraffur + gestrichelte Signal-Kante — Markierung,
            keine Fläche in Orange (GB-00). */}
        {luecken.map((s) => {
          const xl = x(s.jahr) - halbeLuecke, xr = x(s.jahr) + halbeLuecke;
          return (
            <g key={s.jahr}>
              <foreignObject x={xl} y={YTOP} width={xr - xl} height={Y0 - YTOP}>
                <div className="hh-schraffur h-full w-full opacity-60" />
              </foreignObject>
              <rect x={xl} y={YTOP} width={xr - xl} height={Y0 - YTOP} fill="none"
                strokeDasharray="4 3" className="stroke-signal" />
              {s.art === "unerklaert" && (
                <text x={x(s.jahr)} y={(Y0 + YTOP) / 2} textAnchor="middle" fontSize={11}
                  className="fill-signal font-mono">?</text>
              )}
            </g>
          );
        })}

        {/* Fläche + Linie: `defined()` hat die Segmente an den Lücken schon
            getrennt — hier wird nur noch gezeichnet. */}
        {nullbasis && <path d={flaeche(stellenListe) ?? undefined} style={{ fill: TON }} opacity={0.08} />}
        {zweitreihe && (
          <path d={zweitLinie(zweitStellen) ?? undefined} fill="none" strokeWidth={1.5}
            strokeDasharray="5 4" strokeLinecap="round" style={{ stroke: TON_ZWEIT }} />
        )}
        <path d={linie(stellenListe) ?? undefined} fill="none" strokeWidth={2.2}
          strokeLinejoin="round" strokeLinecap="round" style={{ stroke: TON }} />

        {/* Der Endpunkt der Zweitreihe mit ihrem Namen — breit im Bild,
            schmal nur in der Legende darunter. */}
        {zweitLetzter && (
          <circle cx={x(zweitLetzter.jahr)} cy={y(zweitLetzter.wert)} r={3}
            style={{ fill: TON_ZWEIT }} />
        )}
        {zweitBeschriftung && (
          <text x={zweitBeschriftung.tx} y={zweitBeschriftung.ty} textAnchor="end"
            fontSize={fs.marke} className="stroke-card" {...halo}
            style={{ fill: TON_ZWEIT }}>{zweitBeschriftung.text}</text>
        )}

        {/* Annotationen: ⓘ im Bild, der Kurztext im Chip darüber, der ganze
            Satz in der Ableseleiste, sobald das Jahr gewählt ist. Das
            gewählte ⓘ füllt sich, damit sichtbar ist, WOHER die Zeile in der
            Leiste gerade kommt. */}
        {annoMarken.map((a) => {
          const aktivesJahr = stellenListe[ablesen.aktiv]?.jahr === a.jahr;
          return (
            <g key={a.jahr}>
              <line x1={x(a.jahr)} y1={YTOP + 8} x2={x(a.jahr)} y2={a.py - 8}
                strokeWidth={1} strokeDasharray="2 3" className="stroke-foreground/40" />
              <circle cx={x(a.jahr)} cy={YTOP + 8} r={7.5} strokeWidth={1.2}
                className={aktivesJahr
                  ? "fill-foreground/75 stroke-foreground/75"
                  : "fill-card stroke-foreground/45"} />
              <text x={x(a.jahr)} y={YTOP + 11.5} textAnchor="middle" fontSize={10} fontStyle="italic"
                className={aktivesJahr ? "fill-card font-mono" : "fill-foreground/75 font-mono"}>i</text>
            </g>
          );
        })}

        {/* Die größte Bewegung: Punkt und Führungsstrich zuerst, damit kein
            Strich durch die Beschriftung der anderen Marke zieht. */}
        {spruengeMarken.map((m) => (
          <g key={`sprung-${m.jahr}`}>
            {(Math.abs(m.mitte - x(m.jahr)) > 2 || m.ty < m.py - 13 || m.ty > m.py) && (
              <line x1={x(m.jahr)} y1={m.py + (m.ty > m.py ? 6 : -6)}
                x2={Math.min(Math.max(x(m.jahr), m.mitte - m.w / 2), m.mitte + m.w / 2)}
                y2={m.ty > m.py ? m.ty - fs.marke - 2 : m.ty + 4}
                strokeWidth={1} className="stroke-signal" opacity={0.45} />
            )}
            <circle cx={x(m.jahr)} cy={m.py} r={4}
              className="fill-card stroke-signal" strokeWidth={2} />
          </g>
        ))}
        {spruengeMarken.map((m) => (
          <text key={`sprung-text-${m.jahr}`} x={m.mitte} y={m.ty} textAnchor="middle"
            fontSize={fs.marke} className="fill-signal stroke-card" {...halo}>{m.text}</text>
        ))}

        {/* Direktbeschriftung: Endwerte immer (GB-01). */}
        <circle cx={x(erster.jahr)} cy={y(erster.wert)} r={4} className="fill-card"
          strokeWidth={2} style={{ stroke: TON }} />
        <circle cx={x(letzter.jahr)} cy={y(letzter.wert)} r={5} style={{ fill: TON }} />
        <text x={x(letzter.jahr) - 7} y={endY} textAnchor="end"
          fontSize={fs.wert + 1} fontWeight={700} className="stroke-card" {...halo}
          style={{ fill: TON }}>{endText}</text>

        {jahresmarken.map((j) => (
          <text key={j} x={x(j)} y={yJahr} textAnchor="middle" fontSize={fs.jahr}
            className={j === bis ? "fill-foreground font-mono" : "fill-muted-foreground font-mono"}>
            {j}
          </text>
        ))}

        {/* Zuletzt: die Ablese-Fläche über allem, sonst fängt die Kurve den
            Zeiger ab. */}
        <AbleseFlaeche
          stellen={ableseStellen} steuerung={ablesen} gruppe="Jahre der Reihe"
          x={(i) => x(stellenListe[i].jahr)} xVon={X0} xBis={X1}
          yVon={YTOP} hoehe={Y0 - YTOP} fangHoehe={yJahr + 4 - YTOP}
          marken={(i) => {
            const s = stellenListe[i];
            const z = zweitNach.get(s.jahr);
            return [
              ...(s.art === "wert" ? [{ y: y(s.punkt.wert), farbe: TON }] : []),
              // Die Leiste zeigt beide Reihen als Wert — dann gehören auch
              // beide Marken an den Führungsstrich.
              ...(z?.art === "wert" ? [{ y: y(z.punkt.wert), farbe: TON_ZWEIT }] : []),
            ];
          }}
        />
      </svg>

      {/* Der ⓘ-Zusatz hängt an JEDEM Hinweis, auch einem eigenen der Seite:
          Er wirbt für die einzige Stelle, an der der Anmerkungssatz steht —
          eine Seite, die ihn wegformuliert, versteckte ihre Annotationen. */}
      <Ableseleiste className="mt-2" stelle={ableseStellen[ablesen.aktiv]} steuerung={ablesen}
        hinweis={(hinweis ?? `${einheit} · Jahr überfahren, antippen oder mit den Pfeiltasten wechseln.`)
          + ((annotationen ?? []).length ? " ⓘ-Jahre tragen eine Anmerkung." : "")} />

      {/* Lücken beschriftet die GRAFIK (GB-00) — nie einklappbar. */}
      {luecken.length > 0 && (
        <div className="mt-2 flex flex-col gap-1.5">
          {luecken.map((s) => (
            <LueckenFeld key={s.jahr} label={String(s.jahr)}
              grund={s.art === "luecke" ? s.punkt.fehlt : "in der Reihe ohne Wert und ohne Grund"}
              datum={s.art === "luecke" ? s.punkt.datum : undefined} />
          ))}
        </div>
      )}

      {/* Alle Werte zum Abschreiben. Anders als die Lücken-Hinweise darf
          das hier eingeklappt sein: Es ist dieselbe Auskunft ein zweites
          Mal, nicht die einzige. */}
      {tabelle && (
        <>
          <button type="button" onClick={() => setTabelleOffen((t) => !t)}
            aria-expanded={tabelleOffen} className="mt-2 text-[12px] font-semibold text-primary">
            {tabelleOffen ? "Tabelle ausblenden"
              : `Alle ${stellenListe.length} Werte als Tabelle`}
          </button>
          {tabelleOffen && (
            <div className="mt-2 grid grid-cols-[repeat(auto-fill,minmax(104px,1fr))] gap-x-3 gap-y-1 text-[11.5px] tabular-nums">
              {stellenListe.map((s) => (
                <span key={s.jahr} className="flex justify-between gap-2 border-t border-border/60 py-1">
                  <span className="font-mono text-muted-foreground">{s.jahr}</span>
                  {/* Eine Lücke bleibt auch in der Tabelle eine Lücke. */}
                  <span className={s.art === "wert" ? "" : "text-signal"}>
                    {s.art === "wert" ? fmt(s.punkt.wert) : "—"}
                  </span>
                </span>
              ))}
            </div>
          )}
        </>
      )}

      {/* Quellenzeile mit Beleg-Chip-Slot + Legende der Zweitreihe. */}
      {(beleg || zweitreihe) && (
        <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] leading-relaxed text-muted-foreground">
          {zweitreihe && (
            <span className="inline-flex items-center gap-1.5">
              <svg width="18" height="4" aria-hidden="true" className="flex-none">
                <line x1="0" y1="2" x2="18" y2="2" strokeWidth={1.5} strokeDasharray="5 4"
                  style={{ stroke: TON_ZWEIT }} />
              </svg>
              {zweitreihe.label}
            </span>
          )}
          {beleg && <span className="inline-flex items-center">Quelle{beleg}</span>}
        </p>
      )}
    </div>
  );
}

/** <ZeitreiheMini> — die Sparkline-Variante für Karten (GB-01 „mini",
 *  H3-02/H4-11: Beteiligungs-Karten, „Sparkline behält Endpunkt-Beschriftung").
 *
 *  Bewusst OHNE Ableseleiste und ohne Achsen: Auf einer Karte ist die große
 *  Kennzahl daneben die Auskunft, die Sparkline zeigt nur die Form des
 *  Verlaufs. Deshalb hier `role="img"` mit vollständigem `aria-label` (die
 *  Seite liefert den Satz) — es gibt keine Einzelziele, die verloren gingen.
 *  Lücken brechen die Linie über dasselbe `defined()`; ein Sparkline-Knick
 *  über eine Lücke hinweg wäre dieselbe Interpolation wie im großen Bild. */
export function ZeitreiheMini({ reihe, ariaLabel, format, className }: {
  reihe: JahrPunkt[];
  /** Ganzer Satz für die Vorlesehilfe — die Mini-Form ist EIN Bild. */
  ariaLabel: string;
  /** Formatiert die Endpunkt-Beschriftung (Vorgabe: `deZahl(v, 1)`). */
  format?: (wert: number) => string;
  className?: string;
}) {
  const { box, breite } = useBreite(220, 120);
  const stellen = normalisiere(reihe);
  const werte = stellen.filter(definiert);
  if (werte.length < 2) return null;

  const fmt = format ?? ((v: number) => deZahl(v, 1));
  const letzterWert = werte[werte.length - 1].punkt;
  const endText = fmt(letzterWert.wert);

  const H = 46, YTOP = 5, Y0 = 33, yJahr = 44;
  const W = breite;
  // Rechts Platz für die Endpunkt-Beschriftung (≈0,58 em je Zeichen + Punkt).
  const reserve = Math.ceil(endText.length * 10.5 * 0.58) + 12;
  const X0 = 2;
  const X1 = Math.max(W - reserve, X0 + 40);

  const von = stellen[0].jahr, bis = stellen[stellen.length - 1].jahr;
  const zahlen = werte.map((s) => s.punkt.wert);
  const lo = Math.min(...zahlen), hi = Math.max(...zahlen);
  const x = (jahr: number) => X0 + ((jahr - von) / Math.max(bis - von, 1)) * (X1 - X0);
  const y = (v: number) => (hi === lo ? (Y0 + YTOP) / 2 : Y0 - ((v - lo) / (hi - lo)) * (Y0 - YTOP));

  const linie = line<Stelle>()
    .defined(definiert)
    .x((s) => x(s.jahr))
    .y((s) => y((s as { punkt: JahrWert }).punkt.wert));

  const luecken = stellen.filter((s) => s.art !== "wert");

  return (
    <div ref={box} className={cn("min-w-0", className)}>
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img" aria-label={ariaLabel}>
        {/* Nulllinie, wenn die Reihe das Vorzeichen wechselt — sonst läse
            sich ein Verlust-zu-Gewinn-Verlauf wie eine beliebige Steigung. */}
        {lo < 0 && hi > 0 && (
          <line x1={X0} y1={y(0)} x2={X1} y2={y(0)} strokeWidth={1}
            className="stroke-border" strokeDasharray="2 3" />
        )}
        {/* Lücken als schmale Schraffur-Streifen — auch die Sparkline hat
            keine Erlaubnis, eine Lücke zu glätten. */}
        {luecken.map((s) => (
          <g key={s.jahr}>
            <foreignObject x={x(s.jahr) - 3} y={YTOP} width={6} height={Y0 - YTOP}>
              <div className="hh-schraffur h-full w-full opacity-70" />
            </foreignObject>
            <rect x={x(s.jahr) - 3} y={YTOP} width={6} height={Y0 - YTOP} fill="none"
              strokeDasharray="2 2" strokeWidth={0.8} className="stroke-signal" />
          </g>
        ))}
        <path d={linie(stellen) ?? undefined} fill="none" strokeWidth={1.8}
          strokeLinejoin="round" strokeLinecap="round" style={{ stroke: TON }} />
        <circle cx={x(letzterWert.jahr)} cy={y(letzterWert.wert)} r={3.5} style={{ fill: TON }} />
        {/* Endpunkt-Beschriftung — bleibt auf jedem Gerät (H4-11). */}
        <text x={X1 + 6} y={y(letzterWert.wert) + 3.5} fontSize={10.5} fontWeight={700}
          className="tabular-nums" style={{ fill: TON }}>{endText}</text>
        <text x={X0} y={yJahr} fontSize={9} className="fill-muted-foreground font-mono">{von}</text>
        <text x={X1} y={yJahr} textAnchor="end" fontSize={9}
          className="fill-muted-foreground font-mono">{bis}</text>
      </svg>
    </div>
  );
}
