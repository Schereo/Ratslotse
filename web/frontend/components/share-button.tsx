"use client";

import { Share2 } from "lucide-react";
import { Button, toast } from "@/components/ui";
import { isNativeApp } from "@/lib/platform";

/**
 * Teilt die öffentliche Web-URL der Seite: Web Share API wo vorhanden (mobil),
 * sonst Link in die Zwischenablage. Aus der nativen App heraus wird immer die
 * ratslotse.de-URL geteilt — der capacitor://-Origin wäre für Empfänger nutzlos.
 */
export function ShareButton({ path, title, className }: { path: string; title: string; className?: string }) {
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

  return (
    <Button variant="secondary" size="sm" onClick={share} className={className}>
      <Share2 /> Teilen
    </Button>
  );
}
