"use client";

/* A reference to a document page inside a note: the editor node, its chip,
   and the picker that inserts one (Tims Wunsch 23.11.2026). In the stored
   text it is a link to the Ratsinfo (`lib/note-markdown.ts`), here a chip:
   open the PDF on that page, or „Im Chat fragen" — then „Frag den Rat" gets
   document and page (`chat-bridge.tsx`) and answers from that page. */

import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Node, mergeAttributes } from "@tiptap/core";
import { NodeViewWrapper, ReactNodeViewRenderer, type ReactNodeViewProps } from "@tiptap/react";
import { ChevronLeft, ChevronRight, FileText, MessageCircleQuestion, X, ZoomIn } from "lucide-react";
import { useChatBridge } from "@/components/notiz/chat-bridge";
import { PagePreview } from "@/components/notiz/page-preview";
import { PageZoom } from "@/components/notiz/page-zoom";
import { api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";
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

/** Die Vorschau beim Überfahren: nur mit Maus (ein Finger öffnet das PDF
 *  gleich) und für die Tastatur beim Fokus. */
const VORSCHAU_BREIT = 260;
const VORSCHAU_HOCH = Math.round(VORSCHAU_BREIT * 1.414) + 36;

function DocRefChip({ node, selected }: ReactNodeViewProps) {
  const a = node.attrs as DocRefAttrs;
  const bridge = useChatBridge();
  const name = docRefName(a);
  const tipId = useId();
  const link = useRef<HTMLAnchorElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const zeigen = () => {
    const r = link.current?.getBoundingClientRect();
    if (!r) return;
    const left = Math.min(Math.max(8, r.left), window.innerWidth - VORSCHAU_BREIT - 8);
    const unten = r.bottom + 6 + VORSCHAU_HOCH <= window.innerHeight;
    setPos({ left, top: unten ? r.bottom + 6 : Math.max(8, r.top - 6 - VORSCHAU_HOCH) });
  };
  const verbergen = () => {
    if (timer.current) clearTimeout(timer.current);
    setPos(null);
  };

  return (
    <NodeViewWrapper as="span" data-doc-ref=""
      className={cn("mx-0.5 inline-flex max-w-[calc(100%-0.5rem)] items-center gap-0.5 rounded-md border border-primary/30 bg-primary/[0.06] align-baseline text-[13px] leading-6",
        selected && "ring-2 ring-ring")}>
      <a ref={link} href={docRefHref(a)} target="_blank" rel="noreferrer" contentEditable={false}
        title={pos ? undefined : `${name} öffnen`} aria-label={`${name} öffnen`} aria-describedby={pos ? tipId : undefined}
        // ProseMirror soll den Klick nicht als Auswahl verstehen.
        onMouseDown={(e) => e.stopPropagation()}
        onMouseEnter={() => {
          if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
          timer.current = setTimeout(zeigen, 350);
        }}
        onMouseLeave={verbergen}
        onFocus={(e) => { if (e.currentTarget.matches(":focus-visible")) zeigen(); }}
        onBlur={verbergen}
        onKeyDown={(e) => { if (e.key === "Escape" && pos) { e.preventDefault(); verbergen(); } }}
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
      {pos && createPortal(
        // Ins <body>: Das Notizfeld scrollt selbst und schnitte die Vorschau ab.
        <span role="tooltip" id={tipId} contentEditable={false}
          style={{ left: pos.left, top: pos.top, width: VORSCHAU_BREIT, zIndex: "var(--level-schwebend)" }}
          className="pointer-events-none fixed block rounded-lg border border-border bg-popover p-2 text-popover-foreground shadow-lg">
          <PagePreview documentId={a.documentId} page={a.page ?? 1} label={a.label} />
          <span className="mt-1.5 block truncate text-xs text-muted-foreground">
            {a.page ? `Seite ${a.page}` : "Seite 1 · ganze Unterlage"} · {a.label}
          </span>
        </span>,
        document.body)}
    </NodeViewWrapper>
  );
}

/** Die Auswahl unter der Leiste: welche Unterlage, welche Seite — mit der
 *  Seite als Bild daneben, damit man sieht, was man einfügt. */
export function DocRefPicker({ documents, onInsert, onClose }: {
  documents: NoteDocument[];
  onInsert: (ref: DocRefAttrs) => void;
  onClose: () => void;
}) {
  const id = useId();
  const [chosen, setChosen] = useState<number | null>(documents.length === 1 ? documents[0].documentId : null);
  const [page, setPage] = useState("");
  const [counted, setCounted] = useState<Record<number, number>>({});
  const gefragt = useRef(new Set<number>());
  const first = useRef<HTMLInputElement>(null);
  useEffect(() => { first.current?.focus(); }, []);
  const doc = documents.find((d) => d.documentId === chosen) ?? null;
  const total = doc ? (doc.pages ?? counted[doc.documentId] ?? null) : null;

  // Seitenzahl unbekannt (kein Steckbrief): einmal je Unterlage beim Server
  // nachfragen — auch wenn es scheitert, nicht noch einmal.
  const docId = doc?.documentId ?? null;
  const docPages = doc?.pages ?? null;
  useEffect(() => {
    if (docId == null || docPages || gefragt.current.has(docId)) return;
    gefragt.current.add(docId);
    api.get<ApiAntwort<"/council/documents/{document_id}/pages">>(`/council/documents/${docId}/pages`)
      .then((r) => setCounted((c) => ({ ...c, [r.document_id]: r.n_pages })))
      .catch(() => { /* ohne Zahl blättert man eben ohne Ende */ });
  }, [docId, docPages]);

  const n = Number(page);
  const pageOk = !page || (Number.isInteger(n) && n >= 1 && (!total || n <= total));
  // Die Vorschau folgt dem Tippen mit kurzem Abstand — nicht jede Ziffer ist ein Abruf.
  const [shown, setShown] = useState(1);
  useEffect(() => {
    const t = setTimeout(() => setShown(page && pageOk ? n : 1), page ? 250 : 0);
    return () => clearTimeout(t);
  }, [page, pageOk, n]);
  const blaettern = (d: number) => {
    const next = Math.max(1, (page && pageOk ? n : 1) + d);
    if (total && next > total) return;
    setPage(String(next));
    setShown(next);   // Geblättert wird ohne die Verzögerung fürs Tippen.
  };
  const insert = () => {
    if (!doc || !pageOk) return;
    onInsert({ documentId: doc.documentId, page: page ? n : null, label: doc.label, href: doc.href });
  };
  const [zoom, setZoom] = useState(false);
  const KNOPF = "inline-flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-40 desk:h-8 desk:w-8";
  return (
    <div role="group" aria-labelledby={`${id}-t`} className="border-b border-border bg-muted/40 px-3 py-2.5"
      onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); onClose(); } }}>
      <div className="flex items-center justify-between gap-2">
        <p id={`${id}-t`} className="text-sm font-medium text-foreground">Unterlage verweisen</p>
        <button type="button" onClick={onClose} aria-label="Schließen" className={KNOPF}>
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>
      <div className="mt-1 grid grid-cols-1 gap-3 sm:grid-cols-[minmax(0,1fr)_200px]">
        <div className="min-w-0">
          {/* `min-w-0`: Ein fieldset ist ab Werk mindestens so breit wie sein
              längster Titel — auf dem Telefon schob das die Seite 74 px zur Seite. */}
          <fieldset className="min-w-0">
            <legend className="sr-only">Welche Unterlage?</legend>
            <ul className="max-h-64 space-y-0.5 overflow-y-auto">
              {documents.map((d, i) => (
                <li key={d.documentId}>
                  <label className={cn("flex min-h-11 cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-accent desk:min-h-9",
                    chosen === d.documentId && "bg-primary/[0.08]")}>
                    <input ref={i === 0 ? first : undefined} type="radio" name={`${id}-doc`} checked={chosen === d.documentId}
                      onChange={() => { setChosen(d.documentId); setPage(""); }} className="accent-primary" />
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
              <input type="number" inputMode="numeric" min={1} max={total ?? undefined} value={page}
                onChange={(e) => setPage(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); insert(); } }}
                aria-invalid={!pageOk} className="mt-0.5 h-11 w-28 rounded-lg border border-input bg-background px-2 text-sm desk:h-9" />
            </label>
            <button type="button" onClick={insert} disabled={!doc || !pageOk}
              className="inline-flex h-11 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 desk:h-9">
              Einfügen
            </button>
            {!pageOk && total && <p className="w-full text-xs text-destructive" role="alert">Die Unterlage hat {total} Seiten.</p>}
          </div>
        </div>
        <figure className="mx-auto w-full max-w-[200px]">
          {doc ? (
            <button type="button" onClick={() => setZoom(true)} aria-label={`Seite ${shown} größer anzeigen`}
              title="Größer anzeigen"
              className="group relative block w-full cursor-zoom-in rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <PagePreview documentId={doc.documentId} page={shown} label={doc.label} />
              <span aria-hidden className="absolute bottom-1.5 right-1.5 inline-flex h-7 w-7 items-center justify-center rounded-md border border-border bg-card/90 text-foreground shadow-sm group-hover:bg-card">
                <ZoomIn className="h-4 w-4" />
              </span>
            </button>
          ) : (
            <PagePreview documentId={null} page={null} label="" />
          )}
          <figcaption className="mt-1 flex items-center justify-between gap-1 text-xs text-muted-foreground">
            <button type="button" onClick={() => blaettern(-1)} disabled={!doc || shown <= 1} aria-label="Vorige Seite" className={KNOPF}>
              <ChevronLeft className="h-4 w-4" aria-hidden />
            </button>
            <span aria-live="polite">{doc ? `Seite ${shown}${total ? ` von ${total}` : ""}` : "–"}</span>
            <button type="button" onClick={() => blaettern(1)} disabled={!doc || (total != null && shown >= total)} aria-label="Nächste Seite" className={KNOPF}>
              <ChevronRight className="h-4 w-4" aria-hidden />
            </button>
          </figcaption>
        </figure>
      </div>
      {doc && (
        <PageZoom open={zoom} onOpenChange={setZoom} documentId={doc.documentId} label={doc.label} page={shown}
          total={total} onPage={(p) => { setPage(String(p)); setShown(p); }}
          onInsert={() => { setZoom(false); onInsert({ documentId: doc.documentId, page: shown, label: doc.label, href: doc.href }); }} />
      )}
    </div>
  );
}
