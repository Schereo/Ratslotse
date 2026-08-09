"use client";

import { Share2 } from "lucide-react";
import { Button, toast } from "@/components/ui";
import { isNativeApp } from "@/lib/platform";

/**
 * Teilt die öffentliche Web-URL der Seite: Web Share API wo vorhanden (mobil),
 * sonst Link in die Zwischenablage. Aus der nativen App heraus wird immer die
 * ratslotse.de-URL geteilt — der capacitor://-Origin wäre für Empfänger nutzlos.
 */
export function ShareButton({ path, title, className, iconOnly }: { path: string; title: string; className?: string; iconOnly?: boolean }) {
  const share = async () => {
    const base = isNativeApp() ? "https://ratslotse.de" : window.location.origin;
    const url = `${base}${path}`;
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
        return;
      } catch (e) {
        if ((e as Error).name === "AbortError") return; // Nutzer:in hat den Share-Dialog geschlossen
        /* Share-API vorhanden, aber blockiert (z. B. WKWebView) → Clipboard-Fallback */
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Link kopiert.");
    } catch {
      toast.error("Link konnte nicht kopiert werden.");
    }
  };

  if (iconOnly) {
    // Ratsgespräch v2 (Design 2③): stille Icon-Aktion statt gerahmtem Button.
    return (
      <button type="button" onClick={share} aria-label="Antwort teilen" title="Teilen"
        className={`inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground ${className ?? ""}`}>
        <Share2 className="h-3.5 w-3.5" />
      </button>
    );
  }
  return (
    <Button variant="secondary" size="sm" onClick={share} className={className}>
      <Share2 /> Teilen
    </Button>
  );
}
