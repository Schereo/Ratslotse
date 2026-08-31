"use client";

// Die Städte-Leiter am Hebesatz-Regler (Labor 2.0, Entwurf „Regler mit
// Städte-Treppe“): Beim Drehen läuft mit, wo Oldenburg damit unter den
// kreisfreien Städten stünde — ein Hebesatz ohne Nachbarn ist nur eine Zahl.
//
// BEWUSST KEINE BEWERTUNGSFARBEN: Ein höherer Hebesatz ist keine schlechte
// Nachricht (dieselbe Regel wie an der Hebesatz-Treppe des Steckbriefs).
// Der eigene Wert trägt Hafenblau, „heute“ die Ist-Marke — sonst nichts.
//
// Die Zeile „Oldenburg · dein Wert“ wird EINSORTIERT statt hervorgehoben
// angehängt: Die Aussage der Leiter ist die Position, nicht der Wert.

import { deZahl } from "@/components/grafik/format";
import type { StadtHebesatz } from "@/lib/haushalt-labor";
import { Beleg } from "@/components/haushalt/quelle";
import { cn } from "@/lib/utils";

type Zeile = {
  name: string;
  wert: number;
  rolle: "stadt" | "heute" | "dein";
};

export function StaedteLeiter({ staedte, heute, deinWert, geaendert }: {
  staedte: StadtHebesatz[];
  /** Der geltende Oldenburger Satz — die Zeile aus dem LSN-Vergleich wird
   *  durch ihn ersetzt, damit Leiter und Regler dieselbe Zahl führen, auch
   *  wenn der Vergleichs-Jahrgang älter ist als die Hebesatz-Reihe. */
  heute: number;
  deinWert: number;
  geaendert: boolean;
}) {
  if (staedte.length < 3) return null;
  const year = staedte[0].year;

  const zeilen: Zeile[] = staedte.map((s) => ({
    name: s.istOldenburg ? "Oldenburg · heute" : s.stadt,
    wert: s.istOldenburg ? heute : s.wert,
    rolle: s.istOldenburg ? "heute" : "stadt",
  }));
  if (geaendert && deinWert !== heute) {
    zeilen.push({ name: "Oldenburg · dein Wert", wert: deinWert, rolle: "dein" });
  }
  zeilen.sort((a, b) => b.wert - a.wert);

  const werte = zeilen.map((z) => z.wert);
  const [min, max] = [Math.min(...werte), Math.max(...werte)];
  const spanne = Math.max(1, max - min);
  const pos = (w: number) => 4 + ((w - min) / spanne) * 92;

  // Wer steht direkt über dem eigenen Wert? Der eine Satz, den jede*r aus
  // der Leiter mitnimmt („zöge mit Osnabrück gleich“).
  const dein = zeilen.findIndex((z) => z.rolle === "dein");
  const gleichauf = dein >= 0
    ? zeilen.find((z, i) => i !== dein && z.rolle === "stadt" && z.wert === zeilen[dein].wert)
    : undefined;

  return (
    <div className="mt-3 rounded-xl bg-muted/40 p-3">
      <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Die kreisfreien Städte · {year}
      </p>
      <div className="mt-1.5 flex flex-col">
        {zeilen.map((z) => (
          <div key={z.name}
            className={cn("flex items-center gap-2.5 py-[3px]",
              z.rolle === "dein" && "-mx-1.5 rounded-lg bg-primary/10 px-1.5")}>
            <span className={cn("w-[124px] shrink-0 truncate text-[11.5px]",
              z.rolle === "dein" ? "font-semibold text-primary"
                : z.rolle === "heute" ? "text-foreground" : "text-foreground/80")}>
              {z.name}
            </span>
            <span className="relative h-2 min-w-0 flex-1 rounded-full bg-muted">
              {z.rolle === "dein" ? (
                <span className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[2.5px] border-primary bg-card"
                  style={{ left: `${pos(z.wert)}%` }} />
              ) : (
                <span className={cn("absolute top-1/2 w-[2px] -translate-x-1/2 -translate-y-1/2 rounded-full",
                  z.rolle === "heute" ? "h-3.5 bg-foreground/35" : "h-3 bg-[var(--hh-aus-2)]")}
                  style={{ left: `${pos(z.wert)}%` }} />
              )}
            </span>
            <span className={cn("w-12 shrink-0 text-right font-mono text-[11px] tabular-nums",
              z.rolle === "dein" ? "font-medium text-primary" : "text-muted-foreground")}>
              {deZahl(z.wert)}&nbsp;%
            </span>
          </div>
        ))}
      </div>
      <p className="mt-1.5 text-[10.5px] leading-relaxed text-muted-foreground">
        {gleichauf && <>Damit zöge Oldenburg mit {gleichauf.name} gleich. </>}
        Hebesätze der acht kreisfreien Städte aus dem Realsteuervergleich des
        Landes<Beleg q="lsn_realsteuern" />; Oldenburgs Zeile führt den Satz der
        eigenen Reihe.
      </p>
    </div>
  );
}
