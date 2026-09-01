"use client";

// „Von 100 Euro der Stadt" (Design H-04): 10×10-Raster, ein Feld = 1 Euro.
// Bewusst NICHT das Kern-Visual (Rundung verschluckt Details), sondern die
// zweite Ansicht hinter dem Umschalter in der Übersicht. Die Grenze der
// Metapher steht sichtbar darunter: Es sind nicht 100 Euro Steuergeld —
// bei einem Minus stammt ein Teil aus dem Ersparten.
//
// DIE ZAHLEN STEHEN SCHON DA — DIE ZUORDNUNG NICHT.
// Jeder Bereich trägt seinen Betrag dauerhaft in der Legende („Soziales 21 €"),
// eine Ablese-Leiste wie in `zeitreihe.tsx` hätte hier also nichts hinzuzufügen.
// Was fehlte, war die Verbindung: Zehn Stufen derselben Ausgabenrampe sind in
// der Mitte kaum zu unterscheiden, und wer wissen wollte, welcher Block welcher
// Bereich ist, musste Farbtöne vergleichen. Deshalb heben sich Raster und
// Legende jetzt gegenseitig hervor.
//
// DIE LEGENDE IST DIE BEDIENFLÄCHE, nicht das Raster. Ihre Zeilen sind echte
// Knöpfe: fokussierbar, antippbar, groß genug für einen Finger. Ein 28-px-Feld
// im Raster ist ein brauchbares Ziel für den Zeiger, aber die Tastatur hätte
// dort 100 Stationen zu durchlaufen, um zehn Bereiche zu erreichen. Das Raster
// reagiert deshalb auf den Zeiger und bleibt im Übrigen Bild.

import { useState } from "react";
import { bereichKanon } from "@/lib/haushalt-bereiche";
import { HaushaltZeile, deMio, mio } from "@/lib/haushalt";
import { cn } from "@/lib/utils";

/** Ganze Euro je Bereich per größtem Rest auf exakt 100 bringen —
 *  simple Rundung ergäbe je nach Jahr 98–102 Felder. */
