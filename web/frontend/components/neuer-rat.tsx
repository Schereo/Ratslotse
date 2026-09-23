"use client";

/**
 * Der gewählte Rat, bevor er in den Protokollen steht.
 *
 * Das Personenverzeichnis entsteht aus Anwesenheitslisten. Wer neu gewählt
 * ist, hätte bis zur ersten Sitzung keine Seite, bei der Ratswahl 2026 also
 * die Hälfte des neuen Rats. Die Daten kommen aus `/council/elected`
 * (Wahlergebnis + Kandidatenregister, `app/election/elected.py`).
 *
 * Drei Bausteine:
 * - `NeuerRatHinweis`: die Zeile auf dem Profil einer Person, die schon im
 *   Verzeichnis steht und wieder (oder neu) gewählt ist,
 * - `GewaehltProfil`: das ganze Profil für jemanden ohne Protokolle,
 * - `NeuerRatTeaser`: der Einstieg über dem Personenverzeichnis.
 */
import Link from "next/link";
import { ArrowLeft, ChevronRight, Vote } from "lucide-react";

import { Punkt } from "@/components/wahlabend/bausteine";
import { Card } from "@/components/ui";
import { partyBrand } from "@/components/decision-ui";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { featureAktiv, useAppConfig, useFeature } from "@/lib/features";
import type { ApiAntwort } from "@/lib/vertrag";
import { useZurueck } from "@/lib/zurueck";
import { ratsjahre } from "@/lib/ratsjahre";

export type GewaehlterRat = ApiAntwort<"/council/elected">;
export type Gewaehlt = ApiAntwort<"/council/elected/{slug}">;

export const NEUER_RAT_HREF = "/council/neuer-rat";

/**
 * Den gewählten Rat (ohne `slug`) oder eine Person daraus abrufen — nur bei
 * angeschaltetem Schalter.
 *
 * `laedt` deckt BEIDE Wartezeiten ab: die auf die App-Konfiguration und die
 * auf die Antwort. Mit `useFetch` gab es dazwischen einen Takt, in dem der
 * Schalter schon an, der Abruf aber noch nicht gestartet war — die Seite hielt
 * das für „nichts da" und zeigte auf dem Handy „Diesen Inhalt finde ich
 * nicht" (gemessen 23.09.2026).
 */
export function useGewaehlt<T extends GewaehlterRat | Gewaehlt>(slug?: string | null) {
  const { data: config, isLoading: configLaedt } = useAppConfig();
  const an = featureAktiv(config, "neuer-rat") && slug !== null;
  const pfad = slug ? `/council/elected/${encodeURIComponent(slug)}` : "/council/elected";
  const q = useQuery({
    queryKey: ["gewaehlt", slug ?? ""],
    queryFn: () => api.get<T>(pfad),
    enabled: an,
    staleTime: 60 * 60 * 1000,
    // Ein 404 ist hier die häufige, richtige Antwort (die Person ist nicht
    // gewählt) — drei Wiederholungen hielten jede Personen-Seite auf.
    retry: false,
  });
  return { an, data: q.data ?? null, laedt: configLaedt || (an && q.isPending) };
}

const zahl = (n: number) => n.toLocaleString("de-DE");

/** „1. November 2026" aus einem ISO-Datum. */
export function langesDatum(iso: string): string {
  const [j, m, t] = iso.slice(0, 10).split("-").map(Number);
  return new Date(j, m - 1, t).toLocaleDateString("de-DE", { day: "numeric", month: "long", year: "numeric" });
}

/** Wie der Sitz zustande kam — in den Worten des NKWG, ohne „Direktmandat":
 *  Das gibt es bei einer Ratswahl in Niedersachsen nicht. */
export const MANDAT: Record<Gewaehlt["mandate"], string> = {
  direct: "über Personenstimmen",
  list: "über den Listenplatz",
  transfer: "aus einem anderen Wahlbereich",
  successor: "nachgerückt",
  unknown: "",
};

/** „Dr. Benjamin Giesers" → „BG": Titel zählen nicht mit. */
function initialen(name: string): string {
  return name.split(/\s+/).filter((w) => w && !w.endsWith(".")).map((w) => w[0])
    .filter((_, i, a) => i === 0 || i === a.length - 1).join("").toUpperCase() || "?";
}

/** Die Wahlperiode, die mit der Wahl endet (2021 bei der Ratswahl 2026). */
export const letztePeriode = (termStart: string) => Number(termStart.slice(0, 4)) - 5;

/** Beruf und Jahrgang, soweit bekannt: „Studienrätin · Jg. 1960". */
export function steckbrief(g: Pick<Gewaehlt, "occupation" | "born">): string {
  return [g.occupation, g.born ? `Jg. ${g.born}` : null].filter(Boolean).join(" · ");
}

function StandHinweis({ status, compact = false }: { status: GewaehlterRat["status"]; compact?: boolean }) {
  if (status === "amtlich") {
    return <span className="text-meta text-muted-foreground">Amtliches Endergebnis</span>;
  }
  return (
    <span className="inline-flex items-center rounded-full border border-[#fde68a] bg-[#fffbeb] px-2.5 py-0.5 text-xs font-medium text-[#92400e] dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-300">
      {compact ? "vorläufig" : "Vorläufiges Ergebnis"}
    </span>
  );
}

