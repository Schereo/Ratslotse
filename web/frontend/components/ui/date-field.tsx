"use client";

import { useEffect, useRef, useState } from "react";
import { Calendar as CalendarIcon, X } from "lucide-react";
import { cn } from "@/lib/utils";

const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const MONTHS = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];

function toISO(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function parseISO(s: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : null;
}

/**
 * Lightweight, theme-aware date picker (German, no native browser popup).
 * Value is an ISO `YYYY-MM-DD` string (empty = no date), matching the API.
 */
export function DateField({
  value,
  onChange,
  placeholder = "TT.MM.JJJJ",
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = parseISO(value);
  const [view, setView] = useState<Date>(() => selected ?? new Date());

  // Jump the visible month to the value when it changes from the outside.
  useEffect(() => {
    const d = parseISO(value);
    if (d) setView(d);
  }, [value]);

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const year = view.getFullYear();
  const month = view.getMonth();
  const startOffset = (new Date(year, month, 1).getDay() + 6) % 7; // Monday-first
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: (number | null)[] = [
    ...Array<null>(startOffset).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  const display = selected
    ? `${String(selected.getDate()).padStart(2, "0")}.${String(selected.getMonth() + 1).padStart(2, "0")}.${selected.getFullYear()}`
    : "";
  const todayISO = toISO(new Date());

  return (
    <div className={cn("relative", className)} ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex h-10 w-full items-center justify-between rounded-md border border-input bg-card px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
          !display && "text-muted-foreground",
        )}
      >
        <span>{display || placeholder}</span>
        {display ? (
          <X
            className="h-4 w-4 shrink-0 text-muted-foreground hover:text-foreground"
            onClick={(e) => { e.stopPropagation(); onChange(""); }}
          />
        ) : (
          <CalendarIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
        )}
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-64 rounded-lg border border-border bg-popover p-3 text-popover-foreground shadow-lg">
          <div className="flex items-center justify-between">
            <button
              type="button"
              aria-label="Vorheriger Monat"
              className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
              onClick={() => setView(new Date(year, month - 1, 1))}
            >
              ‹
            </button>
            <span className="text-sm font-medium">{MONTHS[month]} {year}</span>
            <button
              type="button"
              aria-label="Nächster Monat"
              className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
              onClick={() => setView(new Date(year, month + 1, 1))}
            >
              ›
            </button>
          </div>

          <div className="mt-2 grid grid-cols-7 text-center text-xs text-muted-foreground">
            {WEEKDAYS.map((w) => <div key={w} className="py-1">{w}</div>)}
          </div>

          <div className="grid grid-cols-7 gap-0.5">
            {cells.map((day, i) => {
              if (day === null) return <div key={i} />;
              const iso = toISO(new Date(year, month, day));
              const isSelected = iso === value;
              const isToday = iso === todayISO;
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => { onChange(iso); setOpen(false); }}
                  className={cn(
                    "flex h-8 items-center justify-center rounded-md text-sm hover:bg-accent",
                    isSelected && "bg-primary text-primary-foreground hover:bg-primary",
                    !isSelected && isToday && "font-semibold text-primary",
                  )}
                >
                  {day}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
