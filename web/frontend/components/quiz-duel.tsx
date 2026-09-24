"use client";

import { Swords } from "lucide-react";
import { cn } from "@/lib/utils";

export type DuelView = {
  code: string;
  owner_name: string;
  owner_correct: number;
  total: number;
  mine: boolean;
  played: boolean;
  questions: import("@/lib/types").QuizQuestion[];
  players: { name: string; correct: number; me: boolean }[];
};

/** Die Tabelle eines Duells: Herausforderer oben, dann alle, die gespielt
 *  haben, nach Treffern. Ich bin hervorgehoben. */
export function DuelScore({ duel, className }: { duel: DuelView; className?: string }) {
  const rows = [
    { name: duel.owner_name, correct: duel.owner_correct, me: duel.mine, owner: true },
    ...duel.players.map((p) => ({ ...p, owner: false })),
  ].sort((a, b) => b.correct - a.correct);
  const best = rows[0]?.correct ?? 0;
  return (
    <div className={cn("mx-auto w-full max-w-sm rounded-xl border border-border bg-muted/30 p-3 text-left", className)}>
      <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <Swords className="h-3.5 w-3.5" /> Duell
      </p>
      <ul className="space-y-1.5">
        {rows.map((r, i) => (
          <li key={i} className={cn("flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm",
            r.me && "bg-primary/10 font-semibold")}>
            <span className="flex-1 truncate text-foreground">
              {r.me ? "Du" : r.name}{r.owner && <span className="font-normal text-muted-foreground"> · hat herausgefordert</span>}
            </span>
            <span className={cn("tabular-nums", r.correct === best ? "text-green-700 dark:text-green-400" : "text-muted-foreground")}>
              {r.correct} / {duel.total}
            </span>
          </li>
        ))}
      </ul>
      {rows.length === 1 && (
        <p className="mt-2 text-xs text-muted-foreground">Noch hat niemand mitgespielt — teile den Link.</p>
      )}
    </div>
  );
}

/** Link teilen, wo das Gerät es kann, sonst in die Zwischenablage. */
export async function shareDuelLink(url: string, owner: number, total: number): Promise<"shared" | "copied" | "none"> {
  const text = `Ich habe ${owner} von ${total} Oldenburg-Fragen geschafft. Schaffst du mehr?`;
  try {
    if (navigator.share) { await navigator.share({ text, url }); return "shared"; }
    await navigator.clipboard.writeText(`${text} ${url}`);
    return "copied";
  } catch {
    return "none";
  }
}
