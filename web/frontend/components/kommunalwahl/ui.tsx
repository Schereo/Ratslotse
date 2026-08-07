// Gemeinsame Bausteine des Kommunalwahl-Bereichs — bewusst OHNE "use client":
// alles hier rendert serverseitig, nur die interaktiven Teile (Matrix-Sheet,
// Nähe-Detail) liegen in eigenen Client-Dateien.
//
// Design-Referenz: Claude-Design-Projekt „Kommunalwahl – Überblick", Runde 2a/3a–3d.

import Link from "next/link";
import { BrandMark } from "@/components/brand";
import { cn } from "@/lib/utils";
import type { Pos } from "@/lib/kommunalwahl-types";

/* ── Ampel (Bauplan E6): eigene semantische Skala, Glyphe IMMER zur Farbe ── */

export const AMPEL: Record<
  "1" | "0" | "-1" | "null",
  { bg: string; fg: string; glyph: string; label: string }
> = {
  "1": { bg: "#2E7D5B", fg: "#fff", glyph: "✓", label: "dafür" },
  "0": { bg: "#C1861B", fg: "#fff", glyph: "~", label: "teils / mit Bedingungen" },
  "-1": { bg: "#B04434", fg: "#fff", glyph: "✕", label: "dagegen" },
  null: { bg: "hsla(212,40%,20%,0.12)", fg: "hsl(209 18% 42%)", glyph: "–", label: "keine Aussage im Programm" },
};

export function ampel(pos: Pos) {
  return AMPEL[String(pos) as keyof typeof AMPEL];
}

/** Eine Position als Ampelkreis mit Glyphe — lesbar ohne Farbwahrnehmung. */
export function Glyph({ pos, size = 22, className }: { pos: Pos; size?: number; className?: string }) {
  const a = ampel(pos);
  return (
    <span
      role="img"
      aria-label={a.label}
      className={cn("inline-flex flex-none items-center justify-center rounded-full font-extrabold", className)}
      style={{ width: size, height: size, background: a.bg, color: a.fg, fontSize: size * 0.52 }}
    >
      {a.glyph}
    </span>
  );
}

/** Legende unter jeder Matrix — inklusive des Satzes zur Farbunabhängigkeit. */
export function AmpelLegende() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border bg-background/60 px-5 py-3 text-[11.5px] text-muted-foreground">
      {(["1", "0", "-1", "null"] as const).map((k) => (
        <span key={k} className="inline-flex items-center gap-1.5">
          <Glyph pos={k === "null" ? null : (Number(k) as Pos)} size={16} />
          {AMPEL[k].label}
        </span>
      ))}
      <span className="ml-auto hidden sm:inline">Glyphen zusätzlich zur Farbe — lesbar ohne Farbwahrnehmung</span>
    </div>
  );
}

/* ── Parteifarben als Datenmarken (E5) ────────────────────────────────────── */

export function FarbPunkt({
  farbe,
  farbeDunkel,
  size = 10,
  className,
}: {
  farbe: string;
  farbeDunkel?: string;
  size?: number;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cn("kw-farbe inline-block flex-none rounded-full", className)}
      style={{ width: size, height: size, "--kw-f": farbe, "--kw-fd": farbeDunkel } as React.CSSProperties}
    />
  );
}

/** BSW-Markierung (E1): hängt an JEDER BSW-Instanz, nicht nur an der Karte. */
export function BswPill({ kompakt = false }: { kompakt?: boolean }) {
  return (
    <span className="inline-flex flex-none items-center rounded-full bg-amber-500/15 px-2 py-0.5 text-[10.5px] font-semibold text-amber-800 dark:text-amber-300">
      {kompakt ? "Landesprogramm" : "Landesprogramm — ohne Oldenburg-Bezug"}
    </span>
  );
}

/* ── KI-Kennzeichnung (Pflicht, drei Stellen — Handoff) ───────────────────── */

export function KiPlakette({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex flex-none items-center justify-center rounded-md bg-foreground text-[9px] font-extrabold tracking-wider text-background",
        className,
      )}
      style={{ width: 24, height: 16 }}
    >
      KI
    </span>
  );
}

