"use client";

/* The page of a document, large (Tims Wunsch 23.11.2026: „in der preview
   sieht sie sehr klein aus"). Opened from the preview in the picker; you can
   page through and insert the page you see right here.

   A real dialog (Radix: focus trap, Esc, focus back to the preview), with the
   `.scrim` and the `--level-dialog` level from the design language. ← and →
   page through; „Vergrößern“ (also double click, + and −) doubles the width
   and lets the page scroll both ways — a table page across a phone is
   otherwise still too small to read. */

import { useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ChevronLeft, ChevronRight, X, ZoomIn, ZoomOut } from "lucide-react";
import { PagePreview } from "@/components/notiz/page-preview";

export function PageZoom({ open, onOpenChange, documentId, label, page, total, onPage, onInsert }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  documentId: number;
  label: string;
  page: number;
  total: number | null;
  onPage: (page: number) => void;
  /** Ohne: nur ansehen. Mit: „Seite n einfügen“ schließt und fügt ein. */
  onInsert?: () => void;
}) {
  const KNOPF = "inline-flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-40";
  const vor = page > 1;
  const weiter = total == null || page < total;
  const [gross, setGross] = useState(false);
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="scrim fixed inset-0" style={{ zIndex: "var(--level-dialog)" }} />
        <DialogPrimitive.Content
          style={{ zIndex: "var(--level-dialog)" }}
          onKeyDown={(e) => {
            // React reicht Tasten aus dem Portal an die Vorfahren weiter — ohne
            // das schlösse Esc hier auch die Auswahl darunter.
            if (e.key === "Escape") e.stopPropagation();
            if (e.key === "ArrowLeft" && vor) { e.preventDefault(); onPage(page - 1); }
            if (e.key === "ArrowRight" && weiter) { e.preventDefault(); onPage(page + 1); }
            if (e.key === "+") { e.preventDefault(); setGross(true); }
            if (e.key === "-") { e.preventDefault(); setGross(false); }
          }}
          className="fixed left-1/2 top-1/2 flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] max-w-[960px] -translate-x-1/2 -translate-y-1/2 flex-col rounded-xl border border-border bg-card shadow-lg">
          <div className="flex items-center gap-2 border-b border-border py-1 pl-4 pr-1">
            <DialogPrimitive.Title className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
              Seite {page}{total ? ` von ${total}` : ""} · {label}
            </DialogPrimitive.Title>
            <DialogPrimitive.Close aria-label="Schließen" className={KNOPF}>
              <X className="h-4 w-4" aria-hidden />
            </DialogPrimitive.Close>
          </div>
          <DialogPrimitive.Description className="sr-only">
            Die Seite in groß. Mit den Pfeiltasten blättern.
          </DialogPrimitive.Description>
          <div className="min-h-0 flex-1 overflow-auto bg-muted/40 p-3">
            <div style={{ width: gross ? "200%" : "100%" }} onDoubleClick={() => setGross((g) => !g)}
              className={gross ? "cursor-zoom-out" : "cursor-zoom-in"}>
              <PagePreview documentId={documentId} page={page} label={label} width={1280} natural />
            </div>
          </div>
          <div className="flex items-center gap-2 border-t border-border px-2 py-2">
            <button type="button" onClick={() => onPage(page - 1)} disabled={!vor} aria-label="Vorige Seite" className={KNOPF}>
              <ChevronLeft className="h-4 w-4" aria-hidden />
            </button>
            <span className="whitespace-nowrap text-sm text-muted-foreground" aria-live="polite">
              {page}{total ? ` / ${total}` : ""}<span className="sr-only"> Seiten</span>
            </span>
            <button type="button" onClick={() => onPage(page + 1)} disabled={!weiter} aria-label="Nächste Seite" className={KNOPF}>
              <ChevronRight className="h-4 w-4" aria-hidden />
            </button>
            <button type="button" onClick={() => setGross((g) => !g)} aria-pressed={gross}
              aria-label={gross ? "Ganze Seite zeigen" : "Vergrößern"} title={gross ? "Ganze Seite (−)" : "Vergrößern (+)"}
              className={KNOPF}>
              {gross ? <ZoomOut className="h-4 w-4" aria-hidden /> : <ZoomIn className="h-4 w-4" aria-hidden />}
            </button>
            {onInsert && (
              <button type="button" onClick={onInsert}
                className="ml-auto inline-flex h-11 items-center whitespace-nowrap rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90">
                Seite {page} einfügen
              </button>
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
