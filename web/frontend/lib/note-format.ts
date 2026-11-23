/* Formatting for the notes field (`components/notiz/note-field.tsx`).

   Notes stay plain text with a little Markdown in it: `**fett**`, `*kursiv*`,
   `- Punkt`, `1. Punkt`, `- [ ] Aufgabe`. Why not a rich-text editor: the
   text is encrypted on the device and stored as `{ text }`; the iOS app edits
   the same field in a plain `TextEditor`, the conflict dialog and the export
   show it as is. Markdown reads fine in all three, HTML would not, and a
   note written before this change is already valid.

   Every function here is pure: it takes the value and the selection and
   returns ONE replacement (`Edit`), which the field applies through the
   browser's own text insertion so that undo keeps working. */

export type ListKind = "bullet" | "number" | "task";

export interface Edit {
  /** Replace `value.slice(from, to)` … */
  from: number;
  to: number;
  /** … with this, then select `selStart`–`selEnd`. */
  insert: string;
  selStart: number;
  selEnd: number;
}

export interface LineInfo {
  kind: ListKind | null;
  indent: string;
  /** Length of indent plus list marker, i.e. where the content starts. */
  prefixLen: number;
  marker?: string;
  num?: number;
  delim?: string;
  checked?: boolean;
}

const TASK = /^(\s*)([-*+]) \[([ xX])\] /;
const BULLET = /^(\s*)([-*+]) /;
const NUMBER = /^(\s*)(\d{1,9})([.)]) /;

export function lineInfo(line: string): LineInfo {
  let m = TASK.exec(line);
  if (m) return { kind: "task", indent: m[1], prefixLen: m[0].length, marker: m[2], checked: m[3] !== " " };
  m = BULLET.exec(line);
  if (m) return { kind: "bullet", indent: m[1], prefixLen: m[0].length, marker: m[2] };
  m = NUMBER.exec(line);
  if (m) return { kind: "number", indent: m[1], prefixLen: m[0].length, num: Number(m[2]), delim: m[3] };
  const indent = /^\s*/.exec(line)?.[0] ?? "";
  return { kind: null, indent, prefixLen: indent.length };
}

/** Start and end of the lines the selection touches. A selection that ends
 *  right after a line break does not touch the next line. */
function lineSpan(value: string, start: number, end: number): { from: number; to: number } {
  const from = value.lastIndexOf("\n", start - 1) + 1;
  const last = end > start && value[end - 1] === "\n" ? end - 1 : end;
  const nl = value.indexOf("\n", last);
  return { from, to: nl === -1 ? value.length : nl };
}

/** Which list the caret's line belongs to — for the pressed state of the
 *  toolbar buttons. */
export function activeList(value: string, caret: number): ListKind | null {
  const { from, to } = lineSpan(value, caret, caret);
  return lineInfo(value.slice(from, to)).kind;
}

function prefixFor(kind: ListKind, indent: string, n: number): string {
  if (kind === "bullet") return `${indent}- `;
  if (kind === "task") return `${indent}- [ ] `;
  return `${indent}${n}. `;
}

/** Turn the selected lines into a list of `kind` — or back into plain lines
 *  when they all are one already. Another kind of list is converted. */
export function toggleList(value: string, start: number, end: number, kind: ListKind): Edit {
  const { from, to } = lineSpan(value, start, end);
  const lines = value.slice(from, to).split("\n");
  const infos = lines.map(lineInfo);
  const filled = lines.map((l, i) => l.slice(infos[i].prefixLen).trim() !== "" || infos[i].kind !== null);
  const relevant = infos.filter((_, i) => filled[i] || lines.length === 1);
  const remove = relevant.length > 0 && relevant.every((x) => x.kind === kind);

  let n = 0;
  const out = lines.map((line, i) => {
    const info = infos[i];
    const content = line.slice(info.prefixLen);
    if (remove) return info.indent + content;
    // Empty lines between items stay empty; a single empty line becomes an item.
    if (!filled[i] && lines.length > 1) return line;
    n += 1;
    return prefixFor(kind, info.indent, n) + content;
  });
  const insert = out.join("\n");

  if (start === end && lines.length === 1) {
    // Keep the caret on the same character of the content.
    const oldPrefix = infos[0].prefixLen;
    const newPrefix = insert.length - (lines[0].length - oldPrefix);
    const inContent = Math.max(0, start - from - oldPrefix);
    const caret = from + newPrefix + inContent;
    return { from, to, insert, selStart: caret, selEnd: caret };
  }
  return { from, to, insert, selStart: from, selEnd: from + insert.length };
}

const WORD = /[\p{L}\p{N}_-]/u;

function starsBefore(value: string, i: number): number {
  let n = 0;
  while (i - n - 1 >= 0 && value[i - n - 1] === "*") n++;
  return n;
}

