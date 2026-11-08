import { committeeIcon, committeeImage } from "@/lib/committees";
import { cn } from "@/lib/utils";

/** Lotti mit einem Requisit aus dem Sachbereich des Gremiums (`public/gremien/`),
 *  gewählt = Ring in der Primärfarbe. Gremien ohne Bild behalten das Zeichen auf
 *  getönter Scheibe (Primär-Tint /8, DESIGNSPRACHE §2; gewählt = gefüllt).
 *
 *  Eine eigene Komponente, weil dieselben Bilder an mehreren Stellen stehen —
 *  zuerst im Einrichtungs-Assistenten, seit 11/2026 auch auf den
 *  Ausschuss-Abos, wo bis dahin noch die alten Zeichen standen (Tim
 *  08.11.2026). Der leichte Zoom schneidet nur Hintergrund ab: Die Motive
 *  halten zum Rand rund ein Sechstel Abstand und füllen sonst nur zwei Drittel
 *  der Fläche. */
export function CommitteePicture({ committee, active, className }: {
  committee: string;
  active: boolean;
  /** Größe des Bildes, z. B. `h-16 w-16`; die Zeichen-Scheibe bleibt 36 px. */
  className?: string;
}) {
  const bild = committeeImage(committee);
  if (bild) {
    return (
      <span aria-hidden className={cn(
        "block shrink-0 overflow-hidden rounded-xl bg-muted transition-shadow",
        className ?? "h-16 w-16",
        active && "ring-2 ring-primary ring-offset-2 ring-offset-background",
      )}>
        {/* Feste 256-px-Dateien aus dem Repo; `next/image` optimiert hier nichts (s. next.config.mjs). */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={bild} alt="" width={80} height={80} loading="lazy" decoding="async"
          className="h-full w-full scale-[1.1] object-cover" />
      </span>
    );
  }
  const Icon = committeeIcon(committee);
  return (
    <span aria-hidden className={cn(
      "flex h-9 w-9 shrink-0 items-center justify-center rounded-[11px] transition-colors",
      active ? "bg-primary text-primary-foreground" : "bg-primary/[0.08] text-primary",
    )}>
      <Icon className="h-[18px] w-[18px]" strokeWidth={2} />
    </span>
  );
}
