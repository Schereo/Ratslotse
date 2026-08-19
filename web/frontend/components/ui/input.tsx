import * as React from "react";
import { cn } from "@/lib/utils";

// 16px (`text-base`) ist hier keine Geschmacksfrage: Safari/WKWebView zoomt
// beim Fokussieren automatisch rein, sobald ein Feld eine kleinere
// Schriftgröße hat — und der Zoom bleibt auf dem iPhone/iPad oft hängen
// (Tims Befund 19.08. am Umbenennen-Feld). `sm:` (640px) schien lange die
// richtige Schwelle für „genug Platz, darf kleiner sein" — bis ein iPad in
// jeder Ausrichtung ≥640px misst UND ein Touch-Gerät bleibt: `maus`
// (pointer:fine, kein Breiten-Gate) ist die richtige Bedingung dafür, nicht
// die Fensterbreite.

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-md border border-input bg-card px-3 py-2 text-base maus:text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        // Bewusst KEIN font-mono: Textareas sind normale Fließtext-Eingaben
        // (Themen-Beschreibung, Feedback …). Der Admin-Prompt-Editor setzt
        // sich sein Mono gezielt per className.
        "flex min-h-[80px] w-full rounded-md border border-input bg-card px-3 py-2 text-base maus:text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-md border border-input bg-card px-3 py-2 text-base maus:text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  ),
);
Select.displayName = "Select";
