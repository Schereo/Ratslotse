"use client";

// <Flussbild> — Quellen → EIN Topf → Empfänger (GB-07).
//
// Bewusst KEIN Sankey, und d3-sankey wird nicht installiert: Ein
// durchgehendes Quer-Band von „Gewerbesteuer" nach „Soziales" behauptete
// eine Zweckbindung, die es im kommunalen Haushalt nicht gibt — alle
// Einnahmen finanzieren gemeinsam alle Ausgaben. Alle Kurven enden deshalb
// im EINEN Kollektorknoten; kein Band überquert die Mitte. Dass alles durch
// einen Topf läuft, IST die Aussage des Bildes.
//
// Entstanden als `components/haushalt/flussbild.tsx` (Design H-18); mit dem
// Baukasten hierher verallgemeinert. HIER wohnt die reine Geometrie und
// Interaktion — Seiten (und der Haushalts-Adapter) liefern fertige Bänder,
// eine Skala und die Formatierung; gerechnet wird hier nichts nach.
//
// Die Regeln, an denen sich alles ausrichtet (unverändert übernommen):
//
//  1. EINE SKALA. Links und rechts rechnen mit demselben Wert-pro-Pixel-
//     Faktor; er kommt aus der Seite mit den MEISTEN Zwischenräumen und gilt
//     für beide. Die kürzere Seite bleibt kürzer, statt gestreckt zu werden.
//  2. DIE VIEWBOX IST SO BREIT WIE DER CONTAINER. Ein fester Wert skalierte
//     das ganze Bild samt Schrift (12-px-Labels landeten als 8,8 px auf dem
//     Schirm). Gemessen statt geraten.
//  3. MOBIL WIRD UMGEBAUT, NICHT GESCHRUMPFT (`richtungMobil: senkrecht`,
//     eingebaut): Unter 620 px Containerbreite gibt es keine Bänder mehr,
//     sondern gestapelte Listen mit dem Topf dazwischen — dieselben Zahlen,
//     dieselbe Bündelung, nur ohne Geometrie, die auf 320 px unlesbar wäre.
//  4. KLEINE POSTEN BÜNDELN, NICHT VERSCHWEIGEN: Unter `mindestAnteil` der
//     Skala wandert ein Posten in den aufklappbaren Sammelposten. Eine
//     Lesbarkeits-, keine Relevanzentscheidung — ein 4-px-Band ist seiner
//     Zeile nicht zuzuordnen. Differenz-Bänder werden NIE gebündelt: Genau
//     sie erklären, warum das Bild aussieht, wie es aussieht.
//
// KEINE BEWERTUNGSFARBEN: Links trägt die Einnahmen-Rampe (`--hh-ein-*`),
// rechts die Ausgaben-Rampe (`--hh-aus-*`) — Kategorien, keine Noten.
// Signal-Orange steht nur an den Differenz-Bändern (Schraffur, gestrichelte
// Kante).

import { useEffect, useId, useRef, useState } from "react";
import { ArrowDown, X } from "lucide-react";
import { cn } from "@/lib/utils";

export type FlussPosten = {
  id: string;
  /** Kurzform für die Grafik. */
  label: string;
  /** Volle Bezeichnung — Panel, title, aria. */
  lang: string;
  wert: number;
  /** `posten` = Kategorie (Rampe) · `difference` = Ehrlichkeits-Band
   *  („aus dem Ersparten", „nicht aufgeschlüsselt"): Schraffur + Signal. */
  art: "posten" | "difference";
};

export type FlussSeiteDaten = {
  /** Überschrift der Listen-Fassung: „Woher das Geld kommt". */
  titel: string;
  /** Ecken-Label der Band-Fassung: „Woher". */
  kurz: string;
  /** Zählangabe neben der Überschrift: „Einnahmearten". */
  hint: string;
  /** Kopf des aufgeklappten Sammelpostens: „Die kleineren Einnahmearten". */
  sammelTitel: string;
  baender: FlussPosten[];
  gesamt: number;
};

