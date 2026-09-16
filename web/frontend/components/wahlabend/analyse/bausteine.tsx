import type { ReactNode } from "react";
import { ExternalLink } from "lucide-react";
import { KICKER } from "@/components/wahlabend/bausteine";

export function Abschnitt({ id, kicker, titel, children }: { id: string; kicker: string; titel: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-titel`} className="mt-12 scroll-mt-24">
      <div className={KICKER}>{kicker}</div>
      <h2 id={`${id}-titel`} className="mt-1 font-display text-2xl font-bold tracking-tight">{titel}</h2>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}

export function Kennzahl({ wert, titel, children }: { wert: string; titel: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="font-display text-3xl font-bold tabular-nums tracking-tight">{wert}</div>
      <h3 className="mt-1 font-semibold">{titel}</h3>
      <p className="mt-1 text-hinweis text-muted-foreground">{children}</p>
    </div>
  );
}

export function Quelle({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center gap-1.5 text-hinweis text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-primary">
      <span>{children}</span><ExternalLink className="h-3.5 w-3.5 flex-none" aria-hidden />
    </a>
  );
}

export function Erklaerung({ children }: { children: ReactNode }) {
  return <p className="max-w-[76ch] text-lese">{children}</p>;
}
