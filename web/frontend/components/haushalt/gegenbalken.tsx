"use client";

// Kern-Visual der Haushalts-Übersicht (Design H-03, Empfehlung aus dem
// Variantenvergleich H-02…H-04): zwei gestapelte Leisten „Woher"/„Wohin" auf
// GEMEINSAMER Achse — 100 % = die größere der beiden Summen. Endet die
// Einnahmen-Leiste früher, ist der Überhang das Minus: Er wird als
// schraffierter Rücklagen-Kasten gezeigt (die eine Stärke des verworfenen
// Sankeys, hierher übernommen). Kein Sankey: Der Plan kennt keine
// Euro-zu-Zweck-Flüsse, jede Verbindungslinie wäre erfunden.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { SegmentText } from "@/components/grafik/gegenbalken";
import { bereichKanon } from "@/lib/haushalt-bereiche";
import { HaushaltZeile, bereichSlug, deMio, mio } from "@/lib/haushalt";
import { cn } from "@/lib/utils";

type Seite = "ein" | "aus";

// Die Beschriftungsregel (H-03) — „Name · Wert", „Kurzname · Wert", Kurzname,
// nichts, gemessen im unsichtbaren Zwilling — wohnt seit dem Baukasten in
// `components/grafik/gegenbalken.tsx` (`SegmentText`): eine Implementierung,
// beide Gegenbalken. Die Lehren aus dem Dauerflackern (Tim, 16.08.) und dem
// Font-Swap stehen dort.

function Leiste({
  seite, zeilen, skala, onHover, onPin, aktiv,
}: {
  seite: Seite;
  zeilen: { z: HaushaltZeile; wert: number }[];
  skala: number;
  onHover: (name: string) => void;
  onPin: (name: string) => void;
  aktiv: string | null;
}) {
  return (
    <div className="flex h-8 gap-[1.5px] overflow-hidden rounded-md" role="list">
      {zeilen.map(({ z, wert }, i) => {
        const breite = (wert / skala) * 100;
        const gewaehlt = aktiv === z.bereich;
        // Kurzname aus dem Wörterbuch (`lib/haushalt-bereiche.ts`), nicht am
        // Trennzeichen abgeschnitten: „Klima/Umwelt/Mobilität/Bau/Grün/Friedh."
        // wurde so zu „Klima", „Personal/Organisation/Digitalisierung/IT" zu
        // „Personal" — beides sagt weniger, als der Bereich enthält, und beim
        // nächsten Namenswechsel wäre es wieder etwas anderes.
        const kanon = bereichKanon(z.bereich);
        return (
          <button
            key={z.bereich}
            type="button"
            role="listitem"
            aria-label={`${kanon.name}: ${deMio(wert)} Mio. Euro`}
            onClick={() => onPin(z.bereich)}
            onMouseEnter={() => onHover(z.bereich)}
            onFocus={() => onHover(z.bereich)}
            className={cn(
              // KEIN Padding am Button: Es zählt zur Elementbreite und macht
              // die Leiste auf schmalen Bildschirmen unmaßstäblich — bei 13
              // Segmenten fraßen 13×16 px Innenabstand so viel Platz, dass der
              // größte Balken statt 65 % nur noch 23 % einnahm (Tim, 16.08.).
              // Der Innenabstand sitzt jetzt im Text-Span, wo er die Breite
              // des Balkens nicht verändert.
              "flex min-w-0 items-center overflow-hidden text-[11px] font-semibold transition-opacity",
              aktiv && !gewaehlt && "opacity-35",
              gewaehlt && "z-[2] rounded ring-2 ring-signal",
            )}
            style={{ width: `${breite}%`, background: `var(--hh-${seite}-${Math.min(i, seite === "ein" ? 6 : 9)})`, color: "var(--hh-seg-text)" }}
          >
            <SegmentText stufen={[
              `${kanon.name} · ${deMio(wert)} Mio. €`,
              `${kanon.name} · ${deMio(wert)}`,
              `${kanon.kurz} · ${deMio(wert)}`,
              kanon.kurz,
            ]} />
          </button>
        );
      })}
    </div>
  );
}

/** Detail zum gewählten Bereich (H-03): Ausgaben, eigene Einnahmen, Netto,
 *  Sprung ins Dossier. Sitzt direkt unter „seiner" Leiste und bleibt nach
 *  einem Klick offen (gepinnt) — inklusive Schließen-Knopf, weil sie dann
 *  nicht mehr von selbst verschwindet. */
