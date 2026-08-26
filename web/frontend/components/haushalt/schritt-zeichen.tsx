"use client";

// Die Zeichen-Kachel im Kopf jeder Schritt-Seite.
//
// WARUM ES SIE GIBT (Tim, 24.08.2026): „Hier oben ist auch noch sehr viel
// Luft auf der Seite. Vlt können wir allgemein ein paar helfende Icons oder
// was weiteres visuelles fürs Auge einbauen?" — Die Köpfe der Schritt-Seiten
// sind Kicker + Titel + Absatz, und weil der Absatz bei ~66 Zeichen gedeckelt
// ist (Designsprache §4), bleibt rechts davon auf jedem breiteren Schirm eine
// leere Ecke. Genau dort steht jetzt das Zeichen des Schritts.
//
// Es ist dasselbe Zeichen wie in der Wegweiser-Zeile und in der
// Weiter-Navigation — definiert wird es EINMAL, am Schritt selbst
// (`wegweiser.tsx`, Feld `zeichen`). Diese Komponente schlägt nur nach.
// Kennt die Liste den Pfad nicht (Steckbriefe wie /haushalt/bereich haben
// bewusst keinen Schritt), rendert sie nichts — dieselbe Regel wie beim
// Kicker: kein erfundenes Zeichen.
//
// Rein dekorativ: aria-hidden, kein Link, keine Aussage. Deshalb darf sie
// unter 640 px auch ersatzlos verschwinden — mobil ist die leere Ecke, die
// sie füllt, gar nicht da.

import { SCHRITTE } from "@/components/haushalt/wegweiser";
import { cn } from "@/lib/utils";

export function SchrittZeichen({ href, className }: {
  href: string;
  className?: string;
}) {
  const schritt = SCHRITTE.find((s) => s.href === href);
  if (!schritt) return null;
  return (
    <span
      aria-hidden="true"
      className={cn(
        "hidden h-16 w-16 flex-none items-center justify-center rounded-2xl",
        "border border-primary/15 bg-primary/[0.06] text-primary sm:flex",
        className,
      )}
    >
      {/* 30 px / Strich 1,75 — bewusst außerhalb der 11–22-px-UI-Spanne und
          dünner als Strich 2: In Kachelgröße wirkt der UI-Strich gestaucht.
          Die Ausnahme steht in der Designsprache (§5, „Schritt-Zeichen"). */}
      <schritt.zeichen size={30} strokeWidth={1.75} />
    </span>
  );
}
