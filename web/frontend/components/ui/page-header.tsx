import * as React from "react";

/**
 * Consistent page header: title + optional description on the left, optional
 * primary action aligned to the right. Mirrors the Vercel/GitHub dashboard
 * pattern so every page has the same visual hierarchy.
 */
export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    // Kein flex-wrap: Die Aktion rutschte auf schmalen Screens unter den Text
    // und kostete eine ganze Zeile (Tims Fragen-Screen 12.08.). Der Textblock
    // hat min-w-0 und bricht stattdessen selbst um.
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        {/* RL-202: Seitentitel in Bricolage, 30/700 ab sm (mobil 24). */}
        <h1 className="font-display text-2xl font-bold tracking-tight text-foreground sm:text-[30px] sm:leading-9">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
