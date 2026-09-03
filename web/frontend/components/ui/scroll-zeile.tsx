"use client";

import { useRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";
import { useScrollRand } from "@/lib/use-scroll-rand";

/** Eine waagerecht scrollbare Zeile, die zeigt, dass sie scrollt.
 *
 *  Für Chip-Reihen und Segment-Schalter, die auf dem Handy breiter sind als
 *  ihr Platz: Der Inhalt fadet am verdeckten Ende per Maske aus (Designsprache
 *  § 6), statt hart abgeschnitten zu stehen — und nur dort, wo wirklich etwas
 *  verdeckt ist. Ohne Rollbalken, wie bisher (`scrollbar-none`).
 *
 *  Die Klasse kommt aus `useScrollRand`; wer einen anderen Wurzelknoten
 *  braucht (etwa ein `ul`), nimmt den Hook direkt. */
export function ScrollZeile({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  const zeile = useRef<HTMLDivElement>(null);
  const maske = useScrollRand(zeile);
  return (
    <div ref={zeile} className={cn("scrollbar-none overflow-x-auto", maske, className)} {...rest}>
      {children}
    </div>
  );
}
