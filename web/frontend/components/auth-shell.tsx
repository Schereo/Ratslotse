"use client";

import * as React from "react";
import Link from "next/link";
import { Check } from "lucide-react";
import { Card } from "@/components/ui";
import { cn } from "@/lib/utils";
import { Mascot, type MascotPose } from "@/components/mascot";
import { SeasonalFamily, useMascotTheme } from "@/components/seasonal-mascot";
import { BrandMark } from "@/components/brand";

// RL-F04 (Design 6a): drei Belege unter dem Claim der Marken-Hälfte.
const CLAIM_POINTS = [
  "Frag den Rat — Antworten mit Quellen",
  "Benachrichtigungen zu deinen Themen",
  "Direkt aus dem amtlichen Ratsinformationssystem",
];

/** Pflicht-Fuß aller Auth-Seiten — steht auf dem Hintergrund, nicht in der Karte.
 *
 *  Die Abgrenzung zur Stadt ist App-Store-Auflage (Richtlinie 5.2), „Hilfe"
 *  ebenso (Richtlinie 1.5: Der Feedback-Dialog hängt am angemeldeten Konto,
 *  hilft also ausgerechnet dem nicht, der auf dieser Seite hängenbleibt).
 *  Beides gehört zur *Seite*, nicht zum Formular: In der Karte hat es die
 *  Registrierung so hoch gemacht, dass sie auf dem iPad quer nicht mehr aufs
 *  Bild passte (Tims Befund 15.08., Build 11). Hier unten trägt es außerdem
 *  jede Auth-Seite, nicht nur Anmelden und Registrieren.
 */
function RechtlicherFuss({ breit }: { breit: boolean }) {
  return (
    <div
      className={cn(
        "mx-auto mt-5 w-full max-w-sm space-y-1 text-center text-xs leading-relaxed text-muted-foreground",
        breit && "lg:max-w-xl",
      )}
    >
      <p className="text-balance">
        Ratslotse ist ein privates Bürgerprojekt und kein Angebot der Stadt Oldenburg.
      </p>
      <p>
        <Link href="/hilfe" className="hover:text-foreground hover:underline">Hilfe &amp; Kontakt</Link>
        {" · "}
        <Link href="/impressum" className="hover:text-foreground hover:underline">Impressum</Link>
        {" · "}
        <Link href="/datenschutz" className="hover:text-foreground hover:underline">Datenschutz</Link>
      </p>
    </div>
  );
}

/**
 * Gemeinsamer Rahmen der Auth-Seiten (RL-1001, Design 2a): Split-Layout —
 * links (ab lg) eine Marken-Fläche mit Verlauf, Wellen und der Lotti-Familie,
 * rechts die Formular-Karte mit Lotti über der Kante. Mobil bleibt nur die
 * Karte auf Wellen-Hintergrund.
 *
 * `breit` gibt der Karte ab lg mehr Breite — für Seiten mit langem Formular
 * (Registrieren), die ihre Felder dort zweispaltig legen. Breite ist auf dem
 * iPad die einzige Reserve, die es im Überfluss gibt; Höhe ist quer knapp.
 */
export function AuthShell({
  title,
  pose = "wave",
  breit = false,
  children,
}: {
  title: string;
  pose?: MascotPose;
  breit?: boolean;
  children: React.ReactNode;
}) {
  const theme = useMascotTheme();
  // min-h-screen (100vh), nicht dvh: Die dynamische Einheit schrumpft auf iOS
  // mit der Tastatur — die Karte würde beim Antippen eines Feldes springen.
  // 100vh steht still, und im WebView der App ist es ohnehin die Fensterhöhe.
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

      {/* Formular-Hälfte: Karte oben, Pflicht-Fuß unten am Spaltenende. */}
      {/* Der Abstand über der Karte ist kein Geschmack, sondern Lottis Platz:
          Sie hängt 5,65 rem über der Kartenkante, und zentriertes Layout gibt
          ihr nur die halbe Restluft — auf dem iPad quer (und auf 900-px-
          Desktops) war das zu wenig, sie wurde oben abgeschnitten. Deshalb
          steht der Mindestabstand ab lg als Polsterung fest; die Safe Area
          rechnet überall mit, damit nichts unter der Statusleiste klebt. */}
      <div className="flex flex-col bg-waves px-4 pb-[calc(1.5rem+env(safe-area-inset-bottom))] pt-[calc(7rem+env(safe-area-inset-top))] lg:bg-none lg:pt-[calc(6rem+env(safe-area-inset-top))]">
        {/* `my-auto` statt `items-center`: Auto-Ränder verteilen nur *freien*
            Platz und werden zu 0, sobald der Inhalt höher ist als der Streifen.
            Zentriert bleibt die Karte also, solange sie passt — und rutscht bei
            langen Formularen auf kleinen Bildschirmen nicht nach oben aus dem
            Bild, wie es echtes Zentrieren täte (Lotti in der Dynamic Island,
            Tims Befund 14.08.). */}
        <div className="flex flex-1 justify-center">
          <div className={cn("relative my-auto w-full max-w-sm", breit && "lg:max-w-xl")}>
            <Mascot pose={pose} theme={theme} className="pointer-events-none absolute -top-[5.65rem] left-1/2 h-24 w-24 -translate-x-1/2" />
            {/* p-6 auf dem Handy: Die Registrieren-Karte ist die längste —
                2 × 8 px weniger Polsterung sind eine ganze Textzeile weniger
                Höhe, ohne dass es enger wirkt. */}
            <Card className="relative w-full p-6 shadow-lifted sm:p-8">
              <div className="flex items-center gap-3">
                <Link href="/" aria-label="Zur Startseite" className="lg:hidden"><BrandMark /></Link>
                <h1 className="font-display text-[30px] font-extrabold tracking-tight text-foreground">{title}</h1>
              </div>
              {children}
            </Card>
          </div>
        </div>
        <RechtlicherFuss breit={breit} />
      </div>
    </div>
  );
}