function starsAfter(value: string, i: number): number {
  let n = 0;
  while (i + n < value.length && value[i + n] === "*") n++;
  return n;
}

/** Does a run of `n` stars carry this emphasis? `***x***` is both. */
function carries(n: number, marker: "**" | "*"): boolean {
  return marker === "**" ? n >= 2 : n % 2 === 1;
}

/** `**fett**` or `*kursiv*` around the selection — or off again. Without a
 *  selection the word under the caret is meant; between words a pair of
 *  markers is inserted with the caret in the middle. */
export function toggleWrap(value: string, start: number, end: number, marker: "**" | "*"): Edit {
  let s = start;
  let e = end;
  if (s === e) {
    while (s > 0 && WORD.test(value[s - 1])) s--;
    while (e < value.length && WORD.test(value[e])) e++;
  } else {
    // `** fett**` is not bold in Markdown: leave the spaces outside.
    while (s < e && /\s/.test(value[s])) s++;
    while (e > s && /\s/.test(value[e - 1])) e--;
  }
  const m = marker.length;

  if (s === e) {
    const insert = marker + marker;
    return { from: s, to: e, insert, selStart: s + m, selEnd: s + m };
  }

  const sel = value.slice(s, e);
  if (sel.includes("\n")) {
    // Markdown emphasis does not cross lines: one pair per line.
    const { from, to } = lineSpan(value, s, e);
    const lines = value.slice(from, to).split("\n");
    const parts = lines.map((line) => {
      const p = lineInfo(line).prefixLen;
      const content = line.slice(p);
      const lead = /^\s*/.exec(content)?.[0] ?? "";
      const core = content.trim();
      return { head: line.slice(0, p) + lead, core, tail: content.slice(lead.length + core.length) };
    });
    const wrapped = (c: string) =>
      c.length > 2 * m && c.startsWith(marker) && c.endsWith(marker) && carries(starsAfter(c, 0), marker);
    const all = parts.filter((x) => x.core).every((x) => wrapped(x.core));
    const insert = parts.map(({ head, core, tail }) => {
      if (!core) return head + tail;
      return head + (all ? core.slice(m, -m) : marker + core + marker) + tail;
    }).join("\n");
    return { from, to, insert, selStart: from, selEnd: from + insert.length };
  }

  // Markers just outside the selection: take them away.
  const before = starsBefore(value, s);
  const after = starsAfter(value, e);
  if (carries(Math.min(before, after), marker)) {
    return { from: s - m, to: e + m, insert: sel, selStart: s - m, selEnd: e - m };
  }
  // Markers inside the selection: take them away.
  const inBefore = starsAfter(sel, 0);
  const inAfter = starsBefore(sel, sel.length);
  if (sel.length > 2 * m && carries(Math.min(inBefore, inAfter), marker)) {
    const inner = sel.slice(m, -m);
    return { from: s, to: e, insert: inner, selStart: s, selEnd: s + inner.length };
  }
  return { from: s, to: e, insert: marker + sel + marker, selStart: s + m, selEnd: e + m };
}

/** Enter inside a list item: the next item gets the same marker (numbers
 *  count up, tasks start open). Enter on an EMPTY item ends the list.
 *  `null` = not a list line, the browser's own line break is right. */
export function continueList(value: string, start: number, end: number): Edit | null {
  if (start !== end) return null;
  const from = value.lastIndexOf("\n", start - 1) + 1;
  const nl = value.indexOf("\n", start);
  const to = nl === -1 ? value.length : nl;
  const line = value.slice(from, to);
  const info = lineInfo(line);
  if (!info.kind || start < from + info.prefixLen) return null;

  if (line.slice(info.prefixLen).trim() === "") {
    return { from, to, insert: "", selStart: from, selEnd: from };
  }
  const next = info.kind === "number"
    ? `${info.indent}${(info.num ?? 0) + 1}${info.delim ?? "."} `
    : info.kind === "task" ? `${info.indent}${info.marker ?? "-"} [ ] ` : `${info.indent}${info.marker ?? "-"} `;
  const insert = "\n" + next;
  return { from: start, to: start, insert, selStart: start + insert.length, selEnd: start + insert.length };
}

/** Tick or untick the task on the caret's line. `null` = no task there. */
export function toggleTask(value: string, caret: number): Edit | null {
  const { from, to } = lineSpan(value, caret, caret);
  const info = lineInfo(value.slice(from, to));
  if (info.kind !== "task") return null;
  const box = from + info.prefixLen - 3; // the character between the brackets
  return { from: box, to: box + 1, insert: info.checked ? " " : "x", selStart: caret, selEnd: caret };
}

/** Apply an edit to a string — what the field does in the DOM, for tests. */
export function applyEdit(value: string, e: Edit): string {
  return value.slice(0, e.from) + e.insert + value.slice(e.to);
}