export type FlussTopf = {
  /** Beschriftung im Bild: „Eine Kasse". */
  kurz: string;
  /** Überschrift des Topf-Blocks in der Listen-Fassung. */
  lang: string;
  wert: number;
  /** Der Satz IM Knoten (Band-Fassung, senkrecht): „Alles Geld der Stadt". */
  satz: string;
  /** Der Satz im Topf-Block der Listen-Fassung. */
  note: string;
};

type SeitenLage = "links" | "rechts";

/** Ab dieser Containerbreite gibt es Bänder; darunter kippt das Bild
 *  senkrecht (Listen). */
const SCHWELLE_BREIT = 620;

/** Die Farbrampe wird über die tatsächliche Bänderzahl VERTEILT, statt Stufe
 *  für Stufe abgeräumt zu werden — und sie endet vor ihrem hellsten Ende:
 *  Ein freistehendes Band in einem 90-%-Ton ist auf weißer Karte nicht mehr
 *  da. Bei mehr Bändern als Stufen wiederholt sich ein Ton — verkraftbar,
 *  weil jedes Band seine Beschriftung trägt und die Farbe hier nichts
 *  kodiert außer „nicht dasselbe". */
const LETZTE_STUFE: Record<SeitenLage, number> = { links: 4, rechts: 6 };

const stufe = (lage: SeitenLage, i: number, n: number) =>
  n <= 1 ? 0 : Math.round((i / (n - 1)) * LETZTE_STUFE[lage]);

const farbe = (lage: SeitenLage, i: number, n: number, art: FlussPosten["art"]) => {
  if (art !== "posten") return undefined; // Differenz-Bänder tragen ihr Muster
  const s = stufe(lage, i, n);
  return lage === "links" ? `var(--hh-ein-${s})` : `var(--hh-aus-${s})`;
};

/** Kleine Posten bündeln, damit die Bänder beschriftbar bleiben (Regel 4). */
export function fasseKleineZusammen(
  baender: FlussPosten[], skala: number, mindestAnteil: number,
): { gezeigt: FlussPosten[]; gebuendelt: FlussPosten[] } {
  const gross = baender.filter(
    (b) => b.art !== "posten" || b.wert >= mindestAnteil * skala);
  const gebuendelt = baender.filter(
    (b) => b.art === "posten" && b.wert < mindestAnteil * skala);
  if (gebuendelt.length < 2) return { gezeigt: baender, gebuendelt: [] };
  const sammel: FlussPosten = {
    id: "weitere",
    label: `${gebuendelt.length} weitere`,
    lang: `${gebuendelt.length} weitere Posten`,
    wert: gebuendelt.reduce((s, b) => s + b.wert, 0),
    art: "posten",
  };
  // Sammelposten und Differenz-Bänder ans Ende: Der Stapel liest sich von
  // oben nach unten „groß nach klein", die Sonderfälle stehen unten.
  const posten = gross.filter((b) => b.art === "posten");
  const sonder = gross.filter((b) => b.art !== "posten");
  return { gezeigt: [...posten, sammel, ...sonder], gebuendelt };
}

/** Ein Band als Schlauch konstanter Dicke: links am Knoten, rechts am Topf.
 *  Zwei Kubiken, oben hin und unten zurück. */
function schlauch(x0: number, y0: number, x1: number, y1: number, dicke: number) {
  const mx = (x0 + x1) / 2;
  return [
    `M${x0},${y0}`,
    `C${mx},${y0} ${mx},${y1} ${x1},${y1}`,
    `L${x1},${y1 + dicke}`,
    `C${mx},${y1 + dicke} ${mx},${y0 + dicke} ${x0},${y0 + dicke}`,
    "Z",
  ].join(" ");
}

/** Beschriftungen entzerren, ohne die Reihenfolge zu ändern: erst von oben
 *  nach unten auf Mindestabstand schieben, dann den Überlauf unten wieder
 *  nach oben zurückdrücken. Ohne das kleben die Zeilen dünner Bänder
 *  aufeinander, sobald zwei kleine Posten benachbart sind. */