function Detail({ z, gepinnt, onClose, onOpen }: {
  z: HaushaltZeile | null | undefined;
  gepinnt: boolean;
  onClose: () => void;
  onOpen: (bereich: string) => void;
}) {
  if (!z) return null;
  return (
    <div className="mt-2.5 inline-block rounded-xl border border-border bg-card px-3 py-2.5 shadow-[0_12px_32px_-10px_rgba(2,32,71,0.28)]">
      <div className="flex items-start gap-3">
        <p className="text-[12.5px] font-bold">{bereichKanon(z.bereich).name}</p>
        {gepinnt && (
          <button type="button" onClick={onClose} aria-label="Schließen"
            className="-mr-1 -mt-0.5 rounded p-0.5 text-muted-foreground hover:text-foreground">
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      <p className="mt-1 text-[11.5px] leading-relaxed text-foreground/80">
        {deMio(mio(z.expenses))}&#8239;Mio.&nbsp;€ geplante Ausgaben · {deMio(mio(z.revenues))}&#8239;Mio.&nbsp;€ Erträge des Bereichs
        <br />
        <strong className="text-foreground">{deMio(mio(z.result))}&#8239;Mio.&nbsp;€</strong>{" "}
        {(z.result ?? 0) < 0 ? "Zuschussbedarf" : "Überschuss"}
      </p>
      <button type="button" className="mt-1.5 text-[11.5px] font-semibold text-primary"
        onClick={() => onOpen(z.bereich)}>
        Bereich öffnen →
      </button>
    </div>
  );
}

export function Gegenbalken({ zeilen, year }: { zeilen: HaushaltZeile[]; year: number }) {
  const router = useRouter();
  // Zwei Zustände statt einem: `hover` ist flüchtig, `gepinnt` überlebt das
  // Verlassen des Segments. Vorher schloss das onMouseLeave des Segments die
  // Detail-Box genau in dem Moment, in dem man sie anklicken wollte
  // (Tim, 16.08.) — jetzt hält der Container den Hover, und ein Klick pinnt.
  type Wahl = { seite: Seite; bereich: string };
  const [hover, setHover] = useState<Wahl | null>(null);
  const [gepinnt, setGepinnt] = useState<Wahl | null>(null);
  const wahl = gepinnt ?? hover;
  const aktiv = wahl?.bereich ?? null;
  const pinnen = (w: Wahl) =>
    setGepinnt((g) => (g?.bereich === w.bereich && g.seite === w.seite ? null : w));

  const parts = zeilen.filter((z) => z.is_total !== 1);
  const gesamt = zeilen.find((z) => z.is_total === 1);
  if (!gesamt || !parts.length) return null;

  const einSumme = mio(gesamt.revenues) ?? 0;
  const ausSumme = mio(gesamt.expenses) ?? 0;
  const skala = Math.max(einSumme, ausSumme);
  // Saldo aus den Rohwerten runden — 812,9 − 883,9 ergäbe −71,0, tatsächlich −71,1.
  const balance = mio((gesamt.revenues ?? 0) - (gesamt.expenses ?? 0)) ?? 0;
  const einEnde = (einSumme / skala) * 100; // wo die kürzere Leiste endet

  const sortiert = (key: "revenues" | "expenses") =>
    [...parts]
      .map((z) => ({ z, wert: mio(z[key]) ?? 0 }))
      .filter((x) => x.wert > 0)
      .sort((a, b) => b.wert - a.wert);

  const ein = sortiert("revenues");
  const aus = sortiert("expenses");
  const gewaehlte = aktiv ? parts.find((z) => z.bereich === aktiv) : null;
  const oeffnen = (bereich: string) => router.push(`/haushalt/bereich?name=${bereichSlug(bereich)}`);

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
      {/* Umbricht statt zu spalten: Auf 375 px zerriss `justify-between` beide
          Kicker in je zwei Zeilen, die dann ineinander verzahnt standen. */}
      <div className="mb-3.5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Einnahmen und Ausgaben · {year}
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {parts.length} Teilhaushalte · Mio. Euro
        </span>
      </div>

      {/* Ein Block = eine Hover-Fläche: Leiste, Legende UND Detail-Box liegen
          im selben Container, damit der Weg von der Leiste zur Box den Hover
          nicht abreißen lässt (Tim, 16.08.). */}
      <div onMouseLeave={() => setHover(null)}>
      {/* Diese Leiste hieß bis 16.08. „Woher das Geld kommt". Das ist sie
          nicht: Sie zeigt, WELCHER BEREICH eine Einnahme verbucht — und weil
          Steuern und Zuweisungen zentral in der Kämmerei auflaufen, liegen
          dort rund zwei Drittel. Wer die Überschrift wörtlich nahm, las
          heraus, das meiste Geld komme aus der Verwaltung selbst. Woher es
          wirklich stammt, beantwortet die Seite „Woher kommt das Geld?"
          und das Flussbild darunter. */}
      <p className="mb-1.5 text-[12.5px] font-semibold">
        Wo Einnahmen verbucht werden <span className="font-normal text-muted-foreground">— {deMio(einSumme)}&#8239;Mio.&nbsp;€</span>
      </p>
      <div style={{ width: `${einEnde}%` }}>
        <Leiste seite="ein" zeilen={ein} skala={einSumme} aktiv={aktiv}
          onHover={(b) => setHover({ seite: "ein", bereich: b })}
          onPin={(b) => pinnen({ seite: "ein", bereich: b })} />
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3.5 gap-y-1">
        {einLeg.gezeigt.map(({ z, wert }, i) => (
          <span key={z.bereich} className="inline-flex items-center gap-1.5 text-[11px] text-foreground/80">
            <span className="h-2 w-2 rounded-[2px]" style={{ background: `var(--hh-ein-${Math.min(ein.findIndex((e) => e.z === z), 6)})` }} />
            {bereichKanon(z.bereich).name} {deMio(wert)}&#8239;Mio.&nbsp;€
          </span>
        ))}
        {einLeg.rest.length > 0 && (
          <span className="text-[11px] text-muted-foreground">{einLeg.rest.length} weitere {deMio(einLeg.restSumme)}&#8239;Mio.&nbsp;€</span>
        )}
      </div>
      {ein[0] && (
        <p className="mt-1.5 max-w-[74ch] text-[11.5px] leading-relaxed text-muted-foreground">
          Der größte Abschnitt ist keine einzelne Einnahmequelle. Im Bereich
          „{bereichKanon(ein[0].z.bereich).name}“ verbucht die Stadt Steuern und allgemeine
          Zuweisungen zentral. Die tatsächlichen Einnahmearten zeigt weiter unten der
          Abschnitt <em>Woher kommt das Geld?</em>
        </p>
      )}
      {wahl?.seite === "ein" && <Detail z={gewaehlte} gepinnt={!!gepinnt} onClose={() => { setGepinnt(null); setHover(null); }} onOpen={oeffnen} />}
      </div>

      {/* Achse mit Überhang: Bei Minus ein schraffierter Rücklagen-Kasten,
          bei Plus ein grüner Überschuss-Vermerk — nie interpoliert. Bei
          schmalem Überhang steht das Label rechtsbündig UNTER dem Kasten
          (wie H-03 mobil), sonst liefe es aus der Karte. */}
      <div className={cn("relative my-3.5", 100 - einEnde < 20 && balance < 0 ? "h-10" : "h-6")}>
        <div className="absolute inset-x-0 top-3 border-t border-border/60" />
        {balance < 0 && (
          <>
            <div className="absolute -top-1.5 h-9 border-l border-dashed border-signal" style={{ left: `${einEnde}%` }} />
            <div
              className="absolute top-1 flex h-4 items-center justify-center rounded border border-signal/55 hh-schraffur"
              style={{ left: `${einEnde}%`, right: 0 }}
            >
              {100 - einEnde >= 20 && (
                <span className="whitespace-nowrap font-mono text-[9.5px] font-bold uppercase text-signal">
                  {deMio(-balance)}&#8239;Mio.&nbsp;€ geplantes Minus
                </span>
              )}
            </div>
            {100 - einEnde < 20 && (
              <p className="absolute right-0 top-6 font-mono text-[9.5px] font-bold uppercase text-signal">
                {deMio(-balance)}&#8239;Mio.&nbsp;€ geplantes Minus
              </p>
            )}
          </>
        )}
        {/* Kein Grün. Ein geplanter Überschuss ist keine gute Note und ein
            geplantes Minus keine schlechte — dieselbe Regel, die für die
            Hantel gilt (components/grafik/hantel.tsx). Der Überschuss trug
            bis 16.08. den Erfolgs-Tint aus der Beschluss-Semantik und stand
            damit als Gegenstück zum orangefarbenen Minus da: gut gegen
            schlecht, ohne dass irgendwer das behaupten wollte. */}
        {balance > 0 && (
          <span className="absolute right-0 top-0 rounded-full border border-border bg-muted px-2 py-0.5 text-[10.5px] font-semibold text-foreground/80">
            +{deMio(balance)}&#8239;Mio.&nbsp;€ Überschuss geplant
          </span>
        )}
      </div>

      <div onMouseLeave={() => setHover(null)}>
      <p className="mb-1.5 text-[12.5px] font-semibold">
        Wo Ausgaben verbucht werden <span className="font-normal text-muted-foreground">— {deMio(ausSumme)}&#8239;Mio.&nbsp;€</span>
      </p>
      <div style={{ width: `${(ausSumme / skala) * 100}%` }}>
        <Leiste seite="aus" zeilen={aus} skala={ausSumme} aktiv={aktiv}
          onHover={(b) => setHover({ seite: "aus", bereich: b })}
          onPin={(b) => pinnen({ seite: "aus", bereich: b })} />
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3.5 gap-y-1">
        {ausLeg.gezeigt.map(({ z, wert }) => (
          <span key={z.bereich} className="inline-flex items-center gap-1.5 text-[11px] text-foreground/80">
            <span className="h-2 w-2 rounded-[2px]" style={{ background: `var(--hh-aus-${Math.min(aus.findIndex((a) => a.z === z), 9)})` }} />
            {bereichKanon(z.bereich).name} {deMio(wert)}&#8239;Mio.&nbsp;€
          </span>
        ))}
        {ausLeg.rest.length > 0 && (
          <span className="text-[11px] text-muted-foreground">{ausLeg.rest.length} weitere {deMio(ausLeg.restSumme)}&#8239;Mio.&nbsp;€</span>
        )}
      </div>
      {wahl?.seite === "aus" && <Detail z={gewaehlte} gepinnt={!!gepinnt} onClose={() => { setGepinnt(null); setHover(null); }} onOpen={oeffnen} />}
      </div>

    </div>
  );
}
