import type { ReactNode } from "react";
import { Card } from "@/components/ui";
import { cn } from "@/lib/utils";

/** Gemeinsame Hülle für eigenständige Heute-Bausteine. Daten und Zustände
 * gehören ins jeweilige Widget; die Seite bestimmt nur Platz und Reihenfolge.
 * Die stabile Kennung kann später die persönliche Widget-Auswahl tragen. */
export function HeuteWidget({ id, title, icon, children, footer, className }: {
  id: string;
  title: string;
  icon?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  return (
    <section aria-labelledby={`${id}-title`} data-heute-widget={id} className="min-w-0">
      <Card className={cn("overflow-hidden", className)}>
        <header className="flex items-start gap-2.5 border-b border-border/60 px-4 py-3">
          {icon && <span className="mt-0.5 shrink-0 text-primary" aria-hidden>{icon}</span>}
          <h2 id={`${id}-title`} tabIndex={-1} className="min-w-0 font-display text-base font-bold text-foreground [overflow-wrap:anywhere]">{title}</h2>
        </header>
        <div className="p-4 [overflow-wrap:anywhere]">{children}</div>
        {footer && <footer className="border-t border-border/60 px-4 py-2">{footer}</footer>}
      </Card>
    </section>
  );
}
