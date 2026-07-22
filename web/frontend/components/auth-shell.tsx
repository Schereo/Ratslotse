"use client";

import * as React from "react";
import Link from "next/link";
import { Check } from "lucide-react";
import { Card } from "@/components/ui";
import { Mascot, type MascotPose } from "@/components/mascot";
import { SeasonalFamily, useMascotTheme } from "@/components/seasonal-mascot";
import { BrandMark } from "@/components/brand";

// RL-F04 (Design 6a): drei Belege unter dem Claim der Marken-Hälfte.
const CLAIM_POINTS = [
  "Frag den Rat — Antworten mit Quellen",
  "Benachrichtigungen zu deinen Themen",
  "Direkt aus dem amtlichen Ratsinformationssystem",
];

/**
 * Gemeinsamer Rahmen der Auth-Seiten (RL-1001, Design 2a): Split-Layout —
 * links (ab lg) eine Marken-Fläche mit Verlauf, Wellen und der Lotti-Familie,
 * rechts die Formular-Karte mit Lotti über der Kante. Mobil bleibt nur die
 * Karte auf Wellen-Hintergrund.
 */
export function AuthShell({
  title,
  pose = "wave",
  children,
}: {
  title: string;
  pose?: MascotPose;
  children: React.ReactNode;
}) {
  const theme = useMascotTheme();
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      {/* Marken-Hälfte: nur Desktop — Claim + Familien-Fries. */}
      <div className="relative hidden overflow-hidden bg-waves bg-gradient-to-br from-[#eaf5fd] via-background to-[hsl(19_92%_55%/0.07)] dark:from-muted/40 dark:via-background dark:to-card lg:flex lg:flex-col lg:justify-between lg:p-12">
        {/* Logo führt zurück zur Startseite — sonst ist die Auth-Seite eine Sackgasse. */}
        <Link href="/" aria-label="Zur Startseite" className="w-fit">
          <BrandMark />
        </Link>
        <div>
          <p className="max-w-md font-display text-3xl font-extrabold leading-tight tracking-tight text-foreground">
            Der Stadtrat, verständlich erklärt.
          </p>
          <p className="mt-3 max-w-sm text-sm leading-relaxed text-muted-foreground">
            Beschlüsse durchsuchen, Themen folgen, Fragen stellen — Lotti lotst
            dich durch die Oldenburger Ratspolitik.
          </p>
          <ul className="mt-5 space-y-2.5">
            {CLAIM_POINTS.map((point) => (
              <li key={point} className="flex items-center gap-2.5 text-sm text-foreground">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10">
                  <Check className="h-3.5 w-3.5 text-primary" />
                </span>
                {point}
              </li>
            ))}
          </ul>
        </div>
        <SeasonalFamily className="h-24 self-start" />
      </div>

      {/* Formular-Hälfte. */}
      <div className="flex items-center justify-center bg-waves px-4 pb-12 pt-28 lg:bg-none lg:pt-12">
        <div className="relative w-full max-w-sm">
          <Mascot pose={pose} theme={theme} className="pointer-events-none absolute -top-[5.65rem] left-1/2 h-24 w-24 -translate-x-1/2" />
          <Card className="relative w-full p-8 shadow-lifted">
            <div className="flex items-center gap-3">
              <Link href="/" aria-label="Zur Startseite" className="lg:hidden"><BrandMark /></Link>
              <h1 className="font-display text-[30px] font-extrabold tracking-tight text-foreground">{title}</h1>
            </div>
            {children}
          </Card>
        </div>
      </div>
    </div>
  );
}
