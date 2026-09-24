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
import { useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";
import {
  type Achse,
  type Punkt,
  type Stufe,
  ART_TEXT,
  STUFE_TEXT,
  STUFEN_REIHE,
  anteil,
  datumText,
  jahresmarken,
  naechster,
  satz,
  spuren,
  stufe,
} from "@/lib/zeitleiste";

export const PUNKT: Record<Stufe, string> = {
  ok: "bg-green-600 dark:bg-green-400",
  no: "bg-red-600 dark:bg-red-400",
  wait: "bg-amber-500 dark:bg-amber-400",
  noted: "bg-[hsl(209_18%_48%)] dark:bg-[hsl(206_20%_68%)]",
  open: "bg-card ring-[1.5px] ring-muted-foreground",
};

/** Die Leiste. `jahre` zeichnet die gestrichelten Jahreslinien.
 *
 *  `aktiv` ist die Vorlage, die gerade abgelesen wird: Sie bekommt einen
 *  Ring. `fuehrung` ist die Stelle der Führungslinie als Anteil der Breite —
 *  auf der Ideen-Seite zeichnet jede Zeile ihr Stück an derselben Stelle,
 *  und weil die Zeilen ohne Abstand stehen, liest es sich als EIN Strich
 *  durch alle Städte.
 *
 *  Anders als im Haushalt gibt es keinen blassen, gestrichelten Strich im
 *  Ruhezustand: Hier sind die Jahreslinien gestrichelt, und ein ruhender
 *  Strich sah aus wie eine weitere davon (Bild vom 23.09.2026). */
export function Zeitleiste({
  achse,
  punkte,
  jahre = true,
  className,
  label,
  aktiv = null,
  fuehrung = null,
}: {
  achse: Achse;
  punkte: Punkt[];
  jahre?: boolean;
  className?: string;
  /** Überschreibt den vorgelesenen Satz (etwa „Osnabrück: …" je Zeile). */
  label?: string;
  aktiv?: string | null;
  fuehrung?: number | null;
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
      {fuehrung !== null && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 w-0 border-l border-foreground/45 transition-[left] duration-150 ease-out motion-reduce:transition-none"
          style={{ left: `${fuehrung * 100}%` }}
        />
      )}
      {/* Kein `title` mehr: Der Browser zeigte ihn erst nach gut einer
          Sekunde, und nur der Maus. Was ein Punkt ist, steht jetzt sofort in
          der Ablese-Zeile darunter (`ZeitleistenFlaeche`). */}
      {datiert.map(({ p }, i) => (
        <span
          key={p.paper_id}
          data-punkt={p.paper_id}
          aria-hidden
          className={cn(
            "absolute top-1/2 h-[11px] w-[11px] -translate-x-1/2 -translate-y-1/2 rounded-full",
            "transition-transform duration-150 ease-out motion-reduce:transition-none",
            p.paper_id === aktiv
              ? "z-10 scale-[1.35] shadow-[0_0_0_2px_hsl(var(--card)),0_0_0_3.5px_hsl(var(--foreground))]"
              : "shadow-[0_0_0_2px_hsl(var(--card))]",
            PUNKT[stufe(p.outcome)],
          )}
          style={{ left: `${datiert[i].a * 100}%`, marginTop: `${spur[i] * 8}px` }}
        />
      ))}
    </div>
  );
}

// ------------------------------------------------------------ Ablesen

/** Die Fläche, die den Zeiger fängt — um EINE Leiste (Karte) oder um alle
 *  Zeilen der Ideen-Seite.
 *
 *  Gesucht wird der nächste Punkt in Bildschirm-Pixeln, gemessen an den
 *  Punkten selbst (`data-punkt`): So stimmt die Zuordnung auch mit Spuren,
 *  mehreren Zeilen und einer Namensspalte links, ohne dass die Fläche die
 *  Geometrie der Leisten kennen muss.
 *
 *  Dieselbe Grammatik wie der Ablese-Baustein der Grafiken
 *  (`components/grafik/ablesen.tsx`): Die Maus wählt beim Überfahren und
 *  setzt beim Verlassen zurück — NUR die Maus, auf dem Telefon feuert
 *  `pointerleave` nach jedem Tippen. `beruehren` schaltet Tippen und Wischen
 *  ein; auf einer Karte bleibt es aus, dort heißt Tippen „öffnen".
 *  `reihe` schaltet die Pfeiltasten ein und ist ihre Reihenfolge. */
