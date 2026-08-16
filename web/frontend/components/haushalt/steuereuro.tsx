"use client";

// „Von 100 Euro der Stadt" (Design H-04): 10×10-Raster, ein Feld = 1 Euro.
// Bewusst NICHT das Kern-Visual (Rundung verschluckt Details), sondern die
// zweite Ansicht hinter dem Umschalter in der Übersicht. Die Grenze der
// Metapher steht sichtbar darunter: Es sind nicht 100 Euro Steuergeld —
// bei einem Minus stammt ein Teil aus dem Ersparten.

import { bereichKanon } from "@/lib/haushalt-bereiche";
import { HaushaltZeile, deMio, mio } from "@/lib/haushalt";

/** Ganze Euro je Bereich per größtem Rest auf exakt 100 bringen —
 *  simple Rundung ergäbe je nach Jahr 98–102 Felder. */
function verteile100<T extends { wert: number }>(rows: T[], gesamt: number) {
  const roh = rows.map((r) => ({ ...r, exakt: (r.wert / gesamt) * 100 }));
  const basis = roh.map((r) => ({ ...r, euro: Math.floor(r.exakt) }));
  let rest = 100 - basis.reduce((s, r) => s + r.euro, 0);
  const nachRest = [...basis].sort((a, b) => (b.exakt - b.euro) - (a.exakt - a.euro));
  for (const r of nachRest) {
    if (rest <= 0) break;
    r.euro += 1;
    rest -= 1;
  }
  return basis.filter((r) => r.euro > 0);
}

export function Steuereuro({ zeilen, jahr }: { zeilen: HaushaltZeile[]; jahr: number }) {
  const parts = zeilen.filter((z) => z.is_summe !== 1);
  const gesamt = zeilen.find((z) => z.is_summe === 1);
  if (!gesamt?.aufwendungen) return null;

  // Namen aus dem Wörterbuch (`lib/haushalt-bereiche.ts`): Die Schreibweise
  // wechselt je Jahrgang, die Legende soll beim Jahreswechsel aber nicht
  // mitwandern. `kurz` trägt die Überschrift, `name` die Legende.
  const sortiert = [...parts]
    .map((z) => {
      const kanon = bereichKanon(z.bereich);
      return { name: kanon.name, kurz: kanon.kurz, wert: z.aufwendungen ?? 0 };
    })
    .filter((r) => r.wert > 0)
    .sort((a, b) => b.wert - a.wert);
  // Ab Platz 10 bündeln — kleiner als 1 Feld wird sonst unsichtbar.
  const gross = sortiert.slice(0, 9);
  const kleine = sortiert.slice(9);
  const rows = kleine.length
    ? [...gross, {
        name: `${kleine.length} kleinere Bereiche`,
        kurz: `${kleine.length} kleinere`,
        wert: kleine.reduce((s, r) => s + r.wert, 0),
      }]
    : gross;
  const felder = verteile100(rows, gesamt.aufwendungen);

  const einMio = mio(gesamt.ertraege) ?? 0;
  const ausMio = mio(gesamt.aufwendungen) ?? 0;
  // Fehlbetrag aus Rohwerten runden (812,9/883,9 ergäbe 71,0 statt 71,1).
  const fehltMio = mio((gesamt.aufwendungen ?? 0) - (gesamt.ertraege ?? 0)) ?? 0;
  const eingenommen = Math.min(100, Math.round((einMio / ausMio) * 100));

  // Zellen 0–99 den Bereichen der Reihe nach zuordnen (Leserichtung).
  const zellen: number[] = [];
  felder.forEach((f, i) => { for (let k = 0; k < f.euro; k++) zellen.push(i); });

  const farbe = (i: number) => `var(--hh-aus-${Math.min(i, 9)})`;
  const top = felder[0];
  const zweit = felder[1];

  return (
    <div>
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Von 100 Euro der Stadt · {jahr}
      </p>
      {top && zweit && (
        <p className="mb-3 mt-1.5 max-w-[38ch] font-display text-[19px] font-bold leading-snug tracking-tight">
          Gibt Oldenburg {top.euro} Euro für {top.kurz} aus — und {zweit.euro} für {zweit.kurz}.
        </p>
      )}

      <div className="flex flex-wrap items-start gap-5">
        <svg viewBox="0 0 280 280" className="w-full max-w-[280px] flex-none" role="img"
          aria-label={`Aufteilung von 100 Euro Ausgaben ${jahr}: ${felder.map((f) => `${f.name} ${f.euro} Euro`).join(", ")}`}>
          {zellen.map((bereichIdx, i) => (
            // Die Fuge zwischen den Feldern hat die Farbe der FLÄCHE, auf der
            // das Raster liegt — auf der dunklen Anzeigetafel ist das nicht
            // die Kartenfarbe (`--hh-raster`, s. app/globals.css).
            <rect key={i} x={(i % 10) * 28} y={Math.floor(i / 10) * 28} width={28} height={28}
              fill={farbe(bereichIdx)} strokeWidth={2} stroke="hsl(var(--hh-raster))" />
          ))}
          <rect x={0.5} y={0.5} width={279} height={279} fill="none" className="stroke-border" />
        </svg>

        <div className="min-w-[220px] flex-1 space-y-1.5">
          {felder.map((f, i) => (
            <div key={f.name} className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 flex-none rounded-[2px]" style={{ background: farbe(i) }} />
              <span className="min-w-0 flex-1 truncate text-xs">{f.name}</span>
              <span className="font-mono text-xs font-medium tabular-nums">{f.euro}&nbsp;€</span>
            </div>
          ))}
          <p className="pt-1.5 text-[11px] leading-relaxed text-muted-foreground">
            Ein Feld = 1&nbsp;€ von 100, auf ganze Euro gerundet. Genaue Werte zeigt die Balken-Ansicht.
          </p>
        </div>
      </div>

      {eingenommen < 100 && (
        <p className="mt-3.5 border-t border-border/60 pt-3 text-xs leading-relaxed text-foreground/85">
          <strong>Grenze der Metapher:</strong> Es sind nicht 100 Euro Steuergeld — {eingenommen}&nbsp;Euro
          sind eingenommen, {100 - eingenommen}&nbsp;Euro stammen aus dem Ersparten der Stadt
          ({deMio(fehltMio)}&#8239;Mio. aus der Rücklage).
        </p>
      )}
    </div>
  );
}
