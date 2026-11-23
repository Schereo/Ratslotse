"use client";

/* The notes editor: formatted while you type (Tims Wunsch 23.11.2026: „die
   notizen schon direkt formatiert gerendert"), stored as plain text with a
   little Markdown (`lib/note-markdown.ts` says why and how).

   TipTap 3 with only what a note needs: paragraphs, two sizes of heading,
   bold, italic, three kinds of list. No quotes, code or links — every node
   here must have a line in the text format, or it would be lost on the way
   back. No hard line break either (Shift+Enter): one line is one paragraph.

   Headings are levels 1 and 2 (`#`, `##`, ⌘⌥1/2 — what people know) but
   render as h3/h4: the card around the note is already an h2, and an h1
   inside it would break the page's outline.

   Loaded on demand by `note-field.tsx`; nothing of this reaches a page
   without an unlocked note. */

import { useEffect, useRef, useState } from "react";
import { EditorContent, mergeAttributes, useEditor, useEditorState, type Editor, type JSONContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Heading } from "@tiptap/extension-heading";
import { TaskItem, TaskList } from "@tiptap/extension-list";
import { CharacterCount, Placeholder } from "@tiptap/extensions";
import { Bold, Heading1, Heading2, Italic, List, ListChecks, ListOrdered, type LucideIcon } from "lucide-react";
import { parseNote, serializeNote, type NoteNode } from "@/lib/note-markdown";
import { cn } from "@/lib/utils";

export interface NoteEditorProps {
  id: string;
  /** Für Screenreader: was in das Feld gehört. */
  label: string;
  value: string;
  onChange: (text: string) => void;
  onBlur?: () => void;
  disabled?: boolean;
  /** Mindesthöhe in Zeilen. */
  rows?: number;
  placeholder?: string;
  className?: string;
}

const MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.userAgent);
const MOD = MAC ? "⌘" : "Strg+";

type Action = {
  key: string;
  label: string; shortcut: string; icon: LucideIcon;
  run: (e: Editor) => boolean;
  active: (e: Editor) => boolean;
  /** Beginnt eine neue Gruppe in der Leiste. */
  group?: boolean;
};

const ALT = MAC ? "⌥" : "Alt+";

// Die Kürzel sind TipTaps eigene — dieselben wie in Google Docs und Notion.
const ACTIONS: Action[] = [
  { key: "h1", label: "Überschrift", shortcut: `${MOD}${ALT}1`, icon: Heading1,
    run: (e) => e.chain().focus().toggleHeading({ level: 1 }).run(), active: (e) => e.isActive("heading", { level: 1 }) },
  { key: "h2", label: "Zwischenüberschrift", shortcut: `${MOD}${ALT}2`, icon: Heading2,
    run: (e) => e.chain().focus().toggleHeading({ level: 2 }).run(), active: (e) => e.isActive("heading", { level: 2 }) },
  { key: "bold", group: true, label: "Fett", shortcut: `${MOD}B`, icon: Bold, run: (e) => e.chain().focus().toggleBold().run(),
    active: (e) => e.isActive("bold") },
  { key: "italic", label: "Kursiv", shortcut: `${MOD}I`, icon: Italic, run: (e) => e.chain().focus().toggleItalic().run(),
    active: (e) => e.isActive("italic") },
  { key: "bulletList", label: "Aufzählung", shortcut: `${MOD}⇧8`, icon: List, group: true,
    run: (e) => e.chain().focus().toggleBulletList().run(), active: (e) => e.isActive("bulletList") },
  { key: "orderedList", label: "Nummerierte Liste", shortcut: `${MOD}⇧7`, icon: ListOrdered,
    run: (e) => e.chain().focus().toggleOrderedList().run(), active: (e) => e.isActive("orderedList") },
  { key: "taskList", label: "Checkliste", shortcut: `${MOD}⇧9`, icon: ListChecks,
    run: (e) => e.chain().focus().toggleTaskList().run(), active: (e) => e.isActive("taskList") },
];

/** Ebene 1 und 2 wie in Markdown, im Dokument h3 und h4 (s. oben). Beim
 *  Einfügen werden h1/h2 und h3/h4 zu den beiden Größen. */
const NoteHeading = Heading.extend({
  parseHTML() {
    return [1, 2, 3, 4].map((h) => ({ tag: `h${h}`, attrs: { level: h % 2 === 1 ? 1 : 2 } }));
  },
  renderHTML({ node, HTMLAttributes }) {
    return [`h${node.attrs.level === 2 ? 4 : 3}`, mergeAttributes(this.options.HTMLAttributes, HTMLAttributes), 0];
  },
});

