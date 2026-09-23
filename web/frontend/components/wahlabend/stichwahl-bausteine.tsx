"use client";

// Drei Bausteine der Stichwahl-Seite, die Tim am 23.09.2026 dazu wollte:
// der Ticker der zuletzt gemeldeten Wahlbezirke, der Countdown bis 18 Uhr und
// das Bild zum Teilen. Gerechnet wird nichts davon hier — der Ticker kommt
// fertig vom Backend (`recent_districts`), das Bild ist ein PNG des Backends.

import { useEffect, useRef, useState } from "react";
import { Share2 } from "lucide-react";
import { apiUrl } from "@/lib/api";
import { cn } from "@/lib/utils";
import { prozent, uhrzeit } from "@/lib/wahlabend";
import {
  countdown,
  nachname,
  stichwahlBildPfad,
  type BildFormat,
  type Stichwahl,
  type StichwahlKandidat,
} from "@/lib/stichwahl";

const KICKER = "font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground";

function farbe(k: StichwahlKandidat | undefined): string {
  return k ? `light-dark(${k.color || "#6b7a8c"}, ${k.color_dark || k.color || "#a3b1c2"})` : "hsl(var(--muted-foreground))";
}

/* ── Ticker ───────────────────────────────────────────────────────────── */

const KEINE: Stichwahl["recent_districts"] = [];

/** „Zuletzt gemeldet": die jüngsten Wahlbezirke mit Namen, wer dort vorn
 *  liegt und wie sich das gegen den ersten Wahlgang verschoben hat. Ein Tipp
 *  auf einen Urnenbezirk zeigt ihn auf der Karte. Neue Zeilen gleiten ein —
 *  aber nicht beim ersten Laden. */
export function BezirksTicker({ daten, zeigen }: { daten: Stichwahl; zeigen: (nr: number) => void }) {
  // `?? KEINE` für eine Antwort aus der Zeit vor dem Ticker — eine feste
  // Liste, sonst liefe der Effekt unten bei jedem Rendern.
  const zeilen = daten.recent_districts ?? KEINE;
  const bekannt = useRef<Set<number> | null>(null);
  const neu = bekannt.current === null ? new Set<number>() : new Set(zeilen.filter((z) => !bekannt.current?.has(z.number)).map((z) => z.number));
  useEffect(() => {
    bekannt.current = new Set(zeilen.map((z) => z.number));
  }, [zeilen]);
  if (zeilen.length === 0) return null;
  return (
    <section className="mt-4 rounded-2xl border border-border bg-card p-4 sm:p-5" aria-labelledby="ticker-titel" data-testid="bezirks-ticker">
      <h2 id="ticker-titel" className={KICKER}>Zuletzt gemeldet</h2>
      <ol className="mt-2 divide-y divide-border/70">
        {zeilen.slice(0, 6).map((z) => {
          const vorn = daten.candidates.find((k) => k.slug === z.leader);
          const anteil = z.leader ? z.shares[z.leader] : undefined;
          const vorher = z.leader ? z.first_round_shares[z.leader] : undefined;
          const diff = anteil !== undefined && vorher !== undefined ? Math.round((anteil - vorher) * 10) / 10 : null;
          const inhalt = (
            <>
              <span className="w-11 flex-none font-mono text-[11px] tabular-nums text-muted-foreground">{uhrzeit(z.at) ?? "–"}</span>
              <span className="min-w-0 flex-1 truncate">
                <span className="hidden font-mono text-[11px] text-muted-foreground sm:inline">{z.number} </span>
                <span className="font-medium">{z.postal ? `Briefwahl · ${z.name}` : z.name}</span>
              </span>
              <span className="flex flex-none items-center gap-1.5 tabular-nums">
                <span aria-hidden className="inline-block h-2 w-2 rounded-full" style={{ background: farbe(vorn) }} />
                <span className="font-semibold">{vorn ? nachname(vorn) : "gleichauf"}</span>
                {anteil !== undefined ? <span>{prozent(anteil)}</span> : null}
                {diff !== null ? (
                  <span className="w-9 text-right font-mono text-[11px] text-muted-foreground" title="Verschiebung gegenüber dem ersten Wahlgang in diesem Bezirk">
                    {diff > 0 ? "+" : diff < 0 ? "−" : "±"}
                    {Math.abs(diff).toFixed(1).replace(".", ",")}
                  </span>
                ) : null}
              </span>
            </>
          );
          return (
            <li
              key={z.number}
              className={cn(neu.has(z.number) && "animate-in fade-in-0 slide-in-from-top-1 duration-buehne ease-out-strong")}
            >
              {z.postal ? (
                <div className="flex items-center gap-3 py-2 text-[13px]">{inhalt}</div>
              ) : (
                <button
                  type="button"
                  onClick={() => zeigen(z.number)}
                  className="flex w-full items-center gap-3 rounded-md py-2 text-left text-[13px] transition-colors duration-tipp hover:bg-primary/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={`Wahlbezirk ${z.number} ${z.name} auf der Karte zeigen`}
                >
                  {inhalt}
                </button>
              )}
            </li>
          );
        })}
      </ol>
      <p className="mt-2 text-[11.5px] text-muted-foreground">
        Ganz rechts: wie viele Punkte die Person in diesem Bezirk gegenüber dem ersten Wahlgang gewonnen oder verloren hat.
      </p>
    </section>
  );
}

