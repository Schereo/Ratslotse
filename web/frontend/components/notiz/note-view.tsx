/* A note shown read-only and formatted — where the conflict dialog offers
   the other device's version. Same reading as the editor
   (`lib/note-markdown.ts`), so what you see here is what „übernehmen" gives. */

import type { ReactNode } from "react";
import { parseNote, type NoteNode } from "@/lib/note-markdown";

function inline(nodes: NoteNode[] | undefined): ReactNode[] {
  return (nodes ?? []).map((n, i) => {
    let el: ReactNode = n.text;
    for (const m of n.marks ?? []) el = m.type === "bold" ? <strong key={i}>{el}</strong> : <em key={i}>{el}</em>;
    return <span key={i}>{el}</span>;
  });
}

function block(n: NoteNode, i: number): ReactNode {
  const kids = (n.content ?? []).map(block);
  switch (n.type) {
    case "paragraph": return <p key={i} className="min-h-[1lh]">{inline(n.content)}</p>;
    case "bulletList": return <ul key={i} className="list-disc pl-5">{kids}</ul>;
    case "orderedList": return <ol key={i} start={(n.attrs?.start as number) ?? 1} className="list-decimal pl-5">{kids}</ol>;
    case "taskList": return <ul key={i} className="list-none pl-0">{kids}</ul>;
    case "listItem": return <li key={i}>{kids}</li>;
    case "taskItem": {
      const done = !!n.attrs?.checked;
      return (
        <li key={i} className="flex items-start gap-2">
          <input type="checkbox" checked={done} disabled readOnly aria-label={done ? "erledigt" : "offen"} className="mt-[0.3em] accent-primary" />
          <div className={done ? "line-through opacity-70" : undefined}>{kids}</div>
        </li>
      );
    }
    default: return null;
  }
}

export function NoteView({ text, className }: { text: string; className?: string }) {
  return <div className={className}>{(parseNote(text).content ?? []).map(block)}</div>;
}
