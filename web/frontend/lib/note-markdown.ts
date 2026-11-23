/* Notes are stored as plain text with a little Markdown and SHOWN formatted
   (Tims Wunsch 23.11.2026: „direkt formatiert gerendert"). This module
   translates between the two: text ⇄ the editor's document (TipTap/
   ProseMirror JSON, `components/notiz/note-field.tsx`).

   Why text stays the stored format: it is encrypted on the device as
   `{ text }`; the iOS app edits the same field in a plain `TextEditor`;
   conflict dialog and export show it as is; and every note written before
   is already valid.

   The format is LINE-based, not CommonMark: one line is one paragraph or one
   list item. In CommonMark two lines without a blank line between them melt
   into one paragraph, and a line under a list item becomes part of it — an
   existing note like

       - Defizit 182 Millionen €
       Konsolidierung durch:

   would change its shape the first time it is opened. Here it does not.

       # Titel            heading            (`## Titel` the smaller one;
                                             `###` and deeper read as `##`)
       - Punkt            bullet list        (also `*` and `+`)
       1. Punkt           ordered list       (also `1)`; the first number is the start)
       - [ ] Aufgabe      task list          (`[x]` ticked)
         - Unterpunkt     two spaces per level nest a list
         Text             indented plain line under an item: its next paragraph
       **fett** *kursiv*  inline, read by `marked` (only emphasis and links —
                          code and HTML stay text), so nesting like
                          `**fett *und kursiv***` survives the round trip
       [Anlage 1, S. 14](https://ratsinfo…/getfile.asp?id=312295#page=14)
                          a reference to a page of a document (`docRef`):
                          a chip in the editor, a readable link in the app.
                          Any other link stays text.

   Everything here is pure and covered by `note-markdown.test.ts`. */

import { Lexer, Tokenizer, defaults, type Token, type Tokens } from "marked";
import { istRis } from "@/lib/ris";
import { docRefName, type DocRefAttrs } from "@/lib/doc-ref";

export type { DocRefAttrs };

export type MarkType = "bold" | "italic";

/** The slice of ProseMirror JSON the notes editor uses. */
export interface NoteNode {
  type: string;
  attrs?: Record<string, unknown>;
  content?: NoteNode[];
  text?: string;
  marks?: { type: MarkType }[];
}

type ListType = "bulletList" | "orderedList" | "taskList";

// ---- inline ---------------------------------------------------------------

/** Only `*`/`_` emphasis, `[…](…)` links and backslash escapes: a note is
 *  not a web page, and text that LOOKS like a code span must come back
 *  unchanged. A link that is not a document reference stays its raw text. */
class EmphasisOnly extends Tokenizer {}
for (const k of ["codespan", "reflink", "autolink", "url", "tag", "del", "br"] as const) {
  (EmphasisOnly.prototype as unknown as Record<string, () => undefined>)[k] = () => undefined;
}

function lexInline(src: string): Token[] {
  return new Lexer({ ...defaults, tokenizer: new EmphasisOnly() }).inlineTokens(src);
}

