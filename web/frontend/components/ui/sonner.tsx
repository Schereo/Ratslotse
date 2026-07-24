"use client";

import { Toaster as Sonner } from "sonner";

export function Toaster() {
  return (
    <Sonner
      position="top-right"
      // Höchstens zwei gleichzeitig: Auf dem Handy nimmt jeder Toast die volle
      // Breite ein, ein Stapel verdeckt damit den halben Bildschirm.
      visibleToasts={2}
      // RL-F10: Toasts unterhalb von Uhr/Dynamic Island halten (env()=0 im Web).
      style={{ top: "calc(1rem + env(safe-area-inset-top))" }}
      toastOptions={{
        classNames: {
          toast: "rounded-md border border-border bg-card text-card-foreground shadow-lg",
        },
      }}
    />
  );
}

export { toast } from "sonner";
