"use client";

// Der Weg ins Tippspiel von anderen Seiten aus (Startseite, Heute, Wahlabend,
// Stichwahl) — eine Stelle, damit die Einladung überall dasselbe sagt und
// überall dann verschwindet, wenn es nichts zu tippen gibt.
//
// **Wohin verlinkt wird, entscheidet das BACKEND** (`GET /api/wahlen`,
// `tipp_path`): Ob es zu dieser Wahl eine Runde gibt, ob sie öffentlich ist
// und wie ihre Adresse lautet, steht in `prediction/rounds.py` und der
// Spielzeile — die Seite rät das nicht nach. `tipp_locked` heißt „es gäbe
// eine, aber nicht für dich" (Konto-Runde, nicht angemeldet); dann führt die
// Einladung zur Anmeldung statt ins Leere.

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Trophy } from "lucide-react";
import { api } from "@/lib/api";
import { useFeature } from "@/lib/features";
import { cn } from "@/lib/utils";
import type { Wahlliste, Wahlzeile } from "@/lib/wahlen";

/** Die Zeile der Wahl aus `/api/wahlen` — `slug` leer heißt „die im Fokus".
 *
 *  Eigener Abruf statt eines neuen Feldes in `/api/app-config`: Dort hängt
 *  der App-Start dran, und der darf nicht von der Tippspiel-Tabelle abhängen
 *  (web/backend/CLAUDE.md). `/api/wahlen` ist öffentlich, klein und wird von
 *  React Query ohnehin geteilt. */
export function useWahlzeile(slug?: string | null): Wahlzeile | null {
  const an = useFeature("tippspiel");
  const { data } = useQuery({
    queryKey: ["wahlen", "einladung"],
    queryFn: () => api.get<Wahlliste>("/wahlen"),
    staleTime: 5 * 60 * 1000,
    // Ein Fehler hier darf keine Seite umbringen: Ohne Antwort gibt es eben
    // keine Einladung — dieselbe Regel wie beim Feature-Schalter. `throwOnError`
    // ausdrücklich, nicht dem Standard vertrauend: Diese Einladung ist eine
    // Nebensache auf fremden Seiten, und ein 404 von `/api/wahlen` (Schalter
    // aus) darf den Wahlabend nicht in die Fehlerfläche schicken.
    retry: 1,
    throwOnError: false,
    enabled: an,
  });
  if (!data) return null;
  return (slug ? data.elections.find((z) => z.slug === slug) : data.elections.find((z) => z.focus)) ?? null;
}

/** Knopf „Mittippen" — rendert nichts, wenn es für diese Wahl kein Spiel
 *  gibt. `variant` unterscheidet die Flächen: „leise" für eine Karte, in der
 *  schon ein Hauptknopf steht, „karte" für eine eigenständige Einladung. */
export function TippspielKnopf({ slug, className, kurz }: {
  slug?: string | null;
  className?: string;
  /** Nur das Nötigste („Mittippen") statt des vollen Satzes. */
  kurz?: boolean;
}) {
  const zeile = useWahlzeile(slug);
  if (!zeile) return null;
  if (!zeile.tipp_path) {
    // Es gäbe eines, aber nur mit Konto. Der Weg dahin ist die Anmeldung —
    // ein Link auf die Runde selbst endete an der 401-Wand.
    if (!zeile.tipp_locked) return null;
    return (
      <Link
        href="/login"
        className={cn(
          "inline-flex flex-none items-center gap-1.5 rounded-xl border border-primary/30 bg-card px-4 py-2.5 text-sm font-semibold text-primary transition-colors duration-fluss hover:bg-primary/5",
          className,
        )}
      >
        <Trophy className="h-4 w-4" aria-hidden /> {kurz ? "Tippspiel" : "Zum Tippspiel anmelden"}
      </Link>
    );
  }
  return (
    <Link
      href={zeile.tipp_path}
      className={cn(
        "inline-flex flex-none items-center gap-1.5 rounded-xl border border-primary/30 bg-card px-4 py-2.5 text-sm font-semibold text-primary transition-colors duration-fluss hover:bg-primary/5",
        className,
      )}
    >
      <Trophy className="h-4 w-4" aria-hidden /> {kurz ? "Mittippen" : "Mittippen"}
    </Link>
  );
}

/** Eine eigenständige Einladungs-Karte — für Seiten, auf denen das Tippspiel
 *  nicht nur ein Nebenweg ist (die Wahlabend-Seiten). Der Text folgt der
 *  Phase: vorher wird getippt, danach ist die Rangliste das Interessante. */
export function TippspielEinladung({ slug, phase, className }: {
  slug?: string | null;
  /** "before" = es wird noch getippt; sonst läuft die Auszählung. */
  phase: string;
  className?: string;
}) {
  const zeile = useWahlzeile(slug);
  if (!zeile || (!zeile.tipp_path && !zeile.tipp_locked)) return null;
  const offen = phase === "before";
  const gesperrt = !zeile.tipp_path;
  return (
    <section
      data-testid="tippspiel-einladung"
      className={cn(
        "mt-5 flex flex-col items-start gap-3 rounded-2xl border border-primary/20 bg-primary/[0.05] px-5 py-4 sm:flex-row sm:items-center",
        className,
      )}
      aria-label="Tippspiel"
    >
      <Trophy className="hidden h-6 w-6 flex-none text-primary sm:block" aria-hidden />
      <div className="min-w-0 flex-1">
        <h2 className="font-display text-[16px] font-bold tracking-tight">
          {offen ? "Wie geht es aus? Tipp mit." : "Wer lag richtig?"}
        </h2>
        <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
          {gesperrt
            ? "Zu dieser Wahl läuft ein Tippspiel — dafür brauchst du ein kostenloses Konto."
            : offen
              ? "Tippe die Prozente und die Wahlbeteiligung — ohne Konto, bis die Wahllokale schließen. Am Abend siehst du live, wie dein Tipp zum Stand passt."
              : "Im Tippspiel stehen die Tipps gegen den Auszählungsstand — mit Rangliste und Punkten."}
        </p>
      </div>
      <TippspielKnopf slug={slug} className="w-full justify-center sm:w-auto" />
    </section>
  );
}
