"use client";

import { useState } from "react";
import {Check, ChevronDown, X, type LucideIcon } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { DateField } from "@/components/ui";
import { Button } from "@/components/ui";
import { cn } from "@/lib/utils";

/** Filter-Chips mit Popover-Auswahl (RL-501, Design 1a-Suche).
 *
 *  Zustände: ohne Auswahl = Umriss-Chip mit Label + Chevron; mit Auswahl =
 *  gefüllter Primär-Chip mit Wert + ✕ (✕ löscht, Chipfläche öffnet wieder).
 *  `ghost` (Sortierung) bleibt immer dezent — eine Einstellung, kein Filter. */

// RL-F07 (Motion-Spec 7a): fühlbares Press-Feedback — nur transform, 150 ms.
const chipBase =
  "inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-3 text-xs font-medium transition-[color,background-color,transform] duration-150 ease-out active:scale-[0.94]";

export function ChipPopover({
  label,
  value,
  display,
  options,
  onChange,
  ghost = false,
  clearable = true,
}: {
  label: string;
  value: string;
  /** Anzeige des aktiven Werts (Fallback: Options-Label). */
  display?: string;
  options: { value: string; label: string; sub?: string; icon?: LucideIcon }[];
  onChange: (v: string) => void;
  ghost?: boolean;
  clearable?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const active = clearable && value !== "";
  const current = display ?? options.find((o) => o.value === value)?.label ?? label;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            chipBase,
            active
              ? "bg-primary text-primary-foreground hover:opacity-90"
              : ghost
                ? "text-muted-foreground hover:bg-accent hover:text-foreground"
                : "border border-input bg-card text-foreground hover:bg-accent",
          )}
        >
          {active ? current : label}
          {active ? (
            <X
              className="h-3.5 w-3.5 opacity-80 transition-opacity hover:opacity-100"
              onClick={(e) => {
                e.stopPropagation();
                onChange("");
                setOpen(false);
              }}
            />
          ) : (
            <ChevronDown className="h-3.5 w-3.5 opacity-60" />
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent className="max-h-80 overflow-y-auto">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            onClick={() => {
              onChange(o.value);
              setOpen(false);
            }}
            className={cn(
              "flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm transition-colors hover:bg-accent",
              o.value === value ? "font-medium text-primary" : "text-foreground",
            )}
          >
            <span className="min-w-0">
              <span className="flex items-center gap-1.5 truncate">
                {o.icon && <o.icon className="h-3.5 w-3.5 shrink-0 text-signal" />}
                {o.label}
              </span>
              {/* RL-U15 (13a-C): Untertitel labelt z. B. „Spannendste zuerst"
                  klar als Unterhaltungs-Sortierung. */}
              {o.sub && <span className="block text-[11px] font-normal text-muted-foreground">{o.sub}</span>}
            </span>
            {o.value === value && <Check className="h-4 w-4 shrink-0" />}
          </button>
        ))}
      </PopoverContent>
    </Popover>
  );
}

export function DateRangeChip({
  from,
  to,
  onChange,
}: {
  from: string;
  to: string;
  onChange: (from: string, to: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const active = Boolean(from || to);
  const fmt = (iso: string) => new Date(iso + "T12:00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "2-digit" });
  const labelText = active ? `${from ? fmt(from) : "…"} – ${to ? fmt(to) : "heute"}` : "Zeitraum";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            chipBase,
            active
              ? "bg-primary text-primary-foreground hover:opacity-90"
              : "border border-input bg-card text-foreground hover:bg-accent",
          )}
        >
          {labelText}
          {active ? (
            <X
              className="h-3.5 w-3.5 opacity-80 hover:opacity-100"
              onClick={(e) => {
                e.stopPropagation();
                onChange("", "");
                setOpen(false);
              }}
            />
          ) : (
            <ChevronDown className="h-3.5 w-3.5 opacity-60" />
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-3">
        <div className="grid grid-cols-2 gap-2">
          <label className="text-xs font-medium text-muted-foreground">
            Von
            <DateField className="mt-1" value={from} onChange={(v) => onChange(v, to)} />
          </label>
          <label className="text-xs font-medium text-muted-foreground">
            Bis
            <DateField className="mt-1" value={to} onChange={(v) => onChange(from, v)} />
          </label>
        </div>
        <Button size="sm" variant="secondary" className="mt-3 w-full" onClick={() => setOpen(false)}>
          Übernehmen
        </Button>
      </PopoverContent>
    </Popover>
  );
}