function entzerre(zentren: number[], mindest: number, unten: number): number[] {
  const y = [...zentren];
  for (let i = 1; i < y.length; i++) y[i] = Math.max(y[i], y[i - 1] + mindest);
  if (y.length) y[y.length - 1] = Math.min(y[y.length - 1], unten);
  for (let i = y.length - 2; i >= 0; i--) y[i] = Math.min(y[i], y[i + 1] - mindest);
  return y;
}

/** Eine Seite als gestapelte Bänder: Position und Dicke jedes Bandes. */
function stapeln(baender: FlussPosten[], faktor: number, gap: number, start: number) {
  let y = start;
  return baender.map((b) => {
    const dicke = b.wert * faktor;
    const oben = y;
    y += dicke + gap;
    return { band: b, oben, dicke, mitte: oben + dicke / 2 };
  });
}

/** Die aufgeklappte Auflistung eines Sammelpostens — dieselbe Grammatik wie
 *  die Detail-Box des Gegenbalkens (Karte mit Schließen-Knopf). */
function SammelPanel({ lage, titel, teile, skala, format, unit, onClose }: {
  lage: SeitenLage; titel: string; teile: FlussPosten[]; skala: number;
  format: (w: number) => string; unit: string; onClose: () => void;
}) {
  const groesste = Math.max(...teile.map((t) => t.wert), 1);
  return (
    <div className="mt-3 rounded-xl border border-border bg-card p-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {titel}
        </p>
        <button type="button" onClick={onClose} aria-label="Schließen"
          className="-mr-0.5 -mt-0.5 rounded p-0.5 text-muted-foreground hover:text-foreground">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="mt-2 flex flex-col gap-1.5">
        {[...teile].sort((a, b) => b.wert - a.wert).map((t) => (
          <div key={t.id} className="grid grid-cols-[minmax(0,1fr)_70px_auto] items-center gap-x-2.5">
            <span className="truncate text-[12px]" title={t.lang}>{t.lang}</span>
            <span className="h-1.5 rounded-full bg-muted">
              <span className="block h-full rounded-full"
                style={{ width: `${(t.wert / groesste) * 100}%`, background: farbe(lage, 2, 4, "posten") }} />
            </span>
            <span className="whitespace-nowrap text-right text-[12px] tabular-nums">
              {format(t.wert)}&#8239;{unit}
            </span>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">
        Zusammen {format(teile.reduce((s, t) => s + t.wert, 0))}&#8239;{unit} —
        {" "}{((teile.reduce((s, t) => s + t.wert, 0) / skala) * 100).toLocaleString("de-DE", { maximumFractionDigits: 1 })}
        &nbsp;% von allem.
      </p>
    </div>
  );
}

/** Eine Zeile der Listenfassung: Name, Balken auf der gemeinsamen Skala,
 *  Betrag. Der Balken misst gegen dieselbe Skala wie die Bänder — sonst
 *  erzählten Listen- und Bandfassung zwei verschiedene Geschichten. */
function ListenZeile({ band, lage, rang, count, skala, format, unit, sammel, offen, onToggle }: {
  band: FlussPosten; lage: SeitenLage; rang: number; count: number; skala: number;
  format: (w: number) => string; unit: string;
  sammel: boolean; offen: boolean; onToggle: () => void;
}) {
  const anteil = (band.wert / skala) * 100;
  const inhalt = (
    <>
      <span className="flex items-baseline justify-between gap-2.5">
        <span className={cn("min-w-0 truncate text-[12.5px]",
          sammel && "font-semibold text-primary underline decoration-dotted")} title={band.lang}>
          {band.art === "posten" ? band.label : band.lang}
        </span>
        <span className="flex-none text-[12px] tabular-nums">
          {format(band.wert)}<span className="text-muted-foreground">&#8239;{unit}</span>
        </span>
      </span>
      <span className="mt-1 block h-2.5 w-full">
        {band.art === "posten" ? (
          <span className="block h-full rounded-[3px]"
            style={{ width: `${anteil}%`, background: farbe(lage, rang, count, band.art) }} />
        ) : (
          <span className="hh-schraffur block h-full rounded-[3px] border border-dashed border-signal"
            style={{ width: `${anteil}%` }} />
        )}
      </span>
    </>
  );
  return sammel ? (
    <button type="button" onClick={onToggle} aria-expanded={offen} className="block w-full text-left">
      {inhalt}
    </button>
  ) : (
    <div>{inhalt}</div>
  );
}

/** Der Kollektorknoten als eigener Block (Listen-Fassung) — er trägt die
 *  Aussage, deshalb steht sie in ihm und nicht darunter. */
function TopfBlock({ topf, format, unit }: {
  topf: FlussTopf; format: (w: number) => string; unit: string;
}) {
  return (
    <div className="my-3 rounded-xl border border-border bg-muted/70 px-3 py-2.5">
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        {topf.lang}
      </p>
      <p className="mt-1 font-display text-[19px] font-bold tabular-nums tracking-tight">
        {format(topf.wert)}<span className="text-xs font-semibold text-muted-foreground">&#8239;{unit}&nbsp;€</span>
      </p>
      <p className="mt-1 text-[11.5px] leading-relaxed text-foreground/80">
        {topf.note}
      </p>
    </div>
  );
}

/** Listen-Fassung für schmale Bildschirme: Stapel, der Topf dazwischen —
 *  dieselben Zahlen und dieselbe Bündelung wie die Bänder. */
function Listen({ seiten, topf, empfaenger, skala, mindestAnteil, format, unit, offen, setOffen }: {
  seiten: { lage: SeitenLage; daten: FlussSeiteDaten }[];
  topf: FlussTopf;
  empfaenger?: string;
  skala: number;
  mindestAnteil: number;
  format: (w: number) => string;
  unit: string;
  offen: SeitenLage | null;
  setOffen: (s: SeitenLage | null) => void;
}) {
  return (
    <div>
      {seiten.map(({ lage, daten }, si) => {
        const { gezeigt, gebuendelt } = fasseKleineZusammen(daten.baender, skala, mindestAnteil);
        return (
          <div key={lage}>
            {si === 1 && <TopfBlock topf={topf} format={format} unit={unit} />}
            <div className="mb-2 flex items-baseline justify-between gap-3">
              <p className="text-[12.5px] font-semibold">{daten.titel}</p>
              <span className="font-mono text-[10px] uppercase text-muted-foreground">
                {daten.hint} · {format(daten.gesamt)}&#8239;{unit}
              </span>
            </div>
            <div className="flex flex-col gap-2">
              {gezeigt.map((b, i) => (
                <ListenZeile key={b.id} band={b} lage={lage} rang={i} count={gezeigt.length}
                  skala={skala} format={format} unit={unit}
                  sammel={b.id === "weitere"} offen={offen === lage}
                  onToggle={() => setOffen(offen === lage ? null : lage)} />
              ))}
            </div>
            {offen === lage && gebuendelt.length > 0 && (
              <SammelPanel lage={lage} titel={daten.sammelTitel} teile={gebuendelt}
                skala={skala} format={format} unit={unit}
                onClose={() => setOffen(null)} />
            )}
          </div>
        );
      })}
      {seiten.length === 1 && (
        <>
          <TopfBlock topf={topf} format={format} unit={unit} />
          {empfaenger && (
            <p className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
              <ArrowDown aria-hidden className="h-3.5 w-3.5" /> {empfaenger}
            </p>
          )}
        </>
      )}
    </div>
  );
}

export function Flussbild({
  links, rechts, empfaenger, topf, skala, format, unit = "Mio. €",
  mindestAnteil = 0.05, beschreibung, className,
}: {
  /** Die Quellen — laufen in den Topf (Einnahmen-Rampe). */
  links: FlussSeiteDaten;
  /** Die Empfänger — laufen aus dem Topf heraus (Ausgaben-Rampe). Ohne sie
   *  endet das Bild im Topf, und `empfaenger` benennt, wohin es weitergeht. */
  rechts?: FlussSeiteDaten;
  /** Nur ohne `rechts`: „13 Teilhaushalte" — ein Pfeil, kein Band. */
  empfaenger?: string;
  topf: FlussTopf;
  /** Gemeinsame Achse beider Seiten — von der Seite gerechnet, nie hier. */
  skala: number;
  /** Fertige de-DE-Formatierung eines Wertes (GB-00: Intl, `format.ts`). */
  format: (wert: number) => string;
  /** Suffix hinter formatierten Werten („Mio."). */
  unit?: string;
  /** Unter diesem Anteil der Skala wandert ein Posten in den Sammelposten. */
  mindestAnteil?: number;
  /** Der ganze Satz für die Vorlesehilfe der Band-Fassung. */
  beschreibung: string;
  className?: string;
}) {
  const [offen, setOffen] = useState<SeitenLage | null>(null);
  const musterId = useId().replace(/:/g, "");

  // Containerbreite messen — die viewBox bekommt genau diesen Wert, damit
  // eine SVG-Einheit ein echtes Pixel ist und die Schrift nicht mitskaliert.
  const box = useRef<HTMLDivElement>(null);
  const [breite, setBreite] = useState(880);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const pruefe = () => setBreite(Math.max(el.clientWidth, 280));
    pruefe();
    const ro = new ResizeObserver(pruefe);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const schmal = breite < SCHWELLE_BREIT;
  const seiten: { lage: SeitenLage; daten: FlussSeiteDaten }[] = [
    { lage: "links", daten: links },
    ...(rechts ? [{ lage: "rechts" as const, daten: rechts }] : []),
  ];

  return (
    <div className={className}>
      <div ref={box}>
        {schmal || !rechts ? (
          // Ohne rechte Seite gibt es keine Band-Geometrie zu zeigen — die
          // Listen-Fassung trägt den Ein-Seiten-Fall auf jeder Breite.
          <Listen seiten={seiten} topf={topf} empfaenger={empfaenger} skala={skala}
            mindestAnteil={mindestAnteil} format={format} unit={unit}
            offen={offen} setOffen={setOffen} />
        ) : (
          <Baender links={links} rechts={rechts} topf={topf} skala={skala}
            mindestAnteil={mindestAnteil} format={format} unit={unit}
            breite={breite} musterId={musterId} beschreibung={beschreibung}
            offen={offen} setOffen={setOffen} />
        )}
      </div>

      {offen && !schmal && rechts && (() => {
        const s = offen === "links" ? links : rechts;
        const { gebuendelt } = fasseKleineZusammen(s.baender, skala, mindestAnteil);
        return gebuendelt.length ? (
          <SammelPanel lage={offen} titel={s.sammelTitel} teile={gebuendelt}
            skala={skala} format={format} unit={unit}
            onClose={() => setOffen(null)} />
        ) : null;
      })()}
    </div>
  );
}

/** Die Bandfassung. Eigene Komponente, weil sie das ganze Koordinatensystem
 *  aufspannt und sonst die Lesbarkeit der Hülle frisst. */
function Baender({ links, rechts, topf, skala, mindestAnteil, format, unit, breite, musterId, beschreibung, offen, setOffen }: {
  links: FlussSeiteDaten;
  rechts: FlussSeiteDaten;
  topf: FlussTopf;
  skala: number;
  mindestAnteil: number;
  format: (w: number) => string;
  unit: string;
  breite: number;
  musterId: string;
  beschreibung: string;
  offen: SeitenLage | null;
  setOffen: (s: SeitenLage | null) => void;
}) {
  const gl = fasseKleineZusammen(links.baender, skala, mindestAnteil);
  const gr = fasseKleineZusammen(rechts.baender, skala, mindestAnteil);
  const nL = gl.gezeigt.length, nR = gr.gezeigt.length;

  const W = breite;
  const LABEL = Math.round(Math.min(Math.max(W * 0.215, 126), 206));
  const KNOTEN = 8;
  const TOPF = W < 780 ? 44 : 56;
  const bandBreite = Math.max((W - 2 * LABEL - 2 * KNOTEN - TOPF) / 2, 40);
  const xKnotenL = LABEL;
  const xBandL = LABEL + KNOTEN;
  const xTopf = xBandL + bandBreite;
  const xTopfEnde = xTopf + TOPF;
  const xBandRende = xTopfEnde + bandBreite;

  const GAP = 6;
  const ZEILE = 16; // Mindestabstand zweier Beschriftungen
  const OBEN = 34, UNTEN = 30;
  const stapelHoehe = Math.max(300, 22 * Math.max(nL, nR));
  // EINE Skala: Der Faktor kommt aus der Seite mit den meisten Zwischenräumen
  // und gilt für beide. Die kürzere Seite bleibt kürzer.
  const nutz = stapelHoehe - GAP * Math.max(nL - 1, nR - 1, 0);
  const faktor = nutz / skala;
  const hoeheL = gl.gezeigt.reduce((s, b) => s + b.wert * faktor, 0) + GAP * (nL - 1);
  const hoeheR = gr.gezeigt.reduce((s, b) => s + b.wert * faktor, 0) + GAP * (nR - 1);
  const hoeheTopf = skala * faktor;
  const mitteY = OBEN + stapelHoehe / 2;
  const H = OBEN + stapelHoehe + UNTEN;

  const stapelL = stapeln(gl.gezeigt, faktor, GAP, mitteY - hoeheL / 2);
  const stapelR = stapeln(gr.gezeigt, faktor, GAP, mitteY - hoeheR / 2);
  const topfOben = mitteY - hoeheTopf / 2;
  // Am Topf liegen die Bänder LÜCKENLOS aneinander — das ist der Punkt: Innen
  // ist es ein Betrag, keine Sammlung von Töpfchen.
  const slotL = stapeln(gl.gezeigt, faktor, 0, topfOben);
  const slotR = stapeln(gr.gezeigt, faktor, 0, topfOben);

  const labelL = entzerre(stapelL.map((s) => s.mitte), ZEILE, OBEN + stapelHoehe);
  const labelR = entzerre(stapelR.map((s) => s.mitte), ZEILE, OBEN + stapelHoehe);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img"
      aria-label={beschreibung}>
      <defs>
        {/* Schraffur wie .hh-schraffur, aber als SVG-Muster — eine CSS-
            Hintergrundfläche greift auf einem Pfad nicht. */}
        <pattern id={`schraffur-${musterId}`} width="6" height="6"
          patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" fill="hsl(var(--card))" />
          <line x1="0" y1="0" x2="0" y2="6" strokeWidth="3" stroke="hsl(19 92% 55% / 0.35)" />
        </pattern>
      </defs>

      {/* Bänder zuerst, damit Knoten und Topf sauber darüber liegen. */}
      {stapelL.map((s, i) => (
        <path key={s.band.id}
          d={schlauch(xBandL, s.oben, xTopf, slotL[i].oben, s.dicke)}
          fill={s.band.art === "posten" ? farbe("links", i, nL, s.band.art) : `url(#schraffur-${musterId})`}
          opacity={s.band.art === "posten" ? 0.82 : 0.9}
          stroke={s.band.art === "posten" ? "none" : "hsl(var(--signal))"}
          strokeDasharray={s.band.art === "posten" ? undefined : "4 3"}
          strokeWidth={s.band.art === "posten" ? 0 : 1} />
      ))}
      {stapelR.map((s, i) => (
        <path key={s.band.id}
          d={schlauch(xTopfEnde, slotR[i].oben, xBandRende, s.oben, s.dicke)}
          fill={s.band.art === "posten" ? farbe("rechts", i, nR, s.band.art) : `url(#schraffur-${musterId})`}
          opacity={s.band.art === "posten" ? 0.82 : 0.9}
          stroke={s.band.art === "posten" ? "none" : "hsl(var(--signal))"}
          strokeDasharray={s.band.art === "posten" ? undefined : "4 3"}
          strokeWidth={s.band.art === "posten" ? 0 : 1} />
      ))}

      {/* Knoten außen: die Kante, an der ein Posten anfasst. */}
      {stapelL.map((s, i) => (
        <rect key={s.band.id} x={xKnotenL} y={s.oben} width={KNOTEN} height={Math.max(s.dicke, 1.5)}
          rx={2} fill={s.band.art === "posten" ? farbe("links", i, nL, s.band.art) : "hsl(var(--signal))"} />
      ))}
      {stapelR.map((s, i) => (
        <rect key={s.band.id} x={xBandRende} y={s.oben} width={KNOTEN} height={Math.max(s.dicke, 1.5)}
          rx={2} fill={s.band.art === "posten" ? farbe("rechts", i, nR, s.band.art) : "hsl(var(--signal))"} />
      ))}

      {/* Der Kollektorknoten: eine geschlossene Fläche, kein Durchgang. */}
      <rect x={xTopf} y={topfOben} width={TOPF} height={hoeheTopf} rx={6}
        className="fill-muted stroke-border" strokeWidth={1} />
      <text x={xTopf + TOPF / 2} y={topfOben - 12} textAnchor="middle" fontSize={10.5}
        className="fill-muted-foreground font-mono" letterSpacing="0.09em">
        {topf.kurz.toUpperCase()}
      </text>
      <text x={xTopf + TOPF / 2} y={topfOben + hoeheTopf + 17} textAnchor="middle"
        fontSize={13} fontWeight={700} className="fill-foreground">
        {format(topf.wert)}
      </text>
      <text x={xTopf + TOPF / 2} y={topfOben + hoeheTopf + 29} textAnchor="middle"
        fontSize={10} className="fill-muted-foreground font-mono">
        {unit.toUpperCase()} EURO
      </text>
      <text x={xTopf + TOPF / 2} y={topfOben + hoeheTopf / 2} textAnchor="middle"
        fontSize={11.5} fontWeight={600} className="fill-muted-foreground"
        transform={`rotate(-90 ${xTopf + TOPF / 2} ${topfOben + hoeheTopf / 2})`}>
        {topf.satz}
      </text>

      {/* Beschriftungen als HTML im foreignObject: echtes Kürzen mit Auslassung
          statt abgeschnittener Ziffern (eine gekappte 169,2 liest sich als 16). */}
      {stapelL.map((s, i) => (
        <Beschriftung key={s.band.id} x={0} y={labelL[i]} breite={LABEL - 10} rechtsbuendig
          band={s.band} format={format} istSammel={s.band.id === "weitere"} offen={offen === "links"}
          onToggle={() => setOffen(offen === "links" ? null : "links")} />
      ))}
      {stapelR.map((s, i) => (
        <Beschriftung key={s.band.id} x={xBandRende + KNOTEN + 10} y={labelR[i]} breite={LABEL - 10}
          band={s.band} format={format} istSammel={s.band.id === "weitere"} offen={offen === "rechts"}
          onToggle={() => setOffen(offen === "rechts" ? null : "rechts")} />
      ))}

      <text x={0} y={16} fontSize={11.5} fontWeight={600} className="fill-foreground">{links.kurz}</text>
      <text x={W} y={16} textAnchor="end" fontSize={11.5} fontWeight={600} className="fill-foreground">{rechts.kurz}</text>
    </svg>
  );
}

function Beschriftung({ x, y, breite, band, format, rechtsbuendig = false, istSammel, offen, onToggle }: {
  x: number; y: number; breite: number; band: FlussPosten;
  format: (w: number) => string;
  rechtsbuendig?: boolean; istSammel: boolean; offen: boolean; onToggle: () => void;
}) {
  const inhalt = (
    <>
      <span className={cn("min-w-0 truncate", istSammel && "font-semibold text-primary underline decoration-dotted")}
        title={band.lang}>
        {band.art === "posten" ? band.label : band.lang}
      </span>
      <span className="flex-none tabular-nums text-muted-foreground">{format(band.wert)}</span>
    </>
  );
  return (
    <foreignObject x={x} y={y - 9} width={breite} height={19}>
      {istSammel ? (
        <button type="button" onClick={onToggle} aria-expanded={offen}
          className={cn("flex w-full items-baseline gap-1.5 text-[11.5px] leading-[19px]",
            rechtsbuendig && "justify-end")}>
          {inhalt}
        </button>
      ) : (
        <div className={cn("flex w-full items-baseline gap-1.5 text-[11.5px] leading-[19px]",
          rechtsbuendig && "justify-end")}>
          {inhalt}
        </div>
      )}
    </foreignObject>
  );
}
