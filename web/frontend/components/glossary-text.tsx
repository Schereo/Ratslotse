"use client";

import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { GLOSSARY } from "@/lib/glossary";

// Begriffe längster zuerst, damit „Doppelhaushalt" vor „Haushalt" greift.
const KEYS = Object.keys(GLOSSARY).sort((a, b) => b.length - a.length);
const CANON = new Map(KEYS.map((k) => [k.toLowerCase(), k]));
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
// Wortanfang (nicht von einem Buchstaben vorangestellt) + Begriff + Buchstaben-
// Suffix (\p{L} mit u-Flag fängt Umlaute; deckt Beugungen wie -s/-en ab).
const RE = new RegExp(`(?<!\\p{L})(${KEYS.map(esc).join("|")})(\\p{L}*)`, "giu");

/** Ein erklärter Fachbegriff: gepunktet unterstrichen, zeigt beim Überfahren
 *  (Desktop) bzw. Antippen (mobil) eine kurze Erklärung. */
function Term({ label, def }: { label: string; def: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, [open]);
  return (
    <span ref={ref} className="relative inline-block">
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="cursor-help border-b border-dotted border-primary/70 font-medium text-inherit"
        aria-label={`Was bedeutet ${label}?`}
      >
        {label}
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute left-0 top-full z-50 mt-1 block w-[min(17rem,78vw)] rounded-lg border border-border bg-background p-2.5 text-left text-xs font-normal normal-case leading-relaxed text-muted-foreground shadow-lg"
        >
          <span className="mb-0.5 block font-semibold text-foreground">{label}</span>
          {def}
        </span>
      )}
    </span>
  );
}

/** Rendert Text und unterlegt bekannte Fachbegriffe mit einer Hover-Erklärung. */
export function GlossaryText({ text, className }: { text: string | null | undefined; className?: string }) {
  if (!text) return null;
  const parts: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(RE)) {
    const key = CANON.get(m[1].toLowerCase());
    if (!key) continue;
    const idx = m.index ?? 0;
    if (idx > last) parts.push(text.slice(last, idx));
    parts.push(<Term key={idx} label={m[0]} def={GLOSSARY[key]} />);
    last = idx + m[0].length;
  }
  parts.push(text.slice(last));
  return <span className={className}>{parts.map((n, i) => <Fragment key={i}>{n}</Fragment>)}</span>;
}
