"use client";

// Parteizugehörigkeit im Tippspiel (seit 19.09.2026, Tims Auftrag): beim
// Beitritt freiwillig aus einem Menü gewählt, danach als kleines Etikett
// neben dem Namen — in der Rangliste, bei „Mein Tipp", im Admin. Das Menü
// kommt fertig vom Server (`party_options`, ohne AfD und ohne
// Einzelwahlvorschläge); hier steht nur die Darstellung.

import type { TippParteiOption } from "@/lib/tipp";
import { Select } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export function ParteiAuswahl({ id, optionen, wert, onChange, className }: {
  id: string;
  optionen: readonly TippParteiOption[];
  /** Slug oder `""` für „keine Angabe". */
  wert: string;
  onChange: (slug: string) => void;
  className?: string;
}) {
  if (optionen.length === 0) return null;
  return (
    <div className={className}>
      <label htmlFor={id} className="block text-xs font-semibold text-muted-foreground">
        Parteizugehörigkeit <span className="font-normal">(freiwillig)</span>
      </label>
      {/* Ein natives Menü: Auf dem Handy öffnet es die Systemliste — die
          bedient man mit dem Daumen besser als jedes eigene Dropdown. */}
      <Select id={id} value={wert} onChange={(e) => onChange(e.target.value)} className="mt-2 h-[46px] text-base font-semibold">
        <option value="">Keine Angabe</option>
        {optionen.map((o) => (
          <option key={o.slug} value={o.slug}>{o.short}</option>
        ))}
      </Select>
      <p className="mt-2 text-[11.5px] text-muted-foreground">
        Steht als Etikett neben deinem Namen in der Rangliste.
      </p>
    </div>
  );
}

/** Das Etikett neben dem Namen: Farbpunkt der Liste plus Kurzname. Größe
 *  über `className` (die Bühne des Beamers skaliert in px, das Handy in
 *  Tailwind-Stufen). */
export function ParteiChip({ partei, className, hell }: {
  partei: TippParteiOption | null | undefined;
  className?: string;
  /** Auf dem blauen Platz-1-Feld: weiße Tönung statt Karte. */
  hell?: boolean;
}) {
  if (!partei) return null;
  return (
    <span
      className={cn(
        "inline-flex flex-none items-center gap-1 rounded-full border px-1.5 py-px text-[10px] font-semibold leading-tight",
        hell ? "border-white/30 text-white/90" : "border-border bg-card text-muted-foreground",
        className,
      )}
      title={`Parteizugehörigkeit: ${partei.short}`}
    >
      {partei.color && (
        <span
          aria-hidden
          className="h-[0.7em] w-[0.7em] flex-none rounded-full bg-[var(--dot)] shadow-[inset_0_0_0_1px_rgba(0,0,0,0.15)] dark:bg-[var(--dot-dark)]"
          style={{ "--dot": partei.color, "--dot-dark": partei.color_dark || partei.color } as React.CSSProperties}
        />
      )}
      {partei.short}
    </span>
  );
}
