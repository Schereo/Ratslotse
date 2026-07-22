"use client";

import { useEffect, useRef, useState } from "react";
import { Calendar as CalendarIcon, X } from "lucide-react";
import { cn } from "@/lib/utils";

const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const MONTHS = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];
const MONTHS_SHORT = [
  "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
  "Jul", "Aug", "Sep", "Okt", "Nov", "Dez",
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
  // Klapp-Richtung: nach oben, wenn unten kein Platz ist (z. B. im Filter-
  // Bottom-Sheet), nach links ausgerichtet, außer der Kalender liefe rechts raus.
  const [placement, setPlacement] = useState<{ up: boolean; right: boolean }>({ up: false, right: false });
  // Drilldown-Ebene: Tage → Monate → Jahre. So springt man ohne Monatsschritte
  // schnell in ein anderes Jahr; beim Schließen wieder auf Tage zurücksetzen.
  const [mode, setMode] = useState<"days" | "months" | "years">("days");
  useEffect(() => {
    if (!open) setMode("days");
  }, [open]);

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

  // Beim Öffnen die Klapp-Richtung anhand des verfügbaren Platzes bestimmen.
  useEffect(() => {
    if (!open || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const CAL_H = 320, CAL_W = 256, GAP = 12;
    setPlacement({
      up: window.innerHeight - r.bottom < CAL_H + GAP && r.top > CAL_H + GAP,
      right: r.left + CAL_W > window.innerWidth - 8,
    });
  }, [open]);

  const year = view.getFullYear();
  const month = view.getMonth();
  const startOffset = (new Date(year, month, 1).getDay() + 6) % 7; // Monday-first
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  // Immer 6 Wochen-Reihen (42 Zellen): so bleibt die Pickerhöhe monatsübergreifend
  // konstant. Sonst wandert beim Aufklappen nach oben (Filter-Sheet) der Monats-
  // Pfeil mit, weil der Kalender an der Unterkante verankert ist und nach oben wächst.
  const cells: (number | null)[] = [
    ...Array<null>(startOffset).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length < 42) cells.push(null);
  const yearBlockStart = year - (year % 12); // 12-Jahres-Seite, z. B. 2016–2027

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
        <div className={cn(
          "absolute z-50 w-64 rounded-lg border border-border bg-popover p-3 text-popover-foreground shadow-lg",
          placement.up ? "bottom-full mb-1" : "top-full mt-1",
          placement.right ? "right-0" : "left-0",
        )}>
          <div className="flex items-center justify-between">
            <button
              type="button"
              aria-label={mode === "days" ? "Vorheriger Monat" : mode === "months" ? "Vorheriges Jahr" : "Frühere Jahre"}
              className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
              onClick={() => setView(new Date(
                mode === "days" ? year : mode === "months" ? year - 1 : year - 12,
                mode === "days" ? month - 1 : month,
                1,
              ))}
            >
              ‹
            </button>
            {/* Titel klickbar: eine Ebene hoch (Tag→Monat→Jahr), am Ende zurück auf Tage. */}
            <button
              type="button"
              aria-label="Ansicht wechseln"
              className="rounded-md px-2 py-0.5 text-sm font-medium tabular-nums hover:bg-accent"
              onClick={() => setMode(mode === "days" ? "months" : mode === "months" ? "years" : "days")}
            >
              {mode === "days"
                ? `${MONTHS[month]} ${year}`
                : mode === "months"
                  ? year
                  : `${yearBlockStart}–${yearBlockStart + 11}`}
            </button>
            <button
              type="button"
              aria-label={mode === "days" ? "Nächster Monat" : mode === "months" ? "Nächstes Jahr" : "Spätere Jahre"}
              className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
              onClick={() => setView(new Date(
                mode === "days" ? year : mode === "months" ? year + 1 : year + 12,
                mode === "days" ? month + 1 : month,
                1,
              ))}
            >
              ›
            </button>
          </div>

          {mode === "days" && (
            <>
              <div className="mt-2 grid grid-cols-7 text-center text-xs text-muted-foreground">
                {WEEKDAYS.map((w) => <div key={w} className="py-1">{w}</div>)}
              </div>

              <div className="grid grid-cols-7 gap-0.5">
                {cells.map((day, i) => {
                  if (day === null) return <div key={i} className="h-8" />;
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
            </>
          )}

          {mode === "months" && (
            <div className="mt-2 grid grid-cols-3 gap-1.5">
              {MONTHS_SHORT.map((m, i) => {
                const isSelectedMonth = selected?.getMonth() === i && selected?.getFullYear() === year;
                return (
                  <button
                    key={m}
                    type="button"
                    onClick={() => { setView(new Date(year, i, 1)); setMode("days"); }}
                    className={cn(
                      "flex h-[3.25rem] items-center justify-center rounded-md text-sm hover:bg-accent",
                      isSelectedMonth && "bg-primary text-primary-foreground hover:bg-primary",
                      !isSelectedMonth && i === month && "font-semibold text-primary",
                    )}
                  >
                    {m}
                  </button>
                );
              })}
            </div>
          )}

          {mode === "years" && (
            <div className="mt-2 grid grid-cols-3 gap-1.5">
              {Array.from({ length: 12 }, (_, i) => yearBlockStart + i).map((y) => {
                const isSelectedYear = selected?.getFullYear() === y;
                return (
                  <button
                    key={y}
                    type="button"
                    onClick={() => { setView(new Date(y, month, 1)); setMode("months"); }}
                    className={cn(
                      "flex h-[3.25rem] items-center justify-center rounded-md text-sm tabular-nums hover:bg-accent",
                      isSelectedYear && "bg-primary text-primary-foreground hover:bg-primary",
                      !isSelectedYear && y === year && "font-semibold text-primary",
                    )}
                  >
                    {y}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
