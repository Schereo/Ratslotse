/* A reference from a note to a page of a document in the Ratsinfo — the
   shape that note, editor and chat share. Kept apart from the editor
   (`components/notiz/doc-ref.tsx`, TipTap) and from the text format
   (`lib/note-markdown.ts`, marked): the chat on every item page needs these
   three lines, not those libraries. */

export interface DocRefAttrs {
  documentId: number;
  page: number | null;
  label: string;
  /** The document's address, without `#page`. */
  href: string;
}

/** Die Adresse mit Sprungmarke: `#page=` verstehen die PDF-Anzeigen der Browser. */
export const docRefHref = (r: Pick<DocRefAttrs, "href" | "page">) => (r.page ? `${r.href}#page=${r.page}` : r.href);

/** „Anlage 1, S. 14“ — so steht der Verweis auch im gespeicherten Text. */
export const docRefName = (r: Pick<DocRefAttrs, "label" | "page">) => (r.page ? `${r.label}, S. ${r.page}` : r.label);

/** A document of the page that a note can point to. */
export interface NoteDocument {
  documentId: number;
  label: string;
  href: string;
  pages?: number | null;
  /** Die Nummer in der Liste „Unterlagen“ der Seite. */
  listNo?: number | null;
}

const GETFILE_ID = /\/getfile\.(?:asp|php)\?(?:[^#]*&)?id=(\d+)/i;

/** Die Unterlagen eines Punkts, auf deren Seiten eine Notiz verweisen kann:
 *  alles mit getfile-Kennung — Vorlage, Anlagen, Protokolle früherer
 *  Stationen. Die Kennung steht im Feld oder in der Adresse. */
export function noteDocuments(docs: { document_id?: number; url: string; label: string; pages?: number | null;
  list_no?: number }[], istRis: (url: string) => boolean): NoteDocument[] {
  const out: NoteDocument[] = [];
  for (const d of docs) {
    const id = d.document_id ?? Number(GETFILE_ID.exec(d.url)?.[1] ?? 0);
    if (!id || !istRis(d.url) || out.some((x) => x.documentId === id)) continue;
    out.push({ documentId: id, label: d.label, href: d.url, pages: d.pages ?? null, listNo: d.list_no ?? null });
  }
  return out;
}
