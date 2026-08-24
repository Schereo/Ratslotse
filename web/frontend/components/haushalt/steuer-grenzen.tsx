"use client";

// Der Abbinder des Steuer-Steckbriefs: was die Seite über diese Einnahmeart
// NICHT sagt.

import Link from "next/link";
import { Calculator, Search } from "lucide-react";
import type { SteuerArt } from "@/lib/haushalt-steuern";

/** Was die Seite über diese Einnahmeart **nicht** sagt — in EINEM Block.
 *
 *  Bis 24.08.2026 waren das zwei gestrichelte Kästen direkt untereinander:
 *  „Was brächte ein Punkt mehr?" (wo sich das nicht überschlagen lässt) und
 *  „Dazu hat der Rat entschieden". Beide sagen dasselbe Genre — „das können
 *  wir hier nicht" —, sahen gleich aus und standen am Ende einer Seite, die
 *  ohnehin schon aus Fließtext besteht. Zusammengelegt ist es eine Liste mit
 *  zwei Einträgen statt zweier Karten, und das Zeichen davor gibt dem Auge
 *  einen Halt, den drei Absätze hintereinander nicht haben.
 *
 *  Gestrichelt bleibt der Rahmen: „nicht von uns / noch nicht fertig"
 *  (DESIGNSPRACHE.md). Wo sich der Punkt überschlagen lässt, trägt der Block
 *  nur den zweiten Eintrag — die Zahl steht dann oben in ihrer eigenen
 *  Karte. */
export function Grenzen({ art }: { art: SteuerArt }) {
  const eintraege = [
    art.punktUnmoeglich && {
      schluessel: "punkt",
      icon: Calculator,
      /* Dieselbe Frage wie auf der Zahl-Karte der anderen Steuerarten —
         der Text darunter ist ihre Antwort, nicht ihre Wiederholung. */
      titel: "Was brächte ein Punkt mehr?",
      /* Kein Link ins Labor: Dort fehlt derselbe Regler aus demselben Grund —
         ein Verweis verspräche, was die nächste Seite auch nicht kann. */
      text: art.punktUnmoeglich,
      link: null as { href: string; text: string } | null,
    },
    {
      schluessel: "beschluesse",
      icon: Search,
      titel: "Was der Rat dazu entschieden hat",
      text: "Die automatische Verknüpfung von Beschlüssen mit Einnahmearten "
        + "bauen wir noch. Bis dahin findet die Suche, was dazu beschlossen wurde.",
      link: {
        href: `/council?q=${encodeURIComponent(art.titel)}`,
        text: `Beschlüsse zu „${art.titel}“ suchen`,
      },
    },
  ].filter(Boolean) as {
    schluessel: string;
    icon: typeof Search;
    titel: string;
    text: string;
    link: { href: string; text: string } | null;
  }[];

  return (
    <div className="rounded-2xl border border-dashed border-border bg-card p-4">
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Was hier (noch) nicht steht
      </p>
      <div className="mt-2.5 flex flex-col divide-y divide-dashed divide-border">
        {eintraege.map((e) => (
          <div key={e.schluessel} className="flex gap-2.5 py-2.5 first:pt-0 last:pb-0">
            <e.icon aria-hidden
              className="mt-0.5 h-4 w-4 flex-none text-muted-foreground" />
            <div className="min-w-0">
              <p className="text-[12.5px] font-semibold leading-snug">{e.titel}</p>
              <p className="mt-1 max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/80">
                {e.text}
              </p>
              {e.link && (
                <Link href={e.link.href}
                  className="mt-1.5 inline-flex items-center gap-1.5 text-xs font-semibold text-primary">
                  {e.link.text} →
                </Link>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
