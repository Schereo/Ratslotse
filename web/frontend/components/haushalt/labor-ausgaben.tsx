"use client";

// Werkbank 2 des Haushalts-Labors: Ausgaben. Der Block „Freiwillige
// Leistungen kürzen“ — unverändert in der Mechanik (nur ganze Teilhaushalte,
// nur prozentual), seit dem Werkbank-Umbau (Labor 2.0) eine eigene Datei.
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
  kuerzung, setKuerzung, maxKuerzung, jeEinwohner, anteilText,
}: {
  freiwillig: { bereich: string; aus: number }[];
  produkte: Produkt[];
  produktJahr: number | null;
  basisJahr: number;
  kuerzung: Record<string, number>;
  setKuerzung: (bereich: string, pct: number) => void;
  maxKuerzung: number;
  jeEinwohner: (m: number) => string;
  anteilText: (m: number) => string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Freiwillige Leistungen kürzen
      </p>
      <div className="mt-3 flex flex-col gap-4">
        {freiwillig.map((f) => {
          const pct = kuerzung[f.bereich] ?? 0;
          const betrag = Math.round(f.aus * pct) / 100;
          const drin = produkte
            .filter((p) => p.thh_name === f.bereich && p.ergebnis != null && p.ergebnis < 0)
            .slice(0, 3);
          const vergleich = naechstesProdukt(produkte, betrag, f.bereich);
          return (
            <Regler
              key={f.bereich}
              id={f.bereich}
              label={f.bereich}
              wert={pct} min={0} max={maxKuerzung} step={5}
              onChange={(v) => setKuerzung(f.bereich, v)}
              geaendert={pct > 0}
              ist={{ wert: 0, label: "heute" }}
              marken={{ min: "", max: `−${maxKuerzung} %` }}
              anzeige={
                pct === 0
                  ? <span className="text-muted-foreground">{deMio(f.aus)}&nbsp;Mio.&nbsp;€</span>
                  : <>
                      <span className="text-muted-foreground line-through">{deMio(f.aus)}</span>
                      <strong className="ml-2 text-signal">
                        {deMio(f.aus - betrag)} (−{pct}&nbsp;%)
                      </strong>
                    </>
              }
              wirkung={
                pct === 0 ? (
                  drin.length > 0 ? (
                    <>Darin stecken u.&nbsp;a.{" "}
                    {drin.map((p, i) => (
                      <span key={p.produkt_nr}>
                        {i > 0 && ", "}
                        {p.produkt_name} ({deMio(-(p.ergebnis as number) / 1e6)}&#8239;Mio.&nbsp;€)
                      </span>
                    ))}.</>
                  ) : (
                    <>{deMio(f.aus)}&#8239;Mio.&nbsp;€ Aufwand im Plan {basisJahr}.</>
                  )
                ) : (
                  <>
                    <strong>{deMio(betrag)}&#8239;Mio.&nbsp;€ weniger</strong> ·{" "}
                    {jeEinwohner(betrag)} · {anteilText(betrag)}.
                    {vergleich && (
                      <> Ungefähr so viel, wie <strong>{vergleich.produkt_name}</strong> im
                      ganzen Jahr kostet.</>
                    )}
                  </>
                )
              }
            />
          );
        })}
      </div>
      <p className="mt-4 text-[11.5px] leading-relaxed text-muted-foreground">
        Nur ganze Teilhaushalte, nur prozentual: Welche Einrichtung es träfe, entscheidet kein
        Regler — und ein Beschluss wäre das ohnehin nicht.
        {produktJahr && (
          <> Die einzelnen Aufgaben daneben stammen aus dem Teilhaushaltsplan {produktJahr}{" "}
          <Beleg q="teilhaushalt" /> — zum Einordnen der Größenordnung, nicht zum Mitrechnen.</>
        )}
      </p>
    </div>
  );
}
