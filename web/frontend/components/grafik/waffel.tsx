// <Waffel> — Menge als zählbares Bild (GB-06). Mathe: pure, Rundung deklariert.
//
// Ein Quadrat steht für eine feste Menge (`proQuadrat`, im Stellenplan 10
// Stellen). Die MARKIERTEN Quadrate sind die Abweichung vom Plan — unbesetzte
// Stellen — und tragen deshalb einen Signal-Orange-UMRISS, nie eine Fläche:
// Eine unbesetzte Stelle ist weder gut noch schlecht, sie weicht nur vom Plan
// ab (Bereichsregel, s. components/grafik/hantel.tsx). Eine orangene
// Fläche läse sich als Alarm.
//
// ZWEI ANGABEN, DIE DIE KOMPONENTE SELBST RENDERT, DAMIT SIE NIEMAND
// VERGESSEN KANN (GB-06):
//  * Der STICHTAG der Markierung steht in der Legende. Im Stellenplan wird
//    die Besetzung immer ein Jahr versetzt erhoben — ohne Datum wäre die
//    Markierung eine falsche Aussage über das Planjahr.
//  * Die RUNDUNGSREGEL als Fußzeile: „80 Quadrate, gerundet · 1 Quadrat =
//    10 Stellen". Wer 796 Stellen auf 80 Quadrate rundet, sagt das dazu.
//
// BREAKPOINT-VERHALTEN EINGEBAUT, KEIN PROP (H4-A): Desktop und Tablet
// zeigen `spaltenDesk` Quadrate je Reihe (14), unter 744 px sind es
// `spaltenMobil` (10) bei 13 px Kantenlänge — die Schwelle steht als
// Media-Query in `app/globals.css` (`.gb-waffel`), die Spaltenzahlen reisen
// als CSS-Variablen aus den Props mit.
//
// Die Waffel ist bewusst NICHT interaktiv: Sie hat genau eine Aussage, und
// die steht vollständig im Bild und im `aria-label`. Für die Vorlesehilfe ist
// sie deshalb `role="img"` — anders als die Ablese-Grafiken, deren Stellen
// einzeln ansteuerbar sind (`role="group"`, s. ablesen.tsx).

import type { CSSProperties, ReactNode } from "react";
import { LueckenFeld } from "@/components/grafik/luecken-field";
import { deZahl } from "@/components/grafik/format";
import { cn } from "@/lib/utils";

export function Waffel({
  gesamt, proQuadrat = 10, markiert, einheit, grundLabel,
  spaltenDesk = 14, spaltenMobil = 10, beleg, luecke, className,
}: {
  /** Die Gesamtmenge, die die Waffel zeigt — in `einheit`. */
  gesamt: number;
  /** Wie viel ein Quadrat zählt. */
  proQuadrat?: number;
  /** Die markierten (umrandeten) Quadrate: Menge, Legenden-Text und der
   *  Stichtag, zu dem gezählt wurde. Der Stichtag ist Pflicht — die
   *  Komponente rendert ihn in der Legende (GB-06). */
  markiert: { count: number; grund: string; as_of_date: string };
  /** Was gezählt wird: „Stellen". */
  einheit: string;
  /** Legenden-Text der NICHT markierten Quadrate: „besetzt". */
  grundLabel: string;
  /** Quadrate je Reihe — Desktop/Tablet und mobil (H4-A). */
  spaltenDesk?: number;
  spaltenMobil?: number;
  /** Beleg-Chip der Seite, steht an der Fußzeile. */
  beleg?: ReactNode;
  /** Eine Lücke, die zu dieser Waffel gehört (Teil B 2026: PDF unlesbar).
   *  Rendert die Komponente, nie die Seite — so bleibt sie auch mobil eine
   *  sichtbare Zeile (H4-05). */
  luecke?: { label: string; grund: string; datum?: string };
  className?: string;
}) {
  const quadrate = Math.max(Math.round(gesamt / proQuadrat), 0);
  const markierte = Math.min(
    Math.max(Math.round(markiert.count / proQuadrat), 0), quadrate);

  const vorlesen =
    `${deZahl(gesamt)} ${einheit}, davon ${deZahl(markiert.count)} `
    + `${markiert.grund} (Stichtag ${markiert.as_of_date}). Dargestellt als `
    + `${quadrate} Quadrate zu je ${deZahl(proQuadrat)} ${einheit}, gerundet; `
    + `${markierte} davon sind markiert.`;

  return (
    <div className={cn("flex flex-col gap-2.5", className)}>
      <div
        role="img"
        aria-label={vorlesen}
        className="gb-waffel"
        style={{
          "--gb-waffel-desk": spaltenDesk,
          "--gb-waffel-mobil": spaltenMobil,
        } as CSSProperties}
      >
        {Array.from({ length: quadrate }, (_, i) => (
          <span
            key={i}
            aria-hidden="true"
            className={cn(
              "gb-waffel-q rounded-[4px]",
              i < quadrate - markierte
                ? undefined
                : "border-2 border-dashed border-signal/80",
            )}
            style={i < quadrate - markierte
              ? { background: "var(--hh-ein-0)" }
              : undefined}
          />
        ))}
      </div>

      {/* Legende — mit dem Stichtag, den die Komponente erzwingt. */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11.5px] text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-3 w-3 flex-none rounded-[3px]"
            style={{ background: "var(--hh-ein-0)" }} />
          {grundLabel} (Stichtag {markiert.as_of_date})
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true"
            className="h-3 w-3 flex-none rounded-[3px] border-2 border-dashed border-signal/80" />
          {markiert.grund}
        </span>
      </div>

      {/* Rundungszeile — automatisch, damit die behauptete Genauigkeit nie
          größer ist als die gezeichnete. */}
      <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.09em] text-muted-foreground">
        {quadrate} Quadrate, gerundet · 1 Quadrat = {deZahl(proQuadrat)} {einheit}
        {beleg}
      </p>

      {luecke && (
        <LueckenFeld label={luecke.label} grund={luecke.grund} datum={luecke.datum} />
      )}
    </div>
  );
}
