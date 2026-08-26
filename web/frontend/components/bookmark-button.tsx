"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, BookmarkCheck, Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { BookmarkEntry } from "@/lib/types";
import { Button, toast } from "@/components/ui";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

export type BookmarkTarget =
  | { kind: "session"; ksinr: number }
  | { kind: "agenda_item"; ksinr: number; item_number: string }
  | { kind: "decision"; decision_id: number };

const topNumber = (value: string | null | undefined) => value?.match(/\d+(?:\.\d+)*/)?.[0] ?? "";

function matches(entry: BookmarkEntry, target: BookmarkTarget): boolean {
  if (target.kind === "decision") return entry.decision?.id === target.decision_id;
  if (target.kind === "session") return entry.kind === "session" && entry.ksinr === target.ksinr;
  if (entry.kind !== "agenda_item" && entry.kind !== "decision") return false;
  return entry.ksinr === target.ksinr
    && topNumber(entry.item_number) === topNumber(target.item_number);
}

/** Ein einheitlicher Merken-Knopf für alle Ratsinhalte.
 *
 * Alle Instanzen teilen dieselbe React-Query. Auch eine lange Tagesordnung
 * erzeugt deshalb genau einen Request statt einer Status-Abfrage je TOP.
 */
export function BookmarkButton({ target, compact = false, className }: {
  target: BookmarkTarget;
  compact?: boolean;
  className?: string;
}) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const { data } = useQuery({
    queryKey: ["bookmarks"],
    queryFn: () => api.get<{ bookmarks: BookmarkEntry[] }>("/bookmarks").then((d) => d.bookmarks),
    staleTime: 30_000,
    enabled: !!user,
  });
  if (!user) return null;
  const current = data?.find((entry) => matches(entry, target));

  const toggle = async (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (busy) return;
    setBusy(true);
    try {
      if (current) {
        await api.del(`/bookmarks/${current.id}`);
        toast.success("Aus der Merkliste entfernt.");
      } else {
        await api.post("/bookmarks", target);
        toast.success("Zur Merkliste hinzugefügt.");
      }
      await qc.invalidateQueries({ queryKey: ["bookmarks"] });
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Merken hat nicht geklappt.");
    } finally {
      setBusy(false);
    }
  };

  const label = current ? "Gemerkt" : "Merken";
  return (
    <Button
      type="button"
      variant={current ? "secondary" : "ghost"}
      size={compact ? "icon" : "sm"}
      onClick={toggle}
      disabled={busy}
      aria-pressed={!!current}
      aria-label={current ? "Aus der Merkliste entfernen" : "Zur Merkliste hinzufügen"}
      title={current ? "Aus der Merkliste entfernen" : "Zur Merkliste hinzufügen"}
      className={cn(compact && "h-8 w-8", current && "text-primary", className)}
    >
      {busy ? <Loader2 className="animate-spin" /> : current ? <BookmarkCheck /> : <Bookmark />}
      {!compact && label}
    </Button>
  );
}
