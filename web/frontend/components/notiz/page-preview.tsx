"use client";

/* One page of a document as a picture — in the picker while choosing a
   page, and over a reference chip in the note (`doc-ref.tsx`). */

import { FileText } from "lucide-react";
import { usePageImage, type PageWidth } from "@/lib/page-image";
import { cn } from "@/lib/utils";

/** ``natural``: das Bild in seiner eigenen Höhe (die Vergrößerung, auch für
 *  Seiten im Querformat); sonst ein A4-Rahmen, der beim Laden nicht springt. */
export function PagePreview({ documentId, page, label, className, width = 640, natural = false }: {
  documentId: number | null; page: number | null; label: string; className?: string;
  width?: PageWidth; natural?: boolean;
}) {
  const { src, state } = usePageImage(documentId, page, width);
  const alt = page ? `Seite ${page} von „${label}“` : label;
  if (natural && src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={src} alt={alt} className={cn("block h-auto w-full rounded-md border border-border bg-white", state === "loading" && "opacity-60", className)} />
    );
  }
  return (
    // Seitenverhältnis A4, damit nichts springt, während das Bild lädt.
    <div className={cn("relative aspect-[1/1.414] w-full overflow-hidden rounded-md border border-border bg-card", className)}>
      {/* Objekt-URL aus `lib/page-image.ts` — `next/image` kann damit nichts anfangen. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {src && <img src={src} alt={alt} className={cn("h-full w-full object-contain object-top", state === "loading" && "opacity-60")} />}
      {!src && state === "loading" && <div className="absolute inset-0 animate-pulse bg-muted" aria-hidden />}
      {state === "loading" && <span className="sr-only" role="status">Vorschau lädt</span>}
      {state === "error" && (
        <p className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 p-3 text-center text-xs text-muted-foreground">
          <FileText className="h-5 w-5" aria-hidden /> Keine Vorschau für diese Seite.
        </p>
      )}
      {state === "idle" && !src && (
        <p className="absolute inset-0 flex items-center justify-center p-3 text-center text-xs text-muted-foreground">
          Unterlage wählen
        </p>
      )}
    </div>
  );
}
