"use client";

/**
 * „Neu bei Ratslotse" — die Highlights eines Releases auf der Übersicht.
 *
 * Ratslotse liefert laufend aus; wer alle paar Wochen vorbeikommt, merkt von
 * einem neuen Feature sonst nichts. Die Karte steht im Hinweis-Slot der
 * Heute-Seite und **nicht** als Dialog vor der Seite: Wer die App öffnet, will
 * zum Rat, nicht zu uns (Tims Entscheidung 07.09.2026).
 *
 * **Wer sie sieht, entscheidet der Server** (`GET /news`, `kern/releases.py`).
 * Dieselbe Regel wie beim Einrichtungs-Assistenten: Web und native App sollen
 * dieselbe Antwort bekommen, statt die Bedingung je Client nachzubauen.
 *
 * **Mehrere verpasste Releases.** Wer lange weg war, sieht das jüngste voll
 * und die älteren als Zeilen darunter; was über den Deckel hinausgeht, zählt
 * `older_count` und steht im Changelog. So wächst die Karte nicht mit der
 * Abwesenheit.
 *
 * **„Alles klar" setzt eine Hochwassermarke am Konto**, nicht im Browser: Auf
 * dem Telefon weggewischt heißt auch am Laptop weg. Gemeldet wird die
 * Version, die diese Karte GEZEIGT hat — käme zwischen Laden und Klick ein
 * Deploy, würde „die neueste" ein Release miterledigen, das niemand sah.
 */

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { vertrag, type ApiAntwort } from "@/lib/vertrag";
import { Button, Card } from "@/components/ui";
import { Mascot } from "@/components/mascot";

type NewsState = ApiAntwort<"/news">;

const NEWS_QUERY_KEY = ["news"] as const;

const KICKER =
  "font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-primary";

/** „2.3.0" → „2.3" — die Patch-Null sagt niemandem etwas. */
export function kurzVersion(version: string): string {
  return version.replace(/\.0$/, "");
}

/** Der Kicker über der Karte: eine Ausgabe nennt ihre Nummer, mehrere sagen,
 *  dass hier Liegengebliebenes steht. */
export function kickerText(versionen: string[]): string {
  if (versionen.length <= 1) {
    return `Neu bei Ratslotse · ${kurzVersion(versionen[0] ?? "")}`;
  }
  return `Neu seit deinem letzten Besuch · ${versionen.map(kurzVersion).join(" und ")}`;
}

export function ReleaseNewsCard() {
  const { user } = useAuth();
  const qc = useQueryClient();

  const { data } = useQuery({
    queryKey: NEWS_QUERY_KEY,
    queryFn: () => vertrag.get("/news"),
    enabled: !!user,
    // Eine Ausgabe erscheint ein paar Mal im Jahr — einmal je Sitzung reicht.
    staleTime: 60 * 60 * 1000,
  });

  const wegklicken = useMutation({
    mutationFn: (version: string) => api.post("/news/seen", { version }),
    // Optimistisch leeren: Die Karte soll beim Klick verschwinden, nicht nach
    // der Antwort. Ein Fehlschlag bringt sie beim nächsten Laden zurück —
    // besser, als eine weggewischte Karte stehen zu lassen.
    onMutate: () => {
      qc.setQueryData<NewsState>(NEWS_QUERY_KEY, (cur) =>
        cur ? { ...cur, releases: [], older_count: 0 } : cur);
    },
    onSettled: () => { void qc.invalidateQueries({ queryKey: NEWS_QUERY_KEY }); },
  });

  const releases = data?.releases ?? [];
  if (releases.length === 0) return null;

  const [neuestes, ...aeltere] = releases;
  const weitere = data?.older_count ?? 0;

  return (
    // `@container`: Die Karte steht im Hinweis-Slot über die volle Breite —
    // auf einem 1440er-Schirm sind das 1030 px. Ungeteilt lief jeder
    // Highlight-Satz dort über 147 Zeichen (im Browser gemessen). Gedeckelt
    // ließe das rechts ein Loch; zwei Spalten füllen die Fläche UND halbieren
    // die Zeile auf rund 70 Zeichen — „Spalten statt Deckel", DESIGNSPRACHE §4.
    <Card className="@container flex flex-col gap-4 border-primary/25 bg-primary/[0.04] p-4 sm:flex-row">
      {/* `hat-idee`: Lotti bringt etwas mit, sie warnt nicht. */}
      <Mascot decorative regung="hat-idee" className="hidden h-14 w-14 flex-none sm:block" />

      <div className="min-w-0 flex-1">
        <p className={KICKER}>
          <Sparkles className="mr-1 inline h-3 w-3 align-[-1px]" aria-hidden />
          {kickerText(releases.map((r) => r.version))}
        </p>
        <h2 className="mt-0.5 font-display text-base font-bold text-foreground">
          {neuestes.title}
        </h2>

        {/* Zwei Spalten erst, wenn wirklich Platz ist: Vier Highlights stehen
            dann als 2×2 statt als vier Zeilen quer über den Schirm. Unterhalb
            der Schwelle (Telefon, schmale Seitenspalte) bleibt es eine Spalte —
            zwei Stummel nebeneinander wären schlechter als eine lange Zeile. */}
        <ul className="mt-2.5 grid gap-x-8 gap-y-2.5 @2xl:grid-cols-2">
          {neuestes.highlights.map((h) => (
            <li key={h.url + h.title} className="min-w-0">
              <Link
                href={h.url}
                className="group block rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="text-sm font-semibold text-foreground [@media(hover:hover)]:group-hover:text-primary">
                  {h.title}
                  <ArrowRight
                    aria-hidden
                    className="ml-1 inline h-3.5 w-3.5 align-[-2px] text-primary transition-transform duration-fluss ease-out-strong [@media(hover:hover)]:group-hover:translate-x-0.5"
                  />
                </span>
                {/* Der Satz gehört zum Titel, nicht in eine zweite Spalte:
                    Auf dem Telefon ist die Karte 320 px breit. */}
                <span className="mt-0.5 block text-sm leading-relaxed text-muted-foreground">
                  {h.text}
                </span>
              </Link>
            </li>
          ))}
        </ul>

        {aeltere.length > 0 && (
          <div className="mt-3.5 border-t border-border pt-3">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
              Außerdem seit deinem letzten Besuch
            </p>
            <ul className="mt-1.5 flex flex-col gap-1">
              {aeltere.map((r) => (
                <li key={r.version} className="text-[13px] leading-snug text-muted-foreground">
                  <span className="font-semibold text-foreground">{kurzVersion(r.version)}</span>
                  {" — "}
                  {r.highlights.map((h) => h.title).join(" · ")}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2">
          <Button
            size="sm"
            onClick={() => wegklicken.mutate(neuestes.version)}
            disabled={wegklicken.isPending}
          >
            <Check className="!size-3.5" />
            Alles klar
          </Button>
          {/* „dieser Version" stimmt nur, wenn es wirklich eine ist — bei
              mehreren stünde dort ein falsches Versprechen. */}
          <Link href="/changelog" className="text-[13px] text-muted-foreground underline hover:text-foreground">
            {weitere > 0
              ? `Alle Änderungen — auch ${weitere} ältere Version${weitere === 1 ? "" : "en"}`
              : releases.length > 1
                ? "Alle Änderungen im Einzelnen"
                : "Alle Änderungen dieser Version"}
          </Link>
        </div>
      </div>
    </Card>
  );
}
