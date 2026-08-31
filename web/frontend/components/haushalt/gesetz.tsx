"use client";

// Der Gesetz-Chip: eine Waage neben einer Vorschrift, die auf den amtlichen
// Text führt.
//
// Warum er dem Beleg-Chip gleicht und trotzdem keiner ist, steht im Kopf von
// `lib/gesetze.ts`: Ein Beleg zeigt, woher eine ZAHL kommt, und trägt deshalb
// eine Ziffer aus dem Quellenverzeichnis. Ein Gesetz liefert keine Zahl — es
// sagt, warum es sie gibt. Gleiche Bedienung, gleiche Optik, anderes Zeichen,
// und außerhalb der Nummerierung.
//
// Zwei Dinge, die das Fähnchen bewusst NICHT tut:
//
//  * **Es ersetzt die Fundstelle im Text nicht.** „(§ 30 Abgabenordnung)"
//    bleibt stehen, der Chip kommt dahinter. Wer die Seite ausdruckt oder
//    einen Screenshot weitergibt, hat die Angabe weiterhin — ein Chip allein
//    wäre auf Papier ein leeres Kästchen.
//  * **Es fasst nicht das Gesetz zusammen, sondern die Stelle.** Ein Satz zu
//    „was steht da, das hier gilt", nicht ein Abriss von 36 Paragrafen. Alles
//    Weitere steht im Volltext, und dorthin führt der Link.

import { Scale, ExternalLink } from "lucide-react";
import { GESETZE, herausgeber, type GesetzSchluessel } from "@/lib/gesetze";
import { useFaehnchen } from "@/components/haushalt/quelle";
import { cn } from "@/lib/utils";

export function Gesetz({ g, className }: {
  g: GesetzSchluessel;
  className?: string;
}) {
  // Zustand, Lage und Schließen kommen aus einem Hook — auch das Zugehen bei
  // einem Klick daneben, das dieser Chip sonst wieder selbst bräuchte.
  const { offen, setOffen, knopf, faehnchen, lage } = useFaehnchen();
  const gesetz = GESETZE[g];
  if (!gesetz) return null;

  return (
    <span className="relative inline-block">
      <button
        ref={knopf}
        type="button"
        onClick={() => setOffen((o) => !o)}
        aria-label={`${gesetz.kurz} — ${gesetz.titel}: kurz erklärt und zum Gesetzestext`}
        aria-expanded={offen}
        className={cn(
          "ml-0.5 inline-flex h-4 w-4 items-center justify-center rounded bg-primary/10 align-super text-primary transition-colors hover:bg-primary/20",
          offen && "bg-primary text-primary-foreground",
          className,
        )}
      >
        <Scale className="h-2.5 w-2.5" aria-hidden />
      </button>
      {offen && (
        // `fixed` wie beim Beleg-Chip und aus demselben Grund — ein absolut
        // gesetztes Fähnchen schiebt sich am rechten Textrand aus dem Bild.
        <span
          ref={faehnchen}
          style={lage}
          className="fixed z-30 block max-h-[70vh] overflow-y-auto overscroll-contain rounded-xl border border-border bg-card p-3 text-left shadow-[0_12px_32px_-10px_rgba(2,32,71,0.28)]"
        >
          <span className="flex items-baseline justify-between gap-2">
            <span className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
              {gesetz.kurz}
            </span>
            {/* Bund oder Land — die Antwort auf „wer könnte das ändern?". */}
            <span className="font-mono text-[9.5px] uppercase tracking-[0.09em] text-muted-foreground">
              {gesetz.level === "Bund" ? "Bundesrecht" : "Landesrecht"}
            </span>
          </span>
          <span className="mt-1 block text-[12.5px] font-bold leading-snug text-foreground">
            {gesetz.titel}
          </span>
          <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">
            {gesetz.gesetz}
          </span>
          <span className="mt-2 block text-[12px] leading-relaxed text-foreground/85">
            {gesetz.zusammenfassung}
          </span>
          <a
            href={gesetz.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2.5 inline-flex items-center gap-1 text-[12px] font-semibold text-primary hover:underline"
          >
            Zum Gesetzestext
            <ExternalLink className="h-3 w-3" aria-hidden />
          </a>
          <span className="mt-1 block text-[10.5px] leading-snug text-muted-foreground">
            {herausgeber(gesetz)}
          </span>
        </span>
      )}
    </span>
  );
}
