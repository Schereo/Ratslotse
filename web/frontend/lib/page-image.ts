/* Pictures of document pages for the preview at a note reference
   (`council/page_images.py` renders them). Fetched with the session cookie —
   the endpoint wants an account, and an `<img src>` would not carry it to a
   different origin in local development — and kept as object URLs, so that
   paging back and hovering the same chip again costs nothing. */

import { useEffect, useState } from "react";
import { apiUrl } from "@/lib/api";

/** The widths the server renders. 640 is sharp on a phone at 320 px, 1280
 *  is the enlarged view. */
export type PageWidth = 320 | 640 | 1280;

const MAX = 40;
const cache = new Map<string, Promise<string>>();

export function pageImagePath(documentId: number, page: number, width: PageWidth = 640): string {
  return `/council/documents/${documentId}/page/${page}?w=${width}`;
}

/** The page as an object URL. Rejects when there is no preview (scan too
 *  large, Ratsinfo down, no renderer on this server). */
export function pageImage(documentId: number, page: number, width: PageWidth = 640): Promise<string> {
  const key = `${documentId}:${page}:${width}`;
  const hit = cache.get(key);
  if (hit) {
    // Zuletzt benutzt nach hinten: Verdrängt wird von vorn.
    cache.delete(key);
    cache.set(key, hit);
    return hit;
  }
  const p = fetch(apiUrl(pageImagePath(documentId, page, width)), { credentials: "include" })
    .then((r) => {
      if (!r.ok) throw new Error(String(r.status));
      return r.blob();
    })
    .then((b) => URL.createObjectURL(b));
  p.catch(() => cache.delete(key));
  cache.set(key, p);
  while (cache.size > MAX) {
    const [old, url] = cache.entries().next().value as [string, Promise<string>];
    cache.delete(old);
    void url.then((u) => URL.revokeObjectURL(u), () => {});
  }
  return p;
}

export type PageImageState = { src: string | null; state: "idle" | "loading" | "done" | "error" };

export function usePageImage(documentId: number | null, page: number | null, width: PageWidth = 640): PageImageState {
  const [s, setS] = useState<PageImageState>({ src: null, state: "idle" });
  useEffect(() => {
    if (!documentId || !page) {
      setS({ src: null, state: "idle" });
      return;
    }
    let gone = false;
    setS((alt) => ({ src: alt.src, state: "loading" }));
    pageImage(documentId, page, width).then(
      (src) => { if (!gone) setS({ src, state: "done" }); },
      () => { if (!gone) setS({ src: null, state: "error" }); });
    return () => { gone = true; };
  }, [documentId, page, width]);
  return s;
}