export function ZeitleistenFlaeche({
  children,
  aktiv,
  onWahl,
  beruehren = false,
  reihe,
  label,
  className,
}: {
  children: ReactNode;
  aktiv: string | null;
  onWahl: (paperId: string | null, perTaste?: boolean) => void;
  beruehren?: boolean;
  reihe?: string[];
  label?: string;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const zieht = useRef(false);

  const waehleBei = (x: number, y: number) => {
    const el = ref.current;
    if (!el) return;
    const punkte = Array.from(el.querySelectorAll<HTMLElement>("[data-punkt]"));
    const mitten = punkte.map((p) => {
      const r = p.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    });
    const i = naechster(mitten, x, y);
    if (i >= 0) {
      const id = punkte[i].dataset.punkt ?? null;
      if (id !== aktiv) onWahl(id);
    }
  };

  const tasten = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (!reihe || reihe.length === 0) return;
    const jetzt = aktiv ? reihe.indexOf(aktiv) : -1;
    const springe = (i: number) => {
      e.preventDefault();
      onWahl(reihe[Math.min(Math.max(i, 0), reihe.length - 1)], true);
    };
    if (e.key === "ArrowRight" || e.key === "ArrowDown") springe(jetzt < 0 ? 0 : jetzt + 1);
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") springe(jetzt < 0 ? reihe.length - 1 : jetzt - 1);
    else if (e.key === "Home") springe(0);
    else if (e.key === "End") springe(reihe.length - 1);
    else if (e.key === "Escape") { e.preventDefault(); onWahl(null, true); }
  };

  return (
    <div
      ref={ref}
      role={reihe ? "group" : undefined}
      aria-label={reihe ? label : undefined}
      tabIndex={reihe ? 0 : undefined}
      onKeyDown={reihe ? tasten : undefined}
      className={cn(
        reihe && "rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        className,
      )}
      style={beruehren ? { touchAction: "pan-y" } : undefined}
      onPointerDown={(e) => {
        if (e.pointerType === "mouse" || !beruehren) return;
        zieht.current = true;
        e.currentTarget.setPointerCapture?.(e.pointerId);
        waehleBei(e.clientX, e.clientY);
      }}
      onPointerMove={(e) => {
        if (e.pointerType === "mouse" || zieht.current) waehleBei(e.clientX, e.clientY);
      }}
      onPointerUp={(e) => {
        zieht.current = false;
        e.currentTarget.releasePointerCapture?.(e.pointerId);
      }}
      onPointerCancel={() => { zieht.current = false; }}
      onPointerLeave={(e) => {
        if (e.pointerType === "mouse") onWahl(null);
      }}
    >
      {children}
    </div>
  );
}

/** Was an einem Punkt steht, in zwei Zeilen: wer, wann, wie es ausging —
 *  und worum es ging. */
export function PunktAblesung({
  punkt,
  titel,
  className,
}: {
  punkt: Punkt;
  /** Ein längerer Titel als der der Leiste (die Ideen-Seite kennt ihn). */
  titel?: string;
  className?: string;
}) {
  const s = stufe(punkt.outcome);
  const name = titel || punkt.title || ART_TEXT[punkt.kind] || "Vorlage";
  return (
    <div className={cn("min-w-0", className)}>
      <p className="flex min-w-0 items-center gap-1.5 text-meta leading-snug">
        <span aria-hidden className={cn("inline-block h-[9px] w-[9px] shrink-0 rounded-full", PUNKT[s])} />
        <span className="truncate">
          <b className="font-semibold text-foreground">{punkt.city}</b>
          <span className="text-muted-foreground">
            {" · "}{datumText(punkt.date)}{" · "}{STUFE_TEXT[s]}
          </span>
        </span>
      </p>
      <p className="truncate text-meta leading-snug text-foreground/90">{name}</p>
    </div>
  );
}

/** Die Zeitleiste einer Karte, zum Überfahren.
 *
 *  Im Ruhezustand: Leiste, Jahreszahlen, darunter `ruhe` (die Bilanz der
 *  Karte). Über einem Punkt tauschen Jahreszahlen und Bilanz den Platz mit
 *  der Ablesung — beide liegen im selben Rasterfeld übereinander, die Karte
 *  wird also nicht höher, und das Raster der Übersicht springt nicht.
 *
 *  Nur für die Maus: Die ganze Karte ist ein Link, ein Tippen öffnet sie. */
export function KartenZeitleiste({
  achse,
  punkte,
  ruhe,
}: {
  achse: Achse;
  punkte: Punkt[];
  ruhe: ReactNode;
}) {
  const [aktiv, setAktiv] = useState<string | null>(null);
  const punkt = aktiv ? punkte.find((p) => p.paper_id === aktiv) ?? null : null;
  const a = punkt ? anteil(punkt.date, achse) : null;
  return (
    <div className="grid gap-1">
      <ZeitleistenFlaeche aktiv={aktiv} onWahl={(id) => setAktiv(id)} className="-my-1 py-1">
        <Zeitleiste achse={achse} punkte={punkte} aktiv={aktiv} fuehrung={a} />
      </ZeitleistenFlaeche>
      <div className="grid [grid-template-areas:'x'] *:[grid-area:x]">
        <div className={cn("grid gap-2", punkt && "invisible")}>
          <Jahresskala achse={achse} className="-mt-1.5" />
          {ruhe}
        </div>
        {punkt && <PunktAblesung punkt={punkt} className="self-start" />}
      </div>
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
