import Image from "next/image";
import { cn } from "@/lib/utils";

/**
 * Die Ratslotse-Marke: Lotti, die Lotsenmöwe, als App-Icon-Kachel.
 *
 * Seit 11/2026 ein Bild der 3D-Lotti statt des handgezeichneten Flat-SVG —
 * dieselbe Kachel wie das App-Icon, die Favicons und das Mail-Logo, alle aus
 * einem Render (`scripts/brand_icons.py`). Die Datei ist quadratisch und
 * randlos; die Rundung kommt hier per CSS dazu, im Verhältnis des
 * iOS-Icons (≈ 22 % der Kante), damit sie auf jeder Größe gleich aussieht.
 *
 * `sizes` deckt die größte Verwendung ab (56 px, Beamer-Ansicht des
 * Tippspiels); der Optimierer liefert damit auch auf 3×-Schirmen scharf.
 *
 * Ohne `label` ist das Bild dekorativ (`alt=""`): Überall steht „Ratslotse"
 * als Text daneben oder der Link trägt ein `aria-label`. Ein Alt-Text
 * wiederholte nur den Namen — axe meldet das als `image-redundant-alt`, und
 * Screenreader lasen „Ratslotse Ratslotse". Wer die Marke ALLEIN zeigt,
 * gibt ihr den Namen über `label`.
 */
export function BrandMark({ className, label }: { className?: string; label?: string }) {
  return (
    <Image
      src="/icon-192.png"
      alt={label ?? ""}
      width={192}
      height={192}
      sizes="64px"
      className={cn("h-9 w-9 shrink-0 rounded-[22%]", className)}
    />
  );
}

export function Brand({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <BrandMark />
      <span className="font-display text-lg font-bold tracking-tight text-foreground">Ratslotse</span>
    </div>
  );
}
