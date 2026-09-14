"use client";

// Der Kopf der Wahlabend-Seiten. Stand bis 09/2026 in `view.tsx`; seit die
// Stichwahl eine eigene Seite hat, sind es zwei Seiten mit demselben Kopf —
// und zwei Fassungen davon wären zwei Fassungen des Zurück-Links.

import Link from "next/link";
import { BrandMark } from "@/components/brand";
import { WebThemeSwitch } from "@/components/web-theme-switch";

export function Kopf({ label }: { label: string }) {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-card/95 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-3 px-4 pb-3 pt-[calc(env(safe-area-inset-top)+0.75rem)] sm:px-6 lg:px-10">
        <div className="flex min-w-0 items-center gap-2.5">
          <Link href="/" className="flex flex-none items-center gap-2.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <BrandMark className="h-[30px] w-[30px]" />
            <span className="font-display text-[17px] font-bold tracking-tight text-foreground">Ratslotse</span>
          </Link>
          <span className="truncate border-l border-border pl-2.5 text-[13px] text-muted-foreground">{label}</span>
        </div>
        <div className="flex flex-none items-center gap-3 sm:gap-4">
          <WebThemeSwitch />
          <Link href="/" className="hidden text-[13px] font-medium text-primary sm:inline">
            ← Zurück zu Ratslotse
          </Link>
        </div>
      </div>
    </header>
  );
}