/** Die Zeile auf einem bestehenden Profil: „Gewählt 2026 · Grüne · WB I". */
export function NeuerRatHinweis({ g }: { g: Gewaehlt }) {
  const an = useFeature("neuer-rat");
  if (!an) return null;
  return (
    <Link href={NEUER_RAT_HREF}
      className="mt-4 flex items-center gap-3 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 transition-colors hover:bg-primary/10">
      <Vote className="h-4 w-4 shrink-0 text-primary" aria-hidden />
      <span className="min-w-0 flex-1 text-[13.5px] text-foreground">
        <strong className="font-semibold">{g.council_status === "current" ? "Wiedergewählt" : g.council_status === "former" ? "Wieder gewählt" : "Neu gewählt"}</strong>{" "}
        für {g.list_short} im Wahlbereich {g.area_roman}
        {g.votes != null && <> · {zahl(g.votes)} Personenstimmen</>}
      </span>
      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
    </Link>
  );
}

/** Das Profil einer gewählten Person, die noch in keinem Protokoll steht. */
export function GewaehltProfil({ g }: { g: Gewaehlt }) {
  const { zeigen: zeigeZurueck, zurueck } = useZurueck();
  // Wahlperiode und Stand gehören zum Rat, nicht zur Person — dieselbe
  // Antwort wie die Liste, aus dem Cache des Browsers.
  const { data: rat } = useGewaehlt<GewaehlterRat>();
  const fakten: [string, React.ReactNode][] = [
    ["Liste", <span key="l" className="inline-flex items-center gap-2"><Punkt color={g.color} dark={g.color_dark} />{g.list_short}</span>],
    ["Wahlbereich", `${g.area_roman} · ${g.area_name}`],
    ...(g.position != null ? [["Listenplatz", String(g.position)] as [string, React.ReactNode]] : []),
    ...(g.votes != null ? [["Personenstimmen", zahl(g.votes)] as [string, React.ReactNode]] : []),
    ...(MANDAT[g.mandate] ? [["Sitz", MANDAT[g.mandate]] as [string, React.ReactNode]] : []),
    ...(g.council_terms.length && rat
      ? [["Bisher im Rat", ratsjahre(g.council_terms, letztePeriode(rat.term_start))] as [string, React.ReactNode]]
      : []),
  ];
  const info = steckbrief(g);
  const brand = partyBrand(g.list_short);
  return (
    <Card className="mx-auto max-w-3xl p-5 sm:p-6">
      {zeigeZurueck && (
        <button onClick={() => zurueck(NEUER_RAT_HREF)} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Zurück
        </button>
      )}
      {/* Derselbe Kopf wie beim Profil aus den Protokollen — nur ohne
          Sitzungszahl, die es noch nicht gibt. */}
      <div className="mt-3.5 flex items-center gap-4">
        <span className={cn("flex h-14 w-14 shrink-0 items-center justify-center rounded-full font-display text-xl font-bold shadow-sm", !brand && "bg-muted text-muted-foreground")}
          style={brand ? { backgroundColor: brand.bg, color: brand.fg } : undefined}>
          {initialen(g.name)}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">{g.name}</h1>
            {rat && <StandHinweis status={rat.status} compact />}
          </div>
          {info && <p className="mt-1 text-meta text-muted-foreground">{info}</p>}
        </div>
      </div>

      <p className="mt-4 text-lese text-foreground">
        {g.mandate === "successor" ? "Rückt in den Rat der Stadt Oldenburg nach"
          : g.council_status === "new" ? "Neu gewählt in den Rat der Stadt Oldenburg"
          : "Wieder gewählt in den Rat der Stadt Oldenburg"}
        {rat && <> — die Wahlperiode beginnt am {langesDatum(rat.term_start)}</>}.
      </p>

      <dl className="mt-4 grid gap-x-6 gap-y-2.5 rounded-xl border border-border p-4 sm:grid-cols-2">
        {fakten.map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between gap-3 sm:block">
            <dt className="text-xs text-muted-foreground">{k}</dt>
            <dd className="text-[14px] font-medium tabular-nums text-foreground sm:mt-0.5">{v}</dd>
          </div>
        ))}
      </dl>

      <p className="mt-4 text-hinweis text-muted-foreground">
        Sitzungen, Ausschüsse und Wortbeiträge stehen hier, sobald die ersten Protokolle
        des neuen Rats vorliegen. Name, Beruf und Jahrgang stammen aus der amtlichen
        Bekanntmachung der Wahlvorschläge, Stimmen und Sitz aus dem Wahlergebnis der Stadt.
      </p>
      <Link href={NEUER_RAT_HREF} className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
        Alle Gewählten ansehen <ChevronRight className="h-4 w-4" aria-hidden />
      </Link>
    </Card>
  );
}

/** Der Einstieg über dem Personenverzeichnis. */
export function NeuerRatTeaser() {
  const { an, data } = useGewaehlt<GewaehlterRat>();
  if (!an || !data) return null;
  const neu = data.members.filter((m) => m.council_status === "new").length;
  return (
    <Link href={NEUER_RAT_HREF} className="block">
      <Card className="card-interactive flex items-center gap-3 p-4">
        <Vote className="h-5 w-5 shrink-0 text-primary" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-foreground">
            Der neue Rat ab {langesDatum(data.term_start)}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {data.members.length} Gewählte, davon {neu} neu im Rat
            {data.status === "vorlaeufig" && " · vorläufiges Ergebnis"}
          </p>
        </div>
        <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
      </Card>
    </Link>
  );
}

export { StandHinweis };
