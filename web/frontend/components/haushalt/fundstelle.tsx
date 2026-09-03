// „Woher diese Zahlen kommen" — die Herkunft einer Angabe an der Zahl selbst.
//
// Bis 02.09.2026 stand dieser Block sechsmal im Bereich (Schulden, Vergleich,
// Personal, Investitionsplan, Gebaut, Konzern), jedes Mal ohne Link: Er
// nannte das Blatt und den Stand („Blatt ST_KR_MESS_VGL · 26.03.2026"), aber
// nicht das Dokument. Tims Regel für den Bereich ist die andere: **Jede Zahl
// führt zu ihrem PDF.** Deshalb hier einmal, mit Link — und die sechs Kopien
// sind darauf umgestellt.
//
// Der Linktext kommt aus `zielText`: Er sagt, was hinter der Adresse liegt
// (Dokument, Datensatz, Vorlage), statt überall „Dokument" zu behaupten.

import { ExternalLink } from "lucide-react";
import type { Herkunft } from "@/lib/herkunft";
import { zielText } from "@/lib/haushalt-dokumente";
import { cn } from "@/lib/utils";

export function Fundstelle({ h, className }: {
  h: Herkunft | null | undefined;
  className?: string;
}) {
  // Ohne Fundstelle und ohne Adresse nichts — sonst bliebe eine Überschrift
  // ohne Inhalt stehen.
  if (!h || (!h.citation && !h.url)) return null;
  const ziel = h.url ? (h.page ? `${h.url}#page=${h.page}` : h.url) : null;
  return (
    <div className={cn("border-t border-dashed border-border pt-2.5", className)}>
      <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Woher diese Zahlen kommen
      </p>
      <p className="mt-1 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        {h.citation}{h.citation && h.as_of ? ` · ${h.as_of}` : ""}
        {ziel && (
          <>
            {h.citation ? " · " : ""}
            <a href={ziel} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-semibold text-primary">
              {zielText(h.url as string)}
              <ExternalLink className="h-3 w-3" />
            </a>
          </>
        )}
      </p>
    </div>
  );
}
