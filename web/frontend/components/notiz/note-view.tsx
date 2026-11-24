/* A note shown read-only and formatted — where the conflict dialog offers
   the other device's version. Same reading as the editor
   (`lib/note-markdown.ts`), so what you see here is what „übernehmen" gives. */

import type { ReactNode } from "react";
import { FileText } from "lucide-react";
import { docRefHref, docRefName, type DocRefAttrs } from "@/lib/doc-ref";
import { parseNote, type NoteNode } from "@/lib/note-markdown";

function inline(nodes: NoteNode[] | undefined): ReactNode[] {
  return (nodes ?? []).map((n, i) => {
    if (n.type === "docRef") {
      const r = n.attrs as unknown as DocRefAttrs;
      return (
        <a key={i} href={docRefHref(r)} target="_blank" rel="noreferrer"
          className="mx-0.5 inline-flex items-center gap-1 rounded-md border border-current/30 px-1 not-italic underline-offset-2 hover:underline">
          <FileText className="h-3.5 w-3.5" aria-hidden /> {docRefName(r)}
        </a>
      );
    }
    let el: ReactNode = n.text;
    for (const m of n.marks ?? []) el = m.type === "bold" ? <strong key={i}>{el}</strong> : <em key={i}>{el}</em>;
    return <span key={i}>{el}</span>;
  });
}

function block(n: NoteNode, i: number): ReactNode {
  const kids = (n.content ?? []).map(block);
  switch (n.type) {
    case "paragraph": return <p key={i} className="min-h-[1lh]">{inline(n.content)}</p>;
    // h3/h4 wie im Editor: Die Karte drumherum ist schon ein h2.
    case "heading": return n.attrs?.level === 2
      ? <h4 key={i} className="mt-2 font-semibold first:mt-0">{inline(n.content)}</h4>
      : <h3 key={i} className="mt-3 font-display text-base font-semibold first:mt-0">{inline(n.content)}</h3>;
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
