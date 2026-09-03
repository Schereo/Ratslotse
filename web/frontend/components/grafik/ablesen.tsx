"use client";

// <Ableseleiste> — der gemeinsame Ablese-Baustein des Grafik-Baukastens
// (GB-00): ersetzt Tooltips überall. Desktop Hover, mobil sticky Tap-Zeile,
// immer Pfeiltasten — eine Implementierung, drei Geräte.
//
// Entstanden in der Haushalts-Runde als `components/haushalt/ablesen.tsx`;
// mit dem Baukasten hierher verallgemeinert. Neu gegenüber der Haushalts-
// Fassung sind nur zwei Dinge:
//  * Die STICKY-WERTZEILE (H4-A): unter 744 px bleibt die Leiste am unteren
//    Rand sichtbar, solange ihre Karte im Bild ist — eingebaut, kein Prop.
//    Das CSS dazu ist `.gb-ablese-leiste` in `app/globals.css`; der Abstand
//    zur Tab-Leiste kommt aus `TABLEISTE_HOEHE` (nie eine eigene Zahl).
//  * `bisectCenter` aus d3-array sucht die nächstgelegene Stelle zum
//    Zeiger — O(log n) statt Linear-Scan, der Ableseleisten-Helfer aus
//    GB-15. Voraussetzung: `x(i)` wächst mit i (alle Reihen des Baukastens
//    laufen von links nach rechts).
//
// WARUM EINE LEISTE UND KEIN TOOLTIP.
// Ein Tooltip ist immer die zweite Wahl: Er existiert nur, solange jemand
// darauf zeigt. Wer die Seite ausdruckt, einen Screenshot macht oder mit einem
// Screenreader liest, bekommt ihn nie zu sehen. Deshalb steht der Wert hier in
// einer Leiste, die IMMER etwas anzeigt — im Ruhezustand das jüngste Jahr. Sie
// ist echter Text im Layout, kein Overlay. Zeigen, Tippen oder die Pfeiltasten
// wechseln nur, WELCHE Stelle sie zeigt.
//
// Damit ist auch die alte Falle erledigt, an der eine Box hing, die sich beim
// Hovern öffnete und wieder zuklappte, sobald der Zeiger sie erreichen wollte:
// Es gibt nichts, wohin der Zeiger wandern müsste. Die Leiste steht fest im
// Fluss, die Fläche darüber fängt nur den Zeiger ab.
//
// DREI EINGABEARTEN, EINE MECHANIK.
//  - **Maus**: `pointermove` über der Zeichenfläche wählt die nächstgelegene
//    Stelle; `pointerleave` setzt zurück. Das Zurücksetzen gilt AUSDRÜCKLICH
//    NUR für die Maus — auf dem Telefon feuert `pointerleave` unmittelbar nach
//    jedem Tippen, und die Leiste sprang sonst sofort wieder zurück.
//  - **Touch**: Tippen wählt, Wischen mit aufliegendem Finger schrubbt durch
//    die Reihe. Die Fläche hat `touch-action: pan-y`, damit die Seite senkrecht
//    weiter scrollt — sonst klebte der Finger an der Grafik fest. Ein
//    3-px-Datenpunkt wäre kein Ziel für einen Finger; das Ziel ist deshalb ein
//    Streifen über die volle Höhe der Zeichenfläche.
//  - **Tastatur**: Ein Tabstopp führt in die Grafik, danach bewegen ←/→
//    (Pos1/Ende, Esc) die Auswahl — die übliche Grammatik für eine Reihe
//    gleichartiger Elemente. 28 einzelne Tabstopps für 28 Jahre wären keine
//    Barrierefreiheit, sondern eine Sperre. Der Fokusring wird selbst
//    gezeichnet, weil SVG-Elemente keinen verlässlichen bekommen, und hängt an
//    `:focus-visible` — nach einem Mausklick blitzt also nichts auf.
//
// WAS DER SCREENREADER HÖRT. Jede Stelle trägt ihr `aria-label` mit allen
// Werten. Die Grafik ist deshalb `role="group"` und nicht `role="img"`: Ein
// `img` fasst seinen Inhalt zu einem einzigen Objekt zusammen, die Stellen
// darin wären für die Vorlesehilfe unsichtbar. Die Gesamtbeschreibung hängt
// als `aria-describedby` an einem sr-only-Absatz daneben (`AbleseTexte`).

