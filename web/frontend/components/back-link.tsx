"use client";

import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

/** Zurück-Knopf für Standalone-Seiten (Impressum/Datenschutz) — in der nativen
 *  App gibt es keinen Browser-Zurück, ohne den man dort festhinge. Nutzt die
 *  WebView-History; ist keine da (Direkteinstieg/Deep-Link), führt er zur
 *  Startseite statt ins Leere. */
export function BackLink({ className }: { className?: string }) {
  const router = useRouter();
  const onBack = () => {
    if (typeof window !== "undefined" && window.history.length > 1) router.back();
    else router.push("/");
  };
  return (
    <button
      type="button"
      onClick={onBack}
      className={
        className ??
        "inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
      }
    >
      <ArrowLeft className="h-4 w-4" /> Zurück
    </button>
  );
}
