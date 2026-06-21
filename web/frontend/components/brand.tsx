import { cn } from "@/lib/utils";

/** The Ratslotse logo mark — compass + column, matching the app icon. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-white ring-1 ring-black/5",
        className,
      )}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/logo-mark.png" alt="Ratslotse" className="h-full w-full object-contain" />
    </span>
  );
}

export function Brand({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <BrandMark />
      <span className="text-lg font-bold tracking-tight text-foreground">Ratslotse</span>
    </div>
  );
}
