"use client";

// Alle 44 Thesen einer Liste, kompakt zweispaltig; antippen klappt den Beleg
// direkt darunter auf (Design 3b, „Aufgeklappt (W1)").

import { useState } from "react";
import type { Pos } from "@/lib/kommunalwahl-types";
import { Glyph, ampel } from "./ui";

export type ProfilThese = {
  id: string;
  these: string;
  themaKurz: string;
  pos: Pos;
  beleg: string | null;
  href: string | null;
  seitenLabel: string;
};

export function ThesenListe({ thesen }: { thesen: ProfilThese[] }) {
  const [offen, setOffen] = useState<string | null>(null);
  const [alleMobil, setAlleMobil] = useState(false);
  const gezeigt = thesen;
  const offene = thesen.find((t) => t.id === offen) ?? null;

  return (
    <div className="rounded-2xl border border-border bg-card px-4 py-2 sm:px-5">
      <div className={`sm:grid sm:grid-cols-2 sm:gap-x-10 ${alleMobil ? "" : "max-sm:max-h-[420px] max-sm:overflow-hidden"}`}>
        {gezeigt.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setOffen(offen === t.id ? null : t.id)}
            disabled={t.pos === null}
            aria-expanded={offen === t.id}
            aria-label={`${t.id}: ${ampel(t.pos).label}${t.pos !== null ? " — Beleg anzeigen" : ""}`}
            className="flex w-full items-start gap-2.5 border-b border-border/50 py-1.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default sm:py-[7px]"
          >
            <Glyph pos={t.pos} size={17} className="mt-0.5" />
            <span className="min-w-0 text-[12.5px] leading-normal text-muted-foreground">
              <strong className="font-semibold text-foreground">{t.id}</strong> · {t.these}
            </span>
          </button>
        ))}
      </div>
      {offene && offene.beleg && (
        <div className="my-2.5 rounded-xl border border-primary/25 bg-primary/5 px-4 py-3">
          <p className="text-[12.5px] leading-relaxed text-muted-foreground">
            <strong className="font-semibold text-foreground">
              {offene.id} · {offene.themaKurz}:
            </strong>{" "}
            »{offene.beleg}«{" "}
            {offene.href && (
              <a href={offene.href} target="_blank" rel="noopener noreferrer" className="whitespace-nowrap text-primary">
                {offene.seitenLabel} im Programm ↗
              </a>
            )}
          </p>
        </div>
      )}
      <button
        type="button"
        onClick={() => setAlleMobil((v) => !v)}
        className="block w-full py-2 text-center text-xs font-semibold text-primary sm:hidden"
      >
        {alleMobil ? "Weniger anzeigen ⌃" : "Alle 44 anzeigen ⌄"}
      </button>
    </div>
  );
}
