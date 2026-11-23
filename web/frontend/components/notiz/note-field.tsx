"use client";

/* The text field of „Meine Notiz" and „Mein Mitschrieb", with a small
   formatting bar (Tims Wunsch 23.11.2026: „text editing tools für listen
   usw"). The text stays plain text with a little Markdown — why, and what
   each button does to it, is in `lib/note-format.ts`.

   Edits go through `document.execCommand("insertText")`: deprecated, but the
   only way to change a textarea that keeps the browser's undo stack — with a
   bare `value` assignment, ⌘Z would forget every formatting step. Where it
   refuses, `setRangeText` plus an `input` event does the same without undo. */

import { useRef, useState } from "react";
import { Bold, Italic, List, ListChecks, ListOrdered, type LucideIcon } from "lucide-react";
import {
  activeList, continueList, toggleList, toggleTask, toggleWrap, type Edit, type ListKind,
} from "@/lib/note-format";
import { cn } from "@/lib/utils";

type Action = { key: string; label: string; shortcut: string; icon: LucideIcon; list?: ListKind;
  run: (v: string, s: number, e: number) => Edit };

const MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
const MOD = MAC ? "⌘" : "Strg+";

const ACTIONS: Action[] = [
  { key: "bold", label: "Fett", shortcut: `${MOD}B`, icon: Bold, run: (v, s, e) => toggleWrap(v, s, e, "**") },
  { key: "italic", label: "Kursiv", shortcut: `${MOD}I`, icon: Italic, run: (v, s, e) => toggleWrap(v, s, e, "*") },
  { key: "bullet", label: "Aufzählung", shortcut: `${MOD}⇧8`, icon: List, list: "bullet",
    run: (v, s, e) => toggleList(v, s, e, "bullet") },
  { key: "number", label: "Nummerierte Liste", shortcut: `${MOD}⇧7`, icon: ListOrdered, list: "number",
    run: (v, s, e) => toggleList(v, s, e, "number") },
  { key: "task", label: "Checkliste", shortcut: `${MOD}⇧9`, icon: ListChecks, list: "task",
    run: (v, s, e) => toggleList(v, s, e, "task") },
];

const BY_CODE: Record<string, string> = { KeyB: "bold", KeyI: "italic", Digit8: "bullet", Digit7: "number", Digit9: "task" };

function apply(el: HTMLTextAreaElement, edit: Edit) {
  el.focus();
  if (edit.from !== edit.to || edit.insert) {
    el.setSelectionRange(edit.from, edit.to);
    let ok = false;
    try {
      ok = edit.insert ? document.execCommand("insertText", false, edit.insert) : document.execCommand("delete");
    } catch { /* not supported — fall through */ }
    if (!ok) {
      el.setRangeText(edit.insert, edit.from, edit.to, "end");
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }
  el.setSelectionRange(edit.selStart, edit.selEnd);
}

export function NoteField({ id, label, value, onChange, onBlur, disabled, rows = 5, placeholder, className }: {
  id: string;
  /** Für Screenreader: was in das Feld gehört. */
  label: string;
  value: string;
  onChange: (text: string) => void;
  onBlur?: () => void;
  disabled?: boolean;
  rows?: number;
  placeholder?: string;
  className?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const bar = useRef<HTMLDivElement>(null);
  const [list, setList] = useState<ListKind | null>(null);
  const [focusIdx, setFocusIdx] = useState(0);

  const refresh = () => {
    const el = ref.current;
    if (el) setList(activeList(el.value, el.selectionStart));
  };

  const run = (a: Action) => {
    const el = ref.current;
    if (!el || disabled) return;
    apply(el, a.run(el.value, el.selectionStart, el.selectionEnd));
    refresh();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    const el = e.currentTarget;
    if (e.nativeEvent.isComposing) return;
    const mod = MAC ? e.metaKey && !e.ctrlKey : e.ctrlKey && !e.metaKey;
    if (e.key === "Enter" && !e.shiftKey && !e.altKey) {
      // ⌘↩ hakt die Aufgabe in der Zeile ab, ↩ setzt eine Liste fort.
      const edit = mod ? toggleTask(el.value, el.selectionStart)
        : !e.metaKey && !e.ctrlKey ? continueList(el.value, el.selectionStart, el.selectionEnd) : null;
      if (edit) {
        e.preventDefault();
        apply(el, edit);
        refresh();
      }
      return;
    }
    if (!mod || e.altKey) return;
    const key = BY_CODE[e.code];
    const a = key && ACTIONS.find((x) => x.key === key);
    // B und I ohne Umschalt, die Listen mit — wie in Google Docs und Notion.
    if (!a || Boolean(a.list) !== e.shiftKey) return;
    e.preventDefault();
    run(a);
  };

  // Eine Werkzeugleiste ist EIN Halt für die Tab-Taste, die Pfeile wandern
  // darin (WAI-ARIA „Toolbar").
  const onBarKey = (e: React.KeyboardEvent<HTMLDivElement>) => {
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

  return (
    <div className={cn("rounded-xl border border-input bg-background focus-within:ring-2 focus-within:ring-ring", className)}>
      <div ref={bar} role="toolbar" aria-label="Formatierung" aria-controls={id} onKeyDown={onBarKey}
        className="flex flex-wrap items-center gap-0.5 border-b border-border px-1 py-1">
        {ACTIONS.map((a, i) => {
          const Icon = a.icon;
          const pressed = a.list ? list === a.list : undefined;
          return (
            <span key={a.key} className="contents">
              {a.key === "bullet" && <span className="mx-1 h-5 w-px bg-border" aria-hidden />}
              <button type="button" disabled={disabled} tabIndex={i === focusIdx ? 0 : -1}
                aria-label={a.label} aria-pressed={pressed} title={`${a.label} (${a.shortcut})`}
                // Der Knopf darf dem Feld weder Fokus noch Auswahl nehmen.
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => { setFocusIdx(i); run(a); }}
                className={cn("inline-flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 breit:h-9 breit:w-9",
                  pressed && "bg-primary/[0.1] text-primary hover:bg-primary/[0.14] hover:text-primary")}>
                <Icon className="h-4 w-4" aria-hidden />
              </button>
            </span>
          );
        })}
      </div>
      <label htmlFor={id} className="sr-only">{label}</label>
      <textarea id={id} ref={ref} value={value} disabled={disabled} rows={rows} maxLength={8000}
        onChange={(e) => { onChange(e.target.value); setList(activeList(e.target.value, e.target.selectionStart)); }}
        onSelect={refresh} onKeyDown={onKeyDown} onBlur={onBlur} placeholder={placeholder}
        className="block w-full resize-y rounded-b-xl bg-transparent px-3 py-2 text-sm leading-relaxed focus-visible:outline-none" />
    </div>
  );
}
