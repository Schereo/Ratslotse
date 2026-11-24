"use client";

/* The text field of „Meine Notiz" and „Mein Mitschrieb": formatted while
   you type, stored as plain text with a little Markdown. The editor itself
   (`note-editor.tsx`, TipTap) is loaded only when a note is open — a page
   without one carries none of it. */

import dynamic from "next/dynamic";
import type { NoteEditorProps } from "@/components/notiz/note-editor";
import { cn } from "@/lib/utils";

const NoteEditor = dynamic(() => import("@/components/notiz/note-editor"), {
  ssr: false,
  // Hält die Höhe, bis der Editor da ist — sonst springt die Karte.
  loading: () => (
    <div aria-hidden className="rounded-xl border border-input bg-background">
      <div className="h-[53px] border-b border-border desk:h-[45px]" />
      <div className="h-32 animate-pulse bg-muted/40" />
    </div>
  ),
});

export function NoteField(props: NoteEditorProps) {
  return <NoteEditor {...props} className={cn(props.className)} />;
}
