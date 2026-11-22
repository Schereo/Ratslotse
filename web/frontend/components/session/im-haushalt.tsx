"use client";

/* „Im Haushalt“ auf der Punkt-Seite: Zahlenreihen aus dem Haushalt zu dem,
   was die Vorlage nennt — Teilhaushalt, Produkt, Betrieb, Steuer, Schulden.
   Damit eine Zahl aus der Vorlage eine Größenordnung bekommt. Auswahl und
   Zahlen kommen vom Server (`council/punkt_haushalt.py`), für alle sichtbar
   (Tim, 13.11.2026); in den Haushalts-Bereich führt der Kasten nur, wer ihn
   öffnen darf. Plan, Ist und Sätze stehen nie in einer Reihe: Jede sagt
   unter ihrer Überschrift, was sie ist. */

import Link from "next/link";
import { ArrowRight, ExternalLink } from "lucide-react";
import { BetragZelle, TextZelle, ZahlenTabelle } from "@/components/haushalt/zahlen-tabelle";
import { ABSCHNITT, HINWEIS, INHALT, KARTENTITEL, META } from "@/components/session/unterlagen-typo";
import { useAuth } from "@/lib/auth";
import { darfHaushalt } from "@/lib/rechte";
import { anteilSatz, haushaltSeite, jahrSpalte, wert, type HaushaltBlock, type HaushaltKontext } from "@/lib/punkt-haushalt";
import { cn } from "@/lib/utils";

function Reihe({ b }: { b: HaushaltBlock }) {
  return (
    <div className="border-t border-border pt-4 first:border-t-0 first:pt-0">
      <h3 className={ABSCHNITT}>{b.title}</h3>
      <p className={cn(META, "mt-0.5")}>{b.note}</p>
      {b.description && <p className={cn(HINWEIS, "mt-1.5 not-italic")}>{b.description}</p>}
      <ZahlenTabelle className="mt-2 breit:max-w-xl" spalten={[{ title: jahrSpalte(b.basis) }, ...b.columns.map((c) => ({ title: c, zahl: true }))]}>
        {b.rows.map((r) => (
          <tr key={r.year}>
            <TextZelle className="font-mono text-[11.5px] tabular-nums text-foreground">{r.year}</TextZelle>
            {r.values.map((v, i) => (
              <BetragZelle key={i} schlicht euro={v ?? null} text={wert(v, b.unit)} label={b.columns[i]} />
            ))}
          </tr>
        ))}
      </ZahlenTabelle>
      {b.share && <p className={cn(INHALT, "mt-2")}>{anteilSatz(b.share)}</p>}
      <p className={cn(META, "mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1")}>
        {b.sources.map((s) => (
          <a key={s.url} href={s.url} target="_blank" rel="noreferrer"
            className="inline-flex min-h-8 items-center gap-1 underline decoration-dashed underline-offset-2 hover:text-foreground">
            {s.label} <ExternalLink className="h-3 w-3 flex-none" aria-hidden />
          </a>
        ))}
      </p>
    </div>
  );
}

export function ImHaushalt({ kontext }: { kontext?: HaushaltKontext | null }) {
  const { user } = useAuth();
  if (!kontext?.blocks.length) return null;
  // Ein Weg in den Haushalts-Bereich je Karte, nicht je Reihe — und nur für
  // Konten, die ihn öffnen dürfen: Ein Link, der an der Rechtewand endet, ist
  // keiner.
  const seite = darfHaushalt(user) ? kontext.blocks.map((b) => haushaltSeite(b.page)).find(Boolean) ?? null : null;
  return (
    <section aria-labelledby="im-haushalt" className="mt-6 rounded-2xl border border-border bg-card p-5 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="im-haushalt" className={KARTENTITEL}>Im Haushalt</h2>
        {seite && (
          <Link href={seite} className={cn(META, "inline-flex min-h-11 items-center gap-1 font-medium text-primary hover:underline")}>
            Zum Haushalt <ArrowRight className="h-3.5 w-3.5 flex-none" aria-hidden />
          </Link>
        )}
      </div>
      <div className="mt-3 flex flex-col gap-4">
        {kontext.blocks.map((b) => <Reihe key={b.key} b={b} />)}
      </div>
    </section>
  );
}
