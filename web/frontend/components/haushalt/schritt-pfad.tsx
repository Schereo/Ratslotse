"use client";

// Der Schritt-Pfad im Kopf jeder Schritt-Seite — Nachfolger der Zeichen-Kachel
// (Design H5-09; die Kachel stand hier seit 24.08., „hässlich", Tim 26.08.).
//
// Die Kachel wiederholte das Zeichen des Schritts und sagte sonst nichts. Der
// Pfad zeigt stattdessen, WO im Weg man steht: zwölf Punkte in den vier
// Etappen-Gruppen des Wegweisers, besuchte Seiten gefüllt (derselbe lokale
// Lesestand wie dort, lib/haushalt-fortschritt.ts), die aktuelle als Ring.
// Die Zeichen selbst bleiben an den zwei kleinen Orten — Wegweiser-Zeile und
// Weiter-Fuß.
//
// Der Pfad ist ein LINK zum Wegweiser, kein Dekor: Wer wissen will, was die
// Punkte heißen, landet an der Liste, die sie erklärt. Bis zur Hydration ist
// der Lesestand leer (Server und erster Client-Render deterministisch gleich,
// wie beim Wegweiser) — dann sind alle Punkte offen und nur der Ring gesetzt.
//
// Unter 640 px verschwindet er ersatzlos, wie vorher die Kachel: Mobil gibt
// es die leere Ecke rechts neben dem gedeckelten Kopf-Absatz nicht, und die
// Bühne darunter trägt die Schritt-Auskunft in ihrem Kicker mit. Kein
// erfundener Stand: Seiten ohne Schritt (Steckbriefe) bekommen keinen Pfad.

import Link from "next/link";
import { ETAPPEN, SCHRITTE } from "@/components/haushalt/wegweiser";
import { useFortschritt } from "@/lib/haushalt-fortschritt";
import { cn } from "@/lib/utils";

function Punkt({ zustand }: { zustand: "aktuell" | "gelesen" | "offen" }) {
  if (zustand === "aktuell") {
    return (
      <span className="h-2 w-2 flex-none rounded-full border-2 border-primary bg-card shadow-[0_0_0_3px_hsl(var(--primary)/0.14)]" />
    );
  }
  return (
    <span
      className={cn(
        "h-[7px] w-[7px] flex-none rounded-full",
        zustand === "gelesen" ? "bg-primary" : "bg-border",
      )}
    />
  );
}

export function SchrittPfad({ href, className }: {
  href: string;
  className?: string;
}) {
  const besucht = useFortschritt();
  const schritt = SCHRITTE.find((s) => s.href === href);
  if (!schritt) return null;
  const etappe = ETAPPEN.find((e) => schritt.nr >= e.von && schritt.nr <= e.bis)!;

  return (
    <Link
      href="/haushalt#wegweiser"
      aria-label={`Schritt ${schritt.nr} von ${SCHRITTE.length} · Etappe „${etappe.kicker}“ — zum Wegweiser`}
      className={cn(
        "group hidden flex-none flex-col items-end gap-[5px] pt-1.5 sm:flex",
        className,
      )}
    >
      <span aria-hidden="true" className="flex items-center gap-[7px]">
        {ETAPPEN.map((e) => (
          <span key={e.kicker} className="flex items-center gap-[3px]">
            {SCHRITTE.slice(e.von - 1, e.bis).map((s) => (
              <Punkt
                key={s.nr}
                zustand={
                  s.nr === schritt.nr ? "aktuell"
                    : besucht.has(s.href) ? "gelesen"
                      : "offen"
                }
              />
            ))}
          </span>
        ))}
      </span>
      <span className="font-mono text-[9px] font-medium uppercase tracking-[0.1em] text-muted-foreground transition-colors group-hover:text-primary">
        Schritt {schritt.nr} von {SCHRITTE.length} · {etappe.kicker}
      </span>
    </Link>
  );
}
