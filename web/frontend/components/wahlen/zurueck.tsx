// Der Weg von einer Wahl zurück zur Übersicht.
//
// Bis 10/2026 trugen die Wahlseiten einen eigenen Kopf mit Logo und
// „← Zurück zu Ratslotse“ — sie lagen außerhalb der App-Hülle, und wer über
// „Analyse“ → „Wahlen“ kam, glaubte sich nicht mehr in Ratslotse (Tims Befund
// 16.10.2026). Seit sie in der Hülle liegen, steht die Navigation schon da; es
// fehlt nur der Schritt zurück zur Übersicht aller Wahlen.

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";

export function ZurueckZuWahlen({ className }: { className?: string }) {
  return (
    <Link
      href="/wahlen"
      className={cn(
        "inline-flex items-center gap-1 rounded-md text-sm text-muted-foreground transition-colors duration-fluss hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
    >
      <ArrowLeft className="h-4 w-4" aria-hidden /> Alle Wahlen
    </Link>
  );
}
