import * as React from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-xl border border-border bg-card text-card-foreground shadow-sm", className)} {...props} />;
}

type BadgeColor = "slate" | "blue" | "green" | "amber" | "red";

export function Badge({ children, color = "slate", className }: { children: React.ReactNode; color?: BadgeColor; className?: string }) {
  const colors: Record<BadgeColor, string> = {
    slate: "bg-muted text-muted-foreground",
    blue: "bg-primary/10 text-primary",
    green: "bg-green-100 text-green-700",
    amber: "bg-amber-100 text-amber-700",
    red: "bg-destructive/10 text-destructive",
  };
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", colors[color], className)}>
      {children}
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center justify-center p-8", className)}>
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted border-t-primary" />
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-card p-10 text-center">
      <p className="font-medium text-muted-foreground">{title}</p>
      {hint && <p className="mt-1 text-sm text-muted-foreground/70">{hint}</p>}
    </div>
  );
}