export default function NoteEditor({ id, label, value, onChange, onBlur, disabled, rows = 5, placeholder, className }: NoteEditorProps) {
  // Was das Feld zuletzt gemeldet hat: Kommt genau das als `value` zurück,
  // ist es das eigene Echo und kein neuer Stand (Laden, „übernehmen").
  const last = useRef(value);
  const onChangeRef = useRef(onChange);
  const onBlurRef = useRef(onBlur);
  useEffect(() => { onChangeRef.current = onChange; onBlurRef.current = onBlur; });

  const editor = useEditor({
    // Nur im Browser geladen (`note-field.tsx`), also gleich zeichnen statt
    // erst leer und dann voll.
    immediatelyRender: true,
    shouldRerenderOnTransaction: false,
    extensions: [
      NoteHeading.configure({ levels: [1, 2] }),
      StarterKit.configure({
        heading: false, blockquote: false, codeBlock: false, code: false, strike: false, horizontalRule: false,
        hardBreak: false, link: false, underline: false, dropcursor: false,
        // Kein Leer-Absatz hinter einer Liste am Ende: Er stünde als Leerzeile im Text.
        trailingNode: false,
      }),
      TaskList,
      TaskItem.configure({
        nested: true,
        a11y: { checkboxLabel: (node) => `Aufgabe: ${node.textContent || "leer"}` },
      }),
      Placeholder.configure({ placeholder: placeholder ?? "" }),
      // So viel wie das Textfeld davor; die Grenze des Servers liegt beim Geheimtext.
      CharacterCount.configure({ limit: 8000 }),
    ],
    content: parseNote(value) as JSONContent,
    editable: !disabled,
    editorProps: {
      attributes: {
        id, role: "textbox", "aria-multiline": "true", "aria-label": label,
        class: "notiz-editor min-h-[var(--zeilen)] max-h-[70vh] overflow-y-auto px-3 py-2 text-sm leading-relaxed focus-visible:outline-none",
        style: `--zeilen: calc(${rows} * 1.625em + 1rem)`,
      },
    },
    onUpdate: ({ editor: e }) => {
      const text = serializeNote(e.getJSON() as NoteNode);
      last.current = text;
      onChangeRef.current(text);
    },
    onBlur: () => onBlurRef.current?.(),
  });

  useEffect(() => {
    if (!editor || value === last.current) return;
    last.current = value;
    editor.commands.setContent(parseNote(value) as JSONContent, { emitUpdate: false });
  }, [editor, value]);

  useEffect(() => { editor?.setEditable(!disabled, false); }, [editor, disabled]);

  const active = useEditorState({
    editor,
    selector: ({ editor: e }) => (e ? Object.fromEntries(ACTIONS.map((a) => [a.key, a.active(e)])) : {}),
  }) ?? {};

  return (
    <div className={cn("rounded-xl border border-input bg-background focus-within:ring-2 focus-within:ring-ring", className)}>
      <Leiste editor={editor} active={active} disabled={disabled} controls={id} />
      <EditorContent editor={editor} />
    </div>
  );
}

/** Eine Werkzeugleiste ist EIN Halt für die Tab-Taste, die Pfeile wandern
 *  darin (WAI-ARIA „Toolbar"). */
function Leiste({ editor, active, disabled, controls }: {
  editor: Editor | null; active: Record<string, boolean>; disabled?: boolean; controls: string;
}) {
  const bar = useRef<HTMLDivElement>(null);
  const [focusIdx, setFocusIdx] = useState(0);
  const onKey = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    let next: number | null = null;
    if (step) next = (focusIdx + step + ACTIONS.length) % ACTIONS.length;
    if (e.key === "Home") next = 0;
    if (e.key === "End") next = ACTIONS.length - 1;
    if (next === null) return;
    e.preventDefault();
    setFocusIdx(next);
    bar.current?.querySelectorAll<HTMLButtonElement>("button")[next]?.focus();
  };
  const groups: { a: Action; i: number }[][] = [];
  ACTIONS.forEach((a, i) => {
    if (a.group || !groups.length) groups.push([]);
    groups[groups.length - 1].push({ a, i });
  });
  return (
    // Umgebrochen wird nach Gruppen (Überschriften · Schrift · Listen), nicht
    // Knopf für Knopf: Sieben Knöpfe à 44 px passen auf kein Telefon in eine
    // Zeile, und ein Strich am Zeilenende trennte nichts mehr. Striche daher
    // nur an der Maus, wo alles in eine Zeile passt (36 px, Designsprache).
    <div ref={bar} role="toolbar" aria-label="Formatierung" aria-controls={controls} onKeyDown={onKey}
      className="flex flex-wrap items-center gap-x-3 gap-y-0.5 border-b border-border px-1 py-1 desk:gap-x-0">
      {groups.map((group, g) => (
        <div key={g} className={cn("flex items-center gap-0.5", g > 0 && "desk:ml-1 desk:border-l desk:border-border desk:pl-1")}>
          {group.map(({ a, i }) => {
            const Icon = a.icon;
            const pressed = !!active[a.key];
            return (
              <button key={a.key} type="button" disabled={disabled || !editor} tabIndex={i === focusIdx ? 0 : -1}
                aria-label={a.label} aria-pressed={pressed} title={`${a.label} (${a.shortcut})`}
                // Der Knopf darf dem Feld weder Fokus noch Auswahl nehmen.
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => { setFocusIdx(i); if (editor) a.run(editor); }}
                className={cn("inline-flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 desk:h-9 desk:w-9",
                  pressed && "bg-primary/[0.1] text-primary hover:bg-primary/[0.14] hover:text-primary")}>
                <Icon className="h-4 w-4" aria-hidden />
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}
