import { describe, expect, it } from "vitest";
import { docRefHref, docRefName, noteDocuments } from "./doc-ref";
import { istRis } from "./ris";

describe("Unterlagen für Notiz-Verweise", () => {
  it("nimmt, was eine getfile-Kennung hat, je Dokument einmal", () => {
    const docs = noteDocuments([
      { url: "https://ratsinfo.oldenburg.de/bi/vo0050.asp?__kvonr=30078", label: "Vorlage 26/0622" },
      { url: "https://ratsinfo.oldenburg.de/bi/vo0050.asp?__kvonr=30078", label: "Vorlage 26/0622", document_id: 312296, pages: 4, list_no: 1 },
      { url: "https://ratsinfo.oldenburg.de/bi/getfile.asp?id=312295&type=do", label: "Anlage 1" },
      { url: "https://ratsinfo.oldenburg.de/bi/getfile.asp?id=312295&type=do", label: "Anlage 1 (doppelt)" },
      { url: "https://example.org/getfile.asp?id=9", label: "fremd" },
    ], istRis);
    expect(docs.map((d) => [d.documentId, d.label, d.pages, d.listNo])).toEqual([
      [312296, "Vorlage 26/0622", 4, 1], [312295, "Anlage 1", null, null]]);
  });

  it("Seite als Sprungmarke und im Namen", () => {
    const r = { documentId: 1, page: 14, label: "Anlage 1", href: "https://x/getfile.asp?id=1" };
    expect(docRefHref(r)).toBe("https://x/getfile.asp?id=1#page=14");
    expect(docRefName(r)).toBe("Anlage 1, S. 14");
    expect(docRefName({ ...r, page: null })).toBe("Anlage 1");
  });
});
