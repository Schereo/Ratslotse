"use client";

import { Share2 } from "lucide-react";
import { Button, toast } from "@/components/ui";
import { cn } from "@/lib/utils";
import { isNativeApp } from "@/lib/platform";

/**
 * Teilt die öffentliche Web-URL der Seite: Web Share API wo vorhanden (mobil),
 * sonst Link in die Zwischenablage. Aus der nativen App heraus wird immer die
 * ratslotse.de-URL geteilt — der capacitor://-Origin wäre für Empfänger nutzlos.
 */
export function ShareButton({ path, title, className, iconOnly, kompakt, still, label = "Teilen" }: {
  path: string; title: string; className?: string; iconOnly?: boolean;
  /** Icon-Knopf in den Maßen des Merken-Knopfs — für die Aktionsspalte einer
   *  Zeile (Tagesordnungspunkt), wo ein gerahmter Knopf die Zeile sprengt. */
  kompakt?: boolean;
  /** Stiller Textknopf in einer Aktionszeile (Sitzungskarte: neben „Kalender"
   *  und „Ratsinfo") — dort wäre ein gerahmter Knopf der einzige. */
  still?: boolean;
  /** Beschriftung des gerahmten Knopfs — „Teilen" passt nicht überall
   *  („Sitzung teilen" an der Sitzungskarte). */
  label?: string;
}) {
  const share = async (event?: React.MouseEvent) => {
    event?.preventDefault();
    event?.stopPropagation();
    const base = isNativeApp() ? "https://ratslotse.de" : window.location.origin;
    const url = `${base}${path}`;
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
        return;
      } catch (e) {
        if ((e as Error).name === "AbortError") return; // Nutzer*in hat den Share-Dialog geschlossen
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

  if (still) {
    return (
      <button type="button" onClick={share} title={label}
        className={cn("inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-primary", className)}>
        <Share2 className="h-3.5 w-3.5" /> {label}
      </button>
    );
  }
  if (kompakt) {
    return (
      <Button type="button" variant="ghost" size="icon" onClick={share}
        aria-label={label} title={label} className={cn("h-8 w-8", className)}>
        <Share2 />
      </Button>
    );
  }
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
      <Share2 /> {label}
    </Button>
  );
}