const GETFILE = /\/getfile\.(?:asp|php)\?(?:[^#]*&)?id=(\d+)/i;

/** A link → a document reference, if it points to a document in the Ratsinfo. */
export function docRefFromLink(href: string, text: string): DocRefAttrs | null {
  if (!istRis(href)) return null;
  const id = GETFILE.exec(href);
  if (!id) return null;
  const [base, hash = ""] = href.split("#");
  const p = /(?:^|&)page=(\d+)/.exec(hash);
  const page = p ? Number(p[1]) : null;
  // „…, S. 14“ steht für die App im Text; im Chip steht die Seite für sich.
  const label = (page ? text.replace(new RegExp(`,\\s*S\\.\\s*${page}$`), "") : text).trim();
  return { documentId: Number(id[1]), page, label: label || "Unterlage", href: base };
}

function plain(tokens: Token[] | undefined): string {
  return (tokens ?? []).map((t) => ("tokens" in t && t.tokens ? plain(t.tokens) : (t as Tokens.Text).text ?? t.raw))
    .join("");
}

function textNode(text: string, marks: MarkType[]): NoteNode {
  const order: MarkType[] = ["bold", "italic"];
  const m = order.filter((x) => marks.includes(x));
  return m.length ? { type: "text", text, marks: m.map((type) => ({ type })) } : { type: "text", text };
}

function pushText(out: NoteNode[], text: string, marks: MarkType[]) {
  if (!text) return;
  const last = out[out.length - 1];
  const sameMarks = last?.type === "text"
    && JSON.stringify(last.marks ?? []) === JSON.stringify(textNode("x", marks).marks ?? []);
  if (last && sameMarks) last.text += text;
  else out.push(textNode(text, marks));
}

function inlineNodes(tokens: Token[], marks: MarkType[], out: NoteNode[]) {
  for (const t of tokens) {
    if (t.type === "strong" || t.type === "em") {
      const mark: MarkType = t.type === "strong" ? "bold" : "italic";
      inlineNodes((t as Tokens.Strong | Tokens.Em).tokens ?? [], [...marks, mark], out);
    } else if (t.type === "link") {
      const l = t as Tokens.Link;
      const ref = docRefFromLink(l.href, plain(l.tokens));
      if (ref) out.push({ type: "docRef", attrs: { ...ref } });
      // Kein Verweis: als Text, aus Beschriftung und ENTschlüsselter Adresse
      // neu gebaut. Mit `raw` bekäme die Adresse bei jedem Speichern eine
      // Schicht Backslashes mehr (`?__ksinr` → `?\_\_ksinr` → …).
      else pushText(out, `[${plain(l.tokens)}](${l.href}${l.title ? ` "${l.title}"` : ""})`, marks);
    } else if (t.type === "escape" || t.type === "text") {
      pushText(out, (t as Tokens.Text).text, marks);
    } else if ("raw" in t && t.raw) {
      pushText(out, t.raw, marks);
    }
  }
}

export function parseInline(src: string): NoteNode[] {
  const out: NoteNode[] = [];
  inlineNodes(lexInline(src), [], out);
  return out.filter((n) => n.text || n.type !== "text");
}

const PUNCT = /[!-/:-@[-`{-~]/;
const ALNUM = /[\p{L}\p{N}]/u;

/** Escape what `marked` would read as emphasis: every `*`, a `_` that is
 *  not inside a word, and a backslash in front of punctuation. */
function escapeText(s: string): string {
  // Ein Link-Ziel „](…)“ bleibt, wie es ist: Dort hebt `marked` nichts
  // hervor, und `\_` stünde in der App mitten in einer Adresse.
  return s.split(/(\]\([^)\s]*\))/).map((teil, i) => (i % 2 ? teil : escapeEmphasis(teil))).join("");
}

function escapeEmphasis(s: string): string {
  let out = "";
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c === "*") out += "\\*";
    else if (c === "\\" && i + 1 < s.length && PUNCT.test(s[i + 1])) out += "\\\\";
    else if (c === "_" && !(ALNUM.test(s[i - 1] ?? "") && ALNUM.test(s[i + 1] ?? ""))) out += "\\_";
    else out += c;
  }
  return out;
}

const MARKER: Record<MarkType, string> = { bold: "**", italic: "*" };

/** `[Anlage 1, S. 14](…#page=14)` — die Seite auch im Text, für die App. */
export function serializeDocRef(r: DocRefAttrs): string {
  const text = escapeText(docRefName(r)).replace(/[[\]]/g, (c) => "\\" + c);
  return `[${text}](${r.href}${r.page ? `#page=${r.page}` : ""})`;
}

/** Inline nodes back to text. Marks nest like a stack (`**ab*cd***`), and
 *  spaces stay outside the markers — `** fett**` is not bold. */
export function serializeInline(nodes: NoteNode[] | undefined): string {
  let out = "";
  const open: MarkType[] = [];
  const close = (n: number) => {
    const ws = /\s*$/.exec(out)?.[0] ?? "";
    out = out.slice(0, out.length - ws.length);
    for (let i = 0; i < n; i++) out += MARKER[open.pop()!];
    out += ws;
  };
  for (const node of nodes ?? []) {
    if (node.type === "docRef") {
      close(open.length);
      out += serializeDocRef(node.attrs as unknown as DocRefAttrs);
      continue;
    }
    const text = node.text ?? "";
    if (!text) continue;
    if (!text.trim()) { out += text; continue; }
    const want = (node.marks ?? []).map((m) => m.type).filter((m): m is MarkType => m === "bold" || m === "italic");
    // Close from the innermost mark down to the first one this node does not carry.
    const keep = open.findIndex((m) => !want.includes(m));
    if (keep !== -1) close(open.length - keep);
    const lead = /^\s*/.exec(text)![0];
    out += lead;
    for (const m of (["bold", "italic"] as MarkType[]).filter((x) => want.includes(x) && !open.includes(x))) {
      open.push(m);
      out += MARKER[m];
    }
    out += escapeText(text.slice(lead.length));
  }
  close(open.length);
  return out;
}

// ---- blocks ---------------------------------------------------------------

interface Line {
  level: number;
  kind: ListType | "heading" | null;
  content: string;
  checked?: boolean;
  num?: number;
}

const TASK = /^[-*+] \[([ xX])\](?: (.*))?$/;
const BULLET = /^[-*+] (.*)$/;
const ORDERED = /^(\d{1,9})[.)] (.*)$/;
const HEADING = /^(#{1,6}) (.*)$/;

function readLine(raw: string): Line {
  const indent = /^[ \t]*/.exec(raw)![0];
  const level = [...indent].reduce((n, c) => n + (c === "\t" ? 2 : 1), 0) >> 1;
  const rest = raw.slice(indent.length);
  // Eine Überschrift steht ganz links; eingerückt wäre sie Teil eines Punkts.
  let m = indent ? null : HEADING.exec(rest);
  if (m) return { level: Math.min(m[1].length, 2), kind: "heading", content: m[2] };
  m = TASK.exec(rest);
  if (m) return { level, kind: "taskList", content: m[2] ?? "", checked: m[1] !== " " };
  m = BULLET.exec(rest);
  if (m) return { level, kind: "bulletList", content: m[1] };
  m = ORDERED.exec(rest);
  if (m) return { level, kind: "orderedList", content: m[2], num: Number(m[1]) };
  return { level, kind: null, content: raw };
}

function paragraph(src: string): NoteNode {
  const content = parseInline(src);
  return content.length ? { type: "paragraph", content } : { type: "paragraph" };
}

/** Text → editor document. Never fails: anything it does not recognise is a
 *  paragraph with exactly that text. */
export function parseNote(text: string): NoteNode {
  const doc: NoteNode = { type: "doc", content: [] };
  const stack: { level: number; type: ListType; list: NoteNode }[] = [];
  const lastItem = (list: NoteNode) => list.content![list.content!.length - 1];

  for (const raw of text.replace(/\r\n?/g, "\n").split("\n")) {
    const line = readLine(raw);
    if (line.kind === "heading") {
      stack.length = 0;
      const content = parseInline(line.content);
      doc.content!.push({ type: "heading", attrs: { level: line.level }, ...(content.length ? { content } : {}) });
      continue;
    }
    if (line.kind) {
      while (stack.length && stack[stack.length - 1].level > line.level) stack.pop();
      let top = stack[stack.length - 1];
      if (top && top.level === line.level && top.type !== line.kind) { stack.pop(); top = stack[stack.length - 1]; }
      const item: NoteNode = line.kind === "taskList"
        ? { type: "taskItem", attrs: { checked: !!line.checked }, content: [paragraph(line.content)] }
        : { type: "listItem", content: [paragraph(line.content)] };
      if (top && top.level === line.level) {
        top.list.content!.push(item);
        continue;
      }
      const list: NoteNode = { type: line.kind, content: [item] };
      if (line.kind === "orderedList" && line.num !== 1) list.attrs = { start: line.num };
      if (top) lastItem(top.list).content!.push(list);
      else doc.content!.push(list);
      stack.push({ level: line.level, type: line.kind, list });
      continue;
    }
    // An indented plain line right under a list item continues that item.
    const parent = raw.trim() ? [...stack].reverse().find((s) => s.level < line.level) : undefined;
    if (parent) {
      while (stack[stack.length - 1] !== parent) stack.pop();
      lastItem(parent.list).content!.push(paragraph(raw.trim()));
      continue;
    }
    stack.length = 0;
    doc.content!.push(paragraph(raw));
  }
  return doc;
}

/** A line that would read back as a list item, but is not one, gets a
 *  backslash in front of its marker. */
function escapeParagraphStart(s: string): string {
  if (/^([-*+]|#{1,6}) /.test(s)) return "\\" + s;
  const m = /^(\d{1,9})([.)]) /.exec(s);
  if (m) return m[1] + "\\" + s.slice(m[1].length);
  return s;
}

function serializeList(list: NoteNode, level: number, lines: string[]) {
  const indent = "  ".repeat(level);
  let n = typeof list.attrs?.start === "number" ? list.attrs.start : 1;
  for (const item of list.content ?? []) {
    const marker = list.type === "orderedList" ? `${n++}. `
      : list.type === "taskList" ? `- [${item.attrs?.checked ? "x" : " "}] ` : "- ";
    const [first, ...rest] = item.content ?? [];
    let head = first?.type === "paragraph" ? serializeInline(first.content) : "";
    // `[ ] ` at the start of a bullet's text would read back as a task.
    if (list.type !== "taskList" && /^\[[ xX]\]( |$)/.test(head)) head = "\\" + head;
    lines.push(indent + marker + head);
    for (const child of first?.type === "paragraph" ? rest : item.content ?? []) {
      // Was keine Liste ist (auch eine Überschrift im Punkt), wird Folgezeile.
      if (child.type.endsWith("List")) serializeList(child, level + 1, lines);
      else lines.push(indent + "  " + serializeInline(child.content));
    }
  }
}

/** Editor document → text. `parseNote(serializeNote(d))` gives `d` back. */
export function serializeNote(doc: NoteNode): string {
  const lines: string[] = [];
  let afterList = false;
  for (const block of doc.content ?? []) {
    if (block.type === "heading") {
      lines.push(`${"#".repeat(block.attrs?.level === 2 ? 2 : 1)} ${serializeInline(block.content)}`);
      afterList = false;
    } else if (block.type === "paragraph") {
      let s = escapeParagraphStart(serializeInline(block.content));
      // Indented right after a list, it would read back as part of it.
      if (afterList) s = s.trimStart();
      lines.push(s);
      afterList = false;
    } else {
      serializeList(block, 0, lines);
      afterList = true;
    }
  }
  return lines.join("\n");
}
