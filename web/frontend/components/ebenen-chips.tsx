"use client";

import { cn } from "@/lib/utils";
import { EBENEN, type EbenenId } from "@/lib/karten-ebenen";

/** Die Ebenen-Chips oben auf der Stadtkarte (STADTKARTE-PLAN.md, Schritt 2).
 *
 *  Ein Chip trägt Farbe, Label und Zähler; aus ist er hohl. Die Chips sind
 *  zugleich die Legende — deshalb steht der Farbpunkt auch am ausgeschalteten
 *  Chip, nur blass. Ebenen, die auf der aktuellen Stufe nichts zeichnen
 *  (Planflächen auf der Stadt-Stufe), bleiben stehen und sagen es im Tooltip:
 *  Ein Chip, der kommt und geht, sähe aus wie ein Fehler.
 */
export function EbenenChips({ ebenen, stufe, zaehler, onToggle, unterzeile, verborgen, className }: {
  ebenen: ReadonlySet<EbenenId>;
  stufe: "city" | "district";
  /** Ebenen, deren Schalter aus ist — der Chip bleibt weg, nicht hohl. */
  verborgen?: ReadonlySet<EbenenId>;
  /** Wie viel je Ebene gerade auf der Karte liegt (fehlt = kein Zähler). */
  zaehler?: Partial<Record<EbenenId, number>>;
  onToggle: (id: EbenenId) => void;
  /** Eine zweite Zeile unter den Chips — die Unter-Chips einer Ebene (Art der Themen-Orte). */
  unterzeile?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-start gap-1.5", className)}>
    <div className="flex flex-wrap gap-1.5" role="group" aria-label="Ebenen der Karte">
      {EBENEN.filter((e) => !verborgen?.has(e.id)).map((e) => {
        const an = ebenen.has(e.id);
        const hier = e.stufen.includes(stufe);
        const n = zaehler?.[e.id];
        return (
          <button
            key={e.id}
            type="button"
            aria-pressed={an}
            onClick={() => onToggle(e.id)}
            title={hier ? e.quelle : `${e.quelle} — erst im Viertel sichtbar`}
            className={cn(
              "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] font-semibold shadow-sm backdrop-blur transition-colors",
              an ? "border-border bg-card/95 text-foreground" : "border-border/70 bg-card/70 text-muted-foreground hover:text-foreground",
              !hier && "opacity-70",
            )}
          >
            <span
              aria-hidden
              className={cn("h-2.5 w-2.5 rounded-full border-2", e.gestrichelt && "border-dashed")}
              style={an
                ? { background: e.gestrichelt ? `color-mix(in srgb, ${e.farbe} 25%, transparent)` : e.farbe, borderColor: e.farbe }
                : { background: "transparent", borderColor: e.farbe, opacity: 0.6 }}
            />
            {e.label}
            {n != null && <span className="font-mono text-[10.5px] font-medium tabular-nums opacity-70">{n}</span>}
          </button>
        );
      })}
    </div>
    {unterzeile}
    </div>
  );
}
