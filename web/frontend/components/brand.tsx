import { Activity } from "lucide-react";
import { cn } from "@/lib/utils";

/** The Stadtpuls logo mark — a pulse line, matching the app icon. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm",
        className,
      )}
    >
      <Activity className="h-5 w-5" strokeWidth={2.5} />
    </span>
  );
}

export function Brand({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <BrandMark />
      <span className="text-lg font-bold tracking-tight text-foreground">Stadtpuls</span>
    </div>
  );
}