export function KiKasten({ kompakt = false }: { kompakt?: boolean }) {
  return (
    <div className="flex items-start gap-3.5 rounded-2xl border border-amber-600/35 bg-amber-500/[0.07] p-4 sm:p-5">
      <KiPlakette className="mt-0.5 !h-6 !w-9 text-[12px]" />
      <div className="min-w-0">
        <p className="font-display text-[15px] font-bold sm:text-[16.5px]">
          Von einer KI ausgewertet — nicht von einer Redaktion.
        </p>
        <p className="mt-1.5 max-w-[88ch] text-[13px] leading-relaxed text-muted-foreground sm:text-[13.5px]">
          Ratslotse hat die Programme mit KI gelesen, zusammengefasst und den 44 Thesen zugeordnet.
          Niemand hat jede Einordnung von Hand kuratiert — und KI macht Fehler, auch hier. Deshalb
          steht hinter jeder Aussage ein Belegzitat mit Fundstelle, und jeder Klick führt an die
          Stelle im Original der Partei. Prüf nach, bevor du dich festlegst.
        </p>
        {!kompakt && (
          <div className="mt-2.5 flex flex-wrap gap-2">
            <span className="rounded-full border border-border bg-card px-2.5 py-0.5 text-xs font-semibold">
              Jede Aussage belegt
            </span>
            <span className="rounded-full border border-border bg-card px-2.5 py-0.5 text-xs font-semibold">
              Links ins Original
            </span>
            <Link
              href="/impressum"
              className="rounded-full border border-primary/30 bg-card px-2.5 py-0.5 text-xs font-semibold text-primary"
            >
              Fehler gefunden? Melden →
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Prägnanz: drei Punkte in Hafenblau, ungenutzte gedimmt ───────────────── */

export function PraegnanzDots({ n, size = 7 }: { n: number; size?: number }) {
  return (
    <span className="inline-flex flex-none gap-[3px]" aria-label={`Prägnanz ${n} von 3`} role="img">
      {[1, 2, 3].map((i) => (
        <span
          key={i}
          className="rounded-full bg-primary"
          style={{ width: size, height: size, opacity: i <= n ? 1 : 0.18 }}
        />
      ))}
    </span>
  );
}

/* ── Ähnlichkeits-Skala (nur /naehe u. Paar-Anzeigen) ─────────────────────── */

export function skalaStil(wert: number | null): { className: string } {
  if (wert === null)
    return { className: "bg-muted text-muted-foreground" };
  if (wert >= 70)
    return { className: "bg-emerald-700/15 text-emerald-900 dark:bg-emerald-400/15 dark:text-emerald-300" };
  if (wert >= 40)
    return { className: "bg-amber-600/15 text-amber-900 dark:bg-amber-400/15 dark:text-amber-300" };
  return { className: "bg-red-700/10 text-red-900 dark:bg-red-400/15 dark:text-red-300" };
}

/* ── Kopf- und Fußzeile des Bereichs ──────────────────────────────────────── */

export function KwKopf({ crumb }: { crumb: React.ReactNode }) {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-card/95 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-3 px-4 pb-3 pt-[calc(env(safe-area-inset-top)+0.75rem)] sm:px-6 lg:px-10">
        <div className="flex min-w-0 items-center gap-2.5">
          <Link
            href="/kommunalwahl"
            className="flex flex-none items-center gap-2.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <BrandMark className="h-[30px] w-[30px]" />
            <span className="font-display text-[17px] font-bold tracking-tight text-foreground">Ratslotse</span>
          </Link>
          <span className="truncate border-l border-border pl-2.5 text-[13px] text-muted-foreground">{crumb}</span>
        </div>
        <div className="flex flex-none items-center gap-4">
          <Link href="/" className="hidden text-[13px] font-medium text-primary sm:inline">
            ← Zurück zu Ratslotse
          </Link>
          <Link
            href="/register"
            className="inline-flex rounded-[11px] bg-primary px-3.5 py-1.5 text-[13px] font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Kostenlos registrieren
          </Link>
        </div>
      </div>
    </header>
  );
}

export function KwCrumb({ teil }: { teil?: string }) {
  return (
    <>
      <Link href="/kommunalwahl" className="font-medium text-primary">
        Kommunalwahl
      </Link>
      {teil ? <> / {teil}</> : " 2026"}
    </>
  );
}

export function KwFuss({
  stand,
  links,
}: {
  stand: string;
  links?: { href: string; label: string }[];
}) {
  return (
    <div className="mt-7 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border pt-3.5">
      <p className="text-[12.5px] text-muted-foreground">
        Stand: {stand} · <strong className="font-semibold text-foreground">Programme, nicht Politik im Rat</strong> ·
        KI-ausgewertet, Fehler möglich — jede Aussage belegt
      </p>
      <span className="ml-auto flex flex-wrap gap-4">
        {(links ?? [{ href: "/kommunalwahl/methodik", label: "Methodik & Quellen" }]).map((l) => (
          <Link key={l.href + l.label} href={l.href} className="text-[12.5px] font-medium text-primary">
            {l.label}
          </Link>
        ))}
      </span>
    </div>
  );
}

/* ── Abschnitts-Überschrift mit Nebensatz ─────────────────────────────────── */

export function Abschnitt({
  titel,
  neben,
  className,
}: {
  titel: string;
  neben?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-baseline gap-x-3 gap-y-1", className)}>
      <h2 className="font-display text-[21px] font-bold tracking-tight sm:text-2xl">{titel}</h2>
      {neben && <span className="text-[12.5px] text-muted-foreground">{neben}</span>}
    </div>
  );
}
