import { halbkreis } from "@/lib/wahlabend";
import { cn } from "@/lib/utils";

/**
 * Das kleine Bild des Mehrheitsrechners für die Werkzeug-Übersicht: ein
 * Sitzbogen, links der Mittellinie gefüllt. Bewusst ohne Parteifarben und
 * ohne echte Zahlen — es zeigt, WAS das Werkzeug tut, nicht einen Stand.
 */
export function MehrheitenVorschau({ className }: { className?: string }) {
  const plaetze = halbkreis(41, 3);
  const gefuellt = 23;
  return (
    <svg viewBox="-0.06 -0.08 2.12 1.14" className={cn("block", className)} aria-hidden>
      <line x1="1" y1="-0.06" x2="1" y2="0.6" className="stroke-signal" strokeWidth="0.012" strokeDasharray="0.04 0.03" />
      {plaetze.map((q, i) => (
        <circle key={i} cx={q.x} cy={q.y} r={q.r} className={i < gefuellt ? "fill-primary" : "fill-foreground/15"} />
      ))}
    </svg>
  );
}
