"use client";

// Der große Verweis von der Landing auf den Wahlprogramm-Vergleich —
// befristetes Element bis zum 13.09.2026 (Bauplan §5.5/§5.6): Nach der Wahl
// nimmt er sich selbst aus der Seite, ohne dass jemand deployen muss.
// Trägt dasselbe Umgebungs-Gate wie /kommunalwahl (layout.tsx): Auf Prod ist
// die Zielseite ein 404, also erscheint dort auch der Banner nicht.

import Link from "next/link";
import { ArrowRight, Vote } from "lucide-react";
import { Mascot } from "@/components/mascot";
import { TageZahl, tageBis } from "@/components/kommunalwahl/countdown";
import { useEffect, useState } from "react";

export function KommunalwahlBanner() {
  const [vorbei, setVorbei] = useState(false);
  useEffect(() => setVorbei(tageBis() <= 0), []);
  if (process.env.NEXT_PUBLIC_RATSLOTSE_ENV !== "dev") return null;
  if (vorbei) return null;

  return (
    <section aria-label="Kommunalwahl 2026" className="border-y border-border bg-primary">
      <Link
        href="/kommunalwahl"
        className="group mx-auto flex max-w-6xl flex-col items-center gap-5 px-5 py-8 text-primary-foreground sm:flex-row sm:gap-7 sm:py-7"
      >
        <Mascot pose="point" decorative className="hidden h-20 w-20 flex-none sm:block lg:h-24 lg:w-24" />
        <div className="min-w-0 text-center sm:text-left">
          <p className="inline-flex items-center gap-1.5 rounded-full bg-signal px-3 py-1 text-xs font-semibold text-signal-foreground">
            <Vote className="h-3.5 w-3.5" />
            Ratswahl am 13. September — noch <TageZahl /> Tage
          </p>
          <h2 className="mt-2.5 font-display text-[22px] font-bold leading-tight tracking-tight sm:text-[26px]">
            Wahlprogramme, verständlich verglichen.
          </h2>
          <p className="mt-1.5 max-w-[62ch] text-sm leading-relaxed text-primary-foreground/85">
            Wer steht wofür? Alle Programme gelesen, 44 Thesen, jede Aussage mit Beleg im Original —
            ohne Empfehlung. Öffentlich, ganz ohne Konto.
          </p>
        </div>
        <span className="inline-flex flex-none items-center gap-1.5 rounded-xl bg-card px-5 py-2.5 text-sm font-semibold text-foreground transition-transform duration-200 ease-out-strong sm:ml-auto [@media(hover:hover)]:group-hover:-translate-y-0.5">
          Zum Wahl-Check <ArrowRight className="h-4 w-4" />
        </span>
      </Link>
    </section>
  );
}
