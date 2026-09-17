"use client";
import { Card } from "@/components/ui";
import { StatKicker } from "@/components/admin-charts";
import { cn } from "@/lib/utils";

/** Die vier neuen Statistik-Abschnitte (Plan „Sehen und Zurückholen", Teil A).
 *
 *  Gemeinsamer Grundsatz nach Tims Rückmeldung vom 09.09.: Jede Zahl sagt,
 *  **woraus** sie besteht (Zähler und Nenner) und **wie sie sich verändert**
 *  hat (gegen dieselbe Spanne davor). Ein Stand allein — „43 %" — sagt weder,
 *  ob das 3 von 7 sind, noch ob es letzte Woche 60 % waren. Die Veränderung
 *  trägt Signal-Orange, wie jedes Delta in der Designsprache (§ 2, § 5 RG-04);
 *  Ampelfarben auf Balken sind raus, sie beantworteten eine andere Frage als
 *  die Balkenlänge und brauchten eine Legende, um nicht falsch gelesen zu werden.
 */

/** Zähler und Nenner in Mono — „6 von 14". */
export function Basis({ n, von, was }: { n: number; von: number; was?: string }) {
  return (
    <span className="font-mono text-xs tabular-nums text-muted-foreground">
      {n.toLocaleString("de-DE")} von {von.toLocaleString("de-DE")}{was ? ` ${was}` : ""}
    </span>
  );
}

/** Die Veränderung gegen den Vorzeitraum — als Chip in Signal-Orange.
 *
 *  `prozent`: beide Werte sind Anteile, die Differenz steht in Punkten.
 *  `invers`: klein ist gut (Antworten ohne Quelle). Die Farbe sagt nicht
 *  „gut/schlecht", sondern nur „hat sich bewegt" — die Richtung trägt der
 *  Pfeil, die Bewertung der Kontext. Ohne Vergleichswert: „kein Vergleich",
 *  nie eine erfundene Null. */
export function Veraenderung({ jetzt, vorher, prozent, invers, klein }: {
  jetzt: number | null; vorher: number | null | undefined; prozent?: boolean; invers?: boolean; klein?: boolean;
}) {
  const groesse = klein ? "text-xs px-1.5 py-px" : "text-xs px-2 py-0.5";
  if (jetzt == null || vorher == null) {
    return <span className={cn("inline-flex items-center rounded-full border border-dashed border-border font-mono text-muted-foreground", groesse)}>kein Vergleich</span>;
  }
  const d = prozent ? Math.round((jetzt - vorher) * 100) : jetzt - vorher;
  if (d === 0) {
    return <span className={cn("inline-flex items-center rounded-full bg-muted font-mono text-muted-foreground", groesse)}>unverändert</span>;
  }

  const text = prozent ? `${d > 0 ? "+" : "−"}${Math.abs(d)} Pkt.` : `${d > 0 ? "+" : "−"}${Math.abs(d).toLocaleString("de-DE")}`;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full bg-signal/[0.10] font-mono font-semibold text-orange-800 dark:text-orange-300", groesse)}
      title={`Gegenüber dem vorherigen Zeitraum${invers ? " (weniger ist hier besser)" : ""}`}>
      <svg className="h-2.5 w-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        {d > 0 ? <path d="M12 19V5M5 12l7-7 7 7" /> : <path d="M12 5v14M19 12l-7 7-7-7" />}
      </svg>
      {text}
    </span>
  );
}

export function AbschnittKopf({ titel, rechts, children }: { titel: string; rechts?: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
      <div className="min-w-0">
        <h3 className="font-display text-lg font-bold text-foreground">{titel}</h3>
        {children && <p className="mt-0.5 max-w-[62ch] text-sm text-muted-foreground">{children}</p>}
      </div>
      {rechts && <span className="pt-1 font-mono text-xs text-muted-foreground">{rechts}</span>}
    </div>
  );
}

/** Eine Kennzahl: die Zahl, woraus sie besteht, und wie sie sich bewegt hat.
 *  `null` heißt „keine Aussage", nicht „0 %". */
export function KennzahlCard({ label, hint, wert, vorher, basis, anteil, invers, vergleichbar = true }: {
  label: string; hint: string; wert: number | null; vorher: number | null;
  basis?: [number, number] | readonly [number, number]; anteil?: boolean; invers?: boolean;
  /** Ein Vorzeitraum mit ein, zwei Konten ist kein Vergleich, sondern Rauschen —
   *  dann steht „kein Vergleich" da, nicht „−57 Pkt.". */
  vergleichbar?: boolean;
}) {
  const text = wert == null ? "–" : anteil ? `${Math.round(wert * 100)} %` : wert.toLocaleString("de-DE");
  return (
    <Card className="p-3.5">
      <StatKicker>{label}</StatKicker>
      <p className={cn("mt-1.5 whitespace-nowrap font-display text-[28px] font-extrabold leading-none tracking-tight tabular-nums", wert == null ? "text-muted-foreground" : "text-foreground")}>
        {text}
      </p>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
        <Veraenderung jetzt={wert} vorher={vergleichbar ? vorher : null} prozent={anteil} invers={invers} klein />
        {basis && wert != null && <Basis n={basis[0]} von={basis[1]} />}
      </div>
      <p className="mt-1.5 text-sm leading-snug text-muted-foreground">{wert == null ? "noch keine Grundlage" : hint}</p>
    </Card>
  );
}

