"use client";

/**
 * Die Zeitleiste einer Bewegung: je Vorlage ein Punkt auf EINER Achse.
 *
 * Die Achse kommt vom Server (`axis`), damit jede Karte und jede Zeile der
 * Ideen-Seite dieselbe zeichnet — die Rechnung steht in `lib/zeitleiste.ts`.
 *
 * Farben aus den Semantik-Tints der Designsprache (§ 2), nie als Fläche: Ein
 * Punkt trägt die Farbe, die Leiste bleibt eine Linie. „Ohne Ergebnis" ist
 * ein hohler Ring — nicht grau gefüllt, sonst läse er sich wie „zur Kenntnis".
 */
import { cn } from "@/lib/utils";
import {
  type Achse,
  type Punkt,
  type Stufe,
  STUFE_TEXT,
  STUFEN_REIHE,
  anteil,
  jahresmarken,
  satz,
  spuren,
  stufe,
} from "@/lib/zeitleiste";

const PUNKT: Record<Stufe, string> = {
  ok: "bg-green-600 dark:bg-green-400",
  no: "bg-red-600 dark:bg-red-400",
  wait: "bg-amber-500 dark:bg-amber-400",
  noted: "bg-[hsl(209_18%_48%)] dark:bg-[hsl(206_20%_68%)]",
  open: "bg-card ring-[1.5px] ring-muted-foreground",
};

const ART: Record<string, string> = {
  motion: "Antrag", amendment: "Änderungsantrag", inquiry: "Anfrage",
  proposal: "Beschlussvorlage",
};

function datum(iso: string | null): string {
  if (!iso) return "ohne Datum";
  const [j, m, t] = iso.slice(0, 10).split("-");
  return t ? `${t}.${m}.${j}` : iso;
}

/** Die Leiste. `jahre` zeichnet die gestrichelten Jahreslinien. */
export function Zeitleiste({
  achse,
  punkte,
  jahre = true,
  className,
  label,
}: {
  achse: Achse;
  punkte: Punkt[];
  jahre?: boolean;
  className?: string;
  /** Überschreibt den vorgelesenen Satz (etwa „Osnabrück: …" je Zeile). */
  label?: string;
}) {
  const datiert = punkte
    .map((p) => ({ p, a: anteil(p.date, achse) }))
    .filter((x): x is { p: Punkt; a: number } => x.a !== null)
    .sort((x, y) => x.a - y.a);
  const spur = spuren(datiert.map((x) => x.a));
  return (
    <div
      role="img"
      aria-label={label ?? satz(punkte)}
      className={cn("relative h-9", className)}
    >
      {/* An die gedämpfte TEXTfarbe gebunden, nicht an `border`: Auf der
          Anzeigetafel im Dunkelmodus liegt der Rahmenton einen Punkt neben
          der Kartenfarbe, und die Linie verschwand (Bild vom 22.09.2026). */}
      <div className="absolute inset-x-0 top-1/2 h-px bg-muted-foreground/35" aria-hidden />
      {jahre &&
        jahresmarken(achse).map((m) => (
          <div
            key={m.jahr}
            aria-hidden
            className="absolute inset-y-0.5 border-l border-dashed border-muted-foreground/25"
            style={{ left: `${m.anteil * 100}%` }}
          />
        ))}
      {datiert.map(({ p }, i) => (
        <span
          key={p.paper_id}
          title={`${p.city} · ${datum(p.date)} · ${ART[p.kind] ?? "Vorlage"} · ${STUFE_TEXT[stufe(p.outcome)]}`}
          aria-hidden
          className={cn(
            "absolute top-1/2 h-[11px] w-[11px] -translate-x-1/2 -translate-y-1/2 rounded-full",
            "shadow-[0_0_0_2px_hsl(var(--card))]",
            PUNKT[stufe(p.outcome)],
          )}
          style={{ left: `${datiert[i].a * 100}%`, marginTop: `${spur[i] * 8}px` }}
        />
      ))}
    </div>
  );
}

/** Die Jahreszahlen unter einer oder mehreren Leisten. */
export function Jahresskala({ achse, className }: { achse: Achse; className?: string }) {
  const marken = jahresmarken(achse);
  if (marken.length === 0) return null;
  // Das letzte Jahr ist das Ende der Achse (01.01. des Folgejahres) — als
  // Zahl stünde es für ein Jahr, in dem nichts liegt.
  const gezeigt = marken.slice(0, -1);
  return (
    <div aria-hidden className={cn("relative h-4", className)}>
      {gezeigt.map((m) => (
        <span
          key={m.jahr}
          className="absolute font-mono text-[11.5px] leading-none text-muted-foreground"
          style={{ left: `${m.anteil * 100}%` }}
        >
          {m.jahr}
        </span>
      ))}
    </div>
  );
}

/** Die Legende — einmal je Fläche, nicht unter jeder Karte. */
export function ZeitleisteLegende({ className }: { className?: string }) {
  return (
    <ul className={cn("flex flex-wrap gap-x-4 gap-y-1 text-meta text-muted-foreground", className)}>
      {STUFEN_REIHE.map((s) => (
        <li key={s} className="inline-flex items-center gap-1.5">
          <span aria-hidden className={cn("inline-block h-[9px] w-[9px] rounded-full", PUNKT[s])} />
          {STUFE_TEXT[s]}
        </li>
      ))}
    </ul>
  );
}
