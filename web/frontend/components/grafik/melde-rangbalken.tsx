import { type CSSProperties, type Key, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { reportCountLabel, type ProblemFrequency } from "@/lib/probleme";
import { cn } from "@/lib/utils";
import styles from "./melde-rangbalken.module.css";

export type MeldeRangzeile = {
  key: Key;
  label: string;
  wert: number;
  haeufigkeit: ProblemFrequency;
  offen: boolean;
  umschalten: () => void;
  vorschau: ReactNode;
};

/**
 * Vollständige Bürgerportal-Rangliste hinter einer fokussierten Schnittstelle.
 *
 * Die Seite liefert ausschließlich die öffentlichen Zeilendaten, ihren
 * Aufklappzustand und den fachlichen Vorschauinhalt. Das Grafikmodul besitzt
 * Rang, Maximum, proportionale Balken, Container-Hierarchie, Interaktion,
 * Animation und die einmalige sichtbare Quellenzeile.
 */
export function MeldeRanglisteGrafik({
  zeilen,
  beleg,
}: {
  zeilen: MeldeRangzeile[];
  beleg: ReactNode;
}) {
  const maximum = Math.max(0, ...zeilen.map((zeile) => zeile.wert));

  return (
    <figure className={styles.figure}>
      <ol className={cn(styles.list, "problem-leaderboard")} aria-label="Meistgemeldete ungelöste Probleme">
        {zeilen.map((zeile, index) => (
          <MeldeRangzeileAnsicht
            key={zeile.key}
            zeile={zeile}
            rang={index + 1}
            maximum={maximum}
          />
        ))}
      </ol>
      <figcaption className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
        {beleg}
      </figcaption>
    </figure>
  );
}

function MeldeRangzeileAnsicht({
  zeile,
  rang,
  maximum,
}: {
  zeile: MeldeRangzeile;
  rang: number;
  maximum: number;
}) {
  const topThree = rang <= 3;
  const previewId = `problem-preview-${String(zeile.key)}`;
  const countLabel = reportCountLabel(zeile.wert);

  return (
    <li
      data-ranggruppe={topThree ? "top-drei" : "weitere"}
      style={{ "--rank-index": rang - 1 } as CSSProperties}
      className={cn(
        styles.card,
        rang === 1 && styles.first,
        (rang === 2 || rang === 3) && styles.podium,
        !topThree && styles.other,
        zeile.offen && styles.expanded,
        "problem-disclosure-card",
      )}
    >
      <button
        type="button"
        aria-expanded={zeile.offen}
        aria-controls={previewId}
        aria-label={`${rang}. ${zeile.label}, ${countLabel}`}
        onClick={zeile.umschalten}
        className={cn(
          styles.toggle,
          topThree && styles.topToggle,
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
        )}
      >
        <span className={cn(
          "font-sans text-xl font-bold tabular-nums text-muted-foreground",
          topThree && "text-primary sm:text-2xl @3xl:text-[28px]",
          rang === 1 && "@3xl:text-[30px]",
        )} aria-hidden>{String(rang).padStart(2, "0")}</span>
        <span className="min-w-0">
          <span className={cn(
            "block text-sm font-semibold leading-snug text-foreground sm:text-[15px]",
            topThree && "@3xl:text-base",
            rang === 1 && "@3xl:text-xl",
          )}>{zeile.label}</span>
          <strong className={cn(
            "mt-1.5 block font-sans text-xs font-semibold tabular-nums text-foreground",
            topThree && "@3xl:text-sm",
            rang === 1 && "@3xl:text-base",
          )}>{countLabel}</strong>
          <span className="mt-2 block">
            <MeldeRangbalken wert={zeile.wert} maximum={maximum} haeufigkeit={zeile.haeufigkeit} />
          </span>
        </span>
        <ChevronDown className={cn(styles.chevron, "problem-disclosure-chevron h-5 w-5 text-muted-foreground", zeile.offen && "rotate-180")} aria-hidden />
      </button>

      {zeile.offen && (
        <div
          id={previewId}
          className={cn(styles.preview, "problem-preview")}
          role="region"
          aria-label={`Vorschau: ${zeile.label}`}
        >
          {zeile.vorschau}
        </div>
      )}
    </li>
  );
}

/** Proportionale Null-bis-Max-Schiene ohne optische Mindestbreite. */
function MeldeRangbalken({
  wert,
  maximum,
  haeufigkeit,
}: {
  wert: number;
  maximum: number;
  haeufigkeit: ProblemFrequency;
}) {
  const anteil = maximum > 0 ? Math.min(1, Math.max(0, wert / maximum)) : 0;

  return (
    <span className="block h-1.5 overflow-hidden rounded-full bg-primary/8" aria-hidden>
      <span
        className={cn(styles.bar, `frequency-${haeufigkeit}`, "problem-rank-bar block h-full rounded-full bg-[var(--problem-frequency)]")}
        style={{ width: `${anteil * 100}%` }}
      />
    </span>
  );
}
