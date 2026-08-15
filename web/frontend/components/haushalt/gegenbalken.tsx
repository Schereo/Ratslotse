"use client";

// Kern-Visual der Haushalts-Übersicht (Design H-03, Empfehlung aus dem
// Variantenvergleich H-02…H-04): zwei gestapelte Leisten „Woher"/„Wohin" auf
// GEMEINSAMER Achse — 100 % = die größere der beiden Summen. Endet die
// Einnahmen-Leiste früher, ist der Überhang das Minus: Er wird als
// schraffierter Rücklagen-Kasten gezeigt (die eine Stärke des verworfenen
// Sankeys, hierher übernommen). Kein Sankey: Der Plan kennt keine
// Euro-zu-Zweck-Flüsse, jede Verbindungslinie wäre erfunden.

import { useLayoutEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { HaushaltZeile, bereichSlug, deMio, mio } from "@/lib/haushalt";
import { cn } from "@/lib/utils";

type Seite = "ein" | "aus";

/** Beschriftungsregel (H-03) wörtlich: Ein Segment trägt seinen Text nur,
 *  wenn er WIRKLICH hineinpasst — gemessen, nicht geschätzt. Erst die lange
 *  Fassung (Name · Wert), dann der Kurzname, sonst nichts. Nie verkleinern,
 *  nie abschneiden: eine abgeschnittene 169,2 liest sich als 16. */
function SegmentText({ lang, kurz }: { lang: string; kurz: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [stufe, setStufe] = useState(0); // 0 = lang, 1 = kurz, 2 = nichts

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const pruefe = () => {
      // Von vorn messen (Viewport-Resize kann wieder Platz schaffen).
      setStufe(0);
      requestAnimationFrame(() => {
        const e = ref.current;
        if (!e) return;
        if (e.scrollWidth <= e.clientWidth) return;
        setStufe(1);
        requestAnimationFrame(() => {
          const e2 = ref.current;
          if (e2 && e2.scrollWidth > e2.clientWidth) setStufe(2);
        });
      });
    };
    pruefe();
    const ro = new ResizeObserver(pruefe);
    ro.observe(el);
    return () => ro.disconnect();
  }, [lang, kurz]);

  return (
    <span ref={ref} className="block w-full overflow-hidden whitespace-nowrap">
      {stufe === 0 ? lang : stufe === 1 ? kurz : ""}
    </span>
  );
}

function Leiste({
  seite, zeilen, skala, onPick, aktiv,
}: {
  seite: Seite;
  zeilen: { z: HaushaltZeile; wert: number }[];
  skala: number;
  onPick: (name: string | null) => void;
  aktiv: string | null;
}) {
  return (
    <div className="flex h-8 gap-[1.5px] overflow-hidden rounded-md" role="list">
      {zeilen.map(({ z, wert }, i) => {
        const breite = (wert / skala) * 100;
        const gewaehlt = aktiv === z.bereich;
        const kurz = z.bereich.split(" und ")[0].split(",")[0].split("/")[0];
        return (
          <button
            key={z.bereich}
            type="button"
            role="listitem"
            aria-label={`${z.bereich}: ${deMio(wert)} Mio. Euro`}
            onClick={() => onPick(gewaehlt ? null : z.bereich)}
            onMouseEnter={() => onPick(z.bereich)}
            onMouseLeave={() => onPick(null)}
            className={cn(
              "flex min-w-0 items-center overflow-hidden px-2 text-[11px] font-semibold transition-opacity",
              aktiv && !gewaehlt && "opacity-35",
              gewaehlt && "z-[2] rounded ring-2 ring-signal",
            )}
            style={{ width: `${breite}%`, background: `var(--hh-${seite}-${Math.min(i, seite === "ein" ? 6 : 9)})`, color: "var(--hh-seg-text)" }}
          >
            {breite > 8 && <SegmentText lang={`${z.bereich} · ${deMio(wert)}`} kurz={kurz} />}
          </button>
        );
      })}
    </div>
  );
}

