"use client";

// /haushalt/pflicht — „Muss oder kann?" (Design H-15, Empfehlung).
//
// Der Filter ist redaktionell, die Summen darunter sind aus dem Plan. Die
// Seite trägt das stärkste Argument des ganzen Bereichs: Selbst wenn der Rat
// alles Freiwillige striche, wäre das Defizit nicht gedeckt. Das entschärft
// die Reflexdebatte („kürzt doch bei der Kultur"), ohne sie zu bewerten.

import { useState } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { HaushaltDaten, bereiche, deMio, jahreSortiert, mio, summe } from "@/lib/haushalt";
import {
  PFLICHT_ERKLAERUNG, PFLICHT_LABEL, PFLICHT_ZUORDNUNG, PflichtStufe,
} from "@/lib/haushalt-pflicht";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { Segmented } from "@/components/ui";
import { cn } from "@/lib/utils";

const STUFEN: PflichtStufe[] = ["pflicht", "spielraum", "freiwillig"];

export default function PflichtPage() {
  const { data, loading } = useFetch<HaushaltDaten>("/council/haushalt");
  const [filter, setFilter] = useState<PflichtStufe | "alle">("alle");

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>;
  }

  const jahre = jahreSortiert(data);
  const jahr = jahre[jahre.length - 1];
  const zeilen = data.jahre[String(jahr)] ?? [];
  const gesamt = summe(zeilen);
  const gesamtAus = mio(gesamt?.aufwendungen) ?? 0;
  const defizit = gesamt?.ertraege != null && gesamt?.aufwendungen != null
    ? mio(gesamt.aufwendungen - gesamt.ertraege) ?? 0 : 0;

  const rows = bereiche(zeilen).map((z) => ({
    z,
    aus: mio(z.aufwendungen) ?? 0,
    zuordnung: PFLICHT_ZUORDNUNG[z.bereich],
  })).sort((a, b) => b.aus - a.aus);

  const gefiltert = filter === "alle" ? rows : rows.filter((r) => r.zuordnung?.stufe === filter);
  const summeGefiltert = gefiltert.reduce((s, r) => s + r.aus, 0);
  const anteil = gesamtAus > 0 ? (summeGefiltert / gesamtAus) * 100 : 0;
  const freiwillig = rows.filter((r) => r.zuordnung?.stufe === "freiwillig");
  const summeFreiwillig = freiwillig.reduce((s, r) => s + r.aus, 0);

  const quellen: QuellenSchluessel[] = ["plan"];

  return (
    <Quellenkontext schluessel={quellen}>
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">Muss oder kann?</span>
      </div>

      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[25px]">Muss oder kann?</h1>
        <p className="mt-2 max-w-[66ch] text-sm leading-relaxed text-foreground/90">
          Über einen großen Teil des Haushalts kann der Rat gar nicht frei entscheiden — Bundes-
          und Landesgesetze schreiben die Aufgaben vor. Hier steht, welcher Bereich wie viel
          Spielraum lässt.
        </p>
      </div>

      <Segmented
        value={filter}
        onChange={setFilter}
        tone="primary"
        options={[
          { value: "alle" as const, label: `Alle ${rows.length}` },
          ...STUFEN.map((s) => ({ value: s, label: PFLICHT_LABEL[s] })),
        ]}
      />

      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              {filter === "alle" ? "Alle Bereiche" : PFLICHT_LABEL[filter]}
            </p>
            <p className="mt-1.5 text-[13px] text-foreground/85">
              {gefiltert.length} von {rows.length} Bereichen · zusammen{" "}
              <strong>{deMio(summeGefiltert)}&#8239;Mio.&nbsp;€</strong>
              <Beleg q="plan" />
            </p>
          </div>
          <div className="text-right">
            <p className="font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">
              Anteil an allen Ausgaben
            </p>
            <p className="font-display text-2xl font-bold tabular-nums">
              {anteil.toLocaleString("de-DE", { maximumFractionDigits: 1 })}&nbsp;%
            </p>
          </div>
        </div>
        {filter !== "alle" && (
          <p className="mt-3 border-t border-border/60 pt-3 text-[12.5px] leading-relaxed text-foreground/85">
            {PFLICHT_ERKLAERUNG[filter]}
          </p>
        )}
      </div>

      {/* Das Kernargument — mit echten Zahlen, ohne Bewertung. */}
      {summeFreiwillig > 0 && defizit > 0 && (
        <LottiErklaert
          titel="Warum Kürzen allein nicht reicht"
          text={`Alle überwiegend freiwilligen Bereiche zusammen kosten ${deMio(summeFreiwillig)} Millionen Euro im Jahr. Das geplante Minus beträgt ${deMio(defizit)} Millionen. Selbst wenn der Rat das Freiwillige komplett striche — kein Theater, keine Sportförderung, keine Wirtschaftsförderung —, wäre das Loch also nicht gestopft.`}
        />
      )}

      <div className="flex flex-col gap-2">
        {gefiltert.map(({ z, aus, zuordnung }) => (
          <div key={z.bereich} className="rounded-xl border border-border bg-card p-3.5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-bold leading-snug">{z.bereich}</p>
                {zuordnung ? (
                  <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">{zuordnung.was}</p>
                ) : (
                  <p className="mt-1 text-[12px] italic text-muted-foreground">Noch nicht eingeordnet</p>
                )}
              </div>
              <div className="flex flex-none items-center gap-2.5">
                {zuordnung && (
                  <span className={cn(
                    "rounded-full px-2.5 py-1 text-[10.5px] font-semibold",
                    zuordnung.stufe === "pflicht" && "bg-muted text-muted-foreground",
                    zuordnung.stufe === "spielraum" && "bg-primary/10 text-primary",
                    zuordnung.stufe === "freiwillig" && "bg-signal/10 text-signal",
                  )}>
                    {PFLICHT_LABEL[zuordnung.stufe]}
                  </span>
                )}
                <span className="font-display text-[17px] font-bold tabular-nums">
                  {deMio(aus)}<span className="text-[11px] font-semibold text-muted-foreground">&#8239;Mio.</span>
                </span>
              </div>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full" style={{
                width: `${Math.min((aus / (rows[0]?.aus || 1)) * 100, 100)}%`,
                background: zuordnung?.stufe === "freiwillig" ? "hsl(var(--signal))" : "var(--hh-ein-0)",
              }} />
            </div>
          </div>
        ))}
      </div>

      {/* „Genauer wird es erst mit der Produktebene, die wir noch einlesen"
          stand hier bis 16.08. — die Produktebene liegt seit #500 vor. Ein
          Verweis, der auf sie zeigt, ist auch die ehrlichere Auskunft: Die
          Grobzuordnung ganzer Teilhaushalte bleibt grob, aber man kann jetzt
          nachsehen. „Kür" heißt auf dieser Seite und im Labor dasselbe wie
          „überwiegend freiwillig" in den Karten darüber; das stand nirgends. */}
      <p className="max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        <strong>Wie sicher ist diese Einordnung?</strong> Die Summen stammen aus dem beschlossenen
        Haushaltsplan. Die Zuordnung zu Pflicht und Kür — also zu dem, was sein muss, und dem,
        was der Rat freiwillig tut — ist dagegen eine <em>redaktionelle Einschätzung auf Ebene
        ganzer Teilhaushalte</em>: In fast jedem Bereich steckt beides. Genauer steht es je
        Aufgabe auf der{" "}
        <Link href="/haushalt/produkte" className="font-semibold text-primary">Produktebene</Link>,
        wo die Stadt für jedes Produkt selbst angibt, wie viel Spielraum sie sieht.
      </p>

      <Quellenverzeichnis schluessel={quellen} />
    </div>
    </Quellenkontext>
  );
}
