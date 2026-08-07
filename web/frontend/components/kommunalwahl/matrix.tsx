"use client";

// Die Positionsmatrix (Überblick „Streit & Einigkeit" und Themenseiten) samt
// Beleg-Sheet. Bekommt fertig geschnittene Zeilen als Props — nie den ganzen
// Datenbestand (Bauplan §5.2).
//
// Breit: Raster These × 9 Listen, Zelle antippen → Dialog mit allen Belegen.
// Schmal: Listenform — These-Karte mit Chip-Reihe (Design 2a/3a Mobil).

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui";
import type { MatrixZeile } from "@/lib/kommunalwahl-types";
import { AmpelLegende, BswPill, FarbPunkt, Glyph, ampel } from "./ui";

function BelegSheet({ zeile, onClose }: { zeile: MatrixZeile | null; onClose: () => void }) {
  return (
    <Dialog open={zeile !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-[640px] gap-0 p-0">
        {zeile && (
          <>
            <DialogHeader className="border-b border-border p-5">
              <p className="text-[11px] font-bold uppercase tracking-wider text-primary">
                {zeile.id} · {zeile.themaLabel} · Belege
              </p>
              <DialogTitle className="text-left font-sans text-[14.5px] font-semibold leading-snug">
                {zeile.these}
              </DialogTitle>
              {zeile.hinweis && (
                <p className="text-left text-xs leading-relaxed text-muted-foreground">{zeile.hinweis}</p>
              )}
            </DialogHeader>
            <div className="flex flex-col gap-3 p-5">
              {zeile.belege.map((b) => (
                <div key={b.slug} className="flex items-start gap-2.5">
                  <Glyph pos={b.pos} size={17} className="mt-0.5" />
                  <p className="min-w-0 text-[12.5px] leading-relaxed text-muted-foreground">
                    <strong className="font-semibold text-foreground">{b.kurz}</strong>
                    {b.landesprogramm && (
                      <>
                        {" "}
                        <BswPill kompakt />
                      </>
                    )}{" "}
                    ·{" "}
                    {b.href ? (
                      <a href={b.href} target="_blank" rel="noopener noreferrer" className="text-primary">
                        {b.seitenLabel} ↗
                      </a>
                    ) : (
                      b.seitenLabel
                    )}{" "}
                    — »{b.beleg}«
                  </p>
                </div>
              ))}
              {zeile.belege.length < zeile.zellen.length && (
                <p className="text-xs text-muted-foreground">
                  Die übrigen {zeile.zellen.length - zeile.belege.length} Listen äußern sich im Programm nicht dazu.
                </p>
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function PositionsMatrix({
  zeilen,
  mitLage = false,
  mitHinweis = false,
}: {
  zeilen: MatrixZeile[];
  /** Überblick: rechte Spalte „strittig/einig". */
  mitLage?: boolean;
  /** Themenseite: `hinweis` als Subzeile unter der These. */
  mitHinweis?: boolean;
}) {
  const [offen, setOffen] = useState<MatrixZeile | null>(null);
  const listen = zeilen[0]?.zellen ?? [];
  const spalten = mitLage
    ? `minmax(0,1fr) repeat(${listen.length}, 42px) 56px`
    : `minmax(0,1fr) repeat(${listen.length}, 46px)`;

  return (
    <>
      {/* Breit: das Raster */}
      <div className="hidden overflow-hidden rounded-2xl border border-border bg-card md:block">
        <div
          className="grid items-center border-b border-border bg-background/60 px-5 py-2.5"
          style={{ gridTemplateColumns: spalten }}
        >
          <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">These</span>
          {listen.map((l) => (
            <span key={l.slug} className="flex flex-col items-center gap-[3px]">
              <FarbPunkt farbe={l.farbe} farbeDunkel={l.farbeDunkel} />
              <span className="text-[9px] font-semibold text-muted-foreground">{l.kurz}</span>
            </span>
          ))}
          {mitLage && (
            <span className="text-right text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
              Lage
            </span>
          )}
        </div>
        {zeilen.map((r) => (
          <div
            key={r.id}
            className="grid items-center border-b border-border/60 px-5 py-3 last:border-b-0"
            style={{ gridTemplateColumns: spalten }}
          >
            <div className="pr-4">
              <p className="max-w-[58ch] text-[13.5px] font-semibold leading-snug [text-wrap:pretty] sm:text-sm">
                {r.these}
              </p>
              {mitHinweis && r.hinweis && (
                <p className="mt-1 max-w-[62ch] text-xs leading-relaxed text-muted-foreground">{r.hinweis}</p>
              )}
              <span className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                {r.id} · {r.n} von {r.zellen.length} mit Position
              </span>
            </div>
            {r.zellen.map((z) => (
              <button
                key={z.slug}
                type="button"
                onClick={() => setOffen(r)}
                aria-label={`${z.kurz}: ${ampel(z.pos).label} — Beleg öffnen`}
                className="flex justify-center rounded-md py-1 outline-none transition-transform hover:scale-110 focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Glyph pos={z.pos} />
              </button>
            ))}
            {mitLage && (
              <span
                className="text-right text-[11px] font-bold"
                style={{ color: r.lage === "strittig" ? "#B04434" : "#2E7D5B" }}
              >
                {r.lage}
              </span>
            )}
          </div>
        ))}
        <AmpelLegende />
      </div>

      {/* Schmal: Listenform — nur Listen mit Position, als Chips */}
      <div className="flex flex-col gap-2.5 md:hidden">
        {zeilen.map((r) => (
          <button
            key={r.id}
            type="button"
            onClick={() => setOffen(r)}
            className="rounded-[14px] border border-border bg-card p-3.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="text-[10.5px] font-bold uppercase tracking-wider text-primary">
              {r.themaLabel} · {r.n} von {r.zellen.length}
            </span>
            <p className="mt-1 text-[13.5px] font-semibold leading-snug [text-wrap:pretty]">{r.these}</p>
            <span className="mt-2 flex flex-wrap gap-1">
              {r.belege.map((b) => (
                <span
                  key={b.slug}
                  className="inline-flex items-center gap-1 rounded-full bg-background py-0.5 pl-1 pr-2 text-[11px] font-semibold"
                >
                  <Glyph pos={b.pos} size={12} />
                  {b.kurz}
                </span>
              ))}
            </span>
            <span className="mt-2 block text-[11.5px] font-semibold text-primary">Belegzitate →</span>
          </button>
        ))}
        <p className="text-[11px] text-muted-foreground">
          Ampel: <Glyph pos={1} size={12} /> dafür · <Glyph pos={0} size={12} /> teils · <Glyph pos={-1} size={12} />{" "}
          dagegen — Glyphen zusätzlich zur Farbe.
        </p>
      </div>

      <BelegSheet zeile={offen} onClose={() => setOffen(null)} />
    </>
  );
}
