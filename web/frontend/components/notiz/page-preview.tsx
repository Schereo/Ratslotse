"use client";

/* One page of a document as a picture — in the picker while choosing a
   page, and over a reference chip in the note (`doc-ref.tsx`). */

import { FileText } from "lucide-react";
import { usePageImage } from "@/lib/page-image";
import { cn } from "@/lib/utils";

export function PagePreview({ documentId, page, label, className }: {
  documentId: number | null; page: number | null; label: string; className?: string;
}) {
  const { src, state } = usePageImage(documentId, page);
  const alt = page ? `Seite ${page} von „${label}“` : label;
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
