"use client";

// Werkbank 2 des Haushalts-Labors: Ausgaben.
//
// SEIT 24.08.2026 IN BEIDE RICHTUNGEN (Tims Befund: „ein bisschen random,
// dass man viele Regler nicht in die andere Richtung schieben kann"): Ein
// freiwilliger Teilhaushalt lässt sich kürzen UND aufstocken — dieselbe
// Symmetrie wie an den Hebesatz-Reglern, „heute“ steht in der Mitte. Wer
// mehr für Kultur will, sieht den Preis im Minus, statt dass die Richtung
// stillschweigend verboten ist. Die Mechanik bleibt sonst unverändert: nur
// ganze Teilhaushalte, nur prozentual.
//
// Die Produktzahlen daneben („Darin stecken u. a. …“) sind ein VERGLEICH,
// keine Rechengrundlage: Sie stammen aus dem jüngsten auslesbaren
// Teilhaushaltsplan, die Simulation rechnet mit dem aktuellen Planjahr —
// beides zu vermischen wäre eine Zahl, die es nirgends gibt.

import { deMio, naechstesProdukt, type Produkt } from "@/lib/haushalt";
import { Beleg } from "@/components/haushalt/quelle";
import { Regler } from "@/components/haushalt/regler";

export function AusgabenWerkbank({
  freiwillig, produkte, produktJahr, basisJahr,
  aenderung, setAenderung, maxProzent, jeEinwohner, anteilText,
}: {
  freiwillig: { area: string; aus: number }[];
  produkte: Produkt[];
  produktJahr: number | null;
  basisJahr: number;
  /** Prozentuale Änderung je Bereich — negativ = kürzen, positiv = aufstocken. */
  aenderung: Record<string, number>;
  setAenderung: (area: string, pct: number) => void;
  maxProzent: number;
  jeEinwohner: (m: number) => string;
  anteilText: (m: number) => string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Freiwillige Leistungen — kürzen oder aufstocken
      </p>
      <div className="mt-3 flex flex-col gap-4">
        {freiwillig.map((f) => {
          const pct = aenderung[f.area] ?? 0;
          /** Positive Beträge = eingespart, negative = zusätzlich ausgegeben. */
          const amount = -Math.round(f.aus * pct) / 100;
          const drin = produkte
            .filter((p) => p.sub_budget_name === f.area && p.result != null && p.result < 0)
            .slice(0, 3);
          const vergleich = naechstesProdukt(produkte, Math.abs(amount), f.area);
          return (
            <Regler
              key={f.area}
              id={f.area}
              label={f.area}
              wert={pct} min={-maxProzent} max={maxProzent} step={5}
              onChange={(v) => setAenderung(f.area, v)}
              geaendert={pct !== 0}
              ist={{ wert: 0, label: "heute" }}
              marken={{ min: `−${maxProzent} %`, max: `+${maxProzent} %` }}
              anzeige={
                pct === 0
                  ? <span className="text-muted-foreground">{deMio(f.aus)}&nbsp;Mio.&nbsp;€</span>
                  : <>
                      <span className="text-muted-foreground line-through">{deMio(f.aus)}</span>
                      <strong className="ml-2 text-signal">
                        {deMio(f.aus * (1 + pct / 100))} ({pct > 0 ? "+" : "−"}{Math.abs(pct)}&nbsp;%)
                      </strong>
                    </>
              }
              wirkung={
                pct === 0 ? (
                  drin.length > 0 ? (
                    <>Darin stecken u.&nbsp;a.{" "}
                    {drin.map((p, i) => (
                      <span key={p.product_no}>
                        {i > 0 && ", "}
                        {p.product_name} ({deMio(-(p.result as number) / 1e6)}&#8239;Mio.&nbsp;€)
                      </span>
                    ))}.</>
                  ) : (
                    <>{deMio(f.aus)}&#8239;Mio.&nbsp;€ Aufwand im Plan {basisJahr}.</>
                  )
                ) : pct < 0 ? (
                  <>
                    <strong>{deMio(amount)}&#8239;Mio.&nbsp;€ weniger</strong> ·{" "}
                    {jeEinwohner(amount)} · {anteilText(amount)}.
                    {vergleich && (
                      <> Ungefähr so viel, wie <strong>{vergleich.product_name}</strong> im
                      ganzen Jahr kostet.</>
                    )}
                  </>
                ) : (
                  <>
                    <strong>{deMio(-amount)}&#8239;Mio.&nbsp;€ mehr</strong> für {f.area} ·{" "}
                    {jeEinwohner(-amount)} — vergrößert das Minus um {anteilText(-amount)}.
                    {vergleich && (
                      <> So viel kostet <strong>{vergleich.product_name}</strong> im ganzen Jahr —
                      etwa das käme dazu.</>
                    )}
                  </>
                )
              }
            />
          );
        })}
      </div>
      <p className="mt-4 text-[11.5px] leading-relaxed text-muted-foreground">
        Der Regler verändert ganze Teilhaushalte pauschal. Er legt nicht fest, welche
        Einrichtungen von einer Kürzung betroffen wären oder wofür zusätzliches Geld
        eingesetzt würde. Eine solche Entscheidung müsste der Rat konkret beschließen.
        {produktJahr && (
          <> Die einzelnen Aufgaben daneben stammen aus dem Teilhaushaltsplan {produktJahr}{" "}
          <Beleg q="teilhaushalt" /> — zum Einordnen der Größenordnung, nicht zum Mitrechnen.</>
        )}
      </p>
    </div>
  );
}
