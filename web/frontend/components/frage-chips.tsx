"use client";

import Link from "next/link";
import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Fertige Fragen zum Antippen — auf Seiten, die NICHT die KI-Frage sind.
 *
 * Warum: Sechs neue Konten in einer Woche, null Fragen an Lotti (Auswertung
 * 17.09.2026). Nicht aus Desinteresse — BartVZ löste in neun Minuten 159
 * Anfragen aus —, sondern weil der Weg über den Wahlabend, die Auswertungen
 * und die Beschlussliste führt und der Frage-Einstieg außerhalb dieses Pfads
 * liegt. Am 19.09. kamen dann beide Fragen des Tages über einen Chip, beide
 * von Leuten, die vorher nie gefragt hatten. Der Chip zieht; er hing nur an
 * zwei Stellen.
 *
 * Jeder Chip ist ein Link auf `/fragen?q=…&chip=1`. Dort übernimmt der
 * Composer die Frage und stellt sie sofort (wie ein Chip im Gespräch
 * selbst); `chip=1` zählt sie als `ai_question_chip`, damit sichtbar bleibt,
 * ob der Einstieg trägt. Wer nicht angemeldet ist, landet über den
 * Rücksprung der Anmeldung genau dort — die Frage geht nicht verloren.
 *
 * Die Fragen sind kuratiert und BELEGBAR — jede zielt auf etwas, das die
 * Beschlüsse hergeben. Eine Frage, die ins Leere läuft, wäre hier schlimmer
 * als keine: Sie zeigte einem Neuen als Erstes eine Sackgasse.
 *
 * Gestalt nach DESIGNSPRACHE: Vorschlags-Chip (primary-Rahmen /30, bg /5,
 * Radius 9999), Funken in Signal-Orange als das eine Zeichen für „KI".
 */
export function frageLink(frage: string): string {
  return `/fragen?q=${encodeURIComponent(frage)}&chip=1`;
}

/** Ein Chip: die Frage, die gestellt wird — und optional ein kürzerer Text
 *  auf dem Chip, wenn die volle Frage zu lang für eine Pille wäre. */
export type FrageChip = string | { frage: string; label: string };

export function FrageChips({ fragen, titel = "Frag Lotti", className }: {
  fragen: readonly FrageChip[];
  titel?: string;
  className?: string;
}) {
  const liste = fragen
    .map((f) => (typeof f === "string" ? { frage: f, label: f } : f))
    .filter((f) => f.frage.trim()).slice(0, 3);
  if (!liste.length) return null;
  return (
    <div className={cn("flex flex-wrap items-center gap-x-3 gap-y-2", className)}
      role="group" aria-label="Fragen an Lotti">
      <span className="inline-flex items-center gap-1.5 font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
        <Sparkles className="h-3.5 w-3.5 text-signal" aria-hidden />
        {titel}
      </span>
      <div className="flex flex-wrap gap-1.5">
        {liste.map(({ frage, label }) => (
          <Link key={frage} href={frageLink(frage)} prefetch={false} title={label !== frage ? frage : undefined}
            className="inline-flex items-center rounded-full border border-primary/30 bg-primary/[0.05] px-3 py-1.5 text-[12.5px] text-foreground transition-[background-color,transform] duration-150 ease-out-strong hover:bg-primary/[0.1] active:scale-[0.98]">
            {label}
          </Link>
        ))}
      </div>
    </div>
  );
}
