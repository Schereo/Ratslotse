"use client";

import { useEffect, useState } from "react";
import { Printer } from "lucide-react";
import { Button } from "@/components/ui";

/**
 * Druck-Knopf (Design 28a/W3). Das Druck-Stylesheet in `globals.css` räumt
 * Navigation, Kopf- und Fußzeile längst ab — es fehlte nur der Auslöser.
 *
 * Ohne Druckdialog erscheint der Knopf gar nicht erst: ein Knopf, der nichts
 * tut, ist schlimmer als keiner.
 */
export function PrintButton({ className, label = "Drucken", iconOnly }: { className?: string; label?: string; iconOnly?: boolean }) {
  // Erst nach dem Mount entscheiden: Auf dem Server gibt es kein `window`.
  const [show, setShow] = useState(false);
  useEffect(() => {
    setShow(typeof window.print === "function");
  }, []);
  if (!show) return null;
  if (iconOnly) {
    // Ratsgespräch v2 (Design 2③): stille Icon-Aktion statt gerahmtem Button.
    return (
      <button type="button" onClick={() => window.print()} aria-label="Drucken" title="Drucken"
        className={`inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground ${className ?? ""}`}>
        <Printer className="h-3.5 w-3.5" />
      </button>
    );
  }
  return (
    <Button variant="secondary" size="sm" onClick={() => window.print()} className={className}>
      <Printer /> {label}
    </Button>
  );
}
