"use client";

import { Toaster as Sonner } from "sonner";

export function Toaster() {
  return (
    <Sonner
      position="top-right"
      toastOptions={{
        classNames: {
          toast: "rounded-md border border-border bg-card text-card-foreground shadow-lg",
        },
      }}
    />
  );
}

export { toast } from "sonner";