function verteile100<T extends { value: number }>(rows: T[], gesamt: number) {
  const roh = rows.map((r) => ({ ...r, exakt: (r.value / gesamt) * 100 }));
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

export function Steuereuro({ zeilen, year }: { zeilen: HaushaltZeile[]; year: number }) {
  // Welcher Bereich gerade hervorgehoben ist — null = keiner, der Ruhezustand.
  const [hervor, setHervor] = useState<number | null>(null);
  const parts = zeilen.filter((z) => z.is_total !== 1);
  const gesamt = zeilen.find((z) => z.is_total === 1);
  if (!gesamt?.expenses) return null;

  // Namen aus dem Wörterbuch (`lib/haushalt-bereiche.ts`): Die Schreibweise
  // wechselt je Jahrgang, die Legende soll beim Jahreswechsel aber nicht
  // mitwandern. `kurz` trägt die Überschrift, `name` die Legende.
  const sortiert = [...parts]
    .map((z) => {
      const kanon = bereichKanon(z.area);
      return { name: kanon.name, kurz: kanon.kurz, value: z.expenses ?? 0 };
    })
    .filter((r) => r.value > 0)
    .sort((a, b) => b.value - a.value);
  // Ab Platz 10 bündeln — kleiner als 1 Feld wird sonst unsichtbar.
  const gross = sortiert.slice(0, 9);
  const kleine = sortiert.slice(9);
  const rows = kleine.length
    ? [...gross, {
        name: `${kleine.length} kleinere Bereiche`,
        kurz: `${kleine.length} kleinere`,
        value: kleine.reduce((s, r) => s + r.value, 0),
      }]
    : gross;
  const felder = verteile100(rows, gesamt.expenses);

  const einMio = mio(gesamt.revenues) ?? 0;
  const ausMio = mio(gesamt.expenses) ?? 0;
  // Fehlbetrag aus Rohwerten runden (812,9/883,9 ergäbe 71,0 statt 71,1).
  const fehltMio = mio((gesamt.expenses ?? 0) - (gesamt.revenues ?? 0)) ?? 0;
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
        Von 100 Euro geplanter Ausgaben · {year}
      </p>
      {top && zweit && (
        <p className="mb-3 mt-1.5 max-w-[38ch] font-display text-[19px] font-bold leading-snug tracking-tight">
          Von 100 Euro entfallen {top.euro} Euro auf {top.kurz} und {zweit.euro} Euro auf {zweit.kurz}.
        </p>
      )}

      <div className="flex flex-wrap items-start gap-5">
        <svg viewBox="0 0 280 280" className="w-full max-w-[280px] flex-none" role="img"
          aria-label={`Aufteilung von 100 Euro Ausgaben ${year}: ${felder.map((f) => `${f.name} ${f.euro} Euro`).join(", ")}`}
          // Zeiger raus = Ruhezustand. Beim Tippen feuert `pointerleave` erst,
          // wenn woanders hingetippt wird — die Hervorhebung bleibt also
          // stehen, statt sofort zurückzuspringen.
          onPointerLeave={(e) => { if (e.pointerType === "mouse") setHervor(null); }}>
          {zellen.map((bereichIdx, i) => (
            // Die Fuge zwischen den Feldern hat die Farbe der FLÄCHE, auf der
            // das Raster liegt — auf der dunklen Anzeigetafel ist das nicht
            // die Kartenfarbe (`--hh-raster`, s. app/globals.css).
            <rect key={i} x={(i % 10) * 28} y={Math.floor(i / 10) * 28} width={28} height={28}
              fill={farbe(bereichIdx)}
              // Hervorgehoben wird mit der FUGE, nicht mit der Füllung: Die
              // Farbe ist die Auskunft dieser Grafik, sie darf sich beim
              // Zeigen nicht ändern. Die übrigen Felder blassen leicht ab.
              strokeWidth={2}
              stroke={hervor === bereichIdx ? "hsl(var(--foreground))" : "hsl(var(--hh-raster))"}
              opacity={hervor == null || hervor === bereichIdx ? 1 : 0.45}
              onPointerEnter={() => setHervor(bereichIdx)}
              onPointerDown={() => setHervor(bereichIdx)} />
          ))}
          <rect x={0.5} y={0.5} width={279} height={279} fill="none" pointerEvents="none"
            className="stroke-border" />
        </svg>

        <div className="min-w-[220px] flex-1 space-y-1.5">
          {felder.map((f, i) => (
            // Knopf, nicht `div`: Damit ist die Zeile per Tab erreichbar, per
            // Finger groß genug (h 28) und per Zeiger dasselbe Ziel.
            <button
              key={f.name} type="button"
              aria-pressed={hervor === i}
              onPointerEnter={(e) => { if (e.pointerType === "mouse") setHervor(i); }}
              onPointerLeave={(e) => { if (e.pointerType === "mouse") setHervor(null); }}
              onFocus={() => setHervor(i)}
              onBlur={() => setHervor(null)}
              onClick={() => setHervor((h) => (h === i ? null : i))}
              className={cn(
                "flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                hervor === i ? "bg-muted" : "hover:bg-muted/60",
              )}
            >
              <span aria-hidden="true" className="h-2.5 w-2.5 flex-none rounded-[2px]"
                style={{ background: farbe(i) }} />
              <span className="min-w-0 flex-1 truncate text-xs">{f.name}</span>
              <span className="font-mono text-xs font-medium tabular-nums">{f.euro}&nbsp;€</span>
            </button>
          ))}
          <p className="pt-1.5 text-[11px] leading-relaxed text-muted-foreground">
            Jedes Feld steht für 1&nbsp;€ von 100; die Anteile sind auf ganze Euro gerundet.
            Wähle einen Bereich in der Liste oder im Raster, um seine Felder hervorzuheben.
            Die genauen Beträge stehen in der Balkenansicht.
          </p>
        </div>
      </div>

      {eingenommen < 100 && (
        <p className="mt-3.5 border-t border-border/60 pt-3 text-xs leading-relaxed text-foreground/85">
          <strong>So ist die Darstellung zu lesen:</strong> Die 100 Euro stehen für alle
          geplanten Aufwendungen, nicht für Steuereinnahmen. Davon sind rechnerisch
          {" "}{eingenommen}&nbsp;Euro durch geplante Erträge gedeckt; {100 - eingenommen}&nbsp;Euro
          entsprechen dem geplanten Minus von {deMio(fehltMio)}&#8239;Mio.&nbsp;€.
        </p>
      )}
    </div>
  );
}
