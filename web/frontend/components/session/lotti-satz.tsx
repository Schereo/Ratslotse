"use client";

/* Lotti mit Sprechblase im Kopf der Sitzungsseite und beim Mitlesen (Plan
   `docs/plan-sitzungsseite-kurs.md` 3.1, Tims Entscheidung 8.1 vom
   10.11.2026). Bild: `docs/entwurf-sitzungsseite/bilder/nach-der-sitzung-desktop-1.png`.

   Der Satz darin ist GERECHNET (`council/course.py::summary_sentence`) oder
   eine feste Erklärung. `quelle` ist optional; der Sitzungskopf lässt sie
   seit 12.11.2026 weg (DESIGNSPRACHE § 1, Ausnahme für diese Stelle). */

import { Mascot } from "@/components/mascot";
import { cn } from "@/lib/utils";

export function LottiSatz({ text, quelle, className }: { text: string; quelle?: string; className?: string }) {
  return (
    <div className={cn("flex items-start gap-3", className)}>
      <Mascot regung="erklaert" decorative className="mt-1 h-11 w-11 flex-none sm:h-12 sm:w-12" />
      <div className="relative min-w-0 max-w-[40rem] rounded-2xl border border-border bg-card px-4 py-3 shadow-sm">
        {/* Der Zipfel der Blase zeigt auf Lotti. */}
        <span aria-hidden className="absolute -left-[7px] top-5 h-3 w-3 rotate-45 border-b border-l border-border bg-card" />
        <p className="text-lese text-foreground [overflow-wrap:anywhere]">{text}</p>
        {quelle && <p className="mt-1 text-hinweis text-muted-foreground">{quelle}</p>}
      </div>
    </div>
  );
}