export function Gegenbalken({ zeilen, jahr }: { zeilen: HaushaltZeile[]; jahr: number }) {
  const router = useRouter();
  const [aktiv, setAktiv] = useState<string | null>(null);

  const parts = zeilen.filter((z) => z.is_summe !== 1);
  const gesamt = zeilen.find((z) => z.is_summe === 1);
  if (!gesamt || !parts.length) return null;

  const einSumme = mio(gesamt.ertraege) ?? 0;
  const ausSumme = mio(gesamt.aufwendungen) ?? 0;
  const skala = Math.max(einSumme, ausSumme);
  // Saldo aus den Rohwerten runden — 812,9 − 883,9 ergäbe −71,0, tatsächlich −71,1.
  const saldo = mio((gesamt.ertraege ?? 0) - (gesamt.aufwendungen ?? 0)) ?? 0;
  const einEnde = (einSumme / skala) * 100; // wo die kürzere Leiste endet

  const sortiert = (key: "ertraege" | "aufwendungen") =>
    [...parts]
      .map((z) => ({ z, wert: mio(z[key]) ?? 0 }))
      .filter((x) => x.wert > 0)
      .sort((a, b) => b.wert - a.wert);

  const ein = sortiert("ertraege");
  const aus = sortiert("aufwendungen");
  const gewaehlte = aktiv ? parts.find((z) => z.bereich === aktiv) : null;

  // Legende: alles, was in der Leiste kein Label mehr trägt, steht hier als Text.
  const legende = (rows: { z: HaushaltZeile; wert: number }[]) => {
    const klein = rows.filter(({ wert }) => (wert / skala) * 100 <= 7);
    const gezeigt = klein.slice(0, 4);
    const rest = klein.slice(4);
    return { gezeigt, rest, restSumme: rest.reduce((s, r) => s + r.wert, 0) };
  };
  const einLeg = legende(ein);
  const ausLeg = legende(aus);

  return (
    <div>
      <div className="mb-3.5 flex items-baseline justify-between gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Woher &amp; wohin · {jahr}
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {parts.length} Teilhaushalte · Mio. Euro
        </span>
      </div>

      <p className="mb-1.5 text-[12.5px] font-semibold">
        Woher das Geld kommt <span className="font-normal text-muted-foreground">— {deMio(einSumme)}&#8239;Mio.</span>
      </p>
      <div style={{ width: `${einEnde}%` }}>
        <Leiste seite="ein" zeilen={ein} skala={einSumme} onPick={setAktiv} aktiv={aktiv} />
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3.5 gap-y-1">
        {einLeg.gezeigt.map(({ z, wert }, i) => (
          <span key={z.bereich} className="inline-flex items-center gap-1.5 text-[11px] text-foreground/80">
            <span className="h-2 w-2 rounded-[2px]" style={{ background: `var(--hh-ein-${Math.min(ein.findIndex((e) => e.z === z), 6)})` }} />
            {z.bereich} {deMio(wert)}
          </span>
        ))}
        {einLeg.rest.length > 0 && (
          <span className="text-[11px] text-muted-foreground">{einLeg.rest.length} weitere {deMio(einLeg.restSumme)}</span>
        )}
      </div>

      {/* Achse mit Überhang: Bei Minus ein schraffierter Rücklagen-Kasten,
          bei Plus ein grüner Überschuss-Vermerk — nie interpoliert. Bei
          schmalem Überhang steht das Label rechtsbündig UNTER dem Kasten
          (wie H-03 mobil), sonst liefe es aus der Karte. */}
      <div className={cn("relative my-3.5", 100 - einEnde < 20 && saldo < 0 ? "h-10" : "h-6")}>
        <div className="absolute inset-x-0 top-3 border-t border-border/60" />
        {saldo < 0 && (
          <>
            <div className="absolute -top-1.5 h-9 border-l border-dashed border-signal" style={{ left: `${einEnde}%` }} />
            <div
              className="absolute top-1 flex h-4 items-center justify-center rounded border border-signal/55 hh-schraffur"
              style={{ left: `${einEnde}%`, right: 0 }}
            >
              {100 - einEnde >= 20 && (
                <span className="whitespace-nowrap font-mono text-[9.5px] font-bold uppercase text-signal">
                  {deMio(-saldo)} aus der Rücklage
                </span>
              )}
            </div>
            {100 - einEnde < 20 && (
              <p className="absolute right-0 top-6 font-mono text-[9.5px] font-bold uppercase text-signal">
                {deMio(-saldo)} aus der Rücklage
              </p>
            )}
          </>
        )}
        {saldo > 0 && (
          <span className="absolute right-0 top-0 rounded-full bg-[#dcfce7] px-2 py-0.5 text-[10.5px] font-semibold text-[#15803d] dark:bg-[#15803d]/20 dark:text-[#4ade80]">
            +{deMio(saldo)}&#8239;Mio. Überschuss geplant
          </span>
        )}
      </div>

      <p className="mb-1.5 text-[12.5px] font-semibold">
        Wohin es fließt <span className="font-normal text-muted-foreground">— {deMio(ausSumme)}&#8239;Mio.</span>
      </p>
      <div style={{ width: `${(ausSumme / skala) * 100}%` }}>
        <Leiste seite="aus" zeilen={aus} skala={ausSumme} onPick={setAktiv} aktiv={aktiv} />
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3.5 gap-y-1">
        {ausLeg.gezeigt.map(({ z, wert }) => (
          <span key={z.bereich} className="inline-flex items-center gap-1.5 text-[11px] text-foreground/80">
            <span className="h-2 w-2 rounded-[2px]" style={{ background: `var(--hh-aus-${Math.min(aus.findIndex((a) => a.z === z), 9)})` }} />
            {z.bereich} {deMio(wert)}
          </span>
        ))}
        {ausLeg.rest.length > 0 && (
          <span className="text-[11px] text-muted-foreground">{ausLeg.rest.length} weitere {deMio(ausLeg.restSumme)}</span>
        )}
      </div>

      {/* Tap/Hover-Detail (H-03): Ausgaben, eigene Einnahmen, Netto + Sprung. */}
      {gewaehlte && (
        <div className="mt-3 inline-block rounded-xl border border-border bg-card px-3 py-2.5 shadow-[0_12px_32px_-10px_rgba(2,32,71,0.28)]">
          <p className="text-[12.5px] font-bold">{gewaehlte.bereich}</p>
          <p className="mt-1 text-[11.5px] leading-relaxed text-foreground/80">
            {deMio(mio(gewaehlte.aufwendungen))}&#8239;Mio. Ausgaben · {deMio(mio(gewaehlte.ertraege))} eigene Einnahmen
            <br />
            <strong className="text-foreground">{deMio(mio(gewaehlte.ergebnis))}&#8239;Mio.</strong>{" "}
            {(gewaehlte.ergebnis ?? 0) < 0 ? "trägt die Stadt" : "bleibt übrig"}
          </p>
          <button
            type="button"
            className="mt-1.5 text-[11.5px] font-semibold text-primary"
            onClick={() => router.push(`/haushalt/bereich?name=${bereichSlug(gewaehlte.bereich)}`)}
          >
            Bereich öffnen →
          </button>
        </div>
      )}
    </div>
  );
}
