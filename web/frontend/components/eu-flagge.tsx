import { cn } from "@/lib/utils";

/** Die Europaflagge, klein — als Zeichen dafür, dass die KI in der EU läuft.
 *
 *  Seit 11/2026 laufen alle KI-Aufrufe mit Nutzereingabe nur noch über
 *  Rechenzentren in der EU (`kern/llm.py::EU_ZUERST`, kein Rückfall). Tim
 *  08.11.2026: „vielleicht auch mit einer kleinen Europa-Flagge dahinter —
 *  ich glaube, das gibt nochmal sehr viel Vertrauen". Als SVG statt Emoji
 *  (DESIGNSPRACHE § 8: kein Emoji im UI-Text; das Flaggen-Emoji zeigt
 *  Windows ohnehin als „EU" in Buchstaben). Die zwölf Sterne sind bei dieser
 *  Größe Punkte — fünf Zacken wären bei 1 px nur Rauschen. */
export function EuFlagge({ className }: { className?: string }) {
  const sterne = Array.from({ length: 12 }, (_, i) => {
    const w = ((i * 30 - 90) * Math.PI) / 180;
    return [12 + 5.2 * Math.cos(w), 8 + 5.2 * Math.sin(w)] as const;
  });
  return (
    <svg viewBox="0 0 24 16" role="img" aria-label="Europaflagge"
      className={cn("inline-block h-[0.75em] w-[1.125em] shrink-0 rounded-[2px] align-[-0.05em]", className)}>
      <rect width="24" height="16" fill="#003399" />
      {sterne.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="0.95" fill="#FFCC00" />)}
    </svg>
  );
}

/** „KI in der EU" mit Flagge — der kurze Hinweis unter einer Antwort. Die
 *  Einzelheiten (wer vermittelt, welcher Anbieter) stehen im Tooltip und in
 *  der Datenschutzerklärung. */
export function KiInDerEu({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap", className)}
      title="Die KI-Modelle laufen ausschließlich in Rechenzentren in der EU (Microsoft Azure). Vermittelt wird über OpenRouter (USA).">
      <EuFlagge />
      KI in der EU
    </span>
  );
}
