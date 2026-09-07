"use client";

import Link from "next/link";
import { Vote } from "lucide-react";
import { cn } from "@/lib/utils";
import { prozent, type WahlFlaeche, type WahlListe } from "@/lib/wahl-flaechen";

/** Die Karte „Wahlergebnis" in der Tafel-Spalte der Stadtkarte (Schritt 7):
 *  die Listen nach Anteil mit Parteifarbe als PUNKT (Designsprache: nie als
 *  Fläche), der Auszählungsstand und der Weg ins Wahlabend-Dashboard, wo
 *  Sitze, Mehrheiten und Verlauf stehen. Auf der Stadt-Stufe stadtweit, auf
 *  der Viertel-Stufe der Wahlbereich des Ortsbereichs — bei Grenzgebieten
 *  alle, die er berührt.
 */
export function WahlKarte({ kicker, titel, listen, counted, total, hinweis, className, style }: {
  kicker: string;
  titel: string;
  listen: WahlListe[];
  counted: number;
  total: number;
  /** Ein Satz unter den Listen, z. B. für Grenzgebiete. */
  hinweis?: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  const oben = listen.slice(0, 6);
  const ausgezaehlt = counted > 0;
  return (
    <section aria-labelledby={`wahl-${kicker}`} className={cn("rounded-2xl border border-border bg-card p-4", className)} style={style}>
      <div className="flex items-baseline justify-between gap-2">
        <div className="min-w-0">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            <Vote className="mr-1 inline h-3 w-3 align-[-1px]" aria-hidden />
            {kicker}
          </p>
          <h2 id={`wahl-${kicker}`} className="mt-0.5 font-display text-base font-bold text-foreground">{titel}</h2>
        </div>
        <span className="shrink-0 font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
          {ausgezaehlt ? `${counted} von ${total} Bezirken` : "noch nichts ausgezählt"}
        </span>
      </div>
      {ausgezaehlt ? (
        <ol className="mt-3 flex flex-col gap-1.5">
          {oben.map((l) => (
            <li key={l.slug} className="flex items-center gap-2.5 text-sm">
              <span
                aria-hidden
                className="h-2.5 w-2.5 shrink-0 rounded-full ring-1 ring-inset ring-black/10"
                style={{ background: l.color }}
              />
              <span className="min-w-0 flex-1 truncate font-medium text-foreground" title={l.name}>{l.short}</span>
              <span className="h-1.5 w-20 overflow-hidden rounded-full bg-muted" aria-hidden>
                <span className="block h-full rounded-full bg-primary/70" style={{ width: `${Math.max(2, l.share ?? 0)}%` }} />
              </span>
              <span className="w-14 shrink-0 text-right font-mono text-[12px] tabular-nums text-foreground">{prozent(l.share)}</span>
              {l.seats != null && <span className="w-8 shrink-0 text-right font-mono text-[11px] tabular-nums text-muted-foreground" title="Sitze">{l.seats}</span>}
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">Die Zahlen kommen ab Sonntag, 13. September, 18 Uhr — dann färbt sich die Karte nach der stärksten Liste.</p>
      )}
      {hinweis && <p className="mt-2 text-[12px] leading-relaxed text-muted-foreground">{hinweis}</p>}
      <Link href="/wahlabend" className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
        Zum Wahlabend: Sitze, Mehrheiten, Verlauf →
      </Link>
    </section>
  );
}

/** Die Zeile für einen Wahlbereich, aus einer Fläche der Karte. */
export function WahlKarteBereich({ flaechen, className, style }: {
  flaechen: WahlFlaeche[];
  className?: string;
  style?: React.CSSProperties;
}) {
  if (!flaechen.length) return null;
  const [erste, ...weitere] = flaechen;
  return (
    <WahlKarte
      kicker={`Ratswahl · Wahlbereich ${erste.roman}`}
      titel={erste.name}
      listen={erste.listen}
      counted={erste.counted}
      total={erste.total}
      hinweis={weitere.length
        ? `Dieser Ortsbereich reicht auch in Wahlbereich ${weitere.map((f) => `${f.roman} (${f.name})`).join(" und ")} hinein — die Stadt schneidet nach Wahlbezirken, nicht nach Ortsbereichen.`
        : "Die Stadt schneidet ihre Wahlbereiche nach Wahlbezirken, nicht nach Ortsbereichen — die Zuordnung ist ungefähr."}
      className={className}
      style={style}
    />
  );
}