/* ── Countdown ────────────────────────────────────────────────────────── */

/** Bis 18 Uhr: am Wahltag sekundengenau, davor in Tagen. Läuft er ab, sagt
 *  er es der Seite (`vorbei`) — die fragt dann sofort nach, statt eine
 *  Minute auf ihren Takt zu warten. */
export function Countdown({ pollsClose, vorbei }: { pollsClose: string; vorbei?: () => void }) {
  const [jetzt, setJetzt] = useState(() => new Date());
  const stand = countdown(pollsClose, jetzt);
  const sekundengenau = stand?.sekundengenau ?? false;
  const lief = useRef(stand !== null);
  useEffect(() => {
    const id = window.setInterval(() => setJetzt(new Date()), sekundengenau ? 1000 : 60_000);
    return () => window.clearInterval(id);
  }, [sekundengenau]);
  useEffect(() => {
    if (stand === null && lief.current) {
      lief.current = false;
      vorbei?.();
    }
  }, [stand, vorbei]);
  if (!stand) return null;
  return (
    <div className="mt-3" data-testid="countdown">
      <p className={KICKER}>Die Wahllokale schließen in</p>
      <p
        className="mt-1 font-display text-[36px] font-bold leading-none tabular-nums tracking-tight sm:text-[44px]"
        suppressHydrationWarning
        aria-live="off"
      >
        {stand.text}
      </p>
    </div>
  );
}

/* ── Bild zum Teilen ──────────────────────────────────────────────────── */

const FORMATE: { format: BildFormat; label: string }[] = [
  { format: "beitrag", label: "Beitrag" },
  { format: "story", label: "Story" },
  { format: "quer", label: "quer" },
];

/** Das Bild des Stands teilen. Wo das Gerät Dateien teilen kann (Handy),
 *  geht es direkt in WhatsApp & Co.; sonst öffnet sich das Bild zum
 *  Speichern. */
export function BildTeilen({ daten, probe, counted }: { daten: Stichwahl; probe: string | null; counted: string | null }) {
  const [laeuft, setLaeuft] = useState<BildFormat | null>(null);
  async function teilen(format: BildFormat) {
    const url = apiUrl(stichwahlBildPfad(format, probe, counted));
    try {
      if (typeof navigator !== "undefined" && navigator.canShare) {
        setLaeuft(format);
        const blob = await (await fetch(url)).blob();
        const datei = new File([blob], `stichwahl-oldenburg-${format}.png`, { type: "image/png" });
        if (navigator.canShare({ files: [datei] })) {
          await navigator.share({
            files: [datei],
            text: `Stichwahl in Oldenburg — ${daten.reports_received} von ${daten.reports_expected} Bezirken ausgezählt. Live: https://ratslotse.de/wahlabend/stichwahl`,
          });
          return;
        }
      }
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      // Abgebrochen („AbortError") ist kein Fehler; alles andere: das Bild öffnen.
      if (!(e instanceof DOMException && e.name === "AbortError")) window.open(url, "_blank", "noopener,noreferrer");
    } finally {
      setLaeuft(null);
    }
  }
  if (daten.phase === "before") return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2" data-testid="bild-teilen">
      <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-muted-foreground">
        <Share2 className="h-3.5 w-3.5" aria-hidden /> Stand als Bild teilen:
      </span>
      {FORMATE.map((f) => (
        <button
          key={f.format}
          type="button"
          onClick={() => void teilen(f.format)}
          disabled={laeuft !== null}
          className="inline-flex min-h-8 items-center rounded-full border border-border bg-card px-3 text-[12.5px] font-medium text-foreground transition-colors duration-tipp hover:bg-primary/5 disabled:opacity-60"
        >
          {laeuft === f.format ? "…" : f.label}
        </button>
      ))}
    </div>
  );
}