import { useCallback, useId, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { bisectCenter } from "d3-array";
import { TABLEISTE_HOEHE } from "@/components/nav";
import { deZahl } from "@/components/grafik/format";
import { cn } from "@/lib/utils";

export type AbleseWert = {
  /** Kurzer Name der Größe, z. B. „Einnahmen". */
  label: string;
  /** Fertig formatiert (de-DE) — die Leiste rechnet nichts. */
  value: string;
  /** Farbpunkt vor dem Label; üblicherweise `var(--hh-ein-0)`. */
  farbe?: string;
  /** Signal-Orange = „hier ist die Differenz", nie eine Bewertung. */
  signal?: boolean;
};

export type AbleseStelle = {
  /** Steht links in der Leiste, üblicherweise die Jahreszahl. */
  title: string;
  werte: AbleseWert[];
  /** Der ganze Satz für die Vorlesehilfe. */
  vorlesen: string;
  /** Was an dieser Stelle passiert ist — der Anmerkungssatz zum ⓘ im Bild.
   *  Die Leiste zeigt ihn als eigene Zeile, sobald die Stelle gewählt ist:
   *  Ein Tipp aufs ⓘ wählt das Jahr (die Fangfläche liegt darüber), und die
   *  Erklärung erscheint da, wo ohnehin alle Werte der Stelle stehen — statt
   *  dauerhaft unter der Grafik (Tims Entscheid 18.08.2026). Kein Tooltip:
   *  Die Zeile ist Text im Layout, bleibt bis zur nächsten Wahl stehen und
   *  ist per Pfeiltasten genauso erreichbar wie per Finger. */
  anmerkung?: string;
};

/** Ein Punkt, der bei der aktiven Stelle einen Ring bekommt. */
export type AbleseMarke = { y: number; farbe: string };

export type AbleseSteuerung = {
  /** Index der Stelle, die die Leiste gerade zeigt. */
  aktiv: number;
  /** Hat jemand aktiv gewählt — oder ruht die Leiste auf ihrer Vorgabe? */
  gewaehlt: boolean;
  waehle: (i: number) => void;
  zuruecksetzen: () => void;
  tastatur: boolean;
  setTastatur: (an: boolean) => void;
};

/** Zustand einer Ablese-Grafik. `standard` ist die Stelle im Ruhezustand —
 *  üblicherweise die jüngste, damit die Leiste nie leer dasteht. */
export function useAblesen(count: number, standard: number): AbleseSteuerung {
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  const [tastatur, setTastatur] = useState(false);
  const grenze = Math.max(count - 1, 0);
  const klemme = (i: number) => Math.min(Math.max(i, 0), grenze);
  // Geklemmt statt roh: Wechselt der Datensatz unter einer offenen Auswahl
  // (Jahres-Umschalter), zeigte die Leiste sonst auf eine Stelle, die es nicht
  // mehr gibt.
  const aktiv = klemme(gewaehlt ?? standard);

  const waehle = useCallback((i: number) => {
    setGewaehlt(Math.min(Math.max(i, 0), Math.max(count - 1, 0)));
  }, [count]);
  const zuruecksetzen = useCallback(() => setGewaehlt(null), []);

  return { aktiv, gewaehlt: gewaehlt != null, waehle, zuruecksetzen, tastatur, setTastatur };
}

/** Die Farbmarke einer Ablesekarte: Farbe, Schraffur (Sammelposten) oder
 *  nichts — dann steht ein leerer Rahmen, damit der Text nicht springt. */
export type AbleseMarkeKarte = {
  farbe?: string;
  schraffiert?: boolean;
  /** Eckig für Flächen (Kacheln, Segmente), rund für Reihen (Vorgabe). */
  eckig?: boolean;
};

const NEUTRALE_SCHRAFFUR =
  "repeating-linear-gradient(135deg, hsl(var(--muted-foreground) / 0.16) 0 3px, transparent 3px 6px)";

/** <Ablesekarte> — die Auskunft unter dem Bild, als Karte (seit 02.09.).
 *
 *  Bis dahin war die Ableseleiste ein grauer Kasten mit 12,5-px-Mono: Jahr,
 *  dann Werte in einer Zeile. Sie sah aus wie ein Hinweis, nicht wie die
 *  Auskunft — obwohl sie die EINZIGE Stelle ist, an der der Wert einer Stelle
 *  steht (GB-00: kein Tooltip). Jetzt trägt sie ihn wie eine Kennzahl:
 *  Farbmarke, Name (das Jahr, die Kachel, die Säule), eine Zusatzzeile, die
 *  Hauptzahl in Bricolage mit ihrer Einheit darunter, Nebenwerte als kleine
 *  Zeile, wo die Fläche ein Ganzes zerlegt ein Anteilsbalken.
 *
 *  Eine Karte für alle Grafiken: Kachelfläche, Zeitreihe, Naht-Säulen,
 *  Ketten-Matrix, Labor — und die künftigen. Wer sie ändert, ändert alle;
 *  das ist der Zweck. Sie rechnet nichts und formatiert nichts — die Grafik
 *  liefert fertige Zeichenketten. */
export function Ablesekarte({
  marke, name, zusatz, wert, wertLabel, wertSignal, nebenwerte, anteil, anmerkung,
  note, haftet = false, live = false, className,
}: {
  marke?: AbleseMarkeKarte;
  name: ReactNode;
  zusatz?: ReactNode;
  /** Die Hauptzahl, fertig formatiert („337,0" / „—"). */
  wert: string;
  /** Was unter der Hauptzahl steht: die Einheit oder der Name der Größe. */
  wertLabel?: string;
  /** Signal-Orange: die Hauptzahl ist eine Differenz oder eine Lücke. */
  wertSignal?: boolean;
  /** Weitere Werte der Stelle („ggü. Vorjahr +42,1", die Zweitreihe). */
  nebenwerte?: AbleseWert[];
  /** Anteil in Prozent (0–100) — als schmaler Balken und als Zahl. */
  anteil?: number;
  /** Der Anmerkungssatz zum ⓘ — eine eigene Zeile, nie ein Tooltip. */
  anmerkung?: string;
  /** Der Bedien-Hinweis, ganz unten, klein. */
  note?: ReactNode;
  /** Mobil am unteren Rand anheften (s. Ableseleiste). */
  haftet?: boolean;
  /** `aria-live` — nur, wo die Karte nicht bei jeder Zeigerbewegung wechselt. */
  live?: boolean;
  className?: string;
}) {
  return (
    <div
      aria-live={live ? "polite" : undefined}
      className={cn(
        haftet && "gb-ablese-leiste",
        "rounded-xl border border-border/70 bg-muted/30 px-3.5 py-2.5",
        className,
      )}
      style={{ "--gb-ablese-bottom": `calc(${TABLEISTE_HOEHE} + 0.5rem)` } as CSSProperties}
    >
      <div className="flex items-center gap-3">
        {marke && (
          <span
            aria-hidden="true"
            className={cn(
              "flex-none transition-colors duration-200",
              marke.eckig ? "h-3.5 w-3.5 rounded-[3px]" : "h-3 w-3 rounded-full",
              marke.schraffiert && "border border-dashed border-border",
              !marke.farbe && !marke.schraffiert && "ring-1 ring-inset ring-foreground/20",
            )}
            style={{
              background: marke.farbe,
              backgroundImage: marke.schraffiert ? NEUTRALE_SCHRAFFUR : undefined,
            }}
          />
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-semibold leading-snug text-foreground">{name}</p>
          {zusatz && (
            <p className="truncate text-[11.5px] leading-snug text-muted-foreground">{zusatz}</p>
          )}
          {anteil != null && (
            <span className="mt-1.5 block h-[3px] w-full max-w-[280px] overflow-hidden rounded-full bg-border/70">
              <span
                className="block h-full rounded-full bg-primary transition-[width] duration-300 ease-out"
                style={{ width: `${Math.max(1, Math.min(100, anteil))}%` }}
              />
            </span>
          )}
          {nebenwerte && nebenwerte.length > 0 && (
            <p className="mt-1 flex flex-wrap gap-x-3.5 gap-y-0.5 text-[11.5px] leading-snug">
              {nebenwerte.map((w) => (
                <span key={w.label} className="inline-flex items-baseline gap-1.5">
                  {w.farbe && (
                    <span aria-hidden="true" className="h-2 w-2 flex-none translate-y-[-1px] self-center rounded-full"
                      style={{ background: w.farbe }} />
                  )}
                  <span className="text-muted-foreground">{w.label}</span>
                  {/* `whitespace-nowrap`: Der Betrag trägt seine Einheit, und
                      die darf NIE von ihrer Zahl abreißen. */}
                  <span className={cn("whitespace-nowrap font-semibold tabular-nums",
                                      w.signal ? "text-signal" : "text-foreground")}>{w.value}</span>
                </span>
              ))}
            </p>
          )}
        </div>
        <div className="flex-none text-right">
          <p className={cn(
            "whitespace-nowrap font-display text-[20px] font-bold leading-none tracking-tight tabular-nums",
            wertSignal ? "text-signal" : "text-foreground",
          )}>
            {wert}
          </p>
          {(wertLabel || anteil != null) && (
            <p className="mt-1 whitespace-nowrap text-[11px] leading-none text-muted-foreground">
              {anteil != null ? <>{deZahl(anteil, 1)}&nbsp;% der Fläche</> : wertLabel}
            </p>
          )}
        </div>
      </div>
      {anmerkung && (
        <p className="mt-1.5 max-w-[76ch] border-t border-border/60 pt-1.5 text-[11.5px] leading-relaxed text-foreground/85">
          <span aria-hidden="true" className="mr-1 font-mono text-[10px] font-semibold text-foreground/70">ⓘ</span>
          {anmerkung}
        </p>
      )}
      {note && (
        <p className="mt-1 text-[10.5px] leading-snug text-muted-foreground">{note}</p>
      )}
    </div>
  );
}

/** Die Leiste unter dem Diagramm — echter Text, immer sichtbar; seit 02.09.
 *  gerendert als <Ablesekarte>: Der erste Wert der Stelle ist die Hauptzahl,
 *  die übrigen stehen als Nebenwerte darunter.
 *
 *  Mobil (unter 744 px) zusätzlich STICKY am unteren Rand (H4-A): Solange
 *  die Karte im Bild ist, bleibt die Wertzeile über der Tab-Leiste sichtbar —
 *  wer eine hohe Grafik antippt und wischt, liest den Wert, ohne zu
 *  scrollen. Der Abstand nach unten ist die Andockkante der Tab-Leiste
 *  (`TABLEISTE_HOEHE` aus `components/nav.tsx`) plus etwas Luft; das
 *  Verhalten selbst steht in `.gb-ablese-leiste` (app/globals.css). */
export function Ableseleiste({ stelle, steuerung, note, className, haftet = true }: {
  stelle: AbleseStelle;
  steuerung: AbleseSteuerung;
  /** Womit man die Stelle wechselt; ohne Angabe steht der Standardsatz da. */
  note?: string;
  className?: string;
  /** Mobil am unteren Rand anheften (Vorgabe) — oder eben nicht.
   *
   *  `false` gehört überall dorthin, wo unter der Grafik schon etwas am
   *  Rand klebt: Im Chat (/fragen) dockt die Leiste per `TABLEISTE_HOEHE`
   *  an der Tab-Leiste an und wusste nichts von der Eingabezeile darüber —
   *  sie schob sich beim Scrollen über das Eingabefeld (Tims Befund
   *  18.08.2026). Zwei klebende Ebenen übereinander kann niemand lesen. */
  haftet?: boolean;
}) {
  const [haupt, ...neben] = stelle.werte;
  return (
    <Ablesekarte
      haftet={haftet}
      className={className}
      marke={haupt ? { farbe: haupt.signal ? "hsl(var(--signal))" : haupt.farbe } : undefined}
      name={stelle.title}
      wert={haupt?.value ?? "—"}
      wertLabel={haupt?.label}
      wertSignal={haupt?.signal}
      nebenwerte={neben}
      anmerkung={stelle.anmerkung}
      note={<>
        {note ?? "Überfahren, tippen oder mit den Pfeiltasten wechseln."}
        {steuerung.gewaehlt && <> · <button type="button" onClick={steuerung.zuruecksetzen}
          className="font-semibold text-primary">zurücksetzen</button></>}
      </>}
    />
  );
}

/** Der sr-only-Absatz mit der Gesamtbeschreibung. Gehört neben die Grafik und
 *  wird von ihr per `aria-describedby` referenziert. */
export function AbleseBeschreibung({ id, children }: { id: string; children: ReactNode }) {
  return <p id={id} className="sr-only">{children}</p>;
}

/** Eine ID für das Paar aus Grafik und Beschreibung. */
export function useAbleseId(): string {
  return useId();
}

/** Die Fläche über dem Diagramm: Führungslinie, Ringe an der aktiven Stelle,
 *  Zeigerfang und die Tastaturziele. Gehört als LETZTES Kind ins SVG — sonst
 *  liegen Linien und Punkte darüber und fangen den Zeiger ab. */
export function AbleseFlaeche({
  stellen, steuerung, x, xVon, xBis, yVon, hoehe, fangHoehe, marken, gruppe,
}: {
  stellen: AbleseStelle[];
  steuerung: AbleseSteuerung;
  /** x-Koordinate der Stelle i in SVG-Einheiten. */
  x: (i: number) => number;
  /** Linke und rechte Kante der Fangfläche. */
  xVon: number;
  xBis: number;
  yVon: number;
  /** Höhe der Führungslinie (die Zeichenfläche). */
  hoehe: number;
  /** Höhe des Ziels für Finger und Fokusring — darf tiefer reichen als die
   *  Führungslinie, damit auch die Achsenbeschriftung ein Ziel ist. */
  fangHoehe?: number;
  /** Punkte, die bei der aktiven Stelle einen Ring bekommen. */
  marken?: (i: number) => AbleseMarke[];
  /** Name der Gruppe für die Vorlesehilfe, z. B. „Jahre der Reihe". */
  gruppe: string;
}) {
  const { aktiv, gewaehlt, waehle, zuruecksetzen, tastatur, setTastatur } = steuerung;
  const ziele = useRef<(SVGRectElement | null)[]>([]);
  const zieht = useRef(false);

  if (stellen.length < 2) return null;

  /** Nächstgelegene Stelle zur Zeigerposition. Gerechnet wird über die
   *  gemessene Breite der Fangfläche, nicht über `offsetX`: Die viewBox ist
   *  zwar so breit wie ihr Container (Faktor 1,0), aber der Bruchteil eines
   *  Pixels und ein künftiges Zoom-Layout dürfen die Zuordnung nicht kippen.
   *
   *  Die Suche selbst ist `bisectCenter` über den (aufsteigenden)
   *  x-Positionen — der dafür gebaute Griff aus d3-array (GB-15), statt
   *  eines eigenen Linear-Scans. Ein quadtree wäre zu viel: Die Reihen des
   *  Baukastens sind eindimensional. */
  const xs = stellen.map((_, i) => x(i));
  const stelleAn = (klientX: number, el: SVGRectElement): number => {
    const box = el.getBoundingClientRect();
    if (box.width <= 0) return aktiv;
    const sx = xVon + ((klientX - box.left) / box.width) * (xBis - xVon);
    return bisectCenter(xs, sx);
  };

  const bandBreite = stellen.length > 1
    ? Math.abs(x(1) - x(0))
    : xBis - xVon;

  const tasten = (e: React.KeyboardEvent<SVGRectElement>) => {
    const springe = (ziel: number) => {
      e.preventDefault();
      const i = Math.min(Math.max(ziel, 0), stellen.length - 1);
      waehle(i);
      setTastatur(true);
      // Erst im nächsten Frame: Das Ziel trägt bis dahin `tabIndex={-1}`, und
      // ein `focus()` darauf ginge in manchen Engines ins Leere.
      requestAnimationFrame(() => ziele.current[i]?.focus());
    };
    if (e.key === "ArrowRight" || e.key === "ArrowDown") springe(aktiv + 1);
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") springe(aktiv - 1);
    else if (e.key === "Home") springe(0);
    else if (e.key === "End") springe(stellen.length - 1);
    else if (e.key === "Escape") { e.preventDefault(); zuruecksetzen(); }
  };

  const mx = x(aktiv);
  const ringe = marken?.(aktiv) ?? [];
  const fangH = fangHoehe ?? hoehe;

  return (
    <g>
      {/* Die Führung GLEITET zur gewählten Stelle (`.gb-fuehrung`, ein
          Transform-Übergang) statt zu springen — und ein blasses Band hinter
          der Stelle sagt, wie breit ein Jahr ist. Führungslinie: Ohne sie
          wüsste niemand, welche Stelle die Karte gerade zeigt. Im Ruhezustand
          blass, nach einer Wahl deutlicher. Alles in einer Gruppe, deren
          Transform der einzige bewegte Wert ist. */}
      <g className="gb-fuehrung" style={{ transform: `translate(${mx}px, 0)` }}>
        <rect x={-bandBreite / 2} y={yVon} width={bandBreite} height={hoehe}
          className="fill-foreground" opacity={gewaehlt ? 0.05 : 0.03} />
        <line
          x1={0} y1={yVon} x2={0} y2={yVon + hoehe}
          strokeWidth={1} strokeDasharray={gewaehlt ? undefined : "3 3"}
          className={gewaehlt ? "stroke-foreground/45" : "stroke-foreground/25"}
        />
        {/* Radius 6,5, nicht mehr: Liegen zwei Reihen dicht beieinander (2021:
            716,8 gegen 748,1 sind 23 px), berührten sich zwei 7,5er-Ringe zu
            einer Acht. Der Ring gleitet in der Höhe mit, ein gefüllter Kern
            markiert den Wert selbst. */}
        {ringe.map((r, i) => (
          <g key={i} className="gb-fuehrung" style={{ transform: `translate(0, ${r.y}px)` }}>
            <circle r={6.5} fill="none" strokeWidth={1.6} opacity={0.9} style={{ stroke: r.farbe }} />
            <circle r={2.5} style={{ fill: r.farbe }} />
          </g>
        ))}
      </g>

      {/* Zeigerfang über der ganzen Zeichenfläche. `fill="transparent"` statt
          `fill="none"`: `none` bekommt gar keine Zeigerereignisse. */}
      <rect
        x={xVon} y={yVon} width={Math.max(xBis - xVon, 1)} height={fangH}
        fill="transparent" style={{ touchAction: "pan-y" }}
        onPointerDown={(e) => {
          zieht.current = true;
          e.currentTarget.setPointerCapture?.(e.pointerId);
          waehle(stelleAn(e.clientX, e.currentTarget));
          setTastatur(false);
        }}
        onPointerMove={(e) => {
          if (e.pointerType === "mouse" || zieht.current) {
            waehle(stelleAn(e.clientX, e.currentTarget));
          }
        }}
        onPointerUp={(e) => {
          zieht.current = false;
          e.currentTarget.releasePointerCapture?.(e.pointerId);
        }}
        onPointerCancel={() => { zieht.current = false; }}
        onPointerLeave={(e) => {
          // NUR für die Maus. Auf dem Telefon feuert `pointerleave` direkt
          // nach jedem Tippen — die Leiste spränge sofort zurück, und das
          // Antippen hätte sichtbar nichts bewirkt.
          if (e.pointerType === "mouse") { zieht.current = false; zuruecksetzen(); }
        }}
      />

      {/* Tastaturziele. `pointerEvents: none`, damit sie dem Zeigerfang nicht
          in die Quere kommen — fokussierbar bleiben sie trotzdem. */}
      <g
        role="group" aria-label={gruppe}
        onBlur={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
            setTastatur(false);
            zuruecksetzen();
          }
        }}
      >
        {stellen.map((s, i) => (
          <rect
            key={i}
            ref={(el) => { ziele.current[i] = el; }}
            x={x(i) - bandBreite / 2} y={yVon}
            width={bandBreite} height={fangH}
            fill="transparent" style={{ pointerEvents: "none", outline: "none" }}
            tabIndex={i === aktiv ? 0 : -1}
            role="button"
            aria-label={s.vorlesen}
            onKeyDown={tasten}
            onFocus={(e) => {
              waehle(i);
              let sichtbar = true;
              try { sichtbar = e.currentTarget.matches(":focus-visible"); } catch { /* alte Engine */ }
              setTastatur(sichtbar);
            }}
          />
        ))}
      </g>

      {/* Eigener Fokusring: SVG-Elemente bekommen keinen verlässlichen. */}
      {tastatur && (
        <rect
          x={mx - bandBreite / 2 + 1} y={yVon + 1}
          width={Math.max(bandBreite - 2, 2)} height={Math.max(fangH - 2, 2)}
          rx={4} fill="none" strokeWidth={2} className="stroke-primary"
          pointerEvents="none"
        />
      )}
    </g>
  );
}
