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

import { useCallback, useId, useRef, useState, type CSSProperties } from "react";
import { bisectCenter } from "d3-array";
import { TABLEISTE_HOEHE } from "@/components/nav";
import { cn } from "@/lib/utils";

export type AbleseWert = {
  /** Kurzer Name der Größe, z. B. „Einnahmen". */
  label: string;
  /** Fertig formatiert (de-DE) — die Leiste rechnet nichts. */
  wert: string;
  /** Farbpunkt vor dem Label; üblicherweise `var(--hh-ein-0)`. */
  farbe?: string;
  /** Signal-Orange = „hier ist die Differenz", nie eine Bewertung. */
  signal?: boolean;
};

export type AbleseStelle = {
  /** Steht links in der Leiste, üblicherweise die Jahreszahl. */
  titel: string;
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
export function useAblesen(anzahl: number, standard: number): AbleseSteuerung {
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  const [tastatur, setTastatur] = useState(false);
  const grenze = Math.max(anzahl - 1, 0);
  const klemme = (i: number) => Math.min(Math.max(i, 0), grenze);
  // Geklemmt statt roh: Wechselt der Datensatz unter einer offenen Auswahl
  // (Jahres-Umschalter), zeigte die Leiste sonst auf eine Stelle, die es nicht
  // mehr gibt.
  const aktiv = klemme(gewaehlt ?? standard);

  const waehle = useCallback((i: number) => {
    setGewaehlt(Math.min(Math.max(i, 0), Math.max(anzahl - 1, 0)));
  }, [anzahl]);
  const zuruecksetzen = useCallback(() => setGewaehlt(null), []);

  return { aktiv, gewaehlt: gewaehlt != null, waehle, zuruecksetzen, tastatur, setTastatur };
}

/** Die Leiste unter dem Diagramm — echter Text, immer sichtbar.
 *
 *  Mobil (unter 744 px) zusätzlich STICKY am unteren Rand (H4-A): Solange
 *  die Karte im Bild ist, bleibt die Wertzeile über der Tab-Leiste sichtbar —
 *  wer eine hohe Grafik antippt und wischt, liest den Wert, ohne zu
 *  scrollen. Der Abstand nach unten ist die Andockkante der Tab-Leiste
 *  (`TABLEISTE_HOEHE` aus `components/nav.tsx`) plus etwas Luft; das
 *  Verhalten selbst steht in `.gb-ablese-leiste` (app/globals.css). */
export function Ableseleiste({ stelle, steuerung, hinweis, className }: {
  stelle: AbleseStelle;
  steuerung: AbleseSteuerung;
  /** Womit man die Stelle wechselt; ohne Angabe steht der Standardsatz da. */
  hinweis?: string;
  className?: string;
}) {
  return (
    <div
      className={cn("gb-ablese-leiste rounded-xl border border-border bg-muted/40 px-3 py-2", className)}
      style={{ "--gb-ablese-bottom": `calc(${TABLEISTE_HOEHE} + 0.5rem)` } as CSSProperties}
    >
      {/* ZWEI LAYOUTS, EIN MARKUP.
          Breit läuft die Zeile um (viele kurze Werte nebeneinander). Schmal
          ist das falsch: Sechs Einträge mit langen Namen wie „Erwerb von
          Grundstücken und Gebäuden" ergaben Treppenstufen, in denen Name und
          Betrag nicht mehr zusammenfanden. Unter 480 px steht deshalb jeder
          Eintrag auf einer eigenen Zeile, Name links, Betrag rechtsbündig —
          die Beträge stehen dann untereinander und sind vergleichbar. */}
      <div className="flex flex-col gap-y-1 ab-lesezeile:flex-row ab-lesezeile:flex-wrap
                      ab-lesezeile:items-baseline ab-lesezeile:gap-x-3.5">
        <span className="font-mono text-[12.5px] font-semibold uppercase tracking-[0.08em] tabular-nums">
          {stelle.titel}
        </span>
        {stelle.werte.map((w) => (
          <span key={w.label}
            className="flex items-baseline justify-between gap-2 text-[12.5px] leading-tight
                       ab-lesezeile:inline-flex ab-lesezeile:justify-start ab-lesezeile:gap-1.5">
            <span className="flex min-w-0 items-baseline gap-1.5">
              {w.farbe && (
                <span aria-hidden="true" className="h-2 w-2 flex-none translate-y-[-1px] self-center rounded-full"
                  style={{ background: w.farbe }} />
              )}
              <span className="text-muted-foreground">{w.label}</span>
            </span>
            {/* `whitespace-nowrap`: Der Betrag trägt seine Einheit („0,2 Mio.
                €"), und die darf NIE von ihrer Zahl abreißen — auf 375 px
                stand das € sonst allein auf der nächsten Zeile. */}
            <span className={cn("flex-none whitespace-nowrap font-semibold tabular-nums",
                                w.signal && "text-signal")}>{w.wert}</span>
          </span>
        ))}
      </div>
      {stelle.anmerkung && (
        <p className="mt-1.5 max-w-[76ch] border-t border-border/60 pt-1.5 text-[11.5px] leading-relaxed text-foreground/85">
          <span aria-hidden="true" className="mr-1 font-mono text-[10px] font-semibold text-foreground/70">ⓘ</span>
          {stelle.anmerkung}
        </p>
      )}
      <p className="mt-1 text-[10.5px] leading-snug text-muted-foreground">
        {hinweis ?? "Überfahren, tippen oder mit den Pfeiltasten wechseln."}
        {steuerung.gewaehlt && <> · <button type="button" onClick={steuerung.zuruecksetzen}
          className="font-semibold text-primary">zurücksetzen</button></>}
      </p>
    </div>
  );
}

/** Der sr-only-Absatz mit der Gesamtbeschreibung. Gehört neben die Grafik und
 *  wird von ihr per `aria-describedby` referenziert. */
export function AbleseBeschreibung({ id, children }: { id: string; children: React.ReactNode }) {
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
      {/* Führungslinie: Ohne sie wüsste niemand, welche Stelle die Leiste
          gerade zeigt. Im Ruhezustand blass, nach einer Wahl deutlicher. */}
      <line
        x1={mx} y1={yVon} x2={mx} y2={yVon + hoehe}
        strokeWidth={1} strokeDasharray={gewaehlt ? undefined : "3 3"}
        className={gewaehlt ? "stroke-foreground/45" : "stroke-foreground/25"}
      />
      {/* Radius 6,5, nicht mehr: Liegen zwei Reihen dicht beieinander (2021:
          716,8 gegen 748,1 sind 23 px), berührten sich zwei 7,5er-Ringe zu
          einer Acht. */}
      {ringe.map((r, i) => (
        <circle key={i} cx={mx} cy={r.y} r={6.5} fill="none" strokeWidth={1.6}
          opacity={0.9} style={{ stroke: r.farbe }} />
      ))}

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
