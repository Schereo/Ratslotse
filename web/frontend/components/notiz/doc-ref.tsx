"use client";

/* A reference to a document page inside a note: the editor node, its chip,
   and the picker that inserts one (Tims Wunsch 23.11.2026). In the stored
   text it is a link to the Ratsinfo (`lib/note-markdown.ts`), here a chip:
   open the PDF on that page, or „Im Chat fragen" — then „Frag den Rat" gets
   document and page (`chat-bridge.tsx`) and answers from that page. */

import { useEffect, useId, useRef, useState } from "react";
import { Node, mergeAttributes } from "@tiptap/core";
import { NodeViewWrapper, ReactNodeViewRenderer, type ReactNodeViewProps } from "@tiptap/react";
import { FileText, MessageCircleQuestion, X } from "lucide-react";
import { useChatBridge } from "@/components/notiz/chat-bridge";
import { docRefHref, docRefName, type DocRefAttrs, type NoteDocument } from "@/lib/doc-ref";
import { cn } from "@/lib/utils";

export const DocRefNode = Node.create({
  name: "docRef",
  group: "inline",
  inline: true,
  atom: true,
  selectable: true,
  addAttributes() {
    return {
      documentId: { default: null },
      page: { default: null },
      label: { default: "Unterlage" },
      href: { default: "" },
    };
  },
  parseHTML() {
    return [{
      tag: "span[data-doc-ref]",
      getAttrs: (el) => {
        const e = el as HTMLElement;
        const page = Number(e.dataset.page);
        return { documentId: Number(e.dataset.documentId), page: page > 0 ? page : null,
                 label: e.dataset.label ?? "Unterlage", href: e.dataset.href ?? "" };
      },
    }];
  },
  // Beim Kopieren: ein Link mit lesbarem Text, den auch andere Programme verstehen.
  renderHTML({ node }) {
    const a = node.attrs as DocRefAttrs;
    return ["span", mergeAttributes({ "data-doc-ref": "", "data-document-id": a.documentId,
      "data-page": a.page ?? "", "data-label": a.label, "data-href": a.href }),
    ["a", { href: docRefHref(a) }, docRefName(a)]];
  },
  renderText({ node }) {
    return docRefName(node.attrs as DocRefAttrs);
  },
  addNodeView() {
    return ReactNodeViewRenderer(DocRefChip, { as: "span" });
  },
});

function DocRefChip({ node, selected }: ReactNodeViewProps) {
  const a = node.attrs as DocRefAttrs;
  const bridge = useChatBridge();
  const name = docRefName(a);
  return (
    <NodeViewWrapper as="span" data-doc-ref=""
      className={cn("mx-0.5 inline-flex max-w-[calc(100%-0.5rem)] items-center gap-0.5 rounded-md border border-primary/30 bg-primary/[0.06] align-baseline text-[13px] leading-6",
        selected && "ring-2 ring-ring")}>
      <a href={docRefHref(a)} target="_blank" rel="noreferrer" contentEditable={false}
        title={`${name} öffnen`} aria-label={`${name} öffnen`}
        // ProseMirror soll den Klick nicht als Auswahl verstehen.
        onMouseDown={(e) => e.stopPropagation()}
        className="inline-flex min-w-0 items-center gap-1 rounded-l-md py-0 pl-1.5 pr-1 text-foreground no-underline hover:bg-primary/[0.08]">
        <FileText className="h-3.5 w-3.5 flex-none text-primary" aria-hidden />
        <span className="max-w-[26ch] truncate">{a.label}</span>
        {a.page && <span className="flex-none text-muted-foreground">S. {a.page}</span>}
      </a>
      {bridge?.ask && (
        <button type="button" contentEditable={false} title="Im Chat fragen" aria-label={`Im Chat fragen: ${name}`}
          onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); }}
          onClick={() => bridge.ask?.({ ...a })}
          className="inline-flex h-6 w-7 flex-none items-center justify-center rounded-r-md border-l border-primary/20 text-primary hover:bg-primary/[0.12]">
          <MessageCircleQuestion className="h-3.5 w-3.5" aria-hidden />
        </button>
      )}
    </NodeViewWrapper>
  );
}

/** Die Auswahl unter der Leiste: welche Unterlage, welche Seite. */
export function DocRefPicker({ documents, onInsert, onClose }: {
  documents: NoteDocument[];
  onInsert: (ref: DocRefAttrs) => void;
  onClose: () => void;
}) {
  const id = useId();
  const [chosen, setChosen] = useState<number | null>(documents.length === 1 ? documents[0].documentId : null);
  const [page, setPage] = useState("");
  const first = useRef<HTMLInputElement>(null);
  useEffect(() => { first.current?.focus(); }, []);
  const doc = documents.find((d) => d.documentId === chosen) ?? null;
  const n = Number(page);
  const pageOk = !page || (Number.isInteger(n) && n >= 1 && (!doc?.pages || n <= doc.pages));
  const insert = () => {
    if (!doc || !pageOk) return;
    onInsert({ documentId: doc.documentId, page: page ? n : null, label: doc.label, href: doc.href });
  };
  return (
    <div role="group" aria-labelledby={`${id}-t`} className="border-b border-border bg-muted/40 px-3 py-2.5"
      onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); onClose(); } }}>
      <div className="flex items-center justify-between gap-2">
        <p id={`${id}-t`} className="text-sm font-medium text-foreground">Unterlage verweisen</p>
        <button type="button" onClick={onClose} aria-label="Schließen"
          className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground desk:h-8 desk:w-8">
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>
      <fieldset className="mt-1">
        <legend className="sr-only">Welche Unterlage?</legend>
        <ul className="max-h-56 space-y-0.5 overflow-y-auto">
          {documents.map((d, i) => (
            <li key={d.documentId}>
              <label className={cn("flex min-h-11 cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-accent desk:min-h-9",
                chosen === d.documentId && "bg-primary/[0.08]")}>
                <input ref={i === 0 ? first : undefined} type="radio" name={`${id}-doc`} checked={chosen === d.documentId}
                  onChange={() => setChosen(d.documentId)} className="accent-primary" />
                {d.listNo != null && <span className="w-5 flex-none text-right font-mono text-[11px] text-muted-foreground">{d.listNo}</span>}
                <span className="min-w-0 flex-1 truncate text-foreground">{d.label}</span>
                {d.pages ? <span className="flex-none text-xs text-muted-foreground">{d.pages} S.</span> : null}
              </label>
            </li>
          ))}
        </ul>
      </fieldset>
      <div className="mt-2 flex flex-wrap items-end gap-2">
        <label className="text-sm text-foreground">
          <span className="block text-xs text-muted-foreground">Seite (leer = ganze Unterlage)</span>
          <input type="number" inputMode="numeric" min={1} max={doc?.pages ?? undefined} value={page}
            onChange={(e) => setPage(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); insert(); } }}
            aria-invalid={!pageOk} className="mt-0.5 h-11 w-28 rounded-lg border border-input bg-background px-2 text-sm desk:h-9" />
        </label>
        <button type="button" onClick={insert} disabled={!doc || !pageOk}
          className="inline-flex h-11 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 desk:h-9">
          Einfügen
        </button>
        {!pageOk && doc?.pages && <p className="w-full text-xs text-destructive" role="alert">Die Unterlage hat {doc.pages} Seiten.</p>}
      </div>
    </div>
  );
}
