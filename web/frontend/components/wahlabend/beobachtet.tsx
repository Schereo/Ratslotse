"use client";

// Die Beobachtungsliste: Kandidaturen quer über alle Listen im Blick behalten.
//
// Tims Wunsch (14.09.2026): „bestimmte Kandidaten aus allen Parteien zum
// beobachten auswählen". Die Rangliste führt 383 Kandidaturen; wer fünf Namen
// verfolgt — die eigene Nachbarin, den alten Schulleiter, zwei aus dem
// Ortsrat —, will sie nebeneinander sehen und nicht fünfmal filtern.
//
// Gemerkt wird am KONTO, nicht im Browser: Der Stern soll auf dem Telefon
// noch da sein, wenn man ihn am Schreibtisch gesetzt hat. Ohne Konto gibt es
// deshalb keinen Stern, sondern einen Satz, der sagt warum.
//
// Der Server liefert zu jedem Merker die AKTUELLE Zeile mit (`row`) — sonst
// müsste die Seite für fünf Namen die ganze Rangliste durchsuchen, und die
// App noch einmal.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Star } from "lucide-react";
import Link from "next/link";
import { KICKER, Punkt, TON } from "@/components/wahlabend/bausteine";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  beobachtetPfad,
  kandidatenStatus,
  prozent,
  zahl,
  type Beobachtet,
  type BeobachtetEintrag,
  type KandidatenZeile,
  type Wahlabend,
} from "@/lib/wahlabend";

/** Der Schlüssel einer Kandidatur — dasselbe Tripel wie im Backend. */
function schluessel(z: { party: string; area: number; position: number }): string {
  return `${z.party}:${z.area}:${z.position}`;
}

/** Was die Rangliste und die Karte gemeinsam brauchen: Wer ist gemerkt, und
 *  wie ändert man das? Ein Haken statt zweier Abfragen. */
export function useBeobachtet(wahl: string | null, probe: string | null, counted: string | null) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const pfad = beobachtetPfad(wahl, probe, counted);
  const abfrage = useQuery({
    queryKey: ["wahlabend-beobachtet", pfad, user?.id ?? null],
    queryFn: () => api.get<Beobachtet>(pfad),
    enabled: !!user,
    staleTime: 30_000,
  });
  const eintraege = abfrage.data?.entries ?? [];
  const nachSchluessel = new Map(eintraege.map((e) => [schluessel(e), e]));

  const umschalten = useMutation({
    mutationFn: async (z: KandidatenZeile) => {
      const vorhanden = nachSchluessel.get(schluessel(z));
      if (vorhanden) await api.del(`/wahlabend/beobachtet/${vorhanden.id}`);
      else await api.post("/wahlabend/beobachtet", {
        election: abfrage.data?.election.slug ?? wahl, party: z.party, area: z.area, position: z.position,
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wahlabend-beobachtet"] }),
  });

  return {
    angemeldet: !!user,
    eintraege,
    istGemerkt: (z: { party: string; area: number; position: number }) => nachSchluessel.has(schluessel(z)),
    umschalten: (z: KandidatenZeile) => umschalten.mutate(z),
    laeuft: umschalten.isPending,
  };
}

/** Der Stern an einer Zeile der Rangliste. */
export function Stern({ gemerkt, onClick, name, className }: {
  gemerkt: boolean;
  onClick: () => void;
  name: string;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={gemerkt}
      aria-label={gemerkt ? `${name} nicht mehr beobachten` : `${name} beobachten`}
      title={gemerkt ? "Nicht mehr beobachten" : "Beobachten"}
      className={cn(
        "rounded-md p-1 transition-colors hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        gemerkt ? "text-signal" : "text-muted-foreground/50 hover:text-foreground",
        className,
      )}
    >
      <Star aria-hidden className={cn("h-4 w-4", gemerkt && "fill-current")} />
    </button>
  );
}

function Zeile({ eintrag, daten, entfernen }: {
  eintrag: BeobachtetEintrag;
  daten: Wahlabend;
  entfernen: () => void;
}) {
  const z = eintrag.row;
  const status = z ? kandidatenStatus(z, daten.phase, daten.person_votes_available) : null;
  return (
    <li className="flex items-start gap-2.5 py-2">
      <span className="w-7 flex-none pt-0.5 text-right font-mono text-[10.5px] text-muted-foreground tabular-nums">
        {z?.rank ?? "–"}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-semibold">{eintrag.name}</span>
        <span className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-[11.5px] text-muted-foreground">
          {z ? <Punkt color={z.color} dark={z.color_dark} /> : null}
          {eintrag.subtitle}
        </span>
        {status ? (
          <span className={cn("mt-1 inline-block rounded-full px-2 py-0.5 text-[10.5px] font-semibold", TON[status.ton])}>
            {status.text}
          </span>
        ) : (
          <span className="mt-1 block text-[11.5px] text-muted-foreground">
            Diese Kandidatur steht in dieser Wahl nicht (mehr) auf dem Stimmzettel.
          </span>
        )}
      </span>
      <span className="flex-none text-right">
        <span className="block text-[13px] font-semibold tabular-nums">{zahl(z?.votes ?? null)}</span>
        {z?.party_share_pct !== null && z?.party_share_pct !== undefined ? (
          <span className="block text-[10.5px] text-muted-foreground tabular-nums">
            {prozent(z.party_share_pct)} der Liste
          </span>
        ) : null}
      </span>
      <Stern gemerkt onClick={entfernen} name={eintrag.name} className="mt-0.5 flex-none" />
    </li>
  );
}

/** Die Karte über der Rangliste — nur, wenn etwas gemerkt ist. */
export function BeobachtetKarte({ eintraege, daten, entfernen, className }: {
  eintraege: BeobachtetEintrag[];
  daten: Wahlabend;
  entfernen: (e: BeobachtetEintrag) => void;
  className?: string;
}) {
  if (!eintraege.length) return null;
  return (
    <section className={cn("rounded-2xl border border-signal/30 bg-signal/[0.04] p-4", className)}>
      <p className={KICKER}>Deine Liste</p>
      <h3 className="mt-0.5 font-display text-[15px] font-bold tracking-tight">
        {eintraege.length} beobachtete {eintraege.length === 1 ? "Kandidatur" : "Kandidaturen"}
      </h3>
      <p className="mt-1 text-[12.5px] text-muted-foreground">
        In der Reihenfolge des stadtweiten Rangs — quer über alle Listen.
      </p>
      <ol className="mt-1 divide-y divide-border/70">
        {eintraege.map((e) => (
          <Zeile key={e.id} eintrag={e} daten={daten} entfernen={() => entfernen(e)} />
        ))}
      </ol>
    </section>
  );
}

/** Der Satz für alle ohne Konto: Warum es hier keinen Stern gibt. */
export function BeobachtenHinweis({ className }: { className?: string }) {
  return (
    <p className={cn("text-[12.5px] leading-relaxed text-muted-foreground", className)}>
      Mit einem Konto kannst du einzelne Kandidaturen beobachten — quer über alle Listen, und auf jedem Gerät dieselben.{" "}
      <Link href="/register" className="font-semibold text-primary underline-offset-2 hover:underline">
        Kostenlos registrieren
      </Link>
      .
    </p>
  );
}
